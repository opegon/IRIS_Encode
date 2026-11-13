"""
tests/outils_reels.py — Les outils réels qu'emploient les tests de bout en bout.

Ces tests cherchaient `bin\\ffmpeg.exe` et rien d'autre : sous Linux ou macOS
(IE-183, IE-184), avec ffmpeg et mkvmerge dans le `PATH`, ils restaient sautés,
et une régression comme le retrait de `-sub_charenc` (CR-50) passait (CR-147).
Le `bin/` du projet d'abord — c'est l'outil que l'application emploie ici, et
celui sur lequel les mesures ont été faites —, le `PATH` ensuite.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
BIN = RACINE / "bin"


def outil(nom: str) -> Path:
    """Le chemin de l'outil `nom` (« ffmpeg », « mkvmerge »…). Absent partout :
    le chemin qu'il aurait dans `bin/`, dont `.exists()` est faux — un test le
    saute comme avant."""
    exe = nom + (".exe" if sys.platform == "win32" else "")
    local = BIN / exe
    if local.exists():
        return local
    trouve = shutil.which(nom)
    return Path(trouve) if trouve else local
