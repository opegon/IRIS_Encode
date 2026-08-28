"""
tui/screens/wizard.py — L'assistant : un fichier, cinq étapes, `↵` pour avancer.

Écran **autonome**, et non un enchaînement des écrans existants. Le parcours
libre laisse le choix de l'ordre, ce qui suppose de le connaître ; l'assistant
l'impose et ne pose qu'une question à la fois. Ce qu'on retire, c'est la
navigation — **jamais l'information** : chaque étape affiche ce qu'elle a
décidé, et l'étape 2 nomme le fichier qui sortira.

| Étape | Ce qu'on y fait |
|---|---|
| 1 — Fichier | Le nom du fichier et le profil actif. Rien à décider |
| 2 — Décision | Codec, débit et pistes conservées, sur un seul écran |
| 3 — Pistes externes | Présenter un donneur. La mesure est lancée et appliquée aussitôt |
| 4 — Lancer | Muxer ou encoder — les deux sont toujours offerts |
| 5 — Terminé | Le résultat, puis retour à l'accueil |

Il ne calcule rien de neuf : `decide()` a déjà arbitré le codec, le débit, le
conteneur, le sort du Dolby Vision et chaque piste. L'assistant parcourt cette
décision, la rend modifiable au même endroit, et n'appelle les écrans
d'exécution qu'à la fin.

Aucun fichier donneur n'est cherché automatiquement : les conventions de nommage
des releases sont sans limite, et un mauvais appariement est *silencieux*.
"""
from __future__ import annotations

from dataclasses import replace as dc_replace
from enum import Enum, auto
from typing import Optional

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Header, Label, ProgressBar, Static

from core.decision import (ACTION_CYCLE, SUFFIX_BY_ACTION, AudioAction,
                           DVAction, FileDecision, VideoAction, cycle_index,
                           decide_audio)
from core.muxer import SyncOrigin, TrackKind, propager_recalage
from core.sync import measure_external_track

from ..common import (bitrate_picker_config, codec_picker_opts, fmt_duration,
                      footer_line2, retour_accueil, tronquer_milieu)
from ..mixins import TableNavMixin
from ..widgets.footer import KeyFooter
from .value_picker import ValuePickerScreen


class Etape(Enum):
    FICHIER  = auto()
    DECISION = auto()
    PISTES   = auto()
    LANCER   = auto()
    TERMINE  = auto()


_ORDRE = [Etape.FICHIER, Etape.DECISION, Etape.PISTES, Etape.LANCER,
          Etape.TERMINE]

_TITRES = {
    Etape.FICHIER:  "Fichier",
    Etape.DECISION: "Décision",
    Etape.PISTES:   "Pistes externes",
    Etape.LANCER:   "Lancer",
    Etape.TERMINE:  "Terminé",
}

# Genres de lignes de la table de l'étape 2
_L_AUDIO, _L_SUB, _L_EXT = "a", "s", "e"


