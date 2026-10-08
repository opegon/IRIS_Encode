"""
core/opensubtitles.py — Recherche et téléchargement de sous-titres sur
OpenSubtitles.com (API REST v1).

Le fichier obtenu est un `.srt` ordinaire, écrit dans le dossier temporaire :
il entre ensuite dans le chemin de la greffe comme n'importe quel donneur
(`tui/screens/donor_picker.py`), recalage compris.

Deux recherches, fusionnées :

- **par empreinte** (`moviehash`) — trouve les sous-titres déposés pour cette
  release exacte, donc déjà synchronisés. Elles passent en tête ;
- **par nom** — le titre tiré du nom de fichier (`meta.parse_title`), avec
  saison et épisode pour une série. Elle rattrape tout ce que l'empreinte
  ignore : un fichier réencodé n'a plus l'empreinte de sa release.

L'API exige une clé d'application (`Api-Key`) sur chaque appel, et un compte
pour télécharger — 20 fichiers par jour en compte gratuit. Les trois vivent
dans `config.toml`, section `[opensubtitles]`.
"""
from __future__ import annotations

import re
import struct
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .i18n import N_, Nn_, ErreurAffichable
from .meta import parse_title

API_URL = "https://api.opensubtitles.com/api/v1"

# Taille des deux blocs lus par l'empreinte, en tête et en fin de fichier.
_BLOC_HASH = 65536

# L'API rend 50 résultats par page. Un film courant en a 70 dans deux langues,
# et la première page seule perdait des sous-titres français derrière des
# anglais plus téléchargés. Au-delà de 250, la liste ne se lit plus.
_PAGES_MAX = 5

# ISO 639-2 (ce que portent les profils et les pistes) → code de l'API.
_VERS_API: dict[str, str] = {
    "fre": "fr", "fra": "fr", "eng": "en", "ger": "de", "deu": "de",
    "spa": "es", "ita": "it", "jpn": "ja", "por": "pt-pt", "rus": "ru",
    "dut": "nl", "nld": "nl", "chi": "zh-cn", "zho": "zh-cn", "kor": "ko",
    "ara": "ar", "pol": "pl", "swe": "sv", "dan": "da", "nor": "no",
    "fin": "fi", "tur": "tr", "gre": "el", "ell": "el", "heb": "he",
    "cze": "cs", "ces": "cs", "hun": "hu", "rum": "ro", "ron": "ro",
}
# Et retour. Les variantes régionales se rabattent sur leur langue.
_DEPUIS_API: dict[str, str] = {
    **{v: k for k, v in _VERS_API.items() if len(k) == 3},
    "fr": "fre", "de": "ger", "nl": "dut", "zh-cn": "chi", "zh-tw": "chi",
    "el": "gre", "cs": "cze", "ro": "rum", "pt-br": "por", "pt-pt": "por",
}

_EPISODE_RE = re.compile(r"(?i)\bS(\d{1,2})E(\d{1,3})\b")


class ErreurOpenSubtitles(ErreurAffichable):
    """Un échec que l'utilisateur doit lire : message source anglais, traduit
    à l'écran (`texte_erreur`)."""


@dataclass
class Resultat:
    file_id:        int
    langue:         str    # ISO 639-2, comme les pistes
    release:        str
    telechargements: int
    empreinte:      bool   # déposé pour cette release exacte
    malentendants:  bool


# ─── Empreinte ────────────────────────────────────────────────────────────────

def empreinte(path: Path) -> str:
    """L'empreinte OpenSubtitles d'un fichier, sur 16 chiffres hexadécimaux.

    Taille du fichier plus la somme, en entiers 64 bits little-endian, de ses
    64 premiers et 64 derniers Kio — modulo 2⁶⁴. C'est l'algorithme de
    l'extension Kodi officielle. "" pour un fichier trop petit pour en avoir.
    """
    taille = path.stat().st_size
    if taille < _BLOC_HASH * 2:
        return ""
    with path.open("rb") as f:
        tampon = f.read(_BLOC_HASH)
        f.seek(taille - _BLOC_HASH)
        tampon += f.read(_BLOC_HASH)
    somme = taille
    for (mot,) in struct.iter_unpack("<q", tampon):
        somme = (somme + mot) & 0xFFFFFFFFFFFFFFFF
    return f"{somme:016x}"


# ─── Langues ──────────────────────────────────────────────────────────────────

