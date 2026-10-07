"""
tui/widgets/profile_form.py — Formulaire CRUD profil d'encodage.

Layout compact 2 colonnes : chaque ligne contient 2 paramètres côte à côte.
Contrôles : Ctrl+S → enregistrer  |  Esc → annuler
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from textual import on
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Checkbox, Input, Label, Select, Static

from core.i18n import _, N_
from ..common import raccourcis


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
                  (N_("8000k ⚠ recommended"), 8000), ("12000k", 12000)]
_DV_OPTIONS    = [("hdr10", "hdr10"), ("dv", "dv"), ("sdr", "sdr")]
_HDR10_QUALITY = [(N_("compat (NVENC, fast)"), "compat"),
                  (N_("quality (CPU x265, TV-grade)"), "quality")]
_PRESET        = [("fast", "fast"), ("medium", "medium"), ("slow", "slow")]
_BR_STEREO     = [("96k", 96), ("128k", 128), ("192k", 192), ("320k", 320)]
_BR_SURROUND   = [("320k", 320), ("448k", 448), ("640k", 640)]
_BR_71         = [("448k", 448), ("640k", 640), ("768k", 768)]
# Audio sans perte : un seul choix à quatre branches, là où deux réglages
# indépendants (preserve_hd_audio et audio_hd_codec) pouvaient se contredire
# en silence — l'un l'emportait sans que rien ne l'indique à l'écran.
# Les valeurs sont des couples (preserve_hd_audio, audio_hd_codec).
_CONTENEUR = [
    (N_("auto — the content decides"), "auto"),
    (N_("mp4 — compatibility"),      "mp4"),
    (N_("mkv — keep everything"),     "mkv"),
]

_HD_AUDIO = [
    (N_("copy as they are"),              "copy"),
    (N_("→ E-AC3 at the source bitrate"),      "eac3"),
    (N_("→ AC3 at the source bitrate"),        "ac3"),
    (N_("→ fixed 5.1 / 7.1 bitrate below"),     "forfait"),
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
    """Les options d'un champ, libellés traduits (marqués N_ dans les tables)."""
    return [(_(label), val) for label, val in pairs]


# La valeur « rien de choisi » : `Select.NULL` depuis Textual 8, où
# `Select.BLANK` ne subsiste que sous la forme de `False`. Tester `BLANK` seul
# laissait passer la sentinelle : « ramené à Select.NULLk en 4K », et un
# `Select.NULL` enregistré dans le profil en mémoire (UX-03).
_VIDE = getattr(Select, "NULL", Select.BLANK)


def _est_vide(v: Any) -> bool:
    return v is _VIDE or v is Select.BLANK


def _avec_valeur(pairs: list, val: Any) -> list:
    """Les options du champ, plus `val` si le profil en porte une hors liste.

    `serie_basic` règle sa 4K à 3500k, que la liste ne propose pas : le champ
    restait vide. La valeur du profil s'ajoute à sa place dans l'ordre, sans
    rien retirer de la liste.
    """
    if any(v == val for _l, v in pairs) or not isinstance(val, int):
        return list(pairs)
    return sorted([*pairs, (f"{val}k", val)], key=lambda p: p[1])


