"""
tui/screens/segments.py — Détail des plages de décalage détectées.

Quand la mesure refuse parce que le décalage ne tient pas sur tout le film,
elle rend les plages sur lesquelles il tient. Le bandeau de l'écran de
recalage n'a que trois lignes : le détail vit ici.

Écran de lecture seule — rien n'est appliqué depuis cette table.
"""
from __future__ import annotations

from rich.cells import cell_len
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import DataTable, Label, Static

from ..common import raccourcis

from core.i18n import _, N_
from core.sync import Segment, libelle_confiance, mmss, niveau_confiance

_COLUMNS = [N_("Segment"), N_("Duration"), N_("Offset"), N_("Gap"), N_("Confidence")]


class SegmentsScreen(ModalScreen[None]):
    """Plages de décalage d'une mesure refusée."""

    CSS = """
    SegmentsScreen {
        align: center middle;
    }
    #segments-box {
        background: $surface;
        border: solid $warning;
        height: auto;
        max-height: 26;
        padding: 1 2;
    }
    #segments-title {
        text-align: center;
        width: 100%;
        color: $warning;
        margin-bottom: 1;
    }
    #segments-table {
        height: auto;
        max-height: 16;
    }
    #segments-note {
        color: $text-muted;
        width: 100%;
        margin-top: 1;
    }
    #segments-hint {
        color: $text-muted;
        width: 100%;
        text-align: center;
    }
    """

    BINDINGS = [
        Binding("escape",    "close", N_("Close"), show=False, priority=True),
        Binding("backspace", "close", N_("Close"), show=False, priority=True),
        Binding("enter",     "close", N_("Close"), show=False, priority=True),
    ]

    def __init__(self, segments: list[Segment], track_name: str = "") -> None:
        super().__init__()
        self._segments = segments
        self._track    = track_name

    # ── Cellules ──────────────────────────────────────────────────────────────

    def _row_cells(self, i: int, seg: Segment) -> list[Text]:
        plage = Text(f"{mmss(seg.start_s)} – {mmss(seg.end_s)}", no_wrap=True)
        duree = Text(mmss(seg.end_s - seg.start_s), style="dim", no_wrap=True)
        delay = Text(f"{seg.delay_ms:+d} ms", style="bold", no_wrap=True)

        # L'écart au palier précédent est ce qui se lit le mieux : c'est la
        # taille de ce qui a été inséré ou retiré à cet endroit.
        if i == 0:
            ecart = Text("—", style="dim", no_wrap=True)
        else:
            d = seg.delay_ms - self._segments[i - 1].delay_ms
            ecart = Text(f"{d:+d} ms", style="dark_orange", no_wrap=True)

        # Le style suit le niveau, pas son libellé (traduit, il ne vaudrait
        # plus « aucune » ni « faible ») : même famille qu'UX-29.
        conf = Text(libelle_confiance(seg.confidence), no_wrap=True,
                    style="dim" if niveau_confiance(seg.confidence) < 2 else "")
        return [plage, duree, delay, ecart, conf]

    # ── Composition ───────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        titre = _("Detected offset segments")
        if self._track:
            titre += f" — {self._track}"
        with Static(id="segments-box"):
            yield Label(titre, id="segments-title")
            yield DataTable(id="segments-table", cursor_type="row",
                            show_header=True, zebra_stripes=True)
            yield Static("", id="segments-note")
            yield Static(raccourcis([("escape", N_("Close"))]), id="segments-hint")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        rows  = [self._row_cells(i, s) for i, s in enumerate(self._segments)]

        entetes = [_(c) for c in _COLUMNS]
        widths = [
            max(cell_len(entetes[i]), max((r[i].cell_len for r in rows), default=0))
            for i in range(len(entetes))
        ]
        for header, w in zip(entetes, widths):
            table.add_column(header, width=w)
        for row in rows:
            table.add_row(*row)

        self.query_one("#segments-note", Static).update(self._note())

    def _note(self) -> Text:
        """Ce que ces plages veulent dire, et ce qu'on ne peut pas en faire."""
        total = (self._segments[-1].delay_ms - self._segments[0].delay_ms
                 if self._segments else 0)
        return Text(
            _("Each segment is aligned, at its own offset — both files carry "
              "the same content in two different cuts ({total} ms accumulated). "
              "A single offset cannot resync them: adding the track would "
              "require building a corrected track.").format(total=f"{total:+d}"),
            style="dim",
        )

    def action_close(self) -> None:
        self.dismiss(None)
