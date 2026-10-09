"""
core/bluray.py — Les titres d'un dossier Blu-ray (`BDMV`), lus dans ses playlists.

Un Blu-ray ne se travaille pas fichier par fichier : `BDMV\\STREAM\\*.m2ts` ne
sont que des clips, et c'est une playlist `BDMV\\PLAYLIST\\*.mpls` qui fait un
titre — une suite de clips, chacun entre un point d'entrée et un point de
sortie, et ses chapitres (IE-120, pratique de MakeMKV et HandBrake). Le
navigateur présente donc les playlists d'un disque comme ses fichiers :

- au-dessus d'une durée minimale, qui écarte menus et boucles ;
- sans doublon : un disque publie souvent deux fois le même titre (le disque
  d'essai : `00001.mpls` sans chapitres, `01001.mpls` avec quatorze) — on
  garde celle qui en porte le plus ;
- la plus longue est le titre principal : c'est elle que le mode récursif
  retient, et elle seule prend le nom du disque sans numéro.

Le format MPLS est lu ici, sans outil : quelques centaines d'octets par
playlist, en-tête et deux tables (éléments de lecture, marques). Les
langues, elles, viennent de mkvmerge par le clip (`scanner._completer_langues`).

Un disque chiffré (AACS) se reconnaît à ses clips : les octets de
synchronisation des paquets n'y sont plus lisibles. Il est refusé, pas lu.
"""
from __future__ import annotations

import logging
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_log = logging.getLogger("iris_encode.bluray")

# Horloge des temps d'une playlist : 45 kHz.
_TICS = 45_000

# Durée minimale par défaut d'un titre présenté — celle de MakeMKV.
DUREE_MIN_DEFAUT_MIN = 2


@dataclass
class TitreDisque:
    """Un titre de disque : ce qui l'identifie, ses fichiers, sa durée, ses
    chapitres. Blu-ray : `chemin` est sa playlist `.mpls`, `clips` ses `.m2ts`.
    DVD (IE-121, `core/dvd.py`) : `chemin` est un nom fictif `TITLE_nn.dvd`
    sous `VIDEO_TS`, `numero` le numéro du titre, `clips` les VOB de son VTS."""
    chemin:    Path
    racine:    Path               # le dossier qui contient `BDMV` ou `VIDEO_TS`
    clips:     list[Path]
    duree:     float              # secondes
    chapitres: list[float] = field(default_factory=list)   # débuts, en secondes
    nom:       str = ""           # le nom du disque
    principal: bool = False       # le plus long du disque
    numero:    int = 0            # titre de DVD ; 0 pour un Blu-ray
    # Blu-ray d'un seul clip qui n'en joue qu'une partie (concert, épisodes) :
    # posé par l'analyse, qui connaît la durée du clip (CR-01).
    partiel:   bool = False

    @property
    def est_dvd(self) -> bool:
        return self.numero > 0

    @property
    def a_extraire(self) -> bool:
        """Faut-il en faire un Matroska avant l'encodage ? Un DVD toujours —
        ffmpeg ne le lit que par son démultiplexeur `dvdvideo` —, un Blu-ray
        quand ses clips sont plusieurs, ou quand il ne joue qu'une partie du
        sien : lu tel quel, le clip donnait tout le concert pour une chanson
        (CR-01). mkvmerge, lui, respecte les bornes de la playlist."""
        return self.est_dvd or len(self.clips) > 1 or self.partiel

    @property
    def taille(self) -> int:
        """Octets lus pour ce titre : la somme de ses clips."""
        total = 0
        for clip in self.clips:
            try:
                total += clip.stat().st_size
            except OSError:
                pass
        return total

    @property
    def nom_sortie(self) -> str:
        """Le stem du fichier produit : le nom du disque, numéroté hors du
        titre principal — deux bonus ne se marchent pas dessus."""
        if self.principal:
            return self.nom
        return f"{self.nom} - {self.chemin.stem}"


# ─── Lecture d'une playlist ───────────────────────────────────────────────────

@dataclass
class _Element:
    clip:   str     # « 00001 »
    entree: int     # tics
    sortie: int     # tics


