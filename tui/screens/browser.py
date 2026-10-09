"""
tui/screens/browser.py — Écran Browser IRIS ENCODE.

Navigation fichiers avec DataTable, sélection par case, colonnes redimensionnables.
"""
from __future__ import annotations

import logging
from copy import deepcopy
import math
import threading
from concurrent.futures import ThreadPoolExecutor
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from rich.text import Text
from textual import events, on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Static

from core.i18n import N_, _, ngettext, texte_erreur
from core import config as cfg_mod
from core import preview
from core.annexes import supprimer_annexes
from core.decision import (
    Emphase,
    STYLE_PAR_EMPHASE,
    AudioAction, FileDecision, Reglages, VideoAction, appliquer_reglages, decide,
    force_skip_to_encode, reglages_explicites, video_recopiee,
)
from core.scanner import (SCAN_WORKERS, deja_produit, scan,
                          scan_directory_recursive)
from ..common import sauver_config
from ..common import (barre_etat, colonne_fixe,
    touche,
    cellule,
    DV_VALUE_STYLES,
    estimate_encoding_duration,
    fmt_bytes,
    fmt_duration,
    footer_line2,
    get_measured_speed,
)
from ..mixins import ColumnResizeMixin, TableNavMixin
from ..widgets.file_tree import FileNavigator
from ..widgets.entete import Entete
from ..widgets.footer import KeyFooter

if TYPE_CHECKING:
    from ..app import IrisEncodeApp

_LOG = logging.getLogger(__name__)

# ─── Constantes ───────────────────────────────────────────────────────────────

_DIR_ICON  = "📁"
_DISK_ICON = "💾"   # icône volume/disque
_FILE_ICON = "🎬"


# ─── Estimation de taille ─────────────────────────────────────────────────────

def _cellules_volume(volume: Path) -> tuple[Text, Text, Text]:
    """Espace libre, total et taux d'occupation d'un volume.

    Un lecteur vide ou un partage réseau injoignable fait lever `disk_usage` :
    on rend alors des tirets plutôt que de faire disparaître la ligne — le
    volume existe, c'est sa mesure qui manque.
    """
    try:
        usage = shutil.disk_usage(volume)
    except OSError:
        tiret = Text("—", style="dim", no_wrap=True)
        return tiret, Text("—", style="dim", no_wrap=True), Text("—", style="dim", no_wrap=True)

    part = (usage.used / usage.total * 100) if usage.total else 0
    # Un volume presque plein mérite d'être signalé : c'est là qu'un encodage
    # échouera faute de place.
    style_occupe = STYLE_PAR_EMPHASE[
        Emphase.ALERTE if part >= 90 else Emphase.ORDINAIRE]
    return (
        Text(fmt_bytes(usage.free), no_wrap=True),
        Text(fmt_bytes(usage.total), style="dim", no_wrap=True),
        Text(f"{part:.0f}%", style=style_occupe, no_wrap=True),
    )


def sources_reussies(lots: list) -> set[Path]:
    """Les sources encodées avec succès, tous lots confondus (UX-04)."""
    from .run import FileState
    return {s.decision.info.path for lot in lots for s in lot
            if s.state == FileState.SUCCESS}


def _sortie_recopiee(dec: FileDecision) -> bool:
    """La sortie pèsera-t-elle exactement ce que pèse la source ?

    Un remux ne recalcule aucune image : la sortie pèse ce que pèse la source,
    au RPU près — quelques mégaoctets sur un film. Une source Dolby Vision dont
    le RPU ne peut pas être réinjecté est dans le même cas : sa vidéo est
    recopiée, et l'estimer au débit cible annoncerait une réduction qui n'aura
    pas lieu.

    L'estimation et le dégradé lisent le même prédicat : une ligne dont la
    taille ne bouge pas ne doit pas non plus prendre de couleur.
    """
    return (dec.video.action == VideoAction.STRIP_DV
            or video_recopiee(dec.video.action, dec.video.dv_action))


# Bornes du dégradé de la colonne Estim, en pourcentage d'écart à la source :
# gris tant que l'écart affiché reste dans ±5 %, teinte pleine à ±100 %, et
# au-delà la teinte ne bouge plus. Un gain ne dépasse jamais 100 % ; une perte
# peut, et reste orange.
_SEUIL_NEUTRE  =    5.0
_DEGRADE_GAIN  = -100.0
_DEGRADE_PERTE =  100.0
# Courbe logarithmique : la teinte avance vite sur les petits écarts, puis se
# tasse. Plus `_COURBURE` est grand, plus le début est raide.
_COURBURE      =   20.0
_TEINTE_NEUTRE = (138, 138, 138)   # gris
# Ni le gain ni la perte ne partent du gris : dès la sortie de la zone neutre,
# la teinte doit se lire. L'orange final est celui des alertes (#ff8700).
_TEINTE_GAIN_MIN  = (120, 200, 120)   # vert clair
_TEINTE_GAIN      = (  0, 230,  60)   # vert vif
_TEINTE_PERTE_MIN = (255, 190,  90)   # orange clair
_TEINTE_PERTE     = (255, 135,   0)   # orange sombre


def _teinte_estimation(delta_pct: float) -> str:
    """Style Rich d'un écart de taille : vert si la sortie maigrit, orange si
    elle grossit, gris quand l'écart affiché reste dans ±5 %.

    **Exception assumée à la table d'emphases** (`core.decision.Emphase`). Le
    vert y dit « traité sans réencodage » et cette colonne lui fait dire « la
    sortie est plus petite » ; sur une même ligne, le vert de la colonne
    Décision et celui d'Estim ne parlent donc pas de la même chose. C'est le
    prix d'une échelle continue, et il se paie ici seul : la table reste la
    seule autorité partout ailleurs, et aucune autre couleur n'est écrite en
    dur dans cet écran.
    """
    def _melange(a, b, k: float) -> str:
        k = max(0.0, min(1.0, k))
        r, v, bl = (round(x + (y - x) * k) for x, y in zip(a, b))
        return f"rgb({r},{v},{bl})"

    # Seuil lu sur la valeur arrondie : la cellule qui affiche « 5% » est grise.
    if abs(round(delta_pct)) <= _SEUIL_NEUTRE:
        return _melange(_TEINTE_NEUTRE, _TEINTE_NEUTRE, 0)

    def _progression(borne: float) -> float:
        x = (abs(delta_pct) - _SEUIL_NEUTRE) / (abs(borne) - _SEUIL_NEUTRE)
        x = max(0.0, min(1.0, x))
        return math.log1p(_COURBURE * x) / math.log1p(_COURBURE)

    if delta_pct < 0:
        return _melange(_TEINTE_GAIN_MIN, _TEINTE_GAIN, _progression(_DEGRADE_GAIN))
    return _melange(_TEINTE_PERTE_MIN, _TEINTE_PERTE, _progression(_DEGRADE_PERTE))


def _estimate_output_bytes(dec: FileDecision,
                           taille_source: int | None = None) -> int:
    """Taille estimée de sortie (vidéo + audio conservé).
    Retourne 0 si action=SKIP ou durée inconnue.

    `taille_source`, si l'appelant la connaît déjà, évite de relire le disque.
    """
    if dec.video.action == VideoAction.SKIP:
        return 0
    if _sortie_recopiee(dec):
        if taille_source is not None:
            return taille_source
        try:
            return dec.info.taille
        except OSError:
            return 0
    duration = dec.info.duration
    if duration <= 0:
        return 0
    video_bps = dec.video.target_bitrate
    audio_bps = 0
    for ad in dec.audio:
        if ad.action == AudioAction.EXCLUDE:
            continue
        if ad.action == AudioAction.COPY:
            audio_bps += ad.track.bitrate or 192_000
        else:
            audio_bps += ad.output_bitrate
    total_bits = (video_bps + audio_bps) * duration
    return int(total_bits / 8)

