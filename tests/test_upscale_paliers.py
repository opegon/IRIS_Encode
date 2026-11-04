"""
tests/test_upscale_paliers.py — Règle de décision de la super-résolution (IE-167).

Note `conception_upscaling_2026-11-03.md` § 2 : la source va au plus haut
palier (480p, 720p, 1080p) qu'elle atteint sans dépasser ×2,7 (D22), zone
morte sous ×1,2 (D5), dimensions en pixels carrés (D4), débit du palier
atteint (D9). Les vecteurs sont ceux du § 2.2.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core import decision, dovi
from core.decision import (DVAction, VideoAction, _decide_video_classique,
                           decide_video, palier_cible)
from core.encoder import dimensions_reduites
from core.profiles import Profile
from core.scanner import VideoInfo

FF_DV = "C:/iris/bin/dv/ffmpeg.exe"


@pytest.fixture(autouse=True)
def facteurs_par_defaut():
    """La règle ne dépend pas du config.toml du poste."""
    decision._FACTEURS_CACHE = (1.2, 2.7)
    dovi.set_ffmpeg_dv(FF_DV)


def _profil(**over) -> Profile:
    data = {"bitrate_4k_kbps": 12000, "bitrate_1080p_kbps": 2500,
            "bitrate_720p_kbps": 1500, "bitrate_480p_kbps": 900,
            "keep_4k": False, "dolby_vision": "sdr", "preset_encoder": "medium",
            "audio_languages": ["fre"], "upscale": True}
    data.update(over)
    return Profile(id="test", data=data)


def _info(w: int, h: int, sar: str = "", bitrate: int = 1_200_000,
          codec: str = "h264", **over) -> VideoInfo:
    return VideoInfo(path=Path(f"C:/films/source_{w}x{h}.mkv"), width=w, height=h,
                     bitrate=bitrate, codec=codec, duration=600.0, frame_count=15000,
                     dv_profile=None, sar=sar, **over)


# ─── La règle seule (§ 2.2) ───────────────────────────────────────────────────

# (source stockée, SAR, palier, facteur, agrandie, sortie attendue)
VECTEURS = [
    ((160, 120),  "",      480,  4.0,   False, (160, 120)),   # trop petite
    ((240, 180),  "",      480,  2.667, True,  (640, 480)),
    ((320, 240),  "",      480,  2.0,   True,  (640, 480)),
    ((426, 240),  "",      480,  2.0,   True,  (852, 480)),
    ((480, 360),  "",      720,  2.0,   True,  (960, 720)),
    ((640, 360),  "",      720,  2.0,   True,  (1280, 720)),  # 1080p : ×3,0
    ((720, 400),  "1:1",   1080, 2.667, True,  (1920, 1066)), # Cactus Jack
    ((640, 480),  "",      1080, 2.25,  True,  (1440, 1080)),
    ((854, 480),  "",      1080, 2.248, True,  (1920, 1080)),
    ((720, 480),  "8:9",   1080, 2.25,  True,  (1440, 1080)), # DVD NTSC 4:3
    ((720, 480),  "32:27", 1080, 2.25,  True,  (1920, 1080)), # DVD NTSC 16:9
    ((720, 576),  "16:15", 1080, 1.875, True,  (1440, 1080)), # DVD PAL 4:3
    ((720, 576),  "64:45", 1080, 1.875, True,  (1920, 1080)), # DVD PAL 16:9
    ((960, 540),  "",      1080, 2.0,   True,  (1920, 1080)),
    ((1100, 620), "",      1080, 1.742, True,  (1916, 1080)),
    ((1280, 720), "",      1080, 1.5,   True,  (1920, 1080)),
    ((1280, 536), "",      1080, 1.5,   True,  (1920, 804)),
    ((1440, 850), "",      1080, 1.271, True,  (1830, 1080)),
    ((1600, 900), "",      1080, 1.2,   True,  (1920, 1080)), # borne incluse
    ((1700, 960), "",      1080, 1.125, False, (1700, 960)),  # zone morte
]


@pytest.mark.parametrize("source,sar,palier,facteur,agrandie,sortie", VECTEURS,
                         ids=[f"{s[0]}x{s[1]}{'_' + sar if sar else ''}"
                              for s, sar, *_ in VECTEURS])
def test_vecteurs_du_tableau(source, sar, palier, facteur, agrandie, sortie):
    info = _info(*source, sar=sar)
    c = palier_cible(info.largeur_affichee, info.height, 1.2, 2.7)
    assert (c.palier, round(c.facteur, 3), c.agrandir) == (palier, facteur, agrandie)
    if agrandie:
        assert dimensions_reduites(info.largeur_affichee, info.height,
                                   c.largeur, c.hauteur) == sortie


@pytest.mark.parametrize("source", [(1920, 800), (1440, 1080), (1920, 1080),
                                    (3840, 2160)])
def test_source_qui_touche_le_cadre_1080p_hors_regle(source):
    assert palier_cible(*source, 1.2, 2.7) is None


def test_borne_du_plafond_incluse():
    # 710×400 → 1080p : f = min(2,704 ; 2,7) = 2,7 tout juste.
    assert palier_cible(710, 400, 1.2, 2.7).palier == 1080
    assert palier_cible(700, 390, 1.2, 2.7).palier == 720


def test_deux_passes_vont_au_cadre_1080p_sans_plafond():
    # D15 : 640×360 irait en 720p en une passe ; en deux, en 1080p (×3,0).
    c = palier_cible(640, 360, 1.2, 2.7, passes=2)
    assert (c.palier, round(c.facteur, 2), c.agrandir) == (1080, 3.0, True)
    # La zone morte, elle, vaut toujours.
    assert not palier_cible(1700, 960, 1.2, 2.7, passes=2).agrandir


# ─── Les trois fichiers d'essai de l'utilisateur (note § 10.9) ───────────────

@pytest.mark.parametrize("nom,w,h,sar,sortie", [
    ("Cactus Jack (DVDRip)",     720, 400, "1:1", (1920, 1066)),
    ("The Kid (AVI, SAR perdu)", 720, 480, "",    (1620, 1080)),
    ("Le Monde du silence",      704, 528, "1:1", (1440, 1080)),
])
def test_fichiers_reels(nom, w, h, sar, sortie):
    v = decide_video(_info(w, h, sar=sar, codec="mpeg4"), _profil())
    assert v.action == VideoAction.ENCODE_HEVC, nom
    assert (v.target_width, v.target_height) == sortie, nom
    assert v.target_bitrate == 2_500_000, nom


# ─── decide_video ─────────────────────────────────────────────────────────────

def test_dvd_agrandi_en_1080p():
    v = decide_video(_info(720, 576, sar="64:45"), _profil())
    assert v.action == VideoAction.ENCODE_HEVC
    assert (v.target_width, v.target_height) == (1920, 1080)
    assert v.target_bitrate == 2_500_000          # débit du palier atteint (D9)
    assert v.dv_action == DVAction.NONE
    assert v.upscale == decision.Agrandissement(1080, 1.875, 1)
    assert v.label() == "→ HEVC ↑1080p"
    assert "720x576 → 1920x1080" in v.reason and "1.88" in v.reason


def test_360p_en_720p_reste_en_h264():
    v = decide_video(_info(640, 360), _profil())
    assert v.action == VideoAction.ENCODE_H264
    assert v.target_bitrate == 1_500_000
    assert v.label() == "→ H264 ↑720p"


def test_240p_en_480p_au_debit_480p():
    v = decide_video(_info(320, 240), _profil())
    assert (v.action, v.target_bitrate) == (VideoAction.ENCODE_H264, 900_000)
    assert (v.target_width, v.target_height) == (640, 480)


def test_deux_passes_par_le_profil():
    v = decide_video(_info(640, 360), _profil(upscale_passes=2))
    assert (v.target_width, v.target_height) == (1920, 1080)
    assert v.label() == "→ HEVC ↑1080p ×2"


def test_profil_sans_agrandissement_inchange():
    info = _info(720, 576, sar="64:45")
    assert decide_video(info, _profil(upscale=False)) == \
        _decide_video_classique(info, _profil(upscale=False))
    sans_cle = _profil()
    del sans_cle.data["upscale"]
    assert decide_video(info, sans_cle).upscale is None


def test_choix_par_fichier_dans_les_deux_sens():
    info = _info(720, 576, sar="64:45")
    # D23 : demandé sur un profil qui n'agrandit pas…
    assert decide_video(info, _profil(upscale=False), agrandir=True).upscale is not None
    # … ou coupé sur un profil qui agrandit.
    assert decide_video(info, _profil(), agrandir=False).upscale is None
    # D24 : deux passes pour ce seul fichier.
    assert decide_video(info, _profil(), passes=2).upscale.passes == 2


def test_zone_morte_garde_la_definition_en_tranche_1080p():
    # 1500×800 : rabattu en 720p par les seuils classiques ; la règle l'agrandit.
    assert decide_video(_info(1500, 800), _profil()).upscale is not None
    v = decide_video(_info(1700, 960, bitrate=6_000_000), _profil())
    assert v.upscale is None
    assert (v.target_width, v.target_height, v.target_bitrate) == (1700, 960, 2_500_000)


def test_source_trop_petite_reste_native_en_tranche_480p():
    v = decide_video(_info(160, 120, bitrate=3_000_000), _profil())
    assert v.upscale is None
    assert (v.target_width, v.target_height, v.target_bitrate) == (160, 120, 900_000)


def test_sans_libplacebo_pas_de_repli():
    dovi.set_ffmpeg_dv(None)
    info = _info(720, 576, sar="64:45")
    v = decide_video(info, _profil())
    assert v.upscale is None
    assert v.action == _decide_video_classique(info, _profil()).action
    assert "libplacebo" in v.reason


def test_source_hdr_exclue():
    v = decide_video(_info(1280, 720, codec="hevc", color_transfer="smpte2084"),
                     _profil())
    assert v.upscale is None
    assert "HDR" in v.reason


def test_source_4k_hors_regle():
    info = _info(3840, 2160, bitrate=20_000_000, codec="hevc")
    assert decide_video(info, _profil()) == _decide_video_classique(info, _profil())