def langues_api(langues: list[str]) -> str:
    """Les langues d'un profil au format de l'API : codes connus, triés, uniques.

    L'API redirige une requête dont les paramètres ne sont pas triés ; la
    redirection coûte un appel du quota de débit sans rien apporter.
    """
    codes = {_VERS_API[l.lower()] for l in langues if l.lower() in _VERS_API}
    return ",".join(sorted(codes))


def langue_depuis_api(code: str) -> str:
    return _DEPUIS_API.get((code or "").lower(), "und")


# ─── Client ───────────────────────────────────────────────────────────────────

class Client:
    """Une session : le jeton de connexion est gardé le temps de l'instance."""

    def __init__(self, api_key: str, utilisateur: str, mot_de_passe: str,
                 user_agent: str) -> None:
        if not api_key:
            # TRANSLATORS: F5 then K are keys; "API keys" is the name of the
            # API keys window.
            raise ErreurOpenSubtitles(N_(
                "API key missing — enter it from the profile management (F5, "
                "then K “API keys”)."))
        self._api_key     = api_key
        self._utilisateur = utilisateur
        self._mot_de_passe = mot_de_passe
        self._user_agent  = user_agent
        self._jeton: Optional[str] = None
        self._base        = API_URL

    # ── HTTP ──────────────────────────────────────────────────────────────────

    def _entetes(self) -> dict[str, str]:
        h = {"Api-Key": self._api_key, "User-Agent": self._user_agent,
             "Accept": "application/json", "Content-Type": "application/json"}
        if self._jeton:
            h["Authorization"] = f"Bearer {self._jeton}"
        return h

    def _appel(self, methode: str, route: str, **kw):
        import requests
        try:
            r = requests.request(methode, f"{self._base}/{route}",
                                 headers=self._entetes(), timeout=20, **kw)
        except requests.RequestException as e:
            raise ErreurOpenSubtitles(N_("OpenSubtitles unreachable: {error}"),
                                      error=e) from e
        if r.status_code == 401:
            raise ErreurOpenSubtitles(N_(
                "Refused by OpenSubtitles (401) — wrong API key, username or "
                "password."))
        if r.status_code == 403:
            # TRANSLATORS: F5 then K are keys.
            raise ErreurOpenSubtitles(N_(
                "API key refused by OpenSubtitles (403) — check it from the "
                "profile management (F5, then K)."))
        if r.status_code == 406:
            raise _erreur_quota(r)
        if r.status_code == 429:
            attente = r.headers.get("Retry-After", "")
            if attente.isdigit():
                raise ErreurOpenSubtitles(Nn_(
                    "Too many requests — try again in {count} second.",
                    "Too many requests — try again in {count} seconds."),
                    count=int(attente))
            raise ErreurOpenSubtitles(N_(
                "Too many requests — try again in a few seconds."))
        if r.status_code >= 400:
            raise ErreurOpenSubtitles(N_("OpenSubtitles answered {status}: {detail}"),
                                      status=r.status_code, detail=r.text[:200])
        try:
            return r.json()
        except ValueError as e:
            # Portail Wi-Fi captif, proxy, DNS détourné : 200 et du HTML. Le
            # dire, plutôt que fermer l'application (CR-95).
            raise ErreurOpenSubtitles(N_("Unexpected answer from OpenSubtitles "
                                         "(not JSON): {detail}"),
                                      detail=r.text[:120]) from e

    def _connecter(self) -> None:
        if self._jeton:
            return
        if not (self._utilisateur and self._mot_de_passe):
            # TRANSLATORS: F5 then K are keys.
            raise ErreurOpenSubtitles(N_(
                "Downloading needs an account — enter a username and password "
                "from the profile management (F5, then K)."))
        rep = self._appel("POST", "login", json={
            "username": self._utilisateur, "password": self._mot_de_passe})
        self._jeton = rep.get("token")
        if not self._jeton:
            raise ErreurOpenSubtitles(N_("Login refused: no token received."))
        # Un compte VIP est servi par un autre hôte, que la connexion annonce.
        if rep.get("base_url"):
            self._base = f"https://{rep['base_url']}/api/v1"

    # ── Recherche ─────────────────────────────────────────────────────────────

    def chercher(self, video: Path, langues: list[str],
                 nom: str | None = None) -> list[Resultat]:
        """Les sous-titres de cette vidéo, triés : release exacte d'abord, puis
        langue dans l'ordre du profil, puis nombre de téléchargements.

        `nom` remplace le nom du fichier pour la recherche par titre — celui
        du disque pour un titre de Blu-ray ; l'empreinte se calcule toujours
        sur `video` (CR-96)."""
        codes = langues_api(langues)
        base  = {"languages": codes} if codes else {}

        resultats: dict[int, Resultat] = {}
        requetes = []
        cle = empreinte(video)
        if cle:
            requetes.append({**base, "moviehash": cle})
        # `.mkv` ajouté : un nom à points (« Film.2020 ») perdrait sinon sa fin.
        requetes.append({**base, **_parametres_nom(Path(f"{nom}.mkv") if nom else video)})

        for params in requetes:
            page, pages = 1, 1
            while page <= min(pages, _PAGES_MAX):
                # `page` n'est passé qu'au-delà de la première : la requête
                # initiale reste celle que l'API attend, sans paramètre inutile.
                p = {**params, "page": page} if page > 1 else params
                rep = self._appel("GET", "subtitles", params=sorted(p.items()))
                for r in _lire_resultats(rep):
                    deja = resultats.get(r.file_id)
                    if deja is None or (r.empreinte and not deja.empreinte):
                        resultats[r.file_id] = r
                pages = int(rep.get("total_pages") or 1)
                page += 1

        rang = {l: i for i, l in enumerate(
            dict.fromkeys(langue_depuis_api(_VERS_API.get(l.lower(), ""))
                          for l in langues))}
        return sorted(resultats.values(),
                      key=lambda r: (not r.empreinte, rang.get(r.langue, len(rang)),
                                     -r.telechargements))

    # ── Téléchargement ────────────────────────────────────────────────────────

    def telecharger(self, resultat: Resultat, video: Path) -> tuple[Path, Optional[int]]:
        """Écrit le fichier dans le dossier temporaire. Rend (chemin, quota restant).

        Le nom porte la langue en dernier fragment (`Film.fr.srt`) : c'est là
        que `muxer.guess_language` la lit, et la piste greffée ne sortira pas
        en « und ».
        """
        import requests
        self._connecter()
        rep  = self._appel("POST", "download",
                           json={"file_id": resultat.file_id, "sub_format": "srt"})
        lien = rep.get("link")
        if not lien:
            if rep.get("message"):
                raise ErreurOpenSubtitles.brute(rep["message"])
            raise ErreurOpenSubtitles(N_("No download link received."))
        try:
            contenu = requests.get(lien, timeout=30)
            contenu.raise_for_status()
        except requests.RequestException as e:
            raise ErreurOpenSubtitles(N_("Download interrupted: {error}"),
                                      error=e) from e

        dossier = Path(tempfile.gettempdir()) / "iris_opensubtitles"
        dossier.mkdir(exist_ok=True)
        code    = _VERS_API.get(resultat.langue, resultat.langue)
        sortie  = dossier / f"{video.stem}.{resultat.file_id}.{code}.srt"
        sortie.write_bytes(contenu.content)
        return sortie, rep.get("remaining")


