"""
tui/screens/value_picker.py — Modal de sélection de valeur.

Affiche une liste de valeurs et retourne la valeur choisie (ou None).
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import DataTable, Label, Static


class ValuePickerScreen(ModalScreen[int | None]):
    """
    Modal léger : liste de valeurs sélectionnables.
    Retourne l'index de la valeur choisie, ou None si annulé.
    width=None → calculé automatiquement depuis le contenu (min 40).
    """

    CSS = """
    ValuePickerScreen {
        align: center middle;
    }
    #picker-box {
        background: $surface;
        border: thick $accent;
        height: auto;
        max-height: 24;
        padding: 1 2;
    }
    #picker-title {
        text-align: center;
        width: 100%;
        color: $accent;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("enter",     "select",  "Choisir",  show=True, priority=True),
        Binding("escape",    "cancel",  "Annuler",  show=True, priority=True),
        Binding("backspace", "cancel",  "Retour",   show=False, priority=True),
    ]

    def __init__(
        self,
        title: str,
        options: list[str],
        current_idx: int = 0,
        width: int | None = None,
    ) -> None:
        super().__init__()
        self._title       = title
        self._options     = options
        self._current_idx = current_idx
        # "→ " (2) + option + padding (4) + border (4) = 10 overhead
        auto = max(40, max((len(o) for o in options), default=0) + 10)
        self._width       = width if width is not None else auto

    def compose(self) -> ComposeResult:
        with Static(id="picker-box"):
            yield Label(self._title, id="picker-title")
            yield DataTable(id="picker-table", cursor_type="row",
                            show_header=False, zebra_stripes=True)

    def on_mount(self) -> None:
        self.query_one("#picker-box").styles.width = self._width
        table = self.query_one(DataTable)
        table.add_column("", width=None, key="val")
        for i, opt in enumerate(self._options):
            marker = "→ " if i == self._current_idx else "  "
            style  = "bold white" if i == self._current_idx else ""
            table.add_row(
                Text(marker + opt, style=style, no_wrap=True),
                key=str(i),
            )
        table.move_cursor(row=self._current_idx)
        table.focus()

    def action_select(self) -> None:
        self.dismiss(self.query_one(DataTable).cursor_row)

    def action_cancel(self) -> None:
        self.dismiss(None)
