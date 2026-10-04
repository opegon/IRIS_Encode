"""
tests/test_opensubtitles.py — Recherche et téléchargement OpenSubtitles.com.

Aucun appel réseau : `requests` est remplacé par un faux serveur qui rejoue
les réponses de l'API v1 et garde la trace des requêtes reçues.
"""
from __future__ import annotations

import re
import struct
from contextlib import contextmanager
from pathlib import Path

import pytest
import requests

from core import opensubtitles as osub
from core.muxer import guess_language
from core.opensubtitles import Client, ErreurOpenSubtitles


# ─── Empreinte ────────────────────────────────────────────────────────────────

def test_un_fichier_trop_petit_n_a_pas_d_empreinte(tmp_path):
    f = tmp_path / "court.mkv"
    f.write_bytes(b"\0" * 1000)
    assert osub.empreinte(f) == ""


def test_un_fichier_nul_vaut_sa_taille(tmp_path):
    f = tmp_path / "nul.mkv"
    f.write_bytes(b"\0" * 200_000)
    assert osub.empreinte(f) == f"{200_000:016x}"


def test_l_empreinte_somme_la_tete_et_la_queue_modulo_2_64(tmp_path):
    """Un mot en tête, un en queue, un au milieu que l'algorithme ignore."""
    taille = 300_000
    donnees = bytearray(taille)
    donnees[0:8]           = struct.pack("<q", 5)
    donnees[150_000:150_008] = struct.pack("<q", 999)      # hors des deux blocs
    donnees[-8:]           = struct.pack("<q", -1)          # 0xFFFF…: débordement
    f = tmp_path / "v.mkv"
    f.write_bytes(bytes(donnees))
    attendu = (taille + 5 - 1) & 0xFFFFFFFFFFFFFFFF
    assert osub.empreinte(f) == f"{attendu:016x}"
    assert len(osub.empreinte(f)) == 16


# ─── Langues ──────────────────────────────────────────────────────────────────

def test_les_langues_du_profil_passent_au_format_de_l_api():
    assert osub.langues_api(["fre", "eng"]) == "en,fr"      # triées
    assert osub.langues_api(["fra", "fre", "xxx"]) == "fr"  # uniques, inconnues ignorées


@pytest.mark.parametrize("code, attendu", [
    ("fr", "fre"), ("en", "eng"), ("pt-br", "por"), ("de", "ger"), ("", "und"),
])
def test_retour_en_iso_639_2(code, attendu):
    assert osub.langue_depuis_api(code) == attendu


# ─── Faux serveur ─────────────────────────────────────────────────────────────

class _Rep:
    def __init__(self, status=200, json=None, content=b"", headers=None):
        self.status_code = status
        self._json       = json or {}
        self.content     = content
        self.text        = str(json)
        self.headers     = headers or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


def _sub(file_id, lang="fr", hash_ok=False, count=10, release="Film.2019.1080p"):
    return {"attributes": {
        "language": lang, "release": release, "download_count": count,
        "moviehash_match": hash_ok, "hearing_impaired": False,
        "files": [{"file_id": file_id, "file_name": f"{file_id}.srt"}]}}


@pytest.fixture
def serveur(monkeypatch):
    """Rejoue des réponses par route ; `appels` garde (méthode, url, kw)."""
    etat = {"routes": {}, "appels": []}

    def request(methode, url, headers=None, timeout=None, **kw):
        etat["appels"].append((methode, url, headers, kw))
        route = url.rsplit("/", 1)[-1]
        rep = etat["routes"][route]
        return rep(kw) if callable(rep) else rep

    def get(url, timeout=None):
        etat["appels"].append(("GET", url, None, {}))
        return _Rep(content=b"1\n00:00:01,000 --> 00:00:02,000\nBonjour\n")

    monkeypatch.setattr(requests, "request", request)
    monkeypatch.setattr(requests, "get", get)
    return etat


def _video(tmp_path, nom="Film.2019.1080p.mkv", taille=200_000) -> Path:
    v = tmp_path / nom
    v.write_bytes(b"\0" * taille)
    return v


def _client(user="moi", pwd="secret") -> Client:
    return Client("CLE", user, pwd, "IRIS Encode vtest")


# ─── Recherche ────────────────────────────────────────────────────────────────

def test_empreinte_puis_nom_fusionnes_les_exacts_en_tete(tmp_path, serveur):
    def subtitles(kw):
        params = dict(kw["params"])
        if "moviehash" in params:
            return _Rep(json={"data": [_sub(2, hash_ok=True, count=1)]})
        return _Rep(json={"data": [_sub(1, count=500), _sub(2, count=1)]})
    serveur["routes"]["subtitles"] = subtitles

    res = _client().chercher(_video(tmp_path), ["fre"])
    assert [r.file_id for r in res] == [2, 1]      # l'exact d'abord, sans doublon
    assert res[0].empreinte and not res[1].empreinte
    assert res[0].langue == "fre"


def test_les_parametres_sont_tries_et_portent_le_titre(tmp_path, serveur):
    serveur["routes"]["subtitles"] = _Rep(json={"data": []})
    _client().chercher(_video(tmp_path), ["fre", "eng"])
    methode, url, entetes, kw = serveur["appels"][-1]
    cles = [k for k, _ in kw["params"]]
    assert cles == sorted(cles)
    params = dict(kw["params"])
    assert params["query"] == "film" and params["year"] == 2019
    assert params["languages"] == "en,fr"
    assert entetes["Api-Key"] == "CLE" and entetes["User-Agent"] == "IRIS Encode vtest"
    assert "Authorization" not in entetes          # la recherche ne se connecte pas


