"""
tests/test_conversion_h264.py — Conversion H.264 → HEVC à débit dérivé de la
source (IE-202).

La décision comparait le débit de la source à la cible du profil sans regarder
le codec : un H.264 1080p à 5 000k avec une cible de 8 000k restait tel quel.
Un profil qui l'active (`convert_h264`) le convertit en HEVC à
`débit source × h264_to_hevc_ratio` (0,70 par défaut), à partir de
`h264_min_kbps` (2 500 par défaut), en 1080p et au-dessus seulement.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from core import profiles as prof_mod
from core.decision import VideoAction, decide
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo


def _profil(**extra) -> Profile:
    return Profile(id="essai", data={
        "bitrate_720p_kbps": 4000, "bitrate_1080p_kbps": 8000,
        "bitrate_4k_kbps": 8000, "keep_4k": False,
        "audio_languages": ["fre"], "audio_copy_compatible": True, **extra,
    })


def _converti(**extra) -> Profile:
    return _profil(convert_h264=True, **extra)


def _info(tmp_path: Path, codec: str = "h264", kbps: int = 5000,
          largeur: int = 1920, hauteur: int = 1080) -> VideoInfo:
    return VideoInfo(
        path=tmp_path / "Film.mkv", width=largeur, height=hauteur,
        bitrate=kbps * 1000, codec=codec, duration=600.0, frame_count=0,
        dv_profile=None,
        audio_tracks=[AudioTrack(index=0, codec="ac3", channels=6, language="fre",
                                 title="", bitrate=448_000)])


# ─── La décision ──────────────────────────────────────────────────────────────

def test_un_h264_sous_la_cible_est_converti_a_70_pourcents(tmp_path):
    v = decide(_info(tmp_path), _converti()).video
    assert v.action == VideoAction.ENCODE_HEVC
    assert v.target_bitrate == 3_500_000
    assert "5000k" in v.reason and "3500k" in v.reason and "70" in v.reason


def test_sans_l_option_rien_ne_change(tmp_path):
    assert decide(_info(tmp_path), _profil()).video.action == VideoAction.SKIP


def test_un_hevc_au_meme_debit_reste_tel_quel(tmp_path):
    v = decide(_info(tmp_path, codec="hevc"), _converti()).video
    assert v.action == VideoAction.SKIP


def test_un_h264_au_dessus_de_la_cible_reste_au_cas_1(tmp_path):
    v = decide(_info(tmp_path, kbps=12000), _converti()).video
    assert v.action == VideoAction.ENCODE_HEVC
    assert v.target_bitrate == 8_000_000


def test_sous_le_plancher_un_h264_reste_tel_quel(tmp_path):
    assert decide(_info(tmp_path, kbps=2400), _converti()).video.action \
        == VideoAction.SKIP
    assert decide(_info(tmp_path, kbps=2500), _converti()).video.action \
        == VideoAction.ENCODE_HEVC


def test_le_ratio_et_le_plancher_du_profil_s_appliquent(tmp_path):
    p = _converti(h264_to_hevc_ratio=0.6, h264_min_kbps=1500)
    v = decide(_info(tmp_path, kbps=2000), p).video
    assert v.target_bitrate == 1_200_000


def test_la_cible_ne_depasse_jamais_celle_du_profil(tmp_path):
    # 8 500k sous la cible + 10 % ; × 0,99 = 8 415k, ramené à 8 000k.
    p = _converti(h264_to_hevc_ratio=0.99)
    assert decide(_info(tmp_path, kbps=8500), p).video.target_bitrate == 8_000_000


def test_sous_1080p_le_h264_reste_la_sortie(tmp_path):
    v = decide(_info(tmp_path, kbps=3000, largeur=1280, hauteur=720), _converti()).video
    assert v.action == VideoAction.SKIP


def test_une_sortie_convertie_ne_repart_pas_au_scan_suivant(tmp_path):
    sortie = decide(_info(tmp_path), _converti()).video
    refait = decide(_info(tmp_path, codec="hevc",
                          kbps=sortie.target_bitrate * 105 // 100 // 1000), _converti())
    assert refait.video.action == VideoAction.SKIP


def test_une_source_trop_grande_garde_sa_reduction(tmp_path):
    # 4K H.264 à 6 000k, profil sans 4K : réduit en 1080p, au débit converti.
    v = decide(_info(tmp_path, kbps=6000, largeur=3840, hauteur=2160), _converti()).video
    assert v.action == VideoAction.ENCODE_HEVC
    assert (v.target_width, v.target_height) == (1920, 1080)
    assert v.target_bitrate == 4_200_000


def test_l_estimation_de_taille_suit_la_cible_convertie(tmp_path):
    from tui.screens.browser import _estimate_output_bytes
    dec = decide(_info(tmp_path), _converti())
    # 600 s : 3 500k de vidéo + 448k d'AC3 recopié.
    assert _estimate_output_bytes(dec, 1) == (3_500_000 + 448_000) * 600 // 8


# ─── Le contrôle des valeurs de profiles.toml ─────────────────────────────────

@pytest.fixture
def profils(tmp_path, monkeypatch):
    chemin = tmp_path / "profiles.toml"
    monkeypatch.setattr(prof_mod, "PROFILES_PATH", chemin)
    monkeypatch.setattr(prof_mod, "_illisible", None)
    return chemin


@pytest.mark.parametrize("ligne", [
    "convert_h264 = 1", "h264_to_hevc_ratio = 1.0", "h264_to_hevc_ratio = 0",
    'h264_to_hevc_ratio = "0.7"', "h264_min_kbps = 0", "h264_min_kbps = 2.5",
])
def test_une_valeur_invalide_est_ecartee(profils, ligne):
    cle = ligne.split(" = ")[0]
    profils.write_text(f"[p]\n{ligne}\n", encoding="utf-8")
    p = prof_mod.load_all()["p"]
    assert cle not in p.data
    assert prof_mod.corrigees() == [f"p.{cle}"]


def test_des_valeurs_valides_sont_gardees(profils):
    profils.write_text("[p]\nconvert_h264 = true\nh264_to_hevc_ratio = 0.65\n"
                       "h264_min_kbps = 3000\n", encoding="utf-8")
    p = prof_mod.load_all()["p"]
    assert prof_mod.corrigees() == []
    assert (p.get("convert_h264"), p.get("h264_to_hevc_ratio"),
            p.get("h264_min_kbps")) == (True, 0.65, 3000)


# ─── L'éditeur de profils ─────────────────────────────────────────────────────

def _formulaire(donnees: dict):
    from textual.app import App
    from textual.widgets import Static

    from tui.widgets.profile_form import ProfileForm

    class _App(App):
        def compose(self):
            yield ProfileForm()

    async def _run():
        app = _App()
        async with app.run_test(size=(160, 60)) as pilot:
            form = app.query_one(ProfileForm)
            form.load("p", donnees)
            await pilot.pause(0.2)
            return form.dump(), str(app.query_one("#cons-h264", Static).render())
    return asyncio.run(_run())


def test_le_formulaire_relit_et_reecrit_les_trois_cles():
    data, cons = _formulaire({"convert_h264": True, "h264_to_hevc_ratio": 0.72,
                              "h264_min_kbps": 3500})
    assert (data["convert_h264"], data["h264_to_hevc_ratio"],
            data["h264_min_kbps"]) == (True, 0.72, 3500)
    assert "72" in cons and "3500k" in cons


def test_le_formulaire_d_un_ancien_profil_n_active_rien():
    data, _cons = _formulaire({})
    assert data["convert_h264"] is False
    assert (data["h264_to_hevc_ratio"], data["h264_min_kbps"]) == (0.7, 2500)
