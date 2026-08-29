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

# Le mode HDR10 « quality » encode sur processeur, quelle que soit la machine :
# les métadonnées statiques que réclame la compatibilité TV passent par
# `-x265-params`, que les encodeurs matériels n'exposent pas. Nommé ici parce
# que le sondage du lancement doit l'inclure — un encodeur jamais sondé est
# tenu pour absent, et le profil devient inutilisable sur toute machine à GPU.
ENCODEUR_HDR10_QUALITY = "libx265"


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

def build_audio_command(source: Path, output: Path, audio: list,
                        ffmpeg_path: str = "ffmpeg") -> list[str]:
    """Reconstruit les pistes audio d'un fichier, sans toucher à la vidéo.

    Le retrait du Dolby Vision remuxe un flux HEVC intact : mkvmerge y recopie
    les pistes de la source telles quelles, et ne sait ni transcoder ni
    retitrer. Les pistes finales sont donc produites à part, dans un Matroska
    audio que le remux prend comme seconde entrée.

    Les pistes déjà au bon format sont recopiées, pas réencodées — l'étape ne
    coûte que ce que la décision demande vraiment.
    """
    gardees = [ad for ad in audio if ad.action != AudioAction.EXCLUDE]
    cmd = [ffmpeg_path, "-y", "-loglevel", "error", "-i", str(source),
           "-vn", "-sn", "-dn"]
    for ad in gardees:
        cmd += ["-map", f"0:a:{ad.track.index}"]
    cmd += audio_args(gardees)
    cmd += [str(output)]
    return cmd


def pistes_audio_vides(sortie: Path, duree_attendue: float) -> list[str]:
    """Pistes audio du fichier produit qui ne contiennent manifestement rien.

    Le défaut décrit dans `audio_prepass_needed` ne lève aucune erreur et rend
    un code de retour nul : sans cette vérification, un fichier amputé d'une
    piste passe pour un succès. La parade couvre le cas connu ; ce filet couvre
    ceux qu'on ne connaît pas encore.

    Le seuil est volontairement grossier — un dixième de la durée attendue.
    Il ne s'agit pas de mesurer une piste, mais de distinguer « 54 millisecondes
    au lieu de trois heures et demie » de tout ce qui est légitime, y compris
    une piste de commentaires écourtée.
    """
    from .scanner import _ffprobe_json

    if duree_attendue <= 0:
        return []
    try:
        data = _ffprobe_json(["-show_streams", "-select_streams", "a", str(sortie)])
    except Exception:
        return []                      # ne jamais faire échouer sur le filet

    vides: list[str] = []
    for flux in data.get("streams", []):
        tags  = flux.get("tags", {}) or {}
        duree = _duree_secondes(flux.get("duration") or tags.get("DURATION"))
        if duree is not None and duree < duree_attendue / 10:
            nom = tags.get("title") or tags.get("language") or f"a:{flux.get('index')}"
            vides.append(f"{nom} ({flux.get('codec_name', '?')}, {duree:.2f} s)")
    return vides


def _duree_secondes(valeur) -> Optional[float]:
    """Lit « 3600.5 » ou « 03:35:23.244000000 ». None si illisible."""
    if not valeur:
        return None
    texte = str(valeur)
    try:
        if ":" in texte:
            h, m, sec = texte.split(":")
            return int(h) * 3600 + int(m) * 60 + float(sec)
        return float(texte)
    except (ValueError, TypeError):
        return None


