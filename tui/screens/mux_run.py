"""
tui/screens/mux_run.py — Exécution du mux mkvmerge avec progression.

Opération immédiate sur un seul fichier : mkvmerge réécrit le conteneur
entier (copie disque), d'où la barre de progression plutôt qu'un flash.
Chemin d'exécution distinct de la file d'encodage.
"""
from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Header, Label, ProgressBar, Static

from core.decision import FileDecision
from core.muxer import MuxProcess, build_mux_command, mux_output_path

from ..common import footer_line2
from ..widgets.footer import TwoLineFooter


class MuxScreen(Screen[bool]):
    """Lance mkvmerge et suit sa progression."""

    BINDINGS = [
        Binding("backspace", "go_back", "Retour", show=True),
        Binding("escape",    "go_back", "Retour", show=False, priority=True),
    ]

    DEFAULT_CSS = """
    MuxScreen { layout: vertical; }
    #mux-body {
        height: 1fr;
        padding: 1 2;
        layout: vertical;
    }
    #mux-out    { color: $text; height: 2; }
    #mux-bar-row {
        height: 2;
        layout: horizontal;
    }
    #mux-label  { width: 12; }
    #mux-bar    { width: 1fr; }
    #mux-state  { height: 2; }
    #mux-cmd {
        height: 1fr;
        color: $text-muted;
        border-top: solid $primary;
        padding-top: 1;
    }
    """

    def __init__(self, decision: FileDecision) -> None:
        super().__init__()
        self._decision = decision
        self._source   = decision.info.path
        self._tracks   = list(decision.external_tracks)
        self._output   = mux_output_path(self._source)
        self._process: MuxProcess | None = None
        self._done     = False
        self._ok       = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="status-bar", classes="status-bar")
        with Static(id="mux-body"):
            yield Static("", id="mux-out")
            with Static(id="mux-bar-row"):
                yield Label("Mux", id="mux-label")
                yield ProgressBar(total=100, show_eta=False, id="mux-bar")
            yield Static("", id="mux-state")
            yield Static("", id="mux-cmd")
        yield TwoLineFooter(
            line1=[("backspace", "Retour")],
            line2=footer_line2(nav=False),
        )

    def on_mount(self) -> None:
        self.query_one("#status-bar", Static).update(
            f" Mux — {self._source.name} ── {len(self._tracks)} piste(s) greffée(s)"
        )
        self.query_one("#mux-out", Static).update(f"Sortie : {self._output.name}")
        self._run()

    # ── Exécution ─────────────────────────────────────────────────────────────

    def _set(self, widget_id: str, text: str) -> None:
        try:
            self.query_one(widget_id, Static).update(text)
        except Exception:
            pass

    def _set_progress(self, pct: int) -> None:
        try:
            self.query_one("#mux-bar", ProgressBar).progress = pct
        except Exception:
            pass

    @work(thread=True, name="muxer")
    def _run(self) -> None:
        try:
            cmd = build_mux_command(self._source, self._tracks, self._output)
        except ValueError as e:
            self._done = True
            self.app.call_from_thread(
                self._set, "#mux-state", f"✗ {e}")
            return

        self.app.call_from_thread(self._set, "#mux-cmd", " ".join(cmd))
        self.app.call_from_thread(
            self._set, "#mux-state", "▶ Mux lancé — copie du conteneur en cours…")

        proc = MuxProcess(cmd)
        self._process = proc
        proc.start()

        for line, pct in proc.iter_progress():
            if pct is not None:
                self.app.call_from_thread(self._set_progress, pct)
                self.app.call_from_thread(self._set, "#mux-state", f"▶ Mux — {pct}%")

        rc         = proc.wait()
        self._ok   = rc == 0
        self._done = True
        self._process = None

        if self._ok:
            self.app.call_from_thread(self._set_progress, 100)
            self.app.call_from_thread(self._adopt_output)
        else:
            detail = proc.errors[0] if proc.errors else f"code {rc}"
            self.app.call_from_thread(
                self._set, "#mux-state", f"✗ Échec du mux : {detail}")

    def _adopt_output(self) -> None:
        """
        Bascule la décision sur le fichier muxé.

        Sans ça, tout ce qui suit (dry-run, encodage) continuerait à viser le
        fichier d'origine : on aurait greffé des pistes pour rien.
        Les pistes externes sont vidées — elles font désormais partie du fichier.
        """
        from core.decision import decide
        from core import scanner

        try:
            new_info = scanner.scan(self._output)
        except Exception as e:
            self._set("#mux-state",
                      f"✓ Mux réussi ({self._output.name}) mais relecture "
                      f"impossible : {e}. L'encodage viserait le fichier d'origine.")
            return

        fresh = decide(new_info, self._decision.profile)
        self._decision.info             = new_info
        self._decision.video            = fresh.video
        self._decision.audio            = fresh.audio
        self._decision.subtitle_indices = None
        self._decision.external_tracks.clear()
        # Les pistes greffées vivent dans un MKV : un encodage ultérieur ne
        # doit pas le reconvertir en MP4.
        self._decision.force_mkv = True

        self._set("#mux-state",
                  f"✓ Terminé — {self._output.name}. "
                  f"C'est désormais ce fichier qui sera encodé.")
        self._set("#mux-out", f"Fichier de travail : {self._output.name}")

    # ── Sortie ────────────────────────────────────────────────────────────────

    def action_go_back(self) -> None:
        # Mux interrompu : le fichier partiel n'est pas exploitable
        if self._process and not self._done:
            self._process.terminate()
            self._process.wait()
            try:
                self._output.unlink(missing_ok=True)
            except OSError:
                pass
        self.dismiss(self._ok)
