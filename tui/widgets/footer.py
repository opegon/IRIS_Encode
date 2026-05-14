"""
tui/widgets/footer.py — Footer deux lignes réutilisable.

Remplace le Footer Textual natif (1 ligne) par un widget
à deux lignes : navigation d'un côté, actions de l'autre.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static


# Raccourcis clés → affichage lisible
_KEY_LABELS: dict[str, str] = {
    "ctrl+x":    "Ctrl+X",
    "ctrl+c":    "Ctrl+C",
    "shift+tab": "Sh+Tab",
    "backspace": "Back",
    "space":     "Space",
    "enter":     "Enter",
    "escape":    "Esc",
    "pageup":    "PgUp",
    "pagedown":  "PgDn",
    "home":      "Home",
    "end":       "End",
}


def _fmt_key(key: str) -> str:
    return _KEY_LABELS.get(key, key.upper())


def _render_line(pairs: list[tuple[str, str]], sep: str = "   ") -> Text:
    """Retourne une ligne Rich avec les paires (touche, description) stylées."""
    t = Text(overflow="ellipsis", no_wrap=True)
    for i, (key, desc) in enumerate(pairs):
        if i:
            t.append(sep, style="")
        t.append(_fmt_key(key), style="bold yellow")
        t.append(f" {desc}", style="")
    return t


class TwoLineFooter(Widget):
    """Footer à deux lignes configurable."""

    DEFAULT_CSS = """
    TwoLineFooter {
        height: 2;
        dock: bottom;
        layout: vertical;
    }
    TwoLineFooter .footer-row {
        height: 1;
        background: $primary-darken-2;
        color: $text;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        line1: list[tuple[str, str]],
        line2: list[tuple[str, str]],
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._line1 = line1
        self._line2 = line2

    def compose(self) -> ComposeResult:
        yield Static(_render_line(self._line1), classes="footer-row", id="footer-l1")
        yield Static(_render_line(self._line2), classes="footer-row", id="footer-l2")

    def update_line(self, line: int, pairs: list[tuple[str, str]]) -> None:
        """Met à jour une ligne dynamiquement (ex. après changement de profil)."""
        wid_id = f"footer-l{line}"
        try:
            self.query_one(f"#{wid_id}", Static).update(_render_line(pairs))
        except Exception:
            pass
