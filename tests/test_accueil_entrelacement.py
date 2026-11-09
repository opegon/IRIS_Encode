"""
tests/test_accueil_entrelacement.py — L'analyse d'entrelacement après la liste (v0.9.2.2).

Sondée pendant le listage, l'image des sources SD retenait la liste plus de
30 s sur un partage réseau (28,7 s pour un seul 1080p marqué entrelacé, relevé
du 2026-11-09), ses lignes en attente non cochables. Elle passe après : les
lignes se cochent tout de suite, et `F1` attend la fin de l'analyse de ses
fichiers — sans geler l'interface — avant d'ouvrir l'aperçu.
"""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import pytest

from tests.test_accueil import _clips


async def _parcours(td: Path, porte: threading.Event) -> dict:
    from tui.app import IrisEncodeApp
    from tui.screens.browser import _ROW_TYPE_FILE
    from tui.screens.dryrun import DryrunScreen

    releve: dict = {}
    app = IrisEncodeApp(start_path=td)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause(0.5)
        ecran = app.screen
        ecran._nav.enter(td)
        ecran._refresh_view()
        for _ in range(150):
            await pilot.pause(0.1)
            if not ecran._en_attente and ecran._rows:
                break
        releve["lignes"] = [t for t, _p in ecran._rows]
        releve["jauge"] = str(ecran.query_one("#scan-count").render())

        await pilot.press("a")                      # tout cocher
        releve["coches"] = len(ecran._selected)
        await pilot.press("f1")
        await pilot.pause(0.5)
        releve["apercu_pendant"] = isinstance(app.screen, DryrunScreen)
        await pilot.press("f1")                     # seconde touche : pas de doublon
        porte.set()
        for _ in range(100):
            await pilot.pause(0.1)
            if isinstance(app.screen, DryrunScreen):
                break
        releve["apercu_apres"] = isinstance(app.screen, DryrunScreen)
        await pilot.pause(0.5)
        releve["apercus"] = sum(isinstance(s, DryrunScreen) for s in app.screen_stack)
    releve["fichier"] = _ROW_TYPE_FILE
    return releve


def test_f1_attend_l_analyse_d_entrelacement(tmp_path, monkeypatch):
    if not _clips(tmp_path, 2):
        pytest.skip("ffmpeg introuvable")
    from core import config as cfg_mod
    from tui.screens import browser
    monkeypatch.setattr(cfg_mod, "save", lambda *args, **kwargs: None)

    # Les deux clips passent pour des sources SD à sonder ; la sonde attend
    # la porte, comme ffmpeg à travers un partage lent.
    porte = threading.Event()
    a_sonder: set[Path] = {(tmp_path / f"clip{i}.mkv").resolve() for i in range(2)}

    def en_attente(info) -> bool:
        return info.path.resolve() in a_sonder

    def sonder(info) -> None:
        porte.wait(30)
        a_sonder.discard(info.path.resolve())

    monkeypatch.setattr(browser, "entrelacement_en_attente", en_attente)
    monkeypatch.setattr(browser, "analyser_entrelacement", sonder)
    try:
        r = asyncio.run(_parcours(tmp_path.resolve(), porte))
    finally:
        porte.set()

    assert r["lignes"] == [r["fichier"]] * 2        # cochables avant la sonde
    assert "2" in r["jauge"]                        # la seconde passe se voit
    assert r["coches"] == 2
    assert not r["apercu_pendant"]
    assert r["apercu_apres"]
    assert r["apercus"] == 1
