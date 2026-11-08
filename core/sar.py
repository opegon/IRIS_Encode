"""
core/sar.py — Forme des pixels d'une source SD qui ne la déclare pas (IE-173).

Un DVD converti en AVI sans redimensionnement garde son 720×480 ou 720×576,
mais perd le SAR qui disait comment l'étirer : l'image s'affiche déformée
(The Kid : 4:3 vu en 3:2). Le SAR d'origine ne se déduit pas avec certitude ;
trois indices l'approchent, du plus sûr au moins sûr :

1. les métadonnées : ffprobe lit déjà le SAR du conteneur et du flux (en-tête
   VOL d'un MPEG-4, bloc `vprp` d'un AVI) — s'il y en a un, il n'y a pas de
   doute, `sar_douteux` le dit ;
2. le format d'origine du film (Wikidata, propriété P2061), confronté à la
   zone d'image utile : un film en 1,33 dans un cadre 16:9 aurait des bandes
   latérales ;
3. les bandes noires seules : l'hypothèse qui tombe sur un format de cinéma
   connu l'emporte — sauf image pleine, où les deux y tombent (1,33 / 1,78).

Sans indice décisif, l'hypothèse 4:3 est retenue par défaut et dite
« indéterminée » : c'est à l'utilisateur de trancher, image à l'appui.
"""
from __future__ import annotations

import functools
import logging
import re
import subprocess
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .scanner import VideoInfo

_log = logging.getLogger("iris_encode.sar")

# SAR de chaque hypothèse, par géométrie. 720 de large : convention DVD, le
# cadre entier fait le format ; 704 : convention ITU-R BT.601.
SAR: dict[tuple[int, int], dict[str, str]] = {
    (720, 480): {"4:3": "8:9",   "16:9": "32:27"},
    (720, 576): {"4:3": "16:15", "16:9": "64:45"},
    (704, 480): {"4:3": "10:11", "16:9": "40:33"},
    (704, 576): {"4:3": "12:11", "16:9": "16:11"},
}
HYPOTHESES = ("4:3", "16:9")
DEFAUT     = "4:3"

# Ce que ffprobe rend quand le SAR manque ; « 1:1 » aussi, que Xvid écrit par
# défaut, et qu'aucun 720×480 n'a voulu dire.
_SANS_SAR = {"", "N/A", "0:1", "1:1"}

# Formats de cinéma et de télévision auxquels une image utile se compare.
FORMATS_STANDARD = (1.33, 1.37, 1.66, 1.78, 1.85, 2.0, 2.2, 2.35, 2.39, 2.55, 2.76)
# Écart relatif : sous `PROCHE`, l'hypothèse tombe sur le format ; l'autre
# doit en être à `LOIN` au moins pour trancher. Les bords d'une numérisation
# (une dizaine de pixels) décalent la mesure de 2 à 3 %.
PROCHE = 0.05
LOIN   = 0.10


class Confiance(Enum):
    PROBABLE    = auto()   # un indice tranche
    INDETERMINE = auto()   # rien ne tranche : hypothèse par défaut


class Raison(Enum):
    """Sur quoi repose l'hypothèse retenue. Une valeur : le libellé est
    l'affaire de l'écran."""
    FORMAT_CONNU = auto()   # format d'origine du film, confronté au cadre
    BANDES       = auto()   # bandes noires : un seul format standard possible
    AUCUN        = auto()


@dataclass(frozen=True)
class Estimation:
    hypothese: str                          # « 4:3 » ou « 16:9 »
    confiance: Confiance
    raison:    Raison
    sar:       str                          # le SAR de l'hypothèse
    cadre:     Optional[tuple[int, int]]    # image utile mesurée, ou None
    formats:   tuple[float, ...] = ()       # formats d'origine connus


def sar_douteux(info: "VideoInfo") -> bool:
    """Une géométrie de DVD sans SAR déclaré. Un titre de disque lu en direct
    porte toujours le sien (MPEG-2)."""
    return (info.titre is None and (info.width, info.height) in SAR
            and info.sar in _SANS_SAR)


def ratio_affiche(cadre: tuple[int, int], sar: str) -> float:
    """Le format de l'image utile `cadre` (largeur, hauteur) vue avec `sar`."""
    num, den = (int(x) for x in sar.split(":"))
    return cadre[0] * num / den / cadre[1]


