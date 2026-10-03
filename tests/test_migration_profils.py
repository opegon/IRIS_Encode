"""
tests/test_migration_profils.py — `serie_*` devient `series_*` (IE-112).

Les noms de profils ne se traduisent pas (cadrage de la localisation, IE-71) :
ils doivent être neutres. Seul le préfixe `serie_` des profils livrés était
français. Le fichier livré passe à `series_` ; le `profiles.toml` déjà semé
chez l'utilisateur migre au chargement, et la mémoire du profil actif suit.
"""
from __future__ import annotations

import tomllib

import pytest

from core import config as cfg_mod
from core import profiles as prof_mod

_ANCIEN = '''[serie_anime]
bitrate_1080p_kbps = 2000

[mon_profil]
bitrate_1080p_kbps = 3000

[serie_basic_delete]
bitrate_1080p_kbps = 2000
delete_source = true

[serie_perso]
bitrate_1080p_kbps = 1800
'''


@pytest.fixture
def fichier(tmp_path, monkeypatch):
    chemin = tmp_path / "profiles.toml"
    monkeypatch.setattr(prof_mod, "PROFILES_PATH", chemin)
    chemin.write_text(_ANCIEN, encoding="utf-8")
    return chemin


def test_le_fichier_livre_n_a_plus_de_serie():
    livres = tomllib.loads(prof_mod.PROFILS_LIVRES_PATH.read_text(encoding="utf-8"))
    assert not any(nom.startswith("serie_") for nom in livres)
    assert set(prof_mod.RENOMMAGES_LIVRES.values()) <= set(livres)


def test_les_profils_livres_migrent_dans_l_ordre_du_fichier(fichier):
    assert list(prof_mod.load_all()) == [
        "series_anime", "mon_profil", "series_basic_delete", "serie_perso"]


def test_la_migration_est_ecrite_et_garde_les_reglages(fichier):
    prof_mod.load_all()
    relu = tomllib.loads(fichier.read_text(encoding="utf-8"))
    assert "serie_anime" not in relu
    assert relu["series_basic_delete"]["delete_source"] is True


def test_un_profil_cree_par_l_utilisateur_n_est_pas_touche(fichier):
    assert "serie_perso" in prof_mod.load_all()


def test_la_migration_est_idempotente(fichier):
    prof_mod.load_all()
    apres = fichier.read_text(encoding="utf-8")
    prof_mod.load_all()
    assert fichier.read_text(encoding="utf-8") == apres


def test_un_nouveau_nom_deja_pris_bloque_le_renommage(fichier):
    """Renommer écraserait l'un des deux : on garde les deux."""
    fichier.write_text('[serie_hdr]\nbitrate_1080p_kbps = 1\n\n'
                       '[series_hdr]\nbitrate_1080p_kbps = 2\n', encoding="utf-8")
    profils = prof_mod.load_all()
    assert profils["serie_hdr"].data["bitrate_1080p_kbps"] == 1
    assert profils["series_hdr"].data["bitrate_1080p_kbps"] == 2


def test_le_profil_actif_memorise_suit_le_renommage(fichier):
    ids = prof_mod.load_all()
    cfg = {"app": {"active_profile": "serie_basic_delete"}}
    assert cfg_mod.get_active_profile(cfg, ids) == "series_basic_delete"


def test_un_actif_inconnu_retombe_toujours_sur_le_premier(fichier):
    ids = prof_mod.load_all()
    cfg = {"app": {"active_profile": "serie_inconnu"}}
    assert cfg_mod.get_active_profile(cfg, ids) == "series_anime"
