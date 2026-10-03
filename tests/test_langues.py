"""
tests/test_langues.py — Le code de langue, et le filtre des sous-titres.

Deux défauts de la même famille : le profil demande des langues, et le fichier
n'en tient pas compte.

**« fra » n'est pas « fre » pour une comparaison de chaînes.** ISO 639-2 a deux
jeux de codes pour vingt langues — un bibliographique (`fre`, `ger`, `dut`), un
terminologique (`fra`, `deu`, `nld`). Les conteneurs emploient l'un ou l'autre
sans règle. `audio_languages = ["fre"]` excluait donc **silencieusement** une
piste étiquetée « fra ». Mesuré sur un rip réel : ses sous-titres portent `fra`,
`ces`, `nld`, `deu`, `ell`, `ron`, `slk`, `zho` — huit codes terminologiques.

**Les sous-titres n'étaient filtrés par rien.** `subtitle_indices = None` vaut
« toutes », et aucune règle ne s'y appliquait jamais. Un épisode de rip
streaming en embarque quarante-trois ; les quarante-trois traversaient la
chaîne. La clé `subtitle_languages` pose enfin la règle.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.decision import AudioAction, decide_audio, decide_subtitles
from core.profiles import Profile
from core.scanner import (AudioTrack, SubtitleTrack, VideoInfo,
                          normalize_language, same_language)


def _profile(**over) -> Profile:
    data = {"bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
            "bitrate_4k_kbps": 8000, "audio_languages": ["fre", "eng"],
            "audio_copy_compatible": True, "preserve_hd_audio": False}
    data.update(over)
    return Profile(id="test", data=data)


def _info(tmp_path: Path, audio=None, sous_titres=None) -> VideoInfo:
    p = tmp_path / "film.mkv"
    p.write_bytes(b"")
    return VideoInfo(
        path=p, width=1920, height=1080, bitrate=3_000_000, codec="hevc",
        duration=3703.0, frame_count=0, dv_profile=None,
        audio_tracks=audio or [], subtitle_tracks=sous_titres or [],
    )


def _st(index, langue, codec="subrip") -> SubtitleTrack:
    return SubtitleTrack(index=index, codec=codec, language=langue)


# ─── Les deux jeux de codes ISO 639-2 ─────────────────────────────────────────

@pytest.mark.parametrize("termino, biblio", [
    ("fra", "fre"), ("deu", "ger"), ("nld", "dut"), ("ces", "cze"),
    ("ell", "gre"), ("ron", "rum"), ("slk", "slo"), ("zho", "chi"),
])
def test_les_deux_codes_designent_la_meme_langue(termino, biblio):
    assert same_language(termino, biblio)
    assert normalize_language(termino) == biblio


def test_un_code_inconnu_passe_tel_quel():
    """On ne devine pas : « swe » n'a qu'une forme, « xx » n'en a aucune."""
    assert normalize_language("swe") == "swe"
    assert normalize_language("xx") == "xx"


def test_une_langue_vide_ne_vaut_aucune_autre():
    assert not same_language("", "")
    assert not same_language("", "fre")


# ─── Le défaut : une piste « fra » disparaissait ──────────────────────────────

def test_une_piste_fra_est_retenue_par_un_filtre_fre(tmp_path):
    """Le cas qui perdait une VF sans un mot."""
    pistes = [AudioTrack(index=0, codec="eac3", channels=6, language="eng",
                         title="", bitrate=640_000),
              AudioTrack(index=1, codec="eac3", channels=6, language="fra",
                         title="French", bitrate=640_000)]
    d = decide_audio(_info(tmp_path, audio=pistes), _profile())
    assert d[1].action != AudioAction.EXCLUDE, "« fra » est du français"


def test_une_langue_hors_profil_reste_exclue(tmp_path):
    pistes = [AudioTrack(index=0, codec="eac3", channels=6, language="eng",
                         title="", bitrate=640_000),
              AudioTrack(index=1, codec="eac3", channels=6, language="jpn",
                         title="", bitrate=640_000)]
    d = decide_audio(_info(tmp_path, audio=pistes), _profile())
    assert d[1].action == AudioAction.EXCLUDE


# ─── Le filtre des sous-titres ────────────────────────────────────────────────