class WizardScreen(TableNavMixin, Screen):
    """Assistant pas à pas sur un seul fichier."""

    CSS = """
    #wiz-titre {
        background: $primary-darken-2;
        color: $text;
        padding: 0 1;
        height: 1;
    }
    #wiz-corps { height: auto; padding: 1 2; }
    #wiz-jauge-ligne {
        height: 1;
        layout: horizontal;
        padding: 0 2;
        display: none;
    }
    #wiz-jauge-ligne.active { display: block; }
    #wiz-jauge-label { width: 34; color: $warning; }
    #wiz-jauge { width: 1fr; }
    #wiz-table { height: 1fr; margin: 0 2; }
    #wiz-hint  { color: $text-muted; padding: 0 2; height: auto; }
    """

    # `priority` partout : un DataTable étouffe les touches avant que le
    # système de bindings soit consulté — voir l'avertissement en tête de
    # tui/mixins.py. Sans cela, ↵ ne fait rien sur les étapes à table.
    BINDINGS = [
        Binding("enter",     "suivant",  "Suivant", show=True,  priority=True),
        Binding("space",     "basculer", "Garder",  show=True,  priority=True),
        Binding("f6",        "codec",    "Codec",   show=True,  priority=True),
        Binding("f7",        "debit",    "Débit",   show=True,  priority=True),
        Binding("f9",        "donneur",  "Ajouter", show=True,  priority=True),
        Binding("d",         "retirer",  "Retirer", show=True,  priority=True),
        Binding("m",         "muxer",    "Muxer",   show=True,  priority=True),
        Binding("e",         "encoder",  "Encoder", show=True,  priority=True),
        Binding("backspace", "retour",   "Retour",  show=True,  priority=True),
        Binding("escape",    "retour",   "Retour",  show=False, priority=True),
        Binding("ctrl+home", "accueil",  "Accueil", show=True,  priority=True),
    ]

    def __init__(self, decision: FileDecision) -> None:
        super().__init__()
        self._dec    = decision
        self._i      = 0
        self._lignes: list[tuple[str, int]] = []
        self._mesure = False
        self._bilan  = ""            # ce que l'étape 5 annonce

    @property
    def _etape(self) -> Etape:
        return _ORDRE[self._i]

    # ── Composition ───────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="wiz-titre", markup=False)
        yield Static("", id="wiz-corps", markup=False)
        yield DataTable(id="wiz-table", cursor_type="row", show_header=True)
        with Static(id="wiz-jauge-ligne"):
            yield Label("Mesure du décalage", id="wiz-jauge-label")
            yield ProgressBar(total=100, show_eta=False, id="wiz-jauge")
        yield Static("", id="wiz-hint", markup=False)
        # Même accent que la barre de l'accueil en mode assistant : on sait
        # d'un coup d'œil dans quel parcours on se trouve.
        yield KeyFooter(actions=[], classes="assistant",
                        nav=footer_line2(back=True, nav=True, accueil=True))

    def on_mount(self) -> None:
        self._afficher()

    # ── Rendu ─────────────────────────────────────────────────────────────────

    def _jauge(self, visible: bool, libelle: str = "Mesure du décalage") -> None:
        """Une mesure dure des minutes : un écran figé passe pour un blocage."""
        try:
            self.query_one("#wiz-jauge-ligne").set_class(visible, "active")
            if visible:
                self.query_one("#wiz-jauge-label", Label).update(libelle)
        except Exception:
            pass

    def _avancement(self, fraction: float, libelle: str) -> None:
        try:
            self.query_one("#wiz-jauge", ProgressBar).progress = fraction * 100
            self.query_one("#wiz-jauge-label", Label).update(libelle)
        except Exception:
            pass

    def _afficher(self) -> None:
        titre = self.query_one("#wiz-titre", Static)
        corps = self.query_one("#wiz-corps", Static)
        table = self.query_one(DataTable)
        hint  = self.query_one("#wiz-hint", Static)

        # Le fichier traité est rappelé à chaque étape : sans lui, les quatre
        # écrans suivants parlent d'un travail dont on a perdu le sujet. Le
        # chemin n'apporte rien — c'est le nom qui identifie.
        entete = (f" Assistant   ·   étape {self._i + 1} sur {len(_ORDRE)}"
                  f"   ·   {_TITRES[self._etape]}   ·   ")
        place  = max(24, (self.size.width or 120) - len(entete) - 2)
        titre.update(entete + tronquer_milieu(self._dec.info.path.name, place))
        table.display = False
        table.clear(columns=True)
        self._lignes = []

        rendu = {
            Etape.FICHIER:  self._etape_fichier,
            Etape.DECISION: self._etape_decision,
            Etape.PISTES:   self._etape_pistes,
            Etape.LANCER:   self._etape_lancer,
            Etape.TERMINE:  self._etape_termine,
        }[self._etape]
        texte, aide, avec_table = rendu()
        corps.update(texte)
        hint.update(aide)
        table.display = avec_table
        if avec_table:
            table.focus()

    # ── Étape 1 — le fichier ──────────────────────────────────────────────────

    def _etape_fichier(self):
        d = self._dec
        t = Text()
        t.append("Fichier à traiter\n\n", style="bold")
        t.append(f"  {d.info.path.name}\n\n")
        t.append(f"  {d.info.width}×{d.info.height} · {d.info.codec} · "
                 f"{d.info.kbps}k · {fmt_duration(d.info.duration)}\n")
        t.append(f"  {len(d.info.audio_tracks)} piste(s) audio · "
                 f"{len(d.info.subtitle_tracks)} sous-titre(s)\n\n")
        t.append(f"  Profil actif   {d.profile.id}\n", style="bold")
        return t, "↵ Continuer   ·   ⌫ Retour à la liste", False

    # ── Étape 2 — codec, débit, pistes ────────────────────────────────────────

    def _etape_decision(self):
        d, v = self._dec, self._dec.video
        t = Text()
        t.append("Ce qui sera produit\n\n", style="bold")
        t.append(f"  Sortie   {d.output_path.name}\n", style="bold")
        t.append(f"  Vidéo    {v.label()}")
        if v.target_bitrate:
            t.append(f" · {v.target_bitrate // 1000}k visés")
        t.append(f"\n           {v.reason}\n")
        self._remplir_decision()
        return (t,
                "Espace garde ou écarte une piste   ·   F6 Codec   ·   "
                "F7 Débit   ·   ↵ Continuer   ·   ⌫ Retour",
                True)

    def _remplir_decision(self) -> None:
        table = self.query_one(DataTable)
        table.add_column("", width=3)
        table.add_column("Piste",    width=14)
        table.add_column("Codec",    width=12)
        table.add_column("Langue",   width=8)
        table.add_column("Nom",      width=30)
        table.add_column("Décision", width=None)

        d = self._dec
        for ad in d.audio:
            self._ligne(_L_AUDIO, ad.track.index,
                        ad.action != AudioAction.EXCLUDE,
                        f"0:a:{ad.track.index}", ad.track.codec,
                        ad.track.language, ad.track.title,
                        ad.display() or "—")
        gardes = {st.index for st in d.subtitles_finales}
        for st in d.info.subtitle_tracks:
            self._ligne(_L_SUB, st.index, st.index in gardes,
                        f"0:s:{st.index}", st.codec, st.language, st.title,
                        "copie" if st.index in gardes else "")
        for n, ext in enumerate(d.external_tracks):
            kind = "audio" if ext.kind == TrackKind.AUDIO else "sous-titre"
            self._ligne(_L_EXT, n, True, f"greffe {kind}", ext.codec,
                        ext.language, ext.track_name or ext.source_path.name,
                        ext.sync_label())

    def _ligne(self, genre, idx, garde, piste, codec, langue, nom, decision):
        table = self.query_one(DataTable)
        style = "" if garde else "dim"
        table.add_row(
            Text("✓" if garde else " ", style="bold green" if garde else "dim"),
            Text(piste, no_wrap=True, style=style),
            Text(codec, no_wrap=True, style=style),
            Text(langue or "?", no_wrap=True, style=style),
            Text(tronquer_milieu(nom or "—", 30), no_wrap=True, style=style),
            Text(decision, style="green" if garde else "dim"),
        )
        self._lignes.append((genre, idx))

    # ── Étape 3 — les pistes externes ─────────────────────────────────────────

    def _etape_pistes(self):
        d = self._dec
        t = Text()
        t.append("Pistes venues d'un autre fichier\n\n", style="bold")
        if self._mesure:
            t.append("  ⏳ Mesure du décalage en cours…\n", style="yellow")
        elif not d.external_tracks:
            t.append("  Aucune pour l'instant.\n\n", style="dim")
            t.append("  Une VF, des sous-titres : présentez le fichier qui les\n"
                     "  porte. L'assistant n'en cherche aucun tout seul — un\n"
                     "  mauvais appariement ne s'entend qu'après coup.\n",
                     style="dim")
        else:
            for ext in d.external_tracks:
                kind = "audio" if ext.kind == TrackKind.AUDIO else "sous-titre"
                t.append(f"  {kind:11} {ext.language or '?':4} "
                         f"{ext.track_name or ext.source_path.name}\n")
                t.append(f"              {ext.sync_label()}   "
                         f"{self._origine(ext)}\n", style="dim")
        return (t,
                "F9 Présenter un fichier   ·   D Retirer la dernière   ·   "
                "↵ Continuer   ·   ⌫ Retour",
                False)

    @staticmethod
    def _origine(ext) -> str:
        return {
            SyncOrigin.NONE:     "non mesuré",
            SyncOrigin.MEASURED: "mesuré",
            SyncOrigin.MANUAL:   "réglé à la main",
            SyncOrigin.COPIED:   "repris de la piste audio",
        }.get(ext.sync_origin, "")

    # ── Étape 4 — lancer ──────────────────────────────────────────────────────

    def _muxable(self) -> bool:
        """Un mux suffit quand rien n'est à réencoder mais qu'il y a à greffer."""
        return (self._dec.video.action in (VideoAction.SKIP,
                                           VideoAction.STRIP_DV)
                and bool(self._dec.external_tracks))

    def _etape_lancer(self):
        d = self._dec
        t = Text()
        t.append("Prêt\n\n", style="bold")
        t.append(f"  Sortie   {d.output_path.name}\n\n", style="bold")
        if self._muxable():
            t.append("  Recommandé : muxer. Rien n'est à réencoder, les pistes\n"
                     "  sont greffées par mkvmerge et l'image recopiée telle\n"
                     "  quelle — quelques minutes au lieu de quelques heures.\n")
        else:
            t.append(f"  Recommandé : encoder. {d.video.label()}.\n")
            if not d.external_tracks:
                t.append("  Sans piste à greffer, le mux n'aurait rien à faire.\n",
                         style="dim")
        t.append("\n  Les deux restent offerts : ")
        t.append("M", style="bold")
        t.append(" muxer, ")
        t.append("E", style="bold")
        t.append(" encoder.\n")
        return (t,
                "↵ Lancer le choix recommandé   ·   M Muxer   ·   E Encoder   "
                "·   ⌫ Retour",
                False)

    # ── Étape 5 — terminé ─────────────────────────────────────────────────────

    def _etape_termine(self):
        t = Text()
        t.append((self._bilan or "Opération terminée.") + "\n", style="bold")
        t.append(f"\n  {self._dec.output_path.name}\n")
        return t, "↵ Retour à la liste des fichiers", False

    # ── Navigation ────────────────────────────────────────────────────────────

    def action_suivant(self) -> None:
        if self._mesure:
            return
        if self._etape == Etape.LANCER:
            self._lancer(mux=self._muxable())
            return
        if self._etape == Etape.TERMINE:
            retour_accueil(self.app)
            return
        self._i = min(self._i + 1, len(_ORDRE) - 1)
        self._afficher()

    def action_retour(self) -> None:
        if self._mesure:
            return                       # une mesure court : on ne quitte pas
        if self._i == 0:
            self.dismiss(None)
            return
        self._i -= 1
        self._afficher()

    def action_accueil(self) -> None:
        if not self._mesure:
            retour_accueil(self.app)

    # ── Étape 2 : modifier la décision ────────────────────────────────────────

    def _ligne_courante(self) -> Optional[tuple[str, int]]:
        if self._etape != Etape.DECISION:
            return None
        r = self.query_one(DataTable).cursor_row
        return self._lignes[r] if 0 <= r < len(self._lignes) else None

    def action_basculer(self) -> None:
        courant = self._ligne_courante()
        if courant is None:
            return
        genre, idx = courant
        d = self._dec
        if genre == _L_AUDIO:
            gardes = [a.track.index for a in d.audio
                      if a.action != AudioAction.EXCLUDE]
            gardes = ([g for g in gardes if g != idx] if idx in gardes
                      else sorted(gardes + [idx]))
            d.audio = decide_audio(d.info, d.profile, gardes)
        elif genre == _L_SUB:
            gardes = [st.index for st in d.subtitles_finales]
            d.subtitle_indices = ([g for g in gardes if g != idx]
                                  if idx in gardes else sorted(gardes + [idx]))
        else:
            return                       # une greffe se retire avec D, étape 3
        self._afficher()

    def action_codec(self) -> None:
        if self._etape != Etape.DECISION:
            return
        v = self._dec.video

        def _appliquer(choix: Optional[int]) -> None:
            if choix is None:
                return
            action = ACTION_CYCLE[choix]
            dv     = v.dv_action
            if action == VideoAction.ENCODE_H264 and dv == DVAction.DV:
                dv = DVAction.HDR10          # H264 ne sait pas porter de RPU
            self._dec.video = dc_replace(
                v, action=action, dv_action=dv,
                output_suffix=SUFFIX_BY_ACTION.get(action, v.output_suffix),
                reason="Choisi dans l'assistant")
            self._afficher()

        self.app.push_screen(
            ValuePickerScreen(
                "Codec",
                codec_picker_opts(getattr(self.app, "platform", None)),
                cycle_index(v.action)),
            _appliquer)

    def action_debit(self) -> None:
        if self._etape != Etape.DECISION:
            return
        v = self._dec.video
        titre, opts, courant, echelle = bitrate_picker_config(v.action,
                                                              v.target_bitrate)

        def _appliquer(choix: Optional[int]) -> None:
            if choix is None:
                return
            self._dec.video = dc_replace(
                v, target_bitrate=echelle[choix] * 1000,
                reason="Débit choisi dans l'assistant")
            self._afficher()

        self.app.push_screen(ValuePickerScreen(titre, opts, courant), _appliquer)

    # ── Étape 3 : greffer, puis mesurer aussitôt ──────────────────────────────

    def action_donneur(self) -> None:
        if self._etape != Etape.PISTES or self._mesure:
            return
        from .donor_picker import pick_external_tracks

        avant = len(self._dec.external_tracks)

        def _ajoutees() -> None:
            self._afficher()
            self._mesurer(avant)

        pick_external_tracks(self, self._dec, _ajoutees)

    def action_retirer(self) -> None:
        if self._etape != Etape.PISTES or self._mesure:
            return
        if self._dec.external_tracks:
            self._dec.external_tracks.pop()
            self._afficher()

    def _mesurer(self, depuis: int) -> None:
        """Mesure les pistes ajoutées, sans le demander.

        Une piste greffée sans recalage est une piste décalée : il n'y a rien à
        arbitrer. L'audio est mesurée, et son décalage reporté sur les
        sous-titres du même donneur — leur bon décalage *est* le sien.
        """
        nouvelles = list(range(depuis, len(self._dec.external_tracks)))
        if not nouvelles:
            return
        self._mesure = True
        self._afficher()
        self._jauge(True, "Mesure du décalage")
        self._travail_mesure(nouvelles)

    @work(thread=True, name="wizard-mesure")
    def _travail_mesure(self, indices: list[int]) -> None:
        pistes = self._dec.external_tracks
        cible  = self._dec.info.path
        duree  = self._dec.info.duration
        notes: list[str] = []

        # L'audio d'abord : c'est elle qui sert de référence aux sous-titres.
        ordre = sorted(indices,
                       key=lambda i: pistes[i].kind != TrackKind.AUDIO)
        for rang, i in enumerate(ordre):
            t = pistes[i]
            if t.sync_origin != SyncOrigin.NONE:
                continue                 # déjà reprise d'une piste mesurée
            libelle = (f"Mesure {rang + 1}/{len(ordre)} — "
                       f"{t.language or '?'}")

            def rapport(f: float, _l=libelle, _r=rang) -> None:
                # Chaque piste occupe sa part de la jauge : sinon elle
                # repartirait de zéro à chaque piste, ce qui se lit comme un
                # recommencement.
                self.app.call_from_thread(
                    self._avancement, (_r + f) / len(ordre), _l)

            try:
                res = measure_external_track(cible, t, progress=rapport,
                                             duration=duree)
            except Exception as e:                       # noqa: BLE001
                notes.append(f"{t.source_path.name} : mesure impossible ({e})")
                continue
            if res.ok:
                t.delay_ms    = res.delay_ms
                t.stretch     = res.stretch
                t.sync_origin = SyncOrigin.MEASURED
                n = len(propager_recalage(pistes, i))
                notes.append(f"{t.language or '?'} {res.delay_ms:+d} ms"
                             + (f", reporté sur {n} sous-titre(s)" if n else ""))
            else:
                notes.append(f"{t.language or '?'} : {res.reason} — décalage "
                             f"laissé à 0, à vérifier avant de lancer")
        self.app.call_from_thread(self._mesure_finie, notes)

    def _mesure_finie(self, notes: list[str]) -> None:
        self._mesure = False
        self._jauge(False)
        self._afficher()
        if notes:
            self.query_one("#wiz-hint", Static).update(
                " · ".join(notes) + "\nF9 Ajouter   ·   ↵ Continuer")

    # ── Étape 4 : exécution ───────────────────────────────────────────────────

    def action_muxer(self) -> None:
        if self._etape == Etape.LANCER:
            self._lancer(mux=True)

    def action_encoder(self) -> None:
        if self._etape == Etape.LANCER:
            self._lancer(mux=False)

    def _lancer(self, *, mux: bool) -> None:
        if mux and not self._dec.external_tracks:
            self.query_one("#wiz-hint", Static).update(
                "Rien à muxer : aucune piste externe à greffer. "
                "E pour encoder.")
            return

        def _apres(_res=None) -> None:
            if self._dec.output_path.exists():
                self._bilan = ("Terminé — les pistes ont été greffées."
                               if mux else
                               "Terminé — le fichier a été produit.")
            else:
                self._bilan = ("L'opération n'a produit aucun fichier. "
                               "Revenez à l'étape précédente.")
            self._i = _ORDRE.index(Etape.TERMINE)
            self._afficher()

        if mux:
            from .mux_run import MuxScreen
            self.app.push_screen(MuxScreen(self._dec), _apres)
        else:
            from .run import RunScreen
            self.app.push_screen(
                RunScreen([self._dec], self.app.platform), _apres)  # type: ignore[attr-defined]
