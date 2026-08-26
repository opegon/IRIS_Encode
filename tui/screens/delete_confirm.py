"""tui/screens/delete_confirm.py — Confirmation avant suppression d'un fichier."""
from __future__ import annotations

from pathlib import Path

from rich.markup import escape

from ..common import fmt_size
from .confirm import ConfirmModal


class DeleteConfirmModal(ConfirmModal):
    """Modal de confirmation avant suppression définitive d'un fichier source."""

    def __init__(self, path: Path) -> None:
        body = (
            f"Fichier : [bold]{escape(path.name)}[/bold]\n"
            f"Taille : [bold]{escape(fmt_size(path))}[/bold]\n"
            f"Dossier : {escape(str(path.parent))}\n\n"
            "[bold dark_orange]Suppression définitive — pas de corbeille, "
            "pas de retour arrière.[/bold dark_orange]"
        )
        super().__init__(
            title="Ctrl+D — Supprimer le fichier",
            body=body,
            confirm_label="Supprimer",
            cancel_label="Annuler",
            danger=True,
            focus_confirm=False,
        )
