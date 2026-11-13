"""
tests/test_geometrie.py — Orientation, fichier sans image, définition
affichée (IE-186).

Constats de la revue du 2026-11-13 :

- **CR-114** — une vidéo verticale 1080×1920 passait pour de la 4K : réduite à
  608×1080 sans `keep_4k`, jugée au débit 4K avec ;
- **CR-129** — un fichier sans flux vidéo recevait une décision d'encodage ;
- **CR-140** — l'écran affichait le cadre maximal (« 1280x720 » pour un
  720×480) au lieu de la définition produite.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core import scanner
from core.decision import VideoAction, decide
from core.encoder import definition_sortie
from core.i18n import ErreurAffichable
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo


def _profile(**over) -> Profile:
    data = {
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps": 12000, "keep_4k": False,
        "audio_languages": ["fre", "eng"], "audio_copy_compatible": True,
        "preserve_hd_audio": False, "audio_stereo_kbps": 192,
        "audio_surround_kbps": 448, "dolby_vision": "hdr10",
    }
    data.update(over)
    return Profile(id="test", data=data)


def _source(tmp_path: Path, largeur: int, hauteur: int, *,
            bitrate=6_000_000, sar="") -> VideoInfo:
    p = tmp_path / "Clip.mkv"
    p.write_bytes(b"")
    return VideoInfo(
        path=p, width=largeur, height=hauteur, bitrate=bitrate, codec="h264",
        duration=60.0, frame_count=0, dv_profile=None, sar=sar,
        audio_tracks=[AudioTrack(index=0, codec="aac", channels=2,
                                 language="fre", title="", bitrate=128_000)],
    )


# ─── CR-114 : une vidéo verticale ─────────────────────────────────────────────

def test_un_1080_vertical_garde_sa_définition(tmp_path):
    vid = decide(_source(tmp_path, 1080, 1920), _profile()).video
    assert (vid.target_width, vid.target_height) == (1080, 1920)
    assert vid.target_bitrate == 5_000_000


def test_un_1080_vertical_est_jugé_à_la_tranche_1080p(tmp_path):
    """Avec `keep_4k`, la tranche 4K (12 000k) le laissait en SKIP."""
    vid = decide(_source(tmp_path, 1080, 1920), _profile(keep_4k=True)).video
    assert vid.target_bitrate == 5_000_000
    assert vid.action != VideoAction.SKIP


def test_une_4k_verticale_se_réduit_dans_son_orientation(tmp_path):
    vid = decide(_source(tmp_path, 2160, 3840, bitrate=30_000_000), _profile()).video
    assert (vid.target_width, vid.target_height) == (1080, 1920)


def test_une_sd_verticale_garde_son_orientation(tmp_path):
    vid = decide(_source(tmp_path, 480, 854), _profile()).video
    assert (vid.target_width, vid.target_height) == (720, 1280)


@pytest.mark.parametrize("dims, quatre_k", [
    ((3840, 2160), True), ((3832, 1600), True), ((1920, 1080), False),
    ((2048, 1080), False), ((1080, 1920), False), ((2160, 3840), True)])
def test_le_classement_4k(tmp_path, dims, quatre_k):
    assert _source(tmp_path, *dims).is_4k is quatre_k


# ─── CR-129 : un fichier sans image ───────────────────────────────────────────

def test_un_fichier_audio_seul_est_illisible(tmp_path, monkeypatch):
    p = tmp_path / "Concert.mp4"
    p.write_bytes(b"")
    monkeypatch.setattr(scanner, "_ffprobe_json", lambda args, outil=None: {
        "streams": [{"index": 0, "codec_type": "audio", "codec_name": "aac",
                     "channels": 2}],
        "format": {"duration": "60.0", "bit_rate": "128000"}})
    with pytest.raises(ErreurAffichable, match="no video stream"):
        scanner.scan(p)


# ─── CR-140 : la définition affichée ──────────────────────────────────────────

def test_une_sd_s_affiche_dans_sa_définition(tmp_path):
    info = _source(tmp_path, 720, 480)
    assert definition_sortie(info, decide(info, _profile()).video) == (720, 480)


def test_une_sd_anamorphique_s_affiche_en_pixels_carrés(tmp_path):
    info = _source(tmp_path, 720, 480, sar="32:27")
    assert definition_sortie(info, decide(info, _profile()).video) == (852, 480)


def test_une_4k_scope_réduite_s_affiche_réduite(tmp_path):
    info = _source(tmp_path, 3832, 1600, bitrate=30_000_000)
    assert definition_sortie(info, decide(info, _profile()).video) == (1920, 802)