def _ecart(ratio: float, formats: tuple[float, ...]) -> float:
    """Écart relatif de `ratio` au plus proche de `formats`."""
    return min(abs(ratio - f) / f for f in formats)


def _trancher(ecarts: dict[str, float]) -> Optional[str]:
    """L'hypothèse seule proche d'un format, l'autre loin ; None sinon."""
    proches = [h for h, e in ecarts.items() if e <= PROCHE]
    if len(proches) == 1 and all(e >= LOIN for h, e in ecarts.items() if h != proches[0]):
        return proches[0]
    return None


def estimer(largeur: int, hauteur: int, cadre: Optional[tuple[int, int]],
            formats: tuple[float, ...] = ()) -> Estimation:
    """L'hypothèse la plus probable pour une source `largeur`×`hauteur` sans
    SAR, d'après l'image utile mesurée et les formats d'origine connus."""
    sars = SAR[(largeur, hauteur)]
    vue = cadre or (largeur, hauteur)
    ratios = {h: ratio_affiche(vue, sars[h]) for h in HYPOTHESES}

    def _retenue(h: str, raison: Raison) -> Estimation:
        return Estimation(h, Confiance.PROBABLE, raison, sars[h], cadre, formats)

    if formats:
        h = _trancher({h: _ecart(r, formats) for h, r in ratios.items()})
        if h is not None:
            return _retenue(h, Raison.FORMAT_CONNU)
    if cadre is not None:
        h = _trancher({h: _ecart(r, FORMATS_STANDARD) for h, r in ratios.items()})
        if h is not None:
            return _retenue(h, Raison.BANDES)
    return Estimation(DEFAUT, Confiance.INDETERMINE, Raison.AUCUN, sars[DEFAUT],
                      cadre, formats)


def choix(info: "VideoInfo") -> list[tuple[str, str]]:
    """Ce que l'utilisateur peut retenir : (hypothèse, SAR). « 1:1 » laisse
    l'image telle quelle, en pixels carrés (SAR imposé vide)."""
    sars = SAR[(info.width, info.height)]
    return [(h, sars[h]) for h in HYPOTHESES] + [("1:1", "")]


# ─── Indice 2 : la zone d'image utile ─────────────────────────────────────────

# Points de mesure, répartis entre 10 % et 90 % de la durée ; à chacun, les
# images clés de `_FENETRE` secondes (`-skip_frame nokey` : ~2 s pour tout un
# film AVI). Une scène sombre rétrécit la zone détectée, les bandes jamais :
# le cadre est le maximum de chaque dimension sur tous les points.
_POINTS  = 8
_FENETRE = 20
_CROP_RE = re.compile(r"crop=(\d+):(\d+):\d+:\d+")


def build_cropdetect(info: "VideoInfo", debut: float,
                     ffmpeg_path: str = "ffmpeg") -> list[str]:
    """La commande qui mesure l'image utile autour de `debut`."""
    decodeur = ["-c:v", info.decodeur] if info.decodeur else []
    return [ffmpeg_path, "-hide_banner", "-nostdin", "-skip_frame", "nokey",
            "-ss", f"{debut:.1f}", *decodeur, "-i", str(info.lecture),
            "-t", str(_FENETRE), "-map", "0:v:0",
            "-vf", "cropdetect=limit=24:round=2:reset=0", "-f", "null", "-"]


def cadre_mesure(sorties: list[str]) -> Optional[tuple[int, int]]:
    """Le cadre (largeur, hauteur) tiré des journaux de `cropdetect` : le
    maximum de chaque dimension sur toutes les mesures."""
    mesures = [(int(m.group(1)), int(m.group(2)))
               for s in sorties for m in _CROP_RE.finditer(s)]
    if not mesures:
        return None
    return max(l for l, _h in mesures), max(h for _l, h in mesures)


def mesurer_cadre(info: "VideoInfo", ffmpeg_path: str = "ffmpeg") -> Optional[tuple[int, int]]:
    """La zone d'image utile de la source, ou None si ffmpeg n'a rien dit."""
    sorties = []
    for i in range(1, _POINTS + 1):
        debut = info.duration * (0.1 + 0.8 * (i - 1) / max(_POINTS - 1, 1))
        try:
            r = subprocess.run(build_cropdetect(info, debut, ffmpeg_path),
                               stdin=subprocess.DEVNULL, capture_output=True,
                               timeout=60, encoding="utf-8", errors="replace")
        except (OSError, subprocess.TimeoutExpired) as e:
            _log.warning("cropdetect %s @%.0f: %s", info.path, debut, e)
            continue
        sorties.append(r.stderr)
    return cadre_mesure(sorties)


