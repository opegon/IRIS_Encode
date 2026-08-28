"""
tests/test_debit.py — Le débit demandé doit rester une cible, pas un plafond.

`-rc cbr` avec `-maxrate` égal à `-b:v` rend la cible inatteignable par
construction : NVENC ne dépense que ce que le contenu exige, et le plafond
interdit aux scènes difficiles de compenser les scènes faciles. La moyenne ne
peut donc que tomber sous la cible affichée à l'écran.

Mesuré le 2026-08-28 sur un extrait de 180 s de `Watchmen` 2160p 10 bits, cible
6 035k : 92 % avec les anciens réglages, 99 % en VBR avec 50 % de marge. Sur
`Mars Express` — animation, contenu plat — la marge ne change presque rien
(41 % → 54 %) : l'encodeur ne remplit pas un débit dont il n'a pas besoin, et
c'est le comportement voulu.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.decision import decide
from core.encoder import build_command
from core.platform import GPU, OS, PlatformProfile
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo


def _plat() -> PlatformProfile:
    return PlatformProfile(os=OS.WINDOWS, gpu=GPU.NVIDIA, hwaccel="cuda",
                           encoder_hevc="hevc_nvenc", encoder_h264="h264_nvenc",
                           encoder_av1="av1_nvenc")


def _info(tmp_path: Path, bitrate: int) -> VideoInfo:
    p = tmp_path / "film.mkv"
    p.write_bytes(b"")
    return VideoInfo(
        path=p, width=1920, height=1080, bitrate=bitrate, codec="hevc",
        duration=5400.0, frame_count=0, dv_profile=None,
        audio_tracks=[AudioTrack(index=0, codec="eac3", channels=6,
                                 language="fre", title="", bitrate=640_000)],
        subtitle_tracks=[],
    )


def _profile() -> Profile:
    return Profile(id="test", data={
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps": 8000, "audio_languages": ["fre", "eng"],
        "audio_copy_compatible": True, "preserve_hd_audio": False,
    })


def _valeur(cmd: list[str], option: str) -> str:
    return cmd[cmd.index(option) + 1]


def test_le_plafond_laisse_de_la_marge_au_dessus_de_la_cible(tmp_path):
    cmd    = build_command(decide(_info(tmp_path, 8_000_000), _profile()), _plat())
    cible  = int(_valeur(cmd, "-b:v"))
    maxrate = int(_valeur(cmd, "-maxrate"))
    assert cible == 5_000_000
    assert maxrate == cible * 3 // 2, "un plafond égal à la cible la rend inatteignable"


def test_le_tampon_couvre_le_plafond(tmp_path):
    cmd     = build_command(decide(_info(tmp_path, 8_000_000), _profile()), _plat())
    maxrate = int(_valeur(cmd, "-maxrate"))
    bufsize = int(_valeur(cmd, "-bufsize").rstrip("k")) * 1000
    assert bufsize >= maxrate, "un tampon plus petit que le plafond le rend inopérant"


def test_le_mode_est_vbr_pas_cbr(tmp_path):
    cmd = build_command(decide(_info(tmp_path, 8_000_000), _profile()), _plat())
    assert _valeur(cmd, "-rc") == "vbr"
