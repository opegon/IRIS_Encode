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

from textual.widgets import DataTable, Static

from core.decision import VideoAction
from main import force_utf8_output
from tui.app import IrisEncodeApp

# Ce harnais affiche des symboles absents du cp1252 : sans ca, il meurt sur un
# UnicodeEncodeError des que sa sortie est redirigee (pipe, fichier, Git Bash).
force_utf8_output()


def _styles_du_footer(pied) -> str:
    """Styles Rich reellement appliques dans le footer, mis a plat.

    Rich normalise et reordonne les styles (« bold white » ressort en
    « ansi_white bold ») : chercher la couleur dans le texte des styles evite
    de faire echouer le test pour une raison qui n'a rien a voir avec ce qu'il
    verifie.
    """
    from textual.widgets import Static as _S
    rendu = pied.query_one("#footer-body", _S).render()
    return " ".join(str(sp.style) for sp in rendu.spans)


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

            # 'v' : visualisation du fichier sous le curseur. On intercepte mpv
            # pour verifier la cible sans faire surgir de fenetre.
            from core import preview as preview_mod
            ouverts: list[Path] = []
            vrai_open, vrai_dispo = preview_mod.open_file, preview_mod.available
            preview_mod.open_file = lambda p: ouverts.append(p)
            preview_mod.available = lambda: True
            try:
                await pilot.press("v")
                await pilot.pause(0.4)
                assert len(ouverts) == 1, ouverts
                assert ouverts[0].suffix == ".mkv", ouverts[0]
                assert ouverts[0].parent == td, ouverts[0]
            finally:
                preview_mod.open_file, preview_mod.available = vrai_open, vrai_dispo
            print(f"[8b] Lecture depuis le browser : {ouverts[0].name}")

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

            # Ctrl+D : suppression du fichier sous le curseur, avec confirmation.
            table.move_cursor(row=0)
            await pilot.pause(0.2)
            cible = scr._rows[0][1]
            # 1er passage : Esc annule, le fichier survit
            await pilot.press("ctrl+d")
            await pilot.pause(0.4)
            assert type(app.screen).__name__ == "DeleteConfirmModal", type(app.screen).__name__
            await pilot.press("escape")
            await pilot.pause(0.4)
            assert cible.exists(), "Esc a supprime le fichier"
            assert table.row_count == 3, f"apres annulation : {table.row_count}"
            # 2e passage : le focus part sur Annuler, -> puis Enter confirment
            await pilot.press("ctrl+d")
            await pilot.pause(0.4)
            await pilot.press("right", "enter")
            await pilot.pause(0.5)
            assert not cible.exists(), f"{cible.name} existe encore"
            assert table.row_count == 2, f"apres suppression : {table.row_count}"
            assert len(scr._decisions) == 2, f"decisions={len(scr._decisions)}"
            assert cible not in scr._selected
            print(f"[9b] Ctrl+D : Esc annule, confirmation supprime {cible.name} (3 -> 2 lignes)")


_SRT = """1
00:00:01,000 --> 00:00:03,000
Bonjour.
"""

