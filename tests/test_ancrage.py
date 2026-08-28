"""
tests/test_ancrage.py — Recaler à partir d'un point donné à l'oreille.

Dernier recours, et il existe parce que la corrélation a une limite qu'aucun
réglage ne franchit : un sous-titre dont l'adaptation diffère de celle du
doublage plafonne à **0,117** pour un seuil de 0,25, *même parfaitement
aligné*, vérifié à l'oreille en six points sur `the.fall.s02e01`.

Elle n'a pourtant pas besoin d'être fiable — seulement d'être **bornée**.
L'utilisateur donne deux instants, la recherche se centre sur leur écart et se
resserre à ±12 s. Ce qui était insoluble redevient un problème bien posé.

Deux choses sont testées ici : la lecture des instants, tolérante à dessein
parce que personne ne doit deviner le format attendu ; et le fait que la
recherche centrée retrouve bien les paliers autour du point donné.
"""
from __future__ import annotations

import numpy as np
import pytest

from core.sync import (BIN_MS, Segment, _segments_par_accord,
                       accord_avec_ancre, lire_timecode)


# ─── Lecture d'un instant saisi ───────────────────────────────────────────────

@pytest.mark.parametrize("texte, attendu", [
    ("13:16",     796.0),
    ("1:13:16",   4396.0),
    ("13:16,5",   796.5),
    ("13:16.5",   796.5),
    ("796",       796.0),
    ("0:00",      0.0),
    ("  13:16 ",  796.0),
])
def test_les_formats_acceptes(texte, attendu):
    assert lire_timecode(texte) == attendu


@pytest.mark.parametrize("texte", ["", "   ", "abc", "1:2:3:4", "-5", "13:xx",
                                   None])
def test_ce_qui_n_est_pas_lisible_rend_none(texte):
    """None plutôt qu'un zéro : un zéro passerait pour une réponse."""
    assert lire_timecode(texte) is None


# ─── La recherche centrée sur le point donné ──────────────────────────────────

def _parole(n: int, graine: int = 5) -> np.ndarray:
    rng = np.random.default_rng(graine)
    m, t = np.zeros(n), 0
    while t < n:
        d = int(rng.integers(150, 600))
        m[t:t + d] = 1.0
        t += d + int(rng.integers(100, 400))
    return m


def _paliers(ref, decoupe):
    sig = np.zeros_like(ref)
    for a, b, ms in decoupe:
        sig[a:b] = np.roll(ref, -(ms // BIN_MS))[a:b]
    return sig


def test_l_ancre_retrouve_les_paliers_autour_d_elle():
    """Le cas du signalement : trois plages, décalages de quelques secondes."""
    n = 180_000
    a, b = n // 3, 2 * n // 3
    ref = _parole(n, graine=11)
    sig = _paliers(ref, [(0, a, 300), (a, b, 1500), (b, n, 5600)])
    # L'utilisateur a entendu une réplique de la dernière plage 5,6 s trop tard.
    segs = _segments_par_accord(ref, sig, centre_ms=5600, max_lag_s=12.0)
    assert len(segs) == 3, [(s.start_s, s.delay_ms) for s in segs]
    assert [s.delay_ms for s in segs] == [
        pytest.approx(300, abs=200), pytest.approx(1500, abs=200),
        pytest.approx(5600, abs=200)]


def test_un_decalage_hors_de_portee_de_l_ancre_n_est_pas_invente():
    """La marge est étroite à dessein : au-delà, on ne rend rien."""
    n = 180_000
    ref = _parole(n, graine=11)
    sig = _paliers(ref, [(0, n, 30_000)])          # 30 s de décalage réel
    assert _segments_par_accord(ref, sig, centre_ms=0, max_lag_s=12.0) == []


def test_un_ancrage_faux_ne_reste_pas_muet_mais_se_trahit():
    """Le point qui rend le garde-fou nécessaire.

    Une recherche mal centrée ne rend pas rien : elle trouve un pic secondaire,
    et sa régularité compose des plages d'allure honnête. Mesuré : +1600 ms là
    où l'utilisateur annonçait −8000. C'est le **désaccord** entre les deux qui
    trahit l'erreur, pas l'absence de résultat.
    """
    n = 180_000
    ref = _parole(n, graine=3)
    sig = _paliers(ref, [(0, n, 8_000)])

    bon = _segments_par_accord(ref, sig, centre_ms=8000, max_lag_s=12.0)
    assert bon and accord_avec_ancre(bon, 8000)

    faux = _segments_par_accord(ref, sig, centre_ms=-8000, max_lag_s=12.0)
    assert faux, "la recherche mal centrée trouve quand même quelque chose"
    assert not accord_avec_ancre(faux, -8000),         "et ce quelque chose doit être reconnu comme un désaccord"


@pytest.mark.parametrize("delais, centre, attendu", [
    ([300, 1500, 5600], 5600,  True),    # une plage confirme le point donné
    ([300, 1500, 5600], 300,   True),    # n'importe laquelle suffit
    ([300, 1500, 5600], 5600 + 1900, True),   # dans la tolérance
    ([300, 1500, 5600], 5600 + 2500, False),  # au-delà
    ([1600],            -8000, False),   # le cas mesuré
    ([],                0,     False),   # rien à confirmer
])
def test_l_accord_avec_l_ancre(delais, centre, attendu):
    segs = [Segment(0.0, 10.0, d, 0.3) for d in delais]
    assert accord_avec_ancre(segs, centre) is attendu


def test_la_recherche_centree_ne_derive_pas_vers_zero():
    """Sans centrage, un décalage de 20 s sort de la fenêtre par défaut."""
    n = 180_000
    ref = _parole(n, graine=8)
    sig = _paliers(ref, [(0, n, 20_000)])
    centre = _segments_par_accord(ref, sig, centre_ms=20_000, max_lag_s=12.0)
    assert len(centre) == 1
    assert centre[0].delay_ms == pytest.approx(20_000, abs=200)
