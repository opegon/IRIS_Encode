"""
tui/mixins.py — Mixins réutilisables pour les écrans Textual.

TableNavMixin    : Home/End/PageUp/PageDown sur tout écran à DataTable.
ColumnResizeMixin: sélection (Tab/Shift+Tab) + resize (</>) de colonnes,
                   persistés dans config.toml — comportement identique
                   sur browser, tracks et dryrun.
"""
from __future__ import annotations

from textual.binding import Binding
from textual.events import Key
from textual.widgets import DataTable


class TableNavMixin:
    """
    Ajoute Home / End / PageUp / PageDown à tout écran contenant un DataTable.

    Stratégie : on_key direct (intercepte en phase bubble, après le widget
    focalisé) plutôt que BINDINGS (qui peuvent être étouffés par DataTable
    via ScrollView avant que le système de bindings soit consulté).

    Les bindings sont quand même déclarés pour apparaître dans le footer,
    mais l'action réelle passe par on_key.

    ⚠ Un écran qui définit son propre on_key doit appeler super().on_key(event)
    pour les touches qu'il ne consomme pas, sous peine de perdre cette navigation.
    """

    BINDINGS = [
        Binding("home",     "table_home",      "Début",   show=False),
        Binding("end",      "table_end",       "Fin",     show=False),
        Binding("pageup",   "table_page_up",   "Page ↑",  show=False),
        Binding("pagedown", "table_page_down", "Page ↓",  show=False),
    ]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _nav_table(self) -> DataTable | None:
        try:
            return self.query_one(DataTable)  # type: ignore[attr-defined]
        except Exception:
            return None

    def _page_size(self, table: DataTable) -> int:
        try:
            return max(1, table.scrollable_content_region.height)
        except Exception:
            return 10

    # ── Interception directe des touches de navigation ────────────────────────

    def on_key(self, event: Key) -> None:
        """
        Intercepte Home/End/PageUp/PageDown en phase bubble.
        Appelé après le widget focalisé — si DataTable n'a pas stoppé
        l'événement, on l'attrape ici et on déplace le curseur.
        """
        handlers = {
            "home":     self.action_table_home,
            "end":      self.action_table_end,
            "pageup":   self.action_table_page_up,
            "pagedown": self.action_table_page_down,
        }
        if event.key in handlers:
            handlers[event.key]()
            event.stop()

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_table_home(self) -> None:
        table = self._nav_table()
        if table and table.row_count:
            table.move_cursor(row=0)
            table.scroll_home(animate=False)

    def action_table_end(self) -> None:
        table = self._nav_table()
        if table and table.row_count:
            table.move_cursor(row=table.row_count - 1)
            table.scroll_end(animate=False)

    def action_table_page_up(self) -> None:
        table = self._nav_table()
        if table and table.row_count:
            target = max(0, table.cursor_row - self._page_size(table))
            table.move_cursor(row=target)

    def action_table_page_down(self) -> None:
        table = self._nav_table()
        if table and table.row_count:
            target = min(table.row_count - 1, table.cursor_row + self._page_size(table))
            table.move_cursor(row=target)


class ColumnResizeMixin:
    """
    Colonnes redimensionnables au clavier, avec persistance config.toml.

    L'écran hôte déclare :
      RESIZE_COLS   — clés des colonnes redimensionnables (ordre de cycle)
      RESIZE_LABELS — clé → libellé d'en-tête
      RESIZE_MIN    — (optionnel) plancher par colonne, défaut RESIZE_MIN_DEFAULT

    et implémente :
      _resize_widths()       → dict clé → largeur courante
      _resize_persist(k, w)  → écrit la largeur en config
      _resize_rebuild()      → reconstruit la table (curseur conservé)
    """

    RESIZE_COLS:        list[str]      = []
    RESIZE_LABELS:      dict[str, str] = {}
    RESIZE_MIN:         dict[str, int] = {}
    RESIZE_STEP:        int            = 2
    RESIZE_MIN_DEFAULT: int            = 6

    BINDINGS = [
        Binding("shift+tab", "col_prev",   "Col préc.", show=True, priority=True),
        Binding("tab",       "col_next",   "Col suiv.", show=True, priority=True),
        Binding("<",         "col_shrink", "Rétrécir",  show=True),
        Binding(">",         "col_grow",   "Élargir",   show=True),
    ]

    _resize_col_idx: int = 0

    # ── À implémenter par l'écran ─────────────────────────────────────────────

    def _resize_widths(self) -> dict[str, int]:
        raise NotImplementedError

    def _resize_persist(self, key: str, width: int) -> None:
        raise NotImplementedError

    def _resize_rebuild(self) -> None:
        raise NotImplementedError

    # ── Helpers ───────────────────────────────────────────────────────────────

    @property
    def resize_col_key(self) -> str:
        return self.RESIZE_COLS[self._resize_col_idx]

    @property
    def resize_col_label(self) -> str:
        return self.RESIZE_LABELS[self.resize_col_key]

    def resize_header(self, key: str) -> str:
        """En-tête de colonne, marqueur ◄► sur la colonne active."""
        label = self.RESIZE_LABELS[key]
        return f"{label} ◄►" if key == self.resize_col_key else label

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_col_prev(self) -> None:
        self._resize_col_idx = (self._resize_col_idx - 1) % len(self.RESIZE_COLS)
        self._resize_rebuild()

    def action_col_next(self) -> None:
        self._resize_col_idx = (self._resize_col_idx + 1) % len(self.RESIZE_COLS)
        self._resize_rebuild()

    def action_col_shrink(self) -> None:
        self._apply_resize(-self.RESIZE_STEP)

    def action_col_grow(self) -> None:
        self._apply_resize(+self.RESIZE_STEP)

    def _apply_resize(self, delta: int) -> None:
        key     = self.resize_col_key
        current = self._resize_widths().get(key, 12)
        floor   = self.RESIZE_MIN.get(key, self.RESIZE_MIN_DEFAULT)
        new_w   = max(floor, current + delta)
        if new_w == current:
            return
        self._resize_persist(key, new_w)
        self._resize_rebuild()
