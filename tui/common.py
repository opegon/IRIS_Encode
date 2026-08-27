"""
tui/common.py — Formatage, styles et libellés partagés entre les écrans.

Centralise ce qui était dupliqué entre browser/tracks/dryrun/config :
formatage tailles/durées, couleurs Dolby Vision, options des pickers
codec/débit, groupes de raccourcis standard pour le KeyFooter.
"""
from __future__ import annotations

from pathlib import Path

from core import config as cfg_mod
from core.decision import (
    DVAction,
    style_dv,
    AV1_BITRATE_OPTS_KBPS,
    BITRATE_OPTS_KBPS,
    VideoAction,
)

# Codec → clé de stockage des vitesses mesurées (config.toml [stats.encode_speed])
_CODEC_SPEED_KEYS: dict[VideoAction, str] = {
    VideoAction.ENCODE_HEVC: "hevc",
    VideoAction.ENCODE_H264: "h264",
    VideoAction.ENCODE_AV1:  "av1",
}


def get_measured_speed(cfg: dict, action: VideoAction) -> float | None:
    """Vitesse d'encodage réelle moyenne (x temps réel) mesurée sur les runs précédents."""
    key = _CODEC_SPEED_KEYS.get(action)
    return cfg_mod.get_encode_speed(cfg, key) if key else None


def record_measured_speed(cfg: dict, action: VideoAction, speed: float) -> None:
    """Enregistre la vitesse réelle mesurée pour ce codec (moyenne mobile) et persiste."""
    key = _CODEC_SPEED_KEYS.get(action)
    if key is None or speed <= 0:
        return
    cfg_mod.update_encode_speed(cfg, key, speed)
    cfg_mod.save(cfg)


# ─── Noms de touches ──────────────────────────────────────────────────────────
#
# Trois notations coexistaient pour la même information : le footer disait
# « Space Sélect », les modales « Espace  Sélectionner », le formulaire de
# profil « Tab / Shift+Tab : champ suiv./préc. ». Le choix du glyphe importe
# moins que son unicité — mais un glyphe tient en une colonne, ce qui compte
# sur un footer de trois lignes.

TOUCHES: dict[str, str] = {
    "enter":     "↵",
    "backspace": "⌫",
    "space":     "␣",
    "escape":    "Esc",
    "tab":       "Tab",
    "shift+tab": "⇧Tab",
    "delete":    "Suppr",
    "pageup":    "PgUp",
    "pagedown":  "PgDn",
    "home":      "Home",
    "end":       "End",
    "left":      "←",
    "right":     "→",
    "up":        "↑",
    "down":      "↓",
    "ctrl+s":    "Ctrl+S",
    "ctrl+c":    "Ctrl+C",
    "ctrl+d":    "Ctrl+D",
}

# Espacement, lui aussi commun : deux blancs entre la touche et son libellé,
# cinq entre deux raccourcis. Le footer resserre à trois pour tenir en largeur.
SEP_TOUCHE: str = "  "
SEP_ENTREE: str = "     "


def touche(nom: str) -> str:
    """Nom de touche Textual → notation affichée. Inconnue : en majuscules."""
    return TOUCHES.get(nom.lower(), nom.upper())


def raccourci(nom: str, libelle: str) -> str:
    """Un raccourci rendu. `nom` peut être une touche Textual (« enter ») ou
    une notation déjà composée (« +/- », « Shift+↑/↓ »)."""
    return f"{touche(nom)}{SEP_TOUCHE}{libelle}"


def raccourcis(paires: list[tuple[str, str]]) -> str:
    """Une ligne d'aide complète, pour les pieds de modale et les bandeaux."""
    return SEP_ENTREE.join(raccourci(n, l) for n, l in paires)


# ─── Styles partagés ──────────────────────────────────────────────────────────

# Couleur de la valeur `dolby_vision` d'un profil (browser, config). Dérivée de
# la table unique : un profil réglé sur « sdr » doit alerter au même titre
# qu'une décision qui l'applique.
DV_VALUE_STYLES: dict[str, str] = {
    "hdr10": style_dv(DVAction.HDR10),
    "dv":    style_dv(DVAction.DV),
    "sdr":   style_dv(DVAction.SDR),
}


# ─── Formatage ────────────────────────────────────────────────────────────────

def fmt_bytes(b: int) -> str:
    if b >= 1_099_511_627_776:
        return f"{b / 1_099_511_627_776:.1f} To"
    if b >= 1_073_741_824:
        return f"{b / 1_073_741_824:.1f} Go"
    if b >= 1_048_576:
        return f"{b / 1_048_576:.0f} Mo"
    return f"{b // 1024} Ko"


def fmt_size(path: Path) -> str:
    try:
        return fmt_bytes(path.stat().st_size)
    except OSError:
        return "—"


