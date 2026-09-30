"""
updater.py — Mise à jour d'IRIS ENCODE depuis la release GitHub « Latest ».

Appelé par launch.bat avant main.py. Script autonome, **bibliothèque standard
seulement** : il remplace les fichiers de l'application, y compris les modules
que main.py importerait, et ne peut donc dépendre d'aucun d'eux.

Déroulé : dernière release publiée (au plus une interrogation par heure), version
comparée à version.py, confirmation, archive téléchargée puis vérifiée contre
l'empreinte SHA256 que GitHub publie, fichiers remplacés avec sauvegarde, et
restauration de la sauvegarde au moindre échec.

Ne touche jamais à ce que l'archive ne contient pas : config.toml,
profiles.toml, .venv, bin… Un dépôt git (présence de `.git`) n'est jamais mis à
jour : ce serait écraser un travail en cours avec une archive.

Code de sortie : 10 si l'application a été mise à jour (launch.bat se relance),
0 sinon — y compris en cas d'échec : une mise à jour impossible ne doit jamais
empêcher l'application de démarrer.

Réglage, `config.toml` :
    [updates]
    app = "ask"    # "ask" (défaut) : demander, « O » présélectionné
                   # "auto" : installer sans demander ; "off" : ne rien vérifier
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import time
import tomllib
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Callable

DEPOT   = "opegon/IRIS_Encode"
API     = f"https://api.github.com/repos/{DEPOT}/releases/latest"
TTL     = 3600               # l'API GitHub n'accorde que 60 appels par heure et par IP sans jeton
TIMEOUT = 8                  # hors ligne, le lancement ne doit pas attendre

CODE_MIS_A_JOUR = 10
ARCHIVE = re.compile(r"^iris_encode_v[\d.]+\.zip$")

# Ce que l'utilisateur possède et que l'archive ne livre pas. Aucun chemin de
# l'archive n'a le droit d'y écrire, même si une archive fautive le demandait.
PROTEGES = {"config.toml", "profiles.toml", "CLAUDE.md"}
DOSSIERS_PROTEGES = {".venv", "bin", ".git", ".iris_update", "resources_files", "_shots"}
# Présents dans toute archive d'IRIS : une archive qui en manque n'est pas la nôtre.
REQUIS = {"version.py", "main.py", "launch.bat", "updater.py"}

TRAVAIL  = ".iris_update"    # cache, archive téléchargée, sauvegarde, manifeste
LANCEUR  = "launcher/IrisEncodeLauncher.cs"


class ErreurMaj(Exception):
    """Une mise à jour qui ne peut pas aboutir. Le message est affiché tel quel."""


# ─── Versions ─────────────────────────────────────────────────────────────────

def version_locale(racine: Path) -> str:
    """La version installée, lue dans version.py sans l'importer."""
    texte = (racine / "version.py").read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', texte)
    if not m:
        raise ErreurMaj("version.py ne déclare pas de version")
    return m.group(1)


def version_tuple(version: str) -> tuple[int, ...]:
    """« v0.8.9.1 » → (0, 8, 9, 1). Comparaison numérique : 0.8.10 > 0.8.9."""
    return tuple(int(p) for p in version.strip().lstrip("vV").split("."))


# ─── Réglage ──────────────────────────────────────────────────────────────────

def mode(racine: Path) -> str:
    """`[updates] app` de config.toml : "ask" (défaut), "auto" ou "off".

    Un fichier absent ou illisible, une valeur inconnue : "ask". Le défaut sûr
    est de demander, pas de se taire ni d'installer d'office.
    """
    try:
        with open(racine / "config.toml", "rb") as f:
            valeur = tomllib.load(f).get("updates", {}).get("app", "ask")
    except (OSError, tomllib.TOMLDecodeError):
        return "ask"
    return valeur if valeur in ("ask", "auto", "off") else "ask"


# ─── La dernière release ──────────────────────────────────────────────────────

def _lire_api(ouvrir: Callable) -> dict:
    requete = urllib.request.Request(API, headers={
        "Accept":     "application/vnd.github+json",
        "User-Agent": "iris-encode-updater",
    })
    with ouvrir(requete, timeout=TIMEOUT) as reponse:
        return json.loads(reponse.read().decode("utf-8"))


