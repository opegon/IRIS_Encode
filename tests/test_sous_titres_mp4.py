"""
tests/test_sous_titres_mp4.py — Un long silence ne fausse plus un sous-titre en MP4.

Le muxeur MP4 de ffmpeg perd les temps d'une piste `mov_text` après un silence
de plus de 2 147,48 s : la VF forcée de *Premier Contact*, qui ouvre à
53 min 51 s, s'affichait dès les premières images. `core/sous_titres.py`
intercale des répliques invisibles ; les commandes lisent alors les
sous-titres dans un Matroska porteur.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from core import dovi
from core import sous_titres as ST
from core.scanner import SubtitleTrack

SRT_FORCE = """1
00:53:51,562 --> 00:53:53,856
<i>IAN MARCHE</i>

2
00:57:18,769 --> 00:57:20,313
<i>SAUVEZ NOTRE ESPÈCE !</i>

3
01:28:54,580 --> 01:28:57,583
Abbott est processus de mort
"""


# ─── Où poser les répliques invisibles ───────────────────────────────────────

def test_aucun_silence_ne_depasse_le_seuil():
    instants = ST.instants_bouche_trou([(3231.562, 3233.856), (3438.769, 3440.313),
                                        (5334.58, 5337.583)])
    assert instants == [1800.0, 3440.313 + 1800.0]


def test_une_piste_dense_n_est_pas_touchee():
    assert ST.instants_bouche_trou([(72.0, 75.8), (82.7, 84.9), (1500.0, 1502.0)]) == []


def test_le_seuil_reste_sous_le_defaut():
    assert ST.SEUIL_S < 2147.48


# ─── Le SRT réécrit ──────────────────────────────────────────────────────────

def test_le_srt_garde_ses_repliques_et_gagne_des_bouche_trous():
    texte, n = ST.combler_srt(SRT_FORCE)
    assert n == 2
    blocs = texte.strip().split("\n\n")
    assert len(blocs) == 5
    assert blocs[0] == f"1\n00:30:00,000 --> 00:30:00,001\n{ST.BOUCHE_TROU}"
    assert blocs[1] == "2\n00:53:51,562 --> 00:53:53,856\n<i>IAN MARCHE</i>"
    assert blocs[3].startswith("4\n01:27:20,313 --> ")


def test_un_srt_sans_long_silence_est_rendu_tel_quel():
    texte = "1\n00:01:12,031 --> 00:01:15,868\nBonjour\n"
    assert ST.combler_srt(texte) == (texte, 0)


def test_le_bouche_trou_n_est_pas_une_espace_simple():
    """Le décodeur SRT de ffmpeg retire une réplique faite d'espaces."""
    assert ST.BOUCHE_TROU == " "  # espace insécable


# ─── Le porteur garde langue, titre et drapeaux ──────────────────────────────

def test_le_porteur_reporte_langue_titre_et_drapeaux(tmp_path):
    pistes = [SubtitleTrack(index=0, codec="subrip", language="fre",
                            title="FR Forced : SRT", forced=True, default=True),
              SubtitleTrack(index=1, codec="subrip", language="fre", title="FR Full")]
    cmd = ST.build_porteur(pistes, [tmp_path / "a.srt", tmp_path / "b.srt"],
                           tmp_path / "p.mkv")
    assert cmd[cmd.index("-disposition:s:0") + 1] == "default+forced"
    assert cmd[cmd.index("-disposition:s:1") + 1] == "0"
    assert "language=fre" in cmd and "title=FR Forced : SRT" in cmd


def test_l_extraction_lit_la_source_une_fois(tmp_path):
    pistes = [SubtitleTrack(index=2, codec="subrip", language="eng"),
              SubtitleTrack(index=5, codec="subrip", language="fre")]
    cmd, chemins = ST.build_extraction(tmp_path / "Film.mkv", pistes, tmp_path)
    assert cmd.count("-i") == 1
    assert ["-map", "0:s:2"] == cmd[cmd.index("0:s:2") - 1:cmd.index("0:s:2") + 1]
    assert len(chemins) == 2


# ─── Les commandes lisent le porteur ─────────────────────────────────────────

def test_le_remux_dv_prend_les_sous_titres_du_porteur(tmp_path):
    cmd = dovi.build_dv_mp4_remux(tmp_path / "i.mkv", tmp_path / "o.mp4",
                                  porteur=tmp_path / "p.mkv")
    assert "1:s?" in cmd and "0:s?" not in cmd


