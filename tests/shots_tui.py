"""
tests/shots_tui.py — Inventaire visuel des écrans (export SVG).

Pas un test pytest : à lancer manuellement depuis la racine du projet
    python tests/shots_tui.py [dossier_de_sortie]

Pilote l'application en headless (Textual run_test) et exporte chaque écran
en SVG à taille fixe (160x45), pour disposer d'un inventaire fidèle du rendu
réel — et non d'une maquette. Deux contextes :

  A. `resources_files/` — matériel réel (noms longs, pistes multiples, HDR).
     Aucune touche destructrice n'y est pressée : ni F2, ni F3, ni Ctrl+D.
  B. un dossier temporaire — pour les écrans qui écrivent (suppression, mux,
     encodage), qui ne doivent jamais toucher au matériel réel.

Chaque prise est isolée : une prise qui échoue est consignée, les suivantes
continuent. Le récapitulatif final liste ce qui a été capturé et ce qui ne
l'a pas été, avec le motif.
"""
from __future__ import annotations

import asyncio
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))   # pour smoke_tui

from textual.widgets import DataTable

from main import force_utf8_output
from tui.app import IrisEncodeApp

force_utf8_output()

SIZE     = (160, 45)
ROOT     = Path(__file__).resolve().parent.parent
OUT_DIR  = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_shots"
REAL_DIR = ROOT / "resources_files"

# (slug, libellé, classe d'écran, état, détail)
MANIFEST: list[tuple[str, str, str, str, str]] = []


async def shot(app, slug: str, label: str, expect: str | None = None) -> bool:
    """Exporte l'écran courant. Consigne l'écart si ce n'est pas celui attendu."""
    got = type(app.screen).__name__
    if expect is not None and got != expect:
        MANIFEST.append((slug, label, got, "ECART", f"attendu {expect}"))
        return False
    svg  = app.export_screenshot(title=f"{label} - {got}")
    path = OUT_DIR / f"{slug}.svg"
    path.write_text(svg, encoding="utf-8")
    MANIFEST.append((slug, label, got, "OK", f"{len(svg) // 1024} Ko"))
    return True


def skipped(slug: str, label: str, why: str) -> None:
    MANIFEST.append((slug, label, "-", "NON CAPTURE", why))


def failed(slug: str, label: str, exc: BaseException) -> None:
    MANIFEST.append((slug, label, "-", "ECHEC", f"{type(exc).__name__}: {exc}"))


def _row_index(scr, needle: str) -> int | None:
    """Index de la première ligne dont le nom de fichier contient `needle`."""
    for i, (_kind, path) in enumerate(scr._rows):
        if path is not None and needle.lower() in path.name.lower():
            return i
    return None


def _dir_index(scr) -> int | None:
    """Index de la première ligne pointant sur un dossier."""
    for i, (_kind, path) in enumerate(scr._rows):
        if path is not None and path.is_dir():
            return i
    return None


async def _goto(pilot, table: DataTable, row: int) -> None:
    table.move_cursor(row=row)
    await pilot.pause(0.3)


# ─────────────────────────────────────────────────────────────────────────────
# Contexte A — matériel réel, lecture seule
# ─────────────────────────────────────────────────────────────────────────────

