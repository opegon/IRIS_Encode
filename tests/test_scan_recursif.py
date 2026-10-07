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
