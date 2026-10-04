"""
tui/screens/config.py — Écran de gestion des profils d'encodage.

Liste les profils lus dans profiles.toml, avec actions éditer/supprimer/activer.
Intègre ProfileForm pour la création et l'édition inline.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Button, DataTable, Static

from core.i18n import N_, _, pgettext
from core import profiles as prof_mod
from core.profiles import Profile
from ..common import (barre_etat, PROFIL_COLONNES, cellules_profil, profil_colonnes,
                      largeurs_colonnes, actions_ecran, footer_line2, raccourcis,
                      retour_accueil)
from ..mixins import TableNavMixin
from ..widgets.entete import Entete
from ..widgets.footer import KeyFooter
from ..widgets.profile_form import ProfileCancelled, ProfileForm, ProfileSaved

if TYPE_CHECKING:
    from ..app import IrisEncodeApp



def nom_de_copie(nom: str, pris) -> str:
    """`<nom>_copie`, puis `_copie2`, `_copie3`… : un nom libre, tenu dans
    les 32 caractères qu'accepte le formulaire."""
    n = 1
    while True:
        suffixe = "_copie" if n == 1 else f"_copie{n}"
        candidat = nom[:32 - len(suffixe)] + suffixe
        if candidat not in pris:
            return candidat
        n += 1


