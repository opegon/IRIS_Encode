"""
tests/test_nvenc_main10.py — HEVC NVENC en main10 même pour une sortie SDR.

Mesuré en VMAF sur une RTX A4500, au même débit : +0,1 à +0,4 point sur les
quatre extraits et les trois presets, sans perte de vitesse (IE-201,
`wiki/raw/2026-11-16-nvenc-options-vmaf.md`). Seulement si le sondage du
lancement a ouvert `hevc_nvenc` en 10 bits.
"""
from __future__ import annotations

from core.encoder import sortie_10_bits
from tests.test_nvdec import _SONDE, _nvidia
from tests.test_qsv import _apres, _commande

_SDR = dict(w=1920, h=1080, pix_fmt="yuv420p", transfert="bt709")


def test_sdr_sur_la_carte_en_main10(tmp_path):
    cmd = _commande(tmp_path, plat=_nvidia(), codec="h264", **_SDR)
    assert _apres(cmd, "-vf") == "scale_cuda=format=p010le"
    assert _apres(cmd, "-c:v") == "hevc_nvenc"
    assert _apres(cmd, "-profile:v") == "main10"
    assert sortie_10_bits(cmd)


def test_sdr_au_processeur_en_main10(tmp_path):
    """Source que NVDEC ne lit pas à coup sûr : conversion par `-pix_fmt`."""
    cmd = _commande(tmp_path, plat=_nvidia(), codec="mpeg4", **_SDR)
    assert "scale_cuda" not in " ".join(cmd)
    assert _apres(cmd, "-pix_fmt") == "yuv420p10le"
    assert _apres(cmd, "-profile:v") == "main10"


def test_carte_sans_10_bits_reste_en_8_bits(tmp_path):
    """Maxwell : le HEVC s'ouvre en 8 bits seulement."""
    cmd = _commande(tmp_path, plat=_nvidia(_SONDE - {"hevc_nvenc@10"}),
                    codec="mpeg4", **_SDR)
    assert _apres(cmd, "-pix_fmt") == "yuv420p"
    assert _apres(cmd, "-profile:v") == "main"
    assert not sortie_10_bits(cmd)


def test_sans_sondage_reste_en_8_bits(tmp_path):
    cmd = _commande(tmp_path, plat=_nvidia(None), codec="mpeg4", **_SDR)
    assert _apres(cmd, "-pix_fmt") == "yuv420p"
    assert _apres(cmd, "-profile:v") == "main"
