"""
tests/test_nom_iris.py — Le suffixe d'une sortie : `.<caractéristique>-iris`.

v0.8.8.11. Les noms de release séparent leurs marques par des points ; le
`_[hevc]` de l'application détonnait, et ne disait pas qui avait produit le
fichier. Toute sortie finit désormais par `-iris`, précédée de ce que le
traitement a fait — le codec produit, ou le sort du Dolby Vision.

Une caractéristique que le nom annonce déjà n'est pas répétée : un
`Film.2160p.DV` dont le DV est conservé sort `Film.2160p.DV-iris`. Les caractéristiques
que le suffixe ajoute sont en minuscules (`.hevc-iris`) ; seule la marque
est en capitales.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.decision import (SUFFIX_BY_ACTION, SUFFIX_DV_COPIE, DVAction,
                           FileDecision, VideoAction, VideoDecision,
                           suffixe_sans_redite)
from core.scanner import VideoInfo


def _dec(tmp_path: Path, stem: str, action: VideoAction, *,
         dv: DVAction = DVAction.NONE, suffixe: str | None = None,
         hauteur: int = 2160) -> FileDecision:
    info = VideoInfo(path=tmp_path / f"{stem}.mkv", width=3840, height=2160,
                     bitrate=40_000_000, codec="hevc", duration=60.0,
                     frame_count=0, dv_profile=8 if dv != DVAction.NONE else None)
    return FileDecision(
        info=info, profile={},
        video=VideoDecision(action=action, reason="", target_bitrate=8_000_000,
                            target_width=hauteur * 16 // 9, target_height=hauteur,
                            dv_action=dv,
                            output_suffix=(SUFFIX_BY_ACTION[action]
                                           if suffixe is None else suffixe)))


# ─── Les exemples validés ─────────────────────────────────────────────────────

@pytest.mark.parametrize("stem, action, dv, suffixe, hauteur, attendu", [
    ("Film.2160p.x265", VideoAction.ENCODE_HEVC, DVAction.NONE, None, 2160,
     "Film.2160p.hevc-iris"),
    ("Film.2160p.x264", VideoAction.ENCODE_H264, DVAction.NONE, None, 720,
     "Film.720p.h264-iris"),
    ("Film",            VideoAction.ENCODE_AV1,  DVAction.NONE, None, 2160,
     "Film.av1-iris"),
    # DV conservé : vidéo recopiée, le `DV` du nom reste vrai et suffit.
    ("Film.2160p.DV",   VideoAction.ENCODE_HEVC, DVAction.DV, SUFFIX_DV_COPIE, 2160,
     "Film.2160p.DV-iris"),
    # Retrait du RPU : `DV` devient `HDR10`, que le suffixe ne redit pas…
    ("Film.2160p.DV",   VideoAction.STRIP_DV,    DVAction.HDR10, None, 2160,
     "Film.2160p.HDR10-iris"),
    # … et qu'il apporte quand le nom était muet.
    ("Film.2160p",      VideoAction.STRIP_DV,    DVAction.HDR10, None, 2160,
     "Film.2160p.hdr10-iris"),
])
def test_les_noms_produits(tmp_path, stem, action, dv, suffixe, hauteur, attendu):
    dec = _dec(tmp_path, stem, action, dv=dv, suffixe=suffixe, hauteur=hauteur)
    assert dec.output_path.stem == attendu


def test_un_dv_sans_marque_la_recoit(tmp_path):
    dec = _dec(tmp_path, "Film.2160p", VideoAction.ENCODE_HEVC,
               dv=DVAction.DV, suffixe=SUFFIX_DV_COPIE)
    assert dec.output_path.stem == "Film.2160p.dv-iris"


def test_un_hdr10_plus_vaut_annonce_du_hdr10(tmp_path):
    """Le retrait du RPU laisse le HDR10+ intact ; sa couche de base est du
    HDR10, et `HDR10+.HDR10` le dirait deux fois."""
    dec = _dec(tmp_path, "Film.2160p.DV.HDR10+", VideoAction.STRIP_DV,
               dv=DVAction.HDR10)
    assert dec.output_path.stem == "Film.2160p.HDR10+-iris"


# ─── Réencoder une sortie remplace sa marque ─────────────────────────────────

@pytest.mark.parametrize("stem, action, attendu", [
    ("Film.2160p.av1-iris",     VideoAction.ENCODE_HEVC, "Film.2160p.hevc-iris"),
    ("Film.2160p.hevc-iris",    VideoAction.ENCODE_AV1,  "Film.2160p.av1-iris"),
    ("Film.2160p.hevc-iris(2)", VideoAction.ENCODE_HEVC, "Film.2160p.hevc-iris"),
    # Le collage garde sa provenance, perd seulement sa marque.
    ("Film.join-iris",          VideoAction.ENCODE_HEVC, "Film.join.hevc-iris"),
    # L'ancien schéma n'est plus une marque d'IRIS, mais `[hevc]` reste une
    # marque de codec : elle part comme un `x265`.
    ("Film_[hevc]",             VideoAction.ENCODE_HEVC, "Film.hevc-iris"),
])
def test_la_marque_ne_s_empile_pas(tmp_path, stem, action, attendu):
    assert _dec(tmp_path, stem, action).output_path.stem == attendu


def test_une_greffe_porte_mux_iris(tmp_path):
    from core.muxer import ExternalTrack, TrackKind
    dec = _dec(tmp_path, "Film.1080p", VideoAction.SKIP, suffixe="", hauteur=2160)
    dec.external_tracks.append(ExternalTrack(
        source_path=tmp_path / "vf.mka", source_tid=0, kind=TrackKind.AUDIO,
        codec="ac3", language="fre"))
    assert dec.output_path.stem == "Film.1080p.mux-iris"


# ─── Le groupe de la release ──────────────────────────────────────────────────

@pytest.mark.parametrize("stem, attendu", [
    ("Film.1080p.x265-GROUPE",              "Film.1080p.x265"),
    ("Film 1080p - abcdefgh",               "Film 1080p"),
    ("Film.2160p.4KLight.HDR.x265-QTZ",     "Film.2160p.4KLight.HDR.x265"),
    ("Titre - Sous-titre (2001) 1080p - X", "Titre - Sous-titre (2001) 1080p"),
    # Un titre, pas une release : aucune marque avant le tiret.
    ("Spider-Man",                          "Spider-Man"),
    ("Titre - Sous-titre",                  "Titre - Sous-titre"),
    # Le dernier terme est une marque, ou en termine une.
    ("Film.1080p-x265",                     "Film.1080p-x265"),
    ("Film.1080p.DTS-HD",                   "Film.1080p.DTS-HD"),
    ("Film.2160p.WEB-DL",                   "Film.2160p.WEB-DL"),
    ("Film.1080p",                          "Film.1080p"),
])
def test_le_groupe_de_la_release_part(stem, attendu):
    from core.scanner import stem_sans_groupe
    assert stem_sans_groupe(stem) == attendu


def test_un_encodage_perd_le_groupe(tmp_path):
    dec = _dec(tmp_path, "Film.1080p.BluRay - GROUPE", VideoAction.ENCODE_HEVC,
               suffixe=None, hauteur=1080)
    assert dec.output_path.stem == "Film.1080p.BluRay.hevc-iris"


def test_une_greffe_et_un_collage_perdent_le_groupe(tmp_path):
    from core.joiner import join_output_path
    from core.muxer import mux_output_path
    assert mux_output_path(tmp_path / "Film.1080p.x265-GRP.mkv").stem ==         "Film.1080p.x265.mux-iris"
    parts = [tmp_path / "Film.1080p.x265-GRP.mkv"]
    assert join_output_path(parts).stem == "Film.1080p.x265.join-iris"


# ─── La règle de non-redite, isolée ───────────────────────────────────────────

@pytest.mark.parametrize("stem, suffixe, attendu", [
    ("Film",            ".hevc-iris",  ".hevc-iris"),
    ("HEVC",            ".hevc-iris",  "-iris"),     # nom fait de ses marques
    ("Film.DoVi",       ".dv-iris",    "-iris"),
    ("Film [DV]",       ".dv-iris",    "-iris"),
    ("Film.DVD",        ".dv-iris",    ".dv-iris"),  # mot entier
    ("Film.MUX",        ".mux-iris",   "-iris"),
    # Retirer `DV` ferait passer la sortie pour un collage, que le filtre montre.
    ("Film.DV.join",    ".dv-iris",    ".dv-iris"),
    ("Film",            "",            ""),          # SKIP
])
def test_suffixe_sans_redite(stem, suffixe, attendu):
    assert suffixe_sans_redite(stem, suffixe) == attendu


# ─── La casse ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("stem, produit", [
    ("Film.hevc-iris",  True),
    ("Film.mux-iris",   False),
    ("Film.MUX-iris",   False),   # greffe écrite en capitales avant la v0.8.8.14
    ("Film.JOIN-iris",  False),
    ("Hotel-Iris",      False),   # la marque, elle, garde sa casse
])
def test_la_casse_de_la_caracteristique_ne_compte_pas(stem, produit):
    from core.scanner import deja_produit
    assert deja_produit(stem) is produit
