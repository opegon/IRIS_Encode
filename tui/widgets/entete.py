"""
tui/widgets/entete.py — L'en-tête, avec l'accès au guide annoncé à droite.

Le `Header` de Textual docke une horloge à droite et rien d'autre. On y ajoute
le rappel de la touche d'aide : c'est le seul endroit visible depuis **tous**
les écrans, y compris ceux dont le pied de page est déjà plein.

**Un seul widget porte les deux.** Deux widgets `dock: right` distincts se
recouvrent au lieu de s'empiler — essayé, et l'horloge disparaissait sans que
rien ne le signale. Les composer dans le même rendu supprime la question :
l'horloge garde son coin, le rappel se pose à sa gauche, et l'ordre ne dépend
plus de la façon dont le moteur résout deux ancrages concurrents.
"""
from __future__ import annotations

from datetime import datetime

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Header
from textual.widgets._header import HeaderIcon, HeaderTitle

from ..common import touche

# « H Aide  ·  00:12:34 » : six pour le rappel, trois pour le séparateur,
# huit pour l'heure, deux de marge.
_LARGEUR = 21


class AideEtHeure(Widget):
    """« H Aide · 00:12:34 », docké à droite de l'en-tête."""

    DEFAULT_CSS = f"""
    AideEtHeure {{
        dock: right;
        width: {_LARGEUR};
        padding: 0 1;
        content-align: right middle;
        background: $foreground-darken-1 5%;
        color: $foreground;
    }}
    """

    def on_mount(self) -> None:
        self.set_interval(1, self.refresh, name="horloge de l'en-tete")

    def render(self) -> Text:
        t = Text(no_wrap=True, overflow="ellipsis")
        t.append(touche("h"), style="bold yellow")
        t.append(" Aide")
        t.append("  ·  ", style="dim")
        t.append(datetime.now().time().strftime("%X"), style="")
        return t


class Entete(Header):
    """L'en-tête de tous les écrans : icône, titre, rappel de l'aide, heure."""

    def __init__(self, **kwargs) -> None:
        super().__init__(show_clock=False, **kwargs)

    def compose(self) -> ComposeResult:
        yield HeaderIcon().data_bind(Header.icon)
        yield HeaderTitle()
        yield AideEtHeure()
