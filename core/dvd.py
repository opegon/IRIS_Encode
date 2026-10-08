"""
core/dvd.py — Les titres d'un dossier DVD (`VIDEO_TS`), lus dans ses IFO.

Un DVD ne se travaille pas VOB par VOB : `VTS_xx_1.VOB`, `VTS_xx_2.VOB`… ne
sont que des tranches de 1 Go d'un même jeu de titres, et recoller les VOB
échoue sur le multi-angle comme sur un VTS à plusieurs titres. Ce sont les
IFO qui disent les titres (IE-121, pratique de HandBrake et MakeMKV) :

- `VIDEO_TS.IFO`, table TT_SRPT : chaque titre, son jeu (VTS), son rang dans
  ce jeu, son nombre de chapitres ;
- `VTS_xx_0.IFO` : le PGC de chaque titre, et sa durée.

Ils sont lus ici, sans outil, comme les playlists d'un Blu-ray
(`core/bluray.py`), dont ce module reprend le modèle de titre et les règles :
durée minimale, doublons réduits, le plus long principal.

**Lecture et extraction** : par le démultiplexeur `dvdvideo` de ffmpeg (7+),
qui ne se trouve que dans un build avec libdvdnav — le BtbN GPL, pas le gyan
« essentials » qui encode. L'outil DVD est donc à part (`outils()`) : celui de
`bin\\dvd\\` s'il est installé, sinon le ffmpeg principal s'il sait lire un DVD.
Il ne fait qu'analyser un titre et l'extraire, sans perte, en Matroska ;
l'encodage reste au ffmpeg principal.

**Chiffrement** : un DVD protégé par CSS ne se lit pas sans libdvdcss, que ces
builds n'ont pas. Il se reconnaît aux paquets brouillés de ses VOB et est
refusé, pas lu.
"""
from __future__ import annotations

import logging
import re
import struct
import subprocess
from pathlib import Path
from typing import Optional

from .bluray import TitreDisque, nom_disque

_log = logging.getLogger("iris_encode.dvd")

_SECTEUR = 2048
SUFFIXE = ".dvd"


# ─── L'outil ──────────────────────────────────────────────────────────────────

_ffmpeg:  Optional[str] = None
_ffprobe: Optional[str] = None


