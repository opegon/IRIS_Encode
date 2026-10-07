"""
tests/test_annexes.py — Le .nfo et les images Jellyfin partent avec la vidéo.

Les deux dispositions viennent de la bibliothèque de l'utilisateur
(2026-10-07) : des films côte à côte dans un dossier commun, et les épisodes
d'une saison avec leur `season.nfo`. Le danger à garder en vue : un motif trop
large emporterait la sortie (`<nom>.hevc-iris.mkv`), un sous-titre, ou les
fichiers d'une autre vidéo au nom voisin.
"""
from __future__ import annotations

from pathlib import Path

from core.annexes import annexes_jellyfin, supprimer_annexes


def _dossier(tmp_path: Path, noms: list[str]) -> Path:
    for n in noms:
        (tmp_path / n).write_bytes(b"x")
    return tmp_path


def _noms(chemins: list[Path]) -> list[str]:
    return [p.name for p in chemins]


def test_films_cote_a_cote(tmp_path):
    """Thunderbirds : chaque film a son .nfo et ses images, nommés sur lui."""
    a = "Thunderbirds.2004.MULTi.720p.WEB.H264-PiCKLES"
    b = "Thunderbirds.Et.Lady.Penelope.1968.VFF.1080p"
    d = _dossier(tmp_path, [
        f"{a}.mkv", f"{a}.nfo", f"{a}-backdrop.jpg", f"{a}-landscape.jpg",
        f"{a}-logo.png", f"{a}-poster.jpg",
        f"{b}.mkv", f"{b}.nfo", f"{b}-poster.jpg",
    ])
    assert _noms(annexes_jellyfin(d / f"{a}.mkv")) == [
        f"{a}-backdrop.jpg", f"{a}-landscape.jpg", f"{a}-logo.png",
        f"{a}-poster.jpg", f"{a}.nfo"]


def test_episodes_d_une_saison(tmp_path):
    """Un Village Français : le season.nfo est à la saison, il reste."""
    e1 = "Un Village Français S01E01 Le débarquement"
    e2 = "Un Village Français S01E02 Chaos"
    d = _dossier(tmp_path, [
        "season.nfo", "txt",
        f"{e1}.mkv", f"{e1}.nfo", f"{e1}-thumb.jpg",
        f"{e2}.mkv", f"{e2}.nfo", f"{e2}-thumb.jpg",
    ])
    assert _noms(annexes_jellyfin(d / f"{e1}.mkv")) == [
        f"{e1}-thumb.jpg", f"{e1}.nfo"]


def test_la_sortie_ses_annexes_et_les_sous_titres_restent(tmp_path):
    """Ni la sortie, ni ce que Jellyfin a déjà fait pour elle, ni un .srt —
    choix de l'utilisateur : un sous-titre peut être le seul exemplaire."""
    d = _dossier(tmp_path, [
        "Film.mkv", "Film.nfo", "Film-poster.jpg",
        "Film.hevc-iris.mkv", "Film.hevc-iris.nfo", "Film.hevc-iris-poster.jpg",
        "Film.fr.srt", "Film.en.forced.srt", "poster.jpg", "movie.nfo",
    ])
    assert _noms(annexes_jellyfin(d / "Film.mkv")) == [
        "Film-poster.jpg", "Film.nfo"]


def test_une_video_au_nom_plus_long_garde_ses_fichiers(tmp_path):
    """`Film-extended-poster.jpg` répond à `Film-*`, mais il est à
    `Film-extended.mkv`."""
    d = _dossier(tmp_path, [
        "Film.mkv", "Film-poster.jpg",
        "Film-extended.mkv", "Film-extended-poster.jpg", "Film-extended.nfo",
    ])
    assert _noms(annexes_jellyfin(d / "Film.mkv")) == ["Film-poster.jpg"]


def test_casse_et_extensions(tmp_path):
    """Windows ignore la casse ; seules les images et le .nfo sont pris."""
    d = _dossier(tmp_path, [
        "Film.mkv", "FILM-Poster.JPG", "film.NFO", "Film-thumb.webp",
        "Film-notes.txt", "Film-sample.mkv",
    ])
    assert sorted(_noms(annexes_jellyfin(d / "Film.mkv"))) == sorted([
        "FILM-Poster.JPG", "film.NFO", "Film-thumb.webp"])


def test_supprimer_apres_la_video(tmp_path):
    """Appelé une fois la source supprimée, comme après un encodage."""
    d = _dossier(tmp_path, ["Film.mkv", "Film.nfo", "Film-thumb.jpg",
                            "Film.fr.srt"])
    (d / "Film.mkv").unlink()
    assert supprimer_annexes(d / "Film.mkv") == []
    assert _noms(sorted(d.iterdir())) == ["Film.fr.srt"]


def test_dossier_disparu(tmp_path):
    assert annexes_jellyfin(tmp_path / "absent" / "Film.mkv") == []
