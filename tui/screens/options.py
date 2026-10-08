"""
tui/screens/options.py — Les réglages qui ne sont pas ceux d'un profil.

Ouvert depuis la gestion des profils (`F5`, `U`). L'énergie : bloquer la mise
en veille pendant les traitements, et ce que fait la machine après un lot dont
on a coché « Après le lot » (`core/veille.py`) — par défaut, rien. La langue de
l'interface (IE-92) : une par catalogue livré, nommée dans sa propre langue ;
elle prend effet au lancement suivant (IE-71 point 3). Le dossier de sortie
proposé quand celui d'une source est en lecture seule (IE-118). La durée
minimale d'un titre de Blu-ray listé (IE-120).

Rend True si quelque chose a été enregistré.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import (Button, Checkbox, Input, Label, RadioButton, RadioSet,
                             Static)

from core import i18n
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
        /* La section Langue l'a porté à 32 lignes : il défile au lieu d'être
           coupé sur un petit terminal. */
        max-height: 100%;
        overflow-y: auto;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }
    #options-titre { text-style: bold; margin-bottom: 1; }
    .options-section { text-style: bold; color: $accent; margin-top: 1; }
    .options-note { color: $text-muted; }
    #options-sortie { width: 1fr; }
    #options-sortie-btn { min-width: 14; }
    #options-titres { width: 12; }
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
        self._sortie = cfg_mod.get_output_dir(self._cfg)
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
                           "canceled.").format(seconds=veille.COMPTE_A_REBOURS_S),
                         classes="options-note")
            if not veille.disponible():
                yield Static(_("No effect on this system: Windows only."),
                             classes="options-note")
            yield Static(_("Interface language"), classes="options-section")
            langue = self._langue_reglee()
            with RadioSet(id="options-langue"):
                for code in i18n.langues_disponibles():
                    yield RadioButton(i18n.nom_langue(code), value=code == langue,
                                      id=f"langue-{code}")
            yield Static(_("Takes effect the next time IRIS ENCODE starts."),
                         classes="options-note")
            yield Static(_("Output folder"), classes="options-section")
            yield Static(str(self._sortie), id="options-sortie", markup=False)
            yield Button(_("Change…"), id="options-sortie-btn", compact=True)
            yield Static(_("Offered when a source's folder is read-only, such as "
                           "a mounted disc image."), classes="options-note")
            yield Static(_("Disc titles (Blu-ray, DVD)"), classes="options-section")
            yield Input(str(cfg_mod.get_min_title_minutes(self._cfg)),
                        type="integer", id="options-titres", compact=True)
            yield Static(_("Minimum length in minutes of a listed title: shorter "
                           "ones (menus, loops) are hidden. 0 lists them all."),
                         classes="options-note")
            yield Static(raccourcis([("tab", N_("Next field")),
                                     ("ctrl+s", N_("Save")),
                                     ("escape", N_("Cancel"))]), id="options-hint")

    def on_mount(self) -> None:
        self.query_one("#options-veille", Checkbox).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "options-sortie-btn":
            return
        from .output_dir import OutputDirScreen

        def _choisi(dossier) -> None:
            if dossier is not None:
                self._sortie = dossier
                self.query_one("#options-sortie", Static).update(str(dossier))

        self.app.push_screen(OutputDirScreen(self._sortie), _choisi)

    def _action_choisie(self) -> str:
        bouton = self.query_one("#options-fin", RadioSet).pressed_button
        if bouton is None or not bouton.id:
            return cfg_mod.get_action_fin(self._cfg)
        return bouton.id.removeprefix("fin-")

    def _langue_reglee(self) -> str:
        """Celle de config.toml ; à défaut (écriture impossible au premier
        lancement), celle qui est chargée."""
        return self._cfg.get("app", {}).get("language") or i18n.langue()

    def _langue_choisie(self) -> str:
        bouton = self.query_one("#options-langue", RadioSet).pressed_button
        if bouton is None or not bouton.id:
            return self._langue_reglee()
        return bouton.id.removeprefix("langue-")

    def action_enregistrer(self) -> None:
        langue = self._langue_choisie()
        if langue != self._cfg.get("app", {}).get("language"):
            # Écrit par `set_energie` juste après, qui enregistre tout.
            self._cfg.setdefault("app", {})["language"] = langue
            if langue != i18n.langue():
                # Dans la langue courante : la nouvelle n'est pas chargée.
                self.app.notify(_("Language saved. It takes effect the next "
                                  "time IRIS ENCODE starts."), timeout=6)
        if self._sortie != cfg_mod.get_output_dir(self._cfg):
            # Écrit par `set_energie` juste après, qui enregistre tout.
            self._cfg.setdefault("app", {})["output_dir"] = str(self._sortie)
        saisie = self.query_one("#options-titres", Input).value.strip()
        if saisie.isdigit():
            # Écrit par `set_energie` juste après, qui enregistre tout.
            self._cfg.setdefault("app", {})["min_title_minutes"] = int(saisie)
        from ..common import signaler_config
        signaler_config(self.app, cfg_mod.set_energie(
            self._cfg, self.query_one("#options-veille", Checkbox).value,
            self._action_choisie()))
        # Sans attendre le prochain relevé : décocher relâche aussitôt.
        surveiller = getattr(self.app, "surveiller_veille", None)
        if surveiller is not None:
            surveiller()
        self.dismiss(True)

    def action_annuler(self) -> None:
        self.dismiss(False)
