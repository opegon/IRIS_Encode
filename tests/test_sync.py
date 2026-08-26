"""
tests/test_sync.py — Tests unitaires de core/sync.py

Pas de ffmpeg ici : on injecte directement des signaux synthétiques dans la
corrélation. Le décodage audio est couvert par le smoke test.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from core import sync


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _speech(n: int = 20_000, n_events: int = 300, seed: int = 0) -> np.ndarray:
    """Masque binaire « quelqu'un parle » aux positions aléatoires."""
    rng = np.random.default_rng(seed)
    sig = np.zeros(n, dtype=np.float32)
    for start in rng.choice(n - 200, size=n_events, replace=False):
        sig[start:start + int(rng.integers(50, 150))] = 1.0
    return sig


def _shift(sig: np.ndarray, bins: int) -> np.ndarray:
    """Retarde (bins > 0) ou avance (bins < 0) un signal."""
    out = np.zeros_like(sig)
    if bins >= 0:
        out[bins:] = sig[:sig.size - bins]
    else:
        out[:sig.size + bins] = sig[-bins:]
    return out


# ─── Convention de signe ──────────────────────────────────────────────────────

@pytest.mark.parametrize("shift_bins", [0, 50, -50, 200, -200])
def test_lag_is_the_correction_to_apply(shift_bins: int):
    """
    Un signal retardé de +X doit rendre -X : la valeur passée à --sync est
    la correction, pas le décalage observé. Se tromper de signe doublerait
    l'erreur au lieu de la corriger.
    """
    ref = _speech()
    lag, conf, _ = sync._best_lag(ref, _shift(ref, shift_bins))
    assert lag == -shift_bins
    assert conf > 0.95


def test_perfect_match_has_zero_lag():
    ref = _speech()
    lag, conf, salience = sync._best_lag(ref, ref)
    assert lag == 0
    assert conf == pytest.approx(1.0, abs=1e-6)
    assert salience > sync.MIN_SALIENCE


def test_unrelated_signals_have_low_confidence():
    """Deux signaux de parole sans rapport corrèlent un peu — pas assez."""
    _, conf, _ = sync._best_lag(_speech(seed=1), _speech(seed=2))
    assert conf < sync.MIN_CONFIDENCE


def test_empty_signal_is_not_a_crash():
    assert sync._best_lag(np.zeros(0), _speech()) == (0, 0.0, 0.0)
    assert sync._best_lag(_speech(), np.zeros(0)) == (0, 0.0, 0.0)


# ─── Seuil adaptatif ──────────────────────────────────────────────────────────

def test_confidence_floor_decreases_with_events():
    """Le plancher de bruit décroît en 1/√N : le seuil doit suivre."""
    assert sync.confidence_floor(30) > sync.confidence_floor(300)
    assert sync.confidence_floor(300) >= sync.MIN_CONFIDENCE


@pytest.mark.parametrize("n_cues,bogus,vrai", [
    # Valeurs relevées sur parole de synthèse décodée par ffmpeg, à quatre
    # durées. Le seuil doit passer entre les deux à chaque échelle.
    (32,  0.35, 0.90),
    (111, 0.20, 0.89),
    (342, 0.10, 0.89),
    (679, 0.08, 0.89),
])
def test_floor_separates_measured_cases(n_cues: int, bogus: float, vrai: float):
    floor = sync.confidence_floor(n_cues)
    assert bogus < floor <= vrai, f"{n_cues} cues : seuil {floor:.2f}"


def test_confidence_floor_rejects_empty():
    assert sync.confidence_floor(0) == 1.0


# ─── Masque de parole ─────────────────────────────────────────────────────────

def test_speech_mask_is_binary_and_follows_energy():
    env = np.concatenate([np.full(500, -60.0), np.full(500, -10.0)])
    mask = sync._speech_mask(env)
    assert set(np.unique(mask)) <= {0.0, 1.0}
    assert mask[:500].sum() == 0
    assert mask[500:].sum() == 500


def test_speech_mask_on_silent_track():
    """Une piste muette ne doit pas produire un masque plein de 1."""
    assert sync._speech_mask(np.full(1000, -80.0)).sum() == 0


# ─── Lecture des sous-titres ──────────────────────────────────────────────────

_SRT = (
    "1\n00:00:01,500 --> 00:00:03,000\nBonjour.\n\n"
    "2\n00:01:10,250 --> 00:01:12,000\nAu revoir.\n"
)


def test_read_srt_cues(tmp_path: Path):
    p = tmp_path / "s.srt"
    p.write_text(_SRT, encoding="utf-8")
    assert sync.read_cues(p) == [(1.5, 3.0), (70.25, 72.0)]


