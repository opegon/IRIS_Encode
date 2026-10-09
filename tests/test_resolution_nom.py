"""
tests/test_resolution_nom.py — Le nom de sortie dit la définition de sortie.

Un `Film.2160p.BluRay.mkv` rabattu en 1080p ressortait
`Film.2160p.BluRay.hevc-iris.mkv` : le nom promettait une définition que le
fichier n'a plus. Dans une médiathèque, deux fichiers de définitions
différentes se lisaient pareil, et c'est le nom — pas le conteneur — que
regarde l'utilisateur pour choisir.

La marque de la source est donc remplacée par celle de la sortie —
`2160p`, `4K`, `4KLight` → `1080p` — et **seulement dans le nom du fichier
produit** : la source n'est jamais renommée, et rien d'autre dans la décision
ne change.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.decision import VideoAction, decide
from core.encoder import build_command
from core.platform import GPU, OS, PlatformProfile
from core.profiles import Profile
from core.scanner import (AudioTrack, VideoInfo, stem_resolution_ramenee)


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


def _source(tmp_path: Path, nom: str, *, largeur=3840, hauteur=2160,
            bitrate=40_000_000, dv: str | None = None) -> VideoInfo:
    p = tmp_path / f"{nom}.mkv"
    p.write_bytes(b"")
    return VideoInfo(
        path=p, width=largeur, height=hauteur, bitrate=bitrate, codec="hevc",
        duration=7200.0, frame_count=0, dv_profile=dv,
        audio_tracks=[AudioTrack(index=0, codec="ac3", channels=6,
                                 language="fre", title="", bitrate=448_000)],
    )


# ─── La substitution elle-même ───────────────────────────────────────────────

@pytest.mark.parametrize("stem, attendu", [
    ("Film.2160p.BluRay.x265",     "Film.1080p.BluRay.x265"),
    ("Le Film (2019) 4K VOSTFR",   "Le Film (2019) 1080p VOSTFR"),
    ("Serie.S01E02.4KLight.MULTI", "Serie.S01E02.1080p.MULTI"),
    ("Film 4K Light TRUEFRENCH",   "Film 1080p TRUEFRENCH"),
    ("Film-2160P-DV",              "Film-1080p-DV"),
    ("Film.UHD.BluRay.2019",       "Film.1080p.BluRay.2019"),
])
def test_les_marques_sont_remplacees(stem, attendu):
    assert stem_resolution_ramenee(stem, "1080p") == attendu


@pytest.mark.parametrize("stem, attendu", [
    ("Film.2160p.UHD.BluRay",  "Film.1080p.BluRay"),
    ("Film 4K UHD BluRay",     "Film 1080p BluRay"),
])
def test_deux_marques_voisines_n_en_font_qu_une(stem, attendu):
    """`2160p.UHD` disait deux fois la définition : la sortie ne la dit
    qu'une, sans quoi le nom porterait `1080p.1080p`."""
    assert stem_resolution_ramenee(stem, "1080p") == attendu


@pytest.mark.parametrize("stem", [
    "Film 3840x2160 HDR",   # une dimension, pas une marque de release
    "24K Magic",            # un titre
    "H4K Squad",            # une marque collée à un mot
    "Movie.1080p.BD",       # déjà à la définition de sortie
])
def test_ce_qui_n_est_pas_une_marque_de_resolution_ne_bouge_pas(stem):
    assert stem_resolution_ramenee(stem, "1080p") == stem


@pytest.mark.parametrize("stem, attendu", [
    # Certains noms portent la marque dans le titre du dossier repris.
    ("4K.Film.2160p",                 "1080p.Film"),
    ("Film (2023) 4K DV HDR10 2160p", "Film (2023) 1080p DV HDR10"),
    ("Film.4K.DV.2160p.WEB-DL",       "Film.1080p.DV.WEB-DL"),
    ("Film [4K] DV [2160p]",          "Film [1080p] DV"),
])
def test_une_marque_eloignee_n_est_pas_dite_deux_fois(stem, attendu):
    """La première marque est remplacée, les autres partent : `1080p … 1080p`
    disait deux fois la définition."""
    assert stem_resolution_ramenee(stem, "1080p") == attendu


# ─── Ce que produit une décision ─────────────────────────────────────────────

@pytest.mark.parametrize("nom", ["Film.2160p.BluRay", "Film 4K", "Film.4KLight"])
def test_un_4k_rabattu_en_1080p_sort_sous_1080p(tmp_path, nom):
    dec = decide(_source(tmp_path, nom), _profile())
    assert dec.video.action == VideoAction.ENCODE_HEVC
    assert dec.video.target_height == 1080
    assert "2160" not in dec.output_path.stem
    assert "4K" not in dec.output_path.stem
    assert "1080p" in dec.output_path.stem


