"""
tests/test_wiki.py — Le lint du wiki (`wiki/`), au sens du modèle « LLM Wiki ».

Les contrôles mécaniques d'une passe de lint : liens `[[…]]` qui mènent
quelque part, pages orphelines, catalogue (`index.md`) complet, frontmatter
présent, journal (`log.md`) au format fixe. Les contrôles de fond —
contradictions, affirmations périmées — restent une relecture.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

WIKI = Path(__file__).resolve().parent.parent / "wiki"

_LIEN = re.compile(r"\[\[([^\]|#]+)(?:#([^\]|]+))?(?:\|[^\]]+)?\]\]")
_TYPES = {"index", "log", "schema", "source", "entite", "concept", "synthese"}
# Les pages de service : citées par le schéma ou l'index, pas par le contenu.
_SERVICE = {"index", "log", "SCHEMA"}
# Les pages dont le contenu vient de sources et doit dire lesquelles.
_TYPES_SOURCES = {"entite", "concept", "synthese"}


def _lire(chemin: Path) -> str:
    """Le texte sans son code, bloc ou en ligne : Obsidian n'y voit ni lien
    ni titre, et un exemple de format ne doit pas passer pour une entrée."""
    texte = chemin.read_text(encoding="utf-8")
    texte = re.sub(r"^```.*?^```", "", texte, flags=re.S | re.M)
    return re.sub(r"`[^`\n]*`", "", texte)


def _pages() -> dict[str, Path]:
    return {p.stem: p for p in WIKI.rglob("*.md")}


def _frontmatter(texte: str) -> dict[str, str] | None:
    m = re.match(r"---\n(.*?)\n---\n", texte, re.S)
    if not m:
        return None
    return dict(re.findall(r"^(\w+):\s*(.*)$", m.group(1), re.M))


def _titres(texte: str) -> set[str]:
    return {t.strip() for t in re.findall(r"^#+ (.+)$", texte, re.M)}


def test_les_noms_de_page_sont_uniques():
    """Un `[[nom]]` se résout par le nom seul, quel que soit le dossier."""
    noms = [p.stem for p in WIKI.rglob("*.md")]
    doublons = {n for n in noms if noms.count(n) > 1}
    assert not doublons, doublons


def test_chaque_lien_mene_a_une_page_et_a_une_section():
    pages = _pages()
    casses = []
    for nom, chemin in pages.items():
        for cible, titre in _LIEN.findall(_lire(chemin)):
            cible = cible.strip()
            if cible not in pages:
                casses.append(f"{nom} → [[{cible}]]")
            elif titre and titre.strip() not in _titres(
                    _lire(pages[cible])):
                casses.append(f"{nom} → [[{cible}#{titre}]]")
    assert not casses, casses


def test_aucune_page_orpheline():
    """Chaque page est citée ailleurs que dans l'index et le journal : une
    page que rien ne relie n'est jamais retrouvée en suivant le graphe."""
    pages = _pages()
    citees: set[str] = set()
    for nom, chemin in pages.items():
        if nom in _SERVICE:
            continue
        citees |= {c.strip() for c, _ in _LIEN.findall(_lire(chemin))
                   if c.strip() != nom}
    orphelines = set(pages) - citees - _SERVICE
    assert not orphelines, orphelines


def test_l_index_catalogue_toutes_les_pages():
    index = _lire(WIKI / "index.md")
    catalogue = {c.strip() for c, _ in _LIEN.findall(index)}
    absentes = set(_pages()) - catalogue - {"index"}
    assert not absentes, absentes


@pytest.mark.parametrize("chemin", sorted(
    p for p in WIKI.rglob("*.md") if "raw" not in p.relative_to(WIKI).parts),
    ids=lambda p: p.stem)
def test_frontmatter(chemin):
    fm = _frontmatter(chemin.read_text(encoding="utf-8"))
    assert fm is not None, "frontmatter YAML absent"
    assert fm.get("type") in _TYPES, fm.get("type")
    if fm["type"] != "log":
        date.fromisoformat(fm.get("maj", ""))
    if fm["type"] in _TYPES_SOURCES:
        texte = chemin.read_text(encoding="utf-8")
        assert re.search(r"^sources:\n\s+- ", texte, re.M), "sources non déclarées"


def test_le_brut_n_a_pas_de_frontmatter():
    """`raw/` garde les relevés tels quels : rien n'y est compilé."""
    for p in (WIKI / "raw").glob("*.md"):
        assert _frontmatter(p.read_text(encoding="utf-8")) is None, p.name


def test_le_journal_suit_son_format_et_sa_chronologie():
    texte = _lire(WIKI / "log.md")
    entrees = re.findall(r"^## (.+)$", texte, re.M)
    assert entrees, "journal vide"
    dates = []
    for e in entrees:
        m = re.fullmatch(r"\[(\d{4}-\d{2}-\d{2})\] (ingest|query|lint) \| .+", e)
        assert m, e
        dates.append(date.fromisoformat(m.group(1)))
    assert dates == sorted(dates), "le journal s'écrit en ajout seul"
