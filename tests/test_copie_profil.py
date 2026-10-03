"""
tests/test_copie_profil.py — Copier un profil pour en faire un nouveau.

`C` dans l'écran Profils (`F5`) ouvre le formulaire de création avec les
réglages du profil sous le curseur et un nom libre. Le formulaire refuse
désormais un nom déjà pris : avant, l'enregistrement écrasait en silence le
profil du même nom, et une copie au nom laissé tel quel l'aurait rendu courant.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from core import config as cfg_mod
from core import profiles as prof_mod
from tui.screens.config import nom_de_copie

_FICHIER = '''[series_basic]
bitrate_1080p_kbps = 2200

[film_hdr]
bitrate_1080p_kbps = 5000
dolby_vision = "hdr10"
'''


# ─── Le nom proposé ───────────────────────────────────────────────────────────

def test_le_nom_propose_est_libre():
    assert nom_de_copie("film_hdr", {"film_hdr"}) == "film_hdr_copie"
    assert nom_de_copie("film_hdr", {"film_hdr", "film_hdr_copie"}) == "film_hdr_copie2"


def test_le_nom_propose_tient_dans_32_caracteres():
    nom = nom_de_copie("x" * 32, {"x" * 32})
    assert len(nom) == 32 and nom.endswith("_copie")


# ─── Le parcours dans l'application ───────────────────────────────────────────

@pytest.fixture
def bac(tmp_path, monkeypatch):
    """Une configuration et des profils à part, jamais ceux de l'utilisateur."""
    monkeypatch.setattr(cfg_mod,  "CONFIG_PATH",   tmp_path / "config.toml")
    monkeypatch.setattr(prof_mod, "PROFILES_PATH", tmp_path / "profiles.toml")
    (tmp_path / "profiles.toml").write_text(_FICHIER, encoding="utf-8")
    return tmp_path


def _parcours(bac: Path, nom_saisi: str | None):
    from textual.widgets import DataTable, Input, Static

    from tui.app import IrisEncodeApp
    from tui.screens.config import ConfigScreen

    async def _run():
        app = IrisEncodeApp(start_path=bac)
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.pause(0.5)
            app.push_screen(ConfigScreen())
            await pilot.pause(0.3)
            ecran = app.screen
            ecran.query_one(DataTable).move_cursor(row=1)      # film_hdr
            await pilot.press("c")
            await pilot.pause(0.3)
            champ = ecran.query_one("#field-id", Input)
            propose = champ.value
            if nom_saisi is not None:
                champ.value = nom_saisi
            champ.focus()
            await pilot.press("ctrl+s")
            await pilot.pause(0.3)
            erreur = str(ecran.query_one("#form-error", Static).render())
            return propose, erreur, dict(app.profiles)

    return asyncio.run(_run())


def test_la_copie_reprend_les_reglages_sous_un_nouveau_nom(bac):
    propose, _, profils = _parcours(bac, None)
    assert propose == "film_hdr_copie"
    copie = profils["film_hdr_copie"].data
    assert copie["bitrate_1080p_kbps"] == 5000
    assert copie["dolby_vision"] == "hdr10"
    # Écrite dans le fichier, et l'original intact à côté.
    relus = prof_mod.load_all()
    assert relus["film_hdr_copie"].data["bitrate_1080p_kbps"] == 5000
    assert relus["film_hdr"].data["bitrate_1080p_kbps"] == 5000
    assert list(relus) == ["series_basic", "film_hdr", "film_hdr_copie"]


def test_un_nom_deja_pris_est_refuse(bac):
    _, erreur, profils = _parcours(bac, "series_basic")
    assert "existe déjà" in erreur
    assert profils["series_basic"].data["bitrate_1080p_kbps"] == 2200
    assert prof_mod.load_all()["series_basic"].data["bitrate_1080p_kbps"] == 2200
