"""
tests/test_footer_focus.py — Le footer annonce les touches qui répondent.

Le formulaire d'édition de profil est monté *dans* `ConfigScreen` et lui prend
le focus. Le footer, lui, était construit une fois avec les `BINDINGS` de
l'écran : il proposait encore « N Nouveau » et « D Supprimer » alors que taper
« n » écrivait simplement un « n » dans le champ courant. Les vraies touches
n'étaient annoncées que par un bandeau propre au formulaire.

Un footer faux est pire qu'un footer vide : il invite à des gestes sans effet.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from textual.widgets import Static

from tui.app import IrisEncodeApp
from tui.screens.config import ConfigScreen
from tui.widgets.profile_form import ProfileForm

DOSSIER = Path(__file__).resolve().parent.parent


def _lignes_du_footer(ecran) -> str:
    return str(ecran.query_one("#footer-body", Static).render())


async def _scenario():
    # Construire l'application pose les chemins d'outils en variables de
    # module. Cette fixture étant à portée « module », elle s'exécute avant la
    # sauvegarde automatique du conftest : on restaure donc nous-mêmes.
    from tests.conftest import _GLOBALES
    import importlib

    avant = [(importlib.import_module(m), v,
              getattr(importlib.import_module(m), v)) for m, v in _GLOBALES]

    app = IrisEncodeApp(DOSSIER)
    releve = {}
    async with app.run_test(size=(150, 40)) as pilot:
        await pilot.pause(0.3)
        app.push_screen(ConfigScreen())
        await pilot.pause(0.5)
        ecran = app.screen

        releve["liste"] = _lignes_du_footer(ecran)
        ecran._open_form("cinema_4k_basic", False)
        await pilot.pause(0.4)
        releve["formulaire"] = _lignes_du_footer(ecran)
        ecran._close_form()
        await pilot.pause(0.4)
        releve["retour"] = _lignes_du_footer(ecran)

    for module, nom, valeur in avant:
        setattr(module, nom, valeur)
    return releve


@pytest.fixture(scope="module")
def footers():
    return asyncio.run(_scenario())


def test_les_touches_de_l_ecran_disparaissent(footers):
    """Elles ne répondent plus : `check_action` les neutralise déjà."""
    for libelle in ("Nouveau", "Éditer", "Supprimer", "Activer profil"):
        assert libelle not in footers["formulaire"], (
            f"« {libelle} » encore annoncé alors que la touche ne répond pas"
        )


def test_les_touches_du_formulaire_apparaissent(footers):
    for _, libelle in ProfileForm.RACCOURCIS:
        assert libelle in footers["formulaire"], f"« {libelle} » manquant"


def test_f10_reste_partout(footers):
    """Convention du projet : F10 en dernier sur tous les écrans."""
    for etat, contenu in footers.items():
        assert "F10" in contenu, f"F10 absent en état « {etat} »"


def test_les_touches_de_l_ecran_reviennent(footers):
    for libelle in ("Nouveau", "Éditer", "Supprimer"):
        assert libelle in footers["retour"], f"« {libelle} » non restauré"


def test_le_formulaire_ne_porte_plus_son_propre_bandeau():
    """Deux bandeaux disant la même chose, c'en est un de trop — et c'était
    celui du formulaire qui disait vrai pendant que le footer mentait."""
    src = (DOSSIER / "tui" / "widgets" / "profile_form.py").read_text(encoding="utf-8")
    assert 'classes="form-hint"' not in src


def test_la_liste_de_raccourcis_n_est_ecrite_qu_une_fois():
    src = (DOSSIER / "tui" / "screens" / "config.py").read_text(encoding="utf-8")
    assert src.count('("n",         "Nouveau")') <= 1, (
        "la liste des raccourcis de l'écran est écrite deux fois"
    )
