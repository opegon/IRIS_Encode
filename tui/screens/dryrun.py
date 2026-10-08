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
from textual.widgets import DataTable, Static

from core.i18n import _, N_, ngettext
from core import config as cfg_mod
from core.decision import (
    Emphase,
    STYLE_PAR_EMPHASE,
    ACTION_CYCLE,
    cycle_index,
    AV1_BITRATE_OPTS_KBPS,
    choisir_codec,
    AudioAction, DVAction, DV_SORTIE, FileDecision, VideoAction,
    video_recopiee,
)
from ..common import sauver_config
from ..common import (confier_a_la_file, langue_affichee, barre_etat, 
    actions_ecran,
    touche,
    cellule,
    retour_accueil,
    codec_picker_opts,
    bitrate_picker_config,
    estimate_encoding_duration,
    fmt_bytes,
    fmt_duration,
    footer_line2,
    get_measured_speed,
)
from ..mixins import ColumnResizeMixin, TableNavMixin
from ..widgets.entete import Entete
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
    # source, au RPU près — quelques mégaoctets sur un film. Une source Dolby
    # Vision dont le RPU ne peut pas être réinjecté est dans le même cas : sa
    # vidéo est recopiée, et l'estimer au débit cible annonçait une réduction
    # qui n'aura pas lieu.
    if (dec.video.action == VideoAction.STRIP_DV
            or video_recopiee(dec.video.action, dec.video.dv_action)):
        try:
            return dec.info.taille
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
        Binding("space",     "toggle_select",        N_("Toggle"),  show=True),
        # Pas de `↵` : partout ailleurs elle ouvre ou valide, ici elle lançait
        # des heures d'encodage sans rien demander (UX-05). F2 seule lance.
        Binding("f2",        "run",         N_("Encode"), show=True),
        Binding("f6",        "open_codec",  N_("Codec"), show=True),
        Binding("f7",        "open_bitrate",N_("Bitrate"),   show=True),
        Binding("backspace", "go_back",     N_("Back"),  show=True),
        Binding("escape",    "go_back",     N_("Back"),  show=False, priority=True),
        # `priority` : un DataTable etouffe la touche avant les bindings —
        # meme avertissement qu'en tete de tui/mixins.py.
        Binding("ctrl+home", "accueil",   N_("Home"),       show=True,
                priority=True),
    ]

    # Colonnes redimensionnables (ColumnResizeMixin) — fichier en premier pour accès au focus
    RESIZE_COLS   = ["fichier", "taille", "duree", "estim", "temps_estim", "action", "conteneur",
                     "dv", "bitrate", "res", "audio"]
    RESIZE_LABELS = {
        "fichier":     N_("File"),
        "taille":      N_("Size"),
        "duree":       N_("Duration"),
        # TRANSLATORS: estimated output size and its change; keep it short.
        "estim":       N_("Est. (Δ%)"),
        "temps_estim": "ETA",
        "action":      N_("Action"),
        "conteneur":   N_("Container"),
        "dv":          "DV",
        "bitrate":     N_("Target bitrate"),
        "res":         N_("Resolution"),
        "audio":       "Audio",
    }
    RESIZE_MIN    = {"fichier": 20, "audio": 10, **cfg_mod.COLUMN_MIN_WIDTHS}
    RESIZE_FIXE   = 3 + 2 + 2   # case à cocher, sa marge, barre de défilement

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
        # Des copies : un codec ou un débit changé ici ne vaut que pour le
        # lancement `F2` ; Retour n'en laisse rien sur l'accueil (CR-88).
        from copy import deepcopy
        self._decisions = [deepcopy(d) for d in decisions]
        self._selected  = set(range(len(decisions)))  # indices des décisions sélectionnées
        self._totals    = (0, 0)   # (source, estimé) en octets — posés par _build_table

    @property
    def _app(self) -> "IrisEncodeApp":
        return self.app  # type: ignore[return-value]

    def compose(self) -> ComposeResult:
        yield Entete()
        yield Static("", id="status-bar", classes="status-bar", markup=False)
        yield DataTable(id="dryrun-table", cursor_type="row", zebra_stripes=True)
        yield Static("", id="dryrun-summary")
        yield KeyFooter(
            actions=actions_ecran(self),
            nav=footer_line2(back=True, nav=True, resize=True, accueil=True),
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
        fichier_width = self._largeur_fichier(widths)
        table.add_column(self.resize_header("fichier"), width=fichier_width, key="fichier")

        for col in self.RESIZE_COLS[1:]:
            table.add_column(self.resize_header(col), width=self.resize_largeur(col, widths[col]), key=col)

        total_src = 0
        total_est = 0
        for idx, dec in enumerate(self._decisions):
            vid  = dec.video
            info = dec.info

            dv_str = (f"→ {DV_SORTIE[vid.dv_action]}"
                      if vid.dv_action in DV_SORTIE else "—")

            if vid.action in (VideoAction.SKIP, VideoAction.STRIP_DV):
                bitrate_str = "—"
                res_str     = f"{info.width}x{info.height}"
            else:
                bitrate_str = f"{vid.target_bitrate // 1000}k"
                res_str     = f"{vid.target_width}x{vid.target_height}"
                if dec.desentrelace:
                    res_str += " · " + _("deinterlaced")

            audio_parts = [
                f"{ad.track.channel_layout} {langue_affichee(ad.track.language)} ({ad.display()})"
                for ad in dec.audio if ad.action != AudioAction.EXCLUDE
            ]

            container = dec.output_container.upper().lstrip(".")
            # Une piste écartée par le conteneur doit se voir avant le
            # lancement, pas se découvrir dans le fichier produit.
            ecartes = len(dec.sous_titres_ecartes)
            if ecartes:
                # TRANSLATORS: "st" = subtitle track(s) left out; keep it short.
                container += f"  −{ecartes} " + _("st")

            # Estimation taille de sortie — un seul stat() par fichier,
            # réutilisé pour la ligne ET les totaux du summary
            try:
                src_bytes = info.taille
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
                estim_txt = cellule("—", style="dim")
            elif src_bytes > 0:
                delta_pct = (est_bytes - src_bytes) * 100 / src_bytes
                sign      = "+" if delta_pct > 0 else ""
                # Une sortie plus grosse que la source est une anomalie ;
                # une sortie plus petite est le résultat attendu, elle n'a
                # rien à signaler. Le vert reste réservé au sans réencodage.
                color     = STYLE_PAR_EMPHASE[
                    Emphase.ALERTE if delta_pct > 0 else Emphase.ORDINAIRE]
                estim_txt = Text(
                    f"{fmt_bytes(est_bytes)} ({sign}{delta_pct:.0f}%)",
                    style=color, no_wrap=True,
                )
            else:
                estim_txt = cellule(fmt_bytes(est_bytes))

            # Estimation temps d'encodage
            prof = self._app.profiles.get(self._app.active_profile_id)
            preset = prof.data.get("preset_encoder", "medium") if prof else "medium"
            measured_speed = get_measured_speed(self._app.cfg, vid.action)
            est_enc_duration = estimate_encoding_duration(
                info.duration, info.kbps * 1000, vid.target_bitrate,
                vid.action, preset, measured_speed
            )
            temps_txt = Text(fmt_duration(est_enc_duration), no_wrap=True,
                             overflow="ellipsis",
                             style="dim" if vid.action == VideoAction.SKIP else "")

            check_str = Text("[x]", no_wrap=True) if idx in self._selected else Text("[ ]", no_wrap=True)
            table.add_row(
                check_str,
                cellule(info.path.name),
                cellule(fmt_bytes(src_bytes) if src_bytes else "—", style="dim"),
                Text(fmt_duration(info.duration), style="dim", no_wrap=True,
                     overflow="ellipsis"),
                estim_txt,
                temps_txt,
                cellule(vid.label(), style=vid.style()),
                Text(container, no_wrap=True,
                     style=STYLE_PAR_EMPHASE[Emphase.MODIFIEE] if ecartes else ""),
                cellule(dv_str),
                cellule(bitrate_str),
                cellule(res_str),
                cellule("  |  ".join(audio_parts) or "—"),
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
        dv     = counts[VideoAction.ENCODE_DV]

        total_src, total_est = self._totals
        gain_str = ""
        if total_src > 0 and total_est > 0:
            delta_pct = (total_est - total_src) * 100 / total_src
            sign      = "+" if delta_pct > 0 else ""
            gain_str  = (
                "  ·  " + _("Source: {size}").format(size=fmt_bytes(total_src)) + "  →  "
                + _("Estimated: {size}").format(size=fmt_bytes(total_est))
                + f" ({sign}{delta_pct:.0f}%)"
            )

        av1_str   = f"  ·  AV1 {av1}" if av1 else ""
        dv_str    = f"  ·  HEVC+DV {dv}" if dv else ""
        strip_str = f"  ·  DV→HDR10 {strip}" if strip else ""
        self.query_one("#status-bar", Static).update(barre_etat(
            _("Dry run"), ngettext("{count} file selected", "{count} files selected",
                                   total).format(count=total),
            _("Col: {column}").format(column=self.resize_col_label) + "  </>",
        ))
        self.query_one("#dryrun-summary", Static).update(
            " " + _("To encode: {counts}").format(
                counts=f"HEVC {hevc}  ·  H264 {h264}{av1_str}{dv_str}{strip_str}"
                       f"  ·  SKIP {skip}") + gain_str
        )

    # ── Resize colonnes (ColumnResizeMixin) ───────────────────────────────────

    def _largeur_fichier(self, widths: dict[str, int]) -> int:
        """Fichier prend la place que les autres laissent, comme sur l'accueil."""
        reglee = (self._app.cfg.get("tui", {}).get("dryrun", {})
                  .get("columns", {}).get("fichier"))
        if reglee:
            return self.resize_largeur("fichier", reglee)
        return self.resize_remplissage("fichier", widths, widths["fichier"])

    def _resize_widths(self) -> dict[str, int]:
        widths = cfg_mod.get_dryrun_column_widths(self._app.cfg)
        return {**widths, "fichier": self._largeur_fichier(widths)}

    def _resize_persist(self, key: str, width: int) -> None:
        cfg_mod.set_dryrun_column_width(self._app.cfg, key, width)
        sauver_config(self.app)

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
        if new_action == dec.video.action:
            return
        dec.video = dc_replace(
            choisir_codec(dec, new_action),
            reason         = _("Chosen in the dry run"),
        )

    def _apply_bitrate(self, dec: FileDecision, new_bitrate_bps: int) -> None:
        from dataclasses import replace as dc_replace
        if dec.video.action == VideoAction.SKIP:
            return
        dec.video = dc_replace(
            dec.video,
            target_bitrate = new_bitrate_bps,
            reason         = _("Bitrate chosen in the dry run"),
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
        self.app.push_screen(
            ValuePickerScreen(_("Codec"), codec_picker_opts(self._app.platform),
                              current),
            _on_pick)

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
            # Rien à lancer : le dire (UX-17). Une ligne SKIP s'encode après
            # un changement de codec, F6.
            self.notify(
                _("Nothing to encode: no kept line needs re-encoding — {space} "
                  "keeps a line, {codec_key} changes the codec of a SKIP "
                  "line.").format(space=touche("space"), codec_key=touche("f6")),
                severity="warning", timeout=4)
            return
        confier_a_la_file(self.app, to_encode)

    def action_accueil(self) -> None:
        """Retour au choix du fichier, sans repasser par les écrans intermédiaires."""
        retour_accueil(self.app)
