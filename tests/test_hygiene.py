"""
tests/test_hygiene.py — Hygiène : dossiers système, coûts répétés (IE-197 :
CR-130, CR-145).
"""
from __future__ import annotations

import ctypes
import sys

import pytest

from core import scanner


# ─── CR-130 : le scan récursif n'entre pas dans la corbeille ──────────────────

def _scan_note(vus):
    def _scan(chemin):
        vus.append(chemin.name)
        return None
    return _scan


def test_le_scan_recursif_saute_la_corbeille_et_les_dossiers_systeme(tmp_path, monkeypatch):
    for dossier in ("$RECYCLE.BIN/S-1-5-21", "System Volume Information", ".cache",
                    "Films"):
        (tmp_path / dossier).mkdir(parents=True)
    (tmp_path / "$RECYCLE.BIN" / "S-1-5-21" / "$R4F2A.mkv").write_bytes(b"")
    (tmp_path / "System Volume Information" / "x.mkv").write_bytes(b"")
    (tmp_path / ".cache" / "y.mkv").write_bytes(b"")
    (tmp_path / "Films" / "Film.mkv").write_bytes(b"")
    vus: list[str] = []
    monkeypatch.setattr(scanner, "scan", _scan_note(vus))
    scanner.scan_directory_recursive(tmp_path)
    assert vus == ["Film.mkv"]


@pytest.mark.skipif(sys.platform != "win32", reason="attribut caché de Windows")
def test_un_dossier_cache_par_windows_est_saute(tmp_path, monkeypatch):
    cache = tmp_path / "Sauvegarde"
    cache.mkdir()
    (cache / "Film.mkv").write_bytes(b"")
    FILE_ATTRIBUTE_HIDDEN = 0x2
    assert ctypes.windll.kernel32.SetFileAttributesW(str(cache), FILE_ATTRIBUTE_HIDDEN)
    vus: list[str] = []
    monkeypatch.setattr(scanner, "scan", _scan_note(vus))
    scanner.scan_directory_recursive(tmp_path)
    assert vus == []


# ─── CR-145 : coûts répétés ──────────────────────────────────────────────────

def test_le_verrou_d_un_fichier_est_rendu_apres_usage():
    from core import analyses
    with analyses.verrou_de("a"):
        pass
    with analyses.verrou_de("b"):
        pass
    assert analyses._en_cours == {}


def test_lire_ne_reecrit_le_fichier_qu_une_fois_par_jour(monkeypatch):
    import json

    from core import analyses
    entree = {"analyse": {"nature": "PROGRESSIF", "ordre": "", "decime": False,
                          "peigne": 0.0, "peigne_apparie": 0.0},
              "vu": "2026-11-01"}
    analyses.CHEMIN.write_text(json.dumps({c: dict(entree) for c in "abc"}),
                               encoding="utf-8")
    monkeypatch.setattr(analyses, "_entrees", None)
    ecritures: list[int] = []
    vraie = analyses._sauver

    def _compter(entrees):
        ecritures.append(1)
        vraie(entrees)
    monkeypatch.setattr(analyses, "_sauver", _compter)
    for c in "abc":
        assert analyses.lire(c) is not None
    assert len(ecritures) == 1


def test_la_progression_ne_lit_les_octets_ecrits_que_pour_un_mp4(monkeypatch):
    from core import encoder
    lectures: list[int] = []
    monkeypatch.setattr(encoder.EncoderProcess, "octets_ecrits",
                        lambda soi: lectures.append(1) or 0)
    lignes = ["frame=1", "frame=2", "frame=3"]
    for cmd, attendu in ((["ffmpeg", "-i", "a.mkv", "b.mkv"], 0),
                         (["ffmpeg", "-i", "a.mkv", "-movflags", "+faststart",
                           "b.mp4"], 3)):
        lectures.clear()
        proc = encoder.EncoderProcess(cmd, duration=10.0)
        monkeypatch.setattr(proc, "iter_lines", lambda: iter(lignes))
        list(proc.iter_progress())
        assert len(lectures) == attendu, cmd


def test_les_pistes_du_donneur_se_lisent_hors_du_fil_d_interface(tmp_path, monkeypatch):
    import asyncio
    import threading

    from textual.app import App

    from core.muxer import IdentifiedTrack, TrackKind
    from tui.screens import donor_picker

    fils: list[threading.Thread] = []

    def _identify(chemin):
        fils.append(threading.current_thread())
        return [IdentifiedTrack(tid=1, kind=TrackKind.AUDIO, codec="AC-3",
                                language="fre", track_name="VF")]
    monkeypatch.setattr(donor_picker, "identify", _identify)
    donneur = tmp_path / "VF.mka"
    donneur.write_bytes(b"")

    class _App(App):
        def on_mount(self):
            self.push_screen(donor_picker.DonorTrackScreen(donneur))

    async def _run():
        app = _App()
        async with app.run_test() as pilot:
            await pilot.pause(0.5)
            return [t.tid for t in app.screen._tracks], app.screen._selected

    pistes, coche = asyncio.run(_run())
    assert fils and all(f is not threading.main_thread() for f in fils)
    assert pistes == [1] and coche == {1}
