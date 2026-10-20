"""
tests/test_flux_mpeg_abimes.py — Un `.ts` dont l'audio a un trou s'encode.

Le cas réel : trois enregistrements IPTV de « La petite histoire de France »,
chacun avec un paquet audio AAC tronqué peu avant la fin. Recopiée en MP4,
l'AAC passe par le filtre `aac_adtstoasc`, qui bute sur l'en-tête ADTS de ce
paquet : « Error parsing ADTS frame header! », puis « Conversion failed! ». Un
seul paquet abîmé faisait échouer tout l'encodage.

`-fflags +discardcorrupt` fait écarter par le démuxeur les paquets qu'il a
lui-même marqués corrompus : on perd ce qui était déjà illisible, rien d'autre.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from core.decision import decide
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo

_DRAPEAU = ["-fflags", "+discardcorrupt"]


def _profile() -> Profile:
    return Profile(id="test", data={
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 2500,
        "bitrate_4k_kbps": 5000, "audio_languages": ["fre"],
        "audio_copy_compatible": True, "preserve_hd_audio": False,
        "container": "auto",
    })


def _plateforme():
    from core.platform import GPU, OS, PlatformProfile
    return PlatformProfile(os=OS.WINDOWS, gpu=GPU.NONE, hwaccel=None,
                           encoder_hevc="libx265", encoder_h264="libx264",
                           encoder_av1="libsvtav1")


def _info(source: Path) -> VideoInfo:
    return VideoInfo(
        path=source, width=1280, height=720, bitrate=3_400_000, codec="h264",
        duration=180.0, frame_count=0, dv_profile=None,
        audio_tracks=[AudioTrack(index=0, codec="aac", channels=2,
                                 language="fre", title="", bitrate=96_000)],
        subtitle_tracks=[],
    )


def _avant_la_source(cmd: list[str], source: Path) -> list[str]:
    """Les options posées juste avant le `-i` de la source."""
    i = cmd.index(str(source))
    assert cmd[i - 1] == "-i"
    return cmd[i - 3:i - 1]


# ─── La commande ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("nom", ["emission.ts", "EMISSION.TS", "clip.m2ts",
                                 "clip.mts", "dvd.vob", "film.mpg"])
def test_un_flux_mpeg_est_lu_en_ecartant_les_paquets_corrompus(tmp_path, nom):
    from core.encoder import build_command
    source = tmp_path / nom
    cmd = build_command(decide(_info(source), _profile()), _plateforme())
    assert _avant_la_source(cmd, source) == _DRAPEAU


@pytest.mark.parametrize("nom", ["film.mkv", "film.mp4"])
def test_les_autres_conteneurs_ne_changent_pas(tmp_path, nom):
    from core.encoder import build_command
    source = tmp_path / nom
    assert "+discardcorrupt" not in build_command(
        decide(_info(source), _profile()), _plateforme())


def test_la_passe_audio_a_part_lit_aussi_le_flux_avec_tolerance(tmp_path):
    from core.encoder import build_audio_command
    source = tmp_path / "emission.ts"
    dec = decide(_info(source), _profile())
    cmd = build_audio_command(source, tmp_path / "a.mka", dec.audio)
    assert _avant_la_source(cmd, source) == _DRAPEAU


# ─── Le comportement, sur un vrai fichier ─────────────────────────────────────

@pytest.fixture(scope="module")
def ffmpeg() -> str:
    from core.config import get_bin_dir, load
    from core.preflight import get_tool_path
    chemin = get_tool_path("ffmpeg", get_bin_dir(load()))
    if not chemin:
        pytest.skip("ffmpeg introuvable")
    return chemin


def _ts_au_paquet_audio_manquant(ffmpeg: str, dossier: Path) -> Path:
    """Un `.ts` H.264 + AAC dont un paquet TS audio, au milieu d'un PES, a
    disparu — ce que laisse une réception IPTV ou TNT qui décroche."""
    complet = dossier / "complet.ts"
    subprocess.run(
        [ffmpeg, "-v", "error", "-y",
         "-f", "lavfi", "-i", "testsrc=s=320x240:r=25:d=3",
         "-f", "lavfi", "-i", "sine=d=3:sample_rate=48000",
         "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
         "-f", "mpegts", str(complet)],
        check=True, capture_output=True)
    data = complet.read_bytes()
    paquets = [data[i:i + 188] for i in range(0, len(data), 188)]
    pid = lambda p: ((p[1] & 0x1F) << 8) | p[2]
    pid_audio = 0x101                      # le PID audio par défaut de ffmpeg
    suites = [i for i, p in enumerate(paquets)
              if pid(p) == pid_audio and not p[1] & 0x40]   # hors début de PES
    assert suites, "aucun paquet audio dans le flux de test"
    trou = suites[len(suites) // 2]
    abime = dossier / "abime.ts"
    abime.write_bytes(b"".join(p for i, p in enumerate(paquets) if i != trou))
    return abime


def test_un_ts_a_l_audio_abimee_s_encode(tmp_path, ffmpeg):
    """Sans le correctif, ffmpeg s'arrête sur « Error parsing ADTS frame
    header! » ; avec, le fichier sort, audio comprise."""
    from core.encoder import build_command
    source = _ts_au_paquet_audio_manquant(ffmpeg, tmp_path)
    dec = decide(_info(source), _profile())
    dec.output_dir = tmp_path / "sortie"
    dec.output_dir.mkdir()
    cmd = build_command(dec, _plateforme())
    cmd[0] = ffmpeg
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    erreurs = [l for l in r.stderr.splitlines() if "rror" in l]
    assert r.returncode == 0, "\n".join(erreurs[:6])
    assert dec.output_path.stat().st_size > 0
