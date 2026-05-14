"""
tests/test_dovi.py — Tests unitaires de core/dovi.py

Tests sans fichier DV réel : on mocke subprocess.run et on vérifie
la construction des commandes + le parsing des sorties dovi_tool.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest import mock

import pytest

from core import dovi


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_dovi(tmp_path: Path) -> Path:
    """Crée un faux exécutable dovi_tool pour les tests."""
    p = tmp_path / dovi._EXE_NAME
    p.write_bytes(b"")
    return p


# ─── Détection ────────────────────────────────────────────────────────────────

def test_get_path_returns_local_bin(tmp_path: Path, fake_dovi: Path):
    """get_path() trouve dovi_tool dans bin_dir."""
    with mock.patch("shutil.which", return_value=None):
        assert dovi.get_path(tmp_path) == fake_dovi


def test_get_path_returns_none_when_absent(tmp_path: Path):
    with mock.patch("shutil.which", return_value=None):
        assert dovi.get_path(tmp_path) is None


def test_is_available(tmp_path: Path, fake_dovi: Path):
    with mock.patch("shutil.which", return_value=None):
        assert dovi.is_available(tmp_path) is True
    with mock.patch("shutil.which", return_value=None):
        assert dovi.is_available(tmp_path / "nowhere") is False


# ─── Parsing dovi_tool info ───────────────────────────────────────────────────

def test_rpu_info_parses_p8_1():
    fake_output = (
        "Dolby Vision Profile: 8.1\n"
        "MaxCLL: 1000  MaxFALL: 400\n"
        "G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1)\n"
    )
    mock_result = mock.Mock(stdout=fake_output, stderr="", returncode=0)
    with mock.patch("subprocess.run", return_value=mock_result):
        info = dovi.rpu_info(Path("fake.rpu"), Path("fake_dovi"))
    assert info["dv_subprofile"] == "8.1"
    assert info["max_cll"] == (1000, 400)
    assert "G(13250,34500)" in info["master_display"]


def test_rpu_info_parses_profile_5():
    fake_output = "DV profile: 5\n"
    mock_result = mock.Mock(stdout=fake_output, stderr="", returncode=0)
    with mock.patch("subprocess.run", return_value=mock_result):
        info = dovi.rpu_info(Path("fake.rpu"), Path("fake_dovi"))
    assert info["dv_subprofile"] == "5"
    assert "master_display" not in info
    assert "max_cll" not in info


def test_rpu_info_handles_exception():
    with mock.patch("subprocess.run", side_effect=OSError("no exe")):
        info = dovi.rpu_info(Path("fake.rpu"), Path("fake_dovi"))
    assert info == {}


# ─── Construction des paramètres x265 ─────────────────────────────────────────

def test_make_x265_hdr_params_minimal():
    params = dovi.make_x265_hdr_params()
    assert "hdr10-opt=1" in params
    assert "colorprim=bt2020" in params
    assert not any(p.startswith("master-display=") for p in params)
    assert not any(p.startswith("max-cll=")        for p in params)


def test_make_x265_hdr_params_full():
    md = "G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1)"
    params = dovi.make_x265_hdr_params(master_display=md, max_cll=(1000, 400))
    assert f"master-display={md}" in params
    assert "max-cll=1000,400" in params


def test_x265_params_string_concat():
    params = ["hdr10-opt=1", "repeat-headers=1", "colorprim=bt2020"]
    s = dovi.x265_params_string(params)
    assert s == "hdr10-opt=1:repeat-headers=1:colorprim=bt2020"


# ─── Commandes ffmpeg/dovi_tool ───────────────────────────────────────────────

def test_extract_hevc_stream_command(tmp_path: Path):
    src = tmp_path / "src.mkv"
    src.write_bytes(b"")
    dst = tmp_path / "out.hevc"

    def fake_run(cmd, **kwargs):
        # Vérifie les arguments clés
        assert "-c:v" in cmd and "copy" in cmd
        assert "-bsf:v" in cmd and "hevc_mp4toannexb" in cmd
        assert "-f" in cmd and "hevc" in cmd
        # Simule un succès en créant le fichier
        dst.write_bytes(b"\x00")
        return mock.Mock(returncode=0)

    with mock.patch("subprocess.run", side_effect=fake_run):
        assert dovi.extract_hevc_stream(src, dst) is True


def test_extract_hevc_stream_duration_limit(tmp_path: Path):
    src = tmp_path / "src.mkv"
    src.write_bytes(b"")
    dst = tmp_path / "out.hevc"

    captured = {}
    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        dst.write_bytes(b"\x00")
        return mock.Mock(returncode=0)

    with mock.patch("subprocess.run", side_effect=fake_run):
        dovi.extract_hevc_stream(src, dst, duration_limit=30)
    assert "-t" in captured["cmd"]
    assert "30" in captured["cmd"]


def test_extract_rpu_command(tmp_path: Path):
    hevc  = tmp_path / "in.hevc";  hevc.write_bytes(b"\x00")
    rpu   = tmp_path / "out.rpu"
    fake_dovi = tmp_path / "dovi"

    def fake_run(cmd, **kwargs):
        assert cmd[0] == str(fake_dovi)
        assert "extract-rpu" in cmd
        rpu.write_bytes(b"\x00")
        return mock.Mock(returncode=0)

    with mock.patch("subprocess.run", side_effect=fake_run):
        assert dovi.extract_rpu(hevc, rpu, fake_dovi) is True


def test_convert_p7_to_p8_uses_mode_2(tmp_path: Path):
    src = tmp_path / "p7.rpu";   src.write_bytes(b"\x00")
    dst = tmp_path / "p8.rpu"
    fake_dovi = tmp_path / "dovi"

    def fake_run(cmd, **kwargs):
        assert "convert" in cmd
        assert "-m" in cmd
        assert "2" in cmd
        dst.write_bytes(b"\x00")
        return mock.Mock(returncode=0)

    with mock.patch("subprocess.run", side_effect=fake_run):
        assert dovi.convert_p7_to_p8(src, dst, fake_dovi) is True


# ─── Temp dir ─────────────────────────────────────────────────────────────────

def test_get_temp_dir_creates(tmp_path: Path):
    tmp = dovi.get_temp_dir(tmp_path)
    assert tmp.is_dir()
    assert tmp == tmp_path / "temp"


def test_cleanup_temp_files(tmp_path: Path):
    f1 = tmp_path / "a";  f1.write_bytes(b"\x00")
    f2 = tmp_path / "b";  f2.write_bytes(b"\x00")
    f3 = tmp_path / "nonexistent"
    dovi.cleanup_temp_files(f1, f2, f3)
    assert not f1.exists()
    assert not f2.exists()
