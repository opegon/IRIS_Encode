"""
tests/test_muxer.py — Tests unitaires de core/muxer.py

Tests sans mkvmerge réel : on mocke subprocess.run pour identify() et on
vérifie la construction des commandes + le parsing de la sortie --gui-mode.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from core import muxer
from core.muxer import ExternalTrack, TrackKind


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def vf(tmp_path: Path) -> ExternalTrack:
    """Piste audio VF venant d'un autre release, décalée et étirée (PAL)."""
    return ExternalTrack(
        source_path=tmp_path / "Film.VF.mkv",
        source_tid=1,
        kind=TrackKind.AUDIO,
        language="fre",
        track_name="VF",
        delay_ms=-2450,
        stretch=(24000, 25025),
        is_default=True,
    )


@pytest.fixture
def subs(tmp_path: Path) -> ExternalTrack:
    """Sous-titres externes, simple décalage."""
    return ExternalTrack(
        source_path=tmp_path / "Film.fr.srt",
        source_tid=0,
        kind=TrackKind.SUBTITLE,
        language="fre",
        delay_ms=850,
    )


# ─── Construction de la commande ──────────────────────────────────────────────

def test_command_starts_with_output_then_source(tmp_path: Path, vf: ExternalTrack):
    src = tmp_path / "Film.mkv"
    out = tmp_path / "Film_[mux].mkv"
    cmd = muxer.build_mux_command(src, [vf], out)

    assert cmd[0] == "mkvmerge"
    assert "--gui-mode" in cmd
    assert cmd[cmd.index("-o") + 1] == str(out)
    # La source vient avant le donneur
    assert cmd.index(str(src)) < cmd.index(str(vf.source_path))


def test_sync_carries_delay_and_stretch(tmp_path: Path, vf: ExternalTrack):
    cmd = muxer.build_mux_command(tmp_path / "Film.mkv", [vf], tmp_path / "out.mkv")
    assert cmd[cmd.index("--sync") + 1] == "1:-2450,24000/25025"


def test_sync_without_stretch_is_plain_delay(tmp_path: Path, subs: ExternalTrack):
    cmd = muxer.build_mux_command(tmp_path / "Film.mkv", [subs], tmp_path / "out.mkv")
    assert cmd[cmd.index("--sync") + 1] == "0:850"


def test_sync_omitted_when_no_offset(tmp_path: Path, subs: ExternalTrack):
    subs.delay_ms = 0
    cmd = muxer.build_mux_command(tmp_path / "Film.mkv", [subs], tmp_path / "out.mkv")
    assert "--sync" not in cmd


def test_default_flag_always_explicit(tmp_path: Path, subs: ExternalTrack):
    """mkvmerge met le 1er sous-titre en default tout seul : il faut le dire."""
    cmd = muxer.build_mux_command(tmp_path / "Film.mkv", [subs], tmp_path / "out.mkv")
    assert "--default-track-flag" in cmd
    assert cmd[cmd.index("--default-track-flag") + 1] == "0:0"


def test_default_flag_set_when_requested(tmp_path: Path, vf: ExternalTrack):
    cmd = muxer.build_mux_command(tmp_path / "Film.mkv", [vf], tmp_path / "out.mkv")
    assert cmd[cmd.index("--default-track-flag") + 1] == "1:1"


def test_forced_flag_only_when_true(tmp_path: Path, subs: ExternalTrack):
    cmd = muxer.build_mux_command(tmp_path / "Film.mkv", [subs], tmp_path / "out.mkv")
    assert "--forced-display-flag" not in cmd
    subs.is_forced = True
    cmd = muxer.build_mux_command(tmp_path / "Film.mkv", [subs], tmp_path / "out.mkv")
    assert cmd[cmd.index("--forced-display-flag") + 1] == "0:1"


def test_donor_is_limited_to_requested_tracks(tmp_path: Path, vf: ExternalTrack):
    """Sans ces options mkvmerge embarque tout le fichier donneur."""
    cmd = muxer.build_mux_command(tmp_path / "Film.mkv", [vf], tmp_path / "out.mkv")
    assert "--no-video" in cmd
    assert "--no-chapters" in cmd
    assert "--no-global-tags" in cmd
    assert cmd[cmd.index("--audio-tracks") + 1] == "1"
    assert "--no-subtitles" in cmd     # aucun sous-titre demandé chez ce donneur


def test_track_name_omitted_when_empty(tmp_path: Path, subs: ExternalTrack):
    cmd = muxer.build_mux_command(tmp_path / "Film.mkv", [subs], tmp_path / "out.mkv")
    assert "--track-name" not in cmd


# ─── Regroupement par fichier donneur ─────────────────────────────────────────

def test_two_tracks_same_donor_listed_once(tmp_path: Path):
    """Deux pistes du même fichier → un seul bloc, pas deux entrées."""
    donor = tmp_path / "Film.VF.mkv"
    a = ExternalTrack(source_path=donor, source_tid=1, kind=TrackKind.AUDIO,
                      language="fre", delay_ms=-2450)
    b = ExternalTrack(source_path=donor, source_tid=2, kind=TrackKind.SUBTITLE,
                      language="fre", delay_ms=-2450)
    cmd = muxer.build_mux_command(tmp_path / "Film.mkv", [a, b], tmp_path / "out.mkv")

    assert cmd.count(str(donor)) == 1
    assert cmd[cmd.index("--audio-tracks") + 1] == "1"
    assert cmd[cmd.index("--subtitle-tracks") + 1] == "2"
    # Chaque piste garde son propre --sync
    assert cmd.count("--sync") == 2


