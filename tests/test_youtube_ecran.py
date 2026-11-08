"""
tests/test_youtube_ecran.py — L'écran YouTube, de l'accueil à la vidéo cochée
(IE-180).

yt-dlp n'est pas lancé : la lecture de la page et le téléchargement sont
remplacés. Le dossier des téléchargements est posé dans la configuration en
mémoire, rien n'est écrit dans config.toml.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from textual.widgets import Input, RadioSet, SelectionList

from core import youtube

_VIDEO = youtube.Video(
    url="https://www.youtube.com/watch?v=abc123", ident="abc123",
    titre="Un film", duree=5400.0, formats={2160: "401", 1080: "248"},
    audio="140", audio_aac=True,
    sous_titres=[youtube.SousTitre("fr", "fr", "French", auto=False),
                 youtube.SousTitre("en-orig", "en", "English", auto=True)])


async def _parcours(td: Path, monkeypatch, capture: Path | None) -> dict:
    from tui.app import IrisEncodeApp
    from tui.screens.browser import BrowserScreen

    commandes: list[list[str]] = []
    produit = td / "telechargements" / "Un film [abc123].mkv"

    def _lancer(self, cmd, video, dossier, progres):
        commandes.append(cmd)
        progres(0.5)
        produit.write_bytes(b"")
        return produit

    monkeypatch.setattr(youtube, "outils", lambda b: (Path("y.exe"), Path("d.exe")))
    monkeypatch.setattr(youtube, "analyser", lambda url, y, d: _VIDEO)
    monkeypatch.setattr(youtube.Telechargement, "lancer", _lancer)

    (td / "telechargements").mkdir()
    releve: dict = {}
    app = IrisEncodeApp(start_path=td)
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause(0.5)
        app.cfg.setdefault("app", {})["youtube_dir"] = str(td / "telechargements")
        app.push_screen(BrowserScreen(td, start_virtual=False))
        await pilot.pause(1.0)

        await pilot.press("u")
        await pilot.pause(0.3)
        releve["ecran"] = type(app.screen).__name__
        app.screen.query_one(Input).value = _VIDEO.url
        await pilot.press("enter")
        await pilot.pause(0.5)
        ecran = app.screen
        releve["resolutions"] = [str(b.label) for b in
                                 ecran.query_one(RadioSet).query("RadioButton")]
        subs = ecran.query_one(SelectionList)
        releve["sous_titres"] = [str(subs.get_option_at_index(i).prompt)
                                 for i in range(subs.option_count)]
        releve["coches_d_office"] = list(subs.selected)
        if capture is not None:
            app.save_screenshot(str(capture))
        # 1080p, et les sous-titres déposés seulement.
        ecran.query_one(RadioSet).query("RadioButton")[1].value = True
        subs.select(0)
        ecran.query_one("#yt-go").press()
        await pilot.pause(1.5)

        releve["apres"] = type(app.screen).__name__
        releve["dossier"] = app.screen._nav.current
        releve["coches"] = set(app.screen._selected)
    releve["commandes"] = commandes
    releve["produit"] = produit
    return releve


@pytest.fixture(scope="module")
def parcours(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    td = tmp_path_factory.mktemp("yt")
    capture = os.environ.get("IRIS_CAPTURE_YOUTUBE")
    try:
        yield asyncio.run(_parcours(td, mp, Path(capture) if capture else None))
    finally:
        mp.undo()


def test_u_ouvre_l_ecran_youtube(parcours):
    assert parcours["ecran"] == "YouTubeScreen"


def test_les_choix_viennent_de_la_page(parcours):
    assert parcours["resolutions"] == ["2160p", "1080p"]
    assert parcours["sous_titres"][0] == "fr — French"
    assert parcours["sous_titres"][1].startswith("en — English (")
    assert parcours["coches_d_office"] == []


def test_le_telechargement_suit_les_choix(parcours):
    (cmd,) = parcours["commandes"]
    assert cmd[cmd.index("-f") + 1] == "248+140"
    assert cmd[cmd.index("--sub-langs") + 1] == "fr"
    assert "--write-auto-subs" not in cmd


def test_la_video_s_ouvre_cochee_dans_son_dossier(parcours):
    assert parcours["apres"] == "BrowserScreen"
    assert parcours["dossier"] == parcours["produit"].parent
    assert parcours["coches"] == {parcours["produit"]}
