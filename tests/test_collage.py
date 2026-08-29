"""
tests/test_collage.py — Collage bout à bout de plusieurs parties (`core/joiner.py`).

Trois choses ne doivent jamais être approximatives ici :

- **l'ordre** — coller `part2` avant `part1` produit un fichier de la bonne
  durée, donc silencieusement faux ;
- **le refus** — mkvmerge n'apparie pas n'importe quoi, et l'apprendre au bout
  d'une copie de 30 Go n'est pas une option ;
- **la sortie** — elle ne doit jamais tomber sur une des parties.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.joiner import (JOIN_SUFFIX, MIN_PARTIES, build_join_command,
                         controler, derive_duree, duree_attendue,
                         join_output_path, nom_commun, ordre_naturel)
from core.scanner import AudioTrack, SubtitleTrack, VideoInfo, deja_produit


def _info(nom: str, *, duration: float = 3600.0, codec: str = "hevc",
          width: int = 1920, height: int = 1080,
          audio: list[tuple[str, int]] | None = None,
          subs: int = 1) -> VideoInfo:
    """VideoInfo minimale : seuls les champs que le collage regarde comptent."""
    pistes = audio if audio is not None else [("eac3", 6)]
    return VideoInfo(
        path=Path("D:/films") / nom, width=width, height=height,
        bitrate=5_000_000, codec=codec, duration=duration,
        frame_count=0, dv_profile=None,
        audio_tracks=[
            AudioTrack(index=i, codec=c, channels=ch, language="fre",
                       title="", bitrate=640_000)
            for i, (c, ch) in enumerate(pistes)
        ],
        subtitle_tracks=[
            SubtitleTrack(index=i, codec="subrip", language="fre")
            for i in range(subs)
        ],
    )


# ─── Ordre ────────────────────────────────────────────────────────────────────

def test_ordre_naturel_suit_les_nombres():
    """`part10` vient après `part2`, là où un tri alphabétique l'inverse."""
    noms = ["Film part10.mkv", "Film part2.mkv", "Film part1.mkv"]
    parts = [Path("D:/films") / n for n in noms]
    assert [p.name for p in ordre_naturel(parts)] == [
        "Film part1.mkv", "Film part2.mkv", "Film part10.mkv"]


def test_ordre_naturel_sans_nombre_reste_alphabetique():
    parts = [Path("b.mkv"), Path("a.mkv")]
    assert [p.name for p in ordre_naturel(parts)] == ["a.mkv", "b.mkv"]


def test_ordre_naturel_ne_compare_jamais_un_nombre_a_du_texte():
    """La clé est faite de tuples homogènes : aucun `int < str` possible.

    Un `sorted` sur des clés mixtes lève `TypeError` sur certains jeux de noms
    seulement — le genre de panne qui n'arrive que chez l'utilisateur.
    """
    noms = ["1.mkv", "a.mkv", "a1.mkv", "1a.mkv", "ab.mkv", "a-1.mkv", "a-b.mkv"]
    parts = [Path(n) for n in noms]
    assert len(ordre_naturel(parts)) == len(noms)   # ne lève pas


# ─── Nom du fichier produit ───────────────────────────────────────────────────

@pytest.mark.parametrize("noms, attendu", [
    (["Film part1.mkv", "Film part2.mkv"],        "Film"),
    (["Film.CD1.mkv", "Film.CD2.mkv"],            "Film"),
    (["Le Film (2017) pt1.mkv",
      "Le Film (2017) pt2.mkv"],                  "Le Film (2017)"),
    (["Film_disque1.mkv", "Film_disque2.mkv"],    "Film"),
    (["Film 1.mkv", "Film 2.mkv"],                "Film"),
])
def test_nom_commun_retire_le_marqueur_de_partie(noms, attendu):
    assert nom_commun([Path(n) for n in noms]) == attendu


def test_nom_commun_sans_prefixe_commun_prend_la_premiere_partie():
    """Mieux vaut un nom imparfait qu'un `_[join].mkv` sans nom."""
    assert nom_commun([Path("alpha.mkv"), Path("beta.mkv")]) == "alpha"


def test_join_output_path_est_dans_le_dossier_des_parties():
    parts = [Path("D:/films/Film part1.mkv"), Path("D:/films/Film part2.mkv")]
    sortie = join_output_path(parts)
    assert sortie == Path("D:/films/Film_[join].mkv")
    assert sortie.parent == parts[0].parent


def test_le_fichier_colle_reste_visible_au_scan():
    """`_[join]` n'est pas une sortie d'encodage : le navigateur doit le voir.

    L'écarter comme `_[hevc]` rendrait le collage inutile — on ne pourrait
    plus travailler son propre résultat, qui est tout l'objet de la fonction.
    """
    assert not deja_produit(f"Film{JOIN_SUFFIX}")


# ─── Contrôle de compatibilité ────────────────────────────────────────────────

def test_deux_parties_identiques_sont_collables():
    ctrl = controler([_info("p1.mkv"), _info("p2.mkv")])
    assert ctrl.collable
    assert not ctrl.avertissements


