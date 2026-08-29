"""
tests/test_sync.py — Tests unitaires de core/sync.py

Pas de ffmpeg ici : on injecte directement des signaux synthétiques dans la
corrélation. Le décodage audio est couvert par le smoke test.
"""
from __future__ import annotations

from pathlib import Path
from unittest import mock

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


# ─── Recoupement par tiers ────────────────────────────────────────────────────

def test_cross_validation_confirms_a_real_shift():
    """
    Un vrai décalage tient sur chaque tiers du film pris isolément.

    C'est le critère qui prime : mesuré sur un long métrage réel, un
    alignement juste sortait à 0.20 de corrélation — sous le seuil — avec
    trois tiers concordants à 60 ms.
    """
    ref = _speech(n=60_000, n_events=900)
    sig = _shift(ref, 400)
    agreed, dispersion = sync._cross_validate(ref, sig, -400)
    assert agreed is True
    assert dispersion <= sync.CROSS_TOLERANCE_MS


def test_cross_validation_rejects_noise():
    """Deux signaux sans rapport donnent des tiers qui partent dans tous les sens."""
    ref = _speech(n=60_000, n_events=900, seed=1)
    sig = _speech(n=60_000, n_events=900, seed=2)
    lag, _, _ = sync._best_lag(ref, sig)
    agreed, dispersion = sync._cross_validate(ref, sig, lag)
    assert agreed is False
    assert dispersion > sync.CROSS_TOLERANCE_MS


def test_cross_validation_abstains_on_short_files():
    """Sous une minute par tiers, le recoupement ne prouve rien : il s'abstient."""
    ref = _speech(n=3_000, n_events=40)
    agreed, dispersion = sync._cross_validate(ref, _shift(ref, 20), -20)
    assert agreed is None
    assert dispersion == 0


def test_agreement_beats_a_low_correlation():
    """Le cas du film réel : corrélation sous le seuil, tiers concordants."""
    res = sync._finish(lag=3968, ratio=(1, 1), conf=0.20, salience=37.0,
                       floor=0.25, n_events=1327, speech_ratio=0.56,
                       agreed=True, dispersion_ms=60)
    assert res.ok and res.sure
    assert res.delay_ms == 39680
    assert "concordants" in res.report()


def test_disagreement_beats_a_high_correlation():
    """À l'inverse, des tiers discordants doivent l'emporter sur un bon score."""
    res = sync._finish(lag=100, ratio=(1, 1), conf=0.85, salience=200.0,
                       floor=0.25, n_events=500, speech_ratio=0.40,
                       agreed=False, dispersion_ms=94_460)
    assert not res.ok
    assert "discordants" in res.report()


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


def test_count_speech_blocks():
    """Côté audio, les « repères » sont les plages de parole."""
    mask = np.zeros(1000, dtype=np.float32)
    mask[100:200] = 1.0
    mask[400:450] = 1.0
    mask[900:]    = 1.0
    assert sync._count_speech_blocks(mask) == 3
    assert sync._count_speech_blocks(np.zeros(100, dtype=np.float32)) == 0
    assert sync._count_speech_blocks(np.ones(100, dtype=np.float32)) == 1
    assert sync._count_speech_blocks(np.zeros(0, dtype=np.float32)) == 0


def test_speech_mask_on_silent_track():
    """Une piste muette ne doit pas produire un masque plein de 1."""
    assert sync._speech_mask(np.full(1000, -80.0)).sum() == 0


