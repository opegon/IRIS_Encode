"""
core/decision.py — Logique métier encodage vidéo et audio.

Implémente les 4 cas de la spec (CAS 1/2/3/SKIP) et la politique
de sélection + transcodage des pistes audio.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional

from .profiles import Profile
from .scanner import AudioTrack, VideoInfo


# ─── Décision vidéo ───────────────────────────────────────────────────────────

class VideoAction(Enum):
    ENCODE_HEVC = auto()   # CAS 1 ou CAS 2
    ENCODE_H264 = auto()   # CAS 3
    ENCODE_AV1  = auto()   # Manuel uniquement (très gourmand CPU)
    SKIP        = auto()


class DVAction(Enum):
    NONE     = auto()   # pas de DV détecté
    STRIP    = auto()   # supprime RPU → HDR10
    PRESERVE = auto()   # copy sans modification
    SDR      = auto()   # tone map → SDR (P5, CPU, lent)


@dataclass
class VideoDecision:
    action:          VideoAction
    reason:          str
    target_bitrate:  int    # bps — 0 si SKIP
    target_width:    int
    target_height:   int
    dv_action:       DVAction
    output_suffix:   str    # "_[hevc]" | "_[H264]" | ""

    def label(self) -> str:
        if self.action == VideoAction.SKIP:
            return "← SKIP"
        codec = "HEVC" if self.action == VideoAction.ENCODE_HEVC else "H264"
        dv = ""
        if self.dv_action == DVAction.STRIP:    dv = " → HDR10"
        if self.dv_action == DVAction.PRESERVE: dv = " → DV"
        if self.dv_action == DVAction.SDR:      dv = " → SDR ⚠"
        return f"→ {codec}{dv}"

    def style(self) -> str:
        """Nom de style Rich pour la colonne Décision."""
        if self.action == VideoAction.SKIP:
            return "dim"
        if self.action == VideoAction.ENCODE_H264:
            return "cyan"
        if self.dv_action == DVAction.SDR:
            return "yellow"
        return "magenta"


# ─── Décision audio ───────────────────────────────────────────────────────────

class AudioAction(Enum):
    COPY      = auto()
    TRANSCODE = auto()
    EXCLUDE   = auto()


@dataclass
class AudioDecision:
    track:          AudioTrack
    action:         AudioAction
    reason:         str
    output_codec:   str   # "aac" | "ac3" | "copy" | ""
    output_bitrate: int   # bps, 0 si copy/exclude
    locked:         bool = False   # True = piste 0 (verrouillée par défaut)

    def display(self) -> str:
        if self.action == AudioAction.EXCLUDE:
            return ""
        if self.action == AudioAction.COPY:
            return f"→ copy"
        return f"→ {self.output_codec} {self.output_bitrate // 1000}k"


# ─── Décision globale ─────────────────────────────────────────────────────────

@dataclass
class VideoOverride:
    """Surcharge manuelle des paramètres vidéo depuis le TUI (par fichier)."""
    action:        Optional["VideoAction"]  = None
    bitrate:       Optional[int]            = None  # bps, None = conserver
    dv_action:     Optional["DVAction"]     = None
    delete_source: Optional[bool]           = None  # None = suivre profil


@dataclass
class TracksSelection:
    """Sélection manuelle audio + sous-titres + override vidéo depuis le TUI.
    launch=True : le browser lance l'encodage immédiatement après.
    """
    audio:          list[int]                 = field(default_factory=list)
    subtitles:      list[int]                 = field(default_factory=list)
    launch:         bool                      = False
    video_override: Optional["VideoOverride"] = None



@dataclass
class FileDecision:
    info:              VideoInfo
    profile:           Profile
    video:             VideoDecision
    audio:             list[AudioDecision]  = field(default_factory=list)
    subtitle_indices:       list[int] | None = None  # None = tout garder
    delete_source_override: bool | None      = None  # None = suivre profil

    @property
    def output_container(self) -> str:
        return ".mkv" if self.info.has_image_subs else ".mp4"

    @property
    def output_path(self) -> Path:
        stem   = self.info.path.stem
        suffix = self.video.output_suffix
        ext    = self.output_container
        return self.info.path.parent / f"{stem}{suffix}{ext}"

    @property
    def audio_summary(self) -> str:
        """Résumé des pistes conservées pour la colonne Audio du browser."""
        kept = [
            ad.track.display()
            for ad in self.audio
            if ad.action != AudioAction.EXCLUDE
        ]
        return "  ".join(kept) if kept else "—"


# ─── Logique vidéo ────────────────────────────────────────────────────────────

def _resolve_limits(info: VideoInfo, profile: Profile) -> tuple[int, int, str]:
    """Retourne (limit_w, limit_h, label) selon résolution source et profil."""
    keep_4k = profile.get("keep_4k", False)
    is_4k   = info.height >= 2160 or info.width >= 3840
    is_1080 = info.height >= 1080 or info.width >= 1920

    if is_4k or is_1080:
        if keep_4k:
            return info.width, info.height, f"Original {info.width}x{info.height}"
        return 1920, 1080, "1080p"

    return 1280, 720, "720p"


def _decide_dv(info: VideoInfo, profile: Profile) -> DVAction:
    if info.dv_profile is None:
        return DVAction.NONE
    opt = profile.get("dolby_vision", "strip")
    if opt == "preserve":
        return DVAction.PRESERVE
    if opt == "sdr":
        return DVAction.SDR
    return DVAction.STRIP


def decide_video(info: VideoInfo, profile: Profile) -> VideoDecision:
    """Applique les 4 cas de la spec et retourne la décision vidéo."""
    target_bps            = profile.bitrate_for_height(info.height)
    limit_w, limit_h, _  = _resolve_limits(info, profile)
    dv_action             = _decide_dv(info, profile)

    # CAS 1 — Bitrate source ≥ seuil cible
    if info.bitrate >= target_bps:
        return VideoDecision(
            action=VideoAction.ENCODE_HEVC,
            reason=f"Débit {info.kbps}k ≥ {target_bps // 1000}k cible",
            target_bitrate=target_bps,
            target_width=limit_w,
            target_height=limit_h,
            dv_action=dv_action,
            output_suffix="_[hevc]",
        )

    # CAS 2 — Résolution trop grande (débit OK)
    if info.width > limit_w or info.height > limit_h:
        return VideoDecision(
            action=VideoAction.ENCODE_HEVC,
            reason=f"Résolution {info.width}x{info.height} > {limit_w}x{limit_h}",
            target_bitrate=info.bitrate,
            target_width=limit_w,
            target_height=limit_h,
            dv_action=dv_action,
            output_suffix="_[hevc]",
        )

    # CAS 3 — Codec non-standard sur source < 1080p
    if info.height < 1080 and info.codec not in {"h264", "hevc"}:
        return VideoDecision(
            action=VideoAction.ENCODE_H264,
            reason=f"Codec non-standard ({info.codec}), résolution < 1080p",
            target_bitrate=info.bitrate,
            target_width=info.width,
            target_height=info.height,
            dv_action=dv_action,
            output_suffix="_[H264]",
        )

    # SKIP
    return VideoDecision(
        action=VideoAction.SKIP,
        reason=f"Débit OK, résolution OK, codec {info.codec}",
        target_bitrate=0,
        target_width=info.width,
        target_height=info.height,
        dv_action=dv_action,
        output_suffix="",
    )


# ─── Logique audio ────────────────────────────────────────────────────────────

def _transcode_spec(track: AudioTrack, profile: Profile) -> tuple[str, int]:
    """Retourne (codec_sortie, bitrate_bps) pour une piste à transcoder."""
    ch = track.channels
    if ch == 1:
        return "aac", 64_000
    if ch == 2:
        return "aac", profile.get("audio_stereo_kbps", 192) * 1000
    if ch <= 6:
        return "ac3", profile.get("audio_surround_kbps", 448) * 1000
    return "ac3", profile.get("audio_surround_7_1_kbps", 640) * 1000


def decide_audio(
    info: VideoInfo,
    profile: Profile,
    override_selected: Optional[list[int]] = None,
) -> list[AudioDecision]:
    """
    Calcule la décision pour chaque piste audio.
    override_selected : liste d'indices (override TUI) ; None = règle automatique.
    """
    languages    = profile.get("audio_languages", ["fre", "eng"])
    preserve_hd  = profile.get("preserve_hd_audio", False)
    copy_compat  = profile.get("audio_copy_compatible", True)
    decisions:   list[AudioDecision] = []

    for i, track in enumerate(info.audio_tracks):
        # ── Sélection ────────────────────────────────────────────────────────
        if override_selected is not None:
            included = i in override_selected
            reason   = "sélection manuelle" if included else "exclu manuellement"
        elif i == 0:
            included = True
            reason   = "piste originale (index 0)"
        elif track.language in languages:
            included = True
            reason   = f"langue {track.language}"
        else:
            included = False
            reason   = f"langue {track.language or '?'} non retenue"

        if not included:
            decisions.append(AudioDecision(
                track=track, action=AudioAction.EXCLUDE, reason=reason,
                output_codec="", output_bitrate=0, locked=(i == 0),
            ))
            continue

        codec_lc = track.codec.lower()

        # ── Transcodage ───────────────────────────────────────────────────────
        if track.is_lossless:
            if preserve_hd:
                decisions.append(AudioDecision(
                    track=track, action=AudioAction.COPY,
                    reason=f"{reason} · lossless + preserve_hd_audio → copy",
                    output_codec="copy", output_bitrate=0, locked=(i == 0),
                ))
                continue
            out_codec, out_br = _transcode_spec(track, profile)
            decisions.append(AudioDecision(
                track=track, action=AudioAction.TRANSCODE,
                reason=f"{reason} · lossless → {out_codec}",
                output_codec=out_codec, output_bitrate=out_br, locked=(i == 0),
            ))
            continue

        if copy_compat and track.is_copy_compat:
            decisions.append(AudioDecision(
                track=track, action=AudioAction.COPY,
                reason=f"{reason} · {codec_lc} compatible → copy",
                output_codec="copy", output_bitrate=0, locked=(i == 0),
            ))
            continue

        out_codec, out_br = _transcode_spec(track, profile)
        decisions.append(AudioDecision(
            track=track, action=AudioAction.TRANSCODE,
            reason=f"{reason} · → {out_codec}",
            output_codec=out_codec, output_bitrate=out_br, locked=(i == 0),
        ))

    return decisions


# ─── Point d'entrée ───────────────────────────────────────────────────────────

def decide(
    info:               VideoInfo,
    profile:            Profile,
    override_audio:     Optional[list[int]] = None,
    override_subtitles: Optional[list[int]] = None,
) -> FileDecision:
    """Calcule la décision complète pour un fichier."""
    video = decide_video(info, profile)
    audio = decide_audio(info, profile, override_audio)
    return FileDecision(
        info=info, profile=profile, video=video, audio=audio,
        subtitle_indices=override_subtitles,
    )