def fmt_duration(seconds: float) -> str:
    if seconds <= 0:
        return "—"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s   = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def estimate_encoding_duration(
    source_duration: float,
    source_bitrate: int,
    target_bitrate: int,
    action: VideoAction,
    preset: str = "medium",
    measured_speed: float | None = None,
) -> float:
    """
    Estime la durée d'encodage en secondes.

    Si measured_speed est fourni (vitesse réelle x temps réel, mesurée lors
    d'encodages précédents pour ce codec — voir get_measured_speed), elle est
    utilisée directement et remplace l'heuristique bitrate/codec/preset ci-dessous.

    Heuristique de repli (tant qu'aucune mesure réelle n'est disponible) :
    - Ratio bitrate (source → cible)
    - Facteur codec (HEVC plus lent qu'H264, AV1 bien plus lent)
    - Facteur preset (fast plus rapide, slow plus lent)

    Formule : durée_estimée = source_duration * (source_bitrate / target_bitrate) * factor_codec * factor_preset
    """
    if source_duration <= 0 or target_bitrate <= 0:
        return 0.0

    if measured_speed and measured_speed > 0:
        return source_duration / measured_speed

    # Ratio bitrate : réduction de bitrate = encodage plus rapide
    bitrate_ratio = source_bitrate / max(target_bitrate, 1)

    # Facteurs codec (basés sur GPU NVIDIA pour durée réelle approximative)
    # Les facteurs sont relatifs au temps réel du fichier
    # H264 NVENC : ~0.8x (20% plus rapide que temps réel grâce au GPU)
    # HEVC NVENC : ~0.6x (40% plus rapide que temps réel, encodeur très optimisé)
    # AV1 NVENC  : ~1.5x (50% plus lent que temps réel)
    codec_factors = {
        VideoAction.ENCODE_H264: 0.8,    # H264 NVENC rapide
        VideoAction.ENCODE_HEVC: 0.6,    # HEVC NVENC très rapide
        VideoAction.ENCODE_AV1:  1.5,    # AV1 plus lent
        VideoAction.SKIP:        0.0,
    }
    codec_factor = codec_factors.get(action, 1.0)

    # Facteurs preset (relatif à medium=1.0)
    # Impact du preset sur le temps de traitement
    preset_factors = {
        "fast":   0.7,     # 70% du temps de medium (plus rapide)
        "medium": 1.0,     # baseline
        "slow":   1.3,     # 130% du temps de medium (plus lent mais meilleure qualité)
    }
    preset_factor = preset_factors.get(preset, 1.0)

    # Formule d'estimation
    estimated = source_duration * bitrate_ratio * codec_factor * preset_factor
    return max(0.0, estimated)


# ─── Pickers partagés (codec / débit / profil) ────────────────────────────────

# Options du picker codec — même ordre que core.decision.ACTION_CYCLE
CODEC_PICKER_OPTS: list[str] = [
    "HEVC",
    "H264",
    "AV1  (⚠ très gourmand CPU/GPU RTX30+)",
    "SKIP",
]


def bitrate_picker_config(
    action: VideoAction,
    current_bps: int,
) -> tuple[str, list[str], int, list[int]]:
    """Prépare le picker débit : (titre, options, index courant, échelle kbps).

    AV1 a sa propre échelle de débits ; l'index courant est la valeur
    de l'échelle la plus proche du débit actuel.
    """
    is_av1 = action == VideoAction.ENCODE_AV1
    blist  = AV1_BITRATE_OPTS_KBPS if is_av1 else BITRATE_OPTS_KBPS
    title  = "Débit (AV1)" if is_av1 else "Débit cible"
    opts   = [f"{v} kbps" for v in blist]
    cur_k  = current_bps // 1000
    idx    = min(range(len(blist)), key=lambda i: abs(blist[i] - cur_k))
    return title, opts, idx, blist


# ─── Footer : groupes de raccourcis standard ──────────────────────────────────
#
# Convention : ligne 1 = actions propres à l'écran ;
# ligne 2 = retour + navigation table + resize colonnes + F10 Quitter (dernier).

FOOTER_NAV: list[tuple[str, str]] = [
    ("home",     "Début"),
    ("end",      "Fin"),
    ("pageup",   "Page ↑"),
    ("pagedown", "Page ↓"),
]

FOOTER_RESIZE: list[tuple[str, str]] = [
    ("shift+tab", "Col préc."),
    ("tab",       "Col suiv."),
    ("<",         "Rétrécir"),
    (">",         "Élargir"),
]

FOOTER_BACK: tuple[str, str] = ("backspace", "Retour")
FOOTER_QUIT: tuple[str, str] = ("f10",       "Quitter")


def footer_line2(
    *,
    back:   bool = False,
    nav:    bool = True,
    resize: bool = False,
    extra:  tuple[tuple[str, str], ...] = (),
) -> list[tuple[str, str]]:
    """Construit la ligne 2 standard du footer, F10 toujours en dernier."""
    line: list[tuple[str, str]] = []
    if back:
        line.append(FOOTER_BACK)
    if nav:
        line.extend(FOOTER_NAV)
    if resize:
        line.extend(FOOTER_RESIZE)
    line.extend(extra)
    line.append(FOOTER_QUIT)
    return line
