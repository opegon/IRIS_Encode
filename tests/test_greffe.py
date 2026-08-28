"""
tests/test_greffe.py — La piste greffée doit être celle qu'on a choisie.

Le donneur entre dans ffmpeg **en entier**, et la commande mappait son flux
`:0` — ce qui suppose qu'il n'en porte qu'un. Vrai d'un `.srt` nu, faux d'un
conteneur : un rip qui embarque six pistes de sous-titres rendait toujours la
première, quelle que soit celle demandée.

Le défaut était invisible à la relecture de la commande, parce que la langue,
le titre et les drapeaux venaient de la **bonne** piste. Vu de l'utilisateur :
la piste apparaît dans le lecteur, correctement nommée, et n'affiche rien —
la première piste d'un rip est en général la « forced », vingt-trois répliques
sur un épisode entier.

Signalé sur un fichier réel : `Silo.S03E09.720p.FR.mkv`, six pistes françaises
dont deux forced en tête de liste.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core import muxer
from core.decision import decide
from core.encoder import build_command
from core.muxer import ExternalTrack, IdentifiedTrack, TrackKind
from core.platform import GPU, OS, PlatformProfile
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo


def _plat() -> PlatformProfile:
    return PlatformProfile(os=OS.WINDOWS, gpu=GPU.NVIDIA, hwaccel="cuda",
                           encoder_hevc="hevc_nvenc", encoder_h264="h264_nvenc",
                           encoder_av1="av1_nvenc")


def _profile() -> Profile:
    return Profile(id="test", data={
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps": 8000, "audio_languages": ["fre", "eng"],
        "audio_copy_compatible": True, "preserve_hd_audio": False,
    })


def _info(tmp_path: Path) -> VideoInfo:
    p = tmp_path / "episode.mkv"
    p.write_bytes(b"")
    return VideoInfo(
        path=p, width=1920, height=1080, bitrate=8_000_000, codec="h264",
        duration=3703.0, frame_count=0, dv_profile=None,
        audio_tracks=[AudioTrack(index=0, codec="eac3", channels=6,
                                 language="eng", title="", bitrate=640_000)],
        subtitle_tracks=[],
    )


# Un donneur au dessin de Silo.S03E09.720p.FR.mkv : une piste audio, puis six
# sous-titres dont les forced en tête.
_DONNEUR = [
    IdentifiedTrack(tid=1, kind=TrackKind.AUDIO,    codec="EAC3",   language="fre",
                    track_name="French"),
    IdentifiedTrack(tid=2, kind=TrackKind.SUBTITLE, codec="SubRip", language="fre",
                    track_name="Français (France) (forced)"),
    IdentifiedTrack(tid=3, kind=TrackKind.SUBTITLE, codec="SubRip", language="fre",
                    track_name="Français (France)"),
    IdentifiedTrack(tid=4, kind=TrackKind.SUBTITLE, codec="SubRip", language="fre",
                    track_name="Français (France) (SDH)"),
    IdentifiedTrack(tid=5, kind=TrackKind.SUBTITLE, codec="SubRip", language="fre",
                    track_name="Français (Canada) (forced)"),
    IdentifiedTrack(tid=6, kind=TrackKind.SUBTITLE, codec="SubRip", language="fre",
                    track_name="Français (Canada)"),
    IdentifiedTrack(tid=7, kind=TrackKind.SUBTITLE, codec="SubRip", language="fre",
                    track_name="Français (Canada) (SDH)"),
]


@pytest.fixture
def donneur(monkeypatch, tmp_path) -> Path:
    p = tmp_path / "donneur.mkv"
    p.write_bytes(b"")
    monkeypatch.setattr(muxer, "identify", lambda _path: list(_DONNEUR))
    return p


def _maps(cmd: list[str]) -> list[str]:
    return [cmd[i + 1] for i, x in enumerate(cmd) if x == "-map"]


def _commande(tmp_path, pistes: list[ExternalTrack]) -> list[str]:
    dec = decide(_info(tmp_path), _profile())
    dec.external_tracks.extend(pistes)
    return build_command(dec, _plat())


# ─── Le défaut ────────────────────────────────────────────────────────────────

def test_le_sous_titre_greffe_est_celui_qui_a_ete_choisi(tmp_path, donneur):
    """tid 3 = « Français (France) », deuxième sous-titre du donneur → s:1."""
    piste = ExternalTrack(source_path=donneur, source_tid=3,
                          kind=TrackKind.SUBTITLE, codec="SubRip",
                          language="fre", track_name="Français (France)")
    maps = _maps(_commande(tmp_path, [piste]))
    assert "1:s:1" in maps, maps
    assert "1:s:0" not in maps, "c'est la piste « forced » — 23 répliques"


def test_la_derniere_piste_du_donneur_est_atteignable(tmp_path, donneur):
    piste = ExternalTrack(source_path=donneur, source_tid=7,
                          kind=TrackKind.SUBTITLE, codec="SubRip",
                          language="fre", track_name="Français (Canada) (SDH)")
    assert "1:s:5" in _maps(_commande(tmp_path, [piste]))


def test_une_piste_audio_choisie_est_mappee_pareil(tmp_path, donneur):
    """Le même défaut frappait l'audio dès qu'un donneur en portait plusieurs."""
    piste = ExternalTrack(source_path=donneur, source_tid=1,
                          kind=TrackKind.AUDIO, codec="EAC3", language="fre")
    assert "1:a:0" in _maps(_commande(tmp_path, [piste]))


def test_deux_pistes_du_meme_donneur_gardent_chacune_la_sienne(tmp_path, donneur):
    """Chaque piste a sa propre entrée : leurs index ne doivent pas se mélanger."""
    pistes = [
        ExternalTrack(source_path=donneur, source_tid=1, kind=TrackKind.AUDIO,
                      codec="EAC3", language="fre"),
        ExternalTrack(source_path=donneur, source_tid=4, kind=TrackKind.SUBTITLE,
                      codec="SubRip", language="fre"),
    ]
    maps = _maps(_commande(tmp_path, pistes))
    assert "1:a:0" in maps and "2:s:2" in maps, maps


def test_un_srt_nu_reste_en_zero(tmp_path, monkeypatch):
    """Le cas d'origine : un fichier à une seule piste, tid 0."""
    p = tmp_path / "vf.srt"
    p.write_bytes(b"")
    monkeypatch.setattr(muxer, "identify", lambda _p: [
        IdentifiedTrack(tid=0, kind=TrackKind.SUBTITLE, codec="SubRip",
                        language="fre")])
    piste = ExternalTrack(source_path=p, source_tid=0, kind=TrackKind.SUBTITLE,
                          codec="SubRip", language="fre")
    assert "1:s:0" in _maps(_commande(tmp_path, [piste]))


def test_un_donneur_illisible_retombe_sur_le_premier_flux(tmp_path, monkeypatch):
    """mkvmerge absent ou muet : on ne devine pas, on garde l'ancien comportement."""
    p = tmp_path / "muet.mkv"
    p.write_bytes(b"")
    monkeypatch.setattr(muxer, "identify", lambda _p: [])
    piste = ExternalTrack(source_path=p, source_tid=3, kind=TrackKind.SUBTITLE,
                          codec="SubRip", language="fre")
    assert "1:s:0" in _maps(_commande(tmp_path, [piste]))
