"""
tests/test_arret_encodage.py — UX-01, UX-02, UX-05, IE-100 : une frappe ne
jette plus des heures d'encodage, et la navigation reste libre.

- **UX-02** — `⌫`/`Esc` pendant un encodage arrêtait ffmpeg et effaçait la
  sortie partielle sans rien demander.
- **UX-01** — `Ctrl+Home` dépilait l'écran et laissait ffmpeg tourner.
- **UX-05** — `↵` dans le dry-run lançait l'encodage.
- **IE-100** — le lot vit dans son propre mode : `⌫` rend la navigation sans
  rien arrêter, `X` arrête tout après confirmation, `F2` ajoute à la file.

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


from tui.app import IrisEncodeApp as _Iris


class _App(App):
    """La vraie file d'encodage, sans le reste de l'application."""

    BINDINGS       = [b for b in _Iris.BINDINGS if b.action == "encodages"]
    MODE_FICHIERS  = _Iris.MODE_FICHIERS
    MODE_ENCODAGES = _Iris.MODE_ENCODAGES
    lot            = _Iris.lot
    sources_en_file = _Iris.sources_en_file
    encoder        = _Iris.encoder
    _nouveau_lot   = _Iris._nouveau_lot
    _liberer_lot   = _Iris._liberer_lot
    action_encodages = _Iris.action_encodages
    etat_file      = _Iris.etat_file

    def __init__(self, decisions):
        super().__init__()
        self._depart = decisions
        self._lot = None
        self.platform = _PLAT
        self.active_profile_id = "test"
        self.lots_encodes = []
        self.profiles = {}
        self.cfg = {}

    def on_mount(self):
        self.add_mode(self.MODE_FICHIERS, _Accueil)
        self.switch_mode(self.MODE_FICHIERS)
        if isinstance(self._depart, Screen):      # un écran de travail à tester
            self.push_screen(self._depart)
        else:
            self.encoder(self._depart)


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
                            output_suffix=".hevc-iris"))


@pytest.fixture
def faux(monkeypatch):
    _FauxFfmpeg.lances = []
    monkeypatch.setattr(run_mod, "EncoderProcess", _FauxFfmpeg)
    monkeypatch.setattr(run_mod, "audio_prepass_needed", lambda d: False)
    monkeypatch.setattr(run_mod, "build_command",
                        lambda d, p, **k: ["ffmpeg", str(d.output_path)])
    # L'accueil de test n'est pas un BrowserScreen : il est déjà la racine.
    monkeypatch.setattr(run_mod, "retour_accueil", lambda app: None)
    return _FauxFfmpeg.lances


def _sortie(app, i: int = 0) -> Path:
    """La décision est copiée à l'ajout : c'est celle du lot qui fait foi."""
    return app.lot.statuts[i].decision.output_path


async def _scenario(tmp_path: Path, touches: tuple[str, ...]) -> dict:
    decs = [_dec(tmp_path / "a.mkv"), _dec(tmp_path / "b.mkv")]
    app = _App(decs)
    releve: dict = {}
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        lot = app.lot
        releve["en_cours"] = len(_FauxFfmpeg.lances)
        for t in touches:
            await pilot.press(t)
            await pilot.pause(0.4)
        releve["ecran"]   = type(app.screen).__name__
        releve["mode"]    = app.current_mode
        releve["arretes"] = [p.arrete for p in _FauxFfmpeg.lances]
        releve["lances"]  = len(_FauxFfmpeg.lances)
        releve["sortie_a"] = lot.statuts[0].decision.output_path.exists()
        releve["termine"] = lot.termine
        lot._abandon = True                       # ne rien laisser tourner
        for p in _FauxFfmpeg.lances:
            p.terminate()
        await pilot.pause(0.2)
    return releve


@pytest.mark.parametrize("touche", ["backspace", "escape", "ctrl+home", "f12"])
def test_quitter_la_vue_des_encodages_ne_les_arrete_pas(faux, tmp_path, touche):
    """IE-100 : la navigation reprend, ffmpeg continue, rien n'est effacé."""
    r = asyncio.run(_scenario(tmp_path, (touche,)))
    assert r["en_cours"] == 1
    assert r["mode"] == "fichiers" and r["ecran"] == "_Accueil"
    assert r["arretes"] == [False], "l'encodage s'est arrêté en quittant la vue"
    assert r["sortie_a"] and not r["termine"]


