"""
tui/screens/aide.py — Le guide d'utilisation, embarqué dans l'application.

Ouvert par `H` depuis n'importe quel écran. Il répond à une question précise :
« cette touche, elle fait quoi au juste ? » — sans quitter l'application, sans
ouvrir un fichier à côté.

**Rien n'y est écrit à la main sans être vérifié.** La liste des touches est
*dérivée* des `BINDINGS` de chaque écran ; seules les explications sont
rédigées, et elles sont attachées à une action (`measure`, `apply_segments`…),
pas à une touche. Une touche qu'on déplace suit son explication ; une touche
qu'on ajoute sans l'expliquer fait échouer `tests/test_aide.py`.

C'est la leçon d'IE-30 appliquée au guide : un pied de page écrit à côté des
`BINDINGS` avait fini par ne plus les décrire, et personne ne l'avait vu. Un
guide écrit à côté du code dériverait de la même façon, en pire — on lui fait
confiance justement parce qu'on ne connaît pas la réponse.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Static

from ..common import footer_line2, touche_longue
from ..widgets.entete import Entete
from ..widgets.footer import KeyFooter

# Bindings que Textual installe lui-même sur tout écran. Ils ne font pas partie
# du vocabulaire de l'application et n'ont rien à faire dans son guide.
_CADRE = {"app.focus_next", "app.focus_previous", "screen.copy_text"}


# ─── Ce que les touches font, action par action ───────────────────────────────
#
# La clé est le **nom de l'action**, pas la touche : une touche qu'on déplace
# emporte son explication avec elle.

_COMMUNES: dict[str, str] = {
    "table_home":      "Première ligne du tableau.",
    "table_end":       "Dernière ligne du tableau.",
    "table_page_up":   "Recule d'un écran de lignes.",
    "table_page_down": "Avance d'un écran de lignes.",
    "col_prev":        "Sélectionne la colonne précédente pour la redimensionner.",
    "col_next":        "Sélectionne la colonne suivante. La colonne active porte "
                       "le repère ◄► dans son en-tête.",
    "col_shrink":      "Rétrécit la colonne active de deux caractères. Un plancher "
                       "l'empêche de descendre sous ce que son contenu exige.",
    "col_grow":        "Élargit la colonne active. S'arrête à la largeur du "
                       "terminal : au-delà, les dernières colonnes sortiraient de "
                       "l'écran sans que rien ne le dise.",
    "accueil":         "Retourne directement à l'écran d'accueil, sans remonter "
                       "les écrans un par un. Demande confirmation si un travail "
                       "est en cours.",
    "aide":            "Ouvre ce guide.",
    "request_quit":    "Quitte l'application, après confirmation.",
}

_PAR_ECRAN: dict[str, dict[str, str]] = {
    "BrowserScreen": {
        "toggle_select":       "Coche ou décoche le fichier sous le curseur. Seuls "
                               "les fichiers cochés partent en dry-run ou en "
                               "encodage.",
        "select_all":          "Coche tous les fichiers du dossier.",
        "select_none":         "Décoche tout.",
        "enter_dir":           "Ouvre le dossier sous le curseur. Sur un fichier : "
                               "ouvre l'écran des pistes en mode manuel, "
                               "l'assistant en mode assistant.",
        "go_up":               "Remonte au dossier parent.",
        "open_tracks":         "Ouvre l'écran des pistes du fichier sous le "
                               "curseur — quel que soit le mode.",
        "toggle_wizard":       "Bascule entre le mode manuel et l'assistant. Le "
                               "mode actif est nommé dans la barre de profil et "
                               "dans le pied de page, dont la couleur change.",
        "play":                "Lit le fichier dans mpv, si mpv est installé.",
        "delete_file":         "Supprime le fichier sous le curseur, après "
                               "confirmation.",
        "open_dryrun":         "Dry-run : montre ce qui serait fait, sans rien "
                               "faire.",
        "open_run":            "Lance l'encodage des fichiers cochés.",
        "recursive_run":       "Encode toute l'arborescence sous le dossier "
                               "courant, selon le profil actif.",
        "open_profile_picker": "Change le profil actif.",
        "open_config":         "Gère les profils : créer, éditer, supprimer.",
        "join_parts":          "Colle les fichiers cochés bout à bout en un "
                               "seul, sans réencoder — un film livré en part1 / "
                               "part2. L'ordre proposé vient des noms et se "
                               "corrige avant de lancer. Le fichier produit "
                               "porte « _[join] » et s'encode ensuite comme "
                               "n'importe quel autre.",
        "open_allocine":       "Cherche la fiche AlloCiné du fichier.",
        "open_imdb":           "Cherche la fiche IMDB du fichier.",
    },
    "TracksScreen": {
        "toggle_row":     "Garde ou écarte la piste sous le curseur. Une piste "
                          "écartée porte « ← écartée » dans la colonne Décision.",
        "field_prev":     "Champ précédent sur la ligne vidéo (action, débit, "
                          "Dolby Vision, sort de l'original).",
        "field_next":     "Champ suivant. Le champ actif est encadré ◄ ►.",
        "val_up":         "Valeur suivante du champ actif.",
        "val_down":       "Valeur précédente.",
        "enter_action":   "Ouvre la liste des valeurs possibles pour le champ "
                          "actif.",
        "dryrun":         "Dry-run sur ce seul fichier.",
        "run":            "Lance l'encodage de ce fichier.",
        "change_profile": "Change le profil, ce qui recalcule la décision.",
        "open_codec":     "Choisit le codec de sortie.",
        "open_bitrate":   "Choisit le débit vidéo cible.",
        "toggle_delete":  "Supprimer ou garder le fichier source après un encodage "
                          "réussi. « ⚠ SUPPRIMER » s'affiche en orange.",
        "add_external":   "Ajoute une piste venue d'un autre fichier : une VF, des "
                          "sous-titres. Ouvre l'écran de recalage.",
        "dismiss_cancel": "Revient à l'accueil sans appliquer les changements.",
    },
    "SyncScreen": {
        "field_prev":      "Champ précédent : décalage, étirement, langue, nom, "
                           "défaut, forcé.",
        "field_next":      "Champ suivant. Le champ actif est en surbrillance.",
        "val_up":          "Sur le décalage : +100 ms. Sur les autres champs : "
                           "valeur suivante.",
        "val_down":        "Sur le décalage : −100 ms. Sinon : valeur précédente.",
        "jump_up":         "Décalage +1 s — le pas grossier, pour dégrossir.",
        "jump_down":       "Décalage −1 s.",
        "fine_up":         "Décalage +10 ms — le pas fin, pour finir d'approcher "
                           "une valeur mesurée. La combinaison Ctrl et + est liée "
                           "aussi, mais tous les terminaux ne la transmettent "
                           "pas.",
        "fine_down":       "Décalage −10 ms.",
        "open_picker":     "Ouvre la liste des valeurs du champ actif.",
        "measure":         "Mesure le décalage par corrélation audio. Compte "
                           "plusieurs minutes : les deux pistes sont décodées en "
                           "entier. Le résultat est recoupé sur les trois tiers du "
                           "film avant d'être accepté.",
        "preview":         "Ouvre mpv au décalage courant, pour juger à l'oreille.",
        "sample":          "Produit un court extrait avec toutes les pistes, à lire "
                           "dans son lecteur habituel — le contrôle le plus sûr "
                           "avant de muxer.",
        "apply_candidate": "Applique quand même la valeur d'une mesure refusée. À "
                           "contrôler ensuite : elle a été refusée pour une raison.",
        "show_segments":   "Montre les plages de décalage quand la mesure a "
                           "constaté un montage différent. Consultatif : rien n'est "
                           "appliqué.",
        "apply_segments":  "Recale la piste sur ces plages. Un .srt est réécrit ; "
                           "une piste audio est rallongée aux points de bascule, "
                           "puis réencodée.",
        "copy_delay":      "Reprend sur cette piste le décalage d'une autre — utile "
                           "quand une VF et ses sous-titres viennent du même "
                           "fichier.",
        "ancrer":          "Donne un point de repère quand la mesure refuse. "
                           "L'application propose une réplique et son horodatage ; "
                           "vous indiquez l'instant où vous l'entendez, et la "
                           "recherche se fait autour. Sous-titres uniquement : sur "
                           "une piste audio, il n'y a aucun texte à proposer.",
        "remove_track":    "Retire la piste de la liste des greffes.",
        "dryrun":          "Dry-run sur le fichier cible.",
        "run":             "Encode le fichier avec les pistes greffées.",
        "run_mux":         "Muxe sans réencoder : bien plus rapide, quand la vidéo "
                           "n'a pas besoin d'être retouchée.",
        "add_track":       "Ajoute une autre piste externe.",
        "go_back":         "Revient à l'écran des pistes.",
    },
    "DryrunScreen": {
        "toggle_select": "Coche ou décoche une ligne.",
        "run":           "Lance l'encodage des lignes cochées.",
        "open_codec":    "Change le codec de la ligne sous le curseur.",
        "open_bitrate":  "Change son débit cible.",
        "go_back":       "Revient à l'écran précédent.",
    },
    "RunScreen": {
        "pause_resume": "Suspend ou reprend l'encodage en cours.",
        "skip_current": "Abandonne le fichier en cours et passe au suivant.",
        "go_back":      "Quitte l'écran d'encodage.",
    },
    "MuxScreen": {
        "dryrun":  "Dry-run sur le fichier produit par le mux.",
        "encode":  "Encode le fichier produit par le mux.",
        "go_back": "Revient à l'écran précédent.",
    },
    "JoinScreen": {
        "monter":    "Fait monter d'un rang la partie sous le curseur. C'est "
                     "l'ordre du tableau qui sera collé — le vérifier avant de "
                     "lancer : deux parties inversées donnent un fichier de la "
                     "bonne durée, et faux.",
        "descendre": "Fait descendre d'un rang la partie sous le curseur.",
        "coller":    "Lance le collage. Refusé si les parties ne s'apparient "
                     "pas — codec vidéo, définition ou format audio "
                     "différents — ou si le fichier de sortie existe déjà.",
        "go_back":   "Revient à l'accueil. Un collage en cours est interrompu "
                     "et son fichier partiel effacé.",
    },
    "ConfigScreen": {
        "activate":       "Rend actif le profil sous le curseur.",
        "new_profile":    "Crée un profil.",
        "edit_focused":   "Édite le profil sous le curseur.",
        "delete_focused": "Supprime le profil. Les profils fournis avec "
                          "l'application sont protégés.",
        "go_back":        "Revient à l'accueil.",
    },
    "WizardScreen": {
        "suivant":  "Passe à l'étape suivante. À l'étape « Lancer », déclenche le "
                    "choix recommandé ; à la fin, revient à l'accueil.",
        "basculer": "Garde ou écarte la piste sous le curseur (étape 2).",
        "codec":    "Change le codec de sortie (étape 2).",
        "debit":    "Change le débit cible (étape 2).",
        "donneur":  "Présente un fichier donneur (étape 3). La mesure du décalage "
                    "est lancée et appliquée aussitôt.",
        "retirer":  "Retire la dernière piste ajoutée (étape 3).",
        "muxer":    "Muxe sans réencoder (étape 4).",
        "encoder":  "Réencode (étape 4).",
        "retour":   "Revient à l'étape précédente ; à la première, quitte "
                    "l'assistant.",
    },
}

# Ordre de présentation : celui du parcours, pas celui des imports.
_ORDRE: list[tuple[str, str, str]] = [
    ("BrowserScreen", "Accueil",
     "Parcourir, choisir les fichiers, lancer."),
    ("WizardScreen", "Assistant",
     "Un fichier, cinq étapes. Activé par W depuis l'accueil."),
    ("TracksScreen", "Pistes",
     "Ce que deviendra chaque piste du fichier."),
    ("SyncScreen", "Recalage",
     "Greffer une piste venue d'ailleurs, et la remettre à l'heure."),
    ("DryrunScreen", "Dry-run",
     "Ce qui serait fait, sans rien faire."),
    ("RunScreen", "Encodage",
     "L'encodage en cours."),
    ("MuxScreen", "Mux",
     "Le mux en cours, et ce qu'on peut en faire ensuite."),
    ("JoinScreen", "Collage",
     "Recoudre les parties d'un même film en un seul fichier."),
    ("ConfigScreen", "Profils",
     "Créer et régler les profils d'encodage."),
]


def classes_documentees() -> dict[str, type]:
    """Les écrans du guide. Import tardif : plusieurs d'entre eux importent ce module."""
    from .browser import BrowserScreen
    from .config import ConfigScreen
    from .dryrun import DryrunScreen
    from .join import JoinScreen
    from .mux_run import MuxScreen
    from .run import RunScreen
    from .sync import SyncScreen
    from .tracks import TracksScreen
    from .wizard import WizardScreen
    return {c.__name__: c for c in (BrowserScreen, ConfigScreen, DryrunScreen,
                                    JoinScreen, MuxScreen, RunScreen,
                                    SyncScreen, TracksScreen, WizardScreen)}


