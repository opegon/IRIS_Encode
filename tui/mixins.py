"""
tui/mixins.py — Mixins réutilisables pour les écrans Textual.
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
    """

    BINDINGS = [
        Binding("home",     "table_home",      "Début",       show=False),
        Binding("end",      "table_end",       "Fin",         show=False),
        Binding("pageup",   "table_page_up",   "Page préc.",  show=False),
        Binding("pagedown", "table_page_down", "Page suiv.",  show=False),
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
        Si DataTable l'a stoppé (scroll interne), on force quand même
        via _force_nav_key() après le prochain refresh.
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

    def _force_nav(self, key: str) -> None:
        """Appelé via call_after_refresh pour forcer la nav même si le scroll a joué."""
        handlers = {
            "home":     self.action_table_home,
            "end":      self.action_table_end,
            "pageup":   self.action_table_page_up,
            "pagedown": self.action_table_page_down,
        }
        if key in handlers:
            handlers[key]()

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
