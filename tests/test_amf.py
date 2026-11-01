"""
tests/test_amf.py — AMD AMF sur un poste Windows sans NVIDIA (expérimental).

Écrit sans carte AMD : ces tests vérifient la commande construite, pas que la
carte encode bien. AMF est retenu sur sondage, comme Quick Sync, et passe
avant lui.
"""
from __future__ import annotations

import pytest

from core import platform as plat
from core.platform import GPU, OS, PlatformProfile
from tests.test_qsv import _CPU, _NVIDIA, _apres, _commande, _sonde

_AMD = PlatformProfile(os=OS.WINDOWS, gpu=GPU.AMD, hwaccel=None,
                       encoder_hevc="hevc_amf", encoder_h264="h264_amf",
                       encoder_av1="av1_amf")


def test_amf_retenu_quand_hevc_amf_s_ouvre(monkeypatch):
    monkeypatch.setattr(plat, "sonder_encodeurs", _sonde({"hevc_amf"}))
    p = plat.avec_amf(_CPU)
    assert p.gpu == GPU.AMD
    assert (p.encoder_hevc, p.encoder_h264, p.encoder_av1) == (
        "hevc_amf", "h264_amf", "av1_amf")
    assert p.hwaccel is None          # lecture au processeur : rien de mesuré


def test_processeur_garde_quand_amf_refuse(monkeypatch):
    monkeypatch.setattr(plat, "sonder_encodeurs", _sonde(set()))
    assert plat.avec_amf(_CPU) is _CPU


def test_nvidia_n_est_pas_sonde(monkeypatch):
    appels: list = []
    monkeypatch.setattr(plat, "sonder_encodeurs", _sonde({"hevc_amf"}, appels))
    assert plat.avec_amf(_NVIDIA) is _NVIDIA
    assert appels == []


def test_amd_passe_avant_intel(monkeypatch):
    """Processeur Intel et carte Radeon : la Radeon, en général plus rapide."""
    monkeypatch.setattr(plat, "sonder_encodeurs", _sonde({"hevc_amf", "hevc_qsv"}))
    assert plat.avec_qsv(plat.avec_amf(_CPU)).gpu == GPU.AMD


def test_amf_sonde_aussi_en_10_bits():
    liste = plat.encodeurs_a_sonder(_AMD)
    assert "hevc_amf@10" in liste and "av1_amf@10" in liste
    assert "h264_amf@10" not in liste


def test_hdr10_encode_sur_la_carte_le_reste_au_processeur(tmp_path):
    from core.encoder import sortie_10_bits
    cmd = _commande(tmp_path, plat=_AMD)
    assert _apres(cmd, "-c:v") == "hevc_amf"
    assert "-hwaccel" not in cmd and "-hwaccel_output_format" not in cmd
    # AMF refuse `-preset medium` et ne prend pas `yuv420p10le`.
    assert "-preset" not in cmd
    assert _apres(cmd, "-quality") == "balanced"
    assert _apres(cmd, "-pix_fmt") == "p010le"
    assert _apres(cmd, "-profile:v") == "main10"
    assert _apres(cmd, "-rc") == "vbr_peak"
    assert sortie_10_bits(cmd)


@pytest.mark.parametrize("preset,qualite", [
    ("veryfast", "speed"), ("fast", "speed"), ("medium", "balanced"),
    ("slow", "quality"), ("veryslow", "quality"),
])
def test_preset_traduit_pour_amf(preset, qualite):
    from core.encoder import option_preset
    assert option_preset("av1_amf", preset) == ["-quality", qualite]
    assert option_preset("hevc_nvenc", preset) == ["-preset", preset]
    assert option_preset("libx265", preset) == ["-preset", preset]


def test_regle_debit_amf():
    from core.encoder import regle_debit
    args = regle_debit("hevc_amf", 4_000_000)
    assert _apres(args, "-rc") == "vbr_peak"
    assert _apres(args, "-maxrate") == "6000000"


def test_la_passe_dv_amd_reste_au_processeur():
    from tests.test_nvdec import _passe_dv
    amd = PlatformProfile(os=OS.WINDOWS, gpu=GPU.AMD, hwaccel=None,
                          encoder_hevc="hevc_amf", encoder_h264="h264_amf",
                          encoder_av1="av1_amf",
                          encodeurs_ok=frozenset({"hevc_amf", "hevc_amf@10"}))
    cmd = _passe_dv(amd)
    assert "-hwaccel" not in cmd
    assert _apres(cmd, "-pix_fmt") == "p010le"
    assert "-preset" not in cmd and _apres(cmd, "-quality") == "balanced"


def test_av1_amf_refuse_parle_d_amd_pas_de_nvenc():
    from types import SimpleNamespace

    from tui.screens.run import FileState, RunScreen
    amd = PlatformProfile(os=OS.WINDOWS, gpu=GPU.AMD, hwaccel=None,
                          encoder_hevc="hevc_amf", encoder_h264="h264_amf",
                          encoder_av1="av1_amf",
                          encodeurs_ok=frozenset({"hevc_amf", "h264_amf"}))
    statut = SimpleNamespace(state=FileState.RUNNING, error_msg="", last_line="")
    ecran = SimpleNamespace(_statuses=[statut], _platform=amd,
                            app=SimpleNamespace(call_from_thread=lambda f, *a: f(*a)),
                            _update_row=lambda i: None)
    cmd = ["ffmpeg", "-i", "x.mkv", "-c:v", "av1_amf", "-pix_fmt", "yuv420p", "y.mkv"]
    assert RunScreen._refuser_encodeur(ecran, 0, cmd) is True
    assert "Radeon" in statut.last_line
    assert "NVENC" not in statut.last_line
