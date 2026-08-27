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
# Audio sans perte : un seul choix à quatre branches, là où deux réglages
# indépendants (preserve_hd_audio et audio_hd_codec) pouvaient se contredire
# en silence — l'un l'emportait sans que rien ne l'indique à l'écran.
# Les valeurs sont des couples (preserve_hd_audio, audio_hd_codec).
_HD_AUDIO = [
    ("copier telles quelles",              "copy"),
    ("→ E-AC3 au débit de la source",      "eac3"),
    ("→ AC3 au débit de la source",        "ac3"),
    ("→ forfait 5.1 / 7.1 ci-dessous",     "forfait"),
]

_HD_AUDIO_VERS_CLES: dict[str, tuple[bool, str]] = {
    "copy":    (True,  "none"),
    "eac3":    (False, "eac3"),
    "ac3":     (False, "ac3"),
    "forfait": (False, "none"),
}


def _hd_audio_depuis_cles(preserve: bool, codec: str) -> str:
    """Retrouve la branche à afficher depuis le couple stocké.

    Un profil écrit avant cet écran peut porter une combinaison
    contradictoire — `preserve_hd_audio = true` avec un codec renseigné. La
    copie l'emporte dans le moteur : c'est donc elle qu'on affiche, pour que
    l'écran dise ce qui se passe et non ce qui était souhaité.
    """
    if preserve:
        return "copy"
    return codec if codec in ("ac3", "eac3") else "forfait"


