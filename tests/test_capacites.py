"""
tests/test_capacites.py — Ce que la machine sait faire est mesuré, pas supposé.

`platform.detect()` annonçait `av1_nvenc` dès qu'une carte NVIDIA était
détectée. Or NVENC n'encode l'AV1 qu'à partir d'Ada (RTX 40) : une carte
antérieure répond « No capable devices found » — mais seulement au moment
d'échouer, et l'écran n'affichait alors que « Error opening output files:
Invalid argument », c'est-à-dire la seule ligne qui n'apprend rien.

Deux corrections distinctes, et une découverte en chemin :

1. La commande AV1 passait `-profile:v main`, option que `av1_nvenc` **n'a
   pas** : l'AV1 échouait donc sur *toute* machine, capable ou non.
2. Les encodeurs sont sondés au lancement, en parallèle.
3. Le choix AV1 n'est **pas retiré** — une carte se remplace, un pilote se met
   à jour — mais le picker dit qu'il est indisponible, et le lancement refuse
   en nommant la cause au lieu de laisser ffmpeg échouer.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from core.decision import VideoAction
from core.encoder import diagnostiquer, encodeur_de
from core.platform import GPU, OS, PlatformProfile

_PLAT = PlatformProfile(os=OS.WINDOWS, gpu=GPU.NVIDIA, hwaccel="cuda",
                        encoder_hevc="hevc_nvenc", encoder_h264="h264_nvenc",
                        encoder_av1="av1_nvenc")


# ─── L'option -profile:v ──────────────────────────────────────────────────────

def _cmd(action, tmp_path):
    from core.decision import decide, force_skip_to_encode
    from core.encoder import build_command
    from core.profiles import Profile
    from core.scanner import AudioTrack, VideoInfo

    p = tmp_path / "film.mkv"
    p.write_bytes(b"")
    info = VideoInfo(path=p, width=1920, height=1080, bitrate=8_000_000,
                     codec="hevc", duration=60.0, frame_count=0,
                     dv_profile=None,
                     audio_tracks=[AudioTrack(index=0, codec="aac", channels=2,
                                              language="fre", title="",
                                              bitrate=128_000)])
    prof = Profile(id="t", data={"bitrate_1080p_kbps": 2000,
                                 "bitrate_720p_kbps": 2000,
                                 "bitrate_4k_kbps": 8000,
                                 "audio_languages": ["fre"],
                                 "audio_copy_compatible": True})
    dec = force_skip_to_encode(decide(info, prof))
    dec = replace(dec, video=replace(dec.video, action=action,
                                     target_bitrate=2_000_000))
    return build_command(dec, _PLAT)


def test_l_av1_ne_recoit_pas_d_option_profile(tmp_path):
    """`av1_nvenc` n'expose aucune option `profile` : lui en passer une faisait
    échouer la commande avant même que la carte soit interrogée."""
    cmd = _cmd(VideoAction.ENCODE_AV1, tmp_path)
    assert "-profile:v" not in cmd
    assert cmd[cmd.index("-c:v") + 1] == "av1_nvenc"


@pytest.mark.parametrize("action", [VideoAction.ENCODE_HEVC,
                                    VideoAction.ENCODE_H264])
def test_les_autres_encodeurs_gardent_leur_profil(tmp_path, action):
    cmd = _cmd(action, tmp_path)
    assert "-profile:v" in cmd


def test_encodeur_de_lit_la_commande(tmp_path):
    assert encodeur_de(_cmd(VideoAction.ENCODE_HEVC, tmp_path)) == "hevc_nvenc"
    assert encodeur_de(["ffmpeg", "-i", "x"]) is None


# ─── Le sondage ───────────────────────────────────────────────────────────────

def test_sans_sondage_on_ne_prejuge_de_rien():
    """`None` n'est pas `False` : ne rien savoir n'autorise pas à refuser."""
    assert _PLAT.encodeurs_ok is None
    assert _PLAT.peut_encoder("av1_nvenc") is None


def test_apres_sondage_la_reponse_est_ferme():
    plat = replace(_PLAT, encodeurs_ok=frozenset({"hevc_nvenc", "h264_nvenc"}))
    assert plat.peut_encoder("hevc_nvenc") is True
    assert plat.peut_encoder("av1_nvenc") is False


def test_le_sondage_reel_repond_pour_les_trois():
    """Sur la machine de développement : HEVC et H264 passent, l'AV1 non."""
    from pathlib import Path

    from core.platform import sonder_encodeurs

    ffmpeg = Path(__file__).resolve().parent.parent / "bin" / "ffmpeg.exe"
    if not ffmpeg.exists():
        pytest.skip("ffmpeg absent de bin/")
    ok = sonder_encodeurs(["hevc_nvenc", "h264_nvenc", "encodeur_inexistant"],
                          str(ffmpeg))
    assert "encodeur_inexistant" not in ok
    assert isinstance(ok, frozenset)


# ─── Le picker garde le choix, mais le qualifie ───────────────────────────────

def test_le_picker_ne_retire_jamais_l_option():
    from tui.common import CODEC_PICKER_OPTS, codec_picker_opts

    plat = replace(_PLAT, encodeurs_ok=frozenset({"hevc_nvenc"}))
    opts = codec_picker_opts(plat)
    assert len(opts) == len(CODEC_PICKER_OPTS)
    assert opts[2].startswith("AV1"), opts[2]
    assert "indisponible" in opts[2]
    assert "indisponible" in opts[1], "H264 non sondé positif : à signaler aussi"
    assert "indisponible" not in opts[0]


def test_sans_sondage_le_picker_n_annote_rien():
    from tui.common import CODEC_PICKER_OPTS, codec_picker_opts

    assert codec_picker_opts(_PLAT) == CODEC_PICKER_OPTS
    assert codec_picker_opts(None) == CODEC_PICKER_OPTS


# ─── Le diagnostic d'un échec ─────────────────────────────────────────────────

@pytest.mark.parametrize("ligne, attendu", [
    ("[av1_nvenc @ 0x1] No capable devices found", "carte graphique"),
    ("[enc:av1_nvenc] Could not open encoder before EOF", "n'a pas pu s'ouvrir"),
    ("[eac3 @ 0x1] invalid bit rate. must be 3008 to 6144000", "débit demandé"),
    ("No space left on device", "disque"),
])
def test_diagnostic_des_causes_connues(ligne, attendu):
    message = diagnostiquer(["frame= 1 fps=0", ligne, "Conversion failed!"])
    assert message and attendu in message


def test_diagnostic_muet_sur_l_inconnu():
    """Sans cause reconnue, l'appelant retombe sur la dernière ligne : mieux
    vaut une ligne brute qu'un message inventé."""
    assert diagnostiquer(["Conversion failed!"]) is None
