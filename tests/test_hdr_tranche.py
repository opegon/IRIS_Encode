"""
tests/test_hdr_tranche.py — Une source HDR sous la tranche 1080p (IE-189).

**CR-118** (revue du 2026-11-13) : la décision automatique choisissait H264
pour toute cible sous 1080p, HDR compris — `libx264 -pix_fmt yuv420p`, courbe
PQ gardée en 8 bits, sans conversion ni avertissement. Le forçage et le choix
manuel, eux, ne laissent jamais de HDR en H264. Une seule règle désormais :
une sortie HDR est en HEVC, quelle que soit la tranche.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.decision import DVAction, VideoAction, decide
from core.encoder import build_command
from core.platform import GPU, OS, PlatformProfile
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo


def _profile(**over) -> Profile:
    data = {
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps": 12000, "keep_4k": False,
        "audio_languages": ["fre", "eng"], "audio_copy_compatible": True,
        "preserve_hd_audio": False, "dolby_vision": "hdr10",
    }
    data.update(over)
    return Profile(id="test", data=data)


def _source(tmp_path: Path, transfert: str = "", dv=None) -> VideoInfo:
    p = tmp_path / "Clip.mkv"
    p.write_bytes(b"")
    return VideoInfo(
        path=p, width=1280, height=720, bitrate=8_000_000, codec="hevc",
        duration=60.0, frame_count=0, dv_profile=dv, color_transfer=transfert,
        audio_tracks=[AudioTrack(index=0, codec="aac", channels=2,
                                 language="fre", title="", bitrate=128_000)],
    )


@pytest.mark.parametrize("transfert", ["smpte2084", "arib-std-b67"])
def test_un_720p_hdr_reste_en_hevc(tmp_path, transfert):
    vid = decide(_source(tmp_path, transfert), _profile()).video
    assert vid.action == VideoAction.ENCODE_HEVC
    assert vid.dv_action != DVAction.SDR


def test_jamais_de_hdr_en_h264(tmp_path):
    vid = decide(_source(tmp_path, "smpte2084"), _profile()).video
    assert not (vid.action == VideoAction.ENCODE_H264
                and vid.dv_action != DVAction.SDR)


def test_la_sortie_d_un_720p_hdr10_est_en_10_bits(tmp_path):
    plat = PlatformProfile(os=OS.WINDOWS, gpu=GPU.NONE, hwaccel=None,
                           encoder_hevc="libx265", encoder_h264="libx264",
                           encoder_av1="libaom-av1")
    cmd = build_command(decide(_source(tmp_path, "smpte2084"), _profile()), plat)
    assert "libx264" not in cmd
    assert "yuv420p10le" in cmd


def test_un_720p_sdr_reste_en_h264(tmp_path):
    vid = decide(_source(tmp_path), _profile()).video
    assert vid.action == VideoAction.ENCODE_H264


def test_un_dolby_vision_ramené_en_sdr_peut_sortir_en_h264(tmp_path):
    """La sortie n'est plus HDR : H264 la porte."""
    vid = decide(_source(tmp_path, "smpte2084", dv=8),
                 _profile(dolby_vision="sdr")).video
    assert vid.dv_action == DVAction.SDR
    assert vid.action == VideoAction.ENCODE_H264
