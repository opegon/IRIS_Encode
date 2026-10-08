"""
tests/test_veille.py — La machine reste éveillée tant qu'un traitement tourne,
et ne s'endort après un lot que si on l'a demandé.

Les appels Windows sont simulés : un faux moteur note ce qu'on lui demande.
Ce qui est vérifié ici, c'est *quand* l'application pose et retire la demande,
et quand l'action d'après lot part — pas l'API elle-même, qui ne s'éprouve que
sur une vraie machine Windows.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from textual.app import App
from textual.screen import Screen

import core.config as cfg_mod
from core import veille
from core.veille import GardeVeille
from tui.screens import run as run_mod
from tui.screens.fin_lot import FinDeLotModal


class _FauxMoteur:
    def __init__(self, accepte: bool = True) -> None:
        self.accepte  = accepte
        self.journal: list[tuple] = []
        self._n = 0

    def poser(self, motif):
        self.journal.append(("poser", motif))
        if not self.accepte:
            return None
        self._n += 1
        return ("demande", self._n)

    def retirer(self, jeton):
        self.journal.append(("retirer", jeton[1]))

    def executer(self, action):
        self.journal.append(("executer", action))
        return None


# ─── La garde ─────────────────────────────────────────────────────────────────

def test_le_meme_motif_ne_repose_rien():
    m = _FauxMoteur()
    g = GardeVeille(m)
    g.maintenir("encodage")
    g.maintenir("encodage")
    assert m.journal == [("poser", "encodage")]
    assert g.active


def test_un_nouveau_motif_pose_avant_de_retirer():
    """Jamais de trou entre deux demandes : la machine pourrait s'y endormir."""
    m = _FauxMoteur()
    g = GardeVeille(m)
    g.maintenir("encodage")
    g.maintenir("encodage, mesure")
    assert m.journal == [("poser", "encodage"), ("poser", "encodage, mesure"),
                         ("retirer", 1)]


def test_relacher_rend_la_machine_au_systeme():
    m = _FauxMoteur()
    g = GardeVeille(m)
    g.maintenir("encodage")
    g.relacher()
    g.relacher()
    assert m.journal == [("poser", "encodage"), ("retirer", 1)]
    assert not g.active


def test_une_demande_refusee_nest_pas_retentee_a_chaque_releve():
    m = _FauxMoteur(accepte=False)
    g = GardeVeille(m)
    for _ in range(3):
        g.maintenir("encodage")
    assert m.journal == [("poser", "encodage")]
    assert not g.active


def test_l_action_de_fin_relache_d_abord():
    m = _FauxMoteur()
    g = GardeVeille(m)
    g.maintenir("encodage")
    assert g.executer_fin("arret") is None
    assert m.journal[-2:] == [("retirer", 1), ("executer", "arret")]


def test_hors_windows_rien_ne_se_passe(monkeypatch):
    monkeypatch.setattr(veille, "disponible", lambda: False)
    g = GardeVeille()
    g.maintenir("encodage")
    assert not g.active
    assert g.executer_fin("veille") == "indisponible sur ce système"


# ─── La configuration ─────────────────────────────────────────────────────────

@pytest.mark.skipif(not veille.disponible(), reason="API Windows")
def test_le_vrai_moteur_pose_retire_et_prend_le_privilege():
    """Le seul contact avec l'API réelle : ni veille ni arrêt, seulement la
    demande d'éveil et le privilège qu'exige `SetSuspendState`. Sans
    signatures déclarées, ctypes levait sur le pseudo-handle du processus, et
    la mise en veille d'après lot faisait tomber l'application."""
    moteur = veille._MoteurWindows()
    jeton = moteur.poser("IRIS ENCODE : test")
    assert jeton is not None
    moteur.retirer(jeton)
    moteur._privilege_arret()


def test_bloquer_la_veille_est_active_par_defaut():
    cfg = cfg_mod._deep_merge({}, cfg_mod._DEFAULTS)
    assert cfg_mod.get_empecher_veille(cfg) is True
    # Après le lot, par défaut : rien. La machine ne change d'état que si on
    # l'a choisi dans les options.
    assert cfg_mod.get_action_fin(cfg) == "rien"


def test_une_action_inconnue_vaut_le_defaut():
    """config.toml s'édite à la main : une faute de frappe n'arrête pas la machine."""
    assert cfg_mod.get_action_fin({"energie": {"action_fin": "eteindre"}}) == "rien"
    assert cfg_mod.get_action_fin({"energie": {"action_fin": "arret"}}) == "arret"


# ─── L'application ────────────────────────────────────────────────────────────

from tui.app import IrisEncodeApp as _Iris
from tests.test_arret_encodage import _FauxFfmpeg, _PLAT, _dec, faux  # noqa: F401


class _Accueil(Screen):
    pass


