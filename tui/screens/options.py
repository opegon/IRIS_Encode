"""
tui/screens/options.py — Les réglages qui ne sont pas ceux d'un profil.

Ouvert depuis la gestion des profils (`F5`, `U`). Pour l'instant, l'énergie :
bloquer la mise en veille pendant les traitements, et ce que fait la machine
après un lot dont on a coché « Après le lot » (`core/veille.py`) — par défaut,
rien.

Rend True si quelque chose a été enregistré.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Checkbox, Label, RadioButton, RadioSet, Static

from core.i18n import _, N_
from core import config as cfg_mod
from core import veille

from ..common import raccourcis, touche


class OptionsScreen(ModalScreen[bool]):
    """Une case et un choix, enregistrés par `Ctrl+S`."""

    DEFAULT_CSS = """
    OptionsScreen { align: center middle; }
    #options-panel {
        width: 76;
        max-width: 96%;
        height: auto;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }
    #options-titre { text-style: bold; margin-bottom: 1; }
    .options-section { text-style: bold; color: $accent; margin-top: 1; }
    .options-note { color: $text-muted; }
    #options-hint {
        color: $text-muted;
        margin-top: 1;
        border-top: solid $primary-darken-2;
        padding-top: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+s", "enregistrer", N_("Save"), show=False, priority=True),
        Binding("escape", "annuler",     N_("Cancel"),     show=False, priority=True),
    ]

    @property
    def _cfg(self) -> dict:
        return self.app.cfg  # type: ignore[attr-defined]

    def compose(self) -> ComposeResult:
        action = cfg_mod.get_action_fin(self._cfg)
        with Vertical(id="options-panel"):
            yield Label(_("Options"), id="options-titre")
            yield Static(_("Power"), classes="options-section")
            yield Checkbox(_("Block sleep while tasks run"),
                           cfg_mod.get_empecher_veille(self._cfg),
                           id="options-veille")
            yield Static(_("Encoding, mux, join, measurement or resync. The "
                           "screen can still turn off."), classes="options-note")
            yield Static(_("After the batch ({key} during encoding)").format(
                             key=touche("e")),
                         classes="options-section")
            with RadioSet(id="options-fin"):
                for cle, libelle in veille.ACTIONS_FIN.items():
                    yield RadioButton(_(libelle).capitalize(), value=cle == action,
                                      id=f"fin-{cle}")
            yield Static(_("Preceded by a {seconds} s countdown, can be "
                           "cancelled.").format(seconds=veille.COMPTE_A_REBOURS_S),
                         classes="options-note")
            if not veille.disponible():
                yield Static(_("No effect on this system: Windows only."),
                             classes="options-note")
            yield Static(raccourcis([("tab", N_("Next field")),
                                     ("ctrl+s", N_("Save")),
                                     ("escape", N_("Cancel"))]), id="options-hint")

    def on_mount(self) -> None:
        self.query_one("#options-veille", Checkbox).focus()

    def _action_choisie(self) -> str:
        bouton = self.query_one("#options-fin", RadioSet).pressed_button
        if bouton is None or not bouton.id:
            return cfg_mod.get_action_fin(self._cfg)
        return bouton.id.removeprefix("fin-")

    def action_enregistrer(self) -> None:
        cfg_mod.set_energie(self._cfg,
                            self.query_one("#options-veille", Checkbox).value,
                            self._action_choisie())
        # Sans attendre le prochain relevé : décocher relâche aussitôt.
        surveiller = getattr(self.app, "surveiller_veille", None)
        if surveiller is not None:
            surveiller()
        self.dismiss(True)

    def action_annuler(self) -> None:
        self.dismiss(False)