def _extraire(release: dict) -> dict | None:
    """Tag, URL et empreinte de l'archive d'une release, ou None."""
    for asset in release.get("assets", []):
        if ARCHIVE.match(asset.get("name", "")):
            return {
                "tag":    release.get("tag_name", ""),
                "nom":    asset["name"],
                "url":    asset.get("browser_download_url", ""),
                "digest": asset.get("digest") or "",
            }
    return None


def derniere_release(racine: Path, maintenant: float | None = None,
                     ouvrir: Callable = urllib.request.urlopen,
                     installee: str = "") -> dict | None:
    """La release « Latest » de GitHub, mise en cache une heure.

    Le cache n'est pas cru s'il a été écrit par une autre version installée :
    celle qui vient d'être mise à jour, ou remplacée à la main, réinterroge.

    Réseau absent ou API en erreur : le cache, même périmé, ou None. Jamais
    d'exception : l'application démarre de toute façon.
    """
    maintenant = time.time() if maintenant is None else maintenant
    cache = racine / TRAVAIL / "release.json"
    connu = None
    try:
        connu = json.loads(cache.read_text(encoding="utf-8"))
        if (maintenant - connu.get("verifie", 0) < TTL
                and connu.get("installee", "") == installee):
            return connu.get("release")
    except (OSError, ValueError):
        pass
    try:
        release = _extraire(_lire_api(ouvrir))
    except Exception:
        return connu.get("release") if connu else None
    try:
        cache.parent.mkdir(exist_ok=True)
        cache.write_text(json.dumps({"verifie": maintenant, "installee": installee,
                                     "release": release}),
                         encoding="utf-8")
    except OSError:
        pass
    return release


# ─── Confirmation ─────────────────────────────────────────────────────────────

