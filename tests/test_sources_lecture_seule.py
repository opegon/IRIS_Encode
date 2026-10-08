"""
tests/test_sources_lecture_seule.py — Formats MPEG et sources en lecture seule (IE-118).

Deux choses liées par le cas qui les a fait naître, l'ISO monté :

- les flux MPEG (`.ts`, `.m2ts`, `.mts`, `.mpg`, `.mpeg`, `.vob`) sont des
  sources comme les autres, et une seule liste les nomme ;
- un dossier de source où l'on ne peut pas écrire fait choisir un dossier de
  sortie, où vont la sortie **et** les intermédiaires.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import core.decision as decision_mod
from core import config as cfg_mod
from core.decision import (VideoAction, decide, dossier_inscriptible,
                           resoudre_sorties, sorties_bloquees)
from core.profiles import Profile
from core.scanner import SUPPORTED_EXTENSIONS, AudioTrack, VideoInfo

RACINE = Path(__file__).resolve().parent.parent


def _info(dossier: Path, nom: str = "film.m2ts", codec: str = "mpeg2video") -> VideoInfo:
    dossier.mkdir(parents=True, exist_ok=True)
    p = dossier / nom
    p.write_bytes(b"")
    return VideoInfo(
        path=p, width=1920, height=1080, bitrate=30_000_000, codec=codec,
        duration=3600.0, frame_count=0, dv_profile=None,
        audio_tracks=[AudioTrack(index=0, codec="ac3", channels=6,
                                 language="fre", title="", bitrate=448_000)],
    )


def _profile() -> Profile:
    return Profile(id="test", data={
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps": 12000, "keep_4k": True,
        "audio_languages": ["fre", "eng"], "audio_copy_compatible": True,
    })


# ─── Formats ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ext", [".ts", ".m2ts", ".mts", ".mpg", ".mpeg", ".vob"])
def test_les_flux_mpeg_sont_des_sources(ext):
    assert ext in SUPPORTED_EXTENSIONS


def test_le_donneur_n_a_pas_sa_propre_liste_de_videos():
    """Sa copie divergeait : `.ts` y était, `.wmv` et `.flv` non."""
    from tui.screens.donor_picker import DONOR_EXTS, _VIDEO_EXTS
    assert _VIDEO_EXTS is SUPPORTED_EXTENSIONS
    assert SUPPORTED_EXTENSIONS <= DONOR_EXTS


# ─── Dossier inscriptible ─────────────────────────────────────────────────────

def test_un_dossier_ordinaire_est_inscriptible_et_l_essai_ne_laisse_rien(tmp_path):
    assert dossier_inscriptible(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_un_dossier_absent_ne_l_est_pas(tmp_path):
    assert not dossier_inscriptible(tmp_path / "absent")


def test_l_essai_n_utilise_pas_tempfile():
    """Sous Windows, `tempfile` réessaie dix mille noms sur un refus d'accès
    dans un dossier qu'`os.access` croit inscriptible — un partage réseau."""
    import inspect
    assert "tempfile" not in inspect.getsource(dossier_inscriptible).split('"""')[-1]


# ─── Décisions bloquées ───────────────────────────────────────────────────────

@pytest.fixture
def lecture_seule(monkeypatch, tmp_path):
    """Le dossier `iso/` refuse l'écriture ; les essais sont comptés."""
    essais: list[Path] = []

    def faux(dossier: Path) -> bool:
        essais.append(dossier)
        return dossier.name != "iso"

    monkeypatch.setattr(decision_mod, "dossier_inscriptible", faux)
    return essais


def test_une_source_en_lecture_seule_est_bloquee(tmp_path, lecture_seule):
    bloquee = decide(_info(tmp_path / "iso"), _profile())
    libre   = decide(_info(tmp_path / "ok"), _profile())
    assert sorties_bloquees([bloquee, libre]) == [bloquee]


def test_chaque_dossier_n_est_essaye_qu_une_fois(tmp_path, lecture_seule):
    decs = [decide(_info(tmp_path / "iso", f"t{n}.m2ts"), _profile()) for n in range(3)]
    sorties_bloquees(decs)
    assert lecture_seule == [tmp_path / "iso"]


