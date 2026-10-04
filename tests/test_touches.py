"""
tests/test_touches.py — Un seul rendu pour les noms de touches.

Trois notations coexistaient pour la même information : le footer disait
« Space Sélect », les modales « Espace  Sélectionner », le formulaire de profil
« Tab / Shift+Tab : champ suiv./préc. ». Le choix du glyphe importe moins que
son unicité — mais un glyphe tient en une colonne, ce qui compte sur un footer
de trois lignes.

Ces tests verrouillent la source unique et interdisent qu'une quatrième
notation réapparaisse ailleurs.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tui.common import SEP_ENTREE, SEP_TOUCHE, TOUCHES, raccourci, raccourcis, touche

RACINE = Path(__file__).resolve().parent.parent / "tui"


# ─── Le rendu ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("nom, attendu", [
    ("enter",     "↵"),
    ("backspace", "⌫"),
    ("space",     "␣"),
    ("escape",    "Esc"),
    ("shift+tab", "⇧Tab"),
    ("left",      "←"),
])
def test_touche_connue(nom, attendu):
    assert touche(nom) == attendu


def test_touche_inconnue_passe_en_majuscules():
    """Une touche de fonction ou une lettre n'a pas besoin d'entrée dédiée."""
    assert touche("f9") == "F9"
    assert touche("m") == "M"


def test_une_notation_composee_traverse_intacte():
    """« +/- » ou « Shift+↑/↓ » ne sont pas des noms de touches Textual :
    la fonction ne doit pas les défigurer."""
    assert raccourci("+/-", "Valeur") == f"+/-{SEP_TOUCHE}Valeur"


def test_espacement_commun():
    rendu = raccourcis([("enter", "Valider"), ("escape", "Annuler")])
    assert rendu == f"↵{SEP_TOUCHE}Valider{SEP_ENTREE}Esc{SEP_TOUCHE}Annuler"


def test_le_footer_lit_la_meme_table():
    """`_fmt_key` du footer est un alias de `touche`, pas une seconde table."""
    from tui.widgets.footer import _fmt_key

    for nom in TOUCHES:
        assert _fmt_key(nom) == touche(nom)


# ─── Plus aucune notation écrite à la main ────────────────────────────────────

# Les anciennes graphies, telles qu'elles apparaissaient dans les bandeaux.
# « Espace » est aussi un mot francais : il ne compte comme notation de touche
# que suivi du double blanc qui separait la touche de son libelle, sans quoi la
# colonne « Espace libre » de l'ecran des volumes serait signalee a tort.
_ANCIENNES = re.compile(
    r'"[^"]*(?:'
    r'\bEspace\s{2}|\bEnter\s|\bBack\s|\bSh\+Tab\b|\bSpace\s'
    r')[^"]*"'
)


def test_aucun_bandeau_ne_reecrit_les_touches():
    fautifs = []
    for f in sorted(RACINE.rglob("*.py")):
        if f.name == "common.py":          # la source, justement
            continue
        for i, ligne in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if "touche(" in ligne or "raccourci" in ligne:
                continue
            if _ANCIENNES.search(ligne):
                fautifs.append(f"{f.relative_to(RACINE.parent)}:{i} — {ligne.strip()[:60]}")
    assert not fautifs, "notation écrite à la main :\n" + "\n".join(fautifs)


def test_les_glyphes_tiennent_en_une_colonne():
    """L'argument du choix : un footer de trois lignes compte ses colonnes."""
    for nom in ("enter", "backspace", "space", "left", "right", "up", "down"):
        assert len(touche(nom)) == 1, f"{nom} → {touche(nom)!r}"


# ── Une touche de fonction, un seul sens (UX-07) ─────────────────────────────

