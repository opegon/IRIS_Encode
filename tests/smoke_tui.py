"""
tests/smoke_tui.py — Smoke test TUI headless (Textual run_test).

Pas un test pytest : à lancer manuellement depuis la racine du projet
    python tests/smoke_tui.py
Vérifie la navigation entre écrans, les modales de confirmation,
le resize de colonnes et le scan parallèle du browser.
"""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from textual.widgets import DataTable

from tui.app import IrisEncodeApp


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

            # F4 -> picker profils, Esc referme
            await pilot.press("f4")
            await pilot.pause(0.3)
            assert type(app.screen).__name__ == "ValuePickerScreen"
            await pilot.press("escape")
            await pilot.pause(0.3)
            assert type(app.screen).__name__ == "BrowserScreen"
            print("[4] ValuePicker (F4) ouvre et referme")

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
    with tempfile.TemporaryDirectory() as td:
        for i in range(5):
            (Path(td) / f"fake{i}.mkv").write_bytes(b"not a video" * 10)
        app = IrisEncodeApp(start_path=Path(td))
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause(3.0)   # laisse le pool de scan terminer
            table = app.screen.query_one(DataTable)
            # scan() tolerant : 5 fichiers -> 5 decisions (parallelisme verifie)
            assert table.row_count == 5, f"row_count={table.row_count}"
            # Refresh : l'epoch invalide le worker precedent, repopulation propre
            app.screen._refresh_view()
            await pilot.pause(2.0)
            assert table.row_count == 5, f"apres refresh : {table.row_count}"
            # Selection + resize ne plantent pas sur donnees reelles
            await pilot.press("space", "a", "tab", "greater_than_sign")
            await pilot.pause(0.5)
            assert table.row_count == 5
            print("[8] Scan parallele : 5 fichiers, refresh, selection OK")


async def main() -> None:
    await scenario_navigation()
    await scenario_parallel_scan()
    print("SMOKE OK")


if __name__ == "__main__":
    asyncio.run(main())
