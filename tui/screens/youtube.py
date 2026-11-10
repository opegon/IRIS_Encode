"""
tui/screens/youtube.py — Télécharger une vidéo YouTube (IE-180).

Ouvert par `U` depuis l'accueil. On colle l'adresse de la vidéo, `Entrée` la
fait lire par yt-dlp ; on choisit la définition parmi celles qu'elle propose
et les sous-titres (déposés, ou générés automatiquement — marqués comme tels,
et jamais cochés d'office), puis « Télécharger ». Rend les fichiers produits :
l'accueil ouvre leur dossier et les coche, prêts pour la file.

L'adresse d'une chaîne ouvre la liste de ses vidéos (`ChaineYouTubeScreen`,
IE-181), dont on télécharge plusieurs d'un coup.

Les appels à yt-dlp tournent dans un worker ; `Échap` arrête le téléchargement
en cours et retire ses fichiers partiels.
"""
from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import (Button, Input, Label, ProgressBar, RadioButton,
                             RadioSet, SelectionList, Static)

from core import config as cfg_mod
from core import youtube
from core.i18n import N_, _, texte_erreur
from core.preflight import get_tool_path

from ..common import fmt_duration, raccourcis


class YouTubeScreen(ModalScreen["list[Path] | None"]):
    """Adresse, puis définition et sous-titres, puis téléchargement."""

    CSS = """
    YouTubeScreen { align: center middle; }
    #yt-box {
        background: $surface;
        border: solid $accent;
        width: 90;
        max-width: 96%;
        height: auto;
        max-height: 100%;
        overflow-y: auto;
        padding: 1 2;
    }
    #yt-title   { text-align: center; width: 100%; color: $accent; }
    #yt-url     { margin: 1 0; }
    #yt-state   { color: $text-muted; width: 100%; }
    #yt-video   { width: 100%; text-style: bold; margin-top: 1; }
    .yt-section { text-style: bold; color: $accent; margin-top: 1; }
    #yt-subs    { height: auto; max-height: 10; }
    #yt-go      { margin-top: 1; }
    #yt-progress { margin-top: 1; }
    .yt-note    { color: $text-muted; width: 100%; margin-top: 1; }
    #yt-hint {
        color: $text-muted; width: 100%; text-align: center;
        margin-top: 1; border-top: solid $primary-darken-2; padding-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", N_("Cancel"), show=True, priority=True),
    ]

    def __init__(self, dossier: Path) -> None:
        super().__init__()
        self._dossier = dossier
        self._video: youtube.Video | None = None
        self._dl: youtube.Telechargement | None = None
        self._occupe = False
        # Refermé par `Échap` pendant qu'un worker tourne encore.
        self._ferme = False

    def compose(self) -> ComposeResult:
        with Vertical(id="yt-box"):
            yield Label(_("Download from YouTube"), id="yt-title")
            yield Input(placeholder="https://www.youtube.com/watch?v=…", id="yt-url")
            yield Static(_("Paste the address of a video or of a channel, "
                           "then press {key}.").format(
                key="↵"), id="yt-state", markup=False)
            yield Static("", id="yt-video", markup=False)
            yield Static(_("Resolution"), classes="yt-section", id="yt-res-titre")
            yield RadioSet(id="yt-res")
            yield Static(_("Subtitles"), classes="yt-section", id="yt-subs-titre")
            yield SelectionList[int](id="yt-subs")
            yield Button(_("Download"), id="yt-go", variant="primary")
            yield ProgressBar(total=100, show_eta=False, id="yt-progress")
            yield Static(_("Saved to {folder}").format(folder=self._dossier),
                         classes="yt-note", markup=False)
            yield Static(raccourcis([("tab", N_("Next field")),
                                     ("space", N_("Toggle")),
                                     ("escape", N_("Cancel"))]), id="yt-hint")

    def on_mount(self) -> None:
        self._montrer_choix(False)
        self.query_one("#yt-progress").display = False
        self.query_one("#yt-url", Input).focus()

    def _etat(self, texte: str) -> None:
        self.query_one("#yt-state", Static).update(texte)

    def _montrer_choix(self, visible: bool) -> None:
        for wid in ("#yt-video", "#yt-res-titre", "#yt-res", "#yt-subs-titre",
                    "#yt-subs", "#yt-go"):
            self.query_one(wid).display = visible

    # ── Lecture de la page ────────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        url = event.value.strip()
        if self._occupe or not url:
            return
        outils = youtube.outils(cfg_mod.get_bin_dir(self.app.cfg))
        if outils is None:
            self._etat(_("yt-dlp or Deno is missing: restart IRIS ENCODE and "
                         "accept their installation."))
            return
        chaine = youtube.url_chaine(url)
        if chaine is not None:
            from .youtube_chaine import ChaineYouTubeScreen

            def _retour(produits: list[Path] | None) -> None:
                if produits:
                    self.dismiss(produits)

            self.app.push_screen(ChaineYouTubeScreen(chaine, self._dossier, outils),
                                 _retour)
            return
        self._occupe = True
        self._montrer_choix(False)
        self._etat(_("Reading the video page…"))
        self._analyser(url, *outils)

    @work(thread=True, exclusive=True, name="yt-analyse")
    def _analyser(self, url: str, ytdlp: Path, deno: Path) -> None:
        try:
            video = youtube.analyser(url, ytdlp, deno)
        except Exception as e:
            if not self._ferme:
                self.app.call_from_thread(self._echec, texte_erreur(e))
            return
        if not self._ferme:
            self.app.call_from_thread(self._afficher, video)

    def _afficher(self, video: youtube.Video) -> None:
        self._occupe = False
        self._video = video
        duree = fmt_duration(video.duree) if video.duree else "—"
        self.query_one("#yt-video", Static).update(f"{video.titre} — {duree}")
        radios = self.query_one("#yt-res", RadioSet)
        radios.remove_children()
        radios.mount_all(RadioButton(f"{h}p", value=i == 0)
                         for i, h in enumerate(video.hauteurs))
        subs = self.query_one("#yt-subs", SelectionList)
        subs.clear_options()
        for i, s in enumerate(video.sous_titres):
            libelle = f"{s.langue} — {s.nom}"
            if s.auto:
                # TRANSLATORS: after one subtitle track's language and name:
                # made by YouTube's speech recognition.
                libelle += " " + _("(auto-generated)")
            subs.add_option((libelle, i))
        self._montrer_choix(True)
        self.query_one("#yt-subs-titre").display = bool(video.sous_titres)
        subs.display = bool(video.sous_titres)
        if not video.audio_aac:
            self._etat(_("No AAC audio for this video: the best available "
                         "audio will be downloaded."))
        else:
            self._etat(_("Choose the resolution and the subtitles, then "
                         "Download."))
        radios.focus()

    def _echec(self, message: str) -> None:
        self._occupe = False
        self._dl = None
        self.query_one("#yt-progress").display = False
        self._etat(message)

    # ── Téléchargement ────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "yt-go" or self._occupe or self._video is None:
            return
        video = self._video
        radios = self.query_one("#yt-res", RadioSet)
        rang = radios.pressed_index if radios.pressed_index >= 0 else 0
        hauteur = video.hauteurs[rang]
        coches = self.query_one("#yt-subs", SelectionList).selected
        sous_titres = [video.sous_titres[i] for i in sorted(coches)]
        bin_dir = cfg_mod.get_bin_dir(self.app.cfg)
        outils = youtube.outils(bin_dir)
        ffmpeg = get_tool_path("ffmpeg", bin_dir)
        if outils is None or ffmpeg is None:
            self._etat(_("yt-dlp or Deno is missing: restart IRIS ENCODE and "
                         "accept their installation."))
            return
        cmd = youtube.commande(*outils, ffmpeg, video, hauteur, sous_titres,
                               self._dossier)
        self._occupe = True
        self._dl = youtube.Telechargement()
        barre = self.query_one("#yt-progress", ProgressBar)
        barre.update(progress=0)
        barre.display = True
        self._etat(_("Downloading…"))
        self._telecharger(self._dl, cmd, video)

    @work(thread=True, exclusive=True, name="yt-download")
    def _telecharger(self, dl: youtube.Telechargement, cmd: list[str],
                     video: youtube.Video) -> None:
        # Après `Échap`, l'écran est refermé : plus rien ne s'y écrit.
        def _progres(part: float) -> None:
            if not dl.annule:
                self.app.call_from_thread(
                    self.query_one("#yt-progress", ProgressBar).update,
                    progress=part * 100)
        try:
            chemin = dl.lancer(cmd, video, self._dossier, _progres)
        except Exception as e:
            if not dl.annule:
                self.app.call_from_thread(self._echec, texte_erreur(e))
            return
        if chemin is not None:
            self.app.call_from_thread(self.dismiss, [chemin])

    def action_cancel(self) -> None:
        self._ferme = True
        if self._dl is not None:
            # Le worker voit l'arrêt, nettoie, et ne rend rien.
            self._dl.annuler()
        self.dismiss(None)
