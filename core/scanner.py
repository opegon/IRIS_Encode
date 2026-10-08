"""
core/scanner.py — Analyse des fichiers vidéo via ffprobe.

Retourne des objets VideoInfo complets incluant pistes audio,
sous-titres et profil Dolby Vision.
"""
from __future__ import annotations

import functools
import json
import logging
import re
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from .bluray import TitreDisque

_log = logging.getLogger("iris_encode.scanner")

# Analyses ffprobe simultanées : le travail est fait par des processus
# externes, l'attente est d'entrée-sortie (un partage réseau surtout). Partagé
# par l'accueil et le mode récursif.
SCAN_WORKERS = 4


# Les flux MPEG (IE-118) : `.ts` des enregistrements TNT et IPTV, `.m2ts` /
# `.mts` des Blu-ray et de l'AVCHD, `.mpg` / `.mpeg` / `.vob` du DVD. Le
# conteneur de sortie n'en dépend pas : il suit la règle commune (§ 8.6).
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({
    ".mp4", ".avi", ".mkv", ".mov", ".wmv",
    ".flv", ".webm", ".m4v", ".3gp",
    ".ts", ".m2ts", ".mts", ".mpg", ".mpeg", ".vob",
})

# La marque que toute sortie de l'application porte en dernier, précédée de la
# caractéristique qui dit ce que le traitement a fait (`.hevc-iris`,
# `.hdr10-iris`…). Le tiret la détache comme le groupe d'une release, en
# minuscules : plus sobre que l'ancien `.IRIS`, qui n'est plus reconnu (§ 8.7).
#
# La casse compte, à dessein : un titre qui finirait par `-Iris` n'est pas une
# sortie, et le filtre le masquerait sans un mot.
MARQUE_IRIS = "-iris"

# Les sorties qui restent des **entrées** : un collage ou une greffe de pistes
# ne sont pas des encodages, et on les encode ensuite. Le filtre ne doit pas
# les masquer, sans quoi le navigateur les rendrait inutiles.
ENTREES_IRIS = ("mux", "join")

# `(n)` : la numérotation de collision, posée après la marque (`resoudre_sorties`).
_RE_MARQUE_IRIS = re.compile(rf"{re.escape(MARQUE_IRIS)}(?:\(\d+\))?$")
# La caractéristique, elle, se lit sans casse : un `.MUX-iris` écrit avant
# le passage aux minuscules reste une entrée.
_RE_ENTREE_IRIS = re.compile(
    rf"\.(?i:{'|'.join(ENTREES_IRIS)}){re.escape(MARQUE_IRIS)}(?:\(\d+\))?$")


# Les fichiers intermédiaires d'un traitement : `<nom>.iris_<étape>.<ext>`
# (`.iris_titre.mkv`, `.iris_audio.mka`, `.iris_st0.srt`, `.iris_premux.mkv`…).
# Une seule forme, reconnue ici et produite partout : laissé par une coupure,
# un intermédiaire n'est pas une source (CR-11).
_RE_INTERMEDIAIRE = re.compile(r"\.iris_[a-z]+\d*$")


def intermediaire(nom: str, etape: str) -> str:
    """Le nom (sans dossier) d'un intermédiaire de `nom` pour une étape."""
    return f"{nom}.iris_{etape}"


def est_intermediaire(stem: str) -> bool:
    """Ce stem est-il celui d'un fichier intermédiaire de l'application ?"""
    return bool(_RE_INTERMEDIAIRE.search(stem))


def deja_produit(stem: str) -> bool:
    """Ce nom de fichier est-il celui d'une sortie de l'application ?

    La marque est cherchée en **fin** de stem : `Film.hevc-iris (copie)` n'est
    pas une sortie que nous venons d'écrire. Les noms de l'ancien schéma
    (`_[hevc]`, `_[av1]`…) ne sont plus reconnus — ils redeviennent des sources.
    Un intermédiaire laissé par une coupure en est une aussi : grisé, hors de
    `Ctrl+A` et du mode récursif, il reste visible pour être supprimé (CR-11).
    """
    if est_intermediaire(stem):
        return True
    return bool(_RE_MARQUE_IRIS.search(stem)) and not _RE_ENTREE_IRIS.search(stem)


