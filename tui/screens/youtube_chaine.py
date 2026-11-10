"""
tui/screens/youtube_chaine.py — Les vidéos d'une chaîne YouTube publique (IE-181).

Ouvert par `YouTubeScreen` quand l'adresse collée est celle d'une chaîne. La
liste montre ses `PAGE_CHAINE` vidéos les plus récentes (`+` : les suivantes),
lues à plat, sans compte. La définition de chaque vidéo demande de lire sa
page : un worker les lit l'une après l'autre en arrière-plan, les vidéos
cochées d'abord, et la colonne se remplit pendant qu'on coche.

Le lot partage un réglage : une définition maximale (chaque vidéo prend la
meilleure qui ne la dépasse pas) et des sous-titres, choisis parmi ceux des
vidéos cochées déjà lues, jamais cochés d'office. Les vidéos se téléchargent
l'une après l'autre ; un échec n'arrête pas les suivantes. Rend la liste des
fichiers produits — après `Échap`, ceux déjà terminés.
"""
from __future__ import annotations

import threading
from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (Button, DataTable, Label, ProgressBar, RadioButton,
                             RadioSet, SelectionList, Static)

from core import config as cfg_mod
from core import youtube
from core.i18n import N_, _, liste, ngettext, texte_erreur
from core.preflight import get_tool_path

from ..common import (cellule, colonne_fixe, fmt_duration, largeur_entete,
                      raccourcis, touche)

_COLONNES = ("check", "titre", "duree", "date", "res")


def _date(aaaammjj: str, approx: bool) -> str:
    if len(aaaammjj) != 8:
        return "—"
    d = f"{aaaammjj[:4]}-{aaaammjj[4:6]}-{aaaammjj[6:]}"
    return f"≈ {d}" if approx else d


