"""
tests/test_densite.py — Ne pas payer deux fois, ne pas passer à la ligne trop tôt.

Deux constats de densité de la revue d'interface.

**IE-08** — la barre d'état donne le dossier courant ; quatre lignes plus bas, la
notice donnait le chemin *complet* du fichier survolé, qui recommence par ce même
dossier. Une quarantaine de colonnes payées deux fois : sur un chemin réseau, il ne
restait plus la place d'afficher le nom du fichier.

**IE-09** — le footer répartissait les raccourcis en trois bandes et enroulait
chacune séparément. Chaque bande démarrait donc une ligne, même pour une seule
entrée : « ⌫ Retour » ou « F10 Quitter » occupait une ligne entière.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from tui.common import footer_line2
from tui.widgets.footer import KeyFooter, pack, split_bands

RACINE = Path(__file__).resolve().parent.parent


# ─── IE-08 : la notice complète la barre d'état ───────────────────────────────

class _FauxNav:
    def __init__(self, courant: Path):
        self.current = courant


class _FauxEcran:
    """Juste ce qu'il faut pour appeler la méthode sans monter l'écran."""
    def __init__(self, courant: Path):
        self._nav = _FauxNav(courant)

    from tui.screens.browser import BrowserScreen as _B
    _libelle_survol = _B._libelle_survol


@pytest.mark.parametrize("courant, fichier, attendu", [
    # Cas courant : le dossier est déjà dans la barre d'état
    ("D:/films",          "D:/films/Watchmen.mkv",        "Watchmen.mkv"),
    # Scan récursif : le sous-dossier, lui, dit quelque chose de neuf
    ("D:/films",          "D:/films/2009/Watchmen.mkv",   "2009\\Watchmen.mkv"),
    # Hors de l'arborescence : plus rien n'est redondant
    ("D:/films",          "C:/ailleurs/Autre.mkv",        "C:\\ailleurs\\Autre.mkv"),
])
def test_la_notice_ne_repete_pas_le_dossier_courant(courant, fichier, attendu):
    ecran = _FauxEcran(Path(courant))
    assert ecran._libelle_survol(Path(fichier)) == attendu


def test_un_chemin_long_ne_mange_plus_la_notice():
    """Le cas qui motivait le constat : un partage réseau profond."""
    courant = Path(r"\\NAS\media\films\collection\integrale")
    fichier = courant / "Watchmen.2009.Ultimate.Cut.2160p.mkv"
    rendu = _FauxEcran(courant)._libelle_survol(fichier)
    assert rendu == "Watchmen.2009.Ultimate.Cut.2160p.mkv"
    assert len(rendu) < len(str(fichier)) - 30


# ─── IE-09 : une ligne ne se coupe qu'au débordement ──────────────────────────

_ACTIONS_RUN = [("p", "Pause / Reprendre"), ("s", "Passer le fichier"),
                ("backspace", "Retour")]


async def _lignes_rendues(actions, nav, largeur):
    from textual.app import App, ComposeResult
    from textual.widgets import Static

    class Bac(App):
        def compose(self) -> ComposeResult:
            yield KeyFooter(actions=actions, nav=nav)

    async with Bac().run_test(size=(largeur, 10)) as pilot:
        await pilot.pause(0.4)
        corps = pilot.app.query_one("#footer-body", Static)
        return [l for l in str(corps.render()).splitlines() if l.strip()]


def test_une_bande_d_une_entree_n_occupe_plus_sa_ligne():
    lignes = asyncio.run(_lignes_rendues(_ACTIONS_RUN, footer_line2(nav=False), 150))
    assert len(lignes) == 1, lignes
    assert "F10" in lignes[0] and "Retour" in lignes[0]


def test_l_ordre_par_role_est_conserve():
    """Propres à l'écran, puis globaux, puis touches de fonction."""
    lignes = asyncio.run(_lignes_rendues(_ACTIONS_RUN, footer_line2(nav=True), 150))
    texte = " ".join(lignes)
    assert texte.index("Pause") < texte.index("Début") < texte.index("Quitter")


def test_on_passe_bien_a_la_ligne_au_debordement():
    lignes = asyncio.run(_lignes_rendues(_ACTIONS_RUN, footer_line2(nav=True), 40))
    assert len(lignes) > 1


def test_aucun_raccourci_n_est_perdu():
    actions, nav = _ACTIONS_RUN, footer_line2(nav=True)
    attendus = len(actions) + len(nav)
    for largeur in (40, 80, 150):
        rendues = pack([p for b in split_bands(actions, nav) for p in b], largeur)
        assert sum(len(l) for l in rendues) == attendus, largeur