def test_read_srt_handles_cp1252(tmp_path: Path):
    """Beaucoup de .srt réels ne sont pas en UTF-8 : ne pas planter dessus."""
    p = tmp_path / "s.srt"
    p.write_bytes("1\n00:00:01,000 --> 00:00:02,000\nDéjà vu — ça.\n"
                  .encode("cp1252"))
    assert sync.read_cues(p) == [(1.0, 2.0)]


def test_read_srt_handles_bom(tmp_path: Path):
    p = tmp_path / "s.srt"
    p.write_bytes(b"\xef\xbb\xbf" + _SRT.encode("utf-8"))
    assert len(sync.read_cues(p)) == 2


def test_read_ass_cues(tmp_path: Path):
    p = tmp_path / "s.ass"
    p.write_text(
        "[Events]\n"
        "Format: Layer, Start, End, Style, Text\n"
        "Dialogue: 0,0:00:01.50,0:00:03.00,Default,Bonjour\n"
        "Dialogue: 0,0:01:10.25,0:01:12.00,Default,Au revoir\n",
        encoding="utf-8",
    )
    assert sync.read_cues(p) == [(1.5, 3.0), (70.25, 72.0)]


def test_unreadable_subtitle_returns_no_cues(tmp_path: Path):
    p = tmp_path / "s.srt"
    p.write_text("pas du tout un sous-titre", encoding="utf-8")
    assert sync.read_cues(p) == []


# ─── Masque de répliques ──────────────────────────────────────────────────────

def test_cue_mask_marks_the_right_bins():
    mask = sync._cue_mask([(1.0, 2.0)], n_bins=500)
    assert mask[:100].sum() == 0
    assert mask[100:200].sum() == 100
    assert mask[200:].sum() == 0


def test_cue_mask_clips_out_of_range():
    """Un sous-titre plus long que la vidéo ne doit pas déborder."""
    mask = sync._cue_mask([(-5.0, 1.0), (100.0, 200.0)], n_bins=500)
    assert mask.size == 500
    assert mask[:100].sum() == 100      # le début négatif est tronqué à 0


def test_cue_mask_applies_ratio():
    plain = sync._cue_mask([(10.0, 11.0)], n_bins=5000)
    fast  = sync._cue_mask([(10.0, 11.0)], n_bins=5000, ratio=(1, 2))
    assert int(np.argmax(plain)) == pytest.approx(1000, abs=2)
    assert int(np.argmax(fast))  == pytest.approx(500, abs=2)


# ─── Grille de ratios ─────────────────────────────────────────────────────────

def test_search_finds_stretch():
    """Une dérive linéaire doit être retrouvée sur la grille, pas ignorée."""
    ref = _speech(n=60_000, n_events=600)
    ratio = (24000, 25025)

    lag, found, conf, _ = sync._search(ref, lambda r: sync._rescale(
        sync._rescale(ref, ratio), (r[1], r[0])))
    assert found == ratio, found
    assert conf > 0.9


def test_search_prefers_no_stretch_when_aligned():
    """À alignement parfait, ne pas inventer un étirement."""
    ref = _speech(n=60_000, n_events=600)
    lag, ratio, conf, _ = sync._search(ref, lambda r: sync._rescale(ref, r))
    assert ratio == (1, 1)
    assert lag == 0


# ─── Verdict ──────────────────────────────────────────────────────────────────

def test_result_below_floor_is_refused():
    res = sync._finish(lag=10, ratio=(1, 1), conf=0.05, salience=100.0)
    assert not res.ok
    assert res.delay_ms == 0          # ne pas proposer une valeur qu'on rejette
    assert "aucun décalage" in res.reason


def test_flat_curve_is_refused_even_with_good_correlation():
    res = sync._finish(lag=10, ratio=(1, 1), conf=0.9, salience=1.0)
    assert not res.ok


def test_middling_result_is_accepted_but_flagged():
    res = sync._finish(lag=-245, ratio=(1, 1), conf=0.30, salience=50.0,
                       floor=0.25)
    assert res.ok and not res.sure
    assert "vérifie" in res.reason or "contrôle" in res.reason
    assert "à vérifier" in res.label()


def test_confident_result_is_clean():
    res = sync._finish(lag=-245, ratio=(24000, 25025), conf=0.9, salience=90.0)
    assert res.ok and res.sure
    assert res.delay_ms == -2450
    assert res.stretch == (24000, 25025)
    assert res.reason == ""
