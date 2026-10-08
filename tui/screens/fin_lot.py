"""
tui/screens/fin_lot.py — Le compte à rebours avant l'action d'après lot.

Celui qui a coché « Après le lot » est souvent parti ; celui qui revient
devant l'écran à la dernière minute doit pouvoir dire non. Rien ne part sans
ces soixante secondes, sauf « Maintenant ».

Rend True (agir) ou False (annulé). Focus initial sur Annuler, comme toute
confirmation qui coûte : `↵` réflexe n'endort pas la machine.
"""
from __future__ import annotations

from core.veille import COMPTE_A_REBOURS_S, libelle_action

from core.i18n import _
from .confirm import ConfirmModal


class FinDeLotModal(ConfirmModal):
    """« Mise en veille dans 60 s », décompté chaque seconde."""

    def __init__(self, action: str, delai: int | None = None) -> None:
        self._libelle = libelle_action(action)
        self._reste   = COMPTE_A_REBOURS_S if delai is None else delai
        super().__init__(
            title=self._titre(),
            body=_("All tasks are done."),
            confirm_label=_("Now"),
            danger=True,
            focus_confirm=False,
        )

    def _titre(self) -> str:
        # TRANSLATORS: {action} is "Sleep", "Shut down"… (capitalized by the
        # code), {seconds} the countdown.
        return _("{action} in {seconds} s").format(
            action=self._libelle.capitalize(), seconds=self._reste)

    def on_mount(self) -> None:
        super().on_mount()
        self._minuteur = self.set_interval(1, self._decompter, name="compte à rebours")

    def _decompter(self) -> None:
        self._reste = max(self._reste - 1, 0)
        if self._reste <= 0:
            # `dismiss` retire l'écran du **sommet** : recouverte (guide, file,
            # confirmation de sortie), la modale aurait fait retirer l'autre
            # écran, puis planté au tour suivant. Elle attend d'être revenue
            # devant, et ne rend qu'une fois (CR-104).
            if not self.is_active:
                return
            self._minuteur.stop()
            self.dismiss(True)
            return
        from textual.widgets import Static
        try:
            self.query_one("#confirm-title", Static).update(self._titre())
        except Exception:
            pass
