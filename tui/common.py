"""
tui/common.py — Formatage, styles et libellés partagés entre les écrans.

Centralise ce qui était dupliqué entre browser/tracks/dryrun/config :
formatage tailles/durées, couleurs Dolby Vision, options des pickers
codec/débit, groupes de raccourcis standard pour le KeyFooter.
"""
from __future__ import annotations

import re
from pathlib import Path

from rich.cells import cell_len
from rich.text import Text

from core.i18n import N_, _, pgettext
from core import config as cfg_mod
from core.muxer import TrackKind
from core.decision import (
    DVAction,
    style_dv,
    AV1_BITRATE_OPTS_KBPS,
    BITRATE_OPTS_KBPS,
    VideoAction,
)

# Codec → clé de stockage des vitesses mesurées (config.toml [stats.encode_speed])
_CODEC_SPEED_KEYS: dict[VideoAction, str] = {
    VideoAction.ENCODE_HEVC: "hevc",
    VideoAction.ENCODE_H264: "h264",
    VideoAction.ENCODE_AV1:  "av1",
}


def get_measured_speed(cfg: dict, action: VideoAction) -> float | None:
    """Vitesse d'encodage réelle moyenne (x temps réel) mesurée sur les runs précédents."""
    key = _CODEC_SPEED_KEYS.get(action)
    return cfg_mod.get_encode_speed(cfg, key) if key else None


def record_measured_speed(cfg: dict, action: VideoAction, speed: float) -> None:
    """Enregistre la vitesse réelle mesurée pour ce codec (moyenne mobile) et persiste."""
    key = _CODEC_SPEED_KEYS.get(action)
    if key is None or speed <= 0:
        return
    cfg_mod.update_encode_speed(cfg, key, speed)
    cfg_mod.save(cfg)


# ─── Noms de touches ──────────────────────────────────────────────────────────
#
# Trois notations coexistaient pour la même information : le footer disait
# « Space Sélect », les modales « Espace  Sélectionner », le formulaire de
# profil « Tab / Shift+Tab : champ suiv./préc. ». Le choix du glyphe importe
# moins que son unicité — mais un glyphe tient en une colonne, ce qui compte
# sur un footer de trois lignes.

TOUCHES: dict[str, str] = {
    "enter":     "↵",
    "backspace": "⌫",
    "space":     "␣",
    "escape":    "Esc",
    "tab":       "Tab",
    "shift+tab": "⇧Tab",
    # TRANSLATORS: the Delete key, as printed on the keyboard ("Suppr" in French).
    "delete":    N_("Del"),
    "pageup":    "PgUp",
    "pagedown":  "PgDn",
    "home":      "Home",
    "ctrl+home": "Ctrl+Home",
    "end":       "End",
    "left":      "←",
    "right":     "→",
    "up":        "↑",
    "down":      "↓",
    "shift+up":   "⇧↑",
    "shift+down": "⇧↓",
    "ctrl+up":    "Ctrl+↑",
    "ctrl+down":  "Ctrl+↓",
    "ctrl+s":    "Ctrl+S",
    "ctrl+c":    "Ctrl+C",
    "ctrl+d":    "Ctrl+D",
}

# Espacement, lui aussi commun : deux blancs entre la touche et son libellé,
# cinq entre deux raccourcis. Le footer resserre à trois pour tenir en largeur.
SEP_TOUCHE: str = "  "
SEP_ENTREE: str = "     "


def touche(nom: str) -> str:
    """Nom de touche Textual → notation affichée. Inconnue : en majuscules.
    Les symboles passent tels quels ; un nom écrit (« Suppr ») se traduit."""
    return _(TOUCHES[nom.lower()]) if nom.lower() in TOUCHES else nom.upper()


def raccourci(nom: str, libelle: str) -> str:
    """Un raccourci rendu. `nom` peut être une touche Textual (« enter ») ou
    une notation déjà composée (« +/- », « ⇧↑/↓ »)."""
    # `libelle` arrive en texte source (marqué N_) : traduit ici, au rendu (L-39).
    return f"{touche(nom)}{SEP_TOUCHE}{_(libelle)}"


def raccourcis(paires: list[tuple[str, str]]) -> str:
    """Une ligne d'aide complète, pour les pieds de modale et les bandeaux."""
    return SEP_ENTREE.join(raccourci(n, l) for n, l in paires)


