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

import re
from pathlib import Path

import pytest

from tui.common import TOUCHES as _TOUCHES
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
    assert aide._lisible("ctrl+up,ctrl+plus") == "CTRL+HAUT"


def test_le_guide_nomme_les_touches_en_toutes_lettres():
    """
    Le pied de page abrège, le guide nomme.

    Un glyphe tient en une colonne, ce qui décide sur un pied de page de trois
    lignes. Le guide n'a pas cette contrainte et a le devoir inverse : « ⇧Tab »
    se devine, « Shift+Tab » se lit. Un glyphe se cherche sur le clavier, un
    nom s'y trouve — et on ouvre le guide justement parce qu'on cherche.
    """
    assert aide._lisible("enter")     == "ENTER"
    assert aide._lisible("backspace") == "BACKSPACE"
    assert aide._lisible("space")     == "ESPACE"
    assert aide._lisible("shift+tab") == "SHIFT+TAB"
    assert aide._lisible("left")      == "GAUCHE"


def test_les_touches_du_guide_sont_en_capitales():
    """Les capitales suivent `raccourcis()`, et détachent le nom de son explication."""
    for classe in aide.classes_documentees().values():
        for touche, _, _ in aide.touches_de(classe):
            assert touche == touche.upper(), touche


def test_aucun_glyphe_dans_la_colonne_des_touches():
    """La règle porte sur le rendu, pas seulement sur la fonction qui le nourrit.

    Le contrôle se limite à la colonne de gauche : « ◄► » et « ← écartée »
    appartiennent aux explications, où ils citent ce que l'écran affiche.
    """
    texte = aide.AideScreen()._contenu().plain
    fautifs = [l for l in texte.splitlines()
               if any(g in l[:14] for g in "↵⌫␣⇧←→↑↓")]
    assert not fautifs, fautifs


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


# ─── GUIDE.md — le guide écrit à la main dérive aussi ────────────────────────
#
# Le guide embarqué dérive des `BINDINGS` : les tests ci-dessus suffisent à le
# tenir. `GUIDE.md` est écrit à la main, et rien ne le rattachait au code — il
# a passé quinze incréments sans être relu, et annonçait `<` pour élargir une
# colonne quand `<` la rétrécit.
#
# Ce que ces tests verrouillent est étroit à dessein : **une touche annoncée
# par le guide doit exister**. Ils ne prétendent pas vérifier une explication,
# qui est du texte ; ils attrapent la promesse d'un geste qui ne répond plus.

_GUIDE = Path(__file__).resolve().parent.parent / "GUIDE.md"

# Les tables de touches du guide, par écran documenté.
_TABLES_GUIDE = {
    "2.1": ("tui.screens.browser", "BrowserScreen"),
    "2.1bis": ("tui.screens.join", "JoinScreen"),
    "2.2": ("tui.screens.tracks",  "TracksScreen"),
    "2.4": ("tui.screens.sync",    "SyncScreen"),
    "2.5": ("tui.screens.dryrun",  "DryrunScreen"),
    "2.6": ("tui.screens.run",     "RunScreen"),
}

# Notation affichée → nom Textual. L'inverse de `tui.common.TOUCHES`, plus les
# formes que le guide compose lui-même (« Maj+↑ » pour `shift+up`).
_VERS_TEXTUAL = {affiche.lower(): nom for nom, affiche in _TOUCHES.items()}
_VERS_TEXTUAL.update({
    "espace": "space", "maj+tab": "shift+tab",
    "maj+↑": "shift+up", "maj+↓": "shift+down",
    "ctrl+↑": "ctrl+up", "ctrl+↓": "ctrl+down",
    "↑": "up", "↓": "down",
})


def _touches_reelles(module: str, classe: str) -> set[str]:
    """Toutes les touches auxquelles cet écran répond, mixins compris."""
    import importlib

    ecran = getattr(importlib.import_module(module), classe)
    touches: set[str] = set()
    for base in ecran.__mro__:
        for b in getattr(base, "BINDINGS", []):
            brut = b.key if hasattr(b, "key") else b[0]
            touches |= {k.strip().lower() for k in str(brut).split(",")}
    return touches


def _touches_annoncees(section: str) -> set[str]:
    """Les touches citées dans la table de cette section du guide."""
    texte = _GUIDE.read_text(encoding="utf-8")
    debut = texte.index(f"### {section} ")
    fin   = texte.index("\n### ", debut + 5)

    annoncees: set[str] = set()
    for ligne in texte[debut:fin].splitlines():
        cellule = re.match(r"\|\s*(.+?)\s*\|", ligne)
        if not cellule or "Touche" in cellule.group(1):
            continue
        for cite in re.findall(r"`([^`]+)`", cellule.group(1)):
            # « ←/→ », « Ctrl+↑/↓ », « F1 / F2 » : chaque moitié est une touche
            for moitie in re.split(r"\s*/\s*", cite):
                moitie = moitie.strip()
                if moitie:
                    annoncees.add(moitie)
    return annoncees


def _resout(annoncee: str) -> set[str]:
    """Noms Textual possibles pour une notation du guide."""
    bas = annoncee.lower()
    cands = {bas, _VERS_TEXTUAL.get(bas, bas)}
    # « Ctrl+↓ » écrit comme moitié de « Ctrl+↑/↓ » perd son préfixe
    for prefixe in ("ctrl+", "shift+", "maj+"):
        if bas in ("↑", "↓"):
            cands.add(_VERS_TEXTUAL.get(prefixe + bas, ""))
    return {c for c in cands if c}


@pytest.mark.parametrize("section", sorted(_TABLES_GUIDE))
def test_le_guide_n_annonce_que_des_touches_qui_repondent(section):
    module, classe = _TABLES_GUIDE[section]
    reelles = _touches_reelles(module, classe)
    fantomes = sorted(a for a in _touches_annoncees(section)
                      if not (_resout(a) & reelles))
    assert not fantomes, (
        f"GUIDE.md § {section} annonce des touches absentes des BINDINGS de "
        f"{classe} : {fantomes}")


def test_le_guide_documente_bien_des_touches():
    """Le garde-fou du garde-fou : un extracteur muet passerait au vert."""
    for section in _TABLES_GUIDE:
        assert len(_touches_annoncees(section)) >= 3, section


def test_l_entete_du_guide_suit_la_version():
    """Règle 5.4 : tout document qui affiche une version la tient à jour.

    Le guide était resté en 0.8.1.23 pendant quinze incréments — assez pour
    qu'on ne sache plus ce qu'il décrit.
    """
    import version as version_mod

    entete = _GUIDE.read_text(encoding="utf-8").splitlines()[2]
    assert version_mod.__version__ in entete, (
        f"GUIDE.md annonce « {entete} » pour une application en "
        f"{version_mod.__version__}")
