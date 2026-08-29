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
        self.active_profile_id = "serie_basic"
        self.platform:         PlatformProfile = detect_platform()
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
            from core.platform import encodeurs_a_sonder, sonder_encodeurs
            self.platform = _dc(self.platform, encodeurs_ok=sonder_encodeurs(
                encodeurs_a_sonder(self.platform), ffmpeg_p))
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

    def on_mount(self) -> None:
        from tui.screens.browser import BrowserScreen
        self.push_screen(BrowserScreen(self.start_path, start_virtual=True))

    def action_aide(self) -> None:
        """Ouvre le guide des touches, sauf si on est en train d'écrire."""
        from textual.widgets import Input, TextArea
        from tui.screens.aide import AideScreen

        if isinstance(self.focused, (Input, TextArea)):
            return
        if isinstance(self.screen, AideScreen):
            return                       # déjà ouvert : `h` le referme
        self.push_screen(AideScreen())

    def action_request_quit(self) -> None:
        """Affiche la modal de confirmation avant de quitter."""
        from tui.screens.quit import QuitConfirmScreen
        self.push_screen(QuitConfirmScreen(), self._on_quit_answer)

    def _on_quit_answer(self, confirmed: bool) -> None:
        if confirmed:
            self.exit()

    # Surcharge de l'action native Textual (Ctrl+C système)
    def action_quit(self) -> None:
        self.action_request_quit()
