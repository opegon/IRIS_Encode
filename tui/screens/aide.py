"""
tui/screens/aide.py — Le guide d'utilisation, embarqué dans l'application.

Ouvert par `H` depuis n'importe quel écran. Il répond à une question précise :
« cette touche, elle fait quoi au juste ? » — sans quitter l'application, sans
ouvrir un fichier à côté.

**Rien n'y est écrit à la main sans être vérifié.** La liste des touches est
*dérivée* des `BINDINGS` de chaque écran ; seules les explications sont
rédigées, et elles sont attachées à une action (`measure`, `apply_segments`…),
pas à une touche. Une touche qu'on déplace suit son explication ; une touche
qu'on ajoute sans l'expliquer fait échouer `tests/test_aide.py`.

C'est la leçon d'IE-30 appliquée au guide : un pied de page écrit à côté des
`BINDINGS` avait fini par ne plus les décrire, et personne ne l'avait vu. Un
guide écrit à côté du code dériverait de la même façon, en pire — on lui fait
confiance justement parce qu'on ne connaît pas la réponse.
"""
from __future__ import annotations

from rich.cells import cell_len
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Static

from core.i18n import N_, _, pgettext

from ..common import footer_line2, libelle_ecartee, touche
from ..widgets.entete import Entete
from ..widgets.footer import KeyFooter

# Bindings que Textual installe lui-même sur tout écran. Ils ne font pas partie
# du vocabulaire de l'application et n'ont rien à faire dans son guide.
_CADRE = {"app.focus_next", "app.focus_previous", "screen.copy_text"}


# ─── Ce que les touches font, action par action ───────────────────────────────
#
# La clé est le **nom de l'action**, pas la touche : une touche qu'on déplace
# emporte son explication avec elle.
#
# Textes source marqués `N_()`, traduits au rendu par `explication()` (L-53).
# Un libellé ou une touche que l'explication cite est un paramètre (L-55),
# rempli par `_parametres()` avec le libellé traduit et la notation de
# `touche()` : le guide cite ce que l'écran affiche, dans toutes les langues.

_COMMUNES: dict[str, str] = {
    "table_home":      N_("First row of the table."),
    "table_end":       N_("Last row of the table."),
    "table_page_up":   N_("Moves back one screen of rows."),
    "table_page_down": N_("Moves forward one screen of rows."),
    "col_prev":        N_("Selects the previous column for resizing."),
    "col_next":        N_("Selects the next column. The header of the active "
                          "column is highlighted."),
    "col_shrink":      N_("Narrows the active column by two characters. A "
                          "floor keeps it from going below what its content "
                          "requires."),
    "col_grow":        N_("Widens the active column. Stops at the width of "
                          "the terminal: beyond it, the last columns would "
                          "leave the screen without anything saying so."),
    "accueil":         N_("Goes straight back to the list of volumes, without "
                          "going back up the screens one by one. Asks for "
                          "confirmation if work is in progress."),
    "aide":            N_("Opens this guide."),
    "request_quit":    N_("Quits the application, after confirmation."),
    "encodages":       N_("Switches from the files to the encoding queue, and "
                          "back. Encoding continues while you navigate; the "
                          "header says so."),
}

