"""
tests/test_footer.py — Répartition des raccourcis du footer.

Le point à garantir : aucun raccourci ne disparaît, quelle que soit la
largeur. Une troncature silencieuse ferait croire qu'une touche n'existe pas.
"""
from __future__ import annotations

import pytest

from tui.widgets.footer import _SEP, _entry_width, pack, split_bands

_ACTIONS = [
    ("enter", "Liste"), ("m", "Mesurer"), ("v", "mpv"), ("k", "Extrait"),
    ("a", "Forcer"), ("s", "Plages"), ("p", "Appliquer"), ("c", "Copier"),
    ("d", "Retirer"), ("f9", "Ajouter"), ("f1", "Dry-run"), ("f2", "Encoder"),
    ("f3", "Muxer"), ("backspace", "Retour"),
]


def _largeur(ligne):
    return sum(_entry_width(k, d) for k, d in ligne) + len(_SEP) * (len(ligne) - 1)


@pytest.mark.parametrize("largeur", [200, 147, 120, 100, 80, 60])
def test_no_shortcut_is_ever_dropped(largeur: int):
    lignes = pack(_ACTIONS, largeur)
    assert [p for l in lignes for p in l] == _ACTIONS


@pytest.mark.parametrize("largeur", [200, 147, 120, 100, 80])
def test_lines_fit_the_width(largeur: int):
    for ligne in pack(_ACTIONS, largeur):
        # Une ligne d'un seul raccourci peut déborder : on ne coupe jamais
        # un raccourci en deux.
        assert _largeur(ligne) <= largeur or len(ligne) == 1


def test_narrower_means_more_lines():
    assert len(pack(_ACTIONS, 200)) < len(pack(_ACTIONS, 80))


def test_a_wide_footer_stays_on_one_line():
    assert len(pack(_ACTIONS, 500)) == 1


def test_an_oversized_entry_keeps_its_own_line():
    pairs = [("m", "Mesurer"), ("x", "U" * 300), ("d", "Retirer")]
    lignes = pack(pairs, 40)
    assert [p for l in lignes for p in l] == pairs
    assert [("x", "U" * 300)] in lignes


def test_empty_and_degenerate_widths():
    assert pack([], 100) == []
    # Largeur inconnue (avant le premier layout) : tout sur une ligne plutôt
    # que de perdre des raccourcis.
    assert pack(_ACTIONS, 0) == [_ACTIONS]


# ─── Trois bandes ─────────────────────────────────────────────────────────────

_NAV = [("home", "Début"), ("end", "Fin"), ("pageup", "Page ↑"), ("f10", "Quitter")]


def test_function_keys_land_on_the_last_band():
    """Les touches de fonction ont une place fixe : la dernière ligne."""
    propres, globaux, fonctions = split_bands(_ACTIONS, _NAV)
    # _ACTIONS mêle raccourcis d'écran et touches de fonction
    assert [k for k, _ in fonctions] == ["f1", "f2", "f3", "f9", "f10"]
    assert not [k for k, _ in propres if k.startswith("f") and k[1:].isdigit()]
    assert not [k for k, _ in globaux if k.startswith("f") and k[1:].isdigit()]


def test_function_keys_are_sorted_by_number():
    """F9 avant F10, quel que soit l'ordre de déclaration dans l'écran."""
    _, _, fonctions = split_bands(
        [("f10", "Quitter"), ("f2", "Run"), ("f9", "Ajouter"), ("f1", "Dry-run")], [])
    assert [k for k, _ in fonctions] == ["f1", "f2", "f9", "f10"]


def test_bands_keep_every_shortcut():
    actions = [("m", "Mesurer"), ("f2", "Encoder"), ("d", "Retirer")]
    tout = [p for b in split_bands(actions, _NAV) for p in b]
    assert sorted(tout) == sorted(actions + _NAV)


def test_screen_and_global_stay_separate():
    propres, globaux, _ = split_bands([("m", "Mesurer")], [("home", "Début")])
    assert propres == [("m", "Mesurer")]
    assert globaux == [("home", "Début")]


def test_a_band_without_function_keys_is_empty_not_missing():
    bandes = split_bands([("m", "Mesurer")], [])
    assert len(bandes) == 3
    assert bandes[2] == []
