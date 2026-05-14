"""
tui/screens/quit.py — Modal de confirmation de sortie.
"""
from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class QuitConfirmScreen(ModalScreen[bool]):
    """
    Modal bloquant demandant confirmation avant de quitter.
    Retourne True (quitter) ou False (annuler).
    """

    CSS = """
    QuitConfirmScreen {
        align: center middle;
    }
    #dialog {
        padding: 2 4;
        background: $surface;
        border: thick $error;
        width: 44;
        height: auto;
    }
    #dialog Label {
        text-align: center;
        width: 100%;
        margin-bottom: 1;
        color: $text;
    }
    #dialog .subtitle {
        color: $text-muted;
        margin-bottom: 2;
    }
    #btn-row {
        layout: horizontal;
        align: center middle;
        width: 100%;
        height: auto;
    }
    #btn-confirm {
        margin-right: 2;
        background: $error;
        color: $text;
        border: none;
        min-width: 14;
    }
    #btn-cancel {
        background: $surface-lighten-2;
        color: $text;
        border: none;
        min-width: 14;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Annuler", show=False, priority=True),
        Binding("enter",  "confirm","Confirmer",show=False, priority=True),
        Binding("left",   "focus_confirm", "", show=False),
        Binding("right",  "focus_cancel",  "", show=False),
    ]

    def compose(self) -> ComposeResult:
        from textual.widgets import Static
        with Static(id="dialog"):
            yield Label("⚠  Quitter IRIS ENCODE ?")
            yield Label("L'encodage en cours sera interrompu.", classes="subtitle")
            with Static(id="btn-row"):
                yield Button("✓  Confirmer", id="btn-confirm", variant="error")
                yield Button("✗  Annuler",   id="btn-cancel",  variant="default")

    def on_mount(self) -> None:
        self.query_one("#btn-cancel", Button).focus()

    # ── Boutons ───────────────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-confirm")
    def _do_quit(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#btn-cancel")
    def _do_cancel(self) -> None:
        self.dismiss(False)

    # ── Clavier ───────────────────────────────────────────────────────────────

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_focus_confirm(self) -> None:
        self.query_one("#btn-confirm", Button).focus()

    def action_focus_cancel(self) -> None:
        self.query_one("#btn-cancel", Button).focus()
