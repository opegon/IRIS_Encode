"""
tests/test_accueil_revue.py — L'accueil et la navigation (IE-135 2/3,
constats CR-68, CR-75, CR-78, CR-80, CR-102 de `revue_code_2026-10-08.md`).
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from textual.widgets import DataTable, Static

from tui.widgets.file_tree import FileNavigator

RACINE = Path(__file__).resolve().parent.parent


def _source(rel: str) -> str:
    return (RACINE / rel).read_text(encoding="utf-8")


# ─── CR-68 — la lettre du lecteur reste ──────────────────────────────────────

def test_la_navigation_ne_suit_plus_les_liens():
    assert ".resolve()" not in _source("tui/widgets/file_tree.py")


def test_le_chemin_est_normalise(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    nav = FileNavigator(tmp_path / "a" / ".." / "b")
    assert nav.current == tmp_path / "b"


@pytest.mark.skipif(sys.platform != "win32", reason="jonction NTFS")
def test_une_jonction_garde_son_propre_chemin(tmp_path):
    """Même mécanisme que `subst` ou un lecteur réseau : `resolve()` suivait
    le lien jusqu'à sa cible (mesuré avec `subst` : `Z:\\Films` devenait le
    chemin du dossier visé)."""
    import _winapi
    cible = tmp_path / "cible"
    cible.mkdir()
    lien = tmp_path / "lien"
    _winapi.CreateJunction(str(cible), str(lien))
    try:
        nav = FileNavigator(tmp_path)
        nav.enter(lien)
        assert nav.current == lien
    finally:
        os.rmdir(lien)


# ─── CR-78 — l'espace des volumes se mesure dans le worker ───────────────────

def test_la_table_ne_mesure_pas_les_volumes():
    texte = _source("tui/screens/browser.py")
    peupler = texte[texte.index("def _populate_table"):texte.index("_FORCABLES =")]
    assert "_cellules_volume(" not in peupler and "disk_usage" not in peupler
    charger = texte[texte.index("def _load_directory"):texte.index("def action_open_profile_picker")]
    assert "_cellules_volume(" in charger


# ─── CR-75 — un fichier illisible se voit ────────────────────────────────────

def _ffmpeg():
    from core import config as cfg_mod
    from core.preflight import get_tool_path
    return get_tool_path("ffmpeg", cfg_mod.get_bin_dir(cfg_mod.load()))


async def _lignes(td: Path) -> tuple[list[str], str]:
    from tui.app import IrisEncodeApp
    from tui.screens.browser import BrowserScreen
    app = IrisEncodeApp(start_path=td)
    async with app.run_test(size=(180, 40)) as pilot:
        await pilot.pause(0.5)
        app.push_screen(BrowserScreen(td, start_virtual=False))
        await pilot.pause(3.0)
        table = app.screen.query_one(DataTable)
        lignes = [" ".join(str(c) for c in table.get_row_at(i))
                  for i in range(table.row_count)]
        barre = str(app.screen.query_one("#status-bar", Static).render())
    return lignes, barre


def test_un_fichier_tronque_reste_dans_la_liste():
    ffmpeg = _ffmpeg()
    if not ffmpeg:
        pytest.skip("ffmpeg absent")
    from core.i18n import _
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        subprocess.run([str(ffmpeg), "-y", "-loglevel", "error", "-f", "lavfi",
                        "-i", "testsrc=duration=1:size=320x240:rate=10",
                        "-c:v", "libx264", str(td / "bon.mkv")],
                       check=True, capture_output=True)
        (td / "abime.mkv").write_bytes((td / "bon.mkv").read_bytes()[:40])
        lignes, barre = asyncio.run(_lignes(td))
    marque = _("unreadable: {cause}").split("{")[0]
    assert len(lignes) == 2, lignes
    assert any("abime.mkv" in l and marque in l for l in lignes), lignes
    from core.i18n import ngettext
    assert ngettext("{count} unreadable", "{count} unreadable", 1).format(count=1) in barre


def test_un_dossier_tout_illisible_n_est_pas_vide():
    from core.i18n import _
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        (td / "abime.mkv").write_bytes(b"\x1aE\xdf\xa3 pas une video")
        lignes, _barre = asyncio.run(_lignes(td))
    assert not any(_("No video file in this folder") in l for l in lignes), lignes
    assert any("abime.mkv" in l for l in lignes)


# ─── CR-80 — un `on_key` d'écran sans `super()` garde la navigation ──────────

def test_plus_aucun_super_on_key():
    import ast
    for f in (RACINE / "tui").rglob("*.py"):
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if (isinstance(n, ast.Attribute) and n.attr == "on_key"
                    and isinstance(n.value, ast.Call)
                    and getattr(n.value.func, "id", "") == "super"):
                pytest.fail(f"{f.relative_to(RACINE)}:{n.lineno}")


def test_page_down_avance_d_une_page_exactement():
    """Même forme que TracksScreen et SyncScreen : un `on_key` propre, les
    mixins dessous. Textual appelle l'`on_key` de chaque classe de la MRO."""
    from textual.app import App
    from textual.events import Key
    from textual.screen import Screen
    from tui.mixins import TableNavMixin

    class Ecran(TableNavMixin, Screen):
        def compose(self):
            yield DataTable()

        def on_mount(self):
            t = self.query_one(DataTable)
            t.add_column("n")
            for i in range(200):
                t.add_row(str(i))
            t.focus()

        def on_key(self, event: Key) -> None:
            if event.key == "left":
                event.stop()
                event.prevent_default()

    async def _scenario():
        app = App()
        async with app.run_test(size=(60, 30)) as pilot:
            app.push_screen(Ecran())
            await pilot.pause(0.3)
            table = app.screen.query_one(DataTable)
            await pilot.press("pagedown")
            await pilot.pause(0.1)
            une = table.cursor_row
            await pilot.press("pagedown")
            await pilot.pause(0.1)
            return une, table.cursor_row

    une, deux = asyncio.run(_scenario())
    assert une > 0, "la navigation du mixin a disparu"
    assert deux == 2 * une, (une, deux)


# ─── CR-102 — le guide dit ce que le code fait ───────────────────────────────

def test_le_guide_ne_promet_plus_de_profils_proteges():
    assert "are protected" not in _source("tui/screens/aide.py")


def test_r_sur_une_ligne_de_fichier_le_dit():
    from tui.screens.browser import BrowserScreen, _ROW_TYPE_FILE
    notes = []
    ecran = SimpleNamespace(
        _current_row_info=lambda: (_ROW_TYPE_FILE, Path("film.mkv")),
        notify=lambda texte, **k: notes.append(texte))
    BrowserScreen.action_recursive_run(ecran)
    assert notes, "R sans effet ni message"
