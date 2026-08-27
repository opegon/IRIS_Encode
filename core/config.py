"""
core/config.py — Lecture/écriture config.toml.

Fournit les valeurs par défaut et des helpers pour accéder aux sections
fréquemment utilisées (bin_dir, largeurs de colonnes).
"""
from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import tomli_w

APP_DIR     = Path(__file__).resolve().parent.parent
CONFIG_PATH = APP_DIR / "config.toml"

_DEFAULTS: dict[str, Any] = {
    "app": {
        "language": "fr",
    },
    "ffmpeg": {
        "fetch_url":    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
        "auto_install": True,
        "bin_dir":      "./bin",
    },
    "updates": {
        "check_on_startup": True,
    },
    "meta": {
        "omdb_api_key": "",
    },
    "decision": {
        "near_1080p_min_width":  1600,
        "near_1080p_min_height":  850,
    },
    "stats": {
        "encode_speed": {},
    },
    "tui": {
        "browser": {
            "columns": {
                "fichier":      50,
                "taille":        8,
                "resolution":   12,
                "duree":        12,
                "debit":        10,
                "codec":         8,
                "dolby_vision": 12,
                "decision":     12,
                "estim":        16,
                "temps_estim":  9,
                "audio":        20,
            }
        }
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load() -> dict[str, Any]:
    """Charge config.toml en appliquant les valeurs par défaut."""
    if not CONFIG_PATH.exists():
        return _deep_merge({}, _DEFAULTS)
    try:
        with CONFIG_PATH.open("rb") as f:
            user = tomllib.load(f)
        return _deep_merge(_DEFAULTS, user)
    except Exception:
        return _deep_merge({}, _DEFAULTS)


def save(cfg: dict[str, Any]) -> None:
    """Écrit config.toml."""
    with CONFIG_PATH.open("wb") as f:
        tomli_w.dump(cfg, f)


def get_bin_dir(cfg: dict[str, Any]) -> Path:
    raw = cfg.get("ffmpeg", {}).get("bin_dir", "./bin")
    p = Path(raw)
    return p if p.is_absolute() else APP_DIR / p


def get_column_widths(cfg: dict[str, Any]) -> dict[str, int]:
    return dict(
        _DEFAULTS["tui"]["browser"]["columns"]
        | cfg.get("tui", {}).get("browser", {}).get("columns", {})
    )


def set_column_width(cfg: dict[str, Any], col: str, width: int) -> None:
    (cfg
     .setdefault("tui", {})
     .setdefault("browser", {})
     .setdefault("columns", {}))[col] = width


def get_encode_speed(cfg: dict[str, Any], codec: str) -> float | None:
    """Vitesse d'encodage mesurée (x temps réel) pour un codec, ou None si pas encore de donnée."""
    v = cfg.get("stats", {}).get("encode_speed", {}).get(codec)
    return float(v) if v else None


def update_encode_speed(cfg: dict[str, Any], codec: str, measured: float, alpha: float = 0.25) -> None:
    """Met à jour la moyenne mobile de vitesse d'encodage mesurée pour un codec."""
    if measured <= 0:
        return
    speeds = cfg.setdefault("stats", {}).setdefault("encode_speed", {})
    prev = speeds.get(codec)
    speeds[codec] = measured if not prev else prev + (measured - prev) * alpha


_DRYRUN_COL_DEFAULTS: dict[str, int] = {
    "fichier":     30,
    "taille":       8,
    "duree":       10,
    "estim":       12,
    "temps_estim": 9,
    "action":      16,
    "conteneur":    7,
    "dv":          10,
    "bitrate":     12,
    "res":         12,
    "audio":       16,
}


def get_dryrun_column_widths(cfg: dict[str, Any]) -> dict[str, int]:
    return dict(
        _DRYRUN_COL_DEFAULTS
        | cfg.get("tui", {}).get("dryrun", {}).get("columns", {})
    )


def set_dryrun_column_width(cfg: dict[str, Any], col: str, width: int) -> None:
    (cfg
     .setdefault("tui", {})
     .setdefault("dryrun", {})
     .setdefault("columns", {}))[col] = width


_TRACKS_COL_DEFAULTS: dict[str, int] = {
    "codec": 12,
    "fmt":   16,
    "src":   32,
}


def get_tracks_column_widths(cfg: dict[str, Any]) -> dict[str, int]:
    return dict(
        _TRACKS_COL_DEFAULTS
        | cfg.get("tui", {}).get("tracks", {}).get("columns", {})
    )


def set_tracks_column_width(cfg: dict[str, Any], col: str, width: int) -> None:
    (cfg
     .setdefault("tui", {})
     .setdefault("tracks", {})
     .setdefault("columns", {}))[col] = width
