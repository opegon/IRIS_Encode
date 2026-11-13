"""
tests/test_fil_workers.py — Fil d'interface et workers (IE-191).

Revue de code du 2026-11-13 :

- **CR-124** — après un mux, la relecture du fichier (ffprobe, SAR, analyse
  d'entrelacement) et, à l'écran d'encodage, la chaîne prévue de chaque
  fichier se faisaient sur le fil d'interface : jusqu'à 30 s d'écran figé ;
- **CR-125** — une exception imprévue dans la boucle d'encodage ou dans un
  worker OpenSubtitles fermait l'application ;
- **CR-128** — `R` deux fois lançait deux scans récursifs, et l'aperçu
  s'empilait sur l'écran courant quel qu'il soit.
"""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace

from textual.screen import Screen

from core import scanner
from core.scanner import VideoInfo
from tests.test_arret_encodage import _App, _dec, _FauxFfmpeg, faux  # noqa: F401
from tui.screens import run as run_mod


def _hors_interface(fils: list[threading.Thread]) -> bool:
    return bool(fils) and all(f is not threading.main_thread() for f in fils)


# ─── CR-124 : rien de lent sur le fil d'interface ─────────────────────────────

class _FauxMux:
    errors: list = []
    def __init__(self, cmd): pass
    def start(self): pass
    def iter_progress(self): yield from ()
    def wait(self): return 0
    def terminate(self): pass


def test_le_fichier_muxé_se_relit_hors_du_fil_d_interface(tmp_path, monkeypatch):
    from tui.screens import mux_run
    from tests.test_sorties_protegees import _dec_mux

    dec = _dec_mux(tmp_path / "Film.mkv")
    fils: list[threading.Thread] = []
    relu: list[VideoInfo] = []

    def _scan(chemin):
        fils.append(threading.current_thread())
        info = VideoInfo(path=chemin, width=1920, height=1080, bitrate=8_000_000,
                         codec="h264", duration=60.0, frame_count=0, dv_profile=None)
        relu.append(info)
        return info

    def _entrelacement(info, mesurer=True):
        fils.append(threading.current_thread())
        info.entrelacement_lu = True

    monkeypatch.setattr(mux_run, "MuxProcess", _FauxMux)
    monkeypatch.setattr(mux_run, "build_mux_command", lambda s, t, o: ["mkvmerge"])
    monkeypatch.setattr(mux_run, "mkvmerge_reussi", lambda rc, sortie: True)
    monkeypatch.setattr(mux_run, "dossier_inscriptible", lambda d: True)
    monkeypatch.setattr(scanner, "scan", _scan)
    monkeypatch.setattr(scanner, "analyser_entrelacement", _entrelacement)

    async def _run():
        ecran = mux_run.MuxScreen(dec)
        app = _App(ecran)
        async with app.run_test() as pilot:
            for _i in range(20):
                await pilot.pause(0.1)
                if ecran._done:
                    break
            return ecran._ok, ecran._done

    ok, fini = asyncio.run(_run())
    assert ok and fini
    assert len(fils) == 2, "relecture ou analyse d'entrelacement manquante"
    assert _hors_interface(fils), "relecture du mux sur le fil d'interface"
    assert dec.info is relu[0] and dec.info.entrelacement_lu
    assert dec.external_tracks == []


def test_la_chaîne_prévue_se_calcule_hors_du_fil_d_interface(faux, tmp_path,
                                                             monkeypatch):
    fils: list[threading.Thread] = []

    def _prevue(decision, platform):
        fils.append(threading.current_thread())
        return "cpu", "cpu", "cpu"
    monkeypatch.setattr(run_mod, "chaine_prevue", _prevue)

    async def _run():
        from textual.widgets import DataTable
        app = _App([_dec(tmp_path / "a.mkv"), _dec(tmp_path / "b.mkv")])
        async with app.run_test() as pilot:
            await pilot.pause(0.5)
            table = app.screen.query_one(DataTable)
            attente = [str(table.get_cell("1", k)) for k in ("read", "filt", "enc")]
            app.lot._abandon = True
            for p in faux:
                p.terminate()
            await pilot.pause(0.2)
        return attente

    attente = asyncio.run(_run())
    assert _hors_interface(fils), "chaîne prévue calculée sur le fil d'interface"
    assert attente == ["CPU", "CPU", "CPU"], "la prévision n'a pas été affichée"


# ─── CR-125 : une exception imprévue ne ferme plus l'application ──────────────

