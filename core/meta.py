"""core/meta.py — Recherche métadonnées film/série (IMDB + AlloCiné)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ─── Nettoyage nom de fichier ─────────────────────────────────────────────────

# Marqueurs qui indiquent la fin du titre — on tronque au premier trouvé
_CUT_RE = re.compile(
    r"""(?ix)
    [\[\(]?                              # bracket optionnel avant
    \b(
      \d{3,4}p | 4k | uhd |             # résolution
      (19|20)\d{2} |                     # année
      S\d{1,2}E\d{1,2} |                # épisode série
      blu[\-\.]?ray | bdrip |            # source
      web[\-\.]?dl | webrip | dvdrip |
      hdtv | remux | proper | repack |
      extended | theatrical | unrated
    )\b
""",
)
_SEPARATORS = re.compile(r"[._\-]+")
_SPACES     = re.compile(r"\s{2,}")
_YEAR_RE    = re.compile(r"\b(19|20)\d{2}\b")


def parse_title(path: Path) -> tuple[str, Optional[int]]:
    """Tronque au premier marqueur de format, retourne (titre, année)."""
    name = path.stem

    # Extraire l'année depuis le nom complet avant de couper
    year: Optional[int] = None
    m = _YEAR_RE.search(name)
    if m:
        year = int(m.group())

    # Tronquer au premier marqueur (résolution, année, source…)
    m_cut = _CUT_RE.search(name)
    if m_cut:
        name = name[: m_cut.start()]

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


# ─── IMDB : OMDb API (clé config) + suggestions API (fallback) ───────────────

def fetch_imdb(title: str, year: Optional[int] = None,
               omdb_key: str = "") -> MovieMeta:
    import json, requests
    from urllib.parse import quote

    if omdb_key:
        return _fetch_imdb_omdb(title, year, omdb_key)
    return _fetch_imdb_suggestions(title, year)


def _fetch_imdb_omdb(title: str, year: Optional[int], key: str) -> MovieMeta:
    """Données complètes via OMDb API (nécessite clé gratuite sur omdbapi.com)."""
    import requests
    from urllib.parse import quote

    params = f"t={quote(title)}&apikey={key}&type=movie"
    if year:
        params += f"&y={year}"
    r = requests.get(f"http://www.omdbapi.com/?{params}", headers=_HEADERS, timeout=12)
    r.raise_for_status()
    d = r.json()
    if d.get("Response") == "False":
        raise RuntimeError(f"OMDb : {d.get('Error', 'résultat introuvable')}")

    kind_map = {"movie": "Film", "series": "Série", "episode": "Épisode"}
    kind = kind_map.get(d.get("Type", "movie"), "Film")

    try:
        rating = float(d.get("imdbRating", "N/A").replace(",", "."))
    except ValueError:
        rating = None

    year_out: Optional[int] = None
    m = _YEAR_RE.search(d.get("Year", ""))
    if m:
        year_out = int(m.group())

    genres    = [g.strip() for g in d.get("Genre", "").split(",") if g.strip()][:5]
    directors = [g.strip() for g in d.get("Director", "").split(",") if g.strip()][:3]
    cast      = [g.strip() for g in d.get("Actors", "").split(",") if g.strip()][:8]
    imdb_id   = d.get("imdbID", "")

    return MovieMeta(
        source     = "imdb",
        title      = d.get("Title", title),
        year       = year_out or year,
        kind       = kind,
        rating     = rating,
        rating_max = 10.0,
        genres     = genres,
        directors  = directors,
        cast       = cast,
        synopsis   = d.get("Plot", ""),
        url        = f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else "",
    )


def _fetch_imdb_suggestions(title: str, year: Optional[int]) -> MovieMeta:
    """Données partielles via l'API suggestions IMDB (sans clé, sans scraping)."""
    import json, requests, re as _re
    from urllib.parse import quote

    query = _re.sub(r"\s+", "_", title.lower())
    url   = f"https://v2.sg.media-imdb.com/suggests/t/{quote(query)}.json"
    r     = requests.get(url, headers=_HEADERS, timeout=12)
    r.raise_for_status()

    # Réponse JSONP : imdb$xxx(data)
    m = _re.search(r"\((.+)\)$", r.text, _re.DOTALL)
    if not m:
        raise RuntimeError("Réponse IMDB inattendue")
    results = json.loads(m.group(1)).get("d", [])

    best = None
    for res in results:
        if res.get("qid") not in ("movie", "tvSeries", "tvMiniSeries", "tvMovie"):
            continue
        if best is None:
            best = res
        if year and res.get("y") == year:
            best = res
            break
    if not best:
        raise RuntimeError(f"Aucun résultat IMDB pour « {title} »")

    kind_map = {"movie": "Film", "tvSeries": "Série",
                "tvMiniSeries": "Mini-série", "tvMovie": "Téléfilm"}
    kind  = kind_map.get(best.get("qid", "movie"), "Film")
    stars = [s.strip() for s in best.get("s", "").split(",") if s.strip()]
    imdb_id = best.get("id", "")

    return MovieMeta(
        source     = "imdb",
        title      = best.get("l", title),
        year       = best.get("y") or year,
        kind       = kind,
        rating     = None,
        rating_max = 10.0,
        genres     = [],
        directors  = [],
        cast       = stars,
        synopsis   = "Note et synopsis disponibles avec une clé OMDb (omdbapi.com — gratuit).",
        url        = f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else "",
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
    """Scrape AlloCiné via l'autocomplete JSON + JSON-LD de la fiche."""
    import json
    import requests
    from bs4 import BeautifulSoup
    from urllib.parse import quote

    # 1. Autocomplete → entity_id + entity_type
    ac_url = f"https://www.allocine.fr/_/autocomplete/{quote(title)}"
    r = requests.get(ac_url, headers=_HEADERS, timeout=12)
    r.raise_for_status()
    results = r.json().get("results", [])

    # Préférer le résultat dont le label correspond le mieux (et l'année si dispo)
    best = None
    for res in results[:8]:
        if res.get("entity_type") not in ("movie", "tvseries"):
            continue
        if best is None:
            best = res
        if year and str(year) in res.get("label", ""):
            best = res
            break
    if best is None:
        raise RuntimeError(f"Aucun résultat AlloCiné pour « {title} »")

    entity_id   = best["entity_id"]
    is_serie    = best["entity_type"] == "tvseries"
    if is_serie:
        fiche_url = f"https://www.allocine.fr/series/ficheserie_gen_cserie={entity_id}.html"
    else:
        fiche_url = f"https://www.allocine.fr/film/fichefilm_gen_cfilm={entity_id}.html"

    # 2. Fiche — JSON-LD
    r2 = requests.get(fiche_url, headers=_HEADERS, timeout=12)
    r2.raise_for_status()
    soup = BeautifulSoup(r2.text, "html.parser")

    ld_tag = soup.find("script", {"type": "application/ld+json"})
    if not ld_tag:
        raise RuntimeError("Impossible de lire les données AlloCiné (JSON-LD absent)")
    data = json.loads(ld_tag.string)

    # Réalisateurs
    raw_dir = data.get("director", [])
    if isinstance(raw_dir, dict):
        raw_dir = [raw_dir]
    directors = [d.get("name", "") for d in raw_dir[:3] if d.get("name")]

    # Casting — JSON-LD d'abord, sinon fallback HTML (.meta-body-actor)
    raw_act = data.get("actor", [])
    if isinstance(raw_act, dict):
        raw_act = [raw_act]
    cast = [a.get("name", "") for a in raw_act[:8] if a.get("name")]
    if not cast:
        actor_el = soup.select_one(".meta-body-actor")
        if actor_el:
            raw = actor_el.get_text(strip=True).removeprefix("Avec")
            cast = [n.strip() for n in raw.split(",") if n.strip()][:8]

    # Genres
    genres = data.get("genre", [])[:5]
    if isinstance(genres, str):
        genres = [genres]

    # Note (format français : virgule → point)
    rating: Optional[float] = None
    agg = data.get("aggregateRating", {})
    if agg:
        try:
            rating = float(str(agg.get("ratingValue", "")).replace(",", ".")) or None
        except (ValueError, TypeError):
            pass

    # Année
    year_out: Optional[int] = None
    date_str = data.get("datePublished", "")
    m = _YEAR_RE.search(date_str)
    if m:
        year_out = int(m.group())

    kind_map = {"Movie": "Film", "TVSeries": "Série", "TVMiniSeries": "Mini-série"}
    kind = kind_map.get(data.get("@type", ""), "Série" if is_serie else "Film")

    return MovieMeta(
        source     = "allocine",
        title      = data.get("name", best.get("label", title)),
        year       = year_out or year,
        kind       = kind,
        rating     = rating,
        rating_max = 5.0,
        genres     = genres,
        directors  = directors,
        cast       = cast,
        synopsis   = data.get("description", ""),
        url        = fiche_url,
    )
