"""
core/scanner.py — Analyse des fichiers vidéo via ffprobe.

Retourne des objets VideoInfo complets incluant pistes audio,
sous-titres et profil Dolby Vision.
"""
from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

_log = logging.getLogger("iris_encode.scanner")


SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({
    ".mp4", ".avi", ".mkv", ".mov", ".wmv",
    ".flv", ".webm", ".m4v", ".3gp",
})

_LOSSLESS_CODECS = frozenset({"truehd", "dts-hd ma", "dtshd", "mlp"})
_IMAGE_SUB_CODECS = frozenset({"hdmv_pgs_subtitle", "dvd_subtitle", "dvdsub", "pgssub"})
_COPY_COMPAT_CODECS = frozenset({"aac", "ac3", "eac3"})

# ── Chemin dovi_tool (singleton, settable par l'app au démarrage) ────────────
_dovi_path: Optional[Path] = None
_ffmpeg_path: str = "ffmpeg"


def set_dovi_path(path: Optional[Path]) -> None:
    """Active l'enrichissement DV au scan en fournissant le chemin dovi_tool."""
    global _dovi_path
    _dovi_path = path


def set_ffmpeg_path(path: str) -> None:
    """Précise l'exécutable ffmpeg à utiliser pour le probing (défaut: 'ffmpeg' du PATH)."""
    global _ffmpeg_path
    _ffmpeg_path = path


# ─── Modèles ──────────────────────────────────────────────────────────────────

@dataclass
class AudioTrack:
    index:    int
    codec:    str
    channels: int
    language: str   # ISO 639-2 ou ""
    title:    str
    bitrate:  int   # bps, 0 si inconnu

    @property
    def channel_layout(self) -> str:
        if self.channels == 1:  return "1.0"
        if self.channels == 2:  return "2.0"
        if self.channels == 6:  return "5.1"
        if self.channels == 8:  return "7.1"
        return f"{self.channels}ch"

    @property
    def is_lossless(self) -> bool:
        return self.codec.lower() in _LOSSLESS_CODECS

    @property
    def is_copy_compat(self) -> bool:
        return self.codec.lower() in _COPY_COMPAT_CODECS

    def display(self) -> str:
        lang = self.language or "?"
        return f"{self.codec} {self.channel_layout} {lang}"


@dataclass
class SubtitleTrack:
    index:    int
    codec:    str
    language: str

    @property
    def is_image_based(self) -> bool:
        return self.codec.lower() in _IMAGE_SUB_CODECS


@dataclass
class VideoInfo:
    path:            Path
    width:           int
    height:          int
    bitrate:         int          # bps
    codec:           str
    duration:        float        # secondes
    frame_count:     int          # 0 si inconnu
    dv_profile:      Optional[int]
    audio_tracks:    list[AudioTrack]    = field(default_factory=list)
    subtitle_tracks: list[SubtitleTrack] = field(default_factory=list)
    # ── Métadonnées Dolby Vision enrichies (dovi_tool, optionnel) ────────────
    dv_subprofile:   Optional[str]              = None   # "5", "7.06", "8.1"…
    hdr10_master_display: Optional[str]         = None   # G(...)B(...)R(...)WP(...)L(...)
    hdr10_max_cll:        Optional[tuple[int, int]] = None  # (MaxCLL, MaxFALL)

    # ── Propriétés dérivées ──────────────────────────────────────────────────

    @property
    def kbps(self) -> int:
        return self.bitrate // 1000

    @property
    def has_image_subs(self) -> bool:
        return any(s.is_image_based for s in self.subtitle_tracks)

    @property
    def is_already_encoded(self) -> bool:
        """Vrai si le fichier porte un suffixe _[hevc] ou _[H264]."""
        stem = self.path.stem
        return "_[hevc]" in stem or "_[H264]" in stem

    @property
    def resolution_label(self) -> str:
        if self.height >= 2160 or self.width >= 3840:
            return "4K"
        if self.height >= 1080 or self.width >= 1920:
            return "1080p"
        if self.height >= 720:
            return "720p"
        return f"{self.width}x{self.height}"

    @property
    def dv_label(self) -> str:
        if self.dv_profile is None:
            return "—"
        return f"DV:P{self.dv_profile}"


# ─── Helpers ffprobe ──────────────────────────────────────────────────────────

def _ffprobe_json(args: list[str]) -> dict:
    cmd = ["ffprobe", "-v", "error", "-print_format", "json"] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe: {r.stderr.strip()}")
    return json.loads(r.stdout)


def _safe_int(val: Any, default: int = 0) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ─── Détection Dolby Vision ───────────────────────────────────────────────────

def _detect_dv_profile(path: Path) -> Optional[int]:
    """
    Détecte le profil Dolby Vision via les side_data ffprobe.
    Retourne l'entier du profil (5, 7, 8…) ou None.
    """
    try:
        data = _ffprobe_json([
            "-select_streams", "v:0",
            "-show_entries",
            "stream_side_data=dv_profile:stream_tags=:stream=color_transfer",
            str(path),
        ])
        for stream in data.get("streams", []):
            for sd in stream.get("side_data_list", []):
                if "dv_profile" in sd:
                    return int(sd["dv_profile"])
    except Exception as e:
        _log.debug("dv_profile probe failed for %s: %s", path, e)
    return None


