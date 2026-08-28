"""
tests/test_x265_debit.py — libx265 et NVENC veulent des réglages **opposés**.

Le mode standard (NVENC) a reçu en v0.8.1.24 un plafond à 1,5 × la cible : avec
`-maxrate` égal à `-b:v`, son CBR traitait le débit demandé comme un plafond
que rien ne l'obligeait à atteindre, et la moyenne ne pouvait que tomber en
dessous — 92 % du débit visé sur un film en prises de vues réelles.

La tentation était d'appliquer la même correction au mode « HDR10 quality »
(libx265 CPU), par cohérence. **La mesure dit l'inverse.** L'ABR de x265
distribue un budget selon son modèle de qualité ; c'est un VBV serré qui le
force à le dépenser. Desserrer le plafond le fait sous-consommer.

Mesuré sur `pilgrimage.2017.1080p`, 10 bits, extraits de 120 s, cible 5 000k :

| Réglage | t=1800 | t=4200 |
|---|---|---|
| `maxrate` = cible — **l'actuel** | 99,9 % | 100,0 % |
| `maxrate` = 1,5 × la cible | 93,6 % | 99,9 % |
| ABR seul, sans VBV | 93,7 % | — |

Au preset `slow`, celui de `cinema_4k_basic` : **99,6 %**. Le préréglage ne
change pas la conclusion.

Le réglage en place n'est jamais battu, et il est parfois meilleur de six
points. Ces tests existent pour qu'une passe d'harmonisation entre les deux
branches de `build_command` échoue bruyamment au lieu de casser ce mode en
silence : elles se ressemblent, et elles doivent différer.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.decision import DVAction, VideoAction, decide
from core.encoder import build_command
from core.platform import GPU, OS, PlatformProfile
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo


def _plat() -> PlatformProfile:
    return PlatformProfile(os=OS.WINDOWS, gpu=GPU.NVIDIA, hwaccel="cuda",
                           encoder_hevc="hevc_nvenc", encoder_h264="h264_nvenc",
                           encoder_av1="av1_nvenc")


def _profile(**over) -> Profile:
    data = {"bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
            "bitrate_4k_kbps": 8000, "audio_languages": ["fre", "eng"],
            "audio_copy_compatible": True, "preserve_hd_audio": False,
            "preset_encoder": "slow", "keep_4k": True}
    data.update(over)
    return Profile(id="test", data=data)


def _info(tmp_path: Path) -> VideoInfo:
    """Une source 4K HDR à Dolby Vision, au-dessus du seuil : réencodage HEVC."""
    p = tmp_path / "film.mkv"
    p.write_bytes(b"")
    return VideoInfo(
        path=p, width=3840, height=2160, bitrate=12_000_000, codec="hevc",
        duration=8000.0, frame_count=0, dv_profile=8, dv_bl_compat=1,
        color_transfer="smpte2084", frame_rate="24/1",
        audio_tracks=[AudioTrack(index=0, codec="eac3", channels=6,
                                 language="fre", title="", bitrate=640_000)],
        subtitle_tracks=[],
    )


def _valeur(cmd: list[str], option: str) -> str:
    return cmd[cmd.index(option) + 1]


@pytest.fixture
def commande_x265(tmp_path):
    dec = decide(_info(tmp_path), _profile(hdr10_quality="quality"))
    assert dec.video.action == VideoAction.ENCODE_HEVC, dec.video.action
    assert dec.video.dv_action == DVAction.HDR10, dec.video.dv_action
    cmd = build_command(dec, _plat())
    assert _valeur(cmd, "-c:v") == "libx265", "ce n'est pas le mode quality"
    return cmd


# ─── Le mode « HDR10 quality » garde son plafond serré ────────────────────────

def test_le_plafond_reste_egal_a_la_cible(commande_x265):
    """Ce qui a été corrigé pour NVENC serait une régression ici : 99,9 % → 93,6 %."""
    assert _valeur(commande_x265, "-maxrate") == _valeur(commande_x265, "-b:v")


def test_le_vbv_reste_present(commande_x265):
    """Sans contrainte VBV, x265 sous-consomme — 93,7 % de la cible mesurés."""
    assert "-bufsize" in commande_x265
    bufsize = int(_valeur(commande_x265, "-bufsize").rstrip("k")) * 1000
    cible   = int(_valeur(commande_x265, "-b:v"))
    assert bufsize == cible * 2


def test_le_mode_quality_n_est_pas_pilote_par_un_rc(commande_x265):
    """`-rc` est une option NVENC : la passer à libx265 n'aurait aucun sens."""
    assert "-rc" not in commande_x265


# ─── Le mode standard, lui, garde sa marge ────────────────────────────────────

def test_les_deux_chemins_different_a_dessein(tmp_path):
    """Le même profil sans « quality » : NVENC, plafond à 1,5 × la cible."""
    dec = decide(_info(tmp_path), _profile(hdr10_quality="compat"))
    cmd = build_command(dec, _plat())
    assert _valeur(cmd, "-c:v") == "hevc_nvenc"
    cible   = int(_valeur(cmd, "-b:v"))
    maxrate = int(_valeur(cmd, "-maxrate"))
    assert maxrate == cible * 3 // 2
    assert _valeur(cmd, "-rc") == "vbr"
