"""
tests/test_aac_secours.py — Une piste AAC stéréo avant chaque piste qui n'en est pas.

Le client web de Jellyfin sous Chrome ne lit pas l'E-AC3 : sur
`Silo.S01E01.MULTi.1080p.WEB-FW.hevc-iris.mp4` (E-AC3 5.1 Atmos fre + eng),
Jellyfin transcodait l'audio à chaque lecture. Il ne bascule pas de lui-même
vers une piste lisible : il prend la piste par défaut de la langue voulue.
D'où l'ordre voulu par l'utilisateur (2026-11-23) : AAC fre, E-AC3 fre,
AAC eng, E-AC3 eng — la première par défaut (`audio_aac_fallback`).
"""
from __future__ import annotations

from pathlib import Path

from core.decision import (AudioAction, VideoAction, decide, motifs_remux,
                           sorties_audio)
from core.dovi import build_strip_mp4
from core.encoder import audio_pass_needed, build_audio_command, build_command
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
            "audio_stereo_kbps": 192, "audio_aac_fallback": True}
    data.update(over)
    return Profile(id="test", data=data)


def _silo(tmp_path: Path, pistes=None) -> VideoInfo:
    """La sortie du signalement : HEVC 2 Mb/s, E-AC3 Atmos fre puis eng."""
    p = tmp_path / "Silo.S01E01.MULTi.1080p.WEB-FW.hevc-iris.mp4"
    p.write_bytes(b"")
    if pistes is None:
        pistes = [
            AudioTrack(index=0, codec="eac3", channels=6, language="fre",
                       title="FR E-AC3 5.1 Atmos", bitrate=448_000),
            AudioTrack(index=1, codec="eac3", channels=6, language="eng",
                       title="", bitrate=448_000),
        ]
    return VideoInfo(p, 1920, 1080, 2_047_554, "hevc", 3000.0, 0, None,
                     audio_tracks=pistes)


def _maps(cmd: list[str]) -> list[str]:
    return [cmd[i + 1] for i, x in enumerate(cmd) if x == "-map"]


def _option(cmd: list[str], nom: str) -> str | None:
    """Dernière valeur d'une option : c'est celle que ffmpeg retient."""
    valeur = None
    for i, x in enumerate(cmd[:-1]):
        if x == nom:
            valeur = cmd[i + 1]
    return valeur


# ─── Décision ─────────────────────────────────────────────────────────────────

def test_chaque_langue_recoit_son_aac_avant_l_eac3(tmp_path):
    dec = decide(_silo(tmp_path), _profile())
    sorties = sorties_audio(dec.audio)
    assert [(s.track.language, s.action, s.output_codec) for s in sorties] == [
        ("fre", AudioAction.TRANSCODE, "aac"),
        ("fre", AudioAction.COPY, "copy"),
        ("eng", AudioAction.TRANSCODE, "aac"),
        ("eng", AudioAction.COPY, "copy"),
    ]
    aac = sorties[0]
    assert (aac.output_bitrate, aac.output_channels) == (192_000, 2)
    # Le titre ne ment pas : la piste AAC n'est ni de l'E-AC3, ni de l'Atmos.
    assert aac.output_title == "FR AAC 2.0"


def test_une_ligne_par_piste_source(tmp_path):
    """L'écran des pistes garde une ligne — une clé — par piste de la source :
    le secours se rattache à sa piste, il n'en est pas une de plus."""
    dec = decide(_silo(tmp_path), _profile())
    assert [ad.track.index for ad in dec.audio] == [0, 1]
    assert "aac" in dec.audio[0].display()


def test_sans_la_cle_rien_ne_change(tmp_path):
    dec = decide(_silo(tmp_path), _profile(audio_aac_fallback=False))
    assert all(ad.secours is None for ad in dec.audio)
    data = dict(_profile().data)
    del data["audio_aac_fallback"]
    dec = decide(_silo(tmp_path), Profile(id="t", data=data))
    assert all(ad.secours is None for ad in dec.audio)


def test_une_langue_deja_en_aac_n_en_recoit_pas_d_autre(tmp_path):
    """Une sortie repassée garde ses secours ; elle n'en reçoit pas de
    nouveaux à chaque passage."""
    pistes = [
        AudioTrack(index=0, codec="aac", channels=2, language="fre", title="",
                   bitrate=192_000),
        AudioTrack(index=1, codec="eac3", channels=6, language="fre", title="",
                   bitrate=448_000),
        AudioTrack(index=2, codec="eac3", channels=6, language="eng", title="",
                   bitrate=448_000),
    ]
    dec = decide(_silo(tmp_path, pistes), _profile())
    assert [ad.secours is not None for ad in dec.audio] == [False, False, True]


def test_une_piste_ecartee_n_a_pas_de_secours(tmp_path):
    info = _silo(tmp_path)
    info.audio_tracks[1].language = "ger"
    dec = decide(info, _profile())
    assert dec.audio[1].action == AudioAction.EXCLUDE
    assert dec.audio[1].secours is None
    assert len(sorties_audio(dec.audio)) == 2


def test_une_sortie_sans_aac_passe_en_remux(tmp_path):
    """La vidéo convient (SKIP) ; c'est l'audio qui ferait transcoder."""
    dec = decide(_silo(tmp_path), _profile())
    assert "AAC" in motifs_remux(dec)
    assert dec.video.action == VideoAction.REMUX


# ─── Commandes ffmpeg ─────────────────────────────────────────────────────────

def test_encodage_mappe_et_encode_dans_l_ordre(tmp_path):
    dec = decide(_silo(tmp_path), _profile())
    cmd = build_command(dec, _plat())
    assert [m for m in _maps(cmd) if ":a:" in m] == [
        "0:a:0", "0:a:0", "0:a:1", "0:a:1"]
    assert [_option(cmd, f"-c:a:{n}") for n in range(4)] == [
        "aac", "copy", "aac", "copy"]
    assert _option(cmd, "-ac:a:0") == "2" and _option(cmd, "-ac:a:2") == "2"


def test_seule_la_premiere_piste_est_par_defaut(tmp_path):
    """Recopiés de la source, les drapeaux se dédoublaient : l'AAC et
    l'E-AC3 français lisent le même flux, marqué par défaut."""
    dec = decide(_silo(tmp_path), _profile())
    for cmd in (build_command(dec, _plat()),
                build_audio_command(dec.info.path, tmp_path / "a.mka", dec.audio),
                build_strip_mp4(dec.info.path, tmp_path / "o.mp4", [],
                                audio=dec.audio)):
        assert [_option(cmd, f"-disposition:a:{n}") for n in range(4)] == [
            "default", "0", "0", "0"], cmd


def test_sans_secours_les_drapeaux_de_la_source_restent(tmp_path):
    dec = decide(_silo(tmp_path), _profile(audio_aac_fallback=False))
    cmd = build_command(dec, _plat())
    assert not any(x.startswith("-disposition:a") for x in cmd)


def test_la_passe_audio_du_retrait_dv_fabrique_le_secours(tmp_path):
    """mkvmerge recopie, il ne fabrique pas d'AAC : la passe ffmpeg s'impose."""
    dec = decide(_silo(tmp_path), _profile())
    assert all(ad.action == AudioAction.COPY for ad in dec.audio)
    assert audio_pass_needed(dec.audio) is True
    cmd = build_audio_command(dec.info.path, tmp_path / "a.mka", dec.audio)
    assert _maps(cmd) == ["0:a:0", "0:a:0", "0:a:1", "0:a:1"]
    assert _option(cmd, "-c:a:0") == "aac"
