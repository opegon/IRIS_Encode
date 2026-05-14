"""
tui/screens/dryrun.py — Écran Dry-run.

Prévisualise les décisions pour tous les fichiers sélectionnés.
Colonnes redimensionnables via [/] (sélection) et </> (resize).
"""
from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Header, Static
from ..widgets.footer import TwoLineFooter
from ..mixins import TableNavMixin

from core import config as cfg_mod
from core.decision import AudioAction, DVAction, FileDecision, VideoAction

if TYPE_CHECKING:
    from ..app import IrisEncodeApp


# ── Colonnes redimensionnables ─────────────────────────────────────────────────

_RESIZE_COLS   = ["fichier", "taille", "action", "conteneur", "dv", "bitrate", "res", "audio"]
_RESIZE_LABELS = {
    "fichier":   "Fichier",
    "taille":    "Taille",
    "action":    "Action",
    "conteneur": "Conteneur",
    "dv":        "DV",
    "bitrate":   "Débit cible",
    "res":       "Résolution",
    "audio":     "Audio",
}


def _fmt_size(path) -> str:
    try:
        b = path.stat().st_size
    except OSError:
        return "—"
    if b >= 1_073_741_824:
        return f"{b / 1_073_741_824:.1f} Go"
    if b >= 1_048_576:
        return f"{b / 1_048_576:.0f} Mo"
    return f"{b // 1024} Ko"
_RESIZE_STEP        = 2
_RESIZE_MIN         = 6
_RESIZE_MIN_FICHIER = 20
_RESIZE_MIN_AUDIO   = 10


