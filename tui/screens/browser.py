"""
tui/screens/browser.py — Écran Browser IRIS ENCODE.

Navigation fichiers avec DataTable, sélection par case, colonnes redimensionnables.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Header, Label, Static
from ..widgets.footer import TwoLineFooter
from ..mixins import TableNavMixin

from core import config as cfg_mod
from core.decision import FileDecision, VideoAction, decide
from core.scanner import VideoInfo, scan, scan_directory
from ..widgets.file_tree import FileNavigator

if TYPE_CHECKING:
    from ..app import IrisEncodeApp


# ─── Constantes ───────────────────────────────────────────────────────────────

_DIR_ICON  = "📁"
_DISK_ICON = "💾"   # icône volume/disque
_FILE_ICON = "🎬"

_STYLE_HEVC = "bold magenta"
_STYLE_H264 = "bold cyan"
_STYLE_SDR  = "bold yellow"
_STYLE_SKIP = "dim"

# Marqueurs de ligne dans la table
_ROW_TYPE_DIR  = "dir"
_ROW_TYPE_FILE  = "file"
_ROW_TYPE_EMPTY = "empty"  # placeholder dossier vide

# Colonnes redimensionnables (ordre d'affichage)
_RESIZE_COLS   = ["resolution", "duree", "debit", "codec", "dolby_vision", "decision", "audio"]
_RESIZE_LABELS = {"fichier":"Fichier", "resolution":"Résol.", "duree":"Durée",
                   "debit":"Débit", "codec":"Codec", "dolby_vision":"Dolby V.",
                   "decision":"Décision", "audio":"Audio"}
_RESIZE_STEP   = 2
_RESIZE_MIN         = 6
_RESIZE_MIN_FICHIER = 20   # minimum plus large pour la colonne nom
_RESIZE_MIN_AUDIO   = 10   # minimum pour la colonne audio


def _fmt_duration(seconds: float) -> str:
    if seconds <= 0:
        return "—"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s   = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class BrowserScreen(TableNavMixin, Screen):
    """Écran principal — navigation + sélection fichiers."""

    BINDINGS = [
        Binding("space",     "toggle_select",      "Sélect",   show=True),
        Binding("a",         "select_all",         "Tout",     show=True),
        Binding("n",         "select_none",        "Aucun",    show=True),
        Binding("enter",     "enter_dir",          "Entrer ↵", show=True, priority=True),
        Binding("backspace", "go_up",              "Remonter", show=True),
        Binding("t",         "open_tracks",        "Pistes",   show=True),
        Binding("f1",        "open_dryrun",        "Dry-run",  show=True),
        Binding("f2",        "open_run",           "Run",      show=True),
        Binding("f4",        "open_profile_picker","Profil",   show=True),
        Binding("f5",        "open_config",        "Config",   show=True),
        # ── Resize colonnes ──────────────────────────────────────
        Binding("shift+tab", "col_prev",   "Col préc.", show=True, priority=True),
        Binding("tab",       "col_next",   "Col suiv.", show=True, priority=True),
        Binding("<",         "col_shrink", "Rétrécir",  show=True),
        Binding(">",         "col_grow",   "Élargir",   show=True),
    ]

    DEFAULT_CSS = """
    BrowserScreen {
        layout: vertical;
    }
    #status-bar {
        height: 1;
        background: $accent;
        color: $text;
        padding: 0 2;
    }
    #profile-bar {
        height: 1;
        background: $primary-darken-1;
        color: $text;
        padding: 0 2;
    }
    #scan-notice {
        height: 1;
        color: $text-muted;
        padding: 0 2;
    }
    DataTable { height: 1fr; }
    """

    def __init__(self, path: Path, start_virtual: bool = False) -> None:
        super().__init__()
        self._nav        = FileNavigator(path, start_virtual=start_virtual)
        self._decisions:  dict[Path, FileDecision] = {}
        self._selected:   set[Path] = set()
        self._rows:       list[tuple[str, Path | None]] = []
        # Override audio par fichier (TUI tracks)
        self._audio_overrides:    dict[Path, list[int]] = {}
        self._subtitle_overrides: dict[Path, list[int]] = {}
        self._resize_col_idx:  int                  = 0
        self._scan_epoch:      int                  = 0

    # ─── Accesseurs app ───────────────────────────────────────────────────────

    @property
    def _app(self) -> "IrisEncodeApp":
        return self.app  # type: ignore[return-value]

    def _active_profile(self):
        return self._app.profiles[self._app.active_profile_id]

    # ─── Composition ──────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="status-bar")
        yield Static("", id="profile-bar")
        yield Static("⏳ Analyse en cours…", id="scan-notice")
        yield DataTable(id="file-table", cursor_type="row", zebra_stripes=True)
        yield TwoLineFooter(
            line1=[
                ("space",    "Sélect"),
                ("a",        "Tout"),
                ("n",        "Aucun"),
                ("enter",    "Entrer"),
                ("backspace","Remonter"),
                ("t",        "Pistes"),
                ("pageup",   "Haut"),
                ("pagedown", "Bas"),
                ("home",     "Début"),
                ("end",      "Fin"),
            ],
            line2=[
                ("f1",        "Dry-run"),
                ("f2",        "Run"),
                ("f4",        "Profil"),
                ("f5",        "Config"),
                ("shift+tab", "Col préc."),
                ("tab",       "Col suiv."),
                ("<",         "Rétrécir"),
                (">",         "Élargir"),
                ("f10",       "Quitter"),
            ],
        )

    def on_mount(self) -> None:
        self._build_columns()
        self._update_profile_bar()
        self._refresh_view()
        self.query_one(DataTable).focus()

    # ─── Table ────────────────────────────────────────────────────────────────

    def _build_columns(self) -> None:
        table  = self.query_one(DataTable)
        widths = cfg_mod.get_column_widths(self._app.cfg)
        active = _RESIZE_COLS[self._resize_col_idx]

        def _hdr(key: str) -> str:
            label = _RESIZE_LABELS[key]
            return f"{label} ◄►" if key == active else label

        table.add_column("",            width=3,    key="check")
        table.add_column(_hdr("fichier"),      width=None, key="fichier")
        table.add_column(_hdr("resolution"),   width=widths["resolution"],   key="resolution")
        table.add_column(_hdr("duree"),        width=widths["duree"],        key="duree")
        table.add_column(_hdr("debit"),        width=widths["debit"],        key="debit")
        table.add_column(_hdr("codec"),        width=widths["codec"],        key="codec")
        table.add_column(_hdr("dolby_vision"), width=widths["dolby_vision"], key="dolby_vision")
        table.add_column(_hdr("decision"),     width=widths["decision"],     key="decision")
        table.add_column(_hdr("audio"),        width=widths["audio"],        key="audio")

    def _refresh_view(self) -> None:
        """Reconstruit la vue complète (dirs + fichiers)."""
        self._scan_epoch += 1   # invalide tout worker en cours
        self._update_status()
        self._load_directory()

    def _update_status(self) -> None:
        sel_count   = len(self._selected)
        total_files = sum(1 for t, _ in self._rows if t == _ROW_TYPE_FILE)
        col_label   = _RESIZE_LABELS[_RESIZE_COLS[self._resize_col_idx]]
        self.query_one("#status-bar", Static).update(
            f" {self._nav.breadcrumb()}    "
            f"{sel_count}/{total_files} sélectionné(s)"
            f"  ·  Col : {col_label} [</>]"
        )

    def _update_profile_bar(self) -> None:
        pid  = self._app.active_profile_id
        prof = self._app.profiles.get(pid)
        if prof is None:
            return
        f = prof.summary_fields()

        keep_4k  = prof.data.get("keep_4k", False)
        k4_str   = f"4K : {f['4k']}" if keep_4k else "4K → 1080p"
        k4_style = "green"              if keep_4k else "dim"
        dv_color = {"hdr": "yellow", "preserve": "green", "sdr": "bold dark_orange"}.get(f["dv"], "")

        txt = Text(no_wrap=True)
        txt.append(" Profil : ", style="dim")
        txt.append(f" {pid} ", style="bold white")
        txt.append("   ")
        txt.append("1080p ", style="dim"); txt.append(f["1080p"], style="bold")
        txt.append("  ·  ")
        txt.append(k4_str, style=k4_style)
        txt.append("  ·  ")
        txt.append("DV ", style="dim"); txt.append(f["dv"], style=dv_color or "bold")
        txt.append("  ·  ")
        txt.append("preset ", style="dim"); txt.append(f["preset"], style="bold")
        txt.append("  ·  ")
        txt.append("HD audio ", style="dim"); txt.append(f["hd_audio"], style="bold")
        if prof.data.get("delete_source", False):
            txt.append("  ·  ")
            txt.append("⚠ SUPPRESSION ORIGINAUX", style="bold dark_orange")
        txt.append("   F4 changer", style="dim")
        self.query_one("#profile-bar", Static).update(txt)

    def _populate_table(
        self,
        subdirs:   list[Path],
        decisions: list[FileDecision],
        epoch:     int = -1,
    ) -> None:
        """Appelé depuis le worker (thread-safe via call_from_thread).
        epoch : -1 = appel direct (rebuild colonnes) ; >= 0 = validé contre _scan_epoch.
        """
        if epoch >= 0 and epoch != self._scan_epoch:
            return                                  # callback stale — navigation entre-temps
        table = self.query_one(DataTable)
        table.clear()
        self._rows = []

        # ── Sous-répertoires ──────────────────────────────────────────────────
        is_virtual = self._nav.is_virtual
        for d in subdirs:
            row_key = str(d)
            icon    = _DISK_ICON if is_virtual else _DIR_ICON
            label   = str(d) if is_virtual else d.name
            table.add_row(
                "",
                Text(f"{icon} {label}", style="bold cyan" if is_virtual else "bold blue"),
                "", "", "", "", "", "", "",
                key=row_key,
            )
            self._rows.append((_ROW_TYPE_DIR, d))

        # ── Fichiers ──────────────────────────────────────────────────────────
        for dec in decisions:
            self._decisions[dec.info.path] = dec
            row_key = str(dec.info.path)
            check   = self._check_str(dec.info.path)
            self._rows.append((_ROW_TYPE_FILE, dec.info.path))
            table.add_row(
                *self._row_cells(dec, check),
                key=row_key,
            )

        # ── Dossier vide ──────────────────────────────────────────────────────
        if not subdirs and not decisions:
            table.add_row(
                "",
                Text("⚠  Aucun fichier vidéo dans ce dossier  —  ⌫ pour remonter",
                     style="dim italic"),
                "", "", "", "", "", "", "",
                key="__empty__",
            )
            self._rows.append((_ROW_TYPE_EMPTY, None))

        self.query_one("#scan-notice", Static).update("")
        self._update_status()

    def _row_cells(self, dec: FileDecision, check: str) -> tuple:
        info = dec.info
        vid  = dec.video

        # Nom (tronqué)
        name     = info.path.name
        name_txt = Text(f"{_FILE_ICON} {name}", overflow="ellipsis", no_wrap=True)

        # Résolution
        res_txt  = Text(f"{info.width}x{info.height}")

        # Durée
        dur_txt  = Text(_fmt_duration(info.duration), style="dim")

        # Débit
        kbps_txt = Text(f"{info.kbps}k")

        # Codec
        codec_txt = Text(info.codec)

        # Dolby Vision
        dv_txt   = Text(info.dv_label)

        # Décision (colorée)
        label    = vid.label()
        style    = vid.style()
        dec_txt  = Text(label, style=style)

        # Audio résumé
        audio_txt = Text(dec.audio_summary, overflow="ellipsis", no_wrap=True)

        return (check, name_txt, res_txt, dur_txt, kbps_txt, codec_txt, dv_txt, dec_txt, audio_txt)

    def _check_str(self, path: Path) -> Text:
        # Text() évite l'interprétation des crochets comme balises Rich markup
        return Text("[x]", no_wrap=True) if path in self._selected else Text("[ ]", no_wrap=True)

    def _update_row_check(self, path: Path) -> None:
        """Met à jour uniquement la cellule de case à cocher."""
        table   = self.query_one(DataTable)
        row_key = str(path)
        try:
            table.update_cell(row_key, "check", self._check_str(path), update_width=False)
        except Exception:
            pass

    # ─── Worker de scan ───────────────────────────────────────────────────────

    @work(thread=True, exclusive=True, name="scanner")
    def _load_directory(self) -> None:
        epoch   = self._scan_epoch          # capture l'epoch au lancement du thread
        subdirs = self._nav.list_subdirs()
        videos  = self._nav.list_videos()
        total   = len(videos)
        profile = self._active_profile()

        def _set_notice(msg: str) -> None:
            if self._scan_epoch != epoch:
                return                      # navigation entre-temps : abandon silencieux
            self.app.call_from_thread(
                self.query_one("#scan-notice", Static).update, msg
            )

        _set_notice(f"⏳ Analyse en cours… 0 / {total}")

        decisions: list[FileDecision] = []
        for i, vpath in enumerate(videos, 1):
            try:
                info = scan(vpath)
                override_a = self._audio_overrides.get(vpath)
                override_s = self._subtitle_overrides.get(vpath)
                decisions.append(decide(info, profile, override_a, override_s))
            except Exception:
                pass
            _set_notice(f"⏳ Analyse en cours… {i} / {total}")

        if self._scan_epoch != epoch:
            return                          # navigation entre-temps : ne pas peupler
        self.app.call_from_thread(self._populate_table, subdirs, decisions, epoch)


    # ─── Sélection de profil (F4) ──────────────────────────────────────────────

    def action_open_profile_picker(self) -> None:
        from .value_picker import ValuePickerScreen
        profiles = self._app.profiles
        names    = list(profiles.keys())
        cur      = self._app.active_profile_id
        cur_idx  = names.index(cur) if cur in names else 0
        pad      = max(len(n) for n in names)

        opts = []
        for name, prof in profiles.items():
            f       = prof.summary_fields()
            keep_4k = prof.data.get("keep_4k", False)
            k4_str  = f"4K {f['4k']}" if keep_4k else "4K→1080p"
            parts   = [f["1080p"], k4_str, f"DV {f['dv']}", f["preset"]]
            if prof.data.get("preserve_hd_audio"):
                parts.append("HD audio")
            if prof.data.get("delete_source"):
                parts.append("⚠ suppr.")
            opts.append(f"{name:<{pad}}   {'  ·  '.join(parts)}")

        def _on_pick(idx: int | None) -> None:
            if idx is None:
                return
            self._app.active_profile_id = names[idx]
            self._update_profile_bar()
            self._refresh_view()
        self.app.push_screen(ValuePickerScreen("Sélectionner un profil", opts, cur_idx), _on_pick)

    # ─── Resize colonnes ─────────────────────────────────────────────────────────────

    def _rebuild_columns(self) -> None:
        """Reconstruit colonnes + données après resize. Conserve curseur + sélection."""
        table      = self.query_one(DataTable)
        cursor_row = table.cursor_row
        subdirs    = [p for t, p in self._rows if t == _ROW_TYPE_DIR  and p is not None]
        decisions  = [self._decisions[p] for t, p in self._rows
                      if t == _ROW_TYPE_FILE and p is not None and p in self._decisions]
        table.clear(columns=True)
        self._build_columns()
        self._populate_table(subdirs, decisions)
        if table.row_count > 0:
            table.move_cursor(row=min(cursor_row, table.row_count - 1))

    def _apply_resize(self, delta: int) -> None:
        key     = _RESIZE_COLS[self._resize_col_idx]
        cfg     = self._app.cfg
        widths  = cfg_mod.get_column_widths(cfg)
        current = widths.get(key, 12)
        floor   = (_RESIZE_MIN_FICHIER if key == "fichier"
                   else _RESIZE_MIN_AUDIO if key == "audio"
                   else _RESIZE_MIN)
        new_w   = max(floor, current + delta)
        if new_w == current:
            return
        cfg_mod.set_column_width(cfg, key, new_w)
        cfg_mod.save(cfg)
        self._rebuild_columns()

    def action_col_prev(self) -> None:
        self._resize_col_idx = (self._resize_col_idx - 1) % len(_RESIZE_COLS)
        self._rebuild_columns()

    def action_col_next(self) -> None:
        self._resize_col_idx = (self._resize_col_idx + 1) % len(_RESIZE_COLS)
        self._rebuild_columns()

    def action_col_shrink(self) -> None:
        self._apply_resize(-_RESIZE_STEP)

    def action_col_grow(self) -> None:
        self._apply_resize(+_RESIZE_STEP)

    # ─── Navigation ───────────────────────────────────────────────────────────

    def _current_row_info(self) -> tuple[str, Path | None]:
        table = self.query_one(DataTable)
        idx   = table.cursor_row
        if 0 <= idx < len(self._rows):
            return self._rows[idx]
        return ("", None)

    def action_enter_dir(self) -> None:
        row_type, path = self._current_row_info()
        if row_type == _ROW_TYPE_DIR and path is not None:
            self._nav.enter(path)
            self._selected.clear()
            self._refresh_view()
        elif row_type == _ROW_TYPE_FILE:
            self.action_open_tracks()

    def action_go_up(self) -> None:
        changed = self._nav.go_up()
        if changed:
            self._selected.clear()
            self._refresh_view()

    # ─── Sélection ────────────────────────────────────────────────────────────

    def action_toggle_select(self) -> None:
        row_type, path = self._current_row_info()
        if row_type != _ROW_TYPE_FILE or path is None:
            return
        if path in self._selected:
            self._selected.discard(path)
        else:
            self._selected.add(path)
        self._update_row_check(path)
        self._update_status()

    def action_select_all(self) -> None:
        for row_type, path in self._rows:
            if row_type == _ROW_TYPE_FILE and path is not None:
                self._selected.add(path)
                self._update_row_check(path)
        self._update_status()

    def action_select_none(self) -> None:
        paths = list(self._selected)
        self._selected.clear()
        for path in paths:
            self._update_row_check(path)
        self._update_status()

    # ─── Ouverture des autres écrans ──────────────────────────────────────────

    def action_open_tracks(self) -> None:
        row_type, path = self._current_row_info()
        if row_type != _ROW_TYPE_FILE or path is None:
            return
        dec = self._decisions.get(path)
        if dec is None:
            return
        from .tracks import TracksScreen
        from core.decision import TracksSelection, decide_audio
        def _on_tracks_return(result: TracksSelection | None) -> None:
            if result is None:
                return
            # Stocker les overrides pistes
            self._audio_overrides[path]    = result.audio
            self._subtitle_overrides[path] = result.subtitle_indices
            # Recalculer la décision audio
            dec.audio            = decide_audio(dec.info, dec.profile, result.audio)
            dec.subtitle_indices = result.subtitle_indices
            # Appliquer les overrides vidéo
            if result.video_override:
                from dataclasses import replace as dc_replace
                ov = result.video_override
                if ov.action        is not None: dec.video = dc_replace(dec.video, action=ov.action)
                if ov.bitrate       is not None: dec.video = dc_replace(dec.video, target_bitrate=ov.bitrate)
                if ov.dv_action     is not None: dec.video = dc_replace(dec.video, dv_action=ov.dv_action)
                if ov.delete_source is not None: dec.delete_source_override = ov.delete_source
            # Mettre à jour la cellule audio dans la table
            try:
                self.query_one(DataTable).update_cell(
                    str(path), "audio",
                    Text(dec.audio_summary, overflow="ellipsis", no_wrap=True),
                    update_width=False,
                )
            except Exception:
                pass
            # Lancement direct demandé depuis TracksScreen
            if result.launch:
                from .run import RunScreen
                self.app.push_screen(
                    RunScreen([dec], self.app.platform)  # type: ignore[attr-defined]
                )
        self.app.push_screen(TracksScreen(dec), _on_tracks_return)
    def action_open_dryrun(self) -> None:
        decisions = [
            self._decisions[p]
            for p in self._selected
            if p in self._decisions
        ]
        if not decisions:
            return
        from .dryrun import DryrunScreen
        self.app.push_screen(DryrunScreen(decisions))

    def action_open_run(self) -> None:
        decisions = [
            self._decisions[p]
            for p in self._selected
            if p in self._decisions
            and self._decisions[p].video.action != VideoAction.SKIP
        ]
        if not decisions:
            return
        from .run import RunScreen
        self.app.push_screen(RunScreen(decisions, self._app.platform))

    def action_open_config(self) -> None:
        from .config import ConfigScreen
        def _on_config_return(changed: bool) -> None:
            if changed:
                # Recalcul des décisions avec le nouveau profil
                self._decisions.clear()
                self._refresh_view()
        self.app.push_screen(ConfigScreen(), _on_config_return)

    # ─── Mise à jour profil actif (depuis ConfigScreen) ───────────────────────

    @on(DataTable.RowHighlighted)
    def _on_row_highlight(self, event: DataTable.RowHighlighted) -> None:
        """Met à jour la barre de statut avec le nom complet du fichier au survol."""
        row_type, path = self._current_row_info()
        if path:
            notice = self.query_one("#scan-notice", Static)
            notice.update(str(path))
