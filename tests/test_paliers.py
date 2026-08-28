"""
tests/test_paliers.py — Détecter des paliers par accord, non par amplitude.

La voie ordinaire juge une corrélation sur sa force. Certains couples n'y
arrivent jamais : un sous-titre dont l'adaptation diffère de celle du doublage
ne décalque pas la parole. Mesuré sur un cas réel — `the.fall.s02e01` — ce
couple plafonne à **0,117** pour un seuil de 0,25, *même parfaitement aligné*,
vérifié à l'oreille en six points. Aucun seuil d'amplitude ne le sauvera.

Son décalage, lui, est stable : des fenêtres voisines tombent sur la même
valeur, et cette régularité ne s'obtient pas par hasard. C'est elle que
`_segments_par_accord` lit.

Deux garde-fous portent tout le raisonnement, et sont testés comme tels :

- **la recherche est bornée** — un décalage de montage se compte en secondes ;
  chercher à ±90 s n'ajoute que des candidats fantômes. Sur le cas réel, douze
  fenêtres rendaient douze réponses incohérentes à ±90 s, et l'escalier
  apparaissait du premier coup à ±12 s ;
- **une fenêtre dont le pic touche la borne est écartée**, pas moyennée : c'est
  le signe qu'il n'y a pas de pic du tout.

Enfin, rien n'est appliqué d'office : la fonction rend des plages, que
l'utilisateur consulte (`S`) puis applique (`P`).
"""
from __future__ import annotations

import numpy as np
import pytest

from core.sync import BIN_MS, _lag_borne, _segments_par_accord


def _parole(n: int, graine: int = 7) -> np.ndarray:
    """Un masque de parole plausible : des blocs, des silences, irréguliers."""
    rng = np.random.default_rng(graine)
    m, t = np.zeros(n), 0
    while t < n:
        d = int(rng.integers(150, 600))
        m[t:t + d] = 1.0
        t += d + int(rng.integers(100, 400))
    return m


def _decale(ref: np.ndarray, paliers: list[tuple[int, int, int]]) -> np.ndarray:
    """Construit un signal avançant sur `ref` de `ms` par plage de bins."""
    sig = np.zeros_like(ref)
    for a, b, ms in paliers:
        bins = ms // BIN_MS
        sig[a:b] = np.roll(ref, -bins)[a:b]
    return sig


# ─── La recherche bornée ──────────────────────────────────────────────────────

@pytest.mark.parametrize("ms", [300, 1500, -800, 0])
def test_le_decalage_est_retrouve(ms):
    ref = _parole(60_000)
    sig = np.roll(ref, -(ms // BIN_MS))
    lag, saillance = _lag_borne(ref, sig, 30.0, 100)
    assert lag == ms
    assert saillance > 0.5


def test_un_pic_colle_a_la_borne_est_ecarte():
    """Sans pic réel, la corrélation s'échappe vers la borne. On ne la suit pas.

    C'est ce qui distingue un palier d'un artefact : sur le cas réel, les
    fenêtres fautives rendaient toutes ±10 à ±12 s, exactement la borne.
    """
    ref = _parole(60_000)
    autre = _parole(60_000, graine=99)          # aucun rapport avec ref
    lag, _ = _lag_borne(ref, autre, 1.0, 100)   # borne très serrée
    assert lag is None or abs(lag) < 900


def test_un_signal_plat_ne_rend_rien():
    ref = _parole(60_000)
    assert _lag_borne(ref, np.zeros(60_000), 30.0, 100) == (None, 0.0)


# ─── Les paliers ──────────────────────────────────────────────────────────────

def test_deux_paliers_sont_retrouves():
    n = 120_000                                  # 20 min : huit fenêtres
    ref = _parole(n)
    sig = _decale(ref, [(0, n // 2, 200), (n // 2, n, 2000)])
    segs = _segments_par_accord(ref, sig)
    assert len(segs) == 2, [(s.start_s, s.delay_ms) for s in segs]
    assert segs[0].delay_ms == pytest.approx(200, abs=150)
    assert segs[1].delay_ms == pytest.approx(2000, abs=150)


def test_trois_paliers_comme_le_cas_reel():
    """La forme rencontrée sur `the.fall` : trois plages, deux bascules."""
    n = 180_000                                  # 30 min
    a, b = n // 3, 2 * n // 3
    ref = _parole(n, graine=11)
    sig = _decale(ref, [(0, a, 300), (a, b, 1500), (b, n, 5600)])
    segs = _segments_par_accord(ref, sig)
    assert len(segs) == 3, [(s.start_s, s.delay_ms) for s in segs]
    assert [s.delay_ms for s in segs] == [
        pytest.approx(300, abs=200), pytest.approx(1500, abs=200),
        pytest.approx(5600, abs=200)]


def test_les_plages_sont_jointives_et_couvrent_tout():
    """Un trou ferait rendre à `delay_at` le décalage de la plage suivante."""
    n = 180_000
    ref = _parole(n, graine=11)
    sig = _decale(ref, [(0, n // 3, 300), (n // 3, 2 * n // 3, 1500),
                        (2 * n // 3, n, 5600)])
    segs = _segments_par_accord(ref, sig)
    assert segs[0].start_s == 0.0
    for gauche, droite in zip(segs, segs[1:]):
        assert gauche.end_s == droite.start_s, "plages disjointes"
    assert segs[-1].end_s >= (n - 1) * BIN_MS / 1000


def test_un_decalage_constant_rend_une_seule_plage():
    n = 120_000
    ref = _parole(n)
    segs = _segments_par_accord(ref, np.roll(ref, -50))
    assert len(segs) == 1
    assert segs[0].delay_ms == pytest.approx(500, abs=150)


# ─── Ce qu'elle refuse ────────────────────────────────────────────────────────

def test_deux_signaux_sans_rapport_ne_rendent_rien():
    """Le cas qui compte : ne rien dire vaut mieux que dire faux."""
    ref = _parole(180_000, graine=1)
    autre = _parole(180_000, graine=2)
    assert _segments_par_accord(ref, autre) == []


def test_un_extrait_trop_court_ne_rend_rien():
    """Moins de quatre fenêtres : il n'y a rien à croiser."""
    ref = _parole(40_000)
    assert _segments_par_accord(ref, np.roll(ref, -30)) == []


def test_un_signal_vide_ne_rend_rien():
    ref = _parole(180_000)
    assert _segments_par_accord(ref, np.zeros(180_000)) == []
