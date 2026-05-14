"""
tui/app.py — Application Textual principale IRIS ENCODE.

Point d'entrée TUI. Maintient l'état global (profils, config, platform).
"""
from __future__ import annotations

from pathlib import Path

from textual.app import App
from textual.binding import Binding

import core.config as cfg_mod
import core.profiles as prof_mod
from core.platform import PlatformProfile, detect as detect_platform


class IrisEncodeApp(App):
    """Application principale IRIS ENCODE."""

    TITLE     = "IRIS ENCODE"
    SUB_TITLE = "v0.1"

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
        self.start_path        = (start_path or Path.cwd()).resolve()
        self.cfg               = cfg_mod.load()
        self.profiles          = prof_mod.load_all()
        self.active_profile_id = "default"
        self.platform:         PlatformProfile = detect_platform()

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
