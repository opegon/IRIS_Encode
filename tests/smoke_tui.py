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
            cols = [str(k.value) for k in dr_table.columns.keys()]
            assert len(cols) == 12, f"colonnes={len(cols)} {cols}"
            # Colonne Duree reperee par sa cle (l'index bouge a chaque ajout
            # de colonne) : clips d'1 s -> "0:01"
            duree = dr_table.get_row_at(0)[cols.index("duree")].plain
            assert duree.startswith("0:0"), f"duree={duree!r}"
            await pilot.press("backspace")
            await pilot.pause(0.3)
            assert type(app.screen).__name__ == "BrowserScreen"
            print(f"[9] DryrunScreen : 3 lignes, {len(cols)} colonnes, Duree affichee ({duree}), retour OK")


_SRT = """1
00:00:01,000 --> 00:00:03,000
Bonjour.
"""


def _make_donor_set(td: Path) -> bool:
    """Cible video+audio, donneur audio (VF) et sous-titre externe."""
    from core import config as cfg_mod
    from core.preflight import get_tool_path
    ffmpeg = get_tool_path("ffmpeg", cfg_mod.get_bin_dir(cfg_mod.load()))
    if not ffmpeg:
        return False
    subprocess.run(
        [str(ffmpeg), "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-c:v", "libx264", "-c:a", "ac3", str(td / "film.mkv")],
        check=True, capture_output=True,
    )
    subprocess.run(
        [str(ffmpeg), "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", "sine=frequency=880:duration=2",
         "-c:a", "ac3", str(td / "film.VF.mka")],
        check=True, capture_output=True,
    )
    (td / "film.fr.srt").write_text(_SRT, encoding="utf-8")
    return True


async def _add_donor(pilot, app, filename: str) -> None:
    """F9 -> choisit un donneur -> valide ses pistes -> revient sur SyncScreen."""
    await pilot.press("f9")
    await pilot.pause(0.6)
    table = app.screen.query_one(DataTable)
    noms  = [str(table.get_row_at(i)[0]) for i in range(table.row_count)]
    table.move_cursor(row=noms.index(filename))
    await pilot.press("enter")
    await pilot.pause(0.6)
    await pilot.press("enter")     # piste unique, déjà présélectionnée
    await pilot.pause(0.8)


async def scenario_external_tracks() -> None:
    """Greffe d'une VF et d'un sous-titre externes, recalés indépendamment."""
    with tempfile.TemporaryDirectory() as td_str:
        td = Path(td_str)
        if not _make_donor_set(td):
            print("[10-12] SKIP : ffmpeg introuvable")
            return

        app = IrisEncodeApp(start_path=td)
        if not app.mkvmerge_available:
            print("[10-12] SKIP : mkvmerge introuvable, greffe non testee")
            return

        async with app.run_test(size=(160, 45)) as pilot:
            await pilot.pause(0.5)
            from tui.screens.browser import BrowserScreen
            app.push_screen(BrowserScreen(td, start_virtual=False))
            await pilot.pause(4.0)

            await pilot.press("t")
            await pilot.pause(0.8)
            assert type(app.screen).__name__ == "TracksScreen", type(app.screen).__name__

            # F9 : le donneur ne doit jamais proposer la source elle-meme
            await pilot.press("f9")
            await pilot.pause(0.6)
            assert type(app.screen).__name__ == "DonorFileScreen", type(app.screen).__name__
            dtab = app.screen.query_one(DataTable)
            noms = [str(dtab.get_row_at(i)[0]) for i in range(dtab.row_count)]
            assert "film.mkv" not in noms, f"source proposee comme donneur : {noms}"
            await pilot.press("escape")
            await pilot.pause(0.4)
            print("[10] DonorFileScreen : source exclue de la liste")

            # Piste audio VF
            await _add_donor(pilot, app, "film.VF.mka")
            assert type(app.screen).__name__ == "SyncScreen", type(app.screen).__name__
            sync = app.screen
            await pilot.press("minus")        # -100 ms
            await pilot.press("shift+down")   # -1 s
            await pilot.pause(0.3)
            vf = sync._tracks[0]
            assert vf.delay_ms == -1100, vf.delay_ms
            await pilot.press("right")        # champ etirement
            await pilot.press("plus")
            await pilot.pause(0.3)
            assert vf.stretch == (24000, 25025), vf.stretch
            await pilot.press("right")        # champ langue
            await pilot.press("plus")
            await pilot.pause(0.3)
            assert vf.language == "fre", vf.language

            # Retour aux pistes, puis sous-titre externe depuis un autre fichier
            await pilot.press("backspace")
            await pilot.pause(0.5)
            assert type(app.screen).__name__ == "TracksScreen", type(app.screen).__name__
            await _add_donor(pilot, app, "film.fr.srt")
            assert type(app.screen).__name__ == "SyncScreen", type(app.screen).__name__
            sync = app.screen
            assert len(sync._tracks) == 2, len(sync._tracks)

            # Le sous-titre garde son propre decalage : independance des pistes
            sub = sync._tracks[1]
            sub.language = "fre"
            sub.delay_ms = 850
            assert vf.delay_ms == -1100 and sub.delay_ms == 850
            print("[11] SyncScreen : 2 pistes, decalages independants "
                  f"({vf.delay_ms} ms / {sub.delay_ms} ms)")

            # Mux reel
            await pilot.press("f2")
            await pilot.pause(4.0)
            assert type(app.screen).__name__ == "MuxScreen", type(app.screen).__name__
            assert app.screen._done, "mux non termine"
            assert app.screen._ok, "mux en echec"

            out = td / "film_[mux].mkv"
            assert out.exists(), "fichier muxe absent"
            from core import muxer
            produced = muxer.identify(out)
            langs = [t.language for t in produced]
            assert langs.count("fre") == 2, [t.display() for t in produced]
            print(f"[12] Mux : {out.name} produit, "
                  f"{len(produced)} pistes dont 2 en 'fre'")


async def main() -> None:
    await scenario_navigation()
    await scenario_parallel_scan()
    await scenario_external_tracks()
    print("SMOKE OK")


if __name__ == "__main__":
    asyncio.run(main())