def demander(installee: str, disponible: str,
             entree: Callable[[str], str] = input,
             interactif: Callable[[], bool] = lambda: sys.stdin.isatty()) -> bool:
    """« Installer maintenant ? [O/n] » — Entrée vaut oui.

    Sans console pour répondre (lancement non interactif), on ne demande rien
    et on n'installe rien : un « oui » présélectionné n'est pas un consentement.
    """
    if not interactif():
        return False
    print(f"\n  Mise à jour disponible : v{installee} → {disponible}")
    try:
        reponse = entree("  Installer maintenant ? [O/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return reponse in ("", "o", "oui", "y", "yes")


# ─── Téléchargement ───────────────────────────────────────────────────────────

def telecharger(release: dict, dest: Path,
                ouvrir: Callable = urllib.request.urlopen) -> Path:
    """Télécharge l'archive et la vérifie contre l'empreinte publiée."""
    attendu = release.get("digest", "")
    if not attendu.startswith("sha256:"):
        raise ErreurMaj("la release ne publie pas d'empreinte SHA256 — rien n'est installé")
    dest.parent.mkdir(parents=True, exist_ok=True)
    requete = urllib.request.Request(release["url"],
                                     headers={"User-Agent": "iris-encode-updater"})
    empreinte = hashlib.sha256()
    with ouvrir(requete, timeout=60) as reponse, open(dest, "wb") as f:
        while bloc := reponse.read(1 << 16):
            empreinte.update(bloc)
            f.write(bloc)
    if empreinte.hexdigest() != attendu.split(":", 1)[1].lower():
        dest.unlink(missing_ok=True)
        raise ErreurMaj("l'archive téléchargée ne correspond pas à son empreinte")
    return dest


# ─── Application ──────────────────────────────────────────────────────────────

def _protege(nom: str) -> bool:
    parties = PurePosixPath(nom).parts
    return nom in PROTEGES or bool(parties) and parties[0] in DOSSIERS_PROTEGES


def contenu_archive(archive: Path, version_attendue: str) -> list[str]:
    """Les fichiers de l'archive, après contrôle qu'elle est bien la bonne."""
    with zipfile.ZipFile(archive) as z:
        noms = [n for n in z.namelist() if not n.endswith("/")]
        for n in noms:
            p = PurePosixPath(n)
            if p.is_absolute() or ".." in p.parts or ":" in n:
                raise ErreurMaj(f"chemin refusé dans l'archive : {n}")
            if _protege(n):
                raise ErreurMaj(f"l'archive voudrait écrire un fichier personnel : {n}")
        manquants = REQUIS - set(noms)
        if manquants:
            raise ErreurMaj(f"archive incomplète, il manque : {', '.join(sorted(manquants))}")
        m = re.search(r'__version__\s*=\s*"([^"]+)"', z.read("version.py").decode("utf-8"))
        if not m or version_tuple(m.group(1)) != version_tuple(version_attendue):
            raise ErreurMaj("la version de l'archive ne correspond pas à la release")
    return noms


def appliquer(racine: Path, archive: Path, version_attendue: str) -> list[str]:
    """Remplace les fichiers de l'application par ceux de l'archive.

    Ce que la version précédente livrait et que la nouvelle ne livre plus est
    retiré, d'après le manifeste écrit à la mise à jour précédente. Sans
    manifeste (première mise à jour d'une installation), rien n'est retiré :
    on ne supprime pas ce qu'on ne sait pas avoir installé.

    Tout est sauvegardé avant d'être touché ; au moindre échec, la sauvegarde
    est restaurée et l'erreur remonte. Rend la liste des fichiers écrits.
    """
    nouveaux = contenu_archive(archive, version_attendue)
    travail   = racine / TRAVAIL
    manifeste = travail / "manifeste.txt"
    anciens: set[str] = set()
    if manifeste.exists():
        anciens = {l for l in manifeste.read_text(encoding="utf-8").splitlines() if l}
    retires = sorted(n for n in anciens - set(nouveaux)
                     if not _protege(n) and (racine / n).is_file())

    sauvegarde = travail / "sauvegarde"
    shutil.rmtree(sauvegarde, ignore_errors=True)
    sauvegarde.mkdir(parents=True)
    crees: list[Path] = []
    try:
        for n in nouveaux + retires:
            cible = racine / n
            if cible.is_file():
                copie = sauvegarde / n
                copie.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(cible, copie)
        with zipfile.ZipFile(archive) as z:
            for n in nouveaux:
                cible = racine / n
                if not cible.exists():
                    crees.append(cible)
                cible.parent.mkdir(parents=True, exist_ok=True)
                with z.open(n) as src, open(cible, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        for n in retires:
            (racine / n).unlink()
    except BaseException:
        for c in crees:
            c.unlink(missing_ok=True)
        for copie in sauvegarde.rglob("*"):
            if copie.is_file():
                cible = racine / copie.relative_to(sauvegarde)
                cible.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(copie, cible)
        raise
    manifeste.write_text("\n".join(sorted(nouveaux)) + "\n", encoding="utf-8")
    return nouveaux


# ─── Point d'entrée ───────────────────────────────────────────────────────────

def main(racine: Path | None = None,
         ouvrir: Callable = urllib.request.urlopen,
         entree: Callable[[str], str] = input,
         interactif: Callable[[], bool] = lambda: sys.stdin.isatty()) -> int:
    racine = racine or Path(__file__).resolve().parent
    if (racine / ".git").exists():
        return 0
    reglage = mode(racine)
    if reglage == "off":
        return 0
    try:
        installee = version_locale(racine)
        release = derniere_release(racine, ouvrir=ouvrir, installee=installee)
        if not release or not release.get("tag"):
            return 0
        if version_tuple(release["tag"]) <= version_tuple(installee):
            return 0
        if reglage == "ask" and not demander(installee, release["tag"], entree, interactif):
            print("  Mise à jour remise à plus tard. Réglage : [updates] app dans config.toml.\n")
            return 0

        print(f"  Téléchargement de {release['nom']}…")
        archive = racine / TRAVAIL / release["nom"]
        lanceur_avant = _empreinte(racine / LANCEUR)
        try:
            telecharger(release, archive, ouvrir)
            ecrits = appliquer(racine, archive, release["tag"])
        finally:
            # Acceptée ou refusée, l'archive n'a plus rien à faire sur le disque.
            archive.unlink(missing_ok=True)
        print(f"  IRIS ENCODE mis à jour en {release['tag']} ({len(ecrits)} fichiers).")
        if _empreinte(racine / LANCEUR) != lanceur_avant and (racine / "IRIS_Encode.exe").exists():
            print("  Le lanceur a changé : relancez launcher\\build.bat pour recompiler IRIS_Encode.exe.")
        print()
        return CODE_MIS_A_JOUR
    except Exception as e:
        print(f"\n  [AVERTISSEMENT] Mise à jour impossible : {e}")
        print("  IRIS ENCODE démarre dans sa version actuelle.\n")
        return 0


def _empreinte(chemin: Path) -> str:
    try:
        return hashlib.sha256(chemin.read_bytes()).hexdigest()
    except OSError:
        return ""


if __name__ == "__main__":
    sys.exit(main())