# Barres d'état : « Titre — élément · élément ». Trois séparateurs coexistaient
# — « · », « ── », des blancs doublés (UX-14).
SEP_ETAT: str = "  ·  "


def barre_etat(titre: str, *elements: str) -> str:
    """Une barre d'état. `titre` vide : les éléments seuls. Éléments vides omis."""
    corps = SEP_ETAT.join(e for e in elements if e)
    if not titre:
        return f" {corps}"
    return f" {titre} — {corps}" if corps else f" {titre}"


# ─── Styles partagés ──────────────────────────────────────────────────────────

# Couleur de la valeur `dolby_vision` d'un profil (browser, config). Dérivée de
# la table unique : un profil réglé sur « sdr » doit alerter au même titre
# qu'une décision qui l'applique.
DV_VALUE_STYLES: dict[str, str] = {
    "hdr10": style_dv(DVAction.HDR10),
    "dv":    style_dv(DVAction.DV),
    "sdr":   style_dv(DVAction.SDR),
}


# ─── Formatage ────────────────────────────────────────────────────────────────

def tronquer_milieu(texte: str, largeur: int) -> str:
    """Tronque en gardant le début **et** la fin, jamais par la droite seule.

    Ce qui distingue deux pistes est presque toujours à la fin :
    « Français (France) » et « Français (France) (forced) », « English » et
    « English [SDH] ». Une ellipse à droite les rend identiques à l'écran —
    et c'est ainsi qu'on greffe une piste de vingt-trois répliques en croyant
    prendre la piste complète.

    La fin l'emporte sur le début quand la place est impaire : c'est elle qui
    porte le sens.
    """
    if len(texte) <= largeur:
        return texte
    if largeur <= 1:
        return "…"[:max(largeur, 0)]
    queue = -(-(largeur - 1) // 2)          # arrondi au-dessus
    tete  = largeur - 1 - queue
    return texte[:tete] + "…" + texte[len(texte) - queue:]


# Les colonnes d'un DataTable ont une largeur fixe, et Rich coupe net ce qui
# dépasse. « → HEVC → HDR10 » devient « → HEVC → » : une décision valide, et
# fausse — le sort du Dolby Vision a disparu sans laisser de trace. Une ellipse
# ne rend pas la valeur, mais elle dit qu'il en manque, et c'est la différence
# entre une lecture prudente et une lecture confiante.
#
def largeur_entete(libelle: str, largeur: int) -> int:
    """Largeur fixe d'une colonne, relevée pour tenir son en-tête.

    Textual rogne un en-tête trop long sans ellipse. « Langue » en 7 ne
    tiendra pas « Language » (UX-28) : calculée sur le libellé à l'exécution,
    la largeur suit la langue affichée. `tests/test_troncature.py` interdit
    une largeur littérale pour une colonne nommée.
    """
    return max(largeur, len(libelle))


def colonne_fixe(table, libelle: str, plancher: int, **kw) -> None:
    """Ajoute une colonne de largeur fixe relevée à son en-tête.

    Le libellé n'est écrit qu'une fois : `add_column(libellé,
    width=largeur_entete(libellé, n))`, recopié à chaque colonne, l'écrivait
    deux fois — et deux copies d'un en-tête se traduisent deux fois (L-66).
    """
    table.add_column(libelle, width=largeur_entete(libelle, plancher), **kw)


def libelle_type_piste(kind: TrackKind) -> str:
    """Le type d'une piste greffée, tel que l'affichent les écrans (L-66)."""
    return _("audio") if kind == TrackKind.AUDIO else _("subtitle")


_CHAMP = re.compile(r"\{\{|\}\}|\{(\w+)\}")


def texte_style(gabarit: str, style: str = "", **champs) -> Text:
    """Un gabarit traduit dont certains champs portent leur propre style.

    `texte_style(_("{key} launches the join."), key=("F2", "bold"))` : la
    phrase reste entière pour le traducteur, qui peut déplacer `{key}`, et le
    style ne passe pas par des balises Rich dans le message (L-57, L-65). Un
    champ vaut un texte, ou un couple (texte, style). `{{` et `}}` donnent des
    accolades.
    """
    t, pos = Text(style=style), 0
    for m in _CHAMP.finditer(gabarit):
        t.append(gabarit[pos:m.start()])
        if m.group(1) is None:
            t.append(m.group(0)[0])
        else:
            v = champs[m.group(1)]
            texte, st = v if isinstance(v, tuple) else (v, "")
            t.append(str(texte), style=st)
        pos = m.end()
    t.append(gabarit[pos:])
    return t


# Toute cellule de table passe par ici. `tests/test_troncature.py` le vérifie.
def cellule(texte: str, *, style: str = "", largeur: int | None = None) -> Text:
    """Une cellule de table : coupée à vue, jamais en silence.

    `largeur` déclenche en plus une troncature au milieu — la fin d'un nom de
    piste porte ce qui la distingue (voir `tronquer_milieu`). Sans elle, Rich
    coupe par la droite et pose l'ellipse lui-même.
    """
    if largeur is not None:
        texte = tronquer_milieu(texte, largeur)
    return Text(texte, style=style, no_wrap=True, overflow="ellipsis")


# Une piste que l'encodage laissera de côté. L'accueil, l'écran des pistes et
# l'assistant l'écrivaient chacun à leur façon — et l'assistant ne l'écrivait
# pas du tout : une case vide se lit comme une donnée manquante, pas comme une
# décision prise.
def libelle_ecartee() -> str:
    """« ← écartée » : une piste que la sortie ne contiendra pas."""
    # TRANSLATORS: a track left out of the output (feminine in French: "piste").
    return f"← {pgettext('track', 'discarded')}"


def fmt_bytes(b: int) -> str:
    if b >= 1_099_511_627_776:
        return f"{b / 1_099_511_627_776:.1f} To"
    if b >= 1_073_741_824:
        return f"{b / 1_073_741_824:.1f} Go"
    if b >= 1_048_576:
        return f"{b / 1_048_576:.0f} Mo"
    return f"{b // 1024} Ko"


def fmt_size(path: Path) -> str:
    try:
        return fmt_bytes(path.stat().st_size)
    except OSError:
        return "—"


def fmt_duration(seconds: float) -> str:
    if seconds <= 0:
        return "—"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s   = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def estimate_encoding_duration(
    source_duration: float,
    source_bitrate: int,
    target_bitrate: int,
    action: VideoAction,
    preset: str = "medium",
    measured_speed: float | None = None,
) -> float:
    """
    Estime la durée d'encodage en secondes.

    Si measured_speed est fourni (vitesse réelle x temps réel, mesurée lors
    d'encodages précédents pour ce codec — voir get_measured_speed), elle est
    utilisée directement et remplace l'heuristique bitrate/codec/preset ci-dessous.

    Heuristique de repli (tant qu'aucune mesure réelle n'est disponible) :
    - Ratio bitrate (source → cible)
    - Facteur codec (HEVC plus lent qu'H264, AV1 bien plus lent)
    - Facteur preset (fast plus rapide, slow plus lent)

    Formule : durée_estimée = source_duration * (source_bitrate / target_bitrate) * factor_codec * factor_preset
    """
    if source_duration <= 0 or target_bitrate <= 0:
        return 0.0

    if measured_speed and measured_speed > 0:
        return source_duration / measured_speed

    # Ratio bitrate : réduction de bitrate = encodage plus rapide
    bitrate_ratio = source_bitrate / max(target_bitrate, 1)

    # Facteurs codec (basés sur GPU NVIDIA pour durée réelle approximative)
    # Les facteurs sont relatifs au temps réel du fichier
    # H264 NVENC : ~0.8x (20% plus rapide que temps réel grâce au GPU)
    # HEVC NVENC : ~0.6x (40% plus rapide que temps réel, encodeur très optimisé)
    # AV1 NVENC  : ~1.5x (50% plus lent que temps réel)
    codec_factors = {
        VideoAction.ENCODE_H264: 0.8,    # H264 NVENC rapide
        VideoAction.ENCODE_HEVC: 0.6,    # HEVC NVENC très rapide
        VideoAction.ENCODE_AV1:  1.5,    # AV1 plus lent
        VideoAction.SKIP:        0.0,
    }
    codec_factor = codec_factors.get(action, 1.0)

    # Facteurs preset (relatif à medium=1.0)
    # Impact du preset sur le temps de traitement
    preset_factors = {
        "fast":   0.7,     # 70% du temps de medium (plus rapide)
        "medium": 1.0,     # baseline
        "slow":   1.3,     # 130% du temps de medium (plus lent mais meilleure qualité)
    }
    preset_factor = preset_factors.get(preset, 1.0)

    # Formule d'estimation
    estimated = source_duration * bitrate_ratio * codec_factor * preset_factor
    return max(0.0, estimated)


# ─── Pickers partagés (codec / débit / profil) ────────────────────────────────

# Options du picker codec — même ordre que core.decision.ACTION_CYCLE
CODEC_PICKER_OPTS: list[str] = [
    "HEVC",
    "H264",
    N_("AV1  (⚠ very demanding)"),
    "SKIP",
]


def codec_picker_opts(plat=None) -> list[str]:
    """Options du picker, annotées de ce que la machine sait faire.

    Le choix n'est jamais retiré : une carte peut être remplacée, un pilote mis
    à jour, et masquer l'option laisserait croire qu'elle n'existe pas. On dit
    ce qui va se passer, et la décision reste à l'utilisateur.
    """
    opts = [_(o) for o in CODEC_PICKER_OPTS]
    if plat is None:
        return opts
    for i, (action, encodeur) in enumerate((
        (0, getattr(plat, "encoder_hevc", None)),
        (1, getattr(plat, "encoder_h264", None)),
        (2, getattr(plat, "encoder_av1", None)),
    )):
        if encodeur and plat.peut_encoder(encodeur) is False:
            opts[action] += "  ✗ " + _("unavailable here")
    return opts


def bitrate_picker_config(
    action: VideoAction,
    current_bps: int,
) -> tuple[str, list[str], int, list[int]]:
    """Prépare le picker débit : (titre, options, index courant, échelle kbps).

    AV1 a sa propre échelle de débits ; l'index courant est la valeur
    de l'échelle la plus proche du débit actuel.
    """
    is_av1 = action == VideoAction.ENCODE_AV1
    blist  = AV1_BITRATE_OPTS_KBPS if is_av1 else BITRATE_OPTS_KBPS
    title  = _("Bitrate (AV1)") if is_av1 else _("Target bitrate")
    opts   = [f"{v} kbps" for v in blist]
    cur_k  = current_bps // 1000
    idx    = min(range(len(blist)), key=lambda i: abs(blist[i] - cur_k))
    return title, opts, idx, blist


# ─── Footer : groupes de raccourcis standard ──────────────────────────────────
#
# Convention : ligne 1 = actions propres à l'écran ;
# ligne 2 = retour + navigation table + resize colonnes + F10 Quitter (dernier).

FOOTER_NAV: list[tuple[str, str]] = [
    ("home",     N_("Start")),
    ("end",      N_("End")),
    ("pageup",   N_("Page ↑")),
    ("pagedown", N_("Page ↓")),
]

FOOTER_RESIZE: list[tuple[str, str]] = [
    # TRANSLATORS: "Col" is short for column; keep these labels short.
    ("shift+tab", N_("Prev col")),
    ("tab",       N_("Next col")),
    ("<",         N_("Narrow")),
    (">",         N_("Widen")),
]

FOOTER_BACK: tuple[str, str] = ("backspace", N_("Back"))
# `Home` appartient à la navigation dans les tables — voir FOOTER_NAV et
# TableNavMixin. Le retour à l'accueil prend donc Ctrl+Home, qui dit la même
# chose d'un cran au-dessus.
FOOTER_ACCUEIL: tuple[str, str] = ("ctrl+home", N_("Home"))
FOOTER_QUIT: tuple[str, str] = ("f10",       N_("Quit"))


# Touches rendues par `footer_line2` : elles ont leur place fixe en bande 2 et
# n'ont rien à faire dans la bande propre à l'écran.
_TOUCHES_BANDE_2: frozenset[str] = frozenset({
    "backspace", "escape", "ctrl+home", "f10",
    "home", "end", "pageup", "pagedown",
    "tab", "shift+tab", "<", ">",
})


def actions_ecran(ecran, garder: tuple[str, ...] | None = None
                  ) -> list[tuple[str, str]]:
    """Les raccourcis propres à un écran, lus dans ses `BINDINGS`.

    Chaque écran écrivait sa liste à la main, à côté de ses `BINDINGS`. Les
    deux ont divergé en silence : la touche `R` du recalage, déclarée
    `show=True`, n'apparaissait nulle part, et l'assistant n'annonçait aucune
    de ses huit touches. Une déclaration ne peut plus mentir sur ce qu'elle
    déclare.

    `garder` restreint à une liste de touches, pour un écran dont l'ensemble
    utile change d'une étape à l'autre.
    """
    vus:  set[str] = set()
    sortie: list[tuple[str, str]] = []
    # Une instance en usage, une classe sous test : les BINDINGS sont les mêmes.
    origine = ecran if isinstance(ecran, type) else type(ecran)
    # Les BINDINGS de l'écran d'abord, ceux des mixins ensuite : l'ordre de
    # déclaration est le seul ordre que l'auteur de l'écran a choisi.
    for classe in origine.__mro__:
        for b in classe.__dict__.get("BINDINGS", ()):
            touches = getattr(b, "key", "").split(",")
            libelle = getattr(b, "description", "")
            if not getattr(b, "show", False) or not libelle:
                continue
            cle = touches[0].strip().lower()
            if cle in _TOUCHES_BANDE_2 or cle in vus:
                continue
            if garder is not None and cle not in garder:
                continue
            vus.add(cle)
            sortie.append((cle, libelle))
    if garder is not None:
        rang = {k: i for i, k in enumerate(garder)}
        sortie.sort(key=lambda p: rang[p[0]])
    return sortie


def footer_line2(
    *,
    back:    bool = False,
    nav:     bool = True,
    resize:  bool = False,
    accueil: bool = False,
    extra:   tuple[tuple[str, str], ...] = (),
) -> list[tuple[str, str]]:
    """Construit la ligne 2 standard du footer, F10 toujours en dernier."""
    line: list[tuple[str, str]] = []
    if back:
        line.append(FOOTER_BACK)
    if nav:
        line.extend(FOOTER_NAV)
    if resize:
        line.extend(FOOTER_RESIZE)
    if accueil:
        line.append(FOOTER_ACCUEIL)
    line.extend(extra)
    line.append(FOOTER_QUIT)
    return line


def confier_a_la_file(app, decisions: list) -> None:
    """Met des décisions en file d'encodage depuis un écran de travail.

    La navigation revient d'abord à la liste des fichiers — c'est là qu'on
    choisit le suivant (IE-100) ; l'aperçu, les pistes ou le recalage d'un
    fichier déjà confié n'ont plus rien à offrir. Dépiler **avant** : un
    premier lot bascule l'affichage sur le mode des encodages, et la pile à
    dépiler serait alors la sienne.
    """
    from .screens.browser import BrowserScreen

    if any(isinstance(e, BrowserScreen) for e in app.screen_stack):
        while len(app.screen_stack) > 1 and not isinstance(app.screen, BrowserScreen):
            app.pop_screen()
    app.encoder(decisions)


def retour_accueil(app) -> None:
    """Dépile les écrans jusqu'à l'accueil, le browser, et l'amène aux volumes.

    Traiter plusieurs fichiers d'affilée revenait à remonter les écrans un par
    un ; le raccourci saute à la racine, la liste des volumes du système.

    Les écrans dépilés ne rendent aucun résultat — leurs rappels ne sont pas
    appelés. C'est sans conséquence pour ceux qui n'ont rien à rendre. Les deux
    qui portent un travail non validé, les pistes et le recalage, demandent
    confirmation avant d'arriver ici : perdre une mesure de trois minutes sur
    une frappe de deux touches n'est pas acceptable.

    Sans accueil dans la pile, on ne touche à rien : mieux vaut ne rien faire
    que de vider la pile jusqu'à l'écran par défaut.
    """
    from .screens.browser import BrowserScreen

    accueil = next((e for e in reversed(app.screen_stack)
                    if isinstance(e, BrowserScreen)), None)
    if accueil is None:
        return
    while len(app.screen_stack) > 1 and not isinstance(app.screen, BrowserScreen):
        app.pop_screen()
    accueil.action_accueil()


# ─── Présentation d'un profil ─────────────────────────────────────────────────
#
# Le choix (`F4`) et la gestion (`F5`) montraient les mêmes profils sous deux
# formes : « DV » / « Dolby V. », « HD audio » / « HD Audio », « Source » /
# « Suppr. », la 4K lue « → 1080p » d'un côté et « 3500k » de l'autre, le nom
# entre crochets d'un seul côté (UX-13). Une définition, deux écrans.

# En-têtes marqués ici, traduits à l'usage (`profil_colonnes`).
# TRANSLATORS: "Dolby V." is short for Dolby Vision; keep it short.
PROFIL_COLONNES: list[str] = [N_("Profile"), "1080p", "4K", N_("Dolby V."),
                              N_("Preset"), N_("HD audio"), N_("Source")]


def profil_colonnes() -> list[str]:
    """Les en-têtes de `PROFIL_COLONNES`, dans la langue chargée."""
    return [_(c) for c in PROFIL_COLONNES]


def cellules_profil(nom: str, prof, actif: bool) -> list[Text]:
    """Les cellules d'un profil, dans l'ordre de `PROFIL_COLONNES`."""
    f      = prof.summary_fields()
    garde  = prof.data.get("keep_4k", False)
    suppr  = prof.data.get("delete_source", False)
    hd     = prof.data.get("preserve_hd_audio", False)
    return [
        Text(f"{nom} ✓" if actif else nom,
             style="bold green" if actif else "bold", no_wrap=True),
        Text(f["1080p"], no_wrap=True),
        # La 4K n'a de débit que si elle est gardée ; sinon elle est ramenée.
        (Text(f'{prof.data.get("bitrate_4k_kbps", "?")}k', style="green", no_wrap=True)
         if garde else Text("→ 1080p", style="dim", no_wrap=True)),
        Text(f["dv"], style=DV_VALUE_STYLES.get(f["dv"], ""), no_wrap=True),
        Text(f["preset"], no_wrap=True),
        # Ces deux colonnes se lisent sur les booléens du profil, pas sur un
        # libellé (UX-29, L-43).
        Text(f["hd_audio"], style="" if hd else "dim", no_wrap=True),
        # TRANSLATORS: profile column Source — "del." = the source is deleted
        # after encoding (keep it short), "keep" = it is kept.
        (Text("⚠ " + pgettext("source file", "del."), style="bold dark_orange",
              no_wrap=True) if suppr
         else Text(pgettext("source file", "keep"), style="dim", no_wrap=True)),
    ]


def largeurs_colonnes(entetes: list[str], lignes: list[list[Text]]) -> list[int]:
    """Largeur de chaque colonne : le plus large de l'en-tête et du contenu,
    mesuré en cellules d'écran (`cell_len`) plutôt qu'en caractères."""
    return [max(cell_len(e), max((l[i].cell_len for l in lignes), default=0))
            for i, e in enumerate(entetes)]


# ─── Une donnée, une forme ────────────────────────────────────────────────────
#
# Les pistes arrivent de deux outils : ffprobe (« subrip », « ac3 ») pour les
# fichiers scannés, mkvmerge (« SubRip/SRT », « AC-3 ») pour les donneurs. Le
# même codec s'affichait sous deux noms d'un écran à l'autre, la langue
# inconnue « — » ici et « ? » là (UX-21). On affiche les noms de ffprobe.

_CODECS_MKVMERGE: dict[str, str] = {
    "subrip/srt": "subrip", "webvtt": "webvtt", "substationalpha": "ass",
    "hdmv pgs": "hdmv_pgs", "vobsub": "dvd_subtitle", "ac-3": "ac3",
    "e-ac-3": "eac3", "dts": "dts", "truehd": "truehd", "aac": "aac",
    "flac": "flac", "opus": "opus", "mp3": "mp3", "pcm": "pcm",
    "avc/h.264/mpeg-4p10": "h264", "hevc/h.265/mpeg-h": "hevc",
}


def nom_codec(codec: str) -> str:
    """Le nom affiché d'un codec, quelle que soit l'outil qui l'a lu.

    « unknown » est ce que rend ffprobe pour un flux qu'il ne sait pas lire —
    un WebVTT muxé par mkvmerge, par exemple : « ? », comme une langue
    inconnue.
    """
    if not codec or codec in ("unknown", "?"):
        return "?"
    return _CODECS_MKVMERGE.get(codec.lower(), codec)


def langue_affichee(code: str) -> str:
    """Code de langue, ou « ? » quand la piste n'en déclare pas."""
    return code or "?"
