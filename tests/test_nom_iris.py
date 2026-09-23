"""
tests/test_nom_iris.py — Le suffixe d'une sortie : `.<caractéristique>.IRIS`.

v0.8.8.11. Les noms de release séparent leurs marques par des points ; le
`_[hevc]` de l'application détonnait, et ne disait pas qui avait produit le
fichier. Toute sortie finit désormais par `.IRIS`, précédée de ce que le
traitement a fait — le codec produit, ou le sort du Dolby Vision.

Une caractéristique que le nom annonce déjà n'est pas répétée : un
`Film.2160p.DV` dont le DV est conservé sort `Film.2160p.DV.IRIS`. Les caractéristiques
que le suffixe ajoute sont en minuscules (`.hevc.IRIS`) ; seule la marque
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
     "Film.2160p.hevc.IRIS"),
    ("Film.2160p.x264", VideoAction.ENCODE_H264, DVAction.NONE, None, 720,
     "Film.720p.h264.IRIS"),
    ("Film",            VideoAction.ENCODE_AV1,  DVAction.NONE, None, 2160,
     "Film.av1.IRIS"),
    # DV conservé : vidéo recopiée, le `DV` du nom reste vrai et suffit.
    ("Film.2160p.DV",   VideoAction.ENCODE_HEVC, DVAction.DV, SUFFIX_DV_COPIE, 2160,
     "Film.2160p.DV.IRIS"),
    # Retrait du RPU : `DV` devient `HDR10`, que le suffixe ne redit pas…
    ("Film.2160p.DV",   VideoAction.STRIP_DV,    DVAction.HDR10, None, 2160,
     "Film.2160p.HDR10.IRIS"),
    # … et qu'il apporte quand le nom était muet.
    ("Film.2160p",      VideoAction.STRIP_DV,    DVAction.HDR10, None, 2160,
     "Film.2160p.hdr10.IRIS"),
])
def test_les_noms_produits(tmp_path, stem, action, dv, suffixe, hauteur, attendu):
    dec = _dec(tmp_path, stem, action, dv=dv, suffixe=suffixe, hauteur=hauteur)
    assert dec.output_path.stem == attendu


def test_un_dv_sans_marque_la_recoit(tmp_path):
    dec = _dec(tmp_path, "Film.2160p", VideoAction.ENCODE_HEVC,
               dv=DVAction.DV, suffixe=SUFFIX_DV_COPIE)
    assert dec.output_path.stem == "Film.2160p.dv.IRIS"


def test_un_hdr10_plus_vaut_annonce_du_hdr10(tmp_path):
    """Le retrait du RPU laisse le HDR10+ intact ; sa couche de base est du
    HDR10, et `HDR10+.HDR10` le dirait deux fois."""
    dec = _dec(tmp_path, "Film.2160p.DV.HDR10+", VideoAction.STRIP_DV,
               dv=DVAction.HDR10)
    assert dec.output_path.stem == "Film.2160p.HDR10+.IRIS"


# ─── Réencoder une sortie remplace sa marque ─────────────────────────────────

@pytest.mark.parametrize("stem, action, attendu", [
    ("Film.2160p.av1.IRIS",     VideoAction.ENCODE_HEVC, "Film.2160p.hevc.IRIS"),
    ("Film.2160p.hevc.IRIS",    VideoAction.ENCODE_AV1,  "Film.2160p.av1.IRIS"),
    ("Film.2160p.hevc.IRIS(2)", VideoAction.ENCODE_HEVC, "Film.2160p.hevc.IRIS"),
    # Le collage garde sa provenance, perd seulement sa marque.
    ("Film.join.IRIS",          VideoAction.ENCODE_HEVC, "Film.join.hevc.IRIS"),
    # L'ancien schéma n'est plus une marque d'IRIS, mais `[hevc]` reste une
    # marque de codec : elle part comme un `x265`.
    ("Film_[hevc]",             VideoAction.ENCODE_HEVC, "Film.hevc.IRIS"),
])
def test_la_marque_ne_s_empile_pas(tmp_path, stem, action, attendu):
    assert _dec(tmp_path, stem, action).output_path.stem == attendu


def test_une_greffe_porte_mux_iris(tmp_path):
    from core.muxer import ExternalTrack, TrackKind
    dec = _dec(tmp_path, "Film.1080p", VideoAction.SKIP, suffixe="", hauteur=2160)
    dec.external_tracks.append(ExternalTrack(
        source_path=tmp_path / "vf.mka", source_tid=0, kind=TrackKind.AUDIO,
        codec="ac3", language="fre"))
    assert dec.output_path.stem == "Film.1080p.mux.IRIS"


# ─── La règle de non-redite, isolée ───────────────────────────────────────────

@pytest.mark.parametrize("stem, suffixe, attendu", [
    ("Film",            ".hevc.IRIS",  ".hevc.IRIS"),
    ("HEVC",            ".hevc.IRIS",  ".IRIS"),     # nom fait de ses marques
    ("Film.DoVi",       ".dv.IRIS",    ".IRIS"),
    ("Film [DV]",       ".dv.IRIS",    ".IRIS"),
    ("Film.DVD",        ".dv.IRIS",    ".dv.IRIS"),  # mot entier
    ("Film.MUX",        ".mux.IRIS",   ".IRIS"),
    # Retirer `DV` ferait passer la sortie pour un collage, que le filtre montre.
    ("Film.DV.join",    ".dv.IRIS",    ".dv.IRIS"),
    ("Film",            "",            ""),          # SKIP
])
def test_suffixe_sans_redite(stem, suffixe, attendu):
    assert suffixe_sans_redite(stem, suffixe) == attendu


# ─── La casse ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("stem, produit", [
    ("Film.hevc.IRIS",  True),
    ("Film.mux.IRIS",   False),
    ("Film.MUX.IRIS",   False),   # greffe écrite en capitales avant la v0.8.8.14
    ("Film.JOIN.IRIS",  False),
    ("Hotel.Iris",      False),   # la marque, elle, garde sa casse
])
def test_la_casse_de_la_caracteristique_ne_compte_pas(stem, produit):
    from core.scanner import deja_produit
    assert deja_produit(stem) is produit
