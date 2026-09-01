"""
tests/test_profils_livres.py — Les profils livrés avec l'application.

Jusqu'à la v0.8.8.4, une installation neuve semait `profiles.toml` avec le seul
profil codé en dur `_default_`. Le sélecteur (`F4`) s'ouvrait donc sur une liste
d'un seul élément : rien qui montre ce qu'un profil règle, ni ce que change le
fait d'en changer. Le besoin d'origine — ne pas rester bloqué au lancement si le
fichier manque — était couvert, mais au minimum vital.

`data/profiles.default.toml` porte désormais les dix profils livrés. Trois
niveaux : le fichier de l'utilisateur, les profils livrés, puis le plancher codé
en dur si l'installation a perdu son fichier livré.

Ce module vérifie les trois, et la cohérence du fichier livré lui-même : c'est
une donnée versionnée, éditable à la main, et rien d'autre ne la relit.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from core import profiles as pm

RACINE = Path(__file__).resolve().parent.parent


# ─── Les trois niveaux ────────────────────────────────────────────────────────

def test_une_installation_neuve_recoit_les_profils_livres(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "PROFILES_PATH", tmp_path / "profiles.toml")
    charges = pm.load_all()
    livres  = tomllib.loads(pm.PROFILS_LIVRES_PATH.read_text(encoding="utf-8"))
    assert list(charges) == list(livres), "l'ordre du fichier livré fait foi"
    assert len(charges) > 1, "un sélecteur d'un seul élément ne montre rien"


def test_le_fichier_seme_est_relisable_a_l_identique(tmp_path, monkeypatch):
    """Le semage passe par `save_all`, donc par tomli_w : ce qui est écrit doit
    se relire tel quel, sinon l'utilisateur hérite d'un fichier dégradé."""
    monkeypatch.setattr(pm, "PROFILES_PATH", tmp_path / "profiles.toml")
    seme = pm.load_all()
    relu = pm.load_all()
    assert list(relu) == list(seme)
    assert all(relu[n].data == seme[n].data for n in seme)


def test_le_profil_actif_au_premier_lancement_n_efface_rien():
    """`config.get_active_profile` retient le **premier** du fichier tant que
    rien n'a été choisi. Un profil `delete_source = true` posé en tête
    effacerait les sources d'un lot lancé sans regarder."""
    livres = tomllib.loads(pm.PROFILS_LIVRES_PATH.read_text(encoding="utf-8"))
    premier = next(iter(livres.values()))
    assert premier.get("delete_source", False) is False


def test_un_toml_casse_tient_la_session_sans_toucher_au_fichier(tmp_path,
                                                                monkeypatch):
    cible = tmp_path / "profiles.toml"
    cible.write_text("[casse\n", encoding="utf-8")
    monkeypatch.setattr(pm, "PROFILES_PATH", cible)
    charges = pm.load_all()
    assert len(charges) > 1, "la session tient sur les profils livrés"
    assert cible.read_text(encoding="utf-8") == "[casse\n", \
        "le fichier de l'utilisateur est sa bibliothèque : on n'y touche pas"


def test_sans_fichier_livre_le_plancher_reprend_la_main(tmp_path, monkeypatch):
    """Une archive amputée, un fichier corrompu au transfert : l'application
    doit encore démarrer."""
    monkeypatch.setattr(pm, "PROFILES_PATH", tmp_path / "profiles.toml")
    monkeypatch.setattr(pm, "PROFILS_LIVRES_PATH", tmp_path / "absent.toml")
    assert list(pm.load_all()) == [pm.PROFIL_DEFAUT_ID]


def test_le_fichier_livre_accompagne_le_code():
    """Il est versionné, donc présent dans l'archive d'une release — à la
    différence de `profiles.toml`, ignoré par git."""
    assert pm.PROFILS_LIVRES_PATH.exists(), pm.PROFILS_LIVRES_PATH
    assert pm.PROFILS_LIVRES_PATH.parent == RACINE / "data"


# ─── Cohérence du fichier livré ───────────────────────────────────────────────

