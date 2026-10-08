"""
tui/screens/cles.py — Saisir les clés d'API sans éditer config.toml (IE-101).

S'ouvre au lancement pour chaque service dont la clé manque, et depuis la
gestion des profils (`F5`, `K`) pour tous. Chaque service a son bouton vers la
page qui délivre la clé ; une clé est vérifiée auprès du service avant d'être
enregistrée (`core.cles`).

Rend True si quelque chose a été enregistré.
"""
from __future__ import annotations

import webbrowser

from textual import events, on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Static

from core import cles
from core.i18n import N_, _

from ..common import sauver_config
from ..common import raccourcis


class ClesScreen(ModalScreen[bool]):
    """Une section par service : lien, champs, « Ne plus demander », état."""

    DEFAULT_CSS = """
    ClesScreen { align: center middle; }
    #cles-panel {
        width: 88;
        max-width: 96%;
        height: auto;
        max-height: 92%;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }
    #cles-titre { text-style: bold; margin-bottom: 1; }
    #cles-corps { height: auto; }
    .cles-service { height: auto; margin-bottom: 1; }
    .cles-nom { text-style: bold; color: $accent; }
    .cles-usage { color: $text-muted; }
    .cles-ligne { height: auto; }
    .cles-lbl { width: 16; padding-top: 1; color: $text-muted; }
    .cles-ligne Input { width: 1fr; }
    .cles-lien { height: auto; }
    #cles-panel .cles-lien Button { border: none; height: 1; min-width: 20; margin-right: 2; }
    .cles-url { padding-top: 0; color: $text-muted; }
    .cles-service Checkbox { border: none; padding: 0; }
    .cles-etat { height: auto; display: none; }
    .cles-etat.ok { color: $success; }
    .cles-etat.refus { color: darkorange; text-style: bold; }
    #cles-boutons { height: auto; align: center middle; margin-top: 1; }
    #cles-boutons Button { min-width: 16; margin-right: 2; border: none; }
    #cles-hint {
        color: $text-muted;
        margin-top: 1;
        border-top: solid $primary-darken-2;
        padding-top: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+s", "enregistrer", N_("Save"), show=False, priority=True),
        Binding("escape", "plus_tard",   N_("Later"),   show=False, priority=True),
    ]

    # Lignes du panneau hors zone défilante : cadre, marges, titre, boutons,
    # raccourcis. La zone prend le reste, pour que les boutons restent visibles.
    _HORS_CORPS = 12

    def __init__(self, services: list[cles.Service], au_lancement: bool) -> None:
        super().__init__()
        self._services     = services
        self._au_lancement = au_lancement
        self._verification = False

    @property
    def _cfg(self) -> dict:
        return self.app.cfg  # type: ignore[attr-defined]

    # ── Composition ───────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        titre = (_("Missing API keys") if self._au_lancement
                 else _("API keys of the online services"))
        with Vertical(id="cles-panel"):
            yield Label(titre, id="cles-titre")
            with VerticalScroll(id="cles-corps"):
                for s in self._services:
                    actuelles = cles.valeurs(self._cfg, s)
                    with Vertical(classes="cles-service", id=f"svc-{s.id}"):
                        yield Static(s.nom, classes="cles-nom", markup=False)
                        yield Static(_("{usage} — {without_key}.").format(
                                         usage=_(s.usage), without_key=_(s.sans_cle)),
                                     classes="cles-usage", markup=False)
                        with Horizontal(classes="cles-lien"):
                            yield Button(_("Get a key"), id=f"lien-{s.id}")
                            yield Static(s.url, classes="cles-url", markup=False)
                        for c in s.champs:
                            with Horizontal(classes="cles-ligne"):
                                yield Label(_(c.libelle), classes="cles-lbl")
                                yield Input(value=actuelles[c.cle],
                                            password=c.secret,
                                            id=f"champ-{s.id}-{c.cle}")
                        if self._au_lancement:
                            yield Checkbox(_("Do not ask again"),
                                           id=f"ecarter-{s.id}")
                        yield Static("", classes="cles-etat", id=f"etat-{s.id}",
                                     markup=False)
            with Horizontal(id="cles-boutons"):
                yield Button("✓  " + _("Check and save"), id="btn-enregistrer",
                             variant="primary")
                yield Button("✗  " + _("Later"), id="btn-plus-tard")
            yield Static(raccourcis([("tab", N_("Next field")),
                                     ("ctrl+s", N_("Check and save")),
                                     ("escape", N_("Later"))]), id="cles-hint")

    def on_resize(self, event: events.Resize) -> None:
        panneau = event.size.height * 92 // 100
        self.query_one("#cles-corps").styles.max_height = max(
            6, panneau - self._HORS_CORPS)

    def on_mount(self) -> None:
        premier = self.query(Input)
        if premier:
            premier.first().focus()

    # ── Actions ───────────────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-enregistrer")
    def _bouton_enregistrer(self) -> None:
        self.action_enregistrer()

    @on(Button.Pressed, "#btn-plus-tard")
    def _bouton_plus_tard(self) -> None:
        self.action_plus_tard()

    @on(Button.Pressed, ".cles-lien Button")
    def _ouvrir_page(self, event: Button.Pressed) -> None:
        sid = (event.button.id or "").removeprefix("lien-")
        service = cles.PAR_ID.get(sid)
        if service is not None:
            webbrowser.open(service.url)
            self._etat(sid, _("Page opened in the browser: copy the key, "
                              "then paste it here."), "")

    def _saisies(self, s: cles.Service) -> dict[str, str]:
        return {c.cle: self.query_one(f"#champ-{s.id}-{c.cle}", Input).value
                for c in s.champs}

    def _etat(self, sid: str, texte: str, classe: str) -> None:
        etat = self.query_one(f"#etat-{sid}", Static)
        etat.set_classes(f"cles-etat {classe}".strip())
        etat.update(texte)
        etat.display = bool(texte)

    def action_plus_tard(self) -> None:
        if self._verification:
            return
        # « Ne plus demander » vaut aussi quand on ne saisit rien.
        if self._au_lancement and self._ecarts():
            sauver_config(self.app)
        self.dismiss(False)

    def _ecarts(self) -> bool:
        """Reporte les cases « Ne plus demander » ; vrai si une a changé."""
        change = False
        for s in self._services:
            try:
                oui = self.query_one(f"#ecarter-{s.id}", Checkbox).value
            except Exception:
                continue
            if oui != (s.id in cles.ne_plus_demander(self._cfg)):
                cles.ecarter(self._cfg, s.id, oui)
                change = True
        return change

    def action_enregistrer(self) -> None:
        if self._verification:
            return
        a_verifier = []
        for s in self._services:
            saisies = self._saisies(s)
            if saisies == cles.valeurs(self._cfg, s):
                continue                        # inchangé : rien à éprouver
            if not any(v.strip() for v in saisies.values()):
                cles.enregistrer(self._cfg, s, saisies)   # effacé volontairement
                continue
            a_verifier.append((s, saisies))
            self._etat(s.id, _("Checking with the service…"), "")
        self._verification = True
        self._verifier(a_verifier)

    @work(thread=True, name="cles-verification")
    def _verifier(self, a_verifier: list) -> None:
        import time
        refus: list[tuple[str, str]] = []
        acceptes: list[tuple[cles.Service, dict]] = []
        for n, (s, saisies) in enumerate(a_verifier):
            if n:
                time.sleep(1.1)          # OpenSubtitles : une connexion par seconde
            erreur = cles.VERIFICATEURS[s.id](saisies)
            if erreur:
                refus.append((s.id, erreur))
            else:
                acceptes.append((s, saisies))
        self.app.call_from_thread(self._fin_verification, acceptes, refus)

    def _fin_verification(self, acceptes: list, refus: list) -> None:
        self._verification = False
        for s, saisies in acceptes:
            cles.enregistrer(self._cfg, s, saisies)
            # Une clé enregistrée n'a plus à être écartée.
            cles.ecarter(self._cfg, s.id, False)
            self._etat(s.id, "✓ " + _("Key accepted and saved."), "ok")
        for sid, erreur in refus:
            self._etat(sid, "✗ " + _("{error} Nothing is saved for this service.")
                       .format(error=erreur),
                       "refus")
        if self._au_lancement:
            self._ecarts()
        sauver_config(self.app)
        if refus:
            return                        # la fenêtre reste, on corrige
        if acceptes:
            self.app.notify(_("API keys saved."), timeout=3)
        self.dismiss(bool(acceptes))
