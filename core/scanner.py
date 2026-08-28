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
# ffprobe nomme toutes les variantes DTS « dts » et met la famille dans
# `profile` : « DTS », « DTS-ES », « DTS-HD HR », « DTS-HD MA ». Sans lire le
# profil, un DTS-HD MA passe pour un DTS ordinaire.
_LOSSLESS_PROFILES = frozenset({"dts-hd ma", "dts-hd ma + dts:x"})
# Familles qu'aucun lecteur de fichier grand public ne prend en charge : c'est
# sur elles que porte le transcodage au débit de la source.
_HD_AUDIO_CODECS = frozenset({"truehd", "mlp", "dts", "dts-hd ma", "dtshd"})


def channel_layout_label(channels: int) -> str:
    """Nombre de canaux → « 5.1 », « 7.1 »… Utilisé aussi par la décision,
    qui doit nommer la disposition de sortie après un repli."""
    if channels == 1:  return "1.0"
    if channels == 2:  return "2.0"
    if channels == 6:  return "5.1"
    if channels == 8:  return "7.1"
    return f"{channels}ch"
_IMAGE_SUB_CODECS = frozenset({"hdmv_pgs_subtitle", "dvd_subtitle", "dvdsub", "pgssub"})

# ISO 639-2 a deux jeux de codes pour vingt langues : un bibliographique (fre,
# ger, dut…) et un terminologique (fra, deu, nld…). Les deux désignent la même
# langue, et les conteneurs emploient l'un ou l'autre sans règle — un même
# fichier peut mêler les deux. Comparer les chaînes brutes fait donc échouer
# `audio_languages = ["fre"]` sur une piste étiquetée « fra », qui disparaît du
# fichier produit sans un mot.
_LANG_TERMINOLOGIQUES: dict[str, str] = {
    "sqi": "alb", "hye": "arm", "eus": "baq", "mya": "bur", "zho": "chi",
    "ces": "cze", "nld": "dut", "fra": "fre", "kat": "geo", "deu": "ger",
    "ell": "gre", "isl": "ice", "mkd": "mac", "mri": "mao", "msa": "may",
    "fas": "per", "ron": "rum", "slk": "slo", "bod": "tib", "cym": "wel",
}


def normalize_language(code: str) -> str:
    """Ramène un code ISO 639-2 à sa forme bibliographique, pour comparaison.

    Ne sert qu'à comparer : l'affichage garde ce que le fichier déclare.
    """
    c = (code or "").strip().lower()
    return _LANG_TERMINOLOGIQUES.get(c, c)


def same_language(a: str, b: str) -> bool:
    """Deux codes désignent-ils la même langue ? « fra » et « fre », oui."""
    return bool(a) and normalize_language(a) == normalize_language(b)
_COPY_COMPAT_CODECS = frozenset({"aac", "ac3", "eac3"})

# ── Chemin dovi_tool (singleton, settable par l'app au démarrage) ────────────
_dovi_path: Optional[Path] = None
# Chemin de ffprobe. Le preflight installe les binaires dans ./bin/ sans
# toucher au PATH : les appeler par leur nom nu fait echouer tout scan sur une
# installation neuve, et chaque fichier est alors ecarte comme illisible.
_ffprobe_path: str = "ffprobe"


def set_dovi_path(path: Optional[Path]) -> None:
    """Active l'enrichissement DV au scan en fournissant le chemin dovi_tool."""
    global _dovi_path
    _dovi_path = path


def set_ffprobe_path(path: str) -> None:
    """Précise l'exécutable ffmpeg à utiliser pour le probing (défaut: 'ffmpeg' du PATH)."""
    global _ffprobe_path
    _ffprobe_path = path


# ─── Modèles ──────────────────────────────────────────────────────────────────

@dataclass
class AudioTrack:
    index:    int
    codec:    str
    channels: int
    language: str   # ISO 639-2 ou ""
    title:    str
    bitrate:  int   # bps, 0 si inconnu
    profile:  str = ""   # « DTS-HD MA », « Dolby Digital Plus + Atmos »…

    @property
    def channel_layout(self) -> str:
        return channel_layout_label(self.channels)

    @property
    def is_lossless(self) -> bool:
        if self.codec.lower() in _LOSSLESS_CODECS:
            return True
        return self.profile.lower() in _LOSSLESS_PROFILES

    @property
    def is_hd_audio(self) -> bool:
        """TrueHD ou DTS, toutes variantes — les formats que le transcodage
        au débit de la source vise (voir `audio_hd_codec` dans un profil)."""
        return self.codec.lower() in _HD_AUDIO_CODECS

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
    # Compatibilité de la couche de base d'un profil 8 : 1 = HDR10, 2 = SDR,
    # 4 = HLG. C'est elle qui distingue un 8.1 d'un 8.4, et elle seule dit si
    # retirer le RPU laisse une image juste.
    dv_bl_compat:    Optional[int]       = None
    color_transfer:  str                 = ""
    frame_rate:      str                 = ""    # "24/1", "24000/1001"…
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
    def is_hdr(self) -> bool:
        """Vrai si la courbe de transfert est PQ ou HLG."""
        return self.color_transfer in ("smpte2084", "arib-std-b67")

    @property
    def can_strip_dv(self) -> bool:
        """Vrai si retirer le RPU laisse un HDR10 valide, sans réencodage.

        Profil 8.1 : la couche de base *est* du HDR10, le RPU n'est qu'un jeu
        de NAL en plus. Profil 7 : couche de base HDR10 également, et
        dovi_tool retire en même temps la couche d'amélioration.
        Profil 5 (couche de base IPT-PQ) et 8.4 (couche de base HLG) sont
        exclus : leur retirer le RPU ne donne pas du HDR10.
        """
        if self.dv_profile == 7:
            return True
        return self.dv_profile == 8 and self.dv_bl_compat == 1

    @property
    def dv_label(self) -> str:
        if self.dv_profile is None:
            return "—"
        if self.dv_profile == 8 and self.dv_bl_compat in (1, 2, 4):
            return f"DV:P8.{self.dv_bl_compat}"
        return f"DV:P{self.dv_profile}"


