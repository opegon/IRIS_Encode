"""core/meta.py — Recherche métadonnées film/série (IMDB + AlloCiné)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ─── Nettoyage nom de fichier ─────────────────────────────────────────────────

_TAGS = re.compile(
    r"""(?ix)
    \b(
      \d{3,4}p | 4k | uhd | hdr10?\+ | hdr | dv | dolby\.?vision |
      hevc | h\.?26[45] | x26[45] | av1 |
      blu[\-\.]?ray | bdrip | web[\-\.]?dl | webrip | dvdrip | remux |
      proper | repack | multi | extended | theatrical | unrated |
      french | english | vf | vfq | vostfr | trueHD | dts[\-\.]?hd |
      dts | aac | ac3 | atmos | \d{3,4}kbps
    )\b
""",
)
_BRACKETS   = re.compile(r"[\[({].*?[\])}]")
_SEPARATORS = re.compile(r"[._\-]+")
_SPACES     = re.compile(r"\s{2,}")
_YEAR_RE    = re.compile(r"\b(19|20)\d{2}\b")
_EPISODE_RE = re.compile(r"\bS\d{1,2}E\d{1,2}\b", re.IGNORECASE)


def parse_title(path: Path) -> tuple[str, Optional[int]]:
    """Retourne (titre nettoyé, année détectée ou None) depuis le nom de fichier."""
    name = path.stem

    year: Optional[int] = None
    m = _YEAR_RE.search(name)
    if m:
        year = int(m.group())
        name = name[: m.start()]

    m2 = _EPISODE_RE.search(name)
    if m2:
        name = name[: m2.start()]

    name = _BRACKETS.sub(" ", name)
    name = _TAGS.sub(" ", name)
    name = _SEPARATORS.sub(" ", name)
    name = _SPACES.sub(" ", name).strip()
    return name, year


# ─── Données retournées ───────────────────────────────────────────────────────

@dataclass
class MovieMeta:
    source:     str
    title:      str
    year:       Optional[int]
    kind:       str              # "Film" | "Série" | "Téléfilm" | …
    rating:     Optional[float]
    rating_max: float            # 10.0 IMDB, 5.0 AlloCiné
    genres:     list[str]        = field(default_factory=list)
    directors:  list[str]        = field(default_factory=list)
    cast:       list[str]        = field(default_factory=list)
    synopsis:   str              = ""
    url:        str              = ""


# ─── IMDB via scraping JSON-LD ───────────────────────────────────────────────

def fetch_imdb(title: str, year: Optional[int] = None) -> MovieMeta:
    """Scrape IMDB via le JSON-LD embarqué dans chaque page titre."""
    import json
    import requests
    from bs4 import BeautifulSoup
    from urllib.parse import quote

    # 1. Recherche
    search_url = f"https://www.imdb.com/find/?q={quote(title)}&s=tt"
    r = requests.get(search_url, headers=_HEADERS, timeout=12)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # Premier lien /title/ttXXX/
    title_url: str | None = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/title/tt" in href:
            path = href.split("?")[0].rstrip("/")
            title_url = "https://www.imdb.com" + path if href.startswith("/") else href
            break
    if not title_url:
        raise RuntimeError(f"Aucun résultat IMDB pour « {title} »")

    # 2. Page titre — extraction du JSON-LD
    r2 = requests.get(title_url, headers=_HEADERS, timeout=12)
    r2.raise_for_status()
    soup2 = BeautifulSoup(r2.text, "html.parser")

    ld_tag = soup2.find("script", {"type": "application/ld+json"})
    if not ld_tag:
        raise RuntimeError("Impossible de lire les données IMDB (JSON-LD absent)")
    data = json.loads(ld_tag.string)

    kind_map = {
        "Movie":       "Film",
        "TVMovie":     "Téléfilm",
        "TVSeries":    "Série",
        "TVMiniSeries":"Mini-série",
        "Short":       "Court-métrage",
    }
    kind = kind_map.get(data.get("@type", "Movie"), "Film")

    # Réalisateurs
    raw_dir = data.get("director", [])
    if isinstance(raw_dir, dict):
        raw_dir = [raw_dir]
    directors = [d.get("name", "") for d in raw_dir[:3] if d.get("name")]

    # Casting
    raw_act = data.get("actor", [])
    if isinstance(raw_act, dict):
        raw_act = [raw_act]
    cast = [a.get("name", "") for a in raw_act[:8] if a.get("name")]

    # Genres
    genres = data.get("genre", [])[:5]
    if isinstance(genres, str):
        genres = [genres]

    # Note
    rating: Optional[float] = None
    agg = data.get("aggregateRating", {})
    if agg:
        try:
            rating = float(agg.get("ratingValue", 0)) or None
        except (ValueError, TypeError):
            pass

    # Année
    year_out: Optional[int] = None
    date_str = data.get("datePublished", "")
    m = _YEAR_RE.search(date_str)
    if m:
        year_out = int(m.group())

    synopsis = data.get("description", "")

    return MovieMeta(
        source     = "imdb",
        title      = data.get("name", title),
        year       = year_out or year,
        kind       = kind,
        rating     = rating,
        rating_max = 10.0,
        genres     = genres,
        directors  = directors,
        cast       = cast,
        synopsis   = synopsis,
        url        = title_url,
    )


# ─── AlloCiné via scraping ────────────────────────────────────────────────────

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_allocine(title: str, year: Optional[int] = None) -> MovieMeta:
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        raise RuntimeError("beautifulsoup4 non installé — pip install beautifulsoup4")

    from urllib.parse import quote

    # 1. Recherche
    search_url = f"https://www.allocine.fr/rechercher/1/?q={quote(title)}"
    r = requests.get(search_url, headers=_HEADERS, timeout=12)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # Premier résultat film ou série
    link = soup.select_one("a.meta-title-link")
    if not link:
        for a in soup.find_all("a", href=True):
            h = a["href"]
            if ("/film/fichefilm" in h or "/series/ficheserie" in h):
                link = a
                break
    if not link:
        raise RuntimeError(f"Aucun résultat AlloCiné pour « {title} »")

    href = link["href"]
    if href.startswith("/"):
        href = "https://www.allocine.fr" + href
    is_serie = "/series/" in href

    # 2. Page fiche
    r2 = requests.get(href, headers=_HEADERS, timeout=12)
    r2.raise_for_status()
    soup2 = BeautifulSoup(r2.text, "html.parser")

    def _text(selector: str) -> str:
        el = soup2.select_one(selector)
        return el.get_text(strip=True) if el else ""

    def _texts(selector: str, limit: int = 8) -> list[str]:
        return [el.get_text(strip=True) for el in soup2.select(selector)[:limit]]

    # Titre
    title_out = (_text("h1.title") or _text("[itemprop='name']") or
                 _text(".titlebar-title") or title)

    # Année
    year_out: Optional[int] = None
    for sel in ("time[itemprop='startDate']", ".meta-body-item time",
                "[itemprop='datePublished']"):
        raw = _text(sel)
        m = _YEAR_RE.search(raw)
        if m:
            year_out = int(m.group())
            break

    # Note spectateurs (plus représentative que la presse)
    rating: Optional[float] = None
    for sel in (".rating-item .stareval-note", "[itemprop='ratingValue']",
                ".rating-mdl .stareval-note"):
        raw = _text(sel)
        if raw:
            try:
                rating = float(raw.replace(",", "."))
                break
            except ValueError:
                continue

    # Genres
    genres: list[str] = []
    for sel in (".meta-body-item.meta-body-info .dark-grey",
                "[itemprop='genre']", ".genre"):
        genres = [t for t in _texts(sel, 5) if t and len(t) < 30]
        if genres:
            break

    # Réalisateurs
    directors: list[str] = []
    for sel in ("[itemprop='director'] [itemprop='name']",
                ".meta-body-direction .dark-grey",
                ".meta-body-direction a"):
        directors = [t for t in _texts(sel, 3) if t]
        if directors:
            break

    # Casting
    cast: list[str] = []
    for sel in ("[itemprop='actor'] [itemprop='name']",
                ".casting-card-name", ".cast-list a"):
        cast = [t for t in _texts(sel, 8) if t and len(t) < 40]
        if cast:
            break

    # Synopsis
    synopsis = ""
    for sel in ("[itemprop='description']", ".synopsis-container .content-txt",
                ".synopsis .content-txt", ".blk-synopsis"):
        synopsis = _text(sel)
        if synopsis:
            break

    return MovieMeta(
        source     = "allocine",
        title      = title_out,
        year       = year_out or year,
        kind       = "Série" if is_serie else "Film",
        rating     = rating,
        rating_max = 5.0,
        genres     = genres,
        directors  = directors,
        cast       = cast,
        synopsis   = synopsis,
        url        = href,
    )
