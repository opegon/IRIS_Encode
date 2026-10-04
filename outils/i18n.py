"""outils/i18n.py — Extraction, mise à jour et compilation des traductions.

Outil de développement (IE-86), sans dépendance : choisi le 2026-10-04 contre
Babel. L'utilisateur n'en a jamais besoin — les `.mo` sont versionnés et
livrés dans la release (IE-111 point 4) ; Weblate régénère les siens.

    python outils/i18n.py extraire   # code → locales/iris_encode.pot
    python outils/i18n.py maj        # .pot → chaque locales/<l>/LC_MESSAGES/*.po
    python outils/i18n.py compiler   # chaque .po → son .mo
    python outils/i18n.py tout       # les trois, dans l'ordre

Les fichiers produits sont **déterministes** (pas de date dans l'en-tête du
`.pot`, entrées triées par première apparition) : `tests/test_i18n.py` vérifie
que le `.pot` et les `.mo` du dépôt sont ceux que ces commandes produiraient.
"""
from __future__ import annotations

import ast
import re
import struct
import sys
import tokenize
from dataclasses import dataclass, field
from pathlib import Path

RACINE   = Path(__file__).resolve().parent.parent
LOCALES  = RACINE / "locales"
DOMAINE  = "iris_encode"
POT      = LOCALES / f"{DOMAINE}.pot"
SOURCES  = ("core", "tui", "main.py")

# Fonction → rôle de chaque argument positionnel.
MOTS_CLES: dict[str, tuple[str, ...]] = {
    "_":         ("msgid",),
    "N_":        ("msgid",),
    "Nn_":       ("msgid", "plural"),
    "ngettext":  ("msgid", "plural"),
    "pgettext":  ("ctxt", "msgid"),
    "npgettext": ("ctxt", "msgid", "plural"),
}
MARQUE_TRADUCTEURS = "TRANSLATORS:"
_CHAMP_FORMAT = re.compile(r"(?<!\{)\{[A-Za-z_]\w*\}(?!\})")


# ─── Modèle ───────────────────────────────────────────────────────────────────

@dataclass
class Entree:
    msgid:     str
    ctxt:      str | None = None
    plural:    str | None = None
    msgstr:    list[str] = field(default_factory=lambda: [""])
    refs:      list[str] = field(default_factory=list)
    notes:     list[str] = field(default_factory=list)    # #. pour le traducteur
    drapeaux:  list[str] = field(default_factory=list)    # #, fuzzy, python-brace-format
    obsolete:  bool = False

    @property
    def cle(self) -> tuple[str | None, str]:
        return (self.ctxt, self.msgid)

    @property
    def traduite(self) -> bool:
        return all(self.msgstr) and "fuzzy" not in self.drapeaux


# ─── Extraction ───────────────────────────────────────────────────────────────

class ErreurExtraction(Exception):
    pass


def _fichiers(racine: Path) -> list[Path]:
    out: list[Path] = []
    for s in SOURCES:
        p = racine / s
        out += sorted(p.rglob("*.py")) if p.is_dir() else ([p] if p.exists() else [])
    return out


def _commentaires(source: str) -> dict[int, str]:
    """N° de ligne → texte des commentaires `# TRANSLATORS:` (un bloc peut
    s'étendre sur plusieurs lignes de commentaire consécutives)."""
    lignes: dict[int, str] = {}
    import io
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT:
            lignes[tok.start[0]] = tok.string.lstrip("#").strip()
    notes: dict[int, str] = {}
    for n, texte in lignes.items():
        if texte.startswith(MARQUE_TRADUCTEURS):
            bloc, k = [texte[len(MARQUE_TRADUCTEURS):].strip()], n + 1
            while k in lignes and not lignes[k].startswith(MARQUE_TRADUCTEURS):
                bloc.append(lignes[k]); k += 1
            notes[k - 1] = " ".join(b for b in bloc if b)
    return notes


def _deja_compose(arg: ast.expr) -> bool:
    """f-string, concaténation, `%`, ou `.format()` : la phrase est remplie
    avant d'être traduite, donc introuvable au catalogue."""
    return (isinstance(arg, (ast.JoinedStr, ast.BinOp))
            or isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute)
            and arg.func.attr == "format")


def extraire_fichier(chemin: Path, racine: Path) -> list[Entree]:
    source = chemin.read_text(encoding="utf-8")
    notes  = _commentaires(source)
    rel    = chemin.relative_to(racine).as_posix()
    out: list[Entree] = []
    for n in ast.walk(ast.parse(source, str(chemin))):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id in MOTS_CLES):
            continue
        roles = MOTS_CLES[n.func.id]
        if len(n.args) < len(roles):
            continue
        valeurs: dict[str, str] = {}
        for role, arg in zip(roles, n.args):
            if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
                if _deja_compose(arg):
                    raise ErreurExtraction(
                        f"{rel}:{n.lineno} — {n.func.id}() veut le gabarit, pas "
                        f"un texte déjà composé ({type(arg).__name__}) : "
                        f"_(\"… {{nom}}\").format(nom=…)")
                break           # variable : traduction d'un texte marqué N_()
            valeurs[role] = arg.value
        else:
            e = Entree(msgid=valeurs["msgid"], ctxt=valeurs.get("ctxt"),
                       plural=valeurs.get("plural"), refs=[f"{rel}:{n.lineno}"])
            e.msgstr = ["", ""] if e.plural is not None else [""]
            note = notes.get(n.lineno - 1)
            if note:
                e.notes.append(note)
            if _CHAMP_FORMAT.search(e.msgid + (e.plural or "")):
                e.drapeaux.append("python-brace-format")
            out.append(e)
    return out


