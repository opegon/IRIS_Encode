r"""
tui/screens/emplacements.py — Gérer les emplacements sans éditer config.toml (IE-162).

S'ouvre par `E` sur l'accueil. La liste : `Inser` ajoute, `↵` modifie,
`Ctrl+D` supprime. Le formulaire porte le libellé, le chemin, et l'identité du
**serveur** : Windows n'admet qu'un compte par serveur, elle vaut donc pour
tous les emplacements de ce serveur. Le mot de passe va au Gestionnaire
d'identifiants Windows (`core.emplacements.enregistrer_identite`), jamais dans
config.toml.

Rend True si quelque chose a changé.
"""
from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Static

from core import emplacements as emp
from core.i18n import N_, _

from ..common import colonne_fixe, raccourcis, sauver_config, touche
from .confirm import ConfirmModal

_CSS_PANNEAU = """
    {ecran} {{ align: center middle; }}
    #{id} {{
        width: 96;
        max-width: 96%;
        height: auto;
        max-height: 92%;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }}
    .empl-titre {{ text-style: bold; margin-bottom: 1; }}
    .empl-hint {{
        color: $text-muted;
        margin-top: 1;
        border-top: solid $primary-darken-2;
        padding-top: 1;
    }}
"""


class EmplacementsScreen(ModalScreen[bool]):
    """La liste des emplacements."""

    DEFAULT_CSS = _CSS_PANNEAU.format(ecran="EmplacementsScreen", id="empl-panel") + """
    #empl-table { height: auto; max-height: 20; }
    """

    BINDINGS = [
        Binding("insert", "ajouter",   N_("Add"),    show=False, priority=True),
        Binding("enter",  "modifier",  N_("Edit"),   show=False, priority=True),
        Binding("ctrl+d", "supprimer", N_("Delete"), show=False, priority=True),
        Binding("escape", "fermer",    N_("Back"),   show=False, priority=True),
        Binding("backspace", "fermer", N_("Back"),   show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._change = False

    @property
    def _cfg(self) -> dict:
        return self.app.cfg  # type: ignore[attr-defined]

    def _liste(self) -> list[emp.Emplacement]:
        return emp.lire(self._cfg)

    def compose(self) -> ComposeResult:
        with Vertical(id="empl-panel"):
            yield Label(_("Locations — network shares of the home screen"),
                        classes="empl-titre")
            yield DataTable(id="empl-table", cursor_type="row", zebra_stripes=True)
            yield Static(raccourcis([("insert", N_("Add")), ("enter", N_("Edit")),
                                     ("ctrl+d", N_("Delete")),
                                     ("escape", N_("Back"))]),
                         classes="empl-hint")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        colonne_fixe(table, _("Label"), 16, key="libelle")
        colonne_fixe(table, _("Path"), 36, key="chemin")
        colonne_fixe(table, _("Account"), 24, key="compte")
        self._remplir()
        table.focus()

    def _remplir(self, curseur: int = 0) -> None:
        table = self.query_one(DataTable)
        table.clear()
        liste = self._liste()
        comptes: dict[str, str | None] = {}
        for e in liste:
            srv = emp.serveur(e.chemin)
            if srv is not None and srv not in comptes:
                comptes[srv] = emp.compte(srv)
            srv_compte = comptes.get(srv) if srv else None
            table.add_row(
                Text(e.libelle, style="bold cyan", no_wrap=True),
                Text(emp.texte(e.chemin), no_wrap=True),
                Text(srv_compte, no_wrap=True) if srv_compte else
                Text(_("Windows session") if srv else "—", style="dim", no_wrap=True),
                key=e.libelle)
        if not liste:
            table.add_row(Text(_("No location yet — {key} to add one.").format(
                key=touche("insert")), style="dim italic"),
                "", "", key="__vide__")
        else:
            table.move_cursor(row=min(curseur, len(liste) - 1))

    def _courant(self) -> emp.Emplacement | None:
        liste = self._liste()
        ligne = self.query_one(DataTable).cursor_row
        return liste[ligne] if 0 <= ligne < len(liste) else None

    def _apres_formulaire(self, change: bool | None) -> None:
        if change:
            self._change = True
            self._remplir(self.query_one(DataTable).cursor_row)

    def action_ajouter(self) -> None:
        self.app.push_screen(EmplacementForm(None), self._apres_formulaire)

    def action_modifier(self) -> None:
        courant = self._courant()
        if courant is None:
            self.action_ajouter()
            return
        self.app.push_screen(EmplacementForm(courant), self._apres_formulaire)

    def action_supprimer(self) -> None:
        courant = self._courant()
        if courant is None:
            return

        def _confirme(ok: bool | None) -> None:
            if not ok:
                return
            ecran_liste = [e for e in self._liste() if e != courant]
            emp.ecrire(self._cfg, ecran_liste)
            if sauver_config(self.app):
                self._change = True
            self._remplir(self.query_one(DataTable).cursor_row)

        srv = emp.serveur(courant.chemin)
        corps = _("Remove the location “{label}” ({path}) from the home screen? "
                  "The share itself is not touched.").format(
                      label=courant.libelle, path=emp.texte(courant.chemin))
        if srv and emp.compte(srv):
            corps += " " + _("The identity saved for {server} stays in Windows.").format(
                server=srv)
        self.app.push_screen(ConfirmModal(_("Delete a location"), corps,
                                          confirm_label=_("Delete"), danger=True),
                             _confirme)

    def action_fermer(self) -> None:
        self.dismiss(self._change)


class EmplacementForm(ModalScreen[bool]):
    """Ajouter ou modifier un emplacement, et l'identité de son serveur."""

    DEFAULT_CSS = _CSS_PANNEAU.format(ecran="EmplacementForm", id="empl-form") + """
    .empl-ligne { height: auto; }
    .empl-lbl { width: 16; padding-top: 1; color: $text-muted; }
    .empl-ligne Input { width: 1fr; }
    #empl-note { color: $text-muted; height: auto; margin-top: 1; }
    #empl-erreur { color: darkorange; text-style: bold; height: auto; display: none; }
    #empl-boutons { height: auto; align: center middle; margin-top: 1; }
    #empl-boutons Button { min-width: 16; margin-right: 2; border: none; }
    """

    BINDINGS = [
        Binding("ctrl+s", "enregistrer", N_("Save"),   show=False, priority=True),
        Binding("escape", "annuler",     N_("Cancel"), show=False, priority=True),
    ]

    def __init__(self, ancien: emp.Emplacement | None) -> None:
        super().__init__()
        self._ancien = ancien

    @property
    def _cfg(self) -> dict:
        return self.app.cfg  # type: ignore[attr-defined]

    def compose(self) -> ComposeResult:
        a = self._ancien
        srv = emp.serveur(a.chemin) if a else None
        compte = (emp.compte(srv) if srv else None) or ""
        titre = _("Edit a location") if a else _("Add a location")
        with Vertical(id="empl-form"):
            yield Label(titre, classes="empl-titre")
            for cle, libelle, valeur, secret, indice in (
                ("libelle", N_("Label"), a.libelle if a else "", False, "Films"),
                ("chemin", N_("Path"), emp.texte(a.chemin) if a else "", False,
                 r"\\10.0.0.10\Films"),
                ("compte", N_("Account"), compte, False, r"nas\user"),
                ("mdp", N_("Password"), "", True, ""),
            ):
                with Horizontal(classes="empl-ligne"):
                    yield Label(_(libelle), classes="empl-lbl")
                    yield Input(value=valeur, password=secret, placeholder=indice,
                                id=f"champ-{cle}")
            yield Static("", id="empl-note", markup=False)
            yield Static("", id="empl-erreur", markup=False)
            with Horizontal(id="empl-boutons"):
                yield Button("✓  " + _("Save"), id="btn-enregistrer", variant="primary")
                yield Button("✗  " + _("Cancel"), id="btn-annuler")
            yield Static(raccourcis([("tab", N_("Next field")), ("ctrl+s", N_("Save")),
                                     ("escape", N_("Cancel"))]), classes="empl-hint")

    def on_mount(self) -> None:
        self.query_one("#champ-libelle", Input).focus()
        self._noter()

    def _valeur(self, cle: str) -> str:
        return self.query_one(f"#champ-{cle}", Input).value.strip()

    @on(Input.Changed, "#champ-chemin")
    def _noter(self) -> None:
        """Dit à quoi s'applique le compte : au serveur entier."""
        chemin = self._valeur("chemin")
        srv = emp.serveur(chemin)
        mdp = self.query_one("#champ-mdp", Input)
        if srv is None:
            texte = (_("Local folder or drive: no account needed.")
                     if chemin else "")
            mdp.placeholder = ""
        else:
            enregistre = emp.compte(srv)
            partages = [e.libelle for e in emp.lire(self._cfg)
                        if e != self._ancien and emp.serveur(e.chemin)
                        and emp.serveur(e.chemin).lower() == srv.lower()]
            texte = _("Windows allows one account per server: this account "
                      "applies to all of {server}.").format(server=srv)
            if partages:
                texte += " " + _("Also used by: {labels}.").format(
                    labels=", ".join(partages))
            texte += " " + (_("Saved account: {account}.").format(account=enregistre)
                            if enregistre else
                            _("No saved account: the Windows session's is used."))
            mdp.placeholder = _("unchanged") if enregistre else ""
        self.query_one("#empl-note", Static).update(texte)

    def _erreur(self, texte: str) -> None:
        zone = self.query_one("#empl-erreur", Static)
        zone.update("✗ " + texte)
        zone.display = True

    @on(Button.Pressed, "#btn-enregistrer")
    def _bouton_enregistrer(self) -> None:
        self.action_enregistrer()

    @on(Button.Pressed, "#btn-annuler")
    def _bouton_annuler(self) -> None:
        self.action_annuler()

    def action_annuler(self) -> None:
        self.dismiss(False)

    def action_enregistrer(self) -> None:
        libelle, chemin = self._valeur("libelle"), self._valeur("chemin")
        compte = self._valeur("compte")
        mdp = self.query_one("#champ-mdp", Input).value
        liste = emp.lire(self._cfg)
        erreur = emp.valider(liste, libelle, chemin, self._ancien)
        if erreur:
            self._erreur(erreur)
            return

        # L'identité, d'abord : un refus de Windows laisse tout en l'état.
        srv = emp.serveur(chemin)
        if srv is not None:
            enregistre = emp.compte(srv) or ""
            try:
                if compte and (compte != enregistre or mdp):
                    if not mdp:
                        self._erreur(_("Type the password of this account."))
                        return
                    emp.enregistrer_identite(srv, compte, mdp)
                    emp.deconnecter_serveur(srv)
                elif not compte and enregistre:
                    emp.retirer_identite(srv)
                    emp.deconnecter_serveur(srv)
            except emp.IdentiteRefusee as err:
                self._erreur(str(err))
                return

        nouveau = emp.Emplacement(libelle, Path(chemin))
        if self._ancien is not None:
            liste = [nouveau if e == self._ancien else e for e in liste]
        else:
            liste.append(nouveau)
        emp.ecrire(self._cfg, liste)
        sauver_config(self.app)
        self.dismiss(True)
