"""
tests/test_finalisation_mp4.py — la finalisation d'un MP4 (`+faststart`) et le
remux MP4 se voient à l'écran.

ffmpeg réécrit tout le MP4 pour en mettre l'index en tête, sans rien dire ; et
sous `-loglevel error` sans `-stats`, il ne disait rien du remux non plus.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from core import dovi, encoder
from core.encoder import (EncoderProcess, MARGE_FINALISATION,
                          SILENCE_FINALISATION, octets_ecrits)

FFMPEG = shutil.which("ffmpeg")


def test_octets_ecrits_compte_ce_que_le_processus_ecrit(tmp_path):
    cible = tmp_path / "x.bin"
    code = (f"import sys,time; f=open(r'{cible}','wb'); "
            "f.write(b'0'*(4<<20)); f.flush(); print('ok', flush=True); time.sleep(30)")
    p = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE)
    try:
        assert p.stdout.readline().strip() == b"ok"
        n = octets_ecrits(p.pid)
        assert n is not None and n >= 4 << 20
    finally:
        p.kill()
        p.wait()


def test_rien_a_lire_d_un_processus_termine():
    proc = EncoderProcess([sys.executable, "-c", "pass"])
    proc.start()
    proc.wait()
    assert proc.octets_ecrits() is None


def test_vitesse_en_notation_scientifique():
    ligne = ("frame=  500 fps=0.0 q=-1.0 Lsize=     127KiB time=00:00:19.92 "
             "bitrate=  52.2kbits/s speed=1.06e+03x elapsed=0:00:00.01")
    p = encoder.parse_progress(ligne, 20.0)
    assert p is not None and p.speed == pytest.approx(1060.0)


class _Horloge:
    t = 1000.0

    def __call__(self) -> float:
        return self.t


def _proc(monkeypatch, cmd, ecrits):
    horloge = _Horloge()
    monkeypatch.setattr(encoder.time, "monotonic", horloge)
    proc = EncoderProcess(cmd)
    monkeypatch.setattr(proc, "octets_ecrits", lambda: ecrits[0])
    # La dernière ligne de ffmpeg : le fichier pèse alors 1 Go.
    proc._proc = type("P", (), {"stderr": iter(["frame=1 time=00:00:01.00\n"])})()
    list(proc.iter_progress())
    return proc, horloge


MP4 = ["ffmpeg", "-i", "a.mkv", "-movflags", "+faststart", "b.mp4"]


def test_finalisation_mesuree(monkeypatch):
    ecrits = [1 << 30]
    proc, h = _proc(monkeypatch, MP4, ecrits)
    h.t += SILENCE_FINALISATION + 1
    ecrits[0] += 100 << 20
    assert proc.finalisation() == (100 << 20, 1 << 30, 0.0)
    h.t += 4
    ecrits[0] += 20 << 20
    fait, total, debit = proc.finalisation()
    assert (fait, total) == (120 << 20, 1 << 30)
    assert debit == pytest.approx((20 << 20) / 4)


def test_rien_tant_que_ffmpeg_parle(monkeypatch):
    ecrits = [1 << 30]
    proc, h = _proc(monkeypatch, MP4, ecrits)
    ecrits[0] += 100 << 20
    assert proc.finalisation() is None


def test_rien_sans_ecriture(monkeypatch):
    """Un partage qui ne répond plus se tait aussi : sans écriture, ce n'est
    pas une finalisation."""
    ecrits = [1 << 30]
    proc, h = _proc(monkeypatch, MP4, ecrits)
    h.t += 60
    ecrits[0] += MARGE_FINALISATION - 1
    assert proc.finalisation() is None


def test_rien_hors_mp4(monkeypatch):
    ecrits = [1 << 30]
    proc, h = _proc(monkeypatch, ["ffmpeg", "-i", "a.mkv", "b.mkv"], ecrits)
    h.t += 60
    ecrits[0] += 100 << 20
    assert proc.finalisation() is None


@pytest.mark.skipif(FFMPEG is None, reason="ffmpeg absent")
@pytest.mark.parametrize("construire", ["strip", "remux"])
def test_remux_mp4_rend_sa_progression(tmp_path, construire):
    source = tmp_path / "mire.mkv"
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "testsrc=size=320x240:rate=25:duration=20",
                    "-c:v", "libx265", "-preset", "ultrafast", "-x265-params",
                    "log-level=error", str(source)], check=True)
    sortie = tmp_path / "sortie.mp4"
    if construire == "strip":
        cmd = dovi.build_strip_mp4(source, sortie, [], FFMPEG, audio=[])
    else:
        cmd = dovi.build_dv_mp4_remux(source, sortie, FFMPEG)
    proc = EncoderProcess(cmd, 20.0)
    proc.start()
    vus = [p for _, p in proc.iter_progress() if p]
    assert proc.wait() == 0
    assert vus and vus[-1].percent > 0.9
