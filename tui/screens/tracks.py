"""
tui/screens/tracks.py — Sélection pistes + édition décision vidéo.

Un seul DataTable avec trois sections :
  ── VIDÉO ──────  (1 ligne éditable : action / débit / DV / original)
  ── AUDIO ──────  (pistes sélectionnables)
  ── SOUS-TITRES ─ (pistes sélectionnables)

Quand le curseur est sur la ligne vidéo :
  ←/→   cycle entre les champs éditables
  +/-   change la valeur du champ actif

Quand le curseur est sur une piste audio/sous-titre :
  Espace   toggle sélection

L   → lancer directement  |  ↵ → valider (ou sur ligne Valider)  |  ⌫ → annuler
Tab/Shift+Tab → colonne suivante/précédente  |  < / > → rétrécir/élargir
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual import on
from textual.widgets import DataTable, Header, Static
from ..mixins import TableNavMixin
from ..widgets.footer import TwoLineFooter

from .value_picker import ValuePickerScreen
from core.decision import (
    AudioAction, DVAction, FileDecision, TracksSelection,
    VideoAction, VideoOverride, decide_audio,
)
import core.config as cfg_mod

# ── Types de lignes ───────────────────────────────────────────────────────────
_ROW_VIDEO    = "video"
_ROW_AUDIO    = "audio"
_ROW_SUBTITLE = "subtitle"
_ROW_SECTION  = "section"
_ROW_VALIDATE = "validate"

_DEFAULT_SUB_LANGS = {"fre", "fra", "fr", "eng", "en"}

# Champs éditables (vidéo)
_EDIT_FIELDS = ["action", "bitrate", "dv", "orig"]

_ACTION_CYCLE = [
    VideoAction.ENCODE_HEVC,
    VideoAction.ENCODE_H264,
    VideoAction.ENCODE_AV1,
    VideoAction.SKIP,
]
_DV_CYCLE     = [DVAction.STRIP, DVAction.PRESERVE, DVAction.SDR]
_BITRATE_OPTS     = [500, 800, 1000, 1500, 2000, 2200, 2500, 3000, 3500, 5000, 8000, 12000]
_AV1_BITRATE_OPTS = [300, 500, 800, 1000, 1500, 2000, 2500, 3000, 4000, 6000]

_ACTION_SHORT = {
    VideoAction.ENCODE_HEVC: ("HEVC",   "magenta"),
    VideoAction.ENCODE_H264: ("H264",   "cyan"),
    VideoAction.ENCODE_AV1:  ("AV1 ⚠", "dark_orange"),
    VideoAction.SKIP:        ("SKIP",   "dim"),
}
_DV_SHORT = {
    DVAction.NONE:     ("—",      ""),
    DVAction.STRIP:    ("HDR10",  ""),
    DVAction.PRESERVE: ("DV copy","green"),
    DVAction.SDR:      ("SDR ⚠", "yellow"),
}

# Colonnes redimensionnables
_RESIZE_COLS   = ["codec", "fmt", "src"]
_RESIZE_LABELS = {"codec": "Codec", "fmt": "Format", "src": "Source"}
_RESIZE_STEP   = 2
_RESIZE_MIN    = 6


class TracksScreen(TableNavMixin, Screen["TracksSelection | None"]):

    BINDINGS = [
        Binding("space",     "toggle_row",    "Sélect",                show=True),
        Binding("left",      "field_prev",    "< Champ",               show=True),
        Binding("right",     "field_next",    "> Champ",               show=True),
        Binding("+",         "val_up",        "+ Val.",                 show=True),
        Binding("-",         "val_down",      "- Val.",                 show=True),
        Binding("enter",     "enter_action",  "Valider",               show=True, priority=True),
        Binding("l",         "launch",        "L  Lance",              show=True),
        Binding("backspace", "dismiss_cancel","Retour",                show=True),
        Binding("escape",    "dismiss_cancel","Retour",                show=False, priority=True),
        Binding("shift+tab", "col_prev",      "Col préc.",             show=True, priority=True),
        Binding("tab",       "col_next",      "Col suiv.",             show=True, priority=True),
        Binding("<",         "col_shrink",    "Rétrécir",              show=True),
        Binding(">",         "col_grow",      "Élargir",               show=True),
    ]

    DEFAULT_CSS = """
    TracksScreen { layout: vertical; }
    #status-bar {
        height: 1;
        background: $accent;
        color: $text;
        padding: 0 2;
    }
    DataTable { height: 1fr; }
    """

    def __init__(self, decision: FileDecision) -> None:
        super().__init__()
        self._decision = decision
        self._sel_audio: set[int] = set()
        self._sel_subs:  set[int] = set()
        self._rows: list[tuple[str, int]] = []
        # Édition vidéo
        self._edit_idx     = 0
        self._ov_action:   VideoAction | None = None
        self._ov_bitrate:  int | None         = None
        self._ov_dv:       DVAction | None    = None
        self._ov_delete:   bool | None        = None
        # Resize colonnes
        self._resize_col_idx: int = 0

    # ── Initialisation ────────────────────────────────────────────────────────

    def _init_selection(self) -> None:
        for ad in self._decision.audio:
            if ad.action != AudioAction.EXCLUDE:
                self._sel_audio.add(ad.track.index)
        if self._decision.subtitle_indices is not None:
            # Restaure une sélection déjà explicite
            self._sel_subs = set(self._decision.subtitle_indices)
        else:
            # Par défaut : toutes les pistes sélectionnées
            for st in self._decision.info.subtitle_tracks:
                self._sel_subs.add(st.index)

    # ── Décision effective ────────────────────────────────────────────────────

    def _eff_action(self)  -> VideoAction: return self._ov_action  or self._decision.video.action
    def _eff_bitrate(self) -> int:         return self._ov_bitrate or self._decision.video.target_bitrate
    def _eff_dv(self)      -> DVAction:    return self._ov_dv      or self._decision.video.dv_action
    def _eff_delete(self)  -> bool:
        if self._ov_delete is not None:
            return self._ov_delete
        return self._decision.profile.data.get("delete_source", False)

    def _has_override(self) -> bool:
        return any(x is not None for x in (self._ov_action, self._ov_bitrate, self._ov_dv, self._ov_delete))

    # ── Composition ───────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="status-bar")
        yield DataTable(id="tracks-table", cursor_type="row",
                        zebra_stripes=False, show_header=True)
        yield TwoLineFooter(
            line1=[
                ("space",     "Sélect"),
                ("left",      "Champ préc."),
                ("right",     "Champ suiv."),
                ("+",         "Valeur ↑"),
                ("-",         "Valeur ↓"),
                ("enter",     "Valider"),
            ],
            line2=[
                ("l",         "Lancer maintenant"),
                ("backspace", "Retour"),
                ("shift+tab", "Col préc."),
                ("tab",       "Col suiv."),
                ("<",         "Rétrécir"),
                (">",         "Élargir"),
                ("f10",       "Quitter"),
            ],
        )

    def on_mount(self) -> None:
        self._init_selection()
        self._build_table()
        self._update_status()
        self.query_one(DataTable).focus()

    # ── Construction table ────────────────────────────────────────────────────

    def _build_table(self, keep_cursor: bool = False) -> None:
        table      = self.query_one(DataTable)
        cursor_row = table.cursor_row if keep_cursor else 0
        table.clear(columns=True)

        widths = cfg_mod.get_tracks_column_widths(self.app.cfg)  # type: ignore[attr-defined]
        active = _RESIZE_COLS[self._resize_col_idx]

        def _hdr(key: str) -> str:
            label = _RESIZE_LABELS[key]
            return f"{label} ◄►" if key == active else label

        table.add_column("",           width=5,                        key="check")
        table.add_column("Piste",      width=10,                       key="idx")
        table.add_column(_hdr("codec"),width=max(_RESIZE_MIN, widths["codec"]), key="codec")
        table.add_column(_hdr("fmt"),  width=max(_RESIZE_MIN, widths["fmt"]),   key="fmt")
        table.add_column("Langue",     width=8,                        key="lang")
        table.add_column(_hdr("src"),  width=max(_RESIZE_MIN, widths["src"]),   key="src")
        table.add_column("Décision / Cible", width=None,               key="dec")
        self._rows = []

        # ── Section VIDÉO ─────────────────────────────────────────────────────
        table.add_row(
            Text(""), Text("── VIDÉO ───────────────", style="bold dim"),
            Text(""), Text(""), Text(""), Text(""), Text(""),
            key="__sec_video__",
        )
        self._rows.append((_ROW_SECTION, -1))
        self._add_video_row(table)

        # ── Section AUDIO ─────────────────────────────────────────────────────
        table.add_row(
            Text(""), Text("── AUDIO ───────────────", style="bold dim"),
            Text(""), Text(""), Text(""), Text(""), Text(""),
            key="__sec_audio__",
        )
        self._rows.append((_ROW_SECTION, -1))
        for ad in self._decision.audio:
            t   = ad.track
            idx = t.index
            excl = ad.action == AudioAction.EXCLUDE
            dim  = "dim" if excl else ""
            lock = " ⚑" if idx == 0 else ""
            table.add_row(
                self._check_text(_ROW_AUDIO, idx),
                Text(f"0:a:{idx}{lock}", no_wrap=True, style=dim),
                Text(t.codec,            no_wrap=True, style=dim),
                Text(t.channel_layout,   no_wrap=True, style=dim),
                Text(t.language or "?",  no_wrap=True, style=dim),
                Text(ad.reason,          overflow="ellipsis", no_wrap=True, style=dim),
                Text(ad.display() or "—", style="green" if not excl else "dim"),
                key=f"a:{idx}",
            )
            self._rows.append((_ROW_AUDIO, idx))

        # ── Section SOUS-TITRES ───────────────────────────────────────────────
        table.add_row(
            Text(""), Text("── SOUS-TITRES ─────────", style="bold dim"),
            Text(""), Text(""), Text(""), Text(""), Text(""),
            key="__sec_subs__",
        )
        self._rows.append((_ROW_SECTION, -1))
        subs = self._decision.info.subtitle_tracks
        if not subs:
            table.add_row(
                Text(""), Text("  (aucun)", style="dim italic"),
                Text(""), Text(""), Text(""), Text(""), Text(""),
                key="__no_subs__",
            )
            self._rows.append((_ROW_SECTION, -1))
        else:
            for st in subs:
                sel   = st.index in self._sel_subs
                style = "" if sel else "dim"
                type_str = "image" if st.is_image_based else "texte"
                cont_str = "→ MKV copy" if st.is_image_based else "→ MP4 copy"
                table.add_row(
                    self._check_text(_ROW_SUBTITLE, st.index),
                    Text(f"0:s:{st.index}", no_wrap=True, style=style),
                    Text(st.codec,          no_wrap=True, style=style),
                    Text(type_str,          no_wrap=True, style=style),
                    Text(st.language or "?",no_wrap=True, style=style),
                    Text("sélectionné" if sel else "—", style=style),
                    Text(cont_str, style="green" if sel else "dim"),
                    key=f"s:{st.index}",
                )
                self._rows.append((_ROW_SUBTITLE, st.index))

        # ── Ligne Valider ─────────────────────────────────────────────────────
        table.add_row(
            Text(""), Text("", style="dim"),
            Text(""), Text(""), Text(""), Text(""), Text(""),
            key="__sep_val__",
        )
        self._rows.append((_ROW_SECTION, -1))
        table.add_row(
            Text("[ ✓ ]", style="bold green"),
            Text("Valider la sélection", style="bold green"),
            Text(""), Text(""), Text(""), Text(""), Text(""),
            key="__validate__",
        )
        self._rows.append((_ROW_VALIDATE, -1))

        if keep_cursor and table.row_count > 0:
            table.move_cursor(row=min(cursor_row, table.row_count - 1))

    def _add_video_row(self, table: DataTable) -> None:
        """Construit et ajoute la ligne vidéo avec les champs éditables."""
        info    = self._decision.info
        vid     = self._decision.video
        action  = self._eff_action()
        bitrate = self._eff_bitrate()
        dv      = self._eff_dv()
        del_src = self._eff_delete()
        active  = _EDIT_FIELDS[self._edit_idx]
        ovr     = self._has_override()

        # Colonne "check" : icône action + indicateur override
        act_short, act_col = _ACTION_SHORT.get(action, ("?", ""))
        check_txt = Text(no_wrap=True)
        check_txt.append("✎ " if ovr else "  ", style="bold yellow" if ovr else "")
        check_txt.append(act_short, style=act_col)

        # Colonne "src" : infos source
        dv_src = f" DV:P{info.dv_profile}" if info.dv_profile else ""
        src_txt = Text(f"{info.width}x{info.height}  {info.kbps}k{dv_src}", no_wrap=True, style="dim")

        # Colonne "dec" : décision éditable avec champ actif surligné
        def _f(field: str, label: str, style: str) -> Text:
            t = Text(no_wrap=True)
            if field == active:
                t.append("◄", style="bold yellow")
                t.append(label, style=f"bold {style}" if style else "bold white")
                t.append("►", style="bold yellow")
            else:
                t.append(label, style=style or "")
            return t

        dec_txt = Text(no_wrap=True)
        dec_txt.append_text(_f("action", f"→ {_ACTION_SHORT.get(action,('?',''))[0]}",
                                _ACTION_SHORT.get(action,('?',''))[1]))
        dec_txt.append("  ·  ")
        dec_txt.append_text(_f("bitrate", f"{bitrate//1000} kbps", ""))
        if action != VideoAction.SKIP:
            dec_txt.append(f"  ·  {vid.target_width}x{vid.target_height}")
            dec_txt.append(f"  ·  {self._decision.output_container.upper().lstrip('.')}")
        dv_lbl, dv_sty = _DV_SHORT.get(dv, ("—", ""))
        if dv != DVAction.NONE:
            dec_txt.append("  ·  ")
            dec_txt.append_text(_f("dv", dv_lbl, dv_sty))
        # Champ original
        if self._ov_delete is None:
            del_profile = self._decision.profile.data.get("delete_source", False)
            orig_lbl = ("⚠ supprimer" if del_profile else "○ garder") + " (profil)"
            orig_sty = "dim"
        elif del_src:
            orig_lbl, orig_sty = "⚠ SUPPRIMER", "bold dark_orange"
        else:
            orig_lbl, orig_sty = "○ GARDER", "bold green"
        dec_txt.append("  ·  ")
        dec_txt.append_text(_f("orig", orig_lbl, orig_sty))

        table.add_row(
            check_txt,
            Text("0:v:0", no_wrap=True),
            Text(info.codec, no_wrap=True),
            Text(f"{info.width}x{info.height}", no_wrap=True),
            Text("—"),
            src_txt,
            dec_txt,
            key="v:0",
        )
        self._rows.append((_ROW_VIDEO, 0))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _check_text(self, row_type: str, idx: int) -> Text:
        sel = (idx in self._sel_audio) if row_type == _ROW_AUDIO else (idx in self._sel_subs)
        return Text("[x]" if sel else "[ ]", no_wrap=True)

    def _update_video_row(self) -> None:
        self._build_table(keep_cursor=True)

    def _update_track_cell(self, row_type: str, idx: int) -> None:
        key = f"{'a' if row_type == _ROW_AUDIO else 's'}:{idx}"
        try:
            self.query_one(DataTable).update_cell(
                key, "check", self._check_text(row_type, idx), update_width=False,
            )
        except Exception:
            pass

    def _update_status(self) -> None:
        fname   = self._decision.info.path.name
        n_a     = len(self._sel_audio);  tot_a = len(self._decision.audio)
        n_s     = len(self._sel_subs);   tot_s = len(self._decision.info.subtitle_tracks)
        ovr_str = "  ·  ★ vidéo modifiée" if self._has_override() else ""
        col_lbl = _RESIZE_LABELS[_RESIZE_COLS[self._resize_col_idx]]
        self.query_one("#status-bar", Static).update(
            f" {fname}    "
            f"Audio : {n_a}/{tot_a}  ·  "
            f"Sous-titres : {n_s}/{tot_s}"
            f"{ovr_str}"
            f"  ·  Col : {col_lbl} [</>]"
        )

    def _current_row(self) -> tuple[str, int] | None:
        row = self.query_one(DataTable).cursor_row
        if 0 <= row < len(self._rows):
            rt, idx = self._rows[row]
            if rt != _ROW_SECTION:
                return rt, idx
        return None

    def _make_selection(self, launch: bool = False) -> TracksSelection:
        ovr = VideoOverride(
            action        = self._ov_action,
            bitrate       = self._ov_bitrate,
            dv_action     = self._ov_dv,
            delete_source = self._ov_delete,
        ) if self._has_override() else None
        all_subs = {st.index for st in self._decision.info.subtitle_tracks}
        sub_indices = None if self._sel_subs == all_subs else sorted(self._sel_subs)
        return TracksSelection(
            audio=sorted(self._sel_audio),
            subtitles=sorted(self._sel_subs),
            launch=launch,
            video_override=ovr,
            subtitle_indices=sub_indices,
        )

    # ── Actions pistes ────────────────────────────────────────────────────────

    def on_key(self, event) -> None:
        if self._on_video_row():
            if event.key == "left":
                event.stop(); self.action_field_prev()
            elif event.key == "right":
                event.stop(); self.action_field_next()

    def action_toggle_row(self) -> None:
        info = self._current_row()
        if info is None:
            return
        row_type, idx = info
        if row_type == _ROW_AUDIO:
            if idx == 0:
                return
            self._sel_audio.symmetric_difference_update({idx})
            self._update_track_cell(_ROW_AUDIO, idx)
        elif row_type == _ROW_SUBTITLE:
            self._sel_subs.symmetric_difference_update({idx})
            self._update_track_cell(_ROW_SUBTITLE, idx)
        self._update_status()

    # ── Actions édition vidéo (actives seulement sur la ligne vidéo) ──────────

    def _on_video_row(self) -> bool:
        info = self._current_row()
        return info is not None and info[0] == _ROW_VIDEO

    def action_field_prev(self) -> None:
        if not self._on_video_row():
            return
        self._edit_idx = (self._edit_idx - 1) % len(_EDIT_FIELDS)
        self._update_video_row()

    def action_field_next(self) -> None:
        if not self._on_video_row():
            return
        self._edit_idx = (self._edit_idx + 1) % len(_EDIT_FIELDS)
        self._update_video_row()

    def action_val_up(self)   -> None: self._change_value(+1)
    def action_val_down(self) -> None: self._change_value(-1)

    def _change_value(self, delta: int) -> None:
        if not self._on_video_row():
            return
        field = _EDIT_FIELDS[self._edit_idx]

        if field == "action":
            cur  = self._eff_action()
            nxt  = _ACTION_CYCLE[(_ACTION_CYCLE.index(cur) + delta) % len(_ACTION_CYCLE)]
            self._ov_action = nxt if nxt != self._decision.video.action else None

        elif field == "bitrate":
            cur_k = self._eff_bitrate() // 1000
            ci    = min(range(len(_BITRATE_OPTS)), key=lambda i: abs(_BITRATE_OPTS[i]-cur_k))
            ni    = max(0, min(len(_BITRATE_OPTS)-1, ci + delta))
            nxt   = _BITRATE_OPTS[ni] * 1000
            self._ov_bitrate = nxt if nxt != self._decision.video.target_bitrate else None

        elif field == "dv":
            cur = self._eff_dv()
            if cur == DVAction.NONE:
                return
            nxt = _DV_CYCLE[(_DV_CYCLE.index(cur) + delta) % len(_DV_CYCLE)]
            self._ov_dv = nxt if nxt != self._decision.video.dv_action else None

        elif field == "orig":
            profile_val = self._decision.profile.data.get("delete_source", False)
            self._ov_delete = None if self._ov_delete is not None else not profile_val

        self._update_video_row()
        self._update_status()

    # ── Actions sortie ────────────────────────────────────────────────────────

    def action_enter_action(self) -> None:
        info = self._current_row()
        if info is not None and info[0] == _ROW_VIDEO:
            self._open_picker()
        else:
            self.action_dismiss_ok()

    def _open_picker(self) -> None:
        field       = _EDIT_FIELDS[self._edit_idx]
        profile_del = self._decision.profile.data.get("delete_source", False)

        cfg: tuple[str, list[str], int, object] | None = None

        if field == "action":
            opts    = [
                "HEVC",
                "H264",
                "AV1  (⚠ très gourmand CPU/GPU RTX30+)",
                "SKIP",
            ]
            current = _ACTION_CYCLE.index(self._eff_action())
            def apply_action(idx, s=self):
                if idx is None: return
                nxt = _ACTION_CYCLE[idx]
                s._ov_action = nxt if nxt != s._decision.video.action else None
                if nxt == VideoAction.ENCODE_AV1 and s._ov_bitrate is None:
                    s._ov_bitrate = 1500 * 1000
                s._update_video_row(); s._update_status()
            cfg = ("Action", opts, current, apply_action)

        elif field == "bitrate":
            is_av1  = (self._eff_action() == VideoAction.ENCODE_AV1)
            blist   = _AV1_BITRATE_OPTS if is_av1 else _BITRATE_OPTS
            title_b = "Débit (AV1)" if is_av1 else "Débit cible"
            opts    = [f"{v} kbps" for v in blist]
            cur_k   = self._eff_bitrate() // 1000
            current = min(range(len(blist)), key=lambda i: abs(blist[i]-cur_k))
            def apply_bitrate(idx, s=self, bl=blist):
                if idx is None: return
                nxt = bl[idx] * 1000
                s._ov_bitrate = nxt if nxt != s._decision.video.target_bitrate else None
                s._update_video_row(); s._update_status()
            cfg = (title_b, opts, current, apply_bitrate)

        elif field == "dv":
            if self._eff_dv() == DVAction.NONE: return
            opts    = [_DV_SHORT[d][0] for d in _DV_CYCLE]
            current = _DV_CYCLE.index(self._eff_dv())
            def apply_dv(idx, s=self):
                if idx is None: return
                nxt = _DV_CYCLE[idx]
                s._ov_dv = nxt if nxt != s._decision.video.dv_action else None
                s._update_video_row(); s._update_status()
            cfg = ("Dolby Vision", opts, current, apply_dv)

        elif field == "orig":
            del_lbl = "supprimer" if profile_del else "garder"
            opts    = [f"Profil ({del_lbl})", "Garder l'original", "Supprimer l'original"]
            current = 0 if self._ov_delete is None else (2 if self._ov_delete else 1)
            def apply_orig(idx, s=self):
                if idx is None: return
                s._ov_delete = None if idx == 0 else (idx == 2)
                s._update_video_row(); s._update_status()
            cfg = ("Fichier original", opts, current, apply_orig)

        if cfg:
            title, opts, cur, callback = cfg
            self.app.push_screen(ValuePickerScreen(title, opts, cur), callback)

    def action_dismiss_ok(self)     -> None: self.dismiss(self._make_selection(False))
    def action_launch(self)         -> None: self.dismiss(self._make_selection(True))
    def action_dismiss_cancel(self) -> None: self.dismiss(None)

    # ── Resize colonnes ───────────────────────────────────────────────────────

    def action_col_prev(self) -> None:
        self._resize_col_idx = (self._resize_col_idx - 1) % len(_RESIZE_COLS)
        self._build_table(keep_cursor=True)
        self._update_status()

    def action_col_next(self) -> None:
        self._resize_col_idx = (self._resize_col_idx + 1) % len(_RESIZE_COLS)
        self._build_table(keep_cursor=True)
        self._update_status()

    def action_col_shrink(self) -> None: self._apply_resize(-_RESIZE_STEP)
    def action_col_grow(self)   -> None: self._apply_resize(+_RESIZE_STEP)

    def _apply_resize(self, delta: int) -> None:
        key     = _RESIZE_COLS[self._resize_col_idx]
        cfg     = self.app.cfg  # type: ignore[attr-defined]
        widths  = cfg_mod.get_tracks_column_widths(cfg)
        current = widths.get(key, 12)
        new_w   = max(_RESIZE_MIN, current + delta)
        if new_w == current:
            return
        cfg_mod.set_tracks_column_width(cfg, key, new_w)
        cfg_mod.save(cfg)
        self._build_table(keep_cursor=True)
        self._update_status()
