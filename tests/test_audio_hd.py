"""
tests/test_audio_hd.py — Transcodage des pistes HD au débit de la source.

`audio_hd_codec` convertit les pistes TrueHD et DTS en AC3 ou E-AC3 **au débit
présent dans la piste**, plafonné à ce que l'encodeur sait produire. Les
plafonds ci-dessous sont mesurés sur le ffmpeg livré dans `bin/`, pas déduits
de la norme : l'AC3 ramène silencieusement toute demande au-dessus de 640 kbps,
l'E-AC3 honore jusqu'à 6144 kbps.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.decision import (
    CODEC_MAX_BPS, MAX_TRANSCODE_CHANNELS, AudioAction, decide_audio, retitle,
)
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _track(codec="truehd", *, channels=6, bitrate=3_501_887, profile="",
           index=0, language="eng") -> AudioTrack:
    return AudioTrack(index=index, codec=codec, channels=channels,
                      language=language, title="", bitrate=bitrate,
                      profile=profile)


def _info(tmp_path: Path, tracks: list[AudioTrack]) -> VideoInfo:
    p = tmp_path / "film.mkv"
    p.write_bytes(b"")
    return VideoInfo(path=p, width=3840, height=1600, bitrate=9_000_000,
                     codec="hevc", duration=3600.0, frame_count=86400,
                     dv_profile=None, audio_tracks=tracks)


def _profile(**over) -> Profile:
    data = {
        "audio_languages": ["fre", "eng"], "audio_stereo_kbps": 192,
        "audio_surround_kbps": 448, "audio_surround_7_1_kbps": 640,
        "audio_copy_compatible": True, "preserve_hd_audio": False,
        "audio_hd_codec": "none",
    }
    data.update(over)
    return Profile(id="test", data=data)


def _only(tmp_path, track, **prof) -> "AudioDecision":  # noqa: F821
    return decide_audio(_info(tmp_path, [track]), _profile(**prof))[0]


# ─── Détection des pistes concernées ──────────────────────────────────────────

def test_dts_hd_ma_est_reconnu_sans_perte():
    """ffprobe nomme toutes les variantes « dts » : sans lire `profile`, un
    DTS-HD MA passait pour un DTS ordinaire."""
    assert _track("dts", profile="DTS-HD MA").is_lossless is True
    assert _track("dts", profile="DTS").is_lossless is False
    assert _track("truehd").is_lossless is True


@pytest.mark.parametrize("codec, profil, attendu", [
    ("truehd", "",           True),
    ("mlp",    "",           True),
    ("dts",    "DTS",        True),
    ("dts",    "DTS-HD MA",  True),
    ("eac3",   "",           False),
    ("ac3",    "",           False),
    ("aac",    "",           False),
])
def test_is_hd_audio(codec, profil, attendu):
    assert _track(codec, profile=profil).is_hd_audio is attendu


# ─── Débit repris de la source ────────────────────────────────────────────────

def test_eac3_reprend_le_debit_de_la_piste(tmp_path):
    d = _only(tmp_path, _track(bitrate=3_501_887), audio_hd_codec="eac3")
    assert d.action == AudioAction.TRANSCODE
    assert d.output_codec == "eac3"
    assert d.output_bitrate == 3_501_887


def test_ac3_plafonne_a_640(tmp_path):
    """Demander plus à l'encodeur AC3 ne produit rien de plus : il ramène
    silencieusement à 640 kbps. Autant que la décision l'annonce."""
    d = _only(tmp_path, _track(bitrate=3_501_887), audio_hd_codec="ac3")
    assert d.output_codec == "ac3"
    assert d.output_bitrate == CODEC_MAX_BPS["ac3"] == 640_000


def test_eac3_plafonne_au_maximum_de_l_encodeur(tmp_path):
    d = _only(tmp_path, _track(bitrate=9_000_000), audio_hd_codec="eac3")
    assert d.output_bitrate == CODEC_MAX_BPS["eac3"] == 6_144_000


def test_debit_inferieur_au_plafond_conserve(tmp_path):
    """Un DTS 768k reste à 768k — le forfait 448k du profil ne s'applique pas."""
    d = _only(tmp_path, _track("dts", profile="DTS", bitrate=768_000),
              audio_hd_codec="eac3")
    assert d.output_bitrate == 768_000


def test_sans_l_option_le_forfait_du_profil_s_applique(tmp_path):
    d = _only(tmp_path, _track(bitrate=3_501_887))
    assert (d.output_codec, d.output_bitrate) == ("ac3", 448_000)


def test_debit_source_inconnu_retombe_sur_le_forfait(tmp_path):
    """Sans débit lisible, mieux vaut le forfait qu'une valeur inventée."""
    d = _only(tmp_path, _track(bitrate=0), audio_hd_codec="eac3")
    assert (d.output_codec, d.output_bitrate) == ("ac3", 448_000)


