"""
tui/screens/sync.py — Recalage manuel des pistes externes avant mux.

Une ligne par piste greffée, chacune avec son propre décalage : ajouter une
VF et ses sous-titres se règle indépendamment, piste par piste.

  ←/→          champ suivant / précédent
  +/-          ±100 ms sur le décalage, valeur suivante sur les autres champs
  Shift+↑/↓    ±1 s sur le décalage
  ↵            liste de choix du champ actif
  c            reprend le décalage d'une autre piste
  d            retire la piste de la liste
  F2           lance le mux
"""
from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.events import Key
from textual.screen import Screen
from textual.widgets import DataTable, Header, Static

from core.muxer import ExternalTrack, SyncOrigin, TrackKind

from ..common import footer_line2
from ..mixins import TableNavMixin
from ..widgets.footer import TwoLineFooter
from .value_picker import ValuePickerScreen

# Champs éditables, dans l'ordre de parcours ←/→
_FIELDS = ["delay", "stretch", "lang", "name", "default", "forced"]

_FIELD_LABELS = {
    "delay":   "Décalage",
    "stretch": "Étirement",
    "lang":    "Langue",
    "name":    "Nom",
    "default": "Défaut",
    "forced":  "Forcé",
}

# Étirements courants : corrige les sources PAL accélérées (25 vs 23.976 fps)
_STRETCH_CYCLE: list[tuple[int, int] | None] = [
    None,
    (24000, 25025),
    (25025, 24000),
]
_STRETCH_LABELS = {
    None:           "—",
    (24000, 25025): "PAL→film",
    (25025, 24000): "film→PAL",
}

_LANGS = ["fre", "eng", "ger", "spa", "ita", "jpn", "por", "rus", "und"]
_NAMES = ["—", "VF", "VOSTFR", "VO", "Forcés", "Commentaires", "SDH"]

_DELAY_STEP_MS = 100
_DELAY_JUMP_MS = 1000

_HINT = ("←/→  Champ     +/-  ±100 ms     Shift+↑/↓  ±1 s     "
         "↵  Liste     c  Copier décalage     d  Retirer")


