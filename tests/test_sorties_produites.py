"""
tests/test_sorties_produites.py — L'application ne se propose pas ses propres sorties.

IE-49. Le filtre « déjà produit ici » connaissait deux littéraux, `_[hevc]` et
`_[H264]`, recopiés à quatre endroits sans jamais dériver de `SUFFIX_BY_ACTION`.
L'application a depuis appris à écrire `_[av1]` et `_[hdr10]`, et aucun des
quatre n'a suivi.

Le cas coûteux est l'AV1. Ce codec n'est pas dans `CODECS_LISIBLES` : un
`Film_[av1].mkv` reparu au scan fait tomber `decide_video` en CAS 3 — « codec
non lu par la chaîne » — qui propose de réencoder en HEVC une sortie que
l'application venait de produire. Sur le profil livré `basic_delete`, qui a
`delete_source = true`, l'AV1 est effacé au passage : perte de génération
irréversible sur un fichier que personne n'a demandé à retoucher.

`_[mux]` reste **volontairement** hors du filtre : ce n'est pas un encodage
mais une greffe de pistes, et encoder le résultat ensuite est un geste
légitime. L'écarter du scan rendrait le fichier invisible dans le navigateur.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.decision import SUFFIX_BY_ACTION, VideoAction
from core.muxer import MUX_SUFFIX
from core.scanner import deja_produit, suffixes_produits


# ─── Le prédicat dérive, il ne recopie pas ───────────────────────────────────

def test_tous_les_suffixes_d_encodage_sont_couverts():
    """La question à laquelle la paire en dur ne savait pas répondre."""
    attendus = {s for s in SUFFIX_BY_ACTION.values() if s}
    assert suffixes_produits() == attendus
    # Et nommément, pour que l'échec dise lequel manque
    for suffixe in ("_[hevc]", "_[H264]", "_[av1]", "_[hdr10]"):
        assert suffixe in suffixes_produits(), suffixe


@pytest.mark.parametrize("action", [a for a in VideoAction
                                    if SUFFIX_BY_ACTION.get(a)])
def test_chaque_action_qui_ecrit_un_suffixe_est_filtree(action):
    """Ajouter un codec au projet doit suffire : le filtre suit tout seul."""
    assert deja_produit(f"Film{SUFFIX_BY_ACTION[action]}")


def test_l_av1_ne_revient_pas_au_scan():
    """Le cas signalé — et le plus coûteux, `av1` n'étant pas un codec lu."""
    assert deja_produit("Film_[av1]")


def test_le_hdr10_ne_revient_pas_au_scan():
    assert deja_produit("Film_[hdr10]")


def test_le_mux_reste_visible():
    """Un remux n'est pas un encodage : on doit pouvoir l'encoder ensuite."""
    assert not deja_produit(f"Film{MUX_SUFFIX}")
    assert MUX_SUFFIX not in suffixes_produits()


def test_un_fichier_ordinaire_passe():
    assert not deja_produit("Le Nom du film (2017)")


def test_le_suffixe_vide_de_skip_ne_filtre_pas_tout():
    """`SUFFIX_BY_ACTION[SKIP]` vaut `""`, et `"" in stem` est toujours vrai."""
    assert "" not in suffixes_produits()
    assert not deja_produit("n'importe quoi")


# ─── Les quatre usages passent par lui ───────────────────────────────────────

def _sources() -> list[Path]:
    racine = Path(__file__).resolve().parent.parent
    return [racine / "core" / "scanner.py",
            racine / "tui" / "widgets" / "file_tree.py"]


def test_plus_aucun_litteral_de_suffixe_dans_les_filtres():
    """Le défaut n'était pas la valeur, c'était les quatre copies.

    Une seule oubliée et le filtre redevient faux à un endroit — ce qui est
    exactement ce qui s'est produit trois fois de suite.
    """
    fautifs = {}
    for f in _sources():
        lignes = [n for n, l in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
                  if '"_[hevc]"' in l or '"_[H264]"' in l]
        if lignes:
            fautifs[f.name] = lignes
    assert not fautifs, f"suffixes encore écrits en dur : {fautifs}"


def test_la_propriete_de_videoinfo_suit_le_meme_predicat(tmp_path):
    from core.scanner import VideoInfo

    def _info(nom: str) -> VideoInfo:
        return VideoInfo(path=tmp_path / f"{nom}.mkv", width=1920, height=1080,
                         bitrate=8_000_000, codec="hevc", duration=1.0,
                         frame_count=0, dv_profile=None)

    assert _info("Film_[av1]").is_already_encoded
    assert _info("Film_[hdr10]").is_already_encoded
    assert not _info("Film_[mux]").is_already_encoded
    assert not _info("Film").is_already_encoded


def test_le_scan_ecarte_ce_qu_il_a_produit(tmp_path, monkeypatch):
    """Bout à bout : le fichier n'est pas seulement non proposé, il n'est pas lu."""
    from core import scanner

    for nom in ("Film.mkv", "Film_[av1].mkv", "Film_[hdr10].mkv",
                "Film_[mux].mkv", "Film_[hevc].mkv"):
        (tmp_path / nom).write_bytes(b"")

    scannes: list[str] = []
    monkeypatch.setattr(scanner, "scan",
                        lambda p: scannes.append(p.name) or _FAUX_INFO(p))
    scanner.scan_directory(tmp_path)
    assert sorted(scannes) == ["Film.mkv", "Film_[mux].mkv"], scannes


def _FAUX_INFO(p: Path):
    from core.scanner import VideoInfo
    return VideoInfo(path=p, width=1920, height=1080, bitrate=1, codec="hevc",
                     duration=1.0, frame_count=0, dv_profile=None)
