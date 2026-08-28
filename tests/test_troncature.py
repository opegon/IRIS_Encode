"""
tests/test_troncature.py — Ce qui déborde doit se voir déborder.

Sept des huit constats de la revue du 2026-08-28 étaient de la même famille :
une valeur coupée net, qui reste plausible une fois coupée. « → HEVC → HDR10 »
rendu « → HEVC → » se lit comme une décision complète — le sort du Dolby Vision
a disparu sans laisser de trace. Corriger une colonne à la fois n'a jamais
suffi : la famille est revenue à chaque version depuis IE-01.

Trois garde-fous, du plus général au plus précis :

  1. toute cellule de table passe par `cellule()`, qui pose l'ellipse ;
  2. le plancher d'une colonne à valeurs énumérables tient le plus long
     libellé que cette colonne peut produire — l'ellipse ne s'y déclenche
     jamais, parce qu'il n'y a rien à couper ;
  3. la somme des largeurs ne dépasse pas le terminal.
"""
from __future__ import annotations

import itertools

import pytest
from rich.text import Text

from core import config as cfg_mod
from core.decision import DVAction, VideoAction, VideoDecision
from tui.common import cellule
from tui.mixins import ColumnResizeMixin


# ── 1. La cellule pose l'ellipse ──────────────────────────────────────────────

def test_cellule_signale_le_debordement():
    """Rich ne peut poser l'ellipse que si on la lui demande."""
    c = cellule("→ HEVC → HDR10")
    assert c.no_wrap is True
    assert c.overflow == "ellipsis"


def test_cellule_tronque_au_milieu_quand_une_largeur_est_donnee():
    """La fin d'un nom de piste porte ce qui le distingue — voir tronquer_milieu."""
    c = cellule("Français (France) (forced)", largeur=12)
    assert "…" in c.plain
    assert len(c.plain) == 12
    assert c.plain.endswith("orced)")


# ── 2. Les planchers tiennent les libellés que la colonne produit ─────────────

def _libelles_decision() -> list[str]:
    """Tout ce que la colonne « Décision » de l'accueil peut afficher."""
    return [
        VideoDecision(action=a, reason="", target_bitrate=0,
                      target_width=0, target_height=0, dv_action=dv,
                      output_suffix="").label()
        for a, dv in itertools.product(VideoAction, DVAction)
    ]


@pytest.mark.parametrize("colonne", ["decision", "action"])
def test_le_plancher_tient_le_plus_long_libelle(colonne):
    """
    Le plancher d'une colonne énumérable n'est pas une question de goût.

    « → HEVC → HDR10 » et « → HEVC → SDR ⚠ » font quatorze caractères. La
    colonne en offrait huit, sans ellipse : trois sorties très différentes
    s'affichaient à l'identique. Ce test échoue si un libellé s'allonge sans
    que le plancher suive.
    """
    plus_long = max(_libelles_decision(), key=len)
    plancher  = cfg_mod.COLUMN_MIN_WIDTHS[colonne]
    assert plancher >= len(plus_long), (
        f"« {plus_long} » fait {len(plus_long)} caractères, la colonne "
        f"« {colonne} » n'en garantit que {plancher}"
    )


def test_le_plancher_dolby_vision_tient_le_profil_le_plus_long():
    """« DV:P8.1 » — sept caractères, les deux écrans nommant la colonne autrement."""
    for cle in ("dolby_vision", "dv"):
        assert cfg_mod.COLUMN_MIN_WIDTHS[cle] >= len("DV:P8.1")


def test_les_planchers_valent_a_la_lecture_dune_largeur_persistee():
    """Une largeur écrite avant l'existence du plancher ne doit pas survivre."""
    cfg = {"tui": {"browser": {"columns": {"decision": 8, "duree": 5}}}}
    w   = cfg_mod.get_column_widths(cfg)
    assert w["decision"] >= 14
    assert w["duree"]    >= 7


# ── 3. La somme des largeurs ne déborde pas de l'écran ────────────────────────

class _Ecran(ColumnResizeMixin):
    """Le mixin seul, sans Textual : on n'exerce que l'arithmétique."""

    RESIZE_COLS = ["a", "b", "c"]
    RESIZE_LABELS = {"a": "A", "b": "B", "c": "C"}
    RESIZE_FIXE = 4

    def __init__(self, widths, largeur):
        self._w       = dict(widths)
        self._largeur = largeur
        self.refus    = 0
        self.rebuilds = 0

    def _place_disponible(self):      return self._largeur
    def _resize_widths(self):         return self._w
    def _resize_persist(self, k, w):  self._w[k] = w
    def _resize_rebuild(self):        self.rebuilds += 1
    def _refus_elargir(self, place):  self.refus += 1


def test_elargir_sarrete_a_la_largeur_du_terminal():
    """
    IE-02 a donné un plancher par colonne ; rien ne limitait la somme.

    Mesuré sur le dry-run : 186 colonnes enregistrées pour un terminal de 160.
    Les dernières sortaient de l'écran, et le réglage était persisté.
    """
    e = _Ecran({"a": 20, "b": 20, "c": 20}, largeur=70)   # 60 + 4 fixes = 64
    e._resize_col_idx = 0
    e.action_col_grow()                 # +2 → 66, ça tient
    assert e._w["a"] == 22
    e.action_col_grow()                 # +2 → 68, ça tient
    assert e._w["a"] == 24
    e.action_col_grow()                 # +2 → 70 pile
    assert e._w["a"] == 26
    e.action_col_grow()                 # ne tient plus
    assert e._w["a"] == 26
    assert e.refus == 1


def test_elargir_donne_la_place_qui_reste_plutot_que_rien():
    """Un pas de deux qui ne tient pas ne doit pas annuler le seul point libre."""
    e = _Ecran({"a": 20, "b": 20, "c": 20}, largeur=65)   # 64 occupés, 1 libre
    e._resize_col_idx = 0
    e.action_col_grow()
    assert e._w["a"] == 21
    assert e.refus == 0


def test_retrecir_reste_possible_une_fois_le_plafond_atteint():
    """Sans quoi une largeur persistée trop grande serait sans recours."""
    e = _Ecran({"a": 90, "b": 40, "c": 40}, largeur=100)  # déjà 174 > 100
    e._resize_col_idx = 0
    e.action_col_grow()
    assert e._w["a"] == 90 and e.refus == 1
    e.action_col_shrink()
    assert e._w["a"] == 88

def test_le_plafond_ne_sapplique_pas_sans_ecran_monte():
    """Hors terminal (tests, capture), la largeur disponible vaut zéro."""
    e = _Ecran({"a": 20, "b": 20, "c": 20}, largeur=0)
    e._resize_col_idx = 0
    e.action_col_grow()
    assert e._w["a"] == 22 and e.refus == 0
