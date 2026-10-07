"""
tests/test_formats.py — Les formats suivent la langue de l'application (IE-90).

Arbitrages du 2026-10-07 : unités d'octets traduites (TB/GB/MB/KB en anglais,
comme l'Explorateur Windows ; To/Go/Mo/Ko en français), point décimal fixe dans
toutes les langues, pourcentage collé au nombre (« 12% ») partout. Durées,
`ms`, `s`, `k`, `kbps` : symboles identiques dans les deux langues.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from core import i18n

RACINE = Path(__file__).resolve().parent.parent
CATALOGUES = [RACINE / "locales" / "iris_encode.pot",
              RACINE / "locales" / "fr" / "LC_MESSAGES" / "iris_encode.po"]


@pytest.fixture
def langue():
    """Charge une langue le temps du test, puis rend le français de `conftest.py`."""
    avant = i18n.langue()
    yield i18n.init
    i18n.init(avant)


@pytest.mark.parametrize("code, attendu", [
    ("en", ["2.0 TB", "500.0 GB", "35 MB", "512 KB"]),
    ("fr", ["2.0 To", "500.0 Go", "35 Mo", "512 Ko"]),
])
def test_les_unites_d_octets_suivent_la_langue(langue, code, attendu):
    from tui.common import fmt_bytes

    langue(code)
    tailles = [2 * 1024 ** 4, 500 * 1024 ** 3, 35 * 1024 ** 2, 512 * 1024]
    assert [fmt_bytes(t) for t in tailles] == attendu


def test_aucun_pourcentage_detache_dans_les_catalogues():
    """« 12% » partout : un « 12 % » dans un msgid ou sa traduction est une
    récidive de l'incohérence relevée par L-67."""
    fautifs = []
    for chemin in CATALOGUES:
        for n, ligne in enumerate(chemin.read_text(encoding="utf-8").splitlines(), 1):
            if ligne.startswith(("msgid", "msgstr", '"')) and re.search(r"[\d}] %", ligne):
                fautifs.append(f"{chemin.name}:{n}: {ligne}")
    assert not fautifs, "\n".join(fautifs)


def test_aucun_pourcentage_detache_dans_le_code_affiche():
    """Même règle pour les f-strings hors catalogue (`browser.py`, `run.py`…)."""
    fautifs = []
    for chemin in [*(RACINE / "core").rglob("*.py"), *(RACINE / "tui").rglob("*.py")]:
        for n, ligne in enumerate(chemin.read_text(encoding="utf-8").splitlines(), 1):
            code = ligne.split("#", 1)[0]
            if re.search(r"[\d}] %[\"')]", code):
                fautifs.append(f"{chemin.relative_to(RACINE)}:{n}: {ligne.strip()}")
    assert not fautifs, "\n".join(fautifs)
