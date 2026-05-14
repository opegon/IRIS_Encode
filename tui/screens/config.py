"""
tui/screens/config.py — Écran de gestion des profils d'encodage.

Liste les profils (builtins + user) avec actions éditer/supprimer/activer.
Intègre ProfileForm pour la création et l'édition inline.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Button, DataTable, Header, Static
from ..widgets.footer import TwoLineFooter
from ..mixins import TableNavMixin

from core import profiles as prof_mod
from core.profiles import BUILTIN_NAMES, Profile
from ..widgets.profile_form import ProfileCancelled, ProfileForm, ProfileSaved

if TYPE_CHECKING:
    from ..app import IrisEncodeApp


class ConfigScreen(TableNavMixin, Screen[bool]):
    """Écran Config — CRUD profils d'encodage."""

    BINDINGS = [
        Binding("n",      "new_profile",  "+ Nouveau",  show=True),
        Binding("e",      "edit_focused", "✎ Éditer",   show=True),
        Binding("left",   "go_back",      "← Retour",   show=True),
        Binding("escape", "go_back",      "Retour",     show=False),
        Binding("enter",  "activate",     "Activer",    show=True, priority=True),
    ]

    DEFAULT_CSS = """
    ConfigScreen { layout: vertical; }
    #config-header-bar {
        height: 1;
        background: $accent;
        padding: 0 2;
    }
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
        yield Header(show_clock=True)
        yield Static("", id="config-header-bar")
        yield DataTable(id="profile-table", cursor_type="row", zebra_stripes=True)
        yield ProfileForm(id="form-container", classes="hidden")
        with Static(id="config-actions"):
            yield Button("+ Nouveau profil",  id="btn-new",  variant="primary")
            yield Button("← Retour",          id="btn-back", variant="default")
        yield TwoLineFooter(
            line1=[
                ("enter",     "Activer profil"),
                ("e",         "Éditer"),
                ("n",         "Nouveau profil"),
                ("backspace", "Retour"),
            ],
            line2=[
                ("home",     "Début"),
                ("end",      "Fin"),
                ("pageup",   "Page préc."),
                ("pagedown", "Page suiv."),
                ("f10",      "Quitter"),
            ],
        )

    def on_mount(self) -> None:
        self._build_table()
        self._update_header()

    # ─── Table ────────────────────────────────────────────────────────────────

    def _build_table(self) -> None:
        table = self.query_one(DataTable)
        table.clear(columns=True)
        table.add_column("Profil",    width=18,  key="name")
        table.add_column("Type",      width=9,   key="type")
        table.add_column("Dolby V.",  width=11,  key="dv")
        table.add_column("1080p",     width=8,   key="br1080")
        table.add_column("4K",        width=11,  key="br4k")
        table.add_column("Preset",    width=9,   key="preset")
        table.add_column("HD Audio",  width=10,  key="hd")
        table.add_column("Suppr.",    width=8,   key="del")
        table.add_column("Actions",   width=None, key="actions")

        for name, profile in self._app.profiles.items():
            is_active = (name == self._app.active_profile_id)
            f         = profile.summary_fields()

            name_txt  = Text(
                f"[{name}]" + (" ✓" if is_active else ""),
                style="bold green" if is_active else "bold",
            )
            type_txt  = Text(
                "user" if profile.user else "builtin",
                style="dim cyan" if profile.user else "dim",
            )
            dv_style  = {"strip": "yellow", "preserve": "green", "sdr": "red"}.get(f["dv"], "")
            actions   = Text("✎ éditer" + ("  ✕ suppr." if profile.user else ""), no_wrap=True)

            table.add_row(
                name_txt,
                type_txt,
                Text(f["dv"],       style=dv_style, no_wrap=True),
                Text(f["1080p"],    no_wrap=True),
                Text(f["4k"],       no_wrap=True),
                Text(f["preset"],   no_wrap=True),
                Text(f["hd_audio"], no_wrap=True),
                Text(f["del_src"],  style="bold dark_orange" if "oui" in f["del_src"] else "dim", no_wrap=True),
                actions,
                key=name,
            )

    def _update_header(self) -> None:
        if self._form_mode:
            return
        active = self._app.active_profile_id
        self.query_one("#config-header-bar", Static).update(
            f" Configuration — Profils d'encodage    "
            f"profiles.toml · Actif : {active}"
        )

    def _focused_profile_name(self) -> str | None:
        table = self.query_one(DataTable)
        row   = table.cursor_row
        names = list(self._app.profiles.keys())
        if 0 <= row < len(names):
            return names[row]
        return None

    # ─── Actions ──────────────────────────────────────────────────────────────

    def on_key(self, event) -> None:
        if event.key == "enter" and not self._form_mode:
            self.action_activate()
            event.stop()

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

    def _open_form(self, profile_id: str, is_new: bool) -> None:
        self._form_mode = True
        self.query_one(DataTable).display         = False
        self.query_one(ProfileForm).remove_class("hidden")
        self.query_one("#config-actions").display = False
        # Header contextuel
        lbl = "Nouveau profil" if is_new else f"Edition [{profile_id}]"
        self.query_one("#config-header-bar", Static).update(
            f" {lbl}   —   Ctrl+S Enregistrer   Esc Annuler"
        )

        form     = self.query_one(ProfileForm)
        profiles = self._app.profiles
        if is_new:
            default_data = profiles["serie_basic"].data.copy()
            form.load("", default_data, is_new=True, is_builtin=False)
        else:
            p = profiles[profile_id]
            form.load(profile_id, p.data, is_new=False, is_builtin=not p.user)

    def _close_form(self) -> None:
        self._form_mode = False
        self.query_one(DataTable).display         = True
        self.query_one(ProfileForm).add_class("hidden")
        self.query_one("#config-actions").display = True

    @on(ProfileSaved)
    def _on_profile_saved(self, msg: ProfileSaved) -> None:
        from core.profiles import Profile
        profiles = self._app.profiles
        is_new   = msg.profile_id not in profiles

        if is_new:
            profiles[msg.profile_id] = Profile(
                id=msg.profile_id, data=msg.data, user=True
            )
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
    def _on_profile_cancelled(self, _: ProfileCancelled) -> None:
        self._close_form()

    def _show_save_notice(self, profile_id: str) -> None:
        """Affiche une confirmation de sauvegarde dans le header."""
        bar = self.query_one("#config-header-bar", Static)
        bar.update(
            f" Configuration — Profils d'encodage   ✓ Profil [{profile_id}] enregistré et actif"
        )
        # Remet le header normal après 3 secondes
        self.set_timer(3.0, self._update_header)

    def _delete_profile(self, name: str) -> None:
        if name in BUILTIN_NAMES:
            return
        profiles = self._app.profiles
        del profiles[name]
        if self._app.active_profile_id == name:
            self._app.active_profile_id = "serie_basic"
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
