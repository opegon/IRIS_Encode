"""
core/entrelacement.py — Nature de l'entrelacement d'une source SD (IE-174).

Les marqueurs du flux ne suffisent pas (IE-122 s'y fiait) : un AVI ne dit
rien (The Kid, `field_order=unknown`), un DVD peut se dire progressif et ne
porter que des images entrelacées (Cure in Orange). L'image tranche, sondée
en quelques passages :

- `idet` sur l'image brute : la part d'images en peigne ;
- `fieldmatch` puis `idet` : la part qui reste en peigne une fois chaque
  demi-image appariée à sa voisine. Un film télécinéma se recompose (The
  Kid : 88% → 7%), une vraie vidéo entrelacée non (Cure in Orange :
  97% → 27 à 47%) — ses deux demi-images sont deux instants ;
- `mpdecimate` après l'appariement : la part d'images uniques. Un pulldown
  3:2 régulier en garde 4 sur 5 ; The Kid, film muet transféré à sa vitesse
  de projection, 2 sur 3 ou 3 sur 4 selon le passage.

Le télécinéma inverse (`fieldmatch`) rend les images du film, définition
verticale entière ; `bwdif` ne reprend que celles qu'il n'a pas su apparier.
La cadence de la source est gardée, doublons compris, sauf pour un 3:2
régulier à 29,97 i/s, ramené à 23,976 par `decimate` (arbitrage de
l'utilisateur, 2026-11-08) : une cadence irrégulière n'a pas de diviseur
juste, et une suppression fixe y laisserait des doublons ou ôterait des
images.
"""
from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .scanner import VideoInfo

_log = logging.getLogger("iris_encode.entrelacement")

# Le désentrelacement d'IE-122 : bwdif, une image par image — la cadence de la
# source. `deint=interlaced` ne touche que les images que le flux marque
# entrelacées : un passage progressif d'une source mixte reste intact.
# `parity=auto` suit l'ordre des trames que le flux déclare.
FILTRE_BWDIF = "bwdif=mode=send_frame:parity=auto:deint=interlaced"

# Sondage : `_POINTS` passages de `_FENETRE` secondes, entre 10 % et 90 % de
# la durée. Mesuré le 2026-11-08 sur des sources 720×480/576 : ~0,2 s par
# passage pour `idet` seul, ~1 s avec l'appariement.
_POINTS  = 6
_FENETRE = 10

# Seuils, sur les mesures du 2026-11-08 (The Kid, Cure in Orange) :
# sous `PEIGNE_MIN` d'images en peigne, la source est progressive ; après
# appariement, au plus `PEIGNE_APPARIE_MAX`, c'est un télécinéma.
PEIGNE_MIN         = 0.10
PEIGNE_APPARIE_MAX = 0.15
# Un 3:2 garde 4 images sur 5 ; une scène fixe en garde moins, un bruit
# fort davantage — l'un comme l'autre écarte `decimate`, le repli sûr.
UNIQUES_3_2 = (0.76, 0.84)

# Cadences candidates : PAL et NTSC.
_CADENCES = (25.0, 30000 / 1001)


class Nature(Enum):
    PROGRESSIF = auto()
    TELECINE   = auto()   # demi-images d'un film, à réapparier
    ENTRELACE  = auto()   # vraie vidéo : deux instants par image


@dataclass(frozen=True)
class Brut:
    """`idet` sur l'image brute d'un passage (détection « multi »)."""
    tff:   int
    bff:   int
    total: int

    @property
    def peigne(self) -> int:
        return self.tff + self.bff


@dataclass(frozen=True)
class Apparie:
    """`idet` après `fieldmatch` (détection « single »), et les images que
    garde `mpdecimate`."""
    peigne:  int
    total:   int
    uniques: int


@dataclass(frozen=True)
class Analyse:
    nature:         Nature
    ordre:          str      # « tff » ou « bff »
    decime:         bool     # 3:2 régulier ramené à 23,976
    peigne:         float    # part d'images en peigne, brute
    peigne_apparie: float    # après appariement


def cadence(info: "VideoInfo") -> float:
    """La cadence déclarée, en images par seconde ; 0 si illisible."""
    num, _sep, den = info.frame_rate.partition("/")
    try:
        return float(num) / float(den or 1)
    except (ValueError, ZeroDivisionError):
        return 0.0


def a_analyser(info: "VideoInfo") -> bool:
    """Une source SD à 25 ou 29,97 i/s, quels que soient ses marqueurs
    (arbitrage du 2026-11-08) ; au-delà, une source qui se dit entrelacée."""
    if info.entrelace:
        return True
    return (0 < info.height <= 576
            and any(abs(cadence(info) - c) < 0.05 for c in _CADENCES))


def _commande(info: "VideoInfo", debut: float, graphe: str,
              ffmpeg_path: str) -> list[str]:
    decodeur = ["-c:v", info.decodeur] if info.decodeur else []
    return [ffmpeg_path, "-hide_banner", "-nostdin", "-nostats",
            "-ss", f"{debut:.1f}", *decodeur, "-i", str(info.lecture),
            "-t", str(_FENETRE), "-filter_complex", graphe,
            "-map", "[sortie]", "-f", "null", "-"]


def build_brut(info: "VideoInfo", debut: float,
               ffmpeg_path: str = "ffmpeg") -> list[str]:
    """La commande qui compte les images en peigne d'un passage (~0,2 s)."""
    return _commande(info, debut, "[0:v:0]idet@brut[sortie]", ffmpeg_path)