# ─── Indice 3 : le format d'origine (Wikidata) ────────────────────────────────

_API     = "https://www.wikidata.org/w/api.php"
_TIMEOUT = 10
# Libellés anglais des valeurs de P2061 : « 4:3 », « 2.35:1 », « Academy ratio ».
_FORMAT_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\s*$")
_FORMATS_NOMMES = {"academy ratio": 1.375}


def format_du_libelle(libelle: str) -> Optional[float]:
    """« 2.35:1 » → 2.35, « 4:3 » → 1.333…, « Academy ratio » → 1.375."""
    m = _FORMAT_RE.match(libelle)
    if m:
        num, den = float(m.group(1)), float(m.group(2))
        return num / den if den else None
    return _FORMATS_NOMMES.get(libelle.strip().lower())


def _get(params: dict) -> dict:
    import requests
    from version import __version__
    r = requests.get(_API, params={**params, "format": "json"}, timeout=_TIMEOUT,
                     headers={"User-Agent": f"IRIS_Encode/{__version__}"})
    r.raise_for_status()
    return r.json()


def _annee(claims: dict) -> Optional[int]:
    """L'année de la première date de publication (P577)."""
    annees = []
    for c in claims.get("P577", []):
        temps = (c.get("mainsnak", {}).get("datavalue", {})
                 .get("value", {}).get("time", ""))
        m = re.match(r"[+-](\d{4})", temps)
        if m:
            annees.append(int(m.group(1)))
    return min(annees) if annees else None


def _valeurs(claims: dict, prop: str) -> list[str]:
    return [c["mainsnak"]["datavalue"]["value"]["id"]
            for c in claims.get(prop, [])
            if c.get("mainsnak", {}).get("datavalue")]


def titres_a_chercher(titre: str) -> list[str]:
    """Le titre, puis sans ses parenthèses : « The Kid (and A Dog's Life) »
    ne trouve rien, « The Kid » trouve le film de 1921."""
    court = re.sub(r"\s*\([^)]*\)", "", titre).strip()
    return [titre] + ([court] if court and court != titre else [])


@functools.lru_cache(maxsize=256)
def format_connu(titre: str, annee: Optional[int]) -> tuple[float, ...]:
    """Les formats d'origine d'un film, d'après Wikidata ; () si le film
    n'est pas trouvé, pas daté de `annee`, ou le réseau absent.

    Sans année, rien : sept films s'appellent « The Kid ».
    """
    if not titre or annee is None:
        return ()
    try:
        for t in titres_a_chercher(titre):
            res = _get({"action": "query", "list": "search", "srlimit": 10,
                        "srsearch": f"{t} haswbstatement:P2061"})
            ids = [r["title"] for r in res.get("query", {}).get("search", [])]
            if not ids:
                continue
            ent = _get({"action": "wbgetentities", "ids": "|".join(ids),
                        "props": "claims"}).get("entities", {})
            for qid in ids:     # dans l'ordre de pertinence
                claims = ent.get(qid, {}).get("claims", {})
                a = _annee(claims)
                if a is None or abs(a - annee) > 1:
                    continue
                valeurs = _valeurs(claims, "P2061")
                if not valeurs:
                    continue
                libs = _get({"action": "wbgetentities", "ids": "|".join(valeurs),
                             "props": "labels", "languages": "en"}).get("entities", {})
                formats = {format_du_libelle(libs.get(v, {}).get("labels", {})
                                             .get("en", {}).get("value", ""))
                           for v in valeurs}
                return tuple(sorted(f for f in formats if f))
    except Exception as e:      # réseau, quota, réponse inattendue
        _log.warning("wikidata %s (%s): %s", titre, annee, e)
    return ()


# ─── Aperçu : les deux hypothèses côte à côte (IE-173 3/3) ────────────────────

# Une image prise vers le quart du film (le début est souvent un générique) :
# `thumbnail` retient la plus représentative de `_APERCU_IMAGES` images
# consécutives, ce qui écarte un noir ou un fondu. ~0,4 s sur The Kid.
APERCU_DEBUT   = 0.25
_APERCU_IMAGES = 150
_POLICE        = Path(r"C:\Windows\Fonts\arial.ttf")


