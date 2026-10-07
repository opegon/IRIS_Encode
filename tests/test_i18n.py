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
    """Chaque test part de l'anglais, puis rend la langue d'avant (le
    français de `conftest.py`) : la langue est globale."""
    avant = i18n.langue()
    i18n.init("en")
    yield
    i18n.init(avant)


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

def test_plus_aucun_accord_par_texte_py():
    """IE-87 puis IE-88 : les pluriels passent par `ngettext`. `core/texte.py`,
    qui codait la règle française, est retiré (L-37) et ne doit pas revenir."""
    assert not RACINE.joinpath("core", "texte.py").exists()
    fautes = [str(f.relative_to(RACINE))
              for f in [*RACINE.joinpath("core").glob("*.py"),
                        *RACINE.joinpath("tui").rglob("*.py")]
              if any(isinstance(n, ast.ImportFrom)
                     and (n.module or "").split(".")[-1] == "texte"
                     for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))))]
    assert not fautes, fautes


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


def test_une_erreur_au_pluriel_s_accorde_dans_chaque_langue(tmp_path):
    dossier = _catalogue(tmp_path, "fr", _ENTETE_FR, [outils.Entree(
        msgid="{count} part given.", plural="{count} parts given.",
        msgstr=["{count} partie donnée.", "{count} parties données."])])
    gabarit = i18n.Nn_("{count} part given.", "{count} parts given.")
    zero, deux = (i18n.ErreurAffichable(gabarit, count=n) for n in (0, 2))
    assert str(zero) == "0 parts given."                     # règle anglaise
    i18n.init("fr", dossier)
    assert zero.message() == "0 partie donnée."              # règle française
    assert deux.message() == "2 parties données."


def test_texte_erreur_traduit_ce_qui_peut_l_etre(tmp_path):
    dossier = _catalogue(tmp_path, "fr", _ENTETE_FR, [outils.Entree(
        msgid="Cannot read {path}.", msgstr=["Impossible de lire {path}."])])
    i18n.init("fr", dossier)
    e = i18n.ErreurAffichable(i18n.N_("Cannot read {path}."), path="a")
    assert isinstance(e, ValueError)          # les `except ValueError` tiennent
    assert i18n.texte_erreur(e) == "Impossible de lire a."
    assert i18n.texte_erreur(OSError("disque plein")) == "disque plein"


def test_un_module_qui_traduit_n_ecrase_pas_underscore():
    """`for _ in …` ou `a, _ = …` dans un module qui importe `_` de
    `core.i18n` remplacerait la fonction de traduction dans ce bloc : le
    prochain `_("…")` planterait, ou pire, rendrait n'importe quoi."""
    fautes = []
    for f in sorted([*RACINE.joinpath("core").rglob("*.py"),
                     *RACINE.joinpath("tui").rglob("*.py")]):
        arbre = ast.parse(f.read_text(encoding="utf-8"))
        # `from core.i18n import _` comme `from .i18n import _`.
        importe = any(isinstance(n, ast.ImportFrom)
                      and (n.module or "").split(".")[-1] == "i18n"
                      and any(a.name == "_" for a in n.names)
                      for n in ast.walk(arbre))
        if not importe:
            continue
        for n in ast.walk(arbre):
            if (isinstance(n, ast.Name) and n.id == "_" and isinstance(n.ctx, ast.Store)
                    or isinstance(n, ast.arg) and n.arg == "_"):
                fautes.append(f"{f.relative_to(RACINE)}:{n.lineno}")
    assert not fautes, fautes


_TRADUCTION = {"_", "N_", "Nn_", "ngettext", "pgettext", "npgettext"}
# Une expression régulière lit des noms de fichiers ou des réponses d'outils.
_REGEX = {"compile", "search", "match", "fullmatch", "findall", "sub", "split"}


def _sources_affichees() -> list[Path]:
    return sorted([*RACINE.joinpath("core").rglob("*.py"),
                   *RACINE.joinpath("tui").rglob("*.py")])


