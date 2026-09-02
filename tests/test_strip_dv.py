"""
tests/test_strip_dv.py — Retrait du Dolby Vision sans réencodage.

Un profil 8.1 porte une couche de base qui *est* du HDR10 : retirer le RPU
suffit à obtenir un HDR10 valide, sans toucher une seule image. Ces tests
verrouillent qui y a droit, ce que la décision en dit, et la forme des
commandes — pas la qualité du résultat, qui se vérifie sur un vrai fichier.
"""
from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from core import decision as decision_mod
from core import dovi, muxer
from core.decision import AudioAction, DVAction, VideoAction, decide
from core.platform import GPU, OS, PlatformProfile
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def outils_presents():
    """Les tests supposent dovi_tool et mkvmerge installés, sauf mention."""
    decision_mod.set_strip_dv_available(True)
    yield
    decision_mod.set_strip_dv_available(False)


def _info(tmp_path: Path, *, dv_profile=8, dv_bl_compat=1, bitrate=5_600_000,
          width=3840, height=1606, transfer="smpte2084") -> VideoInfo:
    p = tmp_path / "film.mkv"
    p.write_bytes(b"")
    return VideoInfo(
        path=p, width=width, height=height, bitrate=bitrate, codec="hevc",
        duration=8680.0, frame_count=208_000, dv_profile=dv_profile,
        audio_tracks=[AudioTrack(index=0, codec="eac3", channels=8,
                                 language="fre", title="VFF", bitrate=640_000)],
        dv_bl_compat=dv_bl_compat, color_transfer=transfer, frame_rate="24/1",
    )


def _profile(**over) -> Profile:
    data = {
        "bitrate_4k_kbps": 12000, "bitrate_1080p_kbps": 5000,
        "bitrate_720p_kbps": 2000, "keep_4k": True,
        "dolby_vision": "hdr10", "preset_encoder": "slow",
        "audio_languages": ["fre", "eng"], "audio_copy_compatible": True,
        "preserve_hd_audio": True,
    }
    data.update(over)
    return Profile(id="test", data=data)


_PLAT = PlatformProfile(
    os=OS.WINDOWS, gpu=GPU.NVIDIA, hwaccel="cuda",
    encoder_hevc="hevc_nvenc", encoder_h264="h264_nvenc",
    encoder_av1="av1_nvenc",
)


# ─── Éligibilité ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("profil, compat, attendu", [
    (8, 1, True),      # 8.1 — couche de base HDR10
    (7, None, True),   # 7   — couche de base HDR10 + couche d'amélioration
    (8, 4, False),     # 8.4 — couche de base HLG, pas HDR10
    (8, 2, False),     # 8.2 — couche de base SDR
    (8, None, False),  # profil 8 sans compat annoncée : on ne devine pas
    (5, None, False),  # 5   — couche de base IPT-PQ, illisible sans RPU
    (None, None, False),
])
def test_can_strip_dv(tmp_path, profil, compat, attendu):
    info = _info(tmp_path, dv_profile=profil, dv_bl_compat=compat)
    assert info.can_strip_dv is attendu


def test_dv_label_montre_le_sous_profil(tmp_path):
    assert _info(tmp_path, dv_profile=8, dv_bl_compat=1).dv_label == "DV:P8.1"
    assert _info(tmp_path, dv_profile=8, dv_bl_compat=4).dv_label == "DV:P8.4"
    assert _info(tmp_path, dv_profile=8, dv_bl_compat=None).dv_label == "DV:P8"
    assert _info(tmp_path, dv_profile=5).dv_label == "DV:P5"


# ─── Décision ─────────────────────────────────────────────────────────────────

def test_debit_sous_le_seuil_donne_un_retrait_de_dv(tmp_path):
    """Rien à réencoder + RPU retirable = remux, pas SKIP."""
    dec = decide(_info(tmp_path), _profile())
    assert dec.video.action == VideoAction.STRIP_DV
    assert dec.video.dv_action == DVAction.HDR10
    assert dec.video.target_bitrate == 0
    assert dec.output_path.stem == "film_[hdr10]"


