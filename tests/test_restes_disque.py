"""
tests/test_restes_disque.py — Ce qui reste sur le disque (IE-129).

Constats de la revue IE-114 :

- **CR-57**, **CR-90** — une sortie partielle restait après un échec ou un `S`,
  sous le nom d'une sortie réussie ;
- **CR-58** — une sortie anticipée de la passe principale laissait
  l'assemblage d'un titre (le poids du film) ;
- **CR-11** — un intermédiaire laissé par une coupure passait pour une source ;
- **CR-28**, **CR-93** — mux préalable et piste recalée dans le temp du système ;
- **CR-89** — le code 1 de mkvmerge (avertissements) traité comme un échec ;
- **CR-24** — `Film.avi` perdait ses annexes Jellyfin avec `Film.mkv`.
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest

from core import muxer
from core.annexes import annexes_jellyfin
from core.muxer import ExternalTrack, TrackKind
from core.scanner import deja_produit, est_intermediaire, intermediaire

RACINE = Path(__file__).resolve().parent.parent


# ─── Les intermédiaires se reconnaissent ──────────────────────────────────────

@pytest.mark.parametrize("stem", ["TITLE_01.iris_titre", "Film.iris_dv", "Film.iris_st",
                                  "Film.iris_st0", "Film.iris_audio", "Film.iris_premux",
                                  "Film_fre.iris_recale"])
def test_un_intermédiaire_n_est_pas_une_source(stem):
    assert est_intermediaire(stem) and deja_produit(stem)


@pytest.mark.parametrize("stem", ["Film.iris", "Iris", "Film.iris_", "Film.mux-iris"])
def test_une_source_qui_ressemble_reste_une_source(stem):
    assert not est_intermediaire(stem)


def test_le_nom_d_un_intermédiaire_se_fabrique_en_un_seul_endroit():
    assert est_intermediaire(intermediaire("Film", "titre"))


def test_le_mode_récursif_écarte_les_intermédiaires(tmp_path, monkeypatch):
    from core import scanner
    for nom in ("Film.mkv", "Film.iris_titre.mkv", "Film.iris_premux.mkv"):
        (tmp_path / nom).write_bytes(b"")
    vus = []
    monkeypatch.setattr(scanner, "scan", lambda p: vus.append(p.name) or None)
    scanner.scan_directory_recursive(tmp_path)
    assert vus == ["Film.mkv"]


def test_les_intermédiaires_de_la_file_portent_la_forme_reconnue():
    """Toute écriture d'un intermédiaire dans la file finit en `.iris_<mot>`."""
    texte = (RACINE / "tui" / "screens" / "run.py").read_text(encoding="utf-8")
    for nom in re.findall(r'\.iris_([a-z0-9{}]+)\.', texte):
        assert est_intermediaire(f"x.iris_{nom.replace('{n}', '0')}"), nom


# ─── Les gros intermédiaires vont à côté de la sortie ─────────────────────────

def test_la_piste_recalée_va_à_côté_de_la_sortie(tmp_path):
    """CR-93."""
    from tui.screens.sync import SyncScreen

    class _Faux:
        class _decision:
            dossier_sortie = tmp_path
            class info:
                path = tmp_path / "Film.mkv"

    piste = ExternalTrack(source_path=tmp_path / "VF.mkv", source_tid=1,
                          kind=TrackKind.AUDIO, codec="AC-3", language="fre")
    out = SyncScreen._fichier_recale(_Faux(), piste, ".mka")
    assert out.parent == tmp_path and est_intermediaire(out.stem)


# ─── mkvmerge : 1, ce sont des avertissements ─────────────────────────────────

def test_le_code_1_de_mkvmerge_est_un_succès(tmp_path):
    sortie = tmp_path / "x.mkv"
    assert not muxer.mkvmerge_reussi(0, sortie), "sans sortie, rien n'a réussi"
    sortie.write_bytes(b"mkv")
    assert muxer.mkvmerge_reussi(0, sortie) and muxer.mkvmerge_reussi(1, sortie)
    assert not muxer.mkvmerge_reussi(2, sortie)


@pytest.mark.parametrize("fichier", ["tui/screens/mux_run.py", "tui/screens/join.py",
                                     "tui/screens/sync.py", "tui/screens/run.py"])
def test_chaque_appel_de_mkvmerge_accepte_ses_avertissements(fichier):
    """CR-89 : une seule règle, partout où mkvmerge écrit."""
    texte = (RACINE / fichier).read_text(encoding="utf-8")
    assert "mkvmerge_reussi(" in texte
    if not fichier.endswith("run.py"):            # run.py : `rc == 0` est ffmpeg
        assert not re.search(r"(rc|code) == 0", texte), "code 1 encore pris pour un échec"


def test_un_mux_raté_efface_sa_sortie():
    """CR-90."""
    texte = (RACINE / "tui" / "screens" / "mux_run.py").read_text(encoding="utf-8")
    assert "self._output.unlink(missing_ok=True)" in texte


# ─── Annexes partagées ────────────────────────────────────────────────────────