class ChaineYouTubeScreen(ModalScreen["list[Path] | None"]):
    """Liste des vidéos d'une chaîne, cases à cocher, téléchargement en lot."""

    CSS = """
    ChaineYouTubeScreen { align: center middle; }
    #ch-box {
        background: $surface;
        border: solid $accent;
        width: 120;
        max-width: 96%;
        height: 96%;
        padding: 1 2;
    }
    #ch-title   { text-align: center; width: 100%; color: $accent; }
    #ch-state   { color: $text-muted; width: 100%; }
    #ch-table   { height: 1fr; min-height: 5; margin-top: 1; }
    .ch-section { text-style: bold; color: $accent; margin-top: 1; }
    #ch-reglages { height: auto; }
    #ch-res-bloc { width: 38; height: auto; margin-right: 2; }
    #ch-subs-bloc { width: 1fr; height: auto; }
    #ch-res     { layout: horizontal; height: auto; width: 100%; }
    #ch-subs    { height: auto; max-height: 6; }
    #ch-go      { margin-top: 1; }
    #ch-progress { margin-top: 1; }
    #ch-hint {
        color: $text-muted; width: 100%; text-align: center;
        margin-top: 1; border-top: solid $primary-darken-2; padding-top: 1;
    }
    """

    BINDINGS = [
        Binding("space",  "toggle", N_("Toggle"), show=True),
        Binding("plus",   "more",   N_("More videos"), show=True),
        Binding("escape", "cancel", N_("Cancel"), show=True, priority=True),
    ]

    def __init__(self, url: str, dossier: Path, outils: tuple[Path, Path]) -> None:
        super().__init__()
        self._url = url
        self._dossier = dossier
        self._outils = outils
        self._entrees: list[youtube.EntreeChaine] = []
        self._prochaine = 1              # rang de la première vidéo non lue
        self._suite = False
        self._charge = False             # une page en cours de lecture
        # Partagés avec le worker d'analyse : sous verrou.
        self._verrou = threading.Lock()
        self._coches: set[str] = set()
        self._videos: dict[str, youtube.Video] = {}
        self._erreurs: dict[str, str] = {}
        self._a_faire = threading.Event()
        self._subs: list[youtube.SousTitre] = []
        self._occupe = False             # un lot en cours
        self._dl: youtube.Telechargement | None = None
        self._produits: list[Path] = []
        self._ferme = False

    def compose(self) -> ComposeResult:
        with Vertical(id="ch-box"):
            yield Label(_("YouTube channel"), id="ch-title")
            yield Static(_("Reading the channel…"), id="ch-state", markup=False)
            yield DataTable(id="ch-table", cursor_type="row", zebra_stripes=True)
            # Côte à côte : la liste garde la hauteur sur un petit terminal.
            with Horizontal(id="ch-reglages"):
                with Vertical(id="ch-res-bloc"):
                    yield Static(_("Maximum resolution"), classes="ch-section")
                    with RadioSet(id="ch-res"):
                        for i, h in enumerate(youtube.PALIERS):
                            yield RadioButton(f"{h}p", value=i == 0)
                with Vertical(id="ch-subs-bloc"):
                    yield Static(_("Subtitles"), classes="ch-section",
                                 id="ch-subs-titre")
                    yield SelectionList[int](id="ch-subs")
            yield Button(_("Download"), id="ch-go", variant="primary")
            yield ProgressBar(total=100, show_eta=False, id="ch-progress")
            yield Static(raccourcis([("space", N_("Toggle")),
                                     ("plus", N_("More videos")),
                                     ("tab", N_("Next field")),
                                     ("escape", N_("Cancel"))]), id="ch-hint")

    def on_mount(self) -> None:
        self.query_one("#ch-progress").display = False
        self._montrer_subs()
        self.query_one(DataTable).focus()
        self._charger(1)
        self._analyser()

    def _colonnes(self) -> None:
        """Posées à la première page, quand la table a sa largeur : Titre
        prend la place que les autres laissent."""
        table = self.query_one(DataTable)
        fixes = [(_("Duration"), 8, "duree"), (_("Date"), 12, "date"),
                 (_("Resolution"), 10, "res")]
        autres = 5 + sum(largeur_entete(libelle, n) for libelle, n, _k in fixes)
        # Une case de marge de part et d'autre de chaque colonne ; deux pour
        # la barre de défilement.
        titre = max(20, table.size.width - autres - 2 * (len(fixes) + 2) - 2)
        table.add_column("", width=5, key="check")
        table.add_column(_("Title"), width=titre, key="titre")
        for libelle, n, cle in fixes:
            colonne_fixe(table, libelle, n, key=cle)

    def on_unmount(self) -> None:
        self._ferme = True
        self._a_faire.set()

    def _etat(self, texte: str) -> None:
        self.query_one("#ch-state", Static).update(texte)

    # ── Liste ─────────────────────────────────────────────────────────────────

    @work(thread=True, exclusive=True, name="yt-chaine")
    def _charger(self, debut: int) -> None:
        self._charge = True
        try:
            chaine = youtube.lister_chaine(self._url, *self._outils, debut=debut)
        except Exception as e:
            if not self._ferme:
                self.app.call_from_thread(self._echec_liste, texte_erreur(e))
            return
        if not self._ferme:
            self.app.call_from_thread(self._ajouter, chaine, debut)

    def _echec_liste(self, message: str) -> None:
        self._charge = False
        self._etat(message)

    def _ajouter(self, chaine: youtube.Chaine, debut: int) -> None:
        self._charge = False
        self._prochaine = debut + youtube.PAGE_CHAINE
        self._suite = chaine.suite
        if chaine.nom:
            self.query_one("#ch-title", Label).update(chaine.nom)
        connus = {e.ident for e in self._entrees}
        table = self.query_one(DataTable)
        if not table.columns:
            self._colonnes()
        for e in chaine.entrees:
            if e.ident not in connus:
                self._entrees.append(e)
                table.add_row(*self._ligne(e), key=e.ident)
        self._a_faire.set()
        if not self._entrees:
            self._etat(_("No public video on this channel."))
            return
        n = len(self._entrees)
        if self._suite:
            # TRANSLATORS: {key} is the key that lists the following videos.
            texte = ngettext("{count} video listed. {key}: the next ones.",
                             "{count} videos listed. {key}: the next ones.", n)
        else:
            texte = ngettext("{count} video listed.", "{count} videos listed.", n)
        self._etat(texte.format(count=n, key=touche("plus")))

    def _ligne(self, e: youtube.EntreeChaine) -> tuple[Text, ...]:
        with self._verrou:
            coche = e.ident in self._coches
            video = self._videos.get(e.ident)
            erreur = e.ident in self._erreurs
        if video is not None:
            res = cellule(f"{video.hauteurs[0]}p")
            date = _date(video.date, approx=False) if video.date else _date(e.date, True)
        else:
            res = cellule("✗" if erreur else "…", style="dim")
            date = _date(e.date, approx=True)
        return (
            cellule("  ✓  " if coche else "  ·  ", style="bold green" if coche else "dim"),
            cellule(e.titre),
            cellule(fmt_duration(e.duree) if e.duree else "—"),
            cellule(date),
            res,
        )

    def _rafraichir(self, ident: str) -> None:
        e = next((x for x in self._entrees if x.ident == ident), None)
        if e is None:
            return
        table = self.query_one(DataTable)
        for col, val in zip(_COLONNES, self._ligne(e)):
            table.update_cell(ident, col, val, update_width=False)

    def action_more(self) -> None:
        if self._suite and not self._charge and not self._occupe:
            self._etat(_("Reading the channel…"))
            self._charger(self._prochaine)

    def action_toggle(self) -> None:
        table = self.query_one(DataTable)
        if self._occupe or self.focused is not table:
            return
        row = table.cursor_row
        if not (0 <= row < len(self._entrees)):
            return
        ident = self._entrees[row].ident
        with self._verrou:
            self._coches.symmetric_difference_update({ident})
        self._a_faire.set()
        self._rafraichir(ident)
        self._montrer_subs()

    # ── Analyse en arrière-plan ───────────────────────────────────────────────

    def _suivante(self) -> youtube.EntreeChaine | None:
        """La prochaine vidéo à lire : une cochée d'abord, sinon dans l'ordre."""
        with self._verrou:
            faites = self._videos.keys() | self._erreurs.keys()
            restantes = [e for e in self._entrees if e.ident not in faites]
            return next((e for e in restantes if e.ident in self._coches),
                        restantes[0] if restantes else None)

    @work(thread=True, group="yt-chaine-analyse")
    def _analyser(self) -> None:
        while not self._ferme:
            entree = self._suivante()
            if entree is None:
                self._a_faire.wait(1.0)
                self._a_faire.clear()
                continue
            try:
                video = youtube.analyser(entree.url, *self._outils)
            except Exception as e:
                with self._verrou:
                    self._erreurs[entree.ident] = texte_erreur(e)
            else:
                with self._verrou:
                    self._videos[entree.ident] = video
            if self._ferme:
                return
            self.app.call_from_thread(self._analysee, entree.ident)

    def _analysee(self, ident: str) -> None:
        self._rafraichir(ident)
        with self._verrou:
            coche = ident in self._coches
        if coche:
            self._montrer_subs()

    def _montrer_subs(self) -> None:
        """Les sous-titres des vidéos cochées déjà lues ; les choix faits
        restent cochés."""
        liste_subs = self.query_one("#ch-subs", SelectionList)
        gardes = {(self._subs[i].cle, self._subs[i].auto)
                  for i in liste_subs.selected if i < len(self._subs)}
        with self._verrou:
            videos = [self._videos[e.ident] for e in self._entrees
                      if e.ident in self._coches and e.ident in self._videos]
        subs = youtube.sous_titres_communs(videos)
        if subs != self._subs:
            self._subs = subs
            liste_subs.clear_options()
            for i, s in enumerate(subs):
                libelle = f"{s.langue} — {s.nom}"
                if s.auto:
                    libelle += " " + _("(auto-generated)")
                liste_subs.add_option((libelle, i))
                if (s.cle, s.auto) in gardes:
                    liste_subs.select(i)
        self.query_one("#ch-subs-titre").display = bool(subs)
        liste_subs.display = bool(subs)

    # ── Téléchargement ────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "ch-go" or self._occupe:
            return
        with self._verrou:
            choisies = [e for e in self._entrees if e.ident in self._coches]
        if not choisies:
            self._etat(_("Check at least one video."))
            return
        radios = self.query_one("#ch-res", RadioSet)
        rang = radios.pressed_index if radios.pressed_index >= 0 else 0
        plafond = youtube.PALIERS[rang]
        liste_subs = self.query_one("#ch-subs", SelectionList)
        subs = [self._subs[i] for i in sorted(liste_subs.selected)]
        ffmpeg = get_tool_path("ffmpeg", cfg_mod.get_bin_dir(self.app.cfg))
        if ffmpeg is None:
            self._etat(_("ffmpeg is missing."))
            return
        self._occupe = True
        barre = self.query_one("#ch-progress", ProgressBar)
        barre.update(progress=0)
        barre.display = True
        self._telecharger(choisies, plafond, subs, ffmpeg)

    @work(thread=True, exclusive=True, name="yt-lot")
    def _telecharger(self, choisies: list[youtube.EntreeChaine], plafond: int,
                     subs: list[youtube.SousTitre], ffmpeg: str) -> None:
        echecs: list[tuple[str, str]] = []
        total = len(choisies)
        for rang, entree in enumerate(choisies):
            if self._ferme:
                return
            self.app.call_from_thread(self._etat, _(
                "Video {n} of {total}: {title}").format(
                    n=rang + 1, total=total, title=entree.titre))
            try:
                with self._verrou:
                    video = self._videos.get(entree.ident)
                if video is None:
                    video = youtube.analyser(entree.url, *self._outils)
                    with self._verrou:
                        self._videos[entree.ident] = video
                cmd = youtube.commande(
                    *self._outils, ffmpeg, video, video.hauteur_sous(plafond),
                    youtube.sous_titres_retenus(video, subs), self._dossier)
                dl = self._dl = youtube.Telechargement()
                if self._ferme:
                    return

                def _progres(part: float, rang: int = rang) -> None:
                    if not self._ferme:
                        self.app.call_from_thread(
                            self.query_one("#ch-progress", ProgressBar).update,
                            progress=(rang + part) / total * 100)

                chemin = dl.lancer(cmd, video, self._dossier, _progres)
            except Exception as e:
                if self._ferme:
                    return
                echecs.append((entree.titre, texte_erreur(e)))
                continue
            if chemin is None:          # arrêté par `Échap`
                return
            self._produits.append(chemin)
        if not self._ferme:
            self.app.call_from_thread(self._fin_lot, echecs)

    def _fin_lot(self, echecs: list[tuple[str, str]]) -> None:
        self._occupe = False
        self._dl = None
        self.query_one("#ch-progress").display = False
        if len(echecs) == 1:
            titre, raison = echecs[0]
            self.notify(_("Not downloaded: {title}. {error}").format(
                title=titre, error=raison), severity="warning", timeout=12)
        elif echecs:
            self.notify(ngettext(
                "{count} video not downloaded: {titles}. First error: {error}",
                "{count} videos not downloaded: {titles}. First error: {error}",
                len(echecs)).format(count=len(echecs),
                                    titles=liste(t for t, _r in echecs),
                                    error=echecs[0][1]),
                severity="warning", timeout=12)
        if self._produits:
            self.dismiss(list(self._produits))
        elif echecs:
            self._etat(echecs[0][1])

    def action_cancel(self) -> None:
        self._ferme = True
        self._a_faire.set()
        if self._dl is not None:
            # Le worker voit l'arrêt, nettoie, et ne rend rien.
            self._dl.annuler()
        self.dismiss(list(self._produits) or None)
