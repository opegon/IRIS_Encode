"""
tests/test_cause_echec.py — La cause d'un échec se lit en entier.

La colonne État coupe à soixante caractères (« sous-titres : préparation
écho… ») ; le détail restait en mémoire, affiché nulle part, et le journal
n'en gardait rien (constaté le 2026-11-01).
"""
from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

from tui.screens.run import FileState, RunScreen

_DETAIL = ("L'extraction des sous-titres a échoué (code 4294967274). "
           "[sist#0:2/none] Decoding requested, but no decoder found for: none")


def _statut(etat, nom, error_msg="", last_line="", avertissements=()):
    return SimpleNamespace(
        state=etat, error_msg=error_msg, last_line=last_line,
        avertissements=list(avertissements),
        decision=SimpleNamespace(info=SimpleNamespace(path=Path("D:/v") / nom),
                                 output_path=Path("D:/v") / f"{nom}.out"))


def _ecran(statuts):
    return SimpleNamespace(
        _statuses=statuts, _SORTIES_LISTEES=RunScreen._SORTIES_LISTEES,
        _ECHECS_LISTES=RunScreen._ECHECS_LISTES,
        _cause_complete=RunScreen._cause_complete,
        apres_lot=False, _abandon=False, _vu=False,
        app=SimpleNamespace(current_mode="encodages", MODE_ENCODAGES="encodages"))


def test_le_bilan_donne_la_cause_entiere():
    ecran = _ecran([
        _statut(FileState.ERROR, "ceremonie.mkv",
                "sous-titres : préparation échouée", _DETAIL),
        _statut(FileState.SUCCESS, "ok.mkv")])
    bilan = RunScreen._resume(ecran)
    assert "ceremonie.mkv" in bilan
    assert "sous-titres : préparation échouée" in bilan
    assert "no decoder found for: none" in bilan
    assert "iris_encode.log" in bilan


def test_une_cause_deja_complete_n_est_pas_doublee():
    s = _statut(FileState.ERROR, "f.mkv", "Disque plein", "Disque plein — ffmpeg: …")
    assert RunScreen._cause_complete(s) == "Disque plein — ffmpeg: …"
    s = _statut(FileState.ERROR, "f.mkv", "remux: code 2", "")
    assert RunScreen._cause_complete(s) == "remux: code 2"


def test_au_dela_de_trois_echecs_le_reste_se_compte():
    ecran = _ecran([_statut(FileState.ERROR, f"f{n}.mkv", "e", f"d{n}")
                    for n in range(5)])
    bilan = RunScreen._resume(ecran)
    assert "f2.mkv" in bilan and "f3.mkv" not in bilan
    assert "2" in bilan.splitlines()[-2]


def test_le_journal_garde_la_cause(caplog):
    ecran = _ecran([_statut(FileState.ERROR, "ceremonie.mkv",
                            "sous-titres : préparation échouée", _DETAIL),
                    _statut(FileState.SUCCESS, "ok.mkv")])
    with caplog.at_level(logging.WARNING, logger="tui.screens.run"):
        RunScreen._on_all_done(ecran)
    lignes = [r.getMessage() for r in caplog.records]
    assert len(lignes) == 1
    assert "ceremonie.mkv" in lignes[0] and "no decoder found" in lignes[0]


def test_le_bilan_reprend_les_avertissements():
    """Un PGS que l'OCR n'a pas lu (IE-176) : le fichier a réussi, le bilan
    le dit quand même ; un fichier en échec ne le répète pas."""
    ecran = _ecran([
        _statut(FileState.SUCCESS, "film.mkv",
                avertissements=["OCR : piste 0:s:1 gardée en PGS"]),
        _statut(FileState.ERROR, "autre.mkv", "e", "d",
                avertissements=["ne doit pas paraître"])])
    bilan = RunScreen._resume(ecran)
    assert "⚠ film.mkv : OCR : piste 0:s:1 gardée en PGS" in bilan
    assert "ne doit pas paraître" not in bilan
