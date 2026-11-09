"""
tests/test_accueil_chargements_croises.py — Un chargement périmé ne fige pas
l'accueil (IE-182).

Entrer dans un dossier pendant qu'un chargement tourne encore en lance un
second. Le premier, plus lent, publiait son relevé (`_releve`) après le second ;
la minuterie, qui ne relève que l'époque courante, ne reportait plus rien : les
lignes restaient « en attente » jusqu'à la fin de toute l'analyse. Le test
retient le premier chargement pendant son listage, le relâche une fois le relevé
du second publié, puis attend que les fichiers non retenus se remplissent.
"""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import pytest

from tests.test_accueil import _clips


async def _parcours(td: Path, premier_liste: threading.Event,
                    relache: threading.Event, porte: threading.Event) -> list[str]:
    from tui.app import IrisEncodeApp
    from tui.screens.browser import _ROW_TYPE_FILE

    app = IrisEncodeApp(start_path=td)
    async with app.run_test(size=(160, 40)) as pilot:
        assert premier_liste.wait(10), "le premier chargement n'a pas listé"
        ecran = app.screen
        ecran._nav.enter(td)
        ecran._refresh_view()                    # second chargement, époque suivante
        for _ in range(100):
            await pilot.pause(0.05)
            r = ecran._releve
            if r is not None and r.epoch == ecran._scan_epoch:
                break
        relache.set()                            # le premier reprend, périmé
        for _ in range(100):
            await pilot.pause(0.1)
            if sum(t == _ROW_TYPE_FILE for t, _p in ecran._rows) == 2:
                break
        lignes = [t for t, _p in ecran._rows]
        porte.set()                              # ne pas retenir la fermeture
        return lignes


def test_un_chargement_perime_ne_fige_pas_la_liste(tmp_path, monkeypatch):
    if not _clips(tmp_path, 4):
        pytest.skip("ffmpeg introuvable")
    from core import config as cfg_mod
    from tui.screens import browser
    from tui.widgets.file_tree import FileNavigator
    monkeypatch.setattr(cfg_mod, "save", lambda *a, **kw: None)

    premier_liste, relache, porte = (threading.Event() for _ in range(3))
    appels = []
    vrai_liste = FileNavigator.list_videos

    def liste_retenue(self):
        videos = vrai_liste(self)
        if not appels:
            appels.append(1)
            premier_liste.set()
            relache.wait(10)                     # le premier chargement attend ici
        return videos

    vrai_scan = browser.scan

    def scan_retenu(chemin: Path):
        if chemin.name in ("clip2.mkv", "clip3.mkv"):
            porte.wait(30)
        return vrai_scan(chemin)

    monkeypatch.setattr(FileNavigator, "list_videos", liste_retenue)
    monkeypatch.setattr(browser, "scan", scan_retenu)
    try:
        lignes = asyncio.run(_parcours(tmp_path.resolve(), premier_liste, relache,
                                       porte))
    finally:
        relache.set()
        porte.set()

    assert lignes == ["file", "file", "pending", "pending"]
