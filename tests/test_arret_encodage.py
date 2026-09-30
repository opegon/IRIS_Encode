"""
tests/test_arret_encodage.py — UX-01, UX-02, UX-05 : une frappe ne jette plus
des heures d'encodage.

- **UX-02** — `⌫`/`Esc` pendant un encodage arrêtait ffmpeg et effaçait la
  sortie partielle sans rien demander.
- **UX-01** — `Ctrl+Home` dépilait l'écran et laissait ffmpeg tourner.
- **UX-05** — `↵` dans le dry-run lançait l'encodage.

Les processus sont simulés : un faux ffmpeg qui tourne jusqu'à ce qu'on
l'arrête, et qui écrit sa sortie comme le vrai.
"""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import pytest
from textual.app import App
from textual.screen import Screen

from core.decision import DVAction, FileDecision, VideoAction, VideoDecision
from core.platform import GPU, OS, PlatformProfile
from core.scanner import VideoInfo
from tui.screens import run as run_mod
from tui.screens.confirm import ConfirmModal
from tui.screens.dryrun import DryrunScreen
from tui.screens.run import RunScreen


class _FauxFfmpeg:
    """Tourne jusqu'à `terminate()` ; un code non nul, comme un vrai arrêt."""

    lances: list["_FauxFfmpeg"] = []

    def __init__(self, cmd, duration=0.0):
        self.sortie  = Path(cmd[-1])
        self.arrete  = False
        self._fin    = threading.Event()
        _FauxFfmpeg.lances.append(self)

    def start(self):
        self.sortie.write_bytes(b"partiel")

    def iter_progress(self):
        self._fin.wait(10)
        yield from ()

    def terminate(self):
        self.arrete = True
        self._fin.set()

    def wait(self):
        self._fin.wait(10)
        return 1 if self.arrete else 0

    def finir(self):
        """Fin normale : code 0."""
        self._fin.set()

    def pause(self):  pass
    def resume(self): pass


class _Accueil(Screen):
    pass


_PLAT = PlatformProfile(os=OS.WINDOWS, gpu=GPU.NONE, hwaccel=None,
                        encoder_hevc="libx265", encoder_h264="libx264",
                        encoder_av1="libsvtav1")


class _App(App):
    def __init__(self, ecran):
        super().__init__()
        self._ecran = ecran
        self.platform = _PLAT
        self.active_profile_id = "test"
        self.lots_encodes = []
        self.profiles = {}
        self.cfg = {}

    def on_mount(self):
        self.push_screen(_Accueil())
        self.push_screen(self._ecran)


def _dec(path: Path) -> FileDecision:
    path.write_bytes(b"")
    info = VideoInfo(path=path, width=1920, height=1080, bitrate=8_000_000,
                     codec="h264", duration=60.0, frame_count=0,
                     dv_profile=None)
    return FileDecision(
        info=info, profile={},
        video=VideoDecision(action=VideoAction.ENCODE_HEVC, reason="",
                            target_bitrate=3_000_000, target_width=1920,
                            target_height=1080, dv_action=DVAction.NONE,
                            output_suffix=".hevc.IRIS"))


@pytest.fixture
def faux(monkeypatch):
    _FauxFfmpeg.lances = []
    monkeypatch.setattr(run_mod, "EncoderProcess", _FauxFfmpeg)
    monkeypatch.setattr(run_mod, "audio_prepass_needed", lambda d: False)
    monkeypatch.setattr(run_mod, "build_command",
                        lambda d, p, **k: ["ffmpeg", str(d.output_path)])
    # L'accueil de test n'est pas un BrowserScreen : dépiler suffit.
    monkeypatch.setattr(run_mod, "retour_accueil", lambda app: app.pop_screen())
    return _FauxFfmpeg.lances


