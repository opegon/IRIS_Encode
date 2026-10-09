"""
tests/test_dv_chemins.py — Les chemins Dolby Vision de la file (IE-126).

Constats CR-31, CR-54, CR-65 et CR-85 de `revue_code_2026-10-08.md`.
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import dovi
from core.decision import VideoAction
from core.muxer import ExternalTrack, TrackKind
from tui.screens.run import FileState, RunScreen

RACINE = Path(__file__).resolve().parent.parent
RUN = (RACINE / "tui" / "screens" / "run.py").read_text(encoding="utf-8")


# ─── CR-54 : une seule suppression de la source ──────────────────────────────

def _dec(chemin: Path, titre=None, supprimer=True):
    return SimpleNamespace(
        info=SimpleNamespace(path=chemin, titre=titre),
        delete_source_override=supprimer, profile={})


def _statut(etat=FileState.RUNNING):
    return SimpleNamespace(state=etat)


def test_un_fichier_part_avec_ses_annexes(tmp_path):
    film = tmp_path / "Film.mkv"
    film.write_bytes(b"x")
    nfo = tmp_path / "Film.nfo"
    nfo.write_text("<movie/>", encoding="utf-8")
    RunScreen._supprimer_source(None, _dec(film), _statut())
    assert not film.exists() and not nfo.exists()


def test_un_titre_de_disque_n_est_jamais_supprime(tmp_path):
    clip = tmp_path / "BDMV" / "STREAM" / "00001.m2ts"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"x")
    RunScreen._supprimer_source(None, _dec(clip, titre=object()), _statut())
    assert clip.exists()


def test_un_fichier_abandonne_par_s_garde_sa_source(tmp_path):
    """Les chemins DV supprimaient avant de regarder `S` ; la sortie,
    abandonnée, était effacée ensuite : on perdait les deux."""
    film = tmp_path / "Film.mkv"
    film.write_bytes(b"x")
    RunScreen._supprimer_source(None, _dec(film), _statut(FileState.SKIPPED))
    assert film.exists()


def test_sans_demande_rien_n_est_supprime(tmp_path):
    film = tmp_path / "Film.mkv"
    film.write_bytes(b"x")
    RunScreen._supprimer_source(None, _dec(film, supprimer=False), _statut())
    assert film.exists()


def test_les_trois_chemins_passent_par_la_meme_regle():
    """Passe principale, retrait DV, réencodage DV."""
    assert RUN.count("self._supprimer_source(dec, s)") == 3
    assert "source.unlink()" not in RUN


# ─── CR-65 : le succès se vérifie aussi sur les chemins DV ───────────────────

def test_une_piste_audio_vide_est_un_echec(tmp_path, monkeypatch):
    import tui.screens.run as run
    monkeypatch.setattr(run, "pistes_audio_vides",
                        lambda sortie, duree: ["VF (eac3, 0.05 s)"])
    dec = SimpleNamespace(info=SimpleNamespace(duration=7200.0))
    assert "VF (eac3, 0.05 s)" in RunScreen._audio_vide(dec, tmp_path / "x.mp4")
    monkeypatch.setattr(run, "pistes_audio_vides", lambda sortie, duree: [])
    assert RunScreen._audio_vide(dec, tmp_path / "x.mp4") == ""


def test_chaque_sortie_finale_est_controlee():
    """Passe principale et les deux chemins DV, avant toute suppression."""
    assert len(re.findall(r"self\._audio_vide\(dec, ", RUN)) == 3


# ─── CR-31 : ffmpeg en erreur dans le tuyau du RPU ───────────────────────────

class _Processus:
    def __init__(self, code: int):
        self.code = code
        self.returncode = code
        self.stdout = SimpleNamespace(close=lambda: None)

    def communicate(self, timeout=None):
        return b"", b""

    def wait(self, timeout=None):
        return self.code

    def poll(self):
        return self.code


def test_un_ffmpeg_en_erreur_invalide_le_rpu(tmp_path, monkeypatch):
    """Une lecture cassée en route : dovi_tool rend 0 sur le flux tronqué."""
    rpu = tmp_path / "x.rpu"
    rpu.write_bytes(b"rpu partiel")
    codes = iter([1, 0])                       # ffmpeg, puis dovi_tool
    monkeypatch.setattr(dovi.subprocess, "Popen",
                        lambda *a, **k: _Processus(next(codes)))
    assert dovi.extract_rpu_depuis_source(tmp_path / "s.mkv", rpu,
                                          tmp_path / "dovi_tool.exe") is False


def test_les_deux_a_zero_rendent_le_rpu(tmp_path, monkeypatch):
    rpu = tmp_path / "x.rpu"
    rpu.write_bytes(b"rpu")
    codes = iter([0, 0])
    monkeypatch.setattr(dovi.subprocess, "Popen",
                        lambda *a, **k: _Processus(next(codes)))
    assert dovi.extract_rpu_depuis_source(tmp_path / "s.mkv", rpu,
                                          tmp_path / "dovi_tool.exe") is True


# ─── CR-85 : un retrait du DV avec greffe ne part pas en mux ─────────────────

@pytest.mark.parametrize("action,attendu", [
    (VideoAction.SKIP, True),
    (VideoAction.STRIP_DV, False),
])
def test_seul_un_skip_avec_greffe_se_contente_d_un_mux(tmp_path, action, attendu):
    from tui.screens.wizard import WizardScreen
    piste = ExternalTrack(source_path=tmp_path / "vf.mka", source_tid=0,
                          kind=TrackKind.AUDIO, language="fre")
    faux = SimpleNamespace(_dec=SimpleNamespace(
        video=SimpleNamespace(action=action), external_tracks=[piste]))
    assert WizardScreen._muxable(faux) is attendu
