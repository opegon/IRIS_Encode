"""
tui/screens/profile_picker.py — Sélecteur de profil en table à colonnes.

Remplace le rendu en chaînes paddées à la main (ValuePicker) par une vraie
DataTable : colonnes alignées, profil actif marqué ✓, valeurs Dolby Vision
colorées, alerte suppression de la source.

Retourne l'id du profil choisi (str), ou None si annulé.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import DataTable, Label, Static

from ..common import (PROFIL_COLONNES, cellules_profil, largeurs_colonnes,
                      raccourcis)

if TYPE_CHECKING:
    from core.profiles import Profile

class ProfilePickerScreen(ModalScreen[str | None]):
    """Modal de sélection de profil — mêmes touches que ValuePicker."""

    CSS = """
    ProfilePickerScreen {
        align: center middle;
    }
    #profile-picker-box {
        background: $surface;
        border: solid $accent;
        height: auto;
        max-height: 26;
        padding: 1 2;
    }
    #profile-picker-title {
        text-align: center;
        width: 100%;
        color: $accent;
        margin-bottom: 1;
    }
    #profile-picker-table {
        height: auto;
        max-height: 18;
    }
    #profile-picker-hint {
        color: $text-muted;
        width: 100%;
        text-align: center;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("enter",     "select", "Choisir", show=False, priority=True),
        Binding("escape",    "cancel", "Annuler", show=False, priority=True),
        Binding("backspace", "cancel", "Retour",  show=False, priority=True),
    ]

    def __init__(
        self,
        profiles:   dict[str, "Profile"],
        current_id: str,
        title:      str = "Sélectionner un profil",
    ) -> None:
        super().__init__()
        self._profiles   = profiles
        self._names      = list(profiles.keys())
        self._current_id = current_id
        self._title      = title

    # ── Composition ───────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Static(id="profile-picker-box"):
            yield Label(self._title, id="profile-picker-title")
            yield DataTable(id="profile-picker-table", cursor_type="row",
                            show_header=True, zebra_stripes=True)
            yield Static(raccourcis([("enter", "Choisir"), ("escape", "Annuler")]),
                         id="profile-picker-hint")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)

        rows = [cellules_profil(n, p, n == self._current_id)
                for n, p in self._profiles.items()]
        widths = largeurs_colonnes(PROFIL_COLONNES, rows)
        for header, w in zip(PROFIL_COLONNES, widths):
            table.add_column(header, width=w)

        for name, cells in zip(self._names, rows):
            table.add_row(*cells, key=name)

        # Largeur du panneau : colonnes + séparateurs (1/col) + padding/bordure
        self.query_one("#profile-picker-box").styles.width = sum(widths) + len(widths) + 10

        cur_idx = self._names.index(self._current_id) if self._current_id in self._names else 0
        table.move_cursor(row=cur_idx)
        table.focus()

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_select(self) -> None:
        row = self.query_one(DataTable).cursor_row
        if 0 <= row < len(self._names):
            self.dismiss(self._names[row])
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
