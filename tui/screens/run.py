"""
tui/screens/run.py — Écran d'encodage avec progression live.

Zone commande ffmpeg + ligne de retour live (non scrollable).

Depuis IE-100, l'écran **est** la file d'encodage : il vit dans son propre mode
Textual, reçoit les ajouts faits pendant qu'il tourne (`ajouter`), et `⌫`
rend la navigation sans rien arrêter.
"""
from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from enum import Enum, auto

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Label, ProgressBar, Static

from core.i18n import N_, _, ngettext, texte_erreur
from core.annexes import supprimer_annexes
from core.decision import (AudioAction, FileDecision, VideoAction,
                           resoudre_sorties)
from core.encoder import (
    EncoderProcess, audio_pass_needed, audio_prepass_needed,
    build_audio_command, build_command, diagnostiquer, encodeur_a_controler,
    pistes_audio_vides,
)
from core.muxer import (
    ExternalTrack, MuxProcess, TrackKind, build_mux_command, build_strip_command,
    needs_premux, mkvmerge_reussi, premux_output_path, premux_track_order,
)
from core.platform import PlatformProfile
from core.scanner import est_intermediaire
from ..common import (barre_etat, actions_ecran, colonne_fixe, footer_line2,
                      record_measured_speed,
                      retour_accueil)
from ..mixins import TableNavMixin
from ..widgets.entete import Entete
from ..widgets.footer import KeyFooter


# ─── État fichier ─────────────────────────────────────────────────────────────

def _a_muxer(dec: FileDecision) -> bool:
    """Rien à réencoder, des pistes à greffer : un mux. Pas sur un titre de
    disque — on n'écrit jamais dans le disque, et le titre n'est pas un
    fichier que mkvmerge recopie tel quel."""
    return (dec.video.action == VideoAction.SKIP and bool(dec.external_tracks)
            and dec.info.titre is None)


class FileState(Enum):
    PENDING  = auto()
    RUNNING  = auto()
    SUCCESS  = auto()
    ERROR    = auto()
    SKIPPED  = auto()


@dataclass
class FileRunStatus:
    decision:       FileDecision
    state:          FileState = FileState.PENDING
    percent:        float     = 0.0
    last_line:      str       = ""
    error_msg:      str       = ""
    _last_progress: object    = None  # ProgressInfo pour affichage ETA


# ─── Écran ────────────────────────────────────────────────────────────────────

