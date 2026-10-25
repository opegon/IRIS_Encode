"""
tests/test_tri_accueil.py — Trier l'accueil (O).

L'accueil listait les fichiers par nom seulement : retrouver les plus gros,
ou ceux qui gagneront le plus à l'encodage, demandait de lire toute la liste.
`O` trie par nom, taille, résolution, durée, débit, codec ou estimation ;
rechoisir le critère en place inverse le sens. Une valeur inconnue reste en
fin de liste, dans un sens comme dans l'autre.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from core.decision import VideoAction
from core.scanner import VideoInfo
from tui.screens.browser import TRI_NOM, trier


def _dec(nom: str, largeur: int = 1920, hauteur: int = 1080,
         debit: int = 8_000_000, codec: str = "h264", duree: float = 60.0,
         action: VideoAction = VideoAction.SKIP):
    info = VideoInfo(path=Path(f"{nom}.mkv"), width=largeur, height=hauteur,
                     bitrate=debit, codec=codec, duration=duree,
                     frame_count=0, dv_profile=None)
    return SimpleNamespace(info=info, video=SimpleNamespace(action=action),
                           audio=[])


A = _dec("a", largeur=3840, hauteur=2160, debit=20_000_000, codec="hevc", duree=30)
B = _dec("b", largeur=1280, hauteur=720,  debit=2_000_000,  codec="mpeg2video", duree=90)
C = _dec("c", debit=8_000_000, codec="av1", duree=0)       # durée inconnue
TAILLES = {A.info.path: 500, B.info.path: 3000, C.info.path: None}


def _noms(decs) -> list[str]:
    return [d.info.path.stem for d in decs]


def test_le_nom_garde_l_ordre_du_dossier():
    assert _noms(trier([A, B, C], TRI_NOM, False, TAILLES)) == ["a", "b", "c"]
    assert _noms(trier([A, B, C], TRI_NOM, True, TAILLES)) == ["c", "b", "a"]


@pytest.mark.parametrize("critere, decroissant, attendu", [
    ("taille",     True,  ["b", "a", "c"]),
    ("taille",     False, ["a", "b", "c"]),      # inconnue en fin, dans les deux sens
    ("resolution", True,  ["a", "c", "b"]),
    ("duree",      True,  ["b", "a", "c"]),
    ("duree",      False, ["a", "b", "c"]),
    ("debit",      True,  ["a", "c", "b"]),
    ("codec",      False, ["c", "a", "b"]),      # av1, hevc, mpeg2video
])
def test_tri_par_critere(critere, decroissant, attendu):
    assert _noms(trier([A, B, C], critere, decroissant, TAILLES)) == attendu


def test_estim_classe_du_plus_fort_gain_et_ecarte_les_skip(monkeypatch):
    from tui.screens import browser
    estimations = {"x": 100, "y": 900, "z": 0}       # z : SKIP, pas d'estimation
    monkeypatch.setattr(browser, "_estimate_output_bytes",
                        lambda d, t=None: estimations[d.info.path.stem])
    monkeypatch.setattr(browser, "_sortie_recopiee", lambda d: False)
    x, y, z = _dec("x"), _dec("y"), _dec("z")
    tailles = {d.info.path: 1000 for d in (x, y, z)}
    # x : −90 %, y : −10 %
    assert _noms(trier([z, y, x], "estim", False, tailles)) == ["x", "y", "z"]
    assert _noms(trier([z, y, x], "estim", True, tailles)) == ["y", "x", "z"]


# ─── Dans l'application ───────────────────────────────────────────────────────

def test_o_trie_l_accueil(tmp_path, monkeypatch):
    """`O` puis Taille range du plus gros au plus petit ; rechoisir Taille
    inverse le sens ; la barre d'état nomme le tri."""
    import asyncio
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
            r["dossier"] = list(ecran._dossier)
            # Tailles imposées : le dernier clip est le plus gros.
            for i, p in enumerate(ecran._dossier):
                ecran._tailles[p] = (i + 1) * 1000
            await pilot.press("o")
            await pilot.pause(0.3)
            await pilot.press("down", "enter")        # Taille
            await pilot.pause(0.3)
            r["taille"] = [p for _, p in ecran._rows]
            r["barre"] = str(ecran.query_one("#status-bar").render())
            await pilot.press("o")
            await pilot.pause(0.3)
            await pilot.press("enter")                # Taille encore : inverse
            await pilot.pause(0.3)
            r["inverse"] = [p for _, p in ecran._rows]
        return r

    r = asyncio.run(_parcours())
    assert r["taille"] == list(reversed(r["dossier"]))
    assert "▼" in r["barre"]
    assert r["inverse"] == r["dossier"]
