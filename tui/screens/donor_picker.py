"""
tui/screens/donor_picker.py — Choix d'un fichier donneur puis de ses pistes.

Deux modales enchaînées :
  DonorFileScreen  → navigation simple, retourne le fichier choisi — ou,
                     par `O`, un sous-titre téléchargé sur OpenSubtitles.com
  DonorTrackScreen → pistes du fichier via mkvmerge -J, sélection multiple

Les tid retournés sont ceux de mkvmerge (numérotation globale), jamais les
index ffprobe de core/scanner.py.
"""
from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import DataTable, Label, Static

from ..common import (cellule, colonne_fixe, fmt_size, langue_affichee,
                      libelle_type_piste, nom_codec, raccourcis)

from core.i18n import _, N_
from core.scanner import SUPPORTED_EXTENSIONS
from core.muxer import (
    ExternalTrack, IdentifiedTrack, guess_language, identify,
)

# Conteneurs pouvant porter une piste audio ou des sous-titres
# Mêmes icônes que l'accueil : un dossier, une vidéo ; une piste isolée
# (.srt, .ac3…) n'est pas une vidéo (UX-22).
_ICONE_DOSSIER = "📁"
_ICONE_VIDEO   = "🎬"
_ICONE_PISTE   = "📄"
# Une seule liste des vidéos, celle du scan : la copie divergeait déjà.
_VIDEO_EXTS    = SUPPORTED_EXTENSIONS

DONOR_EXTS = SUPPORTED_EXTENSIONS | frozenset({
    ".mka", ".ac3", ".eac3", ".dts", ".flac", ".aac", ".mp3", ".opus",
    ".srt", ".ass", ".ssa", ".sub", ".vtt",
})


def pick_external_tracks(screen, decision, on_added) -> None:
    """
    Enchaîne donneur → pistes → ajout à `decision.external_tracks`.

    Partagé par l'écran des pistes et celui du recalage : greffer une VF puis
    ses sous-titres ne doit pas obliger à remonter d'un écran entre les deux.
    `on_added` n'est appelé que si au moins une piste a été ajoutée.
    """
    source = decision.info.path
    chosen_donor: Path | None = None

    def _on_tracks(chosen) -> None:
        if not chosen or chosen_donor is None:
            return
        for it in chosen:
            # Un .srt nu n'a aucune langue déclarée : on la déduit du nom de
            # fichier, sinon la piste sortirait en « und ».
            lang = it.language
            if lang in ("", "und"):
                lang = guess_language(chosen_donor) or lang
            decision.external_tracks.append(ExternalTrack(
                source_path=chosen_donor,
                source_tid=it.tid,
                kind=it.kind,
                codec=it.codec,
                language=lang,
                track_name=it.track_name,
            ))
        on_added()

    def _on_donor(donor) -> None:
        nonlocal chosen_donor
        if donor is None:
            return
        chosen_donor = donor
        screen.app.push_screen(DonorTrackScreen(donor), _on_tracks)

    langues = decision.profile.get("subtitle_languages", None) or ["fre", "eng"]
    screen.app.push_screen(
        DonorFileScreen(decision.info.dossier, exclude=source, langues=langues),
        _on_donor)


