"""
tests/test_nvdec.py — tout sur la carte NVIDIA : NVDEC, `scale_cuda`, NVENC.

Avec `-hwaccel cuda` seul, chaque image décodée redescendait au processeur
pour `scale`, puis remontait à NVENC. Mesuré sur une RTX A4500 (60 s de 4K
HDR10 → 1080p) : 28 s, autant que sans décodage matériel ; 5,6 s sans
quitter la carte, HDR10 et écran de mastering conservés (IE-148).
"""
from __future__ import annotations

import pytest

from core.platform import GPU, OS, PlatformProfile
from tests.test_qsv import _apres, _commande

_SONDE = frozenset({"hevc_nvenc", "hevc_nvenc@10", "h264_nvenc"})


def _nvidia(ok=_SONDE):
    return PlatformProfile(os=OS.WINDOWS, gpu=GPU.NVIDIA, hwaccel="cuda",
                           encoder_hevc="hevc_nvenc", encoder_h264="h264_nvenc",
                           encoder_av1="av1_nvenc", encodeurs_ok=ok)


def test_4k_hdr10_vers_1080p_tout_sur_la_carte(tmp_path):
    from core.encoder import sortie_10_bits
    cmd = _commande(tmp_path, plat=_nvidia())
    assert _apres(cmd, "-hwaccel") == "cuda"
    assert cmd.index("-hwaccel") < cmd.index("-i")
    assert _apres(cmd, "-hwaccel_output_format") == "cuda"
    assert _apres(cmd, "-vf") == "scale_cuda=w=1920:h=1080:format=p010le"
    assert "-pix_fmt" not in cmd
    assert _apres(cmd, "-c:v") == "hevc_nvenc"
    assert _apres(cmd, "-profile:v") == "main10"
    # `scale_cuda` laisse un SAR de 192079:192000 sur 3832×1600 : `-aspect`.
    assert _apres(cmd, "-aspect") == "1920:1080"
    assert sortie_10_bits(cmd)


def test_h264_sans_changement_de_taille_reste_sur_la_carte(tmp_path):
    cmd = _commande(tmp_path, plat=_nvidia(), w=1920, h=1080, codec="h264",
                    pix_fmt="yuv420p", transfert="bt709")
    assert _apres(cmd, "-vf") == "scale_cuda=format=nv12"
    assert _apres(cmd, "-hwaccel_output_format") == "cuda"
    assert "-aspect" not in cmd


def test_h264_plage_pleine_sur_la_carte(tmp_path):
    """`scale_cuda` garde 0-255 et l'étiquette `pc`, comme `scale` (IE-149)."""
    cmd = _commande(tmp_path, plat=_nvidia(), w=1920, h=1080, codec="h264",
                    pix_fmt="yuvj420p", transfert="bt709")
    assert _apres(cmd, "-vf") == "scale_cuda=format=nv12"


def test_carte_anterieure_a_pascal_garde_le_chemin_actuel(tmp_path):
    """Sans HEVC 10 bits à l'encodage (Maxwell), rien ne garantit NVDEC."""
    cmd = _commande(tmp_path, plat=_nvidia(frozenset({"hevc_nvenc", "h264_nvenc"})),
                    w=1920, h=1080, codec="h264", pix_fmt="yuv420p",
                    transfert="bt709")
    assert _apres(cmd, "-hwaccel") == "cuda"
    assert "-hwaccel_output_format" not in cmd
    assert "-pix_fmt" in cmd


def test_sans_sondage_le_chemin_actuel(tmp_path):
    cmd = _commande(tmp_path, plat=_nvidia(None))
    assert "-hwaccel_output_format" not in cmd
    assert "scale_cuda" not in " ".join(cmd)


def test_av1_seulement_si_av1_nvenc_s_ouvre(tmp_path):
    """NVDEC lit l'AV1 depuis Ampere ; `av1_nvenc` (Ada) le garantit."""
    sans = _commande(tmp_path, plat=_nvidia(), codec="av1")
    assert "-hwaccel_output_format" not in sans
    avec = _commande(tmp_path, plat=_nvidia(_SONDE | {"av1_nvenc"}), codec="av1")
    assert _apres(avec, "-vf") == "scale_cuda=w=1920:h=1080:format=p010le"


@pytest.mark.parametrize("cas", [
    dict(codec="h264", pix_fmt="yuv420p10le"),          # Hi10P : Blackwell seul
    dict(codec="mpeg4", pix_fmt="yuv420p", transfert=""),
    dict(pix_fmt=""),                                    # format inconnu
    dict(ordre="tt"),                                    # désentrelacement
    dict(w=720, h=480, sar="32:27", codec="mpeg2video", pix_fmt="yuv420p",
         transfert=""),                                  # pixels non carrés
    dict(dv=8),                                          # Dolby Vision
])
def test_les_autres_cas_restent_au_processeur(tmp_path, cas):
    cmd = _commande(tmp_path, plat=_nvidia(), **cas)
    assert "-hwaccel_output_format" not in cmd
    assert "scale_cuda" not in " ".join(cmd)
    assert "-pix_fmt" in cmd


# ─── Passe vidéo du réencodage Dolby Vision (IE-149) ─────────────────────────

def _passe_dv(plat, pix_fmt="yuv420p10le"):
    from pathlib import Path

    from core import decision as D
    from core.encoder import build_dv_video_command
    from core.profiles import Profile
    from core.scanner import AudioTrack, VideoInfo
    D.set_strip_dv_available(True)
    try:
        info = VideoInfo(path=Path("Film.mkv"), width=3840, height=2160,
                         bitrate=60_000_000, codec="hevc", duration=7200.0,
                         frame_count=0, dv_profile=8, dv_bl_compat=1,
                         audio_tracks=[AudioTrack(index=0, codec="ac3", channels=6,
                                                  language="fre", title="",
                                                  bitrate=640_000)],
                         pix_fmt=pix_fmt)
        prof = Profile(id="dv", data={"bitrate_4k_kbps": 12000, "keep_4k": True,
                                      "dolby_vision": "dv"})
        dec = D.decide(info, prof)
        assert dec.video.action is D.VideoAction.ENCODE_DV
        return build_dv_video_command(dec, plat, Path("t.hevc"), "ffmpeg")
    finally:
        D.set_strip_dv_available(False)


def test_la_passe_dv_reste_sur_la_carte():
    """21 s → 13,5 s pour 60 s de 4K DV 8.1, flux identique bit à bit."""
    cmd = _passe_dv(_nvidia())
    assert _apres(cmd, "-hwaccel") == "cuda"
    assert _apres(cmd, "-hwaccel_output_format") == "cuda"
    assert "-pix_fmt" not in cmd
    assert "-vf" not in cmd
    assert _apres(cmd, "-profile:v") == "main10"


@pytest.mark.parametrize("plat,pix_fmt", [
    (_nvidia(None), "yuv420p10le"),                      # pas de sondage
    (_nvidia(frozenset({"hevc_nvenc"})), "yuv420p10le"), # avant Pascal
    (_nvidia(), ""),                                     # format inconnu
])
def test_la_passe_dv_garde_sinon_son_chemin(plat, pix_fmt):
    cmd = _passe_dv(plat, pix_fmt)
    assert "-hwaccel_output_format" not in cmd
    assert _apres(cmd, "-pix_fmt") == "p010le"
