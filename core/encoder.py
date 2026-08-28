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

# Chemin de ffmpeg, posé au démarrage. Même raison que pour ffprobe : le
# preflight installe les binaires dans ./bin/ sans toucher au PATH, et les
# appeler par leur nom nu ferait échouer tout encodage sur une installation
# neuve.
_ffmpeg_path: str = "ffmpeg"


def set_ffmpeg_path(path: str) -> None:
    """Précise l'exécutable ffmpeg (défaut : celui du PATH)."""
    global _ffmpeg_path
    _ffmpeg_path = path


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


def _seconds_to_time(seconds: float) -> str:
    """Convertit des secondes en "HH:MM:SS"."""
    if seconds <= 0:
        return "0:00:00"
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h}:{m:02d}:{sec:02d}"


@dataclass
class ProgressInfo:
    frame:    int
    fps:      float
    elapsed:  float   # secondes encodées
    bitrate:  float   # kbits/s
    speed:    float   # x réel (ex: 3.71x)
    percent:  float   # 0.0–1.0, -1 si inconnu
    duration: float   # durée totale du fichier (secondes)

    @property
    def remaining(self) -> float:
        """Temps restant estimé en secondes (basé sur speed)."""
        if self.speed <= 0 or self.duration <= 0:
            return 0.0
        remaining_duration = self.duration - self.elapsed
        return max(0.0, remaining_duration / self.speed)

    def format_remaining(self) -> str:
        """Formate le temps restant comme 'HH:MM:SS'."""
        return _seconds_to_time(self.remaining)

    def format_elapsed(self) -> str:
        """Formate le temps écoulé comme 'HH:MM:SS'."""
        return _seconds_to_time(self.elapsed)


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
        duration=total_duration,
    )


# ─── Diagnostic d'un échec ────────────────────────────────────────────────────
#
# ffmpeg annonce la cause puis constate l'échec : « No capable devices found »,
# puis « Error opening output files: Invalid argument ». L'écran ne gardait que
# la dernière ligne, c'est-à-dire la seule qui n'apprend rien. Chaque entrée
# ci-dessous a été reproduite avant d'être ajoutée.
#
# (signature dans la sortie ffmpeg, message rendu à l'utilisateur)
_CAUSES: tuple[tuple[str, str], ...] = (
    ("no capable devices found",
     "Cette carte graphique ne sait pas encoder ce format. L'AV1 par NVENC "
     "demande une RTX 40 ou plus récente ; le HEVC et le H264 restent "
     "disponibles."),
    ("could not open encoder",
     "L'encodeur n'a pas pu s'ouvrir sur cette machine. Si c'est de l'AV1 : "
     "NVENC ne l'encode qu'à partir des RTX 40."),
    ("cannot load nvcuda",
     "Le pilote NVIDIA est introuvable. Sans lui, aucun encodage accéléré "
     "n'est possible."),
    ("invalid bit rate",
     "Le débit demandé sort de ce que l'encodeur accepte. Choisissez une "
     "valeur dans la plage qu'il annonce."),
    ("is not supported by the",
     "L'encodeur choisi ne prend pas cette disposition de canaux ou ce format "
     "de pixels."),
    ("no space left on device",
     "Le disque de destination est plein."),
    ("permission denied",
     "Écriture refusée à cet emplacement."),
)


def encodeur_de(cmd: list[str]) -> Optional[str]:
    """Encodeur vidéo d'une commande construite, ou None."""
    try:
        return cmd[cmd.index("-c:v") + 1]
    except (ValueError, IndexError):
        return None


