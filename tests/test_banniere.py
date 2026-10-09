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
    dans_venv = (sys.prefix != sys.base_prefix
                 and Path(sys.prefix).resolve() == (ROOT / ".venv").resolve())
    attendu   = ".venv local" if dans_venv else "système"
    assert main._environnement_python().endswith(attendu)


def test_un_venv_posix_lie_au_python_du_systeme_reste_le_venv(monkeypatch):
    """CR-105 : `.venv/bin/python` est un lien vers `/usr/bin/python3` ;
    suivre l'exécutable faisait annoncer « système »."""
    monkeypatch.setattr(sys, "executable", "/usr/bin/python3.13")
    monkeypatch.setattr(sys, "prefix", str(ROOT / ".venv"))
    monkeypatch.setattr(sys, "base_prefix", "/usr")
    assert main._environnement_python().endswith(".venv local")


def test_hors_venv_c_est_le_systeme(monkeypatch):
    monkeypatch.setattr(sys, "prefix", "/usr")
    monkeypatch.setattr(sys, "base_prefix", "/usr")
    assert main._environnement_python().endswith("système")


def test_un_autre_venv_n_est_pas_celui_d_iris(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "prefix", str(tmp_path / "autre_venv"))
    monkeypatch.setattr(sys, "base_prefix", "/usr")
    assert main._environnement_python().endswith("système")


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