def stem_sans_suffixe_produit(stem: str) -> str:
    """Le stem débarrassé de la marque `-iris` qu'il porte, s'il en porte une.

    Réencoder une sortie ne doit pas empiler les marques : `Film.av1-iris`
    réencodé en HEVC donne `Film.hevc-iris`, pas `Film.av1-iris.hevc-iris`.
    Seule la marque part ici ; la caractéristique qui la précède est une marque
    comme une autre, que `FileDecision._stem_a_jour` réécrit si elle a changé
    (le `AV1` part avec les marques de codec) ou laisse si elle reste vraie.

    La numérotation de collision part avec elle — sans cela un
    `Film.hevc-iris(2)` réencodé redonnerait `Film.hevc-iris(2).hevc-iris`.
    `Film (2)`, la copie que fait Windows, n'est pas touché : le compteur ne
    compte que s'il suit immédiatement la marque.

    Un `.mux-iris` ou un `.join-iris` perd aussi sa marque mais garde `mux` ou
    `join` : ils disent d'où vient le fichier, et l'encodage ne l'efface pas.
    """
    return _RE_MARQUE_IRIS.sub("", stem)


# ─── Ce que le nom du fichier produit annonce ────────────────────────────────
#
# Un nom de release décrit la source : sa définition, son codec, son HDR, son
# audio. Le fichier produit n'a plus forcément ces propriétés, et c'est le nom
# — pas le conteneur — que l'utilisateur lit pour choisir. Les fonctions qui
# suivent réécrivent ces marques une à une (§ 8.7).


def _motif_marque(jeton: str) -> str:
    """Le motif d'une marque telle qu'un nom de fichier l'écrit.

    Un nom de release remplace les espaces d'un format par le séparateur qu'il
    s'est choisi : « DTS-HD MA » s'y écrit `DTS-HD.MA`, `DTS-HD-MA` ou
    `DTS HD MA`. Les espaces et tirets du jeton acceptent donc n'importe quel
    séparateur, ou aucun.
    """
    return r"[ ._-]?".join(re.escape(p) for p in re.split(r"[ -]", jeton))


@functools.cache
def _re_marques(jetons: tuple[str, ...]) -> re.Pattern:
    """Le motif qui reconnaît l'une de ces marques dans un stem.

    Trois précautions, chacune payée par un nom cassé :

    - **le plus long d'abord** — sans quoi `DTS` l'emporterait sur `DTS-HD MA`
      et laisserait un `.MA` orphelin ;
    - **mot entier** — le `AV1` de `AV1ator`, le `DD` de `ADD` n'annoncent
      rien. Un `+` compte comme la fin d'une marque, sinon `HDR10+` perdrait
      son `HDR10` et garderait son `+` ;
    - **la paire de crochets ou de parenthèses part avec la marque**, sans
      quoi retirer le `hevc` de `Film [hevc]` laisserait un `[]` vide.

    La ponctuation qui entoure la marque est capturée avec elle : elle doit se
    recoller quand la marque disparaît.
    """
    alt = "|".join(_motif_marque(j) for j in sorted(jetons, key=len, reverse=True))
    return re.compile(
        rf"(?P<avant>[ ._-]*)"
        rf"(?:(?P<ouvre>[\[(])(?:{alt})[\])]"
        rf"|(?<![0-9A-Za-z])(?:{alt})(?![0-9A-Za-z+]))"
        rf"(?P<apres>[ ._-]*)",
        re.IGNORECASE,
    )


def porte_marque(stem: str, jetons: tuple[str, ...]) -> bool:
    """Le stem porte-t-il l'une de ces marques, prise comme mot entier ?"""
    return bool(_re_marques(jetons).search(stem))


def stem_marques_retirees(stem: str, jetons: tuple[str, ...]) -> str:
    """Le stem privé de ces marques, ponctuation recollée.

    `Film.1080p.x265-GROUP` doit donner `Film.1080p-GROUP`, pas
    `Film.1080p.-GROUP`, et une marque en tête ne doit pas laisser un
    séparateur devant le titre.

    Un nom qui ne serait fait que de marques est rendu tel quel : mieux vaut
    un nom redondant qu'un fichier nommé par son seul suffixe.
    """
    sans = _re_marques(jetons).sub(
        lambda m: m.group("apres") if m.group("avant") else "", stem)
    if sans == stem:
        return stem
    # Deux marques en fin de nom laissent le séparateur de la première, qui
    # attendait le texte que la seconde vient d'emporter : `Film.DV.HDR10`
    # rendait `Film.` — un nom que rien ne finit.
    sans = sans.strip(" ._-")
    return sans or stem


