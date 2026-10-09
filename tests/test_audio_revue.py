"""
tests/test_audio_revue.py — Audio : DTS:X IMAX, marques collées, pistes écartées (IE-128).

Constats CR-09, CR-10 et CR-18 de `revue_code_2026-10-08.md`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.decision import AudioAction, decide
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo, stem_marques_retirees


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


def _piste(codec, canaux, profil="", index=0, pid=None) -> AudioTrack:
    return AudioTrack(index=index, codec=codec, channels=canaux, language="fre",
                      title="", bitrate=3_500_000, profile=profil, pid=pid)


def _source(tmp_path: Path, nom: str, pistes, largeur=1920, hauteur=1080) -> VideoInfo:
    p = tmp_path / f"{nom}.mkv"
    p.write_bytes(b"")
    return VideoInfo(path=p, width=largeur, height=hauteur, bitrate=40_000_000,
                     codec="h264", duration=7200.0, frame_count=0, dv_profile=None,
                     audio_tracks=pistes)


# ─── CR-09 : DTS:X IMAX est sans perte ───────────────────────────────────────

@pytest.mark.parametrize("profil,sans_perte", [
    ("DTS", False), ("DTS-ES", False), ("DTS 96/24", False),
    ("DTS-HD HRA", False), ("DTS Express", False),
    ("DTS-HD MA", True), ("DTS-HD MA + DTS:X", True),
    ("DTS-HD MA + DTS:X IMAX", True),
])
def test_les_profils_dts_sans_perte(profil, sans_perte):
    assert _piste("dts", 8, profil).is_lossless is sans_perte


def test_un_dts_x_imax_preserve_est_recopie_en_mkv(tmp_path):
    """`preserve_hd_audio` le transcodait en AC-3 5.1, sortie en MP4 : avec
    `delete_source`, la piste sans perte était perdue pour de bon."""
    info = _source(tmp_path, "Film", [_piste("dts", 8, "DTS-HD MA + DTS:X IMAX")])
    dec = decide(info, _profile(preserve_hd_audio=True))
    assert dec.audio[0].action == AudioAction.COPY
    assert dec.output_container == ".mkv"


# ─── CR-10 : une famille collée à ses canaux ─────────────────────────────────

@pytest.mark.parametrize("nom,piste,attendu", [
    ("Film.1080p.BluRay.DTS5.1.x264-GRP", ("dts", 6),
     "Film.1080p.BluRay.E-AC3.5.1.hevc-iris"),
    ("Film.2160p.BluRay.TrueHD7.1.Atmos.x265-GRP", ("truehd", 8),
     "Film.2160p.BluRay.E-AC3.5.1.hevc-iris"),
    ("Film.1080p.BluRay.DTS.5.1.x264-GRP", ("dts", 6),
     "Film.1080p.BluRay.E-AC3.5.1.hevc-iris"),
])
def test_la_famille_collee_a_ses_canaux_est_reecrite(tmp_path, nom, piste, attendu):
    largeur, hauteur = (3840, 2160) if "2160p" in nom else (1920, 1080)
    info = _source(tmp_path, nom, [_piste(*piste)], largeur, hauteur)
    dec = decide(info, _profile(audio_hd_codec="eac3"))
    assert dec.audio[0].action == AudioAction.TRANSCODE
    assert dec.output_path.stem == attendu


def test_un_ddp_colle_recopie_reste_tel_quel(tmp_path):
    info = _source(tmp_path, "Film.1080p.WEB.DDP5.1.x264-GRP", [_piste("eac3", 6)])
    dec = decide(info, _profile())
    assert dec.audio[0].action == AudioAction.COPY
    assert dec.output_path.stem == "Film.1080p.WEB.DDP5.1.hevc-iris"


def test_retirer_une_marque_collee_garde_le_separateur():
    assert stem_marques_retirees("Film.DTS5.1.x264", ("dts",)) == "Film.5.1.x264"


# ─── CR-18 : la famille d'une piste écartée ──────────────────────────────────

def test_la_truehd_ecartee_au_profit_de_son_coeur_quitte_le_nom(tmp_path):
    """TrueHD et cœur AC-3 de même PID : le cœur est gardé (IE-119), la
    sortie en AC-3 5.1 seule ne s'appelle plus `TrueHD.7.1.Atmos`."""
    info = _source(tmp_path,
                   "Film.2160p.UHD.BluRay.REMUX.HEVC.TrueHD.7.1.Atmos-GRP",
                   [_piste("truehd", 8, index=0, pid=0x1100),
                    _piste("ac3", 6, index=1, pid=0x1100)], 3840, 2160)
    dec = decide(info, _profile(keep_4k=False))
    assert [ad.action for ad in dec.audio] == [AudioAction.EXCLUDE, AudioAction.COPY]
    stem = dec.output_path.stem
    assert "TrueHD" not in stem and "Atmos" not in stem
    assert "AC3.5.1" in stem


def test_une_famille_encore_portee_reste(tmp_path):
    """Deux DTS, l'un écarté par la langue, l'autre recopié : `DTS` reste vrai."""
    ecartee = AudioTrack(index=1, codec="dts", channels=6, language="ger",
                         title="", bitrate=1_500_000)
    info = _source(tmp_path, "Film.1080p.BluRay.DTS.5.1-GRP",
                   [_piste("dts", 6, "DTS-HD MA"), ecartee])
    dec = decide(info, _profile(preserve_hd_audio=True))
    assert [ad.action for ad in dec.audio] == [AudioAction.COPY, AudioAction.EXCLUDE]
    assert dec.output_path.stem.startswith("Film.1080p.BluRay.DTS.5.1")