# Decalage injecte dans le SRT du scenario de mesure (secondes)
_MEASURE_OFFSET = 2.5


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

            # Ces scenarios eprouvent le parcours libre ; l'assistant a le sien.
            app.wizard_mode = False
            await pilot.press("t")
            await pilot.pause(0.8)
            assert type(app.screen).__name__ == "TracksScreen", type(app.screen).__name__

            # Le nom du profil actif etait invisible : ecrit « [serie_basic] »,
            # Rich le prenait pour une balise et le supprimait.
            barre = str(app.screen.query_one("#status-bar", Static).render())
            actif = app.active_profile_id
            assert actif in barre, f"profil absent de la barre -> {barre!r}"
            print(f"[9d] TracksScreen : le profil [{actif}] apparait dans la barre")

            # Regression : STRIP_DV n'appartient pas a ACTION_CYCLE. F6 y
            # cherchait l'index de l'action courante et levait un ValueError.
            from dataclasses import replace as dc_replace

            from core.decision import VideoAction as _VA
            tracks = app.screen
            avant  = tracks._decision
            tracks._decision = dc_replace(
                avant, video=dc_replace(avant.video, action=_VA.STRIP_DV))
            await pilot.press("f6")
            await pilot.pause(0.5)
            assert type(app.screen).__name__ == "ValuePickerScreen", type(app.screen).__name__
            await pilot.press("escape")
            await pilot.pause(0.4)
            await pilot.press("plus")          # cycle +/- sur la meme action
            await pilot.pause(0.3)
            tracks._decision = avant
            print("[9c] TracksScreen : F6 et +/- sur une decision STRIP_DV")

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

            # Pas fin : la question n'est pas que la liaison soit declaree,
            # c'est qu'elle traverse le DataTable, qui etouffe les touches
            # avant le systeme de bindings (voir l'entete de tui/mixins.py).
            await pilot.press("ctrl+down")    # -10 ms
            await pilot.press("ctrl+down")
            await pilot.pause(0.3)
            assert vf.delay_ms == -1120, vf.delay_ms
            await pilot.press("ctrl+up")      # +10 ms
            await pilot.pause(0.3)
            assert vf.delay_ms == -1110, vf.delay_ms
            print(f"[11a] Pas fin Ctrl+haut/bas : {vf.delay_ms} ms "
                  "(atteint l'action a travers le DataTable)")
            await pilot.press("ctrl+up")      # retour a -1100
            await pilot.pause(0.3)
            assert vf.delay_ms == -1100, vf.delay_ms
            await pilot.press("right")        # champ etirement
            await pilot.press("plus")
            await pilot.pause(0.3)
            assert vf.stretch == (24000, 25025), vf.stretch
            # "film.VF.mka" : la langue est deduite du nom, rien a saisir
            assert vf.language == "fre", vf.language

            # F9 depuis l'ecran de recalage : on greffe le sous-titre sans
            # repasser par l'ecran des pistes. La VF et ses sous-titres
            # viennent de deux fichiers, mais une seule passe suffit.
            await _add_donor(pilot, app, "film.fr.srt")
            assert type(app.screen).__name__ == "SyncScreen", type(app.screen).__name__
            assert app.screen is sync, "SyncScreen recree au lieu d'etre enrichi"
            assert len(sync._tracks) == 2, len(sync._tracks)

            # Langue deduite du nom de fichier : un .srt nu n'en declare aucune
            sub = sync._tracks[1]
            assert sub.language == "fre", f"langue non deduite : {sub.language!r}"

            # Le sous-titre se regle AU CLAVIER, comme le ferait l'utilisateur :
            # regler ces valeurs par code masquerait toute panne d'edition.
            table = sync.query_one(DataTable)
            table.move_cursor(row=1)
            await pilot.pause(0.2)
            while sync._field_idx != 0:              # revient sur Decalage
                await pilot.press("left")
                await pilot.pause(0.1)
            for _ in range(8):                       # 8 x +100 ms
                await pilot.press("plus")
            await pilot.press("shift+up")            # +1 s
            await pilot.pause(0.3)
            assert sub.delay_ms == 1800, sub.delay_ms

            # ↵ doit ouvrir une liste sur CHAQUE champ, decalage compris
            for field_idx in range(6):
                while sync._field_idx != field_idx:
                    await pilot.press("right")
                    await pilot.pause(0.1)
                await pilot.press("enter")
                await pilot.pause(0.4)
                assert type(app.screen).__name__ == "ValuePickerScreen", \
                    f"champ {field_idx} : aucune liste ouverte"
                await pilot.press("escape")
                await pilot.pause(0.3)

            # Les deux pistes gardent bien des decalages distincts
            assert vf.delay_ms == -1100 and sub.delay_ms == 1800
            print("[11] SyncScreen : 2 pistes reglees au clavier, decalages "
                  f"independants ({vf.delay_ms} ms / {sub.delay_ms} ms), "
                  "↵ ouvre une liste sur les 6 champs")

            # Un etirement ne bloque plus : mkvmerge greffera les pistes juste
            # avant l'encodage. Le bandeau l'annonce, et le dry-run passe.
            assert vf.stretch is not None
            await pilot.press("f1")
            await pilot.pause(1.2)
            assert type(app.screen).__name__ == "DryrunScreen", (
                "dry-run bloque par un etirement")
            await pilot.press("backspace")
            await pilot.pause(0.6)
            assert type(app.screen).__name__ == "SyncScreen", type(app.screen).__name__
            assert "mkvmerge" in sync._hint_override, sync._hint_override
            print("[11b] SyncScreen : etirement -> mux prealable annonce, dry-run OK")

            vf.stretch = None

            # Un decalage negatif ne doit jamais sortir en -itsoffset : ffmpeg
            # decalerait tout le fichier vers l'avant et la video ne
            # commencerait plus a zero, ce que des TV refusent de lire.
            from core.encoder import build_command as _build_cmd
            from core.decision import force_skip_to_encode as _forcer
            # Le clip de test est SKIP : on force l'encodage pour que la
            # commande existe. Les pistes greffees, elles, sont inchangees.
            _cmd = _build_cmd(_forcer(sync._decision), app.platform)
            assert "-ss" in _cmd, "decalage negatif non converti en -ss"
            _neg = [_cmd[k + 1] for k, a in enumerate(_cmd)
                    if a == "-itsoffset" and _cmd[k + 1].startswith("-")]
            assert not _neg, f"-itsoffset negatif encore present : {_neg}"
            # Le decalage positif garde -itsoffset : il ne produit aucun
            # horodatage negatif, et la video reste calee sur zero.
            assert "-itsoffset" in _cmd, "decalage positif perdu"
            print("[11d] Decalage negatif : -ss en entree, positif : -itsoffset")

            # Le bandeau doit pouvoir afficher les 3 lignes d'un compte rendu :
            # la derniere porte le renvoi vers 'a' ou 's'. La bordure compte
            # dans `height`, d'ou une hauteur de 4 pour 3 lignes utiles.
            from textual.widgets import Static as _Static
            _hint = sync.query_one("#sync-hint", _Static)
            sync._set_hint(chr(10).join(["ligne 1", "ligne 2", "ligne 3"]))
            await pilot.pause(0.3)
            assert _hint.content_size.height >= 3, (
                f"bandeau trop court : {_hint.content_size.height} lignes")
            print(f"[11e] Bandeau : {_hint.content_size.height} lignes utiles "
                  f"(3 requises pour le renvoi vers 'a'/'s')")

            # 'k' : extrait de controle reellement muxe. mpv est neutralise
            # pour que le test ne fasse pas surgir de fenetre.
            from core import preview as preview_mod
            mpv_reel = preview_mod._mpv_path
            preview_mod.set_mpv_path(None)
            try:
                await pilot.press("k")
                for _ in range(40):
                    await pilot.pause(0.5)
                    if not sync._sampling:
                        break
                assert not sync._sampling, "extrait jamais termine"
                from core.muxer import identify, sample_output_path
                extrait = sample_output_path(sync._source)
                assert extrait.exists(), f"extrait absent : {extrait}"
                pistes = identify(extrait)
                assert len(pistes) >= 3, [p.display() for p in pistes]
                taille = extrait.stat().st_size
                extrait.unlink(missing_ok=True)
                print(f"[11c] Extrait de controle : {len(pistes)} pistes, "
                      f"{taille / 1024:.0f} Ko")
            finally:
                preview_mod.set_mpv_path(mpv_reel)

            # Mux reel (F3 : F1/F2 restent dry-run et encodage partout)
            await pilot.press("f3")
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

            # Le markup Rich mangeait « _[mux] » : l'ecran annoncait film_.mkv.
            # On lit ce qui est reellement rendu, pas ce qu'on a demande.
            for wid in ("#mux-out", "#mux-state"):
                rendu = str(app.screen.query_one(wid, Static).render())
                assert "_[mux]" in rendu, f"{wid} : suffixe mange -> {rendu!r}"
            print("[12b] Ecran de mux : le suffixe _[mux] survit a l'affichage")

            # Apres le mux, c'est le fichier MUXE qui devient le fichier de
            # travail : sans ca, un encodage viserait l'original et la greffe
            # n'aurait servi a rien.
            dec = app.screen._decision
            assert dec.info.path == out, dec.info.path
            assert not dec.external_tracks, "pistes externes non videes"
            # Le conteneur suit le contenu, pas l'historique : AC3 + SubRip
            # tiennent en MP4, rien n'impose de rester en Matroska.
            assert not dec.needs_mkv, "MKV impose sans raison"

            # F1 depuis l'ecran de mux : dry-run sur le fichier produit
            await pilot.press("f1")
            await pilot.pause(1.0)
            assert type(app.screen).__name__ == "DryrunScreen", type(app.screen).__name__
            await pilot.press("backspace")
            await pilot.pause(0.6)
            assert type(app.screen).__name__ == "MuxScreen", type(app.screen).__name__

            # F2 depuis l'ecran de mux : encodage direct, sans repasser par
            # les ecrans precedents — et sur le fichier muxe, en MKV
            await pilot.press("f2")
            await pilot.pause(1.5)
            assert type(app.screen).__name__ == "RunScreen", type(app.screen).__name__
            run_dec = app.screen._statuses[0].decision
            assert run_dec.info.path == out, run_dec.info.path
            assert run_dec.output_path.suffix == ".mp4", run_dec.output_path.name
            assert run_dec.video.action != VideoAction.SKIP, "SKIP non force en encodage"
            print(f"[13] Depuis l'ecran de mux : F1 dry-run OK, F2 encode "
                  f"{run_dec.info.path.name} -> {run_dec.output_path.name}")


