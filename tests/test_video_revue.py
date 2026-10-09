"""
tests/test_video_revue.py — Vidéo et encodeurs (IE-130).

Constats CR-14, CR-16, CR-17, CR-19, CR-22 et CR-42 de
`revue_code_2026-10-08.md`, et la question « H264 sur HDR10 » de la même
revue, tranchée le 2026-10-09 : H264 sur une source HDR sort en SDR, et
l'écran le dit au moment du choix.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import encoder
from core import platform as plat_mod
from core.decision import (ACTION_CYCLE, CODEC_PAR_ACTION, DVAction, VideoAction,
                           choisir_codec, decide, force_skip_to_encode)
from core.encoder import build_command, build_dv_video_command
from core.platform import GPU, OS, PlatformProfile
from core.profiles import Profile
from core.scanner import VideoInfo

_BIN = Path(__file__).resolve().parent.parent / "bin"
_FFMPEG, _FFPROBE = _BIN / "ffmpeg.exe", _BIN / "ffprobe.exe"
outils = pytest.mark.skipif(not (_FFMPEG.exists() and _FFPROBE.exists()),
                            reason="ffmpeg du projet absent")


def _profile(**over) -> Profile:
    data = {"bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
            "bitrate_4k_kbps": 12000, "keep_4k": True,
            "audio_languages": ["fre"], "audio_copy_compatible": True,
            "preset_encoder": "ultrafast", "dolby_vision": "hdr10"}
    data.update(over)
    return Profile(id="test", data=data)


def _plat(hevc="libx265", h264="libx264", av1="libaom-av1") -> PlatformProfile:
    return PlatformProfile(os=OS.WINDOWS, gpu=GPU.NONE, hwaccel=None,
                           encoder_hevc=hevc, encoder_h264=h264, encoder_av1=av1)


def _info(tmp_path, nom="Film", w=1920, h=1080, codec="hevc", bitrate=1_500_000,
          transfert="", sar="", dv=None) -> VideoInfo:
    p = tmp_path / f"{nom}.mkv"
    if not p.exists():
        p.write_bytes(b"")
    return VideoInfo(path=p, width=w, height=h, bitrate=bitrate, codec=codec,
                     duration=60.0, frame_count=0, dv_profile=dv,
                     color_transfer=transfert, sar=sar)


def _valeur(cmd, option):
    return cmd[cmd.index(option) + 1]


# ─── H264 sur une source HDR : SDR, et averti ────────────────────────────────

@pytest.mark.parametrize("transfert", ["smpte2084", "arib-std-b67"])
def test_h264_sur_une_source_hdr_sort_en_sdr(tmp_path, transfert):
    dec = decide(_info(tmp_path, bitrate=20_000_000, transfert=transfert), _profile())
    v = choisir_codec(dec, VideoAction.ENCODE_H264)
    assert v.dv_action == DVAction.SDR and "SDR" in v.label()
    dec.video = v
    vf = _valeur(build_command(dec, _plat()), "-vf")
    assert "tonemap" in vf
    assert _valeur(build_command(dec, _plat()), "-pix_fmt") == "yuv420p"


def test_h264_sur_une_source_sdr_ne_change_rien(tmp_path):
    dec = decide(_info(tmp_path, bitrate=20_000_000), _profile())
    assert choisir_codec(dec, VideoAction.ENCODE_H264).dv_action == DVAction.NONE


def test_hevc_sur_une_source_hdr_garde_le_hdr(tmp_path):
    dec = decide(_info(tmp_path, bitrate=20_000_000, transfert="smpte2084"), _profile())
    assert choisir_codec(dec, VideoAction.ENCODE_HEVC).dv_action != DVAction.SDR


def test_l_ecran_avertit_au_moment_du_choix(tmp_path):
    from tui.common import avertir_h264_sdr
    notes = []
    ecran = SimpleNamespace(notify=lambda m, **k: notes.append(m))
    hdr = _info(tmp_path, transfert="smpte2084")
    avertir_h264_sdr(ecran, hdr, VideoAction.ENCODE_HEVC)
    avertir_h264_sdr(ecran, _info(tmp_path, "SDR"), VideoAction.ENCODE_H264)
    assert notes == []
    avertir_h264_sdr(ecran, hdr, VideoAction.ENCODE_H264)
    assert len(notes) == 1 and "SDR" in notes[0]


@outils
def test_la_sortie_h264_d_une_source_pq_est_en_sdr(tmp_path):
    """Bout en bout : la commande d'IRIS convertit vraiment (zscale, tonemap)."""
    src = tmp_path / "pq.mkv"
    subprocess.run([str(_FFMPEG), "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "testsrc=size=640x360:rate=25:duration=1",
                    # Étiquettes posées dans le flux : les options de sortie
                    # seules laissaient primaires et courbe « unknown », et
                    # zscale ne sait pas convertir sans elles (mesuré).
                    "-vf", "format=yuv420p10le,setparams=color_primaries=bt2020"
                    ":color_trc=smpte2084:colorspace=bt2020nc",
                    "-c:v", "libx265", "-preset", "ultrafast", "-x265-params",
                    "log-level=none:colorprim=bt2020:transfer=smpte2084"
                    ":colormatrix=bt2020nc", str(src)],
                   check=True, capture_output=True)
    encoder.set_ffmpeg_path(str(_FFMPEG))
    info = _info(tmp_path, "pq", w=640, h=360, bitrate=20_000_000,
                 transfert="smpte2084")
    info.path = src
    dec = decide(info, _profile())
    dec.video = choisir_codec(dec, VideoAction.ENCODE_H264)
    r = subprocess.run(build_command(dec, _plat()), capture_output=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr[-600:]
    flux = json.loads(subprocess.run(
        [str(_FFPROBE), "-v", "error", "-print_format", "json", "-show_streams",
         "-select_streams", "v", str(dec.output_path)],
        capture_output=True, encoding="utf-8", check=True).stdout)["streams"][0]
    assert flux["codec_name"] == "h264"
    assert flux.get("color_transfer", "") not in ("smpte2084", "arib-std-b67")


# ─── CR-16 : forcer un film au format scope ──────────────────────────────────

@pytest.mark.parametrize("w,h,transfert,attendu", [
    (1920, 800, "", VideoAction.ENCODE_HEVC),
    (1280, 720, "", VideoAction.ENCODE_H264),
    (1280, 720, "smpte2084", VideoAction.ENCODE_HEVC),
])
def test_le_forcage_suit_la_tranche_et_garde_le_hdr(tmp_path, w, h, transfert, attendu):
    dec = decide(_info(tmp_path, w=w, h=h, transfert=transfert), _profile())
    assert dec.video.action == VideoAction.SKIP
    assert force_skip_to_encode(dec).video.action == attendu


# ─── CR-17 : chaque action a son libellé ─────────────────────────────────────

def test_chaque_codec_s_affiche_sous_son_nom(tmp_path):
    dec = decide(_info(tmp_path, bitrate=20_000_000), _profile())
    for action in ACTION_CYCLE:
        if action == VideoAction.SKIP:
            continue
        assert CODEC_PAR_ACTION[action] in choisir_codec(dec, action).label()
    assert "AV1" in choisir_codec(dec, VideoAction.ENCODE_AV1).label()


def test_toute_action_qui_encode_a_un_libelle():
    assert set(VideoAction) - set(CODEC_PAR_ACTION) == {VideoAction.SKIP,
                                                        VideoAction.STRIP_DV}


# ─── CR-19 : débit inconnu ───────────────────────────────────────────────────

def test_un_debit_inconnu_est_reencode_a_la_cible(tmp_path):
    dec = decide(_info(tmp_path, w=3840, h=2160, bitrate=0), _profile())
    assert dec.video.action == VideoAction.ENCODE_HEVC
    assert dec.video.target_bitrate == 12_000_000
    assert "12000k" in dec.video.reason


def test_forcer_un_debit_inconnu_prend_la_cible(tmp_path):
    dec = decide(_info(tmp_path, bitrate=1_500_000), _profile())
    dec.info.bitrate = 0
    assert force_skip_to_encode(dec).video.target_bitrate == 5_000_000


def test_l_analyse_garde_l_inconnu():
    from core import scanner
    assert "9_999_999" not in Path(scanner.__file__).read_text(encoding="utf-8")


# ─── CR-14 : pixels non carrés ───────────────────────────────────────────────

def test_une_source_anamorphique_passe_en_pixels_carres(tmp_path):
    dec = decide(_info(tmp_path, w=720, h=480, codec="mpeg2video",
                       bitrate=6_000_000, sar="32:27"), _profile())
    vf = _valeur(build_command(dec, _plat()), "-vf")
    assert vf.startswith("scale=trunc(iw*sar/2)*2:trunc(ih/2)*2,setsar=1")


def test_une_source_aux_pixels_carres_n_a_pas_de_filtre(tmp_path):
    dec = decide(_info(tmp_path, w=1280, h=720, codec="mpeg2video",
                       bitrate=6_000_000, sar="1:1"), _profile())
    assert "-vf" not in build_command(dec, _plat())


@outils
def test_la_sortie_d_un_dvd_anamorphique_est_carree_en_16_9(tmp_path):
    src = tmp_path / "dvd.mkv"
    subprocess.run([str(_FFMPEG), "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "testsrc=size=720x480:rate=25:duration=1",
                    "-vf", "setsar=32/27", "-c:v", "mpeg2video", str(src)],
                   check=True, capture_output=True)
    encoder.set_ffmpeg_path(str(_FFMPEG))
    info = _info(tmp_path, "dvd", w=720, h=480, codec="mpeg2video",
                 bitrate=6_000_000, sar="32:27")
    info.path = src
    dec = decide(info, _profile())
    r = subprocess.run(build_command(dec, _plat()), capture_output=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr[-600:]
    flux = json.loads(subprocess.run(
        [str(_FFPROBE), "-v", "error", "-print_format", "json", "-show_streams",
         "-select_streams", "v", str(dec.output_path)],
        capture_output=True, encoding="utf-8", check=True).stdout)["streams"][0]
    assert flux.get("sample_aspect_ratio", "1:1") == "1:1"
    assert flux["width"] / flux["height"] == pytest.approx(16 / 9, rel=0.01)


# ─── CR-22 : la règle de débit suit l'encodeur effectif ──────────────────────

def test_libx265_garde_le_plafond_a_la_cible_partout(tmp_path):
    dec = decide(_info(tmp_path, bitrate=20_000_000), _profile())
    for cmd in (build_command(dec, _plat()),
                build_dv_video_command(dec, _plat(), tmp_path / "v.hevc")):
        assert _valeur(cmd, "-maxrate") == _valeur(cmd, "-b:v")
        assert "-rc" not in cmd


def test_nvenc_garde_sa_marge(tmp_path):
    dec = decide(_info(tmp_path, bitrate=20_000_000), _profile())
    for cmd in (build_command(dec, _plat("hevc_nvenc")),
                build_dv_video_command(dec, _plat("hevc_nvenc"), tmp_path / "v.hevc")):
        assert int(_valeur(cmd, "-maxrate")) == int(_valeur(cmd, "-b:v")) * 3 // 2
        assert _valeur(cmd, "-rc") == "vbr"


# ─── CR-42 : la sonde essaie aussi le 10 bits ────────────────────────────────

def test_nvenc_hevc_et_av1_sont_sondes_en_10_bits():
    liste = plat_mod.encodeurs_a_sonder(_plat("hevc_nvenc", "h264_nvenc", "av1_nvenc"))
    assert "hevc_nvenc@10" in liste and "av1_nvenc@10" in liste
    assert "h264_nvenc@10" not in liste and "libx265@10" not in liste


def test_l_essai_10_bits_demande_p010_et_main10(monkeypatch):
    lances = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **k: lances.append(cmd)
                        or SimpleNamespace(returncode=0, stderr=b""))
    ok = plat_mod.sonder_encodeurs(["hevc_nvenc@10", "av1_nvenc@10"], "ffmpeg")
    assert ok == {"hevc_nvenc@10", "av1_nvenc@10"}
    hevc = next(c for c in lances if "hevc_nvenc" in c)
    av1 = next(c for c in lances if "av1_nvenc" in c)
    assert _valeur(hevc, "-pix_fmt") == "p010le" and _valeur(hevc, "-profile:v") == "main10"
    assert _valeur(av1, "-pix_fmt") == "p010le" and "-profile:v" not in av1


def _ecran(platform):
    from tui.screens.run import FileState
    statut = SimpleNamespace(state=FileState.RUNNING, error_msg="", last_line="")
    return SimpleNamespace(_statuses=[statut], _platform=platform,
                           app=SimpleNamespace(call_from_thread=lambda f, *a: f(*a)),
                           _update_row=lambda i: None), statut


@pytest.mark.parametrize("pix_fmt,refuse", [("p010le", True), ("yuv420p", False)])
def test_un_hdr_est_refuse_quand_seul_le_8_bits_passe(pix_fmt, refuse):
    from tui.screens.run import FileState, RunScreen
    carte = _plat("hevc_nvenc", "h264_nvenc")
    from dataclasses import replace
    carte = replace(carte, encodeurs_ok=frozenset({"hevc_nvenc", "h264_nvenc"}))
    ecran, statut = _ecran(carte)
    cmd = ["ffmpeg", "-i", "x.mkv", "-c:v", "hevc_nvenc", "-pix_fmt", pix_fmt, "y.mkv"]
    assert RunScreen._refuser_encodeur(ecran, 0, cmd) is refuse
    assert (statut.state == FileState.ERROR) is refuse
    if refuse:
        assert "10" in statut.error_msg