def test_codec_video_different_bloque():
    ctrl = controler([_info("p1.mkv", codec="hevc"),
                      _info("p2.mkv", codec="h264")])
    assert not ctrl.collable
    assert "h264" in ctrl.blocages[0]


def test_definition_differente_bloque():
    ctrl = controler([_info("p1.mkv", width=1920, height=1080),
                      _info("p2.mkv", width=1280, height=720)])
    assert not ctrl.collable
    assert any("1280" in b for b in ctrl.blocages)


def test_codec_audio_different_bloque():
    ctrl = controler([_info("p1.mkv", audio=[("eac3", 6)]),
                      _info("p2.mkv", audio=[("ac3", 6)])])
    assert not ctrl.collable


def test_nombre_de_canaux_different_bloque():
    ctrl = controler([_info("p1.mkv", audio=[("eac3", 6)]),
                      _info("p2.mkv", audio=[("eac3", 2)])])
    assert not ctrl.collable
    assert "2.0" in ctrl.blocages[0]


def test_piste_audio_en_trop_avertit_sans_bloquer():
    """mkvmerge n'appariera que le premier rang : le dire, ne pas refuser."""
    ctrl = controler([_info("p1.mkv", audio=[("eac3", 6)]),
                      _info("p2.mkv", audio=[("eac3", 6), ("eac3", 2)])])
    assert ctrl.collable
    assert ctrl.avertissements


def test_sous_titre_en_moins_avertit_sans_bloquer():
    ctrl = controler([_info("p1.mkv", subs=2), _info("p2.mkv", subs=1)])
    assert ctrl.collable
    assert any("sous-titres" in a for a in ctrl.avertissements)


def test_une_seule_partie_ne_se_colle_pas():
    ctrl = controler([_info("p1.mkv")])
    assert not ctrl.collable


def test_la_premiere_partie_est_la_reference():
    """Inverser l'ordre inverse le sens du message, pas le verdict."""
    a, b = _info("p1.mkv", codec="hevc"), _info("p2.mkv", codec="h264")
    assert not controler([a, b]).collable
    assert not controler([b, a]).collable


# ─── Commande ─────────────────────────────────────────────────────────────────

def test_build_join_command_intercale_un_plus():
    """Le `+` est ce qui distingue un collage d'un mux : sans lui, mkvmerge
    superposerait les pistes au lieu de les enchaîner."""
    parts  = [Path("D:/films/p1.mkv"), Path("D:/films/p2.mkv"),
              Path("D:/films/p3.mkv")]
    sortie = Path("D:/films/Film_[join].mkv")
    cmd    = build_join_command(parts, sortie)

    assert cmd[1:4] == ["--gui-mode", "-o", str(sortie)]
    assert cmd[4:] == [str(parts[0]), "+", str(parts[1]), "+", str(parts[2])]
    assert cmd.count("+") == len(parts) - 1


def test_build_join_command_suit_le_chemin_mkvmerge_pose():
    """`set_mkvmerge_path` est appelé après l'import : la commande doit le lire
    au moment où elle est construite, pas au chargement du module."""
    from core import muxer

    muxer.set_mkvmerge_path("D:/bin/mkvmerge.exe")
    cmd = build_join_command([Path("p1.mkv"), Path("p2.mkv")],
                             Path("out.mkv"))
    assert cmd[0] == "D:/bin/mkvmerge.exe"


def test_build_join_command_refuse_une_seule_partie():
    with pytest.raises(ValueError, match=str(MIN_PARTIES)):
        build_join_command([Path("p1.mkv")], Path("out.mkv"))


def test_build_join_command_refuse_une_partie_en_double():
    with pytest.raises(ValueError, match="deux fois"):
        build_join_command([Path("p1.mkv"), Path("p1.mkv")], Path("out.mkv"))


def test_build_join_command_refuse_d_ecraser_une_partie():
    parts = [Path("D:/films/p1.mkv"), Path("D:/films/p2.mkv")]
    with pytest.raises(ValueError, match="Collage refusé"):
        build_join_command(parts, parts[1])


# ─── Vérification du résultat ─────────────────────────────────────────────────

def test_duree_attendue_est_la_somme_des_parties():
    infos = [_info("p1.mkv", duration=3852.0), _info("p2.mkv", duration=3527.0)]
    assert duree_attendue(infos) == pytest.approx(7379.0)


def test_derive_duree_tolere_l_arrondi_des_blocs():
    assert derive_duree(7379.0, 7379.8) is None


def test_derive_duree_signale_un_collage_tronque():
    """Un mkvmerge tué en route laisse un fichier lisible et court — même
    piège qu'IE-41, où un ffmpeg mort passait pour un film court."""
    ecart = derive_duree(7379.0, 3852.0)
    assert ecart is not None and ecart < 0


def test_derive_duree_sans_duree_attendue_ne_conclut_pas():
    assert derive_duree(0.0, 1234.0) is None