_PAR_ECRAN: dict[str, dict[str, str]] = {
    "BrowserScreen": {
        "toggle_select":       N_("Checks or unchecks the file under the "
                                  "cursor. Only checked files go to dry run or "
                                  "encoding."),
        "select_all":          N_("Checks every file in the folder."),
        "select_none":         N_("Unchecks everything."),
        "enter_dir":           N_("Opens the folder under the cursor. On a "
                                  "file: opens the Tracks screen in manual "
                                  "mode, the guided mode in guided mode."),
        "go_up":               N_("Goes up to the parent folder."),
        "open_tracks":         N_("Opens the Tracks screen of the file under "
                                  "the cursor — whatever the mode."),
        "toggle_wizard":       N_("Switches between manual and guided mode. "
                                  "The active mode is named in the profile bar "
                                  "and in the footer, whose color changes."),
        "play":                N_("Plays the file in mpv, if mpv is installed."),
        "delete_file":         N_("Deletes the file under the cursor, after "
                                  "confirmation, with its .nfo and images "
                                  "created by Jellyfin."),
        "open_dryrun":         N_("Dry run: shows what would be done, without "
                                  "doing anything."),
        "open_run":            N_("Adds the checked files to the encoding "
                                  "queue, which starts if it was empty."),
        "recursive_run":       N_("Encodes the whole tree under the current "
                                  "folder, with the active profile."),
        "open_profile_picker": N_("Changes the active profile."),
        "open_config":         N_("Manages the profiles: create, edit, "
                                  "delete."),
        "join_parts":          N_("Joins the checked files end to end into "
                                  "one, without re-encoding — a movie delivered "
                                  "as part1 / part2. The proposed order comes "
                                  "from the names and can be corrected before "
                                  "launching. The resulting file carries "
                                  "“.join-iris” and is then encoded like any "
                                  "other."),
        # TRANSLATORS: {key_tab} is the key that switches to IMDB.
        "open_fiche":          N_("Opens the movie's Info card: AlloCiné, then "
                                  "IMDB with {key_tab}."),
        "filtre_type":         N_("Shows only one image type: Dolby Vision, one "
                                  "DV profile, HDR without DV, or SDR. A checked "
                                  "row stays visible."),
        "masquer_skip":        N_("Hides or shows again the SKIP files. A "
                                  "checked row stays visible."),
    },
    "TracksScreen": {
        # TRANSLATORS: {discarded} and {decision} are labels of the tracks
        # screen, quoted as displayed.
        "toggle_row":     N_("Keeps or discards the track under the cursor. A "
                             "discarded track shows “{discarded}” in the "
                             "{decision} column."),
        "field_prev":     N_("Previous field on the video row (action, "
                             "bitrate, Dolby Vision, fate of the original)."),
        "field_next":     N_("Next field. The active field is framed ◄ ►."),
        "val_up":         N_("Next value of the active field."),
        "val_down":       N_("Previous value."),
        "enter_action":   N_("Opens the list of possible values for the "
                             "active field."),
        "dryrun":         N_("Dry run of this file only."),
        "run":            N_("Adds this file to the encoding queue."),
        "change_profile": N_("Changes the profile, which recomputes the "
                             "decision."),
        "open_codec":     N_("Chooses the output codec."),
        "open_bitrate":   N_("Chooses the target video bitrate."),
        # TRANSLATORS: {delete_flag} is the warning shown on the tracks screen.
        "toggle_delete":  N_("Deletes or keeps the source file after a "
                             "successful encode. “{delete_flag}” is shown in "
                             "orange."),
        "add_external":   N_("Adds a track taken from another file: a dub, "
                             "subtitles. Opens the Sync screen."),
        "dismiss_cancel": N_("Returns to the Home screen without applying the "
                             "changes."),
    },
    "SyncScreen": {
        "field_prev":      N_("Previous field: offset, stretch, language, "
                              "name, default, forced."),
        "field_next":      N_("Next field. The active field is highlighted."),
        "val_up":          N_("On the offset: +100 ms. On the other fields: "
                              "next value."),
        "val_down":        N_("On the offset: −100 ms. Otherwise: previous "
                              "value."),
        "jump_up":         N_("Offset +1 s — the coarse step, to get close."),
        "jump_down":       N_("Offset −1 s."),
        "fine_up":         N_("Offset +10 ms — the fine step, to close in on a "
                              "measured value. The Ctrl and + combination is "
                              "bound too, but not every terminal passes it "
                              "on."),
        "fine_down":       N_("Offset −10 ms."),
        "open_picker":     N_("Opens the list of values of the active field."),
        "measure":         N_("Measures the offset by audio correlation. Takes "
                              "several minutes: both tracks are decoded in "
                              "full. The result is cross-checked on the three "
                              "thirds of the movie before being accepted."),
        "preview":         N_("Opens mpv at the current offset, to judge by "
                              "ear."),
        "sample":          N_("Produces a check sample: a short excerpt "
                              "with all the tracks, to play in your usual "
                              "player — the safest check before muxing."),
        "apply_candidate": N_("Applies the value of a refused measurement "
                              "anyway. Check it afterwards: it was refused for "
                              "a reason."),
        "show_segments":   N_("Shows the offset segments when the measurement "
                              "found a different cut. Advisory: nothing is "
                              "applied."),
        "apply_segments":  N_("Resyncs the track over these segments. An "
                              ".srt is rewritten; an audio track is "
                              "lengthened at the switch points, then "
                              "re-encoded."),
        "copy_delay":      N_("Copies onto this track the offset of another — "
                              "useful when a dub and its subtitles come from "
                              "the same file."),
        "ancrer":          N_("Gives an anchor point when the measurement "
                              "is refused. The application suggests a line and "
                              "its timestamp; you give the moment you hear "
                              "it, and the search is done around it. Subtitles "
                              "only: an audio track has no text to suggest."),
        "remove_track":    N_("Removes the track from the added tracks."),
        "dryrun":          N_("Dry run of the target file."),
        "run":             N_("Adds the file, with its added tracks, to the "
                              "encoding queue."),
        "run_mux":         N_("Muxes without re-encoding: much faster, when "
                              "the video does not need to be touched."),
        "add_track":       N_("Adds another external track."),
        "go_back":         N_("Returns to the Tracks screen."),
    },
    "DryrunScreen": {
        "toggle_select": N_("Checks or unchecks a row."),
        "run":           N_("Adds the checked rows to the encoding queue."),
        "open_codec":    N_("Changes the codec of the row under the cursor."),
        "open_bitrate":  N_("Changes its target bitrate."),
        "go_back":       N_("Returns to the previous screen."),
    },
    "RunScreen": {
        "pause_resume": N_("Pauses or resumes the current encode."),
        "skip_current": N_("Abandons the current file, after confirmation, and moves to the next."),
        "monter":       N_("Moves the waiting file under the cursor up one "
                           "place."),
        "descendre":    N_("Moves the waiting file under the cursor down one "
                           "place."),
        "retirer":      N_("Removes the waiting file under the cursor from the "
                           "queue."),
        "arreter_tout": N_("Stops the current file and empties the queue, "
                           "after confirmation. The partial output is "
                           "deleted."),
        # TRANSLATORS: {key_options_screen} then {key_options} open the
        # options; {do_nothing} is the option label; {key_stop_all} stops the
        # batch.
        "apres_lot":    N_("Checks or unchecks the after-batch action: sleep, "
                           "hibernate or shut down, as set in the options "
                           "({key_options_screen}, {key_options}). By default "
                           "the options say “{do_nothing}” and the key arms "
                           "nothing. It fires when nothing is running any"
                           "more, after a 60 s countdown that can be "
                           "canceled. Unchecked at each new batch; a batch "
                           "stopped by {key_stop_all} triggers nothing."),
        # TRANSLATORS: {key_queue} reopens the encoding queue.
        "go_back":      N_("Returns to the files without stopping anything: "
                           "encoding continues, {key_queue} reopens it."),
    },
    "MuxScreen": {
        "dryrun":  N_("Dry run of the encode of the file produced by the "
                      "mux."),
        "encode":  N_("Adds the file produced by the mux to the encoding "
                      "queue."),
        "go_back": N_("Returns to the previous screen."),
    },
    "JoinScreen": {
        "monter":    N_("Moves the part under the cursor up one place. The "
                        "order of the table is the one that will be joined — "
                        "check it before launching: two swapped parts give a "
                        "file of the right length, and wrong."),
        "descendre": N_("Moves the part under the cursor down one place."),
        "coller":    N_("Starts the join. Refused if the parts do not match — "
                        "different video codec, resolution or audio format — "
                        "or if the output file already exists."),
        "go_back":   N_("Returns to the Home screen. A join in progress is "
                        "interrupted and its partial file deleted."),
    },
    "ConfigScreen": {
        "cles":           N_("Enters or changes the API keys (OpenSubtitles, "
                             "OMDb), checked with the service before being "
                             "saved."),
        # TRANSLATORS: {key_after_batch} is the key of the encoding screen.
        "options":        N_("Opens the options: block sleep during "
                             "processing (on by default), and the after-batch "
                             "action that {key_after_batch} checks during "
                             "encoding."),
        "activate":       N_("Makes the profile under the cursor active."),
        "new_profile":    N_("Creates a profile."),
        "edit_focused":   N_("Edits the profile under the cursor."),
        "copy_focused":   N_("Creates a profile from the one under the cursor: "
                             "same settings, name to choose."),
        "delete_focused": N_("Deletes the profile. The profiles shipped with "
                             "the application are protected."),
        "go_back":        N_("Returns to the Home screen."),
    },
    "WizardScreen": {
        # TRANSLATORS: {launch} is the name of the last step but one.
        "suivant":  N_("Moves to the next step. At the “{launch}” step, "
                       "triggers the recommended choice; at the end, returns "
                       "to the Home screen."),
        "basculer": N_("Keeps or discards the track under the cursor (step "
                       "2)."),
        "codec":    N_("Changes the output codec (step 2)."),
        "debit":    N_("Changes the target bitrate (step 2)."),
        "donneur":  N_("Presents a donor file (step 3). The offset "
                       "measurement is started and applied at once."),
        "retirer":  N_("Removes the last added track (step 3)."),
        "muxer":    N_("Muxes without re-encoding (step 4)."),
        "encoder":  N_("Re-encodes (step 4)."),
        "retour":   N_("Returns to the previous step; at the first, leaves "
                       "guided mode."),
    },
}

