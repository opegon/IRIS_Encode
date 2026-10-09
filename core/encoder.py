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
from .i18n import N_, ErreurAffichable, _
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
# Le désentrelacement (IE-122) : bwdif, une image par image — la cadence de la
# source, donc le même débit cible. `deint=interlaced` ne touche que les images
# que le flux marque entrelacées : un passage progressif d'une source mixte
# reste intact. `parity=auto` suit l'ordre des trames que le flux déclare.
FILTRE_DESENTRELACEMENT = "bwdif=mode=send_frame:parity=auto:deint=interlaced"

_SDR_TONEMAP_FILTER = (
    "zscale=t=linear:npl=100,"
    "format=gbrpf32le,"
    "zscale=p=bt709,"
    "tonemap=tonemap=hable:desat=0,"
    "zscale=t=bt709:m=bt709:r=tv,"
    "format=yuv420p"
)

# Regex pour parser la ligne de progression ffmpeg. `frame=` et `fps=` sont
# facultatifs : une sortie sans vidéo (passes audio) écrit `size= … time= …
# bitrate= … speed=`, et sa barre restait indéterminée (CR-21) ; `time=` suffit
# au pourcentage.
_PROGRESS_RE = re.compile(
    r"(?:frame=\s*(?P<frame>\d+).*?fps=\s*(?P<fps>[\d.]+).*?)?"
    r"time=(?P<time>\d{2}:\d{2}:\d{2}\.\d{2})"
    r".*?bitrate=\s*(?P<bitrate>[\d.]+)kbits/s"
    r".*?speed=\s*(?P<speed>[\d.]+)x"
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
        frame=int(m.group("frame") or 0),
        fps=float(m.group("fps") or 0),
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
# (signature dans la sortie ffmpeg, message rendu à l'utilisateur). La
# signature est le texte anglais de ffmpeg, une donnée ; le message est marqué
# N_() et traduit au retour de `diagnostiquer`.
_CAUSES: tuple[tuple[str, str], ...] = (
    ("no capable devices found",
     N_("This graphics card cannot encode this format. AV1 with NVENC needs an "
        "RTX 40 or newer; HEVC and H264 remain available.")),
    ("required nvenc api version",
     N_("NVENC refused: this ffmpeg needs a newer NVIDIA driver than the one "
        "installed. Update the driver, or use an ffmpeg built for an older "
        "NVENC API.")),
    ("could not open encoder",
     N_("The encoder could not be opened on this computer. If it is AV1: NVENC "
        "only encodes it from the RTX 40 series.")),
    ("cannot load nvcuda",
     N_("The NVIDIA driver cannot be found. Without it, no accelerated "
        "encoding is possible.")),
    ("invalid bit rate",
     N_("The requested bitrate is outside what the encoder accepts. Choose a "
        "value within the range it announces.")),
    ("is not supported by the",
     N_("The chosen encoder does not support this channel layout or this "
        "pixel format.")),
    ("no space left on device",
     N_("The destination disk is full.")),
    ("permission denied",
     N_("Writing to this location is not allowed.")),
)


def _sortie_hevc(cmd: list[str], codec_source: str) -> bool:
    """La vidéo de sortie est-elle du HEVC ? Une copie garde le codec source.

    En MP4, ffmpeg étiquette le HEVC `hev1` ; les lecteurs Apple exigent
    `hvc1`. Le G3 lit les deux en lecture directe (IE-74) : `hvc1` partout.
    """
    encodeur = encodeur_de(cmd) or ""
    if encodeur == "copy":
        return codec_source == "hevc"
    return "hevc" in encodeur or "265" in encodeur


def encodeur_de(cmd: list[str]) -> Optional[str]:
    """Encodeur vidéo d'une commande construite, ou None."""
    try:
        return cmd[cmd.index("-c:v") + 1]
    except (ValueError, IndexError):
        return None


def sortie_10_bits(cmd: list[str]) -> bool:
    """La commande encode-t-elle en 10 bits (sortie HDR) ?"""
    try:
        return cmd[cmd.index("-pix_fmt") + 1] in ("p010le", "yuv420p10le")
    except (ValueError, IndexError):
        return False


def encodeur_a_controler(cmd: list[str]) -> Optional[str]:
    """Encodeur à confronter au sondage du démarrage, ou None.

    `copy` n'est pas un encodeur : une vidéo recopiée (Dolby Vision conservé)
    échouait sur « copy indisponible ici » avant même de lancer ffmpeg.
    """
    encodeur = encodeur_de(cmd)
    return None if encodeur == "copy" else encodeur


def diagnostiquer(lignes: list[str]) -> Optional[str]:
    """Cause lisible d'un échec, cherchée dans toute la sortie de ffmpeg.

    Retourne None si rien de connu n'y figure : l'appelant retombe alors sur
    la dernière ligne, faute de mieux.
    """
    texte = "\n".join(lignes).lower()
    for signature, message in _CAUSES:
        if signature in texte:
            return _(message)
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

    Ce Matroska remplace l'audio de la source : une langue lue dans le `.clpi`
    d'un Blu-ray (IE-119), que ffmpeg ne voit pas, y est écrite — sans elle,
    les pistes sortaient en `und` (CR-63).
    """
    gardees = [ad for ad in audio if ad.action != AudioAction.EXCLUDE]
    # `-stats` : sous `-loglevel error`, ffmpeg n'écrit plus sa ligne de
    # progression, et la barre restait indéterminée (CR-21, mesuré).
    cmd = [ffmpeg_path, "-y", "-loglevel", "error", "-stats", "-i", str(source),
           "-vn", "-sn", "-dn"]
    for ad in gardees:
        cmd += ["-map", f"0:a:{ad.track.index}"]
    cmd += audio_args(gardees)
    for n, ad in enumerate(gardees):
        if ad.track.langue_completee:
            cmd += [f"-metadata:s:a:{n}", f"language={ad.track.language}"]
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

    **Plus reproduit en ffmpeg 8.1.2 et 8.1.3** (IE-80, 2026-10-07) : ni sur
    le fichier qui le déclenchait, ni sur de vrais TrueHD et DTS-HD MA, ni sur
    MLP, FLAC ou PCM, même avec la commande complète et la passe ôtée. La
    version de ffmpeg d'août n'a pas été notée. La passe est **gardée**, par
    choix de l'utilisateur : elle coûte un transcodage audio, et le ffmpeg du
    `PATH` passe avant celui de `bin/` — il peut être plus ancien.
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


def audio_args(included_audio: list, debut: int = 0) -> list[str]:
    """Arguments ffmpeg des pistes audio retenues, dans leur ordre de sortie.

    Partagé par l'encodage et par le chemin de retrait du Dolby Vision, qui
    doit produire exactement les mêmes pistes sans toucher à la vidéo.
    `debut` : index de sortie de la première — les greffées suivent celles
    de la source.
    """
    args: list[str] = []
    for out_i, ad in enumerate(included_audio, start=debut):
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
            # `build_strip_mp4` mappent la vidéo en premier, `-ar:0`
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


def regle_debit(encodeur: str, cible: int) -> list[str]:
    """Les options de débit d'un encodage, d'après l'encodeur **effectif**.

    NVENC : un `-maxrate` égal à la cible fait du débit demandé un plafond que
    rien ne compense — chaque scène facile tire la moyenne vers le bas. Mesuré
    sur un film en prises de vues réelles, la cible n'était honorée qu'à 92 % ;
    avec 50 % de marge en VBR, 99 %. La marge ne gonfle pas les fichiers
    faciles : NVENC ne dépense que ce que le contenu exige.

    libx265 : le réglage inverse (wiki `codecs-video`, mesuré) — c'est un VBV
    serré qui l'oblige à dépenser son budget ; à 1,5 × la cible, 93,6 % au lieu
    de 99,9 %. Sur un poste sans NVIDIA, la branche standard et le réencodage
    DV lui appliquaient la règle de NVENC (CR-22). `-rc` n'existe que chez
    NVENC : ailleurs, ffmpeg l'ignorait en avertissant.
    """
    if encodeur == "libx265":
        maxrate, bufsize_k = cible, max(cible * 2 // 1000, 1)
    else:
        maxrate = cible * 3 // 2
        bufsize_k = max(maxrate * 2 // 1000, 1)
    args = ["-b:v", str(cible), "-maxrate", str(maxrate), "-bufsize", f"{bufsize_k}k"]
    if "nvenc" in encodeur and "av1" not in encodeur:
        args += ["-rc", "vbr"]
    return args


def build_dv_video_command(decision, platform, sortie_hevc: Path,
                           ffmpeg_path: str | None = None) -> list[str]:
    """Encode la seule vidéo, en Annex-B brut, pour un réencodage DV.

    Le RPU sera réinjecté ensuite entre les tranches d'image : cette passe doit
    donc rendre **exactement autant d'images que la source en compte**. D'où
    l'absence de tout `-vf` — pas même un `scale` aux dimensions d'origine, qui
    serait un no-op mais ouvrirait la porte à un filtre ajouté plus tard sans
    voir la contrainte. `decision.peut_reencoder_en_dv` a déjà garanti que la
    résolution ne change pas.

    Les métadonnées HDR10 statiques — primaires BT.2020, courbe PQ, master
    display, MaxCLL — n'ont pas à être reposées : ffmpeg les recopie de la
    source vers la sortie en SEI, y compris à travers NVENC. Mesuré, pas
    supposé (voir CHANGELOG v0.8.7.5).
    """
    info    = decision.info
    vid     = decision.video
    profile = decision.profile

    cmd = [ffmpeg_path or _ffmpeg_path, "-y"]
    if platform.hwaccel:
        cmd += ["-hwaccel", platform.hwaccel]
    cmd += ["-i", str(decision.encode_source or info.lecture)]

    # Le Dolby Vision est du 10 bits par construction : la couche de base d'un
    # profil 8.1 est du HDR10, et un encodage 8 bits la trahirait.
    cmd += [
        "-map",       "0:v:0",
        "-c:v",       platform.encoder_hevc,
        "-pix_fmt",   "p010le" if "nvenc" in platform.encoder_hevc else "yuv420p10le",
        *regle_debit(platform.encoder_hevc, vid.target_bitrate),
        "-preset",    profile.get("preset_encoder", "medium"),
        "-profile:v", "main10",
        "-f",         "hevc",
        str(sortie_hevc),
    ]
    return cmd


def build_command(
    decision: FileDecision,
    platform: PlatformProfile,
    audio_source: Path | None = None,
    sous_titres_porteur: Path | None = None,
    chapitres: Path | None = None,
) -> list[str]:
    """
    Retourne la liste d'arguments ffmpeg pour un FileDecision.
    Retourne [] si l'action est SKIP.

    `sous_titres_porteur` : le Matroska de `core/sous_titres.py`, d'où les
    sous-titres texte de la source sont pris à la place de la source.
    `chapitres` : un fichier FFMETADATA, ceux d'un titre de Blu-ray lus dans
    sa playlist (IE-120) — le `.m2ts` n'en porte aucun.
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
        raise ErreurAffichable(N_(
            "Output path identical to the source ({path}). Empty suffix and "
            "same container — encoding refused to avoid corrupting the source "
            "file."), path=info.path)

    cmd: list[str] = [_ffmpeg_path]

    # hwaccel — absent pour :
    #   - SDR tone map (CPU obligatoire pour zscale)
    #   - DV preserve (copy)
    #   - HDR10 quality (libx265 CPU pour metadata propres)
    preserve_video = (vid.dv_action == DVAction.DV)
    # Le mode HDR10 « quality » décide deux choses à la fois : l'encodeur
    # (libx265, plus bas) et l'absence de hwaccel. Un seul nom pour un seul
    # prédicat — l'expression était écrite deux fois, mot pour mot, et en
    # modifier une seule aurait passé `-hwaccel` à un encodage processeur, ou
    # l'aurait retiré à un NVENC.
    hdr10_quality = (
        vid.dv_action == DVAction.HDR10
        and vid.action == VideoAction.ENCODE_HEVC
        and profile.get("hdr10_quality") == "quality"
    )
    use_hwaccel = (
        platform.hwaccel
        and vid.dv_action != DVAction.SDR
        and not preserve_video
        and not hdr10_quality
    )
    if use_hwaccel:
        cmd += ["-hwaccel", platform.hwaccel]

    # Après un mux préalable, l'entrée est l'intermédiaire, pas la source.
    # `info.path` reste la source : c'est d'elle que dépend le nom de sortie.
    cmd += ["-i", str(decision.encode_source or info.lecture)]

    # ── Entrées supplémentaires : pistes externes greffées ────────────────────
    # ffmpeg les absorbe dans la même passe que l'encodage : inutile de muxer
    # séparément quand le fichier est de toute façon réencodé.
    from .muxer import (TrackKind, ffmpeg_stream_index, premux_track_order,
                        types_par_defaut)
    from .sous_titres import encodage_texte

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
        # TRANSLATORS: -itsoffset is an ffmpeg option, keep it as is.
        raise ErreurAffichable(N_(
            "The track “{track}” needs a stretch factor, which ffmpeg cannot "
            "apply in one pass (-itsoffset only shifts by a constant offset). "
            "mkvmerge can: install it so that the track is added through it."),
            track=stretched[0].source_path.name)
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
        # ffmpeg lit un sous-titre texte en UTF-8 : un `.srt` en cp1252 perdait
        # toutes ses répliques accentuées, code de retour nul (CR-50).
        if ext.kind == TrackKind.SUBTITLE:
            jeu = encodage_texte(ext.source_path)
            if jeu and jeu != "UTF-8":
                cmd += ["-sub_charenc", jeu]
        cmd += ["-i", str(ext.source_path)]

    # Les pistes audio produites à part (voir `audio_prepass_needed`). Posée
    # en dernier : les index des donneurs ne bougent pas.
    if audio_source is not None:
        cmd += ["-i", str(audio_source)]

    # Un profil en `container = "mp4"` écarte les sous-titres image, que le
    # MP4 ne porte pas — jamais en silence : la décision les liste, et si ce
    # sont les seuls du fichier, c'est le conteneur qui cède, pas eux.
    ecartes = {st.index for st in decision.sous_titres_ecartes}
    sub_indices = decision.subtitle_indices
    premux_subs = [t for t in premux_tracks if t.kind != TrackKind.AUDIO]
    tout_garder = sub_indices is None and not ecartes
    sous_titres_source = bool(
        (info.subtitle_tracks if tout_garder else decision.subtitles_finales)
        or premux_subs)

    # Les sous-titres de la source passent par une entrée à eux dès que l'audio
    # vient d'une autre entrée que la vidéo. Lus avec la vidéo, ils rendent un
    # fichier dont l'audio s'interrompt : le muxeur écrit des centaines de
    # secondes de vidéo seule, puis l'audio en bloc (mesuré, ffmpeg 8.1 : audio
    # absente de 31,9 s à 122,6 s, et un retard jusqu'à 1 150 s). ffmpeg le
    # relit sans broncher, un lecteur de salon s'arrête quand l'audio manque.
    # `-max_interleave_delta 0` répare aussi, mais retient en mémoire tout ce
    # qui précède la réplique suivante — 2 168 s de film sur une piste
    # « forced ». Le prix ici est une seconde lecture de la source.
    audio_a_part = (audio_source is not None
                    or any(t.kind == TrackKind.AUDIO for t in ext_tracks))
    sub_input = 0
    if audio_a_part and sous_titres_source:
        sub_input = len(ext_tracks) + 1 + (audio_source is not None)
        cmd += ["-i", str(decision.encode_source or info.lecture)]

    porteur_input = None
    if sous_titres_porteur is not None:
        porteur_input = cmd.count("-i")
        cmd += ["-i", str(sous_titres_porteur)]

    chapitres_input = None
    if chapitres is not None:
        chapitres_input = cmd.count("-i")
        cmd += ["-f", "ffmetadata", "-i", str(chapitres)]

    # ── Filtre vidéo ──────────────────────────────────────────────────────────
    if not preserve_video:
        # `scale` rattrape l'arrondi de la hauteur par un SAR : 3832x1600 donne
        # 1920x802 en 192079:192000. Jellyfin y voit une vidéo anamorphique et
        # la transcode. `setsar=1` rend des pixels carrés (écart < 0,05 %).
        # Une source qui tient dans la cible n'est pas agrandie (1918x802 sortait
        # en 1920x802) ; une dimension impaire, que le 4:2:0 refuse, perd un pixel.
        filtres = []
        # Avant la mise à l'échelle : réduire des trames mêlées les mélange.
        if decision.desentrelace:
            filtres.append(FILTRE_DESENTRELACEMENT)
        # Une source anamorphique (DVD 720×480 en 32:27, TNT SD, HDV) tenait
        # dans la cible et gardait son SAR : Jellyfin la transcodait. Elle
        # passe d'abord en pixels carrés, en largeur — rien n'est perdu en
        # hauteur (CR-14).
        largeur = info.largeur_affichee
        if info.pixels_non_carres:
            filtres.append("scale=trunc(iw*sar/2)*2:trunc(ih/2)*2,setsar=1")
        if largeur > vid.target_width or info.height > vid.target_height:
            filtres.append(
                f"scale={vid.target_width}:{vid.target_height}"
                ":force_original_aspect_ratio=decrease"
                ":force_divisible_by=2"
                ",setsar=1"
            )
        elif not info.pixels_non_carres and (info.width % 2 or info.height % 2):
            filtres.append("scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1")
        if vid.dv_action == DVAction.SDR:
            filtres.append(_SDR_TONEMAP_FILTER)
        if filtres:
            cmd += ["-vf", ",".join(filtres)]

    # ── Encodeur vidéo ────────────────────────────────────────────────────────
    # DV : copy flux vidéo DV intégralement (preserve_video)
    # HDR10 compat : re-encode NVENC standard (supprime RPU, pas de metadata HDR10 fines)
    # HDR10 quality : libx265 CPU + master-display + max-cll → compatibilité TV LG
    # SDR : re-encode + tone-mapping vers SDR (CPU intensif)
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

        # La règle de débit dépend de l'encodeur effectif (`regle_debit`).
        preset = profile.get("preset_encoder", "medium")
        cmd += ["-c:v", encoder, "-pix_fmt", pix_fmt,
                *regle_debit(encoder, vid.target_bitrate), "-preset", preset]
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

    if porteur_input is not None:
        # Le porteur tient toutes les pistes de la source que la sortie garde,
        # puis les greffées — directes ou passées par un mux préalable — dans
        # l'ordre de `sous_titres.greffes_a_porter` (CR-34).
        from .sous_titres import pistes_a_porter
        n_src_subs = len(pistes_a_porter(decision))
        n_greffes  = len(premux_subs) + sum(
            t.kind != TrackKind.AUDIO for t in ext_tracks)
        for j in range(n_src_subs + n_greffes):
            cmd += ["-map", f"{porteur_input}:s:{j}"]
        subs_sortie = pistes_a_porter(decision)
    elif tout_garder:
        # `0:s?` prend tout l'intermédiaire, greffées comprises : les mapper
        # une seconde fois les livrerait en double.
        cmd += ["-map", f"{sub_input}:s?"]
        n_src_subs = len(info.subtitle_tracks)
        subs_sortie = list(info.subtitle_tracks)
    else:
        subs_sortie = decision.subtitles_finales
        gardes = [st.index for st in subs_sortie]
        for si in gardes:
            cmd += ["-map", f"{sub_input}:s:{si}"]
        n_src_subs = len(gardes)
        for j in range(len(premux_subs)):
            cmd += ["-map", f"{sub_input}:s:{len(info.subtitle_tracks) + j}"]

    # Pistes externes. Le donneur entre en entier : mapper son flux `:0`
    # supposait qu'il n'en porte qu'un — vrai d'un .srt nu, faux d'un
    # conteneur. Un donneur à six pistes de sous-titres rendait toujours la
    # première, quelle que soit celle choisie, pendant que la langue et le
    # titre venaient de la bonne. La piste apparaissait donc au lecteur,
    # correctement nommée, et n'affichait rien — la première d'un rip est en
    # général la piste « forced », vingt-trois répliques sur un épisode.
    for n, ext in enumerate(ext_tracks, start=1):
        if ext.kind != TrackKind.AUDIO and porteur_input is not None:
            continue                      # déjà mappé depuis le porteur
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

    # ── Langues lues hors du flux ─────────────────────────────────────────────
    # Celles d'un Blu-ray viennent du `.clpi` (IE-119) : ffmpeg ne les voit pas
    # dans le `.m2ts`, la sortie n'en aurait aucune sans ces lignes.
    for n, ad in enumerate(included_audio):
        if ad.track.langue_completee:
            cmd += [f"-metadata:s:a:{n}", f"language={ad.track.language}"]
    for n, st in enumerate(subs_sortie):
        if st.langue_completee:
            cmd += [f"-metadata:s:s:{n}", f"language={st.language}"]
    if chapitres_input is not None:
        cmd += ["-map_chapters", str(chapitres_input)]

    # ── Pistes externes : copie, langue, nom, drapeaux ────────────────────────
    # Qu'elles soient entrées par mkvmerge ou par ffmpeg, les pistes greffées
    # se recopient, se nomment et se marquent pareil — et les deux listes
    # s'excluent : le mux préalable vide `external_tracks`.
    ext_audio = [t for t in ext_tracks if t.kind == TrackKind.AUDIO] + premux_audio
    ext_subs  = [t for t in ext_tracks if t.kind != TrackKind.AUDIO] + premux_subs

    # Une piste externe marquée « défaut » retire le drapeau des pistes source
    # de son type — sous-titres compris (CR-23) : deux pistes par défaut, et le
    # lecteur prend la première. Même règle que le mux (`types_par_defaut`).
    defaut = types_par_defaut(ext_audio + ext_subs)
    if TrackKind.AUDIO in defaut:
        for out_i in range(len(included_audio)):
            cmd += [f"-disposition:a:{out_i}", "0"]
    if TrackKind.SUBTITLE in defaut:
        for out_i in range(n_src_subs):
            cmd += [f"-disposition:s:{out_i}", "0"]

    # Une piste greffée suit la règle audio du profil, comme celles de la
    # source : un DTS ou un Opus recopié faisait transcoder Jellyfin (IE-125).
    from .decision import audio_greffee
    for j, ext in enumerate(ext_audio):
        out_i = len(included_audio) + j
        ad = audio_greffee(ext, profile)
        cmd += audio_args([ad], debut=out_i)
        cmd += [f"-metadata:s:a:{out_i}", f"language={ext.language}"]
        if ext.track_name and not ad.output_title:
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

    # Les polices jointes d'un ASS : sans elles, panneaux et karaokés
    # s'affichent dans une police de repli (CR-20). Le MP4 n'en porte pas.
    if container == ".mkv":
        cmd += ["-map", "0:t?", "-c:t", "copy"]

    # faststart est un réglage MP4 ; ffmpeg l'ignore en avertissant sur MKV
    if container == ".mp4":
        cmd += ["-movflags", "+faststart"]
        if _sortie_hevc(cmd, info.codec):
            cmd += ["-tag:v", "hvc1"]
        # Sans `-strict unofficial`, ffmpeg n'écrit pas la boîte `dvcC` en MP4 :
        # le RPU reste dans le flux, mais le G3 ne voit plus de Dolby Vision
        # (IE-109, mesuré sur ffmpeg 8.1.2).
        if preserve_video and encodeur_de(cmd) == "copy":
            cmd += ["-strict", "unofficial"]
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
        # Les dernières lignes de stderr : la cause d'un échec précède le
        # constat de quelques lignes (`diagnostiquer`, CR-62).
        self.journal: list[str] = []

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
            if line:
                self.journal.append(line)
                del self.journal[:-40]
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
