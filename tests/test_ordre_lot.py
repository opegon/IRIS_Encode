"""
tests/test_ordre_lot.py — Un lot part dans l'ordre alphabétique du tableau.

La sélection du navigateur est un ensemble. L'aperçu, `F2` et le collage le
parcouraient tel quel : le lot suivait l'ordre des hachages, différent d'une
session à l'autre, et l'écran d'encodage affichait les fichiers pêle-mêle.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from tui.screens.browser import BrowserScreen

NOMS = ["Serie.S01E03.mkv", "serie.S01E01.mkv", "Serie.S01E10.mkv",
        "Serie.S01E02.mkv", "Autre.mkv"]


def _ecran(dossier: Path, noms: list[str], coches: list[str]) -> BrowserScreen:
    ecran = object.__new__(BrowserScreen)
    ecran._decisions = {dossier / n: SimpleNamespace(info=SimpleNamespace(path=dossier / n))
                        for n in noms}
    ecran._selected = {dossier / n for n in coches}
    return ecran


def test_les_cochees_sortent_dans_l_ordre_du_tableau(tmp_path):
    ecran = _ecran(tmp_path, NOMS, NOMS)
    ordre = [d.info.path for d in ecran._cochees()]
    # Même tri que `FileNavigator.list_videos`, qui ordonne le tableau.
    assert ordre == sorted(tmp_path / n for n in NOMS)


def test_l_ordre_est_alphabetique(tmp_path):
    ecran = _ecran(tmp_path, NOMS, NOMS)
    noms = [d.info.path.name for d in ecran._cochees()]
    assert noms[0] == "Autre.mkv"
    assert noms.index("Serie.S01E02.mkv") < noms.index("Serie.S01E03.mkv")


def test_une_coche_sans_decision_est_ignoree(tmp_path):
    ecran = _ecran(tmp_path, NOMS[:2], NOMS)
    assert len(ecran._cochees()) == 2