def _hd_audio_cles(branche: str) -> dict[str, Any]:
    """Couple (preserve_hd_audio, audio_hd_codec) écrit pour une branche."""
    preserve, codec = _HD_AUDIO_VERS_CLES.get(branche, (False, "none"))
    return {"preserve_hd_audio": preserve, "audio_hd_codec": codec}


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
    /* Conséquence d'un réglage : ce que la valeur choisie implique */
    ProfileForm .consequence {
        color: $text-muted;
        height: auto;
        margin-bottom: 1;
        padding-left: 2;
    }
    ProfileForm .consequence-warn {
        color: $warning;
        height: auto;
        margin-bottom: 1;
        padding-left: 2;
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

        # ── Quand réencoder ───────────────────────────────────────────────────
        yield Static("── QUAND RÉENCODER", classes="section-hdr")

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
                yield Checkbox("garder la 4K (sinon → 1080p)", id="field-keep4k")

        yield Static("", id="cons-seuils", classes="consequence")

        # ── Comment encoder ───────────────────────────────────────────────────
        yield Static("── COMMENT ENCODER", classes="section-hdr")

        with Widget(classes="form-row"):
            with Widget(classes="form-cell"):
                yield Label("preset",      classes="form-lbl")
                yield Select(_opts(_PRESET),        id="field-preset", classes="form-ctrl")
            with Widget(classes="form-cell"):
                pass

        yield Static("", id="cons-preset", classes="consequence")

        # ── Dolby Vision ──────────────────────────────────────────────────────
        yield Static("── DOLBY VISION", classes="section-hdr")

        with Widget(classes="form-row"):
            with Widget(classes="form-cell"):
                yield Label("traitement",  classes="form-lbl")
                yield Select(_opts(_DV_OPTIONS),    id="field-dv",     classes="form-ctrl")
            with Widget(classes="form-cell"):
                yield Label("mode HDR10",  classes="form-lbl")
                yield Select(_opts(_HDR10_QUALITY), id="field-hdr10q", classes="form-ctrl")

        yield Static("", id="cons-dv", classes="consequence")

        # ── Audio sans perte ──────────────────────────────────────────────────
        yield Static("── AUDIO SANS PERTE (TrueHD, DTS-HD MA)", classes="section-hdr")

        with Widget(classes="form-row"):
            with Widget(classes="form-cell"):
                yield Label("traitement",  classes="form-lbl")
                yield Select(_opts(_HD_AUDIO), id="field-hdaudio", classes="form-ctrl")
            with Widget(classes="form-cell"):
                pass

        yield Static("", id="cons-hdaudio", classes="consequence")

        # ── Autres pistes ─────────────────────────────────────────────────────
        yield Static("── AUTRES PISTES AUDIO", classes="section-hdr")

        with Widget(classes="form-row"):
            with Widget(classes="form-cell"):
                yield Label("Langues",     classes="form-lbl")
                yield Input(placeholder="fre, eng", id="field-langs", classes="form-ctrl")
            with Widget(classes="form-cell"):
                yield Checkbox("copier AAC / AC3 / E-AC3 sans transcoder",
                               id="field-copy-compat")

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
                pass

        yield Static("", id="cons-pistes", classes="consequence")

        # ── Fichier source ────────────────────────────────────────────────────
        yield Static("── FICHIER SOURCE", classes="section-hdr")

        with Widget(classes="check-row"):
            yield Checkbox("supprimer la source après un encodage réussi",
                           id="field-delsrc")

        yield Static("", id="cons-source", classes="consequence")

        # ── Pied ──────────────────────────────────────────────────────────────
        yield Static(
            "  Tab / Shift+Tab : champ suiv./préc.    "
            "Enter : ouvrir une liste    +/- : valeur suiv./préc.    "
            "Ctrl+S : enregistrer    Esc : annuler",
            classes="form-hint",
        )
        yield Static("", id="form-error", classes="form-error")

    # ── Conséquences ──────────────────────────────────────────────────────────

    _PRESET_TXT = {
        "fast":   "le plus rapide, qualité moindre à débit égal.",
        "medium": "compromis par défaut.",
        "slow":   "meilleure qualité à débit égal, environ 30 % plus lent.",
    }

    _HD_AUDIO_TXT = {
        "copy": ("La piste est recopiée intacte. Elle impose le conteneur MKV, "
                 "et la plupart des lecteurs ne la décodent pas : le serveur "
                 "transcodera à chaque lecture."),
        "eac3": ("Un TrueHD à 3 500 kbps ressort en E-AC3 à 3 500 kbps — le "
                 "débit de la piste, plafonné à 6 144 kbps. Décodé nativement "
                 "par les téléviseurs récents, et le MP4 l'accepte."),
        "ac3":  ("Repli universel, mais l'AC3 plafonne à 640 kbps : l'encodeur "
                 "ramène en silence toute demande supérieure."),
        "forfait": ("Les débits 5.1 et 7.1 ci-dessous s'appliquent. Convient à "
                    "une piste déjà compressée, jette beaucoup sur une source "
                    "sans perte."),
    }

    def _txt(self, wid: str, defaut=None):
        try:
            v = self.query_one(wid, Select).value
            return defaut if v is Select.BLANK else v
        except Exception:
            return defaut

    def _chk(self, wid: str) -> bool:
        try:
            return bool(self.query_one(wid, Checkbox).value)
        except Exception:
            return False

    def _pose(self, wid: str, texte: str, alerte: bool = False) -> None:
        try:
            w = self.query_one(wid, Static)
        except Exception:
            return
        w.update(texte)
        w.set_class(alerte, "consequence-warn")
        w.set_class(not alerte, "consequence")

    def refresh_consequences(self) -> None:
        """Réécrit chaque ligne de conséquence d'après les valeurs courantes."""
        k4  = self._txt("#field-4k", 8000)
        k10 = self._txt("#field-1080p", 2500)
        k7  = self._txt("#field-720p", 1500)
        garde = self._chk("#field-keep4k")
        self._pose("#cons-seuils",
                   f"Un fichier dont le débit vidéo est sous le seuil de sa "
                   f"résolution n'est pas réencodé. Au-dessus, il est ramené à "
                   f"{k4}k en 4K, {k10}k en 1080p, {k7}k en 720p.\n"
                   + ("Une source 4K reste en 4K." if garde
                      else "Une source 4K est ramenée en 1080p."))

        preset = self._txt("#field-preset", "medium")
        self._pose("#cons-preset",
                   f"Ne s'applique qu'aux fichiers réellement réencodés — "
                   f"{self._PRESET_TXT.get(preset, '')}")

        dv  = self._txt("#field-dv", "hdr10")
        hq  = self._txt("#field-hdr10q", "compat")
        if dv == "hdr10":
            txt = ("Le Dolby Vision est retiré. Sur un profil 8.1 ou 7 que rien "
                   "n'oblige par ailleurs à réencoder, le retrait se fait par "
                   "remux : quelques minutes, image intacte, HDR10+ conservé.")
            if hq == "quality":
                txt += ("\nMode quality : libx265 sur processeur — de l'ordre de "
                        "70 heures pour un film 4K. À réserver au 1080p.")
        elif dv == "dv":
            txt = ("Le Dolby Vision est conservé tel quel. Aucun retrait, donc "
                   "aucun remux : un fichier que rien n'oblige à réencoder est "
                   "laissé intact.")
        else:
            txt = ("Conversion vers SDR par tone mapping. Opération processeur, "
                   "lente, et l'image perd sa plage dynamique étendue.")
        self._pose("#cons-dv", txt)

        self._pose("#cons-hdaudio",
                   self._HD_AUDIO_TXT.get(self._txt("#field-hdaudio", "forfait"), ""))

        self._pose("#cons-pistes",
                   "Les pistes AAC, AC3 et E-AC3 sont recopiées sans être "
                   "retouchées ; les forfaits ne concernent que les autres."
                   if self._chk("#field-copy-compat") else
                   "Toutes les pistes sont transcodées aux forfaits ci-dessus, "
                   "y compris celles qui étaient déjà au bon format.")

        supprime = self._chk("#field-delsrc")
        self._pose("#cons-source",
                   "La source est supprimée dès que l'encodage réussit. "
                   "Irréversible — aucune corbeille."
                   if supprime else
                   "La source est conservée à côté du fichier produit.",
                   alerte=supprime)

    @on(Select.Changed)
    @on(Checkbox.Changed)
    def _sur_changement(self, _event) -> None:
        self.refresh_consequences()

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
        _set_sel("#field-hdaudio", _hd_audio_depuis_cles(
            bool(data.get("preserve_hd_audio", False)),
            str(data.get("audio_hd_codec", "none"))))
        _set_chk("#field-copy-compat",data.get("audio_copy_compatible", True))

        id_field = self.query_one("#field-id", Input)
        id_field.disabled = is_builtin and not is_new

        # Les conséquences décrivent les valeurs chargées, pas les précédentes.
        self.refresh_consequences()

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
            **_hd_audio_cles(_g_sel("#field-hdaudio", "forfait")),
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
        "#field-hdaudio": _HD_AUDIO,
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
