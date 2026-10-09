"""
tests/test_code_mort.py — Code mort retiré, et ce qu'il cachait (IE-137,
constats CR-08, CR-13, CR-33, CR-46, CR-66, CR-69, CR-73 de
`revue_code_2026-10-08.md`, décisions de l'utilisateur du 2026-10-09).
"""
from __future__ import annotations

import asyncio
import subprocess
import sys
import typing
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent


# ─── CR-08 — l'outil DVD, jamais un ffmpeg nu ────────────────────────────────

def test_sans_outil_dvd_la_commande_d_extraction_leve(monkeypatch):
    from core import dvd
    monkeypatch.setattr(dvd, "_ffmpeg", None)
    with pytest.raises(ValueError):
        dvd.build_extraction_command(object(), Path("sortie.mkv"))


# ─── CR-13, CR-33, CR-46 — plus rien de ce qui n'avait pas d'appelant ────────

@pytest.mark.parametrize("module,nom", [
    ("core.scanner", "scan_directory"), ("core.scanner", "list_subdirs"),
    ("core.scanner", "set_dovi_path"), ("core.scanner", "_dovi_path"),
    ("core.dovi", "extract_hevc_stream"), ("core.dovi", "extract_rpu"),
    ("core.dovi", "get_temp_dir"), ("core.dovi", "cleanup_temp_files"),
    ("core.profiles", "parse_languages"),
])
def test_le_code_sans_appelant_est_retire(module, nom):
    import importlib
    assert not hasattr(importlib.import_module(module), nom)


@pytest.mark.parametrize("attribut", ["is_already_encoded", "resolution_label",
                                      "has_image_subs"])
def test_videoinfo_n_a_plus_ses_proprietes_mortes(attribut):
    from core.scanner import VideoInfo
    assert not hasattr(VideoInfo, attribut)


def test_profile_n_a_plus_summary_line():
    from core.profiles import Profile
    assert not hasattr(Profile, "summary_line")


def test_ce_qui_sert_reste():
    """`same_language` sert au collage (IE-136), `validate_id` au formulaire
    de profil (CR-99) : la revue les croyait morts."""
    from core import profiles, scanner
    assert scanner.same_language("fra", "fre") and profiles.validate_id("series_basic")


def test_la_doc_de_dovi_ne_decrit_plus_de_fonction_absente():
    texte = (RACINE / "core" / "dovi.py").read_text(encoding="utf-8")
    assert "probe_file" not in texte and "rpu_info" not in texte


# ─── CR-66 — les annotations de run.py se résolvent ──────────────────────────

def test_les_annotations_de_run_py_se_resolvent():
    from tui.screens.run import RunScreen
    for nom in ("_liberer", "_audio_prepass", "_porter_sous_titres",
                "_playlist_chapitres", "_transcoder_greffes", "_ecrire_chapitres"):
        typing.get_type_hints(getattr(RunScreen, nom))


# ─── CR-69 — le fil d'Ariane ─────────────────────────────────────────────────

def test_le_fil_d_ariane_est_le_dossier(tmp_path):
    from tui.widgets.file_tree import FileNavigator
    assert FileNavigator(tmp_path).breadcrumb() == str(tmp_path)


# ─── CR-73 — le dossier passé en argument s'ouvre ────────────────────────────

def _depart(app) -> tuple[bool, Path]:
    async def _scenario():
        async with app.run_test(size=(160, 40)) as pilot:
            await pilot.pause(0.5)
            return app.screen._nav.is_virtual, app.screen._nav.current
    return asyncio.run(_scenario())


def test_un_dossier_donne_ouvre_l_accueil_dedans(tmp_path):
    from tui.app import IrisEncodeApp
    virtuel, courant = _depart(IrisEncodeApp(start_path=tmp_path, ouvrir_dossier=True))
    assert not virtuel and courant == tmp_path


def test_sans_dossier_l_accueil_part_des_volumes(tmp_path):
    from tui.app import IrisEncodeApp
    virtuel, _courant = _depart(IrisEncodeApp(start_path=tmp_path))
    assert virtuel


def test_main_transmet_le_dossier_donne():
    texte = (RACINE / "main.py").read_text(encoding="utf-8")
    assert "ouvrir_dossier=args.path is not None" in texte
    assert ".resolve()" not in texte.split("def main")[1]


def test_main_refuse_un_dossier_absent(tmp_path):
    r = subprocess.run([sys.executable, str(RACINE / "main.py"),
                        str(tmp_path / "absent")],
                       capture_output=True, text=True, timeout=60,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 1 and "Path not found" in r.stdout
