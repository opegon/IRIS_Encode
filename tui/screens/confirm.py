"""
tui/screens/confirm.py — Modale de confirmation générique.

Normalise toutes les confirmations de l'application (quitter, run récursif,
suppression de profil) : mêmes couleurs, mêmes touches, même disposition.

Touches : ←/→ ou Tab déplacent le focus, Enter active le bouton focalisé
(pas de validation aveugle), Esc / Backspace annulent.
"""
from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from core.i18n import _, N_
from ..common import raccourcis


class ConfirmModal(ModalScreen[bool]):
    """Retourne True (confirmer) ou False (annuler).

    danger=True       → bordure/titre $warning, bouton confirmer "warning".
    focus_confirm=True→ focus initial sur Confirmer (sinon Annuler, plus sûr).
    """

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }
    #confirm-panel {
        width: 70;
        height: auto;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }
    ConfirmModal.danger #confirm-panel {
        border: solid $warning;
    }
    #confirm-title {
        text-style: bold;
        margin-bottom: 1;
    }
    ConfirmModal.danger #confirm-title {
        color: $warning;
    }
    #confirm-body {
        margin-bottom: 1;
    }
    #confirm-buttons {
        height: auto;
        align: center middle;
    }
    /* Le bouton actif se voyait mal : les deux portaient un fond, et l'actif
       seulement l'inversion vidéo. Désormais lui seul a un fond, plus les
       marqueurs ▶ ◀ (revue du 2026-11-08). */
    #confirm-buttons Button {
        min-width: 16;
        margin-right: 2;
        border: none;
        background: $surface;
        color: $text-muted;
        text-style: none;
    }
    #confirm-buttons Button:focus {
        background: $accent;
        color: auto 90%;
        text-style: bold;
    }
    ConfirmModal.danger #confirm-buttons #btn-confirm:focus {
        background: $warning;
    }
    #confirm-hint {
        color: $text-muted;
        margin-top: 1;
        border-top: solid $primary-darken-2;
        padding-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape",    "cancel",        N_("Cancel"), show=False, priority=True),
        Binding("backspace", "cancel",        N_("Cancel"), show=False),
        Binding("left",      "toggle_focus",  "",        show=False),
        Binding("right",     "toggle_focus",  "",        show=False),
        Binding("enter",     "press_focused", N_("OK"), show=False),
    ]

    def __init__(
        self,
        title:         str,
        body,                                 # texte, ou `rich.text.Text`
        confirm_label: str | None = None,     # défaut : « Confirmer », traduit
        cancel_label:  str | None = None,     # défaut : « Annuler », traduit
        danger:        bool = False,
        focus_confirm: bool = False,
    ) -> None:
        super().__init__(classes="danger" if danger else "")
        self._title         = title
        self._body          = body
        self._confirm_label = confirm_label or _("Confirm")
        self._cancel_label  = cancel_label or _("Cancel")
        self._danger        = danger
        self._focus_confirm = focus_confirm

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-panel"):
            # markup desactive : aucun appelant n'y met de balise, et le titre
            # porte des identifiants entre crochets que Rich mangerait.
            yield Static(self._title, id="confirm-title", markup=False)
            yield Static(self._body,  id="confirm-body")
            with Horizontal(id="confirm-buttons"):
                yield Button(
                    self._texte_bouton("#btn-confirm", False),
                    id="btn-confirm",
                    variant="warning" if self._danger else "primary",
                )
                yield Button(self._texte_bouton("#btn-cancel", False),
                             id="btn-cancel", variant="default")
            yield Static(raccourcis([("←/→", N_("Choose")), ("enter", N_("OK")),
                                     ("escape", N_("Cancel"))]), id="confirm-hint")

    def on_mount(self) -> None:
        target = "#btn-confirm" if self._focus_confirm else "#btn-cancel"
        self.query_one(target, Button).focus()

    def _texte_bouton(self, bouton: str, actif: bool) -> str:
        """Le libellé d'un bouton, encadré de ▶ ◀ s'il a le focus. Les blancs
        de l'inactif occupent la place des marqueurs : rien ne bouge."""
        texte = (f"✓  {self._confirm_label}" if bouton == "#btn-confirm"
                 else f"✗  {self._cancel_label}")
        return f"▶ {texte} ◀" if actif else f"  {texte}  "

    def on_descendant_focus(self) -> None:
        for bouton in ("#btn-confirm", "#btn-cancel"):
            b = self.query_one(bouton, Button)
            b.label = self._texte_bouton(bouton, b.has_focus)

    # ── Boutons ───────────────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-confirm")
    def _do_confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#btn-cancel")
    def _do_cancel(self) -> None:
        self.dismiss(False)

    # ── Clavier ───────────────────────────────────────────────────────────────

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_toggle_focus(self) -> None:
        confirm = self.query_one("#btn-confirm", Button)
        cancel  = self.query_one("#btn-cancel",  Button)
        (cancel if self.focused is confirm else confirm).focus()

    def action_press_focused(self) -> None:
        # Filet de sécurité si le Button focalisé n'a pas consommé Enter
        if isinstance(self.focused, Button):
            self.focused.press()
        else:
            self.dismiss(False)
