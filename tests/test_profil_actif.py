"""
tests/test_profil_actif.py — Le profil actif survit à la fermeture.

Le choix du profil est un état de session, pas une propriété de
`profiles.toml`. Tant qu'il ne l'était pas, l'actif au démarrage était le
premier du fichier : un profil `delete_source = true` posé en tête devenait
actif au lancement, et effaçait les sources d'un lot lancé sans regarder.

La persistance tient dans une propriété de `IrisEncodeApp`, et non dans chaque
écran qui change le profil — il y en a trois, et celui qu'on oublierait est
celui qui perdrait le réglage.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core import config as cfg_mod
from core import profiles as prof_mod

_FICHIER = '''[qui_supprime]
bitrate_1080p_kbps = 2000
delete_source = true

[serie_basic]
bitrate_1080p_kbps = 2200

[film_hdr]
bitrate_1080p_kbps = 5000
'''


@pytest.fixture
def bac(tmp_path, monkeypatch):
    """Une configuration et des profils à part, jamais ceux de l'utilisateur."""
    monkeypatch.setattr(cfg_mod,  "CONFIG_PATH",   tmp_path / "config.toml")
    monkeypatch.setattr(prof_mod, "PROFILES_PATH", tmp_path / "profiles.toml")
    (tmp_path / "profiles.toml").write_text(_FICHIER, encoding="utf-8")
    return tmp_path


def _app():
    from tui.app import IrisEncodeApp
    return IrisEncodeApp(Path.cwd())


def test_au_premier_lancement_l_actif_est_le_premier_du_fichier(bac):
    assert _app().active_profile_id == "qui_supprime"


def test_le_choix_survit_a_la_fermeture(bac):
    app = _app()
    app.active_profile_id = "film_hdr"
    assert cfg_mod.load()["app"]["active_profile"] == "film_hdr"
    # Une nouvelle session rouvre dessus, malgré l'ordre du fichier.
    assert _app().active_profile_id == "film_hdr"


def test_un_profil_efface_du_fichier_ne_bloque_pas_le_lancement(bac):
    app = _app()
    app.active_profile_id = "film_hdr"
    (bac / "profiles.toml").write_text(
        "[serie_basic]\nbitrate_1080p_kbps = 2200\n", encoding="utf-8")
    assert _app().active_profile_id == "serie_basic"


def test_reposer_le_meme_profil_n_ecrit_pas(bac):
    """Le démarrage ne doit pas réécrire config.toml pour rien."""
    app = _app()
    assert not cfg_mod.CONFIG_PATH.exists(), \
        "construire l'application a écrit la configuration"
    app.active_profile_id = app.active_profile_id
    assert not cfg_mod.CONFIG_PATH.exists()
