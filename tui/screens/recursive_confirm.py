"""tui/screens/recursive_confirm.py — Confirmation avant run récursif."""
from __future__ import annotations

from pathlib import Path

from rich.text import Text

from core.i18n import _
from ..common import texte_style, touche
from .confirm import ConfirmModal


class RecursiveConfirmModal(ConfirmModal):
    """Modal de confirmation avant un scan/encodage récursif."""

    def __init__(self, directory: Path, profile_id: str) -> None:
        body = Text("\n").join([
            texte_style(_("Folder: {folder}"), folder=(str(directory), "bold")),
            texte_style(_("Active profile: {profile}"), profile=(profile_id, "bold")),
            Text(""),
            Text(_("Every video file in this folder and its subfolders (no "
                   "depth limit) will be scanned and sent to the dry run with "
                   "the active profile.")),
            Text(_("No manual track selection — automatic decisions.")),
        ])
        super().__init__(
            title=f"{touche('r')} — " + _("Encode the folder"),
            body=body,
            confirm_label=_("Start the scan"),
            danger=False,
            focus_confirm=True,
        )
