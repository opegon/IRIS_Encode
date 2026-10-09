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


# ─── Note : les métadonnées HDR10 ne viennent plus d'ici ──────────────────────
#
# `rpu_info()` analysait la sortie de `dovi_tool info` avec des expressions
# régulières attendant du texte — « Dolby Vision Profile: 8.1 », « MaxCLL: 1000 ».
# L'outil rend du JSON, et les rendait donc toujours vides : le mode
# « HDR10 quality » n'a jamais injecté ni master-display ni max-cll.
#
# Trois tests passaient pourtant, parce qu'ils fournissaient eux-mêmes le format
# attendu. C'est ce qui a permis au défaut de survivre : un test qui invente son
# entrée ne prouve rien sur ce que produit l'outil réel.
#
# Ces métadonnées sont désormais lues dans les SEI du flux par ffprobe
# (`scanner._hdr10_metadata`), ce qui vaut aussi pour une source HDR sans Dolby
# Vision. Voir tests/test_hdr10.py.

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
    """La commande de l'étape 1 du retrait DV (CR-33 : `extract_hevc_stream`,
    sans appelant, est retirée ; sa commande reste)."""
    cmd = dovi.build_extract_hevc_command(tmp_path / "src.mkv", tmp_path / "out.hevc")
    assert "-c:v" in cmd and "copy" in cmd
    assert "-bsf:v" in cmd and "hevc_mp4toannexb" in cmd
    assert "-f" in cmd and "hevc" in cmd


def test_extract_hevc_stream_duration_limit(tmp_path: Path):
    cmd = dovi.build_extract_hevc_command(tmp_path / "src.mkv", tmp_path / "out.hevc",
                                          duration_limit=30)
    assert "-t" in cmd and "30" in cmd


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
