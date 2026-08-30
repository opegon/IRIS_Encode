"""
tests/test_dv_reencodage.py — Réencoder sans perdre le Dolby Vision.

Le RPU vit *à l'intérieur* du flux HEVC, entre les tranches d'image : tout
réencodage le détruit. Conserver le DV imposait donc de recopier la vidéo, et
le débit cible du profil restait lettre morte — un film de 60 Mb/s ressortait
à 60 Mb/s.

`ENCODE_DV` sort le RPU avant l'encodage et le réinjecte après. Ce que ces
tests verrouillent est surtout **quand on s'y refuse** : le RPU est indexé
image par image, et l'injecter dans un flux qui n'a pas le même compte, ou
dont la couche de base n'est pas du HDR10, rend un fichier faux.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core import decision as D
from core.decision import (SUFFIX_DV_COPIE, DVAction, VideoAction, decide,
                           peut_reencoder_en_dv, video_recopiee)
from core.encoder import build_dv_video_command
from core.platform import GPU, OS, PlatformProfile
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo

_PLAT = PlatformProfile(os=OS.WINDOWS, gpu=GPU.NVIDIA, hwaccel="cuda",
                        encoder_hevc="hevc_nvenc", encoder_h264="h264_nvenc",
                        encoder_av1="av1_nvenc")


@pytest.fixture(autouse=True)
def outils_presents():
    """dovi_tool et mkvmerge sont là — sauf mention contraire d'un test."""
    D.set_strip_dv_available(True)
    yield
    D.set_strip_dv_available(False)


def _profil(**over) -> Profile:
    data = {"bitrate_4k_kbps": 12000, "bitrate_1080p_kbps": 5000,
            "bitrate_720p_kbps": 3000, "keep_4k": True,
            "dolby_vision": "dv", "preset_encoder": "slow"}
    data.update(over)
    return Profile(id="dv", data=data)


def _source(dv_profile=8, bl_compat=1, w=3840, h=2160,
            bitrate=60_000_000) -> VideoInfo:
    return VideoInfo(
        path=Path("Film.mkv"), width=w, height=h, bitrate=bitrate,
        codec="hevc", duration=7200.0, frame_count=0,
        dv_profile=dv_profile, dv_bl_compat=bl_compat,
        audio_tracks=[AudioTrack(index=0, codec="ac3", channels=6,
                                 language="fre", title="", bitrate=640_000)],
    )


# ─── Quand le réencodage DV est retenu ───────────────────────────────────────

@pytest.mark.parametrize("dv_profile,bl_compat", [(8, 1), (7, 0)])
def test_les_profils_a_couche_de_base_hdr10_sont_reencodes(dv_profile, bl_compat):
    """8.1 directement, 7 après conversion de son RPU en 8.1."""
    v = decide(_source(dv_profile, bl_compat), _profil()).video
    assert v.action is VideoAction.ENCODE_DV


def test_le_debit_cible_s_applique_vraiment():
    v = decide(_source(), _profil()).video
    assert v.target_bitrate == 12_000_000
    assert not video_recopiee(v.action, v.dv_action)


def test_l_ecran_annonce_un_encodage_hevc_qui_garde_le_dv():
    v = decide(_source(), _profil()).video
    assert v.label() == "→ HEVC → DV"
    assert "RPU réinjecté" in v.reason


def test_la_sortie_porte_le_suffixe_dv():
    d = decide(_source(), _profil())
    assert d.output_path.name == f"Film{SUFFIX_DV_COPIE}.mkv"


# ─── Quand on s'y refuse ─────────────────────────────────────────────────────

@pytest.mark.parametrize("dv_profile,bl_compat,pourquoi", [
    (5, 0, "couche de base IPT-PQ, pas du HDR10"),
    (8, 4, "couche de base HLG"),
    (8, 2, "couche de base SDR"),
])
def test_sans_couche_de_base_hdr10_on_recopie(dv_profile, bl_compat, pourquoi):
    """Réinjecter ce RPU dans un flux HDR10 donnerait des couleurs fausses."""
    v = decide(_source(dv_profile, bl_compat), _profil()).video
    assert v.action is VideoAction.ENCODE_HEVC, pourquoi
    assert video_recopiee(v.action, v.dv_action)
    assert v.label() == "→ DV (copie)"