# Ordre de présentation : celui du parcours, pas celui des imports.
# Les titres reprennent les `msgid` des écrans eux-mêmes (« Home », « Tracks »…) :
# le guide et l'écran ne peuvent pas porter deux noms différents (L-53).
_ORDRE: list[tuple[str, str, str]] = [
    ("BrowserScreen", N_("Home"),
     N_("Browse, choose the files, launch.")),
    # TRANSLATORS: {key_mode} is the home screen key that turns guided mode on.
    ("WizardScreen", N_("Guided"),
     N_("One file, five steps. Turned on by {key_mode} from the Home "
        "screen.")),
    ("TracksScreen", N_("Tracks"),
     N_("What each track of the file will become.")),
    ("SyncScreen", N_("Sync"),
     N_("Add a track from another file, and put it back in time.")),
    ("DryrunScreen", N_("Dry run"),
     N_("What would be done, without doing anything.")),
    ("RunScreen", N_("Encoding"),
     N_("The encode in progress.")),
    ("MuxScreen", N_("Muxing"),
     N_("The mux in progress, and what can be done with it next.")),
    ("JoinScreen", N_("Join"),
     N_("Put the parts of one movie back together into a single file.")),
    ("ConfigScreen", N_("Profiles"),
     N_("Create and set up the encoding profiles.")),
]


