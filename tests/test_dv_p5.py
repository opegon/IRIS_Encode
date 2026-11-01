"""
tests/test_dv_p5.py — Dolby Vision profil 5 converti en HDR10 ou en SDR.

La couche de base d'un profil 5 est en IPT-PQ : réencodée comme du YUV, elle
sortait verte et violette (Smile 2, v0.9.1.11). Seul `libplacebo`, qui
applique le RPU, en tire des couleurs justes ; sans ffmpeg qui l'a, le fichier
est écarté plutôt que livré faux.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from core import dovi, preflight
from core.decision import DVAction, VideoAction, decide
from core.encoder import build_command
from core.i18n import ErreurAffichable
from core.platform import GPU, OS, PlatformProfile
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo

FF_DV = "C:/iris/bin/dv/ffmpeg.exe"

_PLAT = PlatformProfile(
    os=OS.WINDOWS, gpu=GPU.NVIDIA, hwaccel="cuda",
    encoder_hevc="hevc_nvenc", encoder_h264="h264_nvenc",
    encoder_av1="av1_nvenc",
)


def _info(tmp_path: Path, dv_profile=5, dv_bl_compat=0) -> VideoInfo:
    p = tmp_path / "Smile.2.2024.DV.2160p.mkv"
    p.write_bytes(b"")
    return VideoInfo(
        path=p, width=3840, height=1920, bitrate=23_000_000, codec="hevc",
        duration=7620.0, frame_count=182_000, dv_profile=dv_profile,
        audio_tracks=[AudioTrack(index=0, codec="eac3", channels=6,
                                 language="fre", title="VFF", bitrate=640_000)],
        dv_bl_compat=dv_bl_compat, color_transfer="", frame_rate="24/1",
    )


def _profil(dv="hdr10", **over) -> Profile:
    data = {
        "bitrate_4k_kbps": 12000, "bitrate_1080p_kbps": 5000,
        "bitrate_720p_kbps": 2000, "keep_4k": False,
        "dolby_vision": dv, "preset_encoder": "medium",
        "audio_languages": ["fre"], "audio_copy_compatible": True,
    }
    data.update(over)
    return Profile(id="test", data=data)


def _vf(cmd: list[str]) -> str:
    return cmd[cmd.index("-vf") + 1]


# ─── Décision ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("dv", ["hdr10", "sdr"])
def test_sans_outil_le_p5_est_ecarte(tmp_path, dv):
    dovi.set_ffmpeg_dv(None)
    dec = decide(_info(tmp_path), _profil(dv))
    assert dec.video.action == VideoAction.SKIP
    assert "libplacebo" in dec.video.reason
    assert build_command(dec, _PLAT) == []


def test_avec_outil_le_p5_est_reencode(tmp_path):
    dovi.set_ffmpeg_dv(FF_DV)
    dec = decide(_info(tmp_path), _profil())
    assert dec.video.action == VideoAction.ENCODE_HEVC


def test_garder_le_dv_d_un_p5_ne_demande_pas_l_outil(tmp_path):
    dovi.set_ffmpeg_dv(None)
    dec = decide(_info(tmp_path), _profil("dv"))
    assert dec.video.dv_action == DVAction.DV
    assert dec.video.action != VideoAction.SKIP


# ─── Commande ─────────────────────────────────────────────────────────────────

def test_hdr10_passe_par_libplacebo(tmp_path):
    dovi.set_ffmpeg_dv(FF_DV)
    cmd = build_command(decide(_info(tmp_path), _profil()), _PLAT)
    assert cmd[:3] == [FF_DV, "-init_hw_device", "vulkan"]
    assert "-hwaccel" not in cmd
    vf = _vf(cmd)
    assert vf.startswith("libplacebo=apply_dolbyvision=1:")
    for opt in ("w=1920", "h=1080", "force_original_aspect_ratio=decrease",
                "colorspace=bt2020nc", "color_primaries=bt2020",
                "color_trc=smpte2084", "format=yuv420p10le"):
        assert opt in vf
    assert "zscale" not in vf
    assert cmd[cmd.index("-pix_fmt") + 1] == "yuv420p10le"


def test_sdr_passe_par_libplacebo_sans_zscale(tmp_path):
    dovi.set_ffmpeg_dv(FF_DV)
    cmd = build_command(decide(_info(tmp_path), _profil("sdr")), _PLAT)
    vf = _vf(cmd)
    assert "libplacebo=apply_dolbyvision=1" in vf
    assert "color_trc=bt709" in vf and "format=yuv420p," in vf
    assert "zscale" not in vf


def test_hdr10_quality_garde_libplacebo(tmp_path):
    dovi.set_ffmpeg_dv(FF_DV)
    dec = decide(_info(tmp_path), _profil(hdr10_quality="quality"))
    cmd = build_command(dec, _PLAT)
    assert cmd[0] == FF_DV and "libx265" in cmd
    assert "libplacebo=" in _vf(cmd)


def test_action_forcee_sans_outil_refusee(tmp_path):
    dovi.set_ffmpeg_dv(FF_DV)
    dec = decide(_info(tmp_path), _profil())
    dovi.set_ffmpeg_dv(None)
    with pytest.raises(ErreurAffichable):
        build_command(dec, _PLAT)


def test_un_p8_1_ne_change_pas_de_chemin(tmp_path):
    dovi.set_ffmpeg_dv(FF_DV)
    dec = decide(_info(tmp_path, dv_profile=8, dv_bl_compat=1),
                 _profil("sdr"))
    cmd = build_command(dec, _PLAT)
    assert cmd[0] != FF_DV and "libplacebo" not in " ".join(cmd)


# ─── Outil ────────────────────────────────────────────────────────────────────

def test_l_outil_dv_se_pose_dans_bin_dv(tmp_path):
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as zf:
        for nom in ("ffmpeg.exe", "ffprobe.exe", "ffplay.exe"):
            zf.writestr(f"ffmpeg-n9.0-latest-win64-gpl-9.0/bin/{nom}", b"x")
    assert preflight.poser("ffmpeg_dv", tampon.getvalue(), tmp_path)
    assert [p.name for p in (tmp_path / "dv").iterdir()] == [preflight._exe("ffmpeg")]
    assert not (tmp_path / preflight._exe("ffmpeg")).exists(), "le principal intact"
    assert preflight.chemin_local("ffmpeg_dv", tmp_path) == tmp_path / "dv" / preflight._exe("ffmpeg")


def test_l_outil_dv_n_est_pas_cherche_dans_le_path(tmp_path, monkeypatch):
    monkeypatch.setattr(preflight.shutil, "which", lambda n: "C:/ffmpeg.exe")
    assert preflight._localiser("ffmpeg_dv", tmp_path) is None


def test_pas_d_offre_si_le_principal_a_libplacebo(monkeypatch):
    statuts = [preflight.ToolStatus("ffmpeg", True, Path("ff")),
               preflight.ToolStatus("ffmpeg_dv", False)]
    monkeypatch.setattr(dovi, "a_libplacebo", lambda f: True)
    assert not preflight._dv_manquant(statuts)
    monkeypatch.setattr(dovi, "a_libplacebo", lambda f: False)
    assert preflight._dv_manquant(statuts)


def test_bin_dv_avant_le_principal(tmp_path, monkeypatch):
    monkeypatch.setattr(dovi, "a_libplacebo", lambda f: True)
    assert dovi.chercher_ffmpeg_dv(tmp_path, "ff") == "ff"
    (tmp_path / "dv").mkdir()
    (tmp_path / "dv" / "ffmpeg.exe").write_bytes(b"x")
    assert dovi.chercher_ffmpeg_dv(tmp_path, "ff") == str(tmp_path / "dv" / "ffmpeg.exe")
    (tmp_path / "dv" / "ffmpeg.exe").unlink()
    monkeypatch.setattr(dovi, "a_libplacebo", lambda f: False)
    assert dovi.chercher_ffmpeg_dv(tmp_path, "ff") is None
