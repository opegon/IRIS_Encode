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


# ─── Tout sur la puce : décodage, mise à l'échelle, encodage (IE-147) ────────

_INTEL = PlatformProfile(os=OS.WINDOWS, gpu=GPU.INTEL, hwaccel=None,
                         encoder_hevc="hevc_qsv", encoder_h264="h264_qsv",
                         encoder_av1="av1_qsv")


def _commande(tmp_path, plat=_INTEL, *, w=3840, h=2160, codec="hevc",
              pix_fmt="yuv420p10le", transfert="smpte2084", ordre="progressive",
              sar="1:1", dv=None):
    from dataclasses import replace

    from core.decision import VideoAction, decide, force_skip_to_encode
    from core.encoder import build_command
    from core.profiles import Profile
    from core.scanner import AudioTrack, VideoInfo

    p = tmp_path / "film.mkv"
    p.write_bytes(b"")
    info = VideoInfo(path=p, width=w, height=h, bitrate=12_000_000, codec=codec,
                     duration=60.0, frame_count=0, dv_profile=dv,
                     dv_bl_compat=1 if dv else None,
                     audio_tracks=[AudioTrack(index=0, codec="aac", channels=2,
                                              language="fre", title="",
                                              bitrate=128_000)],
                     color_transfer=transfert, field_order=ordre, sar=sar,
                     pix_fmt=pix_fmt)
    prof = Profile(id="t", data={"bitrate_1080p_kbps": 2500,
                                 "bitrate_720p_kbps": 2000,
                                 "bitrate_4k_kbps": 5000, "keep_4k": False,
                                 "dolby_vision": "hdr10",
                                 "audio_languages": ["fre"],
                                 "audio_copy_compatible": True})
    dec = force_skip_to_encode(decide(info, prof))
    dec = replace(dec, video=replace(dec.video, action=VideoAction.ENCODE_HEVC))
    return build_command(dec, plat)


def _apres(cmd, opt):
    return cmd[cmd.index(opt) + 1] if opt in cmd else None


def test_4k_hdr10_vers_1080p_tout_sur_la_puce(tmp_path):
    """Le cas mesuré sur le portable : 18 s au lieu de 60, HDR10 intact."""
    from core.encoder import sortie_10_bits
    cmd = _commande(tmp_path)
    assert _apres(cmd, "-hwaccel") == "qsv"
    assert cmd.index("-hwaccel") < cmd.index("-i")       # option d'entrée
    assert _apres(cmd, "-hwaccel_output_format") == "qsv"
    assert _apres(cmd, "-vf") == "vpp_qsv=w=1920:h=1080:format=p010le"
    assert "-pix_fmt" not in cmd
    assert _apres(cmd, "-c:v") == "hevc_qsv"
    assert _apres(cmd, "-profile:v") == "main10"
    assert _apres(cmd, "-aspect") == "1920:1080"
    assert sortie_10_bits(cmd)


def test_sdr_sans_changement_de_taille_reste_sur_la_puce(tmp_path):
    from core.encoder import sortie_10_bits
    cmd = _commande(tmp_path, w=1920, h=1080, codec="h264", pix_fmt="yuv420p",
                    transfert="bt709")
    assert _apres(cmd, "-vf") == "vpp_qsv=format=nv12"
    assert _apres(cmd, "-hwaccel_output_format") == "qsv"
    assert "-aspect" not in cmd
    assert _apres(cmd, "-profile:v") == "main"
    assert not sortie_10_bits(cmd)


import pytest


@pytest.mark.parametrize("cas", [
    dict(codec="h264", pix_fmt="yuv420p10le"),          # Hi10P : non décodable
    dict(codec="mpeg4", pix_fmt="yuv420p", transfert=""),
    dict(pix_fmt=""),                                    # format inconnu
    dict(ordre="tt"),                                    # désentrelacement
    dict(w=720, h=480, sar="32:27", codec="mpeg2video", pix_fmt="yuv420p",
         transfert=""),                                  # pixels non carrés
    dict(dv=8),                                          # Dolby Vision
])
def test_les_autres_cas_restent_au_processeur(tmp_path, cas):
    cmd = _commande(tmp_path, **cas)
    assert "-hwaccel_output_format" not in cmd
    assert not (_apres(cmd, "-vf") or "").startswith("vpp_qsv")
    assert "-pix_fmt" in cmd


def test_nvidia_n_est_pas_concerne(tmp_path):
    cmd = _commande(tmp_path, plat=_NVIDIA)
    assert _apres(cmd, "-hwaccel") == "cuda"
    assert "vpp_qsv" not in " ".join(cmd)


def test_dimensions_comme_scale():
    from core.encoder import dimensions_reduites
    assert dimensions_reduites(3840, 2160, 1920, 1080) == (1920, 1080)
    # Relevés avec `scale` (ffmpeg 8.1.2) : arrondi au pair le plus proche,
    # mi-chemin vers le haut — une hauteur différente changerait l'image.
    assert dimensions_reduites(3832, 1600, 1920, 1080) == (1920, 802)
    assert dimensions_reduites(3840, 1600, 1280, 720) == (1280, 534)
    assert dimensions_reduites(4096, 2160, 3840, 2160) == (3840, 2026)
    assert dimensions_reduites(1440, 1080, 1280, 720) == (960, 720)


def test_le_mode_hdr10_quality_reste_a_libx265(tmp_path):
    """`hdr10_quality = "quality"` impose libx265 : rien sur la puce."""
    from dataclasses import replace

    from core.decision import DVAction, VideoAction, decide, force_skip_to_encode
    from core.encoder import build_command
    from core.profiles import Profile
    from core.scanner import VideoInfo

    p = tmp_path / "film.mkv"
    p.write_bytes(b"")
    info = VideoInfo(path=p, width=3840, height=2160, bitrate=12_000_000,
                     codec="hevc", duration=60.0, frame_count=0, dv_profile=None,
                     color_transfer="smpte2084", pix_fmt="yuv420p10le")
    prof = Profile(id="t", data={"bitrate_1080p_kbps": 2500, "bitrate_720p_kbps": 2000,
                                 "bitrate_4k_kbps": 5000, "hdr10_quality": "quality"})
    dec = force_skip_to_encode(decide(info, prof))
    dec = replace(dec, video=replace(dec.video, action=VideoAction.ENCODE_HEVC,
                                     dv_action=DVAction.HDR10))
    cmd = build_command(dec, _INTEL)
    assert cmd[cmd.index("-c:v") + 1] == "libx265"
    assert "-hwaccel" not in cmd and "vpp_qsv" not in " ".join(cmd)
