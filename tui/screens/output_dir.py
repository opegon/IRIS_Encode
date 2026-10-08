"""
tui/screens/output_dir.py — Choix d'un dossier de sortie (IE-118).

Une source dans un dossier en lecture seule — un ISO monté, surtout — ne peut
pas recevoir sa sortie à côté d'elle. La modale s'ouvre sur le dossier proposé
(réglage `[app] output_dir`, Options) : `Entrée` sur la première ligne le
retient, les autres lignes y naviguent. ⌫ remonte, jusqu'à la liste des volumes.

Rend le dossier choisi, ou None si l'on renonce.
"""
from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import DataTable, Label, Static

from core.decision import dossier_inscriptible
from core.i18n import _, N_

from ..common import cellule, raccourcis
from ..widgets.file_tree import list_volumes

_ICONE_DOSSIER = "📁"
_ICI           = "__ici__"


class OutputDirScreen(ModalScreen["Path | None"]):
    """Navigation dans les dossiers ; la première ligne retient le courant."""

    CSS = """
    OutputDirScreen { align: center middle; }
    #outdir-box {
        background: $surface;
        border: solid $accent;
        width: 90;
        max-width: 96%;
        height: 26;
        padding: 1 2;
    }
    #outdir-title { text-align: center; width: 100%; color: $accent; }
    #outdir-note  { color: $text-muted; width: 100%; }
    #outdir-path  { width: 100%; margin: 1 0; text-style: bold; }
    #outdir-table { height: 1fr; }
    #outdir-error { color: $error; width: 100%; height: 1; }
    #outdir-hint  { color: $text-muted; width: 100%; text-align: center; }
    """

    BINDINGS = [
        Binding("enter",     "select", N_("Open"),   show=True, priority=True),
        Binding("backspace", "go_up",  N_("Up"),     show=True, priority=True),
        Binding("escape",    "cancel", N_("Cancel"), show=True, priority=True),
    ]

    def __init__(self, depart: Path, note: str = "") -> None:
        super().__init__()
        # None = la liste des volumes, au-dessus des racines.
        self._dir: Path | None = depart
        self._note    = note
        self._entries: list[Path | str] = []

    def compose(self) -> ComposeResult:
        with Static(id="outdir-box"):
            yield Label(_("Output folder"), id="outdir-title")
            yield Static(self._note, id="outdir-note", markup=False)
            yield Static("", id="outdir-path", markup=False)
            yield DataTable(id="outdir-table", cursor_type="row",
                            show_header=False, zebra_stripes=True)
            yield Static("", id="outdir-error", markup=False)
            yield Static(raccourcis([("enter", N_("Open")),
                                     ("backspace", N_("Up")),
                                     ("escape", N_("Cancel"))]), id="outdir-hint")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_column("", width=None, key="name")
        self._populate()
        table.focus()

    def _populate(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        self._entries = []
        self.query_one("#outdir-error", Static).update("")
        if self._dir is None:
            self.query_one("#outdir-path", Static).update(_("Volumes"))
            enfants = list_volumes()
        else:
            self.query_one("#outdir-path", Static).update(str(self._dir))
            table.add_row(cellule("✔ " + _("Write to this folder"), style="bold green"),
                          key=_ICI)
            self._entries.append(_ICI)
            try:
                enfants = sorted((p for p in self._dir.iterdir() if p.is_dir()),
                                 key=lambda p: p.name.lower())
            except OSError:
                enfants = []
        for p in enfants:
            nom = str(p) if self._dir is None else p.name
            table.add_row(Text(f"{_ICONE_DOSSIER} {nom}", style="bold cyan"), key=str(p))
            self._entries.append(p)
        if table.row_count:
            table.move_cursor(row=0)

    def action_select(self) -> None:
        row = self.query_one(DataTable).cursor_row
        if not (0 <= row < len(self._entries)):
            return
        entry = self._entries[row]
        if entry == _ICI:
            assert self._dir is not None
            if not dossier_inscriptible(self._dir):
                self.app.bell()
                self.query_one("#outdir-error", Static).update(
                    _("This folder is read-only — choose another one."))
                return
            self.dismiss(self._dir)
            return
        self._dir = entry
        self._populate()

    def action_go_up(self) -> None:
        """Le dossier parent ; depuis une racine, la liste des volumes."""
        if self._dir is None:
            return
        self._dir = None if self._dir.parent == self._dir else self._dir.parent
        self._populate()

    def action_cancel(self) -> None:
        self.dismiss(None)
