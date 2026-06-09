"""
tests/smoke_tui.py — Smoke test TUI headless (Textual run_test).

Pas un test pytest : à lancer manuellement depuis la racine du projet
    python tests/smoke_tui.py
Vérifie la navigation entre écrans, les modales de confirmation,
le resize de colonnes et le scan parallèle du browser.
"""
import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from textual.widgets import DataTable

from tui.app import IrisEncodeApp


def _make_test_videos(td: Path, n: int) -> bool:
    """Genere n clips de 1 s avec ffmpeg. False si ffmpeg introuvable."""
    from core import config as cfg_mod
    from core.preflight import get_tool_path
    ffmpeg = get_tool_path("ffmpeg", cfg_mod.get_bin_dir(cfg_mod.load()))
    if not ffmpeg:
        return False
    for i in range(n):
        subprocess.run(
            [str(ffmpeg), "-y", "-loglevel", "error",
             "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
             "-c:v", "libx264", str(td / f"clip{i}.mkv")],
            check=True, capture_output=True,
        )
    return True


async def scenario_navigation() -> None:
    with tempfile.TemporaryDirectory() as td:
        app = IrisEncodeApp(start_path=Path(td))
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause(0.8)
            assert type(app.screen).__name__ == "BrowserScreen"
            print("[1] BrowserScreen monte")

            # F10 -> modale quitter ; Enter sur focus initial (Annuler) NE quitte PAS
            await pilot.press("f10")
            await pilot.pause(0.3)
            assert type(app.screen).__name__ == "QuitConfirmScreen"
            await pilot.press("enter")
            await pilot.pause(0.3)
            assert type(app.screen).__name__ == "BrowserScreen", \
                "Enter sur Annuler doit fermer sans quitter"
            assert app.is_running
            print("[2] Quit modal : Enter sur Annuler ne quitte pas")

            # F10 -> fleches deplacent le focus -> Esc annule
            await pilot.press("f10")
            await pilot.pause(0.3)
            await pilot.press("left")
            await pilot.pause(0.1)
            assert app.screen.focused.id == "btn-confirm"
            await pilot.press("escape")
            await pilot.pause(0.3)
            assert type(app.screen).__name__ == "BrowserScreen"
            print("[3] Quit modal : fleches + Esc OK")

            # F4 -> picker profils (table a colonnes), Esc referme
            await pilot.press("f4")
            await pilot.pause(0.3)
            assert type(app.screen).__name__ == "ProfilePickerScreen"
            await pilot.press("escape")
            await pilot.pause(0.3)
            assert type(app.screen).__name__ == "BrowserScreen"
            # Enter sur le profil courant : ferme et conserve l'actif
            before = app.active_profile_id
            await pilot.press("f4")
            await pilot.pause(0.3)
            await pilot.press("enter")
            await pilot.pause(0.3)
            assert type(app.screen).__name__ == "BrowserScreen"
            assert app.active_profile_id == before
            print("[4] ProfilePicker (F4) : table, Esc et Enter OK")

            # F5 -> ConfigScreen ; d sur builtin refuse ; Backspace revient
            await pilot.press("f5")
            await pilot.pause(0.3)
            assert type(app.screen).__name__ == "ConfigScreen"
            await pilot.press("d")
            await pilot.pause(0.2)
            assert type(app.screen).__name__ == "ConfigScreen"
            print("[5] ConfigScreen : suppr. builtin refusee (flash)")
            await pilot.press("backspace")
            await pilot.pause(0.3)
            assert type(app.screen).__name__ == "BrowserScreen", \
                "Backspace doit fermer ConfigScreen"
            print("[6] ConfigScreen : Backspace revient au browser")

            # Resize colonnes browser
            await pilot.press("tab")
            await pilot.pause(0.2)
            await pilot.press("greater_than_sign")
            await pilot.pause(0.2)
            assert type(app.screen).__name__ == "BrowserScreen"
            print("[7] Resize colonnes (Tab / >) OK")


async def scenario_parallel_scan() -> None:
    with tempfile.TemporaryDirectory() as td_str:
        td = Path(td_str)
        if not _make_test_videos(td, 3):
            print("[8-9] SKIP : ffmpeg introuvable, scenario scan reel non joue")
            return
        (td / "corrompu.mkv").write_bytes(b"not a video" * 10)

        app = IrisEncodeApp(start_path=td)
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause(0.5)
            # L'app demarre sur l'ecran virtuel Volumes (start_virtual=True) :
            # on pousse un browser pointe directement sur le dossier de test.
            from tui.screens.browser import BrowserScreen
            app.push_screen(BrowserScreen(td, start_virtual=False))
            await pilot.pause(4.0)   # laisse le pool de scan terminer
            scr   = app.screen
            table = scr.query_one(DataTable)
            # 3 clips valides scannes en parallele ; le corrompu est ecarte (et logue)
            assert table.row_count == 3, f"row_count={table.row_count}"
            assert len(scr._decisions) == 3, f"decisions={len(scr._decisions)}"
            # Refresh : l'epoch invalide le worker precedent, repopulation propre
            scr._refresh_view()
            await pilot.pause(2.5)
            assert table.row_count == 3, f"apres refresh : {table.row_count}"
            # Selection complete via la touche A
            await pilot.press("a")
            await pilot.pause(0.3)
            assert len(scr._selected) == 3, f"selected={len(scr._selected)}"
            # Resize : la table se reconstruit, selection conservee
            await pilot.press("tab", "greater_than_sign")
            await pilot.pause(0.5)
            assert table.row_count == 3
            assert len(scr._selected) == 3
            print("[8] Scan parallele reel : 3 clips + 1 corrompu ecarte, selection A, refresh, resize OK")

            # F1 -> dry-run : la table (avec colonne Duree) se construit
            await pilot.press("f1")
            await pilot.pause(0.8)
            assert type(app.screen).__name__ == "DryrunScreen", type(app.screen).__name__
            dr_table = app.screen.query_one(DataTable)
            assert dr_table.row_count == 3, f"dryrun row_count={dr_table.row_count}"
            assert len(dr_table.columns) == 10, f"colonnes={len(dr_table.columns)}"
            # Colonne Duree (index 2) remplie : clips d'1 s -> "0:01"
            duree = dr_table.get_row_at(0)[2].plain
            assert duree.startswith("0:0"), f"duree={duree!r}"
            await pilot.press("backspace")
            await pilot.pause(0.3)
            assert type(app.screen).__name__ == "BrowserScreen"
            print(f"[9] DryrunScreen : 3 lignes, 10 colonnes, Duree affichee ({duree}), retour OK")


async def main() -> None:
    await scenario_navigation()
    await scenario_parallel_scan()
    print("SMOKE OK")


if __name__ == "__main__":
    asyncio.run(main())
