"""
tests/test_codecs_sources.py — Un codec que la chaîne ne lit pas se réencode.

La règle « codec non standard » ne se déclenchait qu'en dessous de 1080p : un
VP9 ou un AV1 en 1080p ou en 4K, dont le débit et la résolution tenaient dans
les seuils du profil, ressortait en `← SKIP`. Il restait donc illisible chez le
destinataire — un fichier ne devient pas lisible parce que son débit est
raisonnable.

Le critère porte désormais sur le codec seul. L'Opus, lui, n'a jamais été
copiable : il suivait déjà la règle par canaux.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.decision import CODECS_LISIBLES, VideoAction, decide
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo


def _info(tmp_path: Path, codec: str, *, largeur=1920, hauteur=1080,
          audio="opus", canaux=2) -> VideoInfo:
    p = tmp_path / "film.webm"
    p.write_bytes(b"")
    return VideoInfo(
        path=p, width=largeur, height=hauteur, bitrate=2_500_000, codec=codec,
        duration=3600.0, frame_count=0, dv_profile=None,
        audio_tracks=[AudioTrack(index=0, codec=audio, channels=canaux,
                                 language="fre", title="", bitrate=128_000)],
    )


def _profile(**over) -> Profile:
    data = {
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps": 12000, "keep_4k": True,
        "audio_languages": ["fre", "eng"], "audio_copy_compatible": True,
        "preserve_hd_audio": False, "audio_stereo_kbps": 192,
        "audio_surround_kbps": 448,
    }
    data.update(over)
    return Profile(id="test", data=data)


# ─── Le critère ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("codec", ["h264", "hevc"])
def test_un_codec_lisible_n_est_pas_reencode_pour_son_codec(tmp_path, codec):
    """Débit et résolution dans les clous : rien ne justifie d'y toucher."""
    dec = decide(_info(tmp_path, codec), _profile())
    assert dec.video.action == VideoAction.SKIP


@pytest.mark.parametrize("codec", ["vp9", "av1", "vc1", "mpeg2video", "mpeg4"])
@pytest.mark.parametrize("hauteur", [720, 1080, 2160])
def test_un_codec_illisible_se_reencode_a_toute_resolution(tmp_path, codec, hauteur):
    """C'est le cœur du correctif : la résolution n'entre plus en compte.

    Le débit est choisi sous tous les seuils du profil, pour que seule la
    règle du codec puisse trancher — sinon c'est celle du débit qu'on
    testerait."""
    largeur = {720: 1280, 1080: 1920, 2160: 3840}[hauteur]
    info = _info(tmp_path, codec, largeur=largeur, hauteur=hauteur)
    info.bitrate = 1_500_000
    dec = decide(info, _profile())
    assert dec.video.action != VideoAction.SKIP, f"{codec} {hauteur}p laissé tel quel"
    assert codec in dec.video.reason


def test_la_cible_suit_le_bucket_de_resolution(tmp_path):
    """H264 sous 1080p — il y compresse mieux —, HEVC au-dessus."""
    petit = decide(_info(tmp_path, "av1", largeur=1280, hauteur=720), _profile())
    assert petit.video.action == VideoAction.ENCODE_H264
    assert petit.output_path.stem.endswith("_[H264]")

    grand = decide(_info(tmp_path, "vp9"), _profile())
    assert grand.video.action == VideoAction.ENCODE_HEVC
    assert grand.output_path.stem.endswith("_[hevc]")


def test_un_codec_inconnu_est_traite_comme_illisible(tmp_path):
    """ffprobe rend « unknown » quand il ne reconnaît rien : mieux vaut tenter
    un réencodage que livrer un fichier dont personne ne sait quoi faire."""
    dec = decide(_info(tmp_path, "unknown"), _profile())
    assert dec.video.action != VideoAction.SKIP


def test_le_debit_et_la_resolution_gardent_la_priorite(tmp_path):
    """Un VP9 trop gros reste traité par le cas du débit, pas par celui du
    codec : le motif affiché doit dire lequel a tranché."""
    dec = decide(_info(tmp_path, "vp9"), _profile(bitrate_1080p_kbps=2000))
    assert dec.video.action == VideoAction.ENCODE_HEVC
    assert "Débit" in dec.video.reason


# ─── L'audio Opus ─────────────────────────────────────────────────────────────

def test_opus_n_est_jamais_recopie(tmp_path):
    """Opus n'est pas dans les codecs copiables : il suit la règle par canaux."""
    from core.decision import AudioAction

    stereo = decide(_info(tmp_path, "vp9", audio="opus", canaux=2), _profile())
    assert stereo.audio[0].action == AudioAction.TRANSCODE
    assert stereo.audio[0].output_codec == "aac"

    surround = decide(_info(tmp_path, "vp9", audio="opus", canaux=6), _profile())
    assert surround.audio[0].output_codec == "ac3"


# ─── Le WebM est bien vu ──────────────────────────────────────────────────────

def test_le_webm_est_une_extension_reconnue():
    from core.scanner import SUPPORTED_EXTENSIONS

    assert ".webm" in SUPPORTED_EXTENSIONS


def test_la_table_des_codecs_lisibles_reste_explicite():
    """Elle doit rester courte et nommée : c'est elle qui décide de tout le
    reste, et l'y ajouter un codec est une décision, pas un détail."""
    assert CODECS_LISIBLES == frozenset({"h264", "hevc"})
