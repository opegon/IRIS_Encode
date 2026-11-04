"""
tests/test_comparaison_sr.py — Extrait de comparaison une passe / deux passes (IE-172).

Note `conception_upscaling_2026-11-03.md` D17 : avant d'encoder un fichier en
deux passes, un extrait en écran partagé — la même bande centrale de l'image,
une passe à gauche, deux passes à droite — encodé comme le fichier final.
La touche K du Dry run passe par le smoke test.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from core import decision, dovi, preview, super_resolution as sr
from core.decision import decide, decide_video
from core.encoder import (build_comparaison_command, comparaison_output_path,
                          fenetre_comparaison)
from core.platform import GPU, OS, PlatformProfile
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo

FF_DV  = "C:/iris/bin/dv/ffmpeg.exe"
SHADER = Path("C:/iris/bin/shaders/ArtCNN_C4F16.glsl")

_INTEL = PlatformProfile(os=OS.WINDOWS, gpu=GPU.INTEL, hwaccel="d3d11va",
                         encoder_hevc="hevc_qsv", encoder_h264="h264_qsv",
                         encoder_av1="av1_qsv",
                         encodeurs_ok=frozenset({"hevc_qsv", "h264_qsv"}))


@pytest.fixture(autouse=True)
def outils():
    decision._FACTEURS_CACHE = (1.2, 2.7)
    dovi.set_ffmpeg_dv(FF_DV)
    sr.set_shader(SHADER)
    sr._essais[(FF_DV, str(SHADER))] = None
    yield
    sr._essais.clear()


def _decision(tmp_path: Path, w=720, h=400, duree=6000.0, passes=2):
    p = tmp_path / "Cactus Jack.mkv"
    p.write_bytes(b"")
    info = VideoInfo(path=p, width=w, height=h, bitrate=1_200_000, codec="h264",
                     duration=duree, frame_count=0, dv_profile=None, sar="1:1",
                     frame_rate="25/1", pix_fmt="yuv420p",
                     audio_tracks=[AudioTrack(index=0, codec="ac3", channels=2,
                                              language="fre", title="",
                                              bitrate=192_000)])
    profil = Profile(id="test", data={
        "bitrate_4k_kbps": 12000, "bitrate_1080p_kbps": 3000,
        "bitrate_720p_kbps": 1500, "bitrate_480p_kbps": 1500, "keep_4k": False,
        "dolby_vision": "sdr", "preset_encoder": "medium",
        "audio_languages": ["fre"]})
    dec = decide(info, profil)
    return replace(dec, video=decide_video(info, profil, agrandir=True,
                                           passes=passes))


def _graphe(cmd: list[str]) -> str:
    return cmd[cmd.index("-filter_complex") + 1]


@pytest.mark.parametrize("duree, attendu", [
    (6000.0, (1500.0, 120.0)),      # au quart du film
    (150.0,  (30.0, 120.0)),        # le quart laisserait moins de deux minutes
    (90.0,   (0.0, 90.0)),          # plus court que l'extrait : tout le fichier
])
def test_fenetre(duree, attendu):
    assert fenetre_comparaison(duree) == attendu


def test_meme_zone_une_passe_a_gauche(tmp_path):
    dec = _decision(tmp_path)
    assert dec.video.upscale is not None
    graphe = _graphe(build_comparaison_command(dec, _INTEL, tmp_path / "x.mkv"))
    chaines = graphe.split(";")
    assert chaines[0].startswith("[0:v]setparams=") and chaines[0].endswith(
        "split=2[a][b]")
    gauche, droite = chaines[1], chaines[2]
    # Une passe : un seul libplacebo ; deux passes : ×2, ×2, puis réduction.
    assert gauche.startswith("[a]") and gauche.count("libplacebo=") == 1
    assert droite.startswith("[b]") and droite.count("libplacebo=") == 3
    assert "w=1440:h=800" in droite and "w=2880:h=1600" in droite
    # La même bande centrale des deux côtés : la moitié du cadre 1920×1066.
    coupe = "crop=960:1066:480:0"
    assert gauche.endswith(f"{coupe}[g]") and droite.endswith(f"{coupe}[d]")
    assert chaines[3] == "[g][d]hstack=inputs=2,setsar=1[v]"


def test_le_nombre_de_passes_de_la_ligne_est_ignore(tmp_path):
    une = build_comparaison_command(_decision(tmp_path, passes=1), _INTEL,
                                    tmp_path / "x.mkv")
    deux = build_comparaison_command(_decision(tmp_path, passes=2), _INTEL,
                                     tmp_path / "x.mkv")
    assert une == deux


def test_encode_comme_le_fichier_final(tmp_path):
    dec = _decision(tmp_path)
    sortie = tmp_path / "x.mkv"
    cmd = build_comparaison_command(dec, _INTEL, sortie)
    assert cmd[0] == FF_DV and cmd[cmd.index("-init_hw_device") + 1] == "vulkan"
    assert "-hwaccel" not in cmd
    assert cmd[cmd.index("-c:v") + 1] == "hevc_qsv"
    assert cmd[cmd.index("-b:v") + 1] == "3000000"          # débit 1080p
    assert cmd[cmd.index("-ss") + 1] == "1500.000"
    assert cmd[cmd.index("-t") + 1] == "120.000"
    assert cmd.index("-ss") < cmd.index("-i") < cmd.index("-t")
    assert ["-map", "[v]", "-map", "0:a:0?"] == cmd[cmd.index("-map"):
                                                    cmd.index("-map") + 4]
    assert cmd[cmd.index("-c:a") + 1] == "copy"
    assert cmd[-1] == str(sortie)


def test_sortie_hors_du_dossier_du_film(tmp_path):
    out = comparaison_output_path(tmp_path / "Film.mkv")
    assert out.parent != tmp_path and out.name == "Film_[comparaison].mkv"


def test_mpv_etiquette_les_deux_cotes(monkeypatch):
    vu = []
    monkeypatch.setattr(preview, "launch", lambda cmd: vu.append(cmd))
    preview.set_mpv_path("mpv")
    try:
        preview.open_file(Path("x.mkv"), osd="◀ un  ·  deux ▶")
        preview.open_file(Path("y.mkv"))
    finally:
        preview.set_mpv_path(None)
    assert vu[0] == ["mpv", "--osd-level=1", "--osd-msg1=◀ un  ·  deux ▶", "x.mkv"]
    assert vu[1] == ["mpv", "--osd-level=1", "y.mkv"]
