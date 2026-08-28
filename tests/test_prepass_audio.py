"""
tests/test_prepass_audio.py — Une piste audio transcodée disparaissait en silence.

Défaut ffmpeg mesuré le 2026-08-28, et **reproductible** : quand une même
commande transcode une piste audio *et* recopie un flux de sous-titres dont le
premier repère arrive tardivement, la piste transcodée n'est pas écrite. Deux
trames sortent, puis plus rien. Aucune erreur, aucun code de retour non nul —
le bilan de ffmpeg ne compte que l'audio recopiée.

Mesuré sur un film dont les sous-titres « forced » n'ouvrent qu'à 6 min 20 :

| Sous-titres mappés | Paquets audio produits sur 60 s |
|---|---|
| aucun | 1 875 — correct |
| les denses seules (premier repère à 23 s) | 1 875 — correct |
| la seule piste « forced » (premier repère à 380 s) | **2** |

Ni `max_muxing_queue_size`, ni `max_interleave_delta`, ni `avoid_negative_ts`,
ni `copyts`, ni l'ordre des `-map` n'y changent quoi que ce soit. Le défaut ne
dépend pas du codec — l'AC3 meurt comme l'E-AC3 — ni de la durée : il se
reproduit sur soixante secondes.

C'est la cause des entrées IE-12 et IE-16, closes faute d'explication : le
fichier « mal entrelacé » n'avait tout simplement pas de piste anglaise.

La parade est de produire les pistes finales dans une passe à part, puis de les
**recopier** — une copie n'est jamais perdue. Elle n'est payée que lorsque les
deux conditions sont réunies.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.decision import AudioAction, AudioDecision, decide
from core.encoder import audio_prepass_needed, build_command
from core.muxer import ExternalTrack, TrackKind
from core.platform import GPU, OS, PlatformProfile
from core.profiles import Profile
from core.scanner import AudioTrack, SubtitleTrack, VideoInfo


def _plat() -> PlatformProfile:
    return PlatformProfile(os=OS.WINDOWS, gpu=GPU.NVIDIA, hwaccel="cuda",
                           encoder_hevc="hevc_nvenc", encoder_h264="h264_nvenc",
                           encoder_av1="av1_nvenc")


def _profile(**over) -> Profile:
    data = {"bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
            "bitrate_4k_kbps": 8000, "audio_languages": ["fre", "eng"],
            "audio_copy_compatible": True, "preserve_hd_audio": False,
            "audio_hd_codec": "eac3"}
    data.update(over)
    return Profile(id="test", data=data)


def _info(tmp_path: Path, *, sous_titres=True, hd=True) -> VideoInfo:
    """Une source dont la piste anglaise sans perte sera transcodée."""
    p = tmp_path / "film.mkv"
    p.write_bytes(b"")
    pistes = [AudioTrack(index=0, codec="ac3", channels=6, language="fre",
                         title="FR VFF", bitrate=640_000)]
    pistes.append(AudioTrack(
        index=1, codec="truehd" if hd else "ac3", channels=6, language="eng",
        title="ENG VO", bitrate=3_501_887 if hd else 640_000))
    return VideoInfo(
        p, 3840, 1596, 12_000_000, "hevc", 8000.0, 0, None,
        audio_tracks=pistes,
        subtitle_tracks=([SubtitleTrack(index=0, codec="subrip", language="fre",
                                        title="FR Forced")]
                         if sous_titres else []),
    )


def _maps(cmd: list[str]) -> list[str]:
    return [cmd[i + 1] for i, x in enumerate(cmd) if x == "-map"]


# ─── Quand la passe est nécessaire ────────────────────────────────────────────

def test_transcodage_et_sous_titres_imposent_la_passe(tmp_path):
    dec = decide(_info(tmp_path), _profile())
    assert any(a.action == AudioAction.TRANSCODE for a in dec.audio)
    assert audio_prepass_needed(dec) is True


def test_sans_sous_titre_aucune_passe(tmp_path):
    """Rien à recopier qui puisse bloquer : la commande unique suffit."""
    dec = decide(_info(tmp_path, sous_titres=False), _profile())
    assert audio_prepass_needed(dec) is False


def test_sans_transcodage_aucune_passe(tmp_path):
    """Seules les pistes encodées disparaissent ; les copies traversent."""
    dec = decide(_info(tmp_path, hd=False), _profile())
    assert not any(a.action == AudioAction.TRANSCODE for a in dec.audio)
    assert audio_prepass_needed(dec) is False


def test_des_sous_titres_tous_ecartes_ne_l_imposent_pas(tmp_path):
    dec = decide(_info(tmp_path), _profile())
    dec.subtitle_indices = []
    assert audio_prepass_needed(dec) is False


# ─── La commande qui en découle ───────────────────────────────────────────────

def test_l_audio_vient_de_l_entree_dediee_et_est_recopiee(tmp_path):
    dec = decide(_info(tmp_path), _profile())
    cmd = build_command(dec, _plat(), audio_source=tmp_path / "a.mka")
    assert str(tmp_path / "a.mka") in cmd
    maps = _maps(cmd)
    assert "1:a:0" in maps and "1:a:1" in maps, maps
    assert "0:a:0" not in maps, "l'audio ne doit plus venir de la source"
    assert cmd[cmd.index("-c:a:0") + 1] == "copy"
    assert cmd[cmd.index("-c:a:1") + 1] == "copy"


def test_l_entree_dediee_se_parcourt_par_rang(tmp_path):
    """Elle ne contient que les pistes retenues : leurs index de source n'y
    valent plus rien."""
    info = _info(tmp_path)
    dec  = decide(info, _profile())
    dec.audio[0] = AudioDecision(track=info.audio_tracks[0],
                                 action=AudioAction.EXCLUDE, reason="",
                                 output_codec="", output_bitrate=0)
    cmd = build_command(dec, _plat(), audio_source=tmp_path / "a.mka")
    maps = [m for m in _maps(cmd) if ":a:" in m]
    assert maps == ["1:a:0"], "la seule piste gardée est la première du fichier"


def test_les_donneurs_ne_sont_pas_decales(tmp_path):
    """L'entrée dédiée est posée en dernier, pour que les index des pistes
    greffées restent ceux qu'ils étaient."""
    donneur = tmp_path / "vf.mkv"
    donneur.write_bytes(b"")
    dec = decide(_info(tmp_path), _profile())
    dec.external_tracks.append(ExternalTrack(
        source_path=donneur, source_tid=0, kind=TrackKind.SUBTITLE,
        codec="SubRip", language="fre"))
    cmd  = build_command(dec, _plat(), audio_source=tmp_path / "a.mka")
    maps = _maps(cmd)
    assert "1:s:0" in maps, "le donneur reste l'entrée 1"
    assert "2:a:0" in maps, "l'audio dédiée passe en entrée 2"


def test_sans_passe_la_commande_ne_change_pas(tmp_path):
    """Le chemin historique : transcodage dans la passe d'encodage."""
    dec = decide(_info(tmp_path), _profile())
    cmd = build_command(dec, _plat())
    assert "0:a:0" in _maps(cmd)
    assert cmd[cmd.index("-c:a:1") + 1] == "eac3"