# ─── Helpers ffprobe ──────────────────────────────────────────────────────────

def _ffprobe_json(args: list[str]) -> dict:
    cmd = [_ffprobe_path, "-v", "error", "-print_format", "json"] + args
    # ffprobe, ffmpeg et mkvmerge écrivent en UTF-8. Les lire avec l'encodage
    # local — cp1252 sur un Windows français — fait mourir le thread de lecture
    # de subprocess dès qu'un titre ou un nom de fichier sort de cette table :
    # l'exception n'y remonte pas, `stdout` vaut None, et le fichier est écarté
    # comme illisible. Vu sur un WebM dont un tag portait « ❤️ ».
    r = subprocess.run(cmd, capture_output=True, timeout=30,
                       encoding="utf-8", errors="replace")
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

def _video_bitrate(vid: dict, streams: list, fmt: dict) -> int:
    """Débit du flux vidéo seul, en bps. 0 si vraiment introuvable.

    Un flux vidéo de Matroska n'annonce presque jamais de `bit_rate` : ffprobe
    rend `N/A` et la seule valeur restante est celle du conteneur — vidéo,
    audio et sous-titres confondus. La comparer à un débit vidéo cible fausse
    la décision dans le sens du réencodage, d'autant plus que les pistes sont
    grosses : sur un film porteur d'un TrueHD, l'écart dépasse 40 %.

    Trois sources, dans l'ordre : le `bit_rate` du flux, le tag `BPS` que pose
    mkvmerge, puis le débit du conteneur **moins celui des autres pistes**.
    """
    direct = _safe_int(vid.get("bit_rate"))
    if direct > 0:
        return direct

    tags = {k.lower(): v for k, v in vid.get("tags", {}).items()}
    bps  = _safe_int(tags.get("bps"))
    if bps > 0:
        return bps

    total = _safe_int(fmt.get("bit_rate"))
    if total <= 0:
        return 0

    # Soustraction : chaque piste non vidéo retire sa part. Une piste dont le
    # débit reste inconnu ne retire rien — le résultat penche alors du côté
    # prudent, celui du réencodage.
    autres = 0
    for s in streams:
        if s is vid or s.get("codec_type") == "video":
            continue
        autres += _audio_bitrate(s, s.get("tags", {}))
    reste = total - autres
    return reste if reste > 0 else total


def _audio_bitrate(stream: dict, tags: dict) -> int:
    """Débit réel d'une piste audio, en bps, 0 si vraiment introuvable.

    Un flux TrueHD ou DTS-HD MA n'annonce pas de `bit_rate` : ffprobe rend
    `N/A`. mkvmerge, lui, écrit des tags de statistiques à chaque piste — le
    débit y est exact, mesuré sur le fichier entier. Sans eux, il reste le
    quotient octets/durée, qui vaut mieux qu'un zéro.
    """
    direct = _safe_int(stream.get("bit_rate"))
    if direct > 0:
        return direct

    # Les tags Matroska sont sensibles à la casse selon le mux : BPS, bps…
    lower = {k.lower(): v for k, v in tags.items()}
    bps   = _safe_int(lower.get("bps"))
    if bps > 0:
        return bps

    octets = _safe_int(lower.get("number_of_bytes"))
    duree  = _duration_tag(str(lower.get("duration", "")))
    if octets > 0 and duree > 0:
        return int(octets * 8 / duree)
    return 0


def _duration_tag(raw: str) -> float:
    """« 03:35:23.203000000 » → secondes. 0.0 si illisible."""
    parts = raw.split(":")
    if len(parts) != 3:
        return 0.0
    try:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except ValueError:
        return 0.0


def _fraction(valeur: str, unite: int) -> Optional[int]:
    """« 35400/50000 » → la valeur exprimee dans l'unite voulue.

    ffprobe rend des fractions ; x265 attend des entiers dans une unite fixe :
    1/50000 pour les coordonnees de chromaticite, 1/10000 cd/m2 pour les
    luminances. On reechelonne plutot que de supposer le denominateur.
    """
    try:
        num, _, den = str(valeur).partition("/")
        return round(int(num) / int(den or 1) * unite)
    except (ValueError, ZeroDivisionError):
        return None


