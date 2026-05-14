"""
core/profiles.py — Lecture/écriture profiles.toml.

Gère les profils builtin (non supprimables) et user (CRUD complet).
"""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomli_w

APP_DIR       = Path(__file__).resolve().parent.parent
PROFILES_PATH = APP_DIR / "profiles.toml"

BUILTIN_NAMES = frozenset({
    "default", "serie_hd", "cinema_4k_basic",
    "cinema_4k_hd", "basic_delete", "archivage",
})

ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")

# ─── Données builtin embarquées ────────────────────────────────────────────

_BASE_AUDIO = {
    "audio_languages":         ["fre", "eng"],
    "audio_stereo_kbps":       192,
    "audio_surround_kbps":     448,
    "audio_surround_7_1_kbps": 640,
    "audio_copy_compatible":   True,
}

_BUILTINS: dict[str, dict[str, Any]] = {
    "default": {
        "bitrate_720p_kbps":  1500,
        "bitrate_1080p_kbps": 2200,
        "bitrate_4k_kbps":    5000,
        "keep_4k":            False,
        "delete_source":      False,
        "preset_encoder":     "medium",
        "dolby_vision":       "strip",
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
        "dolby_vision":       "strip",
        "preserve_hd_audio":  False,
        **_BASE_AUDIO,
    },
    "cinema_4k_basic": {
        "bitrate_720p_kbps":  2000,
        "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps":    8000,
        "keep_4k":            True,
        "delete_source":      False,
        "preset_encoder":     "slow",
        "dolby_vision":       "strip",
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
        "dolby_vision":       "preserve",
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
    "archivage": {
        "bitrate_720p_kbps":  1500,
        "bitrate_1080p_kbps": 2000,
        "bitrate_4k_kbps":    5000,
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
        dv   = self.data.get("dolby_vision", "strip")
        p1   = self.data.get("bitrate_1080p_kbps", "?")
        pre  = self.data.get("preset_encoder", "?")
        hd   = "oui" if self.data.get("preserve_hd_audio") else "non"
        return f"dv: {dv}  · 1080p: {p1}k  · preset: {pre}  · hd-audio: {hd}"

    def summary_fields(self) -> dict[str, str]:
        """Valeurs individuelles pour affichage en colonnes séparées."""
        k4   = self.data.get("keep_4k", False)
        del_ = self.data.get("delete_source", False)
        return {
            "dv":       self.data.get("dolby_vision", "strip"),
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


def save_all(profiles: dict[str, "Profile"]) -> None:
    """Écrit tous les profils dans profiles.toml."""
    raw = {name: p.as_toml_dict() for name, p in profiles.items()}
    with PROFILES_PATH.open("wb") as f:
        tomli_w.dump(raw, f)


def _write_defaults() -> None:
    with PROFILES_PATH.open("wb") as f:
        tomli_w.dump({k: dict(v) for k, v in _BUILTINS.items()}, f)


# ─── Validation ───────────────────────────────────────────────────────────────

def validate_id(name: str) -> bool:
    return bool(ID_PATTERN.match(name))


def parse_languages(raw: str) -> list[str]:
    """Parse une chaîne de codes langue séparés par , ; ou espace."""
    parts = re.split(r"[,;\s]+", raw.strip())
    return [p.strip().lower() for p in parts if p.strip()]
