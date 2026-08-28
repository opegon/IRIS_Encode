"""
tui/screens/ancrage.py — Donner un point de repère quand la mesure ne peut pas.

Certains couples ne se mesurent pas. Un sous-titre dont l'adaptation diffère de
celle du doublage ne décalque pas la parole : mesuré sur un cas réel, il
plafonne à **0,117** pour un seuil de 0,25, *même parfaitement aligné*, vérifié
à l'oreille en six points. Aucun réglage de la corrélation ne rattrapera ça.

Mais la corrélation reste utilisable si on lui dit **où** chercher. Cette modale
recueille les deux nombres qui le lui disent : la réplique écrite à tel instant
est entendue à tel autre. La recherche se centre alors sur cet écart et se
resserre à ±12 s, ce qui suffit à retrouver les paliers d'un montage différent.

Le parcours attendu : `V` ouvre mpv avec la piste, on repère une réplique et les
deux instants, `R` les saisit ici.
"""
from __future__ import annotations

from typing import Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Static

from core.sync import lire_timecode

from ..common import raccourcis


class AncrageModal(ModalScreen["tuple[float, float] | None"]):
    """Saisit un point de repère : instant écrit, instant entendu."""

    CSS = """
    AncrageModal { align: center middle; }
    #anc-box {
        background: $surface;
        border: solid $accent;
        width: 76;
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
    #anc-note { color: $text-muted; width: 100%; margin-bottom: 1; }
    .anc-label { width: 100%; margin-top: 1; }
    #anc-erreur { color: $warning; width: 100%; height: 1; }
    #anc-hint { color: $text-muted; width: 100%; text-align: center; }
    """

    BINDINGS = [
        Binding("escape", "annuler", "Annuler", show=False, priority=True),
        Binding("f2",     "valider", "Valider", show=False, priority=True),
    ]

    def __init__(self, nom_piste: str = "") -> None:
        super().__init__()
        self._nom = nom_piste

    def compose(self) -> ComposeResult:
        with Static(id="anc-box"):
            yield Label("Point de repère", id="anc-title")
            yield Static(self._note(), id="anc-note", markup=False)
            yield Label("Instant écrit dans le sous-titre", classes="anc-label")
            yield Input(placeholder="13:16", id="anc-ecrit")
            yield Label("Instant où vous l'entendez", classes="anc-label")
            yield Input(placeholder="13:22", id="anc-entendu")
            yield Static("", id="anc-erreur", markup=False)
            yield Static(raccourcis([("enter", "Champ suivant"),
                                     ("f2", "Valider"),
                                     ("escape", "Annuler")]), id="anc-hint")

    def _note(self) -> Text:
        t = Text()
        if self._nom:
            t.append(f"{self._nom}\n\n", style="bold")
        t.append("Repérez une réplique, et donnez les deux instants : celui\n"
                 "écrit dans le sous-titre, et celui où vous l'entendez.\n\n")
        t.append("La recherche se centrera sur cet écart. Formats acceptés :\n"
                 "13:16 · 1:13:16 · 13:16,5 · 796", style="dim")
        return t

    def on_mount(self) -> None:
        self.query_one("#anc-ecrit", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """↵ passe au champ suivant, puis valide — on ne valide pas à l'aveugle."""
        if event.input.id == "anc-ecrit":
            self.query_one("#anc-entendu", Input).focus()
        else:
            self.action_valider()

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_valider(self) -> None:
        ecrit   = lire_timecode(self.query_one("#anc-ecrit", Input).value)
        entendu = lire_timecode(self.query_one("#anc-entendu", Input).value)
        erreur  = self.query_one("#anc-erreur", Static)

        if ecrit is None or entendu is None:
            erreur.update("Instant illisible — attendu 13:16, 1:13:16 ou 796.")
            return
        # Un écart de plusieurs minutes ne se corrige pas par un décalage : ce
        # serait un autre épisode, ou une erreur de saisie. Le dire plutôt que
        # de lancer une mesure qui n'aboutira pas.
        if abs(entendu - ecrit) > 300:
            erreur.update("Plus de cinq minutes d'écart — vérifiez les deux "
                          "instants avant de valider.")
            return
        self.dismiss((ecrit, entendu))

    def action_annuler(self) -> None:
        self.dismiss(None)