def test_sans_la_cle_tout_est_garde(tmp_path):
    """Comportement historique : une clé absente ne change rien."""
    info = _info(tmp_path, sous_titres=[_st(0, "eng"), _st(1, "jpn")])
    assert decide_subtitles(info, _profile()) is None


def test_avec_la_cle_seules_les_langues_voulues_restent(tmp_path):
    info = _info(tmp_path, sous_titres=[
        _st(0, "eng"), _st(1, "fra"), _st(2, "jpn"), _st(3, "fre"), _st(4, "spa")])
    gardes = decide_subtitles(info, _profile(subtitle_languages=["fre"]))
    assert gardes == [1, 3], "« fra » et « fre » sont tous deux du français"


def test_une_liste_vide_ne_filtre_pas(tmp_path):
    """Une clé vide n'est pas « ne garder aucun sous-titre » — ce serait un piège."""
    info = _info(tmp_path, sous_titres=[_st(0, "eng")])
    assert decide_subtitles(info, _profile(subtitle_languages=[])) is None


def test_la_selection_manuelle_prime_sur_le_filtre(tmp_path):
    info = _info(tmp_path, sous_titres=[_st(0, "eng"), _st(1, "jpn")])
    assert decide_subtitles(info, _profile(subtitle_languages=["fre"]),
                            override=[1]) == [1]


# ── IE-73 : un PGS forcé doublé par un SRT forcé n'est pas proposé à Jellyfin ─

def _force(index, langue, codec="subrip", titre="FR Forced", drapeau=False):
    return SubtitleTrack(index=index, codec=codec, language=langue,
                         title=titre, forced=drapeau)


def test_pgs_force_double_par_un_srt_force_est_ecarte(tmp_path):
    """Starship Troopers : SRT « FR Forced » et PGS « FR Forced »."""
    info = _info(tmp_path, sous_titres=[
        _force(0, "fre"), _force(1, "fre", codec="hdmv_pgs_subtitle"),
        _st(2, "fre")])
    assert decide_subtitles(info, _profile()) == [0, 2]
    assert decide_subtitles(info, _profile(subtitle_languages=["fre"])) == [0, 2]


def test_pgs_force_seul_de_sa_langue_reste(tmp_path):
    """Seul forcé de sa langue, le PGS reste, même si d'autres sous-titres existent."""
    info = _info(tmp_path, sous_titres=[
        _force(0, "fre", codec="hdmv_pgs_subtitle"), _st(1, "fre"),
        _force(2, "eng")])
    assert decide_subtitles(info, _profile()) is None


def test_le_drapeau_du_conteneur_suffit(tmp_path):
    info = _info(tmp_path, sous_titres=[
        _force(0, "eng", titre="", drapeau=True),
        _force(1, "eng", codec="hdmv_pgs_subtitle", titre="", drapeau=True)])
    assert decide_subtitles(info, _profile()) == [0]


def test_la_selection_manuelle_garde_le_pgs_force(tmp_path):
    info = _info(tmp_path, sous_titres=[
        _force(0, "fre"), _force(1, "fre", codec="hdmv_pgs_subtitle")])
    assert decide_subtitles(info, _profile(), override=[0, 1]) == [0, 1]


# ── Un PGS complet doublé par un SRT complet de même langue n'est pas proposé ─

def test_pgs_complet_double_par_un_srt_complet_est_ecarte(tmp_path):
    info = _info(tmp_path, sous_titres=[
        _st(0, "fre"), _st(1, "fre", codec="hdmv_pgs_subtitle"),
        _st(2, "eng", codec="hdmv_pgs_subtitle")])
    assert decide_subtitles(info, _profile()) == [0, 2]


def test_un_srt_force_ne_double_pas_un_pgs_complet(tmp_path):
    """Le SRT forcé ne couvre que les passages étrangers : le PGS complet reste."""
    info = _info(tmp_path, sous_titres=[
        _force(0, "fre"), _st(1, "fre", codec="hdmv_pgs_subtitle")])
    assert decide_subtitles(info, _profile()) is None


def test_pgs_complet_et_force_doubles_ensemble(tmp_path):
    info = _info(tmp_path, sous_titres=[
        _force(0, "fre"), _st(1, "fre"),
        _force(2, "fre", codec="hdmv_pgs_subtitle"),
        _st(3, "fre", codec="hdmv_pgs_subtitle")])
    assert decide_subtitles(info, _profile()) == [0, 1]