def test_une_piste_non_hd_n_est_pas_concernee(tmp_path):
    """L'option ne vise que TrueHD et DTS : une piste AAC garde son forfait."""
    d = _only(tmp_path, _track("aac", channels=6, bitrate=2_000_000),
              audio_hd_codec="eac3", audio_copy_compatible=False)
    assert (d.output_codec, d.output_bitrate) == ("ac3", 448_000)


def test_preserve_hd_audio_garde_la_priorite(tmp_path):
    """Copier sans perte prime sur transcoder au débit source."""
    d = _only(tmp_path, _track(), audio_hd_codec="eac3", preserve_hd_audio=True)
    assert d.action == AudioAction.COPY


# ─── Canaux ───────────────────────────────────────────────────────────────────

def test_une_piste_71_est_annoncee_en_51(tmp_path):
    """Les encodeurs ac3/eac3 ne dépassent pas le 5.1."""
    d = _only(tmp_path, _track(channels=8), audio_hd_codec="eac3")
    assert d.output_channels == MAX_TRANSCODE_CHANNELS == 6
    assert "5.1" in d.display()


def test_une_piste_51_ne_declare_aucun_downmix(tmp_path):
    d = _only(tmp_path, _track(channels=6), audio_hd_codec="eac3")
    assert d.output_channels == 0
    assert d.display() == "→ eac3 3501k"


def test_commande_ffmpeg_pose_le_downmix(tmp_path):
    from core.decision import decide
    from core.encoder import build_command
    from core.platform import GPU, OS, PlatformProfile

    plat = PlatformProfile(os=OS.WINDOWS, gpu=GPU.NVIDIA, hwaccel="cuda",
                           encoder_hevc="hevc_nvenc", encoder_h264="h264_nvenc",
                           encoder_av1="av1_nvenc")
    info = _info(tmp_path, [_track(channels=8, bitrate=4_000_000)])
    cmd  = build_command(decide(info, _profile(audio_hd_codec="eac3",
                                               bitrate_4k_kbps=8000)), plat)
    assert "-c:a:0" in cmd and cmd[cmd.index("-c:a:0") + 1] == "eac3"
    assert cmd[cmd.index("-b:a:0") + 1] == "4000000"
    assert cmd[cmd.index("-ac:a:0") + 1] == "6"


# ─── Réécriture du titre de piste ─────────────────────────────────────────────

@pytest.mark.parametrize("titre, codec, src_ch, out_ch, attendu", [
    # Le jeton de codec devient faux : il est remplacé
    ("ENG VO : TrueHD 5.1",     "eac3", 6, 0, "ENG VO : E-AC3 5.1"),
    ("FR VFF : AC3 5.1",        "eac3", 6, 0, "FR VFF : E-AC3 5.1"),
    ("VF DTS 5.1",              "ac3",  6, 0, "VF AC3 5.1"),
    ("DTS-HD MA 7.1",           "eac3", 8, 6, "E-AC3 5.1"),
    ("TrueHD",                  "eac3", 6, 0, "E-AC3"),
    # « DDP » doit l'emporter sur « DD », sinon il resterait un « P » orphelin
    ("VFF DDP 7.1",             "ac3",  8, 6, "VFF AC3 5.1"),
    # Les objets Atmos ne survivent pas à une conversion vers AC3/E-AC3
    ("VO DDP Atmos 5.1",        "eac3", 6, 0, "VO E-AC3 5.1"),
    ("ENG VO : DDP 5.1 Atmos",  "eac3", 6, 0, "ENG VO : E-AC3 5.1"),
    ("ENG VO : TrueHD Atmos 7.1","eac3", 8, 6, "ENG VO : E-AC3 5.1"),
    # Un titre muet sur le format n'a jamais menti : on n'y touche pas
    ("English",                 "eac3", 6, 0, None),
    ("Commentaire du réalisateur", "aac", 2, 0, None),
    ("",                        "eac3", 6, 0, None),
])
def test_retitle(titre, codec, src_ch, out_ch, attendu):
    assert retitle(titre, codec, src_ch, out_ch) == attendu


def test_le_titre_n_est_pas_touche_sur_une_copie(tmp_path):
    d = _only(tmp_path, _track("ac3", channels=6, bitrate=640_000),
              audio_hd_codec="eac3")
    assert d.action == AudioAction.COPY
    assert d.output_title is None


def test_la_commande_pose_le_titre_corrige(tmp_path):
    from core.decision import decide
    from core.encoder import build_command
    from core.platform import GPU, OS, PlatformProfile

    plat = PlatformProfile(os=OS.WINDOWS, gpu=GPU.NVIDIA, hwaccel="cuda",
                           encoder_hevc="hevc_nvenc", encoder_h264="h264_nvenc",
                           encoder_av1="av1_nvenc")
    piste = _track(bitrate=3_501_887)
    piste.title = "ENG VO : TrueHD 5.1"
    info = _info(tmp_path, [piste])
    cmd  = build_command(decide(info, _profile(audio_hd_codec="eac3",
                                               bitrate_4k_kbps=8000)), plat)
    i = cmd.index("-metadata:s:a:0")
    assert cmd[i + 1] == "title=ENG VO : E-AC3 5.1"
