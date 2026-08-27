"""
tests/test_volumes.py — L'écran d'accueil ne promet que ce qu'il peut tenir.

Premier écran de l'application, il listait `C:\\` et `D:\\` sous l'en-tête
complet du tableau de fichiers — Taille, Résolution, Durée, Débit, Codec,
Dolby V., Décision, Estim., ETA, Audio — dont **aucune ne peut avoir de valeur
pour un volume**. S'y ajoutaient « 0/0 sélectionné(s) », le bandeau détaillé du
profil d'encodage, et un pied proposant de lancer un dry-run.

Un tableau dont dix colonnes sur douze restent vides n'est pas un tableau
dense : c'est une promesse non tenue.
"""
from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path

import pytest
from textual.widgets import DataTable, Static

RACINE = Path(__file__).resolve().parent.parent


# ─── Mesure d'un volume ───────────────────────────────────────────────────────

def test_un_volume_injoignable_ne_fait_pas_disparaitre_sa_ligne():
    """Lecteur vide ou partage réseau coupé : le volume existe, c'est sa
    mesure qui manque."""
    from tui.screens.browser import _cellules_volume

    cellules = _cellules_volume(Path("Z:/inexistant_pour_le_test"))
    assert len(cellules) == 3
    assert all(str(c) == "—" for c in cellules)


def test_les_teraoctets_se_lisent():
    """« 35726.4 Go » pour un partage réseau ne se lit pas."""
    from tui.common import fmt_bytes

    assert fmt_bytes(2 * 1024 ** 4) == "2.0 To"
    assert fmt_bytes(500 * 1024 ** 3).endswith("Go")


def test_un_volume_presque_plein_alerte():
    from core.decision import STYLE_PAR_EMPHASE, Emphase
    from tui.screens.browser import _cellules_volume

    _, _, occupe = _cellules_volume(Path(shutil.__file__).anchor or "/")
    assert occupe.style in (STYLE_PAR_EMPHASE[Emphase.ALERTE],
                            STYLE_PAR_EMPHASE[Emphase.ORDINAIRE])


# ─── Les deux modes ───────────────────────────────────────────────────────────

async def _deux_modes():
    from tui.app import IrisEncodeApp

    from tests.conftest import _GLOBALES
    import importlib
    avant = [(importlib.import_module(m), v,
              getattr(importlib.import_module(m), v)) for m, v in _GLOBALES]

    releve = {}
    app = IrisEncodeApp(RACINE / "tests")
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause(0.8)
        ecran = app.screen
        releve["volumes"] = {
            "colonnes": [str(c.label) for c in ecran.query_one(DataTable).columns.values()],
            "etat":     str(ecran.query_one("#status-bar", Static).render()),
            "profil":   str(ecran.query_one("#profile-bar", Static).render()),
            "svg":      app.export_screenshot(),
        }
        ecran._nav.enter(RACINE)
        ecran._refresh_view()
        await pilot.pause(2.5)
        releve["fichiers"] = {
            "colonnes": [str(c.label) for c in ecran.query_one(DataTable).columns.values()],
            "svg":      app.export_screenshot(),
        }

    for module, nom, valeur in avant:
        setattr(module, nom, valeur)
    return releve


@pytest.fixture(scope="module")
def modes():
    return asyncio.run(_deux_modes())


def test_les_colonnes_parlent_de_volumes(modes):
    colonnes = modes["volumes"]["colonnes"]
    assert colonnes == ["Volume", "Espace libre", "Total", "Occupé"], colonnes


def test_ni_selection_ni_profil_sur_les_volumes(modes):
    assert "sélectionné" not in modes["volumes"]["etat"]
    assert "volume(s)" in modes["volumes"]["etat"]
    assert modes["volumes"]["profil"].strip() == "", "le bandeau de profil s'affiche"


@pytest.mark.parametrize("interdit", ["Sélect", "Dry-run", "AlloCiné", "Rétrécir"])
def test_le_pied_ne_propose_rien_d_inapplicable(modes, interdit):
    assert interdit not in modes["volumes"]["svg"], (
        f"« {interdit} » proposé alors qu'aucun fichier n'est en vue"
    )


def test_entrer_dans_un_volume_rend_les_colonnes_de_fichiers(modes):
    colonnes = modes["fichiers"]["colonnes"]
    assert any("Fichier" in c for c in colonnes), colonnes
    assert any("Durée" in c for c in colonnes), colonnes


def test_entrer_dans_un_volume_rend_les_raccourcis_de_fichiers(modes):
    for attendu in ("Sélect", "Dry-run"):
        assert attendu in modes["fichiers"]["svg"], f"« {attendu} » non restauré"
