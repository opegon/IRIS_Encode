"""
tests/test_choix_langue.py — Choisir la langue de l'interface (IE-92).

Arbitrages du 2026-10-07 : l'écran Options propose l'anglais et chaque
catalogue livré, chaque langue nommée dans sa propre langue ; au premier
lancement, la langue de Windows si elle est traduite, sinon l'anglais — jamais
un code sans catalogue ; un changement prend effet au lancement suivant, un
message le dit, rien ne redémarre.
"""
from __future__ import annotations

import asyncio
import tomllib

import pytest
from textual.app import App
from textual.widgets import RadioButton

from core import config as cfg_mod
from core import i18n


@pytest.fixture
def langue():
    """Charge une langue le temps du test, puis rend le français de `conftest.py`."""
    avant = i18n.langue()
    yield i18n.init
    i18n.init(avant)


# ─── Langues proposées ────────────────────────────────────────────────────────

def test_l_anglais_puis_chaque_catalogue_livre(tmp_path):
    for code in ("pt_BR", "de"):
        (tmp_path / code / "LC_MESSAGES").mkdir(parents=True)
        (tmp_path / code / "LC_MESSAGES" / "iris_encode.mo").write_bytes(b"")
    (tmp_path / "es" / "LC_MESSAGES").mkdir(parents=True)          # .po seul
    assert i18n.langues_disponibles(tmp_path) == ["en", "de", "pt_BR"]


def test_le_depot_livre_l_anglais_et_le_francais():
    assert i18n.langues_disponibles()[:1] == ["en"]
    assert "fr" in i18n.langues_disponibles()


@pytest.mark.parametrize("courante", ["en", "fr"])
def test_chaque_langue_se_nomme_dans_sa_langue(langue, courante):
    """Un francophone perdu dans une interface anglaise cherche « Français »."""
    langue(courante)
    assert i18n.nom_langue("en") == "English"
    assert i18n.nom_langue("fr") == "Français"
    assert i18n.nom_langue("xx") == "xx"


# ─── Premier lancement ────────────────────────────────────────────────────────

@pytest.mark.parametrize("systeme, attendu", [
    ("fr_FR", "fr"), ("fr_CA", "fr"), ("fr-BE", "fr"), ("en_US", "en"),
    ("de_DE", "en"), ("", "en"),
])
def test_la_langue_initiale_est_toujours_traduite(systeme, attendu):
    assert i18n.langue_initiale(systeme, ["en", "fr"]) == attendu


def test_une_variante_regionale_livree_passe_devant_sa_langue():
    assert i18n.langue_initiale("pt_BR", ["en", "pt", "pt_BR"]) == "pt_BR"


@pytest.mark.parametrize("env, attendu", [
    ({"LANG": "de_DE.UTF-8"}, "de_DE"),
    ({"LC_ALL": "fr_FR.UTF-8", "LANG": "en_US.UTF-8"}, "fr_FR"),
    ({"LANG": "C"}, ""),
    ({}, ""),
])
def test_hors_windows_la_langue_vient_de_l_environnement(monkeypatch, env, attendu):
    monkeypatch.setattr(i18n.sys, "platform", "linux")
    for v in ("LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(v, raising=False)
    for v, valeur in env.items():
        monkeypatch.setenv(v, valeur)
    assert i18n.langue_systeme() == attendu


@pytest.fixture
def config_isolee(tmp_path, monkeypatch):
    chemin = tmp_path / "config.toml"
    monkeypatch.setattr(cfg_mod, "CONFIG_PATH", chemin)
    return chemin


def test_premier_lancement_detecte_et_ecrit(config_isolee, monkeypatch):
    monkeypatch.setattr(i18n, "langue_systeme", lambda: "fr_CA")
    cfg = cfg_mod.load()
    assert cfg["app"]["language"] == ""
    assert cfg_mod.assurer_langue(cfg) == "fr"
    with config_isolee.open("rb") as f:
        assert tomllib.load(f)["app"]["language"] == "fr"


def test_ensuite_le_reglage_prime(config_isolee, monkeypatch):
    def jamais():
        raise AssertionError("la détection n'a lieu qu'au premier lancement")
    monkeypatch.setattr(i18n, "langue_systeme", jamais)
    cfg = cfg_mod.load()
    cfg["app"]["language"] = "en"
    assert cfg_mod.assurer_langue(cfg) == "en"
    assert not config_isolee.exists(), "rien à écrire quand la langue est réglée"


def test_un_config_impossible_a_ecrire_n_empeche_pas_de_demarrer(monkeypatch):
    def refuser(_cfg):
        raise PermissionError("lecture seule")
    monkeypatch.setattr(cfg_mod, "save", refuser)
    monkeypatch.setattr(i18n, "langue_systeme", lambda: "de_DE")
    assert cfg_mod.assurer_langue({"app": {"language": ""}}) == "en"


# ─── Écran Options ────────────────────────────────────────────────────────────

class _App(App):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.notes: list[str] = []

    def notify(self, message, **kwargs):
        self.notes.append(message)


def _choisir(cfg, code: str | None):
    from tui.screens.options import OptionsScreen

    async def _run():
        app = _App(cfg)
        async with app.run_test() as pilot:
            app.push_screen(OptionsScreen())
            await pilot.pause(0.2)
            boutons = {b.id: b for b in app.screen.query(RadioButton)
                       if b.id and b.id.startswith("langue-")}
            coches = sorted(i for i, b in boutons.items() if b.value)
            if code:
                boutons[f"langue-{code}"].value = True
                await pilot.pause(0.1)
            await pilot.press("ctrl+s")
            await pilot.pause(0.2)
        return sorted(boutons), coches, app.notes

    return asyncio.run(_run())


def test_options_propose_les_langues_et_coche_la_reglee(config_isolee):
    cfg = cfg_mod.load()
    cfg["app"]["language"] = "fr"
    boutons, coches, notes = _choisir(cfg, None)
    assert boutons == ["langue-en", "langue-fr"]
    assert coches == ["langue-fr"]
    assert notes == [], "rien n'a changé, rien à annoncer"


def test_changer_de_langue_enregistre_et_annonce_le_redemarrage(config_isolee):
    cfg = cfg_mod.load()
    cfg["app"]["language"] = "fr"
    _, _, notes = _choisir(cfg, "en")
    with config_isolee.open("rb") as f:
        assert tomllib.load(f)["app"]["language"] == "en"
    assert len(notes) == 1
    # Dans la langue courante (le français des tests), pas dans la nouvelle.
    assert "prochain lancement" in notes[0]
