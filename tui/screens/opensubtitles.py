"""
tui/screens/opensubtitles.py — Choix d'un sous-titre sur OpenSubtitles.com.

Ouvert par `O` depuis le choix du fichier donneur (F9). Rend le `.srt`
téléchargé, que le donneur reprend comme s'il l'avait choisi sur le disque :
pistes, langue, recalage — rien ne change en aval.

Les appels réseau tournent dans un worker ; l'écran reste pilotable pendant
ce temps, et `Esc` l'abandonne.
"""
from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import DataTable, Label, Static

from ..common import colonne_fixe, raccourcis

from core.texte import pluriel
from core.opensubtitles import Client, ErreurOpenSubtitles, Resultat


def _client(cfg: dict) -> Client:
    from version import __version__
    os_cfg = cfg.get("opensubtitles", {})
    return Client(os_cfg.get("api_key", ""), os_cfg.get("username", ""),
                  os_cfg.get("password", ""), f"IRIS Encode v{__version__}")


class OpenSubtitlesScreen(ModalScreen["Path | None"]):
    """Résultats de recherche ; `Enter` télécharge la ligne et referme."""

    CSS = """
    OpenSubtitlesScreen { align: center middle; }
    #os-box {
        background: $surface;
        border: solid $accent;
        width: 110;
        max-width: 96%;
        height: 28;
        padding: 1 2;
    }
    #os-title  { text-align: center; width: 100%; color: $accent; }
    #os-state  { color: $text-muted; width: 100%; margin-bottom: 1; }
    #os-table  { height: 1fr; }
    #os-hint   { color: $text-muted; width: 100%; text-align: center; margin-top: 1; }
    """

    BINDINGS = [
        Binding("enter",     "download", "Télécharger", show=True, priority=True),
        Binding("escape",    "cancel",   "Annuler",     show=True, priority=True),
        Binding("backspace", "cancel",   "Retour",      show=False, priority=True),
    ]

    def __init__(self, video: Path, langues: list[str]) -> None:
        super().__init__()
        self._video     = video
        self._langues   = langues
        self._resultats: list[Resultat] = []
        self._occupe    = True
        self._client: Client | None = None

    def compose(self) -> ComposeResult:
        with Static(id="os-box"):
            yield Label("OpenSubtitles.com", id="os-title")
            yield Static("", id="os-state", markup=False)
            yield DataTable(id="os-table", cursor_type="row", zebra_stripes=True)
            yield Static(raccourcis([("enter", "Télécharger"),
                                     ("escape", "Annuler")]), id="os-hint")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        # ≡ : déposé pour cette release exacte, donc déjà synchronisé.
        table.add_column("",        width=3,  key="hash")
        colonne_fixe(table, "Langue",  7,  key="lang")
        colonne_fixe(table, "Téléch.", 8,  key="count")
        colonne_fixe(table, "SME",     4,  key="hi")
        table.add_column("Release", width=None, key="release")
        self._etat(f"Recherche pour {self._video.name}…")
        self._chercher()
        table.focus()

    def _etat(self, texte: str) -> None:
        self.query_one("#os-state", Static).update(texte)

    # ── Recherche ─────────────────────────────────────────────────────────────

    @work(thread=True, exclusive=True, name="os-search")
    def _chercher(self) -> None:
        try:
            self._client = _client(self.app.cfg)
            res = self._client.chercher(self._video, self._langues)
            self.app.call_from_thread(self._afficher, res)
        except ErreurOpenSubtitles as e:
            self.app.call_from_thread(self._echec, str(e))

    def _afficher(self, resultats: list[Resultat]) -> None:
        self._occupe    = False
        self._resultats = resultats
        table = self.query_one(DataTable)
        table.clear()
        for i, r in enumerate(resultats):
            table.add_row(
                Text("≡" if r.empreinte else "", style="bold green"),
                Text(r.langue),
                Text(str(r.telechargements), style="dim"),
                Text("oui" if r.malentendants else "", style="dim"),
                Text(r.release, no_wrap=True, overflow="ellipsis"),
                key=str(i),
            )
        exacts = sum(r.empreinte for r in resultats)
        if not resultats:
            self._etat("Aucun sous-titre trouvé dans les langues du profil.")
        else:
            self._etat(f"{pluriel(len(resultats), 'résultat')}, dont {exacts} pour cette "
                       f"release exacte (≡, déjà synchronisés).")

    def _echec(self, message: str) -> None:
        self._occupe = False
        self._etat(message)

    # ── Téléchargement ────────────────────────────────────────────────────────

    def action_download(self) -> None:
        row = self.query_one(DataTable).cursor_row
        if self._occupe or not (0 <= row < len(self._resultats)):
            return
        self._occupe = True
        self._etat("Téléchargement…")
        self._telecharger(self._resultats[row])

    @work(thread=True, exclusive=True, name="os-download")
    def _telecharger(self, resultat: Resultat) -> None:
        try:
            chemin, restant = self._client.telecharger(resultat, self._video)
            self.app.call_from_thread(self._fini, chemin, restant)
        except ErreurOpenSubtitles as e:
            self.app.call_from_thread(self._echec, str(e))

    def _fini(self, chemin: Path, restant) -> None:
        if restant is not None:
            self.app.notify(f"Sous-titre téléchargé — {pluriel(restant, 'restant')} aujourd'hui.")
        self.dismiss(chemin)

    def action_cancel(self) -> None:
        self.dismiss(None)