def lit_les_dvd(ffmpeg: str) -> bool:
    """Ce ffmpeg a-t-il le démultiplexeur `dvdvideo` ?"""
    try:
        r = subprocess.run([ffmpeg, "-hide_banner", "-demuxers"],
                           stdin=subprocess.DEVNULL, capture_output=True,
                           timeout=10, encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return False
    return re.search(r"^\s*D\S*\s+dvdvideo\b", r.stdout, re.M) is not None


def chercher_outils(bin_dir: Path, ffmpeg_principal: Optional[str],
                    ffprobe_principal: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """(ffmpeg, ffprobe) qui lisent les DVD, ou (None, None).

    `bin\\dvd\\` d'abord : c'est là que le preflight pose le BtbN. À défaut, le
    ffmpeg principal, s'il sait lire un DVD — un BtbN dans le PATH, par exemple.
    """
    dossier = bin_dir / "dvd"
    for nom in ("ffmpeg.exe", "ffmpeg"):
        ffmpeg, ffprobe = dossier / nom, dossier / nom.replace("ffmpeg", "ffprobe")
        if ffmpeg.is_file() and ffprobe.is_file():
            return str(ffmpeg), str(ffprobe)
    if ffmpeg_principal and ffprobe_principal and lit_les_dvd(ffmpeg_principal):
        return ffmpeg_principal, ffprobe_principal
    return None, None


def set_outils(ffmpeg: Optional[str], ffprobe: Optional[str]) -> None:
    global _ffmpeg, _ffprobe
    _ffmpeg, _ffprobe = ffmpeg, ffprobe


def outils() -> tuple[Optional[str], Optional[str]]:
    return _ffmpeg, _ffprobe


# ─── Lecture des IFO ──────────────────────────────────────────────────────────

def _bcd(octet: int) -> int:
    return (octet >> 4) * 10 + (octet & 0x0F)


def _duree_pgc(data: bytes, pos: int) -> float:
    """Durée d'un PGC : heures, minutes, secondes en BCD, puis images (les deux
    bits de poids fort disent la cadence : 01 = 25, 11 = 29,97)."""
    h, m, s, f = data[pos:pos + 4]
    cadence = 25.0 if (f >> 6) == 1 else 30000 / 1001
    return _bcd(h) * 3600 + _bcd(m) * 60 + _bcd(s) + _bcd(f & 0x3F) / cadence


def _lire_vts(ifo: Path) -> dict[int, tuple[tuple[int, ...], float]]:
    """Pour chaque titre d'un VTS (rang dans le jeu) : ses PGC, sa durée."""
    data = ifo.read_bytes()
    if data[:12] != b"DVDVIDEO-VTS":
        raise ValueError(f"not a VTS IFO: {ifo.name}")
    ptt, pgci = (s * _SECTEUR for s in struct.unpack_from(">II", data, 0xC8))

    nb_pgc = struct.unpack_from(">H", data, pgci)[0]
    durees = {}
    for i in range(nb_pgc):
        decalage = struct.unpack_from(">I", data, pgci + 8 + 8 * i + 4)[0]
        durees[i + 1] = _duree_pgc(data, pgci + decalage + 4)

    nb_titres, _r, fin = struct.unpack_from(">HHI", data, ptt)
    debuts = [struct.unpack_from(">I", data, ptt + 8 + 4 * i)[0] for i in range(nb_titres)]
    titres = {}
    for i, debut in enumerate(debuts):
        borne = debuts[i + 1] if i + 1 < nb_titres else fin + 1
        pgcs: list[int] = []
        for pos in range(ptt + debut, ptt + borne - 3, 4):
            pgc = struct.unpack_from(">H", data, pos)[0]
            if pgc not in pgcs:
                pgcs.append(pgc)
        titres[i + 1] = (tuple(pgcs), sum(durees.get(p, 0.0) for p in pgcs))
    return titres


def _vobs(video_ts: Path, vts: int) -> list[Path]:
    """Les VOB du contenu d'un VTS (pas le `_0`, qui est son menu)."""
    vobs = []
    for n in range(1, 10):
        p = video_ts / f"VTS_{vts:02d}_{n}.VOB"
        if not p.is_file():
            break
        vobs.append(p)
    return vobs


def _video_ts(racine: Path) -> Path:
    return racine / "VIDEO_TS"


def est_disque(dossier: Path) -> bool:
    """Ce dossier contient-il un DVD (`VIDEO_TS\\VIDEO_TS.IFO`) ?"""
    try:
        return (_video_ts(dossier) / "VIDEO_TS.IFO").is_file()
    except OSError:
        return False


def titres(racine: Path, duree_min: float = 0) -> list[TitreDisque]:
    """Les titres d'un DVD, par numéro.

    Deux titres qui jouent les mêmes PGC d'un même VTS n'en font qu'un (le
    premier). Le principal — le plus long — est marqué avant le filtre.
    """
    video_ts = _video_ts(racine)
    try:
        vmg = (video_ts / "VIDEO_TS.IFO").read_bytes()
        if vmg[:12] != b"DVDVIDEO-VMG":
            return []
        srpt = struct.unpack_from(">I", vmg, 0xC4)[0] * _SECTEUR
        nb = struct.unpack_from(">H", vmg, srpt)[0]
    except (OSError, struct.error):
        return []

    jeux: dict[int, dict] = {}
    vus: set[tuple] = set()
    liste: list[TitreDisque] = []
    for i in range(nb):
        base = srpt + 8 + 12 * i
        try:
            chapitres = struct.unpack_from(">H", vmg, base + 2)[0]
            vts, rang = vmg[base + 6], vmg[base + 7]
            if vts not in jeux:
                jeux[vts] = _lire_vts(video_ts / f"VTS_{vts:02d}_0.IFO")
            pgcs, duree = jeux[vts][rang]
        except (OSError, ValueError, KeyError, IndexError, struct.error) as e:
            _log.debug("DVD title %d ignored: %s", i + 1, e)
            continue
        vobs = _vobs(video_ts, vts)
        if not vobs or (vts, pgcs) in vus:
            continue
        vus.add((vts, pgcs))
        liste.append(TitreDisque(
            chemin=video_ts / f"TITLE_{i + 1:02d}{SUFFIXE}", racine=racine,
            clips=vobs, duree=duree, numero=i + 1,
            # Le nombre seul : les temps viennent de l'extraction.
            chapitres=[0.0] * chapitres))
    if not liste:
        return []

    nom = nom_disque(racine, defaut="DVD")
    principal = max(liste, key=lambda t: t.duree)
    for t in liste:
        t.nom = nom
        t.principal = t is principal
    return [t for t in liste if t.duree >= duree_min]


def titre(chemin: Path) -> TitreDisque:
    """Le titre que désigne un `TITLE_nn.dvd`. ValueError s'il n'existe pas."""
    for t in titres(chemin.parent.parent):
        if t.chemin == chemin:
            return t
    raise ValueError(f"unknown DVD title: {chemin}")


def principal(racine: Path) -> Optional[TitreDisque]:
    return next((t for t in titres(racine) if t.principal), None)


# ─── Chiffrement ──────────────────────────────────────────────────────────────

def vob_chiffre(vob: Path, paquets: int = 512) -> bool:
    """Le VOB est-il brouillé (CSS) ? Lu sur ses premiers paquets de 2 048
    octets : un paquet PES vidéo ou audio dont les bits de brouillage
    (`PES_scrambling_control`) ne sont pas nuls. Faux s'il ne se lit pas."""
    try:
        with vob.open("rb") as f:
            data = f.read(_SECTEUR * paquets)
    except OSError:
        return False
    for base in range(0, len(data) - _SECTEUR + 1, _SECTEUR):
        if data[base:base + 4] != b"\x00\x00\x01\xba":
            continue
        # En-tête de paquet MPEG-2 : 14 octets plus son bourrage.
        pes = base + 14 + (data[base + 13] & 0x07)
        if data[pes:pes + 3] != b"\x00\x00\x01":
            continue
        flux = data[pes + 3]
        if flux == 0xE0 or flux == 0xBD or 0xC0 <= flux <= 0xDF:
            if (data[pes + 6] >> 4) & 0x03:
                return True
    return False


def disque_chiffre(racine: Path) -> bool:
    """Le DVD est-il chiffré ? Lu sur le premier VOB du titre principal."""
    t = principal(racine)
    return t is not None and vob_chiffre(t.clips[0])


# ─── Pour l'analyse et l'extraction ───────────────────────────────────────────

def entree(t: TitreDisque) -> list[str]:
    """Les arguments ffmpeg / ffprobe qui ouvrent ce titre. Le dossier
    `VIDEO_TS`, pas la racine : à la racine d'un lecteur, libdvdread croit
    ouvrir un périphérique et échoue (mesuré)."""
    return ["-f", "dvdvideo", "-title", str(t.numero), "-i",
            str(_video_ts(t.racine))]


def build_extraction_command(t: TitreDisque, sortie: Path) -> list[str]:
    """Le titre recopié sans perte en Matroska : vidéo, audio, sous-titres
    (palette comprise), langues et chapitres lus dans l'IFO."""
    ffmpeg = _ffmpeg or "ffmpeg"
    return [ffmpeg, "-y", "-loglevel", "error", "-stats", *entree(t),
            "-map", "0", "-c", "copy", str(sortie)]
