"""
tests/test_youtube_chaine.py — Les vidéos d'une chaîne YouTube publique (IE-181).

Partie moteur : reconnaître l'adresse d'une chaîne, lire une page de sa liste
à plat, choisir définition et sous-titres d'un lot. Aucun appel réseau : les
JSON sont fabriqués sur le modèle de `yt-dlp --flat-playlist -J`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core import youtube


# ─── Adresse ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url, attendu", [
    ("https://www.youtube.com/@Arte", "https://www.youtube.com/@Arte/videos"),
    ("youtube.com/@Arte/featured", "https://www.youtube.com/@Arte/videos"),
    ("https://m.youtube.com/@Arte/shorts?x=1", "https://www.youtube.com/@Arte/videos"),
    ("https://www.youtube.com/channel/UCabc/", "https://www.youtube.com/channel/UCabc/videos"),
    ("https://www.youtube.com/c/Nom/videos", "https://www.youtube.com/c/Nom/videos"),
    ("https://www.youtube.com/user/Nom", "https://www.youtube.com/user/Nom/videos"),
    ("  https://www.youtube.com/@Arte  ", "https://www.youtube.com/@Arte/videos"),
])
def test_une_adresse_de_chaine_mene_a_son_onglet_videos(url, attendu):
    assert youtube.url_chaine(url) == attendu


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=abc123",
    "https://youtu.be/abc123",
    "https://www.youtube.com/playlist?list=PL123",
    "https://www.youtube.com/shorts/abc123",
    "https://www.youtube.com/watch?v=abc123&list=PL123",
    "https://example.com/@Arte",
])
def test_une_video_n_est_pas_une_chaine(url):
    assert youtube.url_chaine(url) is None


# ─── Liste à plat ─────────────────────────────────────────────────────────────

def _entree(ident, **extra):
    e = {"_type": "url", "ie_key": "Youtube", "id": ident, "title": f"Vidéo {ident}",
         "duration": 600, "url": f"https://www.youtube.com/watch?v={ident}"}
    e.update(extra)
    return e


def test_la_liste_garde_titre_duree_et_date_approchee():
    page = {"channel": "Arte", "title": "Arte - Videos", "entries": [
        _entree("a1", upload_date="20261020"),
        _entree("a2", timestamp=1767225600, duration=None),   # 2026-01-01 UTC
    ]}
    chaine = youtube.lire_chaine(page, taille=100)
    assert chaine.nom == "Arte"
    assert [(e.ident, e.titre, e.duree, e.date) for e in chaine.entrees] == [
        ("a1", "Vidéo a1", 600.0, "20261020"),
        ("a2", "Vidéo a2", None, "20260101"),
    ]
    assert chaine.entrees[0].url == "https://www.youtube.com/watch?v=a1"
    assert not chaine.suite


def test_la_liste_ecarte_ce_qui_demande_un_compte_ou_n_existe_pas_encore():
    page = {"channel": "Arte", "entries": [
        _entree("ok"),
        _entree("membres", availability="subscriber_only"),
        _entree("compte", availability="needs_auth"),
        _entree("bientot", live_status="is_upcoming"),
        _entree("direct", live_status="is_live"),
        {"_type": "url", "ie_key": "YoutubeTab", "id": "UCx", "title": "Shorts"},
        None,
    ]}
    assert [e.ident for e in youtube.lire_chaine(page).entrees] == ["ok"]


def test_une_page_pleine_annonce_une_suite():
    # Les vidéos écartées comptent : la page lue était pleine.
    page = {"entries": [_entree("a"), _entree("b", availability="needs_auth")]}
    chaine = youtube.lire_chaine(page, taille=2)
    assert [e.ident for e in chaine.entrees] == ["a"]
    assert chaine.suite


def test_lister_chaine_lit_une_page_a_plat_avec_les_dates(monkeypatch):
    vues: list[list[str]] = []

    def _json(cmd):
        vues.append(cmd)
        return {"channel": "Arte", "entries": [_entree("a")]}

    monkeypatch.setattr(youtube, "_lire_json", _json)
    chaine = youtube.lister_chaine("https://www.youtube.com/@Arte/videos",
                                   Path("y"), Path("d"), debut=101)
    (cmd,) = vues
    assert "--flat-playlist" in cmd and "-J" in cmd
    assert cmd[cmd.index("--playlist-items") + 1] == "101:200"
    assert cmd[cmd.index("--extractor-args") + 1] == "youtubetab:approximate_date"
    assert cmd[-1] == "https://www.youtube.com/@Arte/videos"
    assert [e.ident for e in chaine.entrees] == ["a"]


# ─── Réglage commun du lot ────────────────────────────────────────────────────

def _video(formats, subs=()):
    return youtube.Video(url="u", ident="i", titre="t", duree=None,
                         formats=formats, audio="140", sous_titres=list(subs))


@pytest.mark.parametrize("formats, plafond, attendu", [
    ({2160: "a", 1440: "b", 1080: "c"}, 1440, 1440),
    ({2160: "a", 1080: "c"}, 1440, 1080),       # pas de 1440 : en dessous
    ({1080: "c"}, 2160, 1080),
    ({720: "x"}, 1080, 720),                    # vidéo ancienne
    ({2160: "a", 1440: "b"}, 1080, 1440),       # rien en dessous : la plus basse
])
def test_chaque_video_prend_la_meilleure_definition_sous_le_plafond(
        formats, plafond, attendu):
    assert _video(formats).hauteur_sous(plafond) == attendu


def test_les_sous_titres_proposes_sont_l_union_sans_doublon():
    fr = youtube.SousTitre("fr", "fr", "French", auto=False)
    fr2 = youtube.SousTitre("fr", "fr", "Français", auto=False)
    en = youtube.SousTitre("en", "en", "English", auto=False)
    en_auto = youtube.SousTitre("en-orig", "en", "English", auto=True)
    v1 = _video({1080: "c"}, [fr, en_auto])
    v2 = _video({1080: "c"}, [fr2, en])
    assert youtube.sous_titres_communs([v1, v2]) == [fr, en_auto, en]
    # Chaque vidéo ne reçoit que ceux qu'elle a.
    assert youtube.sous_titres_retenus(v1, [fr, en]) == [fr]
    assert youtube.sous_titres_retenus(v2, [fr, en]) == [fr2, en]


def test_la_date_exacte_vient_de_la_page_de_la_video():
    page = {"id": "a", "title": "t", "upload_date": "20261020",
            "formats": [{"format_id": "137", "format_note": "1080p", "height": 1080,
                         "vcodec": "avc1", "acodec": "none"},
                        {"format_id": "140", "vcodec": "none", "acodec": "mp4a.40.2"}]}
    assert youtube.lire_infos(page, "u").date == "20261020"
