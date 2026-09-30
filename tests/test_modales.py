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


# ── La fiche : une touche, deux sources (UX-07) ──────────────────────────────

def test_la_fiche_bascule_dallocine_a_imdb(monkeypatch):
    """`I` ouvre AlloCiné ; `Tab` passe à IMDB, puis revient."""
    from pathlib import Path
    from textual.app import App
    from textual.widgets import Static
    from core.meta import MovieMeta
    import tui.screens.meta_popup as mp

    def _fiche(source):
        return lambda title, year, **_: MovieMeta(
            source=source, title=f"{title} {source}", year=year, kind="Film",
            rating=None, rating_max=10.0)
    monkeypatch.setattr(mp, "fetch_allocine", _fiche("allocine"))
    monkeypatch.setattr(mp, "fetch_imdb", _fiche("imdb"))

    async def _scenario():
        app = App()
        entetes = []
        async with app.run_test(size=(100, 40)) as pilot:
            app.push_screen(mp.MetaPopup(Path("Heat.1995.mkv"), "allocine"))
            for _ in range(3):
                await pilot.pause(0.5)
                entetes.append(str(app.screen.query_one("#meta-header", Static).render()))
                await pilot.press("tab")
        return entetes

    entetes = asyncio.run(_scenario())
    assert entetes[0].startswith("AlloCiné") and "allocine" in entetes[0]
    assert entetes[1].startswith("IMDB") and "imdb" in entetes[1]
    assert entetes[2].startswith("AlloCiné")


# ── L'explorateur du donneur ressemble à l'accueil (UX-22) ───────────────────

def test_lexplorateur_du_donneur_ressemble_a_laccueil(tmp_path):
    from textual.app import App
    from textual.widgets import DataTable
    from tui.screens.donor_picker import DonorFileScreen

    (tmp_path / "Saison 1").mkdir()
    (tmp_path / "film.fr.srt").write_text("1\n", encoding="utf-8")
    (tmp_path / "vf.mkv").write_bytes(b"\0" * 2048)

    async def _scenario():
        app = App()
        async with app.run_test(size=(120, 40)) as pilot:
            ecran = DonorFileScreen(tmp_path / "Saison 1")
            app.push_screen(ecran)
            await pilot.pause(0.3)
            await pilot.press("backspace")          # ⌫ remonte
            await pilot.pause(0.3)
            t = ecran.query_one(DataTable)
            return ecran._dir, [(str(t.get_row_at(i)[0]), str(t.get_row_at(i)[1]))
                                for i in range(t.row_count)]

    dossier, lignes = asyncio.run(_scenario())
    assert dossier == tmp_path
    assert ("📁 Saison 1", "") in lignes
    assert all(not n.startswith("..") for n, _ in lignes)
    assert any(n == "🎬 vf.mkv" and taille.endswith("Ko") for n, taille in lignes)
    assert any(n == "📄 film.fr.srt" for n, _ in lignes)
