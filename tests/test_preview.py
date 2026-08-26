"""
tests/test_preview.py — Tests unitaires de core/preview.py

Construction de la commande mpv uniquement : aucun lecteur n'est lancé.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core import preview
from core.muxer import ExternalTrack, TrackKind


@pytest.fixture(autouse=True)
def fake_mpv():
    """mpv réputé disponible pour toute la construction de commandes."""
    preview.set_mpv_path("mpv")
    yield
    preview.set_mpv_path(None)


def _sub(delay_ms: int = 0) -> ExternalTrack:
    return ExternalTrack(source_path=Path("/films/film.fr.srt"), source_tid=0,
                         kind=TrackKind.SUBTITLE, codec="SubRip/SRT",
                         language="fre", delay_ms=delay_ms)


def _audio(delay_ms: int = 0) -> ExternalTrack:
    return ExternalTrack(source_path=Path("/films/film.VF.mka"), source_tid=1,
                         kind=TrackKind.AUDIO, codec="E-AC-3",
                         language="fre", delay_ms=delay_ms)


def _opt(cmd: list[str], prefix: str) -> str:
    return next(a for a in cmd if a.startswith(prefix))


# ─── Disponibilité ────────────────────────────────────────────────────────────

def test_unavailable_without_mpv():
    preview.set_mpv_path(None)
    assert not preview.available()
    with pytest.raises(RuntimeError):
        preview.build_command(Path("/films/f.mkv"), _sub())


# ─── Sous-titres ──────────────────────────────────────────────────────────────

def test_subtitle_command_carries_delay_in_seconds():
    """mpv attend des secondes là où la TUI raisonne en millisecondes."""
    cmd = preview.build_command(Path("/films/f.mkv"), _sub(delay_ms=-2450))
    assert _opt(cmd, "--sub-delay=") == "--sub-delay=-2.450"
    assert _opt(cmd, "--sub-file=").endswith("film.fr.srt")
    assert not any(a.startswith("--audio-file") for a in cmd)


def test_subtitle_starts_just_before_the_first_cue():
    """Le début d'un film est souvent muet : inutilisable pour juger."""
    cmd = preview.build_command(Path("/films/f.mkv"), _sub(),
                                duration=7200.0, first_cue=88.6)
    assert _opt(cmd, "--start=") == "--start=86"


def test_subtitle_start_stays_positive():
    cmd = preview.build_command(Path("/films/f.mkv"), _sub(),
                                duration=7200.0, first_cue=1.0)
    assert _opt(cmd, "--start=") == "--start=0"


def test_falls_back_to_a_quarter_without_cues():
    cmd = preview.build_command(Path("/films/f.mkv"), _sub(), duration=7200.0)
    assert _opt(cmd, "--start=") == "--start=1800"


# ─── Audio ────────────────────────────────────────────────────────────────────

def test_audio_track_id_follows_the_internal_tracks():
    """
    Les pistes d'un --audio-file se numérotent après les pistes internes.

    Vérifié sur mpv : 2 pistes internes + la première du donneur → aid=3.
    """
    cmd = preview.build_command(Path("/films/f.mkv"), _audio(),
                                n_internal_audio=2, donor_audio_index=0)
    assert _opt(cmd, "--aid=") == "--aid=3"


def test_audio_track_id_accounts_for_the_donor_index():
    cmd = preview.build_command(Path("/films/f.mkv"), _audio(),
                                n_internal_audio=2, donor_audio_index=1)
    assert _opt(cmd, "--aid=") == "--aid=4"


def test_audio_command_carries_delay_and_file():
    cmd = preview.build_command(Path("/films/f.mkv"), _audio(delay_ms=-24000),
                                n_internal_audio=2)
    assert _opt(cmd, "--audio-delay=") == "--audio-delay=-24.000"
    assert _opt(cmd, "--audio-file=").endswith("film.VF.mka")
    assert not any(a.startswith("--sub-file") for a in cmd)


# ─── Commun ───────────────────────────────────────────────────────────────────

def test_video_is_the_last_argument():
    """mpv prend le fichier à lire en positionnel, après les options."""
    for track in (_sub(), _audio()):
        cmd = preview.build_command(Path("/films/f.mkv"), track)
        assert cmd[-1] == str(Path("/films/f.mkv"))
        assert cmd[0] == "mpv"


def test_osd_is_enabled():
    """Sans OSD, la valeur ajustée dans mpv resterait invisible."""
    assert "--osd-level=1" in preview.build_command(Path("/films/f.mkv"), _sub())


def test_keys_hint_names_the_real_mpv_bindings():
    """
    Ce sont les noms de bindings mpv, pas les touches physiques : mpv lie
    littéralement Ctrl++ et Ctrl+-, pas Ctrl+= comme sur un clavier US.
    """
    assert "z / Z" in preview.keys_hint(_sub())
    assert "Ctrl++ / Ctrl+-" in preview.keys_hint(_audio())
