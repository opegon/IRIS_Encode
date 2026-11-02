"""
tests/test_audio_flac_pcm.py — FLAC et PCM sont sans perte.

Un concert en FLAC 5.1, profil `preserve_hd_audio = true`, ressortait en
AC3 640 kb/s : seuls TrueHD, MLP et DTS-HD MA comptaient comme sans perte, et
le FLAC n'est pas non plus un codec « compatible » recopié d'office.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.decision import AudioAction, _needs_mkv_codec, decide
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo


def _profile(**over) -> Profile:
    data = {
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 2500,
        "bitrate_4k_kbps": 5000, "keep_4k": True, "dolby_vision": "hdr10",
        "audio_languages": ["fre", "eng"], "audio_copy_compatible": True,
        "preserve_hd_audio": True, "audio_hd_codec": "none",
        "audio_stereo_kbps": 320, "audio_surround_kbps": 640,
        "container": "auto",
    }
    data.update(over)
    return Profile(id="test", data=data)


def _piste(codec: str, canaux: int) -> AudioTrack:
    return AudioTrack(index=0, codec=codec, channels=canaux, language="eng",
                      title="", bitrate=0)


def _source(tmp_path: Path, piste: AudioTrack) -> VideoInfo:
    p = tmp_path / "Concert.1080p.mkv"
    p.write_bytes(b"")
    return VideoInfo(path=p, width=1920, height=1080, bitrate=20_000_000,
                     codec="h264", duration=5400.0, frame_count=0,
                     dv_profile=None, audio_tracks=[piste])


@pytest.mark.parametrize("codec,sans_perte", [
    ("flac", True), ("pcm_s16le", True), ("pcm_s24le", True),
    ("pcm_bluray", True), ("pcm_dvd", True),
    ("aac", False), ("ac3", False), ("eac3", False), ("opus", False),
])
def test_flac_et_pcm_sont_sans_perte(codec, sans_perte):
    assert _piste(codec, 2).is_lossless is sans_perte


@pytest.mark.parametrize("codec", ["flac", "pcm_s24le"])
@pytest.mark.parametrize("canaux", [2, 6])
def test_preserve_hd_audio_recopie_en_mkv(tmp_path, codec, canaux):
    dec = decide(_source(tmp_path, _piste(codec, canaux)), _profile())
    assert dec.audio[0].action == AudioAction.COPY
    assert dec.output_container == ".mkv"


def test_sans_preserve_le_flac_reste_transcode(tmp_path):
    dec = decide(_source(tmp_path, _piste("flac", 6)),
                 _profile(preserve_hd_audio=False))
    assert dec.audio[0].action == AudioAction.TRANSCODE
    assert dec.audio[0].output_codec == "ac3"


@pytest.mark.parametrize("codec", ["FLAC", "A_FLAC", "A_PCM/INT/LIT", "pcm_s16le"])
def test_une_piste_greffee_flac_ou_pcm_impose_le_mkv(codec):
    assert _needs_mkv_codec(codec)
