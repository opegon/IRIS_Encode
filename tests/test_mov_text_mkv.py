"""
tests/test_mov_text_mkv.py — Un `mov_text` vers Matroska (IE-188, CR-117).

Le Matroska ne porte pas le `mov_text` d'un MP4 : recopié (`-c:s copy`),
ffmpeg refusait d'écrire la sortie — « Subtitle codec mov_text is not
supported », mesuré en 6.1.1 et 8.1.2. La piste passe en SubRip, seule.
"""
from __future__ import annotations

from pathlib import Path

from core import muxer, scanner
from core.decision import decide, force_skip_to_encode
from core.encoder import build_command
from core.muxer import ExternalTrack, TrackKind
from core.profiles import Profile
from core.scanner import AudioTrack, SubtitleTrack, VideoInfo
from tests.test_greffes_encodage import (_encoder, _ff, _plat, _repliques,  # noqa: F401
                                         outils, vrais_outils)


def _profil_mkv() -> Profile:
    return Profile(id="test", data={
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps": 8000, "audio_languages": ["fre", "eng"],
        "audio_copy_compatible": True, "preserve_hd_audio": False,
        "preset_encoder": "ultrafast", "container": "mkv",
    })


def _info(tmp_path: Path, sous_titres) -> VideoInfo:
    p = tmp_path / "film.mp4"
    p.write_bytes(b"")
    return VideoInfo(
        path=p, width=1920, height=1080, bitrate=20_000_000, codec="h264",
        duration=60.0, frame_count=0, dv_profile=None,
        audio_tracks=[AudioTrack(index=0, codec="aac", channels=2,
                                 language="fre", title="", bitrate=128_000)],
        subtitle_tracks=sous_titres)


def _apres(cmd: list[str], option: str) -> list[str]:
    return [cmd[i + 1] for i, a in enumerate(cmd[:-1]) if a == option]


def test_seule_la_piste_mov_text_passe_en_srt(tmp_path):
    dec = decide(_info(tmp_path, [SubtitleTrack(0, "ass", "fre"),
                                  SubtitleTrack(1, "mov_text", "eng")]),
                 _profil_mkv())
    cmd = build_command(force_skip_to_encode(dec), _plat())
    assert dec.output_container == ".mkv"
    assert _apres(cmd, "-c:s:1") == ["srt"]
    assert _apres(cmd, "-c:s:0") == [], "l'ASS se recopie, styles compris"


def test_un_donneur_mp4_greffé_passe_en_srt(tmp_path, monkeypatch):
    """mkvmerge nomme « Timed Text » le `mov_text` d'un donneur."""
    dec = force_skip_to_encode(decide(_info(tmp_path, [SubtitleTrack(0, "subrip", "fre")]),
                                      _profil_mkv()))
    donneur = tmp_path / "vo.mp4"
    donneur.write_bytes(b"")
    dec.external_tracks.append(ExternalTrack(source_path=donneur, source_tid=0,
                                             kind=TrackKind.SUBTITLE,
                                             codec="Timed Text", language="eng"))
    monkeypatch.setattr(muxer, "ffmpeg_stream_index", lambda *_a, **_kw: 0)
    cmd = build_command(dec, _plat())
    assert _apres(cmd, "-c:s:1") == ["srt"]
    assert _apres(cmd, "-c:s:0") == []


@outils
def test_un_mp4_à_mov_text_s_encode_en_mkv(tmp_path, vrais_outils):
    srt = tmp_path / "st.srt"
    srt.write_text("1\n00:00:00,200 --> 00:00:01,200\nÉté à Paris\n", encoding="utf-8")
    source = tmp_path / "film.mp4"
    _ff("-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=25:duration=2",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-i", str(srt),
        "-map", "0", "-map", "1", "-map", "2", "-c:v", "libx264",
        "-preset", "ultrafast", "-b:v", "20M", "-c:a", "aac",
        "-c:s", "mov_text", "-metadata:s:s:0", "language=fre", str(source))
    dec = force_skip_to_encode(decide(scanner.scan(source), _profil_mkv()))
    assert dec.output_container == ".mkv"
    _encoder(dec)
    assert "Été à Paris" in _repliques(dec.output_path)
