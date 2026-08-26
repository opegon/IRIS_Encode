"""
tests/test_deps.py — Cohérence des listes de dépendances.

requirements.txt fait foi. main.py et launch.bat vérifient chacun leur copie
de cette liste : un module oublié dans l'une d'elles ne se manifeste qu'à
l'exécution, souvent loin de l'installation.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Nom du paquet pip → nom du module importable
_PIP_TO_MODULE = {
    "tomli-w":        "tomli_w",
    "beautifulsoup4": "bs4",
}


def _requirements() -> set[str]:
    modules = set()
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pip_name = re.split(r"[><=!\[]", line)[0].strip().lower()
        modules.add(_PIP_TO_MODULE.get(pip_name, pip_name))
    return modules


def _main_py_modules() -> set[str]:
    txt = (ROOT / "main.py").read_text(encoding="utf-8")
    m = re.search(r"for pkg in \(([^)]*)\)", txt)
    assert m, "la boucle de vérification des dépendances a changé de forme"
    return set(re.findall(r'"([^"]+)"', m.group(1)))


def _launch_bat_modules() -> set[str]:
    txt = (ROOT / "launch.bat").read_text(encoding="utf-8", errors="replace")
    m = re.search(r'python -c "import ([^"]+)"', txt)
    assert m, "la vérification des dépendances a changé de forme dans launch.bat"
    return {x.strip() for x in m.group(1).split(",")}


@pytest.mark.parametrize("source,extraire", [
    ("main.py",    _main_py_modules),
    ("launch.bat", _launch_bat_modules),
])
def test_dependency_lists_match_requirements(source: str, extraire):
    attendu = _requirements()
    trouve  = extraire()
    assert trouve == attendu, (
        f"{source} diverge de requirements.txt — "
        f"manquants : {sorted(attendu - trouve)}, "
        f"en trop : {sorted(trouve - attendu)}"
    )


def test_requirements_is_not_empty():
    assert len(_requirements()) >= 5
