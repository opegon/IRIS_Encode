"""
tests/test_mesure_piste.py — Le tid mkvmerge n'est pas l'index ffmpeg.

Les deux numérotations se ressemblent assez pour qu'on les confonde : mkvmerge
numérote globalement — vidéo, audio et sous-titres dans la même suite — là où
ffmpeg numérote par type. Sur un donneur ordinaire, la première piste audio
porte le tid **1** et l'index ffmpeg **0**.

Mesurer sur le mauvais flux ne lève rien de lisible : la mesure échoue, ou pire
elle réussit sur une autre piste. Le défaut s'est produit deux fois — d'abord
dans la commande de greffe (IE-19), puis dans l'assistant, alors que l'écran de
recalage traduisait correctement depuis toujours.

`sync.measure_external_track` est donc le point d'entrée unique : la traduction
y vit une fois, et aucun appelant n'a plus à y penser.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core import sync
from core.muxer import ExternalTrack, IdentifiedTrack, TrackKind


@pytest.fixture
def donneur(monkeypatch, tmp_path):
    """Un donneur au dessin courant : une vidéo, deux audio, deux sous-titres.

    Les tid sautent la vidéo ; les index ffmpeg repartent de zéro par type.
    """
    from core import muxer
    pistes = [
        IdentifiedTrack(tid=1, kind=TrackKind.AUDIO,    codec="AC3",    language="fre"),
        IdentifiedTrack(tid=2, kind=TrackKind.AUDIO,    codec="EAC3",   language="eng"),
        IdentifiedTrack(tid=3, kind=TrackKind.SUBTITLE, codec="SubRip", language="fre"),
        IdentifiedTrack(tid=4, kind=TrackKind.SUBTITLE, codec="SubRip", language="eng"),
    ]
    monkeypatch.setattr(muxer, "identify", lambda _p: list(pistes))
    p = tmp_path / "donneur.mkv"
    p.write_bytes(b"")
    return p


@pytest.fixture
def appels(monkeypatch):
    """Retient ce que les mesures reçoivent réellement."""
    vus: dict[str, object] = {}

    def _audio(target, donor, donor_track=0, progress=None, duration=0.0):
        vus.update(quoi="audio", index=donor_track, duree=duration)
        return sync.SyncResult(42, None, 0.9, True)

    def _sous_titre(video, subtitle, progress=None, duration=0.0,
                    donor_track=None):
        vus.update(quoi="sous-titre", index=donor_track, duree=duration)
        return sync.SyncResult(7, None, 0.9, True)

    monkeypatch.setattr(sync, "measure_audio", _audio)
    monkeypatch.setattr(sync, "measure_subtitle", _sous_titre)
    return vus


def _piste(donneur: Path, tid: int, kind: TrackKind) -> ExternalTrack:
    return ExternalTrack(source_path=donneur, source_tid=tid, kind=kind,
                         codec="?", language="fre")


# ─── La traduction ────────────────────────────────────────────────────────────

def test_la_premiere_audio_porte_le_tid_1_et_l_index_0(donneur, appels, tmp_path):
    """Le cas qui cassait l'assistant : passer le tid tel quel visait un flux
    audio inexistant."""
    sync.measure_external_track(tmp_path / "film.mkv",
                                _piste(donneur, 1, TrackKind.AUDIO),
                                duration=3600.0)
    assert appels["quoi"] == "audio"
    assert appels["index"] == 0, "tid 1 → index ffmpeg 0"


def test_la_seconde_audio_devient_l_index_1(donneur, appels, tmp_path):
    sync.measure_external_track(tmp_path / "film.mkv",
                                _piste(donneur, 2, TrackKind.AUDIO))
    assert appels["index"] == 1


def test_les_sous_titres_ont_leur_propre_suite(donneur, appels, tmp_path):
    """tid 3 est le premier sous-titre : index 0, et non 3."""
    sync.measure_external_track(tmp_path / "film.mkv",
                                _piste(donneur, 3, TrackKind.SUBTITLE))
    assert appels["quoi"] == "sous-titre"
    assert appels["index"] == 0


def test_le_second_sous_titre_devient_l_index_1(donneur, appels, tmp_path):
    sync.measure_external_track(tmp_path / "film.mkv",
                                _piste(donneur, 4, TrackKind.SUBTITLE))
    assert appels["index"] == 1


def test_la_duree_est_transmise(donneur, appels, tmp_path):
    """Sans elle, la barre de progression n'a aucune échelle."""
    sync.measure_external_track(tmp_path / "film.mkv",
                                _piste(donneur, 1, TrackKind.AUDIO),
                                duration=5400.0)
    assert appels["duree"] == 5400.0


def test_un_srt_nu_reste_a_zero(monkeypatch, appels, tmp_path):
    """Un fichier à une seule piste : tid 0, index 0, rien à traduire."""
    from core import muxer
    monkeypatch.setattr(muxer, "identify", lambda _p: [
        IdentifiedTrack(tid=0, kind=TrackKind.SUBTITLE, codec="SubRip",
                        language="fre")])
    p = tmp_path / "vf.srt"
    p.write_bytes(b"")
    sync.measure_external_track(tmp_path / "film.mkv",
                                _piste(p, 0, TrackKind.SUBTITLE))
    assert appels["index"] == 0


def test_un_donneur_illisible_vise_le_premier_flux(monkeypatch, appels,
                                                  tmp_path):
    """mkvmerge absent ou muet : `ffmpeg_stream_index` retombe sur 0.

    Viser le premier flux de son type est le seul repli qui ait un sens —
    reprendre le tid tel quel viserait un flux choisi au hasard.
    """
    from core import muxer
    monkeypatch.setattr(muxer, "identify", lambda _p: [])
    p = tmp_path / "muet.mkv"
    p.write_bytes(b"")
    sync.measure_external_track(tmp_path / "film.mkv",
                                _piste(p, 3, TrackKind.AUDIO))
    assert appels["index"] == 0
