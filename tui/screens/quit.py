"""
tui/screens/quit.py — Modal de confirmation de sortie.

Décline ConfirmModal. Focus initial sur Annuler : Enter ne quitte
que si l'utilisateur déplace explicitement le focus sur Quitter.
"""
from __future__ import annotations

from core.i18n import _
from .confirm import ConfirmModal


class QuitConfirmScreen(ConfirmModal):
    """Modal bloquant avant de quitter. Retourne True (quitter) / False."""

    def __init__(self, en_cours: list[str] | None = None) -> None:
        # Le message dit ce qui tourne vraiment (UX-06) : il annonçait un
        # encodage interrompu même quand rien ne tournait, et taisait une
        # mesure ou un mux.
        super().__init__(
            title="⚠  " + _("Quit IRIS ENCODE?"),
            body="\n".join(en_cours) if en_cours else _("No task in progress."),
            confirm_label=_("Quit"),
            danger=True,
            focus_confirm=False,
        )
