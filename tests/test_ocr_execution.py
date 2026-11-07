"""
tests/test_ocr_execution.py — L'OCR pendant le traitement (IE-176).

Chaque PGS retenu est extrait en `.sup`, passé à seconv, et le `.srt` obtenu
remplace la piste dans la sortie, avec sa langue, son nom et ses drapeaux. Une
piste que l'OCR ne lit pas garde son PGS, et le fichier le dit dans ses
avertissements : rien n'est perdu.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import encoder, ocr
from core.decision import VideoAction, decide
from core.profiles import Profile
from core.scanner import AudioTrack, SubtitleTrack, VideoInfo

RACINE = Path(__file__).resolve().parent.parent
_FFMPEG, _FFPROBE = RACINE / "bin" / "ffmpeg.exe", RACINE / "bin" / "ffprobe.exe"
outils = pytest.mark.skipif(not (_FFMPEG.exists() and _FFPROBE.exists()),
                            reason="ffmpeg du projet absent")

SRT = "1\n00:00:01,000 --> 00:00:02,000\nBonjour é\n\n2\n00:00:03,000 --> 00:00:04,000\nAu revoir\n"


def _pgs(index, langue="fre", **kw) -> SubtitleTrack:
    return SubtitleTrack(index=index, codec="hdmv_pgs_subtitle", language=langue, **kw)


def _decision(tmp_path, pistes, source: Path | None = None):
    if source is None:
        source = tmp_path / "Film.1080p.mkv"
        source.write_bytes(b"")
    info = VideoInfo(
        path=source, width=1920, height=1080, bitrate=3_000_000, codec="hevc",
        duration=10.0, frame_count=0, dv_profile=None,
        audio_tracks=[AudioTrack(index=0, codec="ac3", channels=2, language="fre",
                                 title="", bitrate=192_000)],
        subtitle_tracks=list(pistes))
    prof = Profile(id="t", data={"bitrate_1080p_kbps": 5000, "bitrate_720p_kbps": 2000,
                                 "audio_languages": ["fre"]})
    return decide(info, prof)


@pytest.fixture
def seconv(tmp_path):
    exe = tmp_path / "bin" / "seconv" / "seconv.exe"
    ocr.set_seconv(exe)
    yield exe
    ocr.set_seconv(None)


# ─── Commandes ────────────────────────────────────────────────────────────────

def test_extraction_un_sup_par_piste(tmp_path):
    cmd, sups = ocr.build_extraction_pgs(Path("F.mkv"), [_pgs(2), _pgs(5)], tmp_path)
    assert cmd[cmd.index("-i") + 1] == "F.mkv"
    assert cmd.count("-map") == 2 and "0:s:2" in cmd and "0:s:5" in cmd
    assert [p.suffix for p in sups] == [".sup", ".sup"] and sups[0] != sups[1]
    assert cmd[cmd.index("0:s:2") + 2:cmd.index("0:s:2") + 4] == ["copy", str(sups[0])]


def test_commande_seconv(tmp_path):
    exe = tmp_path / "seconv" / "seconv.exe"
    sup = tmp_path / "x.sup"
    cmd = ocr.build_commande_ocr(exe, sup)
    assert cmd[:3] == [str(exe), str(sup), "subrip"]
    assert "--ocr-engine:nocr" in cmd
    assert f"--ocr-db:{exe.parent / ocr.BASE_NOCR}" in cmd
    # La correction des erreurs d'OCR seule, avec les dictionnaires français.
    assert "--fix-common-errors-rules:FixCommonOcrErrors" in cmd
    assert f"--dictionary-folder:{exe.parent / ocr.DICOS}" in cmd
    assert f"--output-folder:{tmp_path}" in cmd
    assert f"--output-filename:{ocr.sortie_ocr(sup).name}" in cmd


def test_repliques_lues(tmp_path):
    p = tmp_path / "a.srt"
    p.write_text(SRT, encoding="utf-8")
    assert ocr.repliques_lues(p) == 2
    p.write_text("1\n00:00:01,000 --> 00:00:02,000\n\n\n", encoding="utf-8")
    assert ocr.repliques_lues(p) == 0
    assert ocr.repliques_lues(tmp_path / "absent.srt") == 0


# ─── L'étape du traitement ────────────────────────────────────────────────────

def _ecran(executer):
    from tui.screens.run import FileState, FileRunStatus
    ecran = SimpleNamespace(
        _statuses=[], app=SimpleNamespace(call_from_thread=lambda f, *a: f(*a),
                                          ffmpeg_path="ffmpeg"),
        _update_row=lambda i: None, _update_ffmpeg_line=lambda t: None,
        _update_cmd_lines=lambda t: None, _executer=executer)
    return ecran, FileState, FileRunStatus


def _simuler(textes: dict[int, str], code_seconv: int = 0, code_ffmpeg: int = 0):
    """`_executer` simulé : ffmpeg écrit les `.sup`, seconv le `.srt` de
    chaque piste (texte vide : un fichier sans réplique)."""
    def executer(index, proc):
        cmd = proc.cmd
        if cmd[0] == "ffmpeg":
            for a in cmd:
                if a.endswith(".sup"):
                    Path(a).write_bytes(b"PG")
            return code_ffmpeg
        sup = Path(cmd[1])
        n = int(sup.stem.rsplit("iris_ocr", 1)[1])
        if n in textes:
            ocr.sortie_ocr(sup).write_text(textes[n], encoding="utf-8")
        return code_seconv
    return executer


def test_ocr_reussi(tmp_path, seconv):
    from tui.screens.run import RunScreen
    dec = _decision(tmp_path, [_pgs(0), _pgs(1, "eng", forced=True)])
    ecran, FileState, FileRunStatus = _ecran(_simuler({0: SRT, 1: SRT}))
    ecran._statuses = [FileRunStatus(decision=dec, state=FileState.RUNNING)]
    faits = RunScreen._ocr_sous_titres(ecran, 0, dec)
    assert sorted(faits) == [0, 1]
    assert all(p.read_text(encoding="utf-8") == SRT for p in faits.values())
    assert ecran._statuses[0].avertissements == []
    assert not list(tmp_path.glob("*.sup")), "les .sup restent"


def test_une_piste_illisible_garde_son_pgs(tmp_path, seconv):
    """seconv rend 0 mais aucune réplique : la piste reste un PGS, le
    fichier continue, l'avertissement le dit."""
    from tui.screens.run import RunScreen
    dec = _decision(tmp_path, [_pgs(0), _pgs(1)])
    ecran, FileState, FileRunStatus = _ecran(_simuler({0: SRT, 1: "\n"}))
    ecran._statuses = [FileRunStatus(decision=dec, state=FileState.RUNNING)]
    faits = RunScreen._ocr_sous_titres(ecran, 0, dec)
    assert sorted(faits) == [0]
    st = ecran._statuses[0]
    assert st.state == FileState.RUNNING
    assert len(st.avertissements) == 1 and "0:s:1" in st.avertissements[0]
    assert not list(tmp_path.glob("*iris_ocr1*")), "le .srt vide reste"