def stem_marques_remplacees(stem: str, jetons: tuple[str, ...],
                            remplacement: str) -> str:
    """Le stem dont ces marques annoncent la sortie, non la source.

    La ponctuation et les crochets éventuels sont conservés — la marque
    change, pas la structure du nom. Seule la première marque est remplacée,
    les suivantes partent : `DV.HDR10` ramené en HDR10 donne `HDR10`, pas
    `HDR10.HDR10`, et `Film 4K DV 2160p` ramené en 1080p donne `Film 1080p DV`,
    pas `Film 1080p DV 1080p` — le nom ne dit la définition qu'une fois.
    """
    vues = 0

    def _sub(m: re.Match) -> str:
        nonlocal vues
        vues += 1
        if vues > 1:
            return m.group("apres") if m.group("avant") else ""
        if m.group("ouvre"):
            ferme = "]" if m.group("ouvre") == "[" else ")"
            return f"{m['avant']}{m['ouvre']}{remplacement}{ferme}{m['apres']}"
        return f"{m['avant']}{remplacement}{m['apres']}"

    ecrit = _re_marques(jetons).sub(_sub, stem)
    if vues > 1:
        # Une marque retirée en fin de nom laisse le séparateur qui l'attendait,
        # comme dans `stem_marques_retirees`.
        ecrit = ecrit.rstrip(" ._-")
    double = re.escape(remplacement)
    return re.sub(rf"{double}(?:[ ._-]+{double})+", remplacement, ecrit,
                  flags=re.IGNORECASE)


# Les marques d'une source 4K. `Light` suit le `4K` avec ou sans séparateur
# selon les releases — c'est la marque entière qui part. `UHD` en est une
# aussi : `2160p.UHD.BluRay` disait deux fois la définition, et n'en corriger
# qu'une laissait le nom à moitié faux.
JETONS_RESOLUTION_4K = ("2160p", "4k light", "4k", "uhd")

# Les marques de codec vidéo. `H.264` s'écrit avec ou sans point selon les
# conventions ; `HEVC` est celle que nous écrivons nous-mêmes.
JETONS_CODEC_VIDEO = ("x264", "x265", "h.264", "h264", "h.265", "h265",
                      "hevc", "av1", "vp9")


def stem_resolution_ramenee(stem: str, cible: str) -> str:
    """Le stem dont la marque de résolution annonce la sortie, non la source.

    Un `Film.2160p.BluRay` réencodé en 1080p gardait `2160p` dans son nom : le
    fichier promettait une définition qu'il n'a plus, et deux fichiers de
    définitions différentes se lisaient pareil dans une médiathèque.

    Ne sont reconnues que les marques d'une source 4K — `2160p`, `4K`,
    `4KLight`, `UHD` — et seulement prises comme mot entier : le `4K` de `H4K`
    ou le `2160` de `3840x2160` ne disent pas une résolution de release.

    Un nom qui en porte deux à la suite n'en garde qu'une : `2160p.UHD.BluRay`
    donne `1080p.BluRay`, la fusion des marques voisines devenues identiques
    étant faite par `stem_marques_remplacees()`.
    """
    return stem_marques_remplacees(stem, JETONS_RESOLUTION_4K, cible)


def stem_sans_marque_codec(stem: str) -> str:
    """Le stem débarrassé des marques de codec vidéo qu'il porte.

    Un `Film.1080p.x264` réencodé en HEVC ressortait `Film.1080p.x264.hevc-iris` :
    le nom annonçait deux codecs, dont un que le fichier n'a plus. C'est le
    suffixe produit qui dit le codec de sortie ; les marques de la source n'ont
    plus rien à annoncer, y compris quand elles tombent juste — un `x265` gardé
    à côté de `.hevc-iris` répète la même chose deux fois.

    Sont reconnues `x264`, `x265`, `H264`, `H265` (avec ou sans point), `HEVC`,
    `AV1` et `VP9`.
    """
    return stem_marques_retirees(stem, JETONS_CODEC_VIDEO)