def test_un_redimensionnement_interdit_la_reinjection():
    """Le RPU est indexé image par image et décrit un cadrage."""
    v = decide(_source(), _profil(keep_4k=False)).video
    assert v.action is VideoAction.ENCODE_HEVC
    assert v.label() == "→ DV (copie)"


def test_sans_dovi_tool_on_recopie():
    D.set_strip_dv_available(False)
    v = decide(_source(), _profil()).video
    assert v.action is VideoAction.ENCODE_HEVC


def test_le_predicat_exige_les_dimensions_exactes():
    info = _source()
    assert peut_reencoder_en_dv(info, 3840, 2160)
    assert not peut_reencoder_en_dv(info, 1920, 1080)
    assert not peut_reencoder_en_dv(info, 3840, 2159)


def test_sous_le_plafond_rien_n_est_reencode():
    v = decide(_source(bitrate=8_000_000), _profil()).video
    assert v.action is VideoAction.SKIP


# ─── Le conteneur ────────────────────────────────────────────────────────────

def test_le_matroska_est_impose_meme_si_le_profil_veut_du_mp4():
    """Le remux passe par mkvmerge, qui n'écrit que du Matroska.

    Un MP4 obtenu autrement perdrait le RPU — soit exactement ce que
    l'opération cherche à préserver.
    """
    d = decide(_source(), _profil(container="mp4"))
    assert d.video.action is VideoAction.ENCODE_DV
    assert d.output_container == ".mkv"


# ─── La commande d'encodage ──────────────────────────────────────────────────

def test_la_passe_video_ne_porte_aucun_filtre():
    """Un filtre changerait le nombre d'images, et le RPU ne collerait plus."""
    cmd = build_dv_video_command(decide(_source(), _profil()), _PLAT,
                                 Path("t.hevc"), "ffmpeg")
    assert "-vf" not in cmd
    assert "-filter:v" not in cmd


def test_la_passe_video_sort_du_annexb_10_bits_au_debit_cible():
    cmd = build_dv_video_command(decide(_source(), _profil()), _PLAT,
                                 Path("t.hevc"), "ffmpeg")
    assert cmd[cmd.index("-f") + 1] == "hevc"
    assert cmd[cmd.index("-c:v") + 1] == "hevc_nvenc"
    assert cmd[cmd.index("-pix_fmt") + 1] == "p010le"
    assert cmd[cmd.index("-b:v") + 1] == "12000000"
    assert cmd[cmd.index("-profile:v") + 1] == "main10"
    assert cmd[-1] == "t.hevc"


def test_la_passe_video_ne_mappe_que_la_video():
    cmd = build_dv_video_command(decide(_source(), _profil()), _PLAT,
                                 Path("t.hevc"), "ffmpeg")
    assert [cmd[i + 1] for i, a in enumerate(cmd) if a == "-map"] == ["0:v:0"]


def test_libx265_recoit_son_propre_format_de_pixels():
    """`p010le` est le format de NVENC ; libx265 veut `yuv420p10le`."""
    cpu = PlatformProfile(os=OS.LINUX, gpu=GPU.NONE, hwaccel="",
                          encoder_hevc="libx265", encoder_h264="libx264",
                          encoder_av1="libaom-av1")
    cmd = build_dv_video_command(decide(_source(), _profil()), cpu,
                                 Path("t.hevc"), "ffmpeg")
    assert cmd[cmd.index("-pix_fmt") + 1] == "yuv420p10le"
    assert "-hwaccel" not in cmd


# ─── L'écran des pistes ──────────────────────────────────────────────────────

def test_encode_dv_se_range_avec_hevc_et_non_avec_skip():
    """Se ranger avec SKIP aurait fait proposer « ne pas réencoder »."""
    assert (D.cycle_index(VideoAction.ENCODE_DV)
            == D.cycle_index(VideoAction.ENCODE_HEVC))


def test_choisir_hevc_sur_une_decision_dv_ne_fait_pas_perdre_le_dv():
    assert D.same_intent(VideoAction.ENCODE_HEVC, VideoAction.ENCODE_DV)
    assert not D.same_intent(VideoAction.ENCODE_H264, VideoAction.ENCODE_DV)


def test_la_nouvelle_action_a_un_libelle_sur_l_ecran_des_pistes():
    from tui.screens.tracks import _ACTION_SHORT
    assert VideoAction.ENCODE_DV in _ACTION_SHORT
