"""
tui/widgets/file_tree.py — Arbre fichiers navigable.

En v1 la navigation est intégrée directement dans BrowserScreen
via DataTable. Ce module expose un wrapper léger pour les
interactions avec le système de fichiers (liste, changement de répertoire).
"""
from __future__ import annotations

import os
import sys
import string
from pathlib import Path

from core import bluray, dvd
from core.scanner import SUPPORTED_EXTENSIONS, module_disque


# ─── Détection des volumes ─────────────────────────────────────────────────────

def list_volumes() -> list[Path]:
    """
    Retourne la liste des volumes disponibles.
    Windows : lettres A–Z existantes (C:\\, D:\\, …)
    Linux/macOS : [Path("/")] — stub minimal
    """
    if sys.platform == "win32":
        # `os.path.isdir` rend False sur toute erreur ; `Path.exists` lève sur
        # celles que pathlib ne connaît pas — volume non reconnu, BitLocker
        # verrouillé, lecteur réseau à l'authentification expirée — et un
        # seul lecteur dans cet état empêchait IRIS de démarrer (CR-67).
        return [
            Path(f"{c}:\\")
            for c in string.ascii_uppercase
            if os.path.isdir(f"{c}:\\")
        ]
    return [Path("/")]


def _absolu(chemin: Path) -> Path:
    r"""Le chemin absolu, normalisé, **sans suivre les liens**.

    `resolve()` remplace la lettre d'un lecteur réseau ou `subst` par sa cible
    (`Z:\Films` → `\\nas\media\Films`, mesuré avec `subst`) : le fil
    d'Ariane et les sorties montraient un chemin que l'utilisateur ne reconnaît
    pas, et `⌫` remontait aux volumes au lieu de `Z:\` (CR-68).
    """
    return Path(os.path.abspath(chemin))


# ─── Sentinelle racine virtuelle ───────────────────────────────────────────────

class FileNavigator:
    """
    Gestionnaire d'état de navigation dans le système de fichiers.

    Niveau virtuel "Volumes" : lorsque l'utilisateur presse Backspace
    depuis la racine d'un volume (ex. C:\\), le navigateur monte vers
    un niveau synthétique qui liste tous les volumes disponibles.
    """

    def __init__(self, start: Path, start_virtual: bool = False) -> None:
        self._current = _absolu(start)
        self._history: list[Path] = []
        self._virtual = start_virtual            # True = écran "Volumes"
        # Titres d'un Blu-ray (IE-120) : la durée minimale d'un titre listé,
        # et ce que le dernier listage a constaté : un disque chiffré, un DVD
        # sans outil pour le lire (IE-121).
        self.duree_min_titre: float = bluray.DUREE_MIN_DEFAUT_MIN * 60
        self.disque_chiffre = False
        self.dvd_sans_outil = False

    @property
    def current(self) -> Path:
        return self._current

    @property
    def is_virtual(self) -> bool:
        return self._virtual

    # ── Navigation ────────────────────────────────────────────────────────────

    def enter(self, subdir: Path) -> None:
        if self._virtual:
            # Les volumes sont la racine : rien au-dessus à mémoriser. Garder
            # le dossier d'avant ferait remonter `⌫` vers lui, pas vers eux.
            self._history.clear()
            self._current = _absolu(subdir)
            self._virtual = False
        else:
            self._history.append(self._current)
            self._current = _absolu(subdir)

    def go_up(self) -> bool:
        if self._virtual:
            return False                         # déjà au sommet

        if self._history:
            self._current = self._history.pop()
            self._virtual = False
            return True

        parent = self._current.parent
        if parent != self._current:
            self._current = parent
            return True

        # Racine du volume (parent == self) → bascule vers l'écran virtuel
        self._virtual = True
        return True

    def aller_aux_volumes(self) -> None:
        """La racine : la liste des volumes que propose le système."""
        self._history.clear()
        self._virtual = True

    # ── Listage ───────────────────────────────────────────────────────────────

    def list_subdirs(self) -> list[Path]:
        if self._virtual:
            return list_volumes()
        try:
            return sorted(p for p in self._current.iterdir() if p.is_dir())
        except (PermissionError, OSError):
            return []

    def list_videos(self) -> list[Path]:
        """Tout ce que le dossier contient de lisible, sorties comprises.

        Le filtre `deja_produit` a vécu ici jusqu'à la v0.8.8.3 : un film
        encodé la veille disparaissait de l'écran, et rien ne distinguait
        « déjà produit » de « jamais existé ». La vue le montre désormais,
        grisé. Le filtre reste en place là où il protège vraiment —
        `scanner.scan_directory` et `scan_directory_recursive`, qui alimentent
        le scan récursif et les lots automatiques.
        """
        self.disque_chiffre = self.dvd_sans_outil = False
        if self._virtual:
            return []
        try:
            fichiers = sorted(
                p for p in self._current.iterdir()
                if p.is_file()
                and p.suffix.lower() in SUPPORTED_EXTENSIONS
            )
        except (PermissionError, OSError):
            return []
        # Le dossier d'un disque présente ses titres : les playlists d'un
        # Blu-ray (IE-120), les titres des IFO d'un DVD (IE-121).
        module = module_disque(self._current)
        if module is dvd and dvd.outils()[1] is None:
            self.dvd_sans_outil = True
        elif module is not None:
            if module.disque_chiffre(self._current):
                self.disque_chiffre = True
            else:
                fichiers += [t.chemin for t in
                             module.titres(self._current, self.duree_min_titre)]
        return fichiers

    # ── Breadcrumb ────────────────────────────────────────────────────────────

    def breadcrumb(self) -> str:
        """Le dossier courant. La liste des volumes a son propre libellé dans
        la barre d'état (« Choose a volume ») : la branche qui rendait
        « Volumes » en dur n'était jamais atteinte (CR-69)."""
        return str(self._current)
