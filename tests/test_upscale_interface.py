"""
tests/test_upscale_interface.py — Super-résolution : profil, nommage, durée (IE-169).

Note `conception_upscaling_2026-11-03.md` D21 (marque `upscaled`), D23 et D24
(clés de profil, un seul choix dans le formulaire), D25 (affichage, durée
estimée). Le choix par fichier du Dry run (U) passe par le smoke test.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core import decision, dovi, super_resolution as sr
from core.decision import decide
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo, stem_agrandi
from tui.common import cellules_profil
from tui.widgets.profile_form import _agrandir_cles, _agrandir_depuis_cles

FF_DV  = "C:/iris/bin/dv/ffmpeg.exe"
SHADER = Path("C:/iris/bin/shaders/ArtCNN_C4F16.glsl")


@pytest.fixture(autouse=True)
def outils():
    decision._FACTEURS_CACHE = (1.2, 2.7)
    dovi.set_ffmpeg_dv(FF_DV)
    sr.set_shader(SHADER)
    sr._essais[(FF_DV, str(SHADER))] = None
    yield
    sr._essais.clear()


def _profil(**over) -> Profile:
    data = {"bitrate_4k_kbps": 12000, "bitrate_1080p_kbps": 3000,
            "bitrate_720p_kbps": 1500, "bitrate_480p_kbps": 1500,
            "keep_4k": False, "dolby_vision": "sdr", "preset_encoder": "medium",
            "audio_languages": ["fre"], "upscale": True}
    data.update(over)
    return Profile(id="test", data=data)


def _info(tmp_path: Path, nom: str, w: int, h: int, **over) -> VideoInfo:
    p = tmp_path / nom
    p.write_bytes(b"")
    champs = {"bitrate": 1_200_000, "codec": "h264", "duration": 600.0,
              "frame_count": 15000, "dv_profile": None, "sar": "1:1",
              "frame_rate": "25/1", "pix_fmt": "yuv420p",
              "audio_tracks": [AudioTrack(index=0, codec="aac", channels=2,
                                          language="fre", title="",
                                          bitrate=128_000)]}
    return VideoInfo(path=p, width=w, height=h, **{**champs, **over})


# ─── Nommage (D21) ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("stem, attendu", [
    ("Film.720p.BluRay.x264", "Film.1080p.upscaled.BluRay.x264"),
    ("Serie.S01E01.576i.DVB", "Serie.S01E01.1080p.upscaled.DVB"),
    ("Film [480p] VF",        "Film [1080p upscaled] VF"),
    ("Film 720p BluRay",      "Film 1080p upscaled BluRay"),
    # Sans marque de définition : elle s'ajoute à la fin.
    ("CactusJack_720x400",    "CactusJack_720x400.1080p.upscaled"),
    ("Cactus Jack",           "Cactus Jack 1080p upscaled"),
    # Déjà agrandie une fois : la marque ne se répète pas.
    ("Film.480p.upscaled",    "Film.1080p.upscaled"),
])
def test_marque_upscaled(stem, attendu):
    assert stem_agrandi(stem, 1080) == attendu


def test_nom_de_sortie_d_un_fichier_agrandi(tmp_path):
    dec = decide(_info(tmp_path, "Film.720p.BluRay.x264-GRP.mkv", 1280, 720),
                 _profil())
    assert dec.video.upscale is not None
    assert dec.output_path.name == "Film.1080p.upscaled.BluRay.hevc-iris.mp4"


def test_nom_inchange_sans_agrandissement(tmp_path):
    dec = decide(_info(tmp_path, "Film.720p.BluRay.x264-GRP.mkv", 1280, 720,
                       bitrate=4_000_000), _profil(upscale=False))
    assert dec.video.upscale is None
    assert "720p" in dec.output_path.name
    assert "upscaled" not in dec.output_path.name


# ─── Profil (D23, D24) ────────────────────────────────────────────────────────

@pytest.mark.parametrize("choix, cles", [
    ("off", {"upscale": False, "upscale_passes": 1}),
    ("1",   {"upscale": True,  "upscale_passes": 1}),
    ("2",   {"upscale": True,  "upscale_passes": 2}),
])
def test_un_choix_pour_deux_cles(choix, cles):
    assert _agrandir_cles(choix) == cles
    assert _agrandir_depuis_cles(cles["upscale"], cles["upscale_passes"]) == choix


def test_deux_passes_sans_agrandissement_se_lit_non():
    """Une clé `upscale_passes = 2` posée à la main sur un profil qui
    n'agrandit pas ne vaut rien : le formulaire montre « non »."""
    assert _agrandir_depuis_cles(False, 2) == "off"


@pytest.mark.parametrize("data, attendu, terne", [
    ({}, "—", True),
    ({"upscale": True}, "↑", False),
    ({"upscale": True, "upscale_passes": 2}, "↑ ×2", False),
])
def test_colonne_agrandissement_des_profils(data, attendu, terne):
    cellule = cellules_profil("p", Profile(id="p", data=data), False)[5]
    assert cellule.plain == attendu
    assert ("dim" in str(cellule.style)) is terne


# ─── Durée estimée (D25) ──────────────────────────────────────────────────────

def test_duree_de_l_agrandissement(tmp_path):
    # Film de 2 h à 24 i/s : 172 800 images.
    info = _info(tmp_path, "f.mkv", 720, 400, frame_count=0)
    info.duration, info.frame_rate = 7200.0, "24/1"
    # Deux passes sur l'iGPU Intel : 9,3 i/s, environ 5 h 10.
    assert sr.duree_agrandissement(info, 2, "intel") == pytest.approx(172800 / 9.3)
    assert sr.duree_agrandissement(info, 1, "nvidia") == pytest.approx(172800 / 161)
    # Carte non mesurée : les chiffres de l'iGPU, l'estimation la plus longue.
    assert sr.duree_agrandissement(info, 1, "amd") == pytest.approx(172800 / 38.2)
    info.frame_count = 1000
    assert sr.duree_agrandissement(info, 1, "intel") == pytest.approx(1000 / 38.2)
