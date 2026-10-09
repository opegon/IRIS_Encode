"""
tests/test_scan_recursif.py — Le mode récursif (`R`) analyse en parallèle.

IE-117 : `scan_directory_recursive` analysait un fichier à la fois quand
l'accueil en analysait quatre. Sur une saison dans un partage réseau, chaque
ffprobe attend le disque : en série, les attentes s'additionnent.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from core import scanner


def _arborescence(racine: Path, n: int) -> list[str]:
    noms = []
    for i in range(n):
        d = racine / f"Saison {i % 2 + 1}"
        d.mkdir(exist_ok=True)
        nom = f"S0{i % 2 + 1}E{i:02d}.mkv"
        (d / nom).touch()
        noms.append(f"{d.name}/{nom}")
    (racine / "Saison 1" / "notes.txt").touch()
    (racine / "Saison 1" / "S01E00.hevc-iris.mkv").touch()
    return sorted(noms)


class _Faux:
    """`scan` simulé : une attente, et le compte des analyses simultanées."""

    def __init__(self, attente: float = 0.05, echec: str | None = None):
        self.attente, self.echec = attente, echec
        self.en_cours = self.maximum = 0
        self.verrou = threading.Lock()

    def __call__(self, path: Path):
        with self.verrou:
            self.en_cours += 1
            self.maximum = max(self.maximum, self.en_cours)
        time.sleep(self.attente)
        with self.verrou:
            self.en_cours -= 1
        if path.name == self.echec:
            raise RuntimeError("ffprobe a échoué")
        return type("Info", (), {"path": path})()


def test_plusieurs_analyses_a_la_fois_dans_l_ordre(tmp_path, monkeypatch):
    attendus = _arborescence(tmp_path, 8)
    faux = _Faux()
    monkeypatch.setattr(scanner, "scan", faux)
    infos = scanner.scan_directory_recursive(tmp_path)
    assert [i.path.relative_to(tmp_path).as_posix() for i in infos] == attendus
    assert faux.maximum == scanner.SCAN_WORKERS, faux.maximum


def test_la_progression_compte_chaque_fichier(tmp_path, monkeypatch):
    _arborescence(tmp_path, 6)
    monkeypatch.setattr(scanner, "scan", _Faux(attente=0.01))
    vus: list[tuple[int, int]] = []
    scanner.scan_directory_recursive(tmp_path, lambda f, t: vus.append((f, t)))
    assert vus == [(i, 6) for i in range(1, 7)]


def test_un_echec_n_arrete_pas_le_reste(tmp_path, monkeypatch):
    _arborescence(tmp_path, 4)
    monkeypatch.setattr(scanner, "scan", _Faux(attente=0.01, echec="S01E00.mkv"))
    vus: list[int] = []
    infos = scanner.scan_directory_recursive(tmp_path, lambda f, t: vus.append(f))
    assert len(infos) == 3 and vus[-1] == 4


def test_dossier_sans_video(tmp_path):
    (tmp_path / "notes.txt").touch()
    assert scanner.scan_directory_recursive(tmp_path) == []


# ─── CR-12 : un seul parcours ─────────────────────────────────────────────────

def _bluray(racine: Path) -> Path:
    from test_bluray import _clip_clair, _disque, _mpls
    return _disque(racine, {"00001": _mpls([("00001", 0, 4000)])},
                   {"00001": _clip_clair()})


def _compter_scandir(monkeypatch) -> list:
    import os
    vus: list = []
    reel = os.scandir

    def compte(chemin="."):
        vus.append(Path(chemin))
        return reel(chemin)
    monkeypatch.setattr(os, "scandir", compte)
    return vus


def test_un_seul_parcours_qui_n_entre_pas_dans_le_disque(tmp_path, monkeypatch):
    """`rglob` des deux marques de disque puis de tout : trois parcours. Un
    seul suffit, et rien sous `BDMV` n'a à être listé."""
    _arborescence(tmp_path, 4)
    _bluray(tmp_path / "Film (2020)")
    monkeypatch.setattr(scanner, "scan", _Faux(attente=0))
    vus = _compter_scandir(monkeypatch)
    infos = scanner.scan_directory_recursive(tmp_path)

    # La lecture des titres du disque liste `PLAYLIST` (iterdir) : hors parcours.
    parcourus = [v for v in vus if "PLAYLIST" not in v.parts]
    assert sorted(parcourus) == sorted([tmp_path, tmp_path / "Saison 1",
                                        tmp_path / "Saison 2", tmp_path / "Film (2020)"])
    noms = [i.path.name for i in infos]
    assert noms.count("00001.mpls") == 1 and "00001.m2ts" not in noms


def test_un_disque_hybride_ne_compte_qu_une_fois(tmp_path, monkeypatch):
    racine = _bluray(tmp_path / "Film")
    video_ts = racine / "VIDEO_TS"
    video_ts.mkdir()
    (video_ts / "VIDEO_TS.IFO").write_bytes(b"DVDVIDEO-VMG")
    (video_ts / "VTS_01_1.VOB").write_bytes(b"\0")
    monkeypatch.setattr(scanner, "scan", _Faux(attente=0))
    noms = [i.path.name for i in scanner.scan_directory_recursive(tmp_path)]
    assert noms == ["00001.mpls"]


def test_lance_depuis_bdmv_le_disque_reste_un_titre(tmp_path, monkeypatch):
    racine = _bluray(tmp_path / "Film")
    monkeypatch.setattr(scanner, "scan", _Faux(attente=0))
    noms = [i.path.name for i in scanner.scan_directory_recursive(racine / "BDMV")]
    assert noms == ["00001.mpls"]
