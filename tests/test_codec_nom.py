"""
tests/test_codec_nom.py — Le nom de sortie dit le codec de sortie.

Un `Film.1080p.x264.mkv` réencodé en HEVC ressortait
`Film.1080p.x264_[hevc].mkv` : le nom annonçait deux codecs, dont un que le
fichier n'a plus. C'est le suffixe produit qui dit le codec ; les marques que
le nom portait pour la source partent, y compris quand elles tombent juste —
un `x265` gardé à côté de `_[hevc]` répète la même chose deux fois.

La substitution ne vaut que pour le **nom du fichier produit**, et seulement
quand le suffixe nomme vraiment le codec : une vidéo recopiée (DV conservé,
`-c:v copy`) et un remux HDR10 sortent dans le codec de la source, et leur
marque reste vraie.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.decision import DVAction, VideoAction, decide
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo, stem_sans_marque_codec


def _profile(**over) -> Profile:
    data = {
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps": 12000, "keep_4k": False,
        "audio_languages": ["fre", "eng"], "audio_copy_compatible": True,
        "preserve_hd_audio": False, "audio_stereo_kbps": 192,
        "audio_surround_kbps": 448, "dolby_vision": "hdr10",
    }
    data.update(over)
    return Profile(id="test", data=data)


def _source(tmp_path: Path, nom: str, *, largeur=1920, hauteur=1080,
            codec="h264", bitrate=20_000_000, dv: str | None = None) -> VideoInfo:
    p = tmp_path / f"{nom}.mkv"
    p.write_bytes(b"")
    return VideoInfo(
        path=p, width=largeur, height=hauteur, bitrate=bitrate, codec=codec,
        duration=7200.0, frame_count=0, dv_profile=dv,
        audio_tracks=[AudioTrack(index=0, codec="ac3", channels=6,
                                 language="fre", title="", bitrate=448_000)],
    )


# ─── Le retrait lui-même ─────────────────────────────────────────────────────

@pytest.mark.parametrize("stem, attendu", [
    ("Film.1080p.BluRay.x264",       "Film.1080p.BluRay"),
    ("Film.1080p.x265-GROUP",        "Film.1080p-GROUP"),
    ("Film 1080p HEVC AAC",          "Film 1080p AAC"),
    ("Film.1080p.H.264.AC3",         "Film.1080p.AC3"),
    ("Film-1080p-h265-VFF",          "Film-1080p-VFF"),
    ("Film.1080p.AV1.WEB-DL",        "Film.1080p.WEB-DL"),
    ("Film.1080p.VP9.WEBRip",        "Film.1080p.WEBRip"),
    ("x264.Film.1080p",              "Film.1080p"),
    ("Film (x265) 2019",             "Film 2019"),
    ("Film_[hevc] (copie)",          "Film (copie)"),
])
def test_les_marques_de_codec_partent(stem, attendu):
    assert stem_sans_marque_codec(stem) == attendu


def test_toutes_les_occurrences_partent():
    assert stem_sans_marque_codec("x264.Film.1080p.x264") == "Film.1080p"


@pytest.mark.parametrize("stem", [
    "AV1ator 1080p",          # une marque collée à un mot
    "MVP9 Story",             # idem, en fin de mot
    "Film.1080p.DTS-HD",      # un codec audio n'est pas concerné
    "Le Nom du film (2017)",  # rien à retirer
])
def test_ce_qui_n_est_pas_une_marque_de_codec_ne_bouge_pas(stem):
    assert stem_sans_marque_codec(stem) == stem


def test_un_nom_fait_de_la_seule_marque_est_rendu_tel_quel():
    """Mieux vaut un nom redondant qu'un fichier nommé par son seul suffixe."""
    assert stem_sans_marque_codec("x264") == "x264"


# ─── Ce que produit une décision ─────────────────────────────────────────────

@pytest.mark.parametrize("nom, attendu", [
    ("Film.1080p.BluRay.x264", "Film.1080p.BluRay_[hevc]"),
    ("Film.1080p.x265-GROUP",  "Film.1080p-GROUP_[hevc]"),
    ("Film 1080p HEVC AAC",    "Film 1080p AAC_[hevc]"),
])
def test_un_reencodage_en_hevc_efface_la_marque_de_la_source(tmp_path, nom, attendu):
    dec = decide(_source(tmp_path, nom), _profile())
    assert dec.video.action == VideoAction.ENCODE_HEVC
    assert dec.output_path.stem == attendu


def test_la_source_n_est_pas_renommee(tmp_path):
    info = _source(tmp_path, "Film.1080p.x264")
    dec  = decide(info, _profile())
    assert dec.info.path.stem == "Film.1080p.x264"
    assert dec.info.path.exists()


def test_les_deux_marques_partent_ensemble(tmp_path):
    """Définition et codec se corrigent dans le même nom."""
    info = _source(tmp_path, "Film.2160p.BluRay.x265-GROUP",
                   largeur=3840, hauteur=2160, codec="hevc",
                   bitrate=40_000_000)
    dec = decide(info, _profile())
    assert dec.output_path.stem == "Film.1080p.BluRay-GROUP_[hevc]"


def test_une_video_recopiee_garde_sa_marque(tmp_path):
    """DV conservé impose `-c:v copy` : le codec de la source est celui de la
    sortie, et `_[dv]` ne le dit pas."""
    info = _source(tmp_path, "Film.2160p.x265", largeur=3840, hauteur=2160,
                   codec="hevc", bitrate=40_000_000, dv="8.1")
    dec  = decide(info, _profile(dolby_vision="dv"))
    assert dec.video.dv_action == DVAction.DV
    assert "x265" in dec.output_path.stem


def test_un_skip_ne_touche_a_rien(tmp_path):
    """Sans réencodage, aucun suffixe ne prend le relais de la marque."""
    info = _source(tmp_path, "Film.1080p.x264", bitrate=3_000_000)
    dec  = decide(info, _profile())
    assert dec.video.action == VideoAction.SKIP
    assert dec.output_path.stem == "Film.1080p.x264"
