"""
core/ocr.py — Sous-titres image (PGS, VobSub) convertis en texte par OCR
(IE-176, IE-179).

Jellyfin incruste un sous-titre image à la lecture, donc transcode la vidéo.
Un PGS ou un VobSub de DVD que rien ne double dans sa langue devient un SRT : `seconv`, la ligne de
commande de Subtitle Edit, moteur nOCR suivi de sa correction des erreurs d'OCR
courantes.

Mesuré le 2026-11-07 sur quatre films (PGS français, SRT français du même
fichier en référence) : 0,33 à 0,43 % de caractères faux, 90 à 92 % de
sous-titres exacts, 5 à 40 s par film. Tesseract, essayé aussi, perdait tous
les italiques et allait trente à cinquante fois moins vite. Sur le VobSub
français de L'Égyptien (1 479 répliques, 6 s), une seule faute relevée, un
titre en capitales (I lu l).

Tout est rangé dans `bin/seconv/` : l'exécutable et ses deux DLL, la base nOCR
et, dans `dictionnaires/`, ce que la correction lit pour le français (l'anglais
est intégré à seconv). Il manque un fichier : l'OCR n'est pas proposé.
"""
from __future__ import annotations

import platform
import re
from pathlib import Path
from typing import Optional

DOSSIER   = "seconv"
BASE_NOCR = "Latin.nocr"
DICOS     = "dictionnaires"
# Ce que l'archive de seconv doit fournir, et que `chercher_seconv` exige.
DLL       = ("libSkiaSharp.dll", "libHarfBuzzSharp.dll")


def _exe() -> str:
    return "seconv.exe" if platform.system() == "Windows" else "seconv"


def dossier(bin_dir: Path) -> Path:
    return bin_dir / DOSSIER


def chemin_seconv(bin_dir: Path) -> Path:
    return dossier(bin_dir) / _exe()


def fichiers_requis(bin_dir: Path, donnees: list[dict]) -> list[Path]:
    """L'exécutable, ses DLL sous Windows et chaque donnée déclarée dans les
    sources (`[[seconv.donnees]]`, chemins relatifs à `bin/seconv/`)."""
    d = dossier(bin_dir)
    requis = [chemin_seconv(bin_dir)]
    if platform.system() == "Windows":
        requis += [d / nom for nom in DLL]
    requis += [d / x["nom"] for x in donnees]
    return requis


def donnees_declarees() -> list[dict]:
    """Les données que les sources statiques déclarent (`[[seconv.donnees]]`)."""
    from .preflight import _load_releases
    return _load_releases().get("seconv", {}).get("donnees", [])


def chercher_seconv(bin_dir: Path,
                    donnees: Optional[list[dict]] = None) -> Optional[Path]:
    """seconv s'il est complet, sinon None."""
    if donnees is None:
        donnees = donnees_declarees()
    if not donnees:
        return None
    if all(p.is_file() for p in fichiers_requis(bin_dir, donnees)):
        return chemin_seconv(bin_dir)
    return None


# Les sous-titres image que seconv lit, et le fichier où ffmpeg les recopie.
# Le VobSub part dans un Matroska d'une piste, qui garde sa palette (le
# CodecPrivate) : ffmpeg n'écrit pas de `.sub`/`.idx`. Il ne devine pas le
# format d'un `.mks`, d'où le `-f`.
_EXTRACTION = {"hdmv_pgs_subtitle": (".sup", []),
               "dvd_subtitle":      (".mks", ["-f", "matroska"])}
CODECS = frozenset(_EXTRACTION)


def build_extraction(source: Path, pistes: list, dossier_tmp: Path,
                     ffmpeg_path: str = "ffmpeg") -> tuple[list[str], list[Path]]:
    """Une lecture de la source, un fichier par piste image (`.sup` pour un
    PGS, `.mks` pour un VobSub), recopiée telle quelle."""
    cmd = [ffmpeg_path, "-y", "-loglevel", "error", "-i", str(source)]
    chemins = []
    for st in pistes:
        ext, fmt = _EXTRACTION[st.codec.lower()]
        chemin = dossier_tmp / f"{source.stem}.iris_ocr{st.index}{ext}"
        cmd += ["-map", f"0:s:{st.index}", "-c:s", "copy", *fmt, str(chemin)]
        chemins.append(chemin)
    return cmd, chemins


def build_commande_ocr(seconv_path: Path, sup: Path) -> list[str]:
    """seconv sur un `.sup` ou un `.mks` : nOCR, puis la correction des erreurs d'OCR
    courantes seule (pas les quarante règles, qui toucheraient aux temps).
    Le `.srt` sort à côté, même nom (`sortie_ocr`)."""
    d = seconv_path.parent
    return [str(seconv_path), str(sup), "subrip",
            "--ocr-engine:nocr", f"--ocr-db:{d / BASE_NOCR}",
            "--fix-common-errors-rules:FixCommonOcrErrors",
            f"--dictionary-folder:{d / DICOS}",
            f"--output-folder:{sup.parent}",
            f"--output-filename:{sortie_ocr(sup).name}",
            "--overwrite"]


def sortie_ocr(sup: Path) -> Path:
    return sup.with_suffix(".srt")


def repliques_lues(srt: Path) -> int:
    """Le nombre de répliques non vides d'un `.srt` produit. seconv peut
    rendre 0 avec un fichier vide : seul ce compte dit que l'OCR a lu."""
    try:
        texte = srt.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return 0
    n = 0
    for bloc in re.split(r"\r?\n\s*\r?\n", texte.strip()):
        lignes = bloc.splitlines()
        for i, ligne in enumerate(lignes):
            if "-->" in ligne:
                n += any(l.strip() for l in lignes[i + 1:])
                break
    return n


_seconv: Optional[Path] = None


def set_seconv(chemin: Optional[Path]) -> None:
    global _seconv
    _seconv = chemin


def seconv() -> Optional[Path]:
    """seconv retenu au lancement, ou None s'il n'est pas installé."""
    return _seconv
