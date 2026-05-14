"""tui/screens/recursive_confirm.py — Confirmation avant run récursif."""
from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static


class RecursiveConfirmModal(ModalScreen[bool]):
    """Modal de confirmation avant un scan/encodage récursif."""

    BINDINGS = [
        Binding("enter",  "confirm", "Continuer", show=True, priority=True),
        Binding("r",      "confirm", "Continuer", show=False),
        Binding("escape", "cancel",  "Annuler",   show=True, priority=True),
    ]

    DEFAULT_CSS = """
    RecursiveConfirmModal {
        align: center middle;
    }
    #confirm-panel {
        width: 70;
        background: $surface;
        border: solid $warning;
        padding: 1 2;
    }
    #confirm-title {
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }
    #confirm-dir {
        margin-bottom: 1;
    }
    #confirm-profile {
        margin-bottom: 1;
    }
    #confirm-warning {
        color: $text-muted;
        text-style: italic;
        margin-bottom: 1;
        border-top: solid $primary-darken-2;
        padding-top: 1;
    }
    #confirm-hint {
        text-style: bold;
        margin-top: 1;
        border-top: solid $primary-darken-2;
        padding-top: 1;
    }
    """

    def __init__(self, directory: Path, profile_id: str) -> None:
        super().__init__()
        self._directory  = directory
        self._profile_id = profile_id

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-panel"):
            yield Static("F3 — Run Récursif", id="confirm-title")
            yield Static(
                f"Répertoire : [bold]{self._directory}[/bold]",
                id="confirm-dir",
            )
            yield Static(
                f"Profil actif : [bold]{self._profile_id}[/bold]",
                id="confirm-profile",
            )
            yield Static(
                "Tous les fichiers vidéo de ce répertoire et de ses "
                "sous-répertoires (illimités) seront analysés et soumis "
                "au dry-run avec le profil actif.\n"
                "Aucune sélection de pistes manuelle — décisions automatiques.",
                id="confirm-warning",
            )
            yield Static(
                "Enter  Lancer l'analyse     Esc  Annuler",
                id="confirm-hint",
            )

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
