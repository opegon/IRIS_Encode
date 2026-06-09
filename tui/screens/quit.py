"""
tui/screens/quit.py — Modal de confirmation de sortie.

Décline ConfirmModal. Focus initial sur Annuler : Enter ne quitte
que si l'utilisateur déplace explicitement le focus sur Quitter.
"""
from __future__ import annotations

from .confirm import ConfirmModal


class QuitConfirmScreen(ConfirmModal):
    """Modal bloquant avant de quitter. Retourne True (quitter) / False."""

    def __init__(self) -> None:
        super().__init__(
            title="⚠  Quitter IRIS ENCODE ?",
            body="L'encodage en cours sera interrompu.",
            confirm_label="Quitter",
            cancel_label="Annuler",
            danger=True,
            focus_confirm=False,
        )