def audio_prepass_needed(decision) -> bool:
    """Vrai si l'audio doit être produite **avant** la passe d'encodage.

    Défaut ffmpeg mesuré le 2026-08-28, reproductible : quand une même
    invocation décode une piste audio sans perte **et** mappe un flux de
    sous-titres dont le premier repère arrive tardivement, la piste transcodée
    n'est pas écrite. Deux trames sortent, puis plus rien, sans un mot d'erreur
    et avec un code de retour nul.

    Mesuré sur un film dont les sous-titres « forced » n'ouvrent qu'à 6 min 20 :
    1 875 paquets attendus sur 60 s, **2** produits.

    **C'est la simultanéité, pas la sortie.** Écrire l'audio dans son propre
    fichier ne la sauve pas ; isoler le sous-titre dans le sien non plus. Il
    suffit que le sous-titre soit *mappé* quelque part dans l'invocation. En
    revanche, un sous-titre présent dans l'entrée mais non mappé est sans
    effet, et un **appel ffmpeg distinct** produit la piste entière.

    Autres facteurs éliminés par mesure : le codec de sortie (l'AC3 meurt comme
    l'E-AC3), les drapeaux de piste, la recopie contre le réencodage du
    sous-titre, la durée, l'encodage matériel, et six réglages de muxeur —
    `max_muxing_queue_size`, `max_interleave_delta`, `avoid_negative_ts`,
    `copyts`, `muxdelay`, l'ordre des `-map`. Transcoder l'AC3 de la même
    source, au lieu du TrueHD, sort indemne.

    La parade est donc nécessairement un **processus séparé** : aucune
    disposition des sorties n'y suffit. C'est ce que fait déjà le retrait du
    Dolby Vision, pour une autre raison.

    **La source décodée doit être sans perte.** Transcoder l'AC3 du même fichier,
    au lieu du TrueHD, sort indemne — c'est mesuré. La passe n'est donc payée
    que sur les pistes TrueHD, MLP et DTS-HD MA, et non sur tout transcodage.

    Cette restriction repose sur deux mesures : un codec sans perte qui échoue,
    un codec avec perte qui passe. Elle n'est pas une loi. `pistes_audio_vides`
    est le filet : si le cas se présente hors de ce périmètre, l'encodage
    échoue bruyamment au lieu de rendre un fichier amputé.
    """
    if not decision.subtitles_finales:
        return False
    return any(ad.action == AudioAction.TRANSCODE and ad.track.is_lossless
               for ad in decision.audio)


def audio_pass_needed(audio: list) -> bool:
    """Vrai si la décision audio demande autre chose qu'une recopie à l'identique.

    Une exclusion seule ne justifie pas cette passe : mkvmerge sait ne pas
    prendre une piste. Un transcodage, si — et il entraîne avec lui le
    retitrage, qui n'a de sens que sur la piste transcodée.
    """
    return any(ad.action == AudioAction.TRANSCODE for ad in audio)


def audio_args(included_audio: list) -> list[str]:
    """Arguments ffmpeg des pistes audio retenues, dans leur ordre de sortie.

    Partagé par l'encodage et par le chemin de retrait du Dolby Vision, qui
    doit produire exactement les mêmes pistes sans toucher à la vidéo.
    """
    args: list[str] = []
    for out_i, ad in enumerate(included_audio):
        if ad.action == AudioAction.COPY:
            args += [f"-c:a:{out_i}", "copy"]
            continue
        args += [
            f"-c:a:{out_i}", ad.output_codec,
            f"-b:a:{out_i}", str(ad.output_bitrate),
        ]
        # ffmpeg replierait le 7.1 de lui-même, l'encodeur ac3/eac3 ne
        # connaissant que jusqu'au 5.1 ; l'écrire rend la commande
        # affichée conforme à ce qui sort.
        if ad.output_channels:
            args += [f"-ac:a:{out_i}", str(ad.output_channels)]
        if ad.output_codec == "aac":
            # `-ar:a:{i}`, pas `-ar:{i}` : un spécificateur nu désigne le flux
            # de sortie n° i **tous types confondus**. Comme `build_command` et
            # `build_strip_remux_mp4` mappent la vidéo en premier, `-ar:0`
            # visait la vidéo — ignoré — et `-ar:1` la première piste audio,
            # alors qu'il était écrit pour la seconde. Le forçage à 48 kHz
            # tombait donc systématiquement d'un cran, sans rien signaler.
            # Toutes les options voisines emploient déjà la forme par type.
            args += [f"-ar:a:{out_i}", "48000"]
        # Le titre de piste survit au transcodage : sans réécriture, un
        # « TrueHD 5.1 » resterait affiché sur une piste E-AC3.
        titre = ad.output_title
        if titre:
            args += [f"-metadata:s:a:{out_i}", f"title={titre}"]
    return args


