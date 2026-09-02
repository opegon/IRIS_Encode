"""
tests/test_hdr_audio_nom.py — Le nom de sortie dit le HDR et l'audio de sortie.

Suite de `test_resolution_nom.py` et `test_codec_nom.py`, sur les deux
dernières choses qu'un nom de release annonce et que la conversion rend
fausses :

- un `Film.2160p.DV` ramené en HDR10 n'est plus du Dolby Vision, et ramené en
  SDR n'est plus rien de tout cela ;
- un `Film.TrueHD.7.1` dont la piste sort en E-AC3 5.1 annonce un format
  absent du fichier — le même mensonge que `retitle()` corrige dans le titre
  des pistes, à ceci près que le nom du fichier est ce qu'on lit en premier.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.decision import (AudioAction, DVAction, VideoAction, decide,
                           famille_audio)
from core.profiles import Profile
from core.scanner import (AudioTrack, VideoInfo, stem_marques_remplacees,
                          stem_marques_retirees)


def _profile(**over) -> Profile:
    data = {
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps": 12000, "keep_4k": True,
        "audio_languages": ["fre", "eng"], "audio_copy_compatible": True,
        "preserve_hd_audio": False, "audio_stereo_kbps": 192,
        "audio_surround_kbps": 448, "dolby_vision": "hdr10",
    }
    data.update(over)
    return Profile(id="test", data=data)


def _piste(codec="truehd", canaux=8, profil="") -> AudioTrack:
    return AudioTrack(index=0, codec=codec, channels=canaux, language="fre",
                      title="", bitrate=3_500_000, profile=profil)


def _source(tmp_path: Path, nom: str, *, dv: str | None = "8.1",
            pistes=None, largeur=3840, hauteur=2160,
            bitrate=40_000_000) -> VideoInfo:
    p = tmp_path / f"{nom}.mkv"
    p.write_bytes(b"")
    return VideoInfo(
        path=p, width=largeur, height=hauteur, bitrate=bitrate, codec="hevc",
        duration=7200.0, frame_count=0, dv_profile=dv,
        audio_tracks=pistes if pistes is not None else [_piste()],
    )


# ─── Les marques Dolby Vision / HDR ──────────────────────────────────────────

@pytest.mark.parametrize("stem, attendu", [
    ("Film.2160p.DV.x265",          "Film.2160p.HDR10.x265"),
    ("Film.2160p.DoVi-GROUP",       "Film.2160p.HDR10-GROUP"),
    ("Film 2160p Dolby Vision VFF", "Film 2160p HDR10 VFF"),
    ("Film.2160p.DV.HDR10.x265",    "Film.2160p.HDR10.x265"),
    ("Film.2160p.HDR.DV",           "Film.2160p.HDR10"),
])
def test_le_dolby_vision_devient_hdr10(stem, attendu):
    from core.decision import JETONS_DV, JETONS_HDR
    assert stem_marques_remplacees(stem, JETONS_DV + JETONS_HDR,
                                   "HDR10") == attendu


def test_le_hdr10_plus_survit_au_passage_en_hdr10():
    """Le retrait du RPU laisse le HDR10+ intact : sa marque reste vraie."""
    from core.decision import JETONS_DV, JETONS_HDR
    assert stem_marques_remplacees("Film.2160p.HDR10+.DV",
                                   JETONS_DV + JETONS_HDR,
                                   "HDR10") == "Film.2160p.HDR10+.HDR10"


def test_une_sortie_sdr_n_annonce_plus_rien():
    from core.decision import JETONS_DV, JETONS_HDR, JETONS_HDR_PLUS
    jetons = JETONS_DV + JETONS_HDR + JETONS_HDR_PLUS
    assert stem_marques_retirees("Film.2160p.DV.HDR10+.x265",
                                 jetons) == "Film.2160p.x265"


@pytest.mark.parametrize("nom, attendu", [
    ("Film.2160p.10bit.DV",       "Film.2160p"),
    ("Film.2160p.10bits.HDR10+",  "Film.2160p"),
    ("Film 2160p 10 bits HDR",    "Film 2160p"),
    ("Film.2160p.Dolby.Vision",   "Film.2160p"),
    ("Film.2160p.Dolby.Video",    "Film.2160p"),
])
def test_une_sortie_sdr_perd_aussi_la_profondeur(tmp_path, nom, attendu):
    """Le tone mapping finit sur `format=yuv420p` : la sortie est en 8 bits."""
    dec = decide(_source(tmp_path, nom), _profile(dolby_vision="sdr"))
    assert dec.video.dv_action == DVAction.SDR
    assert dec.output_path.stem.startswith(f"{attendu}_[")


def test_une_sortie_hdr10_garde_sa_profondeur(tmp_path):
    """`yuv420p10le` : les 10 bits restent vrais, seule la marque DV change."""
    dec = decide(_source(tmp_path, "Film.2160p.10bit.DV"), _profile())
    assert dec.video.dv_action == DVAction.HDR10
    assert dec.output_path.stem.startswith("Film.2160p.10bit.HDR10")


def test_un_dv_ramene_en_hdr10_le_dit_dans_le_nom(tmp_path):
    dec = decide(_source(tmp_path, "Film.2160p.DV.HDR10"), _profile())
    assert dec.video.dv_action == DVAction.HDR10
    assert "HDR10" in dec.output_path.stem
    assert ".DV" not in dec.output_path.stem


def test_un_dv_conserve_garde_sa_marque(tmp_path):
    """`dolby_vision = "dv"` : le RPU reste, le nom aussi."""
    dec = decide(_source(tmp_path, "Film.2160p.DV"), _profile(dolby_vision="dv"))
    assert dec.video.dv_action == DVAction.DV
    assert "DV" in dec.output_path.stem


def test_un_dv_ramene_en_sdr_perd_toutes_les_marques(tmp_path):
    dec = decide(_source(tmp_path, "Film.2160p.DV.HDR10"),
                 _profile(dolby_vision="sdr"))
    assert dec.video.dv_action == DVAction.SDR
    assert dec.output_path.stem.startswith("Film.2160p_[")


def test_une_source_sans_dv_n_est_pas_touchee(tmp_path):
    """Un HDR10 sans RPU n'est pas converti : son nom n'a pas à changer."""
    dec = decide(_source(tmp_path, "Film.2160p.HDR10", dv=None), _profile())
    assert dec.video.dv_action == DVAction.NONE
    assert dec.output_path.stem.startswith("Film.2160p.HDR10")


# ─── Les marques audio ───────────────────────────────────────────────────────

@pytest.mark.parametrize("codec, attendu", [
    ("truehd",     "truehd"),
    ("dts",        "dts"),
    ("pcm_s16le",  "pcm"),
    ("pcm_bluray", "pcm"),
    ("eac3",       "eac3"),
])
def test_la_famille_de_marques_suit_le_codec_lu(codec, attendu):
    assert famille_audio(codec) == attendu


@pytest.mark.parametrize("nom, attendu", [
    ("Film.2160p.TrueHD.7.1",     "Film.2160p.E-AC3.5.1"),
    ("Film.2160p.TrueHD.Atmos",   "Film.2160p.E-AC3"),
    ("Film 2160p True-HD 7.1",    "Film 2160p E-AC3 5.1"),
])
def test_un_truehd_transcode_le_dit_dans_le_nom(tmp_path, nom, attendu):
    dec = decide(_source(tmp_path, nom), _profile(audio_hd_codec="eac3"))
    assert dec.audio[0].action == AudioAction.TRANSCODE
    assert dec.audio[0].output_codec == "eac3"
    assert dec.output_path.stem.startswith(attendu)


@pytest.mark.parametrize("nom, attendu", [
    ("Film.2160p.DTS-HD.MA.7.1", "Film.2160p.E-AC3.5.1"),
    ("Film.2160p.DTS-HD.MA",     "Film.2160p.E-AC3"),
    ("Film.2160p.DTS",           "Film.2160p.E-AC3"),
])
def test_un_dts_transcode_le_dit_dans_le_nom(tmp_path, nom, attendu):
    pistes = [_piste(codec="dts", canaux=8, profil="DTS-HD MA")]
    dec = decide(_source(tmp_path, nom, pistes=pistes),
                 _profile(audio_hd_codec="eac3"))
    assert dec.audio[0].action == AudioAction.TRANSCODE
    assert dec.output_path.stem.startswith(attendu)


def test_une_famille_conservee_garde_sa_marque(tmp_path):
    """L'AC3 recopié reste vrai : seul le TrueHD transcodé change de nom."""
    pistes = [_piste(codec="truehd", canaux=8),
              _piste(codec="ac3", canaux=6)]
    dec = decide(_source(tmp_path, "Film.2160p.TrueHD.AC3", pistes=pistes),
                 _profile(audio_hd_codec="eac3", audio_copy_compatible=True))
    assert dec.audio[1].action == AudioAction.COPY
    stem = dec.output_path.stem
    assert stem.startswith("Film.2160p.E-AC3.AC3")
    assert "TrueHD" not in stem


