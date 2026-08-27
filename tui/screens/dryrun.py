"""
tui/screens/dryrun.py — Écran Dry-run.

Prévisualise les décisions pour tous les fichiers sélectionnés.
Colonnes redimensionnables via Tab/Shift+Tab (sélection) et </> (resize).
"""
from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Header, Static

from core import config as cfg_mod
from core.decision import (
    ACTION_CYCLE,
    cycle_index,
    AV1_BITRATE_OPTS_KBPS,
    SUFFIX_BY_ACTION,
    AudioAction, DVAction, FileDecision, VideoAction,
)
from ..common import (
    CODEC_PICKER_OPTS,
    bitrate_picker_config,
    estimate_encoding_duration,
    fmt_bytes,
    fmt_duration,
    footer_line2,
    get_measured_speed,
)
from ..mixins import ColumnResizeMixin, TableNavMixin
from ..widgets.footer import KeyFooter
from .value_picker import ValuePickerScreen

if TYPE_CHECKING:
    from ..app import IrisEncodeApp


def _estimate_output_bytes(dec: FileDecision) -> int:
    """Taille estimée de sortie (vidéo + audio conservé).
    Retourne 0 si action=SKIP ou durée inconnue."""
    if dec.video.action == VideoAction.SKIP:
        return 0
    # Un remux ne recalcule aucune image : la sortie pèse ce que pèse la
    # source, au RPU près — quelques mégaoctets sur un film.
    if dec.video.action == VideoAction.STRIP_DV:
        try:
            return dec.info.path.stat().st_size
        except OSError:
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


