"""
tests/test_pied_allege.py — Revue d'interface du 2026-11-08, points 1 à 3.

1. Le pied de page n'annonce plus la navigation de table (Début, Fin, PgUp,
   PgDn) ni le redimensionnement des colonnes (Tab, ⇧Tab, <, >) : huit
   entrées répétées sur chaque écran, que le guide (H) documente. Sur
   l'accueil, elles portaient le pied de page à trois lignes.
2. « Accueil » désignait deux choses dans le même pied de page : la touche
   Home (« Accueil  Début ») et le retour à la liste des volumes
   (« Ctrl+Home  Accueil »). La touche s'appelle désormais « Début », comme
   sur un clavier français, et l'action « Volumes ».
3. Sur l'accueil, la colonne Audio montre toutes les pistes gardées, et le nom
   de fichier se coupe au milieu : deux releases qui ne diffèrent que par la
   fin (`…-A.mkv`, `…-B.mkv`) se lisaient identiques.
"""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest
from rich.cells import cell_len

from core import i18n
from tui.common import FOOTER_ACCUEIL, footer_line2, touche
from tui.screens.browser import BrowserScreen

_NAVIGATION = {"home", "end", "pageup", "pagedown",
               "tab", "shift+tab", "<", ">"}


# ─── 1. Pied de page allégé ───────────────────────────────────────────────────

def test_le_pied_standard_n_annonce_plus_la_navigation():
    cles = {cle for cle, _lib in footer_line2(back=True, accueil=True)}
    # F10 est dans l'en-tête depuis v0.9.3.2.
    assert cles == {"backspace", "ctrl+home"}


def test_l_accueil_n_annonce_plus_la_navigation():
    cles = {cle for cle, _lib in BrowserScreen._RACCOURCIS_FICHIERS}
    assert not cles & _NAVIGATION, cles & _NAVIGATION


# ─── 2. « Accueil » ne désigne plus la touche Home ────────────────────────────

def test_la_touche_home_ne_se_lit_plus_accueil():
    i18n.init("fr")
    assert touche("home") == "Début"
    assert touche("ctrl+home") == "Ctrl+Début"
    assert i18n._(FOOTER_ACCUEIL[1]) == "Volumes"
    # Le nom de l'écran d'accueil, lui, ne change pas.
    assert i18n._("Home") == "Accueil"


def test_en_anglais_les_noms_de_touche_restent():
    i18n.init("en")
    try:
        assert touche("home") == "Home"
        assert touche("ctrl+home") == "Ctrl+Home"
    finally:
        i18n.init("fr")


# ─── 3. Audio entière, nom coupé au milieu ────────────────────────────────────

_NOMS = ["Project.Hail.Mary.2026.MULTi.VFF.2160p.10bit.HDR.DV.x265-A.mkv",
         "Project.Hail.Mary.2026.MULTi.VFF.2160p.10bit.HDR.DV.x265-B.mkv"]


def _clips_trois_pistes(td: Path) -> bool:
    """Deux fichiers au nom long, trois pistes audio chacun."""
    from core import config as cfg_mod
    from core.preflight import get_tool_path
    ffmpeg = get_tool_path("ffmpeg", cfg_mod.get_bin_dir(cfg_mod.load()))
    if not ffmpeg:
        return False
    for nom in _NOMS:
        subprocess.run(
            [str(ffmpeg), "-y", "-loglevel", "error",
             "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
             "-f", "lavfi", "-i", "sine=duration=1",
             "-map", "0:v", "-map", "1:a", "-map", "1:a", "-map", "1:a",
             # Deux formats : les pistes d'un même format se regroupent, et le
             # résumé tiendrait sous les 20 colonnes du défaut.
             "-c:v", "libx264", "-c:a:0", "ac3", "-c:a:1", "aac", "-c:a:2", "ac3",
             "-metadata:s:a:0", "language=fre",
             "-metadata:s:a:1", "language=eng",
             "-metadata:s:a:2", "language=ger",
             str(td / nom)],
            check=True, capture_output=True,
        )
    return True


async def _releve(td: Path) -> dict:
    from textual.widgets import DataTable
    from tui.app import IrisEncodeApp

    app = IrisEncodeApp(start_path=td)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause(0.5)
        app.push_screen(BrowserScreen(td, start_virtual=False))
        ecran = None
        for _tour in range(150):
            await pilot.pause(0.1)
            ecran = app.screen
            if (isinstance(ecran, BrowserScreen) and len(ecran._decisions) == 2
                    and not ecran._en_attente):
                break
        await pilot.pause(0.5)
        table = ecran.query_one(DataTable)
        noms = [table.get_cell(str(td / n), "fichier").plain for n in _NOMS]
        resumes = [ecran._decisions[td / n].audio_summary for n in _NOMS]
        return {
            "noms": noms,
            "resumes": resumes,
            "audio": table.columns["audio"].width,
            "fichier": table.columns["fichier"].width,
        }


def test_audio_entiere_et_nom_coupe_au_milieu(tmp_path, monkeypatch):
    if not _clips_trois_pistes(tmp_path):
        pytest.skip("ffmpeg introuvable")
    from core import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "save", lambda *args, **kwargs: None)

    r = asyncio.run(_releve(tmp_path.resolve()))

    besoin = max(cell_len(s) for s in r["resumes"])
    assert besoin > 20, f"témoin trop court pour le défaut de 20 : {r['resumes']}"
    assert r["audio"] >= besoin, (r["audio"], r["resumes"])

    a, b = r["noms"]
    assert a != b, f"deux noms différents se lisent pareil : {a!r}"
    assert "…" in a and a.endswith("-A.mkv"), a
    assert b.endswith("-B.mkv"), b
    assert cell_len(a) <= r["fichier"], (a, r["fichier"])