# ─── Aides ────────────────────────────────────────────────────────────────────

def _parametres_nom(video: Path) -> dict[str, object]:
    """Titre, et saison/épisode pour une série, tirés du nom de fichier."""
    titre, annee = parse_title(video)
    params: dict[str, object] = {"query": titre.lower()}
    m = _EPISODE_RE.search(video.stem)
    if m:
        params["season_number"]  = int(m.group(1))
        params["episode_number"] = int(m.group(2))
    elif annee:
        params["year"] = annee
    return params


def _lire_resultats(rep: dict) -> list[Resultat]:
    sortie = []
    for item in rep.get("data") or []:
        a = item.get("attributes") or {}
        fichiers = a.get("files") or []
        # Un sous-titre en plusieurs CD ne se greffe pas sur un fichier unique.
        if len(fichiers) != 1 or "file_id" not in fichiers[0]:
            continue
        sortie.append(Resultat(
            file_id        = int(fichiers[0]["file_id"]),
            langue         = langue_depuis_api(a.get("language", "")),
            release        = a.get("release") or fichiers[0].get("file_name") or "",
            telechargements= int(a.get("download_count") or 0),
            empreinte      = bool(a.get("moviehash_match")),
            malentendants  = bool(a.get("hearing_impaired")),
        ))
    return sortie


def _erreur_quota(r) -> "ErreurOpenSubtitles":
    """Quota du jour épuisé ; `remise` est le texte de l'API, tel quel (L-27)."""
    try:
        rep = r.json()
    except ValueError:
        rep = {}
    remise = rep.get("reset_time") or rep.get("message") or ""
    if remise:
        # TRANSLATORS: {reset} is OpenSubtitles' own text, in English.
        return ErreurOpenSubtitles(N_("Daily download quota used up — {reset}."),
                                   reset=remise)
    return ErreurOpenSubtitles(N_("Daily download quota used up."))
