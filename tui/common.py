"""
tui/common.py — Formatage, styles et libellés partagés entre les écrans.

Centralise ce qui était dupliqué entre browser/tracks/dryrun/config :
formatage tailles/durées, couleurs Dolby Vision, options des pickers
codec/débit/profil, groupes de raccourcis standard pour le TwoLineFooter.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from core.decision import (
    AV1_BITRATE_OPTS_KBPS,
    BITRATE_OPTS_KBPS,
    VideoAction,
)

if TYPE_CHECKING:
    from core.profiles import Profile


# ─── Styles partagés ──────────────────────────────────────────────────────────

# Couleur d'affichage de la valeur dolby_vision d'un profil (browser, config)
DV_VALUE_STYLES: dict[str, str] = {
    "hdr10": "yellow",
    "dv":    "green",
    "sdr":   "bold dark_orange",
}


# ─── Formatage ────────────────────────────────────────────────────────────────

def fmt_bytes(b: int) -> str:
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


def profile_picker_options(profiles: dict[str, "Profile"]) -> list[str]:
    """Lignes alignées du sélecteur de profils (F4) — browser et tracks."""
    opts: list[str] = []
    for name, prof in profiles.items():
        f       = prof.summary_fields()
        keep_4k = prof.data.get("keep_4k", False)
        delete  = prof.data.get("delete_source", False)

        alert_col = f"{'⚠' if delete else '':<3}"
        br_1080   = f["1080p"].rjust(6)
        br_4k     = (f"4K {f['4k']}" if keep_4k else "4K→1080p").ljust(12)
        dv_info   = f"DV {f['dv']}".ljust(12)
        preset    = f["preset"].ljust(8)

        hd_audio  = "HD audio" if prof.data.get("preserve_hd_audio") else ""
        hd_col    = f"  ·  {hd_audio:<10}" if hd_audio or delete else ""
        alert_end = f"  ·  {'⚠' if delete else '':<3}"

        opts.append(
            f"{alert_col}{name:<15}  {br_1080}  ·  {br_4k}  ·  "
            f"{dv_info}  ·  {preset}{hd_col}{alert_end}"
        )
    return opts


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
