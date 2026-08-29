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


def test_la_ligne_tient_dans_le_cadre():
    """
    Le cadre est dessiné à largeur fixe (`inner`). Une ligne trop longue le
    crève — et c'est la première chose que voit l'utilisateur au lancement.
    """
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    m = re.search(r"^\s*inner\s*=\s*(\d+)", src, re.M)
    assert m, "la largeur du cadre a changé de forme"
    assert len(main._environnement_python()) <= int(m.group(1)) - 2
