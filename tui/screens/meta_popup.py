"""tui/screens/meta_popup.py — Pop-up métadonnées IMDB / AlloCiné."""
from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import LoadingIndicator, Static

from ..common import raccourcis

from core.meta import MovieMeta, fetch_allocine, fetch_imdb, parse_title


class MetaPopup(ModalScreen):
    """Modal affichant les métadonnées IMDB (F8) ou AlloCiné (F7) d'un fichier."""

    BINDINGS = [
        Binding("escape", "dismiss", "Fermer", show=True),
        Binding("f7",     "dismiss", "Fermer", show=False),
        Binding("f8",     "dismiss", "Fermer", show=False),
    ]

    DEFAULT_CSS = """
    MetaPopup {
        align: center middle;
    }
    #meta-panel {
        width: 82;
        max-height: 38;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }
    #meta-header {
        text-style: bold;
        padding-bottom: 1;
        border-bottom: solid $primary-darken-2;
        margin-bottom: 1;
    }
    #meta-body {
        height: 1fr;
        overflow-y: auto;
    }
    #meta-loading {
        height: 5;
        align: center middle;
    }
    .meta-lbl {
        color: $text-muted;
        text-style: dim;
    }
    .meta-val {
        margin-bottom: 1;
    }
    .meta-synopsis-lbl {
        color: $text-muted;
        text-style: dim;
        margin-top: 1;
    }
    .meta-synopsis {
        margin-bottom: 1;
    }
    #meta-url {
        color: $text-muted;
        text-style: dim italic;
        margin-top: 1;
    }
    #meta-error {
        color: darkorange;
        text-style: bold;
        margin-top: 2;
    }
    #meta-hint {
        text-style: dim;
        margin-top: 1;
        text-align: right;
    }
    """

    def __init__(self, path: Path, source: str) -> None:
        super().__init__()
        self._path   = path
        self._source = source  # "imdb" | "allocine"

    def compose(self) -> ComposeResult:
        with Vertical(id="meta-panel"):
            yield Static("", id="meta-header")
            with ScrollableContainer(id="meta-body"):
                yield LoadingIndicator(id="meta-loading")
            yield Static(raccourcis([("escape", "Fermer")]), id="meta-hint")

    def on_mount(self) -> None:
        title, year = parse_title(self._path)
        label = "IMDB" if self._source == "imdb" else "AlloCiné"
        query = f"{title}" + (f" ({year})" if year else "")
        self.query_one("#meta-header", Static).update(
            f"[bold]{label}[/bold] — {query}"
        )
        self._fetch(title, year)

    @work(thread=True, name="meta-fetch")
    def _fetch(self, title: str, year) -> None:
        try:
            if self._source == "imdb":
                from core import config as cfg_mod
                cfg     = cfg_mod.load()
                omdb_key = cfg.get("meta", {}).get("omdb_api_key", "")
                meta = fetch_imdb(title, year, omdb_key=omdb_key)
            else:
                meta = fetch_allocine(title, year)
            self.app.call_from_thread(self._show_result, meta)
        except Exception as exc:
            self.app.call_from_thread(self._show_error, str(exc))

    def _show_result(self, meta: MovieMeta) -> None:
        body = self.query_one("#meta-body", ScrollableContainer)
        body.remove_children()

        # En-tête titre + année
        header_txt = Text(meta.title, style="bold")
        if meta.year:
            header_txt.append(f"  ({meta.year})", style="dim")
        self.query_one("#meta-header", Static).update(header_txt)

        # Note
        rating_str = "—"
        if meta.rating is not None:
            rating_str = f"{meta.rating:.1f} / {meta.rating_max:.0f}"

        rows = [
            ("Type",         meta.kind),
            ("Année",        str(meta.year) if meta.year else "—"),
            ("Note",         rating_str),
            ("Genres",       ", ".join(meta.genres) if meta.genres else "—"),
            ("Réalisateur",  ", ".join(meta.directors) if meta.directors else "—"),
            ("Casting",      ", ".join(meta.cast) if meta.cast else "—"),
        ]
        for lbl, val in rows:
            body.mount(Static(lbl, classes="meta-lbl"))
            body.mount(Static(val, classes="meta-val"))

        if meta.synopsis:
            body.mount(Static("Synopsis", classes="meta-synopsis-lbl"))
            body.mount(Static(meta.synopsis, classes="meta-synopsis"))

        body.mount(Static(meta.url, id="meta-url"))

    def _show_error(self, msg: str) -> None:
        body = self.query_one("#meta-body", ScrollableContainer)
        body.remove_children()
        body.mount(Static(
            f"Impossible de récupérer les informations :\n{msg}",
            id="meta-error",
        ))