def classes_documentees() -> dict[str, type]:
    """Les écrans du guide. Import tardif : plusieurs d'entre eux importent ce module."""
    from .browser import BrowserScreen
    from .config import ConfigScreen
    from .dryrun import DryrunScreen
    from .join import JoinScreen
    from .mux_run import MuxScreen
    from .run import RunScreen
    from .sync import SyncScreen
    from .tracks import TracksScreen
    from .wizard import WizardScreen
    return {c.__name__: c for c in (BrowserScreen, ConfigScreen, DryrunScreen,
                                    JoinScreen, MuxScreen, RunScreen,
                                    SyncScreen, TracksScreen, WizardScreen)}


def _lisible(touches: str) -> str:
    """« +,plus,equals_sign,kp_plus » → « + ».

    Les alias existent pour les dispositions de clavier, pas pour être lus : la
    première touche est celle qu'on écrit dans le guide.

    Même notation que le pied de page (`touche`) : le guide nommait les
    touches en toutes lettres (« SHIFT+TAB », « ESPACE »), une quatrième
    notation à côté des trois autres (UX-10).
    """
    return touche(touches.split(",")[0].strip())


def touches_de(classe: type) -> list[tuple[str, str, str]]:
    """(touche lisible, action, libellé) pour un écran, sans doublon d'action.

    **Toutes** les touches, pas seulement celles que le pied de page annonce :
    ce guide existe précisément pour celles qui ne s'affichent nulle part.
    """
    vus:    set[str] = set()
    sortie: list[tuple[str, str, str]] = []
    for k in classe.__mro__:
        for b in k.__dict__.get("BINDINGS", ()):
            action = getattr(b, "action", "")
            if action in _CADRE or action in vus:
                continue
            vus.add(action)
            sortie.append((_lisible(getattr(b, "key", "")), action,
                           getattr(b, "description", "")))
    return sortie


