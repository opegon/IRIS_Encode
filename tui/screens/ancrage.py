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

from core.sync import lire_timecode, mmss

from ..common import raccourcis


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
        Binding("escape", "annuler",   "Annuler",  show=False, priority=True),
        Binding("f2",     "valider",   "Valider",  show=False, priority=True),
        Binding("down",   "suivante",  "Suivante", show=False, priority=True),
        Binding("up",     "precedente", "Préc.",   show=False, priority=True),
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
            yield Static(raccourcis([("↓/↑", "Autre réplique"),
                                     ("enter", "Valider"),
                                     ("escape", "Annuler")]), id="anc-hint")

    def on_mount(self) -> None:
        self._afficher()
        self.query_one("#anc-entendu", Input).focus()

    def _note(self) -> Text:
        t = Text()
        if self._nom:
            t.append(f"{self._nom}\n", style="bold")
        t.append("Écoutez le film à l'endroit indiqué. Si cette réplique ne se\n"
                 "retrouve pas, ↓ en propose une autre.\n\n", style="dim")
        t.append("Formats acceptés : 13:22 · 1:13:22 · 13:22,5 · 802",
                 style="dim")
        return t

    def _afficher(self) -> None:
        cadre = self.query_one("#anc-replique", Static)
        if not self._reperes:
            cadre.update(Text("Aucune réplique lisible dans cette piste.",
                              style="bold"))
            return
        instant, texte = self._reperes[self._i]
        t = Text()
        t.append(f"Réplique {self._i + 1} sur {len(self._reperes)}"
                 f"   ·   écrite à ", style="dim")
        t.append(mmss(instant), style="bold")
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
            erreur.update("Instant illisible — attendu 13:22, 1:13:22 ou 802.")
            return
        ecrit = self._reperes[self._i][0]
        # Un écart de plusieurs minutes ne se corrige pas par un décalage : ce
        # serait un autre épisode, ou une erreur de saisie. Le dire plutôt que
        # de lancer une mesure qui n'aboutira pas.
        if abs(entendu - ecrit) > 300:
            erreur.update(f"Plus de cinq minutes d'écart avec {mmss(ecrit)} — "
                          f"vérifiez l'instant avant de valider.")
            return
        self.dismiss((ecrit, entendu))

    def action_annuler(self) -> None:
        self.dismiss(None)