class DryrunScreen(TableNavMixin, Screen):
    """Écran de prévisualisation des décisions d'encodage."""

    BINDINGS = [
        Binding("backspace", "go_back",    "⌫ Retour",    show=True),
        Binding("escape",    "go_back",    "Retour",       show=False, priority=True),
        Binding("f2",        "run",        "F2 ▶ Lancer",  show=True),
        Binding("enter",     "run",        "↵  ▶ Lancer",  show=False, priority=True),
        Binding("shift+tab", "col_prev",   "⇧Tab Col préc.", show=True,  priority=True),
        Binding("tab",       "col_next",   "Tab Col suiv.",  show=True,  priority=True),
        Binding("<",         "col_shrink", "< Rétrécir",     show=True),
        Binding(">",         "col_grow",   "> Élargir",      show=True),
    ]

    DEFAULT_CSS = """
    DryrunScreen { layout: vertical; }
    #status-bar {
        height: 1;
        background: $accent;
        color: $text;
        padding: 0 2;
    }
    #dryrun-summary {
        height: 1;
        background: $panel;
        padding: 0 2;
        color: $text-muted;
    }
    DataTable { height: 1fr; }
    """

    def __init__(self, decisions: list[FileDecision]) -> None:
        super().__init__()
        self._decisions      = decisions
        self._resize_col_idx = 0

    @property
    def _app(self) -> "IrisEncodeApp":
        return self.app  # type: ignore[return-value]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="status-bar")
        yield DataTable(id="dryrun-table", cursor_type="row", zebra_stripes=True)
        yield Static("", id="dryrun-summary")
        yield TwoLineFooter(
            line1=[
                ("backspace", "Retour"),
                ("f2",        "Lancer l'encodage"),
                ("enter",     "Lancer"),
            ],
            line2=[
                ("shift+tab", "Col préc."),
                ("tab",       "Col suiv."),
                ("<",         "Rétrécir"),
                (">",         "Élargir"),
                ("home",      "Début"),
                ("end",       "Fin"),
                ("pageup",    "Page préc."),
                ("pagedown",  "Page suiv."),
                ("ctrl+x",    "Quitter"),
            ],
        )

    def on_mount(self) -> None:
        self._build_table()
        self._build_summary()

    # ── Table ─────────────────────────────────────────────────────────────────

    def _build_table(self) -> None:
        table  = self.query_one(DataTable)
        widths = cfg_mod.get_dryrun_column_widths(self._app.cfg)
        active = _RESIZE_COLS[self._resize_col_idx]

        def _hdr(key: str) -> str:
            label = _RESIZE_LABELS[key]
            return f"{label} ◄►" if key == active else label

        table.add_column(_hdr("fichier"),   width=max(_RESIZE_MIN_FICHIER, widths["fichier"]), key="file")
        table.add_column(_hdr("taille"),    width=widths["taille"],    key="taille")
        table.add_column(_hdr("action"),    width=widths["action"],    key="action")
        table.add_column(_hdr("conteneur"), width=widths["conteneur"], key="container")
        table.add_column(_hdr("dv"),        width=widths["dv"],        key="dv")
        table.add_column(_hdr("bitrate"),   width=widths["bitrate"],   key="bitrate")
        table.add_column(_hdr("res"),       width=widths["res"],       key="res")
        table.add_column(_hdr("audio"),     width=widths["audio"],     key="audio")

        for dec in self._decisions:
            vid  = dec.video
            info = dec.info

            dv_str = {
                DVAction.NONE:  "—",
                DVAction.HDR10: "→ HDR10",
                DVAction.DV:    "→ DV",
                DVAction.SDR:   "→ SDR ⚠",
            }.get(vid.dv_action, "?")

            if vid.action == VideoAction.SKIP:
                bitrate_str = "—"
                res_str     = f"{info.width}x{info.height}"
            else:
                bitrate_str = f"{vid.target_bitrate // 1000}k"
                res_str     = f"{vid.target_width}x{vid.target_height}"

            audio_parts = [
                f"{ad.track.channel_layout} {ad.track.language or '?'} (→ {ad.display() or 'copy'})"
                for ad in dec.audio if ad.action != AudioAction.EXCLUDE
            ]

            container = dec.output_container.upper().lstrip(".")

            table.add_row(
                Text(info.path.name, overflow="ellipsis", no_wrap=True),
                Text(_fmt_size(info.path), style="dim", no_wrap=True),
                Text(vid.label(), style=vid.style()),
                Text(container, no_wrap=True),
                Text(dv_str, no_wrap=True),
                Text(bitrate_str, no_wrap=True),
                Text(res_str, no_wrap=True),
                Text("  |  ".join(audio_parts) or "—", overflow="ellipsis", no_wrap=True),
            )

    def _build_summary(self) -> None:
        counts = Counter(dec.video.action for dec in self._decisions)
        total  = len(self._decisions)
        hevc   = counts[VideoAction.ENCODE_HEVC]
        h264   = counts[VideoAction.ENCODE_H264]
        skip   = counts[VideoAction.SKIP]
        col    = _RESIZE_LABELS[_RESIZE_COLS[self._resize_col_idx]]

        self.query_one("#status-bar", Static).update(
            f" Dry-run — {total} fichier(s) sélectionné(s)"
            f"  ·  Col: {col} [</>]"
        )
        self.query_one("#dryrun-summary", Static).update(
            f" À encoder : HEVC {hevc}  ·  H264 {h264}  ·  SKIP {skip}"
        )

    # ── Resize colonnes ───────────────────────────────────────────────────────

    def _rebuild_table(self) -> None:
        table      = self.query_one(DataTable)
        cursor_row = table.cursor_row
        table.clear(columns=True)
        self._build_table()
        self._build_summary()
        if table.row_count > 0:
            table.move_cursor(row=min(cursor_row, table.row_count - 1))

    def _apply_resize(self, delta: int) -> None:
        key     = _RESIZE_COLS[self._resize_col_idx]
        cfg     = self._app.cfg
        widths  = cfg_mod.get_dryrun_column_widths(cfg)
        current = widths.get(key, 10)
        floor   = (_RESIZE_MIN_FICHIER if key == "fichier"
                   else _RESIZE_MIN_AUDIO if key == "audio"
                   else _RESIZE_MIN)
        new_w   = max(floor, current + delta)
        if new_w == current:
            return
        cfg_mod.set_dryrun_column_width(cfg, key, new_w)
        cfg_mod.save(cfg)
        self._rebuild_table()

    def action_col_prev(self) -> None:
        self._resize_col_idx = (self._resize_col_idx - 1) % len(_RESIZE_COLS)
        self._rebuild_table()

    def action_col_next(self) -> None:
        self._resize_col_idx = (self._resize_col_idx + 1) % len(_RESIZE_COLS)
        self._rebuild_table()

    def action_col_shrink(self) -> None:
        self._apply_resize(-_RESIZE_STEP)

    def action_col_grow(self) -> None:
        self._apply_resize(+_RESIZE_STEP)

    # ── Navigation ────────────────────────────────────────────────────────────

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_run(self) -> None:
        to_encode = [d for d in self._decisions if d.video.action != VideoAction.SKIP]
        if not to_encode:
            return
        from .run import RunScreen
        self.app.push_screen(RunScreen(to_encode, self.app.platform))  # type: ignore[attr-defined]