class RunScreen(TableNavMixin, Screen):
    """Écran d'encodage séquentiel avec suivi progression."""

    BINDINGS = [
        Binding("p",         "pause_resume", N_("Pause / Resume"),  show=True),
        Binding("s",         "skip_current", N_("Skip the file"),   show=True),
        Binding("x",         "arreter_tout", N_("Stop all"),        show=True),
        # Veille, veille prolongée ou arrêt une fois tout fini : le choix est
        # dans les options, l'interrupteur repart à « non » à chaque lot.
        # `E` comme « ensuite » : `A` et `F` ont déjà leur sens (UX-12).
        Binding("e",         "apres_lot",    N_("After the batch"),  show=True),
        # La file se réordonne tant qu'un fichier attend (IE-100). `priority` :
        # le DataTable prendrait Ctrl+↑/↓ pour lui — comme sur la jonction.
        Binding("ctrl+up",   "monter",       N_("Move up"),         show=True, priority=True),
        Binding("ctrl+down", "descendre",    N_("Move down"),       show=True, priority=True),
        Binding("delete",    "retirer",      N_("Remove"),          show=True),
        # Retour à la navigation : l'encodage continue (IE-100). Arrêter est
        # une décision à part, `X`, qui demande confirmation.
        Binding("backspace", "go_back",      N_("Files"),           show=True),
        Binding("escape",    "go_back",      N_("Files"),           show=False, priority=True),
        # `priority` : un DataTable etouffe la touche avant les bindings —
        # meme avertissement qu'en tete de tui/mixins.py.
        Binding("ctrl+home", "accueil",   N_("Home"),       show=True,
                priority=True),
    ]

    DEFAULT_CSS = """
    RunScreen { layout: vertical; }
    #file-table {
        height: 1fr;
    }
    /* La commande ffmpeg s'enroule sur quatre lignes ou plus. À hauteur fixe,
       elle occupait toute la zone et chassait la ligne d'avancement en
       dessous : frame, fps, vitesse et temps restant devenaient invisibles
       pendant tout l'encodage. La zone suit désormais son contenu, la ligne
       d'avancement passe devant, et la commande cède la place quand la
       fenêtre est courte. */
    #cmd-zone {
        height: auto;
        max-height: 12;
        background: $panel;
        padding: 0 1;
        border-top: solid $primary;
        layout: vertical;
    }
    #ffmpeg-line {
        color: $text;
        height: 1;
        text-style: bold;
    }
    #cmd-lines {
        height: auto;
        color: $text-muted;
        width: 1fr;
    }
    #global-bar-row {
        height: 2;
        padding: 0 2;
        layout: horizontal;
    }
    #global-label {
        width: 12;
        padding-top: 0;
    }
    #global-bar {
        width: 1fr;
    }
    """

    def __init__(
        self,
        decisions: list[FileDecision],
        platform:  PlatformProfile,
    ) -> None:
        super().__init__()
        # Dernier moment avant l'écriture : les noms de sortie se figent ici,
        # une fois pour tout le lot. Au-delà, `output_path` ne bougera plus —
        # le nettoyage d'une sortie partielle en dépend.
        resoudre_sorties(decisions)
        self._platform  = platform
        self._statuses  = [
            FileRunStatus(decision=dec) for dec in decisions
        ]
        self._current_idx  = -1
        self._process:     EncoderProcess | None = None
        self._mux:         MuxProcess | None     = None
        self._paused       = False
        self._abandon      = False
        self._started      = False
        self._done         = False
        # Le worker lit la file pendant que la navigation y ajoute : le choix du
        # fichier suivant et l'ajout ne doivent pas se croiser, sinon un ajout
        # tombé juste après « plus rien à faire » serait perdu.
        self._verrou       = threading.Lock()
        # Le bilan d'un lot fini reste jusqu'à ce qu'on l'ait vu.
        self._vu           = False
        # L'action d'après lot (`E`). Jamais héritée d'un lot précédent : un
        # arrêt qu'on aurait oublié d'avoir demandé surprendrait des jours après.
        self.apres_lot     = False

    # ─── File (IE-100) ────────────────────────────────────────────────────────

    @property
    def termine(self) -> bool:
        return self._done

    @property
    def statuts(self) -> list[FileRunStatus]:
        return self._statuses

    def sources_en_file(self) -> set[Path]:
        return {s.decision.info.path for s in self._statuses
                if s.state in (FileState.PENDING, FileState.RUNNING)}

    def en_attente(self) -> int:
        return sum(1 for s in self._statuses
                   if s.state == FileState.PENDING
                   and s.decision.video.action != VideoAction.SKIP)

    def ajouter(self, decisions: list[FileDecision]) -> bool:
        """Met des décisions en fin de file. Faux si le lot est déjà fini."""
        with self._verrou:
            if self._done or self._abandon:
                return False
            # Les noms déjà figés sont réservés : un ajout ne peut pas viser la
            # sortie d'un fichier qui attend encore.
            resoudre_sorties([s.decision for s in self._statuses] + decisions)
            self._statuses.extend(FileRunStatus(decision=d) for d in decisions)
        self._reconstruire_table()
        self._update_header()
        return True

    def compose(self) -> ComposeResult:
        yield Entete()
        yield Static("", id="run-header-bar", classes="status-bar")
        yield DataTable(id="file-table", cursor_type="row", zebra_stripes=True)
        with Static(id="global-bar-row"):
            yield Label(_("Overall"), id="global-label")
            yield ProgressBar(total=100, show_eta=False, id="global-bar")
        with Static(id="cmd-zone"):
            # L'avancement d'abord : c'est la seule ligne qui change, et la
            # seule dont l'absence se remarque.
            yield Static("", id="ffmpeg-line", markup=False)
            yield Static("", id="cmd-lines", markup=False)
        yield KeyFooter(
            actions=actions_ecran(self),
            nav=footer_line2(nav=True, accueil=True, extra=(("backspace", N_("Files")),)),
        )

    def on_mount(self) -> None:
        # L'accueil rafraîchit sa vue et décoche ce qui a réussi à son retour.
        self.app.lots_encodes.append(self._statuses)  # type: ignore[attr-defined]
        self._build_table()
        self._update_header()
        self.action_start()

    def on_screen_resume(self) -> None:
        if self._done:
            self._vu = True

    def on_screen_suspend(self) -> None:
        # Quitté après avoir montré son bilan : le lot peut partir. Une modale
        # ouverte par-dessus suspend aussi l'écran — l'application vérifie
        # qu'on a bien changé de mode avant de le retirer.
        if self._done and self._vu:
            self.app.call_later(self.app._liberer_lot)  # type: ignore[attr-defined]

    def _reconstruire_table(self) -> None:
        try:
            table  = self.query_one(DataTable)
        except Exception:
            return
        curseur = table.cursor_row
        table.clear(columns=True)
        self._build_table()
        for i in range(len(self._statuses)):
            self._update_row(i)
        if table.row_count:
            table.move_cursor(row=min(curseur, table.row_count - 1))

    # ─── Table ────────────────────────────────────────────────────────────────

    def _build_table(self) -> None:
        table = self.query_one(DataTable)

        def _cw(header: str, vals: list[str]) -> int:
            return max(len(header), max((len(v) for v in vals), default=0))

        names   = [s.decision.info.path.name for s in self._statuses]
        actions = [s.decision.video.label()  for s in self._statuses]

        table.add_column("",        width=3,                              key="icon")
        fichier, action = _("File"), _("Action")
        table.add_column(fichier, width=max(20, _cw(fichier, names)), key="file")
        table.add_column(action,  width=_cw(action, actions),         key="action")
        colonne_fixe(table, _("State"),    50,     key="state")

        for i, s in enumerate(self._statuses):
            dec   = s.decision
            name  = dec.info.path.name
            action_label = dec.video.label()
            table.add_row(
                self._icon(s),
                Text(name, overflow="ellipsis", no_wrap=True),
                Text(action_label, style=dec.video.style()),
                _("pending"),
                key=str(i),
            )

    def _icon(self, s: FileRunStatus) -> str:
        return {
            FileState.PENDING:  "○",
            FileState.RUNNING:  "▶",
            FileState.SUCCESS:  "✓",
            FileState.ERROR:    "✗",
            FileState.SKIPPED:  "—",
        }[s.state]

    def _update_row(self, index: int) -> None:
        try:
            s     = self._statuses[index]
            table = self.query_one(DataTable)

            # Gère le cas où la durée est inconnue (percent = -1)
            if s.state == FileState.RUNNING:
                if s.percent < 0:
                    running_txt = _("running…")
                else:
                    # Affiche : "45% (2m30s / 3m45s · 3.71x)"
                    prog_pct = f"{s.percent * 100:.0f}%"
                    if hasattr(s, '_last_progress') and s._last_progress:
                        elapsed = s._last_progress.format_elapsed()
                        remaining = s._last_progress.format_remaining()
                        speed = f"{s._last_progress.speed:.2f}x"
                        running_txt = f"{prog_pct} ({elapsed} / {remaining} · {speed})"
                    else:
                        running_txt = prog_pct
                state_txt = Text(running_txt, style="yellow")
            else:
                state_txt = {
                    FileState.PENDING:  Text(_("pending"),      style="dim"),
                    # Le symbole est déjà dans la colonne d'icône (UX-16).
                    # Minuscules, comme « en attente » et « ignoré » (UX-09).
                    FileState.SUCCESS:  Text(_("done"),          style="bold green"),
                    FileState.ERROR:    Text(_("failed: {error}").format(error=s.error_msg[:30]),
                                             style="bold dark_orange"),
                    FileState.SKIPPED:  Text(_("skipped"),       style="dim"),
                }[s.state]
            table.update_cell(str(index), "icon",  self._icon(s),  update_width=False)
            table.update_cell(str(index), "state", state_txt,       update_width=False)
        except Exception:
            pass

    def _update_header(self) -> None:
        """L'avancement global, fichiers terminés **et** fichier en cours.

        Le compte ne portait que sur les fichiers achevés : sur un encodage
        d'un seul fichier — le cas ordinaire depuis l'assistant — la barre
        restait à 0 % pendant deux heures, puis passait à 100 %. Le fichier
        affichait pourtant 69 % dans sa ligne : deux chiffres contradictoires
        à l'écran, dont le plus visible était le faux.
        """
        try:
            done, total, bar_pct = self.avancement()
            apres = ""
            if self.apres_lot and not self._done:
                from core.config import get_action_fin
                from core.veille import libelle_action
                apres = _("After the batch: {action}").format(
                    action=libelle_action(get_action_fin(self.app.cfg)))  # type: ignore[attr-defined]
            self.query_one("#run-header-bar", Static).update(barre_etat(
                _("Encoding"),
                ngettext("{count} file", "{count} files", total).format(count=total),
                ngettext("{done}/{total} done", "{done}/{total} done",
                         done).format(done=done, total=total),
                _("Overall: {percent}%").format(percent=bar_pct),
                apres,
            ))
            self.query_one("#global-bar", ProgressBar).progress = bar_pct
        except Exception:
            pass

    def avancement(self) -> tuple[int, int, int]:
        """(terminés, total, pourcentage global) — l'écran et l'en-tête."""
        finis   = {FileState.SUCCESS, FileState.ERROR, FileState.SKIPPED}
        total   = len(self._statuses)
        done    = sum(1 for s in self._statuses if s.state in finis)
        # `percent` vaut -1 tant que ffmpeg n'a pas rendu de durée : une
        # progression inconnue compte pour rien, jamais pour du négatif.
        encours = sum(min(1.0, max(0.0, s.percent))
                      for s in self._statuses if s.state not in finis)
        return done, total, int((done + encours) / total * 100) if total else 0

    def _update_cmd_lines(self, text: str) -> None:
        try:
            self.query_one("#cmd-lines", Static).update(text)
        except Exception:
            pass

    def _update_ffmpeg_line(self, text: str) -> None:
        try:
            self.query_one("#ffmpeg-line", Static).update(text)
        except Exception:
            pass

    # ─── Encodage ─────────────────────────────────────────────────────────────

    def action_start(self) -> None:
        if self._started:
            return
        self._started = True
        self._encode_next()

    @work(thread=True, name="encoder")
    def _encode_next(self) -> None:
        # Lot abandonné (⌫, Ctrl+Home) : rien ne démarre plus.
        if self._abandon:
            return

        # Cherche le prochain fichier à encoder. Sous verrou : un ajout ne doit
        # pas tomber entre « plus rien » et « lot fini ». Aucun appel au fil
        # principal sous verrou — il peut attendre ce même verrou dans `ajouter`.
        ignores: list[int] = []
        with self._verrou:
            next_idx = self._current_idx + 1
            while next_idx < len(self._statuses):
                s   = self._statuses[next_idx]
                dec = s.decision
                # Un SKIP qui porte des greffes est un mux, pas un fichier à
                # ignorer (CR-82).
                if dec.video.action == VideoAction.SKIP and not _a_muxer(dec):
                    s.state = FileState.SKIPPED
                    ignores.append(next_idx)
                    next_idx += 1
                    continue
                break
            else:
                self._done = True
            if not self._done:
                self._current_idx = next_idx
                s = self._statuses[next_idx]
                s.state = FileState.RUNNING
        for i in ignores:
            self.app.call_from_thread(self._update_row, i)
        if self._done:
            self.app.call_from_thread(self._on_all_done)
            return
        self.app.call_from_thread(self._update_row, next_idx)

        if _a_muxer(dec):
            self._muxer(next_idx, dec)
            return

        # Un titre de Blu-ray fait de plusieurs clips, un titre de DVD : il est
        # d'abord extrait en Matroska, tout ce qui suit lit l'extraction
        # (IE-120, IE-121).
        titre = dec.info.titre
        if titre is not None and titre.a_extraire and dec.encode_source is None:
            if dec.video.action in (VideoAction.STRIP_DV, VideoAction.ENCODE_DV):
                s.state     = FileState.ERROR
                s.error_msg = _("Dolby Vision: single-clip titles only")
                s.last_line = (_("This Blu-ray title plays only part of its clip: "
                                 "its Dolby Vision cannot be kept. Choose a "
                                 "re-encode without Dolby Vision in guided mode.")
                               if titre.partiel and len(titre.clips) == 1 else
                               _("This Blu-ray title spans {count} clips: its Dolby "
                                 "Vision cannot be kept. Choose a re-encode without "
                                 "Dolby Vision in guided mode.").format(
                                    count=len(titre.clips)))
                self.app.call_from_thread(self._update_row, next_idx)
                self._encode_next()
                return
            if not self._remux_titre(next_idx, dec):
                self._encode_next()
                return

        # Retrait du Dolby Vision seul : aucun réencodage, donc aucun appel à
        # build_command. Le fichier suivant est enchaîné par _strip_dv.
        if dec.video.action == VideoAction.STRIP_DV:
            self._strip_dv(next_idx, dec)
            return

        # Réencodage préservant le Dolby Vision : le RPU sort avant, revient
        # après. build_command ne sait pas faire — il produirait un `-c:v copy`.
        if dec.video.action == VideoAction.ENCODE_DV:
            self._encode_dv(next_idx, dec)
            return

        # Une piste étirée ne peut pas être absorbée par ffmpeg : mkvmerge la
        # greffe d'abord, ffmpeg encode l'intermédiaire. Transparent pour
        # l'utilisateur, et payé seulement quand c'est nécessaire.
        if needs_premux(dec.external_tracks) and not self._premux(next_idx, dec):
            self._liberer(dec)
            self._encode_next()
            return

        # Transcoder une piste audio pendant qu'on recopie un sous-titre au
        # premier repère tardif fait perdre la piste, sans un mot. On la
        # produit donc à part, et la passe d'encodage la recopie.
        audio_tmp: Path | None = None
        if audio_prepass_needed(dec):
            audio_tmp = self._audio_prepass(next_idx, dec)
            if audio_tmp is None:
                self._liberer(dec)
                self._encode_next()
                return

        # Un long silence dans un sous-titre fausse ses temps en MP4 : voir
        # `core/sous_titres.py`.
        ok, porteur = self._porter_sous_titres(next_idx, dec)
        if not ok:
            self._liberer(dec, audio_tmp)
            self._encode_next()
            return

        chapitres = self._ecrire_chapitres(dec)
        try:
            cmd = build_command(dec, self._platform, audio_source=audio_tmp,
                                sous_titres_porteur=porteur, chapitres=chapitres)
        except ValueError as e:
            s.state     = FileState.ERROR
            s.last_line = texte_erreur(e)
            s.error_msg = texte_erreur(e)[:60]
            self.app.call_from_thread(self._update_row, next_idx)
            self._liberer(dec, audio_tmp, porteur, chapitres)
            self._encode_next()  # passe au suivant
            return
        self.app.call_from_thread(
            self._update_cmd_lines,
            " ".join(cmd),
        )

        # Le sondage du démarrage a déjà répondu : inutile de lancer ffmpeg
        # pour apprendre ce qu'on sait, ni de laisser l'utilisateur lire
        # « Error opening output files » à la place de la cause.
        choisi = encodeur_a_controler(cmd)
        if choisi and self._platform.peut_encoder(choisi) is False:
            s.state     = FileState.ERROR
            s.error_msg = _("{encoder} unavailable here").format(encoder=choisi)[:60]
            if "nvenc" in choisi and self._platform.alerte_nvenc:
                s.last_line = self._platform.alerte_nvenc
            else:
                s.last_line = _(
                    "This machine cannot encode with “{encoder}” — probed at "
                    "startup. AV1 through NVENC needs an RTX 40 or newer; HEVC "
                    "and H264 remain available.").format(encoder=choisi)
            self.app.call_from_thread(self._update_row, next_idx)
            self._liberer(dec, audio_tmp, porteur, chapitres)
            self._encode_next()
            return

        proc = EncoderProcess(cmd, dec.info.duration)
        self._demarrer(proc)

        # Affiche "Encodage lancé" jusqu'à première ligne
        self.app.call_from_thread(
            self._update_ffmpeg_line,
            "▶ " + _("Encoding started, initializing…")
        )
        s.percent = -1  # Force "en cours…" au lieu de "0%"
        self.app.call_from_thread(self._update_row, next_idx)

        # Affiche toutes les lignes (avec ou sans progression)
        journal: list[str] = []
        for line, progress in proc.iter_progress():
            s.last_line = line
            # Les dernières lignes suffisent : la cause précède toujours le
            # constat d'échec de quelques lignes.
            journal.append(line)
            del journal[:-40]
            if progress:
                s.percent = progress.percent
                s._last_progress = progress  # Stocke pour affichage ETA
                # Formate une ligne de statut enrichie pour ffmpeg-line
                display_line = (
                    f"frame={progress.frame} fps={progress.fps:.1f} "
                    f"elapsed={progress.format_elapsed()} remaining≈{progress.format_remaining()} "
                    f"speed={progress.speed:.2f}x bitrate={progress.bitrate:.0f}kbits/s"
                )
            else:
                display_line = line
            self.app.call_from_thread(
                self._update_ffmpeg_line,
                display_line
            )
            # Met à jour row et header seulement si progression
            if progress:
                self.app.call_from_thread(self._update_row, next_idx)
                self.app.call_from_thread(self._update_header)

        rc = proc.wait()
        success = rc == 0

        # ffmpeg peut rendre un code nul et un fichier amputé d'une piste
        # audio — voir `encoder.audio_prepass_needed`. Le succès se vérifie,
        # il ne se déduit pas du code de retour.
        if success and dec.output_path.exists():
            vide = self._audio_vide(dec, dec.output_path)
            if vide:
                success = False
                s.last_line = vide

        # Une sortie qui n'a pas abouti — échec de ffmpeg, piste vidée, `S` —
        # porterait le nom d'une sortie réussie : Jellyfin l'indexerait, le
        # réessai écrirait à côté un `(2)`. Le nom est le nôtre, figé à la mise
        # en file sur un fichier qui n'existait pas (CR-57).
        if not success or s.state == FileState.SKIPPED:
            try:
                dec.output_path.unlink(missing_ok=True)
            except OSError:
                pass

        if success and s._last_progress:
            self.app.call_from_thread(record_measured_speed, self.app.cfg,  # type: ignore[attr-defined]
                                      dec.video.action, s._last_progress.speed)

        if success:
            self._supprimer_source(dec, s)

        # Les pistes audio produites à part ont été recopiées dans la sortie,
        # les sous-titres réécrits aussi ; l'intermédiaire d'un mux préalable
        # ou d'un titre n'a plus de raison d'être.
        self._liberer(dec, audio_tmp, porteur, chapitres)
        if success:
            # Une piste recalée a été recopiée dans la sortie (CR-93).
            for ext in dec.external_tracks:
                if est_intermediaire(ext.source_path.stem):
                    try:
                        ext.source_path.unlink(missing_ok=True)
                    except OSError:
                        pass

        # Préserve l'état SKIPPED posé par action_skip_current()
        if s.state != FileState.SKIPPED:
            s.state = FileState.SUCCESS if success else FileState.ERROR
            if not success:
                cause = diagnostiquer(journal)
                s.error_msg = (cause or s.last_line)[:60]
                if cause:
                    # Le détail complet reste sous les yeux, sous la cause.
                    s.last_line = (cause + "  —  "
                                   + _("ffmpeg: {detail}").format(detail=s.last_line))

        self.app.call_from_thread(self._update_row, next_idx)
        self.app.call_from_thread(self._update_header)
        self._process = None

        # Enchaîne le suivant
        self._encode_next()

    @staticmethod
    def _audio_vide(dec: FileDecision, sortie: Path) -> str:
        """Le message d'échec si une piste audio de `sortie` est vide, sinon "".

        Le succès se vérifie, il ne se déduit pas du code de retour : voir
        `encoder.audio_prepass_needed`. Les chemins Dolby Vision ne le
        vérifiaient pas (CR-65) — le retrait vers MP4 transcode pourtant l'audio
        dans la même passe que les sous-titres.
        """
        vides = pistes_audio_vides(sortie, dec.info.duration)
        if not vides:
            return ""
        # Le bloc de conclusion retronque `last_line` dans `error_msg` :
        # l'essentiel doit tenir dans les soixante premiers caractères.
        return _(
            "Empty audio track in the output: {tracks}. The encode "
            "nevertheless finished without error. The file is unusable "
            "as it is, and this case is outside the known scope — "
            "please report it.").format(tracks=" · ".join(vides))

    def _supprimer_source(self, dec: FileDecision, s: FileRunStatus) -> None:
        """Supprime la source d'une sortie réussie, si le profil le demande.

        Une seule règle pour tous les chemins (CR-54). Les chemins Dolby Vision
        refaisaient la leur : ils effaçaient le `.m2ts` d'un titre de Blu-ray et
        laissaient le `.nfo` et les images Jellyfin d'un fichier. Et ils
        supprimaient avant de regarder si `S` avait abandonné le fichier — la
        sortie, abandonnée, était effacée ensuite : on perdait les deux.
        """
        if s.state == FileState.SKIPPED:
            return
        voulu = (dec.delete_source_override
                 if dec.delete_source_override is not None
                 else dec.profile.get("delete_source", False))
        # Un titre de disque ne se supprime pas : ce sont les fichiers du disque.
        if not voulu or dec.info.titre is not None:
            return
        try:
            dec.info.path.unlink()
        except OSError:
            return
        # Son .nfo et ses images Jellyfin ne décrivent plus rien (IE-116).
        supprimer_annexes(dec.info.path)

    def _liberer(self, dec: FileDecision, *tmps: Optional[Path]) -> None:
        """Efface les intermédiaires d'un fichier, que le traitement ait abouti
        ou non : ils pèsent le poids du film et se refabriquent. Appelé sur
        **chaque** sortie de la passe principale — une sortie anticipée laissait
        l'assemblage d'un titre dans le dossier de sortie (CR-58)."""
        for tmp in tmps:
            if tmp is not None:
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass                  # tenu par un lecteur : on n'insiste pas
        if dec.encode_source is not None:
            try:
                dec.encode_source.unlink(missing_ok=True)
            except OSError:
                pass
            dec.encode_source = None
            # L'intermédiaire d'un mux préalable parti, la greffe redevient à
            # faire : sans ce retour, un second essai produirait un fichier sans
            # les pistes. L'assemblage d'un titre, lui, n'en a déplacé aucune.
            if dec.premuxed_tracks:
                dec.external_tracks = dec.premuxed_tracks
                dec.premuxed_tracks = []

    def _audio_prepass(self, index: int, dec: FileDecision) -> Optional[Path]:
        """Produit les pistes audio finales avant l'encodage. None si échec.

        Voir `encoder.audio_prepass_needed` pour le défaut ffmpeg que cette
        passe contourne. Elle ne coûte que le temps d'un transcodage audio,
        là où la passe vidéo se compte en heures.
        """
        s   = self._statuses[index]
        src = dec.encode_source or dec.info.lecture
        # Avec l'intermédiaire d'un mux préalable (dossier temporaire), à côté
        # de lui ; sinon dans le dossier de sortie — celui de la source peut
        # être en lecture seule (IE-118).
        dossier = src.parent if dec.encode_source else dec.dossier_sortie
        out = dossier / f"{src.stem}.iris_audio.mka"
        cmd = build_audio_command(src, out, dec.audio,
                                  getattr(self.app, "ffmpeg_path", "ffmpeg"))
        self.app.call_from_thread(self._update_cmd_lines, " ".join(cmd))
        self.app.call_from_thread(
            self._update_ffmpeg_line,
            "▶ " + _("Audio tracks prepared separately — see the release notes…"))
        s.percent = -1
        self.app.call_from_thread(self._update_row, index)

        proc = EncoderProcess(cmd, dec.info.duration)
        self._demarrer(proc)
        for ligne, progress in proc.iter_progress():
            s.last_line = ligne
            if progress:
                s.percent = progress.percent
                self.app.call_from_thread(self._update_row, index)
        code = proc.wait()
        self._process = None

        if code != 0 or not out.exists():
            s.state     = FileState.ERROR
            s.error_msg = _("audio preparation: code {code}").format(code=code)[:60]
            s.last_line = _("Preparing the audio tracks failed (code {code}).").format(
                code=code)
            self.app.call_from_thread(self._update_row, index)
            out.unlink(missing_ok=True)
            return None
        return out

    def _porter_sous_titres(self, index: int, dec: FileDecision,
                            recompose: Optional[Path] = None,
                            ) -> tuple[bool, Optional[Path]]:
        """Les sous-titres texte d'une sortie MP4, réécrits s'il le faut.

        Rend (réussite, porteur). Le porteur est None quand aucune piste n'a
        de silence assez long pour le défaut de `core/sous_titres.py` : la
        commande lit alors la source comme avant. Le coût est une lecture de
        la source, payée seulement par les sorties MP4 qui gardent du texte.
        Les sous-titres greffés y passent aussi (CR-34) : extraits un par un,
        décalage et jeu de caractères appliqués — ou lus dans `recompose`, le
        Matroska des chemins DV, où mkvmerge les a déjà recalés et étirés.
        """
        from core import sous_titres as st_mod

        s       = self._statuses[index]
        pistes  = st_mod.pistes_a_porter(dec)
        try:
            greffes = st_mod.greffes_a_porter(dec, recompose)
        except ValueError as e:          # piste introuvable (CR-27)
            s.state, s.error_msg = FileState.ERROR, _("subtitles: preparation failed")
            s.last_line = texte_erreur(e)
            self.app.call_from_thread(self._update_row, index)
            return False, None
        if not pistes and not greffes:
            return True, None
        source  = dec.encode_source or dec.info.lecture
        ffmpeg  = getattr(self.app, "ffmpeg_path", "ffmpeg")
        porteur = dec.dossier_sortie / f"{source.stem}.iris_st.mkv"
        travaux: list[tuple[list[str], list[Path]]] = []
        if pistes:
            travaux.append(st_mod.build_extraction(source, pistes,
                                                   dec.dossier_sortie, ffmpeg))
        for n, g in enumerate(greffes):
            chemin = dec.dossier_sortie / f"{source.stem}.iris_stg{n}.srt"
            travaux.append((st_mod.build_extraction_greffe(g, chemin, ffmpeg),
                            [chemin]))
        srts = [c for _cmd, chemins in travaux for c in chemins]

        def echouer(detail: str) -> tuple[bool, None]:
            porteur.unlink(missing_ok=True)
            if s.state == FileState.SKIPPED:      # `S` ou `X` (CR-61)
                return False, None
            s.state, s.error_msg = FileState.ERROR, _("subtitles: preparation failed")
            s.last_line = detail
            self.app.call_from_thread(self._update_row, index)
            return False, None

        try:
            self.app.call_from_thread(
                self._update_ffmpeg_line,
                "▶ " + _("Reading the subtitles — a long silence skews their "
                         "timings in MP4…"))
            s.percent = -1
            self.app.call_from_thread(self._update_row, index)
            for cmd, chemins in travaux:
                self.app.call_from_thread(self._update_cmd_lines, " ".join(cmd))
                proc = EncoderProcess(cmd, dec.info.duration)
                self._demarrer(proc)
                for ligne, progress in proc.iter_progress():
                    s.last_line = ligne
                    if progress:
                        s.percent = progress.percent
                        self.app.call_from_thread(self._update_row, index)
                code = proc.wait()
                self._process = None
                if code != 0 or not all(p.exists() for p in chemins):
                    return echouer(_("Extracting the subtitles failed (code {code}).").format(
                        code=code))

            combles = 0
            for chemin in srts:
                texte, n = st_mod.combler_srt(chemin.read_text(encoding="utf-8"))
                if n:
                    chemin.write_text(texte, encoding="utf-8")
                combles += n
            if not combles:
                return True, None

            cmd = st_mod.build_porteur(pistes + [g.piste for g in greffes],
                                       srts, porteur, ffmpeg)
            self.app.call_from_thread(self._update_cmd_lines, " ".join(cmd))
            r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                               encoding="utf-8", errors="replace", timeout=300)
            if r.returncode != 0 or not porteur.exists():
                return echouer(_("Grouping the subtitles failed: {detail}").format(
                    detail=(r.stderr.strip().splitlines() or ["?"])[-1]))
            return True, porteur
        finally:
            for chemin in srts:
                chemin.unlink(missing_ok=True)

    def _executer(self, index: int, proc) -> int:
        """Une étape des chemins DV, publiée comme les autres : `S`, `X`,
        la pause et la sortie l'atteignent, et aucun délai fixe ne la tue
        (CR-32, CR-61). La progression, quand le processus en donne."""
        s = self._statuses[index]
        self._demarrer(proc)
        for ligne, progress in proc.iter_progress():
            if ligne:
                s.last_line = ligne
            if progress:
                s.percent = progress.percent
                self.app.call_from_thread(self._update_row, index)
        code = proc.wait()
        self._process = None
        return code

    @staticmethod
    def _playlist_chapitres(dec: FileDecision) -> Optional[Path]:
        """La playlist d'un titre de Blu-ray à chapitres, où mkvmerge les lit
        (CR-63). La règle de `ffmetadata_chapitres` : deux au moins."""
        titre = dec.info.titre
        if titre is None or titre.est_dvd or len(titre.chapitres) < 2:
            return None
        return titre.chemin

    def _transcoder_greffes(self, index: int, dec: FileDecision,
                            produits: list[Path]) -> Optional[list[ExternalTrack]]:
        """Les pistes greffées d'un chemin DV, l'audio à la règle du profil.

        mkvmerge ne sait que recopier : un DTS greffé sortait en DTS, quand la
        passe principale le transcode (IE-125). Chaque piste que la règle
        transcode passe par ffmpeg vers un Matroska audio, qui remplace son
        donneur (piste 0) ; décalage, étirement, langue et drapeaux restent à
        mkvmerge. Les fichiers produits sont ajoutés à `produits`, à effacer
        par l'appelant. None si une transcription échoue ou si `S` l'abandonne.

        L'ordre est celui de `premux_track_order` : mkvmerge range les pistes
        par donneur, et un donneur qui perd son audio au profit d'un `.mka`
        doit garder sa place — les sous-titres du Matroska recomposé sont lus
        dans cet ordre (`greffes_a_porter`).
        """
        from dataclasses import replace
        from core.decision import audio_greffee

        s      = self._statuses[index]
        ffmpeg = getattr(self.app, "ffmpeg_path", "ffmpeg")
        pistes: list[ExternalTrack] = []
        for n, ext in enumerate(premux_track_order(dec.external_tracks)):
            if ext.kind != TrackKind.AUDIO:
                pistes.append(ext)
                continue
            ad = audio_greffee(ext, dec.profile)
            if ad.action != AudioAction.TRANSCODE:
                pistes.append(ext)
                continue
            mka = dec.dossier_sortie / f"{dec.info.lecture.stem}.iris_greffe{n}.mka"
            produits.append(mka)
            cmd = build_audio_command(ext.source_path, mka, [ad], ffmpeg)
            self.app.call_from_thread(self._update_cmd_lines, " ".join(cmd))
            self.app.call_from_thread(
                self._update_ffmpeg_line,
                "▶ " + _("Transcoding the added audio track “{name}”…").format(
                    name=ext.source_path.name))
            s.percent = -1
            self.app.call_from_thread(self._update_row, index)
            proc = EncoderProcess(cmd, dec.info.duration)
            self._demarrer(proc)
            for ligne, progress in proc.iter_progress():
                s.last_line = ligne
                if progress:
                    s.percent = progress.percent
                    self.app.call_from_thread(self._update_row, index)
            code = proc.wait()
            self._process = None
            if s.state == FileState.SKIPPED:
                return None
            if code != 0 or not mka.exists():
                s.state     = FileState.ERROR
                s.error_msg = _("audio transcoding: code {code}").format(code=code)[:60]
                s.last_line = _("Transcoding the added audio track “{name}” failed "
                                "(code {code}).").format(name=ext.source_path.name,
                                                         code=code)
                self.app.call_from_thread(self._update_row, index)
                return None
            pistes.append(replace(ext, source_path=mka, source_tid=0,
                                  track_name=ad.output_title or ext.track_name))
        return pistes

    def _strip_dv(self, index: int, dec: FileDecision) -> None:
        """Retire le RPU Dolby Vision sans réencoder, puis passe au suivant.

        Trois étapes, aucune image recalculée : ffmpeg recopie le flux HEVC,
        dovi_tool en retire les NAL du RPU, mkvmerge remuxe avec les pistes de
        la source. La sortie décode bit à bit comme l'entrée, et le HDR10+
        éventuel survit — ce qu'aucun réencodage ne permet.
        """
        from core import dovi

        s      = self._statuses[index]
        source = dec.info.lecture
        sortie = dec.output_path

        def echouer(resume: str, detail: str) -> None:
            # `S` ou `X` a déjà tranché : l'étape interrompue échoue, mais le
            # fichier reste abandonné, comme le bilan l'affiche (CR-61).
            if s.state == FileState.SKIPPED:
                return
            s.state, s.error_msg, s.last_line = FileState.ERROR, resume[:60], detail
            self.app.call_from_thread(self._update_row, index)

        dovi_path = getattr(self.app, "dovi_path", None)
        if dovi_path is None or not getattr(self.app, "mkvmerge_available", False):
            echouer(_("dovi_tool + mkvmerge required"),
                    _("Removing Dolby Vision needs dovi_tool and mkvmerge. Run "
                      "the preflight again to install them."))
            self._encode_next()
            return

        # Les intermédiaires pèsent le poids du film : les poser à côté de la
        # sortie, sur le même volume, plutôt que dans le temp du système —
        # 30 Go de flux brut n'ont pas leur place sur le disque du système.
        brut = dec.dossier_sortie / f"{source.stem}.iris_bl.hevc"
        nodv = dec.dossier_sortie / f"{source.stem}.iris_nodv.hevc"
        # Les pistes audio finales, quand la décision demande un transcodage.
        # mkvmerge ne sait que recopier : sans ce fichier, le TrueHD annoncé
        # « → E-AC3 » sortait en TrueHD.
        mka  = dec.dossier_sortie / f"{source.stem}.iris_audio.mka"
        # Le MP4 est recomposé par ffmpeg en une passe depuis la source : le
        # filtre `dovi_rpu` retire le RPU, l'audio se transcode au passage.
        # Avec des greffes, ffmpeg ne saurait ni les étirer ni les recaler
        # comme mkvmerge : les pistes greffées disparaissaient, l'encodage
        # était déclaré réussi (CR-55). mkvmerge recompose alors un Matroska,
        # que ffmpeg passe en MP4 — le chemin du réencodage DV.
        mp4    = dec.output_container == ".mp4"
        direct = mp4 and not dec.external_tracks
        mkv    = (dec.dossier_sortie / f"{source.stem}.iris_strip.mkv"
                  if mp4 and not direct else sortie)
        porteur: Optional[Path] = None
        chapitres: Optional[Path] = None
        produits: list[Path] = []
        ffmpeg_path = getattr(self.app, "ffmpeg_path", "ffmpeg")
        if direct and not dovi.strip_bsf_disponible(ffmpeg_path):
            echouer(_("ffmpeg 7.1+ required (dovi_rpu filter)"),
                    _("Removing Dolby Vision to MP4 needs the dovi_rpu filter, "
                      "which came with ffmpeg 7.1. Update ffmpeg from the "
                      "preflight."))
            self._encode_next()
            return
        passe_audio = not direct and audio_pass_needed(dec.audio)
        n_etapes = 1 if direct else (4 if passe_audio else 3) + (mkv != sortie)
        s.percent = -1

        try:
            # Le MP4 direct n'a pas d'intermédiaire : sa passe unique est la
            # dernière.
            if not direct:
                # 1/N — extraction du flux HEVC (copie)
                cmd = dovi.build_extract_hevc_command(
                    source, brut, getattr(self.app, "ffmpeg_path", "ffmpeg"),
                    quiet=False)
                self.app.call_from_thread(self._update_cmd_lines, " ".join(cmd))
                self.app.call_from_thread(
                    self._update_ffmpeg_line,
                    f"▶ 1/{n_etapes} " + _("Extracting the HEVC stream — copy, no "
                                           "re-encoding…"))
                self.app.call_from_thread(self._update_row, index)

                proc = EncoderProcess(cmd, dec.info.duration)
                self._demarrer(proc)
                for ligne, progress in proc.iter_progress():
                    s.last_line = ligne
                    if progress:
                        s.percent = progress.percent
                        self.app.call_from_thread(self._update_row, index)
                        self.app.call_from_thread(self._update_header)
                code = proc.wait()
                self._process = None

                if s.state == FileState.SKIPPED:
                    return
                if code != 0 or not brut.exists():
                    echouer(_("HEVC extraction: code {code}").format(code=code),
                            _("Extracting the HEVC stream failed (code {code}).").format(
                                code=code))
                    return

                # 2/N — retrait du RPU
                cmd = dovi.build_remove_command(brut, nodv, dovi_path)
                self.app.call_from_thread(self._update_cmd_lines, " ".join(cmd))
                self.app.call_from_thread(
                    self._update_ffmpeg_line,
                    f"▶ 2/{n_etapes} " + _("Removing the Dolby Vision RPU with dovi_tool…"))
                s.percent = -1
                self.app.call_from_thread(self._update_row, index)

                code = self._executer(index, EncoderProcess(cmd))
                if s.state == FileState.SKIPPED:
                    return
                if code != 0 or not nodv.exists():
                    echouer(_("dovi_tool remove failed"),
                            _("dovi_tool could not remove the RPU from the stream."))
                    return

            # 3/4 — pistes audio finales, quand la décision en transcode une.
            if passe_audio:
                cmd = build_audio_command(
                    source, mka, dec.audio,
                    getattr(self.app, "ffmpeg_path", "ffmpeg"))
                self.app.call_from_thread(self._update_cmd_lines, " ".join(cmd))
                self.app.call_from_thread(
                    self._update_ffmpeg_line,
                    f"▶ 3/{n_etapes} " + _("Transcoding the audio tracks…"))
                s.percent = -1
                self.app.call_from_thread(self._update_row, index)

                proc = EncoderProcess(cmd, dec.info.duration)
                self._demarrer(proc)
                for ligne, progress in proc.iter_progress():
                    s.last_line = ligne
                    if progress:
                        s.percent = progress.percent
                        self.app.call_from_thread(self._update_row, index)
                code = proc.wait()
                self._process = None

                if s.state == FileState.SKIPPED:
                    return
                if code != 0 or not mka.exists():
                    echouer(_("audio transcoding: code {code}").format(code=code),
                            _("Transcoding the audio tracks failed (code "
                              "{code}).").format(code=code))
                    return

            # N/N — remux avec les pistes de la source. mkvmerge ne sait
            # écrire que du Matroska : quand le profil demande du MP4 sans
            # greffe, c'est ffmpeg qui recompose, depuis la source.
            if direct:
                ok, porteur = self._porter_sous_titres(index, dec)
                if not ok:
                    return
                chapitres = self._ecrire_chapitres(dec)
                cmd = dovi.build_strip_mp4(
                    source, sortie,
                    sous_titres=[st.index for st in dec.subtitles_finales],
                    ffmpeg_path=ffmpeg_path,
                    audio=dec.audio, porteur=porteur, chapitres=chapitres,
                    pistes_st=dec.subtitles_finales)
                self.app.call_from_thread(self._update_cmd_lines, " ".join(cmd))
                self.app.call_from_thread(
                    self._update_ffmpeg_line,
                    "▶ 1/1 " + _("Removing the RPU and remuxing with ffmpeg — "
                                 "copy, no re-encoding…"))
                proc = EncoderProcess(cmd, dec.info.duration)
                self._demarrer(proc)
                for ligne, progress in proc.iter_progress():
                    s.last_line = ligne
                    if progress:
                        s.percent = progress.percent
                        self.app.call_from_thread(self._update_row, index)
                code = proc.wait()
                self._process = None
                erreurs: list[str] = []
            else:
                pistes = self._transcoder_greffes(index, dec, produits)
                if pistes is None:
                    return
                exclues = [ad for ad in dec.audio
                           if ad.action == AudioAction.EXCLUDE]
                cmd = build_strip_command(
                    nodv, source, mkv,
                    fps=dec.info.frame_rate,
                    tracks=pistes,
                    audio_source=mka if passe_audio else None,
                    audio_indices=([ad.track.index for ad in dec.audio
                                    if ad.action != AudioAction.EXCLUDE]
                                   if exclues and not passe_audio else None),
                    sous_titres=[st.index for st in dec.subtitles_finales],
                    chapitres=self._playlist_chapitres(dec))
                etape = n_etapes - (mkv != sortie)
                self.app.call_from_thread(self._update_cmd_lines, " ".join(cmd))
                self.app.call_from_thread(
                    self._update_ffmpeg_line,
                    f"▶ {etape}/{n_etapes} " + _("Remuxing the tracks with mkvmerge…"))

                mux = MuxProcess(cmd)
                self._demarrer(mux)
                for ligne, pourcent in mux.iter_progress():
                    if pourcent is not None:
                        s.percent = pourcent / 100.0
                        self.app.call_from_thread(self._update_row, index)
                    elif ligne:
                        self.app.call_from_thread(self._update_ffmpeg_line, ligne)
                code = mux.wait()
                self._mux = None
                erreurs = mux.errors
                if mkvmerge_reussi(code, mkv):
                    code = 0              # des avertissements : la sortie vaut (CR-89)

            if code != 0 or not mkv.exists():
                detail = erreurs[-1] if erreurs else f"code {code}"
                echouer(_("remux: {detail}").format(detail=detail),
                        _("Remux failed — {detail}").format(detail=detail))
                return

            # N/N — le Matroska recomposé passe en MP4 (CR-55).
            if mkv != sortie:
                if s.state == FileState.SKIPPED:
                    return
                ok, porteur = self._porter_sous_titres(index, dec, recompose=mkv)
                if not ok:
                    return
                cmd = dovi.build_dv_mp4_remux(mkv, sortie, ffmpeg_path, porteur)
                self.app.call_from_thread(self._update_cmd_lines, " ".join(cmd))
                self.app.call_from_thread(
                    self._update_ffmpeg_line,
                    f"▶ {n_etapes}/{n_etapes} " + _("Remuxing to MP4 with ffmpeg…"))
                proc = EncoderProcess(cmd, dec.info.duration)
                self._demarrer(proc)
                for ligne, progress in proc.iter_progress():
                    s.last_line = ligne
                    if progress:
                        s.percent = progress.percent
                        self.app.call_from_thread(self._update_row, index)
                code = proc.wait()
                self._process = None
                if s.state == FileState.SKIPPED:
                    return
                if code != 0 or not sortie.exists():
                    echouer(_("MP4 remux: code {code}").format(code=code),
                            _("The MP4 remux failed (code {code}).").format(code=code))
                    return
            vide = self._audio_vide(dec, sortie)
            if vide:
                echouer(vide, vide)
                return

            self._supprimer_source(dec, s)

            if s.state != FileState.SKIPPED:
                s.state   = FileState.SUCCESS
                s.percent = 1.0
            self.app.call_from_thread(self._update_row, index)
            self.app.call_from_thread(self._update_header)

        except ValueError as e:
            # Un refus de construction de commande (piste introuvable, CR-27) :
            # remonté hors du fil, il fermait l'application.
            echouer(texte_erreur(e), texte_erreur(e))
        finally:
            self._process = None
            if s.state != FileState.SUCCESS:
                sortie.unlink(missing_ok=True)      # partielle (CR-57)
            # Les deux flux bruts pèsent chacun le poids du film : les laisser
            # traîner remplirait le disque, que l'opération ait abouti ou non.
            for tmp in (brut, nodv, mka, porteur, chapitres, *produits) + (
                    (mkv,) if mkv != sortie else ()):
                try:
                    if tmp is not None and tmp.exists():
                        tmp.unlink()
                except OSError:
                    pass
            self._encode_next()

    def _encode_dv(self, index: int, dec: FileDecision) -> None:
        """Réencode la vidéo en préservant le Dolby Vision, puis passe au suivant.

        Le RPU — les métadonnées DV, image par image — vit *à l'intérieur* du
        flux HEVC, entre les tranches. Ce n'est pas une piste qu'un `-map`
        laisse passer : tout réencodage le détruit. On le sort donc avant, on
        encode, on le remet, on remuxe.

        1. `dovi_tool extract-rpu`, branché sur ffmpeg en tuyau — rien sur le
           disque, là où passer par un fichier aurait coûté une recopie du film
           entier pour en tirer quelques kilo-octets.
        2. le profil 7 devient 8.1 : sa couche d'amélioration ne survivrait pas.
        3. l'encodage vidéo seul, en Annex-B brut, sans le moindre filtre — le
           nombre d'images doit correspondre au RPU.
        4. `dovi_tool inject-rpu`, qui exige de vrais fichiers : il relit son
           entrée une première fois pour reconstituer l'ordre des images.
        5. les pistes audio finales si la décision en transcode une, puis le
           remux par mkvmerge.
        6. en sortie MP4, un remux du Matroska par ffmpeg (IE-108) : c'est
           depuis le MKV, et non depuis le flux brut, que ffmpeg sait écrire
           la boîte `dvcC`.
        """
        from core import dovi
        from core.encoder import build_dv_video_command

        s      = self._statuses[index]
        source = dec.info.lecture
        sortie = dec.output_path

        def echouer(resume: str, detail: str) -> None:
            # `S` ou `X` a déjà tranché : l'étape interrompue échoue, mais le
            # fichier reste abandonné, comme le bilan l'affiche (CR-61).
            if s.state == FileState.SKIPPED:
                return
            s.state, s.error_msg, s.last_line = FileState.ERROR, resume[:60], detail
            self.app.call_from_thread(self._update_row, index)

        dovi_path = getattr(self.app, "dovi_path", None)
        if dovi_path is None or not getattr(self.app, "mkvmerge_available", False):
            echouer(_("dovi_tool + mkvmerge required"),
                    _("Preserving Dolby Vision through a re-encode needs "
                      "dovi_tool and mkvmerge. Run the preflight again to "
                      "install them."))
            self._encode_next()
            return

        ffmpeg_path = getattr(self.app, "ffmpeg_path", "ffmpeg")
        # Comme pour le retrait du RPU : les intermédiaires pèsent le poids de
        # la vidéo encodée, ils vont à côté de la sortie et non dans le temp du
        # système. Il y en a deux à la fois — `inject-rpu` ne travaille pas en
        # place — soit environ deux fois la taille de la sortie.
        rpu = dec.dossier_sortie / f"{source.stem}.iris.rpu"
        p8  = dec.dossier_sortie / f"{source.stem}.iris_p8.rpu"
        enc = dec.dossier_sortie / f"{source.stem}.iris_enc.hevc"
        inj = dec.dossier_sortie / f"{source.stem}.iris_dv.hevc"
        mka = dec.dossier_sortie / f"{source.stem}.iris_audio.mka"
        # En sortie MP4, mkvmerge écrit d'abord ce Matroska, que ffmpeg remuxe.
        en_mp4 = sortie.suffix.lower() == ".mp4"
        mkv    = dec.dossier_sortie / f"{source.stem}.iris_dv.mkv" if en_mp4 else sortie
        porteur: Optional[Path] = None
        produits: list[Path] = []

        passe_audio = audio_pass_needed(dec.audio)
        n_etapes    = 5 if passe_audio else 4
        if dec.info.dv_profile == 7:
            n_etapes += 1
        if en_mp4:
            n_etapes += 1
        etape     = 0
        s.percent = -1

        def annoncer(texte: str, commande: str = "") -> None:
            nonlocal etape
            etape += 1
            if commande:
                self.app.call_from_thread(self._update_cmd_lines, commande)
            self.app.call_from_thread(
                self._update_ffmpeg_line, f"▶ {etape}/{n_etapes} {texte}")
            s.percent = -1
            self.app.call_from_thread(self._update_row, index)

        try:
            # 1 — le RPU, en tuyau
            tuyau = dovi.TuyauRpu(source, rpu, dovi_path, ffmpeg_path,
                                  dec.info.duration)
            annoncer(_("Extracting the Dolby Vision metadata…"),
                     " ".join(tuyau.cmd) + " | " + " ".join(tuyau.cmd_dt))
            code = self._executer(index, tuyau)
            if s.state == FileState.SKIPPED:
                return
            if code != 0 or not dovi.rpu_valide(rpu):
                echouer(_("RPU extraction failed"),
                        _("dovi_tool could not extract the Dolby Vision metadata "
                          "from the source. The re-encode would have destroyed "
                          "it: stopping rather than producing a file without "
                          "Dolby Vision."))
                return

            # 2 — profil 7 → 8.1
            if dec.info.dv_profile == 7:
                annoncer(_("Converting the RPU to profile 8.1…"),
                         f"{dovi_path.name} convert -m 2 -i {rpu.name}")
                if not dovi.convert_p7_to_p8(rpu, p8, dovi_path):
                    echouer(_("RPU 7 → 8.1 conversion failed"),
                            _("dovi_tool could not convert the RPU from profile 7 "
                              "to profile 8.1."))
                    return
                p8.replace(rpu)

            # 3 — l'encodage vidéo, seul
            cmd = build_dv_video_command(dec, self._platform, enc, ffmpeg_path)
            annoncer(_("Encoding the video…"), " ".join(cmd))
            proc = EncoderProcess(cmd, dec.info.duration)
            self._demarrer(proc)
            for ligne, progress in proc.iter_progress():
                s.last_line = ligne
                if progress:
                    s.percent = progress.percent
                    self.app.call_from_thread(self._update_row, index)
                    self.app.call_from_thread(self._update_header)
            code = proc.wait()
            self._process = None
            if s.state == FileState.SKIPPED:
                return
            if code != 0 or not enc.exists():
                echouer(_("video encoding: code {code}").format(code=code),
                        _("Encoding the video failed (code {code}).").format(code=code))
                return

            # 4 — le RPU revient
            cmd = dovi.build_inject_command(enc, rpu, inj, dovi_path)
            annoncer(_("Re-injecting Dolby Vision…"), " ".join(cmd))
            code = self._executer(index, EncoderProcess(cmd))
            if s.state == FileState.SKIPPED:
                return
            if code != 0 or not inj.exists():
                echouer(_("RPU re-injection failed"),
                        _("dovi_tool could not re-inject the RPU. The most "
                          "common cause is a different frame count between the "
                          "source and the encode."))
                return

            # 5 — pistes audio finales, quand la décision en transcode une
            if passe_audio:
                cmd = build_audio_command(source, mka, dec.audio, ffmpeg_path)
                annoncer(_("Transcoding the audio tracks…"), " ".join(cmd))
                proc = EncoderProcess(cmd, dec.info.duration)
                self._demarrer(proc)
                for ligne, progress in proc.iter_progress():
                    s.last_line = ligne
                    if progress:
                        s.percent = progress.percent
                        self.app.call_from_thread(self._update_row, index)
                code = proc.wait()
                self._process = None
                if s.state == FileState.SKIPPED:
                    return
                if code != 0 or not mka.exists():
                    echouer(_("audio transcoding: code {code}").format(code=code),
                            _("Transcoding the audio tracks failed (code "
                              "{code}).").format(code=code))
                    return

            # N — remux par mkvmerge, vers la sortie ou vers l'intermédiaire
            # que l'étape suivante passera en MP4.
            pistes = self._transcoder_greffes(index, dec, produits)
            if pistes is None:
                return
            exclues = [ad for ad in dec.audio if ad.action == AudioAction.EXCLUDE]
            cmd = build_strip_command(
                inj, source, mkv,
                fps=dec.info.frame_rate,
                tracks=pistes,
                audio_source=mka if passe_audio else None,
                audio_indices=([ad.track.index for ad in dec.audio
                                if ad.action != AudioAction.EXCLUDE]
                               if exclues and not passe_audio else None),
                sous_titres=[st.index for st in dec.subtitles_finales],
                chapitres=self._playlist_chapitres(dec))
            annoncer(_("Remuxing the tracks with mkvmerge…"), " ".join(cmd))
            mux = MuxProcess(cmd)
            self._demarrer(mux)
            for ligne, pourcent in mux.iter_progress():
                if pourcent is not None:
                    s.percent = pourcent / 100.0
                    self.app.call_from_thread(self._update_row, index)
                elif ligne:
                    self.app.call_from_thread(self._update_ffmpeg_line, ligne)
            code = mux.wait()
            self._mux = None
            if not mkvmerge_reussi(code, mkv):
                detail = mux.errors[-1] if mux.errors else f"code {code}"
                echouer(_("remux: {detail}").format(detail=detail),
                        _("Remux failed — {detail}").format(detail=detail))
                return

            # N+1 — le Matroska passe en MP4, Dolby Vision compris (IE-108)
            if en_mp4:
                if s.state == FileState.SKIPPED:
                    return
                ok, porteur = self._porter_sous_titres(index, dec, recompose=mkv)
                if not ok:
                    return
                cmd = dovi.build_dv_mp4_remux(mkv, sortie, ffmpeg_path, porteur)
                annoncer(_("Remuxing to MP4 with ffmpeg…"), " ".join(cmd))
                proc = EncoderProcess(cmd, dec.info.duration)
                self._demarrer(proc)
                for ligne, progress in proc.iter_progress():
                    s.last_line = ligne
                    if progress:
                        s.percent = progress.percent
                        self.app.call_from_thread(self._update_row, index)
                code = proc.wait()
                self._process = None
                if s.state == FileState.SKIPPED:
                    return
                if code != 0 or not sortie.exists():
                    echouer(_("MP4 remux: code {code}").format(code=code),
                            _("The MP4 remux failed (code {code}).").format(code=code))
                    return
            vide = self._audio_vide(dec, sortie)
            if vide:
                echouer(vide, vide)
                return

            self._supprimer_source(dec, s)

            if s.state != FileState.SKIPPED:
                s.state   = FileState.SUCCESS
                s.percent = 1.0
            self.app.call_from_thread(self._update_row, index)
            self.app.call_from_thread(self._update_header)

        except ValueError as e:
            # Un refus de construction de commande (piste introuvable, CR-27) :
            # remonté hors du fil, il fermait l'application.
            echouer(texte_erreur(e), texte_erreur(e))
        finally:
            self._process = None
            if s.state != FileState.SUCCESS:
                sortie.unlink(missing_ok=True)      # partielle (CR-57)
            # Deux flux bruts de la taille de la vidéo encodée : les laisser
            # traîner remplirait le disque, que l'opération ait abouti ou non.
            for tmp in (rpu, p8, enc, inj, mka, porteur, *produits) + (
                    (mkv,) if en_mp4 else ()):
                try:
                    if tmp is not None and tmp.exists():
                        tmp.unlink()
                except OSError:
                    pass
            self._encode_next()

    def _muxer(self, index: int, dec: FileDecision) -> None:
        """Greffe les pistes externes d'un fichier qui n'a rien à réencoder.

        Le chemin de l'écran du mux, dans la file : mkvmerge recopie l'image et
        ajoute les pistes, en quelques minutes. Sans lui, un SKIP muni de
        greffes envoyé par `F2` depuis l'écran des pistes finissait « ignoré »
        sans rien écrire (CR-82).
        """
        s      = self._statuses[index]
        sortie = dec.output_path
        try:
            if not getattr(self.app, "mkvmerge_available", False):
                s.state, s.error_msg = FileState.ERROR, _("mkvmerge required")
                s.last_line = _("Adding tracks without re-encoding needs mkvmerge. "
                                "Run the preflight again to install it.")
                return
            try:
                cmd = build_mux_command(dec.info.path, dec.external_tracks, sortie)
            except ValueError as e:
                s.state, s.error_msg, s.last_line = (FileState.ERROR,
                                                     texte_erreur(e)[:60], texte_erreur(e))
                return
            self.app.call_from_thread(self._update_cmd_lines, " ".join(cmd))
            self.app.call_from_thread(
                self._update_ffmpeg_line,
                "▶ " + _("Adding the tracks with mkvmerge, no re-encoding…"))
            proc = MuxProcess(cmd)
            self._demarrer(proc)
            for ligne, pourcent in proc.iter_progress():
                if pourcent is not None:
                    s.percent = pourcent / 100
                    self.app.call_from_thread(self._update_row, index)
                elif ligne:
                    self.app.call_from_thread(self._update_ffmpeg_line, ligne)
            code = proc.wait()
            self._mux = None
            # mkvmerge rend 1 pour de simples avertissements : la sortie vaut.
            if mkvmerge_reussi(code, sortie):
                if s.state != FileState.SKIPPED:
                    s.state, s.percent = FileState.SUCCESS, 1.0
                return
            sortie.unlink(missing_ok=True)
            if s.state == FileState.SKIPPED:          # `S` ou `X` (CR-61)
                return
            detail = proc.errors[-1] if proc.errors else f"code {code}"
            s.state, s.error_msg = (FileState.ERROR,
                                    _("mux: {detail}").format(detail=detail)[:60])
            s.last_line = _("Mux failed — {detail}").format(detail=detail)
        finally:
            self.app.call_from_thread(self._update_row, index)
            self.app.call_from_thread(self._update_header)
            self._encode_next()

    def _ecrire_chapitres(self, dec: FileDecision) -> Optional[Path]:
        """Les chapitres d'un titre de Blu-ray d'un seul clip, écrits pour
        ffmpeg (IE-120). None sans titre, sans chapitres, ou quand l'entrée
        est un assemblage : mkvmerge les y a déjà mis."""
        from core.bluray import ffmetadata_chapitres

        titre = dec.info.titre
        if titre is None or dec.encode_source is not None:
            return None
        texte = ffmetadata_chapitres(titre)
        if not texte:
            return None
        chemin = dec.dossier_sortie / f"{dec.info.path.stem}.iris_chap.txt"
        try:
            chemin.write_text(texte, encoding="utf-8")
        except OSError:
            return None               # des chapitres en moins, pas un échec
        return chemin

    def _remux_titre(self, index: int, dec: FileDecision) -> bool:
        """Extrait un titre de disque en Matroska. False si ça échoue.
        L'extraction devient `encode_source`, supprimée après l'encodage comme
        l'intermédiaire d'un mux préalable."""
        if dec.info.titre.est_dvd:
            return self._extraire_dvd(index, dec)
        from core.bluray import build_remux_command

        s = self._statuses[index]
        if not getattr(self.app, "mkvmerge_available", False):
            s.state     = FileState.ERROR
            s.error_msg = _("mkvmerge required (Blu-ray title)")
            s.last_line = _("This Blu-ray title spans several clips: only mkvmerge "
                            "can join them. Run the preflight again to install it.")
            self.app.call_from_thread(self._update_row, index)
            return False

        sortie = dec.dossier_sortie / f"{dec.info.path.stem}.iris_titre.mkv"
        cmd = build_remux_command(dec.info.titre, sortie)
        self.app.call_from_thread(self._update_cmd_lines, " ".join(cmd))
        self.app.call_from_thread(
            self._update_ffmpeg_line,
            "▶ " + _("Joining the clips of the Blu-ray title with mkvmerge…"))

        proc = MuxProcess(cmd)
        self._demarrer(proc)
        for ligne, pourcent in proc.iter_progress():
            if pourcent is not None:
                s.percent = pourcent
                self.app.call_from_thread(self._update_row, index)
            elif ligne:
                self.app.call_from_thread(self._update_ffmpeg_line, ligne)
        code = proc.wait()
        self._mux = None

        # mkvmerge rend 1 pour de simples avertissements.
        if not mkvmerge_reussi(code, sortie):
            sortie.unlink(missing_ok=True)
            if s.state == FileState.SKIPPED:          # `S` ou `X` (CR-61)
                return False
            detail = proc.errors[-1] if proc.errors else f"code {code}"
            s.state, s.error_msg = (FileState.ERROR,
                                    _("mux: {detail}").format(detail=detail)[:60])
            s.last_line = _("Joining the Blu-ray title failed — {detail}").format(
                detail=detail)
            self.app.call_from_thread(self._update_row, index)
            return False

        # La décision a numéroté les pistes du premier clip : l'assemblage doit
        # avoir les mêmes, sinon `-map` en prendrait une autre (CR-03).
        from core.bluray import ecart_pistes
        from core.scanner import _ffprobe_json
        try:
            flux = _ffprobe_json(["-show_streams", str(sortie)]).get("streams", [])
            ecart = ecart_pistes(dec.info, flux)
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as e:
            ecart = texte_erreur(e)
        if ecart:
            sortie.unlink(missing_ok=True)
            s.state, s.error_msg = FileState.ERROR, _("title: tracks differ")
            s.last_line = _("The joined Blu-ray title does not have the tracks the "
                            "analysis saw ({detail}): encoding it would label one "
                            "track as another.").format(detail=ecart)
            self.app.call_from_thread(self._update_row, index)
            return False

        dec.encode_source = sortie
        s.percent = -1
        self.app.call_from_thread(self._update_row, index)
        return True

    def _extraire_dvd(self, index: int, dec: FileDecision) -> bool:
        """Un titre de DVD recopié sans perte en Matroska par l'outil DVD —
        langues, chapitres et palette des sous-titres compris (IE-121)."""
        from core import dvd

        s = self._statuses[index]
        if dvd.outils()[0] is None:
            s.state     = FileState.ERROR
            s.error_msg = _("DVD tool required")
            s.last_line = _("Reading a DVD title needs the DVD tool (an ffmpeg with "
                            "libdvdnav). Restart IRIS ENCODE and accept its "
                            "installation.")
            self.app.call_from_thread(self._update_row, index)
            return False

        sortie = dec.dossier_sortie / f"{dec.info.path.stem}.iris_titre.mkv"
        cmd = dvd.build_extraction_command(dec.info.titre, sortie,
                                           dec.info.audio_tracks)
        self.app.call_from_thread(self._update_cmd_lines, " ".join(cmd))
        self.app.call_from_thread(
            self._update_ffmpeg_line,
            "▶ " + _("Extracting the DVD title (lossless copy)…"))

        proc = EncoderProcess(cmd, dec.info.duration)
        self._demarrer(proc)
        journal: list[str] = []
        for ligne, progress in proc.iter_progress():
            if progress:
                s.percent = progress.percent
                self.app.call_from_thread(self._update_row, index)
            elif ligne:
                journal.append(ligne)
                del journal[:-5]
        code = proc.wait()
        self._process = None

        if code != 0 or not sortie.exists():
            sortie.unlink(missing_ok=True)
            if s.state == FileState.SKIPPED:          # `S` ou `X` (CR-61)
                return False
            detail = journal[-1] if journal else f"code {code}"
            s.state, s.error_msg = (FileState.ERROR,
                                    _("DVD: {detail}").format(detail=detail)[:60])
            s.last_line = _("Extracting the DVD title failed — {detail}").format(
                detail=detail)
            self.app.call_from_thread(self._update_row, index)
            return False

        dec.encode_source = sortie
        s.percent = -1
        self.app.call_from_thread(self._update_row, index)
        return True

    def _premux(self, index: int, dec: FileDecision) -> bool:
        """
        Greffe les pistes par mkvmerge avant l'encodage. False si ça échoue.

        Appelée depuis le thread d'encodage : mkvmerge tourne jusqu'au bout
        avant que ffmpeg démarre.
        """
        s = self._statuses[index]
        if not getattr(self.app, "mkvmerge_available", False):
            s.state     = FileState.ERROR
            s.error_msg = _("mkvmerge required (stretch)")
            s.last_line = _("A track needs a stretch factor: only mkvmerge can "
                            "apply it. Run the preflight again to install it.")
            self.app.call_from_thread(self._update_row, index)
            return False

        sortie = premux_output_path(dec.info.path, dec.dossier_sortie)
        # Après l'assemblage d'un titre de Blu-ray, c'est lui que la greffe
        # complète ; il cède ensuite la place.
        assemblage = dec.encode_source
        try:
            cmd = build_mux_command(assemblage or dec.info.lecture,
                                    dec.external_tracks, sortie)
        except ValueError as e:
            s.state, s.error_msg, s.last_line = (FileState.ERROR,
                                                 texte_erreur(e)[:60], texte_erreur(e))
            self.app.call_from_thread(self._update_row, index)
            return False

        self.app.call_from_thread(self._update_cmd_lines, " ".join(cmd))
        self.app.call_from_thread(
            self._update_ffmpeg_line,
            "▶ " + _("Adding the tracks with mkvmerge (stretch) before encoding…"))

        proc = MuxProcess(cmd)
        self._demarrer(proc)
        for ligne, pourcent in proc.iter_progress():
            if pourcent is not None:
                s.percent = pourcent
                self.app.call_from_thread(self._update_row, index)
            elif ligne:
                self.app.call_from_thread(self._update_ffmpeg_line, ligne)
        code = proc.wait()
        self._mux = None

        if not mkvmerge_reussi(code, sortie):
            # Interrompu ou échoué, l'intermédiaire pèse le poids du film.
            sortie.unlink(missing_ok=True)
            if s.state == FileState.SKIPPED:          # `S` ou `X` (CR-61)
                return False
            detail = proc.errors[-1] if proc.errors else f"code {code}"
            s.state, s.error_msg = (FileState.ERROR,
                                    _("mux: {detail}").format(detail=detail)[:60])
            s.last_line = _("Pre-mux failed — {detail}").format(detail=detail)
            self.app.call_from_thread(self._update_row, index)
            return False

        # L'intermédiaire porte désormais les pistes : ffmpeg n'a plus qu'à
        # l'encoder. info.path reste la source, dont dépend le nom de sortie.
        # Les pistes quittent `external_tracks` — ffmpeg ne doit pas rouvrir
        # les donneurs — mais elles ne sont pas oubliées pour autant : la
        # commande d'encodage a encore à les mapper depuis l'intermédiaire.
        if assemblage is not None:
            assemblage.unlink(missing_ok=True)
        dec.encode_source   = sortie
        dec.premuxed_tracks = dec.external_tracks
        dec.external_tracks = []
        s.percent = -1
        self.app.call_from_thread(self._update_row, index)
        return True

    # Au-delà, la zone de commande déborderait : le reste se compte.
    _SORTIES_LISTEES = 6

    def _resume(self) -> str:
        """Le bilan du lot, et où trouver ce qu'il a produit (UX-16)."""
        compte = {etat: sum(1 for s in self._statuses if s.state == etat)
                  for etat in (FileState.SUCCESS, FileState.ERROR,
                               FileState.SKIPPED)}
        lignes = [_("Done — succeeded: {success} · failed: {failed} · skipped: "
                    "{skipped}").format(success=compte[FileState.SUCCESS],
                                        failed=compte[FileState.ERROR],
                                        skipped=compte[FileState.SKIPPED])]
        sorties = [s.decision.output_path for s in self._statuses
                   if s.state == FileState.SUCCESS]
        lignes += [f"→ {p}" for p in sorties[:self._SORTIES_LISTEES]]
        reste = len(sorties) - self._SORTIES_LISTEES
        if reste > 0:
            lignes.append("   " + ngettext("… and {count} other", "… and {count} others",
                                           reste).format(count=reste))
        return "\n".join(lignes)

    def _on_all_done(self) -> None:
        from ..common import touche
        app = self.app
        # Un lot arrêté (`X`, F10) ne déclenche rien : on est là, et on a
        # choisi d'arrêter.
        if self.apres_lot and not self._abandon:
            app.armer_fin_de_lot()  # type: ignore[attr-defined]
        if app.current_mode == app.MODE_ENCODAGES:  # type: ignore[attr-defined]
            self._vu = True
        else:
            app.notify(_("Encoding batch done — {key} for the summary.").format(
                key=touche("f12")),
                       timeout=8)
        try:
            self._update_header()
            self.query_one("#cmd-lines",   Static).update(self._resume())
            self.query_one("#ffmpeg-line", Static).update("")
            # Pause et « Passer le fichier » n'ont plus d'objet : le pied ne
            # garde que la navigation, Retour et Accueil.
            self.query_one(KeyFooter).update_line(1, [])
        except Exception:
            pass

    # ─── Réordonner la file (IE-100) ─────────────────────────────────────────

    def _en_attente_a(self, i: int) -> bool:
        return (0 <= i < len(self._statuses)
                and self._statuses[i].state == FileState.PENDING)

    def _refus_file(self) -> None:
        self.notify(_("Only a pending file can be moved or removed — the "
                      "running one and the finished ones stay."),
                    severity="warning", timeout=4)

    def _deplacer(self, sens: int) -> None:
        i = self.query_one(DataTable).cursor_row
        j = i + sens
        with self._verrou:
            # Les deux lignes doivent attendre : un fichier ne passe pas devant
            # celui qui tourne, ni derrière le bout de la file.
            ok = self._en_attente_a(i) and self._en_attente_a(j)
            if ok:
                self._statuses[i], self._statuses[j] = (self._statuses[j],
                                                        self._statuses[i])
        if not ok:
            if self._en_attente_a(i) and 0 <= j < len(self._statuses):
                return                    # déjà en tête des attentes : rien à dire
            self._refus_file()
            return
        self._reconstruire_table()
        self.query_one(DataTable).move_cursor(row=j)

    def action_monter(self) -> None:
        self._deplacer(-1)

    def action_descendre(self) -> None:
        self._deplacer(+1)

    def action_retirer(self) -> None:
        i = self.query_one(DataTable).cursor_row
        with self._verrou:
            ok = self._en_attente_a(i)
            retire = self._statuses.pop(i) if ok else None
        if retire is None:
            self._refus_file()
            return
        self._reconstruire_table()
        self._update_header()
        self.notify(_("{file} removed from the queue.").format(
                        file=retire.decision.info.path.name),
                    timeout=3)

    # ─── Après le lot ─────────────────────────────────────────────────────────

    def action_apres_lot(self) -> None:
        """Bascule l'action d'après lot ; la confirme par un message."""
        from core import veille
        from core.config import get_action_fin
        from ..common import touche
        if self._done:
            return
        if not veille.disponible():
            self.notify(_("Sleep and shutdown are only managed under "
                          "Windows."), severity="warning", timeout=4)
            return
        action = get_action_fin(self.app.cfg)  # type: ignore[attr-defined]
        if action == "rien" and not self.apres_lot:
            self.notify(_("After the batch: nothing is planned. Choose an "
                          "action in the options ({key}, then {option_key}).").format(
                            key=touche("f5"), option_key=touche("u")),
                        timeout=6)
            return
        self.apres_lot = not self.apres_lot
        libelle = veille.libelle_action(action)
        self.notify(_("After the batch: {action}, after a {seconds} s "
                      "countdown.").format(action=libelle,
                                           seconds=veille.COMPTE_A_REBOURS_S)
                    if self.apres_lot
                    else _("After the batch: nothing."), timeout=4)
        self._update_header()

    # ─── Pause/Resume ─────────────────────────────────────────────────────────

    def action_pause_resume(self) -> None:
        if self._process is None:
            return
        if self._paused:
            self._process.resume()
            self._paused = False
        else:
            self._process.pause()
            self._paused = True

    def action_skip_current(self) -> None:
        """Termine l'encodage en cours et passe au fichier suivant.

        Une étape mkvmerge (assemblage d'un titre, mux préalable, remux des
        chemins DV) s'arrête aussi : `S` n'y faisait rien, sans un mot (CR-61).
        """
        if self._done:
            return
        if self._process is None and self._mux is None:
            if self._started:
                # Entre deux étapes : un instant, la suivante sera arrêtable.
                self.notify(_("No step to skip at this instant — try again in a "
                              "moment."), timeout=3)
            return
        if 0 <= self._current_idx < len(self._statuses):
            s = self._statuses[self._current_idx]
            s.state    = FileState.SKIPPED
            s.last_line = _("Skipped manually")
            self._update_row(self._current_idx)
        # terminate() ferme le process : la boucle iter_progress se termine,
        # _encode_next() enchaîne automatiquement sur le suivant. Un processus
        # suspendu doit d'abord reprendre : sous POSIX, l'arrêt resterait en
        # attente, et le fichier suivant ne démarrerait jamais (CR-60).
        if self._process is not None:
            if self._paused:
                self._process.resume()
                self._paused = False
            self._process.terminate()
        else:
            self._mux.terminate()

    # ─── Sortie ───────────────────────────────────────────────────────────────

    def _demarrer(self, proc: EncoderProcess | MuxProcess) -> None:
        """Démarre un processus du lot et le rend interruptible.

        Démarré *avant* d'être publié, et le drapeau relu *après* : un abandon
        survenu entre deux étapes trouve soit le processus (et l'arrête), soit
        le drapeau déjà levé ici — jamais ni l'un ni l'autre.
        """
        proc.start()
        if isinstance(proc, MuxProcess):
            self._mux = proc          # hors de `_process` : il ne sait pas se suspendre
        else:
            self._process = proc
        if self._abandon:
            self._arreter(proc)

    def _arreter(self, proc: EncoderProcess | MuxProcess) -> None:
        """Termine `proc` et, s'il n'a pas fini de lui-même, efface la sortie
        du fichier en cours — une fois le processus sorti, qui la tenait.

        Ici plutôt qu'en fin de boucle : la boucle enchaîne par un nouveau
        worker, et celui d'un écran déjà dépilé ne démarre pas toujours.
        """
        if isinstance(proc, EncoderProcess) and self._paused:
            proc.resume()
        proc.terminate()
        if proc.wait() == 0:
            return                    # fini juste avant l'arrêt : on garde
        if 0 <= self._current_idx < len(self._statuses):
            try:
                self._statuses[self._current_idx].decision.output_path.unlink(
                    missing_ok=True)
            except OSError:
                pass

    def _interrompre(self) -> None:
        """Abandonne le lot : le processus en cours, et tout ce qui l'aurait suivi.

        Le drapeau empêche la boucle d'encodage d'enchaîner sur l'étape ou le
        fichier suivant ; on ne compte pas sur l'annulation des workers d'un
        écran dépilé.
        """
        self._abandon = True
        for proc in (self._process, self._mux):
            if proc is not None:
                self._arreter(proc)

    def action_go_back(self) -> None:
        """La navigation, sans rien arrêter : le lot continue (IE-100)."""
        self.app.switch_mode(self.app.MODE_FICHIERS)  # type: ignore[attr-defined]

    def action_accueil(self) -> None:
        """La liste des volumes, côté navigation ; le lot continue."""
        self.app.switch_mode(self.app.MODE_FICHIERS)  # type: ignore[attr-defined]
        retour_accueil(self.app)

    def action_arreter_tout(self) -> None:
        """Arrête le fichier en cours et tout ce qui attend, après confirmation."""
        if self._done:
            return
        from .confirm import ConfirmModal

        def _reponse(ok) -> None:
            if not ok:
                return
            # L'état se pose **avant** l'arrêt : le worker, en voyant ffmpeg
            # sortir, garde un SKIPPED au lieu d'écrire un échec.
            with self._verrou:
                for s in self._statuses:
                    if s.state in (FileState.PENDING, FileState.RUNNING):
                        s.state     = FileState.SKIPPED
                        s.last_line = _("Stopped")
                self._done = True
            self._interrompre()
            for i in range(len(self._statuses)):
                self._update_row(i)
            self._on_all_done()

        restants = self.en_attente()
        corps = _("The current file is abandoned, its partial output deleted.")
        if restants:
            corps += "\n" + ngettext("The pending file will not be encoded.",
                                     "The {count} pending files will not be encoded.",
                                     restants).format(count=restants)
        self.app.push_screen(ConfirmModal(
            _("Stop all encodes?"), corps,
            confirm_label=_("Stop"), cancel_label=_("Continue"), danger=True),
            _reponse)