def diagnostiquer(lignes: list[str]) -> Optional[str]:
    """Cause lisible d'un échec, cherchée dans toute la sortie de ffmpeg.

    Retourne None si rien de connu n'y figure : l'appelant retombe alors sur
    la dernière ligne, faute de mieux.
    """
    texte = "\n".join(lignes).lower()
    for signature, message in _CAUSES:
        if signature in texte:
            return message
    return None


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

    # Ni l'un ni l'autre ne passe par ffmpeg : SKIP ne fait rien, et le retrait
    # du RPU est un remux (dovi_tool + mkvmerge), pas un encodage.
    if vid.action in (VideoAction.SKIP, VideoAction.STRIP_DV):
        return []

    # Garde-fou : ne JAMAIS écraser le fichier source
    if decision.output_path.resolve() == info.path.resolve():
        raise ValueError(
            f"Chemin de sortie identique à la source ({info.path}). "
            f"Suffixe vide et conteneur identique — encodage refusé pour éviter "
            f"la corruption du fichier source."
        )

    cmd: list[str] = [_ffmpeg_path]

    # hwaccel — absent pour :
    #   - SDR tone map (CPU obligatoire pour zscale)
    #   - DV preserve (copy)
    #   - HDR10 quality (libx265 CPU pour metadata propres)
    preserve_video      = (vid.dv_action == DVAction.DV)
    hdr10_quality_check = (
        vid.dv_action == DVAction.HDR10
        and vid.action == VideoAction.ENCODE_HEVC
        and profile.get("hdr10_quality") == "quality"
    )
    use_hwaccel = (
        platform.hwaccel
        and vid.dv_action != DVAction.SDR
        and not preserve_video
        and not hdr10_quality_check
    )
    if use_hwaccel:
        cmd += ["-hwaccel", platform.hwaccel]

    # Après un mux préalable, l'entrée est l'intermédiaire, pas la source.
    # `info.path` reste la source : c'est d'elle que dépend le nom de sortie.
    cmd += ["-i", str(decision.encode_source or info.path)]

    # ── Entrées supplémentaires : pistes externes greffées ────────────────────
    # ffmpeg les absorbe dans la même passe que l'encodage : inutile de muxer
    # séparément quand le fichier est de toute façon réencodé.
    ext_tracks = decision.external_tracks
    stretched  = [t for t in ext_tracks if t.stretch]
    if stretched:
        # Le mux préalable est censé avoir absorbé ces pistes en amont : y
        # arriver ici signifie qu'il n'a pas eu lieu, faute de mkvmerge.
        raise ValueError(
            f"La piste « {stretched[0].source_path.name} » demande un facteur "
            f"d'étirement, que ffmpeg ne sait pas appliquer en une passe "
            f"(-itsoffset ne fait qu'un décalage constant). mkvmerge sait le "
            f"faire : installez-le pour que la greffe passe par lui."
        )
    for ext in ext_tracks:
        if ext.delay_ms > 0:
            cmd += ["-itsoffset", f"{ext.delay_ms / 1000:.3f}"]
        elif ext.delay_ms < 0:
            # Un -itsoffset négatif rend négatifs les horodatages du donneur.
            # ffmpeg refuse de les écrire tels quels et décale TOUT le fichier
            # vers l'avant : la vidéo ne commence alors plus à zéro (mesuré :
            # start_time = 2.5 s pour un décalage de -2500 ms). Les lecteurs
            # de bureau normalisent, les décodeurs matériels de téléviseur pas
            # toujours — d'où des fichiers illisibles sur TV.
            # Sauter le début du donneur donne le même résultat sans jamais
            # produire d'horodatage négatif.
            cmd += ["-ss", f"{-ext.delay_ms / 1000:.3f}"]
        cmd += ["-i", str(ext.source_path)]

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
    # DV : copy flux vidéo DV intégralement (preserve_video)
    # HDR10 compat : re-encode NVENC standard (supprime RPU, pas de metadata HDR10 fines)
    # HDR10 quality : libx265 CPU + master-display + max-cll → compatibilité TV LG
    # SDR : re-encode + tone-mapping vers SDR (CPU intensif)
    hdr10_quality = (
        vid.dv_action == DVAction.HDR10
        and vid.action == VideoAction.ENCODE_HEVC
        and profile.get("hdr10_quality") == "quality"
    )

    if preserve_video:
        cmd += ["-c:v", "copy"]
    elif hdr10_quality:
        # Mode CPU/libx265 avec métadonnées HDR10 statiques injectées
        bufsize_k = max(vid.target_bitrate * 2 // 1000, 1)
        preset    = profile.get("preset_encoder", "medium")
        from . import dovi
        x265_params = dovi.make_x265_hdr_params(
            master_display=info.hdr10_master_display,
            max_cll=info.hdr10_max_cll,
        )
        cmd += [
            "-c:v",         "libx265",
            "-pix_fmt",     "yuv420p10le",
            "-b:v",         str(vid.target_bitrate),
            "-maxrate",     str(vid.target_bitrate),
            "-bufsize",     f"{bufsize_k}k",
            "-preset",      preset,
            "-profile:v",   "main10",
            "-x265-params", dovi.x265_params_string(x265_params),
        ]
    else:
        is_av1 = (vid.action == VideoAction.ENCODE_AV1)
        if vid.action == VideoAction.ENCODE_HEVC:
            encoder, prof_str = platform.encoder_hevc, "main"
        elif is_av1:
            encoder, prof_str = platform.encoder_av1, "main"
        else:
            encoder, prof_str = platform.encoder_h264, "high"

        # Une sortie HDR10 en 8 bits, c'est du banding garanti dans les
        # dégradés : la courbe PQ étale 10 bits de source sur 256 niveaux.
        # HEVC et AV1 savent encoder en 10 bits, H264 non (pas de main10 chez
        # NVENC) — une source HDR ramenée en H264 reste donc en 8 bits, et
        # cela ne concerne que les cibles sous 1080p.
        hdr10_out = (
            vid.dv_action == DVAction.HDR10
            or (info.is_hdr and vid.dv_action != DVAction.SDR)
        )
        pix_fmt = "yuv420p"
        if hdr10_out and vid.action in (VideoAction.ENCODE_HEVC,
                                        VideoAction.ENCODE_AV1):
            pix_fmt  = "yuv420p10le"
            if not is_av1:
                prof_str = "main10"

        # Un `-maxrate` égal à la cible fait du débit demandé un plafond que
        # rien ne peut compenser : chaque scène facile tire la moyenne vers le
        # bas, aucune scène difficile ne peut la remonter. Mesuré sur un film
        # en prises de vues réelles, la cible n'était honorée qu'à 92 % ; avec
        # 50 % de marge en VBR, 99 %. La marge ne gonfle pas les fichiers
        # faciles : NVENC ne dépense que ce que le contenu exige.
        maxrate   = vid.target_bitrate * 3 // 2
        bufsize_k = max(maxrate * 2 // 1000, 1)
        preset    = profile.get("preset_encoder", "medium")

        cmd += [
            "-c:v",      encoder,
            "-pix_fmt",  pix_fmt,
            "-b:v",      str(vid.target_bitrate),
            "-maxrate",  str(maxrate),
            "-bufsize",  f"{bufsize_k}k",
        ]
        if not is_av1:
            cmd += ["-rc", "vbr"]
        cmd += ["-preset", preset]
        # `av1_nvenc` n'expose aucune option `profile` : lui en passer une fait
        # échouer la commande avant même que la carte soit interrogée —
        # « Unable to parse "profile" option value ». L'AV1 était donc cassé
        # sur toute machine, capable ou non.
        if not is_av1:
            cmd += ["-profile:v", prof_str]

    # ── Mapping ───────────────────────────────────────────────────────────────
    cmd += ["-map", "0:v:0"]

    included_audio = [ad for ad in decision.audio if ad.action != AudioAction.EXCLUDE]
    for ad in included_audio:
        cmd += ["-map", f"0:a:{ad.track.index}"]

    # Un profil en `container = "mp4"` écarte les sous-titres image, que le
    # MP4 ne porte pas — jamais en silence : la décision les liste, et si ce
    # sont les seuls du fichier, c'est le conteneur qui cède, pas eux.
    ecartes = {st.index for st in decision.sous_titres_ecartes}
    sub_indices = decision.subtitle_indices
    if sub_indices is None and not ecartes:
        cmd += ["-map", "0:s?"]
        n_src_subs = len(info.subtitle_tracks)
    else:
        gardes = [st.index for st in decision.subtitles_finales]
        for si in gardes:
            cmd += ["-map", f"0:s:{si}"]
        n_src_subs = len(gardes)

    # Pistes externes : chacune est l'unique flux utile de son entrée
    from .muxer import TrackKind
    for n, ext in enumerate(ext_tracks, start=1):
        stream = "a" if ext.kind == TrackKind.AUDIO else "s"
        cmd += ["-map", f"{n}:{stream}:0"]

    # ── Encodage audio ────────────────────────────────────────────────────────
    for out_i, ad in enumerate(included_audio):
        if ad.action == AudioAction.COPY:
            cmd += [f"-c:a:{out_i}", "copy"]
        else:
            cmd += [
                f"-c:a:{out_i}", ad.output_codec,
                f"-b:a:{out_i}", str(ad.output_bitrate),
            ]
            # ffmpeg replierait le 7.1 de lui-même, l'encodeur ac3/eac3 ne
            # connaissant que jusqu'au 5.1 ; l'écrire rend la commande
            # affichée conforme à ce qui sort.
            if ad.output_channels:
                cmd += [f"-ac:a:{out_i}", str(ad.output_channels)]
            if ad.output_codec == "aac":
                cmd += [f"-ar:{out_i}", "48000"]
            # Le titre de piste survit au transcodage : sans réécriture, un
            # « TrueHD 5.1 » resterait affiché sur une piste E-AC3.
            titre = ad.output_title
            if titre:
                cmd += [f"-metadata:s:a:{out_i}", f"title={titre}"]

    # ── Pistes externes : copie, langue, nom, drapeaux ────────────────────────
    ext_audio = [t for t in ext_tracks if t.kind == TrackKind.AUDIO]
    ext_subs  = [t for t in ext_tracks if t.kind != TrackKind.AUDIO]

    # Une piste externe marquée « défaut » retire le drapeau des pistes source
    if any(t.is_default for t in ext_audio):
        for out_i in range(len(included_audio)):
            cmd += [f"-disposition:a:{out_i}", "0"]

    for j, ext in enumerate(ext_audio):
        out_i = len(included_audio) + j
        cmd += [f"-c:a:{out_i}", "copy"]
        cmd += [f"-metadata:s:a:{out_i}", f"language={ext.language}"]
        if ext.track_name:
            cmd += [f"-metadata:s:a:{out_i}", f"title={ext.track_name}"]
        flags = [f for f, on in (("default", ext.is_default),
                                 ("forced", ext.is_forced)) if on]
        cmd += [f"-disposition:a:{out_i}", "+".join(flags) if flags else "0"]

    for j, ext in enumerate(ext_subs):
        out_i = n_src_subs + j
        cmd += [f"-metadata:s:s:{out_i}", f"language={ext.language}"]
        if ext.track_name:
            cmd += [f"-metadata:s:s:{out_i}", f"title={ext.track_name}"]
        flags = [f for f, on in (("default", ext.is_default),
                                 ("forced", ext.is_forced)) if on]
        cmd += [f"-disposition:s:{out_i}", "+".join(flags) if flags else "0"]

    # ── Sous-titres ───────────────────────────────────────────────────────────
    container = decision.output_container
    has_subs  = (sub_indices is None or len(sub_indices) > 0) or bool(ext_subs)
    if has_subs:
        # Le conteneur découle déjà des pistes conservées : s'il sort en MP4,
        # c'est qu'aucun sous-titre image n'est gardé, donc mov_text convient.
        cmd += ["-c:s", "copy" if container == ".mkv" else "mov_text"]

    # faststart est un réglage MP4 ; ffmpeg l'ignore en avertissant sur MKV
    if container == ".mp4":
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
        # Voir scanner._ffprobe_json : lire dans l'encodage local
        # tue le thread de lecture dès qu'un nom de fichier en sort.
            encoding="utf-8",
            errors="replace",
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
