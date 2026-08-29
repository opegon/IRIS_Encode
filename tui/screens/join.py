"""
tui/screens/join.py — Collage bout à bout des parties d'un même film.

L'ordre est la seule chose que le collage ne peut pas deviner sans risque :
il est déduit des noms (`part1` avant `part2`), montré, et corrigeable par
`Ctrl+↑/↓` avant que quoi que ce soit ne soit écrit.

L'écran s'arrête au fichier produit. Il n'enchaîne volontairement pas sur le
dry-run ou l'encodage comme `MuxScreen` le fait : le fichier recousu est une
entrée ordinaire, et `BACKSPACE` le retrouve dans le navigateur avec toutes
les touches qui valent pour les autres fichiers.
"""
from __future__ import annotations

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Label, ProgressBar, Static

from core import config as cfg_mod
from core.joiner import (build_join_command, controler, derive_duree,
                         duree_attendue, join_output_path, ordre_naturel)
from core.muxer import MuxProcess
from core.scanner import VideoInfo

from ..common import actions_ecran, cellule, fmt_duration, footer_line2, retour_accueil
from ..mixins import TableNavMixin
from ..widgets.entete import Entete
from ..widgets.footer import KeyFooter

# Largeurs fixes, sauf celle du nom de fichier : elle vaut `None` ici et se
# lit sur l'accueil au montage (voir `_largeur_fichier`). Les autres colonnes
# portent des libellés bornés, le nom est le seul qui déborde vraiment.
_COLUMNS: list[tuple[str, int | None]] = [
    ("#", 3), ("Fichier", None), ("Durée", 9), ("Pistes", 12), ("Collage", 22),
]


def ordre_naturel_infos(infos: list[VideoInfo]) -> list[VideoInfo]:
    """`ordre_naturel` appliqué à des VideoInfo plutôt qu'à des chemins."""
    par_chemin = {i.path: i for i in infos}
    return [par_chemin[p] for p in ordre_naturel(list(par_chemin))]


