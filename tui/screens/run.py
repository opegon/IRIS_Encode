"""
tui/screens/run.py — Écran d'encodage avec progression live.

Zone commande ffmpeg + ligne de retour live (non scrollable).

Depuis IE-100, l'écran **est** la file d'encodage : il vit dans son propre mode
Textual, reçoit les ajouts faits pendant qu'il tourne (`ajouter`), et `⌫`
rend la navigation sans rien arrêter.
"""
from __future__ import annotations

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

from core.texte import accorde, pluriel
from core.decision import (AudioAction, FileDecision, VideoAction,
                           resoudre_sorties)
from core.encoder import (
    EncoderProcess, audio_pass_needed, audio_prepass_needed,
    build_audio_command, build_command, diagnostiquer, encodeur_de,
    pistes_audio_vides,
)
from core.muxer import (
    MuxProcess, build_mux_command, build_strip_command, needs_premux,
    premux_output_path,
)
from core.platform import PlatformProfile
from ..common import (barre_etat, actions_ecran, footer_line2, largeur_entete,
                      record_measured_speed,
                      retour_accueil)
from ..mixins import TableNavMixin
from ..widgets.entete import Entete
from ..widgets.footer import KeyFooter


# ─── État fichier ─────────────────────────────────────────────────────────────

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
        Binding("p",         "pause_resume", "Pause / Reprendre",  show=True),
        Binding("s",         "skip_current", "Passer le fichier",  show=True),
        Binding("x",         "arreter_tout", "Arrêter tout",       show=True),
        # La file se réordonne tant qu'un fichier attend (IE-100). `priority` :
        # le DataTable prendrait Ctrl+↑/↓ pour lui — comme sur la jonction.
        Binding("ctrl+up",   "monter",       "Monter",             show=True, priority=True),
        Binding("ctrl+down", "descendre",    "Descendre",          show=True, priority=True),
        Binding("delete",    "retirer",      "Retirer",            show=True),
        # Retour à la navigation : l'encodage continue (IE-100). Arrêter est
        # une décision à part, `X`, qui demande confirmation.
        Binding("backspace", "go_back",      "Fichiers",           show=True),
        Binding("escape",    "go_back",      "Fichiers",           show=False, priority=True),
        # `priority` : un DataTable etouffe la touche avant les bindings —
        # meme avertissement qu'en tete de tui/mixins.py.
        Binding("ctrl+home", "accueil",   "Accueil",       show=True,
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
            yield Label("Global", id="global-label")
            yield ProgressBar(total=100, show_eta=False, id="global-bar")
        with Static(id="cmd-zone"):
            # L'avancement d'abord : c'est la seule ligne qui change, et la
            # seule dont l'absence se remarque.
            yield Static("", id="ffmpeg-line", markup=False)
            yield Static("", id="cmd-lines", markup=False)
        yield KeyFooter(
            actions=actions_ecran(self),
            nav=footer_line2(nav=True, accueil=True, extra=(("backspace", "Fichiers"),)),
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
        table.add_column("Fichier", width=max(20, _cw("Fichier", names)), key="file")
        table.add_column("Action",  width=_cw("Action", actions),         key="action")
        table.add_column("État",    width=largeur_entete("État", 50),     key="state")

        for i, s in enumerate(self._statuses):
            dec   = s.decision
            name  = dec.info.path.name
            action_label = dec.video.label()
            table.add_row(
                self._icon(s),
                Text(name, overflow="ellipsis", no_wrap=True),
                Text(action_label, style=dec.video.style()),
                "en attente",
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
                    running_txt = "en cours…"
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
                    FileState.PENDING:  Text("en attente",      style="dim"),
                    # Le symbole est déjà dans la colonne d'icône (UX-16).
                    # Minuscules, comme « en attente » et « ignoré » (UX-09).
                    FileState.SUCCESS:  Text("terminé",          style="bold green"),
                    FileState.ERROR:    Text(f"échec : {s.error_msg[:30]}", style="bold dark_orange"),
                    FileState.SKIPPED:  Text("ignoré",           style="dim"),
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
            self.query_one("#run-header-bar", Static).update(barre_etat(
                "Encodage", pluriel(total, "fichier"),
                f"{done}/{total} {accorde(done, 'terminé')}", f"Global : {bar_pct}%",
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
                if dec.video.action == VideoAction.SKIP:
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
            self._encode_next()
            return

        # Transcoder une piste audio pendant qu'on recopie un sous-titre au
        # premier repère tardif fait perdre la piste, sans un mot. On la
        # produit donc à part, et la passe d'encodage la recopie.
        audio_tmp: Path | None = None
        if audio_prepass_needed(dec):
            audio_tmp = self._audio_prepass(next_idx, dec)
            if audio_tmp is None:
                self._encode_next()
                return

        try:
            cmd = build_command(dec, self._platform, audio_source=audio_tmp)
        except ValueError as e:
            s.state     = FileState.ERROR
            s.last_line = str(e)
            s.error_msg = str(e)[:60]
            self.app.call_from_thread(self._update_row, next_idx)
            self._encode_next()  # passe au suivant
            return
        self.app.call_from_thread(
            self._update_cmd_lines,
            " ".join(cmd),
        )

        # Le sondage du démarrage a déjà répondu : inutile de lancer ffmpeg
        # pour apprendre ce qu'on sait, ni de laisser l'utilisateur lire
        # « Error opening output files » à la place de la cause.
        choisi = encodeur_de(cmd)
        if choisi and self._platform.peut_encoder(choisi) is False:
            s.state     = FileState.ERROR
            s.error_msg = f"{choisi} indisponible ici"[:60]
            if "nvenc" in choisi and self._platform.alerte_nvenc:
                s.last_line = self._platform.alerte_nvenc
            else:
                s.last_line = (
                    f"Cette machine ne sait pas encoder avec « {choisi} » — sondé "
                    f"au lancement. L'AV1 par NVENC demande une RTX 40 ou plus "
                    f"récente ; le HEVC et le H264 restent disponibles.")
            self.app.call_from_thread(self._update_row, next_idx)
            self._encode_next()
            return

        proc = EncoderProcess(cmd, dec.info.duration)
        self._demarrer(proc)

        # Affiche "Encodage lancé" jusqu'à première ligne
        self.app.call_from_thread(
            self._update_ffmpeg_line,
            "▶ Encodage lancé, initialisation en cours…"
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
            vides = pistes_audio_vides(dec.output_path, dec.info.duration)
            if vides:
                success = False
                # Le bloc de conclusion retronque `last_line` dans `error_msg` :
                # l'essentiel doit tenir dans les soixante premiers caractères.
                s.last_line = (
                    f"Piste audio vide dans la sortie : {' · '.join(vides)}. "
                    "L'encodage s'est pourtant terminé sans erreur. Le fichier "
                    "est inutilisable en l'état, et ce cas sort du périmètre "
                    "connu — signalez-le.")

        if success and s._last_progress:
            record_measured_speed(self.app.cfg, dec.video.action, s._last_progress.speed)  # type: ignore[attr-defined]

        should_delete = (
            dec.delete_source_override
            if dec.delete_source_override is not None
            else dec.profile.get("delete_source", False)
        )
        if success and should_delete:
            try:
                dec.info.path.unlink()
            except Exception:
                pass

        # Les pistes audio produites à part ont été recopiées dans la sortie.
        if audio_tmp is not None:
            try:
                audio_tmp.unlink(missing_ok=True)
            except OSError:
                pass

        # L'intermédiaire d'un mux préalable n'a plus de raison d'être, que
        # l'encodage ait réussi ou non : il pèse le poids du film et se
        # refabrique en quelques secondes.
        if dec.encode_source is not None:
            try:
                dec.encode_source.unlink()
            except OSError:
                pass                      # tenu par un lecteur : on n'insiste pas
            dec.encode_source = None
            # L'intermédiaire parti, la greffe redevient à faire : sans ce
            # retour, un second essai sur la même décision produirait un
            # fichier sans les pistes, le mux préalable ne se déclenchant plus.
            dec.external_tracks = dec.premuxed_tracks
            dec.premuxed_tracks = []

        # Préserve l'état SKIPPED posé par action_skip_current()
        if s.state != FileState.SKIPPED:
            s.state = FileState.SUCCESS if success else FileState.ERROR
            if not success:
                cause = diagnostiquer(journal)
                s.error_msg = (cause or s.last_line)[:60]
                if cause:
                    # Le détail complet reste sous les yeux, sous la cause.
                    s.last_line = f"{cause}  —  ffmpeg : {s.last_line}"

        self.app.call_from_thread(self._update_row, next_idx)
        self.app.call_from_thread(self._update_header)
        self._process = None

        # Enchaîne le suivant
        self._encode_next()

    def _audio_prepass(self, index: int, dec: FileDecision) -> Optional[Path]:
        """Produit les pistes audio finales avant l'encodage. None si échec.

        Voir `encoder.audio_prepass_needed` pour le défaut ffmpeg que cette
        passe contourne. Elle ne coûte que le temps d'un transcodage audio,
        là où la passe vidéo se compte en heures.
        """
        s   = self._statuses[index]
        src = dec.encode_source or dec.info.path
        out = src.with_name(f"{src.stem}.iris_audio.mka")
        cmd = build_audio_command(src, out, dec.audio,
                                  getattr(self.app, "ffmpeg_path", "ffmpeg"))
        self.app.call_from_thread(self._update_cmd_lines, " ".join(cmd))
        self.app.call_from_thread(
            self._update_ffmpeg_line,
            "▶ Pistes audio préparées à part — voir la note de version…")
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
            s.error_msg = f"préparation audio : code {code}"[:60]
            s.last_line = ("La préparation des pistes audio a échoué "
                           f"(code {code}).")
            self.app.call_from_thread(self._update_row, index)
            out.unlink(missing_ok=True)
            return None
        return out

    def _strip_dv(self, index: int, dec: FileDecision) -> None:
        """Retire le RPU Dolby Vision sans réencoder, puis passe au suivant.

        Trois étapes, aucune image recalculée : ffmpeg recopie le flux HEVC,
        dovi_tool en retire les NAL du RPU, mkvmerge remuxe avec les pistes de
        la source. La sortie décode bit à bit comme l'entrée, et le HDR10+
        éventuel survit — ce qu'aucun réencodage ne permet.
        """
        from core import dovi

        s      = self._statuses[index]
        source = dec.info.path
        sortie = dec.output_path

        def echouer(resume: str, detail: str) -> None:
            s.state, s.error_msg, s.last_line = FileState.ERROR, resume[:60], detail
            self.app.call_from_thread(self._update_row, index)

        dovi_path = getattr(self.app, "dovi_path", None)
        if dovi_path is None or not getattr(self.app, "mkvmerge_available", False):
            echouer("dovi_tool + mkvmerge requis",
                    "Le retrait du Dolby Vision demande dovi_tool et mkvmerge. "
                    "Relancez le preflight pour les installer.")
            self._encode_next()
            return

        # Les intermédiaires pèsent le poids du film : les poser à côté de la
        # source, sur le même volume, plutôt que dans le temp du système —
        # 30 Go de flux brut n'ont pas leur place sur le disque du système.
        brut = source.with_name(f"{source.stem}.iris_bl.hevc")
        nodv = source.with_name(f"{source.stem}.iris_nodv.hevc")
        # Les pistes audio finales, quand la décision demande un transcodage.
        # mkvmerge ne sait que recopier : sans ce fichier, le TrueHD annoncé
        # « → E-AC3 » sortait en TrueHD.
        mka  = source.with_name(f"{source.stem}.iris_audio.mka")
        # Le MP4 est recomposé par ffmpeg en une passe depuis la source : le
        # filtre `dovi_rpu` retire le RPU, l'audio se transcode au passage.
        mp4 = dec.output_container == ".mp4"
        ffmpeg_path = getattr(self.app, "ffmpeg_path", "ffmpeg")
        if mp4 and not dovi.strip_bsf_disponible(ffmpeg_path):
            echouer("ffmpeg 7.1+ requis (filtre dovi_rpu)",
                    "Le retrait du Dolby Vision vers du MP4 demande le filtre "
                    "dovi_rpu, apparu avec ffmpeg 7.1. Mettez ffmpeg à jour "
                    "depuis le preflight.")
            self._encode_next()
            return
        passe_audio = not mp4 and audio_pass_needed(dec.audio)
        n_etapes = 1 if mp4 else (4 if passe_audio else 3)
        s.percent = -1

        try:
            # Le MP4 n'a pas d'intermédiaire : sa passe unique est la dernière.
            if not mp4:
                # 1/N — extraction du flux HEVC (copie)
                cmd = dovi.build_extract_hevc_command(
                    source, brut, getattr(self.app, "ffmpeg_path", "ffmpeg"),
                    quiet=False)
                self.app.call_from_thread(self._update_cmd_lines, " ".join(cmd))
                self.app.call_from_thread(
                    self._update_ffmpeg_line,
                    f"▶ 1/{n_etapes} Extraction du flux HEVC — copie, sans réencodage…")
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
                    echouer(f"extraction HEVC : code {code}",
                            f"L'extraction du flux HEVC a échoué (code {code}).")
                    return

                # 2/N — retrait du RPU
                self.app.call_from_thread(
                    self._update_cmd_lines,
                    f"{dovi_path} remove -i {brut.name} -o {nodv.name}")
                self.app.call_from_thread(
                    self._update_ffmpeg_line,
                    f"▶ 2/{n_etapes} Retrait du RPU Dolby Vision par dovi_tool…")
                s.percent = -1
                self.app.call_from_thread(self._update_row, index)

                if not dovi.remove_dv(brut, nodv, dovi_path):
                    echouer("dovi_tool remove a échoué",
                            "dovi_tool n'a pas pu retirer le RPU du flux.")
                    return

            # 3/4 — pistes audio finales, quand la décision en transcode une.
            if passe_audio:
                cmd = build_audio_command(
                    source, mka, dec.audio,
                    getattr(self.app, "ffmpeg_path", "ffmpeg"))
                self.app.call_from_thread(self._update_cmd_lines, " ".join(cmd))
                self.app.call_from_thread(
                    self._update_ffmpeg_line,
                    "▶ 3/4 Transcodage des pistes audio…")
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
                    echouer(f"transcodage audio : code {code}",
                            f"Le transcodage des pistes audio a échoué (code {code}).")
                    return

            # N/N — remux avec les pistes de la source. mkvmerge ne sait
            # écrire que du Matroska : quand le profil demande du MP4, c'est
            # ffmpeg qui recompose, depuis la source.
            if mp4:
                cmd = dovi.build_strip_mp4(
                    source, sortie,
                    sous_titres=[st.index for st in dec.subtitles_finales],
                    ffmpeg_path=ffmpeg_path,
                    audio=dec.audio)
                self.app.call_from_thread(self._update_cmd_lines, " ".join(cmd))
                self.app.call_from_thread(
                    self._update_ffmpeg_line,
                    "▶ 1/1 Retrait du RPU et remux par ffmpeg — copie, "
                    "sans réencodage…")
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
                exclues = [ad for ad in dec.audio
                           if ad.action == AudioAction.EXCLUDE]
                cmd = build_strip_command(
                    nodv, source, sortie,
                    fps=dec.info.frame_rate,
                    tracks=dec.external_tracks,
                    audio_source=mka if passe_audio else None,
                    audio_indices=([ad.track.index for ad in dec.audio
                                    if ad.action != AudioAction.EXCLUDE]
                                   if exclues and not passe_audio else None),
                    sous_titres=[st.index for st in dec.subtitles_finales])
                self.app.call_from_thread(self._update_cmd_lines, " ".join(cmd))
                self.app.call_from_thread(
                    self._update_ffmpeg_line,
                    f"▶ {n_etapes}/{n_etapes} Remux des pistes par mkvmerge…")

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

            if code != 0 or not sortie.exists():
                detail = erreurs[-1] if erreurs else f"code {code}"
                echouer(f"remux : {detail}", f"Remux échoué — {detail}")
                return

            should_delete = (
                dec.delete_source_override
                if dec.delete_source_override is not None
                else dec.profile.get("delete_source", False)
            )
            if should_delete:
                try:
                    source.unlink()
                except OSError:
                    pass

            if s.state != FileState.SKIPPED:
                s.state   = FileState.SUCCESS
                s.percent = 1.0
            self.app.call_from_thread(self._update_row, index)
            self.app.call_from_thread(self._update_header)

        finally:
            self._process = None
            # Les deux flux bruts pèsent chacun le poids du film : les laisser
            # traîner remplirait le disque, que l'opération ait abouti ou non.
            for tmp in (brut, nodv, mka):
                try:
                    if tmp.exists():
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
        """
        from core import dovi
        from core.encoder import build_dv_video_command

        s      = self._statuses[index]
        source = dec.info.path
        sortie = dec.output_path

        def echouer(resume: str, detail: str) -> None:
            s.state, s.error_msg, s.last_line = FileState.ERROR, resume[:60], detail
            self.app.call_from_thread(self._update_row, index)

        dovi_path = getattr(self.app, "dovi_path", None)
        if dovi_path is None or not getattr(self.app, "mkvmerge_available", False):
            echouer("dovi_tool + mkvmerge requis",
                    "Préserver le Dolby Vision à travers un réencodage demande "
                    "dovi_tool et mkvmerge. Relancez le preflight pour les "
                    "installer.")
            self._encode_next()
            return

        ffmpeg_path = getattr(self.app, "ffmpeg_path", "ffmpeg")
        # Comme pour le retrait du RPU : les intermédiaires pèsent le poids de
        # la vidéo encodée, ils vont à côté de la source et non dans le temp du
        # système. Il y en a deux à la fois — `inject-rpu` ne travaille pas en
        # place — soit environ deux fois la taille de la sortie.
        rpu = source.with_name(f"{source.stem}.iris.rpu")
        p8  = source.with_name(f"{source.stem}.iris_p8.rpu")
        enc = source.with_name(f"{source.stem}.iris_enc.hevc")
        inj = source.with_name(f"{source.stem}.iris_dv.hevc")
        mka = source.with_name(f"{source.stem}.iris_audio.mka")

        passe_audio = audio_pass_needed(dec.audio)
        n_etapes    = 5 if passe_audio else 4
        if dec.info.dv_profile == 7:
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
            annoncer("Extraction des métadonnées Dolby Vision…",
                     f"{dovi_path.name} extract-rpu - -o {rpu.name}")
            if not dovi.extract_rpu_depuis_source(source, rpu, dovi_path, ffmpeg_path):
                echouer("extraction du RPU échouée",
                        "dovi_tool n'a pas pu extraire les métadonnées Dolby "
                        "Vision de la source. Le réencodage les aurait "
                        "détruites : on s'arrête plutôt que de rendre un "
                        "fichier sans Dolby Vision.")
                return
            if s.state == FileState.SKIPPED:
                return

            # 2 — profil 7 → 8.1
            if dec.info.dv_profile == 7:
                annoncer("Conversion du RPU en profil 8.1…",
                         f"{dovi_path.name} convert -m 2 -i {rpu.name}")
                if not dovi.convert_p7_to_p8(rpu, p8, dovi_path):
                    echouer("conversion RPU 7 → 8.1 échouée",
                            "dovi_tool n'a pas pu convertir le RPU du profil 7 "
                            "vers le profil 8.1.")
                    return
                p8.replace(rpu)

            # 3 — l'encodage vidéo, seul
            cmd = build_dv_video_command(dec, self._platform, enc, ffmpeg_path)
            annoncer("Encodage de la vidéo…", " ".join(cmd))
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
                echouer(f"encodage vidéo : code {code}",
                        f"L'encodage de la vidéo a échoué (code {code}).")
                return

            # 4 — le RPU revient
            annoncer("Réinjection du Dolby Vision…",
                     f"{dovi_path.name} inject-rpu -i {enc.name} --rpu-in {rpu.name}")
            if not dovi.inject_rpu(enc, rpu, inj, dovi_path):
                echouer("réinjection du RPU échouée",
                        "dovi_tool n'a pas pu réinjecter le RPU. La cause la "
                        "plus courante est un nombre d'images différent entre "
                        "la source et l'encodage.")
                return
            if s.state == FileState.SKIPPED:
                return

            # 5 — pistes audio finales, quand la décision en transcode une
            if passe_audio:
                cmd = build_audio_command(source, mka, dec.audio, ffmpeg_path)
                annoncer("Transcodage des pistes audio…", " ".join(cmd))
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
                    echouer(f"transcodage audio : code {code}",
                            f"Le transcodage des pistes audio a échoué (code {code}).")
                    return

            # N — remux par mkvmerge. Le conteneur est forcément du Matroska :
            # la décision l'impose dès qu'elle retient ENCODE_DV.
            exclues = [ad for ad in dec.audio if ad.action == AudioAction.EXCLUDE]
            cmd = build_strip_command(
                inj, source, sortie,
                fps=dec.info.frame_rate,
                tracks=dec.external_tracks,
                audio_source=mka if passe_audio else None,
                audio_indices=([ad.track.index for ad in dec.audio
                                if ad.action != AudioAction.EXCLUDE]
                               if exclues and not passe_audio else None),
                sous_titres=[st.index for st in dec.subtitles_finales])
            annoncer("Remux des pistes par mkvmerge…", " ".join(cmd))
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
            if code != 0 or not sortie.exists():
                detail = mux.errors[-1] if mux.errors else f"code {code}"
                echouer(f"remux : {detail}", f"Remux échoué — {detail}")
                return

            should_delete = (
                dec.delete_source_override
                if dec.delete_source_override is not None
                else dec.profile.get("delete_source", False)
            )
            if should_delete:
                try:
                    source.unlink()
                except OSError:
                    pass

            if s.state != FileState.SKIPPED:
                s.state   = FileState.SUCCESS
                s.percent = 1.0
            self.app.call_from_thread(self._update_row, index)
            self.app.call_from_thread(self._update_header)

        finally:
            self._process = None
            # Deux flux bruts de la taille de la vidéo encodée : les laisser
            # traîner remplirait le disque, que l'opération ait abouti ou non.
            for tmp in (rpu, p8, enc, inj, mka):
                try:
                    if tmp.exists():
                        tmp.unlink()
                except OSError:
                    pass
            self._encode_next()

    def _premux(self, index: int, dec: FileDecision) -> bool:
        """
        Greffe les pistes par mkvmerge avant l'encodage. False si ça échoue.

        Appelée depuis le thread d'encodage : mkvmerge tourne jusqu'au bout
        avant que ffmpeg démarre.
        """
        s = self._statuses[index]
        if not getattr(self.app, "mkvmerge_available", False):
            s.state     = FileState.ERROR
            s.error_msg = "mkvmerge requis (étirement)"
            s.last_line = ("Une piste demande un facteur d'étirement : seul "
                           "mkvmerge sait l'appliquer. Relancez le preflight "
                           "pour l'installer.")
            self.app.call_from_thread(self._update_row, index)
            return False

        sortie = premux_output_path(dec.info.path)
        try:
            cmd = build_mux_command(dec.info.path, dec.external_tracks, sortie)
        except ValueError as e:
            s.state, s.error_msg, s.last_line = FileState.ERROR, str(e)[:60], str(e)
            self.app.call_from_thread(self._update_row, index)
            return False

        self.app.call_from_thread(self._update_cmd_lines, " ".join(cmd))
        self.app.call_from_thread(
            self._update_ffmpeg_line,
            "▶ Greffe des pistes par mkvmerge (étirement) avant encodage…")

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

        if code != 0 or not sortie.exists():
            # Interrompu ou échoué, l'intermédiaire pèse le poids du film.
            sortie.unlink(missing_ok=True)
            detail = proc.errors[-1] if proc.errors else f"code {code}"
            s.state, s.error_msg = FileState.ERROR, f"mux : {detail}"[:60]
            s.last_line = f"Mux préalable échoué — {detail}"
            self.app.call_from_thread(self._update_row, index)
            return False

        # L'intermédiaire porte désormais les pistes : ffmpeg n'a plus qu'à
        # l'encoder. info.path reste la source, dont dépend le nom de sortie.
        # Les pistes quittent `external_tracks` — ffmpeg ne doit pas rouvrir
        # les donneurs — mais elles ne sont pas oubliées pour autant : la
        # commande d'encodage a encore à les mapper depuis l'intermédiaire.
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
        lignes = [f"Terminé — réussis : {compte[FileState.SUCCESS]}"
                  f" · en échec : {compte[FileState.ERROR]}"
                  f" · ignorés : {compte[FileState.SKIPPED]}"]
        sorties = [s.decision.output_path for s in self._statuses
                   if s.state == FileState.SUCCESS]
        lignes += [f"→ {p}" for p in sorties[:self._SORTIES_LISTEES]]
        reste = len(sorties) - self._SORTIES_LISTEES
        if reste > 0:
            lignes.append(f"   … et {reste} autres")
        return "\n".join(lignes)

    def _on_all_done(self) -> None:
        from ..common import touche
        app = self.app
        if app.current_mode == app.MODE_ENCODAGES:  # type: ignore[attr-defined]
            self._vu = True
        else:
            app.notify(f"Lot d'encodage terminé — {touche('f12')} pour le bilan.",
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
        self.notify("Seul un fichier en attente se déplace ou se retire — "
                    "celui qui tourne et ceux qui sont finis restent.",
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
        self.notify(f"{retire.decision.info.path.name} retiré de la file.",
                    timeout=3)

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
        """Termine l'encodage en cours et passe au fichier suivant."""
        if self._process is None or self._done:
            return
        if 0 <= self._current_idx < len(self._statuses):
            s = self._statuses[self._current_idx]
            s.state    = FileState.SKIPPED
            s.last_line = "Passé manuellement"
            self._update_row(self._current_idx)
        # terminate() ferme le process : la boucle iter_progress se termine,
        # _encode_next() enchaîne automatiquement sur le suivant
        self._process.terminate()
        self._paused = False

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
                        s.last_line = "Arrêté"
                self._done = True
            self._interrompre()
            for i in range(len(self._statuses)):
                self._update_row(i)
            self._on_all_done()

        restants = self.en_attente()
        corps = "Le fichier en cours est abandonné, sa sortie partielle effacée."
        if restants:
            corps += (f"\nLes {restants} fichiers en attente ne seront pas encodés."
                      if restants > 1 else
                      "\nLe fichier en attente ne sera pas encodé.")
        self.app.push_screen(ConfirmModal(
            "Arrêter tous les encodages ?", corps,
            confirm_label="Arrêter", cancel_label="Continuer", danger=True),
            _reponse)
