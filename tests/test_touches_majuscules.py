"""
tests/test_touches_majuscules.py — Une lettre agit en majuscule comme en
minuscule (v0.9.2.6).

Textual nomme « W » la touche Maj+w (ou w sous Verr. Maj.) : une liaison sur
« w » ne la voyait pas. `IrisEncodeApp._check_bindings` rejoue la minuscule
quand rien ne répond à la majuscule. Une saisie focalisée garde la lettre,
même face à une liaison prioritaire : Textual retire de la chaîne les touches
qu'elle consomme.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from pathlib import Path

import pytest
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Button, Input

from tui.app import lettre_minuscule


@pytest.mark.parametrize("cle, attendu", [
    ("W", "w"), ("shift+w", "w"), ("shift+W", "w"),
    ("w", None), ("F2", None), ("f2", None), ("shift+tab", None),
    ("ctrl+W", None), ("plus", None), ("É", "é"),
])
def test_lettre_minuscule(cle, attendu):
    assert lettre_minuscule(cle) == attendu


class _EcranPrioritaire(Screen):
    """Une liaison prioritaire sur une lettre, une saisie, un bouton."""

    BINDINGS = [Binding("p", "vu", "p", priority=True)]

    def __init__(self) -> None:
        super().__init__()
        self.vus = 0

    def compose(self) -> ComposeResult:
        yield Input(id="saisie")
        yield Button("ok", id="bouton")

    def action_vu(self) -> None:
        self.vus += 1


async def _parcours(td: Path, monkeypatch) -> dict:
    from core import youtube
    from tui.app import IrisEncodeApp
    from tui.screens.browser import BrowserScreen

    monkeypatch.setattr(youtube, "outils", lambda *_a: (Path("y.exe"), Path("d.exe")))
    releve: dict = defaultdict(lambda: None)
    app = IrisEncodeApp(start_path=td)
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause(0.5)
        app.cfg.setdefault("app", {})["youtube_dir"] = str(td)
        app.push_screen(BrowserScreen(td, start_virtual=False))
        await pilot.pause(1.0)

        # Une liaison de l'application (H, le guide).
        await pilot.press("H")
        await pilot.pause(0.3)
        releve["H"] = type(app.screen).__name__
        await pilot.press("H")                      # le referme
        await pilot.pause(0.3)
        releve["H_referme"] = type(app.screen).__name__

        # Une liaison d'écran (U, YouTube) ; la saisie y garde les majuscules.
        await pilot.press("U")
        await pilot.pause(0.3)
        releve["U"] = type(app.screen).__name__
        if releve["U"] == "YouTubeScreen":
            await pilot.press("H", "U", "W")
            await pilot.pause(0.2)
            releve["saisie_youtube"] = app.screen.query_one(Input).value
            releve["apres_saisie"] = type(app.screen).__name__
            await pilot.press("escape")
            await pilot.pause(0.3)

        # Liaison prioritaire : la saisie focalisée garde la lettre.
        ecran = _EcranPrioritaire()
        app.push_screen(ecran)
        await pilot.pause(0.3)
        ecran.query_one(Input).focus()
        await pilot.press("P")
        await pilot.pause(0.1)
        releve["prio_saisie_valeur"] = ecran.query_one(Input).value
        releve["prio_saisie_vus"] = ecran.vus
        ecran.query_one(Button).focus()
        await pilot.press("P")
        await pilot.pause(0.1)
        releve["prio_bouton_vus"] = ecran.vus
    return releve


@pytest.fixture(scope="module")
def parcours(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    td = tmp_path_factory.mktemp("maj")
    try:
        yield asyncio.run(_parcours(td, mp))
    finally:
        mp.undo()


def test_une_liaison_de_l_application_repond_a_la_majuscule(parcours):
    assert parcours["H"] == "AideScreen"
    assert parcours["H_referme"] == "BrowserScreen"


def test_une_liaison_d_ecran_repond_a_la_majuscule(parcours):
    assert parcours["U"] == "YouTubeScreen"


def test_une_saisie_garde_les_majuscules(parcours):
    assert parcours["saisie_youtube"] == "HUW"
    assert parcours["apres_saisie"] == "YouTubeScreen"


def test_une_liaison_prioritaire_laisse_la_majuscule_a_la_saisie(parcours):
    assert parcours["prio_saisie_valeur"] == "P"
    assert parcours["prio_saisie_vus"] == 0
    assert parcours["prio_bouton_vus"] == 1
