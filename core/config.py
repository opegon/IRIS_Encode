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
            # Largeurs réglées à l'usage : les colonnes numériques n'ont besoin
            # que de leur contenu, et la place gagnée va au nom de fichier et
            # aux pistes audio — les deux seules qui débordent vraiment.
            "columns": {
                "fichier":      50,
                "taille":        8,
                "resolution":   10,
                "duree":         7,   # « 3:17:24 » — sept caractères dès une heure
                "debit":         6,
                "codec":         6,
                "dolby_vision":  8,
                "decision":      8,
                "estim":        14,
                "temps_estim":   9,
                "audio":        20,
            }
        }
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """
    Fusionne `override` dans `base`, sans jamais partager de sous-dictionnaire.

    La récursion porte sur **toute** valeur de type dict, y compris absente de
    `base` : sans ça, `_deep_merge({}, _DEFAULTS)` — le cas d'une machine sans
    config.toml — rendait un cfg dont les branches *sont* celles de _DEFAULTS.
    La moindre écriture dans la configuration corrompait alors les valeurs par
    défaut du module pour tout le reste du processus.
    """
    result = dict(base)
    for k, v in override.items():
        if isinstance(v, dict):
            existant = result.get(k)
            result[k] = _deep_merge(existant if isinstance(existant, dict) else {}, v)
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


# Largeurs minimales imposées par le contenu, non par le goût. `fmt_duration`
# rend sept caractères dès qu'il y a des heures : en dessous, « 3:17:24 »
# s'affiche « 3:17:2 » — une durée valide et fausse. Ces planchers valent à la
# lecture comme au redimensionnement, parce qu'une largeur trop courte a pu
# être persistée avant qu'ils existent.
COLUMN_MIN_WIDTHS: dict[str, int] = {
    "duree":        7,   # « 3:17:24 »
    "temps_estim":  7,
    # « → HEVC → HDR10 » et « → HEVC → SDR ⚠ » font quatorze caractères. À huit,
    # la colonne rendait « → HEVC → » : le sort du Dolby Vision — conservé,
    # converti en HDR10, aplati en SDR — disparaissait, et les trois sorties
    # s'affichaient à l'identique. `decision` sur l'accueil, `action` sur le
    # dry-run, même libellé des deux côtés.
    "decision":    14,
    "action":      14,
    # « DV:P8.1 » — sept caractères. Les deux écrans nomment cette colonne
    # différemment, le plancher vaut pour les deux noms.
    "dolby_vision": 7,
    "dv":           7,
}

# Ces planchers ne se maintiennent pas à la main : `tests/test_troncature.py`
# énumère les libellés que chaque colonne peut produire et échoue si l'un
# dépasse.


def _plancher(widths: dict[str, int]) -> dict[str, int]:
    """Relève les colonnes tombées sous ce que leur contenu exige."""
    return {k: max(v, COLUMN_MIN_WIDTHS[k]) if k in COLUMN_MIN_WIDTHS else v
            for k, v in widths.items()}


def get_column_widths(cfg: dict[str, Any]) -> dict[str, int]:
    return _plancher(
        _DEFAULTS["tui"]["browser"]["columns"]
        | cfg.get("tui", {}).get("browser", {}).get("columns", {})
    )


def reset_browser_columns(cfg: dict[str, Any]) -> None:
    """
    Oublie les largeurs mémorisées du browser, en mémoire seulement.

    L'écran d'accueil repart des valeurs par défaut à chaque lancement : une
    disposition stable, qu'on retrouve identique d'une session à l'autre, vaut
    mieux qu'un réglage qui dérive au fil des redimensionnements ponctuels.
    Le redimensionnement reste disponible pendant la session.

    Le fichier n'est pas réécrit ici : rien ne justifie une écriture disque à
    chaque démarrage.
    """
    cfg.get("tui", {}).get("browser", {}).pop("columns", None)


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
    return _plancher(
        _DRYRUN_COL_DEFAULTS
        | cfg.get("tui", {}).get("dryrun", {}).get("columns", {})
    )


def set_dryrun_column_width(cfg: dict[str, Any], col: str, width: int) -> None:
    (cfg
     .setdefault("tui", {})
     .setdefault("dryrun", {})
     .setdefault("columns", {}))[col] = width


# « Source » portait deux sens — le motif de sélection pour l'audio, le titre
# déclaré pour les sous-titres. Séparées, les deux colonnes tiennent dans la
# largeur qu'occupait l'ancienne à elle seule, à quatre colonnes près.
_TRACKS_COL_DEFAULTS: dict[str, int] = {
    "codec": 12,
    "fmt":   16,
    "src":   18,   # « exclu manuellement »
    "titre": 24,
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