def test_seconv_en_echec(tmp_path, seconv):
    from tui.screens.run import RunScreen
    dec = _decision(tmp_path, [_pgs(0)])
    ecran, FileState, FileRunStatus = _ecran(_simuler({0: SRT}, code_seconv=3))
    ecran._statuses = [FileRunStatus(decision=dec, state=FileState.RUNNING)]
    assert RunScreen._ocr_sous_titres(ecran, 0, dec) == {}
    assert len(ecran._statuses[0].avertissements) == 1
    assert not list(tmp_path.glob("*iris_ocr*"))


def test_extraction_en_echec(tmp_path, seconv):
    from tui.screens.run import RunScreen
    dec = _decision(tmp_path, [_pgs(0)])
    ecran, FileState, FileRunStatus = _ecran(_simuler({0: SRT}, code_ffmpeg=1))
    ecran._statuses = [FileRunStatus(decision=dec, state=FileState.RUNNING)]
    assert RunScreen._ocr_sous_titres(ecran, 0, dec) == {}
    assert len(ecran._statuses[0].avertissements) == 1


def test_sans_pgs_a_lire_rien_n_est_lance(tmp_path, seconv):
    from tui.screens.run import RunScreen
    dec = _decision(tmp_path, [SubtitleTrack(index=0, codec="subrip", language="fre")])

    def executer(index, proc):
        pytest.fail("aucune commande attendue")
    ecran, FileState, FileRunStatus = _ecran(executer)
    ecran._statuses = [FileRunStatus(decision=dec, state=FileState.RUNNING)]
    assert RunScreen._ocr_sous_titres(ecran, 0, dec) == {}


# ─── La sortie ────────────────────────────────────────────────────────────────

def _plateforme():
    from core.platform import GPU, OS, PlatformProfile
    return PlatformProfile(os=OS.WINDOWS, gpu=GPU.NONE, hwaccel=None,
                           encoder_hevc="libx265", encoder_h264="libx264",
                           encoder_av1="libaom-av1")


