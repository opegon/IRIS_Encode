"""
tests/test_footer_bindings.py — Une touche déclarée s'annonce.

La touche `R` du recalage était déclarée `show=True` et n'apparaissait nulle
part : la liste des raccourcis du pied de page était écrite à la main, à côté
des `BINDINGS`, et les deux ont divergé en silence. L'assistant, lui,
construisait son pied de page avec `actions=[]` — ses huit touches n'étaient
annoncées nulle part.

`actions_ecran()` lit désormais les `BINDINGS`. Ce test vérifie qu'aucun écran
n'y échappe, y compris les deux qui gardent une liste explicite parce que leur
contenu dépend du contexte (l'accueil : volumes ou fichiers).
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from tui.common import _TOUCHES_BANDE_2, actions_ecran, footer_line2
from tui.screens.browser import BrowserScreen
from tui.screens.config import ConfigScreen
from tui.screens.dryrun import DryrunScreen
from tui.screens.join import JoinScreen
from tui.screens.mux_run import MuxScreen
from tui.screens.run import RunScreen
from tui.screens.sync import SyncScreen
from tui.screens.tracks import TracksScreen
from tui.screens.wizard import WizardScreen, _TOUCHES_ETAPE

_ECRANS = [BrowserScreen, ConfigScreen, DryrunScreen, JoinScreen, MuxScreen,
           RunScreen, SyncScreen, TracksScreen, WizardScreen]


def _declarees(classe) -> set[str]:
    """Les touches que l'écran annonce comme visibles, bande 2 exclue."""
    touches = set()
    for c in classe.__mro__:
        for b in c.__dict__.get("BINDINGS", ()):
            if not getattr(b, "show", False):
                continue
            cle = getattr(b, "key", "").split(",")[0].strip().lower()
            if cle not in _TOUCHES_BANDE_2:
                touches.add(cle)
    return touches


@pytest.mark.parametrize("classe", _ECRANS, ids=lambda c: c.__name__)
def test_actions_ecran_rend_toutes_les_touches_visibles(classe):
    """`show=True` veut dire « affichée » — pas « affichée si on y pense »."""
    rendues = {k for k, _ in actions_ecran(classe)}
    assert rendues == _declarees(classe)


@pytest.mark.parametrize("classe", _ECRANS, ids=lambda c: c.__name__)
def test_aucun_libelle_vide(classe):
    for cle, libelle in actions_ecran(classe):
        assert libelle.strip(), f"{classe.__name__}: {cle} sans libellé"


# ── Le pied de page complet, lu dans le code de l'écran ──────────────────────

def _nav_de_lecran(module: str) -> list[tuple[str, str]]:
    """Rejoue l'appel `footer_line2(...)` que l'écran fait dans `compose`.

    Lire la source plutôt qu'une table écrite ici : une table dupliquerait
    l'information qu'on cherche justement à ne plus dupliquer. L'appel est
    fait de littéraux, il s'évalue sans exécuter l'écran.
    """
    arbre = ast.parse(pathlib.Path("tui/screens", f"{module}.py")
                      .read_text(encoding="utf-8"))
    # Celui de `compose` seulement : les autres appels servent aux bascules de
    # contexte (l'accueil sur un volume, la config en formulaire), où masquer
    # une touche qui ne répond pas est le comportement voulu.
    for n in ast.walk(arbre):
        if not (isinstance(n, ast.FunctionDef) and n.name == "compose"):
            continue
        for c in ast.walk(n):
            if isinstance(c, ast.Call) and getattr(c.func, "id", "") == "footer_line2":
                kw = {k.arg: ast.literal_eval(k.value) for k in c.keywords}
                return footer_line2(**kw)
    raise AssertionError(f"aucun footer_line2 dans compose() de {module}")