def extraire(racine: Path = RACINE) -> list[Entree]:
    vues: dict[tuple, Entree] = {}
    for f in _fichiers(racine):
        for e in sorted(extraire_fichier(f, racine),
                        key=lambda e: int(e.refs[0].rsplit(":", 1)[1])):
            deja = vues.get(e.cle)
            if deja is None:
                vues[e.cle] = e
                continue
            if deja.plural != e.plural:
                raise ErreurExtraction(
                    f"{e.refs[0]} — « {e.msgid} » a deux pluriels différents "
                    f"(voir {deja.refs[0]})")
            deja.refs += e.refs
            deja.notes += [x for x in e.notes if x not in deja.notes]
    return list(vues.values())


# ─── Format .po ───────────────────────────────────────────────────────────────

def _echapper(s: str) -> str:
    return (s.replace("\\", "\\\\").replace('"', '\\"')
             .replace("\n", "\\n").replace("\t", "\\t"))


def _chaine(mot: str, s: str, prefixe: str = "") -> list[str]:
    """`mot "…"` ; une chaîne qui contient des retours à la ligne est coupée
    après chacun, comme le fait msgmerge (plus lisible pour le traducteur)."""
    if "\n" not in s.rstrip("\n"):
        return [f'{prefixe}{mot} "{_echapper(s)}"']
    morceaux = [m for m in re.split(r"(?<=\n)", s) if m]
    return [f'{prefixe}{mot} ""'] + [f'{prefixe}"{_echapper(m)}"' for m in morceaux]


def ecrire_po(entete: str, entrees: list[Entree]) -> str:
    lignes = ['msgid ""', 'msgstr ""']
    lignes += [f'"{_echapper(l)}\\n"' for l in entete.rstrip("\n").split("\n")]
    for e in entrees:
        p = "#~ " if e.obsolete else ""
        lignes.append("")
        if not e.obsolete:
            lignes += [f"#. {n}" for n in e.notes]
            lignes += [f"#: {r}" for r in e.refs]
            if e.drapeaux:
                lignes.append("#, " + ", ".join(e.drapeaux))
        if e.ctxt is not None:
            lignes += _chaine("msgctxt", e.ctxt, p)
        lignes += _chaine("msgid", e.msgid, p)
        if e.plural is not None:
            lignes += _chaine("msgid_plural", e.plural, p)
            for i, s in enumerate(e.msgstr):
                lignes += _chaine(f"msgstr[{i}]", s, p)
        else:
            lignes += _chaine("msgstr", e.msgstr[0], p)
    return "\n".join(lignes) + "\n"


def _desechapper(s: str) -> str:
    out, i = [], 0
    table = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            out.append(table.get(s[i + 1], s[i + 1])); i += 2
        else:
            out.append(s[i]); i += 1
    return "".join(out)


def lire_po(texte: str) -> tuple[str, list[Entree]]:
    """(en-tête, entrées). Lit les entrées obsolètes `#~`."""
    entrees: list[Entree] = []
    courant: dict = {}
    dernier: str | None = None

    def fermer():
        nonlocal courant
        if "msgid" in courant:
            n = max([int(k[7:-1]) for k in courant if k.startswith("msgstr[")] or [-1])
            msgstr = ([courant.get(f"msgstr[{i}]", "") for i in range(n + 1)]
                      if n >= 0 else [courant.get("msgstr", "")])
            entrees.append(Entree(
                msgid=courant["msgid"], ctxt=courant.get("msgctxt"),
                plural=courant.get("msgid_plural"), msgstr=msgstr,
                refs=courant.get("refs", []), notes=courant.get("notes", []),
                drapeaux=courant.get("drapeaux", []),
                obsolete=courant.get("obsolete", False)))
        courant = {}

    for brute in texte.splitlines():
        ligne = brute.strip()
        obsolete = ligne.startswith("#~")
        if obsolete:
            ligne = ligne[2:].strip()
        if not ligne:
            continue
        if ligne.startswith("#"):
            if "msgid" in courant and dernier and dernier.startswith("msgstr"):
                fermer()
            if ligne.startswith("#."):
                courant.setdefault("notes", []).append(ligne[2:].strip())
            elif ligne.startswith("#:"):
                courant.setdefault("refs", []).extend(ligne[2:].split())
            elif ligne.startswith("#,"):
                courant.setdefault("drapeaux", []).extend(
                    d.strip() for d in ligne[2:].split(",") if d.strip())
            continue
        m = re.match(r'(msgctxt|msgid_plural|msgid|msgstr(?:\[\d+\])?)\s+"(.*)"$', ligne)
        if m:
            mot = m.group(1)
            if mot in ("msgctxt", "msgid") and "msgid" in courant:
                fermer()
            courant[mot] = _desechapper(m.group(2))
            if obsolete:
                courant["obsolete"] = True
            dernier = mot
        elif ligne.startswith('"') and dernier:
            courant[dernier] += _desechapper(ligne[1:-1])
    fermer()
    entete = ""
    if entrees and entrees[0].msgid == "" and entrees[0].ctxt is None:
        entete = entrees.pop(0).msgstr[0]
    return entete, entrees