def build_command(
    decision: FileDecision,
    platform: PlatformProfile,
    audio_source: Path | None = None,
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
    from .muxer import TrackKind, ffmpeg_stream_index, premux_track_order

    ext_tracks = decision.external_tracks
    # Après un mux préalable, les pistes greffées ne sont plus des entrées à
    # part : elles sont déjà dans l'intermédiaire, à la suite de celles de la
    # source. Elles restent entièrement à mapper — les oublier rend un fichier
    # amputé de la piste que le mux venait d'y poser, sans un mot d'erreur et
    # avec un code de retour nul.
    premux_tracks = premux_track_order(decision.premuxed_tracks)
    stretched     = [t for t in ext_tracks if t.stretch]
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

    # Les pistes audio produites à part (voir `audio_prepass_needed`). Posée
    # en dernier : les index des donneurs ne bougent pas.
    if audio_source is not None:
        cmd += ["-i", str(audio_source)]

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
            "-c:v",         ENCODEUR_HDR10_QUALITY,
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
    audio_input = len(ext_tracks) + 1 if audio_source is not None else 0
    for n, ad in enumerate(included_audio):
        # L'entrée dédiée ne contient QUE les pistes retenues, dans l'ordre :
        # on la parcourt par rang, pas par index de source.
        cmd += ["-map", f"{audio_input}:a:{n if audio_source is not None else ad.track.index}"]

    # L'intermédiaire porte la source entière — mkvmerge n'en écarte aucune
    # piste — puis les greffées : leur index part donc du nombre de pistes
    # audio de la source, quelles que soient celles que la décision garde.
    premux_audio = [t for t in premux_tracks if t.kind == TrackKind.AUDIO]
    for j in range(len(premux_audio)):
        cmd += ["-map", f"0:a:{len(info.audio_tracks) + j}"]

    # Un profil en `container = "mp4"` écarte les sous-titres image, que le
    # MP4 ne porte pas — jamais en silence : la décision les liste, et si ce
    # sont les seuls du fichier, c'est le conteneur qui cède, pas eux.
    ecartes = {st.index for st in decision.sous_titres_ecartes}
    sub_indices = decision.subtitle_indices
    premux_subs = [t for t in premux_tracks if t.kind != TrackKind.AUDIO]
    if sub_indices is None and not ecartes:
        # `0:s?` prend tout l'intermédiaire, greffées comprises : les mapper
        # une seconde fois les livrerait en double.
        cmd += ["-map", "0:s?"]
        n_src_subs = len(info.subtitle_tracks)
    else:
        gardes = [st.index for st in decision.subtitles_finales]
        for si in gardes:
            cmd += ["-map", f"0:s:{si}"]
        n_src_subs = len(gardes)
        for j in range(len(premux_subs)):
            cmd += ["-map", f"0:s:{len(info.subtitle_tracks) + j}"]

    # Pistes externes. Le donneur entre en entier : mapper son flux `:0`
    # supposait qu'il n'en porte qu'un — vrai d'un .srt nu, faux d'un
    # conteneur. Un donneur à six pistes de sous-titres rendait toujours la
    # première, quelle que soit celle choisie, pendant que la langue et le
    # titre venaient de la bonne. La piste apparaissait donc au lecteur,
    # correctement nommée, et n'affichait rien — la première d'un rip est en
    # général la piste « forced », vingt-trois répliques sur un épisode.
    for n, ext in enumerate(ext_tracks, start=1):
        stream = "a" if ext.kind == TrackKind.AUDIO else "s"
        idx    = ffmpeg_stream_index(ext.source_path, ext.source_tid, ext.kind)
        cmd += ["-map", f"{n}:{stream}:{idx}"]

    # ── Encodage audio ────────────────────────────────────────────────────────
    if audio_source is not None:
        # Tout a été fait dans la passe précédente — et une piste recopiée
        # traverse ce que le transcodage ne traversait pas.
        for n in range(len(included_audio)):
            cmd += [f"-c:a:{n}", "copy"]
    else:
        cmd += audio_args(included_audio)

    # ── Pistes externes : copie, langue, nom, drapeaux ────────────────────────
    # Qu'elles soient entrées par mkvmerge ou par ffmpeg, les pistes greffées
    # se recopient, se nomment et se marquent pareil — et les deux listes
    # s'excluent : le mux préalable vide `external_tracks`.
    ext_audio = [t for t in ext_tracks if t.kind == TrackKind.AUDIO] + premux_audio
    ext_subs  = [t for t in ext_tracks if t.kind != TrackKind.AUDIO] + premux_subs

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
