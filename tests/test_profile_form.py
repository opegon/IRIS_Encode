"""
tests/test_profile_form.py — Le couple audio sans perte ne peut plus se contredire.

`preserve_hd_audio` et `audio_hd_codec` étaient deux réglages indépendants dont
l'un l'emportait en silence : un profil pouvait porter « copier sans perte » et
« transcoder en E-AC3 » à la fois, et rien à l'écran ne disait lequel gagnait.
L'écran n'expose plus qu'un choix, et ces tests verrouillent la traduction dans
les deux sens.
"""
from __future__ import annotations

import pytest

from tui.widgets.profile_form import _hd_audio_cles, _hd_audio_depuis_cles


# ─── Du choix vers les clés ───────────────────────────────────────────────────

@pytest.mark.parametrize("branche, preserve, codec", [
    ("copy",    True,  "none"),
    ("eac3",    False, "eac3"),
    ("ac3",     False, "ac3"),
    ("forfait", False, "none"),
])
def test_ecriture_du_couple(branche, preserve, codec):
    d = _hd_audio_cles(branche)
    assert d["preserve_hd_audio"] is preserve
    assert d["audio_hd_codec"] == codec


def test_branche_inconnue_retombe_sur_le_forfait():
    """Une valeur inattendue ne doit pas activer la copie sans perte."""
    d = _hd_audio_cles("n_importe_quoi")
    assert d["preserve_hd_audio"] is False
    assert d["audio_hd_codec"] == "none"


# ─── Des clés vers le choix ───────────────────────────────────────────────────

@pytest.mark.parametrize("preserve, codec, attendu", [
    (True,  "none", "copy"),
    (False, "eac3", "eac3"),
    (False, "ac3",  "ac3"),
    (False, "none", "forfait"),
])
def test_lecture_du_couple(preserve, codec, attendu):
    assert _hd_audio_depuis_cles(preserve, codec) == attendu


@pytest.mark.parametrize("codec", ["eac3", "ac3"])
def test_couple_contradictoire_affiche_ce_qui_se_passe(codec):
    """La copie l'emporte dans le moteur : c'est elle que l'écran doit montrer,
    pas l'intention qu'exprimait le codec."""
    assert _hd_audio_depuis_cles(True, codec) == "copy"


def test_aller_retour_stable():
    for branche in ("copy", "eac3", "ac3", "forfait"):
        d = _hd_audio_cles(branche)
        relu = _hd_audio_depuis_cles(d["preserve_hd_audio"], d["audio_hd_codec"])
        assert relu == branche
