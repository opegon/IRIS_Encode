"""
tests/test_accueil.py — L'accueil sur un partage réseau, et sa racine.

Sur un partage réseau, chaque `<` ou `>` mettait plusieurs secondes à
s'afficher : le redimensionnement reconstruit la table, et chaque ligne
relisait la taille de son fichier — jusqu'à trois `stat()` par fichier et par
frappe. La taille est désormais relevée une fois, par le worker de scan.

`Ctrl+Home` ramenait au dossier de travail ; il ramène à la vraie racine, la
liste des volumes du système.
"""
from __future__ import annotations

import asyncio
import subprocess
import tempfile
from pathlib import Path

import pytest
from textual.widgets import DataTable

from tui.widgets.file_tree import FileNavigator


# ─── Navigation ───────────────────────────────────────────────────────────────

def test_aller_aux_volumes_est_la_racine(tmp_path):
    nav = FileNavigator(tmp_path)
    nav.enter(tmp_path)
    nav.aller_aux_volumes()
    assert nav.is_virtual
    assert nav.go_up() is False, "rien au-dessus des volumes"


def test_remonter_d_un_volume_rend_les_volumes(tmp_path):
    """Entrer dans un volume depuis la liste, puis remonter à sa racine,
    doit retomber sur la liste — pas sur le dossier ouvert avant elle."""
    ailleurs = tmp_path / "ailleurs"
    ailleurs.mkdir()
    nav = FileNavigator(ailleurs, start_virtual=True)
    volume = Path(tmp_path.anchor)
    nav.enter(volume)
    nav.go_up()
    assert nav.is_virtual


# ─── Dans l'application ───────────────────────────────────────────────────────

def _clips(td: Path, n: int) -> bool:
    from core import config as cfg_mod
    from core.preflight import get_tool_path
    ffmpeg = get_tool_path("ffmpeg", cfg_mod.get_bin_dir(cfg_mod.load()))
    if not ffmpeg:
        return False
    for i in range(n):
        subprocess.run(
            [str(ffmpeg), "-y", "-loglevel", "error",
             "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
             "-c:v", "libx264", str(td / f"clip{i}.mkv")],
            check=True, capture_output=True,
        )
    return True


async def _parcours(td: Path, compte_stat: list[Path]) -> dict:
    from tui.app import IrisEncodeApp
    from tui.screens.browser import BrowserScreen

    releve: dict = {}
    app = IrisEncodeApp(start_path=td)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause(0.5)
        app.push_screen(BrowserScreen(td, start_virtual=False))
        await pilot.pause(3.0)
        ecran = app.screen
        releve["lignes"] = ecran.query_one(DataTable).row_count
        releve["taille"] = str(ecran.query_one(DataTable).get_row_at(0)[2])

        compte_stat.clear()
        for touche in (">", ">", "<", "tab", "shift+tab"):
            await pilot.press(touche)
        await pilot.pause(0.3)
        releve["stat_pendant_resize"] = list(compte_stat)

        # Depuis un écran empilé, puis depuis l'accueil lui-même.
        await pilot.press("a")
        await pilot.press("f1")
        await pilot.pause(1.0)
        releve["dryrun"] = type(app.screen).__name__
        await pilot.press("ctrl+home")
        await pilot.pause(1.0)
        releve["apres_dryrun"] = (type(app.screen).__name__,
                                  app.screen._nav.is_virtual,
                                  [str(c.label) for c in
                                   app.screen.query_one(DataTable).columns.values()])

        app.screen._nav.enter(td)
        app.screen._refresh_view()
        await pilot.pause(2.0)
        await pilot.press("ctrl+home")
        await pilot.pause(1.0)
        releve["depuis_accueil"] = app.screen._nav.is_virtual
    return releve