def test_une_serie_cherche_sa_saison_et_son_episode(tmp_path, serveur):
    serveur["routes"]["subtitles"] = _Rep(json={"data": []})
    _client().chercher(_video(tmp_path, "Serie.S02E07.1080p.mkv"), ["fre"])
    params = dict(serveur["appels"][-1][3]["params"])
    assert (params["query"], params["season_number"], params["episode_number"]) \
        == ("serie", 2, 7)


def test_un_petit_fichier_ne_cherche_que_par_nom(tmp_path, serveur):
    serveur["routes"]["subtitles"] = _Rep(json={"data": []})
    _client().chercher(_video(tmp_path, taille=100), ["fre"])
    assert len(serveur["appels"]) == 1
    assert "moviehash" not in dict(serveur["appels"][0][3]["params"])


def test_un_sous_titre_en_plusieurs_cd_est_ecarte(tmp_path, serveur):
    multi = _sub(9)
    multi["attributes"]["files"].append({"file_id": 10})
    serveur["routes"]["subtitles"] = _Rep(json={"data": [multi, _sub(1)]})
    res = _client().chercher(_video(tmp_path, taille=100), ["fre"])
    assert [r.file_id for r in res] == [1]


# ─── Téléchargement ───────────────────────────────────────────────────────────

def test_le_telechargement_se_connecte_et_ecrit_un_srt_qui_dit_sa_langue(tmp_path, serveur):
    serveur["routes"]["login"]    = _Rep(json={"token": "JWT", "base_url": "vip-api.opensubtitles.com"})
    serveur["routes"]["download"] = _Rep(json={"link": "https://dl/x.srt", "remaining": 19})
    video = _video(tmp_path)
    r = osub.Resultat(file_id=42, langue="fre", release="x", telechargements=1,
                      empreinte=True, malentendants=False)

    chemin, restant = _client().telecharger(r, video)

    assert restant == 19
    assert chemin.suffix == ".srt" and b"Bonjour" in chemin.read_bytes()
    assert guess_language(chemin) == "fre"         # la piste ne sortira pas en « und »
    _, url, entetes, kw = serveur["appels"][1]     # le download, après le login
    assert url.startswith("https://vip-api.opensubtitles.com/")   # hôte VIP suivi
    assert entetes["Authorization"] == "Bearer JWT"
    assert kw["json"] == {"file_id": 42, "sub_format": "srt"}
    chemin.unlink()


@contextmanager
def _refuse(motif: str):
    """Le refus, lu comme l'écran le montre (`texte_erreur`, en français)."""
    from core.i18n import texte_erreur
    with pytest.raises(ErreurOpenSubtitles) as refus:
        yield
    assert re.search(motif, texte_erreur(refus.value)), texte_erreur(refus.value)


def test_sans_compte_le_telechargement_le_dit(tmp_path, serveur):
    r = osub.Resultat(1, "fre", "", 0, False, False)
    with _refuse("identifiant et mot de passe"):
        _client(user="", pwd="").telecharger(r, _video(tmp_path))
    assert serveur["appels"] == []


def test_sans_cle_rien_ne_part():
    with _refuse("Clé d.API absente"):
        Client("", "u", "p", "ua")


@pytest.mark.parametrize("status, json, headers, motif", [
    (401, {}, {}, "incorrect"),
    (406, {"reset_time": "dans 5 heures"}, {}, "Quota .* dans 5 heures"),
    (429, {}, {"Retry-After": "3"}, "dans 3 secondes"),
    (503, {}, {}, "503"),
])
def test_les_refus_de_l_api_sont_lisibles(tmp_path, serveur, status, json, headers, motif):
    serveur["routes"]["subtitles"] = _Rep(status, json, headers=headers)
    with _refuse(motif):
        _client().chercher(_video(tmp_path, taille=100), ["fre"])


def test_le_reseau_absent_est_lisible(tmp_path, monkeypatch):
    def panne(*a, **k):
        raise requests.ConnectionError("pas de réseau")
    monkeypatch.setattr(requests, "request", panne)
    with _refuse("injoignable"):
        _client().chercher(_video(tmp_path, taille=100), ["fre"])


def test_les_pages_suivantes_sont_lues(tmp_path, serveur):
    """La première page seule perdait les sous-titres moins téléchargés."""
    def subtitles(kw):
        page = dict(kw["params"]).get("page", 1)
        return _Rep(json={"total_pages": 2, "data": [_sub(page)]})
    serveur["routes"]["subtitles"] = subtitles
    res = _client().chercher(_video(tmp_path, taille=100), ["fre"])
    assert sorted(r.file_id for r in res) == [1, 2]
    assert "page" not in dict(serveur["appels"][0][3]["params"])


def test_les_pages_sont_plafonnees(tmp_path, serveur):
    serveur["routes"]["subtitles"] = lambda kw: _Rep(json={"total_pages": 40, "data": []})
    _client().chercher(_video(tmp_path, taille=100), ["fre"])
    assert len(serveur["appels"]) == osub._PAGES_MAX


def test_la_langue_du_profil_passe_avant_les_telechargements(tmp_path, serveur):
    """Profil fre puis eng : le français d'abord, même moins téléchargé."""
    serveur["routes"]["subtitles"] = _Rep(json={"data": [
        _sub(1, lang="en", count=900), _sub(2, lang="fr", count=5),
        _sub(3, lang="fr", count=50)]})
    res = _client().chercher(_video(tmp_path, taille=100), ["fre", "eng"])
    assert [r.file_id for r in res] == [3, 2, 1]
