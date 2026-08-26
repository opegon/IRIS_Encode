"""
core/preview.py — Contrôle d'un recalage à l'œil, dans mpv.

La corrélation donne un chiffre ; elle ne dit pas si le résultat *sonne*
juste. mpv ouvre le film avec la piste externe déjà greffée et le décalage
courant appliqué, positionné sur un passage dialogué.

L'utilisateur ajuste ensuite avec les touches de mpv, qui affiche la valeur
en OSD, puis la reporte dans l'écran de recalage :

    audio        Ctrl + +  /  Ctrl + -     pas de 100 ms
    sous-titres  z  /  Z                   pas de 100 ms
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from .muxer import ExternalTrack, TrackKind

# Position d'ouverture quand rien de mieux n'est connu : le début d'un film
# est souvent un générique muet, inutilisable pour juger d'un décalage.
DEFAULT_START_RATIO = 0.25

_mpv_path: Optional[str] = None


def set_mpv_path(path: Optional[str]) -> None:
    """Précise l'exécutable mpv, ou None s'il est absent."""
    global _mpv_path
    _mpv_path = path


def available() -> bool:
    return _mpv_path is not None


def _start_seconds(track: ExternalTrack, duration: float,
                   first_cue: Optional[float]) -> float:
    """Position d'ouverture : de préférence une réplique, sinon un quart."""
    if first_cue is not None and first_cue > 0:
        # Quelques secondes avant, pour entendre venir la réplique
        return max(0.0, first_cue - 3.0)
    return max(0.0, duration * DEFAULT_START_RATIO)


def build_command(
    video:      Path,
    track:      ExternalTrack,
    duration:   float = 0.0,
    n_internal_audio: int = 0,
    donor_audio_index: int = 0,
    first_cue:  Optional[float] = None,
) -> list[str]:
    """
    Commande mpv ouvrant `video` avec `track` greffée et son décalage appliqué.

    Lève RuntimeError si mpv n'est pas disponible.
    """
    if _mpv_path is None:
        raise RuntimeError("mpv n'est pas installé.")

    delay_s = track.delay_ms / 1000.0
    cmd = [
        _mpv_path,
        "--osd-level=1",
        f"--start={_start_seconds(track, duration, first_cue):.0f}",
    ]

    if track.kind == TrackKind.SUBTITLE:
        cmd += [
            f"--sub-file={track.source_path}",
            f"--sub-delay={delay_s:.3f}",
            "--sub-visibility=yes",
        ]
    else:
        # Les pistes d'un --audio-file se numérotent après les pistes internes
        cmd += [
            f"--audio-file={track.source_path}",
            f"--aid={n_internal_audio + donor_audio_index + 1}",
            f"--audio-delay={delay_s:.3f}",
        ]

    cmd.append(str(video))
    return cmd


def launch(cmd: list[str]) -> subprocess.Popen:
    """
    Ouvre mpv sans bloquer la TUI.

    mpv vit sa vie dans sa propre fenêtre : on ne l'attend pas, et on ne lit
    pas ses flux — la TUI garde la main pendant le visionnage.
    """
    return subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def keys_hint(track: ExternalTrack) -> str:
    """Touches mpv à utiliser pour ajuster ce type de piste."""
    if track.kind == TrackKind.SUBTITLE:
        return "dans mpv : z / Z décalent les sous-titres par pas de 100 ms"
    return "dans mpv : Ctrl+= / Ctrl+- décalent l'audio par pas de 100 ms"
