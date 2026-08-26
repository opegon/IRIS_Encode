"""
tui/widgets/footer.py — Footer de raccourcis, réparti sur autant de lignes
qu'il en faut.

Le Footer Textual natif tient sur une ligne et tronque le reste. Ici les
raccourcis sont répartis selon la largeur réellement disponible : sur un écran
large tout tient en deux lignes, sur un 1920×1080 le même contenu en occupe
trois ou quatre, mais **rien ne disparaît**.

C'est le point important : une troncature silencieuse fait croire qu'une touche
n'existe pas. Mieux vaut une ligne de plus qu'une action introuvable.

Deux groupes conservent leur identité en s'enroulant séparément : les actions
propres à l'écran d'abord, la navigation ensuite.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

# Raccourcis clés → affichage lisible (les touches absentes passent en .upper())
_KEY_LABELS: dict[str, str] = {
    "ctrl+s":    "Ctrl+S",
    "ctrl+c":    "Ctrl+C",
    "ctrl+d":    "Ctrl+D",
    "shift+tab": "Sh+Tab",
    "tab":       "Tab",
    "backspace": "Back",
    "space":     "Space",
    "enter":     "Enter",
    "escape":    "Esc",
    "delete":    "Suppr",
    "pageup":    "PgUp",
    "pagedown":  "PgDn",
    "home":      "Home",
    "end":       "End",
    "left":      "←",
    "right":     "→",
}

_SEP = "   "        # entre deux raccourcis d'une même ligne
_PADDING = 2        # padding horizontal du bloc, à défalquer de la largeur


def _fmt_key(key: str) -> str:
    return _KEY_LABELS.get(key, key.upper())


def _entry_width(key: str, desc: str) -> int:
    return len(_fmt_key(key)) + 1 + len(desc)


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


def _render_line(pairs: list[tuple[str, str]]) -> Text:
    """Une ligne Rich avec les paires (touche, description) stylées."""
    t = Text(overflow="ellipsis", no_wrap=True)
    for i, (key, desc) in enumerate(pairs):
        if i:
            t.append(_SEP, style="")
        t.append(_fmt_key(key), style="bold yellow")
        t.append(f" {desc}", style="")
    return t


class KeyFooter(Widget):
    """Footer de raccourcis, hauteur variable selon la largeur disponible."""

    DEFAULT_CSS = """
    KeyFooter {
        height: auto;
        layout: vertical;
    }
    KeyFooter #footer-body {
        height: auto;
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
        for groupe in (self._actions, self._nav):
            lignes.extend(_render_line(l) for l in pack(groupe, largeur))
        bloc = Text("\n").join(lignes) if lignes else Text("")
        try:
            self.query_one("#footer-body", Static).update(bloc)
        except Exception:
            pass                      # pas encore monté : on_mount s'en chargera

    def update_line(self, line: int, pairs: list[tuple[str, str]]) -> None:
        """Remplace un groupe (1 = actions, 2 = navigation) et redessine."""
        if line == 1:
            self._actions = pairs
        else:
            self._nav = pairs
        self._redraw()