def _cle(ecran: str, action: str) -> str:
    """La touche d'une action, lue dans les `BINDINGS` : le guide cite la
    touche que l'écran déclare, pas une lettre recopiée à côté."""
    for k, a, _l in touches_de(classes_documentees()[ecran]):
        if a == action:
            return k
    raise KeyError(f"{ecran}.{action}")


def _parametres() -> dict[str, str]:
    """Les libellés et touches que les explications citent (L-55), traduits."""
    from core.veille import ACTIONS_FIN

    return {
        "discarded":          libelle_ecartee(),
        "decision":           _("Decision"),
        "delete_flag":        "⚠ " + pgettext("source file", "delete").upper(),
        "do_nothing":         _(ACTIONS_FIN["rien"]).capitalize(),
        "launch":             _("Launch"),
        "key_tab":            touche("tab"),
        "key_queue":          touche("f12"),
        "key_mode":           _cle("BrowserScreen", "toggle_wizard"),
        "key_options_screen": _cle("BrowserScreen", "open_config"),
        "key_options":        _cle("ConfigScreen", "options"),
        "key_after_batch":    _cle("RunScreen", "apres_lot"),
        "key_stop_all":       _cle("RunScreen", "arreter_tout"),
    }


def explication(ecran: str, action: str) -> str:
    """Ce que fait une action, sur cet écran, traduit. Vide si personne ne
    l'a écrit."""
    texte = _PAR_ECRAN.get(ecran, {}).get(action) or _COMMUNES.get(action, "")
    return _(texte).format(**_parametres()) if texte else ""


def _replier(texte: str, largeur: int) -> list[str]:
    """Replie aux espaces, en **cellules** de terminal et non en caractères
    (L-54) : un glyphe pleine chasse en occupe deux. Un mot plus large que la
    ligne la prend seul."""
    lignes, ligne = [], ""
    for mot in texte.split():
        if ligne and cell_len(ligne) + 1 + cell_len(mot) > largeur:
            lignes.append(ligne)
            ligne = mot
        else:
            ligne = f"{ligne} {mot}" if ligne else mot
    if ligne:
        lignes.append(ligne)
    return lignes


# ─── L'écran ──────────────────────────────────────────────────────────────────

