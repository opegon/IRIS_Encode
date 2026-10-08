"""
tests/test_fichiers_reglages.py — Les fichiers de réglages (IE-124).

Constats de la revue IE-114 :

- **CR-43** — une faute de frappe dans `config.toml` le faisait écraser au
  lancement suivant (la langue écrite au démarrage), clés d'API comprises ;
- **CR-45** — un `profiles.toml` illisible : le premier enregistrement de la
  session remplaçait la bibliothèque par les profils livrés ;
- **CR-64**, **CR-77** — un `config.toml` qui refuse l'écriture (antivirus,
  synchronisation) fermait l'application, au milieu d'un lot ;
- **CR-44** — l'écriture du worker croisait une modification du fil de
  l'interface.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core import config as cfg_mod
from core import profiles as prof_mod

RACINE = Path(__file__).resolve().parent.parent

CONFIG_FAUTIVE = (b'[app]\noutput_dir = "D:\\\\Films\n'
                  b'[opensubtitles]\napi_key = "CLE-SECRETE"\npassword = "secret"\n')


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
    return chemin


# ─── config.toml illisible : jamais réécrit ───────────────────────────────────

def test_une_faute_de_frappe_ne_fait_plus_écraser_config_toml(config):
    config.write_bytes(CONFIG_FAUTIVE)
    cfg = cfg_mod.load()
    assert cfg_mod.illisible()
    cfg_mod.assurer_langue(cfg)          # écrivait le fichier au démarrage
    assert cfg_mod.enregistrer(cfg) is not None
    with pytest.raises(cfg_mod.ConfigIllisible):
        cfg_mod.save(cfg)
    assert config.read_bytes() == CONFIG_FAUTIVE


def test_un_fichier_réparé_se_réécrit_de_nouveau(config):
    config.write_bytes(CONFIG_FAUTIVE)
    cfg_mod.load()
    config.write_bytes(b'[app]\nlanguage = "fr"\n')
    cfg = cfg_mod.load()
    assert cfg_mod.illisible() is None
    assert cfg_mod.enregistrer(cfg) is None


def test_un_fichier_absent_n_est_pas_illisible(config):
    cfg_mod.load()
    assert cfg_mod.illisible() is None


# ─── profiles.toml illisible : jamais réécrit ─────────────────────────────────

def test_la_bibliothèque_illisible_n_est_jamais_écrasée(profils):
    contenu = (b'[mon_profil_4k]\ncodec = "hevc\n'      # guillemet oublié
               b'[mon_anime]\ncodec = "hevc"\n')
    profils.write_bytes(contenu)
    profiles = prof_mod.load_all()
    assert prof_mod.illisible()
    profiles["nouveau"] = prof_mod.Profile(id="nouveau", data={})
    with pytest.raises(prof_mod.ProfilsIllisibles):
        prof_mod.save_all(profiles)
    assert profils.read_bytes() == contenu


def test_une_bibliothèque_lisible_s_enregistre(profils):
    profils.write_bytes(b'[a]\ncodec = "hevc"\n')
    profiles = prof_mod.load_all()
    assert prof_mod.illisible() is None
    prof_mod.save_all(profiles)


# ─── Une écriture refusée ne ferme plus l'application ─────────────────────────

def _refus(_cfg):
    raise PermissionError("[WinError 5] Access is denied")


def test_enregistrer_rend_la_cause_au_lieu_de_lever(config, monkeypatch):
    monkeypatch.setattr(cfg_mod, "save", _refus)
    assert "Access is denied" in cfg_mod.enregistrer({})
    assert cfg_mod.set_active_profile({}, "x") is not None
    assert cfg_mod.set_energie({}, True, "rien") is not None


def test_la_vitesse_mesurée_perdue_ne_coûte_pas_le_lot(config, monkeypatch):
    """CR-64."""
    from core.decision import VideoAction
    from tui.common import record_measured_speed
    monkeypatch.setattr(cfg_mod, "save", _refus)
    cfg = cfg_mod._deep_merge({}, cfg_mod._DEFAULTS)
    record_measured_speed(cfg, VideoAction.ENCODE_HEVC, 2.5)   # ne lève pas


class _FausseApp:
    def __init__(self):
        self.cfg, self.dits = {}, []

    def notify(self, texte, **_k):
        self.dits.append(texte)


def test_un_échec_se_dit_une_fois_par_cause(config, monkeypatch):
    """CR-77 : `<`, `F4` ou les options ne ferment plus l'application."""
    from tui.common import sauver_config
    monkeypatch.setattr(cfg_mod, "save", _refus)
    app = _FausseApp()
    assert sauver_config(app) is False
    assert sauver_config(app) is False
    assert len(app.dits) == 1 and "Access is denied" in app.dits[0]


def test_l_interface_n_appelle_plus_save_en_direct():
    """Toute écriture de config.toml depuis l'interface passe par
    `sauver_config` / `signaler_config`."""
    for chemin in (RACINE / "tui").rglob("*.py"):
        assert "cfg_mod.save(" not in chemin.read_text(encoding="utf-8"), chemin


def test_la_vitesse_s_enregistre_sur_le_fil_de_l_interface():
    """CR-44 : toutes les modifications de la configuration au même endroit."""
    texte = (RACINE / "tui" / "screens" / "run.py").read_text(encoding="utf-8")
    assert "call_from_thread(record_measured_speed" in texte
