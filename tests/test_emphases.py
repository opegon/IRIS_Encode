"""
tests/test_emphases.py — Une décision porte la même couleur sur tous les écrans.

Trois tables indépendantes coloraient les mêmes notions : celle de
`core/decision.py`, celle de l'écran des pistes, et celle des valeurs de profil
dans `tui/common.py`. La même action y prenait deux teintes selon l'écran, et
le vert signifiait « gain de taille » ici, « décision de piste » là.

Les couleurs se décident désormais une fois, en nommant leur rôle. Ces tests
verrouillent trois choses : que les écrans lisent bien cette table unique, que
le cas le plus banal ne crie pas, et que `dark_orange` reste réservé aux
alertes — une réserve n'a de valeur que si rien d'autre ne l'emploie.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from core.decision import (
    STYLE_PAR_EMPHASE, DVAction, Emphase, VideoAction,
    emphase_dv, emphase_video, style_dv, style_video,
)

RACINE = Path(__file__).resolve().parent.parent


# ─── Le classement ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("action, dv, attendu", [
    (VideoAction.SKIP,        None,           Emphase.INACTION),
    (VideoAction.STRIP_DV,    DVAction.HDR10, Emphase.SANS_PERTE),
    (VideoAction.ENCODE_HEVC, DVAction.HDR10, Emphase.ORDINAIRE),
    (VideoAction.ENCODE_H264, DVAction.NONE,  Emphase.ORDINAIRE),
    (VideoAction.ENCODE_AV1,  DVAction.NONE,  Emphase.ALERTE),
    (VideoAction.ENCODE_HEVC, DVAction.SDR,   Emphase.ALERTE),
])
def test_emphase_video(action, dv, attendu):
    assert emphase_video(action, dv) is attendu


@pytest.mark.parametrize("dv, attendu", [
    (DVAction.NONE,  Emphase.ORDINAIRE),
    (DVAction.HDR10, Emphase.ORDINAIRE),
    (DVAction.DV,    Emphase.SANS_PERTE),
    (DVAction.SDR,   Emphase.ALERTE),
])
def test_emphase_dv(dv, attendu):
    assert emphase_dv(dv) is attendu


def test_toute_action_est_classee():
    """Un membre ajouté sans rôle tomberait ici, pas devant l'utilisateur."""
    for action in VideoAction:
        assert emphase_video(action) in Emphase


# ─── Les arbitrages du rapport ────────────────────────────────────────────────

def test_le_cas_banal_ne_crie_pas():
    """`→ HEVC` occupe presque chaque ligne de l'écran le plus dense : il
    portait le magenta, la teinte la plus criarde."""
    assert style_video(VideoAction.ENCODE_HEVC, DVAction.HDR10) == ""


def test_dark_orange_reste_aux_alertes():
    """La convention du projet le réserve aux alertes ; l'écran des pistes
    l'employait pour un encodage HEVC ordinaire."""
    orange = [e for e, s in STYLE_PAR_EMPHASE.items() if "dark_orange" in s]
    assert orange == [Emphase.ALERTE]


def test_le_vert_ne_dit_qu_une_chose():
    vert = [e for e, s in STYLE_PAR_EMPHASE.items() if s == "green"]
    assert vert == [Emphase.SANS_PERTE]


# ─── Les écrans lisent la table unique ────────────────────────────────────────

def test_l_ecran_des_pistes_ne_tient_pas_sa_propre_table():
    """`_ACTION_SHORT` et `_DV_SHORT` ne portent plus que des libellés."""
    from tui.screens.tracks import _ACTION_SHORT, _DV_SHORT

    for table in (_ACTION_SHORT, _DV_SHORT):
        for valeur in table.values():
            assert isinstance(valeur, str), (
                f"{valeur!r} — un couple (libellé, couleur) est revenu"
            )


def test_toute_action_a_un_libelle_sur_l_ecran_des_pistes():
    """STRIP_DV n'y figurait pas : la ligne affichait « ? »."""
    from tui.screens.tracks import _ACTION_SHORT

    for action in VideoAction:
        assert action in _ACTION_SHORT, f"{action.name} sans libellé"


def test_les_valeurs_de_profil_derivent_de_la_meme_table():
    from tui.common import DV_VALUE_STYLES

    assert DV_VALUE_STYLES["sdr"] == style_dv(DVAction.SDR)
    assert DV_VALUE_STYLES["dv"] == style_dv(DVAction.DV)
    assert DV_VALUE_STYLES["hdr10"] == style_dv(DVAction.HDR10)


def test_plus_de_couleur_de_decision_ecrite_en_dur():
    """Les teintes qui portaient une décision ne doivent plus apparaître comme
    littéraux dans les modules concernés."""
    interdits = re.compile(r'"(bold )?magenta[^"]*"')
    for rel in ("core/decision.py", "tui/screens/tracks.py", "tui/common.py",
                "tui/screens/browser.py", "tui/screens/dryrun.py"):
        src = (RACINE / rel).read_text(encoding="utf-8")
        assert not interdits.search(src), f"{rel} — magenta écrit en dur"