class JoinScreen(TableNavMixin, Screen[bool]):
    """Ordonne les parties, les colle, et rend la main sur le fichier produit."""

    BINDINGS = [
        # Séquences VT standard, toujours transmises — voir le commentaire des
        # bindings de tui/screens/sync.py. `priority` parce qu'un DataTable
        # focalisé étouffe les touches avant le système de bindings.
        Binding("ctrl+up",   "monter",    "Monter",    show=True, priority=True),
        Binding("ctrl+down", "descendre", "Descendre", show=True, priority=True),
        Binding("f2",        "coller",    "Coller",    show=True),
        Binding("backspace", "go_back",   "Retour",    show=True),
        Binding("escape",    "go_back",   "Retour",    show=False, priority=True),
        Binding("ctrl+home", "accueil",   "Accueil",   show=True, priority=True),
    ]

    DEFAULT_CSS = """
    JoinScreen { layout: vertical; }
    #join-body {
        height: 1fr;
        padding: 1 2;
        layout: vertical;
    }
    #join-table { height: 1fr; }
    #join-total { height: 1; color: $text-muted; }
    #join-out   { height: 1; }
    #join-bar-row {
        height: 2;
        layout: horizontal;
    }
    #join-label { width: 12; }
    #join-bar   { width: 1fr; }
    #join-state { height: 3; }
    """

    def __init__(self, infos: list[VideoInfo]) -> None:
        super().__init__()
        # L'ordre proposé, corrigeable : c'est lui que le collage suivra.
        self._infos   = ordre_naturel_infos(infos)
        self._output  = join_output_path([i.path for i in self._infos])
        # Repris de l'accueil au montage ; la valeur par défaut de la config
        # tient jusque-là, aucune cellule n'étant construite avant.
        self._largeur_nom = cfg_mod.get_column_widths({})["fichier"]
        self._process: MuxProcess | None = None
        self._lance   = False
        self._done    = False
        self._ok      = False

    # ── Composition ───────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Entete()
        yield Static("", id="status-bar", classes="status-bar", markup=False)
        with Static(id="join-body"):
            yield DataTable(id="join-table", cursor_type="row",
                            show_header=True, zebra_stripes=True)
            yield Static("", id="join-total", markup=False)
            yield Static("", id="join-out", markup=False)
            with Static(id="join-bar-row"):
                yield Label("Collage", id="join-label")
                yield ProgressBar(total=100, show_eta=False, id="join-bar")
            yield Static("", id="join-state", markup=False)
        yield KeyFooter(
            actions=actions_ecran(self),
            nav=footer_line2(back=True, nav=True, accueil=True),
        )

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        self._largeur_nom = self._largeur_fichier()
        for titre, largeur in _COLUMNS:
            table.add_column(titre,
                             width=self._largeur_nom if largeur is None
                             else largeur)
        self._peupler()
        table.focus()

    def _largeur_fichier(self) -> int:
        """La largeur réglée pour le nom de fichier sur l'accueil.

        Le collage montre les mêmes fichiers que le navigateur : une colonne
        plus étroite ici tronquerait des noms qui se lisent entiers là-bas.
        Elle suit donc celle que l'accueil expose au redimensionnement
        (`Tab` puis `<` / `>`), planchers de `core.config` compris.
        """
        cfg = getattr(self.app, "cfg", None)
        return cfg_mod.get_column_widths(cfg if cfg is not None else {})["fichier"]

    # ── Table ─────────────────────────────────────────────────────────────────

    def _peupler(self, curseur: int = 0) -> None:
        """Réécrit la table dans l'ordre courant, curseur sur la ligne voulue."""
        table = self.query_one(DataTable)
        table.clear()
        for rang, info in enumerate(self._infos):
            table.add_row(*self._row_cells(rang, info))
        if self._infos:
            table.move_cursor(row=max(0, min(curseur, len(self._infos) - 1)))
        self._maj_bandeaux()

    def _row_cells(self, rang: int, info: VideoInfo) -> tuple:
        pistes = (f"V+{len(info.audio_tracks)}A"
                  f"+{len(info.subtitle_tracks)}S")
        return (
            cellule(str(rang + 1)),
            cellule(info.path.name, largeur=self._largeur_nom),
            cellule(fmt_duration(info.duration)),
            cellule(pistes),
            self._verdict(rang, info),
        )

    def _verdict(self, rang: int, info: VideoInfo) -> Text:
        """Cette partie se colle-t-elle sur la première ?

        La première est la référence — c'est elle qui donne au fichier produit
        ses codecs et sa définition ; les suivantes doivent s'y conformer.
        """
        if rang == 0:
            return cellule("référence", style="dim")
        ctrl = controler([self._infos[0], info])
        if ctrl.blocages:
            return cellule("✗ incompatible", style="bold dark_orange")
        if ctrl.avertissements:
            return cellule("✓ avec réserve", style="dark_orange")
        return cellule("✓")

    # ── Bandeaux ──────────────────────────────────────────────────────────────

    def _set(self, widget_id: str, texte: str) -> None:
        try:
            self.query_one(widget_id, Static).update(texte)
        except Exception:
            pass

    def _maj_bandeaux(self) -> None:
        self._set("#status-bar",
                  f" Collage — {len(self._infos)} parties ── {self._output.name}")
        self._set("#join-total",
                  f"Durée attendue du tout : "
                  f"{fmt_duration(duree_attendue(self._infos))}")
        self._set("#join-out", f"Sortie : {self._output.name}")

        if self._lance:
            return                      # le collage parle, on ne le recouvre pas

        ctrl = controler(self._infos)
        if ctrl.blocages:
            self._set("#join-state",
                      "✗ Collage impossible en l'état :\n  · "
                      + "\n  · ".join(ctrl.blocages[:2]))
        elif ctrl.avertissements:
            self._set("#join-state",
                      "⚠ Collage possible, avec réserve :\n  · "
                      + "\n  · ".join(ctrl.avertissements[:2]))
        else:
            self._set("#join-state",
                      "Ordre à vérifier — Ctrl+↑/↓ déplacent la partie "
                      "sous le curseur.\nF2 lance le collage.")

    def _set_progress(self, pct: int) -> None:
        try:
            self.query_one("#join-bar", ProgressBar).progress = pct
        except Exception:
            pass

    # ── Réordonnancement ──────────────────────────────────────────────────────

    def _deplacer(self, pas: int) -> None:
        if self._lance:
            self.app.bell()
            return
        table = self.query_one(DataTable)
        rang  = table.cursor_row
        cible = rang + pas
        if not (0 <= rang < len(self._infos) and 0 <= cible < len(self._infos)):
            self.app.bell()
            return
        self._infos[rang], self._infos[cible] = self._infos[cible], self._infos[rang]
        # Le nom du tout se déduit du préfixe commun : il ne bouge pas avec
        # l'ordre, mais le dossier de sortie suit la première partie.
        self._output = join_output_path([i.path for i in self._infos])
        self._peupler(curseur=cible)

    def action_monter(self) -> None:
        self._deplacer(-1)

    def action_descendre(self) -> None:
        self._deplacer(+1)

    # ── Collage ───────────────────────────────────────────────────────────────

    def action_coller(self) -> None:
        if self._lance:
            self.app.bell()
            self._set("#join-state",
                      "Collage déjà terminé." if self._done
                      else "Collage en cours…")
            return

        ctrl = controler(self._infos)
        if not ctrl.collable:
            self.app.bell()
            self._set("#join-state",
                      "✗ Collage refusé — les parties ne s'apparient pas :\n  · "
                      + "\n  · ".join(ctrl.blocages[:2]))
            return

        if self._output.exists():
            self.app.bell()
            self._set("#join-state",
                      f"✗ {self._output.name} existe déjà. "
                      f"Le renommer ou l'effacer (Ctrl+D) avant de recoller.")
            return

        self._lance = True
        self._run()

    @work(thread=True, name="joiner")
    def _run(self) -> None:
        parts = [i.path for i in self._infos]
        try:
            cmd = build_join_command(parts, self._output)
        except ValueError as e:
            self._done = True
            self.app.call_from_thread(self._set, "#join-state", f"✗ {e}")
            return

        self.app.call_from_thread(
            self._set, "#join-state",
            f"▶ Collage lancé — {len(parts)} parties, copie du conteneur en cours…")

        proc = MuxProcess(cmd)
        self._process = proc
        proc.start()

        for _line, pct in proc.iter_progress():
            if pct is not None:
                self.app.call_from_thread(self._set_progress, pct)
                self.app.call_from_thread(
                    self._set, "#join-state", f"▶ Collage — {pct}%")

        rc            = proc.wait()
        self._ok      = rc == 0
        self._done    = True
        self._process = None

        if not self._ok:
            detail = proc.errors[0] if proc.errors else f"code {rc}"
            self.app.call_from_thread(
                self._set, "#join-state", f"✗ Échec du collage : {detail}")
            return

        self.app.call_from_thread(self._set_progress, 100)
        self.app.call_from_thread(self._set, "#join-state", self._verifier())

    def _verifier(self) -> str:
        """Relit le fichier produit et compare sa durée à la somme des parties.

        Un mkvmerge tué en cours de route laisse un fichier lisible et court :
        sans ce contrôle, il passerait pour un collage réussi (même piège
        qu'IE-41).
        """
        from core import scanner

        attendue = duree_attendue(self._infos)
        try:
            obtenue = scanner.scan(self._output).duration
        except Exception as e:
            return (f"✓ Collage terminé — {self._output.name}, mais relecture "
                    f"impossible ({e}) : vérifier sa durée avant de l'encoder.")

        ecart = derive_duree(attendue, obtenue)
        if ecart is not None:
            return (f"⚠ {self._output.name} dure {fmt_duration(obtenue)} pour "
                    f"{fmt_duration(attendue)} attendues ({ecart:+.0f} s).\n"
                    f"Le collage est peut-être incomplet — le vérifier avant "
                    f"de l'encoder.")

        return (f"✓ Terminé — {self._output.name}, {fmt_duration(obtenue)}. "
                f"Les parties sont conservées.\n"
                f"BACKSPACE revient au dossier, où le fichier se travaille "
                f"comme n'importe quel autre.")

    # ── Sortie ────────────────────────────────────────────────────────────────

    def action_go_back(self) -> None:
        # Collage interrompu : le fichier partiel n'est pas exploitable.
        if self._process and not self._done:
            self._process.terminate()
            self._process.wait()
            try:
                self._output.unlink(missing_ok=True)
            except OSError:
                pass
        self.dismiss(self._ok)

    def action_accueil(self) -> None:
        retour_accueil(self.app)
