"""
tui/screens/sync.py — Recalage manuel des pistes externes avant mux.

Une ligne par piste greffée, chacune avec son propre décalage : ajouter une
VF et ses sous-titres se règle indépendamment, piste par piste.

  ←/→          champ suivant / précédent
  +/-          ±100 ms sur le décalage, valeur suivante sur les autres champs
  Shift+↑/↓    ±1 s sur le décalage
  ↵            liste de choix du champ actif
  c            reprend le décalage d'une autre piste
  d            retire la piste de la liste
  F2           lance le mux
"""
from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.events import Key
from textual.screen import Screen
from textual.widgets import DataTable, Header, Label, ProgressBar, Static

from core import preview
from core.decision import FileDecision
from core.muxer import (
    ExternalTrack, MuxProcess, SyncOrigin, TrackKind, build_sample_command,
    ffmpeg_stream_index, propager_recalage, sample_output_path,
    sample_windows, timecode,
)
from core.sync import (
    Segment, SyncResult, extract_subtitle, measure_external_track,
    measure_with_anchor, read_cues, reperes_proposables,
)

from ..common import (actions_ecran, footer_line2, raccourcis, touche,
                      tronquer_milieu, retour_accueil)
from ..mixins import TableNavMixin
from ..widgets.footer import KeyFooter
from .segments import SegmentsScreen
from .value_picker import ValuePickerScreen

# Champs éditables, dans l'ordre de parcours ←/→
_FIELDS = ["delay", "stretch", "lang", "name", "default", "forced"]

_FIELD_LABELS = {
    "delay":   "Décalage",
    "stretch": "Étirement",
    "lang":    "Langue",
    "name":    "Nom",
    "default": "Défaut",
    "forced":  "Forcé",
}

# Étirements courants : corrige les sources PAL accélérées (25 vs 23.976 fps)
_STRETCH_CYCLE: list[tuple[int, int] | None] = [
    None,
    (24000, 25025),
    (25025, 24000),
]
_STRETCH_LABELS = {
    None:           "—",
    (24000, 25025): "PAL→film",
    (25025, 24000): "film→PAL",
}

_LANGS = ["fre", "eng", "ger", "spa", "ita", "jpn", "por", "rus", "und"]
_NAMES = ["—", "VF", "VOSTFR", "VO", "Forcés", "Commentaires", "SDH"]

# Décalages proposés par ↵ sur le champ Décalage : le réglage fin reste
# sur +/-, mais la liste évite de marteler une touche pour partir de loin.
_DELAY_PRESETS = [-5000, -3000, -2000, -1000, -500, -250, 0,
                  250, 500, 1000, 2000, 3000, 5000]
_BOOLS = ["non", "oui"]

# « Français (France) (forced) » fait 26 caractères : la colonne les tient.
# En dessous, deux pistes d'un même rip s'affichaient à l'identique.
_NAME_WIDTH = 26

# Trois pas pour le décalage. Le pas fin sert à finir le travail : une mesure
# rend souvent la bonne valeur à quelques dizaines de millisecondes près, et
# 100 ms est alors trop gros pour s'en approcher.
_DELAY_FINE_MS = 10
_DELAY_STEP_MS = 100
_DELAY_JUMP_MS = 1000

_HINT = (raccourcis([("←/→", "Champ"), ("Ctrl+↑/↓", "±10 ms"),
                     ("+/-", "±100 ms"),
                     ("Shift+↑/↓", "±1 s"), ("enter", "Liste")]) + "\n"
         + raccourcis([("m", "Mesurer"), ("v", "Visualiser"),
                       ("k", "Extrait de contrôle"), ("c", "Copier"),
                       ("r", "Repère"), ("F9", "Ajouter"),
                       ("d", "Retirer")]))
_HINT_NO_LANG = (f"⚠ Langue manquante — +/- ou {touche('enter')} pour la "
                 f"choisir. Sans elle, la piste sortirait en « und ».")


