"""tui/screens/delete_confirm.py — Confirmation avant suppression d'un fichier."""
from __future__ import annotations

from pathlib import Path

from rich.text import Text

from core.i18n import _
from ..common import fmt_size, texte_style, touche
from .confirm import ConfirmModal


class DeleteConfirmModal(ConfirmModal):
    """Modal de confirmation avant suppression définitive d'un fichier source."""

    def __init__(self, path: Path) -> None:
        # Phrases traduites, valeurs en gras par le code : pas de balise Rich
        # dans les messages (L-65), donc rien à échapper non plus.
        body = Text("\n").join([
            texte_style(_("File: {name}"), name=(path.name, "bold")),
            texte_style(_("Size: {size}"), size=(fmt_size(path), "bold")),
            texte_style(_("Folder: {folder}"), folder=str(path.parent)),
            Text(""),
            Text(_("Permanent deletion — no recycle bin, no undo."),
                 style="bold dark_orange"),
        ])
        super().__init__(
            title=f"{touche('ctrl+d')} — " + _("Delete the file"),
            body=body,
            confirm_label=_("Delete"),
            danger=True,
            focus_confirm=False,
        )
