"""
tests/test_run_colonne_fichier.py — La colonne Fichier de l'écran d'encodage.

Elle prenait la largeur du plus long nom : sur un nom de release, les
colonnes de droite, dont l'état de l'encodage, sortaient de l'écran. Elle
prend désormais la place que les autres laissent, et le nom est coupé au
milieu, comme à l'accueil.

Coupé au milieu seulement, un nom de release perdait son `S01E02` : deux
épisodes s'affichaient pareil. `tronquer_nom` le garde, ici et à l'accueil.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from tui.common import tronquer_milieu, tronquer_nom
from tui.screens.run import RunScreen

# Icône, profil, durée, taille, action, décodage, filtre, encodage, état.
AUTRES = [3, 13, 8, 24, 12, 6, 6, 7, 50]
OCCUPE = sum(AUTRES) + 2 * (len(AUTRES) + 1) + 2      # marges, barre


def _ecran(largeur: int):
    return SimpleNamespace(size=SimpleNamespace(width=largeur),
                           _MARGE_CELLULE=RunScreen._MARGE_CELLULE,
                           _BARRE_DEFILEMENT=RunScreen._BARRE_DEFILEMENT,
                           _PLANCHER_NOM=RunScreen._PLANCHER_NOM)


def _largeur(largeur_ecran: int, besoin: int) -> int:
    return RunScreen._largeur_fichier(_ecran(largeur_ecran), besoin, AUTRES)


def test_un_nom_long_laisse_la_place_aux_autres_colonnes():
    largeur = _largeur(220, 90)
    assert 20 < largeur < 90
    assert largeur + OCCUPE == 220


def test_un_nom_court_ne_prend_que_sa_place():
    assert _largeur(220, 30) == 30


def test_jamais_sous_le_plancher():
    assert _largeur(100, 90) == RunScreen._PLANCHER_NOM


def test_ecran_pas_encore_monte():
    assert _largeur(0, 90) == 90


def test_le_nom_est_coupe_au_milieu():
    nom = "Une.Serie.Tres.Longue.S01E02.MULTi.1080p.WEB.H264-GROUPE.mkv"
    coupe = tronquer_milieu(nom, 30)
    assert len(coupe) == 30 and "…" in coupe
    assert coupe.startswith("Une.Serie") and coupe.endswith("GROUPE.mkv")


# ─── Le repère d'épisode reste ───────────────────────────────────────────────

SERIE = "Une.Serie.Vraiment.Tres.Longue.{ep}.MULTi.1080p.WEB.H264-GROUPE.mkv"


@pytest.mark.parametrize("largeur", [12, 20, 26, 40, 60])
def test_deux_episodes_restent_distincts(largeur):
    un, deux = (tronquer_nom(SERIE.format(ep=ep), largeur)
                for ep in ("S01E01", "S01E02"))
    assert "S01E01" in un and "S01E02" in deux
    assert len(un) == len(deux) == largeur


def test_debut_repere_et_fin():
    assert tronquer_nom(SERIE.format(ep="S01E02"), 26) == "Une.Serie…S01E02…ROUPE.mkv"


@pytest.mark.parametrize("ep", ["S01E01E02", "S01E01-E02", "s1e2", "S2024E105"])
def test_formes_du_repere(ep):
    assert ep in tronquer_nom(SERIE.format(ep=ep), 30)


def test_pas_de_repere_coupe_au_milieu():
    nom = "Un.Film.Vraiment.Tres.Long.2024.MULTi.1080p.WEB.H264-GROUPE.mkv"
    assert tronquer_nom(nom, 26) == tronquer_milieu(nom, 26)


def test_pas_un_repere_au_milieu_d_un_mot():
    nom = "Documentaire.Series01E02.Tres.Long.MULTi.1080p.WEB.H264-GROUPE.mkv"
    assert tronquer_nom(nom, 26) == tronquer_milieu(nom, 26)


def test_un_nom_qui_tient_reste_entier():
    nom = SERIE.format(ep="S01E02")
    assert tronquer_nom(nom, len(nom)) == nom


def test_repere_en_debut_de_nom():
    nom = "S01E02.Une.Serie.Vraiment.Tres.Longue.MULTi.1080p.WEB-GROUPE.mkv"
    coupe = tronquer_nom(nom, 20)
    assert coupe.startswith("S01E02") and len(coupe) == 20


def test_trop_etroit_pour_le_repere():
    nom = SERIE.format(ep="S01E02")
    assert tronquer_nom(nom, 7) == tronquer_milieu(nom, 7)


# ─── La colonne État à 38 ────────────────────────────────────────────────────

def _etat_affiche(en_pause: bool) -> str:
    """Le texte de la colonne État d'un fichier en cours, au pire cas."""
    from core.encoder import ProgressInfo
    from tui.screens.run import FileRunStatus, FileState
    cellules: dict = {}
    table = SimpleNamespace(update_cell=lambda ligne, col, valeur, **kw:
                            cellules.__setitem__(col, valeur))
    statut = FileRunStatus(decision=None, state=FileState.RUNNING, percent=1.0)
    # 01:23:45 encodés sur 03:23:45, à 12,34x : les champs à leur plus long.
    statut._last_progress = ProgressInfo(frame=0, fps=0.0, elapsed=5025.0,
                                         bitrate=0.0, speed=12.34, percent=1.0,
                                         duration=12225.0)
    ecran = SimpleNamespace(_statuses=[statut], en_pause=en_pause, _current_idx=0,
                            query_one=lambda *a, **kw: table,
                            _icon=lambda statut_: "▶")
    RunScreen._update_row(ecran, 0)
    return cellules["state"].plain


def test_l_etat_en_pause_tient_dans_la_colonne():
    from tui.screens.run import LARGEUR_ETAT
    texte = _etat_affiche(en_pause=True)
    assert "x)" not in texte, "la vitesse d'avant la pause ne s'affiche plus"
    assert len(texte) <= LARGEUR_ETAT == 38, texte


def test_l_etat_en_cours_garde_la_vitesse():
    from tui.screens.run import LARGEUR_ETAT
    texte = _etat_affiche(en_pause=False)
    assert "12.34x" in texte and len(texte) <= LARGEUR_ETAT, texte