def _lisible(touches: str) -> str:
    """« +,plus,equals_sign,kp_plus » → « + ».

    Les alias existent pour les dispositions de clavier, pas pour être lus : la
    première touche est celle qu'on écrit dans le guide.

    Et on l'écrit **en toutes lettres**, pas avec le glyphe du pied de page :
    « ⇧Tab » se devine, « Shift+Tab » se lit. Un glyphe se cherche sur le
    clavier, un nom s'y trouve — et le guide existe pour ceux qui cherchent.
    """
    return touche_longue(touches.split(",")[0].strip())


def touches_de(classe: type) -> list[tuple[str, str, str]]:
    """(touche lisible, action, libellé) pour un écran, sans doublon d'action.

    **Toutes** les touches, pas seulement celles que le pied de page annonce :
    ce guide existe précisément pour celles qui ne s'affichent nulle part.
    """
    vus:    set[str] = set()
    sortie: list[tuple[str, str, str]] = []
    for k in classe.__mro__:
        for b in k.__dict__.get("BINDINGS", ()):
            action = getattr(b, "action", "")
            if action in _CADRE or action in vus:
                continue
            vus.add(action)
            sortie.append((_lisible(getattr(b, "key", "")), action,
                           getattr(b, "description", "")))
    return sortie


def explication(ecran: str, action: str) -> str:
    """Ce que fait une action, sur cet écran. Vide si personne ne l'a écrit."""
    return _PAR_ECRAN.get(ecran, {}).get(action) or _COMMUNES.get(action, "")


