"""
tests/test_modales.py — Superposition et cadre unique.

Deux constats de la revue d'interface, tranchés par le propriétaire du projet :

1. **Superposition.** Les modales effaçaient tout — titre, barre d'état, liste
   des fichiers, footer — au moment précis où l'on veut voir sur quoi le choix
   va porter. La cause n'était pas Textual, qui rend ses modales translucides
   par défaut, mais la règle globale `Screen { background: $surface; }` de
   l'application : `ModalScreen` hérite de `Screen`, et la règle l'écrasait.
2. **Cadre.** Deux familles graphiques sans rapport avec le rôle : demi-blocs
   `█ ▀ ▄` pour les listes de choix, traits `┌ ─ │` pour les confirmations.
   Un seul cadre désormais, le trait fin.
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent


# ─── Cadre unique ─────────────────────────────────────────────────────────────

def test_aucune_modale_ne_garde_les_demi_blocs():
    fautifs = []
    for f in sorted((RACINE / "tui").rglob("*.py")):
        for i, ligne in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if "border:" in ligne and "thick" in ligne:
                fautifs.append(f"{f.name}:{i} — {ligne.strip()}")
    assert not fautifs, "cadre en demi-blocs :\n" + "\n".join(fautifs)


def test_la_regle_de_translucidite_existe():
    """Elle doit venir *après* la règle Screen, sinon elle ne s'applique pas."""
    src = (RACINE / "tui" / "app.py").read_text(encoding="utf-8")
    i_screen = src.find("Screen { background:")
    i_modal  = src.find("ModalScreen { background:")
    assert i_modal > 0, "la règle ModalScreen a disparu"
    assert i_modal > i_screen, "ModalScreen doit suivre Screen dans la CSS"


# ─── Rendu réel ───────────────────────────────────────────────────────────────

async def _rendus():
    from core import profiles as pm
    from tui.app import IrisEncodeApp
    from tui.screens.browser import BrowserScreen
    from tui.screens.confirm import ConfirmModal
    from tui.screens.profile_picker import ProfilePickerScreen
    from tui.screens.quit import QuitConfirmScreen
    from tui.screens.value_picker import ValuePickerScreen

    from tests.conftest import _GLOBALES
    import importlib
    avant = [(importlib.import_module(m), v,
              getattr(importlib.import_module(m), v)) for m, v in _GLOBALES]

    dossier = RACINE / "tests"
    profs   = pm.load_all()
    fabriques = {
        "ConfirmModal":  lambda: ConfirmModal(title="Supprimer ?", body="T", danger=True),
        "QuitConfirm":   lambda: QuitConfirmScreen(),
        "ValuePicker":   lambda: ValuePickerScreen("Codec", ["HEVC", "H264"], 0),
        "ProfilePicker": lambda: ProfilePickerScreen(profs, "serie_basic"),
    }

    app = IrisEncodeApp(dossier)
    rendus = {}
    async with app.run_test(size=(110, 26)) as pilot:
        await pilot.pause(0.3)
        app.push_screen(BrowserScreen(dossier, start_virtual=False))
        await pilot.pause(3.0)
        for nom, fabrique in fabriques.items():
            app.push_screen(fabrique())
            await pilot.pause(0.6)
            rendus[nom] = app.export_screenshot()
            app.pop_screen()
            await pilot.pause(0.3)

    for module, nom, valeur in avant:
        setattr(module, nom, valeur)
    return rendus


@pytest.fixture(scope="module")
def rendus():
    return asyncio.run(_rendus())


def test_le_parent_reste_visible(rendus):
    """La boîte garde un fond opaque : seul son pourtour laisse voir l'écran,
    donc rien n'est perdu en lisibilité."""
    for nom, svg in rendus.items():
        assert "IRIS" in svg, f"{nom} : l'en-tête a disparu"
        assert re.search(r"Sélect|Tout|Ouvrir", svg), (
            f"{nom} : le footer de l'écran d'origine a disparu"
        )


def test_toutes_les_modales_portent_le_trait_fin(rendus):
    for nom, svg in rendus.items():
        assert any(c in svg for c in "┌└┐┘"), f"{nom} : pas de trait fin"
        assert not any(c in svg for c in "▀▄"), f"{nom} : demi-blocs restants"
