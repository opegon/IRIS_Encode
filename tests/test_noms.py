"""
tests/test_noms.py — Savoir quelle piste est laquelle.

Deux défauts se cumulaient pour rendre six pistes indiscernables.

**Le nom des sous-titres n'était pas lu.** `SubtitleTrack` portait l'index, le
codec et la langue ; le scanner lisait les tags du flux et jetait le titre. Or
« Français (France) », « Français (France) (forced) » et « Français (Canada)
(SDH) » ont le même codec et la même langue : **seul le titre les sépare**.
L'assistant affichait « — » sur chacune.

**Les colonnes tronquaient par la droite**, c'est-à-dire exactement là où se
trouve ce qui distingue ces noms. À quatorze caractères, les six pistes d'un
rip s'écrivaient toutes « Français (Fra… ».

Conséquence mesurée sur un fichier réel : une piste « forced » de vingt-trois
répliques greffée à la place de la piste complète de 949.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.scanner import SubtitleTrack
from tui.common import tronquer_milieu


# ─── La troncature garde la fin ───────────────────────────────────────────────

def test_un_nom_qui_tient_n_est_pas_touche():
    assert tronquer_milieu("Français (France)", 26) == "Français (France)"


def test_la_fin_survit_a_la_troncature():
    """C'est « (forced) » qui porte le sens, pas « Français ( »."""
    coupe = tronquer_milieu("Français (France) (forced)", 14)
    assert coupe.endswith("forced)")
    assert len(coupe) == 14


@pytest.mark.parametrize("largeur", [8, 14, 20, 26, 40])
def test_la_largeur_n_est_jamais_depassee(largeur):
    """Un nom plus court passe entier — on ne rembourre rien."""
    rendu = tronquer_milieu("Français (Canada) (SDH)", largeur)
    assert len(rendu) <= largeur
    assert len(rendu) == min(largeur, len("Français (Canada) (SDH)"))


def test_les_six_pistes_d_un_rip_restent_distinctes():
    """Le cas du signalement : Silo.S03E09.720p.FR.mkv."""
    noms = [
        "Français (France) (forced)", "Français (France)",
        "Français (France) (SDH)", "Français (Canada) (forced)",
        "Français (Canada)", "Français (Canada) (SDH)",
    ]
    rendus = [tronquer_milieu(n, 26) for n in noms]
    assert len(set(rendus)) == 6, rendus


def test_une_troncature_a_droite_les_confondrait():
    """Ce que faisait l'ancienne colonne, et pourquoi elle induisait en erreur.

    Les trois variantes d'une même région ne diffèrent qu'après le
    quatorzième caractère : coupées à droite, elles s'écrivent à l'identique.
    """
    variantes = ("Français (France)", "Français (France) (forced)",
                 "Français (France) (SDH)")
    assert len({n[:14] for n in variantes}) == 1, "toutes « Français (Fran »"
    assert len({tronquer_milieu(n, 14) for n in variantes}) == 3


@pytest.mark.parametrize("largeur", [0, 1])
def test_les_largeurs_absurdes_ne_lèvent_pas(largeur):
    assert len(tronquer_milieu("Français", largeur)) == largeur


# ─── Le nom est lu ────────────────────────────────────────────────────────────

def test_une_piste_sans_nom_reste_valide():
    st = SubtitleTrack(index=0, codec="subrip", language="fre")
    assert st.title == ""


def test_le_nom_declare_est_conserve():
    st = SubtitleTrack(index=0, codec="subrip", language="fra",
                       title="Français canadien")
    assert st.title == "Français canadien"


def test_un_fichier_reel_rend_le_nom_de_ses_sous_titres():
    """Sans ce champ, rien ne distingue « Français » de « Français canadien »."""
    from core import dovi, scanner
    from core.config import get_bin_dir, load
    from core.preflight import get_tool_path

    p = (Path(__file__).resolve().parent.parent / "resources_files"
         / "silo.s03e09.1080p.mkv")
    if not p.exists():
        pytest.skip("silo.s03e09.1080p.mkv absent du dossier de travail")

    bd = get_bin_dir(load())
    scanner.set_dovi_path(dovi.get_path(bd))
    scanner.set_ffprobe_path(get_tool_path("ffprobe", bd))
    info = scanner.scan(p)

    francais = [st for st in info.subtitle_tracks if st.language == "fra"]
    assert len(francais) == 2, [st.language for st in info.subtitle_tracks]
    noms = {st.title for st in francais}
    assert noms == {"Français", "Français canadien"}, noms
