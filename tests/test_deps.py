"""
tests/test_deps.py — Cohérence des listes de dépendances.

requirements.txt fait foi. main.py en tient une copie, à garder égale : un
module oublié ne se manifeste qu'à l'exécution, souvent loin de
l'installation. Les lanceurs, eux, passent par dependances.py.
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


def test_main_py_matches_requirements():
    attendu = _requirements()
    trouve  = _main_py_modules()
    assert trouve == attendu, (
        f"main.py diverge de requirements.txt — "
        f"manquants : {sorted(attendu - trouve)}, "
        f"en trop : {sorted(trouve - attendu)}"
    )


# launch.bat (le .venv, puis le Python du PATH) et bootstrap.ps1 (avant et
# après construction) ne tiennent plus de liste : ils appellent
# dependances.py, qui lit requirements.txt lui-même (IE-132, CR-109).
@pytest.mark.parametrize("script,appels", [("launch.bat", 2), ("bootstrap.ps1", 1)])
def test_les_scripts_verifient_par_dependances_py(script: str, appels: int):
    txt = (ROOT / script).read_text(encoding="utf-8", errors="replace")
    assert txt.count("dependances.py") >= appels
    assert "import textual" not in txt, (
        f"{script} garde une liste d'imports à tenir à la main")


def test_requirements_is_not_empty():
    assert len(_requirements()) >= 5
