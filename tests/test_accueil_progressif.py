"""
tests/test_accueil_progressif.py — Le dossier s'ouvre avant la fin de son analyse.

Entrer dans un dossier de nombreux fichiers laissait l'ancien affiché, sans
retour, jusqu'au dernier ffprobe. Les fichiers s'affichent désormais dès le
listage, en attente, puis se remplissent au fil de l'analyse, jauge à l'appui.
"""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import pytest
from textual.widgets import DataTable

from tests.test_accueil import _clips


async def _parcours(td: Path, porte: threading.Event) -> dict:
    from tui.app import IrisEncodeApp
    from tui.screens.browser import _ROW_TYPE_ATTENTE, _ROW_TYPE_FILE

    releve: dict = {}
    app = IrisEncodeApp(start_path=td)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause(0.5)
        ecran = app.screen
        ecran._nav.enter(td)
        ecran._refresh_view()
        for _ in range(150):
            await pilot.pause(0.1)
            if sum(t == _ROW_TYPE_FILE for t, _p in ecran._rows) == 2:
                break
        releve["pendant"] = [t for t, _p in ecran._rows]
        releve["jauge_pendant"] = ecran.query_one("#scan-bar").display

        # Une ligne en attente n'est pas encore un fichier qu'on coche.
        table = ecran.query_one(DataTable)
        table.move_cursor(row=2)
        await pilot.press("space")
        releve["coches_pendant"] = set(ecran._selected)

        table.move_cursor(row=3)
        porte.set()
        for _ in range(150):
            await pilot.pause(0.1)
            if not ecran._en_attente and not ecran.query_one("#scan-bar").display:
                break
        releve["apres"] = [t for t, _p in ecran._rows]
        releve["curseur_apres"] = ecran._current_row_info()[1].name
        releve["jauge_apres"] = ecran.query_one("#scan-bar").display
    releve["attente"] = _ROW_TYPE_ATTENTE
    releve["fichier"] = _ROW_TYPE_FILE
    return releve


def test_le_dossier_se_remplit_au_fil_de_l_analyse(tmp_path, monkeypatch):
    if not _clips(tmp_path, 4):
        pytest.skip("ffmpeg introuvable")
    from core import config as cfg_mod
    from tui.screens import browser
    monkeypatch.setattr(cfg_mod, "save", lambda *a, **k: None)

    porte = threading.Event()
    vrai_scan = browser.scan

    def scan_retenu(chemin: Path):
        if chemin.name in ("clip2.mkv", "clip3.mkv"):
            porte.wait(30)
        return vrai_scan(chemin)

    monkeypatch.setattr(browser, "scan", scan_retenu)
    try:
        r = asyncio.run(_parcours(tmp_path.resolve(), porte))
    finally:
        porte.set()

    f, a = r["fichier"], r["attente"]
    assert r["pendant"] == [f, f, a, a]
    assert r["jauge_pendant"]
    assert r["coches_pendant"] == set()
    assert r["apres"] == [f, f, f, f]
    assert r["curseur_apres"] == "clip3.mkv"     # la vue finale ne ramène pas en haut
    assert not r["jauge_apres"]
