"""
tests/test_touches_et_libelles.py — Interface : palette, touches muettes,
libellés (IE-194 : CR-139, CR-141).

La règle UX-17 : une touche sans effet et sans message se lit comme une touche
cassée.
"""
from __future__ import annotations

import asyncio
import html
import re
from pathlib import Path
from types import SimpleNamespace

from textual.widgets import DataTable
from textual.widgets._header import HeaderIcon

from core.decision import decide
from core.i18n import ngettext
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo
from tui.app import IrisEncodeApp
from tui.screens.tracks import TracksScreen


# ─── CR-139 : pas de palette de commandes Textual ─────────────────────────────

def test_ni_ctrl_p_ni_l_icone_n_ouvrent_la_palette(tmp_path):
    async def _scenario():
        app = IrisEncodeApp(start_path=tmp_path)
        async with app.run_test(size=(160, 45)) as pilot:
            await pilot.pause(0.3)
            depart = app.screen
            await pilot.press("ctrl+p")
            await pilot.pause(0.3)
            apres_touche = app.screen
            if apres_touche is not depart:      # ancienne palette : on la ferme
                await pilot.press("escape")
                await pilot.pause(0.3)
            await pilot.click(HeaderIcon)
            await pilot.pause(0.3)
            return depart, apres_touche, app.screen

    depart, apres_touche, apres_clic = asyncio.run(_scenario())
    assert apres_touche is depart
    assert apres_clic is depart


# ─── CR-141 (a) : plus de touche muette ──────────────────────────────────────

def _texte_ecran(app) -> str:
    texte = html.unescape(re.sub(r"<[^>]+>", "", app.export_screenshot()))
    return texte.replace("\xa0", " ")


def _decision_pistes(tmp_path: Path):
    p = tmp_path / "Film.mkv"
    p.write_bytes(b"")
    info = VideoInfo(path=p, width=1920, height=1080, bitrate=20_000_000,
                     codec="h264", duration=6000.0, frame_count=0, dv_profile=None,
                     audio_tracks=[AudioTrack(index=0, codec="ac3", channels=6,
                                              language="fre", title="",
                                              bitrate=448_000)])
    return decide(info, Profile(id="t", data={"bitrate_1080p_kbps": 5000,
                                              "audio_languages": ["fre"]}))


def _noter(dits: list):
    def _notify(message, **_options):
        dits.append(str(message))
    return _notify


def test_les_touches_sans_effet_de_l_ecran_des_pistes_le_disent(tmp_path):
    dec = _decision_pistes(tmp_path)
    dits: list[str] = []

    async def _scenario():
        app = IrisEncodeApp(start_path=tmp_path)
        async with app.run_test(size=(200, 50)) as pilot:
            await pilot.pause(0.3)
            app.push_screen(TracksScreen(dec))
            await pilot.pause(0.4)
            ecran = app.screen
            ecran.notify = _noter(dits)
            table = ecran.query_one(DataTable)
            table.move_cursor(row=table.get_row_index("a:0"))
            ecran.action_toggle_row()                 # piste d'origine
            table.move_cursor(row=table.get_row_index("v:0"))
            ecran._edit_idx = 2                       # champ DV, source sans DV
            ecran._change_value(+1)
            await pilot.pause(0.1)
            return list(ecran._sel_audio)

    selection = asyncio.run(_scenario())
    assert selection == [0]
    assert len(dits) == 2, dits


def test_p_pendant_une_etape_mkvmerge_le_dit():
    from tui.screens.run import RunScreen
    dits: list[str] = []
    faux = SimpleNamespace(app=SimpleNamespace(bell=lambda: None),
                           notify=_noter(dits), _process=None, _mux=object())
    RunScreen.action_pause_resume(faux)
    assert len(dits) == 1


# ─── CR-141 (b) (c) (e) : libellés ───────────────────────────────────────────

def _estimation_voisine(_dec, _taille):
    return 997_000


def _jamais_recopiee(_dec):
    return False


def test_un_ecart_arrondi_a_zero_n_a_pas_de_signe(monkeypatch):
    from tui.screens import browser
    monkeypatch.setattr(browser, "_estimate_output_bytes", _estimation_voisine)
    monkeypatch.setattr(browser, "_sortie_recopiee", _jamais_recopiee)
    _o, texte, _st = browser.texte_estimation(None, 1_000_000)
    assert "(0%)" in texte and "-0" not in texte


def test_und_s_affiche_comme_une_langue_inconnue():
    from tui.common import langue_affichee
    assert langue_affichee("und") == langue_affichee("") == "?"
    assert langue_affichee("fre") == "fre"


def test_une_notation_composee_garde_la_casse_des_modificateurs():
    from tui.common import touche
    assert touche("Ctrl+↑/↓") == "Ctrl+↑/↓"
    assert touche("ctrl+x") == "Ctrl+X"
    assert touche("f2") == "F2"


# ─── CR-141 (d) : la barre d'état de l'accueil à 80 colonnes ─────────────────

def test_un_chemin_long_laisse_voir_les_compteurs(tmp_path):
    profond = tmp_path
    for nom in ("un dossier au nom assez long", "puis un autre encore plus long",
                "et un troisieme pour faire bonne mesure"):
        profond = profond / nom
    profond.mkdir(parents=True)

    async def _scenario():
        app = IrisEncodeApp(start_path=tmp_path)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause(0.3)
            app.screen._nav.enter(profond)
            app.screen._refresh_view()
            await pilot.pause(0.6)
            compteur = ngettext("{selected}/{total} selected",
                                "{selected}/{total} selected", 0).format(
                selected=0, total=0)
            return compteur, _texte_ecran(app)

    compteur, ecran = asyncio.run(_scenario())
    assert compteur in ecran