# Les marques qui font d'un nom un nom de release. Elles ne servent qu'à
# reconnaître un tel nom avant d'en retirer le groupe (`stem_sans_groupe`) :
# hors de ce contexte, « - Sous-titre » est une partie du titre.
JETONS_RELEASE = JETONS_RESOLUTION_4K + JETONS_CODEC_VIDEO + (
    "1080p", "720p", "576p", "480p",
    "dolby vision", "dovi", "dv", "hdr10+", "hdr10", "hdr", "10 bits", "10 bit",
    "truehd", "true-hd", "dts-hd ma", "dts-hd", "dts-x", "dts", "dd+", "ddp",
    "e-ac3", "ac3", "atmos", "flac", "aac",
    "multi", "vff", "vf2", "vfq", "vof", "vostfr", "french", "truefrench",
    "bluray", "web-dl", "webrip", "remux", "hdlight", "bdrip", "hdtv",
)

# Le dernier terme d'un nom, détaché par un tiret : `x265-GROUPE`,
# `1080p - GROUPE`. Un mot seul — sans espace, point ni crochet.
_RE_GROUPE = re.compile(r"\s*-\s*(?P<groupe>[^\s.\-\[\](){}]+)$")


def stem_sans_groupe(stem: str) -> str:
    """Le stem privé du groupe de release qui le termine.

    `Film.1080p.x265-GROUPE` et `Film 1080p - GROUPE` donnent `Film.1080p.x265`
    et `Film 1080p` : le groupe signait la source, pas le fichier produit.

    Trois gardes, car un tiret final n'annonce pas toujours un groupe :

    - le reste du nom porte une **marque de release** — sans elle, `Spider-Man`
      ou `Titre - Sous-titre` sont des titres ;
    - le dernier terme n'est pas **lui-même une marque**, ni un morceau de
      marque : `Film.1080p-x265`, `Film.DTS-HD`, `Film.WEB-DL` le gardent ;
    - un nom qui ne serait plus rien est rendu tel quel.
    """
    m = _RE_GROUPE.search(stem)
    if not m:
        return stem
    debut = m.start("groupe")
    for marque in _re_marques(JETONS_RELEASE).finditer(stem):
        if marque.end("avant") <= debut < marque.start("apres"):
            return stem
    reste = stem[: m.start()].rstrip(" ._-")
    if not reste or not porte_marque(reste, JETONS_RELEASE):
        return stem
    return reste


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
# `dvb_subtitle` : les sous-titres en images de la TNT (IE-119), traités comme
# un PGS — Matroska obligatoire, écartés s'ils sont doublés par un texte.
_IMAGE_SUB_CODECS = frozenset({"hdmv_pgs_subtitle", "dvd_subtitle", "dvdsub", "pgssub",
                               "dvb_subtitle"})

# Ce qu'aucun conteneur de sortie ne porte : le télétexte de la TNT. Il se
# décoderait en texte avec libzvbi, absent du ffmpeg de `bin/` ; il est écarté,
# toujours, et le dire suffit (IE-119).
_SOUS_TITRES_NON_PORTABLES = frozenset({"dvb_teletext"})

