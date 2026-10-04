"""
tests/test_i18n.py — Le socle de la traduction (IE-86).

`core/i18n.py` (gettext, anglais source, repli), l'outillage maison
`outils/i18n.py` (extraction, mise à jour, compilation), les catalogues
versionnés (IE-111 point 4 : `.mo` dans le dépôt, donc forcément à jour), et
les règles d'écriture qu'un test peut garder.
"""
from __future__ import annotations

import ast
import gettext
import sys
from pathlib import Path

import pytest

from core import i18n

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "outils"))
import i18n as outils                                    # noqa: E402  outils/i18n.py

FR_PO = RACINE / "locales" / "fr" / "LC_MESSAGES" / "iris_encode.po"


@pytest.fixture(autouse=True)
def langue_source():
    """Chaque test part de l'anglais et y revient : la langue est globale."""
    i18n.init("en")
    yield
    i18n.init("en")


def _catalogue(tmp_path: Path, langue: str, entete: str, entrees) -> Path:
    dossier = tmp_path / langue / "LC_MESSAGES"
    dossier.mkdir(parents=True)
    po = outils.ecrire_po(entete, entrees)
    (dossier / "iris_encode.mo").write_bytes(outils.compiler_mo(po))
    return tmp_path


_ENTETE_FR = ("Language: fr\nContent-Type: text/plain; charset=UTF-8\n"
              "Plural-Forms: nplurals=2; plural=(n > 1);\n")


# ─── Chargement et repli ──────────────────────────────────────────────────────

def test_sans_catalogue_le_texte_source_anglais_s_affiche():
    assert i18n.init("de") == "en"
    assert i18n._("Back") == "Back"
    assert i18n.ngettext("{count} file", "{count} files", 0) == "{count} files"
    assert i18n.ngettext("{count} file", "{count} files", 1) == "{count} file"


def test_langue_vide_ou_source_reste_en_anglais():
    assert i18n.init("") == "en"
    assert i18n.init(None) == "en"
    assert i18n.init("en_US") == "en"


def test_un_catalogue_traduit_avec_contexte_et_pluriel_francais(tmp_path):
    E = outils.Entree
    dossier = _catalogue(tmp_path, "fr", _ENTETE_FR, [
        E(msgid="Back", msgstr=["Retour"]),
        E(msgid="Source", ctxt="track", msgstr=["Origine"]),
        E(msgid="{count} file", plural="{count} files",
          msgstr=["{count} fichier", "{count} fichiers"]),
        E(msgid="Untranslated", msgstr=[""]),
        E(msgid="Fuzzy", msgstr=["Approximatif"], drapeaux=["fuzzy"]),
    ])
    assert i18n.init("fr", dossier) == "fr"
    assert i18n._("Back") == "Retour"
    assert i18n.pgettext("track", "Source") == "Origine"
    assert i18n._("Source") == "Source"                       # autre contexte
    # Règle française : 0 et 1 au singulier, contrairement à l'anglais.
    assert i18n.ngettext("{count} file", "{count} files", 0) == "{count} fichier"
    assert i18n.ngettext("{count} file", "{count} files", 2) == "{count} fichiers"
    # Non traduit ou flou : jamais une chaîne vide, l'anglais source.
    assert i18n._("Untranslated") == "Untranslated"
    assert i18n._("Fuzzy") == "Fuzzy"


def test_une_variante_regionale_retombe_sur_la_langue(tmp_path):
    dossier = _catalogue(tmp_path, "fr", _ENTETE_FR,
                         [outils.Entree(msgid="Back", msgstr=["Retour"])])
    i18n.init("fr_CA", dossier)
    assert i18n._("Back") == "Retour"


def test_la_liste_suit_la_langue():
    assert i18n.liste([]) == ""
    assert i18n.liste(["a"]) == "a"
    assert i18n.liste(["a", "b", "c"]) == "a, b and c"
    i18n.init("fr")                                   # le vrai catalogue livré
    assert i18n.liste(["a", "b", "c"]) == "a, b et c"


