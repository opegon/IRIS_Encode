"""
tests/test_recalage_fichiers.py — Fichiers du recalage (IE-187).

Constats de la revue du 2026-11-13 :

- **CR-115** — deux pistes de même langue recalées écrivaient le même
  fichier : la seconde remplaçait la première ;
- **CR-116** — l'extrait `K` lisait en mémoire un donneur `.mkv` entier ;
- **CR-123** — un `.srt` UTF-16 était déclaré cp1252 : accents détruits à la
  greffe, aucune réplique lue par la mesure.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import muxer
from core import sous_titres as ST
from core.muxer import ExternalTrack, TrackKind
from core.sync import read_cues
from tests.test_greffes_encodage import (SRT_ACCENTS, _decide, _encoder,  # noqa: F401
                                         _repliques, _video_mkv, outils,
                                         vrais_outils)
from tui.screens import sync as sync_mod
from tui.screens.sync import SyncScreen


def _piste(source: Path, tid: int = 0, langue: str = "fre",
           kind=TrackKind.SUBTITLE) -> ExternalTrack:
    return ExternalTrack(source_path=source, source_tid=tid, kind=kind,
                         codec="SubRip/SRT", language=langue)


def _ecran(tmp_path: Path, pistes: list[ExternalTrack]):
    return SimpleNamespace(
        _decision=SimpleNamespace(dossier_sortie=tmp_path,
                                  info=SimpleNamespace(path=tmp_path / "Film.mkv",
                                                       duration=60.0)),
        _tracks=pistes, _source=tmp_path / "Film.mkv")


# ─── CR-115 : un fichier par piste recalée ────────────────────────────────────

def test_deux_pistes_de_même_langue_ont_chacune_leur_fichier(tmp_path):
    donneur = tmp_path / "VF.mkv"
    complet, force = _piste(donneur, 2), _piste(donneur, 3)
    ecran = _ecran(tmp_path, [complet, force])

    premier = SyncScreen._fichier_recale(ecran, complet, ".srt")
    premier.write_text("1", encoding="utf-8")
    complet.source_path, complet.source_tid = premier, 0

    second = SyncScreen._fichier_recale(ecran, force, ".srt")
    assert second != premier
    assert premier.read_text(encoding="utf-8") == "1"


def test_un_second_recalage_n_écrit_pas_dans_le_fichier_qu_il_lit(tmp_path):
    """Recaler une piste déjà recalée : sa source est le fichier recalé."""
    vf = _piste(tmp_path / "VF.mka", kind=TrackKind.AUDIO)
    ecran = _ecran(tmp_path, [vf])
    vf.source_path = SyncScreen._fichier_recale(ecran, vf, ".mka")
    assert SyncScreen._fichier_recale(ecran, vf, ".mka") != vf.source_path


def test_le_nom_numéroté_reste_un_intermédiaire(tmp_path):
    from core.scanner import est_intermediaire
    vf = _piste(tmp_path / "VF.srt")
    ecran = _ecran(tmp_path, [vf])
    (tmp_path / "Film_fre.iris_recale.srt").write_text("x", encoding="utf-8")
    out = SyncScreen._fichier_recale(ecran, vf, ".srt")
    assert out.name == "Film_fre.iris_recale2.srt" and est_intermediaire(out.stem)


# ─── CR-116 : l'extrait ne lit pas un donneur conteneur ───────────────────────

def test_l_extrait_ne_lit_pas_un_donneur_mkv(tmp_path, monkeypatch):
    def _lu(path):
        raise AssertionError(f"donneur lu en entier : {path.name}")
    monkeypatch.setattr(sync_mod, "read_cues", _lu)

    def _refus(*a, **k):
        raise ValueError("arrêt du test")
    monkeypatch.setattr(sync_mod, "build_sample_command", _refus)

    rendus = []
    ecran = _ecran(tmp_path, [_piste(tmp_path / "VF.mkv", 2)])
    ecran.app = SimpleNamespace(call_from_thread=lambda f, *a: rendus.append(a))
    ecran._sample_done = None
    SyncScreen._build_sample.__wrapped__(ecran)
    assert rendus and rendus[0][1] == "arrêt du test"


# ─── CR-123 : un .srt en UTF-16 ───────────────────────────────────────────────

@pytest.fixture(params=["utf-16-le", "utf-16-be"])
def srt_utf16(request, tmp_path) -> Path:
    bom = b"\xff\xfe" if request.param.endswith("le") else b"\xfe\xff"
    srt = tmp_path / "film.fr.srt"
    srt.write_bytes(bom + SRT_ACCENTS.encode(request.param))
    return srt


def test_un_srt_utf16_n_est_pas_déclaré_cp1252(srt_utf16):
    assert ST.encodage_texte(srt_utf16) is None


def test_la_mesure_lit_les_répliques_d_un_srt_utf16(srt_utf16):
    assert len(read_cues(srt_utf16)) == 3


@outils
def test_un_srt_utf16_greffe_à_l_encodage_garde_ses_accents(tmp_path, vrais_outils,
                                                             srt_utf16):
    dec = _decide(_video_mkv(tmp_path, "film.mkv"))
    dec.external_tracks.append(_piste(srt_utf16))
    assert dec.output_container == ".mp4"
    _encoder(dec)
    texte = _repliques(dec.output_path)
    for ligne in ("Été à Paris", "Bonjour", "Déjà vu"):
        assert ligne in texte, texte


@outils
def test_un_srt_utf16_greffe_au_mux_garde_ses_accents(tmp_path, vrais_outils,
                                                       srt_utf16):
    source = _video_mkv(tmp_path, "film.mkv")
    sortie = tmp_path / "film.mux.mkv"
    cmd = muxer.build_mux_command(source, [_piste(srt_utf16)], sortie)
    r = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
    assert muxer.mkvmerge_reussi(r.returncode, sortie), r.stdout[-500:]
    texte = _repliques(sortie)
    for ligne in ("Été à Paris", "Bonjour", "Déjà vu"):
        assert ligne in texte, texte
