"""core/cles.py — Les clés d'API des services en ligne, et leur vérification.

Deux services en demandent (IE-101) :

- **OMDb**, pour la fiche IMDB complète. Sans clé, la fiche se réduit à ce que
  rendent les suggestions d'IMDB.
- **OpenSubtitles**, pour les sous-titres : une clé pour chercher, un compte
  pour télécharger.

Une clé se vérifie auprès du service avant d'être enregistrée : mal copiée,
elle ne se révélerait qu'à l'usage, loin du moment où on l'a saisie.

**OpenSubtitles ne contrôle pas la clé en lecture** — recherche et listes
répondent 200 à une clé inventée *(mesuré le 2026-09-30)*. Seule la connexion
la contrôle : 403 pour une clé refusée, 401 pour un compte refusé. Sans compte,
on se connecte donc avec un compte **inventé** : 401 prouve que la clé est
bonne, sans consommer les tentatives d'un compte réel — un mauvais mot de passe
en décompte (« remaining:9 »).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class Champ:
    cle:     str           # nom dans la section de config.toml
    libelle: str
    secret:  bool = False  # saisie masquée
    requis:  bool = True   # sans lui, le service est « manquant »


@dataclass(frozen=True)
class Service:
    id:       str
    nom:      str
    section:  str          # section de config.toml
    url:      str          # page qui délivre la clé
    usage:    str          # à quoi il sert, dit dans la fenêtre
    sans_cle: str          # ce qui arrive sans lui
    champs:   tuple[Champ, ...]


SERVICES: tuple[Service, ...] = (
    Service(
        id="opensubtitles", nom="OpenSubtitles", section="opensubtitles",
        url="https://www.opensubtitles.com/consumers",
        usage="sous-titres à télécharger (O depuis le fichier donneur)",
        sans_cle="sans clé, pas de recherche ; sans compte, pas de téléchargement",
        champs=(Champ("api_key", "Clé d'API"),
                Champ("username", "Identifiant", requis=False),
                Champ("password", "Mot de passe", secret=True, requis=False)),
    ),
    Service(
        id="omdb", nom="OMDb", section="meta",
        url="https://www.omdbapi.com/apikey.aspx",
        usage="fiche IMDB complète (I, puis Tab)",
        sans_cle="sans clé, la fiche IMDB se réduit aux suggestions d'IMDB",
        champs=(Champ("omdb_api_key", "Clé d'API"),),
    ),
)

PAR_ID: dict[str, Service] = {s.id: s for s in SERVICES}


# ─── Ce qui manque ────────────────────────────────────────────────────────────

def valeurs(cfg: dict[str, Any], service: Service) -> dict[str, str]:
    section = cfg.get(service.section, {})
    return {c.cle: str(section.get(c.cle, "") or "") for c in service.champs}


def ne_plus_demander(cfg: dict[str, Any]) -> set[str]:
    return set(cfg.get("cles", {}).get("ne_plus_demander", []))


def manquants(cfg: dict[str, Any]) -> list[Service]:
    """Les services dont un champ requis est vide."""
    return [s for s in SERVICES
            if any(c.requis and not valeurs(cfg, s)[c.cle] for c in s.champs)]


def a_demander(cfg: dict[str, Any]) -> list[Service]:
    """Ce que la fenêtre du lancement propose : manquant, et pas écarté."""
    ecartes = ne_plus_demander(cfg)
    return [s for s in manquants(cfg) if s.id not in ecartes]


def enregistrer(cfg: dict[str, Any], service: Service,
                saisies: dict[str, str]) -> None:
    """En mémoire ; l'appelant écrit config.toml (`config.save`)."""
    section = cfg.setdefault(service.section, {})
    for champ in service.champs:
        section[champ.cle] = saisies.get(champ.cle, "").strip()


def ecarter(cfg: dict[str, Any], service_id: str, oui: bool) -> None:
    liste = cfg.setdefault("cles", {}).setdefault("ne_plus_demander", [])
    if oui and service_id not in liste:
        liste.append(service_id)
    elif not oui and service_id in liste:
        liste.remove(service_id)


# ─── Vérification ─────────────────────────────────────────────────────────────

_UA = "IRIS Encode"
# Un compte qui n'existe pas : sa connexion n'éprouve que la clé.
_COMPTE_INVENTE = "iris-encode-verification-de-cle"


def verifier_omdb(saisies: dict[str, str]) -> Optional[str]:
    """None si la clé est acceptée, sinon ce qui ne va pas."""
    import requests
    cle = saisies.get("omdb_api_key", "").strip()
    try:
        r = requests.get("http://www.omdbapi.com/",
                         params={"apikey": cle, "i": "tt0111161"},
                         headers={"User-Agent": _UA}, timeout=12)
    except requests.RequestException as e:
        return f"OMDb injoignable : {e}"
    if r.status_code == 401:
        return "Clé refusée par OMDb — vérifiez-la, ou activez-la par le lien reçu par courriel."
    if r.status_code >= 400:
        return f"OMDb a répondu {r.status_code}."
    try:
        if r.json().get("Response") == "False":
            return f"OMDb : {r.json().get('Error', 'réponse négative')}"
    except ValueError:
        return "OMDb a rendu une réponse illisible."
    return None


def verifier_opensubtitles(saisies: dict[str, str]) -> Optional[str]:
    """None si la clé — et le compte, s'il est donné — sont acceptés."""
    import requests
    cle   = saisies.get("api_key", "").strip()
    user  = saisies.get("username", "").strip()
    mdp   = saisies.get("password", "")
    if bool(user) != bool(mdp):
        return "Donnez l'identifiant et le mot de passe, ou aucun des deux."
    compte = bool(user)
    try:
        r = requests.post(
            "https://api.opensubtitles.com/api/v1/login",
            headers={"Api-Key": cle, "User-Agent": _UA,
                     "Accept": "application/json",
                     "Content-Type": "application/json"},
            json={"username": user if compte else _COMPTE_INVENTE,
                  "password": mdp if compte else "x"},
            timeout=15)
    except requests.RequestException as e:
        return f"OpenSubtitles injoignable : {e}"
    if r.status_code == 403:
        return "Clé d'API refusée par OpenSubtitles."
    if r.status_code == 429:
        return "OpenSubtitles limite les connexions à une par seconde — réessayez."
    if r.status_code == 401:
        return ("Identifiant ou mot de passe refusé par OpenSubtitles."
                if compte else None)          # compte inventé : la clé est bonne
    if r.status_code >= 400:
        return f"OpenSubtitles a répondu {r.status_code}."
    return None


VERIFICATEURS = {"omdb": verifier_omdb, "opensubtitles": verifier_opensubtitles}
