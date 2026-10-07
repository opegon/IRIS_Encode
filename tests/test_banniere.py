"""
tests/test_banniere.py — La bannière dit quel Python tourne.

`launch.bat` choisit entre trois candidats — le `.venv` local, le Python du
PATH, celui que `bootstrap.ps1` installe. Le choix est silencieux. Rien à
l'écran ne disait lequel avait gagné, et c'est précisément ce qu'on veut savoir
quand une dépendance manque ou qu'une version surprend.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

import main

ROOT = Path(__file__).resolve().parent.parent


def test_la_banniere_donne_la_version_complete():
    """Majeur.mineur ne suffit pas : un correctif de patch change un comportement."""
    v = sys.version_info
    assert f"Python {v.major}.{v.minor}.{v.micro}" in main._environnement_python()


def test_la_banniere_nomme_lorigine_de_linterpreteur():
    texte = main._environnement_python()
    assert re.search(r"·\s+(\.venv local|système)$", texte), texte


def test_lorigine_suit_lexecutable_reellement_utilise():
    """
    Le `.venv` du dépôt sert de cas réel quand il existe.

    On ne simule pas `sys.executable` : la fonction résout des chemins, et un
    faux chemin ne prouverait que la logique de comparaison. Ici on interroge
    l'interpréteur qui exécute vraiment les tests.
    """
    dans_venv = Path(sys.executable).resolve().is_relative_to(ROOT / ".venv")
    attendu   = ".venv local" if dans_venv else "système"
    assert main._environnement_python().endswith(attendu)


@pytest.mark.parametrize("lignes", [
    ["IRIS ENCODE  v0.8.9.82", "Python 3.12.7 · système"],
    ["IRIS ENCODE  v0.8.9.82", "Python 3.12.7 · une origine traduite bien plus longue que le cadre"],
    ["IRIS ENCODE  v0.8.9.82", "Python 3.12.7 · 本地虚拟环境本地虚拟环境本地虚拟环境"],
])
def test_le_cadre_suit_sa_plus_longue_ligne(lignes):
    """
    Une ligne trop longue crevait le cadre, dessiné à largeur fixe — et c'est la
    première chose que voit l'utilisateur au lancement. Le cadre se calcule
    désormais en cellules depuis son contenu (L-86) : toutes ses lignes ont la
    même largeur, pleine chasse comprise.
    """
    from rich.cells import cell_len

    cadre = main.banniere(lignes)
    assert {cell_len(l) for l in cadre} == {cell_len(cadre[0])}
    assert cell_len(cadre[0]) >= 45                    # 43 + les deux coins
