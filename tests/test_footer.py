"""
tests/test_footer.py — Répartition des raccourcis du footer.

Le point à garantir : aucun raccourci ne disparaît, quelle que soit la
largeur. Une troncature silencieuse ferait croire qu'une touche n'existe pas.
"""
from __future__ import annotations

import pytest

from tui.widgets.footer import _SEP, _entry_width, pack

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