def test_la_commande_reprend_langue_nom_et_drapeaux(tmp_path, seconv):
    dec = _decision(tmp_path, [_pgs(0, title="FR Forced", forced=True),
                               _pgs(1, title="FR Full", default=True)])
    assert dec.video.action == VideoAction.REMUX
    srt = tmp_path / "a.srt"
    cmd = encoder.build_command(dec, _plateforme(), sous_titres_refaits={1: srt})
    entree = cmd.index(str(srt))
    n_entree = cmd[:entree].count("-i") - 1   # son propre « -i » compris
    assert f"{n_entree}:s:0" in cmd          # la piste 1 vient du .srt
    assert "0:s:0" in cmd                     # la 0 reste le PGS de la source
    paires = list(zip(cmd, cmd[1:]))
    assert ("-metadata:s:s:1", "title=FR Full") in paires
    assert ("-metadata:s:s:1", "language=fre") in paires
    assert ("-disposition:s:1", "default") in paires


@outils
def test_reel_la_sortie_porte_le_srt_nomme(tmp_path, seconv):
    """Bout en bout avec ffmpeg : une source à une piste de sous-titres que la
    décision prend pour un PGS, remplacée par un `.srt` ; la sortie porte le
    texte, la langue, le nom et le drapeau forcé de la piste d'origine."""
    srt0 = tmp_path / "src.srt"
    srt0.write_text(SRT.replace("Bonjour é", "ORIGINAL"), encoding="utf-8")
    source = tmp_path / "Film.1080p.mkv"
    subprocess.run([str(_FFMPEG), "-v", "error", "-f", "lavfi", "-i",
                    "color=black:s=320x240:d=5", "-f", "lavfi", "-i",
                    "anullsrc=r=48000:cl=stereo", "-i", str(srt0), "-t", "5",
                    "-map", "0", "-map", "1", "-map", "2", "-c:v", "libx265",
                    "-c:a", "ac3", "-c:s", "srt", str(source)], check=True)
    dec = _decision(tmp_path, [_pgs(0, title="FR Forced : PGS", forced=True)],
                    source=source)
    ocr_srt = tmp_path / "ocr.srt"
    ocr_srt.write_text(SRT, encoding="utf-8")
    encoder.set_ffmpeg_path(str(_FFMPEG))
    cmd = encoder.build_command(dec, _plateforme(), sous_titres_refaits={0: ocr_srt})
    r = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr[-500:]
    flux = json.loads(subprocess.run(
        [str(_FFPROBE), "-v", "error", "-select_streams", "s", "-show_entries",
         "stream=codec_name:stream_tags=language,title:stream_disposition=forced",
         "-of", "json", str(dec.output_path)],
        capture_output=True, encoding="utf-8").stdout)["streams"]
    assert len(flux) == 1
    assert flux[0]["codec_name"] == "subrip"
    assert flux[0]["tags"]["language"] == "fre"
    assert flux[0]["tags"]["title"] == "FR Forced : PGS"
    assert flux[0]["disposition"]["forced"] == 1
    texte = subprocess.run([str(_FFMPEG), "-v", "error", "-i", str(dec.output_path),
                            "-map", "0:s:0", "-f", "srt", "-"],
                           capture_output=True, encoding="utf-8").stdout
    assert "Bonjour é" in texte and "ORIGINAL" not in texte


def test_l_etape_rejoint_les_srt_refaits(tmp_path, seconv):
    """Ce que la passe principale passe à `build_command` : les WebVTT
    refaits et les PGS lus par l'OCR, ensemble."""
    from tui.screens.run import RunScreen
    dec = _decision(tmp_path, [_pgs(0)])
    ecran, FileState, FileRunStatus = _ecran(_simuler({0: SRT}))
    ecran._statuses = [FileRunStatus(decision=dec, state=FileState.RUNNING)]
    vtt = tmp_path / "vtt.srt"
    ecran._refaire_webvtt = lambda i, d: (True, {7: vtt})
    ecran._ocr_sous_titres = lambda i, d: RunScreen._ocr_sous_titres(ecran, i, d)
    ok, refaits = RunScreen._sous_titres_refaits(ecran, 0, dec)
    assert ok and sorted(refaits) == [0, 7] and refaits[7] == vtt
    ecran._refaire_webvtt = lambda i, d: (False, {})
    assert RunScreen._sous_titres_refaits(ecran, 0, dec) == (False, {})
