"""
tui/screens/browser.py — Écran Browser IRIS ENCODE.

Navigation fichiers avec DataTable, sélection par case, colonnes redimensionnables.
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Header, Static

from core import config as cfg_mod
from core import preview
from core.decision import (
    AudioAction, FileDecision, VideoAction, decide, force_skip_to_encode,
)
from core.scanner import scan, scan_directory_recursive
from ..common import (
    DV_VALUE_STYLES,
    estimate_encoding_duration,
    fmt_bytes,
    fmt_duration,
    fmt_size,
    footer_line2,
    get_measured_speed,
)
from ..mixins import ColumnResizeMixin, TableNavMixin
from ..widgets.file_tree import FileNavigator
from ..widgets.footer import KeyFooter

if TYPE_CHECKING:
    from ..app import IrisEncodeApp

_LOG = logging.getLogger(__name__)

# Nombre max de scans ffprobe simultanés (I/O bound — process externes)
_SCAN_WORKERS = 4


# ─── Constantes ───────────────────────────────────────────────────────────────

_DIR_ICON  = "📁"
_DISK_ICON = "💾"   # icône volume/disque
_FILE_ICON = "🎬"


# ─── Estimation de taille ─────────────────────────────────────────────────────

def _estimate_output_bytes(dec: FileDecision) -> int:
    """Taille estimée de sortie (vidéo + audio conservé).
    Retourne 0 si action=SKIP ou durée inconnue."""
    if dec.video.action == VideoAction.SKIP:
        return 0
    duration = dec.info.duration
    if duration <= 0:
        return 0
    video_bps = dec.video.target_bitrate
    audio_bps = 0
    for ad in dec.audio:
        if ad.action == AudioAction.EXCLUDE:
            continue
        if ad.action == AudioAction.COPY:
            audio_bps += ad.track.bitrate or 192_000
        else:
            audio_bps += ad.output_bitrate
    total_bits = (video_bps + audio_bps) * duration
    return int(total_bits / 8)

# Marqueurs de ligne dans la table
_ROW_TYPE_DIR   = "dir"
_ROW_TYPE_FILE  = "file"
_ROW_TYPE_EMPTY = "empty"  # placeholder dossier vide


class BrowserScreen(TableNavMixin, ColumnResizeMixin, Screen):
    """Écran principal — navigation + sélection fichiers."""

    BINDINGS = [
        Binding("space",     "toggle_select",      "Sélect",   show=True),
        Binding("a",         "select_all",         "Tout",     show=True),
        Binding("n",         "select_none",        "Aucun",    show=True),
        Binding("enter",     "enter_dir",          "Ouvrir",   show=True, priority=True),
        Binding("backspace", "go_up",              "Remonter", show=True),
        Binding("t",         "open_tracks",        "Pistes",   show=False),
        Binding("v",         "play",               "Visualiser", show=True),
        Binding("ctrl+d",    "delete_file",        "Supprimer", show=True),
        Binding("f1",        "open_dryrun",        "Dry-run",  show=True),
        Binding("f2",        "open_run",           "Run",      show=True),
        Binding("f3",        "recursive_run",      "Récursif", show=True),
        Binding("f4",        "open_profile_picker","Profil",   show=True),
        Binding("f5",        "open_config",        "Gérer", show=True),
        Binding("f7",        "open_allocine",      "AlloCiné", show=True),
        Binding("f8",        "open_imdb",          "IMDB",     show=True),
    ]

    # Colonnes redimensionnables (ColumnResizeMixin) — fichier en premier pour accès au focus
    RESIZE_COLS   = ["fichier", "taille", "resolution", "duree", "debit", "codec",
                     "dolby_vision", "decision", "estim", "temps_estim", "audio"]
    RESIZE_LABELS = {"fichier": "Fichier", "taille": "Taille", "resolution": "Résol.",
                     "duree": "Durée", "debit": "Débit", "codec": "Codec",
                     "dolby_vision": "Dolby V.", "decision": "Décision", "estim": "Estim. (Δ%)",
                     "temps_estim": "Temps estim.", "audio": "Audio"}
    RESIZE_MIN    = {"fichier": 30, "audio": 10}

    DEFAULT_CSS = """
    BrowserScreen {
        layout: vertical;
    }
    #spacer-1 {
        height: 1;
    }
    #profile-bar {
        height: 2;
        background: $primary-darken-1;
        color: $text;
        padding: 0 1;
        border-bottom: solid $primary;
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
        self._scan_epoch: int = 0

    # ─── Accesseurs app ───────────────────────────────────────────────────────

    @property
    def _app(self) -> "IrisEncodeApp":
        return self.app  # type: ignore[return-value]

    def _active_profile(self):
        return self._app.profiles[self._app.active_profile_id]

    # ─── Composition ──────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="status-bar", classes="status-bar")
        yield Static("", id="spacer-1")
        yield Static("", id="profile-bar")
        yield Static("⏳ Analyse en cours…", id="scan-notice")
        yield DataTable(id="file-table", cursor_type="row", zebra_stripes=True)
        yield KeyFooter(
            actions=[
                ("space",     "Sélect"),
                ("a",         "Tout"),
                ("n",         "Aucun"),
                ("enter",     "Ouvrir"),
                ("v",         "Visualiser"),
                ("ctrl+d",    "Supprimer"),
                ("backspace", "Remonter"),
                ("home",      "Début"),
                ("end",       "Fin"),
                ("pageup",    "Page ↑"),
                ("pagedown",  "Page ↓"),
            ],
            nav=footer_line2(
                nav=False,
                resize=True,
                extra=(
                    ("f1", "Dry-run"),
                    ("f2", "Run"),
                    ("f3", "Récursif"),
                    ("f4", "Profil"),
                    ("f5", "Gérer"),
                    ("f7", "AlloCiné"),
                    ("f8", "IMDB"),
                ),
            ),
        )

    def on_mount(self) -> None:
        self._resize_col_idx = 0  # Initialise le focus sur "fichier" (première colonne redimensionnable)
        self._build_columns()
        self._update_profile_bar()
        self._refresh_view()
        self.query_one(DataTable).focus()

    # ─── Table ────────────────────────────────────────────────────────────────

    def _build_columns(self) -> None:
        table  = self.query_one(DataTable)
        widths = cfg_mod.get_column_widths(self._app.cfg)

        table.add_column("",                                width=3,    key="check")
        # Colonne fichier : 50% de la largeur de l'écran (ou largeur sauvegardée)
        if "fichier" in widths:
            fichier_width = widths["fichier"]
        else:
            # 50% de la largeur disponible (moins la colonne check et marges)
            terminal_width = self.size.width if hasattr(self, 'size') else 120
            fichier_width = max(self.RESIZE_MIN["fichier"], (terminal_width - 8) // 2)
        table.add_column(self.resize_header("fichier"), width=fichier_width, key="fichier")

        for col in self.RESIZE_COLS[1:]:  # Skip fichier, déjà ajoutée
            table.add_column(self.resize_header(col), width=widths[col], key=col)

    def _refresh_view(self) -> None:
        """Reconstruit la vue complète (dirs + fichiers)."""
        self._scan_epoch += 1   # invalide tout worker en cours
        self._update_status()
        self._load_directory()

    def _update_status(self) -> None:
        sel_count   = len(self._selected)
        total_files = sum(1 for t, _ in self._rows if t == _ROW_TYPE_FILE)
        self.query_one("#status-bar", Static).update(
            f" {self._nav.breadcrumb()}    "
            f"{sel_count}/{total_files} sélectionné(s)"
            f"  ·  Col : {self.resize_col_label} [</>]"
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
        dv_color = DV_VALUE_STYLES.get(f["dv"], "")

        # Ligne 1 : raccourci + nom du profil + infos techniques
        line1 = Text()
        line1.append("[F4] ", style="dim")
        if prof.data.get("delete_source", False):
            line1.append("⚠ ", style="bold dark_orange")
        line1.append(f"🎬 {pid.upper()} 🎬 ", style="bold yellow")
        line1.append(" • ", style="dim")
        line1.append("1080p ", style="dim"); line1.append(f["1080p"], style="bold")
        line1.append("  ·  ")
        line1.append(k4_str, style=k4_style)
        line1.append("  ·  ")
        line1.append("DV ", style="dim"); line1.append(f["dv"], style=dv_color or "bold")
        line1.append("  ·  ")
        line1.append("preset ", style="dim"); line1.append(f["preset"], style="bold")

        # Ligne 2 : autres infos
        line2 = Text()
        line2.append("HD audio ", style="dim"); line2.append(f["hd_audio"], style="bold")
        if prof.data.get("delete_source", False):
            line2.append("  ·  ")
            line2.append("⚠ SUPPRESSION", style="bold dark_orange")

        txt = Text()
        txt.append(line1)
        txt.append("\n")
        txt.append(line2)
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
                "", "", "", "", "", "", "", "",
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
                "", "", "", "", "", "", "", "",
                key="__empty__",
            )
            self._rows.append((_ROW_TYPE_EMPTY, None))

        self.query_one("#scan-notice", Static).update("")
        self._update_status()

    def _row_cells(self, dec: FileDecision, check: Text) -> tuple:
        info = dec.info
        vid  = dec.video

        name_txt  = Text(f"{_FILE_ICON} {info.path.name}", overflow="ellipsis", no_wrap=True)
        size_txt  = Text(fmt_size(info.path), style="dim", no_wrap=True)
        res_txt   = Text(f"{info.width}x{info.height}")
        dur_txt   = Text(fmt_duration(info.duration), style="dim")
        kbps_txt  = Text(f"{info.kbps}k")
        codec_txt = Text(info.codec)
        dv_txt    = Text(info.dv_label)
        dec_txt   = Text(vid.label(), style=vid.style())

        # Estimation taille de sortie
        try:
            src_bytes = info.path.stat().st_size
        except OSError:
            src_bytes = 0
        est_bytes = _estimate_output_bytes(dec)

        if est_bytes == 0:
            estim_txt = Text("—", style="dim", no_wrap=True)
        elif src_bytes > 0:
            delta_pct = (est_bytes - src_bytes) * 100 / src_bytes
            sign      = "+" if delta_pct > 0 else ""
            color     = "dark_orange" if delta_pct > 0 else "green"
            estim_txt = Text(
                f"{fmt_bytes(est_bytes)} ({sign}{delta_pct:.0f}%)",
                style=color, no_wrap=True,
            )
        else:
            estim_txt = Text(fmt_bytes(est_bytes), no_wrap=True)

        # Estimation temps d'encodage
        prof = self._active_profile()
        preset = prof.data.get("preset_encoder", "medium")
        measured_speed = get_measured_speed(self._app.cfg, vid.action)
        est_duration = estimate_encoding_duration(
            info.duration, info.kbps * 1000, vid.target_bitrate,
            vid.action, preset, measured_speed
        )
        temps_txt = Text(fmt_duration(est_duration), style="dim" if vid.action == VideoAction.SKIP else "")

        audio_txt = Text(dec.audio_summary, overflow="ellipsis", no_wrap=True)

        return (check, name_txt, size_txt, res_txt, dur_txt, kbps_txt, codec_txt, dv_txt, dec_txt, estim_txt, temps_txt, audio_txt)

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

        # Scans ffprobe parallélisés (ordre des résultats préservé par map)
        done = 0
        lock = threading.Lock()

        def _scan_one(vpath: Path) -> FileDecision | None:
            nonlocal done
            if self._scan_epoch != epoch:
                return None                 # navigation entre-temps : abandon anticipé
            dec: FileDecision | None = None
            try:
                info = scan(vpath)
                dec  = decide(
                    info, profile,
                    self._audio_overrides.get(vpath),
                    self._subtitle_overrides.get(vpath),
                )
            except Exception:
                _LOG.warning("Échec du scan : %s", vpath, exc_info=True)
            with lock:
                done += 1
                _set_notice(f"⏳ Analyse en cours… {done} / {total}")
            return dec

        decisions: list[FileDecision] = []
        if videos:
            with ThreadPoolExecutor(
                max_workers=min(_SCAN_WORKERS, total), thread_name_prefix="scan"
            ) as pool:
                decisions = [d for d in pool.map(_scan_one, videos) if d is not None]

        if self._scan_epoch != epoch:
            return                          # navigation entre-temps : ne pas peupler
        self.app.call_from_thread(self._populate_table, subdirs, decisions, epoch)

    # ─── Sélection de profil (F4) ──────────────────────────────────────────────

    def action_open_profile_picker(self) -> None:
        from .profile_picker import ProfilePickerScreen

        def _on_pick(pid: str | None) -> None:
            if pid is None:
                return
            self._app.active_profile_id = pid
            self._update_profile_bar()
            self._refresh_view()
        self.app.push_screen(
            ProfilePickerScreen(self._app.profiles, self._app.active_profile_id),
            _on_pick,
        )

    # ─── Resize colonnes (ColumnResizeMixin) ──────────────────────────────────

    def _resize_widths(self) -> dict[str, int]:
        return cfg_mod.get_column_widths(self._app.cfg)

    def _resize_persist(self, key: str, width: int) -> None:
        cfg_mod.set_column_width(self._app.cfg, key, width)
        cfg_mod.save(self._app.cfg)

    def _resize_rebuild(self) -> None:
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

    # ─── Navigation ───────────────────────────────────────────────────────────

    def _current_row_info(self) -> tuple[str, Path | None]:
        table = self.query_one(DataTable)
        idx   = table.cursor_row
        if 0 <= idx < len(self._rows):
            return self._rows[idx]
        return ("", None)

    def action_play(self) -> None:
        """
        Ouvre le fichier sous le curseur dans mpv.

        Juger une source avant de décider quoi en faire évite d'ouvrir un
        lecteur à côté : c'est souvent la première chose qu'on veut faire
        devant une liste de fichiers.
        """
        row_type, path = self._current_row_info()
        if row_type != _ROW_TYPE_FILE or path is None:
            return
        if not preview.available():
            self.app.bell()
            self._flash_status("mpv absent — relancez le preflight pour l'installer.")
            return
        try:
            preview.open_file(path)
        except Exception as e:
            self.app.bell()
            self._flash_status(f"Lecture impossible : {e}")

    def action_delete_file(self) -> None:
        """
        Supprime définitivement le fichier sous le curseur, après confirmation.

        Pendant du Visualiser : juger une source amène parfois à constater
        qu'elle ne vaut rien. Autant s'en débarrasser sans quitter l'écran.
        """
        row_type, path = self._current_row_info()
        if row_type != _ROW_TYPE_FILE or path is None:
            return

        def _on_confirm(ok: bool | None) -> None:
            if ok:
                self._delete_now(path)

        from .delete_confirm import DeleteConfirmModal
        self.app.push_screen(DeleteConfirmModal(path), _on_confirm)

    def _delete_now(self, path: Path) -> None:
        """Supprime le fichier et retire sa ligne, sans re-scanner le dossier."""
        try:
            path.unlink()
        except Exception as e:
            # Cas courant sous Windows : mpv tient encore le fichier ouvert.
            self.app.bell()
            self._flash_status(f"Suppression impossible : {e}")
            return

        self._decisions.pop(path, None)
        self._selected.discard(path)
        self._audio_overrides.pop(path, None)
        self._subtitle_overrides.pop(path, None)

        idx = next(
            (i for i, (t, p) in enumerate(self._rows)
             if t == _ROW_TYPE_FILE and p == path),
            None,
        )
        if idx is None:
            return
        del self._rows[idx]
        try:
            self.query_one(DataTable).remove_row(str(path))
        except Exception:
            pass

        if not self._rows:
            self._refresh_view()   # dossier vidé : faire apparaître le placeholder
        else:
            self._update_status()

    def _flash_status(self, message: str) -> None:
        """Message ponctuel dans la barre d'état, effacé au prochain rafraîchissement."""
        try:
            self.query_one("#status-bar", Static).update(f" {message}")
        except Exception:
            pass

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
            # Un mux a pu adopter un nouveau fichier : la décision ne porte
            # plus sur `path`. On la ré-indexe, et les sélections de pistes
            # faites sur l'ancien fichier ne s'appliquent plus.
            adopted = dec.info.path != path
            if adopted:
                self._decisions.pop(path, None)
                self._decisions[dec.info.path] = dec
                self._audio_overrides.pop(path, None)
                self._subtitle_overrides.pop(path, None)
            else:
                # Stocker les overrides pistes
                self._audio_overrides[path]    = result.audio
                self._subtitle_overrides[path] = result.subtitle_indices
                # Recalculer la décision audio
                dec.audio            = decide_audio(dec.info, dec.profile, result.audio)
                dec.subtitle_indices = result.subtitle_indices
            # Appliquer les overrides vidéo
            if result.video_override:
                from dataclasses import replace as dc_replace
                from core.decision import SUFFIX_BY_ACTION as _SUFFIX_BY_ACTION
                ov = result.video_override
                was_skip = (dec.video.action == VideoAction.SKIP)
                if ov.action        is not None:
                    # Recalculer le suffixe selon la nouvelle action
                    dec.video = dc_replace(
                        dec.video,
                        action       = ov.action,
                        output_suffix= _SUFFIX_BY_ACTION.get(ov.action, dec.video.output_suffix),
                    )
                    # Si l'originale était SKIP (bitrate=0) et qu'on encode désormais,
                    # poser le débit source par défaut si non spécifié explicitement
                    if was_skip and ov.bitrate is None and ov.action != VideoAction.SKIP:
                        dec.video = dc_replace(dec.video, target_bitrate=dec.info.bitrate)
                if ov.bitrate       is not None: dec.video = dc_replace(dec.video, target_bitrate=ov.bitrate)
                if ov.dv_action     is not None: dec.video = dc_replace(dec.video, dv_action=ov.dv_action)
                if ov.delete_source is not None: dec.delete_source_override = ov.delete_source
            # Mettre à jour la cellule audio dans la table
            if adopted:
                self._refresh_view()   # le fichier muxé remplace l'ancien
            else:
                try:
                    self.query_one(DataTable).update_cell(
                        str(path), "audio",
                        Text(dec.audio_summary, overflow="ellipsis", no_wrap=True),
                        update_width=False,
                    )
                except Exception:
                    pass
            # Lancement direct demandé depuis TracksScreen
            if result.launch_mode == "dryrun":
                from .dryrun import DryrunScreen
                self.app.push_screen(DryrunScreen([dec]))
            elif result.launch_mode == "run":
                from .run import RunScreen
                self.app.push_screen(
                    RunScreen([dec], self.app.platform)  # type: ignore[attr-defined]
                )
        self.app.push_screen(TracksScreen(dec), _on_tracks_return)

    def action_open_dryrun(self) -> None:
        decisions = [
            force_skip_to_encode(self._decisions[p])
            for p in self._selected
            if p in self._decisions
        ]
        if not decisions:
            return
        from .dryrun import DryrunScreen
        self.app.push_screen(DryrunScreen(decisions))

    def action_open_run(self) -> None:
        decisions = [
            force_skip_to_encode(self._decisions[p])
            for p in self._selected
            if p in self._decisions
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
                self._update_profile_bar()
                self._refresh_view()
        self.app.push_screen(ConfigScreen(), _on_config_return)

    # ─── Run récursif (F3) ────────────────────────────────────────────────────

    def action_recursive_run(self) -> None:
        row_type, path = self._current_row_info()
        if row_type != _ROW_TYPE_DIR or path is None:
            return
        from .recursive_confirm import RecursiveConfirmModal
        def _on_confirm(ok: bool) -> None:
            if ok:
                self._launch_recursive_scan(path)
        self.app.push_screen(RecursiveConfirmModal(path, self._app.active_profile_id),
                             _on_confirm)

    @work(thread=True, name="recursive-scan")
    def _launch_recursive_scan(self, directory: Path) -> None:
        self.app.call_from_thread(
            self.query_one("#scan-notice", Static).update,
            f"⏳ Scan récursif de {directory.name}…",
        )
        infos     = scan_directory_recursive(directory)
        profile   = self._active_profile()
        decisions = [decide(info, profile) for info in infos]
        decisions = [d for d in decisions if d.video.action != VideoAction.SKIP]

        def _push() -> None:
            self.query_one("#scan-notice", Static).update("")
            if not decisions:
                self.query_one("#scan-notice", Static).update(
                    "⚠ Aucun fichier à encoder dans ce répertoire."
                )
                return
            from .dryrun import DryrunScreen
            self.app.push_screen(DryrunScreen(decisions))

        self.app.call_from_thread(_push)

    # ─── Métadonnées IMDB / AlloCiné ─────────────────────────────────────────

    def _open_meta(self, source: str) -> None:
        row_type, path = self._current_row_info()
        if row_type != _ROW_TYPE_FILE or path is None:
            return
        from .meta_popup import MetaPopup
        self.app.push_screen(MetaPopup(path, source))

    def action_open_imdb(self) -> None:
        self._open_meta("imdb")

    def action_open_allocine(self) -> None:
        self._open_meta("allocine")

    # ─── Survol : chemin complet dans la zone notice ──────────────────────────

    @on(DataTable.RowHighlighted)
    def _on_row_highlight(self, event: DataTable.RowHighlighted) -> None:
        """Met à jour la barre de statut avec le nom complet du fichier au survol."""
        row_type, path = self._current_row_info()
        if path:
            notice = self.query_one("#scan-notice", Static)
            notice.update(str(path))
