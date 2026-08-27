"""
core/decision.py — Logique métier encodage vidéo et audio.

Implémente les 4 cas de la spec (CAS 1/2/3/SKIP) et la politique
de sélection + transcodage des pistes audio.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional

from .muxer import MUX_SUFFIX, ExternalTrack
from .profiles import Profile
from .scanner import AudioTrack, VideoInfo, channel_layout_label


# ─── Décision vidéo ───────────────────────────────────────────────────────────

class VideoAction(Enum):
    ENCODE_HEVC = auto()   # CAS 1 ou CAS 2
    ENCODE_H264 = auto()   # CAS 3
    ENCODE_AV1  = auto()   # Manuel uniquement (très gourmand CPU)
    STRIP_DV    = auto()   # Retrait du RPU seul — remux, aucun réencodage
    SKIP        = auto()


class Emphase(Enum):
    """Rôle d'une valeur affichée, indépendant de la teinte retenue.

    Une même décision portait jusqu'ici deux couleurs selon l'écran, et le
    magenta — la teinte la plus criarde — signalait l'état le plus banal, celui
    qui occupe presque chaque ligne. Les couleurs se décident donc ici, une
    fois, en nommant ce qu'elles veulent dire.
    """
    INACTION   = auto()   # rien ne sera fait
    SANS_PERTE = auto()   # traité sans réencodage : l'image n'est pas touchée
    ORDINAIRE  = auto()   # le cas courant — il n'a pas à crier
    MODIFIEE   = auto()   # l'utilisateur a écarté la décision automatique
    ALERTE     = auto()   # coûteux, lent, ou destructeur


# Le cas ordinaire ne porte aucune couleur : sur un écran dense, ce qui se
# répète à chaque ligne ne doit pas attirer l'œil. Et `dark_orange` reste
# réservé aux alertes (convention du projet) — la réserve n'a de valeur que si
# rien d'autre ne l'emploie.
STYLE_PAR_EMPHASE: dict["Emphase", str] = {
    Emphase.INACTION:   "dim",
    Emphase.SANS_PERTE: "green",
    Emphase.ORDINAIRE:  "",
    Emphase.MODIFIEE:   "bold yellow",
    Emphase.ALERTE:     "bold dark_orange",
}


class DVAction(Enum):
    NONE   = auto()   # pas de DV détecté
    HDR10  = auto()   # DV → HDR10 (enlève RPU)
    DV     = auto()   # DV → DV (copy sans modification)
    SDR    = auto()   # DV → SDR (tone map P5, CPU, lent)


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
        if self.action == VideoAction.STRIP_DV:
            return "→ HDR10"
        codec = "HEVC" if self.action == VideoAction.ENCODE_HEVC else "H264"
        dv = ""
        if self.dv_action == DVAction.HDR10: dv = " → HDR10"
        if self.dv_action == DVAction.DV:    dv = " → DV"
        if self.dv_action == DVAction.SDR:   dv = " → SDR ⚠"
        return f"→ {codec}{dv}"

    def emphase(self) -> "Emphase":
        return emphase_video(self.action, self.dv_action)

    def style(self) -> str:
        """Style Rich de la décision — voir `Emphase`."""
        return STYLE_PAR_EMPHASE[self.emphase()]


def emphase_video(action: "VideoAction",
                  dv_action: "DVAction" = None) -> "Emphase":
    """Rôle d'une action vidéo, avec ou sans décision complète.

    L'écran des pistes classe une action seule pendant que l'utilisateur choisit
    un codec ; le browser classe une décision aboutie. Les deux passent par ici.
    """
    if action == VideoAction.SKIP:
        return Emphase.INACTION
    if action == VideoAction.STRIP_DV:
        return Emphase.SANS_PERTE
    # Le tone mapping détruit la plage dynamique, l'AV1 coûte des heures :
    # ce sont les deux seuls choix vidéo qui méritent d'alerter.
    if dv_action == DVAction.SDR or action == VideoAction.ENCODE_AV1:
        return Emphase.ALERTE
    return Emphase.ORDINAIRE


def emphase_dv(dv_action: "DVAction") -> "Emphase":
    """Rôle d'un traitement Dolby Vision, sur un écran comme dans un profil."""
    if dv_action == DVAction.SDR:
        return Emphase.ALERTE
    if dv_action == DVAction.DV:
        # Le flux vidéo est recopié tel quel : rien n'est recalculé.
        return Emphase.SANS_PERTE
    return Emphase.ORDINAIRE