def test_two_donors_produce_two_blocks(tmp_path: Path, vf: ExternalTrack, subs: ExternalTrack):
    cmd = muxer.build_mux_command(tmp_path / "Film.mkv", [vf, subs], tmp_path / "out.mkv")
    assert cmd.count(str(vf.source_path)) == 1
    assert cmd.count(str(subs.source_path)) == 1
    assert cmd.index(str(vf.source_path)) < cmd.index(str(subs.source_path))
    assert cmd.count("--no-video") == 2


def test_independent_sync_per_track(tmp_path: Path, vf: ExternalTrack, subs: ExternalTrack):
    """Chaque piste porte son décalage, même greffées ensemble."""
    cmd = muxer.build_mux_command(tmp_path / "Film.mkv", [vf, subs], tmp_path / "out.mkv")
    syncs = [cmd[i + 1] for i, a in enumerate(cmd) if a == "--sync"]
    assert syncs == ["1:-2450,24000/25025", "0:850"]


# ─── Garde-fous ───────────────────────────────────────────────────────────────

def test_output_equal_to_source_is_refused(tmp_path: Path, vf: ExternalTrack):
    src = tmp_path / "Film.mkv"
    with pytest.raises(ValueError, match="identique à la source"):
        muxer.build_mux_command(src, [vf], src)


def test_missing_language_is_refused(tmp_path: Path, vf: ExternalTrack):
    vf.language = ""
    with pytest.raises(ValueError, match="Langue manquante"):
        muxer.build_mux_command(tmp_path / "Film.mkv", [vf], tmp_path / "out.mkv")


def test_empty_track_list_is_refused(tmp_path: Path):
    with pytest.raises(ValueError, match="Aucune piste"):
        muxer.build_mux_command(tmp_path / "Film.mkv", [], tmp_path / "out.mkv")


def test_mux_output_path_never_equals_source(tmp_path: Path):
    src = tmp_path / "Film.mkv"
    out = muxer.mux_output_path(src)
    assert out != src
    assert out.name == "Film_[mux].mkv"


# ─── identify() ───────────────────────────────────────────────────────────────

_IDENTIFY_JSON = json.dumps({
    "tracks": [
        {"id": 0, "type": "video", "codec": "AVC/H.264",
         "properties": {"language": "und"}},
        {"id": 1, "type": "audio", "codec": "AC-3",
         "properties": {"language": "eng", "track_name": "Original"}},
        {"id": 2, "type": "subtitles", "codec": "SubRip/SRT",
         "properties": {"language": "fre"}},
    ]
})


def _run_ok(stdout: str):
    return mock.Mock(returncode=0, stdout=stdout, stderr="")


def test_identify_skips_video_but_keeps_global_ids(tmp_path: Path):
    """Le tid de l'audio reste 1 : la vidéo compte dans la numérotation."""
    with mock.patch("subprocess.run", return_value=_run_ok(_IDENTIFY_JSON)):
        tracks = muxer.identify(tmp_path / "Film.mkv")

    assert [t.tid for t in tracks] == [1, 2]
    assert [t.kind for t in tracks] == [TrackKind.AUDIO, TrackKind.SUBTITLE]
    assert tracks[0].language == "eng"
    assert tracks[0].track_name == "Original"


def test_identify_returns_empty_on_failure(tmp_path: Path):
    with mock.patch("subprocess.run", return_value=mock.Mock(returncode=2, stdout="", stderr="err")):
        assert muxer.identify(tmp_path / "Film.mkv") == []


def test_identify_returns_empty_on_bad_json(tmp_path: Path):
    with mock.patch("subprocess.run", return_value=_run_ok("pas du json")):
        assert muxer.identify(tmp_path / "Film.mkv") == []


def test_identify_survives_missing_binary(tmp_path: Path):
    with mock.patch("subprocess.run", side_effect=OSError("introuvable")):
        assert muxer.identify(tmp_path / "Film.mkv") == []


# ─── Progression --gui-mode ───────────────────────────────────────────────────

@pytest.mark.parametrize("line,expected", [
    ("#GUI#progress 0%",    0),
    ("#GUI#progress 42%",   42),
    ("#GUI#progress 100%",  100),
    ("  #GUI#progress 7%",  7),
    ("Multiplexing took 0 seconds.", None),
    ("#GUI#error blabla",   None),
    ("", None),
])
def test_parse_progress(line: str, expected):
    assert muxer.parse_progress(line) == expected


def test_parse_error():
    assert muxer.parse_error("#GUI#error The type of file 'x' could not be recognized.") \
        == "The type of file 'x' could not be recognized."
    assert muxer.parse_error("#GUI#progress 50%") is None


# ─── Intégration avec FileDecision ────────────────────────────────────────────

def test_external_track_forces_mkv_and_suffix():
    """Une piste externe impose le MKV, et SKIP sans suffixe passe en _[mux]."""
    from core.decision import FileDecision, VideoAction, VideoDecision

    info = mock.Mock()
    info.path = Path("/films/Film.mkv")
    info.has_image_subs = False

    video = VideoDecision(
        action=VideoAction.SKIP, reason="déjà encodé", target_bitrate=0,
        target_width=1920, target_height=1080,
        dv_action=mock.Mock(), output_suffix="",
    )
    dec = FileDecision(info=info, profile={}, video=video)

    # Sans piste externe : SKIP → pas de sortie distincte, MP4 par défaut
    assert dec.output_container == ".mp4"

    dec.external_tracks = [ExternalTrack(
        source_path=Path("/films/Film.VF.mkv"), source_tid=1,
        kind=TrackKind.AUDIO, language="fre",
    )]
    assert dec.output_container == ".mkv"
    assert dec.output_path.name == "Film_[mux].mkv"
    assert dec.output_path != info.path
