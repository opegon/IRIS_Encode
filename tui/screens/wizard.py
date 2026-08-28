"""
tui/screens/wizard.py — L'assistant : un fichier, une suite d'étapes.

Le parcours manuel laisse le choix de l'ordre, ce qui suppose de le connaître.
L'assistant l'impose : chaque étape montre ce qui a été décidé, et une touche
avance. Ce qu'on retire, c'est la navigation — **jamais l'information**. Un
assistant qui déciderait en silence remplacerait un doute de manipulation par
un doute de contenu, qui ne se voit qu'après l'encodage.

Il ne calcule rien de neuf : `decide()` a déjà arbitré le codec, le débit, le
conteneur, le sort du Dolby Vision et chaque piste. L'assistant parcourt cette
décision, s'arrête là où elle ne suffit pas, et rend la main aux écrans
existants pour ce qu'ils font déjà — sélection des pistes, greffe, recalage.

Deux arrêts seulement :

- **les langues ambiguës** — plusieurs pistes revendiquent la même langue
  voulue, et seul leur titre les sépare (voir `decision.ambiguites`) ;
- **les pistes additionnelles** — l'assistant ne cherche aucun fichier donneur
  tout seul : les conventions de nommage des releases sont sans limite, et un
  mauvais appariement est silencieux. C'est l'utilisateur qui le présente, s'il
  y en a un — il peut n'y en avoir aucun.
"""
from __future__ import annotations

from enum import Enum, auto
from typing import Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Header, Static

from core.decision import (AudioAction, FileDecision, VideoAction, ambiguites,
                           decide_audio)

from ..common import fmt_duration, footer_line2
from ..mixins import TableNavMixin
from ..widgets.footer import KeyFooter


class Etape(Enum):
    RESUME  = auto()   # ce qui va se passer
    LANGUES = auto()   # une ambiguïté à trancher
    DONNEUR = auto()   # des pistes venues d'un autre fichier ?
    LANCER  = auto()   # muxer ou encoder


