"""
core/encoder.py — Construction de la commande ffmpeg et gestion du processus.

build_command() → liste d'arguments prête pour subprocess.
EncoderProcess  → wrapper autour du sous-processus ffmpeg.
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Optional

from .decision import AudioAction, DVAction, FileDecision, VideoAction
from .platform import PlatformProfile


# ─── Suspend / Resume multiplateforme ────────────────────────────────────────

def _suspend_process(pid: int) -> bool:
    if sys.platform == "win32":
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, pid)
        if not h:
            return False
        ctypes.windll.ntdll.NtSuspendProcess(h)
        ctypes.windll.kernel32.CloseHandle(h)
        return True
    else:
        import signal
        try:
            import os; os.kill(pid, signal.SIGSTOP); return True
        except OSError:
            return False


def _resume_process(pid: int) -> bool:
    if sys.platform == "win32":
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, pid)
        if not h:
            return False
        ctypes.windll.ntdll.NtResumeProcess(h)
        ctypes.windll.kernel32.CloseHandle(h)
        return True
    else:
        import signal
        try:
            import os; os.kill(pid, signal.SIGCONT); return True
        except OSError:
            return False


# Pipeline tone mapping Dolby Vision P5 → SDR (CPU, algorithme Hable)
_SDR_TONEMAP_FILTER = (
    "zscale=t=linear:npl=100,"
    "format=gbrpf32le,"
    "zscale=p=bt709,"
    "tonemap=tonemap=hable:desat=0,"
    "zscale=t=bt709:m=bt709:r=tv,"
    "format=yuv420p"
)

# Regex pour parser la ligne de progression ffmpeg
_PROGRESS_RE = re.compile(
    r"frame=\s*(?P<frame>\d+)"
    r".*?fps=\s*(?P<fps>[\d.]+)"
    r".*?time=(?P<time>\d{2}:\d{2}:\d{2}\.\d{2})"
    r".*?bitrate=(?P<bitrate>[\d.]+)kbits/s"
    r".*?speed=(?P<speed>[\d.]+)x"
)


def _time_to_seconds(t: str) -> float:
    """Convertit "HH:MM:SS.ss" en secondes."""
    try:
        h, m, s = t.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception:
        return 0.0


@dataclass
class ProgressInfo:
    frame:   int
    fps:     float
    elapsed: float   # secondes encodées
    bitrate: float   # kbits/s
    speed:   float   # x réel
    percent: float   # 0.0–1.0, -1 si inconnu


def parse_progress(line: str, total_duration: float) -> Optional[ProgressInfo]:
    """Parse une ligne de sortie ffmpeg et retourne ProgressInfo ou None."""
    m = _PROGRESS_RE.search(line)
    if not m:
        return None
    elapsed = _time_to_seconds(m.group("time"))
    # Si durée inconnue, montre au moins la progression temporelle
    percent = (elapsed / total_duration) if total_duration > 0 else elapsed
    return ProgressInfo(
        frame=int(m.group("frame")),
        fps=float(m.group("fps")),
        elapsed=elapsed,
        bitrate=float(m.group("bitrate")),
        speed=float(m.group("speed")),
        percent=min(percent, 1.0) if total_duration > 0 else -1.0,  # -1 = durée inconnue
    )


# ─── Construction commande ────────────────────────────────────────────────────

def build_command(
    decision: FileDecision,
    platform: PlatformProfile,
) -> list[str]:
    """
    Retourne la liste d'arguments ffmpeg pour un FileDecision.
    Retourne [] si l'action est SKIP.
    """
    vid     = decision.video
    info    = decision.info
    profile = decision.profile

    if vid.action == VideoAction.SKIP:
        return []

    # Garde-fou : ne JAMAIS écraser le fichier source
    if decision.output_path.resolve() == info.path.resolve():
        raise ValueError(
            f"Chemin de sortie identique à la source ({info.path}). "
            f"Suffixe vide et conteneur identique — encodage refusé pour éviter "
            f"la corruption du fichier source."
        )

    cmd: list[str] = ["ffmpeg"]

    # hwaccel — absent pour SDR tone map (CPU obligatoire pour zscale)
    # Aussi absent pour DV car on fait du copy
    preserve_video = (vid.dv_action == DVAction.DV)
    if platform.hwaccel and vid.dv_action != DVAction.SDR and not preserve_video:
        cmd += ["-hwaccel", platform.hwaccel]

    cmd += ["-i", str(info.path)]

    # ── Filtre vidéo ──────────────────────────────────────────────────────────
    if not preserve_video:
        scale = (
            f"scale={vid.target_width}:{vid.target_height}"
            ":force_original_aspect_ratio=decrease"
            ":force_divisible_by=2"
        )
        vf = f"{scale},{_SDR_TONEMAP_FILTER}" if vid.dv_action == DVAction.SDR else scale
        cmd += ["-vf", vf]

    # ── Encodeur vidéo ────────────────────────────────────────────────────────
    # DV : copy flux vidéo DV intégralement
    # HDR10 : re-encode normal (enlève RPU automatiquement)
    #   Note: pour une conversion DV→HDR10 complète avec métadonnées,
    #   voir _extract_dv_to_hdr10_json() qui utilise dovi_tool
    # SDR : re-encode + tone-mapping vers SDR (CPU intensif)
    if preserve_video:
        cmd += ["-c:v", "copy"]
    else:
        is_av1 = (vid.action == VideoAction.ENCODE_AV1)
        if vid.action == VideoAction.ENCODE_HEVC:
            encoder, prof_str = platform.encoder_hevc, "main"
        elif is_av1:
            encoder, prof_str = platform.encoder_av1, "main"
        else:
            encoder, prof_str = platform.encoder_h264, "high"

        bufsize_k = max(vid.target_bitrate * 2 // 1000, 1)
        preset    = profile.get("preset_encoder", "medium")

        cmd += [
            "-c:v",      encoder,
            "-pix_fmt",  "yuv420p",
            "-b:v",      str(vid.target_bitrate),
            "-maxrate",  str(vid.target_bitrate),
            "-bufsize",  f"{bufsize_k}k",
        ]
        if not is_av1:
            cmd += ["-rc", "cbr"]
        cmd += [
            "-preset",   preset,
            "-profile:v", prof_str,
        ]

    # ── Mapping ───────────────────────────────────────────────────────────────
    cmd += ["-map", "0:v:0"]

    included_audio = [ad for ad in decision.audio if ad.action != AudioAction.EXCLUDE]
    for ad in included_audio:
        cmd += ["-map", f"0:a:{ad.track.index}"]

    sub_indices = decision.subtitle_indices
    if sub_indices is None:
        cmd += ["-map", "0:s?"]
    else:
        for si in sub_indices:
            cmd += ["-map", f"0:s:{si}"]

    # ── Encodage audio ────────────────────────────────────────────────────────
    for out_i, ad in enumerate(included_audio):
        if ad.action == AudioAction.COPY:
            cmd += [f"-c:a:{out_i}", "copy"]
        else:
            cmd += [
                f"-c:a:{out_i}", ad.output_codec,
                f"-b:a:{out_i}", str(ad.output_bitrate),
            ]
            if ad.output_codec == "aac":
                cmd += [f"-ar:{out_i}", "48000"]

    # ── Sous-titres ───────────────────────────────────────────────────────────
    has_subs = sub_indices is None or len(sub_indices) > 0
    if has_subs:
        if info.has_image_subs:
            cmd += ["-c:s", "copy"]
        else:
            cmd += ["-c:s", "mov_text"]

    cmd += ["-movflags", "+faststart"]
    cmd += ["-y", str(decision.output_path)]

    return cmd


# ─── Processus d'encodage ─────────────────────────────────────────────────────

class EncoderProcess:
    """Wraps un processus ffmpeg actif."""

    def __init__(self, cmd: list[str], duration: float = 0.0):
        self.cmd      = cmd
        self.duration = duration
        self._proc:   Optional[subprocess.Popen] = None
        self._paused  = False

    def start(self) -> None:
        self._proc = subprocess.Popen(
            self.cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def iter_lines(self) -> Iterator[str]:
        """Itère sur les lignes stderr ffmpeg (bloquant)."""
        if self._proc is None or self._proc.stderr is None:
            return
        for line in self._proc.stderr:
            yield line.rstrip()

    def iter_progress(self) -> Iterator[tuple[str, Optional[ProgressInfo]]]:
        """Itère en retournant (ligne_brute, ProgressInfo|None)."""
        for line in self.iter_lines():
            progress = parse_progress(line, self.duration)
            yield line, progress

    def pause(self) -> None:
        if self._proc and not self._paused:
            if _suspend_process(self._proc.pid):
                self._paused = True

    def resume(self) -> None:
        if self._proc and self._paused:
            if _resume_process(self._proc.pid):
                self._paused = False

    def terminate(self) -> None:
        if self._proc:
            self._proc.terminate()

    @property
    def returncode(self) -> Optional[int]:
        return self._proc.poll() if self._proc else None

    def wait(self) -> int:
        return self._proc.wait() if self._proc else -1
