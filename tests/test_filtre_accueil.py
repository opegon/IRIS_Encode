"""
tests/test_filtre_accueil.py — Filtrer l'accueil par type d'image, masquer les SKIP.

Dans un dossier de quarante films, retrouver les Dolby Vision ou écarter ce
qui n'a rien à faire demandait de lire la liste ligne à ligne. `L` filtre par
type d'image, `Z` masque les lignes SKIP. Une ligne cochée reste visible :
ce qui partira à l'encodage ne doit pas pouvoir disparaître de la vue.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from core.decision import VideoAction
from core.scanner import VideoInfo
from tui.screens.browser import (FILTRE_DV, FILTRE_TOUS, ligne_visible,
                                 options_filtre, type_image)


def _dec(nom: str, dv: int | None = None, compat: int | None = None,
         transfert: str = "", action: VideoAction = VideoAction.ENCODE_HEVC):
    info = VideoInfo(path=Path(f"{nom}.mkv"), width=3840, height=2160,
                     bitrate=20_000_000, codec="hevc", duration=60.0,
                     frame_count=0, dv_profile=dv, dv_bl_compat=compat,
                     color_transfer=transfert)
    return SimpleNamespace(info=info, video=SimpleNamespace(action=action))


DV81 = _dec("a", dv=8, compat=1, transfert="smpte2084")
DV7  = _dec("b", dv=7, transfert="smpte2084")
HDR  = _dec("c", transfert="smpte2084")
HLG  = _dec("d", transfert="arib-std-b67")
SDR  = _dec("e", action=VideoAction.SKIP)


@pytest.mark.parametrize("dec, attendu", [
    (DV81, "DV:P8.1"), (DV7, "DV:P7"), (HDR, "HDR"), (HLG, "HDR"), (SDR, "SDR"),
])
def test_type_image(dec, attendu):
    assert type_image(dec.info) == attendu


def test_filtre_dolby_vision_prend_tous_les_profils():
    visibles = [d for d in (DV81, DV7, HDR, SDR)
                if ligne_visible(d, FILTRE_DV, False, False)]
    assert visibles == [DV81, DV7]


def test_filtre_un_profil_precis():
    assert ligne_visible(DV81, "DV:P8.1", False, False)
    assert not ligne_visible(DV7, "DV:P8.1", False, False)


def test_masquer_skip():
    assert not ligne_visible(SDR, FILTRE_TOUS, True, False)
    assert ligne_visible(HDR, FILTRE_TOUS, True, False)


def test_une_ligne_cochee_reste_visible():
    assert ligne_visible(SDR, FILTRE_DV, True, cochee=True)


def test_options_limitees_aux_types_presents():
    cles = [c for c, _ in options_filtre([DV81, DV7, SDR])]
    assert cles == [FILTRE_TOUS, FILTRE_DV, "DV:P7", "DV:P8.1", "SDR"]


def test_options_portent_leur_nombre():
    libelles = dict(options_filtre([HDR, HLG, SDR]))
    assert libelles[FILTRE_TOUS].endswith("(3)")
    assert libelles["HDR"].endswith("(2)")
    assert FILTRE_DV not in libelles


# ─── Dans l'application ───────────────────────────────────────────────────────

def test_l_et_z_sur_l_accueil(tmp_path, monkeypatch):
    """`Z` masque les SKIP et l'annonce ; une ligne cochée survit au filtre ;
    `L` ne propose que les types présents."""
    import asyncio
    from textual.widgets import DataTable
    from core import config as cfg_mod
    from tests.test_accueil import _clips

    if not _clips(tmp_path, 3):
        pytest.skip("ffmpeg introuvable")
    monkeypatch.setattr(cfg_mod, "save", lambda *a, **k: None)

    async def _parcours() -> dict:
        from tui.app import IrisEncodeApp
        from tui.screens.browser import BrowserScreen
        r: dict = {}
        app = IrisEncodeApp(start_path=tmp_path)
        async with app.run_test(size=(160, 40)) as pilot:
            await pilot.pause(0.5)
            app.push_screen(BrowserScreen(tmp_path, start_virtual=False))
            await pilot.pause(3.0)
            ecran = app.screen
            # Décisions posées : le premier clip à encoder, les deux autres SKIP.
            premier, skip = ecran._dossier[0], ecran._dossier[1]
            for i, p in enumerate(ecran._dossier):
                ecran._decisions[p].video.action = (
                    VideoAction.ENCODE_HEVC if i == 0 else VideoAction.SKIP)
            await pilot.press("z")
            await pilot.pause(0.3)
            r["apres_z"] = [p for _, p in ecran._rows]
            r["barre"] = str(ecran.query_one("#status-bar").render())
            await pilot.press("z")
            await pilot.pause(0.3)
            await pilot.press("down", "space")  # coche une ligne SKIP
            await pilot.press("z")
            await pilot.pause(0.3)
            r["cochee"] = [p for _, p in ecran._rows]
            await pilot.press("l")
            await pilot.pause(0.3)
            r["picker"] = [str(table_.get_row_at(i)[0])
                           for table_ in [app.screen.query_one(DataTable)]
                           for i in range(table_.row_count)]
            r["premier"], r["skip"] = premier, skip
        return r

    r = asyncio.run(_parcours())
    assert r["apres_z"] == [r["premier"]]
    assert "sans SKIP" in r["barre"] and "2 masqués" in r["barre"]
    assert r["skip"] in r["cochee"], "une ligne cochée ne se masque pas"
    assert len(r["cochee"]) == 2
    assert len(r["picker"]) == 2 and "SDR (3)" in r["picker"][1]