def test_speech_mask_follows_a_rising_floor():
    """
    La bande-son d'un film monte et descend : un seuil global calé sur les
    passages calmes sature dès que la musique entre, et le masque ne veut
    plus rien dire dans la seconde moitié.
    """
    n = 12_000
    env = np.linspace(-60.0, -20.0, n)          # plancher qui monte
    for start in range(500, n - 500, 900):      # répliques au-dessus du plancher
        env[start:start + 200] += 15.0

    mask = sync._speech_mask(env)
    debut, fin = mask[:n // 2].mean(), mask[n // 2:].mean()

    assert 0.05 < debut < 0.5, debut
    assert 0.05 < fin < 0.5, fin
    # Même densité des deux côtés : le seuil a suivi le plancher
    assert abs(debut - fin) < 0.15, (debut, fin)


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
    res = sync._finish(lag=10, ratio=(1, 1), conf=0.05, salience=100.0,
                       n_events=400, speech_ratio=0.4)
    assert not res.ok
    assert res.delay_ms == 0          # ne pas proposer une valeur qu'on rejette
    # …mais le candidat reste consultable pour comprendre l'échec
    assert res.best_delay_ms == 100
    assert res.floor > 0


@pytest.mark.parametrize("n_events,speech,attendu", [
    (5,   0.40, "repères"),          # sous-titre trop court ou mal lu
    (400, 0.95, "bande-son"),        # VAD saturé par la musique
    (400, 0.01, "piste audio"),      # mauvaise piste sélectionnée
    (400, 0.40, "montage"),          # tout va bien, mais rien ne s'aligne
])
def test_diagnosis_names_the_likely_cause(n_events, speech, attendu):
    """Un refus doit être analysable, pas un simple « non »."""
    res = sync._finish(lag=10, ratio=(1, 1), conf=0.05, salience=100.0,
                       n_events=n_events, speech_ratio=speech)
    assert not res.ok
    assert attendu in res.diagnosis()


def test_report_carries_the_numbers():
    res = sync._finish(lag=-245, ratio=(1, 1), conf=0.62, salience=90.0,
                       floor=0.25, n_events=342, speech_ratio=0.41)
    texte = res.report()
    assert "0.62" in texte and "0.25" in texte
    assert "342" in texte and "41" in texte
    assert len(texte.splitlines()) == 2


def test_report_of_a_failure_shows_the_candidate():
    res = sync._finish(lag=-5499, ratio=(1, 1), conf=0.10, salience=100.0,
                       floor=0.25, n_events=269, speech_ratio=0.72)
    texte = res.report()
    assert "refusée" in texte
    assert "-54990" in texte          # le candidat trouvé reste visible


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


# ─── Découpage en plages ──────────────────────────────────────────────────────

def _with_inserts(sig: np.ndarray, cuts: list[int],
                  gap_bins: int = 200) -> np.ndarray:
    """
    Réinjecte `gap_bins` de silence à chaque position de `cuts`.

    C'est le montage broadcast face au montage streaming : même contenu, des
    noirs de coupure publicitaire en plus, et tout ce qui suit décalé d'autant.
    """
    parts, prev = [], 0
    for c in cuts:
        parts.append(sig[prev:c])
        parts.append(np.zeros(gap_bins, dtype=np.float32))
        prev = c
    parts.append(sig[prev:])
    return np.concatenate(parts)


def test_segments_find_each_insertion():
    ref  = _speech(n=240_000, n_events=3_000, seed=1)
    cuts = [40_000, 90_000, 140_000, 180_000, 215_000]
    segs = sync._segment_lags(ref, _with_inserts(ref, cuts))

    assert len(segs) == len(cuts) + 1
    # Un palier de 2 s de plus à chaque coupure franchie
    assert [s.delay_ms for s in segs] == [0, -2000, -4000, -6000, -8000, -10000]
    # Frontières retrouvées au pas de balayage près
    trouvees = [s.end_s for s in segs[:-1]]
    for attendue, obtenue in zip([c * sync.BIN_MS / 1000 for c in cuts], trouvees):
        assert abs(obtenue - attendue) <= 2.0


def test_constant_delay_yields_no_segments():
    """Un décalage qui tient partout n'a aucune plage à exhiber."""
    ref = _speech(n=240_000, n_events=3_000, seed=2)
    assert sync._segment_lags(ref, _shift(ref, 300)) == []


def test_noise_yields_no_segments():
    ref = _speech(n=240_000, n_events=3_000, seed=3)
    sig = _speech(n=240_000, n_events=3_000, seed=4)
    # Du bruit n'a pas de paliers : mieux vaut ne rien montrer que d'exhiber
    # un découpage inventé.
    assert sync._segment_lags(ref, sig) == []


def test_segments_stay_ordered():
    """Aucune plage ne peut finir avant de commencer."""
    ref  = _speech(n=240_000, n_events=3_000, seed=7)
    cuts = [30_000, 35_000, 120_000, 125_000, 200_000]
    for seg in sync._segment_lags(ref, _with_inserts(ref, cuts)):
        assert seg.end_s > seg.start_s, seg.label()


def test_short_file_abstains():
    ref = _speech(n=8_000, n_events=100, seed=5)
    assert sync._segment_lags(ref, _with_inserts(ref, [4_000])) == []


def test_segments_explain_the_refusal():
    """Le refus nomme le montage plutôt que de rester sur l'hypothèse générique."""
    segs = [sync.Segment(0.0, 500.0, 0, 0.7),
            sync.Segment(500.0, 1000.0, 2000, 0.6)]
    res = sync._finish(lag=200, ratio=(1, 1), conf=0.36, salience=50.0,
                       n_events=12_499, speech_ratio=0.55,
                       agreed=False, dispersion_ms=6010, segments=segs)
    assert not res.ok
    assert "2 plages" in res.reason
    assert "montage" in res.reason
    # Le compte rendu tient dans les 3 lignes du bandeau et renvoie vers 's'
    rapport = res.report()
    assert len(rapport.splitlines()) == 3
    assert "+2000" in rapport and "'s'" in rapport


def test_no_segments_keeps_the_previous_diagnosis():
    res = sync._finish(lag=200, ratio=(1, 1), conf=0.1, salience=1.0,
                       n_events=500, speech_ratio=0.35, agreed=False)
    assert not res.ok and res.segments == []
    assert "plages" not in res.reason


# ─── Sous-titres embarqués ────────────────────────────────────────────────────

def test_extract_subtitle_asks_ffmpeg_for_the_right_track(tmp_path: Path):
    cible = tmp_path / "donneur_2_[sync].srt"

    def _fake_run(cmd, **kw):
        Path(cmd[-1]).write_text("1\n00:00:01,000 --> 00:00:02,000\nX\n",
                                 encoding="utf-8")
        return mock.Mock(returncode=0)

    with mock.patch("core.sync.tempfile.gettempdir", return_value=str(tmp_path)), \
         mock.patch("core.sync.subprocess.run", side_effect=_fake_run) as run:
        out = sync.extract_subtitle(tmp_path / "donneur.mkv", 2)

    assert out == cible
    cmd = run.call_args[0][0]
    assert "-map" in cmd and cmd[cmd.index("-map") + 1] == "0:s:2"
    assert cmd[cmd.index("-c:s") + 1] == "srt"


def test_extract_subtitle_returns_none_on_failure(tmp_path: Path):
    """Un sous-titre image fait échouer ffmpeg : pas de fichier, pas de mesure."""
    with mock.patch("core.sync.tempfile.gettempdir", return_value=str(tmp_path)), \
         mock.patch("core.sync.subprocess.run",
                    return_value=mock.Mock(returncode=1)):
        assert sync.extract_subtitle(tmp_path / "donneur.mkv", 0) is None


def test_measure_subtitle_refuses_an_image_track(tmp_path: Path):
    video = tmp_path / "film.mkv"
    with mock.patch("core.sync.extract_subtitle", return_value=None):
        res = sync.measure_subtitle(video, tmp_path / "donneur.mkv",
                                    donor_track=0)
    assert not res.ok
    assert "image" in res.reason


def test_measure_subtitle_needs_a_track_index_for_a_container(tmp_path: Path):
    res = sync.measure_subtitle(tmp_path / "film.mkv", tmp_path / "donneur.mkv")
    assert not res.ok
    assert "embarquée" in res.reason


def test_measure_subtitle_reads_a_plain_file_without_extracting(tmp_path: Path):
    """Un .srt nu ne doit jamais déclencher d'extraction."""
    srt = tmp_path / "film.fr.srt"
    srt.write_text("1\n00:00:01,000 --> 00:00:02,000\nX\n", encoding="utf-8")
    with mock.patch("core.sync.extract_subtitle") as extract, \
         mock.patch("core.sync._decode_envelope",
                    return_value=np.zeros(0, dtype=np.float32)):
        sync.measure_subtitle(tmp_path / "film.mkv", srt)
    extract.assert_not_called()


# ─── Correction d'un sous-titre par plages ────────────────────────────────────

_SEGS = [
    sync.Segment(0.0,    600.0,  0,    0.8),
    sync.Segment(600.0,  1200.0, 2000, 0.8),
    sync.Segment(1200.0, 1800.0, 4000, 0.8),
]


def test_delay_at_picks_the_right_segment():
    assert sync.delay_at(_SEGS, 0.0)    == 0
    assert sync.delay_at(_SEGS, 599.9)  == 0
    assert sync.delay_at(_SEGS, 600.0)  == 2000
    assert sync.delay_at(_SEGS, 1500.0) == 4000


def test_delay_at_extends_the_last_segment():
    """Au-delà de la dernière plage — générique — le montage ne change plus."""
    assert sync.delay_at(_SEGS, 9_999.0) == 4000


def test_delay_at_without_segments_is_zero():
    assert sync.delay_at([], 42.0) == 0


def test_shift_srt_moves_each_cue_by_its_segment(tmp_path: Path):
    src = tmp_path / "vf.srt"
    src.write_text(
        "1\n00:00:10,000 --> 00:00:12,000\nAvant la premiere coupure\n\n"
        "2\n00:10:30,000 --> 00:10:32,500\nApres la premiere\n\n"
        "3\n00:25:00,000 --> 00:25:01,000\nApres la seconde\n",
        encoding="utf-8",
    )
    out = sync.shift_srt(src, _SEGS, tmp_path / "corrige.srt")
    cues = sync.read_cues(out)

    assert cues[0] == (10.0, 12.0)          # plage à +0
    assert cues[1] == (632.0, 634.5)        # 630 s + 2 s
    assert cues[2] == (1504.0, 1505.0)      # 1500 s + 4 s


def test_shift_srt_preserves_the_text(tmp_path: Path):
    """Seuls les horodatages bougent : le reste du fichier est intouché."""
    src = tmp_path / "vf.srt"
    src.write_text(
        "1\n00:00:10,000 --> 00:00:12,000\n<i>Ça alors — 100 %</i>\n",
        encoding="utf-8",
    )
    out = sync.shift_srt(src, _SEGS, tmp_path / "corrige.srt")
    contenu = out.read_text(encoding="utf-8")
    assert "<i>Ça alors — 100 %</i>" in contenu
    assert contenu.startswith("1\n")


def test_shift_srt_reads_a_cp1252_source(tmp_path: Path):
    src = tmp_path / "vf.srt"
    src.write_bytes(
        "1\n00:10:30,000 --> 00:10:32,000\nDéjà vu\n".encode("cp1252"))
    out = sync.shift_srt(src, _SEGS, tmp_path / "corrige.srt")
    assert "Déjà vu" in out.read_text(encoding="utf-8")
    assert sync.read_cues(out)[0][0] == 632.0


# ─── Correction d'une piste audio ─────────────────────────────────────────────

def _env_with_silence(n: int, trous: list[int], largeur: int = 300) -> np.ndarray:
    """Enveloppe bruyante, creusée de silences aux positions données."""
    env = np.full(n, 1.0, dtype=np.float32)
    for t in trous:
        env[t:t + largeur] = 0.0
    return env


def test_find_silence_snaps_to_the_gap():
    env = _env_with_silence(20_000, [9_000])
    # Frontière estimée 8 s trop tôt : on doit quand même tomber sur le trou
    debut = sync.find_silence(env, center=8_200, need=200, search=1_500)
    assert debut is not None
    milieu = 9_000 + 300 // 2
    assert abs(debut - (milieu - 100)) <= 5


def test_find_silence_gives_up_when_there_is_none():
    env = np.full(20_000, 1.0, dtype=np.float32)
    assert sync.find_silence(env, center=10_000, need=200, search=1_500) is None


def test_plan_inserts_converts_to_donor_time():
    """La plage est en temps cible : le donneur s'en déduit moins le décalage."""
    segs = [sync.Segment(0.0, 500.0, 0, 0.8),
            sync.Segment(500.0, 1000.0, 2000, 0.8)]
    # Silence place a 498 s cote donneur (500 s - 2 s de decalage a venir : 0)
    env = _env_with_silence(150_000, [49_800], largeur=400)
    inserts, approx = sync.plan_inserts(env, segs)
    assert approx == []
    assert len(inserts) == 1
    position, duree = inserts[0]
    assert duree == 2.0
    assert abs(position - 499.0) < 1.5


def test_plan_inserts_falls_back_without_silence():
    """Sans silence, on pose quand même : allonger n'efface jamais de contenu."""
    segs = [sync.Segment(0.0, 500.0, 0, 0.8),
            sync.Segment(500.0, 1000.0, 2000, 0.8)]
    env = np.full(150_000, 1.0, dtype=np.float32)
    inserts, approx = sync.plan_inserts(env, segs)
    assert len(inserts) == 1
    assert approx and "aucun silence" in approx[0]


def test_plan_inserts_refuses_a_negative_jump():
    """Un saut négatif demanderait de retirer du contenu : on s'abstient."""
    segs = [sync.Segment(0.0, 500.0, 2000, 0.8),
            sync.Segment(500.0, 1000.0, 0, 0.8)]
    env = np.full(150_000, 1.0, dtype=np.float32)
    inserts, approx = sync.plan_inserts(env, segs)
    assert inserts == []
    assert approx and "négatif" in approx[0]


def test_retime_command_alternates_content_and_silence():
    cmd = sync.build_retime_command(Path("vf.mkv"), 1,
                                    [(100.0, 2.0), (500.0, 2.0)],
                                    Path("out.mka"))
    fc = cmd[cmd.index("-filter_complex") + 1]
    # 3 morceaux de contenu + 2 silences intercalés
    assert fc.count("atrim") == 5
    assert "concat=n=5:v=0:a=1[out]" in fc
    assert "[k0][g0][k1][g1][k2]concat" in fc
    # Le silence vient de la piste elle-même, pas d'un anullsrc : concat exige
    # une fréquence et une disposition de canaux identiques partout.
    assert "anullsrc" not in fc
    assert fc.count("volume=0") == 2
    assert "[0:a:1]" in fc


def test_retime_command_needs_something_to_do():
    with pytest.raises(ValueError):
        sync.build_retime_command(Path("vf.mkv"), 0, [], Path("out.mka"))


# ─── Arbitrage entre ratios ───────────────────────────────────────────────────

def test_le_ratio_se_choisit_a_la_correlation_pas_a_la_saillance(monkeypatch):
    """
    La saillance ne se compare pas d'un ratio à l'autre.

    `_rescale` change la longueur du signal ; la médiane et le MAD qui
    normalisent la saillance sont alors calculés sur une courbe de corrélation
    d'une autre taille, donc sur une autre échelle.

    Les valeurs ci-dessous sont celles mesurées sur *The Fall* S02E06, VO 1080p
    contre VF 720p. Les deux pistes sont alignées à dix millisecondes près, et
    le classement par saillance seule élisait le ratio PAL sur une corrélation
    de 0.26 — du bruit — à cent soixante secondes de la vérité.
    """
    mesures = {
        (1, 1):           (-1,     0.8297,  546.39),
        (24000, 25025):   (16028,  0.2550, 1008.38),
        (25025, 24000):   (-16753, 0.2572,  101.89),
        (24, 25):         (15922,  0.2638,  951.56),
        (25, 24):         (-16602, 0.2665,  105.92),
    }
    ordre = list(mesures)
    monkeypatch.setattr(sync, "RATIO_GRID", ordre)
    monkeypatch.setattr(sync, "_best_lag",
                        lambda ref, sig: mesures[sig])

    lag, ratio, conf, _ = sync._search(np.zeros(10), lambda r: r)
    assert ratio == (1, 1), f"ratio élu : {ratio}"
    assert lag == -1
    assert conf == pytest.approx(0.8297)


def test_la_saillance_departage_a_correlation_comparable(monkeypatch):
    """
    Elle garde son rôle : à corrélation voisine, c'est le pic net qui tranche.

    C'est la raison d'être du classement d'origine — un mauvais alignement
    garde une corrélation moyenne honorable tout en n'ayant plus aucun pic.
    """
    mesures = {
        (1, 1):         (100, 0.80, 12.0),
        (24, 25):       (200, 0.78, 90.0),   # corrélation voisine, pic bien plus net
        (25, 24):       (300, 0.40, 99.0),   # saillance maximale, mais hors bande
    }
    monkeypatch.setattr(sync, "RATIO_GRID", list(mesures))
    monkeypatch.setattr(sync, "_best_lag", lambda ref, sig: mesures[sig])

    lag, ratio, _, _ = sync._search(np.zeros(10), lambda r: r)
    assert ratio == (24, 25)
    assert lag == 200
