"""
tests/test_statistiques_perimees.py — Une piste réencodée ne garde pas les
statistiques de sa source (IE-199).

mkvmerge pose sur chaque piste des tags `BPS`, `NUMBER_OF_BYTES`… exacts au
moment où il les écrit. ffmpeg les recopie tels quels quand il réencode
(mesuré en 8.1.2) : une sortie HEVC à 500k annonçait encore les 2 883k de sa
source H264. Au scan suivant, ce débit-là fait repartir la sortie en
réencodage. Une piste recopiée, elle, garde des statistiques justes : elles
restent.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from core import encoder, muxer, scanner
from core.decision import AudioAction, AudioDecision, decide, force_skip_to_encode
from core.encoder import audio_args, build_command, encodeur_de
from core.platform import GPU, OS, PlatformProfile
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo

from tests.outils_reels import outil  # noqa: E402

_FFMPEG, _FFPROBE, _MKVMERGE = outil("ffmpeg"), outil("ffprobe"), outil("mkvmerge")
outils = pytest.mark.skipif(
    not (_FFMPEG.exists() and _FFPROBE.exists() and _MKVMERGE.exists()),
    reason="outils du projet absents")


def _plat() -> PlatformProfile:
    return PlatformProfile(os=OS.WINDOWS, gpu=GPU.NONE, hwaccel=None,
                           encoder_hevc="libx265", encoder_h264="libx264",
                           encoder_av1="libaom-av1")


def _profil(**extra) -> Profile:
    return Profile(id="test", data={
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps": 8000, "audio_languages": ["fre", "eng"],
        "audio_copy_compatible": True, "preserve_hd_audio": False,
        "preset_encoder": "ultrafast", **extra})


def _piste(index: int, codec: str) -> AudioTrack:
    return AudioTrack(index=index, codec=codec, channels=6, language="fre",
                      title="", bitrate=640_000)


def _effacees(cmd: list[str], spec: str) -> set[str]:
    """Les tags que la commande vide sur le flux `spec` (« v:0 », « a:1 »)."""
    return {cmd[i + 1].rstrip("=") for i, x in enumerate(cmd)
            if x == f"-metadata:s:{spec}" and cmd[i + 1].endswith("=")}


# ─── Les arguments ────────────────────────────────────────────────────────────

def test_une_piste_audio_transcodee_perd_ses_statistiques():
    copie = AudioDecision(track=_piste(0, "ac3"), action=AudioAction.COPY,
                          reason="", output_codec="copy", output_bitrate=0)
    transcodee = AudioDecision(track=_piste(1, "truehd"),
                               action=AudioAction.TRANSCODE, reason="",
                               output_codec="eac3", output_bitrate=640_000)
    args = audio_args([copie, transcodee])
    assert {"BPS", "NUMBER_OF_BYTES"} <= _effacees(args, "a:1"), args
    assert not _effacees(args, "a:0"), "une recopie garde des statistiques justes"


def test_une_video_recopiee_garde_ses_statistiques(tmp_path):
    """Un remux pour l'audio seul : la vidéo traverse intacte, son `BPS` aussi."""
    p = tmp_path / "film.mkv"
    p.write_bytes(b"")
    info = VideoInfo(path=p, width=1920, height=1080, bitrate=3_000_000,
                     codec="h264", duration=3600.0, frame_count=0,
                     dv_profile=None, audio_tracks=[_piste(0, "dts")],
                     subtitle_tracks=[])
    cmd = build_command(decide(info, _profil()), _plat())
    assert encodeur_de(cmd) == "copy", "prémisse : la vidéo est recopiée"
    assert not _effacees(cmd, "v:0"), cmd


# ─── De bout en bout ──────────────────────────────────────────────────────────

def _tags(chemin: Path, spec: str) -> dict:
    r = subprocess.run([str(_FFPROBE), "-v", "error", "-select_streams", spec,
                        "-show_entries", "stream_tags", "-of", "json",
                        str(chemin)],
                       capture_output=True, encoding="utf-8", check=True)
    return json.loads(r.stdout)["streams"][0].get("tags", {})


@outils
def test_la_sortie_n_annonce_plus_le_debit_de_sa_source(tmp_path):
    encoder.set_ffmpeg_path(str(_FFMPEG))
    scanner.set_ffprobe_path(str(_FFPROBE))
    muxer.set_mkvmerge_path(str(_MKVMERGE))

    brut = tmp_path / "brut.mkv"
    subprocess.run([str(_FFMPEG), "-y", "-loglevel", "error",
                    "-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=25:duration=2",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "20M",
                    "-c:a", "aac", str(brut)],
                   check=True, stdin=subprocess.DEVNULL, capture_output=True)
    source = tmp_path / "source.mkv"
    subprocess.run([str(_MKVMERGE), "-q", "-o", str(source), str(brut)],
                   check=True, capture_output=True)
    assert "BPS" in _tags(source, "v:0"), "prémisse : mkvmerge a posé ses tags"

    # Le Matroska : le MP4 ne porte pas ces tags, il ne prouverait rien.
    dec = force_skip_to_encode(decide(scanner.scan(source),
                                      _profil(container="mkv")))
    assert dec.output_container == ".mkv"
    r = subprocess.run(build_command(dec, _plat()), stdin=subprocess.DEVNULL,
                       capture_output=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr[-800:]

    video = _tags(dec.output_path, "v:0")
    assert "BPS" not in video and "NUMBER_OF_BYTES" not in video, video
    # L'AAC est recopié : ses statistiques restent justes, et restent.
    assert dec.audio[0].action == AudioAction.COPY
    assert "BPS" in _tags(dec.output_path, "a:0")