def lire_mpls(chemin: Path) -> tuple[list[_Element], list[tuple[int, int]]]:
    """Éléments de lecture et marques de chapitre (élément, temps) d'un MPLS.

    Lève ValueError sur ce qui n'est pas une playlist lisible.
    """
    data = chemin.read_bytes()
    if len(data) < 20 or data[:4] != b"MPLS":
        raise ValueError(f"not an MPLS playlist: {chemin.name}")
    debut_liste, debut_marques = struct.unpack_from(">II", data, 8)

    nb_elements = struct.unpack_from(">H", data, debut_liste + 6)[0]
    elements: list[_Element] = []
    pos = debut_liste + 10
    for _i in range(nb_elements):
        longueur = struct.unpack_from(">H", data, pos)[0]
        clip = data[pos + 2:pos + 7].decode("ascii", errors="replace")
        entree, sortie = struct.unpack_from(">II", data, pos + 14)
        elements.append(_Element(clip, entree, sortie))
        pos += 2 + longueur

    nb_marques = struct.unpack_from(">H", data, debut_marques + 4)[0]
    marques: list[tuple[int, int]] = []
    for i in range(nb_marques):
        base = debut_marques + 6 + 14 * i
        type_marque, element, temps = struct.unpack_from(">xBHI", data, base)
        if type_marque == 1:          # marque d'entrée : un chapitre
            marques.append((element, temps))
    return elements, marques


def _titre(mpls: Path, racine: Path) -> Optional[TitreDisque]:
    """Le titre d'une playlist, ou None si elle est illisible ou cite un
    clip absent."""
    try:
        elements, marques = lire_mpls(mpls)
    except (OSError, ValueError, struct.error) as e:
        _log.debug("playlist ignored %s: %s", mpls, e)
        return None
    if not elements:
        return None
    stream = racine / "BDMV" / "STREAM"
    clips = [stream / f"{e.clip}.m2ts" for e in elements]
    if not all(c.is_file() for c in clips):
        return None

    # Le début de chaque élément dans le titre, pour y placer les marques.
    debuts, cumul = [], 0
    for e in elements:
        debuts.append(cumul)
        cumul += max(e.sortie - e.entree, 0)
    duree = cumul / _TICS

    chapitres: list[float] = []
    for element, temps in marques:
        if element >= len(elements):
            continue
        t = (debuts[element] + temps - elements[element].entree) / _TICS
        # Une marque posée sur la fin n'ouvre rien ; deux marques au même
        # instant n'en font qu'une.
        if 0 <= t < duree - 1 and all(abs(t - c) > 0.5 for c in chapitres):
            chapitres.append(t)
    chapitres.sort()
    return TitreDisque(chemin=mpls, racine=racine, clips=clips, duree=duree,
                       chapitres=chapitres)


# ─── Le disque ────────────────────────────────────────────────────────────────

def est_disque(dossier: Path) -> bool:
    """Ce dossier contient-il un Blu-ray (`BDMV\\index.bdmv`) ?"""
    try:
        return (dossier / "BDMV" / "index.bdmv").is_file()
    except OSError:
        return False


def _etiquette_volume(racine: Path) -> str:
    """L'étiquette du volume (Windows), « » ailleurs ou à défaut."""
    if sys.platform != "win32":
        return ""
    import ctypes
    tampon = ctypes.create_unicode_buffer(261)
    ok = ctypes.windll.kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(str(racine)), tampon, len(tampon),
        None, None, None, None, 0)
    return tampon.value if ok else ""


# Ce que Windows refuse dans un nom de fichier, contrôles compris.
_INTERDITS = set('<>:"/\\|?*') | {chr(c) for c in range(32)}


def nom_disque(racine: Path, defaut: str = "BLURAY") -> str:
    """Le nom que prennent les sorties d'un disque.

    Le dossier qui contient `BDMV` — un rip se range sous « Film (2020) ». À
    la racine d'un lecteur, un ISO monté, l'étiquette du volume, ses
    soulignés en espaces (`WITHIN_TEMPTATION_` → « WITHIN TEMPTATION »).

    Une étiquette UDF peut porter ce que Windows refuse dans un nom (« Film:
    Director's Cut ») : ffmpeg échouait sur l'ouverture de la sortie, après
    l'analyse (CR-04). Ces caractères deviennent des espaces, et les points
    et espaces finaux tombent.
    """
    if racine.parent != racine and racine.name:
        return racine.name
    etiquette = "".join(" " if c in _INTERDITS or c == "_" else c
                        for c in _etiquette_volume(racine))
    nom = " ".join(etiquette.split()).rstrip(". ")
    return nom or defaut


def titres(racine: Path, duree_min: float = 0) -> list[TitreDisque]:
    """Les titres d'un disque, par numéro de playlist.

    Les doublons (mêmes clips, mêmes bornes) se réduisent à celui qui porte le
    plus de chapitres. Le titre principal — le plus long — est marqué sur
    l'ensemble, avant le filtre de durée.
    """
    dossier = racine / "BDMV" / "PLAYLIST"
    try:
        playlists = sorted(p for p in dossier.iterdir()
                           if p.suffix.lower() == ".mpls" and p.is_file())
    except OSError:
        return []

    uniques: dict[tuple, TitreDisque] = {}
    for mpls in playlists:
        t = _titre(mpls, racine)
        if t is None:
            continue
        cle = (tuple(t.clips), round(t.duree, 1))
        garde = uniques.get(cle)
        if garde is None or len(t.chapitres) > len(garde.chapitres):
            uniques[cle] = t
    if not uniques:
        return []

    nom = nom_disque(racine)
    liste = sorted(uniques.values(), key=lambda t: t.chemin.name)
    principal = max(liste, key=lambda t: t.duree)
    for t in liste:
        t.nom = nom
        t.principal = t is principal
    return [t for t in liste if t.duree >= duree_min]