def _make_measurable_set(td: Path) -> bool:
    """Video a parole intermittente + SRT cale sur cette parole, mais decale."""
    import wave
    import numpy as np
    from core import config as cfg_mod
    from core.preflight import get_tool_path
    ffmpeg = get_tool_path("ffmpeg", cfg_mod.get_bin_dir(cfg_mod.load()))
    if not ffmpeg:
        return False

    sr, dur = 16_000, 240.0
    rng = np.random.default_rng(7)
    ivs, t = [], 3.0
    while t < dur - 5:
        d = rng.uniform(1.0, 3.5)
        ivs.append((t, t + d))
        t += d + rng.uniform(0.5, 4.0)

    sig = rng.normal(0, 0.02, int(dur * sr)).astype(np.float32)
    for a, b in ivs:
        i, j = int(a * sr), int(b * sr)
        x = np.arange(j - i) / sr
        voice = (np.sin(2*np.pi*180*x)*0.5 + np.sin(2*np.pi*700*x)*0.3
                 + np.sin(2*np.pi*2500*x)*0.2)
        sig[i:j] += (voice * np.abs(np.sin(2*np.pi*4*x)) * 0.5).astype(np.float32)

    wav = td / "voix.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(sig, -1, 1) * 32767).astype("<i2").tobytes())

    subprocess.run(
        [str(ffmpeg), "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", f"testsrc=duration={dur}:size=160x120:rate=5",
         "-i", str(wav), "-c:v", "libx264", "-preset", "ultrafast",
         "-c:a", "ac3", "-shortest", str(td / "film.mkv")],
        check=True, capture_output=True,
    )

    def ts(x):
        h, r = divmod(max(0.0, x), 3600); m, s = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}"
    lignes = []
    for k, (a, b) in enumerate(ivs, 1):
        lignes += [str(k),
                   f"{ts(a + _MEASURE_OFFSET)} --> {ts(b + _MEASURE_OFFSET)}",
                   f"Replique {k}", ""]
    (td / "film.fr.srt").write_text("\n".join(lignes), encoding="utf-8")

    # Meme sous-titre, mais embarque dans un conteneur : read_cues() ne
    # sait pas le lire tel quel, il doit d'abord en etre extrait.
    subprocess.run(
        [str(ffmpeg), "-y", "-loglevel", "error",
         "-i", str(td / "film.fr.srt"), "-c:s", "srt",
         str(td / "sous_titres.mkv")],
        check=True, capture_output=True,
    )
    return True