# ─── Filtre de l'accueil (L, Z) ───────────────────────────────────────────────

FILTRE_TOUS = "tous"
FILTRE_DV   = "dv"      # Dolby Vision, tous profils


def type_image(info) -> str:
    """Le type d'image d'une source : son profil DV (`DV:P8.1`), `HDR` ou `SDR`."""
    if info.dv_profile is not None:
        return info.dv_label
    return "HDR" if info.is_hdr else "SDR"


def ligne_visible(dec: FileDecision, filtre: str, masquer_skip: bool,
                  cochee: bool) -> bool:
    """La ligne passe-t-elle le filtre ?

    Une ligne cochée reste visible quoi qu'il arrive : ce qui partira à
    l'encodage ne doit pas pouvoir disparaître de la vue.
    """
    if cochee:
        return True
    if masquer_skip and dec.video.action == VideoAction.SKIP:
        return False
    if filtre == FILTRE_TOUS:
        return True
    genre = type_image(dec.info)
    if filtre == FILTRE_DV:
        return genre.startswith("DV:")
    return genre == filtre


def options_filtre(decisions: list[FileDecision]) -> list[tuple[str, str]]:
    """Les choix du filtre, limités aux types présents, avec leur nombre."""
    genres  = [type_image(d.info) for d in decisions]
    dv      = sorted({g for g in genres if g.startswith("DV:")})
    options = [(FILTRE_TOUS, _("All files ({count})").format(count=len(genres)))]
    if dv:
        options.append((FILTRE_DV, _("Dolby Vision, all profiles ({count})").format(
            count=sum(g.startswith('DV:') for g in genres))))
        options += [(g, f"  {g} ({genres.count(g)})") for g in dv]
    if "HDR" in genres:
        options.append(("HDR", _("HDR10 / HLG, without DV ({count})").format(
            count=genres.count('HDR'))))
    if "SDR" in genres:
        options.append(("SDR", f"SDR ({genres.count('SDR')})"))
    return options


def libelle_filtre(filtre: str) -> str:
    return {FILTRE_TOUS: "", FILTRE_DV: "Dolby Vision"}.get(filtre, filtre)


# Marqueurs de ligne dans la table
_ROW_TYPE_DIR   = "dir"
_ROW_TYPE_FILE  = "file"
_ROW_TYPE_EMPTY = "empty"  # placeholder dossier vide


