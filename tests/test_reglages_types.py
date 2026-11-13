"""
tests/test_reglages_types.py — Fichiers de réglages valides mais mal typés (IE-190).

Revue de code du 2026-11-13 :

- **CR-120** — `profiles.toml` n'était contrôlé ni en type ni en valeur :
  `audio_languages = "fre"` excluait la piste française sans un mot,
  `bitrate_1080p_kbps = "5000"` rendait chaque fichier « illisible » ;
- **CR-121** — un `config.toml` mal typé fermait l'application au lancement ;
- **CR-122** — premier lancement dans un dossier non inscriptible : trace Python ;
- **CR-131** — éditer un profil à `preset_encoder = "slower"` écrivait `medium`.
"""
from __future__ import annotations

import asyncio
import logging

import pytest

from core import config as cfg_mod
from core import profiles as prof_mod


@pytest.fixture
def config(tmp_path, monkeypatch):
    chemin = tmp_path / "config.toml"
    monkeypatch.setattr(cfg_mod, "CONFIG_PATH", chemin)
    monkeypatch.setattr(cfg_mod, "_illisible", None)
    return chemin


@pytest.fixture
def profils(tmp_path, monkeypatch):
    chemin = tmp_path / "profiles.toml"
    monkeypatch.setattr(prof_mod, "PROFILES_PATH", chemin)
    monkeypatch.setattr(prof_mod, "_illisible", None)
    monkeypatch.setattr(prof_mod, "_non_cree", None, raising=False)
    return chemin


# ─── CR-121 : config.toml ─────────────────────────────────────────────────────

@pytest.mark.parametrize("contenu, cle", [
    ("tui = 1\n",                               "tui"),
    ('app = "x"\n',                             "app"),
    ('[stats.encode_speed]\nhevc = "vite"\n',   "stats.encode_speed.hevc"),
    ("[app]\nlanguage = 1\n",                   None),       # texte voulu
    ('[tui.dryrun]\ncolumns = "large"\n',       "tui.dryrun.columns"),
    ('[tui.browser.columns]\ntaille = "8"\n',   "tui.browser.columns.taille"),
    ("[updates]\ncheck_on_startup = 1\n",       "updates.check_on_startup"),
])
def test_une_config_mal_typée_tourne_sur_les_défauts(config, contenu, cle):
    config.write_text(contenu, encoding="utf-8")
    cfg = cfg_mod.load()
    assert cfg_mod.illisible() is None
    # Ce qui levait au lancement.
    cfg_mod.get_column_widths(cfg)
    cfg_mod.get_dryrun_column_widths(cfg)
    assert cfg_mod.get_encode_speed(cfg, "hevc") is None
    assert isinstance(cfg["app"]["language"], str)
    assert isinstance(cfg["updates"]["check_on_startup"], bool)
    assert cfg_mod.corrigees() == ([cle] if cle else [])


def test_un_mot_de_passe_en_chiffres_reste_le_mot_de_passe(config):
    """Et une configuration bien typée n'est pas touchée."""
    config.write_text("[opensubtitles]\npassword = 1234\n"
                      '[app]\nlanguage = "fr"\nmin_title_minutes = 5\n'
                      "[stats.encode_speed]\nhevc = 2.5\n"
                      "[tui.dryrun.columns]\nfichier = 40\n", encoding="utf-8")
    cfg = cfg_mod.load()
    assert cfg["opensubtitles"]["password"] == "1234"
    assert cfg_mod.get_encode_speed(cfg, "hevc") == 2.5
    assert cfg_mod.get_dryrun_column_widths(cfg)["fichier"] == 40
    assert cfg_mod.corrigees() == []


# ─── CR-120 : profiles.toml ───────────────────────────────────────────────────

def test_une_langue_écrite_seule_se_lit_comme_une_liste(profils):
    profils.write_text('[p]\naudio_languages = "fre"\n'
                       'subtitle_languages = "fre, eng"\n', encoding="utf-8")
    p = prof_mod.load_all()["p"]
    assert p.get("audio_languages") == ["fre"]
    assert p.get("subtitle_languages") == ["fre", "eng"]
    assert prof_mod.corrigees() == []


@pytest.mark.parametrize("ligne", [
    'bitrate_1080p_kbps = "5000"', "bitrate_4k_kbps = 0", "keep_4k = 1",
    'dolby_vision = "hdr"', 'container = "avi"', 'audio_hd_codec = "dts"',
    'hdr10_quality = "max"', "upscale_passes = 3", 'preset_encoder = ""',
    "audio_languages = [1, 2]", "delete_source = \"yes\"",
])
def test_une_valeur_invalide_est_écartée_et_nommée(profils, ligne):
    cle = ligne.split(" = ")[0]
    profils.write_text(f"[p]\n{ligne}\nautre_reglage = 7\n", encoding="utf-8")
    p = prof_mod.load_all()["p"]
    assert cle not in p.data
    assert prof_mod.corrigees() == [f"p.{cle}"]
    assert p.get("autre_reglage") == 7          # une clé inconnue est gardée


def test_un_débit_en_texte_ne_rend_plus_le_fichier_illisible(profils):
    profils.write_text('[p]\nbitrate_1080p_kbps = "5000"\n', encoding="utf-8")
    p = prof_mod.load_all()["p"]
    assert p.bitrate_for_height(1080) == 2_500_000      # le défaut du moteur


# ─── CR-122 : premier lancement sans écriture ─────────────────────────────────

def test_premier_lancement_dans_un_dossier_non_inscriptible(tmp_path, monkeypatch):
    monkeypatch.setattr(prof_mod, "PROFILES_PATH",
                        tmp_path / "absent" / "profiles.toml")
    monkeypatch.setattr(prof_mod, "_illisible", None)
    profiles = prof_mod.load_all()
    assert set(profiles) == set(prof_mod._profils_livres())
    assert prof_mod.non_cree()


def test_un_journal_impossible_à_ouvrir_ne_ferme_pas_l_application(tmp_path,
                                                                    monkeypatch):
    import tui.common
    from tui.app import _setup_logging
    bloquant = tmp_path / "fichier"
    bloquant.write_text("")
    monkeypatch.setattr(tui.common, "JOURNAL", bloquant / "iris_encode.log")
    racine = logging.getLogger()
    avant = list(racine.handlers)
    try:
        assert _setup_logging()
    finally:
        racine.handlers[:] = avant


# ─── CR-131 : le formulaire garde une valeur texte hors liste ─────────────────

def test_éditer_un_profil_garde_un_preset_hors_liste():
    from textual.app import App

    from tui.widgets.profile_form import ProfileForm

    class _App(App):
        def compose(self):
            yield ProfileForm()

    async def _run():
        app = _App()
        async with app.run_test(size=(160, 50)) as pilot:
            form = app.query_one(ProfileForm)
            form.load("p", {"preset_encoder": "slower"})
            await pilot.pause(0.2)
            avant = form.dump()
            form.load("q", {"preset_encoder": "slow"})
            await pilot.pause(0.2)
            return avant, form.dump(), form._opts_champ["#field-preset"]

    avant, apres, opts = asyncio.run(_run())
    assert avant["preset_encoder"] == "slower"
    assert apres["preset_encoder"] == "slow"
    assert ("slower", "slower") not in opts      # pas de reste d'un autre profil
