"""
tests/test_fourcc_nul.py — Un AVI au fourcc nul porte du HEVC, pas de l'image brute.

Un AVI au fourcc nul : ffprobe y voit un flux
`rawvideo` 1920×1080 `bgr24` à 2,5 Mb/s. Le premier paquet commence pourtant
par `00 00 00 01 40 01` — un VPS HEVC. ffmpeg, sans décodeur imposé, n'en
sortait aucune image : « Conversion failed! ». Avec `-c:v hevc` avant `-i`,
l'encodage et la recopie passent (mesuré sous ffmpeg 8.1).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core import scanner
from core.decision import decide
from core.encoder import build_command, encodeur_de
from core.platform import GPU, OS, PlatformProfile
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo

PLAT = PlatformProfile(os=OS.WINDOWS, gpu=GPU.NONE, hwaccel=None, encoder_hevc="libx265",
                       encoder_h264="libx264", encoder_av1="libsvtav1")

# Début réel du premier paquet du fichier (dump de `ffprobe -show_data`).
_VPS_HEVC = ("\n00000000: 0000 0001 4001 0c01 ffff 0140 0000 0300  ....@......@....\n"
             "00000010: 9000 0003 0000 0300 7899 c090 0000 0001  ........x.......\n")
_SPS_H264 = "\n00000000: 0000 0001 6764 0028 acd9 4078 0227 e5c0  ....gd.(..@x.'..\n"
_BGR_BRUT = "\n00000000: 1a2b 3c4d 5e6f 7a8b 9cad becf d0e1 f2a3  .+<M^oz.........\n"


def _flux(monkeypatch, dump: str) -> None:
    def faux(args, outil=None):
        if "-show_packets" in args:
            return {"packets": [{"data": dump}]}
        return {"streams": [{"codec_type": "video", "codec_name": "rawvideo",
                             "codec_tag": "0x0000", "width": 1920, "height": 1080,
                             "pix_fmt": "bgr24", "bit_rate": "2567048",
                             "r_frame_rate": "2997/125"}],
                "format": {"duration": "6271.4", "bit_rate": "2803516"}}
    monkeypatch.setattr(scanner, "_ffprobe_json", faux)
    monkeypatch.setattr(scanner, "_detect_dv", lambda p: (None, None))


@pytest.mark.parametrize("dump, codec", [(_VPS_HEVC, "hevc"), (_SPS_H264, "h264"),
                                         (_BGR_BRUT, "")])
def test_le_premier_paquet_dit_le_codec(monkeypatch, dump, codec):
    _flux(monkeypatch, dump)
    assert scanner._codec_annexe_b(Path("concert.avi")) == codec


def test_le_scan_rend_le_codec_et_le_decodeur(monkeypatch):
    _flux(monkeypatch, _VPS_HEVC)
    info = scanner.scan(Path("concert.avi"))
    assert (info.codec, info.decodeur, info.pix_fmt) == ("hevc", "hevc", "")


def test_une_image_brute_reste_brute(monkeypatch):
    _flux(monkeypatch, _BGR_BRUT)
    info = scanner.scan(Path("concert.avi"))
    assert (info.codec, info.decodeur) == ("rawvideo", "")


def test_le_decodeur_precede_l_entree():
    info = VideoInfo(
        path=Path("/films/concert.avi"), width=1920, height=1080, bitrate=8_000_000,
        codec="hevc", duration=3600.0, frame_count=0, dv_profile=None,
        audio_tracks=[AudioTrack(index=0, codec="mp3", channels=2, language="eng",
                                 title="", bitrate=224_000)],
        decodeur="hevc",
    )
    prof = Profile(id="test", data={
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 2000,
        "bitrate_4k_kbps": 12000, "keep_4k": False,
        "audio_languages": ["eng"], "audio_copy_compatible": True,
    })
    cmd = build_command(decide(info, prof), PLAT)
    i = cmd.index("-i")
    assert cmd[i - 2:i] == ["-c:v", "hevc"]
    # L'encodeur reste celui de la sortie, pas le décodeur imposé.
    assert encodeur_de(cmd) == "libx265"
    assert "hvc1" in cmd
