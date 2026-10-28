"""
tests/test_qsv.py — Intel Quick Sync sur un poste Windows sans NVIDIA.

Sans carte NVIDIA, IRIS encodait tout au processeur, même sur une puce Intel
qui sait encoder le HEVC 8 et 10 bits (essai sur un i5-1135G7, 2026-10-28).
QSV est retenu sur sondage, jamais d'après le modèle de puce.
"""
from __future__ import annotations

from core import platform as plat
from core.platform import GPU, OS, PlatformProfile

_CPU = PlatformProfile(os=OS.WINDOWS, gpu=GPU.NONE, hwaccel=None,
                       encoder_hevc="libx265", encoder_h264="libx264",
                       encoder_av1="libaom-av1")
_NVIDIA = PlatformProfile(os=OS.WINDOWS, gpu=GPU.NVIDIA, hwaccel="cuda",
                          encoder_hevc="hevc_nvenc", encoder_h264="h264_nvenc",
                          encoder_av1="av1_nvenc")


def _sonde(ouvre: set[str], appels: list | None = None):
    def sonder(encodeurs, ffmpeg_path="ffmpeg", refus=None):
        if appels is not None:
            appels.append(list(encodeurs))
        return frozenset(e for e in encodeurs if e in ouvre)
    return sonder


def test_qsv_retenu_quand_hevc_qsv_s_ouvre(monkeypatch):
    monkeypatch.setattr(plat, "sonder_encodeurs", _sonde({"hevc_qsv"}))
    p = plat.avec_qsv(_CPU)
    assert p.gpu == GPU.INTEL
    assert (p.encoder_hevc, p.encoder_h264, p.encoder_av1) == (
        "hevc_qsv", "h264_qsv", "av1_qsv")
    # Décodage au processeur tant que -hwaccel n'est pas mesuré sur Intel.
    assert p.hwaccel is None


def test_processeur_garde_quand_qsv_refuse(monkeypatch):
    monkeypatch.setattr(plat, "sonder_encodeurs", _sonde(set()))
    assert plat.avec_qsv(_CPU) is _CPU


def test_nvidia_ni_linux_ne_sont_sondes(monkeypatch):
    appels: list = []
    monkeypatch.setattr(plat, "sonder_encodeurs", _sonde({"hevc_qsv"}, appels))
    assert plat.avec_qsv(_NVIDIA) is _NVIDIA
    linux = PlatformProfile(os=OS.LINUX, gpu=GPU.NONE, hwaccel=None,
                            encoder_hevc="libx265", encoder_h264="libx264",
                            encoder_av1="libaom-av1")
    assert plat.avec_qsv(linux) is linux
    assert appels == []


def test_qsv_sonde_aussi_en_10_bits(monkeypatch):
    monkeypatch.setattr(plat, "sonder_encodeurs", _sonde({"hevc_qsv"}))
    liste = plat.encodeurs_a_sonder(plat.avec_qsv(_CPU))
    assert "hevc_qsv@10" in liste and "av1_qsv@10" in liste
    assert "h264_qsv@10" not in liste


def test_10_bits_refuse_est_dit():
    p = PlatformProfile(os=OS.WINDOWS, gpu=GPU.INTEL, hwaccel=None,
                        encoder_hevc="hevc_qsv", encoder_h264="h264_qsv",
                        encoder_av1="av1_qsv",
                        encodeurs_ok=frozenset({"hevc_qsv"}))
    assert p.peut_encoder_10_bits("hevc_qsv") is False



def test_av1_qsv_refuse_parle_d_intel_pas_de_nvenc():
    """Le refus de l'AV1 sur un i5-1135G7 citait NVENC et la RTX 40."""
    from types import SimpleNamespace

    from tui.screens.run import FileState, RunScreen
    intel = PlatformProfile(os=OS.WINDOWS, gpu=GPU.INTEL, hwaccel=None,
                            encoder_hevc="hevc_qsv", encoder_h264="h264_qsv",
                            encoder_av1="av1_qsv",
                            encodeurs_ok=frozenset({"hevc_qsv", "h264_qsv"}))
    statut = SimpleNamespace(state=FileState.RUNNING, error_msg="", last_line="")
    ecran = SimpleNamespace(_statuses=[statut], _platform=intel,
                            app=SimpleNamespace(call_from_thread=lambda f, *a: f(*a)),
                            _update_row=lambda i: None)
    cmd = ["ffmpeg", "-i", "x.mkv", "-c:v", "av1_qsv", "-pix_fmt", "yuv420p", "y.mkv"]
    assert RunScreen._refuser_encodeur(ecran, 0, cmd) is True
    assert "Quick Sync" in statut.last_line
    assert "NVENC" not in statut.last_line