def test_le_profil_garde_la_main_sur_le_reencodage(tmp_path):
    """Débit trop élevé : le réencodage l'emporte, il retire le RPU lui-même."""
    dec = decide(_info(tmp_path, bitrate=25_000_000), _profile())
    assert dec.video.action == VideoAction.ENCODE_HEVC
    assert dec.video.dv_action == DVAction.HDR10


def test_profil_qui_preserve_le_dv_ne_retire_rien(tmp_path):
    dec = decide(_info(tmp_path), _profile(dolby_vision="dv"))
    assert dec.video.action == VideoAction.SKIP


def test_sans_les_outils_on_ne_propose_pas(tmp_path):
    """Proposer une action qui échouera au lancement vaut moins que SKIP."""
    decision_mod.set_strip_dv_available(False)
    dec = decide(_info(tmp_path), _profile())
    assert dec.video.action == VideoAction.SKIP


def test_un_84_ne_devient_pas_un_retrait(tmp_path):
    dec = decide(_info(tmp_path, dv_bl_compat=4), _profile())
    assert dec.video.action == VideoAction.SKIP


@pytest.mark.parametrize("conteneur, attendu", [
    ("auto", ".mp4"),   # rien dans ce fichier n'impose le Matroska
    ("mkv",  ".mkv"),
    ("mp4",  ".mp4"),
])
def test_le_conteneur_du_retrait_suit_le_profil(tmp_path, conteneur, attendu):
    """Le retrait n'impose plus le Matroska : mkvmerge le produit, ffmpeg
    produit le MP4, et c'est le contenu — ou le profil — qui tranche."""
    dec = decide(_info(tmp_path), _profile(container=conteneur))
    assert dec.output_container == attendu


def test_resume_audio_montre_les_pistes_du_fichier_produit(tmp_path):
    """Le retrait applique la décision audio : le résumé la montre.

    Il recopiait l'audio en bloc jusqu'à la v0.8.8.0, et le résumé faisait
    exception pour le dire. Les pistes transcodées passent depuis par un
    Matroska produit à part, les exclues par `--audio-tracks` : c'est
    l'exception qui promettait des pistes que le fichier n'a pas.
    """
    info = _info(tmp_path)
    info.audio_tracks.append(AudioTrack(index=1, codec="eac3", channels=6,
                                        language="jpn", title="VO",
                                        bitrate=640_000))
    dec = decide(info, _profile(audio_languages=["fre"]))

    exclue = next(ad for ad in dec.audio if ad.track.language == "jpn")
    assert exclue.action == AudioAction.EXCLUDE
    assert "jpn" not in dec.audio_summary
    assert "fre" in dec.audio_summary


def test_forcage_manuel_repart_du_debit_source(tmp_path):
    dec = decide(_info(tmp_path), _profile())
    forced = decision_mod.force_skip_to_encode(dec)
    assert forced.video.action == VideoAction.ENCODE_HEVC
    assert forced.video.target_bitrate == 5_600_000


# ─── Commandes ────────────────────────────────────────────────────────────────

def test_aucune_commande_ffmpeg_pour_un_retrait(tmp_path):
    from core.encoder import build_command
    dec = decide(_info(tmp_path), _profile())
    assert build_command(dec, _PLAT) == []


def test_remove_dv_appelle_le_bon_sous_programme(tmp_path):
    with mock.patch("subprocess.run") as run:
        run.return_value = mock.Mock(returncode=0)
        (tmp_path / "out.hevc").write_bytes(b"")
        dovi.remove_dv(tmp_path / "in.hevc", tmp_path / "out.hevc",
                       tmp_path / "dovi_tool.exe")
    cmd = run.call_args[0][0]
    assert cmd[1] == "remove"
    assert "-i" in cmd and "-o" in cmd


