"""
tests/test_webvtt_brut.py — Sous-titres WebVTT que ffmpeg ne lit pas.

mkvmerge range un WebVTT sous `S_TEXT/WEBVTT`, que ffmpeg 8.1 ne connaît
pas : la piste sort en `codec_name=unknown`, et la préparation des
sous-titres échouait (« no decoder found for: none »). Constaté le
2026-11-01 sur la cérémonie de clôture des JO 2024, 3663 répliques. Le SRT se
reconstruit depuis les paquets que ffprobe sait lire.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import encoder, muxer, scanner
from core import sous_titres as ST
from core.scanner import SubtitleTrack

RACINE = Path(__file__).resolve().parent.parent
from tests.outils_reels import outil  # noqa: E402

_FFMPEG, _FFPROBE, _MKVMERGE = outil("ffmpeg"), outil("ffprobe"), outil("mkvmerge")
outils = pytest.mark.skipif(
    not all(p.exists() for p in (_FFMPEG, _FFPROBE, _MKVMERGE)),
    reason="outils du projet absents")

# Relevé sur le fichier réel : la dernière ligne est complétée d'espaces.
_DUMP = ("\n00000000: 3c63 2e77 6869 7465 3e50 6c61 6365 20c3  <c.white>Place .\n"
         "00000010: a020 6c61 2063 c3a9 72c3 a96d 6f6e 6965  . la c..r..monie\n"
         "00000020: 2064 6520 636c c3b4 7475 7265 2e3c 2f63   de cl..ture.</c\n"
         "00000030: 3e                                       >\n")


def test_octets_du_hexdump_de_ffprobe():
    assert ST.octets_hexdump(_DUMP).decode("utf-8") == (
        "<c.white>Place à la cérémonie de clôture.</c>")


def test_texte_webvtt_en_srt():
    assert ST.texte_webvtt_vers_srt(
        "<c.white>- L.Luyat: <i>Oui</i> &amp; non</c>\n<v Bob>Fin</v>") == (
        "- L.Luyat: <i>Oui</i> & non\nFin")
    assert ST.texte_webvtt_vers_srt("A<00:00:01.500>B&nbsp;C") == "AB C"


def _paquet(debut, texte, duree=None):
    hexa = texte.encode("utf-8").hex()
    groupes = " ".join(hexa[i:i + 4] for i in range(0, len(hexa), 4))
    pq = {"pts_time": f"{debut:.6f}",
          "data": f"\n00000000: {groupes:<39}  x\n"}
    if duree is not None:
        pq["duration_time"] = f"{duree:.6f}"
    return pq


def test_srt_depuis_les_paquets():
    texte, n = ST.srt_depuis_paquets([
        _paquet(15.56, "Bonjour", 0.44),
        _paquet(16.0, "<c.white></c>", 1.0),          # vide : écarté
        _paquet(19.0, "Sans durée"),                  # finit au suivant
        _paquet(22.5, "Fin", 2.0),
    ])
    assert n == 3
    assert texte == ("1\n00:00:15,560 --> 00:00:16,000\nBonjour\n\n"
                     "2\n00:00:19,000 --> 00:00:22,500\nSans durée\n\n"
                     "3\n00:00:22,500 --> 00:00:24,500\nFin\n")


def test_le_scan_reconnait_le_webvtt_brut(monkeypatch):
    pistes = [SubtitleTrack(index=0, codec="unknown", language="fre"),
              SubtitleTrack(index=1, codec="unknown", language="eng"),
              SubtitleTrack(index=2, codec="subrip", language="fre")]
    entetes = {"s:0": "\n00000000: 5745 4256 5454 0a                        WEBVTT.\n",
               "s:1": "\n00000000: 0000 0000                                ....\n"}
    appels = []

    def sonde(args, outil=None):
        appels.append(args[1])
        return {"streams": [{"extradata": entetes[args[1]]}]}
    monkeypatch.setattr(scanner, "_ffprobe_json", sonde)
    scanner._reconnaitre_webvtt_brut(Path("x.mkv"), pistes)
    assert [(p.codec, p.brut) for p in pistes] == [
        ("webvtt", True), ("unknown", False), ("subrip", False)]
    assert appels == ["s:0", "s:1"]           # une piste connue n'est pas sondée


def test_l_extraction_laisse_le_brut_de_cote(tmp_path):
    brut = SubtitleTrack(index=0, codec="webvtt", language="fre", brut=True)
    srt = SubtitleTrack(index=1, codec="subrip", language="eng")
    cmd, chemins = ST.build_extraction(tmp_path / "f.mkv", [brut, srt], tmp_path)
    assert len(chemins) == 2
    assert "0:s:0" not in cmd and "0:s:1" in cmd
    cmd, chemins = ST.build_extraction(tmp_path / "f.mkv", [brut], tmp_path)
    assert cmd is None and len(chemins) == 1


# ─── De bout en bout : un WebVTT muxé par mkvmerge ───────────────────────────

VTT = ("WEBVTT\n\n00:00:00.200 --> 00:00:00.900\n<c.white>Bonjour é</c>\n\n"
       "00:00:01.000 --> 00:00:01.800\nAu revoir &amp; merci\n")


@pytest.fixture
def source_webvtt(tmp_path):
    encoder.set_ffmpeg_path(str(_FFMPEG))
    scanner.set_ffprobe_path(str(_FFPROBE))
    muxer.set_mkvmerge_path(str(_MKVMERGE))
    av = tmp_path / "av.mkv"
    subprocess.run([str(_FFMPEG), "-y", "-loglevel", "error",
                    "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=2",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
                    str(av)], check=True, capture_output=True)
    vtt = tmp_path / "st.vtt"
    vtt.write_text(VTT, encoding="utf-8")
    source = tmp_path / "film.mkv"
    subprocess.run([str(_MKVMERGE), "-q", "-o", str(source), str(av),
                    "--language", "0:fre", str(vtt)], capture_output=True)
    assert source.exists()
    return source


def _decision(source: Path, conteneur: str):
    from core.decision import VideoAction, decide, force_skip_to_encode
    from core.profiles import Profile
    prof = Profile(id="t", data={
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps": 8000, "audio_languages": ["fre"],
        "subtitle_languages": ["fre"], "audio_copy_compatible": True,
        "container": conteneur})
    dec = force_skip_to_encode(decide(scanner.scan(source), prof))
    dec.video.action = VideoAction.ENCODE_H264
    return dec


def _ecran():
    from tui.screens.run import FileState
    statut = SimpleNamespace(state=FileState.RUNNING, error_msg="", last_line="",
                             percent=0)
    ecran = SimpleNamespace(
        _statuses=[statut], _process=None, _abandon=False,
        app=SimpleNamespace(call_from_thread=lambda f, *a: f(*a),
                            ffmpeg_path=str(_FFMPEG)),
        _update_row=lambda i: None, _update_ffmpeg_line=lambda t: None,
        _update_cmd_lines=lambda t: None)
    ecran._demarrer = lambda proc: proc.start()
    from tui.screens.run import RunScreen
    ecran._cause = RunScreen._cause
    return ecran, statut


def _sous_titres_de(sortie: Path) -> tuple[str, str]:
    """(codec, texte en SRT) de la première piste de sous-titres."""
    codec = json.loads(subprocess.run(
        [str(_FFPROBE), "-v", "error", "-select_streams", "s:0",
         "-show_entries", "stream=codec_name", "-of", "json", str(sortie)],
        capture_output=True, encoding="utf-8").stdout)["streams"][0]["codec_name"]
    texte = subprocess.run(
        [str(_FFMPEG), "-v", "error", "-i", str(sortie), "-map", "0:s:0",
         "-f", "srt", "-"], capture_output=True, encoding="utf-8").stdout
    return codec, texte


@outils
def test_le_mkv_de_mkvmerge_est_vu_brut(source_webvtt):
    st = scanner.scan(source_webvtt).subtitle_tracks
    assert [(p.codec, p.brut) for p in st] == [("webvtt", True)]


@outils
@pytest.mark.parametrize("conteneur,codec", [("mp4", "mov_text"),
                                             ("mkv", "subrip")])
def test_la_sortie_garde_les_sous_titres(source_webvtt, tmp_path, conteneur, codec):
    from tui.screens.run import FileState, RunScreen
    dec = _decision(source_webvtt, conteneur)
    assert dec.output_container == f".{conteneur}"
    ecran, statut = _ecran()
    ok, porteur = RunScreen._porter_sous_titres(ecran, 0, dec)
    assert ok, statut.last_line
    ok, refaits = RunScreen._refaire_webvtt(ecran, 0, dec)
    assert ok, statut.last_line
    # MP4 : le porteur ; MKV : un `.srt` refait. Jamais les deux.
    assert (porteur is not None) == (conteneur == "mp4")
    assert bool(refaits) == (conteneur == "mkv")
    cmd = encoder.build_command(dec, _plateforme(), sous_titres_porteur=porteur,
                                sous_titres_refaits=refaits)
    r = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr[-500:]
    assert statut.state == FileState.RUNNING
    obtenu, texte = _sous_titres_de(dec.output_path)
    assert obtenu == codec
    assert "Bonjour é" in texte and "Au revoir & merci" in texte
    assert "<c" not in texte


def _plateforme():
    from core.platform import GPU, OS, PlatformProfile
    return PlatformProfile(os=OS.WINDOWS, gpu=GPU.NONE, hwaccel=None,
                           encoder_hevc="libx265", encoder_h264="libx264",
                           encoder_av1="libaom-av1")
