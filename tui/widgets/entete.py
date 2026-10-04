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

from rich.cells import cell_len
from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Header
from textual.widgets._header import HeaderIcon, HeaderTitle

from core.i18n import _
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
        # La largeur suit le libellé traduit : « H Aide » tenait dans 21
        # colonnes, une autre langue peut en demander plus (L-49). Padding 0 1.
        self.styles.width = max(_LARGEUR, cell_len(self.render().plain) + 2)
        self.set_interval(1, self.refresh, name="horloge de l'en-tete")

    def render(self) -> Text:
        t = Text(no_wrap=True, overflow="ellipsis")
        t.append(touche("h"), style="bold yellow")
        t.append(" " + _("Help"))
        t.append("  ·  ", style="dim")
        # Format écrit en toutes lettres : `%X` dépendrait de la locale du
        # processus, que rien ne règle aujourd'hui mais qu'un appel suffirait
        # à changer en douce (L-49).
        t.append(datetime.now().time().strftime("%H:%M:%S"), style="")
        return t


class Entete(Header):
    """L'en-tête de tous les écrans : icône, titre, rappel de l'aide, heure.

    Tant qu'un lot d'encodage existe, le titre porte au centre l'état de la
    file et la touche pour y aller (IE-100) : la file tourne pendant qu'on
    navigue, c'est le seul endroit visible de partout. À sa droite, « ☾ » dit
    que la mise en veille est bloquée, et ce que fera la machine après le lot.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(show_clock=False, **kwargs)

    def on_mount(self) -> None:
        self.set_interval(1, self._rafraichir_titre, name="etat de la file")

    def _rafraichir_titre(self) -> None:
        try:
            self.query_one(HeaderTitle).update(self.format_title())
        except Exception:
            pass

    def format_title(self):
        base   = super().format_title()
        etat   = getattr(self.app, "etat_file", lambda: "")()
        veille = getattr(self.app, "etat_veille", lambda: "")()
        if not (etat or veille):
            return base
        t = Text(str(base), no_wrap=True, overflow="ellipsis")
        if etat:
            t.append("     ")
            t.append(f" {etat} ", style="bold reverse")
        # La veille à part : elle tient aussi pour une mesure ou un mux, sans
        # lot d'encodage, et ce n'est pas l'état de la file.
        if veille:
            t.append("   ")
            t.append(veille, style="italic")
        return t

    def compose(self) -> ComposeResult:
        yield HeaderIcon().data_bind(Header.icon)
        yield HeaderTitle()
        yield AideEtHeure()
