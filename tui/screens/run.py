"""
tui/screens/run.py — Écran d'encodage avec progression live.

Zone commande ffmpeg + ligne de retour live (non scrollable).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.screen import Screen
from textual.widgets import DataTable, Header, Label, ProgressBar, Static
from ..widgets.footer import TwoLineFooter
from ..mixins import TableNavMixin

from core.decision import FileDecision, VideoAction
from core.encoder import EncoderProcess, ProgressInfo, build_command
from core.platform import PlatformProfile

if TYPE_CHECKING:
    pass


# ─── État fichier ─────────────────────────────────────────────────────────────

class FileState(Enum):
    PENDING  = auto()
    RUNNING  = auto()
    SUCCESS  = auto()
    ERROR    = auto()
    SKIPPED  = auto()


@dataclass
class FileRunStatus:
    decision:  FileDecision
    state:     FileState = FileState.PENDING
    percent:   float     = 0.0
    last_line: str       = ""
    error_msg: str       = ""


# ─── Messages inter-threads ───────────────────────────────────────────────────

class ProgressUpdate(Message):
    def __init__(self, index: int, info: ProgressInfo, line: str) -> None:
        super().__init__()
        self.index = index
        self.info  = info
        self.line  = line


class EncodeFinished(Message):
    def __init__(self, index: int, success: bool, error: str = "") -> None:
        super().__init__()
        self.index   = index
        self.success = success
        self.error   = error


class AllFinished(Message):
    pass


# ─── Écran ────────────────────────────────────────────────────────────────────

class RunScreen(TableNavMixin, Screen):
    """Écran d'encodage séquentiel avec suivi progression."""

    BINDINGS = [
        Binding("enter",     "start",        "Démarrer",           show=True, priority=True),
        Binding("p",         "pause_resume", "Pause / Reprendre",  show=True),
        Binding("backspace", "go_back",      "Retour",             show=True),
        Binding("escape",    "go_back",      "Retour",             show=False, priority=True),
    ]

    DEFAULT_CSS = """
    RunScreen { layout: vertical; }
    #run-header-bar {
        height: 1;
        background: $accent;
        padding: 0 2;
    }
    #file-table {
        height: 1fr;
    }
    #cmd-zone {
        height: 5;
        background: $panel;
        padding: 0 1;
        border-top: solid $primary;
        layout: vertical;
    }
    #cmd-lines {
        height: auto;
        color: $text-muted;
        width: 1fr;
    }
    #ffmpeg-line {
        color: $text;
        height: 1;
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
        yield Header(show_clock=True)
        yield Static("", id="run-header-bar")
        yield DataTable(id="file-table", cursor_type="row", zebra_stripes=True)
        with Static(id="global-bar-row"):
            yield Label("Global", id="global-label")
            yield ProgressBar(total=100, show_eta=False, id="global-bar")
        with Static(id="cmd-zone"):
            yield Static("", id="cmd-lines")
            yield Static("", id="ffmpeg-line")
        yield TwoLineFooter(
            line1=[
                ("enter",     "Démarrer"),
                ("p",         "Pause / Reprendre"),
                ("backspace", "Retour"),
            ],
            line2=[
                ("home",     "Début liste"),
                ("end",      "Fin liste"),
                ("f10",      "Quitter"),
            ],
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
        table.add_column("État",    width=None,                            key="state")

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
        s     = self._statuses[index]
        table = self.query_one(DataTable)

        # Gère le cas où la durée est inconnue (percent = -1)
        if s.state == FileState.RUNNING:
            if s.percent < 0:
                running_txt = "en cours…"
            else:
                running_txt = f"{s.percent * 100:.0f}%"
            state_txt = Text(running_txt, style="yellow")
        else:
            state_txt = {
                FileState.PENDING:  Text("en attente",      style="dim"),
                FileState.SUCCESS:  Text("✓ SUCCÈS",         style="bold green"),
                FileState.ERROR:    Text(f"✗ ERREUR : {s.error_msg[:30]}", style="bold dark_orange"),
                FileState.SKIPPED:  Text("ignoré",           style="dim"),
            }[s.state]
        try:
            table.update_cell(str(index), "icon",  self._icon(s),  update_width=False)
            table.update_cell(str(index), "state", state_txt,       update_width=False)
        except Exception:
            pass

    def _update_header(self) -> None:
        done    = sum(1 for s in self._statuses if s.state in {FileState.SUCCESS, FileState.ERROR})
        total   = len(self._statuses)
        profile = self.app.active_profile_id  # type: ignore[attr-defined]
        bar_pct = int(done / total * 100) if total else 0
        self.query_one("#run-header-bar", Static).update(
            f" Encodage — {total} fichiers · Profil : {profile} ── Global : {bar_pct}%"
        )
        self.query_one("#global-bar", ProgressBar).progress = bar_pct

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

        cmd = build_command(dec, self._platform)
        self.app.call_from_thread(
            self.query_one("#cmd-lines", Static).update,
            " ".join(cmd),
        )

        proc = EncoderProcess(cmd, dec.info.duration)
        self._process = proc
        proc.start()

        # Affiche "Encodage lancé" jusqu'à première ligne
        self.app.call_from_thread(
            self.query_one("#ffmpeg-line", Static).update,
            "▶ Encodage lancé, initialisation en cours…"
        )
        s.percent = -1  # Force "en cours…" au lieu de "0%"
        self.app.call_from_thread(self._update_row, next_idx)

        # Affiche toutes les lignes (avec ou sans progression)
        for line, progress in proc.iter_progress():
            s.last_line = line
            if progress:
                s.percent = progress.percent
            self.app.call_from_thread(
                self.query_one("#ffmpeg-line", Static).update,
                line
            )
            # Met à jour row et header seulement si progression
            if progress:
                self.app.call_from_thread(self._update_row, next_idx)
                self.app.call_from_thread(self._update_header)

        rc = proc.wait()
        success = rc == 0

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

        s.state = FileState.SUCCESS if success else FileState.ERROR
        if not success:
            s.error_msg = s.last_line[:60]

        self.app.call_from_thread(self._update_row, next_idx)
        self.app.call_from_thread(self._update_header)
        self._process = None

        # Enchaîne le suivant
        self._encode_next()

    def _update_progress(self, index: int, line: str, info: ProgressInfo) -> None:
        s = self._statuses[index]
        s.last_line = line
        s.percent   = info.percent
        self._update_row(index)
        self.query_one("#ffmpeg-line", Static).update(line)

    def _on_all_done(self) -> None:
        self._update_header()
        self.query_one("#cmd-lines",   Static).update("Terminé.")
        self.query_one("#ffmpeg-line", Static).update("")

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

    def action_go_back(self) -> None:
        if self._process and not self._done:
            self._process.terminate()
        self.app.pop_screen()