_MODULES = {
    "BrowserScreen": "browser", "ConfigScreen": "config",
    "DryrunScreen": "dryrun",   "JoinScreen": "join",
    "MuxScreen": "mux_run",
    "RunScreen": "run",         "SyncScreen": "sync",
    "TracksScreen": "tracks",   "WizardScreen": "wizard",
}


@pytest.mark.parametrize("classe", _ECRANS, ids=lambda c: c.__name__)
def test_aucune_touche_visible_nest_absente_du_pied_de_page(classe):
    """
    L'invariant complet : `show=True` implique « présente à l'écran ».

    Il porte sur les deux bandes. Dériver la première des `BINDINGS` a fermé
    le trou d'origine, mais en a ouvert un autre : `⌫ Retour`, déclarée par
    l'écran et rendue par la bande 2, disparaissait des quatre écrans dont
    l'appel à `footer_line2` ne la demandait pas.
    """
    module = _MODULES[classe.__name__]
    if classe is BrowserScreen:
        actions = BrowserScreen._RACCOURCIS_FICHIERS
    elif classe is WizardScreen:
        actions = [p for t in _TOUCHES_ETAPE.values()
                   for p in actions_ecran(classe, t)]
    else:
        actions = actions_ecran(classe)
    pied = {k for k, _ in actions} | {k for k, _ in _nav_de_lecran(module)}
    # Les touches de la bande 2 que l'écran déclare aussi.
    declarees = set()
    for c in classe.__mro__:
        for b in c.__dict__.get("BINDINGS", ()):
            if getattr(b, "show", False):
                declarees.add(getattr(b, "key", "").split(",")[0].strip().lower())
    manquantes = declarees - pied
    assert not manquantes, f"{classe.__name__} : touches déclarées absentes {manquantes}"


def test_le_recalage_annonce_la_touche_de_repere():
    """Le constat d'origine, nommément.

    Le point de repère est la seule issue quand la corrélation plafonne — un
    sous-titre dont l'adaptation diffère du doublage ne se mesure pas. Une
    porte de sortie qui ne s'annonce pas n'existe pas.
    """
    assert "r" in {k for k, _ in actions_ecran(SyncScreen)}


def test_lassistant_annonce_les_touches_de_chaque_etape():
    """`actions=[]` n'annonçait rien ; chaque étape annonce désormais ses touches."""
    for etape, touches in _TOUCHES_ETAPE.items():
        rendues = [k for k, _ in actions_ecran(WizardScreen, touches)]
        assert rendues == list(touches), etape


def test_les_touches_declarees_par_etape_existent_dans_les_bindings():
    """Une étape ne peut pas annoncer une touche que l'écran ne lie pas."""
    connues = _declarees(WizardScreen)
    for etape, touches in _TOUCHES_ETAPE.items():
        inconnues = set(touches) - connues
        assert not inconnues, f"{etape}: {inconnues}"


def test_lassistant_couvre_toutes_ses_touches_sur_lensemble_des_etapes():
    """Aucune touche visible ne doit rester introuvable, étape après étape."""
    vues = {k for touches in _TOUCHES_ETAPE.values() for k in touches}
    assert vues == _declarees(WizardScreen)


def test_laccueil_annonce_ses_touches_malgre_sa_liste_explicite():
    """
    L'accueil garde une liste écrite à la main : ses raccourcis dépendent du
    contexte (un volume ne s'encode pas, ne se sélectionne pas). Il n'échappe
    pas à la règle pour autant — la couverture est vérifiée ici.
    """
    pied = ({k for k, _ in BrowserScreen._RACCOURCIS_FICHIERS}
            | {k for k, _ in footer_line2(
                nav=False, resize=True,
                extra=(("f1", ""), ("f2", ""), ("f3", ""), ("f4", ""),
                       ("f5", ""), ("f6", ""), ("f7", ""), ("f8", "")))})
    manquantes = _declarees(BrowserScreen) - pied
    assert not manquantes, f"touches visibles absentes du pied de page : {manquantes}"