@pytest.fixture(scope="module")
def parcours():
    with tempfile.TemporaryDirectory() as td_str:
        td = Path(td_str).resolve()
        if not _clips(td, 3):
            pytest.skip("ffmpeg introuvable")

        from core import config as cfg_mod
        compte: list[Path] = []
        stat_origine = Path.stat

        def stat_compte(self, *a, **k):
            if self.parent == td:
                compte.append(self)
            return stat_origine(self, *a, **k)

        # Fixture de module : elle passe avant la sauvegarde du conftest, qui
        # prendrait les chemins posés par l'application pour l'état d'origine.
        import importlib
        from tests.conftest import _GLOBALES
        globales = [(importlib.import_module(m), v,
                     getattr(importlib.import_module(m), v)) for m, v in _GLOBALES]

        save_origine = cfg_mod.save
        Path.stat = stat_compte                  # type: ignore[method-assign]
        cfg_mod.save = lambda *a, **k: None      # le test ne touche pas config.toml
        try:
            yield asyncio.run(_parcours(td, compte))
        finally:
            Path.stat = stat_origine             # type: ignore[method-assign]
            cfg_mod.save = save_origine
            for module, nom, valeur in globales:
                setattr(module, nom, valeur)


def test_la_taille_s_affiche_toujours(parcours):
    assert parcours["lignes"] == 3
    assert parcours["taille"] not in ("", "—"), parcours["taille"]


def test_redimensionner_ne_relit_pas_le_disque(parcours):
    assert parcours["stat_pendant_resize"] == [], (
        f"{len(parcours['stat_pendant_resize'])} stat() pendant le "
        "redimensionnement — chacun coûte un aller-retour sur un partage réseau"
    )


def test_ctrl_home_ramene_aux_volumes(parcours):
    assert parcours["dryrun"] == "DryrunScreen"
    ecran, virtuel, colonnes = parcours["apres_dryrun"]
    assert ecran == "BrowserScreen"
    assert virtuel, "Ctrl+Home est resté dans le dossier de travail"
    assert colonnes == ["Volume", "Espace libre", "Total", "Occupé"], colonnes


def test_ctrl_home_depuis_l_accueil(parcours):
    assert parcours["depuis_accueil"]


# ─── La colonne Fichier suit la fenêtre ───────────────────────────────────────

async def _largeurs_fichier(td: Path) -> list[int]:
    """Largeur de Fichier : à l'entrée (180), après 260 puis 220 colonnes, et
    au retour dans le dossier après un passage par les volumes en 240. Assez
    large pour que Fichier reste au-dessus de son plancher."""
    from tui.app import IrisEncodeApp

    def fichier(app) -> int:
        return app.screen.query_one(DataTable).columns.get("fichier").width

    releve: list[int] = []
    app = IrisEncodeApp(start_path=td)
    async with app.run_test(size=(180, 40)) as pilot:
        await pilot.pause(0.5)
        ecran = app.screen
        ecran._nav.enter(td)
        ecran._refresh_view()
        await pilot.pause(0.5)
        releve.append(fichier(app))
        for largeur in (260, 220):
            await pilot.resize_terminal(largeur, 40)
            await pilot.pause(0.5)
            releve.append(fichier(app))
        ecran._nav.aller_aux_volumes()
        ecran._refresh_view()
        await pilot.resize_terminal(240, 40)
        await pilot.pause(0.5)
        ecran._nav.enter(td)
        ecran._refresh_view()
        await pilot.pause(0.5)
        releve.append(fichier(app))
    return releve


def test_fichier_suit_la_largeur_de_la_fenetre(tmp_path, monkeypatch):
    """Fichier prend la place que les autres colonnes laissent : à l'entrée
    dans un dossier, et à chaque changement de taille de la fenêtre."""
    from core import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "save", lambda *a, **k: None)
    entree, a_260, a_220, retour_240 = asyncio.run(_largeurs_fichier(tmp_path))
    assert a_260 == entree + 80, (entree, a_260)
    assert a_220 == entree + 40, (entree, a_220)
    assert retour_240 == entree + 60, (entree, retour_240)