def test_build_strip_command(tmp_path):
    muxer.set_mkvmerge_path("mkvmerge")
    cmd = muxer.build_strip_command(
        tmp_path / "nodv.hevc", tmp_path / "film.mkv",
        tmp_path / "film_[hdr10].mkv", fps="24/1")
    assert cmd[0] == "mkvmerge"
    # La cadence doit précéder le flux brut : sans elle, la vidéo dérive
    assert cmd[cmd.index("--default-duration") + 1] == "0:24p"
    assert cmd.index("--default-duration") < cmd.index(str(tmp_path / "nodv.hevc"))
    # La source ne fournit que ses pistes non vidéo
    assert cmd[cmd.index("--no-video") + 1] == str(tmp_path / "film.mkv")


def test_build_strip_command_fraction(tmp_path):
    muxer.set_mkvmerge_path("mkvmerge")
    cmd = muxer.build_strip_command(tmp_path / "a.hevc", tmp_path / "b.mkv",
                                    tmp_path / "c.mkv", fps="24000/1001")
    assert cmd[cmd.index("--default-duration") + 1] == "0:24000/1001p"


def test_build_strip_command_refuse_ecraser_la_source(tmp_path):
    muxer.set_mkvmerge_path("mkvmerge")
    src = tmp_path / "film.mkv"
    src.write_bytes(b"")
    with pytest.raises(ValueError):
        muxer.build_strip_command(tmp_path / "a.hevc", src, src)


# ─── Sortie HDR10 en 10 bits ──────────────────────────────────────────────────

def test_reencodage_hdr10_sort_en_10_bits(tmp_path):
    """Une courbe PQ étalée sur 256 niveaux, c'est du banding garanti."""
    from core.encoder import build_command
    dec = decide(_info(tmp_path, bitrate=25_000_000), _profile())
    cmd = build_command(dec, _PLAT)
    assert cmd[cmd.index("-pix_fmt") + 1] == "yuv420p10le"
    assert cmd[cmd.index("-profile:v") + 1] == "main10"


def test_source_hdr_sans_dv_sort_aussi_en_10_bits(tmp_path):
    from core.encoder import build_command
    info = _info(tmp_path, dv_profile=None, dv_bl_compat=None,
                 bitrate=25_000_000)
    cmd  = build_command(decide(info, _profile()), _PLAT)
    assert cmd[cmd.index("-pix_fmt") + 1] == "yuv420p10le"


def test_source_sdr_reste_en_8_bits(tmp_path):
    from core.encoder import build_command
    info = _info(tmp_path, dv_profile=None, dv_bl_compat=None,
                 bitrate=25_000_000, transfer="bt709")
    cmd  = build_command(decide(info, _profile()), _PLAT)
    assert cmd[cmd.index("-pix_fmt") + 1] == "yuv420p"


# ─── Cycle codec du TUI ───────────────────────────────────────────────────────

@pytest.mark.parametrize("action", list(VideoAction))
def test_toute_action_a_une_position_dans_le_cycle(action):
    """ACTION_CYCLE ne contient que les codecs proposables ; STRIP_DV n'en est
    pas un. Sans repli, `.index()` levait un ValueError et l'écran Pistes
    plantait sur F6. Le test porte sur *toutes* les actions pour qu'un membre
    ajouté plus tard tombe ici plutôt qu'en production."""
    i = decision_mod.cycle_index(action)
    assert 0 <= i < len(decision_mod.ACTION_CYCLE)


def test_strip_dv_se_range_avec_skip():
    idx = decision_mod.cycle_index(VideoAction.STRIP_DV)
    assert decision_mod.ACTION_CYCLE[idx] == VideoAction.SKIP


def test_choisir_skip_sur_un_strip_dv_leve_la_surcharge():
    """« SKIP » veut dire « ne pas réencoder » — ce que le retrait du RPU fait
    déjà. Imposer un SKIP sec laisserait le Dolby Vision en place sans que
    rien ne l'explique à l'écran."""
    assert decision_mod.same_intent(VideoAction.SKIP, VideoAction.STRIP_DV)
    assert decision_mod.same_intent(VideoAction.SKIP, VideoAction.SKIP)
    assert not decision_mod.same_intent(VideoAction.ENCODE_HEVC,
                                        VideoAction.STRIP_DV)
    assert not decision_mod.same_intent(VideoAction.STRIP_DV,
                                        VideoAction.SKIP)