# ─── Scan principal ───────────────────────────────────────────────────────────

def scan(path: Path) -> VideoInfo:
    """Analyse complète d'un fichier vidéo."""
    data    = _ffprobe_json(["-show_streams", "-show_format", str(path)])
    streams = data.get("streams", [])
    fmt     = data.get("format", {})

    # ── Flux vidéo ────────────────────────────────────────────────────────────
    vid = next((s for s in streams if s.get("codec_type") == "video"), {})

    width  = _safe_int(vid.get("width"))
    height = _safe_int(vid.get("height"))
    codec  = vid.get("codec_name", "unknown")

    # Bitrate : stream en priorité, format en fallback
    bitrate = _safe_int(vid.get("bit_rate"))
    if bitrate == 0:
        bitrate = _safe_int(fmt.get("bit_rate"))
    if bitrate == 0:
        bitrate = 9_999_999   # inconnu → on suppose élevé (force re-encode)

    duration    = _safe_float(fmt.get("duration"))
    frame_count = _safe_int(vid.get("nb_frames"))

    # Estimation frame_count si absent (duration × fps)
    if frame_count == 0 and duration > 0:
        fps_str = vid.get("r_frame_rate", "0/1")
        try:
            num, den = fps_str.split("/")
            fps = float(num) / float(den)
            frame_count = int(duration * fps)
        except Exception:
            pass

    # ── Flux audio ────────────────────────────────────────────────────────────
    audio_tracks: list[AudioTrack] = []
    for i, s in enumerate(s for s in streams if s.get("codec_type") == "audio"):
        tags = s.get("tags", {})
        audio_tracks.append(AudioTrack(
            index=i,
            codec=s.get("codec_name", "unknown"),
            channels=_safe_int(s.get("channels"), 2),
            language=tags.get("language", ""),
            title=tags.get("title", ""),
            bitrate=_safe_int(s.get("bit_rate")),
        ))

    # ── Flux sous-titres ──────────────────────────────────────────────────────
    subtitle_tracks: list[SubtitleTrack] = []
    for i, s in enumerate(s for s in streams if s.get("codec_type") == "subtitle"):
        tags = s.get("tags", {})
        subtitle_tracks.append(SubtitleTrack(
            index=i,
            codec=s.get("codec_name", "unknown"),
            language=tags.get("language", ""),
        ))

    # ── Dolby Vision ──────────────────────────────────────────────────────────
    dv_profile = _detect_dv_profile(path)

    # Enrichissement DV via dovi_tool (sous-profil + master display + MaxCLL)
    dv_subprofile        = None
    hdr10_master_display = None
    hdr10_max_cll        = None
    if dv_profile is not None and _dovi_path is not None:
        try:
            from . import dovi
            extra = dovi.probe_file(path, _dovi_path, _ffmpeg_path)
            dv_subprofile        = extra.get("dv_subprofile")
            hdr10_master_display = extra.get("master_display")
            hdr10_max_cll        = extra.get("max_cll")
        except Exception as e:
            _log.debug("dovi probe failed for %s: %s", path, e)

    return VideoInfo(
        path=path,
        width=width,
        height=height,
        bitrate=bitrate,
        codec=codec,
        duration=duration,
        frame_count=frame_count,
        dv_profile=dv_profile,
        audio_tracks=audio_tracks,
        subtitle_tracks=subtitle_tracks,
        dv_subprofile=dv_subprofile,
        hdr10_master_display=hdr10_master_display,
        hdr10_max_cll=hdr10_max_cll,
    )


def scan_directory(directory: Path) -> list[VideoInfo]:
    """
    Scanne tous les fichiers vidéo supportés dans un répertoire (non récursif).
    Ignore les fichiers déjà encodés (_[hevc] / _[H264]).
    Les erreurs de scan sont silencieuses (fichier ignoré).
    """
    results: list[VideoInfo] = []
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        stem = path.stem
        if "_[hevc]" in stem or "_[H264]" in stem:
            continue
        try:
            results.append(scan(path))
        except Exception as e:
            _log.warning("scan failed for %s: %s", path, e)
    return results


def scan_directory_recursive(root: Path) -> list[VideoInfo]:
    """
    Scanne récursivement tous les fichiers vidéo sous root (tous niveaux).
    Même filtres que scan_directory : extensions supportées, pas d'encodés.
    Tri par chemin complet pour un ordre prévisible (saison → épisode).
    """
    results: list[VideoInfo] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        stem = path.stem
        if "_[hevc]" in stem or "_[H264]" in stem:
            continue
        try:
            results.append(scan(path))
        except Exception as e:
            _log.warning("scan failed for %s: %s", path, e)
    return results


def list_subdirs(directory: Path) -> list[Path]:
    """Liste les sous-répertoires (pour la navigation du browser)."""
    try:
        return sorted(p for p in directory.iterdir() if p.is_dir())
    except PermissionError:
        return []
