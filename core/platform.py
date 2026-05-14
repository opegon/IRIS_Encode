"""
core/platform.py — Abstraction OS + accélération matérielle.

Retourne un PlatformProfile figé décrivant les encodeurs à utiliser.
Version v1 : Windows uniquement, abstraction en place pour macOS/Linux.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum, auto


class OS(Enum):
    WINDOWS = auto()
    MACOS   = auto()
    LINUX   = auto()
    UNKNOWN = auto()


class GPU(Enum):
    NVIDIA = auto()
    APPLE  = auto()
    NONE   = auto()


@dataclass(frozen=True)
class PlatformProfile:
    os:           OS
    gpu:          GPU
    hwaccel:      str | None   # None → pas d'accélération
    encoder_hevc: str
    encoder_h264: str
    encoder_av1:  str   # av1_nvenc (RTX30+) ou libaom-av1 (CPU, très lent)

    def __str__(self) -> str:
        gpu_str = self.gpu.name
        return (
            f"{self.os.name}/{gpu_str} — "
            f"hwaccel={self.hwaccel or 'none'} "
            f"HEVC={self.encoder_hevc} H264={self.encoder_h264}"
        )


def _detect_os() -> OS:
    s = platform.system()
    if s == "Windows":
        return OS.WINDOWS
    if s == "Darwin":
        return OS.MACOS
    if s == "Linux":
        return OS.LINUX
    return OS.UNKNOWN


def _has_nvidia() -> bool:
    if shutil.which("nvidia-smi") is None:
        return False
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            timeout=5,
        )
        return r.returncode == 0 and bool(r.stdout.strip())
    except Exception:
        return False


def detect() -> PlatformProfile:
    """Détecte la plateforme courante et retourne le profil adapté."""
    os_ = _detect_os()

    if os_ == OS.WINDOWS:
        if _has_nvidia():
            return PlatformProfile(
                os=os_,
                gpu=GPU.NVIDIA,
                hwaccel="cuda",
                encoder_hevc="hevc_nvenc",
                encoder_h264="h264_nvenc",
                encoder_av1 ="av1_nvenc",
            )
        # Windows sans NVIDIA → CPU (libx265/libx264 via ffmpeg)
        return PlatformProfile(
            os=os_,
            gpu=GPU.NONE,
            hwaccel=None,
            encoder_hevc="libx265",
            encoder_h264="libx264",
            encoder_av1 ="libaom-av1",
        )

    if os_ == OS.MACOS:
        return PlatformProfile(
            os=os_,
            gpu=GPU.APPLE,
            hwaccel="videotoolbox",
            encoder_hevc="hevc_videotoolbox",
            encoder_h264="h264_videotoolbox",
            encoder_av1 ="libaom-av1",
        )

    # Linux / inconnu → CPU
    return PlatformProfile(
        os=os_,
        gpu=GPU.NONE,
        hwaccel=None,
        encoder_hevc="libx265",
        encoder_h264="libx264",
        encoder_av1 ="libaom-av1",
    )
