"""
tui/app.py — Application Textual principale IRIS ENCODE.

Point d'entrée TUI. Maintient l'état global (profils, config, platform).
"""
from __future__ import annotations

import logging
from pathlib import Path

from textual.app import App
from textual.binding import Binding

import core.config as cfg_mod
import core.profiles as prof_mod
from core.platform import PlatformProfile, detect as detect_platform
from version import __version__


def _setup_logging() -> None:
    """Logge dans iris_encode.log à côté du dossier de l'app (warnings et +)."""
    log_path = Path.home() / ".iris_encode" / "iris_encode.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_path),
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


class IrisEncodeApp(App):
    """Application principale IRIS ENCODE."""

    TITLE     = "IRIS ENCODE"
    SUB_TITLE = f"v{__version__}"

    # CSS global — styles communs à tous les écrans (évite la duplication
    # des barres de statut dans chaque DEFAULT_CSS d'écran).
    CSS = """
    Screen { background: $surface; }
    /* Sans cette ligne, la règle ci-dessus s'applique aussi aux modales — elles
       héritent de Screen — et écrase la translucidité que Textual leur donne
       par défaut. L'écran d'origine disparaissait alors entièrement : il ne
       restait qu'une boîte au milieu du vide, au moment précis où l'on veut
       voir sur quoi le choix porte. */
    ModalScreen { background: $background 40%; }
    Header { background: $primary; }
    Footer { background: $primary-darken-2; }
    .status-bar {
        height: 1;
        background: $accent;
        color: $text;
        padding: 0 2;
    }
    """

    BINDINGS = [
        Binding("f10",    "request_quit", "F10 Quitter", show=True,  priority=True),
        Binding("ctrl+c", "request_quit", "Quitter",     show=False, priority=True),
        # `H` sans `priority` : une liaison prioritaire au niveau de
        # l'application passe **avant** le widget focalisé, et taper « h » dans
        # un nom de profil ouvrirait le guide au lieu d'écrire la lettre.
        # Sans priorité, la touche descend d'abord au champ de saisie, qui la
        # consomme ; ailleurs elle remonte jusqu'ici. `action_aide` refuse en
        # plus d'agir quand une saisie a le focus — ceinture et bretelles, le
        # coût d'une erreur étant un texte corrompu sans message.
        Binding("h",      "aide",         "Aide",        show=False),
    ]

    def __init__(self, start_path: Path | None = None) -> None:
        super().__init__()
        _setup_logging()
        self.start_path        = (start_path or Path.cwd()).resolve()
        self.cfg               = cfg_mod.load()
        self.profiles          = prof_mod.load_all()
        # Le profil retenu au dernier lancement, ou le premier du fichier.
        # On écrit l'attribut privé : passer par la propriété réécrirait
        # config.toml à chaque démarrage pour y remettre la même valeur.
        self._active_profile_id = cfg_mod.get_active_profile(
            self.cfg, self.profiles
        )
        self.platform:         PlatformProfile = detect_platform()
        # Les lots passés par l'écran d'encodage, que l'accueil n'a pas encore
        # pris en compte : il les relit à son retour au premier plan (UX-04).
        self.lots_encodes:     list[list] = []
        # Câble dovi_tool dans le scanner (enrichissement DV au scan)
        from core import dovi, scanner
        bin_dir   = cfg_mod.get_bin_dir(self.cfg)
        dovi_path = dovi.get_path(bin_dir)
        if dovi_path is not None:
            scanner.set_dovi_path(dovi_path)
        # Précise le chemin ffmpeg utilisé pour le probing DV
        from core.preflight import get_tool_path
        # ffprobe est appelé à chaque scan : sans ce câblage, une installation
        # où le preflight a posé les binaires dans ./bin/ écarte tous les
        # fichiers comme illisibles.
        ffprobe_p = get_tool_path("ffprobe", bin_dir)
        if ffprobe_p:
            scanner.set_ffprobe_path(ffprobe_p)
        ffmpeg_p = get_tool_path("ffmpeg", bin_dir)
        if ffmpeg_p:
            from core import encoder as encoder_mod
            encoder_mod.set_ffmpeg_path(ffmpeg_p)
            # Quels encodeurs cette machine sait réellement ouvrir. La
            # détection par le modèle de carte ment : NVENC n'encode l'AV1
            # qu'à partir d'Ada, et une carte antérieure ne le dit qu'au
            # moment d'échouer. ~0,7 s, en parallèle.
            from dataclasses import replace as _dc
            from core.platform import (alerte_pilote_nvenc, encodeurs_a_sonder,
                                       sonder_encodeurs)
            refus: dict[str, str] = {}
            ok = sonder_encodeurs(encodeurs_a_sonder(self.platform), ffmpeg_p,
                                  refus)
            # Un ffmpeg plus récent que le pilote perd tout NVENC sans le dire
            # ailleurs que dans sa sortie d'erreur : on la lit ici.
            alerte = next(filter(None, (alerte_pilote_nvenc(err)
                                        for err in refus.values())), None)
            self.platform = _dc(self.platform, encodeurs_ok=ok,
                                alerte_nvenc=alerte)
            from core import sync as sync_mod
            sync_mod.set_ffmpeg_path(ffmpeg_p)
        # Câble mkvmerge pour la greffe de pistes externes (optionnel)
        from core import muxer
        mkvmerge_p = get_tool_path("mkvmerge", bin_dir)
        self.mkvmerge_available = mkvmerge_p is not None
        if mkvmerge_p:
            muxer.set_mkvmerge_path(mkvmerge_p)
        # Retrait du RPU Dolby Vision sans réencodage : il faut les deux outils.
        from core import decision as decision_mod
        self.dovi_path   = dovi_path
        self.ffmpeg_path = ffmpeg_p or "ffmpeg"
        decision_mod.set_strip_dv_available(
            dovi_path is not None and mkvmerge_p is not None)
        # L'assistant est le mode d'entrée : un fichier, une suite d'étapes.
        # Le parcours libre reste à une touche (F12), et le choix tient pour
        # la session — on ne le repose pas à chaque fichier.
        self.wizard_mode = True
        # Câble mpv pour le contrôle du recalage à l'œil (optionnel)
        from core import preview as preview_mod
        preview_mod.set_mpv_path(get_tool_path("mpv", bin_dir))

    # ── Profil actif ──────────────────────────────────────────────────────────
    #
    # Trois écrans le changent : le sélecteur (`F4`), l'activation depuis la
    # liste des profils, et l'enregistrement d'un profil. Une propriété tient
    # la persistance en un seul endroit — sinon chacun devrait penser à écrire
    # config.toml, et celui qu'on oublie est celui qui perd le réglage.

    @property
    def active_profile_id(self) -> str:
        return self._active_profile_id

    @active_profile_id.setter
    def active_profile_id(self, profile_id: str) -> None:
        if profile_id == self._active_profile_id:
            return                      # rien à écrire
        self._active_profile_id = profile_id
        cfg_mod.set_active_profile(self.cfg, profile_id)

    def on_mount(self) -> None:
        from tui.screens.browser import BrowserScreen
        self.push_screen(BrowserScreen(self.start_path, start_virtual=True))
        if self.platform.alerte_nvenc:
            self.notify(self.platform.alerte_nvenc, title="Carte graphique",
                        severity="warning", timeout=30)

    def action_aide(self) -> None:
        """Ouvre le guide des touches, sauf si on est en train d'écrire."""
        from textual.widgets import Input, TextArea
        from tui.screens.aide import AideScreen

        if isinstance(self.focused, (Input, TextArea)):
            return
        if isinstance(self.screen, AideScreen):
            return                       # déjà ouvert : `h` le referme
        self.push_screen(AideScreen())

    # Worker en cours → ce que quitter lui fait. Les autres (scan, recherches)
    # ne produisent rien qu'on perdrait.
    _TRAVAUX = {
        "encoder":       "L'encodage en cours sera arrêté, sa sortie partielle effacée.",
        "muxer":         "Le mux en cours sera arrêté, sa sortie partielle effacée.",
        "joiner":        "La jonction en cours sera arrêtée, sa sortie partielle effacée.",
        "sync-measure":  "La mesure en cours sera perdue.",
        "sync-ancrage":  "La mesure en cours sera perdue.",
        "wizard-mesure": "La mesure en cours sera perdue.",
        "sync-retime":   "Le recalage en cours sera perdu.",
    }

    def travaux_en_cours(self) -> list[str]:
        """Les phrases de `_TRAVAUX` des workers qui tournent, sans doublon."""
        phrases: list[str] = []
        for w in self.workers:
            texte = self._TRAVAUX.get(w.name or "")
            if w.is_running and texte and texte not in phrases:
                phrases.append(texte)
        return phrases

    def action_request_quit(self) -> None:
        """Affiche la modal de confirmation avant de quitter."""
        from tui.screens.quit import QuitConfirmScreen
        self.push_screen(QuitConfirmScreen(self.travaux_en_cours()),
                         self._on_quit_answer)

    def _on_quit_answer(self, confirmed: bool) -> None:
        if confirmed:
            # Tenir la promesse du message : un processus lancé par l'écran
            # survivrait à l'application et continuerait d'écrire.
            for ecran in self.screen_stack:
                arreter = getattr(ecran, "_interrompre", None)
                if arreter is not None:
                    arreter()
            self.exit()

    # Surcharge de l'action native Textual (Ctrl+C système)
    def action_quit(self) -> None:
        self.action_request_quit()