class WizardScreen(TableNavMixin, Screen):
    """Assistant pas à pas sur un seul fichier."""

    CSS = """
    #wiz-titre {
        background: $primary-darken-2;
        color: $text;
        padding: 0 1;
        height: 1;
    }
    #wiz-corps {
        height: auto;
        padding: 1 2;
    }
    #wiz-table {
        height: 1fr;
        margin: 1 0;
    }
    #wiz-hint {
        color: $text-muted;
        padding: 0 2;
        height: auto;
    }
    """

    # `priority=True` partout : un DataTable étouffe les touches avant que le
    # système de bindings soit consulté — voir l'avertissement de TableNavMixin.
    # Sans ça, ↵ ne fait rien sur les étapes qui affichent une table.
    BINDINGS = [
        Binding("enter",     "suivant", "Suivant",     show=True,  priority=True),
        Binding("space",     "cocher",  "Sélect",      show=True,  priority=True),
        Binding("a",         "ajuster", "Ajuster",     show=True,  priority=True),
        Binding("o",         "donneur", "Ajouter",     show=True,  priority=True),
        Binding("n",         "sans",    "Aucune",      show=True,  priority=True),
        Binding("backspace", "retour",  "Retour",      show=True,  priority=True),
        Binding("escape",    "retour",  "Retour",      show=False, priority=True),
        Binding("f12",       "manuel",  "Mode manuel", show=True,  priority=True),
    ]

    def __init__(self, decision: FileDecision) -> None:
        super().__init__()
        self._dec   = decision
        self._i     = 0
        self._amb_i = 0
        self._relever()

    # ── Le plan, recalculé quand la décision change ───────────────────────────

    def _relever(self) -> None:
        """Repart de la décision courante : ambiguïtés, base, choix par défaut.

        La **base** est la sélection avant tout arbitrage de langue. Les choix
        se réappliquent toujours depuis elle, jamais par retranchements
        successifs : sinon revenir sur un choix et recocher une piste écartée
        ne la ramènerait pas — elle aurait déjà quitté la liste, et on croirait
        l'avoir reprise.

        Les cases partent cochées sur ce que la décision garde déjà : valider
        sans rien toucher ne retire donc rien.
        """
        d = self._dec
        self._amb        = ambiguites(d.info, d.profile)
        self._base_audio = [a.track.index for a in d.audio
                            if a.action != AudioAction.EXCLUDE]
        self._base_subs  = (list(d.subtitle_indices)
                            if d.subtitle_indices is not None else None)
        self._choix: dict[int, set[int]] = {
            i: {t.index for t in a.tracks} for i, a in enumerate(self._amb)
        }
        self._etapes = self._plan()

    @property
    def _coches(self) -> set[int]:
        """Cases de l'ambiguïté courante — conservées d'un aller-retour à l'autre."""
        return self._choix.setdefault(self._amb_i, set())

    def _plan(self) -> list[Etape]:
        plan = [Etape.RESUME]
        if self._amb:
            plan.append(Etape.LANGUES)
        plan += [Etape.DONNEUR, Etape.LANCER]
        return plan

    @property
    def _etape(self) -> Etape:
        return self._etapes[min(self._i, len(self._etapes) - 1)]

    # ── Composition ───────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="wiz-titre", markup=False)
        yield Static("", id="wiz-corps", markup=False)
        yield DataTable(id="wiz-table", cursor_type="row", show_header=True)
        yield Static("", id="wiz-hint", markup=False)
        yield KeyFooter(actions=[], nav=footer_line2(back=True, nav=True))

    def on_mount(self) -> None:
        self._afficher()

    # ── Rendu d'une étape ─────────────────────────────────────────────────────

    def _afficher(self) -> None:
        titre = self.query_one("#wiz-titre", Static)
        corps = self.query_one("#wiz-corps", Static)
        table = self.query_one(DataTable)
        hint  = self.query_one("#wiz-hint", Static)

        n = self._etapes.index(self._etape) + 1
        titre.update(f" Assistant — étape {n} sur {len(self._etapes)}"
                     f"   ·   {self._dec.info.path.name}")

        table.display = False
        table.clear(columns=True)

        if self._etape == Etape.RESUME:
            corps.update(self._texte_resume())
            hint.update("↵ Suivant   ·   A Ajuster les pistes et le codec   ·   "
                        "⌫ Retour   ·   F12 Mode manuel")
        elif self._etape == Etape.LANGUES:
            corps.update(self._texte_langues())
            self._remplir_table()
            table.display = True
            # Masquer la table lui retire le focus : sans ce rappel, les
            # flèches ne déplaçaient plus le curseur en revenant sur l'étape.
            table.focus()
            hint.update("Espace coche ou décoche   ·   ↵ Valider ce choix   ·   "
                        "⌫ Retour")
        elif self._etape == Etape.DONNEUR:
            corps.update(self._texte_donneur())
            hint.update("O Présenter un fichier   ·   N ou ↵ Aucune piste à "
                        "ajouter   ·   ⌫ Retour")
        else:
            corps.update(self._texte_lancer())
            hint.update("↵ Lancer   ·   ⌫ Retour")

    def _texte_resume(self) -> Text:
        d, v = self._dec, self._dec.video
        t = Text()
        t.append("Ce qui va être produit\n\n", style="bold")
        t.append(f"  Source     {d.info.width}×{d.info.height} · "
                 f"{d.info.codec} · {d.info.kbps}k · "
                 f"{fmt_duration(d.info.duration)}\n")
        t.append(f"  Vidéo      {v.label()}")
        if v.target_bitrate:
            t.append(f" · {v.target_bitrate // 1000}k visés")
        t.append(f"\n             {v.reason}\n")

        gardees = [a for a in d.audio if a.action != AudioAction.EXCLUDE]
        t.append(f"  Audio      {len(gardees)} piste(s) sur {len(d.audio)}\n")
        for a in gardees:
            t.append(f"             {a.track.language or '?':4} "
                     f"{a.track.codec} {a.track.channel_layout} "
                     f"{a.display()}\n", style="dim")

        st    = d.subtitles_finales
        total = len(d.info.subtitle_tracks)
        t.append(f"  Sous-titre {len(st)} piste(s) sur {total}")
        if len(st) != total:
            langues = sorted({s.language or "?" for s in st})
            t.append(f" — {', '.join(langues)}")
        t.append("\n")

        if d.external_tracks:
            t.append(f"  Greffées   {len(d.external_tracks)} piste(s) "
                     f"d'un autre fichier\n")
        t.append(f"\n  Sortie     {d.output_path.name}\n")
        return t

    def _texte_langues(self) -> Text:
        a = self._amb[self._amb_i]
        t = Text()
        t.append(f"Plusieurs pistes revendiquent la même langue "
                 f"({self._amb_i + 1} sur {len(self._amb)})\n\n", style="bold")
        t.append(a.label() + ". Seul leur titre les distingue, et un titre ne\n"
                 "se devine pas — cochez celles à garder.\n", style="dim")
        return t

    def _texte_donneur(self) -> Text:
        t = Text()
        t.append("Des pistes à ajouter depuis un autre fichier ?\n\n",
                 style="bold")
        if self._dec.external_tracks:
            t.append(f"  {len(self._dec.external_tracks)} piste(s) déjà "
                     f"présentée(s) :\n")
            for e in self._dec.external_tracks:
                t.append(f"    {e.language or '?':4} {e.codec} — "
                         f"{e.source_path.name}   {e.sync_label()}\n",
                         style="dim")
            t.append("\n  O pour en ajouter d'autres, ↵ pour continuer.\n",
                     style="dim")
        else:
            t.append("  Une VF, des sous-titres — l'assistant ne cherche aucun\n"
                     "  fichier tout seul : présentez-le, ou passez.\n",
                     style="dim")
        return t

    def _texte_lancer(self) -> Text:
        t = Text()
        t.append("Prêt\n\n", style="bold")
        if self._muxable():
            t.append("  Rien à réencoder : les pistes sont greffées par "
                     "mkvmerge,\n  l'image est recopiée telle quelle.\n")
        else:
            t.append(f"  {self._dec.video.label()} — la vidéo est réencodée.\n")
        t.append(f"\n  Sortie   {self._dec.output_path.name}\n")
        return t

    def _muxable(self) -> bool:
        """Un mux suffit quand rien n'est à réencoder mais qu'il y a à greffer."""
        return (self._dec.video.action == VideoAction.SKIP
                and bool(self._dec.external_tracks))

    # ── Table des pistes ambiguës ─────────────────────────────────────────────

    def _remplir_table(self) -> None:
        table = self.query_one(DataTable)
        table.add_column("", width=3)
        table.add_column("Langue", width=8)
        table.add_column("Codec", width=20)
        table.add_column("Titre", width=48)
        for tr in self._amb[self._amb_i].tracks:
            coche = "✓" if tr.index in self._coches else " "
            titre = getattr(tr, "title", "") or "—"
            table.add_row(Text(coche, style="bold"),
                          Text(tr.language or "?"),
                          Text(tr.codec),
                          Text(titre, overflow="ellipsis", no_wrap=True))

    def _rafraichir_coches(self) -> None:
        table = self.query_one(DataTable)
        for ligne, tr in enumerate(self._amb[self._amb_i].tracks):
            table.update_cell_at(
                (ligne, 0),
                Text("✓" if tr.index in self._coches else " ", style="bold"))

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_cocher(self) -> None:
        if self._etape != Etape.LANGUES:
            return
        table  = self.query_one(DataTable)
        ligne  = table.cursor_row
        pistes = self._amb[self._amb_i].tracks
        if not (0 <= ligne < len(pistes)):
            return
        self._coches.symmetric_difference_update({pistes[ligne].index})
        self._rafraichir_coches()

    def action_suivant(self) -> None:
        if self._etape == Etape.LANGUES:
            if not self._coches:
                self.query_one("#wiz-hint", Static).update(
                    "Cochez au moins une piste — sinon la langue disparaît "
                    "du fichier.")
                return
            self._appliquer_choix()
            self._amb_i += 1
            if self._amb_i < len(self._amb):
                self._afficher()
                return
        elif self._etape == Etape.LANCER:
            self._lancer()
            return
        self._i = min(self._i + 1, len(self._etapes) - 1)
        self._afficher()

    def action_sans(self) -> None:
        if self._etape == Etape.DONNEUR:
            self.action_suivant()

    def action_retour(self) -> None:
        # Reculer d'une ambiguïté avant de reculer d'une étape.
        if self._etape == Etape.LANGUES and self._amb_i > 0:
            self._amb_i -= 1
            self._afficher()
            return
        if self._i == 0:
            self.dismiss(None)
            return
        self._i -= 1
        # Revenir *sur* l'étape des langues, c'est revenir sur sa dernière
        # ambiguïté : en validant, le compteur avait dépassé la fin. Sans ce
        # recadrage, l'affichage indexait hors des bornes.
        if self._etape == Etape.LANGUES and self._amb:
            self._amb_i = len(self._amb) - 1
        self._afficher()

    def _appliquer_choix(self) -> None:
        """Réapplique **tous** les choix depuis la base, jamais par retranchement.

        Un choix révisé doit pouvoir rendre une piste, pas seulement en
        retirer. Repartir de la base est la seule façon de le garantir.
        """
        rejet_audio: set[int] = set()
        rejet_subs:  set[int] = set()
        for i, a in enumerate(self._amb):
            rejetees = {t.index for t in a.tracks} - self._choix.get(i, set())
            (rejet_audio if a.kind == "audio" else rejet_subs).update(rejetees)

        gardes = [i for i in self._base_audio if i not in rejet_audio]
        self._dec.audio = decide_audio(self._dec.info, self._dec.profile,
                                       gardes)
        base = (self._base_subs if self._base_subs is not None
                else [s.index for s in self._dec.info.subtitle_tracks])
        self._dec.subtitle_indices = [i for i in base if i not in rejet_subs]

    def action_ajuster(self) -> None:
        """Rend la main à l'écran des pistes — il fait déjà tout ce qu'il faut."""
        if self._etape != Etape.RESUME:
            return
        from .tracks import TracksScreen

        def _retour(result) -> None:
            if result is None:
                return
            self._dec.audio = decide_audio(self._dec.info, self._dec.profile,
                                           result.audio)
            self._dec.subtitle_indices = result.subtitle_indices
            # La sélection manuelle devient la nouvelle base : les arbitrages
            # de langue repartent de ce que l'utilisateur vient de poser.
            self._amb_i = 0
            self._relever()
            self._i     = 0
            self._afficher()

        self.app.push_screen(TracksScreen(self._dec), _retour)

    def action_donneur(self) -> None:
        if self._etape != Etape.DONNEUR:
            return
        from .donor_picker import pick_external_tracks
        from .sync import SyncScreen

        def _apres_ajout() -> None:
            def _apres_recalage(_) -> None:
                self._afficher()
            self.app.push_screen(SyncScreen(self._dec), _apres_recalage)

        pick_external_tracks(self, self._dec, _apres_ajout)

    def action_manuel(self) -> None:
        """Bascule vers le parcours libre, sur la même décision."""
        self.app.wizard_mode = False   # type: ignore[attr-defined]
        self.dismiss(None)

    def _lancer(self) -> None:
        if self._muxable():
            from .mux_run import MuxScreen
            self.app.push_screen(MuxScreen(self._dec))
        else:
            from .run import RunScreen
            self.app.push_screen(
                RunScreen([self._dec], self.app.platform))  # type: ignore[attr-defined]