async def context_real() -> None:
    if not REAL_DIR.is_dir() or not any(REAL_DIR.iterdir()):
        skipped("A", "contexte matériel réel", f"{REAL_DIR} vide ou absent")
        return

    app = IrisEncodeApp(start_path=REAL_DIR)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause(1.0)
        await shot(app, "01-browser-volumes", "Browser - volumes", "BrowserScreen")

        from tui.screens.browser import BrowserScreen
        app.push_screen(BrowserScreen(REAL_DIR, start_virtual=False))
        await pilot.pause(15.0)          # scan parallèle + sondage DV
        scr   = app.screen
        table = scr.query_one(DataTable)
        await shot(app, "02-browser-fichiers", "Browser - fichiers", "BrowserScreen")

        # ── Modales atteignables depuis le browser ───────────────────────────
        for slug, label, key, expect in (
            ("03-profile-picker", "Choix du profil (F4)",     "f4",  "ProfilePickerScreen"),
            ("04-config",         "Gestion des profils (F5)", "f5",  "ConfigScreen"),
            ("05-quit",           "Confirmation de sortie",   "f10", "QuitConfirmScreen"),
        ):
            try:
                await pilot.press(key)
                await pilot.pause(0.6)
                await shot(app, slug, label, expect)
                if expect == "ConfigScreen":
                    await pilot.press("e")      # formulaire d'édition de profil
                    await pilot.pause(0.8)
                    await shot(app, "04b-config-form", "Edition d'un profil (e)")
                    await pilot.press("escape")
                    await pilot.pause(0.4)
                await pilot.press("escape")
                await pilot.pause(0.5)
            except Exception as exc:
                failed(slug, label, exc)

        # Le parcours récursif (F3) exige un dossier sous le curseur :
        # `resources_files/` n'en contient aucun, la prise se fait en contexte B.

        # ── Fiche AlloCiné (F7) ──────────────────────────────────────────────
        # Seule prise qui sort de la machine : elle envoie le titre du film à
        # allocine.fr, exactement comme le fait l'application en usage normal.
        try:
            i = next(k for k, (_t, p) in enumerate(scr._rows)
                     if p is not None and p.suffix.lower() in (".mkv", ".mp4"))
            await _goto(pilot, table, i)
            await pilot.press("f7")
            await pilot.pause(6.0)
            await shot(app, "17-meta", "Fiche AlloCiné (F7)", "MetaPopup")
            await pilot.press("escape")
            await pilot.pause(0.5)
        except Exception as exc:
            failed("17-meta", "Fiche AlloCiné (F7)", exc)

        # ── Dry-run sur deux fichiers ────────────────────────────────────────
        try:
            cibles = [i for i, (_k, p) in enumerate(scr._rows)
                      if p is not None and p.suffix.lower() in (".mkv", ".mp4")][:2]
            for i in cibles:
                await _goto(pilot, table, i)
                await pilot.press("space")
            await pilot.pause(0.5)
            await pilot.press("f1")
            await pilot.pause(4.0)
            await shot(app, "07-dryrun", "Dry-run (F1)", "DryrunScreen")
            await pilot.press("backspace")
            await pilot.pause(1.0)
        except Exception as exc:
            failed("07-dryrun", "Dry-run (F1)", exc)

        # ── Pistes, puis greffe d'un sous-titre externe ──────────────────────
        try:
            i = _row_index(scr, "zookeeper s wife 2017.mkv")
            if i is None:
                i = next(k for k, (_t, p) in enumerate(scr._rows)
                         if p is not None and p.suffix.lower() == ".mkv")
            await _goto(pilot, table, i)
            await pilot.press("t")
            await pilot.pause(3.0)
            await shot(app, "08-tracks", "Pistes (t)", "TracksScreen")

            await pilot.press("f6")            # liste de valeurs (codec)
            await pilot.pause(0.6)
            await shot(app, "09-value-picker", "Liste de valeurs (F6)",
                       "ValuePickerScreen")
            await pilot.press("escape")
            await pilot.pause(0.5)

            await pilot.press("f9")            # choix du fichier donneur
            await pilot.pause(2.0)
            await shot(app, "10-donor-file", "Fichier donneur (F9)",
                       "DonorFileScreen")

            dtab = app.screen.query_one(DataTable)
            noms = [str(dtab.get_row_at(k)[0]) for k in range(dtab.row_count)]
            srt  = next((k for k, n in enumerate(noms)
                         if n.lower().endswith(".srt")), None)
            if srt is None:
                await pilot.press("escape")
                skipped("11-donor-tracks", "Pistes du donneur", "aucun .srt listé")
                skipped("12-sync", "Recalage", "aucun donneur retenu")
            else:
                dtab.move_cursor(row=srt)
                await pilot.press("enter")
                await pilot.pause(2.0)
                await shot(app, "11-donor-tracks", "Pistes du donneur",
                           "DonorTrackScreen")
                await pilot.press("enter")
                await pilot.pause(2.5)
                await shot(app, "12-sync", "Recalage (SyncScreen)", "SyncScreen")
            # Le point de repère : la modale propose une réplique, il ne
            # reste qu'un instant à donner.
            await pilot.press("r")
            await pilot.pause(2.0)
            if type(app.screen).__name__ == "AncrageModal":
                await shot(app, "13-ancrage", "Point de repère (r)",
                           "AncrageModal")
                await pilot.press("escape")
                await pilot.pause(0.5)
            else:
                skipped("13-ancrage", "Point de repère (r)",
                        f"écran inattendu : {type(app.screen).__name__}")

            # Ctrl+Home depuis un écran qui porte un travail non validé.
            await pilot.press("ctrl+home")
            await pilot.pause(0.8)
            if type(app.screen).__name__ == "ConfirmModal":
                await shot(app, "13b-accueil-confirm",
                           "Retour accueil depuis le recalage (Ctrl+Home)",
                           "ConfirmModal")
                await pilot.press("escape")
                await pilot.pause(0.5)
            else:
                skipped("13b-accueil-confirm", "Retour accueil",
                        f"écran inattendu : {type(app.screen).__name__}")
        except Exception as exc:
            failed("08-tracks", "Pistes / donneur / recalage", exc)

        # ── L'assistant, cinq étapes ─────────────────────────────────────────
        try:
            while type(app.screen).__name__ != "BrowserScreen":
                await pilot.press("escape")
                await pilot.pause(0.4)
            app.wizard_mode = True
            scr   = app.screen
            table = scr.query_one(DataTable)
            await shot(app, "02b-browser-assistant",
                       "Accueil en mode assistant (W)", "BrowserScreen")

            i = next(k for k, (_t, p) in enumerate(scr._rows)
                     if p is not None and p.suffix.lower() == ".mkv")
            await _goto(pilot, table, i)
            await pilot.press("enter")
            await pilot.pause(3.0)
            etapes = [("18-wizard-1-fichier",  "Assistant 1 - Fichier"),
                      ("19-wizard-2-decision", "Assistant 2 - Décision"),
                      ("20-wizard-3-pistes",   "Assistant 3 - Pistes externes"),
                      ("21-wizard-4-lancer",   "Assistant 4 - Lancer")]
            for n, (slug, label) in enumerate(etapes):
                await shot(app, slug, label, "WizardScreen")
                if n < len(etapes) - 1:
                    await pilot.press("enter")
                    await pilot.pause(1.0)
            await pilot.press("ctrl+home")
            await pilot.pause(0.8)
        except Exception as exc:
            failed("18-wizard", "Assistant", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Contexte B — dossier temporaire, écrans qui écrivent
# ─────────────────────────────────────────────────────────────────────────────

def _make_set(td: Path) -> bool:
    """Cible vidéo+audio, donneur audio VF, sous-titre — clips de 2 s."""
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
        check=True, capture_output=True)
    subprocess.run(
        [str(ffmpeg), "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", "sine=frequency=880:duration=2",
         "-c:a", "ac3", str(td / "film.VF.mka")],
        check=True, capture_output=True)
    (td / "film.fr.srt").write_text(
        "1\n00:00:01,000 --> 00:00:02,000\nBonjour.\n", encoding="utf-8")
    # Un sous-dossier : le parcours récursif (F3) ne s'ouvre que sur un dossier.
    saison = td / "Saison 1"
    saison.mkdir()
    subprocess.run(
        [str(ffmpeg), "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=10",
         "-c:v", "libx264", str(saison / "episode.mkv")],
        check=True, capture_output=True)
    return True


