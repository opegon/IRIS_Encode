"""
tests/test_cles.py — Les clés d'API se saisissent sans éditer config.toml (IE-101).

Les services réels ne sont pas appelés : les vérificateurs sont remplacés, et
l'écriture de config.toml aussi — un test ne touche jamais au fichier réel.
"""
from __future__ import annotations

import asyncio

import pytest
from textual.app import App
from textual.widgets import Checkbox, Input, Static

from core import cles
from tui.screens import cles as ecran_cles
from tui.screens.cles import ClesScreen


# ─── Ce qui manque ────────────────────────────────────────────────────────────

def test_une_configuration_vide_demande_les_deux_services():
    assert [s.id for s in cles.a_demander({})] == ["opensubtitles", "omdb"]


def test_le_compte_opensubtitles_n_est_pas_requis():
    """Sans compte on cherche encore : seule la clé rend le service manquant."""
    cfg = {"opensubtitles": {"api_key": "K"}, "meta": {"omdb_api_key": "O"}}
    assert cles.a_demander(cfg) == []


def test_un_service_ecarte_n_est_plus_demande():
    cfg = {"cles": {"ne_plus_demander": ["omdb"]}}
    assert [s.id for s in cles.a_demander(cfg)] == ["opensubtitles"]
    assert [s.id for s in cles.manquants(cfg)] == ["opensubtitles", "omdb"]


def test_un_compte_a_moitie_rempli_est_refuse_sans_appel():
    assert "aucun des deux" in cles.verifier_opensubtitles(
        {"api_key": "K", "username": "moi", "password": ""})


# ─── La fenêtre ───────────────────────────────────────────────────────────────

class _App(App):
    def __init__(self, cfg, services, au_lancement=True):
        super().__init__()
        self.cfg = cfg
        self._args = (services, au_lancement)
        self.resultat = "rien"

    def on_mount(self):
        self.push_screen(ClesScreen(*self._args),
                         lambda r: setattr(self, "resultat", r))


@pytest.fixture
def sans_reseau(monkeypatch):
    ecrits = []
    monkeypatch.setattr("core.config.save", lambda cfg: ecrits.append(1))
    monkeypatch.setattr(ecran_cles.webbrowser, "open", lambda url: None)
    verif = {"omdb": None, "opensubtitles": None}
    monkeypatch.setattr(cles, "VERIFICATEURS", {
        sid: (lambda s, sid=sid: verif[sid]) for sid in verif})
    return verif, ecrits


def _scenario(cfg, services, gestes, au_lancement=True):
    async def _run():
        app = _App(cfg, services, au_lancement)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            ecran = app.screen
            for geste in gestes:
                await geste(ecran, pilot)
                await pilot.pause(0.4)
            etats = {s.id: str(ecran.query_one(f"#etat-{s.id}", Static).render())
                     for s in services} if app.screen is ecran else {}
            return app.resultat, etats
    return asyncio.run(_run())


def _saisir(champ, valeur):
    async def g(ecran, pilot):
        ecran.query_one(f"#champ-{champ}", Input).value = valeur
    return g


def _touche(nom):
    async def g(ecran, pilot):
        await pilot.press(nom)
    return g


def _cliquer(bouton):
    async def g(ecran, pilot):
        await pilot.click(f"#{bouton}")
    return g


def _cocher(sid):
    async def g(ecran, pilot):
        ecran.query_one(f"#ecarter-{sid}", Checkbox).value = True
    return g


def test_une_cle_acceptee_est_enregistree(sans_reseau):
    _, ecrits = sans_reseau
    cfg = {}
    resultat, _ = _scenario(cfg, [cles.PAR_ID["omdb"]],
                            [_saisir("omdb-omdb_api_key", "abc123"),
                             _touche("ctrl+s")])
    assert resultat is True
    assert cfg["meta"]["omdb_api_key"] == "abc123"
    assert ecrits, "config.toml n'a pas été écrit"


