"""
tests/test_youtube_chaine_ecran.py — Les vidéos d'une chaîne, de l'adresse
collée aux fichiers cochés dans l'accueil (IE-181).

yt-dlp n'est pas lancé : la liste, la lecture des pages et les téléchargements
sont remplacés. Quatre vidéos sur deux pages : une se lit et se télécharge,
une n'a pas de définition sous le plafond, une ne se lit pas, une échoue au
téléchargement.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from pathlib import Path

import pytest
from textual.widgets import DataTable, Input, RadioSet, SelectionList

from core import youtube
from core.i18n import ErreurAffichable

_CHAINE_URL = "https://www.youtube.com/@Arte"
_FR = youtube.SousTitre("fr", "fr", "French", auto=False)

_PAGES = {
    1: youtube.Chaine("Arte", [
        youtube.EntreeChaine("v1", "Premier", 600.0, "20261020"),
        youtube.EntreeChaine("v2", "Deuxième", 1200.0, "20261001"),
        youtube.EntreeChaine("v3", "Troisième", None, ""),
    ], suite=True),
    101: youtube.Chaine("Arte", [
        youtube.EntreeChaine("v4", "Quatrième", 300.0, "20250101"),
    ], suite=False),
}

_VIDEOS = {
    "v1": youtube.Video(url="u1", ident="v1", titre="Premier", duree=600.0,
                        formats={2160: "401", 1080: "248"}, audio="140",
                        sous_titres=[_FR], date="20261019"),
    "v2": youtube.Video(url="u2", ident="v2", titre="Deuxième", duree=1200.0,
                        formats={1440: "400"}, audio="140"),
    "v4": youtube.Video(url="u4", ident="v4", titre="Quatrième", duree=300.0,
                        formats={1080: "137"}, audio="140"),
}


async def _attendre(pilot, condition, delai=5.0) -> bool:
    """Vrai si `condition` se vérifie dans le délai. Un délai dépassé n'arrête
    pas le parcours : chaque test échoue alors sur ce qu'il vérifie."""
    for _i in range(int(delai / 0.05)):
        if condition():
            return True
        await pilot.pause(0.05)
    return False


async def _parcours(td: Path, monkeypatch) -> dict:
    from tui.app import IrisEncodeApp
    from tui.screens.browser import BrowserScreen

    pages_lues: list[tuple[str, int]] = []
    commandes: list[list[str]] = []
    dossier = td / "telechargements"

    def _lister(url, ytdlp, deno, debut=1):
        pages_lues.append((url, debut))
        return _PAGES[debut]

    def _analyser(url, ytdlp, deno):
        ident = url.rsplit("=", 1)[-1]
        if ident == "v3":
            raise ErreurAffichable.brute("Video unavailable")
        return _VIDEOS[ident]

    def _lancer(self, cmd, video, dossier_, progres):
        commandes.append(cmd)
        if video.ident == "v4":
            raise ErreurAffichable.brute("HTTP Error 403")
        progres(1.0)
        produit = dossier / f"{video.titre} [{video.ident}].mkv"
        produit.write_bytes(b"")
        return produit

    monkeypatch.setattr(youtube, "outils",
                        lambda *_a: (Path("y.exe"), Path("d.exe")))
    monkeypatch.setattr(youtube, "lister_chaine", _lister)
    monkeypatch.setattr(youtube, "analyser", _analyser)
    monkeypatch.setattr(youtube.Telechargement, "lancer", _lancer)

    dossier.mkdir()
    # Une étape non atteinte laisse ses relevés à None.
    releve: dict = defaultdict(lambda: None, commandes=commandes,
                               dossier_attendu=dossier)
    app = IrisEncodeApp(start_path=td)
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause(0.5)
        app.cfg.setdefault("app", {})["youtube_dir"] = str(dossier)
        app.push_screen(BrowserScreen(td, start_virtual=False))
        await pilot.pause(1.0)

        await pilot.press("u")
        await pilot.pause(0.3)
        app.screen.query_one(Input).value = _CHAINE_URL
        await pilot.press("enter")
        await pilot.pause(0.3)
        ecran = app.screen
        releve["ecran"] = type(ecran).__name__
        if releve["ecran"] != "ChaineYouTubeScreen":
            return releve
        table = ecran.query_one(DataTable)
        await _attendre(pilot, lambda: table.row_count == 3)
        releve["titre"] = str(ecran.query_one("#ch-title").render())

        def _cellules(col):
            i = list(table.columns).index(col)
            return [table.get_row_at(r)[i].plain for r in range(table.row_count)]

        await _attendre(pilot, lambda: "…" not in _cellules("res"))
        releve["res_page1"] = _cellules("res")
        releve["dates_page1"] = _cellules("date")

        await pilot.press("plus")
        await _attendre(pilot, lambda: table.row_count == 4)
        await _attendre(pilot, lambda: "…" not in _cellules("res"))
        releve["pages_lues"] = list(pages_lues)

        subs = ecran.query_one(SelectionList)
        releve["subs_avant"] = subs.option_count
        table.focus()
        for rang in (0, 1, 3):
            table.move_cursor(row=rang)
            await pilot.press("space")
        await pilot.pause(0.2)
        releve["coches"] = _cellules("check")
        releve["subs"] = [str(subs.get_option_at_index(i).prompt)
                          for i in range(subs.option_count)]
        releve["subs_coches_d_office"] = list(subs.selected)
        if subs.option_count:
            subs.select(0)
        ecran.query_one(RadioSet).query("RadioButton")[2].value = True   # 1080p
        await pilot.pause(0.1)
        ecran.query_one("#ch-go").press()
        await _attendre(pilot, lambda: type(app.screen).__name__ == "BrowserScreen")
        await pilot.pause(0.5)

        releve["dossier"] = app.screen._nav.current
        releve["coches_accueil"] = set(app.screen._selected)
        releve["notes"] = [n.message for n in app._notifications]
    return releve