def test_lerreur_affichable_journal_en_anglais_ecran_traduit(tmp_path):
    dossier = _catalogue(tmp_path, "fr", _ENTETE_FR, [outils.Entree(
        msgid="Cannot read {path}.", msgstr=["Impossible de lire {path}."])])
    e = i18n.ErreurAffichable(i18n.N_("Cannot read {path}."), path="a.mkv")
    i18n.init("fr", dossier)
    assert str(e) == "Cannot read a.mkv."                     # le journal
    assert e.message() == "Impossible de lire a.mkv."          # l'écran


# ─── Outillage ────────────────────────────────────────────────────────────────

def test_le_po_relu_est_le_po_ecrit():
    E = outils.Entree
    entrees = [
        E(msgid="Back", msgstr=["Retour"], refs=["tui/a.py:3"], notes=["n"]),
        E(msgid='Say "hi"\\now', ctxt="c", msgstr=['Dis "salut"']),
        E(msgid="Two\nlines\n", msgstr=["Deux\nlignes\n"]),
        E(msgid="{n} file", plural="{n} files", msgstr=["{n} f", "{n} fs"],
          drapeaux=["python-brace-format"]),
        E(msgid="Gone", msgstr=["Parti"], obsolete=True),
    ]
    texte = outils.ecrire_po(_ENTETE_FR, entrees)
    entete, relues = outils.lire_po(texte)
    assert entete == _ENTETE_FR
    assert [(e.cle, e.plural, e.msgstr, e.obsolete) for e in relues] == \
           [(e.cle, e.plural, e.msgstr, e.obsolete) for e in entrees]
    assert outils.ecrire_po(entete, relues) == texte


def test_la_fusion_garde_les_traductions_et_les_disparus():
    E = outils.Entree
    po  = outils.ecrire_po(_ENTETE_FR, [E(msgid="Back", msgstr=["Retour"]),
                                       E(msgid="Old", msgstr=["Vieux"])])
    pot = outils.ecrire_po("", [E(msgid="Back"), E(msgid="New")])
    entete, sortie = outils.lire_po(outils.fusionner(po, pot))
    assert entete == _ENTETE_FR                      # l'en-tête du .po reste
    par = {e.msgid: e for e in sortie}
    assert par["Back"].msgstr == ["Retour"]
    assert par["New"].msgstr == [""]
    assert par["Old"].obsolete and par["Old"].msgstr == ["Vieux"]


def test_lextraction_lit_le_contexte_le_pluriel_et_la_note(tmp_path):
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "m.py").write_text(
        "from core.i18n import _, ngettext, pgettext, N_\n"
        "TABLE = (N_('Start'),)\n"
        "# TRANSLATORS: column header,\n"
        "# 8 characters at most.\n"
        "x = pgettext('track', 'Source')\n"
        "y = ngettext('{count} file', '{count} files', 2)\n"
        "z = _(TABLE[0])\n",
        encoding="utf-8")
    par = {e.cle: e for e in outils.extraire(tmp_path)}
    assert set(par) == {(None, "Start"), ("track", "Source"),
                        (None, "{count} file")}
    assert par[("track", "Source")].notes == ["column header, 8 characters at most."]
    assert par[(None, "{count} file")].plural == "{count} files"
    assert "python-brace-format" in par[(None, "{count} file")].drapeaux


def test_lextraction_refuse_un_texte_deja_formate(tmp_path):
    """`_(f"…")` traduirait la phrase une fois remplie : introuvable au
    catalogue. Le gabarit passe à `_()`, les valeurs à `.format()`."""
    (tmp_path / "tui").mkdir()
    (tmp_path / "tui" / "m.py").write_text(
        "from core.i18n import _\nn = 3\nx = _(f'{n} files')\n", encoding="utf-8")
    with pytest.raises(outils.ErreurExtraction):
        outils.extraire(tmp_path)