class AideScreen(Screen):
    """Le guide, dérivé des BINDINGS. Aucune touche n'y manque par oubli."""

    CSS = """
    AideScreen { layout: vertical; }
    #aide-corps {
        height: 1fr;
        padding: 1 3;
        background: $surface;
    }
    #aide-texte { height: auto; }
    """

    BINDINGS = [
        # `priority` : un conteneur défilant étouffe les touches avant que le
        # système de bindings soit consulté — même avertissement qu'en tête de
        # tui/mixins.py.
        Binding("backspace", "fermer", N_("Back"),  show=True,  priority=True),
        Binding("escape",    "fermer", N_("Back"),  show=False, priority=True),
        Binding("h",         "fermer", N_("Close"), show=True,  priority=True),
    ]

    def compose(self) -> ComposeResult:
        yield Entete()
        with VerticalScroll(id="aide-corps"):
            yield Static(self._contenu(), id="aide-texte", markup=False)
        yield KeyFooter(actions=[("backspace", N_("Back")), ("h", N_("Close"))],
                        nav=footer_line2(nav=True))

    def on_mount(self) -> None:
        self.query_one("#aide-corps").focus()

    # ── Rendu ─────────────────────────────────────────────────────────────────

    def _contenu(self) -> Text:
        t = Text()
        t.append(_("Key guide") + "\n", style="bold")
        # Repliée ici, pas dans le message : la page tient en 74 colonnes.
        t.append("\n".join(_replier(_("Every key of every screen, with what it "
                                      "does. This page is built from the "
                                      "shortcuts actually declared: it cannot "
                                      "lag behind the application."), 74))
                 + "\n\n", style="dim")

        classes = classes_documentees()

        t.append("─" * 74 + "\n", style="dim")
        t.append(_("Everywhere").upper() + "\n", style="bold")
        t.append(_("These keys work on every screen.") + "\n\n", style="dim")
        for cle, action in (("h", "aide"), ("ctrl+home", "accueil"),
                            ("f12", "encodages"), ("f10", "request_quit")):
            self._ligne(t, touche(cle), _(_COMMUNES[action]))
        t.append("\n")
        t.append(_("In a table") + "\n", style="bold")
        for cle, action in (("home", "table_home"), ("end", "table_end"),
                            ("pageup", "table_page_up"),
                            ("pagedown", "table_page_down")):
            self._ligne(t, touche(cle), _(_COMMUNES[action]))
        t.append("\n")
        t.append(_("Resizable columns — Home, Tracks, Dry run") + "\n",
                 style="bold")
        for cle, action in (("tab", "col_next"), ("shift+tab", "col_prev"),
                            (">", "col_grow"), ("<", "col_shrink")):
            self._ligne(t, touche(cle), _(_COMMUNES[action]))
        t.append("\n")

        deja = set(_COMMUNES)
        for nom, titre, resume in _ORDRE:
            classe = classes.get(nom)
            if classe is None:
                continue
            lignes = [(k, a, d) for k, a, d in touches_de(classe)
                      if a not in deja]
            if not lignes:
                continue
            t.append("─" * 74 + "\n", style="dim")
            t.append(f"{_(titre).upper()}\n", style="bold")
            t.append(f"{_(resume).format(**_parametres())}\n\n", style="dim")
            for nom_touche, action, libelle in lignes:
                self._ligne(t, nom_touche, explication(nom, action) or _(libelle))
            t.append("\n")
        return t

    @staticmethod
    def _ligne(t: Text, touche: str, texte: str) -> None:
        """Une touche et son explication, l'explication alignée sous elle-même.

        Le repli manuel plutôt qu'un `Text` qui s'enroule : la colonne de
        gauche doit rester une colonne, y compris sur la deuxième ligne d'une
        explication longue.
        """
        marge = 14
        for i, l in enumerate(_replier(texte, 74 - marge) or [""]):
            if i == 0:
                bourrage = " " * max(1, marge - 2 - cell_len(touche))
                t.append(f"  {touche}{bourrage}", style="bold yellow")
            else:
                t.append(" " * marge)
            t.append(l + "\n")

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_fermer(self) -> None:
        self.dismiss()