class DonorFileScreen(ModalScreen["Path | None"]):
    """Navigation minimale pour désigner le fichier donneur."""

    CSS = """
    DonorFileScreen { align: center middle; }
    #donor-box {
        background: $surface;
        border: solid $accent;
        width: 90;
        height: 26;
        padding: 1 2;
    }
    #donor-title { text-align: center; width: 100%; color: $accent; }
    #donor-path  { color: $text-muted; width: 100%; margin-bottom: 1; }
    #donor-table { height: 1fr; }
    #donor-hint  { color: $text-muted; width: 100%; text-align: center; margin-top: 1; }
    """

    # ⌫ remonte, comme sur l'accueil ; Esc annule (UX-22).
    BINDINGS = [
        Binding("enter",     "select", N_("Open"),           show=True, priority=True),
        Binding("backspace", "go_up",  N_("Up"),         show=True, priority=True),
        Binding("o",         "opensubtitles", "OpenSubtitles", show=True),
        Binding("escape",    "cancel", N_("Cancel"),          show=True, priority=True),
    ]

    def __init__(self, start_dir: Path, exclude: Path | None = None,
                 langues: list[str] | None = None) -> None:
        super().__init__()
        self._dir     = start_dir
        self._video   = exclude
        self._langues = langues or ["fre", "eng"]
        self._exclude = exclude.resolve() if exclude else None
        self._entries: list[Path] = []

    def compose(self) -> ComposeResult:
        with Static(id="donor-box"):
            yield Label(_("Donor file"), id="donor-title")
            yield Static("", id="donor-path", markup=False)
            yield DataTable(id="donor-table", cursor_type="row",
                            show_header=True, zebra_stripes=True)
            yield Static(raccourcis([("enter", N_("Open")),
                                     ("backspace", N_("Up")),
                                     ("o", "OpenSubtitles"),
                                     ("escape", N_("Cancel"))]), id="donor-hint")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_column(_("File"), width=None, key="name")
        colonne_fixe(table, _("Size"),  8, key="taille")
        self._populate()
        table.focus()

    def _populate(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        self._entries = []
        self.query_one("#donor-path", Static).update(str(self._dir))

        try:
            children = sorted(
                self._dir.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except OSError:
            children = []

        for p in children:
            if p.is_dir():
                table.add_row(cellule(f"{_ICONE_DOSSIER} {p.name}", style="bold cyan"),
                              Text(""), key=str(p))
                self._entries.append(p)
            elif p.suffix.lower() in DONOR_EXTS:
                if self._exclude and p.resolve() == self._exclude:
                    continue   # jamais le fichier sur lequel on travaille
                icone = _ICONE_VIDEO if p.suffix.lower() in _VIDEO_EXTS else _ICONE_PISTE
                table.add_row(cellule(f"{icone} {p.name}"),
                              Text(fmt_size(p), justify="right"), key=str(p))
                self._entries.append(p)

        if table.row_count:
            table.move_cursor(row=0)

    def action_select(self) -> None:
        row = self.query_one(DataTable).cursor_row
        if not (0 <= row < len(self._entries)):
            return
        entry = self._entries[row]
        if entry.is_dir():
            self._dir = entry
            self._populate()
        else:
            self.dismiss(entry)

    def action_go_up(self) -> None:
        """Le dossier parent ; à la racine, rien à remonter."""
        if self._dir.parent != self._dir:
            self._dir = self._dir.parent
            self._populate()

    def action_opensubtitles(self) -> None:
        """Le sous-titre téléchargé revient ici comme un fichier choisi."""
        if self._video is None:
            return
        from .opensubtitles import OpenSubtitlesScreen

        def _recu(chemin) -> None:
            if chemin is not None:
                self.dismiss(chemin)

        self.app.push_screen(OpenSubtitlesScreen(self._video, self._langues), _recu)

    def action_cancel(self) -> None:
        self.dismiss(None)


class DonorTrackScreen(ModalScreen["list[IdentifiedTrack] | None"]):
    """Pistes audio et sous-titres d'un donneur, sélection multiple."""

    CSS = """
    DonorTrackScreen { align: center middle; }
    #dt-box {
        background: $surface;
        border: solid $accent;
        width: 104;
        max-width: 96%;
        height: auto;
        max-height: 24;
        padding: 1 2;
    }
    #dt-title { text-align: center; width: 100%; color: $accent; }
    #dt-file  { color: $text-muted; width: 100%; margin-bottom: 1; }
    #dt-hint  { color: $text-muted; width: 100%; text-align: center; margin-top: 1; }
    """

    BINDINGS = [
        Binding("space",     "toggle", N_("Toggle"),  show=True),
        Binding("enter",     "accept", N_("OK"), show=True, priority=True),
        Binding("escape",    "cancel", N_("Cancel"), show=True, priority=True),
        Binding("backspace", "cancel", N_("Back"),  show=False, priority=True),
    ]

    def __init__(self, donor: Path) -> None:
        super().__init__()
        self._donor    = donor
        self._tracks   = identify(donor)
        self._selected: set[int] = set()

    def compose(self) -> ComposeResult:
        with Static(id="dt-box"):
            yield Label(_("Donor tracks"), id="dt-title")
            yield Static(self._donor.name, id="dt-file")
            yield DataTable(id="dt-table", cursor_type="row", zebra_stripes=True)
            yield Static(raccourcis([("space", N_("Select")),
                                     ("enter", N_("OK")),
                                     ("escape", N_("Cancel"))]), id="dt-hint")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        # Le nom est ce qui distingue six pistes « Français … » : il prend la
        # place, le codec la rend — « SubRip » n'a jamais eu besoin de 22
        # colonnes.
        table.add_column("",       width=5,  key="check")
        colonne_fixe(table, _("Track"),  6,  key="tid")
        colonne_fixe(table, _("Type"),   11, key="kind")
        colonne_fixe(table, _("Codec"), 14, key="codec")
        colonne_fixe(table, _("Language"), 8,  key="lang")
        table.add_column(_("Name"), width=None, key="name")

        if not self._tracks:
            table.add_row(Text(""), Text(f"({_('no readable track')})", style="dim italic"),
                          Text(""), Text(""), Text(""), Text(""))
        for t in self._tracks:
            table.add_row(*self._row(t), key=str(t.tid))
        # Une seule piste : présélectionnée, le cas courant
        if len(self._tracks) == 1:
            self._selected.add(self._tracks[0].tid)
            self._refresh_row(0)
        table.focus()

    def _row(self, t: IdentifiedTrack) -> tuple:
        sel   = t.tid in self._selected
        style = "" if sel else "dim"
        return (
            Text("  ✓  " if sel else "  ·  ", style="bold green" if sel else "dim"),
            Text(str(t.tid), style=style),
            Text(libelle_type_piste(t.kind), style=style),
            Text(nom_codec(t.codec), no_wrap=True, overflow="ellipsis", style=style),
            Text(langue_affichee(t.language), style=style),
            Text(t.track_name or "—", no_wrap=True, style=style),
        )

    def _refresh_row(self, row: int) -> None:
        t     = self._tracks[row]
        table = self.query_one(DataTable)
        for key, val in zip(("check", "tid", "kind", "codec", "lang", "name"), self._row(t)):
            table.update_cell(str(t.tid), key, val, update_width=False)

    def action_toggle(self) -> None:
        row = self.query_one(DataTable).cursor_row
        if not (0 <= row < len(self._tracks)):
            return
        self._selected.symmetric_difference_update({self._tracks[row].tid})
        self._refresh_row(row)

    def action_accept(self) -> None:
        chosen = [t for t in self._tracks if t.tid in self._selected]
        self.dismiss(chosen or None)

    def action_cancel(self) -> None:
        self.dismiss(None)
