"""
tests/test_file_encodage.py — La file d'encodage : progression, causes d'échec,
journal, confirmation de `S` (IE-135 1/3, constats CR-21, CR-53, CR-59, CR-62,
CR-72 de `revue_code_2026-10-08.md`, et l'arbitrage 10 de la même revue).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import encoder

RACINE = Path(__file__).resolve().parent.parent


def _source(rel: str) -> str:
    return (RACINE / rel).read_text(encoding="utf-8")


# ─── CR-21 — les passes audio avancent ───────────────────────────────────────

def test_une_ligne_de_progression_sans_video_est_lue():
    """Mesuré, ffmpeg 8 : `-stats` sous `-loglevel error`, sortie audio seule."""
    p = encoder.parse_progress(
        "size=     176KiB time=00:00:29.97 bitrate=  72.0kbits/s speed=63.1x "
        "elapsed=0:00:00.31", 60)
    assert p is not None and p.percent == pytest.approx(29.97 / 60)
    assert p.frame == 0 and p.speed == pytest.approx(63.1)


def test_la_ligne_video_reste_lue():
    p = encoder.parse_progress(
        "frame= 1200 fps= 48.0 q=28.0 size=  20480KiB time=00:00:50.00 "
        "bitrate=3355.4kbits/s speed=2.00x", 100)
    assert p.frame == 1200 and p.fps == 48.0 and p.percent == 0.5


def test_build_audio_command_demande_les_stats():
    cmd = encoder.build_audio_command(Path("a.mkv"), Path("b.mka"), [])
    assert "-stats" in cmd and cmd.index("-stats") < cmd.index("-i")


# ─── CR-59 — mkvmerge rend 0–100 ─────────────────────────────────────────────

def test_toute_progression_mkvmerge_est_ramenee_a_l_unite():
    texte = _source("tui/screens/run.py")
    for ligne in texte.splitlines():
        if re.search(r"s\.percent\s*=\s*pourcent\b", ligne):
            assert "/ 100" in ligne, ligne.strip()


# ─── CR-62 — la cause d'un échec, à chaque étape ffmpeg ──────────────────────

def test_le_processus_garde_ses_dernieres_lignes():
    proc = encoder.EncoderProcess(["ffmpeg"], 10)
    proc.iter_lines = lambda: iter([f"ligne {n}" for n in range(60)] + [""])
    list(proc.iter_progress())
    assert len(proc.journal) == 40 and proc.journal[-1] == "ligne 59"


def test_la_cause_passe_en_tete():
    from tui.screens.run import RunScreen
    proc = SimpleNamespace(journal=[
        "[out#0/matroska] Error writing trailer: No space left on device",
        "Conversion failed!"])
    resume, detail = RunScreen._cause(proc, "HEVC extraction: code 1",
                                      "Extracting the HEVC stream failed (code 1).")
    assert resume == encoder.diagnostiquer(proc.journal) is not None
    assert detail.startswith(resume) and detail.endswith("(code 1).")


def test_sans_cause_reconnue_le_constat_reste():
    from tui.screens.run import RunScreen
    proc = SimpleNamespace(journal=["Conversion failed!"])
    assert RunScreen._cause(proc, "r", "d") == ("r", "d")


def test_chaque_etape_ffmpeg_secondaire_passe_par_la_cause():
    """Préparation audio, sous-titres, greffe, HEVC, audio ×2, MP4 direct,
    MP4 ×2, RPU, vidéo, DVD."""
    assert _source("tui/screens/run.py").count("self._cause(") >= 12


def test_l_encodeur_est_refuse_avant_de_lire_le_film_pour_le_rpu():
    texte = _source("tui/screens/run.py")
    corps = texte[texte.index("def _encode_dv"):texte.index("def _muxer")]
    assert corps.index("_refuser_encodeur") < corps.index("TuyauRpu(")


# ─── CR-53, CR-72 — un journal lisible d'un bloc ─────────────────────────────

_FRANCAIS = re.compile(r"[àâçéèêëîïôûùœ]|\b(veille|aucune?|échec|rendu|fin de|"
                       r"a rendu|suspendue|tuyau)\b", re.I)


def _messages_de_journal():
    for dossier in ("core", "tui"):
        for f in (RACINE / dossier).rglob("*.py"):
            arbre = ast.parse(f.read_text(encoding="utf-8"))
            for n in ast.walk(arbre):
                if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                        and isinstance(n.func.value, ast.Name)
                        and n.func.value.id in {"log", "_log", "_LOG", "logger"}
                        and n.args and isinstance(n.args[0], ast.Constant)
                        and isinstance(n.args[0].value, str)):
                    yield f"{f.relative_to(RACINE)}:{n.lineno}", n.args[0].value


def test_les_journaux_sont_en_anglais():
    francais = [(o, m) for o, m in _messages_de_journal() if _FRANCAIS.search(m)]
    assert not francais, francais


def test_le_journal_s_ecrit_en_utf8():
    assert 'encoding="utf-8"' in _source("tui/app.py").split("def _setup_logging")[1][:900]


def test_le_motif_de_la_demande_d_alimentation_est_en_anglais():
    from tui.app import IrisEncodeApp
    assert set(IrisEncodeApp._NATURES.values()) <= {
        "encoding", "mux", "join", "measurement", "resync"}


# ─── Arbitrage 10 — `S` demande confirmation ─────────────────────────────────

def _ecran(index=0):
    from tui.screens.run import FileState
    pousses = []
    statut = SimpleNamespace(state=FileState.RUNNING, last_line="")
    ecran = SimpleNamespace(
        _done=False, _process=SimpleNamespace(), _mux=None, _started=True,
        _current_idx=index, _statuses=[statut, statut],
        app=SimpleNamespace(push_screen=lambda ecr, rappel: pousses.append((ecr, rappel))),
        notify=lambda *a, **k: None, passes=[])
    ecran._passer_courant = lambda: ecran.passes.append(ecran._current_idx)
    return ecran, pousses


def test_s_demande_confirmation_avant_d_abandonner():
    from tui.screens.confirm import ConfirmModal
    from tui.screens.run import RunScreen
    ecran, pousses = _ecran()
    RunScreen.action_skip_current(ecran)
    assert ecran.passes == [], "rien n'est arrêté avant la réponse"
    (modale, rappel), = pousses
    assert isinstance(modale, ConfirmModal)
    rappel(False)
    assert ecran.passes == []
    rappel(True)
    assert ecran.passes == [0]


def test_un_oui_tardif_ne_touche_pas_le_fichier_suivant():
    from tui.screens.run import RunScreen
    ecran, pousses = _ecran()
    RunScreen.action_skip_current(ecran)
    ecran._current_idx = 1                 # le fichier a fini pendant la question
    pousses[0][1](True)
    assert ecran.passes == []
