"""
tui/screens/sar.py — Choisir la proportion d'une source SD qui n'en déclare
pas (IE-173).

Un DVD converti en AVI sans redimensionnement a perdu la forme de ses pixels :
4:3 ou 16:9, l'image ne le dit pas avec certitude. La fenêtre montre
l'estimation de l'analyse et ce qui la fonde, puis le rendu de chaque
hypothèse (définition affichée, format de l'image utile). Elle rend le SAR
choisi — « » pour laisser les pixels carrés —, ou None.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import DataTable, Label, Static

from core import sar as sar_mod
from core.i18n import N_, _
from core.scanner import VideoInfo
from ..common import raccourcis


def libelle_estimation(info: VideoInfo) -> str:
    """« 4:3, probable — format d'origine du film » : l'hypothèse estimée et
    ce qui la fonde. « » hors doute."""
    e = info.sar_estimation
    if e is None:
        return ""
    if e.raison == sar_mod.Raison.FORMAT_CONNU:
        # TRANSLATORS: {hyp} is an aspect ratio such as 4:3.
        return _("{hyp}, probable — the film's original format").format(hyp=e.hypothese)
    if e.raison == sar_mod.Raison.BANDES:
        return _("{hyp}, probable — black bars").format(hyp=e.hypothese)
    return _("{hyp} by default — nothing decides").format(hyp=e.hypothese)


def _largeur(info: VideoInfo, sar: str) -> int:
    """La largeur affichée, paire, comme la rendra l'encodage."""
    if not sar:
        return info.width
    num, den = (int(x) for x in sar.split(":"))
    return info.width * num // den // 2 * 2


def _option(info: VideoInfo, hyp: str, sar: str) -> str:
    vue = info.sar_estimation.cadre if info.sar_estimation else None
    vue = vue or (info.width, info.height)
    ratio = sar_mod.ratio_affiche(vue, sar or "1:1")
    nom = hyp if sar else _("Leave as is (square pixels)")
    # TRANSLATORS: {ratio} is the shape of the visible picture, e.g. 1.33.
    return _("{name}  →  {w}x{h}  ·  picture {ratio}").format(
        name=nom, w=_largeur(info, sar), h=info.height, ratio=f"{ratio:.2f}")


class SarScreen(ModalScreen["str | None"]):
    """Le choix de la proportion d'un fichier sans SAR déclaré."""

    CSS = """
    SarScreen { align: center middle; }
    #sar-box {
        background: $surface;
        border: solid $accent;
        height: auto;
        width: 76;
        padding: 1 2;
    }
    #sar-titre { text-align: center; width: 100%; color: $accent; margin-bottom: 1; }
    #sar-texte { width: 100%; margin-bottom: 1; }
    #sar-table { height: auto; }
    #sar-hint  { color: $text-muted; width: 100%; text-align: center; margin-top: 1; }
    """

    BINDINGS = [
        Binding("enter",     "select", N_("Choose"), show=True,  priority=True),
        Binding("escape",    "cancel", N_("Cancel"), show=True,  priority=True),
        Binding("backspace", "cancel", N_("Back"),   show=False, priority=True),
    ]

    def __init__(self, info: VideoInfo) -> None:
        super().__init__()
        self._info  = info
        self._choix = sar_mod.choix(info)

    def _texte(self) -> Text:
        info, e = self._info, self._info.sar_estimation
        t = Text()
        t.append(_("{w}x{h} without a declared aspect ratio: the picture is "
                   "distorted until it is set.").format(w=info.width, h=info.height)
                 + "\n\n")
        t.append(_("Estimate") + "  ", style="dim")
        t.append(libelle_estimation(info) + "\n", style="bold")
        if e is not None and e.formats:
            t.append(_("Original format") + "  ", style="dim")
            t.append(" / ".join(f"{f:.2f}" for f in e.formats) + "\n")
        if e is not None and e.cadre:
            t.append(_("Visible picture") + "  ", style="dim")
            t.append(f"{e.cadre[0]}x{e.cadre[1]}\n")
        if info.sar_confirme:
            t.append(_("Chosen") + "  ", style="dim")
            t.append(self._nom(info.sar_impose) + "\n", style="bold green")
        return t

    def _nom(self, sar: str) -> str:
        for h, s in self._choix:
            if s == sar:
                return h if s else _("Leave as is (square pixels)")
        return sar

    def compose(self) -> ComposeResult:
        with Static(id="sar-box"):
            yield Label(_("Aspect ratio"), id="sar-titre")
            yield Static(self._texte(), id="sar-texte")
            yield DataTable(id="sar-table", cursor_type="row",
                            show_header=False, zebra_stripes=True)
            yield Static(raccourcis([("enter", N_("Choose")), ("escape", N_("Cancel"))]),
                         id="sar-hint")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_column("", width=None, key="val")
        actuel = next((i for i, (_h, s) in enumerate(self._choix)
                       if s == self._info.sar_impose), 0)
        estime = self._info.sar_estimation.sar if self._info.sar_estimation else None
        for i, (h, s) in enumerate(self._choix):
            t = Text("→ " if i == actuel else "  ", no_wrap=True)
            t.append(_option(self._info, h, s), style="bold white" if i == actuel else "")
            if s == estime:
                t.append("  " + _("(estimate)"), style="dim")
            table.add_row(t, key=str(i))
        table.move_cursor(row=actuel)
        table.focus()

    def action_select(self) -> None:
        self.dismiss(self._choix[self.query_one(DataTable).cursor_row][1])

    def action_cancel(self) -> None:
        self.dismiss(None)