def test_le_retrait_dv_prend_les_sous_titres_du_porteur(tmp_path):
    cmd = dovi.build_strip_mp4(tmp_path / "s.mkv", tmp_path / "o.mp4",
                               sous_titres=[3, 5], porteur=tmp_path / "p.mkv")
    assert "1:s:0" in cmd and "1:s:1" in cmd and "0:s:3" not in cmd


def test_sans_porteur_rien_ne_change(tmp_path):
    cmd = dovi.build_strip_mp4(tmp_path / "s.mkv", tmp_path / "o.mp4", sous_titres=[3])
    assert "0:s:3" in cmd and cmd.count("-i") == 1


def test_l_encodage_prend_les_sous_titres_du_porteur(tmp_path):
    from core.decision import decide
    from core.encoder import build_command
    from core.platform import GPU, OS, PlatformProfile
    from core.profiles import Profile
    from core.scanner import AudioTrack, VideoInfo

    plat = PlatformProfile(os=OS.WINDOWS, gpu=GPU.NVIDIA, hwaccel="cuda",
                           encoder_hevc="hevc_nvenc", encoder_h264="h264_nvenc",
                           encoder_av1="av1_nvenc")
    info = VideoInfo(
        path=tmp_path / "Film.mkv", width=1920, height=1080, bitrate=8_000_000,
        codec="h264", duration=7000.0, frame_count=0, dv_profile=None,
        audio_tracks=[AudioTrack(index=0, codec="ac3", channels=6,
                                 language="fre", title="", bitrate=640_000)],
        subtitle_tracks=[SubtitleTrack(index=0, codec="subrip", language="fre", forced=True),
                         SubtitleTrack(index=1, codec="hdmv_pgs_subtitle", language="fre"),
                         SubtitleTrack(index=2, codec="subrip", language="fre")])
    dec = decide(info, Profile(id="t", data={"bitrate_1080p_kbps": 2000,
                                             "container": "mp4",
                                             "audio_languages": ["fre"]}))
    assert dec.output_container == ".mp4"
    assert [st.index for st in ST.pistes_a_porter(dec)] == [0, 2]
    cmd = build_command(dec, plat, sous_titres_porteur=tmp_path / "p.mkv")
    porteur = cmd.count("-i") - 1
    assert cmd[cmd.index(str(tmp_path / "p.mkv")) - 1] == "-i"
    assert f"{porteur}:s:0" in cmd and f"{porteur}:s:1" in cmd
    assert "0:s:0" not in cmd and "0:s:2" not in cmd


def test_hors_mp4_rien_a_porter(tmp_path):
    dec = type("D", (), {"output_container": ".mkv"})()
    assert ST.pistes_a_porter(dec) == []


# ─── Le défaut lui-même, mesuré avec le ffmpeg du projet ─────────────────────

_FFMPEG = Path(__file__).resolve().parent.parent / "bin" / "ffmpeg.exe"


@pytest.mark.skipif(not _FFMPEG.exists(), reason="ffmpeg du projet absent")
def test_le_mp4_garde_les_temps_une_fois_comble(tmp_path):
    ffprobe = _FFMPEG.with_name("ffprobe.exe")
    srt = tmp_path / "f.srt"
    srt.write_text(ST.combler_srt(SRT_FORCE)[0], encoding="utf-8")
    pistes = [SubtitleTrack(index=0, codec="subrip", language="fre", forced=True)]
    subprocess.run(ST.build_porteur(pistes, [srt], tmp_path / "p.mkv", str(_FFMPEG)),
                   check=True, capture_output=True)
    subprocess.run([str(_FFMPEG), "-v", "error", "-y", "-i", str(tmp_path / "p.mkv"),
                    "-c:s", "mov_text", str(tmp_path / "o.mp4")],
                   check=True, capture_output=True)
    r = subprocess.run([str(ffprobe), "-v", "error", "-show_entries",
                        "packet=pts_time,size", "-of", "csv=p=0", str(tmp_path / "o.mp4")],
                       capture_output=True, text=True, check=True)
    debuts = [float(l.split(",")[0]) for l in r.stdout.split() if int(l.split(",")[1]) > 10]
    assert debuts[0] == pytest.approx(3231.562, abs=0.002)
