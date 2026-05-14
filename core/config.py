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
    "tui": {
        "browser": {
            "columns": {
                "fichier":      50,
                "resolution":   14,
                "duree":         9,
                "debit":        10,
                "codec":        10,
                "dolby_vision": 12,
                "decision":     24,
                "audio":        24,
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


_DRYRUN_COL_DEFAULTS: dict[str, int] = {
    "fichier":   30,
    "action":    16,
    "conteneur":  7,
    "dv":        10,
    "bitrate":   12,
    "res":       12,
    "audio":     16,
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