class _App(App):
    """La file d'encodage et la veille, sans le reste de l'application."""

    MODE_FICHIERS  = _Iris.MODE_FICHIERS
    MODE_ENCODAGES = _Iris.MODE_ENCODAGES
    lot            = _Iris.lot
    sources_en_file = _Iris.sources_en_file
    encoder        = _Iris.encoder
    _mettre_en_file = _Iris._mettre_en_file
    _nouveau_lot   = _Iris._nouveau_lot
    _liberer_lot   = _Iris._liberer_lot
    etat_file      = _Iris.etat_file
    _NATURES          = _Iris._NATURES
    natures_en_cours  = _Iris.natures_en_cours
    fin_prevue        = _Iris.fin_prevue
    etat_veille       = _Iris.etat_veille
    surveiller_veille = _Iris.surveiller_veille
    armer_fin_de_lot  = _Iris.armer_fin_de_lot
    _lancer_decompte  = _Iris._lancer_decompte

    def __init__(self, decisions, cfg=None):
        super().__init__()
        self._depart = decisions
        self._lot = None
        self.platform = _PLAT
        self.active_profile_id = "test"
        self.lots_encodes = []
        self.profiles = {}
        self.cfg = cfg if cfg is not None else cfg_mod._deep_merge({}, cfg_mod._DEFAULTS)
        self.moteur = _FauxMoteur()
        self.veille = GardeVeille(self.moteur)
        self._fin_armee = False
        self._decompte  = False

    def on_mount(self):
        self.add_mode(self.MODE_FICHIERS, _Accueil)
        self.switch_mode(self.MODE_FICHIERS)
        self.encoder(self._depart)


def _cfg_veille():
    """Les options où l'on a choisi la mise en veille après le lot."""
    cfg = cfg_mod._deep_merge({}, cfg_mod._DEFAULTS)
    cfg["energie"]["action_fin"] = "veille"
    return cfg


@pytest.fixture
def windows(monkeypatch):
    monkeypatch.setattr(veille, "disponible", lambda: True)


def test_un_lot_en_cours_bloque_la_veille_et_sa_fin_la_rend(faux, tmp_path):
    async def _run():
        app = _App([_dec(tmp_path / "a.mkv")])
        async with app.run_test() as pilot:
            await pilot.pause(0.4)
            app.surveiller_veille()
            pendant = (app.veille.active, app.etat_veille())
            _FauxFfmpeg.lances[0].finir()
            await pilot.pause(0.6)
            app.surveiller_veille()
            apres = (app.veille.active, app.etat_veille())
        return pendant, apres, app.moteur.journal

    pendant, apres, journal = asyncio.run(_run())
    assert pendant == (True, "☾ veille bloquée")
    assert apres == (False, "")
    assert journal[0] == ("poser", "IRIS ENCODE : encodage en cours")
    assert not any(e[0] == "executer" for e in journal), \
        "une action d'après lot est partie sans qu'on l'ait demandée"


def test_l_option_decochee_laisse_la_veille(faux, tmp_path):
    cfg = cfg_mod._deep_merge({}, cfg_mod._DEFAULTS)
    cfg["energie"]["empecher_veille"] = False

    async def _run():
        app = _App([_dec(tmp_path / "a.mkv")], cfg)
        async with app.run_test() as pilot:
            await pilot.pause(0.4)
            app.surveiller_veille()
            actif = app.veille.active
            app.lot._abandon = True
            for p in _FauxFfmpeg.lances:
                p.terminate()
            await pilot.pause(0.2)
        return actif

    assert asyncio.run(_run()) is False


def test_apres_le_lot_compte_a_rebours_puis_agit(faux, windows, tmp_path,
                                                 monkeypatch):
    monkeypatch.setattr("tui.screens.fin_lot.COMPTE_A_REBOURS_S", 1)

    async def _run():
        app = _App([_dec(tmp_path / "a.mkv")], _cfg_veille())
        async with app.run_test() as pilot:
            await pilot.pause(0.4)
            lot = app.lot
            depart = lot.apres_lot
            await pilot.press("e")
            await pilot.pause(0.1)
            app.surveiller_veille()
            arme = (lot.apres_lot, app.etat_veille())
            _FauxFfmpeg.lances[0].finir()
            await pilot.pause(0.5)
            # Le relevé de l'application, toutes les cinq secondes en vrai : le
            # worker du dernier fichier vit encore quand le lot se dit fini.
            app.surveiller_veille()
            await pilot.pause(0.2)
            decompte = type(app.screen).__name__
            await pilot.pause(1.5)
        return depart, arme, decompte, app.moteur.journal

    depart, arme, decompte, journal = asyncio.run(_run())
    assert depart is False, "l'interrupteur doit partir de « non »"
    assert arme == (True, "☾ veille bloquée · puis mise en veille")
    assert decompte == "FinDeLotModal"
    assert journal[-1] == ("executer", "veille")


