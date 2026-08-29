"""
tests/test_pas_decalage.py — Les trois pas du réglage de décalage.

Une mesure rend souvent la bonne valeur à quelques dizaines de millisecondes
près. Avec 100 ms comme plus petit pas, on ne pouvait pas s'en approcher : on
passait de −1 100 à −1 000 sans jamais atteindre −1 050.

Le pas fin comble ce trou. Ce qui se vérifie ici est double : que les trois pas
existent et se distinguent, et que les touches qui les portent soient des noms
que Textual sait produire — une liaison sur un nom inconnu ne déclenche jamais
rien, et ne le dit pas.
"""
from __future__ import annotations

import pytest
from textual.keys import Keys

from tui.screens import sync as ecran

_NOMS_TEXTUAL = {k.value for k in Keys}


def test_les_trois_pas_sont_distincts_et_ordonnes():
    assert ecran._DELAY_FINE_MS == 10
    assert ecran._DELAY_FINE_MS < ecran._DELAY_STEP_MS < ecran._DELAY_JUMP_MS


def _binding(action: str):
    for b in ecran.SyncScreen.BINDINGS:
        if getattr(b, "action", "") == action:
            return b
    raise AssertionError(f"aucune liaison pour {action}")


@pytest.mark.parametrize("action,attendue", [
    ("fine_up",   "ctrl+up"),
    ("fine_down", "ctrl+down"),
])
def test_le_pas_fin_a_une_touche_que_textual_sait_produire(action, attendue):
    """
    Le piège : `Ctrl+±` n'existe pas comme nom de touche.

    Textual ne connaît ni `ctrl+plus` ni `ctrl+minus`, et en mode terminal
    virtuel — celui qu'il active aussi sous Windows — `Ctrl+=` ne produit
    généralement aucun code. Seul `Ctrl+-` passe, sous le nom
    `ctrl+underscore`. Les alias restent liés pour les terminaux qui savent les
    envoyer, mais au moins un nom **connu de Textual** doit figurer dans la
    liste, sinon le raccourci est mort sans que rien ne le signale.
    """
    touches = [t.strip() for t in _binding(action).key.split(",")]
    assert attendue in touches
    connues = [t for t in touches if t in _NOMS_TEXTUAL]
    assert connues, f"aucune touche connue de Textual parmi {touches}"


def test_les_deux_sens_sont_symetriques():
    """Un pas qui ne marche que dans un sens est pire que pas de pas du tout."""
    haut = [t.strip() for t in _binding("fine_up").key.split(",")]
    bas  = [t.strip() for t in _binding("fine_down").key.split(",")]
    assert len(haut) == len(bas)


def test_le_bandeau_annonce_le_pas_fin():
    """
    Une capacité qui ne se signale pas n'existe pas — c'est le constat IE-36.

    Le bandeau nomme la touche garantie, pas les alias : annoncer `Ctrl+±`
    enverrait l'utilisateur sur une touche que son terminal peut ne pas
    transmettre.

    L'annonce vit désormais sur la ligne du champ actif, qu'aucun message ne
    chasse — voir `tests/test_champ_visible.py`.
    """
    ligne = ecran.ligne_champ("delay")
    assert "±10 ms" in ligne
    # `raccourcis()` capitalise les noms de touches — c'est son rendu, pas une
    # information : on cherche la touche, pas sa casse.
    assert "ctrl+↑/↓" in ligne.lower()
