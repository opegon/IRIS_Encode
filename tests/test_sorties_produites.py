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

v0.8.8.11 : les suffixes deviennent `.<caractéristique>-iris`, et le filtre ne
regarde plus que la marque `-iris` en fin de nom — une seule chose à suivre
au lieu d'une liste. `.mux-iris` et `.join-iris` en sont exceptés. Les noms
de l'ancien schéma ne sont plus reconnus, à la demande.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.decision import SUFFIX_BY_ACTION, SUFFIX_DV_COPIE, VideoAction
from core.joiner import JOIN_SUFFIX
from core.muxer import MUX_SUFFIX
from core.scanner import deja_produit, stem_sans_suffixe_produit


# ─── Toute sortie d'encodage porte la marque ─────────────────────────────────

@pytest.mark.parametrize("action", [a for a in VideoAction
                                    if SUFFIX_BY_ACTION.get(a)])
def test_chaque_action_qui_ecrit_un_suffixe_est_filtree(action):
    """Ajouter un codec au projet doit suffire : le filtre suit tout seul."""
    assert deja_produit(f"Film{SUFFIX_BY_ACTION[action]}")


def test_la_sortie_d_une_source_dv_conservee_n_est_pas_reproposee():
    assert deja_produit(f"Film{SUFFIX_DV_COPIE}")


@pytest.mark.parametrize("stem", ["Film.av1-iris", "Film.HDR10-iris",
                                  "Film.2160p.DV-iris", "Film.hevc-iris(2)"])
def test_les_sorties_ne_reviennent_pas_au_scan(stem):
    """Le suffixe peut se réduire à `-iris` (caractéristique déjà dans le nom),
    et la numérotation de collision le suit."""
    assert deja_produit(stem)


@pytest.mark.parametrize("suffixe", [MUX_SUFFIX, JOIN_SUFFIX])
def test_le_mux_et_le_collage_restent_visibles(suffixe):
    """Ce ne sont pas des encodages : on doit pouvoir les encoder ensuite."""
    assert not deja_produit(f"Film{suffixe}")
    assert not deja_produit(f"Film{suffixe}(2)")


@pytest.mark.parametrize("stem", [
    "Le Nom du film (2017)",
    "Hotel.Iris.2021",          # la casse compte
    "Hotel.Iris",
    "Hotel-Iris",
    "Film.hevc.IRIS",           # ancienne marque : plus reconnue
    "Film.hevc-iris (copie)",   # la marque doit finir le nom
    "Film-iris.1080p",
    "Film_[hevc]",              # ancien schéma : plus reconnu
    "Film_[av1]",
])
def test_un_fichier_ordinaire_passe(stem):
    assert not deja_produit(stem)


@pytest.mark.parametrize("stem, attendu", [
    ("Film.hevc-iris",     "Film.hevc"),
    ("Film.hevc-iris(3)",  "Film.hevc"),
    ("Film.join-iris",     "Film.join"),
    ("Film (2)",           "Film (2)"),
    ("Film.hevc-iris (copie)", "Film.hevc-iris (copie)"),
])
def test_seule_la_marque_finale_part(stem, attendu):
    assert stem_sans_suffixe_produit(stem) == attendu


# ─── Les filtres passent par lui ─────────────────────────────────────────────

def _sources() -> list[Path]:
    racine = Path(__file__).resolve().parent.parent
    return [racine / "core" / "scanner.py",
            racine / "tui" / "widgets" / "file_tree.py"]


def test_plus_aucun_litteral_de_suffixe_dans_les_filtres():
    """Le défaut n'était pas la valeur, c'était les quatre copies."""
    fautifs = {}
    for f in _sources():
        lignes = [n for n, l in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
                  if '".hevc-iris"' in l or '".h264-iris"' in l]
        if lignes:
            fautifs[f.name] = lignes
    assert not fautifs, f"suffixes encore écrits en dur : {fautifs}"


def test_le_scan_ecarte_ce_qu_il_a_produit(tmp_path, monkeypatch):
    """Bout à bout : le fichier n'est pas seulement non proposé, il n'est pas lu."""
    from core import scanner

    for nom in ("Film.mkv", "Film.av1-iris.mkv", "Film.hdr10-iris.mkv",
                "Film.mux-iris.mkv", "Film.join-iris.mkv", "Film.hevc-iris.mkv"):
        (tmp_path / nom).write_bytes(b"")

    scannes: list[str] = []
    monkeypatch.setattr(scanner, "scan",
                        lambda p: scannes.append(p.name) or _FAUX_INFO(p))
    scanner.scan_directory_recursive(tmp_path)
    assert sorted(scannes) == ["Film.join-iris.mkv", "Film.mkv",
                               "Film.mux-iris.mkv"], scannes


def _FAUX_INFO(p: Path):
    from core.scanner import VideoInfo
    return VideoInfo(path=p, width=1920, height=1080, bitrate=1, codec="hevc",
                     duration=1.0, frame_count=0, dv_profile=None)
