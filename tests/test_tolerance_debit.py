"""
tests/test_tolerance_debit.py — Le CAS 1 tolère ±10 % autour du débit cible.

La cible est une moyenne visée. En VBR avec 50 % de marge, une sortie réussie
la dépasse de quelques pourcents : 2 100k à 2 500k pour 2 000k visés, relevé
sur une série encodée avec `video_basic_delete` (2026-10-03). Sans tolérance,
chacune repartait en CAS 1 au scan suivant — un 720p à 1 505k pour 1 500k
visés était proposé au réencodage pour 1 % de gain, au prix d'une génération
de perte.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.decision import TOLERANCE_DEBIT_PCT, VideoAction, decide_video
from core.profiles import Profile
from core.scanner import VideoInfo

PROFIL = Profile("t", {"bitrate_720p_kbps": 1500, "bitrate_1080p_kbps": 2000,
                       "bitrate_4k_kbps": 2000})


def _info(kbps: int, w: int = 1920, h: int = 1080, codec: str = "hevc") -> VideoInfo:
    return VideoInfo(path=Path("Film.mkv"), width=w, height=h,
                     bitrate=kbps * 1000, codec=codec, duration=1500.0,
                     frame_count=0, dv_profile=None)


def test_la_tolerance_vaut_dix_pourcents():
    assert TOLERANCE_DEBIT_PCT == 10


@pytest.mark.parametrize("kbps", [2000, 2100, 2143, 2200])
def test_une_sortie_dans_la_tolerance_n_est_pas_reencodee(kbps):
    assert decide_video(_info(kbps), PROFIL).action == VideoAction.SKIP


def test_le_720p_a_un_pourcent_de_la_cible_n_est_pas_reencode():
    dec = decide_video(_info(1505, 1280, 720, "h264"), PROFIL)
    assert dec.action == VideoAction.SKIP


@pytest.mark.parametrize("kbps", [2201, 2514, 8000])
def test_au_dela_de_la_tolerance_le_cas_1_s_applique(kbps):
    dec = decide_video(_info(kbps), PROFIL)
    assert dec.action == VideoAction.ENCODE_HEVC
    assert dec.target_bitrate == 2_000_000


def test_la_raison_du_skip_dit_que_le_debit_est_dans_la_tolerance():
    assert "±10 %" in decide_video(_info(2100), PROFIL).reason
    assert "±" not in decide_video(_info(1800), PROFIL).reason


def test_la_tolerance_ne_couvre_pas_les_autres_cas():
    """Un codec illisible ou une résolution trop grande se réencodent même
    dans la tolérance : la tolérance ne porte que sur le débit."""
    assert decide_video(_info(2100, codec="vp9"), PROFIL).action == VideoAction.ENCODE_HEVC
    assert decide_video(_info(2100, 3840, 2160), PROFIL).action == VideoAction.ENCODE_HEVC
