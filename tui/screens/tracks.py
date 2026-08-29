"""
tui/screens/tracks.py — Sélection pistes + édition décision vidéo.

Un seul DataTable avec trois sections :
  ── VIDÉO ──────  (1 ligne éditable : action / débit / DV / original)
  ── AUDIO ──────  (pistes sélectionnables)
  ── SOUS-TITRES ─ (pistes sélectionnables)

Quand le curseur est sur la ligne vidéo :
  ←/→   cycle entre les champs éditables
  +/-   change la valeur du champ actif
  ↵     ouvre le picker du champ actif

Quand le curseur est sur une piste audio/sous-titre :
  Espace   toggle sélection
  ↵        valider la sélection

F1/F2 → lancer directement  |  ⌫/Esc → annuler
Tab/Shift+Tab → colonne suivante/précédente  |  < / > → rétrécir/élargir
"""
from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.events import Key
from textual.screen import Screen
from textual.widgets import DataTable, Static

import core.config as cfg_mod
from core import dovi
from core.muxer import TrackKind
from core.decision import (
    Emphase,
    STYLE_PAR_EMPHASE,
    style_dv,
    style_video,
    ACTION_CYCLE as _ACTION_CYCLE,
    cycle_index,
    same_intent,
    BITRATE_OPTS_KBPS as _BITRATE_OPTS,
    AudioAction, DVAction, FileDecision, TracksSelection,
    VideoAction, VideoOverride, decide_audio, decide_video,
)
from ..common import (
    ECARTEE,
    actions_ecran,
    retour_accueil,
    raccourcis,
    cellule,
    codec_picker_opts,
    bitrate_picker_config,
    footer_line2,
)
from ..mixins import ColumnResizeMixin, TableNavMixin
from ..widgets.entete import Entete
from ..widgets.footer import KeyFooter
from .value_picker import ValuePickerScreen

# Les intitulés de section vivaient dans la colonne « Piste », large de dix :
# « ── SOUS-TITRES ───── » y devenait « ── SOUS-TI », coupé au milieu d'un mot.
# Le trait décoratif part donc dans les autres cellules — la ligne se lit comme
# une règle en travers de la table — et la colonne prend la largeur du plus long
# intitulé, jamais moins.
SECTIONS: tuple[str, ...] = ("VIDÉO", "AUDIO", "SOUS-TITRES", "EXTERNES")
_W_IDX: int = max(10, *(len(s) for s in SECTIONS))


# ── Types de lignes ───────────────────────────────────────────────────────────
_ROW_VIDEO    = "video"
_ROW_AUDIO    = "audio"
_ROW_SUBTITLE = "subtitle"
_ROW_EXTERNAL = "external"
_ROW_SECTION  = "section"

# Champs éditables (vidéo)
_EDIT_FIELDS = ["action", "bitrate", "dv", "orig"]

_DV_CYCLE     = [DVAction.HDR10, DVAction.DV, DVAction.SDR]

# Libellés courts seulement : les couleurs viennent de la table unique de
# core.decision, sans quoi la même décision porte deux teintes selon l'écran.
_ACTION_SHORT: dict[VideoAction, str] = {
    VideoAction.ENCODE_HEVC: "HEVC",
    VideoAction.ENCODE_H264: "H264",
    VideoAction.ENCODE_AV1:  "AV1 ⚠",
    VideoAction.STRIP_DV:    "HDR10",   # retrait du RPU, sans réencodage
    VideoAction.SKIP:        "SKIP",
}
_DV_SHORT: dict[DVAction, str] = {
    DVAction.NONE:   "—",
    DVAction.HDR10:  "HDR10",
    DVAction.DV:     "DV",
    DVAction.SDR:    "SDR ⚠",
}

# Hints contextuels affichés dans la barre du bas selon la ligne courante
_HINT_VIDEO = raccourcis([("←/→", "Champ"), ("+/-", "Valeur"),
                          ("enter", "Liste de choix"),
                          ("enter", "sur une piste : Valider")])
_HINT_TRACK = raccourcis([("space", "Sélectionner / désélectionner"),
                          ("enter", "Valider la sélection")])


