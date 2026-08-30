"""
tests/test_dv_copie.py — Ce qui est annoncé est ce qui est fait.

Conserver le Dolby Vision impose `-c:v copy` : le RPU vit *à l'intérieur* du
flux HEVC, entre les tranches d'image, et tout réencodage le détruit. Le débit
cible et la résolution limite du profil restent donc lettre morte.

L'interface annonçait pourtant « → HEVC → DV » et nommait la sortie `_[hevc]`.
Un fichier de 60 Mb/s ressortait à 60 Mb/s sous un nom qui promettait l'inverse,
et rien à l'écran ne permettait de comprendre pourquoi.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.decision import (SUFFIX_DV_COPIE, DVAction, Emphase, VideoAction,
                           decide, emphase_video, video_recopiee)
from core.encoder import build_command
from core.platform import GPU, OS, PlatformProfile
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo, deja_produit

_PLAT = PlatformProfile(os=OS.WINDOWS, gpu=GPU.NVIDIA, hwaccel="cuda",
                        encoder_hevc="hevc_nvenc", encoder_h264="h264_nvenc",
                        encoder_av1="av1_nvenc")

_PROFIL_DV = Profile(id="dv", data={
    "bitrate_4k_kbps": 12000, "bitrate_1080p_kbps": 5000,
    "bitrate_720p_kbps": 3000, "keep_4k": True,
    "preset_encoder": "slow", "dolby_vision": "dv", "preserve_hd_audio": True,
})


def _source(bitrate: int, codec: str = "hevc", dv: str | None = "8.1") -> VideoInfo:
    return VideoInfo(
        path=Path("Film.mkv"), width=3840, height=2160, bitrate=bitrate,
        codec=codec, duration=7200.0, frame_count=0, dv_profile=dv,
        audio_tracks=[AudioTrack(index=0, codec="truehd", channels=8,
                                 language="fre", title="", bitrate=4_000_000)],
    )


# ─── Le prédicat ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("action", [VideoAction.ENCODE_HEVC,
                                    VideoAction.ENCODE_H264,
                                    VideoAction.ENCODE_AV1])
def test_toute_action_d_encodage_sur_du_dv_conserve_est_une_copie(action):
    assert video_recopiee(action, DVAction.DV)


@pytest.mark.parametrize("dv", [DVAction.NONE, DVAction.HDR10, DVAction.SDR])
def test_les_autres_traitements_dv_encodent_vraiment(dv):
    assert not video_recopiee(VideoAction.ENCODE_HEVC, dv)


def test_un_skip_n_est_pas_une_copie():
    """SKIP ne produit aucun fichier : il a déjà son propre libellé."""
    assert not video_recopiee(VideoAction.SKIP, DVAction.DV)


# ─── Ce que l'écran annonce ──────────────────────────────────────────────────

def test_le_libelle_annonce_la_copie_et_non_un_encodage():
    v = decide(_source(60_000_000), _PROFIL_DV).video
    assert v.label() == "→ DV (copie)"
    assert "HEVC" not in v.label()


def test_la_raison_explique_pourquoi_le_debit_ne_baissera_pas():
    v = decide(_source(60_000_000), _PROFIL_DV).video
    assert "60000k ≥ 12000k" in v.reason, "le déclencheur reste visible"
    assert "vidéo copiée" in v.reason,    "sa neutralisation aussi"


def test_la_copie_se_montre_comme_un_traitement_sans_perte():
    """Vert, comme un remux : l'image n'est pas touchée."""
    assert emphase_video(VideoAction.ENCODE_HEVC, DVAction.DV) is Emphase.SANS_PERTE


# ─── Ce que le fichier s'appelle ─────────────────────────────────────────────

def test_le_nom_de_sortie_ne_promet_pas_du_hevc_frais():
    d = decide(_source(60_000_000), _PROFIL_DV)
    assert d.output_path.name == f"Film{SUFFIX_DV_COPIE}.mkv"
    assert "_[hevc]" not in d.output_path.name


def test_la_sortie_n_est_pas_reproposee_au_scan_suivant():
    assert deja_produit(decide(_source(60_000_000), _PROFIL_DV).output_path.stem)


# ─── Et la commande, elle, n'a pas changé ────────────────────────────────────

def test_la_commande_copie_bien_la_video():
    """Le correctif porte sur l'annonce, pas sur ce qui est exécuté."""
    d   = decide(_source(60_000_000), _PROFIL_DV)
    cmd = build_command(d, _PLAT)
    assert cmd[cmd.index("-c:v") + 1] == "copy"
    assert "-b:v" not in cmd, "aucun débit cible n'est appliqué"


def test_sous_le_plafond_rien_n_est_produit():
    v = decide(_source(8_000_000), _PROFIL_DV).video
    assert v.action is VideoAction.SKIP
    assert v.label() == "← SKIP"


def test_une_source_sans_dv_encode_normalement():
    """Le profil `dv` ne bride que les sources Dolby Vision."""
    d = decide(_source(60_000_000, dv=None), _PROFIL_DV)
    assert d.video.label() == "→ HEVC"
    assert d.output_path.name == "Film_[hevc].mkv"
    cmd = build_command(d, _PLAT)
    assert cmd[cmd.index("-c:v") + 1] == "hevc_nvenc"
    assert "12000000" in cmd


# ─── L'estimation de taille ne promet pas la réduction non plus ──────────────

def test_l_estimation_n_annonce_pas_une_reduction_qui_n_aura_pas_lieu(tmp_path):
    """Une vidéo recopiée pèse ce qu'elle pesait.

    L'estimation partait du débit cible et annonçait un fichier trois fois
    plus petit — le même mensonge que le libellé, dans la colonne d'à côté et
    dans le total du dry-run.
    """
    from tui.screens.browser import _estimate_output_bytes

    fichier = tmp_path / "Film.mkv"
    fichier.write_bytes(b"0" * 5_000_000)

    d = decide(_source(60_000_000), _PROFIL_DV)
    object.__setattr__(d.info, "path", fichier)
    assert video_recopiee(d.video.action, d.video.dv_action)
    assert _estimate_output_bytes(d) == 5_000_000