def titre(mpls: Path) -> TitreDisque:
    """Le titre d'une playlist, avec le nom et le rang que lui donne son
    disque. Lève ValueError si elle n'en fait pas un."""
    racine = mpls.parent.parent.parent
    for t in titres(racine):
        if t.chemin == mpls:
            return t
    # Doublon écarté au profit d'une jumelle : il reste un titre à part entière.
    t = _titre(mpls, racine)
    if t is None:
        raise ValueError(f"unreadable Blu-ray playlist: {mpls}")
    t.nom = nom_disque(racine)
    return t


def principal(racine: Path) -> Optional[TitreDisque]:
    """Le titre principal d'un disque, ou None."""
    return next((t for t in titres(racine) if t.principal), None)


# ─── Chiffrement ──────────────────────────────────────────────────────────────

# Un clip se lit par unités de 6 144 octets : 32 paquets de 192, chacun ouvert
# par 4 octets d'horodatage puis l'octet de synchronisation 0x47. AACS chiffre
# chaque unité au-delà de ses 16 premiers octets : la synchronisation des
# paquets 2 à 32 disparaît.
_UNITE, _PAQUET = 6144, 192


def clip_chiffre(clip: Path, unites: int = 8) -> bool:
    """Le clip est-il chiffré (AACS) ? Faux s'il ne se lit pas : l'analyse
    dira pourquoi."""
    try:
        with clip.open("rb") as f:
            data = f.read(_UNITE * unites)
    except OSError:
        return False
    for u in range(len(data) // _UNITE):
        base = u * _UNITE
        synchros = sum(data[base + k * _PAQUET + 4] == 0x47 for k in range(1, 32))
        if synchros < 16:
            return True
    return False


def disque_chiffre(racine: Path) -> bool:
    """Le disque est-il chiffré ? Lu sur le premier clip du titre principal."""
    t = principal(racine)
    return t is not None and clip_chiffre(t.clips[0])


# ─── Pour l'encodage ──────────────────────────────────────────────────────────

def _famille(codec: str) -> str:
    """Le codec tel que les deux lectures le comparent : mkvmerge réécrit le
    `pcm_bluray` d'un clip en PCM ordinaire, c'est la même piste."""
    return "pcm" if codec.startswith("pcm_") else codec


def ecart_pistes(info, flux: list[dict]) -> str:
    """Ce qui manque à l'assemblage d'un titre au regard de l'analyse, ou « ».

    La décision numérote les pistes par type d'après ffprobe sur le premier
    clip, puis l'encodage lit le Matroska de mkvmerge. Qu'une piste y manque
    — une AAC d'un `.m2ts` que ffprobe voit et mkvmerge non —, et `-map 0:a:1`
    prenait une autre langue, étiquetée comme la piste voulue (CR-03).
    `flux` : les flux de l'assemblage, lus par ffprobe.
    """
    for genre, pistes in (("audio", info.audio_tracks),
                          ("subtitle", info.subtitle_tracks)):
        attendus = [_famille(p.codec) for p in pistes]
        lus = [_famille(f.get("codec_name", "")) for f in flux
               if f.get("codec_type") == genre]
        if lus != attendus:
            return f"{genre}: {', '.join(attendus) or '-'} → {', '.join(lus) or '-'}"
    return ""


def ffmetadata_chapitres(t: TitreDisque) -> str:
    """Les chapitres du titre au format FFMETADATA, ou « » s'il n'en a pas
    au moins deux. Nommés comme mkvmerge les nomme : « Chapter 01 »…"""
    if len(t.chapitres) < 2:
        return ""
    lignes = [";FFMETADATA1"]
    bornes = t.chapitres + [t.duree]
    for i, (debut, fin) in enumerate(zip(bornes, bornes[1:]), 1):
        lignes += ["[CHAPTER]", "TIMEBASE=1/1000",
                   f"START={round(debut * 1000)}", f"END={round(fin * 1000)}",
                   f"title=Chapter {i:02d}"]
    return "\n".join(lignes) + "\n"


def build_remux_command(t: TitreDisque, sortie: Path) -> list[str]:
    """mkvmerge assemble les clips d'une playlist en un Matroska, chapitres et
    langues compris. Les pistes y gardent l'ordre de celles du premier clip,
    que la décision a numérotées."""
    from .muxer import _mkvmerge_path
    return [_mkvmerge_path, "--gui-mode", "-o", str(sortie), str(t.chemin)]