def _hdr10_metadata(path: Path) -> tuple[Optional[str], Optional[tuple[int, int]]]:
    """Master display et MaxCLL/MaxFALL d'une source HDR, lus par ffprobe.

    Ces valeurs decrivent le HDR10 du flux : elles vivent dans ses SEI, la ou
    un lecteur les cherche. Les extraire du RPU Dolby Vision reviendrait a
    demander a une autre couche ce que celle-ci dit deja — et n'en dirait rien
    pour une source HDR sans Dolby Vision.

    Rend (None, None) en cas d'echec : le mode quality retombe alors sur un
    encodage sans metadonnees fines plutot que d'echouer.
    """
    try:
        data = _ffprobe_json([
            "-select_streams", "v:0",
            "-read_intervals", "%+#1",
            "-show_frames",
            str(path),
        ])
    except Exception as e:
        _log.debug("hdr10 probe failed for %s: %s", path, e)
        return None, None

    frames = data.get("frames") or [{}]
    master, cll = None, None
    for sd in frames[0].get("side_data_list", []):
        type_sd = sd.get("side_data_type", "")

        if "Mastering display" in type_sd:
            coords = {}
            for nom, unite in (("green_x", 50000), ("green_y", 50000),
                               ("blue_x", 50000),  ("blue_y", 50000),
                               ("red_x", 50000),   ("red_y", 50000),
                               ("white_point_x", 50000), ("white_point_y", 50000),
                               ("max_luminance", 10000), ("min_luminance", 10000)):
                if nom not in sd:
                    break
                v = _fraction(sd[nom], unite)
                if v is None:
                    break
                coords[nom] = v
            else:
                master = (
                    f"G({coords['green_x']},{coords['green_y']})"
                    f"B({coords['blue_x']},{coords['blue_y']})"
                    f"R({coords['red_x']},{coords['red_y']})"
                    f"WP({coords['white_point_x']},{coords['white_point_y']})"
                    f"L({coords['max_luminance']},{coords['min_luminance']})"
                )

        elif "light level" in type_sd.lower():
            contenu = _safe_int(sd.get("max_content"))
            moyen   = _safe_int(sd.get("max_average"))
            # 0,0 signifie « non mesure » : ne rien injecter vaut mieux que
            # d'affirmer que le pic lumineux est nul.
            if contenu or moyen:
                cll = (contenu, moyen)

    return master, cll


def _detect_dv(path: Path) -> tuple[Optional[int], Optional[int]]:
    """
    Détecte le Dolby Vision via les side_data ffprobe.

    Retourne (profil, compatibilité de la couche de base) — (5, None),
    (8, 1) pour un 8.1, (8, 4) pour un 8.4… (None, None) si pas de DV.
    """
    try:
        data = _ffprobe_json([
            "-select_streams", "v:0",
            "-show_entries",
            "stream_side_data=dv_profile,dv_bl_signal_compatibility_id"
            ":stream_tags=:stream=color_transfer",
            str(path),
        ])
        for stream in data.get("streams", []):
            for sd in stream.get("side_data_list", []):
                if "dv_profile" in sd:
                    compat = sd.get("dv_bl_signal_compatibility_id")
                    return (int(sd["dv_profile"]),
                            int(compat) if compat is not None else None)
    except Exception as e:
        _log.debug("dv_profile probe failed for %s: %s", path, e)
    return (None, None)


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

    # Débit **vidéo**, jamais celui du conteneur : c'est à un débit vidéo
    # cible qu'il sera comparé, et c'est un débit vidéo que l'encodeur reçoit.
    bitrate = _video_bitrate(vid, streams, fmt)
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
            bitrate=_audio_bitrate(s, tags),
            profile=s.get("profile", "") if isinstance(s.get("profile"), str) else "",
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
    dv_profile, dv_bl_compat = _detect_dv(path)

    # Sous-profil DV : deduit de la compatibilite annoncee par le flux, sans
    # extraire ni analyser le RPU.
    dv_subprofile = None
    if dv_profile == 8 and dv_bl_compat in (1, 2, 4):
        dv_subprofile = f"8.{dv_bl_compat}"
    elif dv_profile is not None:
        dv_subprofile = str(dv_profile)

    # Master display et MaxCLL : lus dans les SEI du flux, pour toute source
    # HDR — avec ou sans Dolby Vision. Une source SDR n'en a pas, on ne paie
    # donc pas l'appel.
    hdr10_master_display, hdr10_max_cll = (None, None)
    if vid.get("color_transfer", "") in ("smpte2084", "arib-std-b67"):
        hdr10_master_display, hdr10_max_cll = _hdr10_metadata(path)

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
        dv_bl_compat=dv_bl_compat,
        color_transfer=vid.get("color_transfer", ""),
        frame_rate=vid.get("r_frame_rate", ""),
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