def build_apparie(info: "VideoInfo", debut: float, ordre: str,
                  ffmpeg_path: str = "ffmpeg") -> list[str]:
    """La commande qui apparie les demi-images d'un passage et compte ce qui
    reste en peigne et ce qui est unique (~1 s)."""
    graphe = (f"[0:v:0]fieldmatch=order={ordre}:combmatch=full,split[a][b];"
              f"[a]idet@apparie,nullsink;[b]mpdecimate,idet@uniques[sortie]")
    return _commande(info, debut, graphe, ffmpeg_path)


_IDET_RE = re.compile(
    r"\[idet@(?P<nom>\w+) @ [^\]]*\] (?P<type>Single|Multi) frame detection: "
    r"TFF:\s*(?P<tff>\d+) BFF:\s*(?P<bff>\d+) Progressive:\s*(?P<prog>\d+) "
    r"Undetermined:\s*(?P<und>\d+)")


def _comptes(sortie: str) -> dict[tuple[str, str], tuple[int, int, int, int]]:
    """Les comptes de chaque `idet`. ffmpeg en écrit deux par filtre, l'un à
    zéro (un premier graphe, configuré puis jeté) : le plus fourni compte."""
    comptes: dict[tuple[str, str], tuple[int, int, int, int]] = {}
    for m in _IDET_RE.finditer(sortie):
        c = (int(m["tff"]), int(m["bff"]), int(m["prog"]), int(m["und"]))
        cle = (m["nom"], m["type"])
        if sum(c) >= sum(comptes.get(cle, (0,))):
            comptes[cle] = c
    return comptes


def lire_brut(sortie: str) -> Optional[Brut]:
    """La mesure brute d'un passage ; None si ffmpeg n'a rien compté."""
    c = _comptes(sortie).get(("brut", "Multi"))
    return Brut(c[0], c[1], sum(c)) if c and sum(c) else None


def lire_apparie(sortie: str) -> Optional[Apparie]:
    """La mesure après appariement ; None si ffmpeg n'a rien compté."""
    c = _comptes(sortie)
    a, u = c.get(("apparie", "Single")), c.get(("uniques", "Multi"))
    if not a or not sum(a) or u is None:
        return None
    return Apparie(a[0] + a[1], sum(a), sum(u))


def ordre(bruts: list[Brut]) -> str:
    """L'ordre des trames qu'a vu `idet` : « tff » sauf majorité BFF."""
    return "bff" if sum(b.bff for b in bruts) > sum(b.tff for b in bruts) else "tff"


def peigne(bruts: list[Brut]) -> float:
    """La part d'images en peigne, sur tous les passages."""
    total = sum(b.total for b in bruts)
    return sum(b.peigne for b in bruts) / total if total else 0.0


def classer(bruts: list[Brut], apparies: list[Apparie],
            cadence_source: float) -> Optional[Analyse]:
    """La nature de la source, des mesures de ses passages. Sans mesure
    après appariement, une image sans peignes suffit à dire « progressif »."""
    if not bruts:
        return None
    o, p = ordre(bruts), peigne(bruts)
    if p < PEIGNE_MIN:
        return Analyse(Nature.PROGRESSIF, o, False, p, 0.0)
    if not apparies:
        return None
    apparie = sum(a.peigne for a in apparies) / sum(a.total for a in apparies)
    nature = Nature.TELECINE if apparie <= PEIGNE_APPARIE_MAX else Nature.ENTRELACE
    bas, haut = UNIQUES_3_2
    decime = (nature == Nature.TELECINE
              and abs(cadence_source - 30000 / 1001) < 0.05
              and all(bas <= a.uniques / a.total <= haut for a in apparies))
    return Analyse(nature, o, decime, p, apparie)


def _mesurer(info: "VideoInfo", commande, lecteur) -> list:
    mesures = []
    for i in range(_POINTS):
        debut = info.duration * (0.1 + 0.8 * i / max(_POINTS - 1, 1))
        try:
            r = subprocess.run(commande(debut), stdin=subprocess.DEVNULL,
                               capture_output=True, timeout=60,
                               encoding="utf-8", errors="replace")
        except (OSError, subprocess.TimeoutExpired) as e:
            _log.warning("idet %s @%.0f: %s", info.path, debut, e)
            continue
        m = lecteur(r.stderr)
        if m is not None:
            mesures.append(m)
    return mesures


def analyser(info: "VideoInfo", ffmpeg_path: str = "ffmpeg") -> Optional[Analyse]:
    """Sonde la source ; None si ffmpeg n'a rien mesuré. L'appariement, cinq
    fois plus coûteux, n'est tenté que sur une image qui a des peignes."""
    bruts = _mesurer(info, lambda d: build_brut(info, d, ffmpeg_path), lire_brut)
    apparies = []
    if bruts and peigne(bruts) >= PEIGNE_MIN:
        o = ordre(bruts)
        apparies = _mesurer(info, lambda d: build_apparie(info, d, o, ffmpeg_path),
                            lire_apparie)
    analyse = classer(bruts, apparies, cadence(info))
    _log.info("interlacing %s: %s", info.path, analyse)
    return analyse


def filtre(info: "VideoInfo") -> Optional[str]:
    """Le filtre qui rend l'image progressive, ou None. Sans analyse, ou
    quand l'analyse ne voit rien, les marqueurs décident, comme avant
    IE-174 : un flux qui se dit entrelacé passe par `FILTRE_BWDIF`."""
    a = info.entrelacement
    if a is not None and a.nature == Nature.TELECINE:
        f = f"fieldmatch=order={a.ordre}:combmatch=full,{FILTRE_BWDIF}"
        return f + ",decimate" if a.decime else f
    if a is not None and a.nature == Nature.ENTRELACE and not info.entrelace:
        # Images non marquées (AVI) ou marquées sans que le flux le dise :
        # `deint=interlaced` pourrait n'en toucher aucune.
        return f"bwdif=mode=send_frame:parity={a.ordre}:deint=all"
    return FILTRE_BWDIF if info.entrelace else None
