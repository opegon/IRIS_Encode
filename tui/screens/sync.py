"""
tui/screens/sync.py — Recalage manuel des pistes externes avant mux.

Une ligne par piste greffée, chacune avec son propre décalage : ajouter une
VF et ses sous-titres se règle indépendamment, piste par piste.

Le bandeau du bas porte deux choses distinctes : sur sa première ligne, ce que
le champ sous le curseur sait faire — elle ne s'efface jamais — et sur les
suivantes le message du moment (avertissement, compte rendu de mesure).

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
from typing import Callable

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.events import Key
from textual.screen import Screen
from textual.widgets import DataTable, Label, ProgressBar, Static

from core.i18n import N_, _, liste, ngettext, texte_erreur
from core import preview
from core.decision import FileDecision
from core.muxer import (mkvmerge_reussi,
    ExternalTrack, MuxProcess, SyncOrigin, TrackKind, build_sample_command,
    ffmpeg_stream_index, noms_proposes, propager_recalage, sample_output_path,
    sample_windows, timecode,
)
from core.sync import (
    Segment, SyncResult, extract_subtitle, measure_external_track,
    measure_with_anchor, read_cues, reperes_proposables,
)

from ..common import (confier_a_la_file, langue_affichee, barre_etat, actions_ecran, footer_line2, colonne_fixe, libelle_type_piste, raccourcis, touche,
                      tronquer_milieu, retour_accueil)
from ..mixins import TableNavMixin
from ..widgets.entete import Entete
from ..widgets.footer import KeyFooter
from .segments import SegmentsScreen
from .value_picker import ValuePickerScreen

# Champs éditables, dans l'ordre de parcours ←/→
_FIELDS = ["delay", "stretch", "lang", "name", "default", "forced"]

_FIELD_LABELS = {
    "delay":   N_("Offset"),
    "stretch": N_("Stretch"),
    "lang":    N_("Language"),
    "name":    N_("Name"),
    "default": N_("Default"),
    "forced":  N_("Forced"),
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


def _noms(t: ExternalTrack) -> list[str]:
    """Les noms du champ Nom pour cette piste : « — » (aucun), puis ceux de sa
    langue (`core.muxer.noms_proposes`, L-77)."""
    return ["—", *noms_proposes(t.language)]

# Décalages proposés par ↵ sur le champ Décalage : le réglage fin reste
# sur +/-, mais la liste évite de marteler une touche pour partir de loin.
_DELAY_PRESETS = [-5000, -3000, -2000, -1000, -500, -250, 0,
                  250, 500, 1000, 2000, 3000, 5000]
_BOOLS = [N_("no"), N_("yes")]

# « Français (France) (forced) » fait 26 caractères : la colonne les tient.
# En dessous, deux pistes d'un même rip s'affichaient à l'identique.
_NAME_WIDTH = 26

# Planchers des colonnes : la plus longue valeur, dans chaque langue livrée
# (`tests/test_troncature.py`, IE-94). Une cellule réécrite en place ne
# recalcule pas sa largeur : trop courte, « measured » sortait « meas ».
_PLANCHERS = {"tid": 14, "delay": 12, "stretch": 11, "lang": 8,
              "name": _NAME_WIDTH, "default": 8, "forced": 7,
              "origin": 15}       # « copied from #10 »

# Trois pas pour le décalage. Le pas fin sert à finir le travail : une mesure
# rend souvent la bonne valeur à quelques dizaines de millisecondes près, et
# 100 ms est alors trop gros pour s'en approcher.
_DELAY_FINE_MS = 10
_DELAY_STEP_MS = 100
_DELAY_JUMP_MS = 1000

# Ce que sait faire le champ sous le curseur, et avec quelles touches. Sur le
# décalage les trois pas diffèrent ; ailleurs les mêmes touches font défiler
# les valeurs, et annoncer un pas en millisecondes y serait faux.
_FIELD_KEYS: dict[str, list[tuple[str, str]]] = {
    "delay":   [("Ctrl+↑/↓", "±10 ms"), ("+/-", "±100 ms"),
                ("⇧↑/↓", "±1 s"), ("enter", N_("List"))],
    "stretch": [("+/-", N_("Step through values")), ("enter", N_("List"))],
    "lang":    [("+/-", N_("Step through values")), ("enter", N_("List"))],
    "name":    [("+/-", N_("Step through values")), ("enter", N_("List"))],
    "default": [("+/-", N_("Switch")),              ("enter", N_("List"))],
    "forced":  [("+/-", N_("Switch")),              ("enter", N_("List"))],
}


def ligne_champ(field: str) -> str:
    """Ce que le champ actif sait faire — la ligne qui ne s'efface jamais.

    C'était la seule chose que l'écran ne disait nulle part. Le pied de page
    dérive des `BINDINGS`, où les touches d'édition sont `show=False` faute de
    place ; le bandeau les portait, mais un avertissement de langue ou un
    compte rendu de mesure prenait toute sa hauteur — c'est-à-dire dans les
    deux seules situations où l'on vient justement régler une valeur. Ne
    restait que l'état où tout va bien et où il n'y a rien à faire.
    """
    return _("{field}: {keys}").format(
        field=_(_FIELD_LABELS[field]),
        keys=raccourcis(_FIELD_KEYS[field] + [("←/→", N_("Other field"))]))


# Les actions de l'écran, en repli quand aucun message ne les remplace.
# Rendues à l'appel : `raccourcis` traduit, la langue n'est pas chargée à
# l'import (L-39).
def _hint() -> str:
    return raccourcis([("m", N_("Measure")), ("v", N_("Play")),
                       ("k", N_("Check sample")), ("c", N_("Copy")),
                       ("r", N_("Anchor")), ("F9", N_("Add")),
                       ("d", N_("Remove"))])


def _hint_no_lang() -> str:
    return "⚠ " + _("Missing language — +/- or {key} to choose it. Without it, "
                    "the track would come out as “und”.").format(key=touche("enter"))


class SyncScreen(TableNavMixin, Screen["list[ExternalTrack] | None"]):
    """Réglage du recalage de chaque piste externe, puis mux."""

    BINDINGS = [
        Binding("left",      "field_prev",   N_("Prev. field"),   show=False),
        Binding("right",     "field_next",   N_("Next field"),    show=False),
        # Alias clavier : selon la disposition, '+' arrive en 'plus',
        # 'equals_sign' ou depuis le pavé numérique.
        Binding("+,plus,equals_sign,kp_plus",   "val_up",   N_("Next value"), show=False),
        Binding("-,minus,kp_minus",             "val_down", N_("Prev. value"), show=False),
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
        Binding("enter",     "open_picker",  N_("List"),          show=True, priority=True),
        Binding("m",         "measure",      N_("Measure"),       show=True),
        Binding("v",         "preview",      N_("Play"),          show=True),
        Binding("k",         "sample",       N_("Sample"),        show=True),
        # `F` et `G` : `A` coche tout sur l'accueil, `S` passe un fichier
        # pendant l'encodage, `O` ouvre OpenSubtitles sur l'écran voisin (UX-12).
        Binding("f",         "apply_candidate",
                N_("Force"),  show=True),
        Binding("g",         "show_segments", N_("Segments"),   show=True),
        Binding("p",         "apply_segments",
                N_("Apply"),  show=True),
        Binding("c",         "copy_delay",   N_("Copy"),   show=True),
        Binding("r",         "ancrer",       N_("Anchor"), show=True),
        Binding("d",         "remove_track", N_("Remove"),        show=True),
        # F1/F2 gardent partout le même sens : dry-run et encodage. Le mux,
        # propre à cet écran, prend F3.
        Binding("f1",        "dryrun",       N_("Dry run"),       show=True),
        Binding("f2",        "run",          N_("Encode"),        show=True),
        Binding("f3",        "run_mux",      N_("Mux"),           show=True),
        Binding("f9",        "add_track",    N_("Add"), show=True),
        Binding("backspace", "go_back",      N_("Back"),          show=True),
        Binding("escape",    "go_back",      N_("Back"),          show=False, priority=True),
        # `priority` : un DataTable etouffe la touche avant les bindings —
        # meme avertissement qu'en tete de tui/mixins.py.
        Binding("ctrl+home", "accueil",   N_("Home"),       show=True,
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
        /* 4 lignes de texte + 1 pour la bordure : `height` couvre la boîte
           entière, bordure comprise. La première ligne est celle du champ
           actif et ne s'efface jamais ; les trois autres sont au message. À
           une de moins, la dernière ligne d'un refus de mesure disparaissait —
           celle qui renvoie vers F ou G, donc précisément l'indication
           dont l'utilisateur a besoin à ce moment-là. */
        height: 5;
        background: $primary-darken-1;
        color: $text;
        padding: 0 2;
        border-top: solid $primary;
    }
    """

    def __init__(self, decision: FileDecision) -> None:
        super().__init__()
        self._decision  = decision
        self._source    = decision.info.lecture
        tracks          = decision.external_tracks
        self._tracks    = tracks
        # Une piste sans langue bloque le mux : on ouvre directement sur ce
        # champ plutôt que de laisser chercher.
        self._field_idx = (_FIELDS.index("lang")
                           if any(not t.language for t in tracks) else 0)
        self._measuring = False
        self._sampling  = False
        self._hint_override: str = ""
        # Ce qui suit désigne des pistes par l'**objet**, jamais par son rang.
        # Une mesure dure des minutes ; `D` peut retirer une piste entre-temps,
        # et tous les rangs suivants glissent d'un cran. Le résultat s'écrivait
        # alors sur la piste voisine — et `_propager` le recopiait sur les
        # sous-titres du mauvais donneur, sans que rien ne le signale.
        #
        # (piste, décalage) proposé par une mesure refusée
        self._candidate: tuple[ExternalTrack, int] | None = None
        # (piste, plages) de la dernière mesure ayant constaté un montage
        # différent — consultables avec 'g', jamais appliquées
        self._segments: tuple[ExternalTrack, list[Segment]] | None = None

    # ── Composition ───────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Entete()
        yield Static("", id="status-bar", classes="status-bar", markup=False)
        yield DataTable(id="sync-table", cursor_type="row", zebra_stripes=False)
        with Static(id="sync-bar-row"):
            yield Label(_("Measurement in progress"), id="sync-bar-label")
            yield ProgressBar(total=100, show_eta=False, id="sync-bar")
        yield Static("", id="sync-hint", markup=False)
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

        # Les champs éditables portent le nom que leur donne `_FIELD_LABELS` :
        # un en-tête, un libellé (L-79).
        colonne_fixe(table, _("Source"), 28, key="src")
        colonne_fixe(table, _("Track"), _PLANCHERS["tid"], key="tid")
        for champ in _FIELDS:
            colonne_fixe(table, _(_FIELD_LABELS[champ]), _PLANCHERS[champ],
                         key=champ)
        colonne_fixe(table, _("Sync"), _PLANCHERS["origin"], key="origin")

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
            txt = langue_affichee(t.language)
            if not t.language:
                style = f"{style} bold dark_orange".strip()
        elif field == "name":
            # Six pistes « Français (…) » ne se distinguent que par leur fin :
            # une ellipse à droite les rendait toutes identiques.
            txt = tronquer_milieu(t.track_name or "—", _NAME_WIDTH)
        elif field == "default":
            txt = _(_BOOLS[t.is_default])
        else:
            txt = _(_BOOLS[t.is_forced])
        return Text(txt, style=style, no_wrap=True)

    def _row(self, i: int) -> tuple:
        t    = self._tracks[i]
        kind = libelle_type_piste(t.kind)
        origin = {
            SyncOrigin.NONE:     Text("—", style="dim"),
            SyncOrigin.MEASURED: Text(_("measured"), style="green"),
            SyncOrigin.MANUAL:   Text(_("manual"), style="cyan"),
            SyncOrigin.COPIED:   Text(
                _("copied from #{number}").format(number=(t.copied_from or 0) + 1),
                style="cyan"),
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
        warn    = ("⚠ " + ngettext("{count} track without a language",
                                   "{count} tracks without a language",
                                   missing).format(count=missing)) if missing else ""
        self.query_one("#status-bar", Static).update(barre_etat(
            "", self._source.name,
            ngettext("{count} track to add", "{count} tracks to add", n).format(count=n),
            _("Field: {field}").format(field=_(_FIELD_LABELS[_FIELDS[self._field_idx]])),
            warn,
        ))
        self._refresh_hint(missing)

    def _refresh_hint(self, missing: int | None = None) -> None:
        """Recompose le bandeau : le champ actif, puis le message.

        Chacun a sa ligne. Le message occupait la boîte entière, et chassait
        donc les touches d'édition exactement quand elles servent.
        """
        if missing is None:
            missing = sum(1 for t in self._tracks if not t.language)
        # Un message de mesure survit à la navigation : sans ça, la moindre
        # flèche effaçait le résultat et l'écran semblait n'avoir rien fait.
        message = self._hint_override or (_hint_no_lang() if missing else _hint())
        self.query_one("#sync-hint", Static).update(
            ligne_champ(_FIELDS[self._field_idx]) + "\n" + message
        )

    @on(DataTable.RowHighlighted)
    def _on_row_highlight(self, _evt: DataTable.RowHighlighted) -> None:
        self._refresh_all()

    # ── Navigation entre champs ───────────────────────────────────────────────

    def on_key(self, event: Key) -> None:
        # Pas de super().on_key : Textual appelle déjà celui des mixins, et
        # l'appel en plus doublait PageUp/PageDown (CR-80).
        if event.key in ("left", "right"):
            event.stop()
            event.prevent_default()
            self.action_field_prev() if event.key == "left" else self.action_field_next()

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

    def _rang(self, piste: ExternalTrack) -> int | None:
        """Où se trouve cette piste **maintenant**, ou None si elle a disparu.

        Comparaison par identité, pas par égalité : deux pistes issues du même
        fichier peuvent être égales au sens du dataclass tout en étant deux
        entrées distinctes de la liste.
        """
        for n, t in enumerate(self._tracks):
            if t is piste:
                return n
        return None

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
            noms = _noms(t)
            cur = noms.index(t.track_name) if t.track_name in noms else 0
            nxt = noms[(cur + delta) % len(noms)]
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
            opts  = _noms(t)
            cur   = opts.index(label) if label in opts else 0
        elif field == "stretch":
            opts = [_STRETCH_LABELS[s] for s in _STRETCH_CYCLE]
            cur  = _STRETCH_CYCLE.index(t.stretch) if t.stretch in _STRETCH_CYCLE else 0
        elif field == "delay":
            opts = [f"{d:+d} ms" for d in _DELAY_PRESETS]
            cur  = min(range(len(_DELAY_PRESETS)),
                       key=lambda k: abs(_DELAY_PRESETS[k] - t.delay_ms))
        else:
            opts = [_(b) for b in _BOOLS]
            cur  = int(t.is_default if field == "default" else t.is_forced)

        def _apply(choice: int | None) -> None:
            if choice is None:
                return
            if field == "lang":
                t.language = _LANGS[choice]
            elif field == "name":
                t.track_name = "" if opts[choice] == "—" else opts[choice]
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
            ValuePickerScreen(_(_FIELD_LABELS[field]), opts, cur), _apply
        )

    # ── Mesure automatique ────────────────────────────────────────────────────

    def action_measure(self) -> None:
        i = self._current()
        if i is None:
            return
        if self._measuring:
            self._set_hint(_("A measurement is already running — let it finish."))
            return
        self._measuring = True
        self._set_hint("⏳ " + _("Measuring “{file}”").format(
                           file=self._tracks[i].source_path.name) + "\n"
                       + _("Decoding the movie's audio — for a "
                           "feature-length movie, allow several tens of "
                           "seconds."))
        # Visible dans la ligne elle-même : la barre du bas peut passer inaperçue
        self._set_origin_cell(i, Text(_("measuring…"), style="yellow"))
        self._show_bar(True)
        self._measure(self._tracks[i])

    def _set_origin_cell(self, i: int, text: Text) -> None:
        try:
            self.query_one(DataTable).update_cell(
                str(i), "origin", text, update_width=False)
        except Exception:
            pass

    def _show_bar(self, visible: bool, libelle: str = "") -> None:
        """Affiche la barre, en nommant le travail réellement en cours.

        Un libellé qui parle de mesure pendant un recalage laisse croire à un
        blocage : l'opération semble ne jamais finir puisqu'elle n'a pas
        commencé.
        """
        try:
            self.query_one("#sync-bar-row").set_class(visible, "mesure")
            if visible:
                self.query_one("#sync-bar-label", Label).update(
                    libelle or _("Measurement in progress"))
                self.query_one("#sync-bar", ProgressBar).progress = 0
        except Exception:
            pass

    def _set_progress(self, fraction: float) -> None:
        try:
            self.query_one("#sync-bar", ProgressBar).progress = int(fraction * 100)
        except Exception:
            pass

    @work(thread=True, name="sync-measure")
    def _measure(self, t: ExternalTrack) -> None:
        """Corrélation hors du thread UI : le décodage audio prend du temps.

        La **piste** traverse le worker, pas son rang : la liste peut avoir
        bougé quand le résultat revient, plusieurs minutes plus tard.
        """
        def report(fraction: float) -> None:
            self.app.call_from_thread(self._set_progress, fraction)

        try:
            # La traduction du tid en index ffmpeg vit dans
            # `sync.measure_external_track` : elle ne doit exister qu'une fois.
            res = measure_external_track(self._source, t, progress=report,
                                         duration=self._decision.info.duration)
        except Exception as e:                       # ffmpeg absent, fichier illisible…
            res = SyncResult(0, None, 0.0, False, _("cannot measure: {error}").format(
                error=texte_erreur(e)))
        self.app.call_from_thread(self._apply_measure, t, res)

    def _apply_measure(self, piste: ExternalTrack, res: SyncResult) -> None:
        self._measuring = False
        self._show_bar(False)
        i = self._rang(piste)
        if i is None:
            return                                   # piste retirée entre-temps
        if not res.ok:
            self.app.bell()
            self._set_origin_cell(i, Text(_("failed"), style="bold dark_orange"))
            # Le candidat refusé reste applicable : il est souvent correct
            # malgré une confiance basse, et un décalage d'une minute est
            # hors de portée des touches +/-.
            self._candidate = (piste, res.best_delay_ms)
            self._segments  = (piste, res.segments) if res.segments else None
            if res.segments:
                # report() porte déjà les paliers et renvoie vers 'g' :
                # proposer d'appliquer un décalage unique serait ici trompeur.
                self._set_hint(res.report())
            else:
                self._set_hint(res.report() + "\n"
                               + _("{key} applies {delay} ms anyway — check it "
                                   "in a player.").format(
                                   key=touche("f"), delay=f"{res.best_delay_ms:+d}"))
            return
        self._candidate = None
        self._segments  = None
        t = piste
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
        return "\n" + ngettext(
            "{count} subtitle from the same file resynced by the same amount "
            "— {key} to copy from another one.",
            "{count} subtitles from the same file resynced by the same amount "
            "— {key} to copy from another one.", n).format(count=n, key=touche("c"))

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
            self._set_hint(_("The anchor point is for subtitles: an audio track "
                             "is measured directly with {key}.").format(key=touche("m")))
            return

        # Les répliques proposées viennent du fichier lui-même : une piste
        # embarquée doit d'abord être extraite, comme pour la mesure.
        self._en_texte(t, lambda src: self._proposer_reperes(t, src))

    def _proposer_reperes(self, t: ExternalTrack, src: Path) -> None:
        from .ancrage import AncrageModal

        try:
            reperes = reperes_proposables(src)
        except Exception as e:                       # noqa: BLE001
            self._set_hint(_("Cannot read the subtitle lines: {error}").format(
                error=texte_erreur(e)))
            return
        if not reperes:
            self._set_hint(_("No readable line in this track."))
            return

        def _apres(points) -> None:
            i = self._rang(t)
            if points is None or i is None:
                return
            ecrit, entendu = points
            self._measuring = True
            self._set_hint("⏳ " + _("Searching around {offset} s.").format(
                               offset=f"{entendu - ecrit:+.1f}") + "\n"
                           + _("Decoding the movie's audio — allow several tens "
                               "of seconds."))
            self._set_origin_cell(i, Text(_("measuring…"), style="yellow"))
            self._show_bar(True)
            self._mesure_ancree(t, ecrit, entendu)

        self.app.push_screen(
            AncrageModal(reperes, t.track_name or t.source_path.name), _apres)

    # ── Sous-titre embarqué : extraction hors du fil de l'écran ───────────────

    def _en_texte(self, t: ExternalTrack, suite: Callable[[Path], None],
                  direct: tuple[str, ...] = (".srt",)) -> None:
        """Appelle `suite` avec le sous-titre de `t` en fichier texte.

        Un sous-titre embarqué s'extrait en lisant tout le donneur : des
        minutes sur un partage, que le fil de l'écran ne doit pas attendre.
        L'extraction avait un délai de 120 s et gelait l'écran jusque-là
        (CR-35) ; elle tourne maintenant à part, avec sa barre. Un fichier
        dont l'extension est dans `direct` est passé tel quel.
        """
        if t.source_path.suffix.lower() in direct:
            suite(t.source_path)
            return
        self._measuring = True
        self._set_hint("⏳ " + _("Extracting the subtitle track — the whole donor "
                                "file is read."))
        self._show_bar(True)
        self._extraire(t, suite)

    @work(thread=True, name="sync-extraction")
    def _extraire(self, t: ExternalTrack, suite: Callable[[Path], None]) -> None:
        def report(fraction: float) -> None:
            self.app.call_from_thread(self._set_progress, fraction)

        try:
            idx = ffmpeg_stream_index(t.source_path, t.source_tid, TrackKind.SUBTITLE)
            src, erreur = extract_subtitle(t.source_path, idx, report,
                                           self._decision.info.duration), ""
        except Exception as e:                       # noqa: BLE001
            src, erreur = None, texte_erreur(e)
        self.app.call_from_thread(self._extrait, suite, src, erreur)

    def _extrait(self, suite: Callable[[Path], None], src: Path | None,
                 erreur: str) -> None:
        self._measuring = False
        self._show_bar(False)
        if src is None:
            self.app.bell()
            self._set_hint(_("Cannot extract the subtitle track: {error}").format(
                error=erreur))
            return
        suite(src)

    @work(thread=True, name="sync-ancrage")
    def _mesure_ancree(self, t: ExternalTrack, ecrit: float,
                       entendu: float) -> None:
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
            res = SyncResult(0, None, 0.0, False, _("cannot measure: {error}").format(
                error=texte_erreur(e)))
        self.app.call_from_thread(self._apply_measure, t, res)

    def _set_hint(self, text: str) -> None:
        """Message persistant : il survit à la navigation entre champs.

        Passe par `_refresh_hint` : écrire directement dans le bandeau
        effacerait la ligne du champ actif, que ce message ne remplace pas.
        """
        self._hint_override = text
        self._refresh_hint()

    def action_apply_candidate(self) -> None:
        """
        Applique le décalage d'une mesure refusée.

        Une confiance basse ne veut pas dire que la valeur est fausse : sur
        une bande-son dense, le bon décalage sort souvent avec un score
        médiocre. Et un décalage de l'ordre de la minute serait inatteignable
        avec +/-.
        """
        if self._candidate is None:
            self._set_hint(_("No candidate pending — run a measurement with "
                             "{key} first.").format(key=touche("m")))
            return
        piste, delay = self._candidate
        i = self._rang(piste)
        if i is None:                       # piste retirée depuis la mesure
            self._candidate = None
            self._set_hint(_("The measured track has been removed — the "
                             "candidate no longer applies to anything."))
            return
        t = piste
        t.delay_ms    = delay
        t.sync_origin = SyncOrigin.MANUAL     # non validé par la corrélation
        t.copied_from = None
        self._candidate = None
        self._refresh_row(i)
        # Un candidat forcé reste une décision de l'utilisateur : les
        # sous-titres du même donneur la suivent comme ils suivraient une
        # mesure.
        self._set_hint(_("Candidate applied: {delay} ms — not confirmed by the "
                         "measurement, check it in a player before "
                         "muxing.").format(delay=f"{delay:+d}")
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
            self._set_hint(_("No segment to show — they only appear after a "
                             "measurement that found a different cut."))
            return
        piste, segs = self._segments
        nom = piste.source_path.name if self._rang(piste) is not None else ""
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
            self._set_hint(_("No known segment — first measure the donor's "
                             "audio track with {key}.").format(key=touche("m")))
            return

        if self._measuring:
            self._set_hint(_("An operation is already running — let it finish."))
            return

        segs = self._segments[1]
        t = self._tracks[i]
        if t.kind == TrackKind.SUBTITLE:
            self._en_texte(t, lambda src: self._build_corrected_subtitle(t, src, segs))
            return

        # L'audio ne se corrige pas en décalant des nombres : il faut le
        # rallonger aux points de bascule et le réencoder. C'est long, donc
        # hors du thread UI.
        self._measuring = True
        self._set_hint("⏳ " + ngettext("Resyncing “{file}” over {count} segment.",
                                       "Resyncing “{file}” over {count} segments.",
                                       len(segs)).format(file=t.source_path.name,
                                                         count=len(segs))
                       + "\n" + _("Decoding then re-encoding the track — allow a "
                                  "handful of minutes."))
        self._set_origin_cell(i, Text(_("resyncing…"), style="yellow"))
        self._show_bar(True, _("Resync in progress"))
        self._retime(t, segs)

    # La piste est désignée par l'objet, pas par son rang : `D` pendant le
    # recalage faisait glisser les rangs, et l'audio recalée s'écrivait sur la
    # piste voisine (CR-92) — le défaut que `_measure` avait déjà corrigé.
    @work(thread=True, name="sync-retime")
    def _retime(self, t: ExternalTrack, segs: list[Segment]) -> None:
        """Fabrique la piste audio recalée hors du thread UI."""
        from core.sync import retime_audio

        def report(fraction: float) -> None:
            self.app.call_from_thread(self._set_progress, fraction)

        try:
            idx = ffmpeg_stream_index(t.source_path, t.source_tid, TrackKind.AUDIO)
            out = self._fichier_recale(t, ".mka")
            fichier, notes = retime_audio(t.source_path, idx, segs, out,
                                          progress=report)
        except Exception as e:
            fichier, notes = None, [texte_erreur(e)]
        self.app.call_from_thread(self._retime_done, t, fichier, notes)

    def _retime_done(self, t: ExternalTrack, fichier: Path | None,
                     notes: list[str]) -> None:
        self._measuring = False
        self._show_bar(False)
        i = self._rang(t)
        if i is None:
            return                                   # piste retirée entre-temps
        if fichier is None:
            self.app.bell()
            self._set_origin_cell(i, Text(_("failed"), style="bold dark_orange"))
            self._set_hint(_("Cannot resync.") + "\n" + " · ".join(notes))
            return

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
            _("Track resynced — offset now zero.") + "\n"
            f"{fichier.name}{reserve}\n"
            + _("{play_key} to check in mpv, {sample_key} for a muxed "
                "sample.").format(play_key=touche("v"), sample_key=touche("k")))

    def _build_corrected_subtitle(self, t: ExternalTrack, src: Path,
                                  segs: list[Segment]) -> None:
        from core.sync import shift_srt

        i = self._rang(t)
        if i is None:
            return                                   # piste retirée entre-temps
        try:
            out = self._fichier_recale(t, ".srt")
            shift_srt(src, segs, out)
        except Exception as e:
            self.app.bell()
            self._set_hint(_("Cannot correct: {error}").format(error=texte_erreur(e)))
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
            ngettext("Subtitle resynced over {count} segment ({steps} ms) — "
                     "offset now zero.",
                     "Subtitle resynced over {count} segments ({steps} ms) — "
                     "offset now zero.", len(segs)).format(count=len(segs),
                                                           steps=paliers) + "\n"
            f"{out.name}\n"
            + _("{play_key} to check in mpv, {sample_key} for a muxed "
                "sample.").format(play_key=touche("v"), sample_key=touche("k")))

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
            self._set_hint(_("mpv missing — run the preflight again to install it."))
            return

        t = self._tracks[i]
        if t.kind == TrackKind.SUBTITLE:
            # Un donneur conteneur, donné tel quel à `--sub-file`, montrait sa
            # première piste — souvent la « forced » — et non celle choisie
            # (CR-52). mpv reçoit la piste extraite, et la première réplique
            # se lit dans du texte, plus dans le conteneur.
            self._en_texte(t, lambda src: self._ouvrir_mpv(t, src),
                           direct=(".srt", ".ass", ".ssa", ".vtt"))
        else:
            self._ouvrir_mpv(t, None)

    def _ouvrir_mpv(self, t: ExternalTrack, sous_titre: Path | None) -> None:
        try:
            first_cue = None
            donor_idx = 0
            if sous_titre is not None:
                cues = read_cues(sous_titre)
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
                sub_file=sous_titre,
            )
            preview.launch(cmd)
        except Exception as e:
            self.app.bell()
            self._set_hint(_("Cannot start mpv: {error}").format(error=texte_erreur(e)))
            return

        if t.stretch:
            self._set_hint(
                _("mpv opened with {delay} ms.").format(delay=f"{t.delay_ms:+d}") + "\n"
                + "⚠ " + _("The stretch cannot be previewed — mpv can only apply "
                           "a constant offset.") + "\n"
                + _("{keys}, then enter the value here.").format(keys=preview.keys_hint(t)))
        else:
            self._set_hint(
                _("mpv opened with {delay} ms applied.").format(delay=f"{t.delay_ms:+d}") + "\n"
                f"{preview.keys_hint(t)}.\n"
                + _("Then enter the corrected value in this screen."))

    # ── Extrait de contrôle ───────────────────────────────────────────────────

    def action_sample(self) -> None:
        """
        Produit un court extrait réellement muxé, puis l'ouvre dans mpv.

        C'est le seul contrôle honnête d'un facteur d'étirement : ni mpv ni la
        corrélation ne le prévisualisent. Sans étirement, une fenêtre suffit ;
        avec, on en prend deux — tôt et tard — parce que la dérive s'accumule.
        """
        if self._measuring or self._sampling:
            self._set_hint(_("An operation is already running."))
            return
        if not self._ready():
            return
        self._sampling = True
        self._show_bar(True)
        self._set_hint("⏳ " + _("Building the check sample…"))
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
            self.app.call_from_thread(self._sample_done, None, texte_erreur(e), starts)
            return

        proc = MuxProcess(cmd)
        proc.start()
        for _line, pct in proc.iter_progress():
            if pct is not None:
                self.app.call_from_thread(self._set_progress, pct / 100)
        rc = proc.wait()
        # Code 1 : des avertissements, l'extrait vaut (CR-89).
        erreur = (None if mkvmerge_reussi(rc, out)
                  else (proc.errors[0] if proc.errors else f"code {rc}"))
        self.app.call_from_thread(self._sample_done, out, erreur, starts)

    def _fichier_recale(self, piste, extension: str) -> Path:
        """Où écrire une piste recalée : à côté de la sortie, sous un nom
        d'intermédiaire, effacé avec eux après l'encodage. Une piste audio de
        film n'a rien à faire dans le dossier temporaire du système, où rien
        ne l'effaçait et où un nettoyage pouvait la retirer avant son tour dans
        la file (CR-93). Dossier de sortie en lecture seule (choisi seulement à
        la mise en file) : le dossier temporaire, faute de mieux."""
        import tempfile
        from core.decision import dossier_inscriptible
        from core.scanner import intermediaire
        dossier = self._decision.dossier_sortie
        if not dossier_inscriptible(dossier):
            dossier = Path(tempfile.gettempdir())
        nom = f"{self._decision.info.path.stem}_{piste.language or 'und'}"
        return dossier / f"{intermediaire(nom, 'recale')}{extension}"

    def _sample_done(self, out, erreur: str | None, starts: list[float]) -> None:
        self._sampling = False
        self._show_bar(False)
        if erreur:
            self.app.bell()
            self._set_hint("✗ " + _("Cannot build the sample: {error}").format(error=erreur))
            return

        fenetres = liste(timecode(s) for s in starts)
        if preview.available():
            try:
                preview.open_file(out)
            except Exception as e:
                self._set_hint(_("Sample ready: {path}").format(path=out) + "\n"
                               + _("mpv could not open it: {error}").format(
                                   error=texte_erreur(e)))
                return
            self._set_hint(
                _("Sample opened in mpv — windows at {times}.").format(times=fenetres)
                + "\n" + _("This is the actual mux result: what you hear is what "
                           "{key} will produce.").format(key=touche("f3")))
        else:
            self._set_hint(_("Sample ready (mpv missing): {path}").format(path=out)
                           + "\n" + _("Windows at {times}.").format(times=fenetres))

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
            ValuePickerScreen(_("Copy the offset from"), opts, 0), _apply
        )

    def action_add_track(self) -> None:
        """
        Greffe une piste supplémentaire sans quitter l'écran.

        Une VF et ses sous-titres vivent dans deux fichiers distincts : les
        ajouter devait sinon passer par un aller-retour vers l'écran des
        pistes entre les deux.
        """
        if self._measuring:
            self._set_hint(_("Measurement in progress — wait for it to finish "
                             "before adding a track."))
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
        # Retirer une piste fait glisser les rangs des suivantes : pas pendant
        # une opération qui écrira son résultat sur l'une d'elles (CR-92).
        if self._measuring:
            self.app.bell()
            self._set_hint(_("An operation is already running — let it finish."))
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
                _("No track to add — add one with {key}.").format(key=touche("f9"))
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
                "⚠ " + _("Cannot mux: “{file}” has no language. Choose it with "
                         "+/- or {key}.").format(
                    file=self._tracks[missing].source_path.name, key=touche("enter"))
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
                _("“{file}” needs a stretch: mkvmerge will add the tracks just "
                  "before encoding, then ffmpeg will encode the result. The "
                  "intermediate file is temporary.").format(
                    file=stretched.source_path.name))
            return True

        self.app.bell()
        self._set_hint(
            _("“{file}” needs a stretch, which ffmpeg cannot apply in one pass. "
              "Only mkvmerge can — run the preflight again to install "
              "it.").format(file=stretched.source_path.name))
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
        from core.decision import force_skip_to_encode
        confier_a_la_file(self.app, [force_skip_to_encode(self._decision)])

    def action_go_back(self) -> None:
        """Rend les pistes à l'écran appelant — mais pas pendant une mesure.

        `dismiss` remet la liste à l'écran des pistes, qui la tient pour
        validée. Un worker encore en vol continuerait d'écrire dedans
        **après** cette validation : l'état accepté changerait dans le dos de
        l'utilisateur, sans un mot à l'écran.

        Les cinq autres actions longues refusent déjà de la même façon ; celle
        qui sort de l'écran n'avait pas de raison d'y échapper.
        """
        if self._measuring:
            self._set_hint(_("Measurement in progress — wait for it to finish "
                             "before going back. The gauge shows how far it "
                             "has got."))
            return
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
            _("Go back to Home?"),
            _("The added tracks and their resync will be lost."),
            confirm_label=_("Go back"), cancel_label=_("Stay"), danger=True), _apres)