async def scenario_measure() -> None:
    """Mesure automatique du decalage d'un sous-titre (touche m)."""
    with tempfile.TemporaryDirectory() as td_str:
        td = Path(td_str)
        if not _make_measurable_set(td):
            print("[14] SKIP : ffmpeg introuvable")
            return

        app = IrisEncodeApp(start_path=td)
        if not app.mkvmerge_available:
            print("[14] SKIP : mkvmerge introuvable")
            return

        async with app.run_test(size=(160, 45)) as pilot:
            await pilot.pause(0.5)
            from tui.screens.browser import BrowserScreen
            app.push_screen(BrowserScreen(td, start_virtual=False))
            await pilot.pause(5.0)
            app.wizard_mode = False
            await pilot.press("t")
            await pilot.pause(0.8)
            await _add_donor(pilot, app, "film.fr.srt")
            assert type(app.screen).__name__ == "SyncScreen", type(app.screen).__name__

            sync_scr = app.screen
            piste = sync_scr._tracks[0]
            assert piste.delay_ms == 0

            # 'm' : la mesure tourne dans un thread, on lui laisse le temps
            await pilot.press("m")
            for _ in range(40):
                await pilot.pause(0.5)
                if not sync_scr._measuring:
                    break
            assert not sync_scr._measuring, "mesure jamais terminee"

            from core.muxer import SyncOrigin
            attendu = -int(round(_MEASURE_OFFSET * 1000))
            assert piste.sync_origin == SyncOrigin.MEASURED, piste.sync_origin
            ecart = abs(piste.delay_ms - attendu)
            assert ecart <= 50, f"mesure {piste.delay_ms} ms, attendu {attendu} ms"
            print(f"[14] Mesure auto : SRT decale de {_MEASURE_OFFSET * 1000:.0f} ms "
                  f"-> correction {piste.delay_ms} ms (ecart {ecart} ms)")

            # Meme mesure, mais sur une piste embarquee dans un conteneur
            await _add_donor(pilot, app, "sous_titres.mkv")
            assert len(sync_scr._tracks) == 2, len(sync_scr._tracks)
            embarque = sync_scr._tracks[1]
            sync_scr.query_one(DataTable).move_cursor(row=1)
            await pilot.pause(0.3)
            await pilot.press("m")
            for _ in range(40):
                await pilot.pause(0.5)
                if not sync_scr._measuring:
                    break
            assert not sync_scr._measuring, "mesure embarquee jamais terminee"
            assert embarque.sync_origin == SyncOrigin.MEASURED, (
                f"piste embarquee non mesuree : {embarque.sync_origin}")
            ecart2 = abs(embarque.delay_ms - attendu)
            assert ecart2 <= 50, f"mesure {embarque.delay_ms} ms, attendu {attendu} ms"
            print(f"[14b] Sous-titre embarque : extrait du conteneur puis mesure "
                  f"-> {embarque.delay_ms} ms (ecart {ecart2} ms)")

            # 'p' sans plage connue : refus explicite, pas de crash ni de piste
            # silencieusement modifiee.
            avant = (embarque.source_path, embarque.delay_ms)
            await pilot.press("p")
            await pilot.pause(0.3)
            assert (embarque.source_path, embarque.delay_ms) == avant, (
                "'p' a modifie la piste sans plages connues")
            print("[14c] 'p' sans plages : refus explicite, piste intacte")


