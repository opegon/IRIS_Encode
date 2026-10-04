"""core/meta.py — Recherche métadonnées film/série (IMDB + AlloCiné)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional

from .i18n import N_, ErreurAffichable, _


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

class Correspondance(Enum):
    """Sur quoi repose le choix d'une fiche parmi les résultats (UX-24).

    Une valeur, pas un libellé : l'écran en tirait la couleur en testant le
    début du texte affiché, ce qu'une traduction aurait cassé (L-23).
    """
    TITRE_ET_ANNEE = auto()
    TITRE          = auto()
    INCERTAINE     = auto()   # le titre ne correspond pas : à vérifier


class Nature(Enum):
    """Ce que décrit la fiche. Une valeur : le libellé est l'affaire de
    l'écran (L-22)."""
    FILM       = auto()
    SERIE      = auto()
    MINI_SERIE = auto()
    TELEFILM   = auto()
    EPISODE    = auto()


# Les codes de chaque source, ramenés à une `Nature`.
NATURE_OMDB: dict[str, Nature] = {
    "movie": Nature.FILM, "series": Nature.SERIE, "episode": Nature.EPISODE,
}
NATURE_IMDB: dict[str, Nature] = {
    "movie": Nature.FILM, "tvSeries": Nature.SERIE,
    "tvMiniSeries": Nature.MINI_SERIE, "tvMovie": Nature.TELEFILM,
}
NATURE_ALLOCINE: dict[str, Nature] = {
    "Movie": Nature.FILM, "TVSeries": Nature.SERIE,
    "TVMiniSeries": Nature.MINI_SERIE,
}


@dataclass
class MovieMeta:
    source:     str
    title:      str
    year:       Optional[int]
    kind:       Nature
    rating:     Optional[float]
    rating_max: float            # 10.0 IMDB, 5.0 AlloCiné
    genres:     list[str]        = field(default_factory=list)
    directors:  list[str]        = field(default_factory=list)
    cast:       list[str]        = field(default_factory=list)
    synopsis:   str              = ""
    url:        str              = ""
    # Ce qui a fait choisir cette fiche parmi les résultats, quand le choix
    # n'est pas évident — vide si la source a répondu d'un seul résultat sûr.
    confiance:  Optional[Correspondance] = None


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
        # TRANSLATORS: {error} is OMDb's own message, in English.
        raise ErreurAffichable(N_("OMDb: “{error}”"),
                               error=d.get("Error") or _("result not found"))

    kind = NATURE_OMDB.get(d.get("Type", "movie"), Nature.FILM)

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
        raise ErreurAffichable(N_("Unexpected IMDB answer"))
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
        raise ErreurAffichable(N_("No IMDB result for “{title}”"), title=title)

    kind  = NATURE_IMDB.get(best.get("qid", "movie"), Nature.FILM)
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
        synopsis   = _("Rating and synopsis available with an OMDb key "
                       "(omdbapi.com — free)."),
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


def _norme(texte: str) -> str:
    """Minuscules, sans accents ni ponctuation — ce que compare l'appariement."""
    import unicodedata
    t = unicodedata.normalize("NFKD", texte)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return " ".join(re.findall(r"[a-z0-9]+", t))


# Sous ce seuil de ressemblance, le titre ne désigne pas ce résultat.
_RESSEMBLANCE_MIN = 0.8


def choisir_allocine(results: list[dict], title: str,
                     year: Optional[int]
                     ) -> tuple[Optional[dict], Optional[Correspondance]]:
    """Le résultat d'autocomplétion qui correspond au fichier, et pourquoi.

    L'ancien choix gardait le premier résultat, sauf si l'année figurait dans
    le libellé — elle n'y figure jamais, elle est dans `data.year`. AlloCiné
    place en tête un film mis en avant : « Avatar Fire and Ash » ouvrait
    « L'île des souvenirs » (UX-24). On compare le titre au libellé français
    **et** au titre original, puis l'année départage.

    Les séries arrivent en `series` ; `tvseries` n'est gardé que par prudence.
    """
    from difflib import SequenceMatcher

    cible = _norme(title)
    meilleur, score_max, sim_max, annee_ok = None, -1.0, 0.0, False
    for res in results[:8]:
        if res.get("entity_type") not in ("movie", "series", "tvseries"):
            continue
        sim = max(SequenceMatcher(None, cible, _norme(res.get(k) or "")).ratio()
                  for k in ("label", "original_label"))
        annee = (res.get("data") or {}).get("year")
        meme_annee = bool(year and annee and int(annee) == year)
        score = sim + (0.2 if meme_annee else 0.0)
        if score > score_max:
            meilleur, score_max, sim_max, annee_ok = res, score, sim, meme_annee
    if meilleur is None:
        return None, None
    if sim_max >= _RESSEMBLANCE_MIN:
        return meilleur, (Correspondance.TITRE_ET_ANNEE if annee_ok
                          else Correspondance.TITRE)
    return meilleur, Correspondance.INCERTAINE


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

    best, confiance = choisir_allocine(results, title, year)
    if best is None:
        raise ErreurAffichable(N_("No AlloCiné result for “{title}”"), title=title)

    entity_id   = best["entity_id"]
    is_serie    = best["entity_type"] in ("series", "tvseries")
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
        raise ErreurAffichable(N_("Cannot read the AlloCiné data (no JSON-LD)"))
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

    # Genres. La normalisation passe **avant** le découpage : AlloCiné rend une
    # chaîne nue quand le film n'a qu'un genre, et `"Science fiction"[:5]` vaut
    # « Scien » — que l'`isinstance` emballe ensuite consciencieusement en
    # `["Scien"]`. Le casting, dix lignes plus haut, fait déjà les deux dans
    # le bon ordre.
    genres = data.get("genre", [])
    if isinstance(genres, str):
        genres = [genres]
    genres = list(genres)[:5]

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

    kind = NATURE_ALLOCINE.get(data.get("@type", ""),
                               Nature.SERIE if is_serie else Nature.FILM)

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
        confiance  = confiance,
    )