def test_une_piste_recopiee_ne_change_rien(tmp_path):
    """`preserve_hd_audio` : le TrueHD passe tel quel, sa marque reste vraie."""
    dec = decide(_source(tmp_path, "Film.2160p.TrueHD.7.1"),
                 _profile(preserve_hd_audio=True))
    assert dec.audio[0].action == AudioAction.COPY
    assert dec.output_path.stem.startswith("Film.2160p.TrueHD.7.1")


def test_un_nom_muet_sur_l_audio_ne_gagne_rien(tmp_path):
    """On corrige une marque existante, on n'en ajoute pas."""
    dec = decide(_source(tmp_path, "Le Nom du film (2017)"),
                 _profile(audio_hd_codec="eac3"))
    assert dec.output_path.stem.startswith("Le Nom du film (2017)_[")


def test_les_quatre_reecritures_se_composent(tmp_path):
    """Définition, codec, HDR et audio dans le même nom."""
    info = _source(tmp_path, "Film.2160p.DV.HDR10.x265.TrueHD.7.1-GROUP")
    dec  = decide(info, _profile(keep_4k=False, audio_hd_codec="eac3"))
    assert dec.video.action == VideoAction.ENCODE_HEVC
    assert dec.output_path.stem == "Film.1080p.HDR10.E-AC3.5.1-GROUP_[hevc]"


def test_un_skip_ne_touche_a_rien(tmp_path):
    """Sans traitement, rien ne devient faux — pas même un RPU non retiré."""
    info = _source(tmp_path, "Film.1080p.DV.TrueHD.7.1", largeur=1920,
                   hauteur=1080, bitrate=3_000_000)
    dec  = decide(info, _profile(preserve_hd_audio=True))
    assert dec.video.action == VideoAction.SKIP
    assert dec.output_path.stem == "Film.1080p.DV.TrueHD.7.1"
