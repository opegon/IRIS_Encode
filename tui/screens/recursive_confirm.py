"""tui/screens/recursive_confirm.py — Confirmation avant run récursif."""
from __future__ import annotations

from pathlib import Path

from rich.markup import escape

from .confirm import ConfirmModal


class RecursiveConfirmModal(ConfirmModal):
    """Modal de confirmation avant un scan/encodage récursif."""

    def __init__(self, directory: Path, profile_id: str) -> None:
        body = (
            f"Répertoire : [bold]{escape(str(directory))}[/bold]\n"
            f"Profil actif : [bold]{escape(profile_id)}[/bold]\n\n"
            "Tous les fichiers vidéo de ce répertoire et de ses "
            "sous-répertoires (illimités) seront analysés et soumis "
            "au dry-run avec le profil actif.\n"
            "Aucune sélection de pistes manuelle — décisions automatiques."
        )
        super().__init__(
            title="F3 — Run récursif",
            body=body,
            confirm_label="Lancer l'analyse",
            cancel_label="Annuler",
            danger=False,
            focus_confirm=True,
        )
