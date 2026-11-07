"""
tests/test_ocr_decision.py — Quels PGS passent à l'OCR (IE-176).

Un PGS que la sortie garde, en français ou en anglais, forcé ou non, devient
un SRT quand seconv est installé ; il fait alors remuxer une vidéo qui aurait
été laissée telle quelle. Sans seconv, rien ne change.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core import ocr
from core.decision import VideoAction, decide, libelle_ocr, ocr_prevu
from core.profiles import Profile
from core.scanner import AudioTrack, SubtitleTrack, VideoInfo


def _profil(**extra) -> Profile:
    return Profile(id="t", data={"bitrate_1080p_kbps": 5000,
                                 "bitrate_720p_kbps": 2000,
                                 "audio_languages": ["fre", "eng"], **extra})


def _info(tmp_path: Path, sous_titres, dv=None, bitrate=3_000_000) -> VideoInfo:
    p = tmp_path / "Film.1080p.mkv"
    p.write_bytes(b"")
    return VideoInfo(
        path=p, width=1920, height=1080, bitrate=bitrate, codec="hevc",
        duration=5400.0, frame_count=0, dv_profile=dv,
        audio_tracks=[AudioTrack(index=0, codec="ac3", channels=6,
                                 language="fre", title="", bitrate=640_000)],
        subtitle_tracks=list(sous_titres))


def _pgs(index, langue="fre", **kw) -> SubtitleTrack:
    return SubtitleTrack(index=index, codec="hdmv_pgs_subtitle", language=langue, **kw)


@pytest.fixture
def seconv():
    ocr.set_seconv(Path("seconv.exe"))
    yield
    ocr.set_seconv(None)


def test_un_pgs_seul_fait_remuxer(tmp_path, seconv):
    dec = decide(_info(tmp_path, [_pgs(0)]), _profil())
    assert [st.index for st in dec.sous_titres_ocr] == [0]
    assert dec.video.action == VideoAction.REMUX
    assert "PGS" in dec.video.reason


def test_sans_seconv_rien_ne_change(tmp_path):
    dec = decide(_info(tmp_path, [_pgs(0)]), _profil())
    assert dec.sous_titres_ocr == []
    assert dec.video.action == VideoAction.SKIP


def test_forces_aussi(tmp_path, seconv):
    st = [_pgs(0, forced=True), _pgs(1, title="FR Full")]
    dec = decide(_info(tmp_path, st), _profil())
    assert [s.index for s in dec.sous_titres_ocr] == [0, 1]


def test_francais_et_anglais_seulement(tmp_path, seconv):
    st = [_pgs(0, "fra"), _pgs(1, "eng"), _pgs(2, "ger"), _pgs(3, "")]
    dec = decide(_info(tmp_path, st), _profil())
    assert [s.index for s in dec.sous_titres_ocr] == [0, 1]


def test_pgs_double_ecarte_pas_d_ocr(tmp_path, seconv):
    """Un SRT de même langue et de même nature le double : il part, comme
    avant, et l'OCR n'a rien à faire."""
    st = [_pgs(0), SubtitleTrack(index=1, codec="subrip", language="fre")]
    dec = decide(_info(tmp_path, st), _profil())
    assert dec.sous_titres_ocr == []
    assert [s.index for s in dec.subtitles_finales] == [1]


def test_piste_ecartee_par_la_langue_pas_d_ocr(tmp_path, seconv):
    dec = decide(_info(tmp_path, [_pgs(0, "eng")]),
                 _profil(subtitle_languages=["fre"]))
    assert dec.sous_titres_ocr == []


def test_vobsub_pas_d_ocr(tmp_path, seconv):
    st = [SubtitleTrack(index=0, codec="dvd_subtitle", language="fre")]
    assert decide(_info(tmp_path, st), _profil()).sous_titres_ocr == []


def test_reencodage_aussi(tmp_path, seconv):
    """Pas seulement le remux : un fichier réencodé convertit son PGS."""
    dec = decide(_info(tmp_path, [_pgs(0)], bitrate=20_000_000), _profil())
    assert dec.video.action == VideoAction.ENCODE_HEVC
    assert [s.index for s in dec.sous_titres_ocr] == [0]


def test_retrait_dv_seul_pas_d_ocr(tmp_path, seconv, monkeypatch):
    """Le retrait du RPU écrit la sortie sans ffmpeg : l'OCR n'y passe pas,
    et l'affichage ne doit pas le promettre."""
    from core import decision
    monkeypatch.setattr(decision, "_STRIP_DV_AVAILABLE", True)
    info = _info(tmp_path, [_pgs(0)], dv=8)
    info.dv_bl_compat = 1
    info.color_transfer = "smpte2084"
    dec = decide(info, _profil(dolby_vision="hdr10"))
    assert dec.video.action == VideoAction.STRIP_DV
    assert dec.sous_titres_ocr == []
    assert not ocr_prevu(dec, info.subtitle_tracks[0])


def test_libelle():
    assert "SRT" in libelle_ocr() and "OCR" in libelle_ocr()
