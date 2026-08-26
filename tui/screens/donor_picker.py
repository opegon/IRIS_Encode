"""
tui/screens/donor_picker.py — Choix d'un fichier donneur puis de ses pistes.

Deux modales enchaînées :
  DonorFileScreen  → navigation simple, retourne le fichier choisi
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

from core.muxer import (
    ExternalTrack, IdentifiedTrack, TrackKind, guess_language, identify,
)

# Conteneurs pouvant porter une piste audio ou des sous-titres
DONOR_EXTS = frozenset({
    ".mkv", ".mp4", ".m4v", ".avi", ".mov", ".webm", ".ts",
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

    screen.app.push_screen(
        DonorFileScreen(source.parent, exclude=source), _on_donor)


class DonorFileScreen(ModalScreen["Path | None"]):
    """Navigation minimale pour désigner le fichier donneur."""

    CSS = """
    DonorFileScreen { align: center middle; }
    #donor-box {
        background: $surface;
        border: thick $accent;
        width: 90;
        height: 26;
        padding: 1 2;
    }
    #donor-title { text-align: center; width: 100%; color: $accent; }
    #donor-path  { color: $text-muted; width: 100%; margin-bottom: 1; }
    #donor-table { height: 1fr; }
    #donor-hint  { color: $text-muted; width: 100%; text-align: center; margin-top: 1; }
    """

    BINDINGS = [
        Binding("enter",     "select", "Ouvrir / Choisir", show=True, priority=True),
        Binding("escape",    "cancel", "Annuler",          show=True, priority=True),
        Binding("backspace", "cancel", "Retour",           show=False, priority=True),
    ]

    def __init__(self, start_dir: Path, exclude: Path | None = None) -> None:
        super().__init__()
        self._dir     = start_dir
        self._exclude = exclude.resolve() if exclude else None
        self._entries: list[Path | None] = []   # None = remonter d'un niveau

    def compose(self) -> ComposeResult:
        with Static(id="donor-box"):
            yield Label("Fichier donneur", id="donor-title")
            yield Static("", id="donor-path")
            yield DataTable(id="donor-table", cursor_type="row",
                            show_header=False, zebra_stripes=True)
            yield Static("↵  Ouvrir / Choisir     Esc  Annuler", id="donor-hint")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_column("", width=None, key="name")
        self._populate()
        table.focus()

    def _populate(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        self._entries = []
        self.query_one("#donor-path", Static).update(str(self._dir))

        if self._dir.parent != self._dir:
            table.add_row(Text("..", style="bold"), key="up")
            self._entries.append(None)

        try:
            children = sorted(
                self._dir.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except OSError:
            children = []

        for p in children:
            if p.is_dir():
                table.add_row(Text(f"{p.name}/", style="bold cyan"), key=str(p))
                self._entries.append(p)
            elif p.suffix.lower() in DONOR_EXTS:
                if self._exclude and p.resolve() == self._exclude:
                    continue   # jamais le fichier sur lequel on travaille
                table.add_row(Text(p.name, no_wrap=True, overflow="ellipsis"), key=str(p))
                self._entries.append(p)

        if table.row_count:
            table.move_cursor(row=0)

    def action_select(self) -> None:
        row = self.query_one(DataTable).cursor_row
        if not (0 <= row < len(self._entries)):
            return
        entry = self._entries[row]
        if entry is None:
            self._dir = self._dir.parent
            self._populate()
        elif entry.is_dir():
            self._dir = entry
            self._populate()
        else:
            self.dismiss(entry)

    def action_cancel(self) -> None:
        self.dismiss(None)


class DonorTrackScreen(ModalScreen["list[IdentifiedTrack] | None"]):
    """Pistes audio et sous-titres d'un donneur, sélection multiple."""

    CSS = """
    DonorTrackScreen { align: center middle; }
    #dt-box {
        background: $surface;
        border: thick $accent;
        width: 84;
        height: auto;
        max-height: 24;
        padding: 1 2;
    }
    #dt-title { text-align: center; width: 100%; color: $accent; }
    #dt-file  { color: $text-muted; width: 100%; margin-bottom: 1; }
    #dt-hint  { color: $text-muted; width: 100%; text-align: center; margin-top: 1; }
    """

    BINDINGS = [
        Binding("space",     "toggle", "Sélect",  show=True),
        Binding("enter",     "accept", "Valider", show=True, priority=True),
        Binding("escape",    "cancel", "Annuler", show=True, priority=True),
        Binding("backspace", "cancel", "Retour",  show=False, priority=True),
    ]

    def __init__(self, donor: Path) -> None:
        super().__init__()
        self._donor    = donor
        self._tracks   = identify(donor)
        self._selected: set[int] = set()

    def compose(self) -> ComposeResult:
        with Static(id="dt-box"):
            yield Label("Pistes du donneur", id="dt-title")
            yield Static(self._donor.name, id="dt-file")
            yield DataTable(id="dt-table", cursor_type="row", zebra_stripes=True)
            yield Static("Espace  Sélectionner     ↵  Valider     Esc  Annuler", id="dt-hint")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_column("",       width=5,  key="check")
        table.add_column("Piste",  width=8,  key="tid")
        table.add_column("Type",   width=12, key="kind")
        table.add_column("Codec",  width=22, key="codec")
        table.add_column("Langue", width=8,  key="lang")
        table.add_column("Nom",    width=None, key="name")

        if not self._tracks:
            table.add_row(Text(""), Text("(aucune piste lisible)", style="dim italic"),
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
            Text("audio" if t.kind == TrackKind.AUDIO else "sous-titre", style=style),
            Text(t.codec, no_wrap=True, overflow="ellipsis", style=style),
            Text(t.language or "?", style=style),
            Text(t.track_name or "—", no_wrap=True, overflow="ellipsis", style=style),
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