async def _scenario(tmp_path: Path, touche: str, confirmer: bool) -> dict:
    decs = [_dec(tmp_path / "a.mkv"), _dec(tmp_path / "b.mkv")]
    ecran = RunScreen(decs, _PLAT)
    app = _App(ecran)
    releve: dict = {}
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        releve["en_cours"] = len(_FauxFfmpeg.lances)
        await pilot.press(touche)
        await pilot.pause(0.3)
        releve["modale"] = isinstance(app.screen, ConfirmModal)
        if releve["modale"]:
            if confirmer:
                await pilot.press("left", "enter")   # focus sur « Arrêter »
            else:
                await pilot.press("escape")
            await pilot.pause(0.5)
        releve["ecran"] = type(app.screen).__name__
        releve["arretes"] = [p.arrete for p in _FauxFfmpeg.lances]
        releve["lances"] = len(_FauxFfmpeg.lances)
        releve["sortie_a"] = decs[0].output_path.exists()
        ecran._abandon = True                     # ne rien laisser tourner
        for p in _FauxFfmpeg.lances:
            p.terminate()
        await pilot.pause(0.2)
    return releve


@pytest.mark.parametrize("touche", ["backspace", "escape", "ctrl+home"])
def test_quitter_un_encodage_demande_confirmation(faux, tmp_path, touche):
    r = asyncio.run(_scenario(tmp_path, touche, confirmer=False))
    assert r["en_cours"] == 1
    assert r["modale"], f"{touche} n'a rien demandé"
    assert r["ecran"] == "RunScreen"
    assert r["arretes"] == [False], "l'encodage s'est arrêté malgré « Continuer »"
    assert r["sortie_a"]


@pytest.mark.parametrize("touche", ["backspace", "ctrl+home"])
def test_confirmer_arrete_le_lot_entier(faux, tmp_path, touche):
    r = asyncio.run(_scenario(tmp_path, touche, confirmer=True))
    assert r["modale"]
    assert r["ecran"] == "_Accueil"
    assert r["arretes"] == [True], "ffmpeg tourne encore après le retour"
    assert r["lances"] == 1, "le fichier suivant a démarré en arrière-plan"
    assert not r["sortie_a"], "la sortie partielle n'a pas été effacée"


def test_un_abandon_entre_deux_etapes_n_en_demarre_pas_une_autre(faux, tmp_path):
    """Pas de processus au moment de l'arrêt : le suivant s'arrête au départ."""
    ecran = RunScreen([_dec(tmp_path / "a.mkv")], _PLAT)
    ecran._abandon = True
    proc = _FauxFfmpeg(["ffmpeg", str(tmp_path / "x.mkv")])
    ecran._demarrer(proc)
    assert proc.arrete


def test_entree_ne_lance_plus_l_encodage_depuis_le_dry_run():
    touches = {b.key: b.action for b in DryrunScreen.BINDINGS}
    assert "enter" not in touches, "↵ lance encore l'encodage (UX-05)"
    assert touches["f2"] == "run"


# ─── UX-04 : l'accueil suit le lot à son retour ──────────────────────────────

def test_seules_les_sources_reussies_se_decochent(tmp_path):
    from tui.screens.browser import sources_reussies
    from tui.screens.run import FileRunStatus, FileState

    a, b, c = (_dec(tmp_path / n) for n in ("a.mkv", "b.mkv", "c.mkv"))
    lot = [FileRunStatus(a, FileState.SUCCESS), FileRunStatus(b, FileState.ERROR),
           FileRunStatus(c, FileState.PENDING)]
    assert sources_reussies([lot]) == {a.info.path}


def test_l_ecran_d_encodage_annonce_son_lot(faux, tmp_path):
    async def _run():
        ecran = RunScreen([_dec(tmp_path / "a.mkv")], _PLAT)
        app = _App(ecran)
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            lots = list(app.lots_encodes)
            ecran._abandon = True
            for p in _FauxFfmpeg.lances:
                p.terminate()
            await pilot.pause(0.2)
        return lots, ecran._statuses
    lots, statuts = asyncio.run(_run())
    assert lots == [statuts]


# ─── UX-06 : quitter dit ce qui tourne vraiment ──────────────────────────────

def test_quitter_sans_rien_en_cours_ne_parle_pas_d_encodage():
    from tui.screens.quit import QuitConfirmScreen
    assert QuitConfirmScreen()._body == "Aucun traitement en cours."
    assert QuitConfirmScreen(["La mesure en cours sera perdue."])._body \
        == "La mesure en cours sera perdue."


