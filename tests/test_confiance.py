"""
tests/test_confiance.py — La confiance se lit en mots, relativement au seuil.

« confiance 0.09 » ne dit rien à qui n'a pas le seuil en tête. Et le seuil
n'est pas fixe : `confidence_floor()` le relève quand les repères se raréfient,
parce qu'une corrélation sur peu d'événements se trompe plus facilement. Un
même chiffre n'a donc pas le même sens d'une mesure à l'autre — 0,30 est une
bonne mesure sur un sous-titre bavard, une mauvaise sur une piste de forcés.

D'où quatre niveaux calculés **relativement au seuil**, et non sur des paliers
absolus. La frontière entre « faible » et « moyenne » n'est pas arbitraire :
c'est celle de la décision, sous laquelle la mesure est refusée.
"""
from __future__ import annotations

import pytest

from core.sync import MIN_CONFIDENCE, confidence_floor, libelle_confiance


# ─── Les quatre niveaux ───────────────────────────────────────────────────────

@pytest.mark.parametrize("confiance, attendu", [
    (0.00, "aucune"),
    (0.09, "aucune"),      # le cas mesuré sur un sous-titre d'une autre version
    (0.12, "aucune"),
    (0.13, "faible"),
    (0.24, "faible"),
    (0.25, "moyenne"),     # le seuil lui-même : la mesure passe
    (0.37, "moyenne"),
    (0.38, "excellente"),
    (0.90, "excellente"),
])
def test_les_niveaux_au_seuil_par_defaut(confiance, attendu):
    assert libelle_confiance(confiance, MIN_CONFIDENCE) == attendu


def test_le_seuil_par_defaut_s_applique_sans_argument():
    assert libelle_confiance(0.09) == "aucune"
    assert libelle_confiance(0.90) == "excellente"


# ─── Le libellé suit le seuil, pas une échelle absolue ────────────────────────

def test_un_meme_chiffre_change_de_sens_selon_le_seuil():
    """C'est toute la raison d'être du libellé relatif."""
    assert libelle_confiance(0.30, seuil=0.25) == "moyenne"
    assert libelle_confiance(0.30, seuil=0.40) == "faible"


def test_la_frontiere_est_celle_de_la_decision():
    """« moyenne » commence exactement là où la mesure cesse d'être refusée."""
    for seuil in (0.25, 0.33, 0.50):
        assert libelle_confiance(seuil - 0.001, seuil) in ("aucune", "faible")
        assert libelle_confiance(seuil, seuil) == "moyenne"


def test_un_seuil_absent_retombe_sur_le_minimum():
    """`SyncResult.floor` vaut 0 tant qu'aucune mesure n'a tourné."""
    assert libelle_confiance(0.30, seuil=0.0) == "moyenne"


def test_le_seuil_monte_quand_les_reperes_manquent():
    """Le lien avec `confidence_floor` : peu d'événements, exigence plus haute."""
    bavard = confidence_floor(600)
    forces = confidence_floor(25)
    assert forces > bavard
    # Une même corrélation est retenue sur l'un, refusée sur l'autre.
    assert libelle_confiance(0.30, bavard) == "moyenne"
    assert libelle_confiance(0.30, forces) in ("aucune", "faible")


# ─── Ce que l'écran affiche ───────────────────────────────────────────────────

def test_le_compte_rendu_nomme_le_niveau_avant_les_nombres():
    from core.sync import SyncResult
    r = SyncResult(0, None, 0.09, False, "aucun alignement commun",
                   floor=0.25, n_events=589)
    rendu = r.report()
    assert "confiance aucune" in rendu
    assert "0.09 pour 0.25 requis" in rendu, "les nombres restent analysables"


def test_le_libelle_compact_ne_montre_que_le_mot():
    from core.sync import SyncResult
    r = SyncResult(2450, None, 0.62, True, "", floor=0.25, cross_checked=True)
    compact = r.label()
    assert "confiance excellente" in compact
    assert "0.62" not in compact
