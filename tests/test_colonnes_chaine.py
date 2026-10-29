"""
tests/test_colonnes_chaine.py — colonnes « Lect. », « Filt. » et « Enc. » de
l'écran d'encodage : où la vidéo est décodée, filtrée, puis encodée, GPU ou CPU.

Prévues à la mise en file d'après la commande qu'on construirait ; remplacées
par celles de la commande réellement lancée.
"""
from __future__ import annotations

import asyncio

import pytest

from core.encoder import chaine_de
from tests.test_arret_encodage import _App, _dec, faux  # noqa: F401 (fixture)
from tests.test_nvdec import _nvidia
from tests.test_qsv import _commande
from tui.screens import run as run_mod


def test_tout_sur_la_carte(tmp_path):
    assert chaine_de(_commande(tmp_path, plat=_nvidia())) == ("gpu", "gpu", "gpu")


def test_reprise_hors_puce_filtre_au_processeur(tmp_path):
    from tests.test_reprise_hors_puce import _commande as _colle
    source = tmp_path / "colle.mp4"
    source.write_bytes(b"")
    assert chaine_de(_colle(source)) == ("gpu", "gpu", "gpu")
    reprise = _colle(source, tout_puce_permis=False)
    assert chaine_de(reprise) == ("gpu", "cpu", "gpu")


def test_quick_sync_sans_hwaccel(tmp_path):
    cmd = ["ffmpeg", "-i", "a.mkv", "-c:v", "hevc_qsv", "b.mkv"]
    assert chaine_de(cmd) == ("cpu", "cpu", "gpu")


def test_tout_au_processeur():
    cmd = ["ffmpeg", "-i", "a.mkv", "-c:v", "libx265", "b.mkv"]
    assert chaine_de(cmd) == ("cpu", "cpu", "cpu")


def test_un_hwaccel_apres_l_entree_ne_compte_pas():
    cmd = ["ffmpeg", "-i", "a.mkv", "-hwaccel", "cuda", "-c:v", "libx265", "b.mkv"]
    assert chaine_de(cmd)[0] == "cpu"


@pytest.mark.parametrize("cmd", [
    [],
    ["ffmpeg", "-i", "a.mkv", "-c:v", "copy", "b.mp4"],
])
def test_video_ni_decodee_ni_encodee(cmd):
    assert chaine_de(cmd) == (None, None, None)


def test_colonnes_entre_action_et_etat(tmp_path, faux, monkeypatch):
    asyncio.run(_colonnes(tmp_path, faux, monkeypatch))


async def _colonnes(tmp_path, faux, monkeypatch):
    from textual.widgets import DataTable
    # Une reprise hors puce : décodage et encodage sur la carte, filtres non.
    lance = ["ffmpeg", "-hwaccel", "cuda", "-i", "x", "-c:v", "hevc_nvenc"]
    monkeypatch.setattr(run_mod, "build_command",
                        lambda d, p, **k: [*lance, str(d.output_path)])
    app = _App([_dec(tmp_path / "a.mkv"), _dec(tmp_path / "b.mkv")])
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        table = app.screen.query_one(DataTable)
        cles = [c.value for c in table.columns]
        assert cles[cles.index("action"):] == ["action", "read", "filt", "enc",
                                               "state"]
        # En cours : la commande lancée. En attente : la prévision (libx265).
        trois = ("read", "filt", "enc")
        assert [str(table.get_cell("0", k)) for k in trois] == ["GPU", "CPU", "GPU"]
        assert [str(table.get_cell("1", k)) for k in trois] == ["CPU", "CPU", "CPU"]
        for p in faux:
            p.terminate()