async def scenario_wizard() -> None:
    """L'assistant : mode d'entree, cinq etapes, bascule par W."""
    with tempfile.TemporaryDirectory() as td_str:
        td = Path(td_str)
        if not _make_test_videos(td, 1):
            print("[15] SKIP : ffmpeg introuvable, assistant non teste")
            return

        app = IrisEncodeApp(start_path=td)
        async with app.run_test(size=(160, 45)) as pilot:
            await pilot.pause(0.5)
            from tui.screens.browser import BrowserScreen
            app.push_screen(BrowserScreen(td, start_virtual=False))
            await pilot.pause(3.0)

            assert app.wizard_mode is True, "l'assistant est le mode d'entree"
            barre = str(app.screen.query_one("#profile-bar", Static).render())
            assert "Assistant" in barre, f"mode absent de la barre -> {barre[:80]!r}"
            from tui.widgets.footer import KeyFooter
            pied = app.screen.query_one(KeyFooter)
            assert "Assistant" in str(pied.query_one("#footer-body", Static).render()),                 "le footer doit nommer le mode"
            assert pied.has_class("assistant"), "le footer doit changer de couleur"
            # Le jaune des touches se noie dans l'accent : elles passent au
            # blanc, sinon le footer devient illisible la ou il compte le plus.
            styles = _styles_du_footer(pied)
            assert "white" in styles and "yellow" not in styles, styles
            print("[15] Mode assistant : nomme dans la barre, dans le footer, "
                  "et signale par la couleur")

            # ↵ sur un fichier ouvre l'assistant
            await pilot.press("enter")
            await pilot.pause(0.8)
            wiz = app.screen
            assert type(wiz).__name__ == "WizardScreen", type(wiz).__name__
            assert len(wiz._lignes) == 0, "l'etape 1 n'affiche pas de table"
            corps = str(wiz.query_one("#wiz-corps", Static).render())
            assert "clip0.mkv" in corps, corps[:120]
            assert app.active_profile_id in corps, "le profil doit etre nomme"
            print("[15b] Etape 1 : le fichier et le profil sont nommes")

            # Etape 2 : codec, debit et pistes sur un seul ecran
            await pilot.press("enter")
            await pilot.pause(0.5)
            assert wiz._etape.name == "DECISION", wiz._etape
            corps = str(wiz.query_one("#wiz-corps", Static).render())
            assert wiz._dec.output_path.name in corps, "la sortie doit etre nommee"
            print("[15c] Etape 2 : la sortie est annoncee")

            # Etape 3 puis 4 : les deux lancements restent offerts
            await pilot.press("enter"); await pilot.pause(0.4)
            assert wiz._etape.name == "PISTES", wiz._etape
            await pilot.press("enter"); await pilot.pause(0.4)
            assert wiz._etape.name == "LANCER", wiz._etape
            aide = str(wiz.query_one("#wiz-hint", Static).render())
            assert "Muxer" in aide and "Encoder" in aide, aide
            print("[15d] Etape 4 : mux et encodage tous deux offerts")

            # Le fichier traite est rappele sur chaque etape, pas seulement
            # la premiere : quatre ecrans plus loin, on sait encore sur quoi
            # on travaille.
            for etape in range(5):
                wiz._i = etape
                wiz._afficher()
                await pilot.pause(0.2)
                bandeau = str(wiz.query_one("#wiz-titre", Static).render())
                assert "clip0" in bandeau, f"etape {etape + 1} -> {bandeau!r}"
            wiz._i = 3
            wiz._afficher()
            await pilot.pause(0.2)
            print("[15d2] Le fichier traite est rappele sur les cinq etapes")

            # M sans piste externe : refus explicite, on ne lance rien
            await pilot.press("m")
            await pilot.pause(0.5)
            assert type(app.screen).__name__ == "WizardScreen", type(app.screen).__name__
            assert "Rien a muxer" in str(
                wiz.query_one("#wiz-hint", Static).render()).replace("à", "a")
            print("[15e] M sans piste externe : refus explicite")

            # ⌫ remonte les etapes, puis rend la main a l'accueil
            for _ in range(4):
                await pilot.press("backspace")
                await pilot.pause(0.3)
            assert type(app.screen).__name__ == "BrowserScreen", type(app.screen).__name__
            print("[15f] Backspace remonte les etapes jusqu'a l'accueil")

            # W bascule, et ↵ ouvre alors l'ecran des pistes
            # `T` garde son sens quel que soit le mode : l'ecran des pistes.
            await pilot.press("t")
            await pilot.pause(0.8)
            assert type(app.screen).__name__ == "TracksScreen", type(app.screen).__name__
            await pilot.press("backspace")
            await pilot.pause(0.5)
            print("[15f2] En mode assistant, T ouvre quand meme les pistes")

            await pilot.press("w")
            await pilot.pause(0.4)
            assert app.wizard_mode is False
            barre = str(app.screen.query_one("#profile-bar", Static).render())
            assert "Manuel" in barre, barre[:80]
            pied = app.screen.query_one(KeyFooter)
            assert "Manuel" in str(pied.query_one("#footer-body", Static).render())
            assert not pied.has_class("assistant"),                 "le manuel garde le code couleur par defaut"
            styles = _styles_du_footer(pied)
            assert "yellow" in styles, styles
            await pilot.press("enter")
            await pilot.pause(0.8)
            assert type(app.screen).__name__ == "TracksScreen", type(app.screen).__name__
            print("[15g] W bascule en manuel : ↵ ouvre les pistes")