# Les conteneurs où mkvmerge sait des langues que ffprobe ignore : celles d'un
# Blu-ray sont dans le `.clpi` voisin du `.m2ts` (IE-119, wiki disques-optiques).
_EXTENSIONS_CLPI = frozenset({".m2ts", ".mts"})

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
    # Identifiant du flux dans un flux de transport (PID), None ailleurs. Deux
    # pistes de même PID sont une TrueHD et son cœur AC-3 (IE-119).
    pid:      int | None = None
    # Langue venue d'ailleurs que du flux (mkvmerge, `.clpi`) : ffmpeg ne la
    # recopiera pas, l'encodeur doit l'écrire (IE-119).
    langue_completee: bool = False
    sample_rate: int = 0     # Hz, 0 si inconnu — la jonction le compare (CR-30)

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
    # Le nom déclaré dans le conteneur. Il était lu puis jeté : six pistes
    # « Français (France) », « (forced) », « (SDH) », « (Canada) »… ne se
    # distinguent que par lui, et l'application ne savait pas le dire.
    title:    str = ""
    # Drapeau « forced » du conteneur. Beaucoup de rips ne le posent pas et
    # l'écrivent dans le titre (« FR Forced ») : les deux valent.
    forced:   bool = False
    # Drapeau « par défaut ». Lu pour qu'une piste réécrite à part le garde
    # (`core/sous_titres.py`) : recopiée depuis la source, elle l'emporte seule.
    default:  bool = False
    pid:      int | None = None   # voir AudioTrack.pid
    langue_completee: bool = False  # voir AudioTrack.langue_completee

    @property
    def is_image_based(self) -> bool:
        return self.codec.lower() in _IMAGE_SUB_CODECS

    @property
    def portable(self) -> bool:
        """Un conteneur de sortie sait-il porter cette piste ?"""
        return self.codec.lower() not in _SOUS_TITRES_NON_PORTABLES

    @property
    def is_forced(self) -> bool:
        titre = self.title.lower()
        return self.forced or "forced" in titre or "forcé" in titre


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
    # Ordre des trames déclaré par le flux : « progressive », « tt », « bb »,
    # « tb », « bt », ou « » s'il ne dit rien (IE-122).
    field_order:     str                 = ""
    # ── Métadonnées Dolby Vision enrichies (dovi_tool, optionnel) ────────────
    dv_subprofile:   Optional[str]              = None   # "5", "7.06", "8.1"…
    hdr10_master_display: Optional[str]         = None   # G(...)B(...)R(...)WP(...)L(...)
    hdr10_max_cll:        Optional[tuple[int, int]] = None  # (MaxCLL, MaxFALL)
    # Titre d'un Blu-ray (IE-120) : `path` est alors sa playlist `.mpls`, qui
    # l'identifie dans le navigateur, et `lecture` le fichier que lisent les
    # outils.
    titre: Optional["TitreDisque"] = None

    # ── Propriétés dérivées ──────────────────────────────────────────────────

    @property
    def lecture(self) -> Path:
        """Le fichier que lisent ffmpeg, mkvmerge et mpv : la source, ou le
        premier clip d'un titre de disque — le seul, le plus souvent. Un titre
        de plusieurs clips est assemblé avant l'encodage (`encode_source`)."""
        return self.titre.clips[0] if self.titre else self.path

    @property
    def dossier(self) -> Path:
        """Où la sortie s'écrit par défaut : à côté de la source, ou à côté
        du dossier `BDMV` d'un disque, jamais dedans."""
        return self.titre.racine if self.titre else self.path.parent

    @property
    def taille(self) -> int:
        """Octets de la source — les clips d'un titre de disque. OSError si
        elle ne se lit pas."""
        return self.titre.taille if self.titre else self.path.stat().st_size

    @property
    def stem_sortie(self) -> str:
        """Le nom dont part celui de la sortie."""
        return self.titre.nom_sortie if self.titre else self.path.stem

    @property
    def kbps(self) -> int:
        return self.bitrate // 1000

    @property
    def entrelace(self) -> bool:
        """Le flux se déclare-t-il entrelacé ? Les marqueurs seulement : une
        source qui se dit progressive l'est pour l'application (IE-122)."""
        return self.field_order in ("tt", "bb", "tb", "bt")

    @property
    def has_image_subs(self) -> bool:
        return any(s.is_image_based for s in self.subtitle_tracks)

    @property
    def is_already_encoded(self) -> bool:
        """Vrai si le fichier porte la marque `-iris` d'une sortie d'encodage."""
        return deja_produit(self.path.stem)

    @property
    def is_4k(self) -> bool:
        """Vrai pour une source 4K, recadrée comprise.

        Un film scope recadré sort en 3832x1600 : ni ses 3840 de large ni ses
        2160 de haut. Exiger l'une des deux le faisait passer pour un 1080p,
        gardé tel quel et nommé `2160p`. Les seuils sont ceux du « presque
        1080p » (`near_1080p_min_*`) ramenés à l'échelle : 5/6 de la largeur,
        ~4/5 de la hauteur — hors de portée de toute source HD, 2K DCI compris.
        """
        return self.width >= 3200 or self.height >= 1700

    @property
    def resolution_label(self) -> str:
        if self.is_4k:
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

