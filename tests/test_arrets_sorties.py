"""
tests/test_arrets_sorties.py — Arrêts, pauses, sorties de l'application (IE-131).

Constats de la revue IE-114 :

- **CR-60** — `S` sur un encodage en pause : ffmpeg restait suspendu ;
- **CR-67** — un lecteur dans un état inhabituel empêchait IRIS de démarrer ;
- **CR-70** — en français, la confirmation de sortie affichait l'en-tête du
  catalogue ; **CR-103** — deux confirmations empilées ;
- **CR-71**, **CR-91** — un mux ou un collage survivait à la sortie, ou à
  `Ctrl+Home` ;
- **CR-95** — une réponse OpenSubtitles qui n'est pas du JSON fermait l'application ;
- **CR-104** — le compte à rebours recouvert retirait l'écran du dessus.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

RACINE = Path(__file__).resolve().parent.parent


# ─── CR-60 ────────────────────────────────────────────────────────────────────

def test_passer_un_encodage_en_pause_le_reprend_avant_de_l_arrêter():
    from tui.screens.run import RunScreen
    ordre = []
    proc = SimpleNamespace(resume=lambda: ordre.append("resume"),
                           terminate=lambda: ordre.append("terminate"))
    statut = SimpleNamespace(state=None, last_line="")
    faux = SimpleNamespace(_process=proc, _done=False, _current_idx=0,
                           _statuses=[statut], _paused=True,
                           _update_row=lambda i: None)
    RunScreen.action_skip_current(faux)
    assert ordre == ["resume", "terminate"]
    assert faux._paused is False


# ─── CR-67 ────────────────────────────────────────────────────────────────────

def test_un_lecteur_qui_lève_n_empêche_pas_de_lister_les_autres(monkeypatch):
    from tui.widgets import file_tree

    def exists(self):
        raise OSError(1005, "The volume does not contain a recognized file system")
    monkeypatch.setattr(Path, "exists", exists)
    monkeypatch.setattr(file_tree.sys, "platform", "win32")
    monkeypatch.setattr(file_tree.os.path, "isdir", lambda p: p in ("C:\\", "D:\\"))
    assert [str(v) for v in file_tree.list_volumes()] == ["C:\\", "D:\\"]


# ─── CR-70, CR-71, CR-103 ─────────────────────────────────────────────────────

@pytest.fixture
def francais():
    from core import i18n
    avant = i18n.langue()
    i18n.init("fr")
    yield
    i18n.init(avant)


def test_un_worker_hors_table_ne_traduit_pas_la_chaine_vide(francais):
    from tui.app import IrisEncodeApp
    faux = SimpleNamespace(
        _TRAVAUX=IrisEncodeApp._TRAVAUX, _lot=None,
        workers=[SimpleNamespace(name="scanner", is_running=True),
                 SimpleNamespace(name="muxer", is_running=True)])
    phrases = IrisEncodeApp.travaux_en_cours(faux)
    assert len(phrases) == 1
    assert "Project-Id-Version" not in phrases[0]


def test_quitter_arrête_les_écrans_de_tous_les_modes():
    from tui.app import IrisEncodeApp
    arretes = []
    mux = SimpleNamespace(_interrompre=lambda: arretes.append("mux"))
    lot = SimpleNamespace(_interrompre=lambda: arretes.append("lot"))
    faux = SimpleNamespace(_screen_stacks={"fichiers": [object(), mux],
                                           "encodages": [lot]},
                           screen_stack=[lot], _lot=lot, exit=lambda: arretes.append("exit"))
    IrisEncodeApp._on_quit_answer(faux, True)
    assert sorted(arretes) == ["exit", "lot", "mux"]


def test_une_seule_confirmation_de_sortie():
    from tui.app import IrisEncodeApp
    from tui.screens.quit import QuitConfirmScreen
    poussees = []
    faux = SimpleNamespace(screen=QuitConfirmScreen([]),
                           push_screen=lambda *a: poussees.append(a),
                           travaux_en_cours=lambda: [])
    IrisEncodeApp.action_request_quit(faux)
    assert poussees == []


# ─── CR-91 ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("fichier", ["join.py", "mux_run.py"])
def test_retour_a_l_accueil_arrête_mkvmerge(fichier):
    texte = (RACINE / "tui" / "screens" / fichier).read_text(encoding="utf-8")
    corps = texte[texte.index("def action_accueil"):]
    corps = corps[:corps.index("retour_accueil(self.app)")]
    assert "self._interrompre()" in corps


# ─── CR-95 ────────────────────────────────────────────────────────────────────

def test_une_réponse_html_devient_une_erreur_affichable(monkeypatch):
    import requests
    from core.opensubtitles import Client, ErreurOpenSubtitles
    reponse = SimpleNamespace(status_code=200, headers={},
                              text="<html>Portail Wi-Fi</html>",
                              json=lambda: (_ for _ in ()).throw(ValueError("Expecting value")))
    monkeypatch.setattr(requests, "request", lambda *a, **k: reponse)
    client = Client("cle", "", "", "iris")
    with pytest.raises(ErreurOpenSubtitles):
        client._appel("GET", "subtitles")


# ─── CR-104 ───────────────────────────────────────────────────────────────────

def test_le_compte_à_rebours_recouvert_attend_d_être_revenu_devant():
    from textual.app import App
    from textual.screen import Screen
    from tui.screens.fin_lot import FinDeLotModal

    class _Dessus(Screen):
        pass

    rendus = []

    class _App(App):
        def on_mount(self):
            self.push_screen(FinDeLotModal("rien", delai=1), rendus.append)
            self.push_screen(_Dessus())

    async def scenario():
        app = _App()
        async with app.run_test() as pilot:
            await pilot.pause(2.5)
            dessus = type(app.screen).__name__
            app.pop_screen()
            await pilot.pause(1.5)
            return dessus, list(rendus), type(app.screen).__name__

    dessus, rendus_vus, apres = asyncio.run(scenario())
    assert dessus == "_Dessus", "l'écran du dessus n'a pas été retiré"
    assert rendus_vus == [True], "rendu une fois, une fois revenu devant"
    assert apres != "FinDeLotModal"