# ─── L'écran ──────────────────────────────────────────────────────────────────

class AideScreen(Screen):
    """Le guide, dérivé des BINDINGS. Aucune touche n'y manque par oubli."""

    CSS = """
    AideScreen { layout: vertical; }
    #aide-corps {
        height: 1fr;
        padding: 1 3;
        background: $surface;
    }
    #aide-texte { height: auto; }
    """

    BINDINGS = [
        # `priority` : un conteneur défilant étouffe les touches avant que le
        # système de bindings soit consulté — même avertissement qu'en tête de
        # tui/mixins.py.
        Binding("backspace", "fermer", "Retour", show=True,  priority=True),
        Binding("escape",    "fermer", "Retour", show=False, priority=True),
        Binding("h",         "fermer", "Fermer", show=True,  priority=True),
    ]

    def compose(self) -> ComposeResult:
        yield Entete()
        with VerticalScroll(id="aide-corps"):
            yield Static(self._contenu(), id="aide-texte", markup=False)
        yield KeyFooter(actions=[("backspace", "Retour"), ("h", "Fermer")],
                        nav=footer_line2(nav=True))

    def on_mount(self) -> None:
        self.query_one("#aide-corps").focus()

    # ── Rendu ─────────────────────────────────────────────────────────────────

    def _contenu(self) -> Text:
        t = Text()
        t.append("Guide des touches\n", style="bold")
        t.append("Chaque touche de chaque écran, avec ce qu'elle fait.\n"
                 "Cette page est construite à partir des raccourcis\n"
                 "réellement déclarés : elle ne peut pas être en retard\n"
                 "sur l'application.\n\n",
                 style="dim")

        classes = classes_documentees()

        t.append("─" * 74 + "\n", style="dim")
        t.append("PARTOUT\n", style="bold")
        t.append("Ces touches répondent sur tous les écrans.\n\n", style="dim")
        for cle, action in (("h", "aide"), ("ctrl+home", "accueil"),
                            ("f10", "request_quit")):
            self._ligne(t, touche_longue(cle), _COMMUNES[action])
        t.append("\n")
        t.append("Dans un tableau\n", style="bold")
        for cle, action in (("home", "table_home"), ("end", "table_end"),
                            ("pageup", "table_page_up"),
                            ("pagedown", "table_page_down")):
            self._ligne(t, touche_longue(cle), _COMMUNES[action])
        t.append("\n")
        t.append("Colonnes redimensionnables — accueil, pistes, dry-run\n",
                 style="bold")
        for cle, action in (("tab", "col_next"), ("shift+tab", "col_prev"),
                            (">", "col_grow"), ("<", "col_shrink")):
            self._ligne(t, touche_longue(cle), _COMMUNES[action])
        t.append("\n")

        deja = set(_COMMUNES)
        for nom, titre, resume in _ORDRE:
            classe = classes.get(nom)
            if classe is None:
                continue
            lignes = [(k, a, d) for k, a, d in touches_de(classe)
                      if a not in deja]
            if not lignes:
                continue
            t.append("─" * 74 + "\n", style="dim")
            t.append(f"{titre.upper()}\n", style="bold")
            t.append(f"{resume}\n\n", style="dim")
            for touche, action, libelle in lignes:
                self._ligne(t, touche, explication(nom, action) or libelle)
            t.append("\n")
        return t

    @staticmethod
    def _ligne(t: Text, touche: str, texte: str) -> None:
        """Une touche et son explication, l'explication alignée sous elle-même.

        Le repli manuel plutôt qu'un `Text` qui s'enroule : la colonne de
        gauche doit rester une colonne, y compris sur la deuxième ligne d'une
        explication longue.
        """
        marge = 14
        largeur = 74 - marge
        mots, ligne, lignes = texte.split(), "", []
        for mot in mots:
            if ligne and len(ligne) + 1 + len(mot) > largeur:
                lignes.append(ligne)
                ligne = mot
            else:
                ligne = f"{ligne} {mot}".strip()
        if ligne:
            lignes.append(ligne)
        for i, l in enumerate(lignes or [""]):
            if i == 0:
                t.append(f"  {touche:<{marge - 2}}", style="bold yellow")
            else:
                t.append(" " * marge)
            t.append(l + "\n")

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_fermer(self) -> None:
        self.dismiss()