class SyncScreen(TableNavMixin, Screen["list[ExternalTrack] | None"]):
    """Réglage du recalage de chaque piste externe, puis mux."""

    BINDINGS = [
        Binding("left",      "field_prev",   "Champ préc.",   show=False),
        Binding("right",     "field_next",   "Champ suiv.",   show=False),
        Binding("+",         "val_up",       "Valeur suiv.",  show=False),
        Binding("-",         "val_down",     "Valeur préc.",  show=False),
        Binding("shift+up",  "jump_up",      "+1 s",          show=False),
        Binding("shift+down","jump_down",    "-1 s",          show=False),
        Binding("enter",     "open_picker",  "Liste",         show=True, priority=True),
        Binding("c",         "copy_delay",   "Copier décalage", show=True),
        Binding("d",         "remove_track", "Retirer",       show=True),
        Binding("f2",        "run_mux",      "Muxer",         show=True),
        Binding("backspace", "go_back",      "Retour",        show=True),
        Binding("escape",    "go_back",      "Retour",        show=False, priority=True),
    ]

    DEFAULT_CSS = """
    SyncScreen { layout: vertical; }
    #sync-table { height: 1fr; }
    #sync-hint {
        height: 1;
        background: $primary-darken-1;
        color: $text;
        padding: 0 2;
        border-top: solid $primary;
    }
    """

    def __init__(self, source: Path, tracks: list[ExternalTrack]) -> None:
        super().__init__()
        self._source    = source
        self._tracks    = tracks
        self._field_idx = 0

    # ── Composition ───────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="status-bar", classes="status-bar")
        yield DataTable(id="sync-table", cursor_type="row", zebra_stripes=False)
        yield Static(_HINT, id="sync-hint")
        yield TwoLineFooter(
            line1=[
                ("enter",     "Liste de choix"),
                ("c",         "Copier décalage"),
                ("d",         "Retirer"),
                ("f2",        "Muxer"),
                ("backspace", "Retour"),
            ],
            line2=footer_line2(nav=True),
        )

    def on_mount(self) -> None:
        self._build_table()
        self._update_status()
        self.query_one(DataTable).focus()

    # ── Table ─────────────────────────────────────────────────────────────────

    def _build_table(self, keep_cursor: bool = False) -> None:
        table  = self.query_one(DataTable)
        cursor = table.cursor_row if keep_cursor else 0
        table.clear(columns=True)

        table.add_column("Source",    width=28, key="src")
        table.add_column("Piste",     width=14, key="tid")
        table.add_column("Décalage",  width=12, key="delay")
        table.add_column("Étirement", width=11, key="stretch")
        table.add_column("Langue",    width=8,  key="lang")
        table.add_column("Nom",       width=14, key="name")
        table.add_column("Défaut",    width=8,  key="default")
        table.add_column("Forcé",     width=7,  key="forced")
        table.add_column("Recalage",  width=None, key="origin")

        for i, t in enumerate(self._tracks):
            table.add_row(*self._row(i), key=str(i))

        if table.row_count:
            table.move_cursor(row=min(cursor, table.row_count - 1))

    def _cell(self, i: int, field: str) -> Text:
        """Valeur d'un champ, mise en évidence si c'est le champ actif."""
        t      = self._tracks[i]
        active = (field == _FIELDS[self._field_idx]
                  and i == self.query_one(DataTable).cursor_row)
        style  = "reverse bold" if active else ""

        if field == "delay":
            txt = f"{t.delay_ms:+d} ms"
        elif field == "stretch":
            txt = _STRETCH_LABELS.get(t.stretch, "?")
        elif field == "lang":
            txt = t.language or "—"
            if not t.language:
                style = f"{style} bold dark_orange".strip()
        elif field == "name":
            txt = t.track_name or "—"
        elif field == "default":
            txt = "oui" if t.is_default else "non"
        else:
            txt = "oui" if t.is_forced else "non"
        return Text(txt, style=style, no_wrap=True)

    def _row(self, i: int) -> tuple:
        t    = self._tracks[i]
        kind = "audio" if t.kind == TrackKind.AUDIO else "sous-titre"
        origin = {
            SyncOrigin.NONE:     Text("—", style="dim"),
            SyncOrigin.MEASURED: Text("mesuré", style="green"),
            SyncOrigin.MANUAL:   Text("manuel", style="cyan"),
            SyncOrigin.COPIED:   Text(
                f"repris de #{(t.copied_from or 0) + 1}", style="cyan"),
        }[t.sync_origin]
        return (
            Text(t.source_path.name, no_wrap=True, overflow="ellipsis"),
            Text(f"{kind} #{t.source_tid}", no_wrap=True),
            self._cell(i, "delay"),
            self._cell(i, "stretch"),
            self._cell(i, "lang"),
            self._cell(i, "name"),
            self._cell(i, "default"),
            self._cell(i, "forced"),
            origin,
        )

    def _refresh_row(self, i: int) -> None:
        table = self.query_one(DataTable)
        keys  = ("src", "tid", "delay", "stretch", "lang", "name",
                 "default", "forced", "origin")
        for key, val in zip(keys, self._row(i)):
            table.update_cell(str(i), key, val, update_width=False)

    def _refresh_all(self) -> None:
        for i in range(len(self._tracks)):
            self._refresh_row(i)

    def _update_status(self) -> None:
        n       = len(self._tracks)
        missing = sum(1 for t in self._tracks if not t.language)
        warn    = f" ── ⚠ {missing} piste(s) sans langue" if missing else ""
        self.query_one("#status-bar", Static).update(
            f" {self._source.name} ── {n} piste(s) à greffer"
            f" ── Champ : {_FIELD_LABELS[_FIELDS[self._field_idx]]}{warn}"
        )

    @on(DataTable.RowHighlighted)
    def _on_row_highlight(self, _: DataTable.RowHighlighted) -> None:
        self._refresh_all()

    # ── Navigation entre champs ───────────────────────────────────────────────

    def on_key(self, event: Key) -> None:
        if event.key in ("left", "right"):
            event.stop()
            self.action_field_prev() if event.key == "left" else self.action_field_next()
            return
        # Laisse TableNavMixin gérer Home/End/PageUp/PageDown
        super().on_key(event)

    def action_field_prev(self) -> None:
        self._field_idx = (self._field_idx - 1) % len(_FIELDS)
        self._refresh_all()
        self._update_status()

    def action_field_next(self) -> None:
        self._field_idx = (self._field_idx + 1) % len(_FIELDS)
        self._refresh_all()
        self._update_status()

    # ── Édition ───────────────────────────────────────────────────────────────

    def _current(self) -> int | None:
        row = self.query_one(DataTable).cursor_row
        return row if 0 <= row < len(self._tracks) else None

    def action_val_up(self)   -> None: self._change(+1, _DELAY_STEP_MS)
    def action_val_down(self) -> None: self._change(-1, _DELAY_STEP_MS)
    def action_jump_up(self)  -> None: self._change(+1, _DELAY_JUMP_MS)
    def action_jump_down(self)-> None: self._change(-1, _DELAY_JUMP_MS)

    def _change(self, delta: int, step: int) -> None:
        i = self._current()
        if i is None:
            return
        t     = self._tracks[i]
        field = _FIELDS[self._field_idx]

        if field == "delay":
            t.delay_ms += delta * step
            t.sync_origin = SyncOrigin.MANUAL
            t.copied_from = None
        elif field == "stretch":
            cur = _STRETCH_CYCLE.index(t.stretch) if t.stretch in _STRETCH_CYCLE else 0
            t.stretch = _STRETCH_CYCLE[(cur + delta) % len(_STRETCH_CYCLE)]
            t.sync_origin = SyncOrigin.MANUAL
        elif field == "lang":
            cur = _LANGS.index(t.language) if t.language in _LANGS else 0
            t.language = _LANGS[(cur + delta) % len(_LANGS)]
        elif field == "name":
            cur = _NAMES.index(t.track_name) if t.track_name in _NAMES else 0
            nxt = _NAMES[(cur + delta) % len(_NAMES)]
            t.track_name = "" if nxt == "—" else nxt
        elif field == "default":
            t.is_default = not t.is_default
        else:
            t.is_forced = not t.is_forced

        self._refresh_row(i)
        self._update_status()

    def action_open_picker(self) -> None:
        i = self._current()
        if i is None:
            return
        field = _FIELDS[self._field_idx]
        t     = self._tracks[i]

        if field == "lang":
            opts, cur = _LANGS, (_LANGS.index(t.language) if t.language in _LANGS else 0)
        elif field == "name":
            label = t.track_name or "—"
            opts, cur = _NAMES, (_NAMES.index(label) if label in _NAMES else 0)
        elif field == "stretch":
            opts = [_STRETCH_LABELS[s] for s in _STRETCH_CYCLE]
            cur  = _STRETCH_CYCLE.index(t.stretch) if t.stretch in _STRETCH_CYCLE else 0
        else:
            # Décalage et drapeaux se règlent avec +/- : pas de liste
            return

        def _apply(choice: int | None) -> None:
            if choice is None:
                return
            if field == "lang":
                t.language = _LANGS[choice]
            elif field == "name":
                t.track_name = "" if _NAMES[choice] == "—" else _NAMES[choice]
            else:
                t.stretch = _STRETCH_CYCLE[choice]
                t.sync_origin = SyncOrigin.MANUAL
            self._refresh_row(i)
            self._update_status()

        self.app.push_screen(
            ValuePickerScreen(_FIELD_LABELS[field], opts, cur), _apply
        )

    # ── Reprise de décalage ───────────────────────────────────────────────────

    def action_copy_delay(self) -> None:
        """
        Reprend le décalage d'une autre piste externe.

        Cas courant : des sous-titres écrits sur le timing du donneur ont le
        même décalage que la piste audio qui vient du même fichier — inutile
        de les recaler séparément.
        """
        i = self._current()
        if i is None or len(self._tracks) < 2:
            return
        others = [j for j in range(len(self._tracks)) if j != i]
        opts   = [
            f"#{j + 1} {self._tracks[j].source_path.name} — {self._tracks[j].sync_label()}"
            for j in others
        ]

        def _apply(choice: int | None) -> None:
            if choice is None:
                return
            src = self._tracks[others[choice]]
            dst = self._tracks[i]
            dst.delay_ms    = src.delay_ms
            dst.stretch     = src.stretch
            dst.sync_origin = SyncOrigin.COPIED
            dst.copied_from = others[choice]
            self._refresh_row(i)
            self._update_status()

        self.app.push_screen(
            ValuePickerScreen("Reprendre le décalage de", opts, 0), _apply
        )

    def action_remove_track(self) -> None:
        i = self._current()
        if i is None:
            return
        self._tracks.pop(i)
        # Les index de reprise pointent sur une liste qui vient de bouger
        for t in self._tracks:
            if t.copied_from is not None:
                if t.copied_from == i:
                    t.sync_origin = SyncOrigin.MANUAL
                    t.copied_from = None
                elif t.copied_from > i:
                    t.copied_from -= 1
        self._build_table(keep_cursor=True)
        self._update_status()

    # ── Sortie ────────────────────────────────────────────────────────────────

    def action_run_mux(self) -> None:
        if not self._tracks:
            self.app.bell()
            return
        if any(not t.language for t in self._tracks):
            self.app.bell()
            self.query_one("#sync-hint", Static).update(
                "⚠ Chaque piste doit avoir une langue — sinon elle apparaît en « und »."
            )
            return
        from .mux_run import MuxScreen
        self.app.push_screen(MuxScreen(self._source, list(self._tracks)))

    def action_go_back(self) -> None:
        self.dismiss(self._tracks)
