"""
tests/test_aide.py — Le guide embarqué ne peut pas être en retard sur le code.

Un guide écrit à côté des `BINDINGS` dériverait comme le pied de page a dérivé
(IE-30) — en pire : on consulte un guide justement parce qu'on ne connaît pas
la réponse, donc on n'est pas en position de repérer qu'elle est fausse.

D'où la règle vérifiée ici : **toute touche déclarée est expliquée, et toute
explication porte sur une action qui existe.** Les deux sens comptent. Le
premier attrape la touche ajoutée sans un mot ; le second attrape l'explication
d'une fonction supprimée, qui survivrait en décrivant un comportement disparu.
"""
from __future__ import annotations

import pytest

from tui.screens import aide

_ECRANS = sorted(aide.classes_documentees())


@pytest.mark.parametrize("nom", _ECRANS)
def test_chaque_touche_declaree_est_expliquee(nom):
    """Une touche sans explication est une ligne vide dans le guide."""
    classe = aide.classes_documentees()[nom]
    muettes = [(t, a) for t, a, _ in aide.touches_de(classe)
               if not aide.explication(nom, a)]
    assert not muettes, (
        f"{nom} : touches déclarées sans explication dans tui/screens/aide.py "
        f"— {muettes}"
    )


@pytest.mark.parametrize("nom", _ECRANS)
def test_aucune_explication_ne_survit_a_son_action(nom):
    """Le sens inverse : une fonction retirée emporte son paragraphe."""
    classe  = aide.classes_documentees()[nom]
    reelles = {a for _, a, _ in aide.touches_de(classe)}
    orphelines = set(aide._PAR_ECRAN.get(nom, {})) - reelles
    assert not orphelines, (
        f"{nom} : explications sans action correspondante — {orphelines}"
    )


def test_les_explications_communes_correspondent_a_des_actions_reelles():
    reelles = {"aide", "request_quit"}          # portées par l'application
    for classe in aide.classes_documentees().values():
        reelles |= {a for _, a, _ in aide.touches_de(classe)}
    assert not set(aide._COMMUNES) - reelles


def test_le_guide_couvre_tous_les_ecrans_documentes():
    """Un écran ajouté sans entrée dans `_ORDRE` serait absent du guide."""
    dans_ordre = {n for n, _, _ in aide._ORDRE}
    assert dans_ordre == set(aide.classes_documentees())


def test_les_touches_du_cadre_textual_sont_ecartees():
    """`app.focus_next` et consorts ne font pas partie du vocabulaire de l'outil."""
    for classe in aide.classes_documentees().values():
        actions = {a for _, a, _ in aide.touches_de(classe)}
        assert not actions & aide._CADRE


def test_une_touche_a_alias_se_lit_par_sa_premiere_forme():
    """« +,plus,equals_sign,kp_plus » se lit « + », pas la liste entière."""
    assert aide._lisible("+,plus,equals_sign,kp_plus") == "+"
    assert aide._lisible("ctrl+up,ctrl+plus") == "Ctrl+up"
    assert aide._lisible("enter") == "↵"


def test_le_contenu_nomme_chaque_ecran_et_reste_lisible():
    """Le rendu lui-même, pas seulement les données qui le nourrissent."""
    texte = aide.AideScreen()._contenu().plain
    for _, titre, _ in aide._ORDRE:
        assert titre.upper() in texte, titre
    assert "PARTOUT" in texte
    # Rien ne doit déborder : la colonne de gauche fait 14, le total 74.
    trop = [l for l in texte.splitlines() if len(l) > 74]
    assert not trop, f"lignes trop longues : {trop[:3]}"


def test_une_explication_longue_saligne_sous_elle_meme():
    """La colonne de gauche reste une colonne, y compris au repli."""
    from rich.text import Text
    t = Text()
    aide.AideScreen._ligne(t, "M", "mot " * 40)
    lignes = t.plain.rstrip("\n").split("\n")
    assert len(lignes) > 1
    assert lignes[0].startswith("  M")
    for suite in lignes[1:]:
        assert suite.startswith(" " * 14), repr(suite[:20])
