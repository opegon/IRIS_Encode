"""
tests/test_bascule_selection.py — `A` bascule entre tout et rien (v0.9.3.2).

L'accueil avait deux touches, `A` (tout) et `N` (aucun). Une seule suffit :
tant qu'un fichier cochable reste décoché, `A` complète la sélection ; quand
tout l'est, `A` la vide. Les sorties d'IRIS restent hors de « tout ».
"""
from __future__ import annotations

from tui.screens.browser import BrowserScreen


class _FauxEcran:
    """Juste ce qu'il faut pour appeler l'action sans monter l'écran."""
    action_select_toggle_all = BrowserScreen.action_select_toggle_all

    def __init__(self, rows, produits=()):
        self._rows     = rows
        self._produits = set(produits)
        self._selected = set()

    def _update_row_check(self, path):
        pass

    def _annoncer_forcees(self, paths):
        pass

    def _update_status(self):
        pass


def _ecran(tmp_path):
    a, b = tmp_path / "A.mkv", tmp_path / "B.mkv"
    produit = tmp_path / "A.hevc-iris.mkv"
    return _FauxEcran([("file", a), ("file", b), ("file", produit)], {produit}), a, b


def test_rien_coche_puis_tout(tmp_path):
    ecran, a, b = _ecran(tmp_path)
    ecran.action_select_toggle_all()
    assert ecran._selected == {a, b}


def test_tout_coche_puis_rien(tmp_path):
    ecran, a, b = _ecran(tmp_path)
    ecran.action_select_toggle_all()
    ecran.action_select_toggle_all()
    assert ecran._selected == set()


def test_une_selection_partielle_se_complete(tmp_path):
    ecran, a, b = _ecran(tmp_path)
    ecran._selected = {a}
    ecran.action_select_toggle_all()
    assert ecran._selected == {a, b}


def test_n_n_est_plus_liee_sur_l_accueil():
    touches = {b.key for b in BrowserScreen.BINDINGS}
    assert "n" not in touches
    assert "n" not in {k for k, _ in BrowserScreen._RACCOURCIS_FICHIERS}
