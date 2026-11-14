"""
tests/test_titre_sortie.py — La sortie ne reprend pas le titre de la source
(IE-198).

ffmpeg et mkvmerge recopient par défaut le titre global de la source. Celui
d'une release le décrit, elle : une sortie 1080p HDR10 annonçait « … 2160p
DOLBY VISION HDR10+ … x265-QTZ ». Sans titre, le lecteur affiche le nom du
fichier, qui reste juste. Les titres de piste, eux, restent.

L'avertissement « UDTA parsing failed retrying raw » que ffmpeg 8.1.2 donne en
relisant ces MP4 vient du titre d'une piste (boîte `name`), pas du titre
global, et le titre est bien relu (mesuré le 2026-11-14) : il n'est pas visé.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from core import dovi, encoder, muxer, scanner
from core.decision import decide, force_skip_to_encode
from core.encoder import build_command
from core.platform import GPU, OS, PlatformProfile
from core.profiles import Profile

from tests.outils_reels import outil  # noqa: E402

_FFMPEG, _FFPROBE, _MKVMERGE = outil("ffmpeg"), outil("ffprobe"), outil("mkvmerge")
outils = pytest.mark.skipif(
    not (_FFMPEG.exists() and _FFPROBE.exists() and _MKVMERGE.exists()),
    reason="outils du projet absents")

TITRE = "Alien 1979 2160p 10bit 4KLight DOLBY VISION HDR10+ BluRay DDP 5.1 x265-QTZ"
PISTE = "Français 5.1"


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


def _run(cmd: list[str], codes: tuple[int, ...] = (0,)) -> None:
    """mkvmerge rend 1 pour de simples avertissements : `codes=(0, 1)`."""
    r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode in codes, r.stdout[-800:] + r.stderr[-800:]


def _sonde(chemin: Path) -> dict:
    r = subprocess.run([str(_FFPROBE), "-v", "error", "-show_entries",
                        "format_tags:stream=codec_type:stream_tags", "-of", "json",
                        str(chemin)],
                       capture_output=True, encoding="utf-8", check=True)
    return json.loads(r.stdout)


def _titre_global(chemin: Path) -> str | None:
    return _sonde(chemin)["format"].get("tags", {}).get("title")


def _titre_audio(chemin: Path) -> str | None:
    """Le MP4 relit le titre d'une piste sous `name`, le Matroska sous `title`."""
    audio = [s for s in _sonde(chemin)["streams"] if s["codec_type"] == "audio"][0]
    tags = audio.get("tags", {})
    return tags.get("title") or tags.get("name")


def _source(tmp_path: Path, codec_v: str = "libx264") -> Path:
    """Un Matroska titré comme une release, avec une piste audio nommée."""
    source = tmp_path / "source.mkv"
    subprocess.run([str(_FFMPEG), "-y", "-loglevel", "error",
                    "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=25:duration=2",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-c:v", codec_v, "-preset", "ultrafast", "-b:v", "8M",
                    *(["-x265-params", "log-level=none"] if codec_v == "libx265" else []),
                    "-c:a", "aac", "-metadata", f"title={TITRE}",
                    "-metadata:s:a:0", f"title={PISTE}", "-metadata:s:a:0", "language=fre",
                    str(source)],
                   check=True, stdin=subprocess.DEVNULL, capture_output=True)
    assert _titre_global(source) == TITRE, "prémisse : la source est titrée"
    return source


@pytest.fixture
def chemins():
    encoder.set_ffmpeg_path(str(_FFMPEG))
    scanner.set_ffprobe_path(str(_FFPROBE))
    muxer.set_mkvmerge_path(str(_MKVMERGE))


# ─── Encodage (build_command) ─────────────────────────────────────────────────

@outils
@pytest.mark.parametrize("conteneur", ["mkv", "mp4"])
def test_l_encodage_ne_reprend_pas_le_titre_de_la_source(tmp_path, chemins, conteneur):
    source = _source(tmp_path)
    dec = force_skip_to_encode(decide(scanner.scan(source),
                                      _profil(container=conteneur)))
    assert dec.output_container == f".{conteneur}"
    _run(build_command(dec, _plat()))
    assert _titre_global(dec.output_path) is None
    assert _titre_audio(dec.output_path) == PISTE, "le titre de piste reste"


# ─── Passes Dolby Vision ──────────────────────────────────────────────────────

@outils
def test_le_remux_mkvmerge_ne_reprend_pas_le_titre(tmp_path, chemins):
    """`build_strip_command` : flux HEVC brut + pistes de la source."""
    source = _source(tmp_path, "libx265")
    brut = tmp_path / "video.hevc"
    subprocess.run([str(_FFMPEG), "-y", "-loglevel", "error", "-i", str(source),
                    "-map", "0:v", "-c", "copy", "-bsf:v", "hevc_mp4toannexb",
                    str(brut)], check=True, capture_output=True)
    sortie = tmp_path / "sortie.mkv"
    _run(muxer.build_strip_command(brut, source, sortie, fps="25/1"), codes=(0, 1))
    assert _titre_global(sortie) is None
    assert _titre_audio(sortie) == PISTE


@outils
def test_le_retrait_vers_mp4_ne_reprend_pas_le_titre(tmp_path, chemins):
    """`build_strip_mp4` : une passe ffmpeg depuis la source."""
    if not dovi.strip_bsf_disponible(str(_FFMPEG)):
        pytest.skip("ffmpeg sans le filtre dovi_rpu")
    source = _source(tmp_path, "libx265")
    sortie = tmp_path / "sortie.mp4"
    _run(dovi.build_strip_mp4(source, sortie, [], ffmpeg_path=str(_FFMPEG)))
    assert _titre_global(sortie) is None
    assert _titre_audio(sortie) == PISTE


@outils
def test_le_remux_mp4_du_reencodage_dv_ne_reprend_pas_le_titre(tmp_path, chemins):
    """`build_dv_mp4_remux` : le Matroska recomposé passe en MP4."""
    mkv = _source(tmp_path, "libx265")
    sortie = tmp_path / "sortie.mp4"
    _run(dovi.build_dv_mp4_remux(mkv, sortie, ffmpeg_path=str(_FFMPEG)))
    assert _titre_global(sortie) is None
    assert _titre_audio(sortie) == PISTE
