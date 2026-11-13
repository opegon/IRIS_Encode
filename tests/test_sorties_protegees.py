"""
tests/test_sorties_protegees.py — Rien n'est écrasé, rien n'est supprimé sur
un succès supposé (IE-185).

Constats de la revue du 2026-11-13 :

- **CR-113** — le mux d'un fichier (`F3`) écrasait un `.mux-iris.mkv` déjà
  présent, et l'effaçait si l'on revenait en arrière pendant le mux ;
- **CR-127** — la passe principale supprimait la source sur un code 0 de
  ffmpeg, sans regarder la sortie.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from core import encoder, scanner
from core.profiles import Profile
from core.muxer import ExternalTrack, TrackKind

from tests.test_arret_encodage import _App, _dec, _FauxFfmpeg, faux  # noqa: F401
from tui.screens import run as run_mod


# ─── CR-113 : le mux d'un fichier ─────────────────────────────────────────────

def _dec_mux(source: Path):
    dec = _dec(source)
    dec.external_tracks = [ExternalTrack(source_path=source.parent / "VF.mka",
                                         source_tid=0, kind=TrackKind.AUDIO,
                                         codec="AC-3", language="fre")]
    return dec


class _FauxMkvmerge:
    def terminate(self): pass
    def wait(self): return 1


def test_le_mux_ne_touche_pas_un_mux_précédent(tmp_path):
    from tui.screens.mux_run import MuxScreen
    ancien = tmp_path / "Film.mux-iris.mkv"
    ancien.write_bytes(b"mux d'hier")

    ecran = MuxScreen(_dec_mux(tmp_path / "Film.mkv"))
    assert ecran._output.name == "Film.mux-iris(2).mkv"

    # `⌫` pendant le mux : seule la sortie de ce mux-ci s'efface.
    ecran._process = _FauxMkvmerge()
    ecran._interrompre()
    assert ancien.read_bytes() == b"mux d'hier"


# ─── CR-127 : la sortie se contrôle ───────────────────────────────────────────

def test_une_sortie_absente_ou_vide_n_est_pas_un_succès(tmp_path):
    sortie = tmp_path / "Film.hevc-iris.mkv"
    assert encoder.defaut_sortie(sortie, 60.0)
    sortie.write_bytes(b"")
    assert encoder.defaut_sortie(sortie, 60.0)


def test_une_sortie_écourtée_n_est_pas_un_succès(tmp_path, monkeypatch):
    sortie = tmp_path / "Film.hevc-iris.mkv"
    sortie.write_bytes(b"mkv")
    duree = {"v": "30.0"}
    monkeypatch.setattr(scanner, "_ffprobe_json",
                        lambda args, outil=None: {"format": {"duration": duree["v"]}})
    assert encoder.defaut_sortie(sortie, 3600.0)
    duree["v"] = "3601.5"                        # l'arrondi du dernier bloc
    assert encoder.defaut_sortie(sortie, 3600.0) == ""


def test_une_durée_illisible_ne_fait_pas_échouer(tmp_path, monkeypatch):
    sortie = tmp_path / "Film.hevc-iris.mkv"
    sortie.write_bytes(b"mkv")

    def _refus(args, outil=None):
        raise RuntimeError("ffprobe: illisible")
    monkeypatch.setattr(scanner, "_ffprobe_json", _refus)
    assert encoder.defaut_sortie(sortie, 3600.0) == ""


class _FfmpegMuet(_FauxFfmpeg):
    """Rend 0 sans rien écrire."""
    def start(self):
        pass


def test_un_code_0_sans_sortie_garde_la_source(faux, tmp_path, monkeypatch):
    from tui.screens.run import FileState
    monkeypatch.setattr(run_mod, "EncoderProcess", _FfmpegMuet)
    dec = _dec(tmp_path / "Film.mkv")
    dec.profile = Profile("test", {"delete_source": True})

    async def scenario():
        app = _App([dec])
        async with app.run_test() as pilot:
            await pilot.pause(0.5)
            _FauxFfmpeg.lances[0].finir()
            for _i in range(20):
                await pilot.pause(0.2)
                if app.lot.termine:
                    break
            return app.lot.statuts[0].state

    assert asyncio.run(scenario()) == FileState.ERROR
    assert dec.info.path.exists(), "la source a été supprimée sans sortie"
