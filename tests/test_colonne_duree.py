"""
tests/test_colonne_duree.py — colonne « Duration » de l'écran d'encodage,
entre « Profile » et « Size → est. » : la durée du fichier source.
"""
from __future__ import annotations

import asyncio

from tests.test_arret_encodage import _App, _dec, faux  # noqa: F401 (fixture)


def test_duree_entre_profil_et_taille(tmp_path, faux):
    asyncio.run(_duree(tmp_path, faux))


async def _duree(tmp_path, faux):
    from textual.widgets import DataTable
    long = _dec(tmp_path / "long.mkv")
    long.info.duration = 2 * 3600 + 41 * 60 + 7.6     # 2 h 41 min 07 s
    app = _App([_dec(tmp_path / "a.mkv"), long])
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        table = app.screen.query_one(DataTable)
        cles = [c.value for c in table.columns]
        assert cles[cles.index("profile"):cles.index("size") + 1] == [
            "profile", "duration", "size"]
        assert str(table.get_cell("0", "duration")) == "1:00"
        assert str(table.get_cell("1", "duration")) == "2:41:07"
        for p in faux:
            p.terminate()