def largeur_affichee(largeur: int, sar: str) -> int:
    """La largeur en pixels carrés, paire, comme la rendra l'encodage."""
    if not sar:
        return largeur
    num, den = (int(x) for x in sar.split(":"))
    return largeur * num // den // 2 * 2


def chemin_apercu(info: "VideoInfo") -> Path:
    """Où l'image de comparaison s'écrit : le dossier temporaire du système,
    jamais à côté de la source (lecture seule, partage réseau)."""
    import tempfile
    return Path(tempfile.gettempdir()) / f"iris_proportion_{Path(info.path).stem}.png"


def _etiquette(texte: str, police: Path) -> str:
    """`drawtext` en haut à gauche ; les deux-points s'échappent."""
    chemin = police.as_posix().replace(":", r"\:")
    return (f",drawtext=fontfile='{chemin}':text='{texte.replace(':', chr(92) + ':')}'"
            ":x=12:y=12:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=6")


def build_apercu(info: "VideoInfo", sortie: Path, ffmpeg_path: str = "ffmpeg",
                 police: Optional[Path] = None) -> list[str]:
    """La commande qui pose la même image en 4:3 (à gauche) et en 16:9 (à
    droite), chacune à sa largeur affichée, étiquetée si `police` est donnée."""
    sars = SAR[(info.width, info.height)]
    debut = max(0.0, min(info.duration * APERCU_DEBUT, info.duration - 10))
    moities = []
    for nom, h in (("g", "4:3"), ("d", "16:9")):
        l = largeur_affichee(info.width, sars[h])
        f = (f"[{nom}0]setsar={sars[h].replace(':', '/')},scale={l}:{info.height},setsar=1"
             + (_etiquette(f"{h}  {l}x{info.height}", police) if police else ""))
        if nom == "g":      # un liseré sombre entre les deux
            f += ",pad=iw+16:ih:0:0:color=0x202020"
        moities.append(f + f"[{nom}]")
    graphe = (f"[0:v]thumbnail={_APERCU_IMAGES},split=2[g0][d0];"
              + ";".join(moities) + ";[g][d]hstack=inputs=2[v]")
    decodeur = ["-c:v", info.decodeur] if info.decodeur else []
    return [ffmpeg_path, "-hide_banner", "-nostdin", "-y", "-ss", f"{debut:.1f}",
            *decodeur, "-i", str(info.lecture), "-an", "-sn",
            "-filter_complex", graphe, "-map", "[v]", "-frames:v", "1", str(sortie)]


def apercu(info: "VideoInfo", ffmpeg_path: str = "ffmpeg") -> Path:
    """Fabrique l'image de comparaison et rend son chemin. Sans police, ou si
    `drawtext` manque au ffmpeg, l'image sort sans étiquettes (4:3 à gauche).
    RuntimeError si ffmpeg échoue."""
    sortie = chemin_apercu(info)
    polices = ([_POLICE] if _POLICE.exists() else []) + [None]
    erreur = ""
    for police in polices:
        # Une image d'un essai précédent ne doit pas passer pour celle-ci.
        try:
            sortie.unlink(missing_ok=True)
        except OSError:
            pass
        try:
            r = subprocess.run(build_apercu(info, sortie, ffmpeg_path, police),
                               stdin=subprocess.DEVNULL, capture_output=True,
                               timeout=120, encoding="utf-8", errors="replace")
        except (OSError, subprocess.TimeoutExpired) as e:
            raise RuntimeError(str(e)) from e
        if r.returncode == 0 and sortie.exists():
            return sortie
        erreur = (r.stderr or "").strip().splitlines()[-1:] or [f"code {r.returncode}"]
        erreur = erreur[0]
    raise RuntimeError(erreur)


# ─── Ensemble ────────────────────────────────────────────────────────────────

def estimer_source(info: "VideoInfo", ffmpeg_path: str = "ffmpeg") -> Estimation:
    """Mesure le cadre, cherche le format d'origine, et estime."""
    from .meta import parse_title
    cadre = mesurer_cadre(info, ffmpeg_path)
    formats = format_connu(*parse_title(Path(info.path)))
    return estimer(info.width, info.height, cadre, formats)