def _ffprobe_json(args: list[str], outil: str | None = None) -> dict:
    # `-v quiet` pour l'outil DVD : libdvdread signale en erreur ce qui n'en
    # est pas (« Zero check failed », mesuré), et le code de retour suffit.
    niveau = "quiet" if outil else "error"
    cmd = [outil or _ffprobe_path, "-v", niveau, "-print_format", "json"] + args
    # ffprobe, ffmpeg et mkvmerge écrivent en UTF-8. Les lire avec l'encodage
    # local — cp1252 sur un Windows français — fait mourir le thread de lecture
    # de subprocess dès qu'un titre ou un nom de fichier sort de cette table :
    # l'exception n'y remonte pas, `stdout` vaut None, et le fichier est écarté
    # comme illisible. Vu sur un WebM dont un tag portait « ❤️ ».
    r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, timeout=30,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe: {r.stderr.strip()}")
    return json.loads(r.stdout)


def _pid(stream: dict) -> int | None:
    """Le PID d'un flux de transport : ffprobe le donne en `id` (« 0x1101 »)."""
    try:
        return int(stream["id"], 16)
    except (KeyError, TypeError, ValueError):
        return None


def _langue_connue(code: str) -> bool:
    """Une langue dite, pas « und » ni rien."""
    return normalize_language(code) not in ("", "und")


def _completer_langues(path: Path, pistes: list) -> None:
    """Complète par mkvmerge les langues que ffprobe n'a pas lues.

    Sur un `.m2ts` de Blu-ray, ffprobe n'en donne aucune ; mkvmerge les lit
    dans le `.clpi` du disque (mesuré le 2026-10-08, 0,7 s sur 18 Go). Les
    pistes se retrouvent par **PID**, pas par rang : une TrueHD et son cœur
    AC-3 partagent le leur, et en reçoivent la même langue. Sans mkvmerge, ou
    s'il échoue, rien ne change. Une langue déjà lue n'est jamais remplacée.
    """
    if all(_langue_connue(p.language) for p in pistes):
        return
    from .muxer import identify
    par_pid = {t.number: t.language for t in identify(path)
               if t.number is not None and _langue_connue(t.language)}
    for piste in pistes:
        if not _langue_connue(piste.language) and piste.pid in par_pid:
            piste.language = par_pid[piste.pid]
            piste.langue_completee = True


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
    """Analyse complète d'un fichier vidéo, ou d'un titre de Blu-ray désigné
    par sa playlist `.mpls` (IE-120)."""
    if path.suffix.lower() == ".mpls":
        return _scan_titre(path)
    # Un titre de DVD (IE-121) : ffprobe de l'outil DVD, par `dvdvideo`.
    titre_dvd = None
    if path.suffix.lower() == ".dvd":
        from . import dvd
        titre_dvd = dvd.titre(path)
        ffprobe_dvd = dvd.outils()[1]
        if ffprobe_dvd is None:
            raise RuntimeError("no DVD-capable ffprobe")
        data = _ffprobe_json(["-show_streams", "-show_format", *dvd.entree(titre_dvd)],
                             outil=ffprobe_dvd)
    else:
        data = _ffprobe_json(["-show_streams", "-show_format", str(path)])
    streams = data.get("streams", [])
    fmt     = data.get("format", {})
    if titre_dvd is not None and not _safe_int(fmt.get("bit_rate")):
        # `dvdvideo` ne donne pas de débit : celui des VOB sur la durée, que
        # `_video_bitrate` répartit ensuite entre les pistes.
        duree = _safe_float(fmt.get("duration")) or titre_dvd.duree
        if duree > 0:
            fmt["bit_rate"] = str(int(titre_dvd.taille * 8 / duree))

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
            pid=_pid(s),
            sample_rate=_safe_int(s.get("sample_rate")),
        ))

    # ── Flux sous-titres ──────────────────────────────────────────────────────
    subtitle_tracks: list[SubtitleTrack] = []
    for i, s in enumerate(s for s in streams if s.get("codec_type") == "subtitle"):
        tags = s.get("tags", {})
        subtitle_tracks.append(SubtitleTrack(
            index=i,
            codec=s.get("codec_name", "unknown"),
            language=tags.get("language", ""),
            title=tags.get("title", "") or "",
            forced=bool((s.get("disposition") or {}).get("forced")),
            default=bool((s.get("disposition") or {}).get("default")),
            pid=_pid(s),
        ))

    if path.suffix.lower() in _EXTENSIONS_CLPI:
        _completer_langues(path, audio_tracks + subtitle_tracks)

    # ── Dolby Vision ──────────────────────────────────────────────────────────
    dv_profile, dv_bl_compat = (None, None) if titre_dvd else _detect_dv(path)

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
        field_order=vid.get("field_order", "") or "",
        titre=titre_dvd,
    )


