"""
tui/app.py — Application Textual principale IRIS ENCODE.

Point d'entrée TUI. Maintient l'état global (profils, config, platform).
"""
from __future__ import annotations

import logging
from pathlib import Path

from textual.app import App
from textual.binding import Binding

import core.config as cfg_mod
import core.profiles as prof_mod
from core.platform import PlatformProfile, detect as detect_platform


def _setup_logging() -> None:
    """Logge dans iris_encode.log à côté du dossier de l'app (warnings et +)."""
    log_path = Path.home() / ".iris_encode" / "iris_encode.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_path),
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


class IrisEncodeApp(App):
    """Application principale IRIS ENCODE."""

    TITLE     = "IRIS ENCODE"
    SUB_TITLE = "v0.5"

    CSS = """
    Screen { background: $surface; }
    Header { background: $primary; }
    Footer { background: $primary-darken-2; }
    """

    BINDINGS = [
        Binding("f10",    "request_quit", "F10 Quitter", show=True,  priority=True),
        Binding("ctrl+c", "request_quit", "Quitter",     show=False, priority=True),
    ]

    def __init__(self, start_path: Path | None = None) -> None:
        super().__init__()
        _setup_logging()
        self.start_path        = (start_path or Path.cwd()).resolve()
        self.cfg               = cfg_mod.load()
        self.profiles          = prof_mod.load_all()
        self.active_profile_id = "serie_basic"
        self.platform:         PlatformProfile = detect_platform()
        # Câble dovi_tool dans le scanner (enrichissement DV au scan)
        from core import dovi, scanner
        bin_dir   = cfg_mod.get_bin_dir(self.cfg)
        dovi_path = dovi.get_path(bin_dir)
        if dovi_path is not None:
            scanner.set_dovi_path(dovi_path)
        # Précise le chemin ffmpeg utilisé pour le probing DV
        from core.preflight import get_tool_path
        ffmpeg_p = get_tool_path("ffmpeg", bin_dir)
        if ffmpeg_p:
            scanner.set_ffmpeg_path(ffmpeg_p)

    def on_mount(self) -> None:
        from tui.screens.browser import BrowserScreen
        self.push_screen(BrowserScreen(self.start_path, start_virtual=True))

    def action_request_quit(self) -> None:
        """Affiche la modal de confirmation avant de quitter."""
        from tui.screens.quit import QuitConfirmScreen
        self.push_screen(QuitConfirmScreen(), self._on_quit_answer)

    def _on_quit_answer(self, confirmed: bool) -> None:
        if confirmed:
            self.exit()

    # Surcharge de l'action native Textual (Ctrl+C système)
    def action_quit(self) -> None:
        self.action_request_quit()