class SyncScreen(TableNavMixin, Screen["list[ExternalTrack] | None"]):
    """Réglage du recalage de chaque piste externe, puis mux."""

    BINDINGS = [
        Binding("left",      "field_prev",   "Champ préc.",   show=False),
        Binding("right",     "field_next",   "Champ suiv.",   show=False),
        # Alias clavier : selon la disposition, '+' arrive en 'plus',
        # 'equals_sign' ou depuis le pavé numérique.
        Binding("+,plus,equals_sign,kp_plus",   "val_up",   "Valeur suiv.", show=False),
        Binding("-,minus,kp_minus",             "val_down", "Valeur préc.", show=False),
        Binding("shift+up",  "jump_up",      "+1 s",          show=False),
        Binding("shift+down","jump_down",    "-1 s",          show=False),
        # Pas fin, pour finir d'approcher une valeur mesurée.
        #
        # `Ctrl+↑/↓` d'abord : ce sont des séquences VT standard, toujours
        # transmises. `Ctrl+±` ne l'est pas — Textual n'a même pas de nom pour
        # `ctrl+plus`, et en mode terminal virtuel (celui qu'il active aussi
        # sous Windows) `Ctrl+=` ne produit généralement aucun code. Seul
        # `Ctrl+-` passe, sous le nom `ctrl+underscore` : 0x1F. Les alias sont
        # là pour les terminaux qui savent les envoyer ; la flèche est celle
        # sur laquelle on peut compter, et c'est elle que le bandeau annonce.
        Binding("ctrl+up,ctrl+plus,ctrl+equals_sign,ctrl+kp_plus",
                "fine_up",   "+10 ms", show=False),
        Binding("ctrl+down,ctrl+underscore,ctrl+minus,ctrl+kp_minus",
                "fine_down", "-10 ms", show=False),
        Binding("enter",     "open_picker",  "Liste",         show=True, priority=True),
        Binding("m",         "measure",      "Mesurer",       show=True),
        Binding("v",         "preview",      "Visualiser",    show=True),
        Binding("k",         "sample",       "Extrait",       show=True),
        Binding("a",         "apply_candidate",
                "Forcer",  show=True),
        Binding("s",         "show_segments", "Plages",        show=True),
        Binding("p",         "apply_segments",
                "Appliquer",  show=True),
        Binding("c",         "copy_delay",   "Copier", show=True),
        Binding("r",         "ancrer",       "Repère", show=True),
        Binding("d",         "remove_track", "Retirer",       show=True),
        # F1/F2 gardent partout le même sens : dry-run et encodage. Le mux,
        # propre à cet écran, prend F3.
        Binding("f1",        "dryrun",       "Dry-run",       show=True),
        Binding("f2",        "run",          "Encoder",       show=True),
        Binding("f3",        "run_mux",      "Muxer",         show=True),
        Binding("f9",        "add_track",    "Ajouter", show=True),
        Binding("backspace", "go_back",      "Retour",        show=True),
        Binding("escape",    "go_back",      "Retour",        show=False, priority=True),
        # `priority` : un DataTable etouffe la touche avant les bindings —
        # meme avertissement qu'en tete de tui/mixins.py.
        Binding("ctrl+home", "accueil",   "Accueil",       show=True,
                priority=True),
    ]

    DEFAULT_CSS = """
    SyncScreen { layout: vertical; }
    #sync-table { height: 1fr; }
    #sync-bar-row {
        height: 1;
        layout: horizontal;
        padding: 0 2;
        display: none;
    }
    #sync-bar-row.mesure { display: block; }
    #sync-bar-label { width: 20; color: $warning; }
    #sync-bar { width: 1fr; }
    #sync-hint {
        /* 3 lignes de texte + 1 pour la bordure : `height` couvre la boîte
           entière, bordure comprise. À 3, la troisième ligne disparaissait —
           celle qui renvoie vers 'a' ou 's', donc précisément l'indication
           dont l'utilisateur a besoin après un refus. */
        height: 4;
        background: $primary-darken-1;
        color: $text;
        padding: 0 2;
        border-top: solid $primary;
    }
    """

    def __init__(self, decision: FileDecision) -> None:
        super().__init__()
        self._decision  = decision
        self._source    = decision.info.path
        tracks          = decision.external_tracks
        self._tracks    = tracks
        # Une piste sans langue bloque le mux : on ouvre directement sur ce
        # champ plutôt que de laisser chercher.
        self._field_idx = (_FIELDS.index("lang")
                           if any(not t.language for t in tracks) else 0)
        self._measuring = False
        self._sampling  = False
        self._hint_override: str = ""
        # (ligne, décalage) proposé par une mesure refusée
        self._candidate: tuple[int, int] | None = None
        # (ligne, plages) de la dernière mesure ayant constaté un montage
        # différent — consultables avec 's', jamais appliquées
        self._segments: tuple[int, list[Segment]] | None = None

    # ── Composition ───────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="status-bar", classes="status-bar", markup=False)
        yield DataTable(id="sync-table", cursor_type="row", zebra_stripes=False)
        with Static(id="sync-bar-row"):
            yield Label("Mesure en cours", id="sync-bar-label")
            yield ProgressBar(total=100, show_eta=False, id="sync-bar")
        yield Static(_HINT, id="sync-hint", markup=False)
        yield KeyFooter(
            actions=actions_ecran(self),
            nav=footer_line2(back=True, nav=True, accueil=True),
        )

    def on_mount(self) -> None:
        self._build_table()
        # Curseur aligné sur le champ d'ouverture : s'il pointe la langue,
        # c'est qu'une piste en manque — autant se poser dessus.
        missing = next((i for i, t in enumerate(self._tracks) if not t.language), None)
        if missing is not None:
            self.query_one(DataTable).move_cursor(row=missing)
        self._update_status()
        self._refresh_all()
        self.query_one(DataTable).focus()

    # ── Table ─────────────────────────────────────────────────────────────────

    def _build_table(self, keep_cursor: bool = False) -> None:
        table  = self.query_one(DataTable)
        cursor = table.cursor_row if keep_cursor else 0
        table.clear(columns=True)

        table.add_column("Source",    width=28, key="src")
        table.add_column("Piste",     width=14, key="tid")
        table.add_column("Décalage",  width=12, key="delay")
        table.add_column("Étirement", width=11, key="stretch")
        table.add_column("Langue",    width=8,  key="lang")
        table.add_column("Nom",       width=_NAME_WIDTH, key="name")
        table.add_column("Défaut",    width=8,  key="default")
        table.add_column("Forcé",     width=7,  key="forced")
        table.add_column("Recalage",  width=None, key="origin")

        for i, t in enumerate(self._tracks):
            table.add_row(*self._row(i), key=str(i))

        if table.row_count:
            table.move_cursor(row=min(cursor, table.row_count - 1))

    def _cell(self, i: int, field: str) -> Text:
        """Valeur d'un champ, mise en évidence si c'est le champ actif."""
        t      = self._tracks[i]
        active = (field == _FIELDS[self._field_idx]
                  and i == self.query_one(DataTable).cursor_row)
        style  = "reverse bold" if active else ""

        if field == "delay":
            txt = f"{t.delay_ms:+d} ms"
        elif field == "stretch":
            txt = _STRETCH_LABELS.get(t.stretch, "?")
        elif field == "lang":
            txt = t.language or "—"
            if not t.language:
                style = f"{style} bold dark_orange".strip()
        elif field == "name":
            # Six pistes « Français (…) » ne se distinguent que par leur fin :
            # une ellipse à droite les rendait toutes identiques.
            txt = tronquer_milieu(t.track_name or "—", _NAME_WIDTH)
        elif field == "default":
            txt = "oui" if t.is_default else "non"
        else:
            txt = "oui" if t.is_forced else "non"
        return Text(txt, style=style, no_wrap=True)

    def _row(self, i: int) -> tuple:
        t    = self._tracks[i]
        kind = "audio" if t.kind == TrackKind.AUDIO else "sous-titre"
        origin = {
            SyncOrigin.NONE:     Text("—", style="dim"),
            SyncOrigin.MEASURED: Text("mesuré", style="green"),
            SyncOrigin.MANUAL:   Text("manuel", style="cyan"),
            SyncOrigin.COPIED:   Text(
                f"repris de #{(t.copied_from or 0) + 1}", style="cyan"),
        }[t.sync_origin]
        return (
            Text(t.source_path.name, no_wrap=True, overflow="ellipsis"),
            Text(f"{kind} #{t.source_tid}", no_wrap=True),
            self._cell(i, "delay"),
            self._cell(i, "stretch"),
            self._cell(i, "lang"),
            self._cell(i, "name"),
            self._cell(i, "default"),
            self._cell(i, "forced"),
            origin,
        )

    def _refresh_row(self, i: int) -> None:
        table = self.query_one(DataTable)
        keys  = ("src", "tid", "delay", "stretch", "lang", "name",
                 "default", "forced", "origin")
        for key, val in zip(keys, self._row(i)):
            table.update_cell(str(i), key, val, update_width=False)

    def _refresh_all(self) -> None:
        for i in range(len(self._tracks)):
            self._refresh_row(i)

    def _update_status(self) -> None:
        n       = len(self._tracks)
        missing = sum(1 for t in self._tracks if not t.language)
        warn    = f" ── ⚠ {missing} piste(s) sans langue" if missing else ""
        self.query_one("#status-bar", Static).update(
            f" {self._source.name} ── {n} piste(s) à greffer"
            f" ── Champ : {_FIELD_LABELS[_FIELDS[self._field_idx]]}{warn}"
        )
        # Un message de mesure survit à la navigation : sans ça, la moindre
        # flèche effaçait le résultat et l'écran semblait n'avoir rien fait.
        self.query_one("#sync-hint", Static).update(
            self._hint_override or (_HINT_NO_LANG if missing else _HINT)
        )

    @on(DataTable.RowHighlighted)
    def _on_row_highlight(self, _: DataTable.RowHighlighted) -> None:
        self._refresh_all()

    # ── Navigation entre champs ───────────────────────────────────────────────

    def on_key(self, event: Key) -> None:
        if event.key in ("left", "right"):
            event.stop()
            self.action_field_prev() if event.key == "left" else self.action_field_next()
            return
        # Laisse TableNavMixin gérer Home/End/PageUp/PageDown
        super().on_key(event)

    def action_field_prev(self) -> None:
        self._field_idx = (self._field_idx - 1) % len(_FIELDS)
        self._refresh_all()
        self._update_status()

    def action_field_next(self) -> None:
        self._field_idx = (self._field_idx + 1) % len(_FIELDS)
        self._refresh_all()
        self._update_status()

    # ── Édition ───────────────────────────────────────────────────────────────

    def _current(self) -> int | None:
        row = self.query_one(DataTable).cursor_row
        return row if 0 <= row < len(self._tracks) else None

    def action_val_up(self)   -> None: self._change(+1, _DELAY_STEP_MS)
    def action_val_down(self) -> None: self._change(-1, _DELAY_STEP_MS)
    def action_jump_up(self)  -> None: self._change(+1, _DELAY_JUMP_MS)
    def action_jump_down(self)-> None: self._change(-1, _DELAY_JUMP_MS)
    # Sur un champ qui n'est pas le décalage, `_change` ignore le pas et fait
    # défiler les valeurs : le raccourci reste vivant partout plutôt que de ne
    # rien faire sur cinq champs sur six.
    def action_fine_up(self)  -> None: self._change(+1, _DELAY_FINE_MS)
    def action_fine_down(self)-> None: self._change(-1, _DELAY_FINE_MS)

    def _change(self, delta: int, step: int) -> None:
        i = self._current()
        if i is None:
            return
        t     = self._tracks[i]
        field = _FIELDS[self._field_idx]
        # Une saisie manuelle périme le message de la mesure précédente
        self._hint_override = ""

        if field == "delay":
            t.delay_ms += delta * step
            t.sync_origin = SyncOrigin.MANUAL
            t.copied_from = None
        elif field == "stretch":
            cur = _STRETCH_CYCLE.index(t.stretch) if t.stretch in _STRETCH_CYCLE else 0
            t.stretch = _STRETCH_CYCLE[(cur + delta) % len(_STRETCH_CYCLE)]
            t.sync_origin = SyncOrigin.MANUAL
        elif field == "lang":
            cur = _LANGS.index(t.language) if t.language in _LANGS else 0
            t.language = _LANGS[(cur + delta) % len(_LANGS)]
        elif field == "name":
            cur = _NAMES.index(t.track_name) if t.track_name in _NAMES else 0
            nxt = _NAMES[(cur + delta) % len(_NAMES)]
            t.track_name = "" if nxt == "—" else nxt
        elif field == "default":
            t.is_default = not t.is_default
        else:
            t.is_forced = not t.is_forced

        self._refresh_row(i)
        self._update_status()

    def action_open_picker(self) -> None:
        i = self._current()
        if i is None:
            return
        field = _FIELDS[self._field_idx]
        t     = self._tracks[i]

        if field == "lang":
            opts, cur = _LANGS, (_LANGS.index(t.language) if t.language in _LANGS else 0)
        elif field == "name":
            label = t.track_name or "—"
            opts, cur = _NAMES, (_NAMES.index(label) if label in _NAMES else 0)
        elif field == "stretch":
            opts = [_STRETCH_LABELS[s] for s in _STRETCH_CYCLE]
            cur  = _STRETCH_CYCLE.index(t.stretch) if t.stretch in _STRETCH_CYCLE else 0
        elif field == "delay":
            opts = [f"{d:+d} ms" for d in _DELAY_PRESETS]
            cur  = min(range(len(_DELAY_PRESETS)),
                       key=lambda k: abs(_DELAY_PRESETS[k] - t.delay_ms))
        else:
            opts = _BOOLS
            cur  = int(t.is_default if field == "default" else t.is_forced)

        def _apply(choice: int | None) -> None:
            if choice is None:
                return
            if field == "lang":
                t.language = _LANGS[choice]
            elif field == "name":
                t.track_name = "" if _NAMES[choice] == "—" else _NAMES[choice]
            elif field == "stretch":
                t.stretch = _STRETCH_CYCLE[choice]
                t.sync_origin = SyncOrigin.MANUAL
            elif field == "delay":
                t.delay_ms    = _DELAY_PRESETS[choice]
                t.sync_origin = SyncOrigin.MANUAL
                t.copied_from = None
            elif field == "default":
                t.is_default = bool(choice)
            else:
                t.is_forced = bool(choice)
            self._refresh_row(i)
            self._update_status()

        self.app.push_screen(
            ValuePickerScreen(_FIELD_LABELS[field], opts, cur), _apply
        )

    # ── Mesure automatique ────────────────────────────────────────────────────

    def action_measure(self) -> None:
        i = self._current()
        if i is None:
            return
        if self._measuring:
            self._set_hint("Une mesure est déjà en cours — laissez-la finir.")
            return
        self._measuring = True
        self._set_hint(f"⏳ Mesure de « {self._tracks[i].source_path.name} »\n"
                       f"Décodage de l'audio du film — sur un long métrage, "
                       f"comptez plusieurs dizaines de secondes.")
        # Visible dans la ligne elle-même : la barre du bas peut passer inaperçue
        self._set_origin_cell(i, Text("mesure…", style="yellow"))
        self._show_bar(True)
        self._measure(i)

    def _set_origin_cell(self, i: int, text: Text) -> None:
        try:
            self.query_one(DataTable).update_cell(
                str(i), "origin", text, update_width=False)
        except Exception:
            pass

    def _show_bar(self, visible: bool, libelle: str = "Mesure en cours") -> None:
        """Affiche la barre, en nommant le travail réellement en cours.

        Un libellé qui parle de mesure pendant un recalage laisse croire à un
        blocage : l'opération semble ne jamais finir puisqu'elle n'a pas
        commencé.
        """
        try:
            self.query_one("#sync-bar-row").set_class(visible, "mesure")
            if visible:
                self.query_one("#sync-bar-label", Label).update(libelle)
                self.query_one("#sync-bar", ProgressBar).progress = 0
        except Exception:
            pass

    def _set_progress(self, fraction: float) -> None:
        try:
            self.query_one("#sync-bar", ProgressBar).progress = int(fraction * 100)
        except Exception:
            pass

    @work(thread=True, name="sync-measure")
    def _measure(self, i: int) -> None:
        """Corrélation hors du thread UI : le décodage audio prend du temps."""
        t = self._tracks[i]

        def report(fraction: float) -> None:
            self.app.call_from_thread(self._set_progress, fraction)

        try:
            # La traduction du tid en index ffmpeg vit dans
            # `sync.measure_external_track` : elle ne doit exister qu'une fois.
            res = measure_external_track(self._source, t, progress=report,
                                         duration=self._decision.info.duration)
        except Exception as e:                       # ffmpeg absent, fichier illisible…
            res = SyncResult(0, None, 0.0, False, f"mesure impossible : {e}")
        self.app.call_from_thread(self._apply_measure, i, res)

    def _apply_measure(self, i: int, res: SyncResult) -> None:
        self._measuring = False
        self._show_bar(False)
        if not (0 <= i < len(self._tracks)):
            return                                   # piste retirée entre-temps
        if not res.ok:
            self.app.bell()
            self._set_origin_cell(i, Text("échec", style="bold dark_orange"))
            # Le candidat refusé reste applicable : il est souvent correct
            # malgré une confiance basse, et un décalage d'une minute est
            # hors de portée des touches +/-.
            self._candidate = (i, res.best_delay_ms)
            self._segments  = (i, res.segments) if res.segments else None
            if res.segments:
                # report() porte déjà les paliers et renvoie vers 's' :
                # proposer d'appliquer un décalage unique serait ici trompeur.
                self._set_hint(res.report())
            else:
                self._set_hint(f"{res.report()}\n"
                               f"'a' applique quand même "
                               f"{res.best_delay_ms:+d} ms "
                               f"— à vérifier dans un lecteur.")
            return
        self._candidate = None
        self._segments  = None
        t = self._tracks[i]
        t.delay_ms    = res.delay_ms
        t.stretch     = res.stretch
        t.sync_origin = SyncOrigin.MEASURED
        t.copied_from = None
        self._refresh_row(i)
        self._set_hint(res.report() + self._note_propagation(self._propager(i)))
        self._update_status()

    def _propager(self, i: int) -> int:
        """Reporte la mesure sur les sous-titres du même donneur, et rafraîchit.

        La règle vit dans `muxer.propager_recalage` : l'assistant s'en sert
        aussi, et elle ne doit exister qu'une fois.
        """
        touches = propager_recalage(self._tracks, i)
        for j in touches:
            self._refresh_row(j)
        return len(touches)

    @staticmethod
    def _note_propagation(n: int) -> str:
        if n == 0:
            return ""
        pistes = "sous-titre" if n == 1 else "sous-titres"
        accord = "s" if n > 1 else ""
        return (f"\n{n} {pistes} du même fichier recalé{accord} d'autant "
                f"— 'c' pour en reprendre un autre.")

    def action_ancrer(self) -> None:
        """Recale à partir d'un point donné à l'oreille.

        Dernier recours quand la mesure refuse : elle n'a pas besoin d'être
        fiable, seulement d'être **bornée**. Voir `sync.measure_with_anchor`.
        """
        i = self._current()
        if i is None or self._measuring:
            return
        t = self._tracks[i]
        if t.kind != TrackKind.SUBTITLE:
            self._set_hint("Le point de repère sert aux sous-titres : une piste "
                           "audio se mesure directement avec 'm'.")
            return

        from .ancrage import AncrageModal

        # Les répliques proposées viennent du fichier lui-même : une piste
        # embarquée doit d'abord être extraite, comme pour la mesure.
        try:
            src = t.source_path
            if src.suffix.lower() != ".srt":
                idx = ffmpeg_stream_index(src, t.source_tid,
                                          TrackKind.SUBTITLE)
                extrait = extract_subtitle(t.source_path, idx)
                if extrait is None:
                    self._set_hint("Sous-titre image (PGS, VobSub) : aucun "
                                   "texte à proposer comme repère.")
                    return
                src = extrait
            reperes = reperes_proposables(src)
        except Exception as e:                       # noqa: BLE001
            self._set_hint(f"Lecture des répliques impossible : {e}")
            return
        if not reperes:
            self._set_hint("Aucune réplique lisible dans cette piste.")
            return

        def _apres(points) -> None:
            if points is None:
                return
            ecrit, entendu = points
            self._measuring = True
            self._set_hint(f"⏳ Recherche autour de {entendu - ecrit:+.1f} s.\n"
                           f"Décodage de l'audio du film — comptez plusieurs "
                           f"dizaines de secondes.")
            self._set_origin_cell(i, Text("mesure…", style="yellow"))
            self._show_bar(True)
            self._mesure_ancree(i, ecrit, entendu)

        self.app.push_screen(
            AncrageModal(reperes, t.track_name or t.source_path.name), _apres)

    @work(thread=True, name="sync-ancrage")
    def _mesure_ancree(self, i: int, ecrit: float, entendu: float) -> None:
        t = self._tracks[i]

        def report(fraction: float) -> None:
            self.app.call_from_thread(self._set_progress, fraction)

        try:
            idx = ffmpeg_stream_index(t.source_path, t.source_tid,
                                      TrackKind.SUBTITLE)
            res = measure_with_anchor(self._source, t.source_path,
                                      sous_titre_s=ecrit, entendu_s=entendu,
                                      progress=report,
                                      duration=self._decision.info.duration,
                                      donor_track=idx)
        except Exception as e:                       # noqa: BLE001
            res = SyncResult(0, None, 0.0, False, f"mesure impossible : {e}")
        self.app.call_from_thread(self._apply_measure, i, res)

    def _set_hint(self, text: str) -> None:
        """Message persistant : il survit à la navigation entre champs."""
        self._hint_override = text
        self.query_one("#sync-hint", Static).update(text)

    def action_apply_candidate(self) -> None:
        """
        Applique le décalage d'une mesure refusée.

        Une confiance basse ne veut pas dire que la valeur est fausse : sur
        une bande-son dense, le bon décalage sort souvent avec un score
        médiocre. Et un décalage de l'ordre de la minute serait inatteignable
        avec +/-.
        """
        if self._candidate is None:
            self._set_hint("Aucun candidat en attente — lancez d'abord une "
                           "mesure avec 'm'.")
            return
        i, delay = self._candidate
        if not (0 <= i < len(self._tracks)):
            self._candidate = None
            return
        t = self._tracks[i]
        t.delay_ms    = delay
        t.sync_origin = SyncOrigin.MANUAL     # non validé par la corrélation
        t.copied_from = None
        self._candidate = None
        self._refresh_row(i)
        # Un candidat forcé reste une décision de l'utilisateur : les
        # sous-titres du même donneur la suivent comme ils suivraient une
        # mesure.
        self._set_hint(f"Candidat appliqué : {delay:+d} ms — non confirmé par "
                       f"la mesure, vérifiez dans un lecteur avant de muxer."
                       + self._note_propagation(self._propager(i)))
        self._update_status()

    def action_show_segments(self) -> None:
        """
        Détail des plages relevées par la dernière mesure refusée.

        Lecture seule : constater que les deux fichiers sont deux montages ne
        donne pas le moyen de les recaler, et poser l'un des paliers sur toute
        la piste serait faux partout ailleurs.
        """
        if self._segments is None:
            self._set_hint("Aucune plage à montrer — elles n'apparaissent "
                           "qu'après une mesure ayant constaté un montage "
                           "différent.")
            return
        i, segs = self._segments
        nom = self._tracks[i].source_path.name if 0 <= i < len(self._tracks) else ""
        self.app.push_screen(SegmentsScreen(segs, nom))

    def action_apply_segments(self) -> None:
        """
        Applique à un sous-titre les plages relevées sur l'audio.

        Les trois pistes d'un même donneur portent le même montage : les
        coupures mesurées sur l'audio valent pour les sous-titres, dont le
        signal est trop creux pour les retrouver seul.

        Un sous-titre se corrige exactement — il n'y a que des nombres à
        décaler. On produit donc un .srt recalé qui devient la source de la
        piste, avec un décalage nul : mpv, l'extrait de contrôle et le mux le
        traitent ensuite comme n'importe quel fichier.
        """
        i = self._current()
        if i is None:
            return
        if self._segments is None:
            self._set_hint("Aucune plage connue — mesurez d'abord la piste "
                           "audio du donneur avec 'm'.")
            return

        if self._measuring:
            self._set_hint("Une opération est déjà en cours — laissez-la finir.")
            return

        _, segs = self._segments
        t = self._tracks[i]
        if t.kind == TrackKind.SUBTITLE:
            self._build_corrected_subtitle(i, segs)
            return

        # L'audio ne se corrige pas en décalant des nombres : il faut le
        # rallonger aux points de bascule et le réencoder. C'est long, donc
        # hors du thread UI.
        self._measuring = True
        self._set_hint(f"⏳ Recalage de « {t.source_path.name} » sur "
                       f"{len(segs)} plages.\nDécodage puis réencodage de la "
                       f"piste — comptez une poignée de minutes.")
        self._set_origin_cell(i, Text("recalage…", style="yellow"))
        self._show_bar(True, "Recalage en cours")
        self._retime(i, segs)

    @work(thread=True, name="sync-retime")
    def _retime(self, i: int, segs: list[Segment]) -> None:
        """Fabrique la piste audio recalée hors du thread UI."""
        import tempfile
        from core.sync import retime_audio

        t = self._tracks[i]

        def report(fraction: float) -> None:
            self.app.call_from_thread(self._set_progress, fraction)

        try:
            idx = ffmpeg_stream_index(t.source_path, t.source_tid, TrackKind.AUDIO)
            out = (Path(tempfile.gettempdir())
                   / f"{self._source.stem}_{t.language or 'und'}_[recale].mka")
            fichier, notes = retime_audio(t.source_path, idx, segs, out,
                                          progress=report)
        except Exception as e:
            fichier, notes = None, [str(e)]
        self.app.call_from_thread(self._retime_done, i, fichier, notes)

    def _retime_done(self, i: int, fichier: Path | None,
                     notes: list[str]) -> None:
        self._measuring = False
        self._show_bar(False)
        if not (0 <= i < len(self._tracks)):
            return                                   # piste retirée entre-temps
        if fichier is None:
            self.app.bell()
            self._set_origin_cell(i, Text("échec", style="bold dark_orange"))
            self._set_hint("Recalage impossible.\n" + " · ".join(notes))
            return

        t = self._tracks[i]
        t.source_path = fichier
        t.source_tid  = 0            # la piste produite est seule dans son fichier
        t.delay_ms    = 0
        t.stretch     = None
        t.sync_origin = SyncOrigin.MEASURED
        t.copied_from = None
        self._refresh_row(i)
        self._update_status()
        reserve = ("\n⚠ " + " · ".join(notes)) if notes else ""
        self._set_hint(
            f"Piste recalée — décalage nul désormais.\n"
            f"{fichier.name}{reserve}\n"
            f"'v' pour contrôler dans mpv, 'k' pour un extrait muxé.")

    def _build_corrected_subtitle(self, i: int, segs: list[Segment]) -> None:
        import tempfile
        from core.sync import extract_subtitle, shift_srt

        t = self._tracks[i]
        try:
            src = t.source_path
            if src.suffix.lower() != ".srt":
                idx = ffmpeg_stream_index(src, t.source_tid, TrackKind.SUBTITLE)
                src = extract_subtitle(t.source_path, idx)
                if src is None:
                    self.app.bell()
                    self._set_hint("Extraction impossible — sous-titre image "
                                   "(PGS, VobSub) ou piste illisible.")
                    return
            out = (Path(tempfile.gettempdir())
                   / f"{self._source.stem}_{t.language or 'und'}_[recale].srt")
            shift_srt(src, segs, out)
        except Exception as e:
            self.app.bell()
            self._set_hint(f"Correction impossible : {e}")
            return

        t.source_path = out
        t.source_tid  = 0            # un .srt nu n'a qu'une piste, d'id 0
        t.delay_ms    = 0
        t.stretch     = None
        t.sync_origin = SyncOrigin.MEASURED
        t.copied_from = None
        self._refresh_row(i)
        self._update_status()
        paliers = " · ".join(f"{s.delay_ms:+d}" for s in segs)
        self._set_hint(
            f"Sous-titre recalé sur {len(segs)} plages ({paliers} ms) — "
            f"décalage nul désormais.\n"
            f"{out.name}\n"
            f"'v' pour contrôler dans mpv, 'k' pour un extrait muxé.")

    # ── Contrôle à l'œil ──────────────────────────────────────────────────────

    def action_preview(self) -> None:
        """
        Ouvre le film dans mpv avec la piste greffée et le décalage courant.

        La corrélation donne un chiffre ; elle ne dit pas si le résultat sonne
        juste. mpv se positionne sur un passage dialogué plutôt qu'au début,
        souvent muet.
        """
        i = self._current()
        if i is None:
            return
        if not preview.available():
            self.app.bell()
            self._set_hint("mpv absent — relancez le preflight pour l'installer.")
            return

        t = self._tracks[i]
        try:
            first_cue = None
            donor_idx = 0
            if t.kind == TrackKind.SUBTITLE:
                cues = read_cues(t.source_path)
                first_cue = cues[0][0] if cues else None
            else:
                donor_idx = ffmpeg_stream_index(
                    t.source_path, t.source_tid, TrackKind.AUDIO)

            cmd = preview.build_command(
                self._source, t,
                duration=self._decision.info.duration,
                n_internal_audio=len(self._decision.info.audio_tracks),
                donor_audio_index=donor_idx,
                first_cue=first_cue,
            )
            preview.launch(cmd)
        except Exception as e:
            self.app.bell()
            self._set_hint(f"Lancement de mpv impossible : {e}")
            return

        if t.stretch:
            self._set_hint(
                f"mpv ouvert avec {t.delay_ms:+d} ms.\n"
                f"⚠ L'étirement n'est pas prévisualisable — mpv ne sait "
                f"appliquer qu'un décalage constant.\n"
                f"{preview.keys_hint(t)}, puis reportez la valeur ici.")
        else:
            self._set_hint(
                f"mpv ouvert avec {t.delay_ms:+d} ms appliqués.\n"
                f"{preview.keys_hint(t)}.\n"
                f"Reportez ensuite la valeur corrigée dans cet écran.")

    # ── Extrait de contrôle ───────────────────────────────────────────────────

    def action_sample(self) -> None:
        """
        Produit un court extrait réellement muxé, puis l'ouvre dans mpv.

        C'est le seul contrôle honnête d'un facteur d'étirement : ni mpv ni la
        corrélation ne le prévisualisent. Sans étirement, une fenêtre suffit ;
        avec, on en prend deux — tôt et tard — parce que la dérive s'accumule.
        """
        if self._measuring or self._sampling:
            self._set_hint("Une opération est déjà en cours.")
            return
        if not self._ready():
            return
        self._sampling = True
        self._show_bar(True)
        self._set_hint("⏳ Construction de l'extrait de contrôle…")
        self._build_sample()

    @work(thread=True, name="sync-sample")
    def _build_sample(self) -> None:
        first_cue = None
        subs = next((t for t in self._tracks if t.kind == TrackKind.SUBTITLE), None)
        if subs is not None:
            cues = read_cues(subs.source_path)
            first_cue = cues[0][0] if cues else None

        has_stretch = any(t.stretch for t in self._tracks)
        starts = sample_windows(self._decision.info.duration, has_stretch, first_cue)
        out    = sample_output_path(self._source)
        try:
            out.unlink(missing_ok=True)      # une relance remplace l'ancien
            cmd = build_sample_command(self._source, list(self._tracks), out, starts)
        except (ValueError, OSError) as e:
            self.app.call_from_thread(self._sample_done, None, str(e), starts)
            return

        proc = MuxProcess(cmd)
        proc.start()
        for _line, pct in proc.iter_progress():
            if pct is not None:
                self.app.call_from_thread(self._set_progress, pct / 100)
        rc = proc.wait()
        erreur = None if rc == 0 else (proc.errors[0] if proc.errors else f"code {rc}")
        self.app.call_from_thread(self._sample_done, out, erreur, starts)

    def _sample_done(self, out, erreur: str | None, starts: list[float]) -> None:
        self._sampling = False
        self._show_bar(False)
        if erreur:
            self.app.bell()
            self._set_hint(f"✗ Extrait impossible : {erreur}")
            return

        fenetres = " et ".join(timecode(s) for s in starts)
        if preview.available():
            try:
                preview.open_file(out)
            except Exception as e:
                self._set_hint(f"Extrait prêt : {out}\nmpv n'a pas pu l'ouvrir : {e}")
                return
            self._set_hint(
                f"Extrait ouvert dans mpv — fenêtres à {fenetres}.\n"
                f"C'est le résultat réel du mux : ce que vous entendez est "
                f"ce que produira F3.")
        else:
            self._set_hint(f"Extrait prêt (mpv absent) : {out}\n"
                           f"Fenêtres à {fenetres}.")

    # ── Reprise de décalage ───────────────────────────────────────────────────

    def action_copy_delay(self) -> None:
        """
        Reprend le décalage d'une autre piste externe.

        Cas courant : des sous-titres écrits sur le timing du donneur ont le
        même décalage que la piste audio qui vient du même fichier — inutile
        de les recaler séparément.
        """
        i = self._current()
        if i is None or len(self._tracks) < 2:
            return
        others = [j for j in range(len(self._tracks)) if j != i]
        opts   = [
            f"#{j + 1} {self._tracks[j].source_path.name} — {self._tracks[j].sync_label()}"
            for j in others
        ]

        def _apply(choice: int | None) -> None:
            if choice is None:
                return
            src = self._tracks[others[choice]]
            dst = self._tracks[i]
            dst.delay_ms    = src.delay_ms
            dst.stretch     = src.stretch
            dst.sync_origin = SyncOrigin.COPIED
            dst.copied_from = others[choice]
            self._refresh_row(i)
            self._update_status()

        self.app.push_screen(
            ValuePickerScreen("Reprendre le décalage de", opts, 0), _apply
        )

    def action_add_track(self) -> None:
        """
        Greffe une piste supplémentaire sans quitter l'écran.

        Une VF et ses sous-titres vivent dans deux fichiers distincts : les
        ajouter devait sinon passer par un aller-retour vers l'écran des
        pistes entre les deux.
        """
        if self._measuring:
            self._set_hint("Mesure en cours — attendez sa fin avant d'ajouter "
                           "une piste.")
            return
        from .donor_picker import pick_external_tracks

        def _added() -> None:
            self._hint_override = ""
            self._candidate = None
            self._build_table(keep_cursor=True)
            self._update_status()

        pick_external_tracks(self, self._decision, _added)

    def action_remove_track(self) -> None:
        i = self._current()
        if i is None:
            return
        self._tracks.pop(i)
        # Les index de reprise pointent sur une liste qui vient de bouger
        for t in self._tracks:
            if t.copied_from is not None:
                if t.copied_from == i:
                    t.sync_origin = SyncOrigin.MANUAL
                    t.copied_from = None
                elif t.copied_from > i:
                    t.copied_from -= 1
        self._build_table(keep_cursor=True)
        self._update_status()

    # ── Sortie ────────────────────────────────────────────────────────────────

    def _ready(self) -> bool:
        """Pistes présentes et toutes étiquetées, sinon on dit quoi corriger."""
        if not self._tracks:
            self.app.bell()
            self._set_hint(
                "Aucune piste à greffer — ajoutez-en une avec F9."
            )
            return False
        # Piste sans langue : on amène le curseur dessus au lieu de bloquer
        missing = next((i for i, t in enumerate(self._tracks) if not t.language), None)
        if missing is not None:
            self.app.bell()
            self._field_idx = _FIELDS.index("lang")
            self.query_one(DataTable).move_cursor(row=missing)
            self._refresh_all()
            self._set_hint(
                f"⚠ Mux impossible : « {self._tracks[missing].source_path.name} » "
                f"n'a pas de langue. Choisissez-la avec +/- ou ↵."
            )
            self._update_status()
            return False
        return True

    def action_run_mux(self) -> None:
        if not self._ready():
            return
        from .mux_run import MuxScreen

        def _after_mux(_res) -> None:
            # Le mux a pu adopter le fichier produit : la liste locale doit
            # refléter external_tracks, que MuxScreen vide en cas de succès.
            self._tracks = self._decision.external_tracks
            if not self._tracks:
                self.dismiss(self._tracks)
                return
            self._build_table(keep_cursor=True)
            self._update_status()

        self.app.push_screen(MuxScreen(self._decision), _after_mux)

    # ── Encodage direct : ffmpeg absorbe les pistes dans la même passe ────────

    def _encode_ready(self) -> bool:
        """
        Encoder greffe les pistes en une seule passe ffmpeg — sauf étirement.

        -itsoffset ne fait qu'un décalage constant : une piste à rééchelonner
        doit passer par mkvmerge d'abord.
        """
        if not self._ready():
            return False
        stretched = next((t for t in self._tracks if t.stretch), None)
        if stretched is None:
            return True

        # mkvmerge sait étirer : la greffe passera par lui juste avant
        # l'encodage, sans que l'utilisateur ait à enchaîner deux écrans.
        if getattr(self.app, "mkvmerge_available", False):
            self._set_hint(
                f"« {stretched.source_path.name} » demande un étirement : "
                f"mkvmerge greffera les pistes\njuste avant l'encodage, puis "
                f"ffmpeg encodera le résultat. Le fichier intermédiaire est "
                f"temporaire.")
            return True

        self.app.bell()
        self._set_hint(
            f"« {stretched.source_path.name} » demande un étirement, que "
            f"ffmpeg ne sait pas appliquer\nen une passe. Seul mkvmerge en "
            f"est capable — relancez le preflight pour l'installer.")
        return False

    def _launch(self, screen_factory) -> None:
        from core.decision import force_skip_to_encode
        self.app.push_screen(screen_factory(force_skip_to_encode(self._decision)))

    def action_dryrun(self) -> None:
        if not self._encode_ready():
            return
        from .dryrun import DryrunScreen
        self._launch(lambda dec: DryrunScreen([dec]))

    def action_run(self) -> None:
        if not self._encode_ready():
            return
        from .run import RunScreen
        self._launch(
            lambda dec: RunScreen([dec], self.app.platform))  # type: ignore[attr-defined]

    def action_go_back(self) -> None:
        self.dismiss(self._tracks)

    def action_accueil(self) -> None:
        """Retour à l'accueil — mais pas au prix d'un travail non validé.

        Cet écran porte des pistes greffées et leur recalage, que le dépilage
        ne rend à personne. Une mesure prend des minutes ; un raccourci en
        prend deux touches. La confirmation existe pour cet écart.
        """
        from .confirm import ConfirmModal

        def _apres(ok) -> None:
            if ok:
                retour_accueil(self.app)

        self.app.push_screen(ConfirmModal(
            "Revenir à l'accueil ?",
            "Les pistes greffées et leur recalage seront perdus.",
            confirm_label="Revenir", cancel_label="Rester", danger=True), _apres)