def test_une_decision_qui_n_ecrit_rien_n_est_pas_bloquee(tmp_path, lecture_seule):
    dec = decide(_info(tmp_path / "iso", codec="h264"), _profile())
    dec.video.action = VideoAction.SKIP
    assert sorties_bloquees([dec]) == []


def test_un_dossier_de_sortie_choisi_debloque(tmp_path, lecture_seule):
    dec = decide(_info(tmp_path / "iso"), _profile())
    dec.output_dir = tmp_path / "sortie"
    assert sorties_bloquees([dec]) == []


# ─── Où va la sortie ──────────────────────────────────────────────────────────

def test_la_sortie_va_dans_le_dossier_choisi(tmp_path):
    dec = decide(_info(tmp_path / "iso"), _profile())
    defaut = dec.output_path
    assert defaut.parent == tmp_path / "iso"
    dec.output_dir = tmp_path / "sortie"
    assert dec.output_path == tmp_path / "sortie" / defaut.name
    assert dec.dossier_sortie == tmp_path / "sortie"


def test_la_numerotation_regarde_le_dossier_choisi(tmp_path):
    (tmp_path / "sortie").mkdir()
    dec = decide(_info(tmp_path / "iso"), _profile())
    dec.output_dir = tmp_path / "sortie"
    dec.output_path.write_bytes(b"")
    nom = dec.output_path.name
    resoudre_sorties([dec])
    assert dec.output_path.parent == tmp_path / "sortie"
    assert dec.output_path.name != nom and "(2)" in dec.output_path.name


def test_les_intermediaires_suivent_le_dossier_de_sortie():
    """Garde-fou : un intermédiaire posé à côté de la source échouerait sur un
    ISO monté, après des heures d'encodage pour le RPU Dolby Vision."""
    source = (RACINE / "tui" / "screens" / "run.py").read_text(encoding="utf-8")
    assert not re.search(r"\b(source|src)\.with_name\(", source)
    assert "source.parent" not in source


# ─── Réglage ──────────────────────────────────────────────────────────────────

def test_le_reglage_prime_s_il_existe(tmp_path):
    cfg = {"app": {"output_dir": str(tmp_path)}}
    assert cfg_mod.get_output_dir(cfg) == tmp_path


def test_un_reglage_disparu_retombe_sur_un_dossier_existant(tmp_path):
    cfg = {"app": {"output_dir": str(tmp_path / "debranche")}}
    assert cfg_mod.get_output_dir(cfg).is_dir()
    assert cfg_mod.get_output_dir({}).is_dir()


# ─── La mise en file demande le dossier ───────────────────────────────────────

from tests.test_arret_encodage import faux  # noqa: E402,F401  (fixture)


def test_la_mise_en_file_demande_le_dossier_et_l_applique(tmp_path, monkeypatch, faux):
    """Bout à bout : la modale s'ouvre sur le réglage, `Entrée` sur la première
    ligne le retient, et le lot encode vers lui. `Esc` ne met rien en file."""
    import asyncio
    from tests.test_arret_encodage import _App, _dec
    from tui.screens.output_dir import OutputDirScreen

    (tmp_path / "iso").mkdir()
    sortie = tmp_path / "sortie"
    sortie.mkdir()
    monkeypatch.setattr(decision_mod, "dossier_inscriptible",
                        lambda d: d.name != "iso")
    monkeypatch.setattr("tui.screens.output_dir.dossier_inscriptible",
                        lambda d: d.name != "iso")

    async def scenario(touche: str):
        app = _App([_dec(tmp_path / "iso" / "titre.m2ts")])
        app.cfg = {"app": {"output_dir": str(sortie)}}
        async with app.run_test() as pilot:
            await pilot.pause(0.5)
            modale = isinstance(app.screen, OutputDirScreen)
            await pilot.press(touche)
            await pilot.pause(0.5)
            lot = app.lot
            return modale, (lot.statuts[0].decision.output_path if lot else None)

    modale, chemin = asyncio.run(scenario("enter"))
    assert modale
    assert chemin is not None and chemin.parent == sortie

    modale, chemin = asyncio.run(scenario("escape"))
    assert modale and chemin is None