@pytest.fixture(scope="module")
def parcours(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    td = tmp_path_factory.mktemp("ytc")
    try:
        yield asyncio.run(_parcours(td, mp))
    finally:
        mp.undo()


def test_une_adresse_de_chaine_ouvre_la_liste(parcours):
    assert parcours["ecran"] == "ChaineYouTubeScreen"
    assert parcours["titre"] == "Arte"


def test_la_definition_se_remplit_en_arriere_plan(parcours):
    assert parcours["res_page1"] == ["2160p", "1440p", "✗"]
    # La date exacte de la page remplace la date approchée de la liste.
    assert parcours["dates_page1"] == ["2026-10-19", "≈ 2026-10-01", "—"]


def test_plus_lit_la_page_suivante(parcours):
    assert parcours["pages_lues"] == [("https://www.youtube.com/@Arte/videos", 1),
                                      ("https://www.youtube.com/@Arte/videos", 101)]


def test_les_sous_titres_viennent_des_videos_cochees(parcours):
    assert parcours["subs_avant"] == 0
    assert parcours["subs"] == ["fr — French"]
    assert parcours["subs_coches_d_office"] == []
    assert [c.strip() for c in parcours["coches"]] == ["✓", "✓", "·", "✓"]


def test_le_lot_suit_le_reglage_commun(parcours):
    c1, c2, c4 = parcours["commandes"]
    assert c1[c1.index("-f") + 1] == "248+140"          # 1080p sous le plafond
    assert c1[c1.index("--sub-langs") + 1] == "fr"
    assert c2[c2.index("-f") + 1] == "400+140"          # rien sous 1080 : 1440
    assert "--sub-langs" not in c2                      # pas de fr pour elle
    assert c4[c4.index("-f") + 1] == "137+140"


def test_les_videos_telechargees_arrivent_cochees_malgre_un_echec(parcours):
    d = parcours["dossier_attendu"]
    assert parcours["dossier"] == d
    assert parcours["coches_accueil"] == {d / "Premier [v1].mkv",
                                          d / "Deuxième [v2].mkv"}
    notes = parcours["notes"] or []
    assert any("Quatrième" in n and "403" in n for n in notes)
    # Le texte dépend de la langue chargée par les tests précédents.
    assert any(n.startswith("2 ") for n in notes)
