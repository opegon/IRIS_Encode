"""
tui/widgets/footer.py — Footer de raccourcis, organisé en trois bandes.

Le Footer Textual natif tient sur une ligne et tronque le reste. Ici les
raccourcis sont rangés par rôle, du plus contextuel au plus stable :

    propres à l'écran      ce qui change d'un écran à l'autre
    globaux                navigation et retour, identiques partout
    touches de fonction    F1 à F10, toujours la dernière ligne

Une place fixe par rôle vaut mieux qu'un ordre de déclaration : l'œil apprend
où regarder, et les touches de fonction — les plus engageantes, celles qui
lancent un encodage — sont toujours au même endroit.

Chaque bande s'enroule sur autant de lignes que la largeur l'impose : **rien
n'est jamais tronqué**. Une troncature silencieuse fait croire qu'une touche
n'existe pas ; mieux vaut une ligne de plus qu'une action introuvable.

Le footer reste dans le flux vertical, jamais ancré : ancré, il recouvrirait
les dernières lignes de la table au lieu de lui laisser la place.
"""
from __future__ import annotations

import re

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from ..common import SEP_TOUCHE, touche as _fmt_key

_SEP = "   "        # entre deux raccourcis d'une même ligne — resserré ici
_PADDING = 2        # padding horizontal du bloc, à défalquer de la largeur


def _entry_width(key: str, desc: str) -> int:
    return len(_fmt_key(key)) + len(SEP_TOUCHE) + len(desc)


def pack(pairs: list[tuple[str, str]], width: int) -> list[list[tuple[str, str]]]:
    """
    Répartit les raccourcis en lignes tenant dans `width` colonnes.

    Un raccourci n'est jamais coupé : s'il ne tient pas à lui seul, il occupe
    sa ligne et déborde — mieux vaut ça que le faire disparaître.
    """
    if width <= 0:
        return [pairs] if pairs else []
    lignes: list[list[tuple[str, str]]] = []
    courante: list[tuple[str, str]] = []
    reste = width
    for key, desc in pairs:
        besoin = _entry_width(key, desc) + (len(_SEP) if courante else 0)
        if courante and besoin > reste:
            lignes.append(courante)
            courante, reste = [], width
            besoin = _entry_width(key, desc)
        courante.append((key, desc))
        reste -= besoin
    if courante:
        lignes.append(courante)
    return lignes


_FKEY = re.compile(r"^f(\d{1,2})$")


def split_bands(actions: list[tuple[str, str]],
                nav: list[tuple[str, str]],
                ) -> list[list[tuple[str, str]]]:
    """
    Range les raccourcis en trois bandes, de haut en bas.

    Les touches de fonction sont extraites des deux groupes et triées par
    numéro plutôt que par ordre de déclaration : F1 avant F2 avant F10, quel
    que soit l'écran.
    """
    fonctions: list[tuple[str, str]] = []
    propres:   list[tuple[str, str]] = []
    globaux:   list[tuple[str, str]] = []
    for groupe, cible in ((actions, propres), (nav, globaux)):
        for key, desc in groupe:
            (fonctions if _FKEY.match(key.lower()) else cible).append((key, desc))
    fonctions.sort(key=lambda p: int(_FKEY.match(p[0].lower()).group(1)))
    return [propres, globaux, fonctions]


def _render_line(pairs: list[tuple[str, str]]) -> Text:
    """Une ligne Rich avec les paires (touche, description) stylées."""
    t = Text(overflow="ellipsis", no_wrap=True)
    for i, (key, desc) in enumerate(pairs):
        if i:
            t.append(_SEP, style="")
        t.append(_fmt_key(key), style="bold yellow")
        t.append(f"{SEP_TOUCHE}{desc}", style="")
    return t


class KeyFooter(Widget):
    """Footer de raccourcis, hauteur variable selon la largeur disponible."""

    DEFAULT_CSS = """
    /* Hauteur posee explicitement par _redraw() : une hauteur `auto` depend de
       la largeur, qui depend de la mise en page, qui depend du `1fr` du
       contenu au-dessus. La boucle laissait la table a trois lignes et le
       footer flottant au milieu de l'ecran. La valeur ci-dessous n'est qu'un
       point de depart avant le premier calcul. */
    KeyFooter {
        height: 2;
        layout: vertical;
    }
    KeyFooter #footer-body {
        height: 100%;
        background: $primary-darken-2;
        color: $text;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        actions: list[tuple[str, str]],
        nav:     list[tuple[str, str]],
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._actions = actions
        self._nav     = nav

    def compose(self) -> ComposeResult:
        yield Static("", id="footer-body")

    def on_mount(self) -> None:
        self._redraw()

    def on_resize(self) -> None:
        self._redraw()

    # ── Rendu ─────────────────────────────────────────────────────────────────

    def _redraw(self) -> None:
        largeur = max(0, self.size.width - _PADDING)
        lignes: list[Text] = []
        for bande in split_bands(self._actions, self._nav):
            lignes.extend(_render_line(l) for l in pack(bande, largeur))
        bloc = Text("\n").join(lignes) if lignes else Text("")
        try:
            self.query_one("#footer-body", Static).update(bloc)
        except Exception:
            return                    # pas encore monté : on_mount suivra
        # La hauteur suit le nombre de lignes réellement produites ;
        # le contenu au-dessus récupère tout le reste.
        hauteur = max(1, len(lignes))
        if self.styles.height is None or self.styles.height.value != hauteur:
            self.styles.height = hauteur

    def update_line(self, line: int, pairs: list[tuple[str, str]]) -> None:
        """Remplace un groupe (1 = actions, 2 = navigation) et redessine."""
        if line == 1:
            self._actions = pairs
        else:
            self._nav = pairs
        self._redraw()
