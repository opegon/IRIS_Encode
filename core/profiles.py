"""
core/profiles.py — Lecture/écriture profiles.toml.

Gère les profils builtin (non supprimables) et user (CRUD complet).
"""
from __future__ import annotations

import os
import re
import threading
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomli_w

APP_DIR       = Path(__file__).resolve().parent.parent
PROFILES_PATH = APP_DIR / "profiles.toml"

BUILTIN_NAMES = frozenset({
    "serie_anime", "serie_basic", "serie_hd",
    "film_basic", "film_hd", "cinema_4k_basic",
    "cinema_4k_hd", "cinema_4k_quality", "basic_delete",
})

ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")

# ─── Données builtin embarquées ────────────────────────────────────────────

_BASE_AUDIO = {
    "audio_languages":         ["fre", "eng"],
    # Les sous-titres n'étaient filtrés par rien : un rip streaming en embarque
    # quarante, et les quarante traversaient la chaîne. Clé absente d'un profil
    # personnel = comportement historique, tout est gardé.
    "subtitle_languages":      ["fre", "eng"],
    "audio_stereo_kbps":       192,
    "audio_surround_kbps":     448,
    "audio_surround_7_1_kbps": 640,
    "audio_copy_compatible":   True,
    # "none" | "ac3" | "eac3" — transcode les pistes TrueHD et DTS au débit
    # présent dans la piste, plafonné à ce que l'encodeur sait produire.
    "audio_hd_codec":          "none",
    # "auto" | "mp4" | "mkv" — conteneur de sortie. "auto" laisse le contenu
    # décider ; "mp4" écarte les sous-titres image, sauf s'ils sont les seuls.
    "container":               "auto",
}

_BUILTINS: dict[str, dict[str, Any]] = {
    "serie_anime": {
        "bitrate_720p_kbps":  1500,
        "bitrate_1080p_kbps": 2000,
        "bitrate_4k_kbps":    3500,
        "keep_4k":            False,
        "delete_source":      False,
        "preset_encoder":     "fast",
        "dolby_vision":       "sdr",
        "preserve_hd_audio":  False,
        **_BASE_AUDIO,
    },
    "serie_basic": {
        "bitrate_720p_kbps":  1500,
        "bitrate_1080p_kbps": 2200,
        "bitrate_4k_kbps":    5000,
        "keep_4k":            False,
        "delete_source":      False,
        "preset_encoder":     "medium",
        "dolby_vision":       "hdr10",
        "preserve_hd_audio":  False,
        **_BASE_AUDIO,
    },
    "serie_hd": {
        "bitrate_720p_kbps":  1500,
        "bitrate_1080p_kbps": 2500,
        "bitrate_4k_kbps":    5000,
        "keep_4k":            False,
        "delete_source":      False,
        "preset_encoder":     "medium",
        "dolby_vision":       "hdr10",
        "preserve_hd_audio":  False,
        **_BASE_AUDIO,
    },
    "film_basic": {
        "bitrate_720p_kbps":  2000,
        "bitrate_1080p_kbps": 3000,
        "bitrate_4k_kbps":    5000,
        "keep_4k":            False,
        "delete_source":      False,
        "preset_encoder":     "medium",
        "dolby_vision":       "sdr",
        "preserve_hd_audio":  False,
        **_BASE_AUDIO,
    },
    "film_hd": {
        "bitrate_720p_kbps":  3000,
        "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps":    8000,
        "keep_4k":            False,
        "delete_source":      False,
        "preset_encoder":     "slow",
        "dolby_vision":       "hdr10",
        "preserve_hd_audio":  True,
        **_BASE_AUDIO,
    },
    "cinema_4k_basic": {
        "bitrate_720p_kbps":  2000,
        "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps":    8000,
        "keep_4k":            True,
        "delete_source":      False,
        "preset_encoder":     "slow",
        "dolby_vision":       "hdr10",
        "preserve_hd_audio":  True,
        **_BASE_AUDIO,
    },
    "cinema_4k_hd": {
        "bitrate_720p_kbps":  2000,
        "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps":    12000,
        "keep_4k":            True,
        "delete_source":      False,
        "preset_encoder":     "slow",
        "dolby_vision":       "dv",
        "preserve_hd_audio":  True,
        **_BASE_AUDIO,
    },
    "cinema_4k_quality": {
        "bitrate_720p_kbps":  2000,
        "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps":    12000,
        "keep_4k":            True,
        "delete_source":      False,
        "preset_encoder":     "slow",
        "dolby_vision":       "hdr10",
        "hdr10_quality":      "quality",   # libx265 CPU + métadonnées HDR10 propres
        "preserve_hd_audio":  True,
        **_BASE_AUDIO,
    },
    "basic_delete": {
        "bitrate_720p_kbps":  1500,
        "bitrate_1080p_kbps": 2000,
        "bitrate_4k_kbps":    3500,
        "keep_4k":            False,
        "delete_source":      True,
        "preset_encoder":     "fast",
        "dolby_vision":       "sdr",
        "preserve_hd_audio":  False,
        **_BASE_AUDIO,
    },
}


# ─── Modèle ───────────────────────────────────────────────────────────────────