def test_un_4k_recadre_est_rabattu_en_1080p(tmp_path):
    """Un scope recadré en 3832x1600 n'atteint ni 3840 ni 2160 : il passait
    pour un 1080p, gardait sa définition et sortait nommé `2160p.4Klight`."""
    nom = "Spider-Man.2026.MULTi.TRUEFRENCH.2160p.4Klight.HDR.DV.WEB-DL.H265-Slay3R"
    dec = decide(_source(tmp_path, nom, largeur=3832, hauteur=1600,
                         bitrate=8_312_000), _profile())
    assert (dec.video.target_width, dec.video.target_height) == (1920, 1080)
    assert dec.info.is_4k
    assert "2160p" not in dec.output_path.stem
    assert "4Klight" not in dec.output_path.stem
    assert ".1080p." in dec.output_path.stem


def test_la_source_n_est_pas_renommee(tmp_path):
    """La substitution ne vaut que pour le fichier produit."""
    info = _source(tmp_path, "Film.2160p")
    dec  = decide(info, _profile())
    assert dec.info.path.stem == "Film.2160p"
    assert dec.info.path.exists()


def test_un_4k_conserve_garde_sa_marque(tmp_path):
    """`keep_4k` : la sortie est toujours en 2160p, le nom doit le dire."""
    dec = decide(_source(tmp_path, "Film.2160p"), _profile(keep_4k=True))
    assert dec.video.target_height == 2160
    assert dec.output_path.stem.startswith("Film.2160p")


def test_une_video_recopiee_garde_sa_marque(tmp_path):
    """DV conservé impose `-c:v copy` : la définition cible reste lettre morte.

    Renommer sur la seule cible annoncerait un 1080p pour un fichier resté en
    2160p — le mensonge que ce renommage existe pour supprimer.
    """
    dec = decide(_source(tmp_path, "Film.2160p", dv="8.1"),
                 _profile(dolby_vision="dv"))
    assert dec.output_path.stem.startswith("Film.2160p")


def test_un_1080p_est_laisse_tel_quel(tmp_path):
    """Rien à abaisser : le nom ne change pas, suffixe mis à part."""
    info = _source(tmp_path, "Film.1080p.WEB-DL", largeur=1920, hauteur=1080,
                   bitrate=12_000_000)
    dec  = decide(info, _profile())
    assert dec.output_path.stem == "Film.1080p.WEB-DL.hevc-iris"


def test_un_nom_sans_marque_de_resolution_ne_gagne_rien(tmp_path):
    """On remplace une marque existante, on n'en ajoute pas."""
    dec = decide(_source(tmp_path, "Le Nom du film (2017)"), _profile())
    assert dec.output_path.stem == "Le Nom du film (2017).hevc-iris"



# ─── Le filtre de redimensionnement ──────────────────────────────────────────

_PLAT = PlatformProfile(os=OS.WINDOWS, gpu=GPU.NVIDIA, hwaccel="cuda",
                        encoder_hevc="hevc_nvenc", encoder_h264="h264_nvenc",
                        encoder_av1="av1_nvenc")


def _filtre(tmp_path, largeur, hauteur, codec="hevc", bitrate=8_312_000):
    info = _source(tmp_path, "Film.2160p", largeur=largeur, hauteur=hauteur,
                   bitrate=bitrate)
    info.codec = codec
    dec = decide(info, _profile())
    assert dec.video.action == VideoAction.ENCODE_HEVC
    cmd = build_command(dec, _PLAT)
    return cmd[cmd.index("-vf") + 1] if "-vf" in cmd else None


def test_un_4k_recadre_rabattu_garde_des_pixels_carres(tmp_path):
    """`scale` rattrape l'arrondi de 3832x1600 → 1920x802 par un SAR de
    192079:192000 ; Jellyfin prend le fichier pour anamorphique et transcode."""
    assert _filtre(tmp_path, 3832, 1600).split(",")[:2] == [
        "scale=1920:1080:force_original_aspect_ratio=decrease"
        ":force_divisible_by=2", "setsar=1"]


def test_une_source_qui_tient_dans_la_cible_n_est_pas_agrandie(tmp_path):
    """1918x802 en H264 vers HEVC était étiré à 1920x802, en pixels de 959:960
    — Jellyfin transcodait. Il garde sa définition."""
    assert _filtre(tmp_path, 1918, 802, codec="h264", bitrate=10_000_000) is None


def test_une_dimension_impaire_perd_un_pixel_sans_agrandissement(tmp_path):
    """Le 4:2:0 exige des dimensions paires : 1917x801 sort en 1916x800."""
    assert _filtre(tmp_path, 1917, 801, codec="h264", bitrate=10_000_000) == (
        "scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1")
