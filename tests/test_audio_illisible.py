"""Une piste audio sans décodeur est écartée.

1883 S01E06 (release WEB, 2026-11-09) : la piste anglaise est restée chiffrée
(étiquette « enca »), ffprobe la dit `unknown`. Le profil la transcodait en
AAC et ffmpeg s'arrêtait avant la première image : « Decoding requested, but
no decoder found » puis « Error opening output files: Invalid argument ».
"""
from __future__ import annotations

from pathlib import Path

from core.decision import AudioAction, decide_audio
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo


def _track(index: int, codec: str, language: str) -> AudioTrack:
    return AudioTrack(index=index, codec=codec, channels=2, language=language,
                      title="", bitrate=224_000 if codec != "unknown" else 0)


def _info(tmp_path: Path, tracks: list[AudioTrack]) -> VideoInfo:
    p = tmp_path / "serie.mkv"
    p.write_bytes(b"")
    return VideoInfo(path=p, width=1920, height=1080, bitrate=5_000_000,
                     codec="hevc", duration=3078.0, frame_count=73800,
                     dv_profile=None, audio_tracks=tracks)


def _profile() -> Profile:
    return Profile(id="test", data={
        "audio_languages": ["fre", "eng"], "audio_stereo_kbps": 192,
        "audio_surround_kbps": 448, "audio_copy_compatible": True,
        "preserve_hd_audio": False, "audio_hd_codec": "none",
    })


def _pistes_1883(tmp_path):
    return _info(tmp_path, [_track(0, "unknown", "eng"), _track(1, "eac3", "fre")])


def test_piste_sans_decodeur_ecartee(tmp_path):
    chiffree, francaise = decide_audio(_pistes_1883(tmp_path), _profile())
    assert chiffree.action == AudioAction.EXCLUDE
    assert francaise.action == AudioAction.COPY


def test_role_original_passe_a_la_premiere_piste_lisible(tmp_path):
    chiffree, francaise = decide_audio(_pistes_1883(tmp_path), _profile())
    assert not chiffree.locked
    assert francaise.locked


def test_selection_manuelle_ne_la_reprend_pas(tmp_path):
    chiffree, francaise = decide_audio(_pistes_1883(tmp_path), _profile(),
                                       override_selected=[0, 1])
    assert chiffree.action == AudioAction.EXCLUDE
    assert francaise.action == AudioAction.COPY