@pytest.mark.parametrize("voisine", ["Film.avi", "Film.iso", "film.MP4"])
def test_une_vidéo_de_même_nom_garde_les_annexes(tmp_path, voisine):
    """CR-24."""
    for nom in ("Film.mkv", voisine, "Film.nfo", "Film-poster.jpg"):
        (tmp_path / nom).write_bytes(b"")
    assert annexes_jellyfin(tmp_path / "Film.mkv") == []


def test_seule_elle_garde_ses_annexes(tmp_path):
    for nom in ("Film.mkv", "Film.nfo"):
        (tmp_path / nom).write_bytes(b"")
    assert [p.name for p in annexes_jellyfin(tmp_path / "Film.mkv")] == ["Film.nfo"]


# ─── La file : nettoyage sur toutes les sorties ───────────────────────────────

from tests.test_arret_encodage import _App, _dec, _FauxFfmpeg, faux  # noqa: E402,F401


def test_liberer_efface_tout_et_rend_les_greffes(tmp_path):
    """CR-58 : un seul nettoyage, appelé sur chaque sortie."""
    from tui.screens.run import RunScreen
    dec = _dec(tmp_path / "Film.mkv")
    assemblage = tmp_path / "Film.iris_premux.mkv"
    audio = tmp_path / "Film.iris_audio.mka"
    for f in (assemblage, audio):
        f.write_bytes(b"x")
    piste = ExternalTrack(source_path=tmp_path / "VF.mka", source_tid=0,
                          kind=TrackKind.AUDIO, codec="AC-3", language="fre")
    dec.encode_source, dec.premuxed_tracks, dec.external_tracks = assemblage, [piste], []
    RunScreen._liberer(None, dec, audio, None)
    assert not assemblage.exists() and not audio.exists()
    assert dec.encode_source is None and dec.external_tracks == [piste]


def test_l_assemblage_d_un_titre_ne_vide_pas_les_greffes(tmp_path):
    from tui.screens.run import RunScreen
    dec = _dec(tmp_path / "Film.mkv")
    piste = ExternalTrack(source_path=tmp_path / "VF.mka", source_tid=0,
                          kind=TrackKind.AUDIO, codec="AC-3", language="fre")
    dec.encode_source, dec.external_tracks = tmp_path / "x.iris_titre.mkv", [piste]
    RunScreen._liberer(None, dec)
    assert dec.external_tracks == [piste]


def test_chaque_sortie_anticipée_libère():
    """CR-58 : entre le mux préalable et le lancement de ffmpeg, chaque
    `self._encode_next()` est précédé d'un `self._liberer(`."""
    texte = (RACINE / "tui" / "screens" / "run.py").read_text(encoding="utf-8")
    debut = texte.index("if needs_premux(dec.external_tracks)")
    fin = texte.index("proc = EncoderProcess(cmd, dec.info.duration)", debut)
    lignes = [l.strip() for l in texte[debut:fin].splitlines() if l.strip()]
    for i, l in enumerate(lignes):
        if l.startswith("self._encode_next()"):
            assert lignes[i - 1].startswith("self._liberer("), lignes[i - 1]


async def _encoder(tmp_path, geste):
    app = _App([_dec(tmp_path / "Film.mkv")])
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        lot = app.lot
        sortie = lot.statuts[0].decision.output_path
        assert sortie.exists(), "le faux ffmpeg a commencé d'écrire"
        geste(lot)
        for _i in range(20):
            await pilot.pause(0.2)
            if lot.termine:
                break
        return lot.statuts[0].state, sortie.exists()


def test_un_échec_de_ffmpeg_efface_la_sortie_partielle(faux, tmp_path):
    """CR-57."""
    from tui.screens.run import FileState
    etat, existe = asyncio.run(_encoder(tmp_path, lambda lot: _FauxFfmpeg.lances[0].terminate()))
    assert etat == FileState.ERROR and not existe


def test_passer_un_fichier_efface_sa_sortie_partielle(faux, tmp_path):
    """CR-57 : `S`."""
    from tui.screens.run import FileState
    etat, existe = asyncio.run(_encoder(tmp_path, lambda lot: lot._passer_courant()))
    assert etat == FileState.SKIPPED and not existe


def test_une_réussite_garde_sa_sortie_et_efface_la_piste_recalée(faux, tmp_path):
    """CR-93 : la piste recalée a été recopiée, elle part."""
    from tui.screens.run import FileState
    recalee = tmp_path / "Film_fre.iris_recale.mka"
    recalee.write_bytes(b"x")
    dec = _dec(tmp_path / "Film.mkv")
    dec.external_tracks = [ExternalTrack(source_path=recalee, source_tid=0,
                                         kind=TrackKind.AUDIO, codec="AC-3",
                                         language="fre")]

    async def scenario():
        app = _App([dec])
        async with app.run_test() as pilot:
            await pilot.pause(0.5)
            _FauxFfmpeg.lances[0].finir()
            for _i in range(20):
                await pilot.pause(0.2)
                if app.lot.termine:
                    break
            s = app.lot.statuts[0]
            return s.state, s.decision.output_path.exists()

    etat, existe = asyncio.run(scenario())
    assert etat == FileState.SUCCESS and existe
    assert not recalee.exists()
