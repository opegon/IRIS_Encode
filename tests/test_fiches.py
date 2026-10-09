"""
tests/test_fiches.py — Fiches IMDB / AlloCiné et titres tirés des noms
(IE-133, constats CR-47, CR-48, CR-49, CR-101 de `revue_code_2026-10-08.md`).

Aucun appel réseau : `requests.get` est remplacé.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from core import meta

RACINE = Path(__file__).resolve().parent.parent


# ─── CR-49 — le titre et son année ───────────────────────────────────────────

@pytest.mark.parametrize("nom,attendu", [
    ("2001.A.Space.Odyssey.1968.1080p.mkv", ("2001 A Space Odyssey", 1968)),
    ("1917.2019.1080p.mkv",                 ("1917", 2019)),
    ("Blade.Runner.2049.2017.2160p.mkv",    ("Blade Runner 2049", 2017)),
    ("Heat.1995.mkv",                       ("Heat", 1995)),
    ("Film (2020).mkv",                     ("Film", 2020)),
    ("Film [2020] 1080p.mkv",               ("Film", 2020)),
    ("Show.S01E01.1080p.mkv",               ("Show", None)),
    ("Show.2019.S01E01.mkv",                ("Show", 2019)),
    ("Film.1080p.2020.mkv",                 ("Film", 2020)),
])
def test_parse_title(nom, attendu):
    assert meta.parse_title(Path(nom)) == attendu


# ─── CR-47, CR-48 — OMDb en HTTPS, séries comprises ──────────────────────────

class _Rep:
    def __init__(self, donnees=None, texte=""):
        self._d, self.text, self.status_code = donnees, texte, 200

    def raise_for_status(self):
        pass

    def json(self):
        return self._d


def test_aucune_url_http_dans_le_code():
    """Tous les services passent en HTTPS ; la clé OMDb partait en clair."""
    for dossier in ("core", "tui"):
        for f in (RACINE / dossier).rglob("*.py"):
            for n, ligne in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                code = ligne.split("#")[0]
                assert "http://" not in code, f"{f.relative_to(RACINE)}:{n}"


def test_la_requete_omdb_ne_filtre_plus_les_films(monkeypatch):
    import requests
    urls = []

    def get(url, **k):
        urls.append(url)
        return _Rep({"Response": "True", "Title": "Show", "Type": "series",
                     "Year": "2019–2022"})
    monkeypatch.setattr(requests, "get", get)
    fiche = meta.fetch_imdb("Show", None, omdb_key="k")
    assert fiche.kind is meta.Nature.SERIE
    assert urls[0].startswith("https://www.omdbapi.com/")
    assert "type=" not in urls[0]


def test_omdb_introuvable_retombe_sur_les_suggestions(monkeypatch):
    import requests

    def get(url, **k):
        if "omdbapi" in url:
            return _Rep({"Response": "False", "Error": "Movie not found!"})
        return _Rep(texte='imdb$show({"d":[{"qid":"tvSeries","l":"Show",'
                          '"y":2019,"id":"tt1","s":"A, B"}]})')
    monkeypatch.setattr(requests, "get", get)
    fiche = meta.fetch_imdb("Show", None, omdb_key="k")
    assert fiche.title == "Show" and fiche.kind is meta.Nature.SERIE


def test_une_autre_erreur_omdb_reste_affichee(monkeypatch):
    """Une limite atteinte ne se masque pas derrière les suggestions."""
    import requests
    monkeypatch.setattr(requests, "get", lambda url, **k: _Rep(
        {"Response": "False", "Error": "Request limit reached!"}))
    with pytest.raises(Exception, match="Request limit reached"):
        meta.fetch_imdb("Heat", 1995, omdb_key="k")


# ─── CR-101 — les crochets du nom restent à l'écran ──────────────────────────

def test_l_entete_garde_les_crochets_du_nom(monkeypatch):
    from textual.app import App
    from textual.widgets import Static
    import tui.screens.meta_popup as mp

    def echec(title, year, **_):
        raise RuntimeError("pas de réseau")
    monkeypatch.setattr(mp, "fetch_allocine", echec)

    async def _scenario():
        app = App()
        async with app.run_test(size=(100, 40)) as pilot:
            app.push_screen(mp.MetaPopup(Path("Film [Final Cut] (2020).mkv"), "allocine"))
            await pilot.pause(0.3)
            return str(app.screen.query_one("#meta-header", Static).render())

    entete = asyncio.run(_scenario())
    assert "[Final Cut]" in entete, entete