def _scan_titre(mpls: Path) -> VideoInfo:
    """Un titre de Blu-ray : les pistes de son premier clip, la durée et le
    nom de la playlist. Les clips suivants d'un titre assemblé portent les
    mêmes pistes — c'est ce qui permet à mkvmerge de les enchaîner."""
    from .bluray import titre as lire_titre
    t = lire_titre(mpls)
    info = scan(t.clips[0])
    info.path, info.titre = mpls, t
    if t.duree > 0 and info.duration > 0:
        info.frame_count = round(info.frame_count * t.duree / info.duration)
        info.duration = t.duree
    return info


def module_disque(dossier: Path):
    """`core.bluray` ou `core.dvd` si `dossier` contient un disque, sinon None.
    Les deux exposent `titres`, `principal` et `disque_chiffre`."""
    from . import bluray, dvd
    if bluray.est_disque(dossier):
        return bluray
    if dvd.est_disque(dossier):
        return dvd
    return None


def scan_directory(directory: Path) -> list[VideoInfo]:
    """
    Scanne tous les fichiers vidéo supportés dans un répertoire (non récursif).
    Ignore ce que l'application a elle-même produit (`deja_produit`).
    Les erreurs de scan sont silencieuses (fichier ignoré).
    """
    results: list[VideoInfo] = []
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if deja_produit(path.stem):
            continue
        try:
            results.append(scan(path))
        except Exception as e:
            _log.warning("scan failed for %s: %s", path, e)
    return results


def scan_directory_recursive(
    root: Path,
    progres: Callable[[int, int], None] | None = None,
) -> list[VideoInfo]:
    """
    Scanne récursivement tous les fichiers vidéo sous root (tous niveaux).
    Même filtres que scan_directory : extensions supportées, pas d'encodés.
    Tri par chemin complet pour un ordre prévisible (saison → épisode).

    Les analyses tournent à `SCAN_WORKERS` à la fois, comme sur l'accueil
    (IE-117) : une à une, une saison sur un partage réseau se comptait en
    minutes. L'ordre des résultats reste celui du tri. `progres(fait, total)`
    est appelé après chaque fichier, depuis le fil qui l'a analysé.
    """
    # Un disque donne son titre principal, pas ses fichiers (IE-120, IE-121) ;
    # chiffré, ou DVD sans outil pour le lire, rien.
    from . import dvd
    disques = {}
    for marque, dossier in (("index.bdmv", "BDMV"), ("VIDEO_TS.IFO", "VIDEO_TS")):
        for f in root.rglob(marque):
            module = module_disque(f.parent.parent)
            if f.parent.name.upper() == dossier and module is not None:
                disques[f.parent] = (f.parent.parent, module)
    chemins = [p for p in sorted(root.rglob("*"))
               if p.is_file()
               and p.suffix.lower() in SUPPORTED_EXTENSIONS
               and not deja_produit(p.stem)
               and not any(p.is_relative_to(d) for d in disques)]
    for racine, module in disques.values():
        if module is dvd and dvd.outils()[1] is None:
            continue
        t = None if module.disque_chiffre(racine) else module.principal(racine)
        if t is not None:
            chemins.append(t.chemin)
    chemins.sort()
    total, fait = len(chemins), 0
    verrou = threading.Lock()

    def _un(path: Path) -> VideoInfo | None:
        nonlocal fait
        try:
            info = scan(path)
        except Exception as e:
            _log.warning("scan failed for %s: %s", path, e)
            info = None
        if progres is not None:
            with verrou:
                fait += 1
                progres(fait, total)
        return info

    if not chemins:
        return []
    with ThreadPoolExecutor(max_workers=min(SCAN_WORKERS, total),
                            thread_name_prefix="scan-rec") as pool:
        return [i for i in pool.map(_un, chemins) if i is not None]


def list_subdirs(directory: Path) -> list[Path]:
    """Liste les sous-répertoires (pour la navigation du browser)."""
    try:
        return sorted(p for p in directory.iterdir() if p.is_dir())
    except PermissionError:
        return []