def test_aucun_texte_francais_en_dur_dans_tui_ni_core():
    """IE-88 : le français de l'interface vit dans le catalogue, plus dans le
    code. Un littéral accentué hors de `_()`/`N_()` est un texte oublié.
    `core/` y est soumis depuis IE-94 : ses erreurs remontent à l'écran.

    Hors champ : docstrings, CSS, journaux (`_LOG.…`), noms de minuteries
    (`name=`), noms propres. Le guide (`aide.py`) y est soumis depuis IE-89."""
    traduction = _TRADUCTION | _REGEX
    # Des données, pas l'interface : un nom de piste proposé selon la langue
    # **de la piste** (`core/muxer.py`, L-77) et un mot reconnu dans le titre
    # d'une piste (`core/scanner.py`).
    noms_propres = {"AlloCiné", "Forcés", "forcé"}
    # Lettres accentuées, sans `×` ni `÷` (U+00D7, U+00F7) : `+120 ms ×25/24`.
    accent = __import__("re").compile(r"[À-ÖØ-öø-ÿ]")
    fautes = []
    for f in _sources_affichees():
        arbre = ast.parse(f.read_text(encoding="utf-8"))
        exclus: set[int] = set()

        def exclure(noeud):
            exclus.update(id(s) for s in ast.walk(noeud))

        for n in ast.walk(arbre):
            corps = getattr(n, "body", None)
            if (isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                               ast.AsyncFunctionDef))
                    and corps and isinstance(corps[0], ast.Expr)
                    and isinstance(corps[0].value, ast.Constant)):
                exclure(corps[0])
            if isinstance(n, ast.Call):
                fn = n.func
                nom = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
                base = fn.value.id if (isinstance(fn, ast.Attribute)
                                       and isinstance(fn.value, ast.Name)) else ""
                if nom in traduction or base.lstrip("_").lower().startswith("log"):
                    exclure(n)
                for k in n.keywords:
                    if k.arg == "name":
                        exclure(k.value)
            if isinstance(n, (ast.Assign, ast.AnnAssign)):
                cibles = n.targets if isinstance(n, ast.Assign) else [n.target]
                for c in cibles:
                    if isinstance(c, ast.Name) and (
                            c.id in ("CSS", "DEFAULT_CSS")):
                        exclure(n)
        for n in ast.walk(arbre):
            if (id(n) not in exclus and isinstance(n, ast.Constant)
                    and isinstance(n.value, str) and accent.search(n.value)
                    and n.value not in noms_propres):
                fautes.append(f"{f.relative_to(RACINE)}:{n.lineno} {n.value[:50]!r}")
    assert not fautes, fautes


# Fonction d'affichage → position de l'argument qui porte le texte montré.
_AFFICHAGE: dict[str, tuple[int | None, str | None]] = {
    "notify":           (0, "message"),
    "Static":           (0, None),
    "Label":            (0, None),
    "Button":           (0, "label"),
    "Text":             (0, None),
    "add_column":       (0, "label"),
    "colonne_fixe":     (1, None),
    "Binding":          (2, "description"),
    "ErreurAffichable": (0, None),
    "_flash_status":    (0, None),
    "_set_hint":        (0, None),
}


def _invariants() -> list[str]:
    """Les termes que le glossaire déclare intraduisibles, du plus long au plus
    court (« DTS-HD MA » avant « DTS »)."""
    import csv
    with open(RACINE / "locales" / "glossaire.fr.csv", encoding="utf-8",
              newline="") as f:
        termes = [l["source"] for l in csv.DictReader(f)
                  if l["explanation"].startswith("Do not translate")]
    # Les unités restent écrites comme dans la source (wiki `localisation`).
    termes += ["kbps", "ms"]
    return sorted(termes, key=len, reverse=True)


def _textes_en_dur(code: str) -> list[tuple[int, str, str]]:
    """(ligne, fonction, texte) de chaque littéral à mots passé en dur à une
    fonction d'affichage. Les termes intraduisibles du glossaire et ce qui n'a
    pas de mot (`—`, `0:00`, `%`) ne comptent pas."""
    import re
    invariants = [re.compile(r"(?i)(?<![\w.])" + re.escape(t) + r"(?![\w])")
                  for t in _invariants()]
    # Un mot ; pas une extension de domaine (`OpenSubtitles.com`).
    mot = re.compile(r"(?<![\w.])[A-Za-zÀ-ÿ]{2,}")
    trouves = []
    for n in ast.walk(ast.parse(code)):
        if not isinstance(n, ast.Call):
            continue
        fn = n.func
        nom = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
        if nom not in _AFFICHAGE:
            continue
        pos, cle = _AFFICHAGE[nom]
        args = [n.args[pos]] if pos is not None and len(n.args) > pos else []
        args += [k.value for k in n.keywords if k.arg == cle]
        for a in args:
            if not (isinstance(a, ast.Constant) and isinstance(a.value, str)):
                continue                     # traduit, ou calculé : hors champ
            reste = a.value
            for t in invariants:
                reste = t.sub("", reste)
            if mot.search(reste):
                trouves.append((n.lineno, nom, a.value))
    return trouves


def test_aucun_texte_en_dur_aux_points_d_affichage():
    """IE-94 : le pendant anglais du test des accents. Un texte passé tel quel
    à une fonction qui l'affiche (`notify`, `Static`, `Binding`…) échappe au
    catalogue, quelle que soit sa langue."""
    fautes = [f"{f.relative_to(RACINE)}:{ligne} {nom}({texte[:50]!r})"
              for f in _sources_affichees()
              for ligne, nom, texte in _textes_en_dur(f.read_text(encoding="utf-8"))]
    assert not fautes, fautes


