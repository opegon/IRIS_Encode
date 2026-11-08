"""
tests/test_sar_ecran.py — Choisir la proportion d'une source sans SAR, à
l'écran (IE-173 2/3).

L'accueil signale la proportion seulement estimée ; l'écran des pistes et
l'assistant la font choisir par `P`, dans une fenêtre qui dit l'estimation et
ce qui la fonde. Ailleurs, `P` n'apparaît pas.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from textual.widgets import DataTable, Static

from core.decision import decide
from core.i18n import _
from core.profiles import Profile
from core.sar import estimer
from core.scanner import AudioTrack, VideoInfo
from tui.app import IrisEncodeApp
from tui.screens.sar import SarScreen
from tui.screens.tracks import TracksScreen
from tui.screens.wizard import Etape, WizardScreen
from tui.widgets.footer import KeyFooter


def _info(tmp_path: Path, douteuse=True) -> VideoInfo:
    p = tmp_path / "The Kid 1921.avi"
    p.write_bytes(b"")
    info = VideoInfo(path=p, width=720, height=480, bitrate=1_500_000,
                     codec="msmpeg4v3", duration=6000.0, frame_count=0,
                     dv_profile=None,
                     audio_tracks=[AudioTrack(index=0, codec="mp3", channels=2,
                                              language="fre", title="",
                                              bitrate=128_000)])
    if douteuse:
        info.sar_estimation = estimer(720, 480, (690, 468), (4 / 3,))
        info.sar_impose = info.sar_estimation.sar
    return info


def _decision(tmp_path, douteuse=True):
    return decide(_info(tmp_path, douteuse), Profile(id="t", data={
        "bitrate_480p_kbps": 1500, "bitrate_720p_kbps": 2000,
        "bitrate_1080p_kbps": 5000, "audio_languages": ["fre"]}))


def _touches(ecran) -> list[str]:
    return [k for k, _lib in ecran.query_one(KeyFooter)._actions]


def _ligne_video(ecran) -> str:
    table = ecran.query_one("#tracks-table", DataTable)
    return " | ".join(str(c) for c in table.get_row("v:0"))


async def _choisir(pilot, app, rang: int) -> None:
    """Dans la fenêtre ouverte par `P`, descend de `rang` lignes et valide."""
    await pilot.press("p")
    await pilot.pause(0.3)
    assert isinstance(app.screen, SarScreen)
    for _i in range(rang):
        await pilot.press("down")
    await pilot.press("enter")
    await pilot.pause(0.3)


# ─── La fenêtre ──────────────────────────────────────────────────────────────

def test_la_fenetre_dit_l_estimation_et_rend_le_sar(tmp_path):
    info = _info(tmp_path)
    rendus = []

    async def _scenario():
        app = IrisEncodeApp(start_path=tmp_path)
        async with app.run_test(size=(160, 45)) as pilot:
            await pilot.pause(0.3)
            app.push_screen(SarScreen(info), rendus.append)
            await pilot.pause(0.3)
            texte = str(app.screen.query_one("#sar-texte", Static).render())
            table = app.screen.query_one(DataTable)
            lignes = [str(table.get_row_at(i)[0]) for i in range(table.row_count)]
            await pilot.press("down", "enter")
            await pilot.pause(0.2)
            app.push_screen(SarScreen(info), rendus.append)
            await pilot.pause(0.3)
            await pilot.press("escape")
            await pilot.pause(0.2)
            return texte, lignes

    texte, lignes = asyncio.run(_scenario())
    assert _("{hyp}, probable — the film's original format").format(hyp="4:3") in texte
    assert "690x468" in texte and "1.33" in texte
    assert len(lignes) == 3
    assert lignes[0].startswith("→ 4:3") and "640x480" in lignes[0]
    assert _("(estimate)") in lignes[0]
    assert "852x480" in lignes[1]
    assert _("Leave as is (square pixels)") in lignes[2] and "720x480" in lignes[2]
    assert rendus == ["32:27", None]


# ─── L'écran des pistes ──────────────────────────────────────────────────────

def test_pistes_p_choisit_la_proportion(tmp_path):
    dec = _decision(tmp_path)

    async def _scenario():
        app = IrisEncodeApp(start_path=tmp_path)
        async with app.run_test(size=(200, 50)) as pilot:
            await pilot.pause(0.3)
            app.push_screen(TracksScreen(dec))
            await pilot.pause(0.4)
            ecran = app.screen
            avant = (_touches(ecran), _ligne_video(ecran))
            await _choisir(pilot, app, 1)
            return avant, _ligne_video(app.screen)

    (touches, avant), apres = asyncio.run(_scenario())
    assert "p" in touches
    assert "4:3 ?" in avant and "⚠" in avant
    assert "16:9" in apres and "16:9 ?" not in apres and "⚠" not in apres
    assert dec.info.sar_impose == "32:27" and dec.info.sar_confirme
    assert dec.info.largeur_affichee == 853


def test_pistes_sans_doute_pas_de_p(tmp_path):
    dec = _decision(tmp_path, douteuse=False)

    async def _scenario():
        app = IrisEncodeApp(start_path=tmp_path)
        async with app.run_test(size=(200, 50)) as pilot:
            await pilot.pause(0.3)
            app.push_screen(TracksScreen(dec))
            await pilot.pause(0.4)
            touches = _touches(app.screen)
            await pilot.press("p")
            await pilot.pause(0.3)
            return touches, type(app.screen)

    touches, ecran = asyncio.run(_scenario())
    assert "p" not in touches
    assert ecran is TracksScreen


# ─── L'assistant ─────────────────────────────────────────────────────────────

def test_assistant_p_a_l_etape_decision(tmp_path):
    dec = _decision(tmp_path)

    def _corps(ecran) -> str:
        return str(ecran.query_one("#wiz-corps", Static).render())

    async def _scenario():
        app = IrisEncodeApp(start_path=tmp_path)
        async with app.run_test(size=(180, 50)) as pilot:
            await pilot.pause(0.3)
            app.push_screen(WizardScreen(dec))
            await pilot.pause(0.3)
            ecran = app.screen
            touches_fichier = _touches(ecran)
            await pilot.press("enter")
            await pilot.pause(0.3)
            assert ecran._etape == Etape.DECISION
            avant = (_touches(ecran), _corps(ecran))
            await _choisir(pilot, app, 2)
            return touches_fichier, avant, _corps(app.screen)

    touches_fichier, (touches, avant), apres = asyncio.run(_scenario())
    assert "p" not in touches_fichier
    assert "p" in touches
    assert "⚠" in avant and "4:3" in avant
    assert _("Aspect ratio: {name}, chosen").format(name=_("square pixels")) in apres
    assert dec.info.sar_impose == "" and dec.info.sar_confirme


def test_assistant_sans_doute_pas_de_p(tmp_path):
    dec = _decision(tmp_path, douteuse=False)

    async def _scenario():
        app = IrisEncodeApp(start_path=tmp_path)
        async with app.run_test(size=(180, 50)) as pilot:
            await pilot.pause(0.3)
            app.push_screen(WizardScreen(dec))
            await pilot.pause(0.3)
            await pilot.press("enter")
            await pilot.pause(0.3)
            ecran = app.screen
            assert ecran._etape == Etape.DECISION
            touches = _touches(ecran)
            await pilot.press("p")
            await pilot.pause(0.3)
            return touches, type(app.screen)

    touches, ecran = asyncio.run(_scenario())
    assert "p" not in touches and "f6" in touches
    assert ecran is WizardScreen


# ─── L'accueil ───────────────────────────────────────────────────────────────

def test_accueil_signale_la_proportion_estimee(tmp_path, monkeypatch):
    import core.config as cfg_mod
    from tui.screens import browser
    from tui.screens.browser import _ROW_TYPE_FILE

    noms = ("The Kid 1921.avi", "Autre 1999.avi")
    for n in noms:
        (tmp_path / n).write_bytes(b"")

    def _scan(path):
        info = _info(tmp_path, douteuse=(path.name == noms[0]))
        info.path = path
        return info
    monkeypatch.setattr(browser, "scan", _scan)
    monkeypatch.setattr(cfg_mod, "save", lambda *a, **k: None)

    async def _scenario():
        app = IrisEncodeApp(start_path=tmp_path)
        async with app.run_test(size=(200, 45)) as pilot:
            await pilot.pause(0.5)
            ecran = app.screen
            ecran._nav.enter(tmp_path)
            ecran._refresh_view()
            for _i in range(150):
                await pilot.pause(0.1)
                if (sum(t == _ROW_TYPE_FILE for t, _p in ecran._rows) == 2
                        and not ecran._en_attente):
                    break
            await pilot.pause(0.3)
            table = ecran.query_one(DataTable)
            return {n: str(table.get_cell(str(tmp_path / n), "resolution")) for n in noms}

    cellules = asyncio.run(_scenario())
    assert cellules[noms[0]] == "720x480 ⚠"
    assert cellules[noms[1]] == "720x480"