# ─── Catalogues du dépôt ──────────────────────────────────────────────────────

def test_le_pot_du_depot_est_a_jour():
    """`python outils/i18n.py extraire` après tout texte ajouté ou modifié."""
    assert outils.POT.read_text(encoding="utf-8") == outils.produire_pot()


def test_chaque_mo_du_depot_est_celui_de_son_po():
    """IE-111 point 4 : les .mo sont livrés tels quels, donc à jour —
    `python outils/i18n.py compiler`."""
    pos = outils.catalogues()
    assert FR_PO in pos
    for po in pos:
        assert po.with_suffix(".mo").read_bytes() == \
            outils.compiler_mo(po.read_text(encoding="utf-8")), po


def test_chaque_po_couvre_le_pot_avec_les_memes_champs():
    """Un message du .pot absent d'un .po, ou dont la traduction perd ou
    invente un `{champ}`, casserait l'affichage (`KeyError` au `.format`)."""
    import re
    champ = re.compile(r"\{(\w+)\}")
    _, modeles = outils.lire_po(outils.POT.read_text(encoding="utf-8"))
    for po in outils.catalogues():
        _, entrees = outils.lire_po(po.read_text(encoding="utf-8"))
        par = {e.cle: e for e in entrees if not e.obsolete}
        for m in modeles:
            assert m.cle in par, (po, m.cle)
            attendus = set(champ.findall(m.msgid + (m.plural or "")))
            for s in par[m.cle].msgstr:
                if s:
                    assert set(champ.findall(s)) <= attendus, (po, m.cle, s)


def test_le_mo_francais_se_lit_comme_un_mo_de_reference():
    mo = gettext.GNUTranslations(open(FR_PO.with_suffix(".mo"), "rb"))
    assert mo.info()["language"] == "fr"
    assert mo.plural(0) == 0 and mo.plural(2) == 1


def test_aucun_appel_de_traduction_ne_recoit_un_texte_formate():
    """Règle d'écriture d'IE-111 : jamais `_(f"…")`, `_("…" % x)`,
    `_("…".format())` — le code entier passe l'extraction."""
    outils.extraire(RACINE)        # lève ErreurExtraction sinon


# ─── Le helper d'affichage ────────────────────────────────────────────────────

def test_texte_style_garde_la_phrase_entiere():
    from tui.common import texte_style
    t = texte_style("Press {key} to join {{now}}.", key=("F2", "bold yellow"))
    assert t.plain == "Press F2 to join {now}."
    assert [(s.start, s.end, str(s.style)) for s in t.spans] == [(6, 8, "bold yellow")]
    # Le traducteur déplace le champ : le style suit.
    t = texte_style("{key} : jonction", key=("F2", "bold"))
    assert t.plain == "F2 : jonction" and t.spans[0].start == 0


# ─── Glossaire (IE-85) ────────────────────────────────────────────────────────

def test_le_glossaire_est_coherent():
    """`locales/glossaire.fr.csv`, importable comme glossaire Weblate : un
    terme anglais = une traduction, et un terme à ne pas traduire reste
    identique."""
    import csv
    chemin = RACINE / "locales" / "glossaire.fr.csv"
    with open(chemin, encoding="utf-8", newline="") as f:
        lignes = list(csv.DictReader(f))
    assert lignes and set(lignes[0]) == {"source", "target", "explanation"}
    sources = [l["source"] for l in lignes]
    assert len(sources) == len(set(sources)), "terme en double"
    for l in lignes:
        assert l["source"].strip() and l["target"].strip(), l
        if l["explanation"].startswith("Do not translate"):
            assert l["target"] == l["source"], l
    # Les arbitrages du 2026-10-04 (wiki `localisation`).
    par = {l["source"]: l["target"] for l in lignes}
    assert par["SKIP"] == "SKIP" and par["lossless"] == "lossless"
    assert par["Dry run"] == "Aperçu" and par["Guided"] == "Assistant"