def test_f12_rouvre_la_vue_des_encodages(faux, tmp_path):
    r = asyncio.run(_scenario(tmp_path, ("backspace", "f12")))
    assert r["mode"] == "encodages" and r["ecran"] == "RunScreen"
    assert r["arretes"] == [False]


def test_arreter_tout_demande_confirmation(faux, tmp_path):
    r = asyncio.run(_scenario(tmp_path, ("x", "escape")))
    assert r["ecran"] == "RunScreen"
    assert r["arretes"] == [False], "l'encodage s'est arrêté malgré « Continuer »"
    assert not r["termine"]


def test_confirmer_arrete_le_lot_entier(faux, tmp_path):
    r = asyncio.run(_scenario(tmp_path, ("x", "left", "enter")))
    assert r["arretes"] == [True], "ffmpeg tourne encore après l'arrêt"
    assert r["lances"] == 1, "le fichier suivant a démarré en arrière-plan"
    assert not r["sortie_a"], "la sortie partielle n'a pas été effacée"
    assert r["termine"]


def test_un_ajout_pendant_l_encodage_rejoint_la_file(faux, monkeypatch, tmp_path):
    """IE-100 : un F2 pendant un encodage ajoute ; un doublon est refusé."""
    monkeypatch.setattr(run_mod, "pistes_audio_vides", lambda *a, **k: [])

    async def _run():
        a, b = _dec(tmp_path / "a.mkv"), _dec(tmp_path / "b.mkv")
        app = _App([a])
        async with app.run_test() as pilot:
            await pilot.pause(0.4)
            await pilot.press("backspace")        # retour à la navigation
            await pilot.pause(0.2)
            lot = app.lot
            app.encoder([b, a])                   # b rejoint, a est déjà là
            await pilot.pause(0.2)
            noms = [s.decision.info.path.name for s in lot.statuts]
            mode = app.current_mode
            _FauxFfmpeg.lances[0].finir()         # a fini : b démarre
            await pilot.pause(0.6)
            lances = len(_FauxFfmpeg.lances)
            lot._abandon = True
            for p in _FauxFfmpeg.lances:
                p.terminate()
            await pilot.pause(0.2)
        return noms, mode, lances
    noms, mode, lances = asyncio.run(_run())
    assert noms == ["a.mkv", "b.mkv"], "doublon accepté ou ajout perdu"
    assert mode == "fichiers", "l'ajout a quitté la navigation"
    assert lances == 2, "le fichier ajouté n'a pas été encodé à la suite"


def test_les_reglages_sont_figes_a_l_ajout(faux, tmp_path):
    """IE-100 : la file travaille sur une copie de la décision."""
    async def _run():
        a = _dec(tmp_path / "a.mkv")
        app = _App([a])
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            a.video.target_bitrate = 1
            fige = app.lot.statuts[0].decision.video.target_bitrate
            app.lot._abandon = True
            for p in _FauxFfmpeg.lances:
                p.terminate()
            await pilot.pause(0.2)
        return fige
    assert asyncio.run(_run()) == 3_000_000


