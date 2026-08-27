"""
tests/test_colonnes.py — Une colonne ne doit jamais rendre une valeur fausse.

`fmt_duration` produit sept caractères dès qu'il y a des heures (`3:17:24`).
Une colonne de six affichait `3:17:2` — sans ellipse, donc **lisible comme une
durée valide**. C'est le pire des cas : une troncature qui se voit fait perdre
une information, une troncature qui ne se voit pas en invente une.

Trois protections, testées ici :
  1. le défaut de la colonne couvre ce que le contenu exige ;
  2. le plancher de redimensionnement l'exige aussi, pour qu'aucune session ne
     puisse reproduire la troncature à la main ;
  3. la cellule porte une ellipse, pour que toute coupe résiduelle se voie.
"""
from __future__ import annotations

import asyncio

import pytest
from rich.text import Text

from core.config import _DEFAULTS, _DRYRUN_COL_DEFAULTS
from tui.common import fmt_duration
from tui.mixins import ColumnResizeMixin
from tui.screens.browser import BrowserScreen
from tui.screens.dryrun import DryrunScreen

# Une durée d'au moins une heure : le cas de tous les films.
_LONGUE = 3 * 3600 + 17 * 60 + 24


def test_une_duree_dune_heure_prend_sept_caracteres():
    assert fmt_duration(_LONGUE) == "3:17:24"
    assert len(fmt_duration(_LONGUE)) == 7
    # En dessous d'une heure, cinq suffisent — d'où le défaut trop court.
    assert len(fmt_duration(59 * 60 + 12)) == 5


def test_defauts_de_colonnes_couvrent_la_duree():
    assert _DEFAULTS["tui"]["browser"]["columns"]["duree"] >= 7
    assert _DRYRUN_COL_DEFAULTS["duree"] >= 7


@pytest.mark.parametrize("ecran", [BrowserScreen, DryrunScreen])
@pytest.mark.parametrize("colonne", ["duree", "temps_estim"])
def test_plancher_de_redimensionnement(ecran, colonne):
    """Corriger le défaut ne protège de rien tant que la main peut descendre
    en dessous et que le réglage est persisté."""
    assert ecran.RESIZE_MIN.get(colonne, 0) >= 7, (
        f"{ecran.__name__} : la colonne {colonne} peut être rétrécie sous 7"
    )


def test_le_retrecissement_s_arrete_au_plancher():
    class Faux(ColumnResizeMixin):
        RESIZE_COLS = ["duree"]
        RESIZE_MIN  = {"duree": 7}
        def __init__(self):
            self.largeurs = {"duree": 8}
            self.ecrit    = []
        def _resize_widths(self):          return self.largeurs
        def _resize_persist(self, k, w):   self.largeurs[k] = w; self.ecrit.append(w)
        def _resize_rebuild(self):         pass

    f = Faux()
    f.action_col_shrink()          # 8 → 7, autorisé
    assert f.largeurs["duree"] == 7
    f.action_col_shrink()          # refusé : rien n'est écrit
    assert f.largeurs["duree"] == 7
    assert f.ecrit == [7], "une largeur sous le plancher a été persistée"


def test_une_coupe_residuelle_se_voit():
    """Rendu dans une vraie DataTable : avec ellipse la coupe est visible,
    sans elle la valeur reste lisible comme une durée."""
    from textual.app import App, ComposeResult
    from textual.widgets import DataTable

    valeur = fmt_duration(_LONGUE)

    class Bac(App):
        def compose(self) -> ComposeResult:
            yield DataTable()

        def on_mount(self) -> None:
            t = self.query_one(DataTable)
            t.add_column("Durée", width=6, key="duree")
            t.add_row(Text(valeur, no_wrap=True, overflow="ellipsis"), key="avec")
            t.add_row(Text(valeur), key="sans")

    async def rendu():
        async with Bac().run_test(size=(40, 10)) as pilot:
            await pilot.pause(0.3)
            t = pilot.app.query_one(DataTable)
            return [t.render_line(y).text for y in (1, 2)]

    avec, sans = asyncio.run(rendu())
    assert "…" in avec, f"la coupe reste invisible : {avec!r}"
    assert "…" not in sans and "3:17:2" in sans, (
        f"témoin inattendu : {sans!r}"
    )


def test_une_largeur_trop_courte_deja_persistee_est_relevee():
    """Le cas qui compte pour un utilisateur existant : `config.toml` porte
    déjà `duree = 6`, écrit avant que le plancher existe. Corriger le défaut
    ne le répare pas — c'est la lecture qui doit relever la valeur."""
    from core import config as cfg_mod

    cfg = {"tui": {"browser": {"columns": {"duree": 4, "fichier": 30}},
                   "dryrun":  {"columns": {"duree": 6, "temps_estim": 6}}}}

    b = cfg_mod.get_column_widths(cfg)
    assert b["duree"] == 7
    assert b["fichier"] == 30, "une largeur suffisante ne doit pas être touchée"

    d = cfg_mod.get_dryrun_column_widths(cfg)
    assert d["duree"] == 7 and d["temps_estim"] == 7


def test_les_planchers_ont_une_seule_source():
    """Écrans et configuration doivent lire la même table, sinon l'un des deux
    dérive au premier ajout de colonne."""
    from core import config as cfg_mod

    for ecran in (BrowserScreen, DryrunScreen):
        for col, mini in cfg_mod.COLUMN_MIN_WIDTHS.items():
            assert ecran.RESIZE_MIN.get(col) == mini, (
                f"{ecran.__name__} : plancher {col} désynchronisé"
            )