CHAMPS_CONNUS = {
    "bitrate_720p_kbps", "bitrate_1080p_kbps", "bitrate_4k_kbps", "keep_4k",
    "delete_source", "preset_encoder", "dolby_vision", "hdr10_quality",
    "preserve_hd_audio", "audio_languages", "subtitle_languages",
    "audio_stereo_kbps", "audio_surround_kbps", "audio_surround_7_1_kbps",
    "audio_copy_compatible", "audio_hd_codec", "container",
}

TYPES = {
    "bitrate_720p_kbps": int, "bitrate_1080p_kbps": int, "bitrate_4k_kbps": int,
    "keep_4k": bool, "delete_source": bool, "preset_encoder": str,
    "dolby_vision": str, "hdr10_quality": str, "preserve_hd_audio": bool,
    "audio_languages": list, "subtitle_languages": list,
    "audio_stereo_kbps": int, "audio_surround_kbps": int,
    "audio_surround_7_1_kbps": int, "audio_copy_compatible": bool,
    "audio_hd_codec": str, "container": str,
}

DOMAINES = {
    "preset_encoder": {"ultrafast", "superfast", "veryfast", "faster", "fast",
                       "medium", "slow", "slower", "veryslow"},
    "dolby_vision":   {"hdr10", "dv", "sdr"},
    "hdr10_quality":  {"compat", "quality"},
    "audio_hd_codec": {"none", "ac3", "eac3"},
    "container":      {"auto", "mp4", "mkv"},
}


def _livres() -> dict:
    return tomllib.loads(pm.PROFILS_LIVRES_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("nom", list(_livres()))
def test_un_profil_livre_ne_porte_que_des_champs_connus(nom):
    """Une clé inconnue est silencieuse : elle ne fait rien et ne dit rien.
    Dans un fichier livré, elle se propagerait à chaque installation neuve."""
    inconnus = set(_livres()[nom]) - CHAMPS_CONNUS
    assert not inconnus, f"{nom} : {sorted(inconnus)}"


@pytest.mark.parametrize("nom", list(_livres()))
def test_un_profil_livre_a_des_types_justes(nom):
    for cle, valeur in _livres()[nom].items():
        attendu = TYPES[cle]
        assert isinstance(valeur, attendu), \
            f"{nom}.{cle} = {valeur!r} ({type(valeur).__name__}, attendu {attendu.__name__})"


@pytest.mark.parametrize("nom", list(_livres()))
def test_un_profil_livre_reste_dans_les_domaines(nom):
    """Une valeur hors domaine ne lève pas : elle retombe sur un défaut, et le
    profil fait autre chose que ce qu'il annonce."""
    profil = _livres()[nom]
    for cle, valides in DOMAINES.items():
        if cle in profil:
            assert profil[cle] in valides, \
                f"{nom}.{cle} = {profil[cle]!r}, attendu parmi {sorted(valides)}"


@pytest.mark.parametrize("nom", list(_livres()))
def test_les_debits_audio_d_un_profil_livre_sont_croissants(nom):
    """Un 5.1 moins bien servi qu'une stéréo est une faute de frappe, pas un
    choix : rien dans l'interface ne la rendrait visible."""
    p = _livres()[nom]
    st  = p.get("audio_stereo_kbps", 0)
    s51 = p.get("audio_surround_kbps", 0)
    s71 = p.get("audio_surround_7_1_kbps", 0)
    assert st <= s51 <= s71, f"{nom} : {st} / {s51} / {s71}"


@pytest.mark.parametrize("nom", list(_livres()))
def test_les_debits_video_d_un_profil_livre_sont_croissants(nom):
    """Le débit cible est un **plafond** : au-dessous, la source est laissée
    telle quelle (CAS 1 de `decide_video`). Un plafond 1080p supérieur au
    plafond 4K réencoderait des 1080p en épargnant des 4K plus lourdes."""
    p = _livres()[nom]
    assert p["bitrate_720p_kbps"] <= p["bitrate_1080p_kbps"] <= p["bitrate_4k_kbps"], \
        f'{nom} : {p["bitrate_720p_kbps"]} / {p["bitrate_1080p_kbps"]} / {p["bitrate_4k_kbps"]}'
