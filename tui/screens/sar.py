"""
tui/screens/sar.py — Choisir la proportion d'une source SD qui n'en déclare
pas (IE-173).

Un DVD converti en AVI sans redimensionnement a perdu la forme de ses pixels :
4:3 ou 16:9, l'image ne le dit pas avec certitude. La fenêtre montre
l'estimation de l'analyse et ce qui la fonde, puis le rendu de chaque
hypothèse (définition affichée, format de l'image utile). `V` pose la même
image en 4:3 et en 16:9 côte à côte et l'ouvre dans la visionneuse du
système : la réponse ne se donne pas sans voir l'image. Elle rend le SAR
choisi — « » pour laisser les pixels carrés —, ou None.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import DataTable, Label, Static

from core import sar as sar_mod
from core.i18n import N_, _, texte_erreur
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


def _option(info: VideoInfo, hyp: str, sar: str) -> str:
    vue = info.sar_estimation.cadre if info.sar_estimation else None
    vue = vue or (info.width, info.height)
    ratio = sar_mod.ratio_affiche(vue, sar or "1:1")
    nom = hyp if sar else _("Leave as is (square pixels)")
    # TRANSLATORS: {ratio} is the shape of the visible picture, e.g. 1.33.
    return _("{name}  →  {w}x{h}  ·  picture {ratio}").format(
        name=nom, w=sar_mod.largeur_affichee(info.width, sar), h=info.height,
        ratio=f"{ratio:.2f}")


def ouvrir_image(chemin: Path) -> None:
    """Ouvre `chemin` dans la visionneuse du système."""
    if sys.platform == "win32":
        os.startfile(chemin)            # type: ignore[attr-defined]
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(chemin)],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)


def _aide() -> str:
    return raccourcis([("enter", N_("Choose")), ("v", N_("Compare")),
                       ("escape", N_("Cancel"))])


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
        Binding("v",         "comparer", N_("Compare"), show=True, priority=True),
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
            yield Static(_aide(), id="sar-hint")

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

    def action_comparer(self) -> None:
        """La même image en 4:3 et en 16:9, côte à côte, dans la visionneuse."""
        self.query_one("#sar-hint", Static).update(_("Preparing the picture…"))
        self._comparer()

    @work(thread=True, exclusive=True, name="sar-comparer")
    def _comparer(self) -> None:
        from core import encoder
        try:
            chemin = sar_mod.apercu(self._info, encoder._ffmpeg_path)
            ouvrir_image(chemin)
            texte = _("4:3 on the left, 16:9 on the right — {path}").format(path=chemin)
        except Exception as e:
            lignes = texte_erreur(e).strip().splitlines()
            texte = "⚠ " + _("Picture not produced: {cause}").format(
                cause=lignes[-1] if lignes else type(e).__name__)
        self.app.call_from_thread(self._aide_apres, texte)

    def _aide_apres(self, texte: str) -> None:
        self.query_one("#sar-hint", Static).update(texte + "\n" + _aide())

    def action_select(self) -> None:
        self.dismiss(self._choix[self.query_one(DataTable).cursor_row][1])

    def action_cancel(self) -> None:
        self.dismiss(None)
