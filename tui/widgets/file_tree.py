"""
tui/widgets/file_tree.py — Arbre fichiers navigable.

En v1 la navigation est intégrée directement dans BrowserScreen
via DataTable. Ce module expose un wrapper léger pour les
interactions avec le système de fichiers (liste, changement de répertoire).
"""
from __future__ import annotations

import sys
import string
from pathlib import Path

from core.scanner import SUPPORTED_EXTENSIONS


# ─── Détection des volumes ─────────────────────────────────────────────────────

def list_volumes() -> list[Path]:
    """
    Retourne la liste des volumes disponibles.
    Windows : lettres A–Z existantes (C:\\, D:\\, …)
    Linux/macOS : [Path("/")] — stub minimal
    """
    if sys.platform == "win32":
        return [
            Path(f"{c}:\\")
            for c in string.ascii_uppercase
            if Path(f"{c}:\\").exists()
        ]
    return [Path("/")]


# ─── Sentinelle racine virtuelle ───────────────────────────────────────────────

class FileNavigator:
    """
    Gestionnaire d'état de navigation dans le système de fichiers.

    Niveau virtuel "Volumes" : lorsque l'utilisateur presse Backspace
    depuis la racine d'un volume (ex. C:\\), le navigateur monte vers
    un niveau synthétique qui liste tous les volumes disponibles.
    """

    def __init__(self, start: Path, start_virtual: bool = False) -> None:
        self._current = start.resolve()
        self._history: list[Path] = []
        self._virtual = start_virtual            # True = écran "Volumes"

    @property
    def current(self) -> Path:
        return self._current

    @property
    def is_virtual(self) -> bool:
        return self._virtual

    # ── Navigation ────────────────────────────────────────────────────────────

    def enter(self, subdir: Path) -> None:
        if self._virtual:
            self._history.append(self._current)
            self._current = subdir.resolve()
            self._virtual = False
        else:
            self._history.append(self._current)
            self._current = subdir.resolve()

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

    # ── Listage ───────────────────────────────────────────────────────────────

    def list_subdirs(self) -> list[Path]:
        if self._virtual:
            return list_volumes()
        try:
            return sorted(p for p in self._current.iterdir() if p.is_dir())
        except (PermissionError, OSError):
            return []

    def list_videos(self) -> list[Path]:
        if self._virtual:
            return []
        try:
            return sorted(
                p for p in self._current.iterdir()
                if p.is_file()
                and p.suffix.lower() in SUPPORTED_EXTENSIONS
                and "_[hevc]" not in p.stem
                and "_[H264]" not in p.stem
            )
        except (PermissionError, OSError):
            return []

    # ── Breadcrumb ────────────────────────────────────────────────────────────

    def breadcrumb(self) -> str:
        if self._virtual:
            return "\U0001f4c1  Volumes"
        return str(self._current)
