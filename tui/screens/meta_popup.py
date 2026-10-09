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

from core.i18n import N_, _, ngettext, texte_erreur
from core.meta import (Correspondance, MovieMeta, Nature, fetch_allocine,
                       fetch_imdb, parse_title)


_LIBELLES = {"allocine": "AlloCiné", "imdb": "IMDB"}

LIBELLES_NATURE: dict[Nature, str] = {
    Nature.FILM:       N_("Movie"),
    Nature.SERIE:      N_("Series"),
    Nature.MINI_SERIE: N_("Miniseries"),
    Nature.TELEFILM:   N_("TV movie"),
    Nature.EPISODE:    N_("Episode"),
}

LIBELLES_CORRESPONDANCE: dict[Correspondance, str] = {
    Correspondance.TITRE_ET_ANNEE: N_("title and year"),
    Correspondance.TITRE:          N_("title"),
    Correspondance.INCERTAINE:     N_("uncertain — the title does not match"),
}


def ligne_correspondance(c: Correspondance) -> Text:
    """Le libellé de la correspondance, en alerte quand elle est incertaine."""
    return Text(_(LIBELLES_CORRESPONDANCE[c]),
                style="bold dark_orange" if c is Correspondance.INCERTAINE else "")


class MetaPopup(ModalScreen):
    """Fiche AlloCiné ou IMDB d'un fichier (`I` sur l'accueil), `Tab` bascule."""

    BINDINGS = [
        Binding("escape", "dismiss",        N_("Close"),  show=True),
        Binding("i",      "dismiss",        N_("Close"),  show=False),
        # `priority` : sans elle, Tab déplace le focus au lieu de basculer.
        Binding("tab",    "changer_source", N_("Switch source"), show=False,
                priority=True),
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
    .meta-loading {
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
        self._epoque = 0       # une réponse d'avant la bascule est jetée

    def compose(self) -> ComposeResult:
        with Vertical(id="meta-panel"):
            yield Static("", id="meta-header")
            yield ScrollableContainer(id="meta-body")
            yield Static("", id="meta-hint")

    def on_mount(self) -> None:
        self._charger()

    def _autre_source(self) -> str:
        return "imdb" if self._source == "allocine" else "allocine"

    def _charger(self) -> None:
        self._epoque += 1
        title, year = parse_title(self._path)
        query = f"{title}" + (f" ({year})" if year else "")
        # En `Text` : les crochets d'un nom (« [Final Cut] ») étaient lus
        # comme des balises, et l'en-tête ne montrait pas la recherche
        # réellement envoyée (CR-101).
        entete = Text(f"{_LIBELLES[self._source]} — ", style="bold")
        entete.append(query)
        self.query_one("#meta-header", Static).update(entete)
        self.query_one("#meta-hint", Static).update(raccourcis(
            [("tab", _LIBELLES[self._autre_source()]), ("escape", N_("Close"))]))
        body = self.query_one("#meta-body", ScrollableContainer)
        body.remove_children()
        body.mount(LoadingIndicator(classes="meta-loading"))
        self._fetch(title, year, self._epoque)

    def action_changer_source(self) -> None:
        self._source = self._autre_source()
        self._charger()

    @work(thread=True, name="meta-fetch")
    def _fetch(self, title: str, year, epoque: int) -> None:
        try:
            if self._source == "imdb":
                from core import config as cfg_mod
                cfg     = cfg_mod.load()
                omdb_key = cfg.get("meta", {}).get("omdb_api_key", "")
                meta = fetch_imdb(title, year, omdb_key=omdb_key)
            else:
                meta = fetch_allocine(title, year)
            self.app.call_from_thread(self._show_result, meta, epoque)
        except Exception as exc:
            self.app.call_from_thread(self._show_error, texte_erreur(exc), epoque)

    def _show_result(self, meta: MovieMeta, epoque: int) -> None:
        if epoque != self._epoque:
            return
        body = self.query_one("#meta-body", ScrollableContainer)
        body.remove_children()

        # En-tête source + titre + année
        header_txt = Text(f"{_LIBELLES[self._source]} — ", style="bold")
        header_txt.append(meta.title, style="bold")
        if meta.year:
            header_txt.append(f"  ({meta.year})", style="dim")
        self.query_one("#meta-header", Static).update(header_txt)

        # Note
        rating_str = "—"
        if meta.rating is not None:
            rating_str = f"{meta.rating:.1f} / {meta.rating_max:.0f}"

        # Le choix parmi les résultats peut se tromper : on dit sur quoi il
        # repose, et le lien en bas de fiche permet de vérifier (UX-24).
        if meta.confiance:
            body.mount(Static(_("Match"), classes="meta-lbl"))
            body.mount(Static(ligne_correspondance(meta.confiance),
                              classes="meta-val"))

        rows = [
            (_("Type"),      _(LIBELLES_NATURE[meta.kind])),
            (_("Year"),      str(meta.year) if meta.year else "—"),
            (_("Rating"),    rating_str),
            (_("Genres"),    ", ".join(meta.genres) if meta.genres else "—"),
            # Le libellé s'accorde au nombre de noms (L-71).
            (ngettext("Director", "Directors", len(meta.directors)),
             ", ".join(meta.directors) if meta.directors else "—"),
            (_("Cast"),      ", ".join(meta.cast) if meta.cast else "—"),
        ]
        for lbl, val in rows:
            body.mount(Static(lbl, classes="meta-lbl"))
            body.mount(Static(val, classes="meta-val"))

        if meta.synopsis:
            body.mount(Static(_("Synopsis"), classes="meta-synopsis-lbl"))
            body.mount(Static(meta.synopsis, classes="meta-synopsis"))

        body.mount(Static(meta.url, id="meta-url"))

    def _show_error(self, msg: str, epoque: int) -> None:
        if epoque != self._epoque:
            return
        body = self.query_one("#meta-body", ScrollableContainer)
        body.remove_children()
        body.mount(Static(
            _("Cannot fetch the information:") + f"\n{msg}",
            id="meta-error",
        ))
