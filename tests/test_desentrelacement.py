"""
tests/test_desentrelacement.py — Les sources entrelacées sont désentrelacées (IE-122).

Arbitrages de l'utilisateur : la décision suit les **marqueurs** du flux
(`field_order`), sans sondage de l'image ; la sortie garde la **cadence** de la
source (bwdif `send_frame`). `deint=interlaced` laisse intactes les images
qu'une source mixte marque progressives.

Mesuré sur le DVD d'essai (`field_order=tt`) : 30 s encodées en H.264 NVENC à
3 Mb/s, l'image sort sans peignes ; `idet` image par image n'en trouve plus
qu'une sur 899 (686 sans le filtre).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.decision import VideoAction, decide
from core.encoder import FILTRE_DESENTRELACEMENT, build_command
from core.platform import GPU, OS, PlatformProfile
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo

PLAT = PlatformProfile(os=OS.WINDOWS, gpu=GPU.NONE, hwaccel=None, encoder_hevc="libx265",
                       encoder_h264="libx264", encoder_av1="libsvtav1")


def _info(field_order: str, width: int = 720, height: int = 480,
          codec: str = "mpeg2video", bitrate: int = 8_000_000) -> VideoInfo:
    return VideoInfo(
        path=Path("/films/concert.vob"), width=width, height=height, bitrate=bitrate,
        codec=codec, duration=3600.0, frame_count=0, dv_profile=None,
        audio_tracks=[AudioTrack(index=0, codec="ac3", channels=2, language="eng",
                                 title="", bitrate=192_000)],
        field_order=field_order,
    )


def _profile(**extra) -> Profile:
    return Profile(id="test", data={
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps": 12000, "keep_4k": False,
        "audio_languages": ["eng"], "audio_copy_compatible": True, **extra,
    })


def _filtre(cmd: list[str]) -> str:
    return cmd[cmd.index("-vf") + 1] if "-vf" in cmd else ""


# ─── Les marqueurs ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ordre", ["tt", "bb", "tb", "bt"])
def test_un_ordre_de_trames_dit_entrelacé(ordre):
    assert _info(ordre).entrelace


@pytest.mark.parametrize("ordre", ["progressive", "", "unknown"])
def test_progressif_ou_muet_ne_l_est_pas(ordre):
    """Une source qui se dit progressive l'est pour l'application — même un
    enregistrement TNT dont des passages ne le sont pas (choix assumé)."""
    assert not _info(ordre).entrelace


def test_le_scan_lit_l_ordre_des_trames(monkeypatch):
    from core import scanner
    monkeypatch.setattr(scanner, "_ffprobe_json", lambda args, outil=None: {
        "streams": [{"codec_type": "video", "codec_name": "mpeg2video", "width": 720,
                     "height": 480, "field_order": "tt", "r_frame_rate": "30000/1001"}],
        "format": {"duration": "60", "bit_rate": "6000000"}})
    monkeypatch.setattr(scanner, "_detect_dv", lambda p: (None, None))
    assert scanner.scan(Path("/x/VTS_01_1.VOB")).field_order == "tt"


# ─── La décision ──────────────────────────────────────────────────────────────

def test_une_source_entrelacée_réencodée_est_désentrelacée():
    dec = decide(_info("tt"), _profile())
    assert dec.video.action != VideoAction.SKIP
    assert dec.desentrelace


def test_une_source_progressive_ne_l_est_pas():
    assert not decide(_info("progressive"), _profile()).desentrelace


def test_une_source_gardée_telle_quelle_ne_l_est_pas():
    """SKIP : rien n'est recalculé, rien n'est désentrelacé."""
    dec = decide(_info("tt", codec="hevc", bitrate=500_000), _profile())
    assert dec.video.action == VideoAction.SKIP
    assert not dec.desentrelace


# ─── La commande ──────────────────────────────────────────────────────────────

def test_bwdif_garde_la_cadence_et_ne_touche_que_l_entrelacé():
    assert "bwdif" in FILTRE_DESENTRELACEMENT
    assert "mode=send_frame" in FILTRE_DESENTRELACEMENT
    assert "deint=interlaced" in FILTRE_DESENTRELACEMENT
    assert "parity=auto" in FILTRE_DESENTRELACEMENT


def test_la_commande_désentrelace():
    cmd = build_command(decide(_info("tt"), _profile()), PLAT)
    assert _filtre(cmd).startswith(FILTRE_DESENTRELACEMENT)


def test_le_désentrelacement_précède_la_mise_à_l_échelle():
    """Réduire des trames mêlées les mélange : bwdif d'abord."""
    dec = decide(_info("tt", width=3840, height=2160, codec="h264",
                       bitrate=60_000_000), _profile())
    filtres = _filtre(build_command(dec, PLAT)).split(",")
    assert filtres[0] == FILTRE_DESENTRELACEMENT
    assert any(f.startswith("scale=") for f in filtres[1:])


def test_une_source_progressive_n_a_pas_de_bwdif():
    cmd = build_command(decide(_info("progressive"), _profile()), PLAT)
    assert "bwdif" not in " ".join(cmd)
