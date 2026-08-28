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

    Stratégie : Tab/Shift+Tab/</>  sont interceptés en phase bubble via on_key
    (après le widget focalisé, comme TableNavMixin pour Home/End/PageUp/PageDown),
    pour éviter que DataTable les capture et les bloque.

    ⚠ Un écran qui définit son propre on_key doit appeler super().on_key(event)
    pour les touches qu'il ne consomme pas.
    """

    RESIZE_COLS:        list[str]      = []
    RESIZE_LABELS:      dict[str, str] = {}
    RESIZE_MIN:         dict[str, int] = {}
    RESIZE_STEP:        int            = 2
    RESIZE_MIN_DEFAULT: int            = 6
    # Largeur des colonnes que l'écran ajoute hors du cycle de redimensionnement
    # (la case à cocher, le numéro de piste), plus les séparateurs. Elle compte
    # dans le total, donc dans le plafond.
    RESIZE_FIXE:        int            = 0

    BINDINGS = [
        Binding("shift+tab", "col_prev",   "Col préc.", show=True, priority=True),
        Binding("tab",       "col_next",   "Col suiv.", show=True, priority=True),
        Binding("<",         "col_shrink", "Rétrécir",  show=True),
        Binding(">",         "col_grow",   "Élargir",   show=True),
    ]

    _resize_col_idx: int = 0

    def on_key(self, event: Key) -> None:
        """
        Intercepte Tab/Shift+Tab/</>  en phase bubble.
        Appelé après le widget focalisé — si DataTable n'a pas stoppé
        l'événement, on l'attrape ici et on change de colonne ou redimensionne.
        """
        handlers = {
            "tab":               self.action_col_next,
            "shift+tab":         self.action_col_prev,
            "less_than_sign":    self.action_col_shrink,
            "greater_than_sign": self.action_col_grow,
        }
        if event.key in handlers:
            handlers[event.key]()
            event.stop()

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

    def _place_disponible(self) -> int:
        """Colonnes offertes par le terminal, ou 0 si l'écran n'est pas monté."""
        try:
            return int(self.size.width)          # type: ignore[attr-defined]
        except Exception:
            return 0

    def _total_largeurs(self, widths: dict[str, int]) -> int:
        return sum(widths.get(k, 0) for k in self.RESIZE_COLS) + self.RESIZE_FIXE

    def _apply_resize(self, delta: int) -> None:
        key     = self.resize_col_key
        widths  = self._resize_widths()
        current = widths.get(key, 12)
        floor   = self.RESIZE_MIN.get(key, self.RESIZE_MIN_DEFAULT)
        new_w   = max(floor, current + delta)
        if new_w == current:
            return
        # IE-02 a donné un plancher par colonne ; rien ne limitait la somme.
        # Mesuré sur le dry-run : 186 colonnes enregistrées pour un terminal de
        # 160. Les dernières colonnes sortaient de l'écran, « 34.6 Go » perdait
        # son « o », et le réglage était persisté — l'écran restait faux au
        # lancement suivant, sans que rien ne l'ait signalé.
        place = self._place_disponible()
        if delta > 0 and place:
            total = self._total_largeurs({**widths, key: new_w})
            if total > place:
                marge = place - self._total_largeurs(widths)
                if marge <= 0:
                    self._refus_elargir(place)
                    return
                new_w = current + marge          # on donne ce qui reste, pas plus
                if new_w <= current:
                    self._refus_elargir(place)
                    return
        self._resize_persist(key, new_w)
        self._resize_rebuild()

    def _refus_elargir(self, place: int) -> None:
        """Dire pourquoi la colonne ne s'élargit plus, plutôt que ne rien faire.

        Une touche sans effet et sans message se lit comme une touche cassée.
        """
        try:
            self.notify(                          # type: ignore[attr-defined]
                f"Les colonnes occupent déjà les {place} colonnes du terminal — "
                f"rétrécissez-en une autre ({self.resize_col_label} reste "
                f"réglable vers le bas).",
                severity="warning", timeout=4,
            )
        except Exception:
            pass