class TracksScreen(TableNavMixin, ColumnResizeMixin, Screen["TracksSelection | None"]):

    BINDINGS = [
        Binding("space",     "toggle_row",    "Sélect",               show=True),
        Binding("left",      "field_prev",    "Champ préc.",          show=False),
        Binding("right",     "field_next",    "Champ suiv.",          show=False),
        Binding("+",         "val_up",        "Valeur suiv.",         show=False),
        Binding("-",         "val_down",      "Valeur préc.",         show=False),
        Binding("enter",     "enter_action",  "Valider",              show=True, priority=True),
        Binding("f1",        "dryrun",        "Dry-run",              show=True),
        Binding("f2",        "run",           "Run",                  show=True),
        Binding("f4",        "change_profile","Profil",               show=True),
        Binding("f6",        "open_codec",    "Codec",                show=True),
        Binding("f7",        "open_bitrate",  "Débit",                show=True),
        Binding("f8",        "toggle_delete", "Suppr./garder source", show=True),
        Binding("f9",        "add_external",  "Piste externe",        show=True),
        Binding("backspace", "dismiss_cancel","Retour",               show=True),
        Binding("escape",    "dismiss_cancel","Retour",               show=False, priority=True),
        # `priority` : un DataTable etouffe la touche avant les bindings —
        # meme avertissement qu'en tete de tui/mixins.py.
        Binding("ctrl+home", "accueil",   "Accueil",       show=True,
                priority=True),
    ]

    # Colonnes redimensionnables (ColumnResizeMixin)
    RESIZE_COLS   = ["codec", "fmt", "src", "titre"]
    RESIZE_LABELS = {"codec": "Codec", "fmt": "Format", "src": "Source",
                     "titre": "Titre"}
    RESIZE_FIXE   = 26   # case (7) + Piste (_W_IDX) + Langue (8), hors cycle

    DEFAULT_CSS = """
    TracksScreen { layout: vertical; }
    #tracks-table { height: 1fr; }
    #hint-bar {
        height: 1;
        background: $primary-darken-1;
        color: $text;
        padding: 0 2;
        border-top: solid $primary;
    }
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

    def _eff_action(self)  -> VideoAction:
        return self._ov_action  if self._ov_action  is not None else self._decision.video.action
    def _eff_bitrate(self) -> int:
        return self._ov_bitrate if self._ov_bitrate is not None else self._decision.video.target_bitrate
    def _eff_dv(self)      -> DVAction:
        return self._ov_dv      if self._ov_dv      is not None else self._decision.video.dv_action
    def _eff_delete(self)  -> bool:
        if self._ov_delete is not None:
            return self._ov_delete
        return self._decision.profile.data.get("delete_source", False)

    def _dovi_available(self) -> bool:
        """True si dovi_tool est trouvé (PATH ou ./bin/)."""
        return dovi.is_available(cfg_mod.get_bin_dir(self.app.cfg))  # type: ignore[attr-defined]

    def _has_override(self) -> bool:
        return any(x is not None for x in (self._ov_action, self._ov_bitrate, self._ov_dv, self._ov_delete))

    # ── Composition ───────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Entete()
        yield Static("", id="status-bar", classes="status-bar", markup=False)
        yield DataTable(id="tracks-table", cursor_type="row",
                        zebra_stripes=False, show_header=True)
        yield Static(_HINT_TRACK, id="hint-bar")
        yield KeyFooter(
            actions=actions_ecran(self),
            nav=footer_line2(back=True, nav=True, resize=True, accueil=True),
        )

    def on_mount(self) -> None:
        self._init_selection()
        self._build_table()
        self._update_status()
        self.query_one(DataTable).focus()

    # ── Construction table ────────────────────────────────────────────────────

    def _ligne_section(self, table, titre: str, cle: str) -> None:
        """Une règle en travers de la table, l'intitulé lisible en entier.

        Chaque cellule porte le trait sur sa propre largeur ; l'intitulé occupe
        la colonne « Piste », dimensionnée pour lui (`_W_IDX`). Un DataTable ne
        sait pas fusionner de cellules — c'est la seule façon d'obtenir une
        règle qui traverse sans couper le titre.
        """
        w    = self._resize_widths()
        _min = self.RESIZE_MIN_DEFAULT
        # « Décision / Cible » s'ajuste à son contenu : le trait n'a pas de
        # largeur à suivre, il prend celle du plus long libellé qu'on y écrit.
        largeurs = [7, _W_IDX, max(_min, w["codec"]), max(_min, w["fmt"]), 8,
                    max(_min, w["src"]), max(_min, w["titre"]), 24]
        cells = [Text(titre, style="bold dim") if i == 1
                 else Text("─" * n, style="dim")
                 for i, n in enumerate(largeurs)]
        table.add_row(*cells, key=cle)
        self._rows.append((_ROW_SECTION, -1))

    def _build_table(self, keep_cursor: bool = False) -> None:
        table      = self.query_one(DataTable)
        cursor_row = table.cursor_row if keep_cursor else 0
        table.clear(columns=True)

        widths = cfg_mod.get_tracks_column_widths(self.app.cfg)  # type: ignore[attr-defined]
        _min   = self.RESIZE_MIN_DEFAULT

        table.add_column("",                          width=7,                          key="check")
        table.add_column("Piste",                     width=_W_IDX,                     key="idx")
        table.add_column(self.resize_header("codec"), width=max(_min, widths["codec"]), key="codec")
        table.add_column(self.resize_header("fmt"),   width=max(_min, widths["fmt"]),   key="fmt")
        table.add_column("Langue",                    width=8,                          key="lang")
        # « Source » portait deux sens : le motif de sélection pour l'audio
        # (« défaut », « sélectionné ») et le titre déclaré pour les
        # sous-titres (« QoQ-Team »). Les deux comptent — ce sont deux
        # colonnes, pas deux usages d'une seule.
        table.add_column(self.resize_header("src"),   width=max(_min, widths["src"]),   key="src")
        table.add_column(self.resize_header("titre"), width=max(_min, widths["titre"]), key="titre")
        table.add_column("Décision / Cible",          width=None,                       key="dec")
        self._rows = []

        # ── Section VIDÉO ─────────────────────────────────────────────────────
        self._ligne_section(table, "VIDÉO", "__sec_video__")
        self._add_video_row(table)

        # ── Section AUDIO ─────────────────────────────────────────────────────
        self._ligne_section(table, "AUDIO", "__sec_audio__")
        for ad in self._decision.audio:
            t   = ad.track
            idx = t.index
            excl = ad.action == AudioAction.EXCLUDE
            dim  = "dim" if excl else ""
            lock = " ⚑" if idx == 0 else ""

            # Raison simplifiée pour l'affichage
            if excl:
                reason = "exclu manuellement"
            elif idx == 0:
                reason = "défaut"
            else:
                reason = "sélectionné"

            table.add_row(
                self._check_text(_ROW_AUDIO, idx),
                cellule(f"0:a:{idx}{lock}",   style=dim),
                cellule(t.codec,              style=dim),
                cellule(t.channel_layout,     style=dim),
                cellule(t.language or "?",    style=dim),
                cellule(reason,               style=dim),
                cellule(t.title or "—",       style=dim),
                cellule(ad.display() or ECARTEE,
                        style="green" if not excl else "dim"),
                key=f"a:{idx}",
            )
            self._rows.append((_ROW_AUDIO, idx))

        # ── Section SOUS-TITRES ───────────────────────────────────────────────
        self._ligne_section(table, "SOUS-TITRES", "__sec_subs__")
        subs = self._decision.info.subtitle_tracks
        if not subs:
            table.add_row(
                Text(""), Text("  (aucun)", style="dim italic"),
                Text(""), Text(""), Text(""), Text(""), Text(""), Text(""),
                key="__no_subs__",
            )
            self._rows.append((_ROW_SECTION, -1))
        else:
            for st in subs:
                sel   = st.index in self._sel_subs
                style = "" if sel else "dim"
                type_str = "image" if st.is_image_based else "texte"
                cont_str = "→ MKV copy" if st.is_image_based else "→ MP4 copy"

                # Raison simplifiée pour l'affichage
                if sel:
                    reason = "défaut" if st.index == 0 else "sélectionné"
                else:
                    reason = "exclu manuellement"

                table.add_row(
                    self._check_text(_ROW_SUBTITLE, st.index),
                    cellule(f"0:s:{st.index}",  style=style),
                    cellule(st.codec,           style=style),
                    cellule(type_str,           style=style),
                    cellule(st.language or "?", style=style),
                    cellule(reason,             style=style),
                    cellule(st.title or "—",    style=style),
                    cellule(cont_str if sel else ECARTEE,
                            style="green" if sel else "dim"),
                    key=f"s:{st.index}",
                )
                self._rows.append((_ROW_SUBTITLE, st.index))

        # ── Section PISTES EXTERNES ───────────────────────────────────────────
        ext = self._decision.external_tracks
        if ext:
            self._ligne_section(table, "EXTERNES", "__sec_ext__")
            for i, et in enumerate(ext):
                kind = "audio" if et.kind == TrackKind.AUDIO else "sous-titre"
                table.add_row(
                    Text("  ✓  ", style="bold green"),
                    cellule(f"ext #{et.source_tid}"),
                    cellule(et.codec or kind),
                    cellule(et.sync_label()),
                    cellule(et.language or "?",
                            style="" if et.language else "bold dark_orange"),
                    cellule(et.source_path.name),
                    cellule(et.track_name or "—"),
                    cellule(f"→ greffe {kind}", style="green"),
                    key=f"e:{i}",
                )
                self._rows.append((_ROW_EXTERNAL, i))

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
        act_short = _ACTION_SHORT.get(action, "?")
        act_col   = style_video(action, dv)
        check_txt = Text(no_wrap=True)
        check_txt.append("✎ " if ovr else "  ",
                         style=STYLE_PAR_EMPHASE[Emphase.MODIFIEE] if ovr else "")
        check_txt.append(act_short, style=act_col)

        # Colonne "src" : infos source. Affiche le sous-profil DV si connu (8.1, 7.06…).
        if info.dv_subprofile:
            dv_src = f" DV:P{info.dv_subprofile}"
        elif info.dv_profile:
            dv_src = f" DV:P{info.dv_profile}"
        else:
            dv_src = ""
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
        dec_txt.append_text(_f("action", f"→ {act_short}", act_col))
        dec_txt.append("  ·  ")
        dec_txt.append_text(_f("bitrate", f"{bitrate//1000} kbps", ""))
        if action != VideoAction.SKIP:
            dec_txt.append(f"  ·  {vid.target_width}x{vid.target_height}")
            dec_txt.append(f"  ·  {self._decision.output_container.upper().lstrip('.')}")
        # Affichage DV : toujours visible
        dec_txt.append("  ·  ")
        if info.dv_profile is None:
            dec_txt.append_text(_f("dv", "DV - N/A", "dim"))
        else:
            dv_lbl = _DV_SHORT.get(dv, "—")
            dv_sty = style_dv(dv)
            dec_txt.append_text(_f("dv", f"DV → {dv_lbl}", dv_sty))
            # Avertissement si HDR10 demandé mais dovi_tool absent → qualité dégradée
            if dv == DVAction.HDR10 and not self._dovi_available():
                dec_txt.append("  ")
                dec_txt.append("⚠ dovi_tool absent", style="bold dark_orange")
        # Champ original
        if self._ov_delete is None:
            del_profile = self._decision.profile.data.get("delete_source", False)
            orig_lbl = ("⚠ supprimer" if del_profile else "○ garder") + " (profil)"
            orig_sty = "bold dark_orange" if del_profile else "green"
        elif del_src:
            orig_lbl, orig_sty = "⚠ SUPPRIMER", "bold dark_orange"
        else:
            orig_lbl, orig_sty = "○ GARDER", "bold green"
        dec_txt.append("  ·  ")
        dec_txt.append_text(_f("orig", orig_lbl, orig_sty))

        table.add_row(
            check_txt,
            cellule("0:v:0"),
            cellule(info.codec),
            cellule(f"{info.width}x{info.height}"),
            cellule("—"),
            src_txt,
            cellule("—", style="dim"),      # la vidéo n'a pas de titre de piste
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
        prof_id = self._decision.profile.id
        n_a     = len(self._sel_audio);  tot_a = len(self._decision.audio)
        n_s     = len(self._sel_subs);   tot_s = len(self._decision.info.subtitle_tracks)
        ovr_str = "  ·  ★ vidéo modifiée" if self._has_override() else ""
        self.query_one("#status-bar", Static).update(
            f" {fname}    "
            f"Profil : [{prof_id}]  ·  "
            f"Audio : {n_a}/{tot_a}  ·  "
            f"Sous-titres : {n_s}/{tot_s}"
            f"{ovr_str}"
            f"  ·  Col : {self.resize_col_label} [</>]"
        )

    def _update_hint_bar(self) -> None:
        """Aide contextuelle : contrôles d'édition sur la ligne vidéo, sélection sinon."""
        hint = _HINT_VIDEO if self._on_video_row() else _HINT_TRACK
        self.query_one("#hint-bar", Static).update(hint)

    @on(DataTable.RowHighlighted)
    def _on_row_highlight(self, _: DataTable.RowHighlighted) -> None:
        self._update_hint_bar()

    def _current_row(self) -> tuple[str, int] | None:
        row = self.query_one(DataTable).cursor_row
        if 0 <= row < len(self._rows):
            rt, idx = self._rows[row]
            if rt != _ROW_SECTION:
                return rt, idx
        return None

    def _make_selection(self) -> TracksSelection:
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
            video_override=ovr,
            subtitle_indices=sub_indices,
        )

    # ── Actions pistes ────────────────────────────────────────────────────────

    def on_key(self, event: Key) -> None:
        if self._on_video_row() and event.key in ("left", "right"):
            event.stop()
            if event.key == "left":
                self.action_field_prev()
            else:
                self.action_field_next()
            return
        # Laisse TableNavMixin gérer Home/End/PageUp/PageDown
        super().on_key(event)

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
            nxt  = _ACTION_CYCLE[(cycle_index(cur) + delta) % len(_ACTION_CYCLE)]
            self._ov_action = None if same_intent(nxt, self._decision.video.action) else nxt

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
        elif info is not None and info[0] == _ROW_EXTERNAL:
            self._open_sync()
        else:
            self.action_dismiss_ok()

    # ── Pistes externes ───────────────────────────────────────────────────────

    def action_add_external(self) -> None:
        """
        Greffe une piste venue d'un autre fichier : donneur → pistes → recalage.

        Les tid viennent de mkvmerge -J, jamais des index ffprobe affichés
        dans les sections AUDIO et SOUS-TITRES : les deux numérotations sont
        incompatibles.
        """
        if not getattr(self.app, "mkvmerge_available", False):
            self.app.bell()
            self.query_one("#hint-bar", Static).update(
                "mkvmerge absent — relancez le preflight pour l'installer."
            )
            return

        from .donor_picker import pick_external_tracks
        pick_external_tracks(self, self._decision, self._open_sync)

    def _open_sync(self) -> None:
        from .sync import SyncScreen
        before = self._decision.info.path

        def _back(_tracks) -> None:
            if self._decision.info.path != before:
                # Le mux a été adopté : la sélection portait sur l'ancien
                # fichier, dont la liste de pistes n'est plus celle-ci.
                self._sel_audio.clear()
                self._sel_subs.clear()
                self._init_selection()
            self._build_table(keep_cursor=True)
            self._update_status()

        self.app.push_screen(SyncScreen(self._decision), _back)

    def action_open_codec(self) -> None:
        """Ouvre le picker pour changer le codec."""
        self._edit_idx = _EDIT_FIELDS.index("action")
        self._open_picker()

    def action_open_bitrate(self) -> None:
        """Ouvre le picker pour changer le débit."""
        self._edit_idx = _EDIT_FIELDS.index("bitrate")
        self._open_picker()

    def action_toggle_delete(self) -> None:
        """Toggle suppression/conservation des fichiers originaux."""
        profile_val = self._decision.profile.data.get("delete_source", False)
        self._ov_delete = None if self._ov_delete is not None else not profile_val
        self._update_video_row()
        self._update_status()

    def _open_picker(self) -> None:
        field       = _EDIT_FIELDS[self._edit_idx]
        profile_del = self._decision.profile.data.get("delete_source", False)

        cfg: tuple[str, list[str], int, object] | None = None

        if field == "action":
            current = cycle_index(self._eff_action())
            def apply_action(idx, s=self):
                if idx is None: return
                nxt = _ACTION_CYCLE[idx]
                s._ov_action = (None if same_intent(nxt, s._decision.video.action)
                                else nxt)
                if nxt == VideoAction.ENCODE_AV1 and s._ov_bitrate is None:
                    s._ov_bitrate = 1500 * 1000
                s._update_video_row(); s._update_status()
            cfg = ("Codec", codec_picker_opts(getattr(self.app, "platform", None)),
                   current, apply_action)

        elif field == "bitrate":
            title_b, opts, current, blist = bitrate_picker_config(
                self._eff_action(), self._eff_bitrate()
            )
            def apply_bitrate(idx, s=self, bl=blist):
                if idx is None: return
                nxt = bl[idx] * 1000
                s._ov_bitrate = nxt if nxt != s._decision.video.target_bitrate else None
                s._update_video_row(); s._update_status()
            cfg = (title_b, opts, current, apply_bitrate)

        elif field == "dv":
            if self._eff_dv() == DVAction.NONE: return
            opts    = [_DV_SHORT[d] for d in _DV_CYCLE]
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

    def action_dismiss_ok(self) -> None:
        self.dismiss(self._make_selection())

    def action_change_profile(self) -> None:
        """Ouvre le sélecteur de profils (même table que l'écran d'accueil)."""
        from .profile_picker import ProfilePickerScreen
        profiles = self.app.profiles  # type: ignore[attr-defined]

        def _on_pick(pid: str | None) -> None:
            if pid is None:
                return
            new_profile = profiles[pid]
            self._decision.profile = new_profile
            self._decision.video = decide_video(self._decision.info, new_profile)
            self._decision.audio = decide_audio(self._decision.info, new_profile)
            self._build_table()
            self._update_status()

        self.app.push_screen(
            ProfilePickerScreen(profiles, self._decision.profile.id),
            _on_pick,
        )

    def action_dryrun(self) -> None:
        sel = self._make_selection()
        sel.launch_mode = "dryrun"
        self.dismiss(sel)

    def action_run(self) -> None:
        sel = self._make_selection()
        sel.launch_mode = "run"
        self.dismiss(sel)

    def action_dismiss_cancel(self) -> None:
        self.dismiss(None)

    # ── Resize colonnes (ColumnResizeMixin) ───────────────────────────────────

    def _resize_widths(self) -> dict[str, int]:
        return cfg_mod.get_tracks_column_widths(self.app.cfg)  # type: ignore[attr-defined]

    def _resize_persist(self, key: str, width: int) -> None:
        cfg_mod.set_tracks_column_width(self.app.cfg, key, width)  # type: ignore[attr-defined]
        cfg_mod.save(self.app.cfg)  # type: ignore[attr-defined]

    def _resize_rebuild(self) -> None:
        self._build_table(keep_cursor=True)
        self._update_status()

    def action_accueil(self) -> None:
        """Retour à l'accueil — mais pas au prix d'un travail non validé.

        Cet écran porte des pistes greffées et leur recalage, que le dépilage
        ne rend à personne. Une mesure prend des minutes ; un raccourci en
        prend deux touches. La confirmation existe pour cet écart.
        """
        from .confirm import ConfirmModal

        def _apres(ok) -> None:
            if ok:
                retour_accueil(self.app)

        self.app.push_screen(ConfirmModal(
            "Revenir à l'accueil ?",
            "Les pistes sélectionnées et le codec choisi seront perdus.",
            confirm_label="Revenir", cancel_label="Rester", danger=True), _apres)
