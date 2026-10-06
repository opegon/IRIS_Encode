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

from core import i18n
from tui.common import TOUCHES as _TOUCHES, touche as _touche
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
    reelles = {"aide", "request_quit", "encodages"}   # portées par l'application
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
    assert aide._lisible("ctrl+up,ctrl+plus") == "Ctrl+↑"


def test_le_guide_ecrit_les_touches_comme_le_pied_de_page():
    """
    UX-10 : le guide nommait les touches en toutes lettres (« SHIFT+TAB »,
    « ESPACE »), le pied de page en glyphes (« ⇧Tab », « ␣ ») — deux
    notations pour une même touche, sur deux écrans qu'on consulte ensemble.
    Une seule désormais, celle de `touche()`.
    """
    from tui.common import touche
    for nom in ("enter", "backspace", "space", "shift+tab", "left", "w", "f4"):
        assert aide._lisible(nom) == touche(nom)
    assert aide._lisible("shift+tab") == "⇧Tab"


def test_le_contenu_nomme_chaque_ecran_et_reste_lisible():
    """Le rendu lui-même, pas seulement les données qui le nourrissent."""
    texte = aide.AideScreen()._contenu().plain
    for _, titre, _ in aide._ORDRE:
        assert i18n._(titre).upper() in texte, titre
    assert "PARTOUT" in texte
    # Rien ne doit déborder : la colonne de gauche fait 14, le total 74.
    trop = [l for l in texte.splitlines() if len(l) > 74]
    assert not trop, f"lignes trop longues : {trop[:3]}"


def _textes_du_guide() -> list[str]:
    textes = list(aide._COMMUNES.values())
    for par_action in aide._PAR_ECRAN.values():
        textes += par_action.values()
    for _, titre, resume in aide._ORDRE:
        textes += [titre, resume]
    return textes


def test_le_guide_est_traduit():
    """IE-89 : le guide suit la langue de l'application. Une explication que
    le catalogue ne traduit pas resterait en anglais au milieu du français."""
    muets = [t for t in _textes_du_guide() if i18n._(t) == t]
    assert not muets, muets[:3]


def test_les_libelles_cites_sont_ceux_de_l_ecran():
    """L-55 : une explication cite un libellé ou une touche par paramètre,
    jamais recopié. Tout paramètre du texte source est fourni au rendu, et
    la traduction n'en invente ni n'en perd aucun."""
    import string
    fournis = set(aide._parametres())

    def noms(texte):
        return {n for _, n, _, _ in string.Formatter().parse(texte) if n}

    for t in _textes_du_guide():
        assert noms(t) <= fournis, t
        assert noms(i18n._(t)) == noms(t), t
    p = aide._parametres()
    assert p["discarded"] == "← écartée"
    assert p["key_after_batch"] == "E" and p["key_mode"] == "W"


def test_le_repli_compte_en_cellules():
    """L-54 : un glyphe pleine chasse occupe deux colonnes ; compté pour un,
    la ligne déborderait."""
    from rich.cells import cell_len
    lignes = aide._replier("漢字 " * 30, 20)
    assert all(cell_len(l) <= 20 for l in lignes)


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
# Par `touche()` : un nom de touche écrit (« Suppr ») se traduit (IE-88).
_VERS_TEXTUAL = {_touche(nom).lower(): nom for nom in _TOUCHES}
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
    # Les liaisons prioritaires de l'application répondent sur tous les
    # écrans : `F10`, et `F12` qui bascule vers la file (IE-100).
    from tui.app import IrisEncodeApp
    touches |= {b.key for b in IrisEncodeApp.BINDINGS if b.priority}
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