def _section(titre: str, suite: str = "") -> str:
    """« ── TITRE suite » : le filet et les capitales se font ici, au rendu ;
    le message reste en casse normale (L-52). `suite` garde sa casse."""
    return f"── {titre.upper()}" + (f" {suite}" if suite else "")


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
        width: 21;      /* « Bitrate 1080p (kbps) » + une espace */
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

    # Raccourcis réellement actifs quand le formulaire tient le focus. Le
    # footer de l'écran hôte les affiche à sa place tant qu'il est monté :
    # sinon il annonce les touches de l'écran, qui ne répondent plus.
    RACCOURCIS: list[tuple[str, str]] = [
        ("tab",       N_("Next field")),
        ("shift+tab", N_("Previous field")),
        ("enter",     N_("Open a list")),
        ("+/-",       N_("Next/prev value")),
        ("ctrl+s",    N_("Save")),
        ("escape",    N_("Cancel")),
    ]

    def __init__(self, *, name=None, id=None, classes=None, disabled=False):
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._profile_id = ""
        self._is_new     = True
        self._ids_pris: set[str] = set()
        # Options effectives de chaque liste, valeur du profil comprise.
        self._opts_champ: dict[str, list] = dict(self._SELECT_OPTS)

    # ── Composition ───────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        # ── Identifiant ───────────────────────────────────────────────────────
        yield Static(_section(_("Identifier")), classes="section-hdr")
        with Widget(classes="form-row"):
            with Widget(classes="form-cell"):
                yield Label(_("Identifier"), classes="form-lbl")
                yield Input(placeholder=_("my_profile"), id="field-id",
                            classes="form-ctrl")
            with Widget(classes="form-cell"):
                pass   # colonne droite vide

        # ── Quand réencoder ───────────────────────────────────────────────────
        yield Static(_section(_("When to re-encode")), classes="section-hdr")

        with Widget(classes="form-row"):
            with Widget(classes="form-cell"):
                yield Label(_("Bitrate 720p (kbps)"), classes="form-lbl")
                yield Select(_opts(_BITRATE_720P),  id="field-720p",   classes="form-ctrl")
            with Widget(classes="form-cell"):
                yield Label(_("Bitrate 1080p (kbps)"), classes="form-lbl")
                yield Select(_opts(_BITRATE_1080P), id="field-1080p",  classes="form-ctrl")

        with Widget(classes="form-row"):
            with Widget(classes="form-cell"):
                yield Label(_("Bitrate 4K (kbps)"), classes="form-lbl")
                yield Select(_opts(_BITRATE_4K),    id="field-4k",     classes="form-ctrl")
            with Widget(classes="form-cell"):
                yield Checkbox(_("keep 4K (otherwise → 1080p)"), id="field-keep4k")

        yield Static("", id="cons-seuils", classes="consequence")

        # ── Comment encoder ───────────────────────────────────────────────────
        yield Static(_section(_("How to encode")), classes="section-hdr")

        with Widget(classes="form-row"):
            with Widget(classes="form-cell"):
                yield Label(_("Preset"),      classes="form-lbl")
                yield Select(_opts(_PRESET),        id="field-preset", classes="form-ctrl")
            with Widget(classes="form-cell"):
                pass

        yield Static("", id="cons-preset", classes="consequence")

        # ── Dolby Vision ──────────────────────────────────────────────────────
        yield Static(_section("Dolby Vision"), classes="section-hdr")

        with Widget(classes="form-row"):
            with Widget(classes="form-cell"):
                yield Label(_("Handling"),  classes="form-lbl")
                yield Select(_opts(_DV_OPTIONS),    id="field-dv",     classes="form-ctrl")
            with Widget(classes="form-cell"):
                yield Label(_("HDR10 mode"),  classes="form-lbl")
                yield Select(_opts(_HDR10_QUALITY), id="field-hdr10q", classes="form-ctrl")

        yield Static("", id="cons-dv", classes="consequence")

        # ── Audio sans perte ──────────────────────────────────────────────────
        yield Static(_section(_("Lossless audio"), "(TrueHD, DTS-HD MA)"),
                     classes="section-hdr")

        with Widget(classes="form-row"):
            with Widget(classes="form-cell"):
                yield Label(_("Handling"),  classes="form-lbl")
                yield Select(_opts(_HD_AUDIO), id="field-hdaudio", classes="form-ctrl")
            with Widget(classes="form-cell"):
                pass

        yield Static("", id="cons-hdaudio-suite", classes="consequence")

        # ── Conteneur ─────────────────────────────────────────────────────────
        yield Static(_section(_("Output container")), classes="section-hdr")

        with Widget(classes="form-row"):
            with Widget(classes="form-cell"):
                yield Label(_("Container"),   classes="form-lbl")
                yield Select(_opts(_CONTENEUR), id="field-conteneur",
                             classes="form-ctrl")
            with Widget(classes="form-cell"):
                pass

        yield Static("", id="cons-conteneur", classes="consequence")

        yield Static("", id="cons-hdaudio", classes="consequence")

        # ── Autres pistes ─────────────────────────────────────────────────────
        yield Static(_section(_("Other audio tracks")), classes="section-hdr")

        with Widget(classes="form-row"):
            with Widget(classes="form-cell"):
                yield Label(_("Languages"),     classes="form-lbl")
                yield Input(placeholder="fre, eng", id="field-langs", classes="form-ctrl")
            with Widget(classes="form-cell"):
                yield Checkbox(_("copy AAC / AC3 / E-AC3 without transcoding"),
                               id="field-copy-compat")

        # Les sous-titres ont leur propre liste : un rip streaming en embarque
        # quarante, et vouloir deux langues audio ne veut pas dire vouloir les
        # mêmes en sous-titres. Vide = toutes, comme avant l'existence de la clé.
        with Widget(classes="form-row"):
            with Widget(classes="form-cell"):
                yield Label(_("Subtitle languages"), classes="form-lbl")
                # TRANSLATORS: fre, eng are language codes, keep them.
                yield Input(placeholder=_("fre, eng — empty: all"),
                            id="field-sublangs", classes="form-ctrl")

        with Widget(classes="form-row"):
            with Widget(classes="form-cell"):
                yield Label(_("Stereo (kbps)"), classes="form-lbl")
                yield Select(_opts(_BR_STEREO),  id="field-stereo", classes="form-ctrl")
            with Widget(classes="form-cell"):
                yield Label("5.1 (kbps)",  classes="form-lbl")
                yield Select(_opts(_BR_SURROUND),id="field-51",     classes="form-ctrl")

        with Widget(classes="form-row"):
            with Widget(classes="form-cell"):
                yield Label("7.1 (kbps)",  classes="form-lbl")
                yield Select(_opts(_BR_71),      id="field-71",     classes="form-ctrl")
            with Widget(classes="form-cell"):
                pass

        yield Static("", id="cons-pistes", classes="consequence")

        # ── Fichier source ────────────────────────────────────────────────────
        yield Static(_section(_("Source file")), classes="section-hdr")

        with Widget(classes="check-row"):
            yield Checkbox(_("delete the source after a successful encode"),
                           id="field-delsrc")

        yield Static("", id="cons-source", classes="consequence")

        # ── Pied ──────────────────────────────────────────────────────────────
        # Pas de pied propre : le footer de l'écran hôte porte ces mêmes
        # raccourcis tant que le formulaire est monté. Deux bandeaux qui
        # disent la même chose, c'est un de trop.
        yield Static("", id="form-error", classes="form-error")

    # ── Conséquences ──────────────────────────────────────────────────────────

    _PRESET_TXT = {
        "fast":   N_("the fastest, lower quality at equal bitrate."),
        "medium": N_("default compromise."),
        "slow":   N_("better quality at equal bitrate, about 30% slower."),
    }

    _CONTENEUR_TXT = {
        "auto": N_("The content decides: MP4 when everything fits, MKV as soon "
                   "as there is an image subtitle, a styled subtitle or a "
                   "lossless track."),
        "mp4":  N_("Image subtitles (PGS, VobSub) are discarded — MP4 cannot "
                   "carry them — and the decision shows it. If they are the "
                   "file's only ones, the container gives way: better an MKV "
                   "than an output without subtitles."),
        "mkv":  N_("Everything is kept, including image subtitles and lossless "
                   "tracks. Some players handle MKV poorly."),
    }

    _HD_AUDIO_TXT = {
        "copy": N_("The track is copied untouched. It forces the MKV container, "
                   "and most players cannot decode it: the server will "
                   "transcode it at every playback."),
        "eac3": N_("A TrueHD at 3,500 kbps comes out as E-AC3 at 3,500 kbps — "
                   "the track's bitrate, capped at 6,144 kbps. Decoded natively "
                   "by recent TVs, and MP4 accepts it."),
        "ac3":  N_("Universal fallback, but AC3 is capped at 640 kbps: the "
                   "encoder silently brings down any higher request."),
        "forfait": N_("The 5.1 and 7.1 bitrates below apply. Fine for an "
                      "already compressed track, throws a lot away from a "
                      "lossless source."),
    }

    def _txt(self, wid: str, defaut=None):
        try:
            v = self.query_one(wid, Select).value
            return defaut if _est_vide(v) else v
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
                   _("A file whose video bitrate is below the threshold of its "
                     "resolution is not re-encoded. Above it, it is brought "
                     "down to {k4}k in 4K, {k1080}k in 1080p, {k720}k in "
                     "720p.").format(k4=k4, k1080=k10, k720=k7) + "\n"
                   + (_("A 4K source stays in 4K.") if garde
                      else _("A 4K source is brought down to 1080p.")))

        preset = self._txt("#field-preset", "medium")
        self._pose("#cons-preset",
                   _("Only applies to files that are actually re-encoded — "
                     "{effect}").format(effect=_(self._PRESET_TXT.get(preset, ""))))

        dv  = self._txt("#field-dv", "hdr10")
        hq  = self._txt("#field-hdr10q", "compat")
        if dv == "hdr10":
            txt = _("Dolby Vision is removed. On a profile 8.1 or 7 that "
                    "nothing else requires re-encoding, the removal is a remux: "
                    "a few minutes, picture untouched, HDR10+ kept.")
            if hq == "quality":
                # TRANSLATORS: "quality" is the value of the HDR10 mode setting.
                txt += "\n" + _("Quality mode: libx265 on the processor — around "
                                "70 hours for a 4K movie. Keep it for 1080p.")
        elif dv == "dv":
            txt = _("Dolby Vision is kept as it is. No removal, so no remux: a "
                    "file that nothing requires re-encoding is left untouched.")
        else:
            txt = _("Conversion to SDR by tone mapping. Processor-bound, slow, "
                    "and the picture loses its high dynamic range.")
        self._pose("#cons-dv", txt)

        self._pose("#cons-hdaudio",
                   _(self._HD_AUDIO_TXT.get(self._txt("#field-hdaudio", "forfait"), "")))

        self._pose("#cons-hdaudio-suite", "")
        self._pose("#cons-conteneur",
                   _(self._CONTENEUR_TXT.get(self._txt("#field-conteneur", "auto"), "")))

        self._pose("#cons-pistes",
                   _("AAC, AC3 and E-AC3 tracks are copied untouched; the "
                     "fixed bitrates only apply to the others.")
                   if self._chk("#field-copy-compat") else
                   _("All tracks are transcoded at the fixed bitrates above, "
                     "including those already in the right format."))

        supprime = self._chk("#field-delsrc")
        self._pose("#cons-source",
                   _("The source is deleted as soon as the encoding succeeds. "
                     "Irreversible — no recycle bin.")
                   if supprime else
                   _("The source is kept next to the produced file."),
                   alerte=supprime)

    @on(Select.Changed)
    @on(Checkbox.Changed)
    def _sur_changement(self, _event) -> None:
        self.refresh_consequences()

    # ── Chargement / Dump ─────────────────────────────────────────────────────

    def load(self, profile_id: str, data: dict[str, Any],
             is_new: bool = False, ids_pris: Iterable[str] = ()) -> None:
        """`profile_id` pré-remplit le nom d'un profil nouveau (copie) ;
        `ids_pris` sont les noms qu'une création ne peut pas reprendre."""
        self._profile_id = profile_id
        self._is_new     = is_new
        self._ids_pris   = set(ids_pris)

        def _set_sel(wid: str, val: Any) -> None:
            try:
                sel = self.query_one(wid, Select)
                if wid in self._SELECT_OPTS:
                    opts = _avec_valeur(self._SELECT_OPTS[wid], val)
                    if opts != self._opts_champ[wid]:
                        self._opts_champ[wid] = opts
                        sel.set_options(_opts(opts))
                sel.value = val
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

        _set_inp("#field-id",     profile_id)
        _set_sel("#field-720p",   data.get("bitrate_720p_kbps",       1500))
        _set_sel("#field-1080p",  data.get("bitrate_1080p_kbps",      2500))
        _set_sel("#field-4k",     data.get("bitrate_4k_kbps",         5000))
        _set_sel("#field-dv",     data.get("dolby_vision",          "sdr"))
        _set_sel("#field-preset", data.get("preset_encoder",    "medium"))
        _set_sel("#field-hdr10q", data.get("hdr10_quality",     "compat"))
        _set_chk("#field-keep4k", data.get("keep_4k",                False))
        _set_chk("#field-delsrc", data.get("delete_source",          False))
        _set_inp("#field-langs",
                 ", ".join(data.get("audio_languages", ["fre", "eng"])))
        _set_inp("#field-sublangs",
                 ", ".join(data.get("subtitle_languages") or []))
        _set_sel("#field-stereo", data.get("audio_stereo_kbps",        192))
        _set_sel("#field-51",     data.get("audio_surround_kbps",      448))
        _set_sel("#field-71",     data.get("audio_surround_7_1_kbps",  640))
        _set_sel("#field-conteneur", data.get("container", "auto"))
        _set_sel("#field-hdaudio", _hd_audio_depuis_cles(
            bool(data.get("preserve_hd_audio", False)),
            str(data.get("audio_hd_codec", "none"))))
        _set_chk("#field-copy-compat",data.get("audio_copy_compatible", True))

        # Le nom n'est saisissable qu'à la création : `_on_key` réenregistre un
        # profil existant sous `self._profile_id`, jamais sous le contenu du
        # champ. Laisser saisir ici ferait perdre la frappe sans le dire.
        self.query_one("#field-id", Input).disabled = not is_new

        # Les conséquences décrivent les valeurs chargées, pas les précédentes.
        self.refresh_consequences()

    def dump(self) -> dict[str, Any]:
        def _g_sel(wid: str, default: Any) -> Any:
            try:
                v = self.query_one(wid, Select).value
                return default if _est_vide(v) else v
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
        # Vide = aucun filtre, c'est-à-dire le comportement d'avant la clé.
        sub_raw   = _g_inp("#field-sublangs", "")
        sub_langs = [l.strip() for l in sub_raw.replace(";", ",").split(",")
                     if l.strip()]

        return {
            "bitrate_720p_kbps":       _g_sel("#field-720p",   1500),
            "bitrate_1080p_kbps":      _g_sel("#field-1080p",  2500),
            "bitrate_4k_kbps":         _g_sel("#field-4k",     5000),
            "dolby_vision":            _g_sel("#field-dv",    "sdr"),
            "preset_encoder":          _g_sel("#field-preset","medium"),
            "hdr10_quality":           _g_sel("#field-hdr10q","compat"),
            "keep_4k":                 _g_chk("#field-keep4k"),
            "delete_source":           _g_chk("#field-delsrc"),
            "audio_languages":         langs,
            "subtitle_languages":      sub_langs,
            "audio_stereo_kbps":       _g_sel("#field-stereo",  192),
            "audio_surround_kbps":     _g_sel("#field-51",      448),
            "audio_surround_7_1_kbps": _g_sel("#field-71",      640),
            **_hd_audio_cles(_g_sel("#field-hdaudio", "forfait")),
            "container":               _g_sel("#field-conteneur", "auto"),
            "audio_copy_compatible":   _g_chk("#field-copy-compat"),
        }

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self._is_new:
            pid = self.query_one("#field-id", Input).value.strip()
            if not pid:
                errors.append(_("The identifier cannot be empty."))
            elif not all(c.isalnum() or c in "-_" for c in pid):
                errors.append(_("Identifier: allowed characters a-z, 0-9, - _"))
            elif len(pid) > 32:
                errors.append(_("Identifier: 32 characters at most."))
            elif pid in self._ids_pris:
                # Sans ce refus, l'enregistrement écrasait le profil du même nom.
                errors.append(_("The profile “{profile}” already exists.").format(
                    profile=pid))
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
        "#field-conteneur": _CONTENEUR,
    }

    def _cycle_focused_select(self, delta: int) -> bool:
        """Cycle la valeur du Select focalisé. Retourne True si géré."""
        focused = self.app.focused
        if not isinstance(focused, Select):
            return False
        for field_id, opts in self._opts_champ.items():
            try:
                widget = self.query_one(field_id, Select)
            except Exception:
                continue
            if widget is not focused:
                continue
            vals = [v for _l, v in opts]
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