async def scenario_accueil() -> None:
    """Ctrl+Home revient a l'accueil, et demande avant de jeter du travail.

    `Home` appartient a la navigation dans les tables (TableNavMixin) : le
    retour a l'accueil prend Ctrl+Home. Deux ecrans portent un travail que le
    depilage ne rend a personne — les pistes et le recalage : ceux-la
    confirment.
    """
    with tempfile.TemporaryDirectory() as td_str:
        td = Path(td_str)
        if not _make_test_videos(td, 2):
            print("[17] SKIP : ffmpeg introuvable")
            return

        app = IrisEncodeApp(start_path=td)
        async with app.run_test(size=(160, 45)) as pilot:
            await pilot.pause(0.5)
            from tui.screens.browser import BrowserScreen
            app.push_screen(BrowserScreen(td, start_virtual=False))
            await pilot.pause(3.0)
            app.wizard_mode = False

            # Depuis le dry-run : rien a rendre, retour direct.
            await pilot.press("a")          # F1 n'agit que sur une selection
            await pilot.pause(0.3)
            await pilot.press("f1")
            await pilot.pause(1.0)
            assert type(app.screen).__name__ == "DryrunScreen", type(app.screen).__name__
            await pilot.press("ctrl+home")
            await pilot.pause(0.6)
            assert type(app.screen).__name__ == "BrowserScreen", type(app.screen).__name__
            print("[17] Ctrl+Home depuis le dry-run : retour direct a l'accueil")

            # Depuis les pistes : confirmation, et « Rester » ne bouge pas.
            await pilot.press("t")
            await pilot.pause(0.8)
            assert type(app.screen).__name__ == "TracksScreen", type(app.screen).__name__
            await pilot.press("ctrl+home")
            await pilot.pause(0.6)
            assert type(app.screen).__name__ == "ConfirmModal", type(app.screen).__name__
            await pilot.press("escape")
            await pilot.pause(0.6)
            assert type(app.screen).__name__ == "TracksScreen", type(app.screen).__name__
            print("[17b] Depuis les pistes : confirmation demandee, refus respecte")

            # Et cette fois on confirme.
            await pilot.press("ctrl+home")
            await pilot.pause(0.6)
            assert type(app.screen).__name__ == "ConfirmModal"
            await pilot.press("left")
            await pilot.pause(0.2)
            await pilot.press("enter")
            await pilot.pause(0.8)
            assert type(app.screen).__name__ == "BrowserScreen", type(app.screen).__name__
            print("[17c] Confirmation acceptee : retour a l'accueil")

            # Depuis l'accueil, la touche ne doit rien casser.
            await pilot.press("ctrl+home")
            await pilot.pause(0.4)
            assert type(app.screen).__name__ == "BrowserScreen"
            assert app.is_running
            print("[17d] Ctrl+Home depuis l'accueil : sans effet")


async def main() -> None:
    await scenario_navigation()
    await scenario_parallel_scan()
    await scenario_external_tracks()
    await scenario_measure()
    await scenario_wizard()
    await scenario_accueil()
    print("SMOKE OK")


if __name__ == "__main__":
    asyncio.run(main())
