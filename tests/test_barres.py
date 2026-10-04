"""
tests/test_barres.py — Une seule forme de barre d'état (UX-14).

Trois séparateurs coexistaient : « · » sur l'accueil et l'aperçu, « ── » sur
le recalage, le mux et l'encodage, des blancs doublés sur les pistes. Toute
barre passe par `barre_etat()` : « Titre — élément · élément ».
"""
from __future__ import annotations

import ast
from pathlib import Path

from tui.common import barre_etat


def test_forme():
    assert barre_etat("Mux", "film.mkv", "2 pistes") == " Mux — film.mkv  ·  2 pistes"
    assert barre_etat("", "film.mkv", "", "2 pistes") == " film.mkv  ·  2 pistes"
    assert barre_etat("Aperçu") == " Aperçu"


def test_aucun_ancien_separateur_dans_les_textes_affiches():
    fautes = []
    for f in sorted(Path("tui").rglob("*.py")):
        arbre = ast.parse(f.read_text(encoding="utf-8"))
        docs = {id(n.body[0].value) for n in ast.walk(arbre)
                if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef))
                and n.body and isinstance(n.body[0], ast.Expr)}
        for n in ast.walk(arbre):
            if id(n) in docs:
                continue
            if isinstance(n, ast.Constant) and isinstance(n.value, str) \
                    and " ── " in n.value:
                fautes.append(f"{f}:{n.lineno} {n.value!r}")
    assert not fautes, fautes


# ── Accords (UX-15) ───────────────────────────────────────────────────────────

def test_accords():
    """Les cas d'UX-15, par `ngettext` et le catalogue français depuis que
    `core/texte.py` est retiré (IE-88, L-37) : singulier jusqu'à 1."""
    from core.i18n import ngettext

    def n(sing, plur, k, **kw):
        return ngettext(sing, plur, k).format(count=k, **kw)

    assert n("{count} file", "{count} files", 0) == "0 fichier"
    assert n("{count} added track", "{count} added tracks", 1) == "1 piste greffée"
    assert n("{count} added track", "{count} added tracks", 3) == "3 pistes greffées"
    assert n("{count} audio track", "{count} audio tracks", 2) == "2 pistes audio"
    assert ngettext("{done}/{total} done", "{done}/{total} done", 1).format(
        done=1, total=1) == "1/1 terminé"
    assert ngettext("{done}/{total} done", "{done}/{total} done", 4).format(
        done=4, total=4) == "4/4 terminés"


def test_plus_de_marque_de_pluriel_entre_parentheses():
    import ast
    import re
    motif = re.compile(r"\w\(s\)")
    fautes = []
    for f in sorted([*Path("tui").rglob("*.py"), *Path("core").rglob("*.py")]):
        arbre = ast.parse(f.read_text(encoding="utf-8"))
        docs = {id(n.body[0].value) for n in ast.walk(arbre)
                if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef))
                and n.body and isinstance(n.body[0], ast.Expr)}
        for n in ast.walk(arbre):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) \
                    and id(n) not in docs and motif.search(n.value):
                fautes.append(f"{f}:{n.lineno} {n.value!r}")
    assert not fautes, fautes


# ── Une donnée, une forme (UX-21) ─────────────────────────────────────────────

def test_un_codec_un_nom_quel_que_soit_loutil():
    from tui.common import nom_codec
    assert nom_codec("SubRip/SRT") == nom_codec("subrip") == "subrip"
    assert nom_codec("AC-3") == "ac3" and nom_codec("E-AC-3") == "eac3"
    # ffprobe 8.1 ne lit pas un WebVTT muxé par mkvmerge 102 : « unknown »
    assert nom_codec("unknown") == nom_codec("") == "?"


def test_langue_inconnue():
    from tui.common import langue_affichee
    assert langue_affichee("") == "?" and langue_affichee("fre") == "fre"


def test_plus_de_signe_multiplie_dans_une_resolution():
    import ast
    import re
    motif = re.compile(r"\}×\{")
    for f in [*Path("tui").rglob("*.py"), *Path("core").rglob("*.py")]:
        assert not motif.search(f.read_text(encoding="utf-8")), f
