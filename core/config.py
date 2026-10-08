"""
core/config.py — Lecture/écriture config.toml.

Fournit les valeurs par défaut et des helpers pour accéder aux sections
fréquemment utilisées (bin_dir, largeurs de colonnes).
"""
from __future__ import annotations

import os
import threading
import tomllib
from pathlib import Path
from typing import Any

import tomli_w

from core.profiles import RENOMMAGES_LIVRES

APP_DIR     = Path(__file__).resolve().parent.parent
CONFIG_PATH = APP_DIR / "config.toml"

_DEFAULTS: dict[str, Any] = {
    "app": {
        # Langue de l'interface (« en », « fr »…). Vide = jamais choisie :
        # main.py prend celle de Windows au premier lancement et l'écrit ici
        # (IE-92) ; ensuite, c'est l'écran Options qui la change.
        "language": "",
        # Profil sélectionné au dernier lancement. Vide = jamais choisi, on
        # prend alors le premier de profiles.toml.
        "active_profile": "",
        # Dossier proposé quand celui d'une source est en lecture seule — un
        # ISO monté (IE-118). Vide = le dossier Vidéos de l'utilisateur.
        "output_dir": "",
    },
    "ffmpeg": {
        "fetch_url":    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
        "auto_install": True,
        "bin_dir":      "./bin",
    },
    "updates": {
        "check_on_startup": True,
        # Mise à jour d'IRIS ENCODE elle-même, par updater.py avant le
        # lancement : "ask" (demander, « O » présélectionné), "auto", "off".
        "app": "ask",
    },
    "meta": {
        "omdb_api_key": "",
    },
    # Sous-titres téléchargés depuis l'écran F9 (core/opensubtitles.py). La
    # clé se crée sur opensubtitles.com/consumers ; le compte sert au
    # téléchargement. config.toml n'est pas suivi par git.
    "opensubtitles": {
        "api_key":  "",
        "username": "",
        "password": "",
    },
    # Services dont la clé manque et qu'on ne veut plus se voir demander au
    # lancement (IE-101) : identifiants de core/cles.py.
    "cles": {
        "ne_plus_demander": [],
    },
    # La veille pendant les traitements (`core/veille.py`). `action_fin` est
    # ce que fait la machine après un lot dont on a coché « Après le lot » ;
    # l'interrupteur, lui, repart à « non » à chaque lot.
    "energie": {
        "empecher_veille": True,
        "action_fin":      "rien",
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

    La récursion porte sur **toute** valeur de type dict, des deux côtés. Celles
    de `base` comptent autant que celles d'`override` : `dict(base)` seul ne
    recopiait que le premier niveau, et toute branche qu'`override` ne mentionne
    pas restait *celle de base*. Sur `_deep_merge(_DEFAULTS, user)` — un
    config.toml sans section `[tui]`, par exemple — cfg['tui'] était le `[tui]`
    du module : `reset_browser_columns` y supprimait alors les colonnes par
    défaut, et l'écran suivant s'ouvrait sur un KeyError.
    """
    result = {k: _deep_merge(v, {}) if isinstance(v, dict) else v
              for k, v in base.items()}
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


# Deux threads écrivent la configuration : le thread d'interface quand une
# largeur de colonne change, et le worker d'encodage quand il enregistre une
# vitesse mesurée (`tui/common.record_measured_speed`, appelé sous
# `@work(thread=True)`). Un encodage dure des heures ; la fenêtre est étroite
# mais le coût est la configuration entière.
_VERROU_ECRITURE = threading.Lock()


def save(cfg: dict[str, Any]) -> None:
    """Écrit config.toml — entièrement, ou pas du tout.

    L'écriture directe ouvrait le fichier en `"wb"`, ce qui **tronque avant
    d'écrire** : une coupure à mi-course laissait un TOML invalide, et
    l'application ne redémarrait plus. On écrit donc à côté, puis on remplace
    d'un seul geste — `os.replace` est atomique sur NTFS comme sur POSIX.

    C'est la famille de la v0.8.1.4 par un autre chemin : un fichier de
    configuration cassé se paie au lancement suivant, loin de sa cause.
    """
    with _VERROU_ECRITURE:
        provisoire = CONFIG_PATH.with_name(CONFIG_PATH.name + ".tmp")
        try:
            with provisoire.open("wb") as f:
                tomli_w.dump(cfg, f)
                f.flush()
                # Sans fsync, `os.replace` peut publier un fichier dont le
                # contenu n'a pas encore atteint le disque : sur coupure
                # secteur, on remplace un bon fichier par un vide.
                os.fsync(f.fileno())
            os.replace(provisoire, CONFIG_PATH)
        except BaseException:
            provisoire.unlink(missing_ok=True)
            raise


def assurer_langue(cfg: dict[str, Any]) -> str:
    """La langue de l'interface. Au premier lancement (réglage vide), celle du
    système, écrite aussitôt dans config.toml (IE-92) : la détection n'a lieu
    qu'une fois, ensuite le réglage de l'utilisateur prime. Un config.toml
    impossible à écrire n'empêche pas de démarrer — on redétectera au suivant.
    """
    from core import i18n
    app = cfg.setdefault("app", {})
    if not app.get("language"):
        app["language"] = i18n.langue_initiale(i18n.langue_systeme(),
                                               i18n.langues_disponibles())
        try:
            save(cfg)
        except OSError:
            pass
    return app["language"]


def get_active_profile(cfg: dict[str, Any], profile_ids) -> str:
    """Le profil actif à retenir au démarrage, garanti présent dans la liste.

    Le choix du profil est un état de session, pas une propriété du fichier de
    profils : l'application rouvre sur celui qu'on utilisait la dernière fois.
    À défaut — premier lancement, ou profil disparu depuis, renommé ou effacé à
    la main dans profiles.toml — on retombe sur le premier du fichier.

    Sans cette mémoire, l'actif était le premier du fichier à chaque lancement.
    Un profil `delete_source = true` posé en tête devenait donc actif au
    démarrage, et effaçait les sources d'un lot lancé sans regarder.
    """
    ids = list(profile_ids)
    if not ids:
        raise ValueError("no profile to activate")
    retenu = cfg.get("app", {}).get("active_profile", "")
    if retenu not in ids:
        # Profil livré renommé depuis (IE-112) : `profiles.load_all` a migré
        # le fichier, la mémoire du profil actif suit.
        retenu = RENOMMAGES_LIVRES.get(retenu, retenu)
    return retenu if retenu in ids else ids[0]


def set_active_profile(cfg: dict[str, Any], profile_id: str) -> None:
    """Mémorise le profil actif et écrit config.toml."""
    cfg.setdefault("app", {})["active_profile"] = profile_id
    save(cfg)


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
    # « 999.9 Go » — huit caractères. Le dry-run en persistait six : « 34.6 … »
    # (UX-20).
    "taille":       8,
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


# ─── Énergie ──────────────────────────────────────────────────────────────────

def get_empecher_veille(cfg: dict[str, Any]) -> bool:
    return bool(cfg.get("energie", {}).get("empecher_veille", True))


def get_action_fin(cfg: dict[str, Any]) -> str:
    """L'action d'après lot ; une valeur inconnue (fichier édité) vaut le défaut."""
    from core.veille import ACTION_FIN_DEFAUT, ACTIONS_FIN
    action = cfg.get("energie", {}).get("action_fin", ACTION_FIN_DEFAUT)
    return action if action in ACTIONS_FIN else ACTION_FIN_DEFAUT


def set_energie(cfg: dict[str, Any], empecher_veille: bool, action_fin: str) -> None:
    cfg.setdefault("energie", {}).update(empecher_veille=bool(empecher_veille),
                                         action_fin=action_fin)
    save(cfg)


def get_output_dir(cfg: dict[str, Any]) -> Path:
    """Le dossier de sortie proposé pour une source en lecture seule.

    Le réglage s'il désigne un dossier existant ; à défaut le dossier Vidéos de
    l'utilisateur, puis son dossier personnel. Un dossier disparu (disque
    débranché) ne doit pas empêcher de proposer quelque chose.
    """
    regle = cfg.get("app", {}).get("output_dir", "")
    if regle and Path(regle).is_dir():
        return Path(regle)
    videos = Path.home() / "Videos"
    return videos if videos.is_dir() else Path.home()


def set_output_dir(cfg: dict[str, Any], dossier: Path | None) -> None:
    """Enregistre le dossier de sortie ; None revient au défaut."""
    cfg.setdefault("app", {})["output_dir"] = str(dossier) if dossier else ""
    save(cfg)