def style_video(action: "VideoAction", dv_action: "DVAction" = None) -> str:
    return STYLE_PAR_EMPHASE[emphase_video(action, dv_action)]


def style_dv(dv_action: "DVAction") -> str:
    return STYLE_PAR_EMPHASE[emphase_dv(dv_action)]


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
    output_codec:   str   # "aac" | "ac3" | "eac3" | "copy" | ""
    output_bitrate: int   # bps, 0 si copy/exclude
    locked:         bool = False   # True = piste 0 (verrouillée par défaut)
    # Nombre de canaux en sortie quand il diffère de la source. 0 = inchangé.
    # Les encodeurs ac3 et eac3 s'arrêtent au 5.1 ; ffmpeg replie une source
    # 7.1 de lui-même. On le pose quand même explicitement : l'écran
    # d'encodage affiche la commande, et un downmix silencieux n'y serait
    # visible nulle part.
    output_channels: int = 0

    def display(self) -> str:
        if self.action == AudioAction.EXCLUDE:
            return ""
        if self.action == AudioAction.COPY:
            return f"→ copy"
        canaux = ""
        if self.output_channels and self.output_channels != self.track.channels:
            canaux = f" {channel_layout_label(self.output_channels)}"
        return f"→ {self.output_codec}{canaux} {self.output_bitrate // 1000}k"

    @property
    def output_title(self) -> Optional[str]:
        """Titre corrigé quand le transcodage rend l'ancien faux, sinon None.

        Un « ENG VO : TrueHD 5.1 » devenu E-AC3 continuerait d'annoncer un
        codec absent du fichier — c'est ce que lisent les lecteurs, et la
        seule chose que voit l'utilisateur au moment de choisir sa piste.
        """
        if self.action != AudioAction.TRANSCODE:
            return None
        return retitle(self.track.title, self.output_codec,
                       self.track.channels, self.output_channels)


# ─── Constantes partagées TUI (cycle codec / options bitrate / suffixes) ─────

ACTION_CYCLE: list["VideoAction"] = [
    VideoAction.ENCODE_HEVC,
    VideoAction.ENCODE_H264,
    VideoAction.ENCODE_AV1,
    VideoAction.SKIP,
]


def cycle_index(action: "VideoAction") -> int:
    """Position d'une action dans ACTION_CYCLE, pour un picker ou un cycle.

    Toute action n'y figure pas : STRIP_DV n'est pas un choix de codec, c'est
    ce que la décision propose d'elle-même quand le RPU peut partir sans
    réencodage. Il se range avec SKIP, les deux voulant dire « ne pas
    réencoder ». Sans ce repli, `.index()` levait un ValueError et l'écran
    Pistes plantait sur la touche codec.
    """
    if action in ACTION_CYCLE:
        return ACTION_CYCLE.index(action)
    return ACTION_CYCLE.index(VideoAction.SKIP)


def same_intent(choisie: "VideoAction", decidee: "VideoAction") -> bool:
    """Le choix du picker revient-il à ce que la décision proposait déjà ?

    Choisir « SKIP » sur un fichier dont la décision est STRIP_DV, c'est
    demander de ne pas réencoder — ce que le retrait du RPU fait déjà, en
    mieux. On lève alors la surcharge au lieu d'imposer un SKIP sec, qui
    laisserait le Dolby Vision en place sans que rien ne l'explique.
    """
    if choisie == decidee:
        return True
    return choisie == VideoAction.SKIP and decidee == VideoAction.STRIP_DV


BITRATE_OPTS_KBPS:     list[int] = [500, 800, 1000, 1500, 2000, 2200, 2500, 3000, 3500, 5000, 8000, 12000]
AV1_BITRATE_OPTS_KBPS: list[int] = [300, 500, 800, 1000, 1500, 2000, 2500, 3000, 4000, 6000]