class BrowserScreen(TableNavMixin, ColumnResizeMixin, Screen):
    """Écran principal — navigation + sélection fichiers."""

    BINDINGS = [
        Binding("space",     "toggle_select",      N_("Toggle"),   show=True),
        Binding("a",         "select_all",         N_("All"),      show=True),
        Binding("n",         "select_none",        N_("None"),     show=True),
        Binding("enter",     "enter_dir",          N_("Open"),     show=True, priority=True),
        Binding("backspace", "go_up",              N_("Up"),       show=True),
        Binding("ctrl+home", "accueil",            N_("Home"),     show=True,
                priority=True),
        # Visible : en mode assistant, c'est le seul accès aux pistes (UX-25).
        Binding("t",         "open_tracks",        N_("Tracks"),   show=True),
        Binding("w",         "toggle_wizard",      N_("Mode"),     show=True),
        Binding("v",         "play",               N_("Play"), show=True),
        # Les touches de fonction ont un seul sens dans toute l'application
        # (UX-07) ; ce qui n'existe qu'ici passe sur des lettres.
        Binding("r",         "recursive_run",      N_("Encode the folder"), show=True),
        Binding("j",         "join_parts",         N_("Join parts"),  show=True),
        Binding("i",         "open_fiche",         N_("Info"),     show=True),
        Binding("ctrl+d",    "delete_file",        N_("Delete"),   show=True),
        Binding("l",         "filtre_type",        N_("Filter"),   show=True),
        Binding("z",         "masquer_skip",       N_("Hide SKIP"), show=True),
        Binding("f1",       "open_dryrun",        N_("Dry run"),  show=True),
        Binding("f2",        "open_run",           N_("Encode"),   show=True),
        Binding("f4",        "open_profile_picker",N_("Profile"),  show=True),
        Binding("f5",        "open_config",        N_("Manage"),   show=True),
    ]

    # Colonnes redimensionnables (ColumnResizeMixin) — fichier en premier pour accès au focus
    RESIZE_COLS   = ["fichier", "taille", "resolution", "duree", "debit", "codec",
                     "dolby_vision", "decision", "estim", "temps_estim", "audio"]
    RESIZE_LABELS = {"fichier": N_("File"), "taille": N_("Size"),
                     # TRANSLATORS: column header, short for "Resolution".
                     "resolution": N_("Res."),
                     "duree": N_("Duration"), "debit": N_("Bitrate"), "codec": N_("Codec"),
                     "dolby_vision": "Dolby V.", "decision": N_("Decision"),
                     "estim": N_("Est. (Δ%)"),
                     "temps_estim": "ETA", "audio": N_("Audio")}
    # Les planchers imposés par le contenu viennent de core.config, seule
    # source de vérité : ils valent aussi à la lecture d'une largeur persistée.
    # Fichier à 20 : à 160 colonnes, les autres ne lui en laissent que 29.
    RESIZE_MIN    = {"fichier": 20, "audio": 10, **cfg_mod.COLUMN_MIN_WIDTHS}
    RESIZE_FIXE   = 3 + 2 + 2   # case à cocher, sa marge, barre de défilement

    DEFAULT_CSS = """
    BrowserScreen {
        layout: vertical;
    }
    #spacer-1 {
        height: 1;
    }
    #profile-bar {
        height: 2;
        background: $primary-darken-1;
        color: $text;
        padding: 0 1;
        border-bottom: solid $primary;
    }
    #scan-notice {
        height: 1;
        color: $text-muted;
        padding: 0 2;
    }
    #file-table { height: 1fr; }
    """

    def __init__(self, path: Path, start_virtual: bool = False) -> None:
        super().__init__()
        self._nav        = FileNavigator(path, start_virtual=start_virtual)
        # Jeu de colonnes actuellement en place — volumes ou fichiers.
        self._colonnes_volumes = start_virtual
        self._decisions:  dict[Path, FileDecision] = {}
        self._selected:   set[Path] = set()
        self._rows:       list[tuple[str, Path | None]] = []
        # Les lignes qui sont des sorties de l'application : grisées, hors de
        # `Ctrl+A`, mais sélectionnables et encodables comme les autres.
        self._produits:   set[Path] = set()
        # Override audio par fichier (TUI tracks)
        self._audio_overrides:    dict[Path, list[int]] = {}
        self._subtitle_overrides: dict[Path, list[int]] = {}
        # Codec, débit, profil, suppression et greffes réglés à la main sur un
        # fichier : réappliqués à chaque analyse du dossier (CR-74).
        self._reglages:   dict[Path, "Reglages"] = {}
        # Les réussites de lot déjà reflétées par la vue : un retour à l'accueil
        # pendant un lot ne rescanne que si le disque a changé depuis (CR-74).
        self._reussites_vues: set[Path] = set()
        # Taille de chaque fichier, relevée par le worker de scan. Chaque touche
        # `<`/`>` reconstruit la table : sur un partage réseau, relire la taille
        # de chaque ligne à chaque frappe coûtait plusieurs secondes.
        self._tailles:    dict[Path, int | None] = {}
        self._scan_epoch: int = 0
        # Le relevé différé d'un changement de taille de la fenêtre (`on_resize`).
        self._minuterie_largeur = None
        # Filtre de la vue (L, Z) : tient pour la session, d'un dossier à l'autre.
        # `_dossier` garde tous les fichiers du dossier, masqués compris.
        self._filtre       = FILTRE_TOUS
        self._masquer_skip = False
        self._dossier:    list[Path] = []
        # Le dossier de disque dont le titre principal a été coché d'office
        # (IE-120) : une fois par visite, pour qu'un rescan ne recoche pas ce
        # que l'utilisateur a décoché ni ce qui vient d'être encodé.
        self._precoche:   Path | None = None

    # ─── Accesseurs app ───────────────────────────────────────────────────────

    @property
    def _app(self) -> "IrisEncodeApp":
        return self.app  # type: ignore[return-value]

    def _active_profile(self):
        return self._app.profiles[self._app.active_profile_id]

    # ─── Composition ──────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Entete()
        yield Static("", id="status-bar", classes="status-bar", markup=False)
        yield Static("", id="spacer-1")
        yield Static("", id="profile-bar")
        analyse = "⏳ " + _("Analyzing…")
        yield Static(analyse, id="scan-notice", markup=False)
        yield DataTable(id="file-table", cursor_type="row", zebra_stripes=True)
        yield KeyFooter(
            actions=self._RACCOURCIS_FICHIERS,
            nav=footer_line2(
                nav=False,
                resize=True,
                accueil=True,
                extra=(
                    ("f1", N_("Dry run")),
                    ("f2", N_("Encode")),
                    ("f4", N_("Profile")),
                    ("f5", N_("Manage")),
                ),
            ),
        )

    def on_screen_resume(self) -> None:
        """Retour d'un encodage : la vue et la sélection suivent le disque.

        Sans cela les sorties produites n'apparaissaient pas, et `F2`
        relançait le même lot (UX-04). Seuls les fichiers réussis se
        décochent : un fichier en échec ou interrompu reste prêt à relancer.
        """
        lots = self._app.lots_encodes
        if not lots:
            return
        reussies = sources_reussies(lots)
        self._selected -= reussies
        # Un lot encore en cours produira d'autres réussites : on ne le lâche
        # qu'une fois fini (IE-100).
        lot = self._app.lot
        lots[:] = [l for l in lots
                   if lot is not None and l is lot.statuts and not lot.termine]
        # Rescanner à chaque retour d'écran pendant tout un lot coûtait un
        # ffprobe par fichier et par fermeture de fenêtre. Seule une nouvelle
        # réussite change ce que montre le disque (CR-74).
        nouvelles = reussies - self._reussites_vues
        self._reussites_vues |= reussies
        if nouvelles and not self._nav.is_virtual:
            self._refresh_view()

    def on_mount(self) -> None:
        # L'accueil repart des largeurs par défaut : on veut retrouver la même
        # disposition à chaque lancement, pas celle héritée d'un réglage de la
        # veille. Le redimensionnement reste actif pendant la session.
        cfg_mod.reset_browser_columns(self._app.cfg)
        self._resize_col_idx = 0  # Initialise le focus sur "fichier" (première colonne redimensionnable)
        self._build_columns()
        self._footer_suit_le_mode()
        self._update_profile_bar()
        self._refresh_view()
        self.query_one(DataTable).focus()

    # ─── Table ────────────────────────────────────────────────────────────────

    # Colonnes de l'écran d'accueil : un volume n'a ni durée, ni codec, ni
    # décision d'encodage. Promettre dix colonnes qu'aucune ligne ne peut
    # remplir revient à faire lire un tableau vide.
    _COLS_VOLUMES: list[tuple[str, str, int]] = [
        ("volume", N_("Volume"),       34),
        ("libre",  N_("Free space"),   14),
        ("total",  N_("Total"),        12),
        ("occupe", N_("Used"),         10),
    ]

    def _build_columns(self) -> None:
        table  = self.query_one(DataTable)
        widths = cfg_mod.get_column_widths(self._app.cfg)

        if self._nav.is_virtual:
            for cle, libelle, largeur in self._COLS_VOLUMES:
                colonne_fixe(table, _(libelle), largeur, key=cle)
            return

        table.add_column("",                                width=3,    key="check")
        # Fichier prend la place que les autres laissent, sauf largeur réglée
        # dans la session. À 50 fixes, l'accueil faisait 188 caractères : en
        # 160 colonnes, Audio sortait de l'écran (UX-19).
        fichier_width = self._largeur_fichier(widths)
        table.add_column(self.resize_header("fichier"), width=fichier_width, key="fichier")

        for col in self.RESIZE_COLS[1:]:  # Skip fichier, déjà ajoutée
            table.add_column(self.resize_header(col), width=self.resize_largeur(col, widths[col]), key=col)

    # Ce qu'on peut faire d'un volume : l'ouvrir. Sélectionner, encoder,
    # interroger AlloCiné ou redimensionner des colonnes n'a pas de sens tant
    # qu'aucun fichier n'est en vue.
    _RACCOURCIS_VOLUMES: list[tuple[str, str]] = [("enter", N_("Open the volume"))]

    _RACCOURCIS_FICHIERS: list[tuple[str, str]] = [
        ("space",     N_("Toggle")),
        ("a",         N_("All")),
        ("n",         N_("None")),
        ("enter",     N_("Open")),
        ("w",         N_("Mode")),
        ("t",         N_("Tracks")),
        ("v",         N_("Play")),
        ("r",         N_("Encode the folder")),
        ("j",         N_("Join parts")),
        ("i",         N_("Info")),
        ("ctrl+d",    N_("Delete")),
        ("l",         N_("Filter")),
        ("z",         N_("Hide SKIP")),
        ("backspace", N_("Up")),
        ("home",      N_("Start")),
        ("end",       N_("End")),
        ("pageup",    "Page ↑"),
        ("pagedown",  "Page ↓"),
    ]

    def _raccourcis_fichiers(self) -> list[tuple[str, str]]:
        """La liste des fichiers, avec le mode courant nommé sur la touche W.

        « Mode » seul n'apprend rien : ce qui compte est celui qui est actif,
        parce qu'il commande ce que fait ↵ sur un fichier.
        """
        assistant = getattr(self._app, "wizard_mode", True)
        variables = {
            "w": N_("Guided") if assistant else N_("Manual"),
            "z": N_("Show SKIP") if self._masquer_skip else N_("Hide SKIP"),
        }
        return [(k, variables.get(k, lib)) for k, lib in self._RACCOURCIS_FICHIERS]

    def _footer_suit_le_mode(self) -> None:
        """Le footer n'annonce que ce que le mode courant sait faire."""
        try:
            pied = self.query_one(KeyFooter)
        except Exception:
            return
        # La couleur double le libellé : le manuel garde le code par défaut,
        # l'assistant prend l'accent du thème.
        pied.set_class(bool(getattr(self._app, "wizard_mode", True)),
                       "assistant")
        if self._nav.is_virtual:
            pied.update_line(1, self._RACCOURCIS_VOLUMES)
            pied.update_line(2, footer_line2(nav=False))
        else:
            pied.update_line(1, self._raccourcis_fichiers())
            pied.update_line(2, footer_line2(
                nav=False, resize=True, accueil=True,
                extra=(("f1", N_("Dry run")), ("f2", N_("Encode")),
                       ("f4", N_("Profile")), ("f5", N_("Manage")))))

    def _refresh_view(self) -> None:
        """Reconstruit la vue complète (dirs + fichiers)."""
        self._scan_epoch += 1   # invalide tout worker en cours
        # Entrer dans un volume ou en ressortir change le jeu de colonnes.
        if self._nav.is_virtual != self._colonnes_volumes:
            self._colonnes_volumes = self._nav.is_virtual
            table = self.query_one(DataTable)
            table.clear(columns=True)
            self._build_columns()
            self._footer_suit_le_mode()
        self._update_profile_bar()
        self._update_status()
        self._load_directory()

    def _update_status(self) -> None:
        if self._nav.is_virtual:
            # Aucun volume n'est sélectionnable, et les colonnes ne se
            # redimensionnent pas : annoncer l'un ou l'autre serait faux.
            n = sum(1 for t, _p in self._rows if t == _ROW_TYPE_DIR)
            self.query_one("#status-bar", Static).update(
                barre_etat(_("Choose a volume"),
                           ngettext("{count} volume", "{count} volumes", n).format(count=n))
            )
            return
        sel_count   = len(self._selected)
        total_files = sum(1 for t, _p in self._rows if t == _ROW_TYPE_FILE)
        masques     = len(self._dossier) - total_files
        filtre      = " + ".join(f for f in (
            libelle_filtre(self._filtre),
            _("without SKIP") if self._masquer_skip else "") if f)
        masques_txt = ngettext("{count} hidden", "{count} hidden",
                               masques).format(count=masques)
        self.query_one("#status-bar", Static).update(barre_etat(
            "", self._nav.breadcrumb(),
            ngettext("{selected}/{total} selected", "{selected}/{total} selected",
                     sel_count).format(selected=sel_count, total=total_files),
            _("Filter: {filter} ({hidden})").format(filter=filtre, hidden=masques_txt)
            if filtre else "",
            _("Col: {column}").format(column=self.resize_col_label) + "  </>",
        ))

    def _update_profile_bar(self) -> None:
        if self._nav.is_virtual:
            # Le profil décide de ce qu'on fera des fichiers ; il n'a rien à
            # dire tant qu'aucun n'est en vue.
            self.query_one("#profile-bar", Static).update("")
            return
        pid  = self._app.active_profile_id
        prof = self._app.profiles.get(pid)
        if prof is None:
            return
        f = prof.summary_fields()

        keep_4k  = prof.data.get("keep_4k", False)
        k4_str   = _("4K: {value}").format(value=f['4k']) if keep_4k else "4K → 1080p"
        k4_style = "green"              if keep_4k else "dim"
        dv_color = DV_VALUE_STYLES.get(f["dv"], "")

        # Ligne 1 : mode, raccourci, nom du profil, infos techniques
        line1 = Text()
        # Le mode change ce que fait ↵ sur un fichier : il doit se lire sans
        # avoir à l'essayer.
        assistant = getattr(self._app, "wizard_mode", True)
        line1.append(f"{touche('w')} ", style="dim")
        line1.append(_("Guided") if assistant else _("Manual"),
                     style="bold cyan" if assistant else "bold")
        line1.append("  │  ", style="dim")
        line1.append(f"{touche('f4')} ", style="dim")
        if prof.data.get("delete_source", False):
            line1.append("⚠ ", style="bold dark_orange")
        line1.append(f"🎬 {pid} 🎬 ", style="bold yellow")
        line1.append(" • ", style="dim")
        line1.append("1080p ", style="dim"); line1.append(f["1080p"], style="bold")
        line1.append("  ·  ")
        line1.append(k4_str, style=k4_style)
        line1.append("  ·  ")
        line1.append("DV ", style="dim"); line1.append(f["dv"], style=dv_color or "bold")
        line1.append("  ·  ")
        line1.append("preset ", style="dim"); line1.append(f["preset"], style="bold")

        # Ligne 2 : autres infos
        line2 = Text()
        line2.append(_("HD audio") + " ", style="dim"); line2.append(f["hd_audio"], style="bold")
        if prof.data.get("delete_source", False):
            line2.append("  ·  ")
            # TRANSLATORS: the profile deletes the source files; shown in capitals.
            line2.append("⚠ " + _("Deletion").upper(), style="bold dark_orange")

        txt = Text()
        txt.append(line1)
        txt.append("\n")
        txt.append(line2)
        self.query_one("#profile-bar", Static).update(txt)

    def _populate_table(
        self,
        subdirs:   list[Path],
        decisions: list[FileDecision],
        epoch:     int = -1,
    ) -> None:
        """Appelé depuis le worker (thread-safe via call_from_thread).
        epoch : -1 = appel direct (rebuild colonnes) ; >= 0 = validé contre _scan_epoch.
        """
        if epoch >= 0 and epoch != self._scan_epoch:
            return                                  # callback stale — navigation entre-temps
        table = self.query_one(DataTable)
        table.clear()
        self._rows = []
        self._produits = set()

        # ── Volumes, ou sous-répertoires ──────────────────────────────────────
        is_virtual = self._nav.is_virtual
        for d in subdirs:
            row_key = str(d)
            if is_virtual:
                table.add_row(
                    Text(f"{_DISK_ICON} {d}", style="bold cyan"),
                    *_cellules_volume(d),
                    key=row_key,
                )
            else:
                table.add_row(
                    "",
                    Text(f"{_DIR_ICON} {d.name}", style="bold blue"),
                    "", "", "", "", "", "", "", "",
                    key=row_key,
                )
            self._rows.append((_ROW_TYPE_DIR, d))

        # ── Fichiers ──────────────────────────────────────────────────────────
        self._dossier = [dec.info.path for dec in decisions]
        tous      = decisions
        decisions = [d for d in decisions
                     if ligne_visible(d, self._filtre, self._masquer_skip,
                                      d.info.path in self._selected)]
        for dec in tous:
            self._decisions[dec.info.path] = dec
        if epoch >= 0 and self._nav.current != self._precoche:
            principal = [d.info.path for d in tous
                         if d.info.titre is not None and d.info.titre.principal]
            if principal:
                self._selected.update(principal)
                self._precoche = self._nav.current
        for dec in decisions:
            row_key = str(dec.info.path)
            check   = self._check_str(dec.info.path)
            produit = deja_produit(dec.info.path.stem)
            if produit:
                self._produits.add(dec.info.path)
            self._rows.append((_ROW_TYPE_FILE, dec.info.path))
            table.add_row(
                *self._row_cells(dec, check, produit),
                key=row_key,
            )

        # ── Dossier vide ──────────────────────────────────────────────────────
        if not subdirs and not decisions:
            texte = ("⚠  " + _("All files are hidden") + "  —  "
                     + _("{filter_key} filter, {skip_key} SKIP").format(
                         filter_key=touche("l"), skip_key=touche("z"))
                     if tous else
                     "⚠  " + _("No video file in this folder") + "  —  "
                     + _("{key} to go up").format(key=touche("backspace")))
            table.add_row(
                "",
                Text(texte, style="dim italic"),
                "", "", "", "", "", "", "", "",
                key="__empty__",
            )
            self._rows.append((_ROW_TYPE_EMPTY, None))

        self.query_one("#scan-notice", Static).update("")
        self._update_status()

    # Une ligne cochée que F1/F2 réencoderont malgré la décision automatique.
    _FORCABLES = (VideoAction.SKIP, VideoAction.STRIP_DV)

    def _est_forcee(self, dec: FileDecision) -> bool:
        return dec.info.path in self._selected and dec.video.action in self._FORCABLES

    def _row_cells(self, dec: FileDecision, check: Text,
                   produit: bool = False) -> tuple:
        # Cochée, une ligne SKIP ou « retrait DV » part en réencodage
        # (`force_skip_to_encode`). La colonne le montre dès la coche, en
        # alerte : ce n'est plus la décision automatique (UX-18).
        forcee = self._est_forcee(dec)
        if forcee:
            dec = force_skip_to_encode(dec)
        info = dec.info
        vid  = dec.video

        # Toute cellule passe par `cellule()` : ce qui déborde se voit déborder.
        # `→ HEVC → HDR10` rendu `→ HEVC →` se lisait comme une décision
        # complète — voir tests/test_troncature.py.
        taille    = self._tailles.get(info.path)
        name_txt  = cellule(f"{_FILE_ICON} {info.path.name}")
        size_txt  = cellule("—" if taille is None else fmt_bytes(taille),
                            style="dim")
        res_txt   = cellule(f"{info.width}x{info.height}")
        dur_txt   = cellule(fmt_duration(info.duration), style="dim")
        kbps_txt  = cellule(f"{info.kbps}k")
        codec_txt = cellule(info.codec)
        dv_txt    = cellule(info.dv_label)
        dec_txt   = cellule(vid.label(),
                            style="bold dark_orange" if forcee else vid.style())

        # Estimation taille de sortie
        src_bytes = taille or 0
        est_bytes = _estimate_output_bytes(dec, src_bytes)

        if est_bytes == 0:
            estim_txt = cellule("—", style="dim")
        elif _sortie_recopiee(dec):
            # La sortie pèsera la taille de la source : l'écart vaut zéro, et
            # le poser sur le dégradé placerait la ligne en plein jaune — la
            # teinte la plus voyante — pour un cas où rien n'est recalculé.
            estim_txt = cellule(fmt_bytes(est_bytes), style="dim")
        elif src_bytes > 0:
            delta_pct = (est_bytes - src_bytes) * 100 / src_bytes
            sign      = "+" if delta_pct > 0 else ""
            estim_txt = cellule(f"{fmt_bytes(est_bytes)} ({sign}{delta_pct:.0f}%)",
                                style=_teinte_estimation(delta_pct))
        else:
            estim_txt = cellule(fmt_bytes(est_bytes))

        # Estimation temps d'encodage
        prof = self._active_profile()
        preset = prof.data.get("preset_encoder", "medium")
        measured_speed = get_measured_speed(self._app.cfg, vid.action)
        est_duration = estimate_encoding_duration(
            info.duration, info.kbps * 1000, vid.target_bitrate,
            vid.action, preset, measured_speed
        )
        temps_txt = cellule(fmt_duration(est_duration),
                            style="dim" if vid.action == VideoAction.SKIP else "")

        audio_txt = cellule(dec.audio_summary)

        cells = (name_txt, size_txt, res_txt, dur_txt, kbps_txt, codec_txt,
                 dv_txt, dec_txt, estim_txt, temps_txt, audio_txt)
        if produit:
            # Une sortie de l'application : la ligne s'efface d'un bloc, ce qui
            # dit « ceci vient d'ici » sans rien retirer de ce qu'elle porte.
            # Elle reste sélectionnable et encodable — seul `Ctrl+A` l'ignore.
            # La case à cocher garde sa teinte : grisée, on ne verrait plus si
            # la ligne est prise dans le lot.
            cells = tuple(Text(c.plain, style="dim", no_wrap=True,
                               overflow="ellipsis") for c in cells)
        return (check, *cells)

    def _check_str(self, path: Path) -> Text:
        # Text() évite l'interprétation des crochets comme balises Rich markup
        return Text("[x]", no_wrap=True) if path in self._selected else Text("[ ]", no_wrap=True)

    def _update_row_check(self, path: Path) -> None:
        """Met à jour la case à cocher — et la ligne entière si la coche
        change la décision appliquée (ligne SKIP ou retrait DV forcée)."""
        table   = self.query_one(DataTable)
        row_key = str(path)
        dec     = self._decisions.get(path)
        try:
            if dec is None or dec.video.action not in self._FORCABLES:
                table.update_cell(row_key, "check", self._check_str(path),
                                  update_width=False)
                return
            cells = self._row_cells(dec, self._check_str(path),
                                    path in self._produits)
            for col, cell in zip(["check", *self.RESIZE_COLS], cells):
                table.update_cell(row_key, col, cell, update_width=False)
        except Exception:
            pass

    def _annoncer_forcees(self, paths: list[Path]) -> None:
        """Dire, à la coche, qu'une décision automatique est outrepassée."""
        forcees = [p for p in paths
                   if p in self._decisions and self._est_forcee(self._decisions[p])]
        if not forcees:
            return
        if len(forcees) == 1:
            dec = force_skip_to_encode(self._decisions[forcees[0]])
            texte = _("{file} did not need re-encoding: checked, it will be "
                      "encoded ({video}, source bitrate).").format(
                file=forcees[0].name, video=dec.video.label())
        else:
            texte = _("Checked lines not re-encoded by default: {count}. They "
                      "will be encoded at their source bitrate.").format(
                count=len(forcees))
        self.notify(texte, severity="warning", timeout=5)

    # ─── Worker de scan ───────────────────────────────────────────────────────

    @work(thread=True, exclusive=True, name="scanner")
    def _load_directory(self) -> None:
        epoch   = self._scan_epoch          # capture l'epoch au lancement du thread
        self._nav.duree_min_titre = 60 * cfg_mod.get_min_title_minutes(self._app.cfg)
        subdirs = self._nav.list_subdirs()
        videos  = self._nav.list_videos()
        if self._nav.disque_chiffre:
            self.app.call_from_thread(
                self.notify,
                _("This disc is encrypted (AACS or CSS): IRIS ENCODE cannot read "
                  "it. Decrypt it first, then open the decrypted copy."),
                severity="warning", timeout=8)
        elif self._nav.dvd_sans_outil:
            self.app.call_from_thread(
                self.notify,
                _("Reading a DVD's titles needs the DVD tool (an ffmpeg with "
                  "libdvdnav). Restart IRIS ENCODE and accept its installation. "
                  "VIDEO_TS still shows the VOB files."),
                severity="warning", timeout=10)
        total   = len(videos)
        profile = self._active_profile()

        def _set_notice(msg: str) -> None:
            if self._scan_epoch != epoch:
                return                      # navigation entre-temps : abandon silencieux
            self.app.call_from_thread(
                self.query_one("#scan-notice", Static).update, msg
            )

        _set_notice("⏳ " + _("Analyzing… {done} / {total}").format(done=0, total=total))

        # Scans ffprobe parallélisés (ordre des résultats préservé par map)
        done = 0
        lock = threading.Lock()

        def _scan_one(vpath: Path) -> FileDecision | None:
            nonlocal done
            if self._scan_epoch != epoch:
                return None                 # navigation entre-temps : abandon anticipé
            dec: FileDecision | None = None
            try:
                self._tailles[vpath] = vpath.stat().st_size
            except OSError:
                self._tailles[vpath] = None
            try:
                info = scan(vpath)
                if info.titre is not None:
                    self._tailles[vpath] = info.titre.taille
                reglages = self._reglages.get(vpath)
                if reglages is not None:
                    dec = appliquer_reglages(
                        info, profile, reglages, self._app.profiles,
                        self._audio_overrides.get(vpath),
                        self._subtitle_overrides.get(vpath))
                else:
                    dec = decide(
                        info, profile,
                        self._audio_overrides.get(vpath),
                        self._subtitle_overrides.get(vpath),
                    )
            except Exception:
                _LOG.warning("scan failed: %s", vpath, exc_info=True)
            with lock:
                done += 1
                _set_notice("⏳ " + _("Analyzing… {done} / {total}").format(
                    done=done, total=total))
            return dec

        decisions: list[FileDecision] = []
        if videos:
            with ThreadPoolExecutor(
                max_workers=min(SCAN_WORKERS, total), thread_name_prefix="scan"
            ) as pool:
                decisions = [d for d in pool.map(_scan_one, videos) if d is not None]

        if self._scan_epoch != epoch:
            return                          # navigation entre-temps : ne pas peupler
        self.app.call_from_thread(self._populate_table, subdirs, decisions, epoch)

    # ─── Sélection de profil (F4) ──────────────────────────────────────────────

    def action_open_profile_picker(self) -> None:
        from .profile_picker import ProfilePickerScreen

        def _on_pick(pid: str | None) -> None:
            if pid is None:
                return
            self._app.active_profile_id = pid
            self._update_profile_bar()
            self._refresh_view()
        self.app.push_screen(
            ProfilePickerScreen(self._app.profiles, self._app.active_profile_id),
            _on_pick,
        )

    # ─── Resize colonnes (ColumnResizeMixin) ──────────────────────────────────

    def _largeur_fichier(self, widths: dict[str, int]) -> int:
        reglee = (self._app.cfg.get("tui", {}).get("browser", {})
                  .get("columns", {}).get("fichier"))
        if reglee:
            return self.resize_largeur("fichier", reglee)
        return self.resize_remplissage("fichier", widths, widths["fichier"])

    def _resize_widths(self) -> dict[str, int]:
        # La largeur de Fichier est celle qu'on voit, pas le défaut de config :
        # c'est d'elle que partent `<` et `>`.
        widths = cfg_mod.get_column_widths(self._app.cfg)
        return {**widths, "fichier": self._largeur_fichier(widths)}

    def on_resize(self, event: events.Resize) -> None:
        """La fenêtre change de taille : Fichier reprend la place laissée.

        Sans cela, la largeur calculée à l'entrée dans le dossier restait
        figée : agrandir la fenêtre laissait un vide à droite, la réduire
        poussait Audio hors de l'écran. Un bord tiré à la souris envoie une
        rafale d'événements : on ne reconstruit qu'une fois, quand elle cesse.
        """
        if self._minuterie_largeur is not None:
            self._minuterie_largeur.stop()
        self._minuterie_largeur = self.set_timer(0.15, self._suivre_la_fenetre)

    def _suivre_la_fenetre(self) -> None:
        self._minuterie_largeur = None
        if self._nav.is_virtual:
            return
        colonne = self.query_one(DataTable).columns.get("fichier")  # type: ignore[call-overload]
        voulue  = self._largeur_fichier(cfg_mod.get_column_widths(self._app.cfg))
        if colonne is not None and colonne.width != voulue:
            self._resize_rebuild()

    def _resize_persist(self, key: str, width: int) -> None:
        if self._nav.is_virtual:
            return
        cfg_mod.set_column_width(self._app.cfg, key, width)
        sauver_config(self.app)

    def _resize_rebuild(self) -> None:
        """Reconstruit colonnes + données après resize. Conserve curseur + sélection."""
        # Les colonnes des volumes ne se redimensionnent pas. Reconstruire ici,
        # avant que la liste soit chargée, posait la ligne « dossier vide » des
        # fichiers dans une table de quatre colonnes : l'application tombait.
        if self._nav.is_virtual:
            return
        table      = self.query_one(DataTable)
        cursor_row = table.cursor_row
        subdirs    = [p for t, p in self._rows if t == _ROW_TYPE_DIR  and p is not None]
        # Tout le dossier, pas les seules lignes affichées : le filtre a pu
        # changer depuis la dernière construction.
        decisions  = [self._decisions[p] for p in self._dossier
                      if p in self._decisions]
        table.clear(columns=True)
        self._build_columns()
        self._populate_table(subdirs, decisions)
        if table.row_count > 0:
            table.move_cursor(row=min(cursor_row, table.row_count - 1))

    # ─── Navigation ───────────────────────────────────────────────────────────

    def _current_row_info(self) -> tuple[str, Path | None]:
        table = self.query_one(DataTable)
        idx   = table.cursor_row
        if 0 <= idx < len(self._rows):
            return self._rows[idx]
        return ("", None)

    def action_play(self) -> None:
        """
        Ouvre le fichier sous le curseur dans mpv.

        Juger une source avant de décider quoi en faire évite d'ouvrir un
        lecteur à côté : c'est souvent la première chose qu'on veut faire
        devant une liste de fichiers.
        """
        row_type, path = self._current_row_info()
        if row_type != _ROW_TYPE_FILE or path is None:
            return
        if not preview.available():
            self.app.bell()
            self._flash_status(_("mpv missing — run the preflight again to install it."))
            return
        dec = self._decisions.get(path)
        try:
            preview.open_file(dec.info.lecture if dec else path)
        except Exception as e:
            self.app.bell()
            self._flash_status(_("Cannot play: {error}").format(error=texte_erreur(e)))

    def action_delete_file(self) -> None:
        """
        Supprime définitivement le fichier sous le curseur, après confirmation.

        Pendant du Visualiser : juger une source amène parfois à constater
        qu'elle ne vaut rien. Autant s'en débarrasser sans quitter l'écran.
        """
        row_type, path = self._current_row_info()
        if row_type != _ROW_TYPE_FILE or path is None:
            return
        # Un titre de disque n'est pas un fichier à soi : ses fichiers sont
        # ceux du disque, partagés avec d'autres titres (IE-120, IE-121).
        dec = self._decisions.get(path)
        if ((dec is not None and dec.info.titre is not None)
                or path.suffix.lower() in (".mpls", ".dvd")):
            self.app.bell()
            self._flash_status(_("A disc title cannot be deleted from here: "
                                 "its files belong to the disc."))
            return
        # Un fichier en file ou en cours d'encodage se lit encore (IE-100).
        if path in self._app.sources_en_file():
            self.notify(_("{file} is in the encoding queue: it cannot be "
                          "deleted now.").format(file=path.name), severity="warning",
                        timeout=5)
            return

        def _on_confirm(ok: bool | None) -> None:
            if ok:
                self._delete_now(path)

        from .delete_confirm import DeleteConfirmModal
        self.app.push_screen(DeleteConfirmModal(path), _on_confirm)

    def _delete_now(self, path: Path) -> None:
        """Supprime le fichier et retire sa ligne, sans re-scanner le dossier."""
        try:
            path.unlink()
        except Exception as e:
            # Cas courant sous Windows : mpv tient encore le fichier ouvert.
            self.app.bell()
            self._flash_status(_("Cannot delete: {error}").format(error=texte_erreur(e)))
            return
        # Annoncés par la confirmation : le .nfo et les images Jellyfin (IE-116).
        supprimer_annexes(path)

        self._decisions.pop(path, None)
        self._selected.discard(path)
        self._audio_overrides.pop(path, None)
        self._subtitle_overrides.pop(path, None)
        if path in self._dossier:
            self._dossier.remove(path)

        idx = next(
            (i for i, (t, p) in enumerate(self._rows)
             if t == _ROW_TYPE_FILE and p == path),
            None,
        )
        if idx is None:
            return
        del self._rows[idx]
        try:
            self.query_one(DataTable).remove_row(str(path))
        except Exception:
            pass

        if not self._rows:
            self._refresh_view()   # dossier vidé : faire apparaître le placeholder
        else:
            self._update_status()

    def _flash_status(self, message: str) -> None:
        """Message ponctuel dans la barre d'état, effacé au prochain rafraîchissement."""
        try:
            self.query_one("#status-bar", Static).update(f" {message}")
        except Exception:
            pass

    def action_enter_dir(self) -> None:
        row_type, path = self._current_row_info()
        if row_type == _ROW_TYPE_DIR and path is not None:
            self._nav.enter(path)
            self._selected.clear()
            self._precoche = None
            self._refresh_view()
        elif row_type == _ROW_TYPE_FILE:
            # C'est ↵ que le mode commande, et lui seul : `T` garde son sens
            # d'origine — l'écran des pistes — quel que soit le mode. Router la
            # bascule sur `action_open_tracks` détournait les deux touches à la
            # fois, et rendait l'écran des pistes inatteignable en assistant.
            if getattr(self.app, "wizard_mode", False):
                self.action_open_wizard()
            else:
                self.action_open_tracks()

    def action_accueil(self) -> None:
        """La racine : les volumes du système, pas le dossier de travail."""
        if self._nav.is_virtual:
            return
        self._nav.aller_aux_volumes()
        self._selected.clear()
        self._precoche = None
        self._refresh_view()

    def action_go_up(self) -> None:
        changed = self._nav.go_up()
        if changed:
            self._selected.clear()
            self._precoche = None
            self._refresh_view()

    # ─── Sélection ────────────────────────────────────────────────────────────

    def action_toggle_select(self) -> None:
        row_type, path = self._current_row_info()
        if row_type != _ROW_TYPE_FILE or path is None:
            return
        if path in self._selected:
            self._selected.discard(path)
        else:
            self._selected.add(path)
            self._annoncer_forcees([path])
        self._update_row_check(path)
        self._update_status()

    def action_select_all(self) -> None:
        """Coche tout ce qu'il y a à faire ici — donc pas nos propres sorties.

        Elles restent atteignables à l'`espace` : réencoder une sortie est un
        geste légitime, mais c'en est un qui se demande, pas un que « tout
        sélectionner » emporte sans qu'on le voie.
        """
        for row_type, path in self._rows:
            if (row_type == _ROW_TYPE_FILE and path is not None
                    and path not in self._produits):
                self._selected.add(path)
                self._update_row_check(path)
        self._annoncer_forcees(list(self._selected))
        self._update_status()

    def action_select_none(self) -> None:
        paths = list(self._selected)
        self._selected.clear()
        for path in paths:
            self._update_row_check(path)
        self._update_status()

    # ─── Filtre (L, Z) ────────────────────────────────────────────────────────

    def _refiltrer(self) -> None:
        """Reconstruit la vue sous le nouveau filtre, curseur sur la même ligne
        si elle reste visible."""
        _type, path = self._current_row_info()
        self._resize_rebuild()
        table = self.query_one(DataTable)
        idx = next((i for i, (_t, p) in enumerate(self._rows) if p == path), 0)
        if table.row_count > 0:
            table.move_cursor(row=idx)

    def action_filtre_type(self) -> None:
        if self._nav.is_virtual:
            return
        from .value_picker import ValuePickerScreen
        options = options_filtre([self._decisions[p] for p in self._dossier
                                  if p in self._decisions])
        cles    = [c for c, _l in options]
        courant = cles.index(self._filtre) if self._filtre in cles else 0

        def _on_pick(idx: int | None) -> None:
            if idx is None:
                return
            self._filtre = cles[idx]
            self._refiltrer()
        self.app.push_screen(
            ValuePickerScreen(_("Picture type"), [l for _c, l in options], courant),
            _on_pick)

    def action_masquer_skip(self) -> None:
        if self._nav.is_virtual:
            return
        self._masquer_skip = not self._masquer_skip
        self._footer_suit_le_mode()
        self._refiltrer()

    # ─── Ouverture des autres écrans ──────────────────────────────────────────

    def action_toggle_wizard(self) -> None:
        """Bascule assistant / parcours libre. Le choix tient pour la session."""
        app = self.app
        app.wizard_mode = not getattr(app, "wizard_mode", True)   # type: ignore[attr-defined]
        self._update_profile_bar()
        self._footer_suit_le_mode()
        self._flash_status(
            _("Guided mode — {key} opens the guided path, one file at a "
              "time.").format(key=touche("enter"))
            if app.wizard_mode else                               # type: ignore[attr-defined]
            _("Manual mode — {key} opens the Tracks screen.").format(key=touche("enter")))

    def action_open_wizard(self) -> None:
        """Ouvre le parcours guidé sur le fichier sous le curseur."""
        row_type, path = self._current_row_info()
        if row_type != _ROW_TYPE_FILE or path is None:
            return
        dec = self._decisions.get(path)
        if dec is None:
            return
        from .wizard import WizardScreen

        def _retour(_res) -> None:
            # L'assistant travaille sur la décision elle-même : ses choix
            # tiennent, la ligne doit les montrer (CR-87).
            if dec.info.path != path:
                # Un mux a été adopté : la décision porte sur le fichier produit.
                self._oublier(path)
                self._decisions[dec.info.path] = dec
                self._refresh_view()
            else:
                self._retenir(path, dec)
                self._redessiner(path)
            self._update_status()
        self.app.push_screen(WizardScreen(dec), _retour)

    def action_open_tracks(self) -> None:
        row_type, path = self._current_row_info()
        if row_type != _ROW_TYPE_FILE or path is None:
            return
        if path not in self._decisions:
            return
        # L'écran travaille sur une copie : `⌫` n'en garde rien, pas même un
        # profil changé par `F4` (CR-81). Elle remplace la décision de
        # l'accueil seulement quand l'écran rend une sélection.
        dec = deepcopy(self._decisions[path])
        from .tracks import TracksScreen
        from core.decision import TracksSelection, decide_audio
        def _on_tracks_return(result: TracksSelection | None) -> None:
            if result is None:
                return
            # Un mux a pu adopter un nouveau fichier : la décision ne porte
            # plus sur `path`. On la ré-indexe, et les sélections de pistes
            # faites sur l'ancien fichier ne s'appliquent plus.
            adopted = dec.info.path != path
            if adopted:
                self._oublier(path)
                self._decisions[dec.info.path] = dec
            else:
                self._decisions[path] = dec
                # Stocker les overrides pistes
                self._audio_overrides[path]    = result.audio
                self._subtitle_overrides[path] = result.subtitle_indices
                # Recalculer la décision audio
                dec.audio            = decide_audio(dec.info, dec.profile, result.audio)
                dec.subtitle_indices = result.subtitle_indices
            # Appliquer les overrides vidéo
            if result.video_override:
                from dataclasses import replace as dc_replace
                from core.decision import choisir_codec
                ov = result.video_override
                # Codec et sort du DV se tranchent ensemble : HEVC ne garde le
                # DV par réencodage que si le DV est bien conservé.
                if ov.action is not None or ov.dv_action is not None:
                    dec.video = choisir_codec(
                        dec, ov.action or dec.video.action, ov.dv_action)
                if ov.bitrate       is not None: dec.video = dc_replace(dec.video, target_bitrate=ov.bitrate)
                if ov.delete_source is not None: dec.delete_source_override = ov.delete_source
            if adopted:
                self._refresh_view()   # le fichier muxé remplace l'ancien
            else:
                self._retenir(path, dec)
                self._redessiner(path)
            # Lancement direct demandé depuis TracksScreen
            if result.launch_mode == "dryrun":
                from .dryrun import DryrunScreen
                self.app.push_screen(DryrunScreen([dec]))
            elif result.launch_mode == "run":
                self._confier([dec])
        self.app.push_screen(TracksScreen(dec), _on_tracks_return)

    def _refus_sans_selection(self, action: str) -> None:
        """F1/F2 sans rien de coché : le dire, plutôt que ne rien faire (UX-17).

        Une touche sans effet et sans message se lit comme une touche cassée.
        """
        if self._nav.is_virtual:
            texte = _("{action}: first enter a volume, then check files "
                      "({key}).").format(action=action, key=touche("space"))
        else:
            texte = _("{action}: no file checked — {key} checks the line, "
                      "{all_key} checks everything.").format(
                action=action, key=touche("space"), all_key=touche("a"))
        self.notify(texte, severity="warning", timeout=4)

    def _cochees(self) -> list[FileDecision]:
        """Les décisions cochées, dans l'ordre du tableau : alphabétique.

        `_selected` est un ensemble : le parcourir tel quel donnait l'ordre des
        hachages, et un lot partait — et s'affichait — dans un ordre que rien
        ne permettait de suivre. Même tri que `list_videos`.
        """
        return [self._decisions[p] for p in sorted(self._selected)
                if p in self._decisions]

    def action_open_dryrun(self) -> None:
        decisions = [force_skip_to_encode(d) for d in self._cochees()]
        if not decisions:
            self._refus_sans_selection(_("Dry run"))
            return
        from .dryrun import DryrunScreen
        self.app.push_screen(DryrunScreen(decisions))

    def action_open_run(self) -> None:
        decisions = [force_skip_to_encode(d) for d in self._cochees()]
        if not decisions:
            self._refus_sans_selection(_("Encode"))
            return
        self._confier(decisions)

    def _confier(self, decisions: list[FileDecision]) -> None:
        """À la file d'encodage ; les fichiers confiés se décochent (IE-100).

        Rester cochés, ils partiraient une seconde fois au prochain `F2` — que
        la file refuserait, mais avec un message pour rien.
        """
        confies = {d.info.path for d in decisions}

        def _decocher() -> None:
            # Seulement une fois en file : renoncer au choix du dossier de
            # sortie ne met rien en file, et ne doit rien décocher (CR-76).
            for path in confies & self._selected:
                self._selected.discard(path)
                self._update_row_check(path)
            self._update_status()
        self._app.encoder(decisions, apres=_decocher)

    # ─── Registre des réglages explicites ─────────────────────────────────────

    def _retenir(self, path: Path, dec: FileDecision) -> None:
        """Note ce que `dec` règle à la main, pour le réappliquer au rescan."""
        reglages = reglages_explicites(dec, self._active_profile(),
                                       self._audio_overrides.get(path),
                                       self._subtitle_overrides.get(path))
        if reglages.vide:
            self._reglages.pop(path, None)
        else:
            self._reglages[path] = reglages

    def _oublier(self, path: Path) -> None:
        """Ce fichier n'est plus celui qu'on règle (un mux l'a remplacé)."""
        self._decisions.pop(path, None)
        self._audio_overrides.pop(path, None)
        self._subtitle_overrides.pop(path, None)
        self._reglages.pop(path, None)

    def _redessiner(self, path: Path) -> None:
        """La ligne entière d'un fichier, d'après sa décision actuelle."""
        dec = self._decisions.get(path)
        if dec is None:
            return
        try:
            table = self.query_one(DataTable)
            cells = self._row_cells(dec, self._check_str(path), path in self._produits)
            for col, cell in zip(["check", *self.RESIZE_COLS], cells):
                table.update_cell(str(path), col, cell, update_width=False)
        except Exception:
            pass

    # ─── Collage de parties (J) ───────────────────────────────────────────────

    def action_join_parts(self) -> None:
        """Recoud les fichiers cochés en un seul, à encoder ensuite normalement.

        Les décisions sont déjà en mémoire : l'écran de collage n'a pas à
        rescanner, il lui faut seulement les `VideoInfo` des parties.
        """
        from core.joiner import MIN_PARTIES

        infos = [d.info for d in self._cochees()]
        if len(infos) < MIN_PARTIES:
            self.app.bell()
            self._flash_status(
                _("Join: check at least {count} parts ({key}).").format(
                    count=MIN_PARTIES, key=touche("space")))
            return

        from .join import JoinScreen

        def _apres_collage(ok: bool | None) -> None:
            if ok:
                # Le fichier produit n'est pas dans la table : le dossier est
                # relu pour qu'il s'y travaille comme les autres.
                self._selected.clear()
                self._refresh_view()

        self.app.push_screen(JoinScreen(infos), _apres_collage)

    def action_open_config(self) -> None:
        from .config import ConfigScreen
        def _on_config_return(changed: bool) -> None:
            if changed:
                # Recalcul des décisions avec le nouveau profil
                self._decisions.clear()
                self._update_profile_bar()
                self._refresh_view()
        self.app.push_screen(ConfigScreen(), _on_config_return)

    # ─── Run récursif (R) ─────────────────────────────────────────────────────

    def action_recursive_run(self) -> None:
        row_type, path = self._current_row_info()
        if row_type != _ROW_TYPE_DIR or path is None:
            return
        from .recursive_confirm import RecursiveConfirmModal
        def _on_confirm(ok: bool) -> None:
            if ok:
                self._launch_recursive_scan(path)
        self.app.push_screen(RecursiveConfirmModal(path, self._app.active_profile_id),
                             _on_confirm)

    @work(thread=True, name="recursive-scan")
    def _launch_recursive_scan(self, directory: Path) -> None:
        self.app.call_from_thread(
            self.query_one("#scan-notice", Static).update,
            "⏳ " + _("Recursive scan of {folder}…").format(folder=directory.name),
        )
        def _progres(fait: int, total: int) -> None:
            self.app.call_from_thread(
                self.query_one("#scan-notice", Static).update,
                "⏳ " + _("Analyzing… {done} / {total}").format(
                    done=fait, total=total))

        infos     = scan_directory_recursive(directory, _progres)
        profile   = self._active_profile()
        decisions = [decide(info, profile) for info in infos]
        decisions = [d for d in decisions if d.video.action != VideoAction.SKIP]

        def _push() -> None:
            self.query_one("#scan-notice", Static).update("")
            if not decisions:
                self.query_one("#scan-notice", Static).update(
                    "⚠ " + _("No file to encode in this folder.")
                )
                return
            from .dryrun import DryrunScreen
            self.app.push_screen(DryrunScreen(decisions))

        self.app.call_from_thread(_push)

    # ─── Métadonnées IMDB / AlloCiné ─────────────────────────────────────────

    def _open_meta(self, source: str) -> None:
        row_type, path = self._current_row_info()
        if row_type != _ROW_TYPE_FILE or path is None:
            return
        from .meta_popup import MetaPopup
        # Un titre de disque se cherche par le nom du disque, pas par
        # « 00800 » ou « TITLE 01 » (CR-100) : un chemin qui le porte.
        dec = self._decisions.get(path)
        if dec is not None and dec.info.titre is not None:
            path = dec.info.dossier / f"{dec.info.stem_sortie}.mkv"
        self.app.push_screen(MetaPopup(path, source))

    def action_open_fiche(self) -> None:
        """AlloCiné d'abord ; `Tab` dans la fiche passe à IMDB."""
        self._open_meta("allocine")

    # ─── Survol : chemin complet dans la zone notice ──────────────────────────

    def _libelle_survol(self, chemin: Path) -> str:
        """Ce que la barre d'état ne dit pas déjà.

        Elle affiche le dossier courant ; répéter ce préfixe quatre lignes plus
        bas coûtait une quarantaine de colonnes, et sur un chemin réseau il ne
        restait plus la place d'afficher le nom du fichier. Un scan récursif
        remonte en revanche des fichiers de sous-dossiers : là, le chemin
        relatif dit quelque chose que la barre d'état ignore.
        """
        try:
            relatif = chemin.relative_to(self._nav.current)
        except ValueError:
            return str(chemin)      # hors de l'arborescence courante
        return str(relatif)

    @on(DataTable.RowHighlighted)
    def _on_row_highlight(self, event: DataTable.RowHighlighted) -> None:
        """Affiche le fichier survolé, sans répéter le dossier courant."""
        row_type, path = self._current_row_info()
        if path:
            notice = self.query_one("#scan-notice", Static)
            notice.update(self._libelle_survol(path))
