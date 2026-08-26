"""
core/sync.py — Mesure automatique du décalage d'une piste externe.

Deux problèmes distincts, un même noyau :

  audio ↔ audio    on corrèle les deux enveloppes d'énergie. Signal dense,
                   même contenu : la corrélation est directe.
  sous-titre ↔ vidéo
                   il n'y a rien à corréler entre du texte et une forme
                   d'onde. On ramène les deux à un signal binaire « quelqu'un
                   parle » : les cues d'un côté, un VAD par énergie de l'autre.

Dans les deux cas, la corrélation croisée se fait par FFT sur des bins de
10 ms, et le facteur d'étirement est cherché sur une grille de ratios : une
dérive PAL étale complètement le pic, il faut compenser avant de mesurer.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np

# Rapporte l'avancement entre 0 et 1
Progress = Callable[[float], None]

# Part de la barre consacrée au décodage : c'est la phase longue, la
# corrélation ne prend qu'une poignée de FFT.
DECODE_SHARE = 0.85

# Résolution temporelle de l'analyse
BIN_MS       = 10
_SAMPLE_RATE = 16_000
_BIN_SAMPLES = _SAMPLE_RATE * BIN_MS // 1000     # 160 échantillons
_MASK_BLOCK  = 3_000                             # 30 s : fenêtre du seuil local

# Ratios d'étirement plausibles (source PAL accélérée, conversions cinéma).
# 1/1 en premier : à confiance égale, on ne complique pas.
RATIO_GRID: list[tuple[int, int]] = [
    (1, 1),
    (24000, 25025),   # PAL → film
    (25025, 24000),   # film → PAL
    (24, 25),
    (25, 24),
]

# Seuils calés sur mesures, pas devinés. Sur du matériel réaliste (plusieurs
# centaines de répliques), un vrai alignement donne ~0.9 et un fichier sans
# rapport tombe à 0.06–0.10 : le plancher de bruit décroît en 1/√N répliques.
# La bande intermédiaire existe parce qu'un film réel — musique, bruitages,
# VAD imparfait — corrèle moins bien que du signal de test.
MIN_CONFIDENCE  = 0.25    # en dessous : on refuse plutôt que de mentir
SURE_CONFIDENCE = 0.40    # en dessous : on propose, mais on dit de vérifier
# Garde-fou contre une courbe plate dont l'argmax ne veut rien dire. Bas
# volontairement : la saillance est bruitée, elle ne sert qu'aux cas dégénérés.
MIN_SALIENCE    = 8.0
# Écart de durée au-delà duquel les fichiers ne sont pas le même montage
MAX_DURATION_DRIFT = 0.06

# Bande de la parole. Sur un film, la bande-son occupe surtout les graves et
# les aigus : sans ce filtre, une musique continue remplit le masque de VAD et
# la corrélation s'effondre (mesuré : 1.00 sans musique, 0.24 avec).
_SPEECH_BAND = "highpass=f=300,lowpass=f=3400"

_ffmpeg_path: str = "ffmpeg"


def set_ffmpeg_path(path: str) -> None:
    """Précise l'exécutable ffmpeg utilisé pour décoder l'audio."""
    global _ffmpeg_path
    _ffmpeg_path = path


@dataclass
class SyncResult:
    delay_ms:   int
    stretch:    Optional[tuple[int, int]]
    confidence: float
    ok:         bool
    reason:     str = ""
    # Diagnostic : renseigné même en cas de refus, pour qu'un échec soit
    # analysable au lieu d'être un simple « non ».
    best_delay_ms: int   = 0      # candidat trouvé, appliqué ou non
    floor:         float = 0.0    # confiance qu'il aurait fallu atteindre
    n_events:      int   = 0      # répliques, ou blocs de parole
    speech_ratio:  float = 0.0    # part du film détectée comme parlée

    @property
    def sure(self) -> bool:
        """Résultat exploitable sans vérification supplémentaire."""
        return self.ok and self.confidence >= SURE_CONFIDENCE

    def label(self) -> str:
        if not self.ok:
            return f"échec — {self.reason}"
        out = f"{self.delay_ms:+d} ms"
        if self.stretch:
            out += f" ×{self.stretch[0]}/{self.stretch[1]}"
        out += f" (confiance {self.confidence:.2f})"
        return out if self.sure else f"{out} — à vérifier"

    def report(self) -> str:
        """Compte rendu détaillé, lisible dans la TUI."""
        mesures = (f"confiance {self.confidence:.2f} / seuil {self.floor:.2f}"
                   f" · {self.n_events} repères"
                   f" · parole {self.speech_ratio:.0%} du film")
        if self.ok:
            head = f"{'✓' if self.sure else '⚠'} {self.label()}"
            if not self.sure:
                head += "  → contrôlez avant de muxer"
            return f"{head}\n{mesures}"

        candidat = f"meilleur candidat {self.best_delay_ms:+d} ms"
        return f"✗ Mesure refusée — {self.reason}\n{mesures} · {candidat}"

    def diagnosis(self) -> str:
        """Piste la plus probable derrière un refus."""
        if self.ok:
            return ""
        if self.n_events < 20:
            return ("trop peu de repères : sous-titre très court, ou format "
                    "mal lu")
        # Dans un film, la parole occupe 30 à 50 % du temps. Nettement au-delà,
        # c'est le VAD qui déborde sur la musique, pas le film qui bavarde.
        if self.speech_ratio > 0.60:
            return ("la bande-son sature la détection de parole — musique ou "
                    "ambiance continue ; le candidat ci-dessous est peut-être "
                    "bon malgré tout")
        if self.speech_ratio < 0.05:
            return "presque aucune parole détectée — mauvaise piste audio ?"
        return ("aucun alignement commun : montage différent, ou sous-titre "
                "d'une autre version")


# ─── Décodage et enveloppe d'énergie ──────────────────────────────────────────

def _decode_envelope(path: Path, track: int = 0,
                     progress: Optional[Progress] = None,
                     expected_bins: int = 0) -> np.ndarray:
    """
    Enveloppe d'énergie en dB, un point par bin de 10 ms.

    L'audio est réduit au fil du flux : on ne garde jamais le PCM complet
    (2 h à 16 kHz feraient 230 Mo pour 3 Mo d'enveloppe utile). C'est aussi
    ce qui permet d'avancer la jauge : le décodage est la phase longue.
    """
    cmd = [
        _ffmpeg_path, "-loglevel", "error",
        "-i", str(path),
        "-map", f"0:a:{track}",
        "-af", _SPEECH_BAND,
        "-ac", "1", "-ar", str(_SAMPLE_RATE),
        "-f", "s16le", "-",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    assert proc.stdout is not None

    chunks: list[np.ndarray] = []
    leftover = b""
    # Multiple de la taille d'un bin pour ne jamais couper au milieu
    read_size = _BIN_SAMPLES * 2 * 1024
    while True:
        raw = proc.stdout.read(read_size)
        if not raw:
            break
        raw = leftover + raw
        usable = len(raw) - (len(raw) % (_BIN_SAMPLES * 2))
        leftover, block = raw[usable:], raw[:usable]
        if not block:
            continue
        samples = np.frombuffer(block, dtype="<i2").astype(np.float32)
        frames  = samples.reshape(-1, _BIN_SAMPLES)
        chunks.append(np.sqrt(np.mean(frames * frames, axis=1)))
        if progress and expected_bins > 0:
            done = sum(c.size for c in chunks)
            progress(DECODE_SHARE * min(1.0, done / expected_bins))
    proc.wait()

    if not chunks:
        return np.zeros(0, dtype=np.float32)
    rms = np.concatenate(chunks)
    # dB relatif au plein échelle ; +1 évite log(0) sur le silence numérique
    return 20.0 * np.log10(rms + 1.0)


def _speech_mask(envelope: np.ndarray) -> np.ndarray:
    """
    Masque binaire « il y a de la parole », par seuil adaptatif local.

    Le seuil est recalculé par blocs de 30 s puis interpolé : la bande-son
    d'un film monte et descend au fil du récit, et un seuil global calé sur
    les passages calmes sature dès que la musique entre. Mesuré sur bande-son
    variable, le seuil local double la corrélation obtenue (0.41 → 0.78).

    On ne cherche pas à détecter la parole avec précision : il suffit que les
    motifs s'alignent. Les erreurs se moyennent sur des milliers de répliques.
    """
    if envelope.size == 0:
        return envelope

    n_blocks = max(1, envelope.size // _MASK_BLOCK)
    usable   = n_blocks * _MASK_BLOCK
    if usable > envelope.size:          # signal plus court qu'un bloc
        blocks  = envelope[None, :]
        centers = np.array([envelope.size / 2.0])
    else:
        blocks  = envelope[:usable].reshape(n_blocks, _MASK_BLOCK)
        centers = (np.arange(n_blocks) + 0.5) * _MASK_BLOCK

    idx  = np.arange(envelope.size)
    lo   = np.interp(idx, centers, np.percentile(blocks, 10, axis=1))
    hi   = np.interp(idx, centers, np.percentile(blocks, 90, axis=1))
    span = hi - lo
    # span nul = piste muette ou constante sur ce bloc : rien à détecter
    return np.where(span > 1e-6, envelope > lo + 0.4 * span, 0.0).astype(np.float32)


# ─── Lecture des sous-titres ──────────────────────────────────────────────────

_SRT_TIME = re.compile(
    r"(\d+):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d+):(\d{2}):(\d{2})[,.](\d{1,3})"
)
_ASS_LINE = re.compile(
    r"^Dialogue:[^,]*,\s*(\d+):(\d{2}):(\d{2})[.,](\d{1,2}),\s*(\d+):(\d{2}):(\d{2})[.,](\d{1,2}),"
)


def _read_text(path: Path) -> str:
    """
    Lit un fichier de sous-titres quelle que soit son encodage.

    C'est la première cause d'échec sur des fichiers réels : beaucoup de .srt
    circulent en cp1252 ou latin-1, pas en UTF-8.
    """
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def read_cues(path: Path) -> list[tuple[float, float]]:
    """Intervalles (début, fin) en secondes d'un .srt ou .ass/.ssa."""
    text  = _read_text(path)
    cues: list[tuple[float, float]] = []

    if path.suffix.lower() in (".ass", ".ssa"):
        for line in text.splitlines():
            m = _ASS_LINE.match(line.strip())
            if m:
                h1, m1, s1, c1, h2, m2, s2, c2 = (int(g) for g in m.groups())
                start = h1 * 3600 + m1 * 60 + s1 + c1 / 100.0
                end   = h2 * 3600 + m2 * 60 + s2 + c2 / 100.0
                cues.append((start, end))
        return cues

    for m in _SRT_TIME.finditer(text):
        h1, m1, s1, ms1, h2, m2, s2, ms2 = (int(g) for g in m.groups())
        start = h1 * 3600 + m1 * 60 + s1 + ms1 / 1000.0
        end   = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000.0
        cues.append((start, end))
    return cues


def _cue_mask(cues: list[tuple[float, float]], n_bins: int,
              ratio: tuple[int, int] = (1, 1)) -> np.ndarray:
    """Masque binaire des répliques, éventuellement rééchelonné."""
    mask  = np.zeros(n_bins, dtype=np.float32)
    scale = ratio[0] / ratio[1]
    for start, end in cues:
        a = int(start * scale * 1000 / BIN_MS)
        b = int(end   * scale * 1000 / BIN_MS)
        if b <= 0 or a >= n_bins:
            continue
        mask[max(0, a):min(n_bins, b)] = 1.0
    return mask


# ─── Corrélation ──────────────────────────────────────────────────────────────

def _rescale(sig: np.ndarray, ratio: tuple[int, int]) -> np.ndarray:
    """Rééchantillonne un signal sur un axe temporel étiré."""
    if ratio == (1, 1) or sig.size == 0:
        return sig
    scale = ratio[0] / ratio[1]
    n_out = max(1, int(sig.size * scale))
    src   = np.linspace(0, sig.size - 1, n_out)
    return np.interp(src, np.arange(sig.size), sig).astype(np.float32)


def _best_lag(ref: np.ndarray, sig: np.ndarray) -> tuple[int, float, float]:
    """
    Décalage de `sig` par rapport à `ref`, corrélation de Pearson, saillance.

    Les deux signaux sont centrés avant la FFT : sans ça, la composante
    continue domine et l'argmax ne veut plus rien dire. C'est l'erreur
    classique sur ce calcul.

    La saillance mesure de combien le pic dépasse le reste de la courbe.
    C'est elle qui distingue un vrai alignement d'une coïncidence : deux
    signaux de parole sans rapport corrèlent toujours un peu, mais leur
    courbe reste plate — aucun décalage ne se détache.
    """
    if ref.size == 0 or sig.size == 0:
        return 0, 0.0, 0.0

    n = 1 << int(np.ceil(np.log2(ref.size + sig.size)))
    a = ref - ref.mean()
    b = sig - sig.mean()
    corr = np.fft.irfft(np.fft.rfft(a, n) * np.conj(np.fft.rfft(b, n)), n)

    # Les décalages négatifs se lisent en fin de tableau (repliement circulaire)
    idx = int(np.argmax(corr))
    lag = idx if idx <= n // 2 else idx - n

    # Écart-type robuste : la médiane des écarts absolus ignore le pic
    med = float(np.median(corr))
    mad = float(np.median(np.abs(corr - med)))
    salience = (float(corr[idx]) - med) / (1.4826 * mad) if mad > 0 else 0.0

    return lag, _pearson_at(a, b, lag), salience


def _pearson_at(a: np.ndarray, b: np.ndarray, lag: int) -> float:
    """Corrélation de Pearson sur la partie commune aux deux signaux."""
    if lag >= 0:
        x, y = a[lag:], b[:a.size - lag]
    else:
        x, y = a[:b.size + lag], b[-lag:]
    n = min(x.size, y.size)
    if n < 100:                      # trop peu de recouvrement pour conclure
        return 0.0
    x, y = x[:n] - x[:n].mean(), y[:n] - y[:n].mean()
    denom = float(np.sqrt(np.dot(x, x) * np.dot(y, y)))
    return float(np.dot(x, y) / denom) if denom > 0 else 0.0


def _search(ref: np.ndarray, build,
            progress: Optional[Progress] = None,
            ) -> tuple[int, tuple[int, int], float, float]:
    """
    Cherche (décalage, ratio) sur la grille et retient le pic le plus saillant.

    `build(ratio)` produit le signal candidat pour un ratio donné.

    Une dérive d'étirement étale le pic au point de le rendre illisible : on
    ne peut pas mesurer le décalage puis le ratio, il faut essayer chaque
    ratio et regarder lequel donne un pic net. C'est la saillance qui tranche,
    pas la corrélation brute : un mauvais ratio garde une corrélation moyenne
    honorable tout en n'ayant plus aucun pic.
    """
    best = (0, (1, 1), 0.0, -1.0)
    for k, ratio in enumerate(RATIO_GRID, start=1):
        lag, conf, salience = _best_lag(ref, build(ratio))
        if salience > best[3]:
            best = (lag, ratio, conf, salience)
        if progress:
            progress(DECODE_SHARE + (1 - DECODE_SHARE) * k / len(RATIO_GRID))
    return best


# ─── Mesures ──────────────────────────────────────────────────────────────────

def confidence_floor(n_events: int) -> float:
    """
    Confiance minimale exigible pour `n_events` répliques.

    Le plancher de bruit d'une corrélation décroît en 1/√N : mesuré, un
    fichier sans rapport atteint 0.35 avec 30 répliques mais retombe à 0.10
    avec 340. Un seuil fixe serait donc soit trop laxiste sur les fichiers
    courts, soit trop sévère sur les longs.
    """
    if n_events <= 0:
        return 1.0
    return max(MIN_CONFIDENCE, 2.46 / np.sqrt(n_events))


def _finish(lag: int, ratio: tuple[int, int], conf: float, salience: float,
            floor: float = MIN_CONFIDENCE, n_events: int = 0,
            speech_ratio: float = 0.0) -> SyncResult:
    candidate = int(round(lag * BIN_MS))
    common = dict(best_delay_ms=candidate, floor=floor,
                  n_events=n_events, speech_ratio=speech_ratio)

    if salience < MIN_SALIENCE or conf < floor:
        res = SyncResult(
            delay_ms=0, stretch=None, confidence=conf, ok=False, **common,
        )
        res.reason = res.diagnosis()
        return res

    res = SyncResult(
        delay_ms=candidate,
        stretch=None if ratio == (1, 1) else ratio,
        confidence=conf, ok=True, **common,
    )
    if not res.sure:
        res.reason = (f"corrélation moyenne ({conf:.2f}) — contrôlez le "
                      f"résultat avant de muxer")
    return res


def measure_audio(target: Path, donor: Path, donor_track: int = 0,
                  progress: Optional[Progress] = None,
                  duration: float = 0.0) -> SyncResult:
    """Décalage d'une piste audio donneuse par rapport à l'audio de la cible."""
    expected = int(duration * 1000 / BIN_MS)
    # Deux décodages : chacun occupe la moitié de la phase de décodage
    ref = _decode_envelope(
        target, 0, (lambda f: progress(f / 2)) if progress else None, expected)
    sig = _decode_envelope(
        donor, donor_track,
        (lambda f: progress(DECODE_SHARE / 2 + f / 2)) if progress else None,
        expected)
    if ref.size == 0 or sig.size == 0:
        return SyncResult(0, None, 0.0, False, "aucun audio exploitable")

    speech = float(_speech_mask(ref).mean())
    drift  = abs(ref.size - sig.size) / max(ref.size, sig.size)
    lag, ratio, conf, salience = _search(
        ref, lambda r: _rescale(sig, r), progress)
    res = _finish(lag, ratio, conf, salience, speech_ratio=speech)
    if res.ok and ratio == (1, 1) and drift > MAX_DURATION_DRIFT:
        res.reason = (f"durées écartées de {drift:.0%} — vérifiez qu'il s'agit "
                      f"bien du même montage")
    return res


def measure_subtitle(video: Path, subtitle: Path,
                     progress: Optional[Progress] = None,
                     duration: float = 0.0) -> SyncResult:
    """Décalage d'un fichier de sous-titres par rapport à la parole de la vidéo."""
    cues = read_cues(subtitle)
    if not cues:
        return SyncResult(0, None, 0.0, False,
                          "aucune réplique lisible — format inconnu ou "
                          "fichier vide")

    envelope = _decode_envelope(
        video, 0, progress, int(duration * 1000 / BIN_MS))
    if envelope.size == 0:
        return SyncResult(0, None, 0.0, False,
                          "aucun audio dans la vidéo pour servir de référence")

    ref    = _speech_mask(envelope)
    n_bins = ref.size

    # Le signal d'un sous-titre est creux : on corrèle le fichier entier,
    # jamais des fenêtres de quelques secondes.
    lag, ratio, conf, salience = _search(
        ref, lambda r: _cue_mask(cues, n_bins, r), progress)
    return _finish(lag, ratio, conf, salience,
                   floor=confidence_floor(len(cues)),
                   n_events=len(cues), speech_ratio=float(ref.mean()))