def test_le_garde_fou_des_points_d_affichage_mord():
    """Le garde-fou du garde-fou : un texte en dur est attrapé, un terme
    intraduisible, un texte traduit ou sans mot ne l'est pas."""
    code = ('self.notify("File saved")\n'
            'Binding("f2", "go", "Start now")\n'
            'Binding("f3", "mux", _("Mux"))\n'
            'Text("HEVC → DTS-HD MA")\n'
            'Static("—")\n'
            'colonne_fixe(t, "Codec", 8)\n'
            'Label("5.1 (kbps)")\n'
            'Label("Jonction")\n')
    assert [(l, n, t) for l, n, t in _textes_en_dur(code)] == [
        (1, "notify", "File saved"), (2, "Binding", "Start now"),
        (6, "colonne_fixe", "Codec"), (8, "Label", "Jonction")]


def _comparaisons_a_un_texte_traduit(code: str) -> list[int]:
    """Lignes où un texte traduit sert d'opérande à une comparaison."""
    def traduit(n) -> bool:
        if not isinstance(n, ast.Call):
            return False
        fn = n.func
        nom = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
        return nom in _TRADUCTION
    lignes = []
    for n in ast.walk(ast.parse(code)):
        if isinstance(n, ast.Compare) and any(
                traduit(o) for o in (n.left, *n.comparators)):
            lignes.append(n.lineno)
        elif (isinstance(n, ast.Call)
              and getattr(n.func, "attr", "") in ("startswith", "endswith")
              and (traduit(n.func.value) or any(traduit(a) for a in n.args))):
            lignes.append(n.lineno)
    return lignes


def test_aucune_decision_ne_depend_d_un_texte_traduit():
    """L-23, L-43 en règle générale (IE-94) : la couleur de la fiche se
    décidait sur « incertaine », celle de la colonne HD audio sur « oui ».
    Traduits, les tests ne répondaient plus. On compare des valeurs, jamais
    ce qu'on affiche."""
    fautes = [f"{f.relative_to(RACINE)}:{l}" for f in _sources_affichees()
              for l in _comparaisons_a_un_texte_traduit(
                  f.read_text(encoding="utf-8"))]
    assert not fautes, fautes
    assert _comparaisons_a_un_texte_traduit(
        'if x == _("yes"): pass\n'
        'ok = "a" in ngettext("a", "b", n)\n'
        'f = t.startswith(_("uncertain"))\n'
        'g = _(t).upper()\n') == [1, 2, 3]


def test_une_erreur_brute_se_montre_telle_quelle():
    """Le message d'un service : ni catalogue, ni `.format` (ses accolades
    éventuelles ne cassent rien)."""
    e = i18n.ErreurAffichable.brute("Quota {exceeded}")
    assert str(e) == "Quota {exceeded}"
    assert i18n.texte_erreur(e) == "Quota {exceeded}"


def test_la_console_accepte_la_lettre_de_sa_langue_et_y(monkeypatch):
    """L-29 : « (o/N) » testait `answer == "o"` en dur. La lettre vient du
    catalogue avec l'invite, et « y » est toujours compris."""
    from core import preflight
    i18n.init("fr")                                   # le vrai catalogue livré
    invites = []
    for tape, attendu in (("o", True), ("y", True), ("n", False), ("", False)):
        monkeypatch.setattr(preflight, "_ask",
                            lambda p, t=tape: invites.append(p) or t)
        assert preflight._oui_non("Mettre à jour ces outils ?") is attendu
    assert invites[0] == "  Mettre à jour ces outils ? (o/N) : "     # le français d'avant
    i18n.init("en")
    monkeypatch.setattr(preflight, "_ask", lambda p: invites.append(p) or "y")
    assert preflight._oui_non("Update these tools?")
    assert invites[-1] == "  Update these tools? (y/N): "


def test_un_module_importe_ce_qu_il_appelle():
    """Pendant l'extraction (IE-88), un `touche(...)` ajouté sans son import
    ne s'est vu qu'en exécutant ce chemin-là : un `NameError` caché. Les
    fonctions de traduction et d'affichage appelées doivent être importées
    ou définies dans le module."""
    noms = {"_", "N_", "Nn_", "ngettext", "pgettext", "npgettext",
            "texte_erreur", "touche", "texte_style", "raccourcis", "colonne_fixe",
            "largeur_entete", "libelle_ecartee", "libelle_copie"}
    fautes = []
    for f in sorted([*RACINE.joinpath("core").rglob("*.py"),
                     *RACINE.joinpath("tui").rglob("*.py")]):
        arbre = ast.parse(f.read_text(encoding="utf-8"))
        connus = set()
        for n in ast.walk(arbre):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                connus |= {(a.asname or a.name).split(".")[0] for a in n.names}
            elif isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                connus.add(n.name)
            elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                connus.add(n.id)
        appeles = {n.func.id for n in ast.walk(arbre)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                   and n.func.id in noms}
        fautes += [f"{f.relative_to(RACINE)} : {nom}" for nom in appeles - connus]
    assert not fautes, fautes