class DryrunScreen(TableNavMixin, ColumnResizeMixin, Screen):
    """Écran de prévisualisation des décisions d'encodage."""

    BINDINGS = [
        Binding("space",     "toggle_select",        "Sélect",  show=True),
        Binding("f2",        "run",         "Lancer",  show=True),
        Binding("enter",     "run",         "Lancer",  show=False, priority=True),
        Binding("f6",        "open_codec",  "Codec",   show=True),
        Binding("f7",        "open_bitrate","Débit",   show=True),
        Binding("backspace", "go_back",     "Retour",  show=True),
        Binding("escape",    "go_back",     "Retour",  show=False, priority=True),
    ]

    # Colonnes redimensionnables (ColumnResizeMixin) — fichier en premier pour accès au focus
    RESIZE_COLS   = ["fichier", "taille", "duree", "estim", "temps_estim", "action", "conteneur",
                     "dv", "bitrate", "res", "audio"]
    RESIZE_LABELS = {
        "fichier":     "Fichier",
        "taille":      "Taille",
        "duree":       "Durée",
        "estim":       "Estim. (Δ%)",
        "temps_estim": "ETA",
        "action":      "Action",
        "conteneur":   "Conteneur",
        "dv":          "DV",
        "bitrate":     "Débit cible",
        "res":         "Résolution",
        "audio":       "Audio",
    }
    RESIZE_MIN    = {"fichier": 20, "audio": 10}

    DEFAULT_CSS = """
    DryrunScreen { layout: vertical; }
    #dryrun-summary {
        height: 1;
        background: $panel;
        padding: 0 2;
        color: $text-muted;
    }
    #dryrun-table { height: 1fr; }
    """

    def __init__(self, decisions: list[FileDecision]) -> None:
        super().__init__()
        self._decisions = decisions
        self._selected  = set(range(len(decisions)))  # indices des décisions sélectionnées
        self._totals    = (0, 0)   # (source, estimé) en octets — posés par _build_table

    @property
    def _app(self) -> "IrisEncodeApp":
        return self.app  # type: ignore[return-value]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="status-bar", classes="status-bar", markup=False)
        yield DataTable(id="dryrun-table", cursor_type="row", zebra_stripes=True)
        yield Static("", id="dryrun-summary")
        yield KeyFooter(
            actions=[
                ("f2",        "Lancer"),
                ("f6",        "Codec"),
                ("f7",        "Débit"),
                ("backspace", "Retour"),
            ],
            nav=footer_line2(nav=True, resize=True),
        )

    def on_mount(self) -> None:
        self._resize_col_idx = 0  # Initialise le focus sur "fichier" (première colonne redimensionnable)
        self._build_table()
        self._build_summary()

    # ── Table ─────────────────────────────────────────────────────────────────

    def _build_table(self) -> None:
        table  = self.query_one(DataTable)
        widths = cfg_mod.get_dryrun_column_widths(self._app.cfg)

        table.add_column("",                            width=3,    key="check")
        # Colonne fichier : 50% de la largeur de l'écran (ou largeur sauvegardée)
        if "fichier" in widths and widths["fichier"] > self.RESIZE_MIN["fichier"]:
            fichier_width = widths["fichier"]
        else:
            # 50% de la largeur disponible (moins la colonne check et marges)
            terminal_width = self.size.width if hasattr(self, 'size') else 120
            fichier_width = max(self.RESIZE_MIN["fichier"], (terminal_width - 8) // 2)
        table.add_column(self.resize_header("fichier"), width=fichier_width, key="fichier")

        for col in self.RESIZE_COLS[1:]:
            table.add_column(self.resize_header(col), width=widths[col], key=col)

        total_src = 0
        total_est = 0
        for idx, dec in enumerate(self._decisions):
            vid  = dec.video
            info = dec.info

            dv_str = {
                DVAction.NONE:  "—",
                DVAction.HDR10: "→ HDR10",
                DVAction.DV:    "→ DV",
                DVAction.SDR:   "→ SDR ⚠",
            }.get(vid.dv_action, "?")

            if vid.action in (VideoAction.SKIP, VideoAction.STRIP_DV):
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

            # Estimation taille de sortie — un seul stat() par fichier,
            # réutilisé pour la ligne ET les totaux du summary
            try:
                src_bytes = info.path.stat().st_size
            except OSError:
                src_bytes = 0
            est_bytes = _estimate_output_bytes(dec)

            total_src += src_bytes
            if est_bytes:
                total_est += est_bytes
            elif vid.action == VideoAction.SKIP:
                # SKIP : le fichier reste tel quel, on compte sa taille source
                total_est += src_bytes

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
            prof = self._app.profiles.get(self._app.active_profile_id)
            preset = prof.data.get("preset_encoder", "medium") if prof else "medium"
            measured_speed = get_measured_speed(self._app.cfg, vid.action)
            est_enc_duration = estimate_encoding_duration(
                info.duration, info.kbps * 1000, vid.target_bitrate,
                vid.action, preset, measured_speed
            )
            temps_txt = Text(fmt_duration(est_enc_duration), style="dim" if vid.action == VideoAction.SKIP else "")

            check_str = Text("[x]", no_wrap=True) if idx in self._selected else Text("[ ]", no_wrap=True)
            table.add_row(
                check_str,
                Text(info.path.name, overflow="ellipsis", no_wrap=True),
                Text(fmt_bytes(src_bytes) if src_bytes else "—", style="dim", no_wrap=True),
                Text(fmt_duration(info.duration), style="dim", no_wrap=True),
                estim_txt,
                temps_txt,
                Text(vid.label(), style=vid.style()),
                Text(container, no_wrap=True),
                Text(dv_str, no_wrap=True),
                Text(bitrate_str, no_wrap=True),
                Text(res_str, no_wrap=True),
                Text("  |  ".join(audio_parts) or "—", overflow="ellipsis", no_wrap=True),
            )

        self._totals = (total_src, total_est)

    def _build_summary(self) -> None:
        counts = Counter(dec.video.action for dec in self._decisions)
        total  = len(self._decisions)
        hevc   = counts[VideoAction.ENCODE_HEVC]
        h264   = counts[VideoAction.ENCODE_H264]
        av1    = counts[VideoAction.ENCODE_AV1]
        skip   = counts[VideoAction.SKIP]
        strip  = counts[VideoAction.STRIP_DV]

        total_src, total_est = self._totals
        gain_str = ""
        if total_src > 0 and total_est > 0:
            delta_pct = (total_est - total_src) * 100 / total_src
            sign      = "+" if delta_pct > 0 else ""
            gain_str  = (
                f"  ·  Source : {fmt_bytes(total_src)}  →  "
                f"Estimé : {fmt_bytes(total_est)} ({sign}{delta_pct:.0f}%)"
            )

        av1_str   = f"  ·  AV1 {av1}" if av1 else ""
        strip_str = f"  ·  DV→HDR10 {strip}" if strip else ""
        self.query_one("#status-bar", Static).update(
            f" Dry-run — {total} fichier(s) sélectionné(s)"
            f"  ·  Col : {self.resize_col_label} [</>]"
        )
        self.query_one("#dryrun-summary", Static).update(
            f" À encoder : HEVC {hevc}  ·  H264 {h264}{av1_str}"
            f"{strip_str}  ·  SKIP {skip}{gain_str}"
        )

    # ── Resize colonnes (ColumnResizeMixin) ───────────────────────────────────

    def _resize_widths(self) -> dict[str, int]:
        return cfg_mod.get_dryrun_column_widths(self._app.cfg)

    def _resize_persist(self, key: str, width: int) -> None:
        cfg_mod.set_dryrun_column_width(self._app.cfg, key, width)
        cfg_mod.save(self._app.cfg)

    def _resize_rebuild(self) -> None:
        table      = self.query_one(DataTable)
        cursor_row = table.cursor_row
        table.clear(columns=True)
        self._build_table()
        self._build_summary()
        if table.row_count > 0:
            table.move_cursor(row=min(cursor_row, table.row_count - 1))

    # ── Sélection des lignes ──────────────────────────────────────────────────

    def action_toggle_select(self) -> None:
        table = self.query_one(DataTable)
        idx   = table.cursor_row
        if idx is not None and 0 <= idx < len(self._decisions):
            if idx in self._selected:
                self._selected.discard(idx)
            else:
                self._selected.add(idx)
            self._resize_rebuild()

    # ── Édition par ligne (codec / débit) ────────────────────────────────────

    def _current_decision(self) -> FileDecision | None:
        """Décision sous le curseur, ou None si la table est vide."""
        table = self.query_one(DataTable)
        idx   = table.cursor_row
        if idx is None or idx < 0 or idx >= len(self._decisions):
            return None
        return self._decisions[idx]

    def _apply_codec(self, dec: FileDecision, new_action: VideoAction) -> None:
        """Change le codec d'une décision et ajuste suffix/bitrate cohérents."""
        from dataclasses import replace as dc_replace
        old_action = dec.video.action
        if new_action == old_action:
            return
        # SKIP et retrait de DV ont tous deux un débit cible nul : repartir du
        # débit source quand l'un ou l'autre bascule en encodage.
        was_skip   = old_action in (VideoAction.SKIP, VideoAction.STRIP_DV)
        new_bitrate = dec.video.target_bitrate
        if was_skip and new_action != VideoAction.SKIP:
            new_bitrate = dec.info.bitrate
        # H264 ne peut pas porter de RPU DV → DV→HDR10 forcé
        new_dv = dec.video.dv_action
        if new_action == VideoAction.ENCODE_H264 and new_dv == DVAction.DV:
            new_dv = DVAction.HDR10
        dec.video = dc_replace(
            dec.video,
            action         = new_action,
            target_bitrate = new_bitrate if new_action != VideoAction.SKIP else 0,
            output_suffix  = SUFFIX_BY_ACTION.get(new_action, dec.video.output_suffix),
            dv_action      = new_dv,
            reason         = f"Modifié manuellement (dry-run) : {new_action.name}",
        )

    def _apply_bitrate(self, dec: FileDecision, new_bitrate_bps: int) -> None:
        from dataclasses import replace as dc_replace
        if dec.video.action == VideoAction.SKIP:
            return
        dec.video = dc_replace(
            dec.video,
            target_bitrate = new_bitrate_bps,
            reason         = f"Débit modifié manuellement (dry-run) : {new_bitrate_bps // 1000}k",
        )

    def action_open_codec(self) -> None:
        dec = self._current_decision()
        if dec is None:
            return
        current = cycle_index(dec.video.action)
        def _on_pick(idx: int | None, d=dec) -> None:
            if idx is None:
                return
            new_action = ACTION_CYCLE[idx]
            self._apply_codec(d, new_action)
            # AV1 a sa propre échelle de débits — clamp si le débit courant ne s'y trouve pas
            if new_action == VideoAction.ENCODE_AV1:
                cur_k = d.video.target_bitrate // 1000
                if cur_k not in AV1_BITRATE_OPTS_KBPS:
                    closest = min(AV1_BITRATE_OPTS_KBPS, key=lambda v: abs(v - cur_k))
                    self._apply_bitrate(d, closest * 1000)
            self._resize_rebuild()
        self.app.push_screen(ValuePickerScreen("Codec", CODEC_PICKER_OPTS, current), _on_pick)

    def action_open_bitrate(self) -> None:
        dec = self._current_decision()
        if dec is None or dec.video.action == VideoAction.SKIP:
            return
        title, opts, current, blist = bitrate_picker_config(
            dec.video.action, dec.video.target_bitrate
        )
        def _on_pick(idx: int | None, d=dec, bl=blist) -> None:
            if idx is None:
                return
            self._apply_bitrate(d, bl[idx] * 1000)
            self._resize_rebuild()
        self.app.push_screen(ValuePickerScreen(title, opts, current), _on_pick)

    # ── Navigation ────────────────────────────────────────────────────────────

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_run(self) -> None:
        to_encode = [self._decisions[idx] for idx in self._selected
                     if idx < len(self._decisions) and self._decisions[idx].video.action != VideoAction.SKIP]
        if not to_encode:
            return
        from .run import RunScreen
        self.app.push_screen(RunScreen(to_encode, self.app.platform))  # type: ignore[attr-defined]