# Codecs que le MP4 ne porte pas (ou pas utilement). Les noms varient selon
# la source — ffprobe dit "ass", mkvmerge "AdvancedSubStationAlpha" — d'où la
# comparaison par fragment plutôt que par égalité.
_MKV_ONLY_CODECS: tuple[str, ...] = (
    "ass", "ssa", "substation",              # sous-titres stylés
    "pgs", "vobsub", "dvdsub", "dvd_sub",    # sous-titres image
    "truehd", "mlp", "dts-hd", "dtshd",      # audio sans perte
)


def _needs_mkv_codec(codec: str) -> bool:
    low = (codec or "").lower()
    return any(frag in low for frag in _MKV_ONLY_CODECS)


SUFFIX_BY_ACTION: dict["VideoAction", str] = {
    VideoAction.ENCODE_HEVC: "_[hevc]",
    VideoAction.ENCODE_H264: "_[H264]",
    VideoAction.ENCODE_AV1:  "_[av1]",
    VideoAction.STRIP_DV:    "_[hdr10]",
    VideoAction.SKIP:        "",
}


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
    launch_mode : None = pas de lancement, "dryrun" = dry run, "run" = run immédiat.
    """
    audio:             list[int]                 = field(default_factory=list)
    subtitles:         list[int]                 = field(default_factory=list)
    launch_mode:       str | None                = None  # None | "dryrun" | "run"
    video_override:    Optional["VideoOverride"] = None
    subtitle_indices:  Optional[list[int]]       = None  # None = toutes les pistes



@dataclass
class FileDecision:
    info:              VideoInfo
    profile:           Profile
    video:             VideoDecision
    audio:             list[AudioDecision]  = field(default_factory=list)
    subtitle_indices:       list[int] | None = None  # None = tout garder
    delete_source_override: bool | None      = None  # None = suivre profil
    external_tracks:   list["ExternalTrack"] = field(default_factory=list)
    # Fichier réellement donné à ffmpeg, quand il diffère de la source : c'est
    # le cas après un mux préalable, qu'une piste étirée impose. `info.path`
    # reste la source, dont dépend le nom de sortie — l'intermédiaire vit dans
    # le dossier temporaire et ne doit pas déterminer où le résultat atterrit.
    encode_source:     Path | None = None

    @property
    def kept_subtitles(self) -> list:
        """Pistes de sous-titres retenues par la sélection (None = toutes).

        Le conteneur peut en écarter d'autres ensuite — voir
        `sous_titres_ecartes` et `subtitles_finales`.
        """
        if self.subtitle_indices is None:
            return list(self.info.subtitle_tracks)
        return [st for st in self.info.subtitle_tracks
                if st.index in self.subtitle_indices]

    @property
    def subtitles_finales(self) -> list:
        """Ce qui atterrira vraiment dans le fichier de sortie."""
        ecartes = self.sous_titres_ecartes
        return [st for st in self.kept_subtitles if st not in ecartes]

    def _mkv_impose_par_l_audio(self) -> bool:
        """Une piste sans perte recopiée telle quelle ne tient pas en MP4.

        On ne la sacrifie jamais : c'est une piste que l'utilisateur a demandé
        de conserver, et la perdre serait une perte de contenu, pas de
        confort.
        """
        if any(ad.action == AudioAction.COPY and ad.track.is_lossless
               for ad in self.audio):
            return True
        return any(_needs_mkv_codec(ext.codec) for ext in self.external_tracks)

    @property
    def sous_titres_ecartes(self) -> list:
        """Sous-titres que le conteneur MP4 oblige à laisser de côté.

        Vide hors du mode `container = "mp4"`, et vide aussi lorsque ces
        sous-titres sont les **seuls** du fichier : on préfère alors garder le
        MKV plutôt que produire une sortie muette. Écarter une piste doublée
        par un SubRip ne coûte rien ; écarter la dernière coûte le sous-titre.
        """
        if self.profile.get("container", "auto") != "mp4":
            return []
        # Si l'audio impose déjà le Matroska, la sortie y reste : rien à
        # écarter, et pas de circularité avec `needs_mkv`.
        if self._mkv_impose_par_l_audio():
            return []
        images = [st for st in self.kept_subtitles
                  if st.is_image_based or _needs_mkv_codec(st.codec)]
        if not images or len(images) == len(self.kept_subtitles):
            return []
        return images

    @property
    def needs_mkv(self) -> bool:
        """
        Le conteneur de sortie doit-il être du Matroska ?

        Le critère porte sur ce que le fichier de sortie va contenir : pas son
        histoire, et pas non plus les pistes écartées. Seuls les sous-titres
        image, les sous-titres stylés (ASS/SSA) et l'audio sans perte
        obligent au MKV — un SubRip n'a aucun style à perdre en mov_text.

        Le profil peut forcer la main dans un sens comme dans l'autre, mais
        jamais au prix d'une piste perdue en silence : en `container = "mp4"`,
        un contenu qui ne rentre pas fait revenir au MKV plutôt que
        disparaître.
        """
        voulu = self.profile.get("container", "auto")
        if voulu == "mkv":
            return True

        # Le retrait du RPU passe par mkvmerge en MKV, par ffmpeg en MP4 :
        # les deux sont possibles, le conteneur ne le contraint pas.
        if self._mkv_impose_par_l_audio():
            return True

        return any(st.is_image_based or _needs_mkv_codec(st.codec)
                   for st in self.subtitles_finales)

    @property
    def output_container(self) -> str:
        return ".mkv" if self.needs_mkv else ".mp4"

    @property
    def output_path(self) -> Path:
        stem   = self.info.path.stem
        suffix = self.video.output_suffix
        ext    = self.output_container
        # SKIP + pistes externes : pas de suffixe de codec, donc rien ne
        # distinguerait la sortie de la source. On mux sous _[mux].
        if not suffix and self.external_tracks:
            suffix = MUX_SUFFIX
        return self.info.path.parent / f"{stem}{suffix}{ext}"

    @property
    def audio_summary(self) -> str:
        """Résumé des pistes conservées pour la colonne Audio du browser."""
        # Un remux recopie le fichier tel quel : toutes les pistes passent,
        # aucune n'est transcodée. Afficher la sélection du profil mentirait.
        if self.video.action == VideoAction.STRIP_DV:
            kept_all = [t.display() for t in self.info.audio_tracks]
            return "  ".join(kept_all) if kept_all else "—"

        kept = [
            ad.track.display()
            for ad in self.audio
            if ad.action != AudioAction.EXCLUDE
        ]
        return "  ".join(kept) if kept else "—"


# ─── Logique vidéo ────────────────────────────────────────────────────────────

# Codecs vidéo qu'une chaîne de lecture grand public prend en charge sans
# transcodage — téléviseurs, clients mobiles, décodeurs matériels. Tout le
# reste (VP9, AV1, VC-1, MPEG-2, DivX…) est réencodé, **quelle que soit sa
# résolution** : un fichier illisible chez le destinataire ne devient pas
# lisible parce que son débit est raisonnable.
#
# L'AV1 y figure comme *source* à convertir et non comme cible : les décodeurs
# matériels ne le prennent que sur les modèles récents, et le tour de la
# question se pose au cas par cas.
CODECS_LISIBLES: frozenset[str] = frozenset({"h264", "hevc"})


# Le retrait du RPU demande dovi_tool *et* mkvmerge. Sans eux, proposer
# « → HDR10 » serait proposer une action qui échouera au lancement : la
# décision retombe sur SKIP. L'application le renseigne au démarrage.
_STRIP_DV_AVAILABLE = False


def set_strip_dv_available(ok: bool) -> None:
    """Déclare si dovi_tool et mkvmerge sont tous deux disponibles."""
    global _STRIP_DV_AVAILABLE
    _STRIP_DV_AVAILABLE = ok


_NEAR_1080P_CACHE: tuple[int, int] | None = None


def _near_1080p_thresholds() -> tuple[int, int]:
    """Seuils (largeur, hauteur) au-delà desquels une source est traitée 1080p.

    Lus depuis [decision] dans config.toml, mis en cache au premier appel.
    Permet de couvrir les sources rognées (ex. 1918x1040) sans rabattre en 720p.
    """
    global _NEAR_1080P_CACHE
    if _NEAR_1080P_CACHE is None:
        try:
            from . import config as _cfg
            d = _cfg.load().get("decision", {})
            _NEAR_1080P_CACHE = (
                int(d.get("near_1080p_min_width",  1600)),
                int(d.get("near_1080p_min_height",  850)),
            )
        except Exception:
            _NEAR_1080P_CACHE = (1600, 850)
    return _NEAR_1080P_CACHE


def _resolve_limits(info: VideoInfo, profile: Profile) -> tuple[int, int, int, str]:
    """Retourne (limit_w, limit_h, bucket_h, label).

    limit_w/limit_h : dimensions max de la sortie (downscale si source > limit).
    bucket_h        : hauteur de référence pour le calcul du bitrate (720/1080/2160).
    """
    keep_4k      = profile.get("keep_4k", False)
    is_4k_source = info.height >= 2160 or info.width >= 3840

    if is_4k_source:
        if keep_4k:
            return info.width, info.height, 2160, f"Original {info.width}x{info.height}"
        return 1920, 1080, 1080, "1080p"

    near_w, near_h = _near_1080p_thresholds()
    if info.width >= near_w or info.height >= near_h:
        # Source ≈ 1080p (possiblement rognée) → conserve la résolution d'origine.
        return info.width, info.height, 1080, f"Original {info.width}x{info.height}"

    return 1280, 720, 720, "720p"


def _decide_dv(info: VideoInfo, profile: Profile) -> DVAction:
    if info.dv_profile is None:
        return DVAction.NONE
    opt = profile.get("dolby_vision", "hdr10").lower()
    if opt == "dv":
        return DVAction.DV
    if opt == "sdr":
        return DVAction.SDR
    return DVAction.HDR10  # "hdr10" ou valeur inconnue


def decide_video(info: VideoInfo, profile: Profile) -> VideoDecision:
    """Applique les 4 cas de la spec et retourne la décision vidéo."""
    limit_w, limit_h, bucket_h, _ = _resolve_limits(info, profile)
    dv_action                     = _decide_dv(info, profile)

    # bucket_h = hauteur de référence du bucket de bitrate (720/1080/2160),
    # indépendante de limit_h pour gérer les sources rognées (ex. 1918x1040
    # → limit_h=1040 mais bucket_h=1080).
    target_bps = profile.bitrate_for_height(bucket_h)

    # Pour les cibles < 1080p, H264 compresse mieux que HEVC
    sub_1080  = bucket_h < 1080
    action    = VideoAction.ENCODE_H264 if sub_1080 else VideoAction.ENCODE_HEVC
    suffix    = "_[H264]"              if sub_1080 else "_[hevc]"

    # CAS 1 — Bitrate source ≥ seuil cible
    if info.bitrate >= target_bps:
        return VideoDecision(
            action=action,
            reason=f"Débit {info.kbps}k ≥ {target_bps // 1000}k cible",
            target_bitrate=target_bps,
            target_width=limit_w,
            target_height=limit_h,
            dv_action=dv_action,
            output_suffix=suffix,
        )

    # CAS 2 — Résolution trop grande (débit OK)
    if info.width > limit_w or info.height > limit_h:
        return VideoDecision(
            action=action,
            reason=f"Résolution {info.width}x{info.height} > {limit_w}x{limit_h}",
            target_bitrate=info.bitrate,
            target_width=limit_w,
            target_height=limit_h,
            dv_action=dv_action,
            output_suffix=suffix,
        )

    # CAS 3 — Codec que la chaîne de lecture ne prend pas
    if info.codec.lower() not in CODECS_LISIBLES:
        return VideoDecision(
            action=action,
            reason=f"Codec {info.codec} non lu par la chaîne",
            target_bitrate=info.bitrate,
            target_width=limit_w,
            target_height=limit_h,
            dv_action=dv_action,
            output_suffix=suffix,
        )

    # Rien à réencoder, mais un RPU Dolby Vision à retirer : le profil demande
    # du HDR10 et la couche de base en est déjà. Un remux suffit — l'image
    # ressort bit à bit identique, et le HDR10+ éventuel survit, ce qu'aucun
    # réencodage ne permet.
    if _STRIP_DV_AVAILABLE and dv_action == DVAction.HDR10 and info.can_strip_dv:
        return VideoDecision(
            action=VideoAction.STRIP_DV,
            reason=f"{info.dv_label} → HDR10 sans réencodage",
            target_bitrate=0,
            target_width=info.width,
            target_height=info.height,
            dv_action=dv_action,
            output_suffix=SUFFIX_BY_ACTION[VideoAction.STRIP_DV],
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

# ─── Réécriture du titre d'une piste transcodée ───────────────────────────────

# Jetons de codec rencontrés dans les titres de pistes, du plus long au plus
# court : « DTS-HD MA » doit l'emporter sur « DTS », et « DDP » sur « DD ».
_CODEC_TOKENS: tuple[str, ...] = (
    "dts-hd ma", "dts-hd hr", "dts-hd", "dtshd", "dts:x", "dts-es", "dts",
    "truehd", "true-hd", "mlp",
    "e-ac3", "eac3", "ddp", "dd+", "ac3", "dd",
    "aac", "flac", "lpcm", "pcm", "opus", "vorbis", "mp3",
)

# Étiquette lisible du codec de sortie, telle qu'elle s'écrit dans un titre.
_CODEC_LABELS: dict[str, str] = {"ac3": "AC3", "eac3": "E-AC3", "aac": "AAC"}

_LAYOUT_RE = re.compile(r"\b[1-7]\.[01]\b")
_ATMOS_RE  = re.compile(r"\s*\batmos\b", re.IGNORECASE)


def _codec_token_re(token: str) -> re.Pattern:
    """Motif d'un jeton de codec, insensible à la casse et borné par des
    non-alphanumériques — sans quoi « DD » se retrouverait dans « ADD »."""
    return re.compile(rf"(?<![0-9A-Za-z]){re.escape(token)}(?![0-9A-Za-z])",
                      re.IGNORECASE)


def retitle(title: str, out_codec: str,
            src_channels: int, out_channels: int) -> Optional[str]:
    """Titre corrigé d'une piste transcodée, ou None s'il n'y a rien à corriger.

    Un titre comme « ENG VO : TrueHD 5.1 » survit tel quel au transcodage et
    annonce alors un codec que le fichier ne contient plus. On ne réécrit que
    ce qui devient faux : le jeton de codec, la disposition si elle change, et
    la mention Atmos — les objets sonores ne survivent pas à une conversion
    vers AC3 ou E-AC3. Un titre qui ne dit rien du format (« English ») est
    laissé intact : il n'a jamais menti.
    """
    if not title:
        return None

    label   = _CODEC_LABELS.get(out_codec, out_codec.upper())
    nouveau = title
    touche  = False

    for token in _CODEC_TOKENS:
        motif = _codec_token_re(token)
        if motif.search(nouveau):
            nouveau = motif.sub(label, nouveau, count=1)
            touche  = True
            break

    if touche and _ATMOS_RE.search(nouveau):
        nouveau = _ATMOS_RE.sub("", nouveau)

    if out_channels and out_channels != src_channels:
        remplace = channel_layout_label(out_channels)
        if _LAYOUT_RE.search(nouveau):
            nouveau = _LAYOUT_RE.sub(remplace, nouveau, count=1)
            touche  = True

    if not touche:
        return None

    # Un jeton retiré laisse des espaces doubles et parfois un séparateur nu.
    nouveau = re.sub(r"\s{2,}", " ", nouveau).strip()
    nouveau = re.sub(r"[\s:\-–]+$", "", nouveau).strip()
    return nouveau or None


# Plafonds réels des encodeurs ffmpeg, mesurés et non déduits de la norme :
# l'AC3 ramène silencieusement toute demande supérieure à 640 kbps, l'E-AC3
# honore jusqu'à 6144 kbps puis refuse la commande.
CODEC_MAX_BPS: dict[str, int] = {"ac3": 640_000, "eac3": 6_144_000}

# Les deux encodeurs s'arrêtent au 5.1 : « Specified channel layout 7.1 is not
# supported by the ac3 encoder ». ffmpeg négocie le repli tout seul — vérifié,
# la sortie est identique à l'octet près avec ou sans `-ac` — mais la décision
# doit connaître le nombre de canaux réel pour ne pas annoncer du 7.1.
MAX_TRANSCODE_CHANNELS = 6


def _hd_transcode_spec(track: AudioTrack, profile: Profile) -> tuple[str, int, int] | None:
    """Transcodage d'une piste HD au débit de la source, si le profil le demande.

    `audio_hd_codec` vaut `"ac3"` ou `"eac3"` : les pistes TrueHD et DTS sont
    alors converties **au débit présent dans la piste**, plafonné à ce que
    l'encodeur sait produire. Retourne None si l'option est absente, si la
    piste n'est pas concernée, ou si son débit reste inconnu — mieux vaut
    retomber sur le forfait du profil que d'inventer une valeur.
    """
    codec = str(profile.get("audio_hd_codec", "none") or "none").lower()
    if codec not in CODEC_MAX_BPS:
        return None
    if not track.is_hd_audio or track.bitrate <= 0:
        return None
    debit  = min(track.bitrate, CODEC_MAX_BPS[codec])
    canaux = min(track.channels, MAX_TRANSCODE_CHANNELS)
    # 0 = inchangé : ne poser -ac que lorsqu'il y a vraiment un downmix.
    return codec, debit, (canaux if canaux != track.channels else 0)


def _transcode_spec(track: AudioTrack, profile: Profile) -> tuple[str, int, int]:
    """Retourne (codec_sortie, bitrate_bps, canaux_sortie) pour un transcodage.

    canaux_sortie vaut 0 quand la piste garde ses canaux.
    """
    hd = _hd_transcode_spec(track, profile)
    if hd is not None:
        return hd

    ch = track.channels
    if ch == 1:
        return "aac", 64_000, 0
    if ch == 2:
        return "aac", profile.get("audio_stereo_kbps", 192) * 1000, 0
    if ch <= 6:
        return "ac3", profile.get("audio_surround_kbps", 448) * 1000, 0
    # Au-delà du 5.1, l'encodeur AC3 ne connaît pas la disposition : la sortie
    # sera du 5.1, autant que la décision le dise.
    return ("ac3", profile.get("audio_surround_7_1_kbps", 640) * 1000,
            MAX_TRANSCODE_CHANNELS)


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
            out_codec, out_br, out_ch = _transcode_spec(track, profile)
            decisions.append(AudioDecision(
                track=track, action=AudioAction.TRANSCODE,
                reason=f"{reason} · lossless → {out_codec}",
                output_codec=out_codec, output_bitrate=out_br, locked=(i == 0),
                output_channels=out_ch,
            ))
            continue

        if copy_compat and track.is_copy_compat:
            decisions.append(AudioDecision(
                track=track, action=AudioAction.COPY,
                reason=f"{reason} · {codec_lc} compatible → copy",
                output_codec="copy", output_bitrate=0, locked=(i == 0),
            ))
            continue

        out_codec, out_br, out_ch = _transcode_spec(track, profile)
        decisions.append(AudioDecision(
            track=track, action=AudioAction.TRANSCODE,
            reason=f"{reason} · → {out_codec}",
            output_codec=out_codec, output_bitrate=out_br, locked=(i == 0),
            output_channels=out_ch,
        ))

    return decisions


# ─── Point d'entrée ───────────────────────────────────────────────────────────

def force_skip_to_encode(dec: FileDecision) -> FileDecision:
    """Force un fichier SKIP en encodage (HEVC ou H264 si < 1080p).

    Conserve le débit source (pas de gonflement), ajuste dv_action :
    - H264 ne peut pas porter de RPU DV → DV→HDR10 forcé si source DV
    """
    from dataclasses import replace as dc_replace
    if dec.video.action not in (VideoAction.SKIP, VideoAction.STRIP_DV):
        return dec
    sub_1080   = dec.info.height < 1080
    forced_act = VideoAction.ENCODE_H264 if sub_1080 else VideoAction.ENCODE_HEVC
    # H264 incompatible avec DV : si la source est DV et qu'on force H264,
    # convertir en HDR10 (suppression du RPU)
    forced_dv = dec.video.dv_action
    if sub_1080 and forced_dv == DVAction.DV:
        forced_dv = DVAction.HDR10
    return dc_replace(dec, video=dc_replace(
        dec.video,
        action        = forced_act,
        target_bitrate= dec.info.bitrate,
        output_suffix = "_[H264]" if sub_1080 else "_[hevc]",
        dv_action     = forced_dv,
        reason        = ("Forcé manuellement (était SKIP)"
                         if dec.video.action == VideoAction.SKIP
                         else "Forcé manuellement (était retrait DV)"),
    ))


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