def test_un_lot_arrete_ne_declenche_rien(faux, windows, tmp_path):
    async def _run():
        app = _App([_dec(tmp_path / "a.mkv")], _cfg_veille())
        async with app.run_test() as pilot:
            await pilot.pause(0.4)
            await pilot.press("e")
            await pilot.press("x", "left", "enter")   # arrêter, confirmé
            await pilot.pause(0.5)
            app.surveiller_veille()
            await pilot.pause(0.2)
            ecran = type(app.screen).__name__
        return ecran, app._fin_armee, app.moteur.journal

    ecran, armee, journal = asyncio.run(_run())
    assert ecran != "FinDeLotModal" and not armee
    assert not any(e[0] == "executer" for e in journal)


def test_l_action_attend_que_tout_soit_fini(faux, windows, tmp_path, monkeypatch):
    """Une mesure qui tourne encore retient l'action d'après lot."""
    monkeypatch.setattr(_App, "natures_en_cours", lambda self: ["mesure"])

    async def _run():
        app = _App([_dec(tmp_path / "a.mkv")], _cfg_veille())
        async with app.run_test() as pilot:
            await pilot.pause(0.4)
            await pilot.press("e")
            _FauxFfmpeg.lances[0].finir()
            await pilot.pause(0.5)
            app.surveiller_veille()
            ecran = type(app.screen).__name__
            armee = app._fin_armee
        return ecran, armee

    ecran, armee = asyncio.run(_run())
    assert ecran == "RunScreen" and armee


def test_annuler_le_compte_a_rebours_ne_fait_rien(windows):
    class _A(App):
        def on_mount(self):
            self.rendu = "rien"
            self.push_screen(FinDeLotModal("arret", delai=30),
                             lambda ok: setattr(self, "rendu", ok))

    async def _run():
        app = _A()
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            titre = app.screen.query_one("#confirm-title").render()
            await pilot.press("enter")              # focus sur Annuler
            await pilot.pause(0.2)
        return str(titre), app.rendu

    titre, rendu = asyncio.run(_run())
    assert titre.startswith("Arrêt dans")
    assert rendu is False


def test_hors_windows_l_interrupteur_refuse(faux, monkeypatch, tmp_path):
    monkeypatch.setattr(veille, "disponible", lambda: False)

    async def _run():
        app = _App([_dec(tmp_path / "a.mkv")])
        async with app.run_test() as pilot:
            await pilot.pause(0.4)
            await pilot.press("e")
            arme = app.lot.apres_lot
            app.lot._abandon = True
            for p in _FauxFfmpeg.lances:
                p.terminate()
            await pilot.pause(0.2)
        return arme

    assert asyncio.run(_run()) is False


def test_les_natures_suivent_les_travaux_que_quitter_annonce():
    """Ce que F10 dit interrompre est ce qui doit tenir la machine éveillée."""
    assert set(_Iris._NATURES) == set(_Iris._TRAVAUX)


# ─── « Ne rien faire », le défaut ─────────────────────────────────────────────

def test_ne_rien_faire_n_appelle_pas_le_systeme():
    m = _FauxMoteur()
    assert GardeVeille(m).executer_fin("rien") is None
    assert not any(e[0] == "executer" for e in m.journal)


def test_par_defaut_e_n_arme_rien(faux, windows, tmp_path):
    async def _run():
        app = _App([_dec(tmp_path / "a.mkv")])
        async with app.run_test() as pilot:
            await pilot.pause(0.4)
            await pilot.press("e")
            await pilot.pause(0.1)
            arme = app.lot.apres_lot
            _FauxFfmpeg.lances[0].finir()
            await pilot.pause(0.5)
            app.surveiller_veille()
            await pilot.pause(0.2)
            ecran = type(app.screen).__name__
        return arme, ecran, app.moteur.journal

    arme, ecran, journal = asyncio.run(_run())
    assert arme is False
    assert ecran != "FinDeLotModal"
    assert not any(e[0] == "executer" for e in journal)


def test_passer_a_ne_rien_faire_desarme_un_lot_coche(faux, windows, tmp_path):
    """E coché avec la veille, puis « Ne rien faire » choisi pendant le lot."""
    async def _run():
        app = _App([_dec(tmp_path / "a.mkv")], _cfg_veille())
        async with app.run_test() as pilot:
            await pilot.pause(0.4)
            await pilot.press("e")
            await pilot.pause(0.1)
            app.cfg["energie"]["action_fin"] = "rien"
            app.surveiller_veille()
            annonce = app.etat_veille()
            _FauxFfmpeg.lances[0].finir()
            await pilot.pause(0.5)
            app.surveiller_veille()
            await pilot.pause(0.2)
            ecran = type(app.screen).__name__
        return annonce, ecran, app.moteur.journal

    annonce, ecran, journal = asyncio.run(_run())
    assert "puis" not in annonce
    assert ecran != "FinDeLotModal"
    assert not any(e[0] == "executer" for e in journal)
