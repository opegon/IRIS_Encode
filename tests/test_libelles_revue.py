"""
tests/test_libelles_revue.py — Libellés qui disent vrai, et passent par le
catalogue (IE-135 3/3, constats CR-79, CR-83, CR-97, CR-99 de
`revue_code_2026-10-08.md`).
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest

from core.decision import decide
from core.i18n import _, pgettext
from core.profiles import Profile, validate_id
from core.scanner import AudioTrack, SubtitleTrack, VideoInfo

RACINE = Path(__file__).resolve().parent.parent


def _msgids() -> set[str]:
    pot = (RACINE / "locales" / "iris_encode.pot").read_text(encoding="utf-8")
    return set(re.findall(r'^msgid "(.+)"$', pot, re.M))


# ─── CR-79 — tout en-tête de colonne est au catalogue ────────────────────────

def test_tout_entete_redimensionnable_est_un_msgid():
    from tui.screens.browser import BrowserScreen
    from tui.screens.dryrun import DryrunScreen
    from tui.screens.tracks import TracksScreen
    connus = _msgids()
    for ecran in (BrowserScreen, DryrunScreen, TracksScreen):
        for cle, libelle in ecran.RESIZE_LABELS.items():
            assert libelle in connus, f"{ecran.__name__}.{cle} : « {libelle} »"


# ─── CR-97 — pas de valeur affichée en dur ───────────────────────────────────

def test_opensubtitles_n_ecrit_plus_oui_en_dur():
    texte = (RACINE / "tui" / "screens" / "opensubtitles.py").read_text(encoding="utf-8")
    assert '"oui"' not in texte and 'add_column("Release"' not in texte


# ─── CR-99 — l'identifiant d'un profil : une règle, un message ───────────────

@pytest.mark.parametrize("pid,valide", [
    ("series_ete", True), ("Film-4K", True), ("Série_été", False),
    ("a b", False), ("x" * 32, True),
])
def test_formulaire_et_validate_id_disent_pareil(pid, valide):
    from textual.app import App
    from textual.widgets import Input
    from tui.widgets.profile_form import ProfileForm

    assert validate_id(pid) is valide

    class _App(App):
        def compose(self):
            yield ProfileForm()

    async def _scenario():
        app = _App()
        async with app.run_test(size=(140, 50)) as pilot:
            await pilot.pause(0.2)
            form = app.query_one(ProfileForm)
            form.query_one("#field-id", Input).value = pid
            return form.validate()

    erreurs = asyncio.run(_scenario())
    refus = _("Identifier: allowed characters a-z, A-Z, 0-9, - _")
    assert (refus not in erreurs) is valide, erreurs


# ─── CR-83 — la section sous-titres dit ce que fera l'encodage ───────────────

def _decision(tmp_path, sous_titres, **profil):
    p = tmp_path / "film.mkv"
    p.write_bytes(b"")
    info = VideoInfo(
        path=p, width=1920, height=1080, bitrate=3_000_000, codec="hevc",
        duration=5400.0, frame_count=0, dv_profile=None,
        audio_tracks=[AudioTrack(index=0, codec="eac3", channels=6,
                                 language="fre", title="", bitrate=640_000)],
        subtitle_tracks=sous_titres)
    data = {"bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
            "bitrate_4k_kbps": 8000, "audio_languages": ["fre", "eng"],
            "subtitle_languages": ["fre", "eng"],
            "audio_copy_compatible": True, "preserve_hd_audio": False,
            "container": "auto"}
    data.update(profil)
    return decide(info, Profile(id="test", data=data))


def _lignes_sous_titres(dec) -> dict[str, str]:
    from textual.widgets import DataTable
    from tui.app import IrisEncodeApp
    from tui.screens.tracks import TracksScreen

    async def _scenario():
        app = IrisEncodeApp(start_path=dec.info.path.parent)
        async with app.run_test(size=(180, 50)) as pilot:
            await pilot.pause(0.3)
            app.push_screen(TracksScreen(dec))
            await pilot.pause(0.4)
            table = app.screen.query_one(DataTable)
            return {str(cle.value): " | ".join(str(c) for c in table.get_row(cle))
                    for cle in table.rows if str(cle.value).startswith("s:")}
    return asyncio.run(_scenario())


def test_defaut_suit_le_drapeau_de_la_source(tmp_path):
    dec = _decision(tmp_path, [
        SubtitleTrack(index=0, codec="subrip", language="fre", forced=True),
        SubtitleTrack(index=1, codec="subrip", language="eng"),
        SubtitleTrack(index=2, codec="subrip", language="fre", default=True)])
    lignes = _lignes_sous_titres(dec)
    defaut = pgettext("track", "default")
    porteuses = [k for k, l in lignes.items() if f"| {defaut} |" in l]
    assert porteuses == ["s:2"], lignes


def test_la_cible_annonce_le_vrai_conteneur(tmp_path):
    dec = _decision(tmp_path, [
        SubtitleTrack(index=0, codec="subrip", language="fre"),
        SubtitleTrack(index=1, codec="hdmv_pgs_subtitle", language="eng")])
    assert dec.output_container == ".mkv"
    lignes = _lignes_sous_titres(dec)
    assert lignes and not any("MP4" in l for l in lignes.values()), lignes
