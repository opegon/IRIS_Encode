"""
tests/test_revue_interface.py — Revue d'interface du 2026-11-08, points 4 et 5.

4a. L'accueil en mode assistant n'annonce que son parcours.
4b. L'assistant montre un fil d'avancement (fait, en cours, à venir).
5a. L'écran d'encodage nomme ses colonnes Décodage / Filtres / Encodage.
5b. La liste des volumes nomme le partage d'un lecteur réseau, sans bande vide.
5c. La barre d'état explique les lignes grisées (sorties d'IRIS).
5d. Le bouton actif d'une confirmation porte ▶ ◀.
"""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest

from core import i18n
from core.i18n import pgettext


# ─── 5a ───────────────────────────────────────────────────────────────────────

def test_les_colonnes_de_l_encodage_se_lisent():
    i18n.init("fr")
    assert [pgettext("processing stage", m) for m in ("Decode", "Filter", "Encode")] \
        == ["Décodage", "Filtres", "Encodage"]
    source = Path("tui/screens/run.py").read_text(encoding="utf-8")
    assert '_("Read")' not in source


# ─── 4b ───────────────────────────────────────────────────────────────────────

def test_le_fil_de_l_assistant():
    from tui.screens.wizard import WizardScreen

    class Faux:
        _i = 1
        _fil = WizardScreen._fil

    i18n.init("fr")
    fil = Faux()._fil().plain
    assert fil.startswith("✓ Fichier ─ ● Décision ─ ○ Pistes externes"), fil
    assert fil.endswith("○ Terminé"), fil


# ─── Audio compact ────────────────────────────────────────────────────────────

def test_l_audio_regroupe_les_pistes_de_meme_format():
    """`ac3 5.1 fre  ac3 5.1 eng` prenait 24 colonnes à la colonne Fichier pour
    redire le format : les langues d'un même format se regroupent."""
    from types import SimpleNamespace
    from core.decision import AudioAction, FileDecision

    def piste(codec, canaux, langue, action=AudioAction.COPY):
        return SimpleNamespace(action=action, track=SimpleNamespace(
            codec=codec, channel_layout=canaux, language=langue,
            display=lambda: f"{codec} {canaux} {langue or '?'}"))

    def resume(*pistes):
        return FileDecision.audio_summary.fget(SimpleNamespace(audio=list(pistes)))

    assert resume(piste("ac3", "5.1", "fre"), piste("ac3", "5.1", "eng"),
                  piste("dts", "5.1", "eng")) == "ac3 5.1 fre+eng  dts 5.1 eng"
    # L'ordre est celui des pistes ; une langue absente reste « ? ».
    assert resume(piste("dts", "5.1", ""), piste("ac3", "5.1", "fre"),
                  piste("dts", "5.1", "eng")) == "dts 5.1 ?+eng  ac3 5.1 fre"
    assert resume(piste("ac3", "5.1", "fre", AudioAction.EXCLUDE)) == "—"


# ─── 5d ───────────────────────────────────────────────────────────────────────

def test_le_bouton_actif_se_voit():
    from textual.app import App
    from textual.widgets import Button
    from tui.screens.confirm import ConfirmModal

    async def releve():
        app = App()
        async with app.run_test(size=(100, 30)) as pilot:
            app.push_screen(ConfirmModal("Titre", "Corps"))
            await pilot.pause(0.3)
            ecran = app.screen
            avant = (str(ecran.query_one("#btn-confirm", Button).label),
                     str(ecran.query_one("#btn-cancel", Button).label))
            await pilot.press("left")
            await pilot.pause(0.2)
            apres = (str(ecran.query_one("#btn-confirm", Button).label),
                     str(ecran.query_one("#btn-cancel", Button).label))
        return avant, apres

    i18n.init("fr")
    (conf, annul), (conf2, annul2) = asyncio.run(releve())
    assert annul.startswith("▶") and not conf.startswith("▶"), (conf, annul)
    assert conf2.startswith("▶") and not annul2.startswith("▶"), (conf2, annul2)
    # Les blancs de l'inactif tiennent la place des marqueurs.
    assert len(conf) == len(conf2) and len(annul) == len(annul2)


# ─── 4a, 5c : accueil sur un dossier ─────────────────────────────────────────

def _clip(chemin: Path) -> bool:
    from core import config as cfg_mod
    from core.preflight import get_tool_path
    ffmpeg = get_tool_path("ffmpeg", cfg_mod.get_bin_dir(cfg_mod.load()))
    if not ffmpeg:
        return False
    subprocess.run(
        [str(ffmpeg), "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
         "-c:v", "libx264", str(chemin)],
        check=True, capture_output=True)
    return True


async def _accueil(td: Path, assistant: bool) -> dict:
    from textual.widgets import Static
    from tui.app import IrisEncodeApp
    from tui.screens.browser import BrowserScreen
    from tui.widgets.footer import KeyFooter

    app = IrisEncodeApp(start_path=td)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause(0.5)
        app.wizard_mode = assistant
        app.push_screen(BrowserScreen(td, start_virtual=False))
        for _tour in range(150):
            await pilot.pause(0.1)
            ecran = app.screen
            if (isinstance(ecran, BrowserScreen) and len(ecran._decisions) == 2
                    and not ecran._en_attente):
                break
        await pilot.pause(0.3)
        pied = ecran.query_one(KeyFooter)
        return {
            "pied": [cle for cle, _lib in pied._actions],
            "etat": str(ecran.query_one("#status-bar", Static).render()),
            "assistant": ecran._RACCOURCIS_ASSISTANT,
        }


def test_accueil_assistant_et_sorties_grisees(tmp_path, monkeypatch):
    if not (_clip(tmp_path / "film.mkv") and _clip(tmp_path / "film.hevc-iris.mkv")):
        pytest.skip("ffmpeg introuvable")
    from core import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "save", lambda *args, **kwargs: None)
    i18n.init("fr")

    r = asyncio.run(_accueil(tmp_path.resolve(), assistant=True))
    assert r["pied"] == [cle for cle, _lib in r["assistant"]]
    assert "f2" not in r["pied"] and "t" not in r["pied"]
    assert "1 sortie d'IRIS (grisée)" in r["etat"], r["etat"]

    r = asyncio.run(_accueil(tmp_path.resolve(), assistant=False))
    assert "t" in r["pied"], "le mode manuel garde sa liste entière"


# ─── 5b : liste des volumes ──────────────────────────────────────────────────

def test_les_volumes_nomment_le_partage(monkeypatch):
    from textual.widgets import DataTable
    from core import config as cfg_mod
    from core import emplacements as emp_mod
    from tui.app import IrisEncodeApp

    sep = chr(92)
    partage = sep * 2 + "serveur" + sep + "partage"
    monkeypatch.setattr(emp_mod, "lecteurs_reseau", lambda: {"D" + chr(58): partage})
    monkeypatch.setattr(cfg_mod, "save", lambda *args, **kwargs: None)
    i18n.init("fr")

    async def releve():
        app = IrisEncodeApp()
        async with app.run_test(size=(160, 40)) as pilot:
            await pilot.pause(2.0)
            ecran = app.screen
            table = ecran.query_one(DataTable)
            noms = [str(table.get_row_at(i)[0]) for i in range(table.row_count)]
            return (noms, ecran.query_one("#profile-bar").display,
                    ecran.query_one("#scan-row").display)

    noms, profil, analyse = asyncio.run(releve())
    ligne = next(n for n in noms if n.split()[-1:] and "D" + chr(58) in n)
    assert partage in ligne, noms
    assert not profil and not analyse