async def context_temp() -> None:
    with tempfile.TemporaryDirectory() as td_str:
        td = Path(td_str)
        if not _make_set(td):
            for slug, label in (("14-delete", "Suppression (Ctrl+D)"),
                                ("15-mux",    "Mux (F3)"),
                                ("16-run",    "Encodage (F2)")):
                skipped(slug, label, "ffmpeg introuvable")
            return

        app = IrisEncodeApp(start_path=td)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause(0.5)
            from tui.screens.browser import BrowserScreen
            app.push_screen(BrowserScreen(td, start_virtual=False))
            await pilot.pause(5.0)
            scr   = app.screen
            table = scr.query_one(DataTable)

            try:
                d = _dir_index(scr)
                if d is None:
                    skipped("06-recursif", "Parcours récursif (F3)",
                            "aucun sous-dossier listé")
                else:
                    await _goto(pilot, table, d)
                    await pilot.press("f3")
                    await pilot.pause(0.8)
                    await shot(app, "06-recursif", "Parcours récursif (F3)",
                               "RecursiveConfirmModal")
                    await pilot.press("escape")     # ne JAMAIS confirmer
                    await pilot.pause(0.5)
            except Exception as exc:
                failed("06-recursif", "Parcours récursif (F3)", exc)

            try:
                # Ctrl+D n'ouvre la modale que sur un fichier : les .srt ne
                # sont pas listés, on vise la vidéo (Esc annule ensuite).
                f = _row_index(scr, "film.mkv")
                await _goto(pilot, table, f if f is not None else 0)
                await pilot.press("ctrl+d")
                await pilot.pause(0.6)
                await shot(app, "14-delete", "Suppression (Ctrl+D)",
                           "DeleteConfirmModal")
                await pilot.press("escape")     # ne JAMAIS confirmer
                await pilot.pause(0.5)
            except Exception as exc:
                failed("14-delete", "Suppression (Ctrl+D)", exc)

            if not app.mkvmerge_available:
                skipped("15-mux", "Mux (F3)", "mkvmerge introuvable")
                skipped("16-run", "Encodage (F2)", "mux préalable non joué")
                return

            try:
                i = _row_index(scr, "film.mkv")
                await _goto(pilot, table, i if i is not None else 0)
                await pilot.press("t")
                await pilot.pause(1.5)
                await pilot.press("f9")            # donneur
                await pilot.pause(1.0)
                dtab = app.screen.query_one(DataTable)
                noms = [str(dtab.get_row_at(k)[0]) for k in range(dtab.row_count)]
                dtab.move_cursor(row=noms.index("film.VF.mka"))
                await pilot.press("enter")
                await pilot.pause(1.0)
                await pilot.press("enter")
                await pilot.pause(1.2)
                await pilot.press("f3")            # mux réel, en temporaire
                await pilot.pause(6.0)
                await shot(app, "15-mux", "Mux (F3)", "MuxScreen")
            except Exception as exc:
                failed("15-mux", "Mux (F3)", exc)

            try:
                await pilot.press("f2")            # encodage réel, clip de 2 s
                await pilot.pause(3.0)
                await shot(app, "16-run", "Encodage (F2)", "RunScreen")
                await pilot.pause(5.0)
                await shot(app, "16b-run-fin", "Encodage - terminé")
            except Exception as exc:
                failed("16-run", "Encodage (F2)", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Contexte C — mesure automatique, pour atteindre l'écran des plages
# ─────────────────────────────────────────────────────────────────────────────

def _split_edit(srt: Path, extra_ms: int = 3000) -> None:
    """Rend le SRT incompatible avec un décalage unique.

    La seconde moitié des répliques reçoit un décalage supplémentaire : la
    mesure ne peut plus conclure à un palier unique, elle relève des plages —
    c'est la seule voie qui ouvre SegmentsScreen.
    """
    import re

    def to_ms(t: str) -> int:
        h, m, rest = t.split(":")
        s, ms = rest.split(",")
        return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)

    def to_ts(v: int) -> str:
        v = max(0, v)
        h, r = divmod(v, 3_600_000)
        m, r = divmod(r, 60_000)
        s, ms = divmod(r, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lignes = srt.read_text(encoding="utf-8").splitlines()
    temps  = [(i, l) for i, l in enumerate(lignes) if "-->" in l]
    pivot  = to_ms(temps[len(temps) // 2][1].split(" --> ")[0])
    for i, l in temps:
        a, b = (to_ms(x.strip()) for x in l.split("-->"))
        if a >= pivot:
            a, b = a + extra_ms, b + extra_ms
        lignes[i] = f"{to_ts(a)} --> {to_ts(b)}"
    srt.write_text("\n".join(lignes) + "\n", encoding="utf-8")


async def _measure_run(td: Path, slug: str, label: str,
                       segments: bool) -> None:
    """Monte la cible + le SRT, lance la mesure, prend la vue demandée."""
    from smoke_tui import _add_donor

    app = IrisEncodeApp(start_path=td)
    if not app.mkvmerge_available:
        skipped(slug, label, "mkvmerge introuvable")
        return

    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause(0.5)
        from tui.screens.browser import BrowserScreen
        app.push_screen(BrowserScreen(td, start_virtual=False))
        await pilot.pause(6.0)
        await pilot.press("t")
        await pilot.pause(1.5)
        await _add_donor(pilot, app, "film.fr.srt")

        sync = app.screen
        await pilot.press("m")
        for _ in range(60):
            await pilot.pause(0.5)
            if not sync._measuring:
                break
        if sync._measuring:
            skipped(slug, label, "mesure non terminée en 30 s")
            return
        if not segments:
            await shot(app, slug, label, "SyncScreen")
            return
        if sync._segments is None:
            skipped(slug, label,
                    "la mesure a conclu à un palier unique : aucune plage à "
                    "montrer (l'écran n'existe qu'en cas de montage différent)")
            return
        await pilot.press("s")
        await pilot.pause(1.0)
        await shot(app, slug, label, "SegmentsScreen")
        await pilot.press("escape")
        await pilot.pause(0.4)


async def context_segments() -> None:
    """SegmentsScreen n'existe qu'après une mesure : il faut la jouer.

    Le matériel mesurable (vidéo à parole intermittente + SRT décalé) est celui
    de `smoke_tui`, réutilisé tel quel plutôt que redéfini ici. Deux passes :
    un décalage uniforme pour le compte rendu de mesure, puis un SRT à deux
    montages pour l'écran des plages.
    """
    from smoke_tui import _make_measurable_set

    for slug, label, segments in (
        ("12b-sync-mesure", "Recalage - après mesure", False),
        ("13-segments",     "Plages de parole (s)",    True),
    ):
        with tempfile.TemporaryDirectory() as td_str:
            td = Path(td_str)
            try:
                if not _make_measurable_set(td):
                    skipped(slug, label, "ffmpeg introuvable")
                    continue
                if segments:
                    _split_edit(td / "film.fr.srt")
                await _measure_run(td, slug, label, segments)
            except Exception as exc:
                failed(slug, label, exc)


async def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for scenario in (context_real, context_temp, context_segments):
        try:
            await scenario()
        except Exception:
            traceback.print_exc()
            MANIFEST.append((scenario.__name__, "contexte entier", "-",
                             "ECHEC", "voir la trace ci-dessus"))

    print()
    print(f"{'prise':22} {'ecran':24} {'etat':12} detail")
    print("-" * 100)
    for slug, _label, cls, state, detail in MANIFEST:
        print(f"{slug:22} {cls:24} {state:12} {detail}")
    ok = sum(1 for m in MANIFEST if m[3] == "OK")
    print("-" * 100)
    print(f"{ok} prises exportees dans {OUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
