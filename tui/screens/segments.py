"""
tui/screens/segments.py — Détail des plages de décalage détectées.

Quand la mesure refuse parce que le décalage ne tient pas sur tout le film,
elle rend les plages sur lesquelles il tient. Le bandeau de l'écran de
recalage n'a que trois lignes : le détail vit ici.

Écran de lecture seule — rien n'est appliqué depuis cette table.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import DataTable, Label, Static

from core.sync import Segment, mmss

_COLUMNS = ["Plage", "Durée", "Décalage", "Écart", "Confiance"]


class SegmentsScreen(ModalScreen[None]):
    """Plages de décalage d'une mesure refusée."""

    CSS = """
    SegmentsScreen {
        align: center middle;
    }
    #segments-box {
        background: $surface;
        border: thick $warning;
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
        Binding("escape",    "close", "Fermer", show=False, priority=True),
        Binding("backspace", "close", "Fermer", show=False, priority=True),
        Binding("enter",     "close", "Fermer", show=False, priority=True),
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

        conf = Text(f"{seg.confidence:.2f}",
                    style="" if seg.confidence >= 0.30 else "dim", no_wrap=True)
        return [plage, duree, delay, ecart, conf]

    # ── Composition ───────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        titre = "Plages de décalage détectées"
        if self._track:
            titre += f" — {self._track}"
        with Static(id="segments-box"):
            yield Label(titre, id="segments-title")
            yield DataTable(id="segments-table", cursor_type="row",
                            show_header=True, zebra_stripes=True)
            yield Static("", id="segments-note")
            yield Static("Esc  Fermer", id="segments-hint")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        rows  = [self._row_cells(i, s) for i, s in enumerate(self._segments)]

        widths = [
            max(len(_COLUMNS[i]), max((len(r[i].plain) for r in rows), default=0))
            for i in range(len(_COLUMNS))
        ]
        for header, w in zip(_COLUMNS, widths):
            table.add_column(header, width=w)
        for row in rows:
            table.add_row(*row)

        self.query_one("#segments-note", Static).update(self._note())

    def _note(self) -> Text:
        """Ce que ces plages veulent dire, et ce qu'on ne peut pas en faire."""
        total = (self._segments[-1].delay_ms - self._segments[0].delay_ms
                 if self._segments else 0)
        return Text(
            f"Chaque plage est alignée, à son propre décalage — les deux "
            f"fichiers portent le même contenu\n"
            f"dans deux montages différents ({total:+d} ms accumulés). "
            f"Un décalage unique ne peut pas les\n"
            f"recaler : la greffe demanderait de fabriquer une piste corrigée.",
            style="dim",
        )

    def action_close(self) -> None:
        self.dismiss(None)
