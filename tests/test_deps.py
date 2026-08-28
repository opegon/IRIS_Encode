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


# La liste vit dans quatre appels, répartis sur deux scripts : deux dans
# launch.bat (le .venv d'abord, puis le Python du PATH) et deux dans
# bootstrap.ps1 (avant et après construction). Aucun n'est superflu — chacun
# répond à une question différente — mais aucun ne doit diverger. On les
# ramasse tous plutôt que d'en choisir un.
_IMPORTS = re.compile(r'-c "import ([a-z0-9_]+(?:\s*,\s*[a-z0-9_]+)+)"')


def _modules_des_scripts(nom: str) -> list[set[str]]:
    txt = (ROOT / nom).read_text(encoding="utf-8", errors="replace")
    listes = [{x.strip() for x in m.split(",")} for m in _IMPORTS.findall(txt)]
    assert listes, f"aucune vérification de dépendances trouvée dans {nom}"
    return listes


def _launch_bat_modules() -> set[str]:
    listes = _modules_des_scripts("launch.bat")
    assert all(l == listes[0] for l in listes), (
        f"les {len(listes)} vérifications de launch.bat ne disent pas la même "
        f"chose : {listes}"
    )
    return listes[0]


def _bootstrap_ps1_modules() -> set[str]:
    listes = _modules_des_scripts("bootstrap.ps1")
    assert all(l == listes[0] for l in listes), (
        f"les {len(listes)} vérifications de bootstrap.ps1 divergent : {listes}"
    )
    return listes[0]


@pytest.mark.parametrize("source,extraire", [
    ("main.py",       _main_py_modules),
    ("launch.bat",    _launch_bat_modules),
    ("bootstrap.ps1", _bootstrap_ps1_modules),
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