@dataclass
class Profile:
    id:   str
    data: dict[str, Any]
    user: bool = False   # False = builtin

    # --- Accesseurs pratiques -----------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def bitrate_for_height(self, height: int) -> int:
        """Bitrate cible (bps) selon la hauteur de la source."""
        if height >= 2160:
            return self.data.get("bitrate_4k_kbps", 5000) * 1000
        if height >= 1080:
            return self.data.get("bitrate_1080p_kbps", 2500) * 1000
        return self.data.get("bitrate_720p_kbps", 1500) * 1000

    def summary_line(self) -> str:
        """Une ligne résumant les paramètres clés (pour l'écran Config)."""
        dv   = self.data.get("dolby_vision", "hdr10")
        p1   = self.data.get("bitrate_1080p_kbps", "?")
        pre  = self.data.get("preset_encoder", "?")
        hd   = "oui" if self.data.get("preserve_hd_audio") else "non"
        return f"dv: {dv}  · 1080p: {p1}k  · preset: {pre}  · hd-audio: {hd}"

    def summary_fields(self) -> dict[str, str]:
        """Valeurs individuelles pour affichage en colonnes séparées."""
        k4   = self.data.get("keep_4k", False)
        del_ = self.data.get("delete_source", False)
        return {
            "dv":       self.data.get("dolby_vision", "hdr10"),
            "1080p":    f'{self.data.get("bitrate_1080p_kbps", "?")}k',
            "4k":       f'{self.data.get("bitrate_4k_kbps", "?")}k' + (" ✓" if k4 else ""),
            "preset":   self.data.get("preset_encoder", "?"),
            "hd_audio": "oui" if self.data.get("preserve_hd_audio") else "non",
            "del_src":  "⚠ oui" if del_ else "non",
        }

    def as_toml_dict(self) -> dict[str, Any]:
        return dict(self.data)


# ─── Chargement ───────────────────────────────────────────────────────────────

def load_all() -> dict[str, "Profile"]:
    """Charge tous les profils (builtin + user)."""
    profiles: dict[str, Profile] = {
        name: Profile(id=name, data=dict(data), user=False)
        for name, data in _BUILTINS.items()
    }

    if not PROFILES_PATH.exists():
        _write_defaults()
        return profiles

    try:
        with PROFILES_PATH.open("rb") as f:
            raw: dict[str, Any] = tomllib.load(f)
    except Exception as e:
        # Syntaxe invalide — on conserve les builtins et on avertit
        print(
            f"⚠  profiles.toml illisible ({e}). "
            "Chargement du profil [default] intégré."
        )
        return profiles

    for name, data in raw.items():
        if name in BUILTIN_NAMES:
            # L'utilisateur peut éditer un builtin — on merge sur la base
            merged = dict(_BUILTINS[name]) | dict(data)
            profiles[name] = Profile(id=name, data=merged, user=False)
        else:
            profiles[name] = Profile(id=name, data=dict(data), user=True)

    return profiles


# Deux écrans peuvent enregistrer, et `load_all` réécrit les défauts au premier
# lancement : le verrou coûte le temps d'une écriture de quelques kilo-octets.
_VERROU_ECRITURE = threading.Lock()


def _ecrire(raw: dict[str, Any]) -> None:
    """Écrit profiles.toml — entièrement, ou pas du tout.

    L'écriture directe ouvrait le fichier en `"wb"`, ce qui **tronque avant
    d'écrire** : une coupure à mi-course laisse un TOML invalide. `load_all`
    avale alors l'erreur de syntaxe, avertit, et rend les seuls profils
    livrés — tout ce que l'utilisateur a créé ou modifié est perdu, sans
    recours. On écrit donc à côté, puis on remplace d'un seul geste.

    C'est exactement la parade de `config.save`, posée en v0.8.3.12 pour
    `config.toml` et jamais portée ici. Ce fichier-là pèse plus lourd : une
    configuration se refait en trois réglages, une bibliothèque de profils
    non.
    """
    with _VERROU_ECRITURE:
        provisoire = PROFILES_PATH.with_name(PROFILES_PATH.name + ".tmp")
        try:
            with provisoire.open("wb") as f:
                tomli_w.dump(raw, f)
                f.flush()
                # Sans fsync, `os.replace` peut publier un fichier dont le
                # contenu n'a pas encore atteint le disque : sur coupure
                # secteur, on remplace un bon fichier par un vide.
                os.fsync(f.fileno())
            os.replace(provisoire, PROFILES_PATH)
        except BaseException:
            provisoire.unlink(missing_ok=True)
            raise


def save_all(profiles: dict[str, "Profile"]) -> None:
    """Écrit tous les profils dans profiles.toml."""
    _ecrire({name: p.as_toml_dict() for name, p in profiles.items()})


def _write_defaults() -> None:
    _ecrire({k: dict(v) for k, v in _BUILTINS.items()})


# ─── Validation ───────────────────────────────────────────────────────────────

def validate_id(name: str) -> bool:
    return bool(ID_PATTERN.match(name))


def parse_languages(raw: str) -> list[str]:
    """Parse une chaîne de codes langue séparés par , ; ou espace."""
    parts = re.split(r"[,;\s]+", raw.strip())
    return [p.strip().lower() for p in parts if p.strip()]