def test_une_cle_refusee_n_est_pas_enregistree(sans_reseau):
    verif, _ = sans_reseau
    verif["opensubtitles"] = "Clé d'API refusée par OpenSubtitles."
    cfg = {}
    resultat, etats = _scenario(cfg, [cles.PAR_ID["opensubtitles"]],
                                [_saisir("opensubtitles-api_key", "faux"),
                                 _touche("ctrl+s")])
    assert resultat == "rien", "la fenêtre s'est fermée sur un refus"
    assert "refusée" in etats["opensubtitles"]
    assert cfg.get("opensubtitles", {}).get("api_key", "") == ""


def test_ne_plus_demander_est_retenu_sans_cle(sans_reseau):
    cfg = {}
    resultat, _ = _scenario(cfg, [cles.PAR_ID["omdb"]],
                            [_cocher("omdb"), _touche("escape")])
    assert resultat is False
    assert cles.ne_plus_demander(cfg) == {"omdb"}


def test_plus_tard_ne_touche_a_rien(sans_reseau):
    _, ecrits = sans_reseau
    cfg = {}
    resultat, _ = _scenario(cfg, list(cles.SERVICES), [_touche("escape")])
    assert resultat is False and not ecrits and cfg == {}


def test_depuis_f5_les_cles_actuelles_sont_proposees(sans_reseau):
    """Rien à cocher hors du lancement ; une clé inchangée n'est pas re-vérifiée."""
    verif, _ = sans_reseau
    verif["omdb"] = "ne doit pas être appelé"
    cfg = {"meta": {"omdb_api_key": "deja"}}

    async def _run():
        app = _App(cfg, list(cles.SERVICES), au_lancement=False)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            ecran = app.screen
            valeur = ecran.query_one("#champ-omdb-omdb_api_key", Input).value
            cases = len(ecran.query(Checkbox))
            await pilot.press("ctrl+s")
            await pilot.pause(0.4)
        return valeur, cases, app.resultat
    valeur, cases, resultat = asyncio.run(_run())
    assert valeur == "deja" and cases == 0
    assert resultat is False and cfg["meta"]["omdb_api_key"] == "deja"


def test_le_bouton_enregistre_comme_ctrl_s(sans_reseau):
    cfg = {}
    resultat, _ = _scenario(cfg, [cles.PAR_ID["omdb"]],
                            [_saisir("omdb-omdb_api_key", "abc123"),
                             _cliquer("btn-enregistrer")])
    assert resultat is True and cfg["meta"]["omdb_api_key"] == "abc123"


def test_le_bouton_plus_tard_ferme_sans_enregistrer(sans_reseau):
    _, ecrits = sans_reseau
    cfg = {}
    resultat, _ = _scenario(cfg, list(cles.SERVICES), [_cliquer("btn-plus-tard")])
    assert resultat is False and not ecrits and cfg == {}


@pytest.mark.parametrize("lignes", [24, 30, 40])
def test_les_boutons_restent_dans_le_cadre(lignes):
    """La zone des services défile ; les boutons, eux, restent visibles."""
    async def _run():
        app = _App({}, list(cles.SERVICES))
        async with app.run_test(size=(120, lignes)) as pilot:
            await pilot.pause(0.3)
            ecran = app.screen
            panneau = ecran.query_one("#cles-panel").region
            return [ecran.query_one(f"#{b}").region
                    for b in ("btn-enregistrer", "btn-plus-tard")], panneau
    boutons, panneau = asyncio.run(_run())
    for b in boutons:
        assert b.height and panneau.contains_region(b)


def test_sur_40_lignes_toutes_les_cases_se_voient():
    """La case d'OMDb, sous celle d'OpenSubtitles, ne doit pas exiger de défiler."""
    async def _run():
        app = _App({}, list(cles.SERVICES))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.3)
            ecran = app.screen
            corps = ecran.query_one("#cles-corps").region
            return corps, [c.region for c in ecran.query(Checkbox)]
    corps, cases = asyncio.run(_run())
    assert len(cases) == 2
    for c in cases:
        assert corps.contains_region(c)


def test_le_mot_de_passe_est_masque():
    champ = next(c for c in cles.PAR_ID["opensubtitles"].champs if c.cle == "password")
    assert champ.secret