def test_l_entete_annonce_la_file(faux, tmp_path):
    """IE-100 : le bandeau central dit où en est la file, et F12."""
    async def _run():
        app = _App([_dec(tmp_path / "a.mkv")])
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            dans_vue = app.etat_file()
            await pilot.press("backspace")
            await pilot.pause(0.2)
            navigation = app.etat_file()
            app.lot._abandon = True
            for p in _FauxFfmpeg.lances:
                p.terminate()
            await pilot.pause(0.2)
        return dans_vue, navigation
    dans_vue, navigation = asyncio.run(_run())
    assert dans_vue == "F12 Fichiers"
    assert navigation.startswith("F12 Encodages en cours · 0/1")


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
        app = _App([_dec(tmp_path / "a.mkv")])
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            ecran = app.lot
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
        app = _App([_dec(tmp_path / "a.mkv"), _dec(tmp_path / "b.mkv")])
        app._TRAVAUX = IrisEncodeApp._TRAVAUX
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            await pilot.press("backspace")        # le lot n'est plus affiché
            await pilot.pause(0.2)
            pendant = IrisEncodeApp.travaux_en_cours(app)
            sortie = _sortie(app)
            IrisEncodeApp._on_quit_answer(app, True)
            await pilot.pause(0.3)
        return pendant, sortie
    pendant, sortie = asyncio.run(_run())
    # Le texte affiché, en français : celui de `_TRAVAUX` traduit.
    assert pendant == ["L'encodage en cours sera arrêté, sa sortie partielle effacée.",
                       "1 fichier en attente ne sera pas encodé."]
    assert [p.arrete for p in _FauxFfmpeg.lances] == [True]
    assert not sortie.exists()


# ─── UX-16 : la fin du lot dit la suite ──────────────────────────────────────

def test_fin_de_lot_bilan_et_pied_de_navigation(faux, monkeypatch, tmp_path):
    from textual.widgets import Static
    from tui.widgets.footer import KeyFooter

    monkeypatch.setattr(run_mod, "pistes_audio_vides", lambda *a, **k: [])

    async def _run():
        app = _App([_dec(tmp_path / "a.mkv")])
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            ecran = app.lot
            _FauxFfmpeg.lances[0].finir()
            await pilot.pause(0.5)
            pied = ecran.query_one(KeyFooter)
            releve = (ecran._done, list(pied._actions),
                      str(ecran.query_one("#cmd-lines", Static).render()),
                      _sortie(app))
            # Bilan vu, vue quittée : le lot est oublié (IE-100).
            await pilot.press("backspace")
            await pilot.pause(0.4)
            return releve + (app.lot,)
    fini, actions, bilan, sortie, reste = asyncio.run(_run())
    assert fini
    assert actions == [], "Pause et Passer restent proposés après la fin"
    assert "réussis : 1" in bilan and "en échec : 0" in bilan
    assert str(sortie) in bilan
    assert reste is None, "le bilan vu reste en file après être sorti de la vue"


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


# ─── IE-100 : la file se réordonne ───────────────────────────────────────────

def test_la_file_se_reordonne_et_se_vide_de_ce_qui_attend(faux, tmp_path):
    async def _run():
        decs = [_dec(tmp_path / f"{n}.mkv") for n in "abcd"]
        app = _App(decs)
        async with app.run_test() as pilot:
            await pilot.pause(0.4)
            lot = app.lot
            table = lot.query_one("#file-table")
            noms = lambda: [s.decision.info.path.name[0] for s in lot.statuts]
            table.move_cursor(row=3); await pilot.press("ctrl+up"); await pilot.pause(0.2)
            apres_monter = noms()
            table.move_cursor(row=0); await pilot.press("ctrl+down"); await pilot.pause(0.2)
            en_cours_fixe = noms()
            table.move_cursor(row=1); await pilot.press("delete"); await pilot.pause(0.2)
            apres_retrait = noms()
            table.move_cursor(row=0); await pilot.press("delete"); await pilot.pause(0.2)
            en_cours_garde = noms()
            lot._abandon = True
            for p in _FauxFfmpeg.lances:
                p.terminate()
            await pilot.pause(0.2)
        return apres_monter, en_cours_fixe, apres_retrait, en_cours_garde
    monter, fixe, retrait, garde = asyncio.run(_run())
    assert monter == list("abdc")
    assert fixe == list("abdc"), "le fichier en cours a été déplacé"
    assert retrait == list("adc")
    assert garde == list("adc"), "le fichier en cours a été retiré"
