"""
tui/screens/run.py — Écran d'encodage avec progression live.

Zone commande ffmpeg + ligne de retour live (non scrollable).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Label, ProgressBar, Static

from core.decision import AudioAction, FileDecision, VideoAction
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
from ..common import (actions_ecran, footer_line2, record_measured_speed,
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
        Binding("backspace", "go_back",      "Retour",             show=True),
        Binding("escape",    "go_back",      "Retour",             show=False, priority=True),
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
        self._platform  = platform
        self._statuses  = [
            FileRunStatus(decision=dec) for dec in decisions
        ]
        self._current_idx  = -1
        self._process:     EncoderProcess | None = None
        self._paused       = False
        self._started      = False
        self._done         = False

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
            nav=footer_line2(back=True, nav=True, accueil=True),
        )

    def on_mount(self) -> None:
        self._build_table()
        self._update_header()
        self.action_start()

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
        table.add_column("État",    width=50,                             key="state")

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
                    FileState.SUCCESS:  Text("✓ SUCCÈS",         style="bold green"),
                    FileState.ERROR:    Text(f"✗ ERREUR : {s.error_msg[:30]}", style="bold dark_orange"),
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
            finis   = {FileState.SUCCESS, FileState.ERROR, FileState.SKIPPED}
            total   = len(self._statuses)
            done    = sum(1 for s in self._statuses if s.state in finis)
            # `percent` vaut -1 tant que ffmpeg n'a pas rendu de durée : une
            # progression inconnue compte pour rien, jamais pour du négatif.
            encours = sum(min(1.0, max(0.0, s.percent))
                          for s in self._statuses
                          if s.state not in finis)
            profile = self.app.active_profile_id  # type: ignore[attr-defined]
            bar_pct = int((done + encours) / total * 100) if total else 0
            self.query_one("#run-header-bar", Static).update(
                f" Encodage — {total} fichiers · Profil : {profile}"
                f" ── {done}/{total} terminés ── Global : {bar_pct}%"
            )
            self.query_one("#global-bar", ProgressBar).progress = bar_pct
        except Exception:
            pass

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
        # Cherche le prochain fichier à encoder
        next_idx = self._current_idx + 1
        while next_idx < len(self._statuses):
            s   = self._statuses[next_idx]
            dec = s.decision
            if dec.video.action == VideoAction.SKIP:
                s.state = FileState.SKIPPED
                self.app.call_from_thread(self._update_row, next_idx)
                next_idx += 1
                continue
            break
        else:
            # Tout terminé
            self._done = True
            self.app.call_from_thread(self._on_all_done)
            return

        self._current_idx = next_idx
        s = self._statuses[next_idx]
        s.state = FileState.RUNNING
        self.app.call_from_thread(self._update_row, next_idx)

        # Retrait du Dolby Vision seul : aucun réencodage, donc aucun appel à
        # build_command. Le fichier suivant est enchaîné par _strip_dv.
        if dec.video.action == VideoAction.STRIP_DV:
            self._strip_dv(next_idx, dec)
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
            s.last_line = (
                f"Cette machine ne sait pas encoder avec « {choisi} » — sondé "
                f"au lancement. L'AV1 par NVENC demande une RTX 40 ou plus "
                f"récente ; le HEVC et le H264 restent disponibles.")
            self.app.call_from_thread(self._update_row, next_idx)
            self._encode_next()
            return

        proc = EncoderProcess(cmd, dec.info.duration)
        self._process = proc
        proc.start()

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
        self._process = proc
        proc.start()
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
        # Le MP4 est recomposé par ffmpeg, qui transcode dans la même passe.
        passe_audio = (dec.output_container != ".mp4"
                       and audio_pass_needed(dec.audio))
        n_etapes = 4 if passe_audio else 3
        s.percent = -1

        try:
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
            self._process = proc
            proc.start()
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
                self._process = proc
                proc.start()
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
            # ffmpeg qui recompose.
            if dec.output_container == ".mp4":
                cmd = dovi.build_strip_remux_mp4(
                    nodv, source, sortie,
                    fps=dec.info.frame_rate,
                    sous_titres=[st.index for st in dec.subtitles_finales],
                    ffmpeg_path=getattr(self.app, "ffmpeg_path", "ffmpeg"),
                    audio=dec.audio)
                self.app.call_from_thread(self._update_cmd_lines, " ".join(cmd))
                self.app.call_from_thread(
                    self._update_ffmpeg_line,
                    f"▶ {n_etapes}/{n_etapes} Remux des pistes par ffmpeg…")
                proc = EncoderProcess(cmd, dec.info.duration)
                self._process = proc
                proc.start()
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
                mux.start()
                for ligne, pourcent in mux.iter_progress():
                    if pourcent is not None:
                        s.percent = pourcent / 100.0
                        self.app.call_from_thread(self._update_row, index)
                    elif ligne:
                        self.app.call_from_thread(self._update_ffmpeg_line, ligne)
                code = mux.wait()
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
        proc.start()
        for ligne, pourcent in proc.iter_progress():
            if pourcent is not None:
                s.percent = pourcent
                self.app.call_from_thread(self._update_row, index)
            elif ligne:
                self.app.call_from_thread(self._update_ffmpeg_line, ligne)
        code = proc.wait()

        if code != 0 or not sortie.exists():
            detail = proc.errors[-1] if proc.errors else f"code {code}"
            s.state, s.error_msg = FileState.ERROR, f"mux : {detail}"[:60]
            s.last_line = f"Mux préalable échoué — {detail}"
            self.app.call_from_thread(self._update_row, index)
            return False

        # L'intermédiaire porte désormais les pistes : ffmpeg n'a plus qu'à
        # l'encoder. info.path reste la source, dont dépend le nom de sortie.
        dec.encode_source   = sortie
        dec.external_tracks = []
        s.percent = -1
        self.app.call_from_thread(self._update_row, index)
        return True

    def _on_all_done(self) -> None:
        try:
            self._update_header()
            self.query_one("#cmd-lines",   Static).update("Terminé.")
            self.query_one("#ffmpeg-line", Static).update("")
        except Exception:
            pass

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

    def action_go_back(self) -> None:
        if self._process and not self._done:
            output_path = None
            if 0 <= self._current_idx < len(self._statuses):
                output_path = self._statuses[self._current_idx].decision.output_path
            self._process.terminate()
            self._process.wait()  # attend la libération du fichier par ffmpeg
            if output_path is not None:
                try:
                    output_path.unlink(missing_ok=True)
                except Exception:
                    pass
        self.app.pop_screen()

    def action_accueil(self) -> None:
        """Retour au choix du fichier, sans repasser par les écrans intermédiaires."""
        retour_accueil(self.app)