def test_une_exception_imprévue_met_le_fichier_en_échec_et_le_lot_continue(
        faux, tmp_path, monkeypatch):
    def _build(d, p, **k):
        if d.info.path.name == "a.mkv":
            raise RuntimeError("réponse inattendue")
        return ["ffmpeg", str(d.output_path)]
    monkeypatch.setattr(run_mod, "build_command", _build)
    monkeypatch.setattr(run_mod, "chaine_prevue", lambda d, p: (None, None, None))

    async def _run():
        app = _App([_dec(tmp_path / "a.mkv"), _dec(tmp_path / "b.mkv")])
        async with app.run_test() as pilot:
            await pilot.pause(0.8)
            lot = app.lot
            releve = (lot.statuts[0].state, lot.statuts[0].last_line,
                      [Path(p.sortie).name.split(".")[0] for p in faux],
                      app.is_running)
            lot._abandon = True
            for p in faux:
                p.terminate()
            await pilot.pause(0.2)
        return releve

    etat, ligne, lances, vivante = asyncio.run(_run())
    assert vivante, "l'application s'est fermée"
    assert etat == run_mod.FileState.ERROR
    assert "réponse inattendue" in ligne
    assert lances == ["b"], "le fichier suivant n'a pas démarré"


def test_une_réponse_inattendue_d_opensubtitles_reste_dans_l_écran(monkeypatch):
    from tui.screens import opensubtitles as os_mod

    class _Client:
        def chercher(self, *a, **k):
            raise KeyError("data")
        def telecharger(self, *a, **k):
            raise TypeError("'NoneType' object is not subscriptable")

    monkeypatch.setattr(os_mod, "_client", lambda cfg: _Client())
    messages: list[str] = []
    ecran = SimpleNamespace(
        app=SimpleNamespace(cfg={}, call_from_thread=lambda f, *a: f(*a)),
        _video=Path("film.mkv"), _langues=["fre"], _nom=None, _client=_Client(),
        _echec=messages.append, _afficher=lambda r: None)
    os_mod.OpenSubtitlesScreen._chercher.__wrapped__(ecran)
    os_mod.OpenSubtitlesScreen._telecharger.__wrapped__(ecran, None)
    assert len(messages) == 2
    assert "data" in messages[0] and "NoneType" in messages[1]


# ─── CR-128 : un seul scan récursif, et l'aperçu au bon endroit ───────────────

def test_le_scan_récursif_ne_s_empile_pas_sur_un_autre_écran(tmp_path, monkeypatch):
    from tui.app import IrisEncodeApp
    from tui.screens import browser as br
    from tui.screens.dryrun import DryrunScreen

    dossier = tmp_path / "Films"
    dossier.mkdir()
    film = dossier / "film.mkv"
    film.write_bytes(b"")
    libere = threading.Event()
    scans: list[Path] = []

    def _scan_recursif(directory, progres=None):
        scans.append(directory)
        libere.wait(10)
        return [VideoInfo(path=film, width=1920, height=1080, bitrate=20_000_000,
                          codec="h264", duration=60.0, frame_count=0,
                          dv_profile=None)]
    monkeypatch.setattr(br, "scan_directory_recursive", _scan_recursif)
    monkeypatch.setattr(br, "entrelacement_en_attente", lambda info: False)

    class _Pistes(Screen):
        pass

    async def _run():
        releve: dict = {}
        app = IrisEncodeApp(start_path=tmp_path)
        async with app.run_test(size=(160, 40)) as pilot:
            await pilot.pause(0.5)
            accueil = br.BrowserScreen(tmp_path, start_virtual=False)
            app.push_screen(accueil)
            await pilot.pause(1.0)
            accueil._current_row_info = lambda: (br._ROW_TYPE_DIR, dossier)
            await pilot.press("r")
            await pilot.pause(0.3)
            await pilot.press("enter")            # lance le scan
            await pilot.pause(0.3)
            await pilot.press("r")                # pendant le scan
            await pilot.pause(0.3)
            releve["second_r"] = type(app.screen).__name__
            app.push_screen(_Pistes())            # l'utilisateur est ailleurs
            await pilot.pause(0.2)
            libere.set()
            await pilot.pause(1.0)
            releve["fin_ailleurs"] = type(app.screen).__name__
            app.pop_screen()
            await pilot.pause(0.3)
            await pilot.press("r")                # l'aperçu gardé s'ouvre
            await pilot.pause(0.5)
            releve["reprise"] = type(app.screen).__name__
            releve["scans"] = len(scans)
        return releve

    r = asyncio.run(_run())
    assert r["second_r"] == "BrowserScreen", "un second scan a été proposé"
    assert r["fin_ailleurs"] == "_Pistes", "l'aperçu s'est empilé ailleurs"
    assert r["reprise"] == DryrunScreen.__name__
    assert r["scans"] == 1