def test_quitter_pendant_un_encodage_l_annonce_et_l_arrete(faux, tmp_path):
    from tui.app import IrisEncodeApp

    async def _run():
        ecran = RunScreen([_dec(tmp_path / "a.mkv")], _PLAT)
        app = _App(ecran)
        app._TRAVAUX = IrisEncodeApp._TRAVAUX
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            pendant = IrisEncodeApp.travaux_en_cours(app)
            IrisEncodeApp._on_quit_answer(app, True)
            await pilot.pause(0.3)
        return pendant, ecran._statuses[0].decision.output_path
    pendant, sortie = asyncio.run(_run())
    assert pendant == [IrisEncodeApp._TRAVAUX["encoder"]]
    assert [p.arrete for p in _FauxFfmpeg.lances] == [True]
    assert not sortie.exists()


# ─── UX-16 : la fin du lot dit la suite ──────────────────────────────────────

def test_fin_de_lot_bilan_et_pied_de_navigation(faux, monkeypatch, tmp_path):
    from textual.widgets import Static
    from tui.widgets.footer import KeyFooter

    monkeypatch.setattr(run_mod, "pistes_audio_vides", lambda *a, **k: [])

    async def _run():
        ecran = RunScreen([_dec(tmp_path / "a.mkv")], _PLAT)
        app = _App(ecran)
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            _FauxFfmpeg.lances[0].finir()
            await pilot.pause(0.5)
            pied = ecran.query_one(KeyFooter)
            return (ecran._done, list(pied._actions),
                    str(ecran.query_one("#cmd-lines", Static).render()),
                    ecran._statuses[0].decision.output_path)
    fini, actions, bilan, sortie = asyncio.run(_run())
    assert fini
    assert actions == [], "Pause et Passer restent proposés après la fin"
    assert "réussis : 1" in bilan and "en échec : 0" in bilan
    assert str(sortie) in bilan


# ─── UX-17 : une touche sans effet le dit ────────────────────────────────────

def test_f2_du_dry_run_sans_rien_a_encoder_le_dit(tmp_path):
    from dataclasses import replace

    dec = _dec(tmp_path / "a.mkv")
    dec.video = replace(dec.video, action=VideoAction.SKIP)

    async def _run():
        app = _App(DryrunScreen([dec]))
        async with app.run_test(size=(160, 40)) as pilot:
            await pilot.pause(0.5)
            await pilot.press("f2")
            await pilot.pause(0.3)
            return type(app.screen).__name__, [n.message for n in app._notifications]
    ecran, messages = asyncio.run(_run())
    assert ecran == "DryrunScreen"
    assert any("Rien à encoder" in m for m in messages), messages


# ─── UX-18 : une ligne SKIP cochée montre ce qui sera fait ───────────────────

def test_une_ligne_skip_cochee_affiche_la_decision_forcee(tmp_path, monkeypatch):
    from core import config as cfg_mod
    from tests.test_accueil import _clips
    from textual.widgets import DataTable
    from tui.app import IrisEncodeApp
    from tui.screens.browser import BrowserScreen

    if not _clips(tmp_path, 1):
        pytest.skip("ffmpeg introuvable")
    monkeypatch.setattr(cfg_mod, "save", lambda *a, **k: None)
    source = tmp_path / "clip0.mkv"

    async def _run():
        app = IrisEncodeApp(start_path=tmp_path)
        async with app.run_test(size=(160, 40)) as pilot:
            await pilot.pause(0.5)
            app.push_screen(BrowserScreen(tmp_path, start_virtual=False))
            await pilot.pause(3.0)
            ecran = app.screen
            table = ecran.query_one(DataTable)
            action = ecran._decisions[source].video.action
            avant = str(table.get_cell(str(source), "decision"))
            await pilot.press("space")
            await pilot.pause(0.3)
            coche = str(table.get_cell(str(source), "decision"))
            messages = [n.message for n in app._notifications]
            await pilot.press("space")
            await pilot.pause(0.3)
            apres = str(table.get_cell(str(source), "decision"))
        return action, avant, coche, apres, messages

    action, avant, coche, apres, messages = asyncio.run(_run())
    if action != VideoAction.SKIP:
        pytest.skip(f"le clip de test n'est pas SKIP ({action})")
    assert avant == "← SKIP"
    assert coche.startswith("→ H"), coche
    assert any("sera encodée" in m for m in messages), messages
    assert apres == "← SKIP"
