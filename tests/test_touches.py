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
_ANCIENNES = re.compile(
    r'"[^"]*(?:'
    r'\bEspace\s|\bEnter\s|\bBack\s|\bSh\+Tab\b|\bSpace\s'
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
