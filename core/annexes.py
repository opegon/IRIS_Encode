"""
core/annexes.py — Les fichiers que Jellyfin dépose à côté d'une vidéo.

Jellyfin les nomme sur le nom de la vidéo, observé sur la bibliothèque de
l'utilisateur le 2026-10-07 (films côte à côte, épisodes d'une saison) :

    <nom>.mkv
    <nom>.nfo
    <nom>-poster.jpg  <nom>-backdrop.jpg  <nom>-landscape.jpg  <nom>-thumb.jpg
    <nom>-logo.png

Quand la vidéo disparaît, ils ne décrivent plus rien : ils partent avec elle
(IE-116), et Jellyfin refait les siens pour la sortie. Restent en place :

- les fichiers du dossier (`season.nfo`, `poster.jpg`, `movie.nfo`), qui
  servent aussi aux autres vidéos et à la sortie ;
- les sous-titres externes (`<nom>.fr.srt`), parfois le seul exemplaire d'un
  sous-titre téléchargé ou recalé (choix de l'utilisateur).

Pas de motif `<nom>.*` : la sortie `<nom>.hevc-iris.mkv` y répondrait. Et un
fichier qui répond aussi au nom, plus long, d'une autre vidéo du dossier est à
celle-ci : `Film-extended-poster.jpg` n'est pas une annexe de `Film.mkv`.
"""
from __future__ import annotations

from pathlib import Path

from .scanner import SUPPORTED_EXTENSIONS

IMAGES: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".webp"})

# Ce que Jellyfin indexe comme vidéo, au-delà de ce qu'IRIS encode.
_VIDEOS_JELLYFIN: frozenset[str] = SUPPORTED_EXTENSIONS | {".iso", ".divx", ".ogv",
                                                           ".rmvb", ".m2v", ".f4v"}


def _est_annexe(nom: str, base: str) -> bool:
    """`nom` est-il un fichier Jellyfin de la vidéo de nom (sans extension)
    `base` ? Comparaison sans casse, comme le système de fichiers Windows."""
    nom, base = nom.casefold(), base.casefold()
    if nom == base + ".nfo":
        return True
    return nom.startswith(base + "-") and Path(nom).suffix in IMAGES


def annexes_jellyfin(video: Path) -> list[Path]:
    """Les annexes Jellyfin de `video`, triées ; la vidéo peut déjà être
    supprimée. Dossier illisible : aucune."""
    try:
        voisins = [p for p in video.parent.iterdir() if p.is_file()]
    except OSError:
        return []
    # Une autre vidéo du même nom (`Film.avi` à côté de `Film.mkv`, ou un
    # `Film.iso` que la liste ignore) : Jellyfin rattache les annexes aux deux,
    # elles restent avec celle qui reste (CR-24).
    if any(p.stem.casefold() == video.stem.casefold() and p != video
           and p.suffix.lower() in _VIDEOS_JELLYFIN for p in voisins):
        return []
    # Seules les vidéos au nom plus long peuvent réclamer un fichier qui répond
    # aussi à celui de `video`.
    rivales = [p.stem for p in voisins
               if p.suffix.lower() in SUPPORTED_EXTENSIONS
               and len(p.stem) > len(video.stem)]
    return sorted(p for p in voisins
                  if _est_annexe(p.name, video.stem)
                  and not any(_est_annexe(p.name, r) for r in rivales))


def supprimer_annexes(video: Path) -> list[Path]:
    """Supprime les annexes Jellyfin de `video` ; rend celles qui ont résisté
    (fichier ouvert ailleurs, droits)."""
    restees = []
    for p in annexes_jellyfin(video):
        try:
            p.unlink()
        except OSError:
            restees.append(p)
    return restees