class ConfigScreen(TableNavMixin, Screen[bool]):
    """Écran Config — CRUD profils d'encodage."""

    BINDINGS = [
        Binding("enter",     "activate",       N_("Activate"),   show=True, priority=True),
        Binding("n",         "new_profile",    N_("New"),   show=True),
        Binding("e",         "edit_focused",   N_("Edit"),    show=True),
        Binding("c",         "copy_focused",   N_("Copy"),    show=True),
        Binding("d",         "delete_focused", N_("Delete"), show=True),
        Binding("delete",    "delete_focused", N_("Delete"), show=False),
        # Les clés des services en ligne, sans éditer config.toml (IE-101).
        Binding("k",         "cles",           N_("API keys"), show=True),
        # Ce qui n'appartient à aucun profil : la veille, l'après-lot.
        # `O` est déjà OpenSubtitles chez le donneur, et une lettre n'a qu'un
        # sens dans toute l'application (UX-12).
        Binding("u",         "options",        N_("Options"),   show=True),
        Binding("backspace", "go_back",        N_("Back"),    show=True),
        Binding("escape",    "go_back",        N_("Back"),    show=False),
        # `priority` : un DataTable etouffe la touche avant les bindings —
        # meme avertissement qu'en tete de tui/mixins.py.
        Binding("ctrl+home", "accueil",   N_("Home"),       show=True,
                priority=True),
    ]

    DEFAULT_CSS = """
    ConfigScreen { layout: vertical; }
    #profile-table { height: 1fr; }
    #form-container {
        height: 1fr;
        overflow-y: auto;
    }
    #form-container.hidden { display: none; }
    #config-actions {
        height: 3;
        layout: horizontal;
        padding: 0 2;
    }
    #config-actions Button { margin-right: 2; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._changed    = False
        self._form_mode  = False

    @property
    def _app(self) -> "IrisEncodeApp":
        return self.app  # type: ignore[return-value]

    def compose(self) -> ComposeResult:
        yield Entete()
        yield Static("", id="config-header-bar", classes="status-bar", markup=False)
        yield DataTable(id="profile-table", cursor_type="row", zebra_stripes=True)
        yield ProfileForm(id="form-container", classes="hidden")
        with Static(id="config-actions"):
            yield Button("+ " + _("New profile"),  id="btn-new",  variant="primary")
            yield Button("← " + _("Back"),          id="btn-back", variant="default")
        yield KeyFooter(
            actions=self._RACCOURCIS_ECRAN,
            nav=footer_line2(back=True, nav=True, accueil=True),
        )

    def on_mount(self) -> None:
        self._build_table()
        self._update_header()

    # ─── Table ────────────────────────────────────────────────────────────────

    def _build_table(self) -> None:
        table    = self.query_one(DataTable)
        table.clear(columns=True)
        profiles = self._app.profiles
        active   = self._app.active_profile_id

        entetes = profil_colonnes() + [_("Actions")]
        lignes  = [cellules_profil(n, p, n == active) +
                   # TRANSLATORS: column Actions of the profile list; keep it short.
                   [Text("✎ " + _("edit") + "  ✕ " + pgettext("source file", "del."),
                         no_wrap=True)]
                   for n, p in profiles.items()]
        for entete, largeur in zip(entetes, largeurs_colonnes(entetes, lignes)):
            table.add_column(entete, width=largeur)
        for nom, cellules in zip(profiles, lignes):
            table.add_row(*cellules, key=nom)

    def action_cles(self) -> None:
        if self._form_mode:
            return
        self.app.demander_cles(tous=True)  # type: ignore[attr-defined]

    def action_options(self) -> None:
        if self._form_mode:
            return
        from .options import OptionsScreen
        self.app.push_screen(OptionsScreen())

    def _update_header(self) -> None:
        if self._form_mode:
            return
        active = self._app.active_profile_id
        self.query_one("#config-header-bar", Static).update(barre_etat(
            _("Manage profiles"), "profiles.toml",
            _("Active: {profile}").format(profile=active),
        ))

    def _focused_profile_name(self) -> str | None:
        table = self.query_one(DataTable)
        row   = table.cursor_row
        names = list(self._app.profiles.keys())
        if 0 <= row < len(names):
            return names[row]
        return None

    # ─── Actions ──────────────────────────────────────────────────────────────

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        # En mode formulaire, les touches restent au widget focalisé (Select/Input)
        if self._form_mode and action in {
            "activate", "new_profile", "edit_focused", "copy_focused",
            "delete_focused", "options",
        }:
            return False
        return True

    def action_activate(self) -> None:
        name = self._focused_profile_name()
        if name and name in self._app.profiles:
            self._app.active_profile_id = name
            self._changed = True
            self._build_table()
            self._update_header()

    def action_edit_focused(self) -> None:
        name = self._focused_profile_name()
        if name:
            self._open_form(name, is_new=False)

    def action_new_profile(self) -> None:
        self._open_form("", is_new=True)

    def action_copy_focused(self) -> None:
        """Nouveau profil qui part des réglages de celui sous le curseur."""
        name = self._focused_profile_name()
        if name:
            self._open_form(name, is_new=True, copie=True)

    def action_delete_focused(self) -> None:
        """Supprime le profil sous le curseur, avec confirmation."""
        name = self._focused_profile_name()
        if name is None:
            return
        prof = self._app.profiles.get(name)
        if prof is None:
            return
        # Le fichier fait foi, donc tout profil s'efface — sauf le dernier :
        # une liste vide ne laisse rien à sélectionner pour encoder.
        if len(self._app.profiles) == 1:
            self._flash_header("✗ " + _("[{profile}] is the last profile — cannot be "
                                        "deleted").format(profile=name))
            return
        from .confirm import ConfirmModal
        def _on_answer(ok: bool) -> None:
            if ok:
                self._delete_profile(name)
                self._flash_header("✓ " + _("Profile [{profile}] deleted").format(profile=name))
        self.app.push_screen(
            ConfirmModal(
                title=_("Delete the profile [{profile}]?").format(profile=name),
                body=_("The profile will be removed from profiles.toml for good."),
                confirm_label=_("Delete"),
                danger=True,
            ),
            _on_answer,
        )

    # Raccourcis de l'écran lui-même, restaurés à la fermeture du formulaire.
    @property
    def _RACCOURCIS_ECRAN(self) -> list[tuple[str, str]]:
        """Les touches de la liste des profils, lues dans les `BINDINGS`."""
        return actions_ecran(self)

    def _footer_suit(self, en_formulaire: bool) -> None:
        """Le footer annonce les touches qui répondent, pas celles de l'écran.

        Le formulaire est monté *dans* cet écran et lui prend le focus : sans
        ça, le footer proposait « N Nouveau » alors que taper « n » écrivait
        simplement un « n » dans le champ courant.
        """
        try:
            pied = self.query_one(KeyFooter)
        except Exception:
            return
        if en_formulaire:
            pied.update_line(1, ProfileForm.RACCOURCIS)
            # La navigation de table n'a plus cours, mais F10 reste : la
            # convention du projet le veut en dernier sur tous les écrans.
            pied.update_line(2, footer_line2(nav=False))
        else:
            pied.update_line(1, self._RACCOURCIS_ECRAN)
            pied.update_line(2, footer_line2(nav=True))

    def _open_form(self, profile_id: str, is_new: bool,
                   copie: bool = False) -> None:
        self._form_mode = True
        self._footer_suit(True)
        self.query_one(DataTable).display         = False
        self.query_one(ProfileForm).remove_class("hidden")
        self.query_one("#config-actions").display = False
        # Header contextuel
        lbl = (_("Copy of {profile}").format(profile=profile_id) if copie else
               _("New profile") if is_new
               else _("Editing — {profile}").format(profile=profile_id))
        self.query_one("#config-header-bar", Static).update(
            f" {lbl}   —   " + raccourcis([("ctrl+s", N_("Save")),
                                          ("escape", N_("Cancel"))])
        )

        form     = self.query_one(ProfileForm)
        profiles = self._app.profiles
        if copie:
            form.load(nom_de_copie(profile_id, profiles),
                      profiles[profile_id].data.copy(), is_new=True,
                      ids_pris=profiles)
        elif is_new:
            # Le profil actif sert de point de départ : le nom codé en dur
            # qui tenait ici levait un KeyError dès que le fichier ne le
            # décrivait plus.
            default_data = profiles[self._app.active_profile_id].data.copy()
            form.load("", default_data, is_new=True, ids_pris=profiles)
        else:
            form.load(profile_id, profiles[profile_id].data, is_new=False)

    def _close_form(self) -> None:
        self._form_mode = False
        self._footer_suit(False)
        self.query_one(DataTable).display         = True
        self.query_one(ProfileForm).add_class("hidden")
        self.query_one("#config-actions").display = True

    @on(ProfileSaved)
    def _on_profile_saved(self, msg: ProfileSaved) -> None:
        profiles = self._app.profiles
        is_new   = msg.profile_id not in profiles

        if is_new:
            profiles[msg.profile_id] = Profile(id=msg.profile_id, data=msg.data)
        else:
            p = profiles[msg.profile_id]
            p.data.update(msg.data)

        # Activer le profil sauvegardé et écrire
        self._app.active_profile_id = msg.profile_id
        prof_mod.save_all(profiles)
        self._changed = True
        self._close_form()
        self._build_table()
        self._update_header()
        # Feedback visuel immédiat
        self._show_save_notice(msg.profile_id)

    @on(ProfileCancelled)
    def _on_profile_cancelled(self, _msg: ProfileCancelled) -> None:
        self._close_form()

    def _flash_header(self, msg: str) -> None:
        """Affiche un message temporaire dans le header (3 s), puis restaure."""
        self.query_one("#config-header-bar", Static).update(f" {msg}")
        self.set_timer(3.0, self._update_header)

    def _show_save_notice(self, profile_id: str) -> None:
        self._flash_header(
            _("Configuration — Encoding profiles") + "   ✓ "
            + _("Profile [{profile}] saved and active").format(profile=profile_id)
        )

    def _delete_profile(self, name: str) -> None:
        profiles = self._app.profiles
        if name not in profiles or len(profiles) == 1:
            return  # inexistant, ou dernier de la liste
        del profiles[name]
        if self._app.active_profile_id == name:
            self._app.active_profile_id = next(iter(profiles))
        prof_mod.save_all(profiles)
        self._changed = True
        self._build_table()
        self._update_header()

    def action_go_back(self) -> None:
        if self._form_mode:
            self._close_form()
            return
        self.dismiss(self._changed)

    @on(Button.Pressed, "#btn-new")
    def _on_new(self) -> None:
        self.action_new_profile()

    @on(Button.Pressed, "#btn-back")
    def _on_back(self) -> None:
        self.action_go_back()

    def action_accueil(self) -> None:
        """Retour au choix du fichier, sans repasser par les écrans intermédiaires."""
        retour_accueil(self.app)
