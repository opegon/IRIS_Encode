"""
tui/widgets/profile_form.py — Formulaire CRUD profil d'encodage.

Layout compact 2 colonnes : chaque ligne contient 2 paramètres côte à côte.
Contrôles : Ctrl+S → enregistrer  |  Esc → annuler
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Checkbox, Input, Label, Select, Static


# ─── Messages ─────────────────────────────────────────────────────────────────

class ProfileSaved(Message):
    def __init__(self, profile_id: str, data: dict[str, Any]) -> None:
        super().__init__()
        self.profile_id = profile_id
        self.data       = data


class ProfileCancelled(Message):
    pass


# ─── Options des champs ───────────────────────────────────────────────────────

_BITRATE_720P  = [("1500k", 1500), ("2000k", 2000)]
_BITRATE_1080P = [("2000k", 2000), ("2200k", 2200), ("2500k", 2500),
                  ("3000k", 3000), ("3500k", 3500), ("5000k", 5000)]
_BITRATE_4K    = [("3000k", 3000), ("5000k", 5000),
                  ("8000k ⚠ recommandé", 8000), ("12000k", 12000)]
_DV_OPTIONS    = [("hdr10", "hdr10"), ("dv", "dv"), ("sdr", "sdr")]
_HDR10_QUALITY = [("compat (NVENC, rapide)", "compat"),
                  ("quality (CPU x265, TV-grade)", "quality")]
_PRESET        = [("fast", "fast"), ("medium", "medium"), ("slow", "slow")]
_BR_STEREO     = [("96k", 96), ("128k", 128), ("192k", 192), ("320k", 320)]
_BR_SURROUND   = [("320k", 320), ("448k", 448), ("640k", 640)]
_BR_71         = [("448k", 448), ("640k", 640), ("768k", 768)]
_HD_CODEC      = [("none (forfait ci-dessus)", "none"),
                  ("ac3 (max 640k)",           "ac3"),
                  ("eac3 (max 6144k)",         "eac3")]


def _opts(pairs):
    return [(label, val) for label, val in pairs]


# ─── Widget formulaire ────────────────────────────────────────────────────────

class ProfileForm(Widget):
    """
    Formulaire compact 2 colonnes.
    Ctrl+S → ProfileSaved   |   Esc → ProfileCancelled
    """

    DEFAULT_CSS = """
    ProfileForm {
        height: auto;
        padding: 0 1;
    }
    /* Ligne de section */
    ProfileForm .section-hdr {
        color: $accent;
        text-style: bold;
        margin-top: 1;
        height: 1;
    }
    /* Ligne de champs (2 colonnes) */
    ProfileForm .form-row {
        layout: horizontal;
        height: auto;
        margin-bottom: 0;
    }
    /* Cellule = label + contrôle */
    ProfileForm .form-cell {
        layout: horizontal;
        width: 1fr;
        height: auto;
        padding-right: 2;
    }
    ProfileForm .form-lbl {
        width: 20;
        padding-top: 1;
        color: $text-muted;
    }
    ProfileForm .form-ctrl {
        width: 1fr;
    }
    /* Ligne de cases à cocher */
    ProfileForm .check-row {
        layout: horizontal;
        height: auto;
        margin-top: 0;
    }
    ProfileForm .check-row Checkbox {
        width: 1fr;
        margin-right: 2;
    }
    ProfileForm .form-hint {
        color: $accent;
        margin-top: 1;
        height: 1;
    }
    ProfileForm .form-error {
        color: $warning;
        height: auto;
    }
    """

    def __init__(self, *, name=None, id=None, classes=None, disabled=False):
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._profile_id = ""
        self._is_new     = True
        self._is_builtin = False

    # ── Composition ───────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        # ── Identifiant ───────────────────────────────────────────────────────
        yield Static("── Identifiant", classes="section-hdr")
        with Widget(classes="form-row"):
            with Widget(classes="form-cell"):
                yield Label("id",          classes="form-lbl")
                yield Input(placeholder="mon_profil", id="field-id",
                            classes="form-ctrl")
            with Widget(classes="form-cell"):
                pass   # colonne droite vide

        # ── Vidéo ─────────────────────────────────────────────────────────────
        yield Static("── Vidéo", classes="section-hdr")

        with Widget(classes="form-row"):
            with Widget(classes="form-cell"):
                yield Label("720p kbps",   classes="form-lbl")
                yield Select(_opts(_BITRATE_720P),  id="field-720p",   classes="form-ctrl")
            with Widget(classes="form-cell"):
                yield Label("1080p kbps",  classes="form-lbl")
                yield Select(_opts(_BITRATE_1080P), id="field-1080p",  classes="form-ctrl")

        with Widget(classes="form-row"):
            with Widget(classes="form-cell"):
                yield Label("4K kbps",     classes="form-lbl")
                yield Select(_opts(_BITRATE_4K),    id="field-4k",     classes="form-ctrl")
            with Widget(classes="form-cell"):
                yield Label("Dolby Vision",classes="form-lbl")
                yield Select(_opts(_DV_OPTIONS),    id="field-dv",     classes="form-ctrl")

        with Widget(classes="form-row"):
            with Widget(classes="form-cell"):
                yield Label("Preset",      classes="form-lbl")
                yield Select(_opts(_PRESET),        id="field-preset", classes="form-ctrl")
            with Widget(classes="form-cell"):
                yield Label("HDR10 mode",  classes="form-lbl")
                yield Select(_opts(_HDR10_QUALITY), id="field-hdr10q", classes="form-ctrl")

        with Widget(classes="check-row"):
            yield Checkbox("keep_4k",       id="field-keep4k")
            yield Checkbox("delete_source", id="field-delsrc")

        # ── Audio ─────────────────────────────────────────────────────────────
        yield Static("── Audio", classes="section-hdr")

        with Widget(classes="form-row"):
            with Widget(classes="form-cell"):
                yield Label("Langues",     classes="form-lbl")
                yield Input(placeholder="fre, eng", id="field-langs", classes="form-ctrl")
            with Widget(classes="form-cell"):
                pass

        with Widget(classes="form-row"):
            with Widget(classes="form-cell"):
                yield Label("Stéréo kbps", classes="form-lbl")
                yield Select(_opts(_BR_STEREO),  id="field-stereo", classes="form-ctrl")
            with Widget(classes="form-cell"):
                yield Label("5.1 kbps",    classes="form-lbl")
                yield Select(_opts(_BR_SURROUND),id="field-51",     classes="form-ctrl")

        with Widget(classes="form-row"):
            with Widget(classes="form-cell"):
                yield Label("7.1 kbps",    classes="form-lbl")
                yield Select(_opts(_BR_71),      id="field-71",     classes="form-ctrl")
            with Widget(classes="form-cell"):
                yield Label("TrueHD/DTS → débit source", classes="form-lbl")
                yield Select(_opts(_HD_CODEC),   id="field-hdcodec", classes="form-ctrl")

        with Widget(classes="check-row"):
            yield Checkbox("preserve_hd_audio (TrueHD/DTS-HD → copy)", id="field-hd")
            yield Checkbox("audio_copy_compatible (AAC/AC3 → copy)",    id="field-copy-compat")

        # ── Pied ──────────────────────────────────────────────────────────────
        yield Static(
            "  Tab / Shift+Tab : champ suiv./préc.    "
            "Enter : ouvrir une liste    +/- : valeur suiv./préc.    "
            "Ctrl+S : enregistrer    Esc : annuler",
            classes="form-hint",
        )
        yield Static("", id="form-error", classes="form-error")

    # ── Chargement / Dump ─────────────────────────────────────────────────────

    def load(self, profile_id: str, data: dict[str, Any],
             is_new: bool = False, is_builtin: bool = False) -> None:
        self._profile_id = profile_id
        self._is_new     = is_new
        self._is_builtin = is_builtin

        def _set_sel(wid: str, val: Any) -> None:
            try:
                self.query_one(wid, Select).value = val
            except Exception:
                pass

        def _set_inp(wid: str, val: str) -> None:
            try:
                self.query_one(wid, Input).value = val
            except Exception:
                pass

        def _set_chk(wid: str, val: bool) -> None:
            try:
                self.query_one(wid, Checkbox).value = val
            except Exception:
                pass

        _set_inp("#field-id",     "" if is_new else profile_id)
        _set_sel("#field-720p",   data.get("bitrate_720p_kbps",       1500))
        _set_sel("#field-1080p",  data.get("bitrate_1080p_kbps",      2500))
        _set_sel("#field-4k",     data.get("bitrate_4k_kbps",         5000))
        _set_sel("#field-dv",     data.get("dolby_vision",        "hdr10"))
        _set_sel("#field-preset", data.get("preset_encoder",    "medium"))
        _set_sel("#field-hdr10q", data.get("hdr10_quality",     "compat"))
        _set_chk("#field-keep4k", data.get("keep_4k",                False))
        _set_chk("#field-delsrc", data.get("delete_source",          False))
        _set_inp("#field-langs",
                 ", ".join(data.get("audio_languages", ["fre", "eng"])))
        _set_sel("#field-stereo", data.get("audio_stereo_kbps",        192))
        _set_sel("#field-51",     data.get("audio_surround_kbps",      448))
        _set_sel("#field-71",     data.get("audio_surround_7_1_kbps",  640))
        _set_sel("#field-hdcodec", data.get("audio_hd_codec",        "none"))
        _set_chk("#field-hd",         data.get("preserve_hd_audio",   False))
        _set_chk("#field-copy-compat",data.get("audio_copy_compatible", True))

        id_field = self.query_one("#field-id", Input)
        id_field.disabled = is_builtin and not is_new

    def dump(self) -> dict[str, Any]:
        def _g_sel(wid: str, default: Any) -> Any:
            try:
                v = self.query_one(wid, Select).value
                return v if v is not Select.BLANK else default
            except Exception:
                return default

        def _g_inp(wid: str, default: str = "") -> str:
            try:
                return self.query_one(wid, Input).value.strip()
            except Exception:
                return default

        def _g_chk(wid: str) -> bool:
            try:
                return bool(self.query_one(wid, Checkbox).value)
            except Exception:
                return False

        langs_raw = _g_inp("#field-langs", "fre, eng")
        langs = [l.strip() for l in langs_raw.replace(";", ",").split(",") if l.strip()]
        if not langs:
            langs = ["fre", "eng"]

        return {
            "bitrate_720p_kbps":       _g_sel("#field-720p",   1500),
            "bitrate_1080p_kbps":      _g_sel("#field-1080p",  2500),
            "bitrate_4k_kbps":         _g_sel("#field-4k",     5000),
            "dolby_vision":            _g_sel("#field-dv",  "hdr10"),
            "preset_encoder":          _g_sel("#field-preset","medium"),
            "hdr10_quality":           _g_sel("#field-hdr10q","compat"),
            "keep_4k":                 _g_chk("#field-keep4k"),
            "delete_source":           _g_chk("#field-delsrc"),
            "audio_languages":         langs,
            "audio_stereo_kbps":       _g_sel("#field-stereo",  192),
            "audio_surround_kbps":     _g_sel("#field-51",      448),
            "audio_surround_7_1_kbps": _g_sel("#field-71",      640),
            "audio_hd_codec":          _g_sel("#field-hdcodec","none"),
            "preserve_hd_audio":       _g_chk("#field-hd"),
            "audio_copy_compatible":   _g_chk("#field-copy-compat"),
        }

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self._is_new:
            pid = self.query_one("#field-id", Input).value.strip()
            if not pid:
                errors.append("L'identifiant ne peut pas être vide.")
            elif not all(c.isalnum() or c in "-_" for c in pid):
                errors.append("Identifiant : caractères autorisés a-z, 0-9, - _")
            elif len(pid) > 32:
                errors.append("Identifiant : 32 caractères maximum.")
        return errors

    # ── Clavier ───────────────────────────────────────────────────────────────

    # Mapping champ → liste d'options (pour le cycling +/-)
    _SELECT_OPTS: dict[str, list] = {
        "#field-720p":   _BITRATE_720P,
        "#field-1080p":  _BITRATE_1080P,
        "#field-4k":     _BITRATE_4K,
        "#field-dv":     _DV_OPTIONS,
        "#field-preset": _PRESET,
        "#field-hdr10q": _HDR10_QUALITY,
        "#field-stereo": _BR_STEREO,
        "#field-51":     _BR_SURROUND,
        "#field-71":     _BR_71,
        "#field-hdcodec": _HD_CODEC,
    }

    def _cycle_focused_select(self, delta: int) -> bool:
        """Cycle la valeur du Select focalisé. Retourne True si géré."""
        focused = self.app.focused
        if not isinstance(focused, Select):
            return False
        for field_id, opts in self._SELECT_OPTS.items():
            try:
                widget = self.query_one(field_id, Select)
            except Exception:
                continue
            if widget is not focused:
                continue
            vals = [v for _, v in opts]
            cur  = widget.value
            if cur in vals:
                widget.value = vals[(vals.index(cur) + delta) % len(vals)]
            elif vals:
                widget.value = vals[0]
            return True
        return False

    def on_key(self, event) -> None:
        if event.key == "ctrl+s":
            event.stop()
            errors = self.validate()
            if errors:
                try:
                    self.query_one("#form-error", Static).update("\n".join(errors))
                except Exception:
                    pass
                return
            profile_id = (
                self.query_one("#field-id", Input).value.strip()
                if self._is_new else self._profile_id
            )
            self.post_message(ProfileSaved(profile_id, self.dump()))
        elif event.key == "escape":
            event.stop()
            self.post_message(ProfileCancelled())
        elif event.key in ("+", "-"):
            if self._cycle_focused_select(1 if event.key == "+" else -1):
                event.stop()