# ─── .pot et mise à jour des .po ──────────────────────────────────────────────

ENTETE_POT = """Project-Id-Version: IRIS ENCODE
Report-Msgid-Bugs-To: https://github.com/opegon/IRIS_Encode/issues
Language:
MIME-Version: 1.0
Content-Type: text/plain; charset=UTF-8
Content-Transfer-Encoding: 8bit
Plural-Forms: nplurals=2; plural=(n != 1);
"""


def produire_pot(racine: Path = RACINE) -> str:
    return ecrire_po(ENTETE_POT, extraire(racine))


def fusionner(po: str, pot: str) -> str:
    """Le .po mis à jour sur le .pot : traductions gardées, nouveaux messages
    vides, disparus gardés en obsolètes (`#~`) pour ne perdre aucun travail."""
    entete, anciennes = lire_po(po)
    _, modeles = lire_po(pot)
    par_cle = {e.cle: e for e in anciennes}
    sortie: list[Entree] = []
    for m in modeles:
        a = par_cle.pop(m.cle, None)
        if a is not None and (a.plural is None) == (m.plural is None):
            m.msgstr = a.msgstr if m.plural is None else (a.msgstr + [""] * 6)[:max(len(a.msgstr), 2)]
            if "fuzzy" in a.drapeaux:
                m.drapeaux.append("fuzzy")
        sortie.append(m)
    for a in par_cle.values():
        if any(a.msgstr):
            a.obsolete = True
            sortie.append(a)
    return ecrire_po(entete, sortie)


# ─── Compilation .mo ──────────────────────────────────────────────────────────

def compiler_mo(po: str) -> bytes:
    """Le .mo (format GNU, sans table de hachage) d'un .po. Comme `msgfmt` :
    ni messages flous, ni non traduits, ni obsolètes — `gettext` retombera sur
    l'anglais source pour eux."""
    entete, entrees = lire_po(po)
    paires: dict[bytes, bytes] = {b"": entete.encode("utf-8")}
    for e in entrees:
        if e.obsolete or not e.traduite:
            continue
        cle = e.msgid if e.plural is None else f"{e.msgid}\0{e.plural}"
        if e.ctxt is not None:
            cle = f"{e.ctxt}\x04{cle}"
        paires[cle.encode("utf-8")] = "\0".join(e.msgstr).encode("utf-8")
    cles = sorted(paires)
    n = len(cles)
    debut_textes = 7 * 4 + 16 * n
    ids, strs, offsets_ids, offsets_strs = b"", b"", [], []
    for k in cles:
        offsets_ids.append((len(k), len(ids))); ids += k + b"\0"
    for k in cles:
        v = paires[k]
        offsets_strs.append((len(v), len(strs))); strs += v + b"\0"
    table_ids  = b"".join(struct.pack("<2I", l, debut_textes + o) for l, o in offsets_ids)
    base_strs  = debut_textes + len(ids)
    table_strs = b"".join(struct.pack("<2I", l, base_strs + o) for l, o in offsets_strs)
    entete_mo  = struct.pack("<7I", 0x950412DE, 0, n, 28, 28 + 8 * n, 0, 28 + 16 * n)
    return entete_mo + table_ids + table_strs + ids + strs


def catalogues(locales: Path = LOCALES) -> list[Path]:
    return sorted(locales.glob(f"*/LC_MESSAGES/{DOMAINE}.po"))


# ─── Ligne de commande ────────────────────────────────────────────────────────

def _ecrire(chemin: Path, contenu: str | bytes) -> None:
    if isinstance(contenu, str):
        chemin.write_text(contenu, encoding="utf-8", newline="\n")
    else:
        chemin.write_bytes(contenu)
    print(f"  {chemin.relative_to(RACINE)}")


def main(argv: list[str]) -> int:
    commande = argv[1] if len(argv) > 1 else ""
    if commande not in ("extraire", "maj", "compiler", "tout"):
        print(__doc__)
        return 2
    if commande in ("extraire", "tout"):
        _ecrire(POT, produire_pot())
    if commande in ("maj", "tout"):
        pot = POT.read_text(encoding="utf-8")
        for po in catalogues():
            _ecrire(po, fusionner(po.read_text(encoding="utf-8"), pot))
    if commande in ("compiler", "tout"):
        for po in catalogues():
            _ecrire(po.with_suffix(".mo"), compiler_mo(po.read_text(encoding="utf-8")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
