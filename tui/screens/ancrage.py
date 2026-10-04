"""
tui/screens/ancrage.py — Donner un point de repère quand la mesure ne peut pas.

Certains couples ne se mesurent pas. Un sous-titre dont l'adaptation diffère de
celle du doublage ne décalque pas la parole : mesuré sur un cas réel, il
plafonne à **0,117** pour un seuil de 0,25, *même parfaitement aligné*, vérifié
à l'oreille en six points. Aucun réglage de la corrélation ne rattrapera ça.

Mais la corrélation reste utilisable si on lui dit **où** chercher.

L'écran propose une réplique et son horodatage ; il ne reste qu'un nombre à
trouver — l'instant où on l'entend. Demander les deux serait obliger à charger
le sous-titre dans un lecteur rien que pour relire ce que l'application sait
déjà. `↓` et `↑` changent de proposition : une réplique peut tomber dans un
passage muet, ou ne pas se retrouver.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Static

from core.i18n import _, N_
from core.sync import lire_timecode, mmss

from ..common import raccourcis, texte_style


class AncrageModal(ModalScreen["tuple[float, float] | None"]):
    """Propose une réplique, recueille l'instant où l'utilisateur l'entend."""

    CSS = """
    AncrageModal { align: center middle; }
    #anc-box {
        background: $surface;
        border: solid $accent;
        width: 82;
        max-width: 96%;
        height: auto;
        padding: 1 2;
    }
    #anc-title {
        text-align: center;
        width: 100%;
        color: $accent;
        margin-bottom: 1;
    }
    #anc-note    { color: $text-muted; width: 100%; margin-bottom: 1; }
    #anc-replique {
        background: $primary-darken-2;
        color: $text;
        width: 100%;
        padding: 1 2;
        height: auto;
    }
    .anc-label   { width: 100%; margin-top: 1; }
    #anc-erreur  { color: $warning; width: 100%; height: 1; }
    #anc-hint    { color: $text-muted; width: 100%; text-align: center; }
    """

    BINDINGS = [
        Binding("escape", "annuler",   N_("Cancel"),  show=False, priority=True),
        Binding("f2",     "valider",   N_("OK"),  show=False, priority=True),
        Binding("down",   "suivante",  N_("Next"), show=False, priority=True),
        Binding("up",     "precedente", N_("Prev."),   show=False, priority=True),
    ]

    def __init__(self, reperes: list[tuple[float, str]],
                 nom_piste: str = "") -> None:
        super().__init__()
        self._reperes = reperes
        self._nom     = nom_piste
        self._i       = 0

    # ── Composition ───────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Static(id="anc-box"):
            yield Label("Point de repère", id="anc-title")
            yield Static(self._note(), id="anc-note", markup=False)
            yield Static("", id="anc-replique", markup=False)
            yield Label("À quel instant l'entendez-vous ?", classes="anc-label")
            yield Input(placeholder="13:22", id="anc-entendu")
            yield Static("", id="anc-erreur", markup=False)
            yield Static(raccourcis([("↓/↑", N_("Other line")),
                                     ("enter", N_("OK")),
                                     ("escape", N_("Cancel"))]), id="anc-hint")

    def on_mount(self) -> None:
        self._afficher()
        self.query_one("#anc-entendu", Input).focus()

    def _note(self) -> Text:
        t = Text()
        if self._nom:
            t.append(f"{self._nom}\n", style="bold")
        # Pas de retour à la ligne dans le message : le texte se replie seul (L-54).
        t.append(_("Listen to the film at the given point. If this line cannot "
                   "be found, {key} offers another one.").format(key="↓") + "\n\n",
                 style="dim")
        # TRANSLATORS: examples of time formats, keep them as they are.
        t.append(_("Accepted formats: {examples}").format(
                     examples="13:22 · 1:13:22 · 13:22.5 · 802"),
                 style="dim")
        return t

    def _afficher(self) -> None:
        cadre = self.query_one("#anc-replique", Static)
        if not self._reperes:
            cadre.update(Text(_("No readable line in this track."),
                              style="bold"))
            return
        instant, texte = self._reperes[self._i]
        t = Text()
        # Une phrase entière ; l'instant en gras par le code (L-57).
        t.append_text(texte_style(
            _("Line {number} of {total}   ·   written at {time}").format(
                number=self._i + 1, total=len(self._reperes), time="{time}"),
            style="dim", time=(mmss(instant), "bold")))
        t.append("\n\n")
        t.append(texte, style="bold")
        cadre.update(t)

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_suivante(self) -> None:
        if self._reperes:
            self._i = (self._i + 1) % len(self._reperes)
            self._afficher()

    def action_precedente(self) -> None:
        if self._reperes:
            self._i = (self._i - 1) % len(self._reperes)
            self._afficher()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.action_valider()

    def action_valider(self) -> None:
        erreur = self.query_one("#anc-erreur", Static)
        if not self._reperes:
            self.dismiss(None)
            return
        entendu = lire_timecode(self.query_one("#anc-entendu", Input).value)
        if entendu is None:
            erreur.update(_("Unreadable time — expected 13:22, 1:13:22 or 802."))
            return
        ecrit = self._reperes[self._i][0]
        # Un écart de plusieurs minutes ne se corrige pas par un décalage : ce
        # serait un autre épisode, ou une erreur de saisie. Le dire plutôt que
        # de lancer une mesure qui n'aboutira pas.
        if abs(entendu - ecrit) > 300:
            erreur.update(_("More than five minutes away from {time} — check "
                            "the time before confirming.").format(time=mmss(ecrit)))
            return
        self.dismiss((ecrit, entendu))

    def action_annuler(self) -> None:
        self.dismiss(None)