# La table réservée, tranchée le 2026-09-30. F2 est « l'action principale » :
# encoder, ou ce qui en tient lieu sur un écran qui n'encode pas (joindre,
# valider un ancrage). Un écran qui a besoin d'une touche à lui prend une
# lettre, comme l'accueil pour R, J et I.
_TABLE_RESERVEE: dict[str, set[str]] = {
    "f1": {"open_dryrun", "dryrun"},
    "f2": {"open_run", "run", "encode", "coller", "valider", "encoder"},
    "f3": {"run_mux", "mux", "muxer"},
    "f4": {"open_profile_picker", "change_profile"},
    "f5": {"open_config"},
    "f6": {"open_codec", "codec"},
    "f7": {"open_bitrate", "debit"},
    "f8": {"toggle_delete"},
    "f9": {"add_track", "add_external", "donneur"},
}


def test_une_touche_de_fonction_garde_son_sens_partout():
    import importlib, inspect, pkgutil
    import tui.screens as ecrans
    fautes = []
    for m in pkgutil.iter_modules(ecrans.__path__):
        mod = importlib.import_module(f"tui.screens.{m.name}")
        for nom, cls in inspect.getmembers(mod, inspect.isclass):
            if cls.__module__ != mod.__name__:
                continue
            for b in getattr(cls, "BINDINGS", []):
                cle, action = (b.key, b.action) if not isinstance(b, tuple) else b[:2]
                for k in cle.split(","):
                    if k in _TABLE_RESERVEE and action not in _TABLE_RESERVEE[k]:
                        fautes.append(f"{nom} : {k} → {action}")
    assert not fautes, fautes


def test_les_lettres_tranchees_nont_quun_sens():
    """
    UX-12 : `M` voulait dire Mesurer sur le recalage et Muxer dans
    l'assistant ; `S` Plages ou Passer le fichier ; `A` Tout ou Forcer.
    Tranché le 2026-09-30 : chacune de ces lettres n'a plus qu'une action.
    """
    import collections, importlib, inspect, pkgutil
    import tui.screens as ecrans
    sens = collections.defaultdict(set)
    for m in pkgutil.iter_modules(ecrans.__path__):
        mod = importlib.import_module(f"tui.screens.{m.name}")
        for nom, cls in inspect.getmembers(mod, inspect.isclass):
            if cls.__module__ != mod.__name__:
                continue
            for b in getattr(cls, "BINDINGS", []):
                cle, action = (b.key, b.action) if not isinstance(b, tuple) else b[:2]
                for k in cle.split(","):
                    sens[k].add(action)
    for lettre in "msafgo":
        assert len(sens[lettre]) <= 1, (lettre, sens[lettre])


def test_aucune_touche_entre_crochets_ni_entre_apostrophes():
    """
    UX-10 : le bandeau d'accueil écrivait « [W] » et « [F4] », le recalage
    « 's' », « 'm' ». Une touche citée dans un texte passe par `touche()`.
    """
    import ast
    import re
    from pathlib import Path
    motif = re.compile(r"\[(?:[A-Z]|F\d+|</>)\]|(?<![\w'])'[a-z]'(?![\w'])")
    fautes = []
    for f in sorted(Path("tui").rglob("*.py")):
        arbre = ast.parse(f.read_text(encoding="utf-8"))
        docs = {id(n.body[0].value) for n in ast.walk(arbre)
                if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef))
                and n.body and isinstance(n.body[0], ast.Expr)}
        for n in ast.walk(arbre):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) \
                    and id(n) not in docs and motif.search(n.value):
                fautes.append(f"{f}:{n.lineno} {n.value!r}")
    assert not fautes, fautes


def test_lassistant_nomme_les_touches_selon_letape():
    """UX-11 : le pied porte le sens de l'étape, la ligne d'aide ne le redit plus."""
    from tui.screens.wizard import Etape, WizardScreen, _actions_etape
    from core.i18n import _
    # Descriptions sources, traduites au rendu : comparer au texte affiché.
    lancer = {k: _(v) for k, v in _actions_etape(WizardScreen, Etape.LANCER)}
    assert lancer["enter"] == "Lancer le recommandé"
    assert lancer["f2"] == "Encoder" and lancer["f3"] == "Muxer"
    assert _(dict(_actions_etape(WizardScreen, Etape.DECISION))["space"]) == "Garder / écarter"
    assert _(dict(_actions_etape(WizardScreen, Etape.FICHIER))["enter"]) == "Continuer"
