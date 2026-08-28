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
import tempfile
from dataclasses import dataclass, field
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

# Une confiance brute ne dit rien à personne : « 0,09 » ne se lit qu'en le
# comparant au seuil, qui varie avec le nombre de repères (voir
# `confidence_floor`). Le libellé est donc **relatif au seuil** — c'est la
# seule façon qu'il soit vrai d'une mesure à l'autre.
NIVEAUX_CONFIANCE = ("aucune", "faible", "moyenne", "excellente")


def libelle_confiance(confidence: float, seuil: float = MIN_CONFIDENCE) -> str:
    """Confiance en mots. Sous le seuil, la mesure est refusée."""
    seuil = seuil or MIN_CONFIDENCE
    if confidence < seuil / 2:
        return NIVEAUX_CONFIANCE[0]
    if confidence < seuil:
        return NIVEAUX_CONFIANCE[1]
    if confidence < seuil * 1.5:
        return NIVEAUX_CONFIANCE[2]
    return NIVEAUX_CONFIANCE[3]
SURE_CONFIDENCE = 0.40    # en dessous : on propose, mais on dit de vérifier
# Garde-fou contre une courbe plate dont l'argmax ne veut rien dire. Bas
# volontairement : la saillance est bruitée, elle ne sert qu'aux cas dégénérés.
MIN_SALIENCE    = 8.0

# Recoupement par tiers : critère principal quand le film est assez long.
# Un vrai alignement tient sur chaque tiers ; du bruit se disperse.
CROSS_TOLERANCE_MS = 500
_MIN_SEGMENT_BINS  = 6_000    # 60 s : en dessous, un tiers ne prouve rien
# Écart de durée au-delà duquel les fichiers ne sont pas le même montage
MAX_DURATION_DRIFT = 0.06

# Découpage en plages, quand le recoupement constate que le décalage ne tient
# pas sur tout le film. Une fenêtre de 2 min est assez longue pour que la
# corrélation ait de quoi mordre, assez courte pour isoler une coupure
# publicitaire. Les bornes évitent 200 fenêtres sur une intégrale et 3 sur un
# épisode court.
_SEGMENT_WINDOW_S    = 120
_SEGMENT_MIN_WINDOWS = 8
_SEGMENT_MAX_WINDOWS = 32
# Pas du balayage qui affine une frontière entre deux plages
_BOUNDARY_STEP_S     = 1.0

# Sous-titres lisibles directement : tout le reste est une piste embarquée,
# qu'il faut extraire du conteneur avant d'en tirer des répliques.
_TEXT_SUB_EXT = {".srt", ".ass", ".ssa", ".vtt", ".sub"}

# Bande de la parole. Sur un film, la bande-son occupe surtout les graves et
# les aigus : sans ce filtre, une musique continue remplit le masque de VAD et
# la corrélation s'effondre (mesuré : 1.00 sans musique, 0.24 avec).
_SPEECH_BAND = "highpass=f=300,lowpass=f=3400"

_ffmpeg_path: str = "ffmpeg"


def set_ffmpeg_path(path: str) -> None:
    """Précise l'exécutable ffmpeg utilisé pour décoder l'audio."""
    global _ffmpeg_path
    _ffmpeg_path = path


def mmss(seconds: float) -> str:
    """Secondes → m:ss, pour situer une plage dans le film."""
    s = max(0, int(seconds))
    return f"{s // 60}:{s % 60:02d}"


@dataclass
class Segment:
    """
    Plage du film sur laquelle un même décalage tient.

    Existe parce qu'un décalage unique ne décrit pas tous les cas réels : deux
    montages du même épisode diffèrent par des insertions ponctuelles — noirs
    de coupure publicitaire, bumpers — qui décalent tout ce qui suit sans rien
    changer au contenu. Chaque plage est alors juste, et c'est seulement leur
    réunion qui ne l'est pas.
    """
    start_s:    float
    end_s:      float
    delay_ms:   int
    confidence: float

    def label(self) -> str:
        return (f"{mmss(self.start_s)}–{mmss(self.end_s)}"
                f"  {self.delay_ms:+d} ms")


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
    cross_checked: bool  = False  # les trois tiers donnent le même décalage
    dispersion_ms: int   = 0      # écart entre tiers
    # Plages détectées quand le décalage ne tient pas sur tout le film. Jamais
    # appliquées : elles expliquent un refus, elles ne le contournent pas.
    segments:      list["Segment"] = field(default_factory=list)

    @property
    def sure(self) -> bool:
        """
        Résultat exploitable sans vérification supplémentaire.

        Le recoupement par tiers prime sur le niveau de corrélation : une
        corrélation médiocre dont les trois tiers concordent au dixième de
        seconde est bien plus fiable qu'un score élevé isolé.
        """
        return self.ok and (self.cross_checked
                            or self.confidence >= SURE_CONFIDENCE)

    def label(self) -> str:
        if not self.ok:
            return f"échec — {self.reason}"
        out = f"{self.delay_ms:+d} ms"
        if self.stretch:
            out += f" ×{self.stretch[0]}/{self.stretch[1]}"
        out += (f" (confiance "
                f"{libelle_confiance(self.confidence, self.floor)})")
        return out if self.sure else f"{out} — à vérifier"

    def report(self) -> str:
        """Compte rendu détaillé, lisible dans la TUI."""
        recoupe = (f"tiers concordants à {self.dispersion_ms} ms près"
                   if self.cross_checked
                   else f"tiers discordants ({self.dispersion_ms} ms d'écart)")
        # Le mot d'abord, les nombres ensuite : ce panneau existe pour qu'un
        # refus soit analysable, mais personne ne devrait avoir à traduire
        # « 0,09 » de tête.
        mesures = (f"confiance "
                   f"{libelle_confiance(self.confidence, self.floor)}"
                   f" ({self.confidence:.2f} pour {self.floor:.2f} requis)"
                   f" · {recoupe}"
                   f" · {self.n_events} repères"
                   f" · parole {self.speech_ratio:.0%}")
        if self.ok:
            head = f"{'✓' if self.sure else '⚠'} {self.label()}"
            if not self.sure:
                head += "  → contrôlez avant de muxer"
            return f"{head}\n{mesures}"

        candidat = f"meilleur candidat {self.best_delay_ms:+d} ms"
        if self.segments:
            # Une ligne, quel que soit le nombre de plages : le détail tient
            # dans son propre écran, le bandeau n'a que trois lignes.
            paliers = " · ".join(f"{s.delay_ms:+d}" for s in self.segments)
            return (f"✗ Mesure refusée — {self.reason}\n"
                    f"{mesures}\n"
                    f"plages (ms) : {paliers}   —   's' pour le détail")
        return f"✗ Mesure refusée — {self.reason}\n{mesures} · {candidat}"

    def diagnosis(self) -> str:
        """Piste la plus probable derrière un refus."""
        if self.ok:
            return ""
        if self.segments:
            # Constat, pas hypothèse : chaque plage a été vérifiée isolément.
            return (f"montage différent — {len(self.segments)} plages, chacune "
                    f"alignée mais à un décalage propre")
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


def _count_speech_blocks(mask: np.ndarray) -> int:
    """Nombre de plages de parole — l'équivalent des répliques, côté audio."""
    if mask.size == 0:
        return 0
    return int(np.count_nonzero(np.diff(mask, prepend=0.0) > 0))


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


def extract_subtitle(video: Path, ffmpeg_index: int) -> Optional[Path]:
    """
    Sort une piste de sous-titres embarquée du conteneur, vers un .srt temporaire.

    read_cues() ne sait lire qu'un fichier texte. Une piste greffée depuis un
    mkv ou un mp4 — le cas courant quand le donneur est un autre montage du
    même épisode — n'a donc aucune réplique lisible tant qu'elle n'en est pas
    extraite.

    Retourne None si ffmpeg refuse la conversion : c'est ce qui arrive aux
    sous-titres image (PGS, VobSub), qui ne contiennent pas de texte.
    """
    out = Path(tempfile.gettempdir()) / f"{video.stem}_{ffmpeg_index}_[sync].srt"
    cmd = [_ffmpeg_path, "-y", "-v", "error",
           "-i", str(video), "-map", f"0:s:{ffmpeg_index}",
           "-c:s", "srt", str(out)]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        return None
    return out


def delay_at(segments: list[Segment], t: float) -> int:
    """
    Décalage applicable à l'instant `t`, en millisecondes.

    Hors des plages connues, on prolonge celle du bord le plus proche plutôt
    que de retomber à zéro : un générique de fin au-delà de la dernière plage
    suit le même montage que ce qui le précède.
    """
    if not segments:
        return 0
    for seg in segments:
        if t < seg.end_s:
            return seg.delay_ms
    return segments[-1].delay_ms


def _srt_stamp(seconds: float) -> str:
    s = max(0.0, seconds)
    h, r = divmod(int(s), 3600)
    m, sec = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{sec:02d},{int(round((s % 1) * 1000)):03d}"


def shift_srt(src: Path, segments: list[Segment], out: Path) -> Path:
    """
    Réécrit un `.srt` en appliquant un décalage propre à chaque plage.

    Seuls les horodatages sont touchés : le texte, la numérotation et tout ce
    que le fichier porte par ailleurs passent tels quels. C'est ce qui rend la
    correction exacte pour un sous-titre — contrairement à l'audio, il n'y a
    rien à rééchantillonner, juste des nombres à décaler.

    La plage est choisie sur l'instant de départ de la réplique : une réplique
    ne chevauche pas une coupure, qui tombe sur un noir sans dialogue.
    """
    text = _read_text(src)

    def _rewrite(m: re.Match) -> str:
        h1, m1, s1, ms1, h2, m2, s2, ms2 = (int(g) for g in m.groups())
        start = h1 * 3600 + m1 * 60 + s1 + ms1 / 1000.0
        end   = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000.0
        d = delay_at(segments, start) / 1000.0
        return f"{_srt_stamp(start + d)} --> {_srt_stamp(end + d)}"

    out.write_text(_SRT_TIME.sub(_rewrite, text), encoding="utf-8")
    return out


# ─── Correction d'une piste audio ─────────────────────────────────────────────

# Une coupure est cherchée dans cette fenêtre autour de la frontière estimée.
# Mesuré : la corrélation place la bascule à moins de 2 s du silence réel ;
# 15 s laissent de la marge sans risquer d'attraper une autre pause.
CUT_SEARCH_S    = 15.0
# Un insert n'est pas toujours parfaitement muet — bruit de fond, fondu.
CUT_MIN_RATIO   = 0.75
# Centile d'énergie sous lequel on considère qu'il ne se passe rien
_SILENCE_PCTL   = 20


def find_silence(envelope: np.ndarray, center: int, need: int,
                 search: int) -> Optional[int]:
    """
    Début du silence le plus proche de `center`, long d'au moins `need` bins.

    Couper sur la frontière rendue par la corrélation serait imprudent : elle
    est juste à une seconde ou deux près, et deux secondes de décalage font la
    différence entre retirer un noir et amputer une réplique. Le silence, lui,
    est une borne physique — on s'y accroche.
    """
    if envelope.size == 0 or need <= 0:
        return None
    seuil = float(np.percentile(envelope, _SILENCE_PCTL))
    lo    = max(0, center - search)
    hi    = min(envelope.size, center + search)
    if hi - lo < need:
        return None

    bas     = envelope[lo:hi] < seuil
    minimum = int(need * CUT_MIN_RATIO)
    plages, debut = [], None
    for k, muet in enumerate(bas):
        if muet:
            if debut is None:
                debut = k
        else:
            if debut is not None and k - debut >= minimum:
                plages.append((debut, k))
            debut = None
    if debut is not None and bas.size - debut >= minimum:
        plages.append((debut, bas.size))
    if not plages:
        return None

    # Le silence dont le milieu est le plus proche de la frontière estimée
    a, b = min(plages, key=lambda p: abs((p[0] + p[1]) // 2 - (center - lo)))
    # La coupe est centrée sur le silence : si celui-ci est un peu plus court
    # que l'insert, l'erreur se répartit des deux côtés au lieu de tomber
    # entièrement sur une réplique.
    milieu = lo + (a + b) // 2
    return max(0, milieu - need // 2)


def plan_inserts(envelope: np.ndarray,
                 segments: list[Segment]) -> tuple[list[tuple[float, float]], list[str]]:
    """
    Points où allonger le donneur pour le ramener au montage de la cible.

    Retourne (insertions `(position, durée)` en secondes du donneur, frontières
    posées sans ancrage). Un décalage qui **croît** signifie que la cible porte
    du contenu que le donneur n'a pas : il faut donc pousser la suite plus
    tard, c'est-à-dire intercaler du silence — jamais en retirer.

    Les coordonnées des plages sont celles de la cible ; le donneur s'en déduit
    par `donneur = cible − décalage`.
    """
    inserts: list[tuple[float, float]] = []
    approx:  list[str] = []
    for gauche, droite in zip(segments, segments[1:]):
        saut = droite.delay_ms - gauche.delay_ms
        if saut <= 0:
            # Le donneur est plus long ici : il faudrait le recouper, ce qui
            # supprimerait du contenu. On préfère s'abstenir.
            approx.append(f"{mmss(gauche.end_s)} : saut négatif ({saut} ms), ignoré")
            continue
        centre = int((gauche.end_s - gauche.delay_ms / 1000.0) * 1000 / BIN_MS)
        besoin = int(saut / BIN_MS)
        debut  = find_silence(envelope, centre, besoin,
                              int(CUT_SEARCH_S * 1000 / BIN_MS))
        if debut is None:
            # Sans silence où se loger, on pose quand même : allonger une
            # pause au mauvais endroit s'entend, mais n'efface rien.
            debut = centre
            approx.append(f"{mmss(gauche.end_s)} : aucun silence trouvé, "
                          f"insertion sur la frontière estimée")
        inserts.append((debut * BIN_MS / 1000.0, saut / 1000.0))
    return inserts, approx


def build_retime_command(donor: Path, audio_index: int,
                         inserts: list[tuple[float, float]], out: Path,
                         bitrate_kbps: int = 192) -> list[str]:
    """
    Commande ffmpeg produisant la piste allongée aux points demandés.

    `atrim` découpe à l'échantillon près, là où une copie de flux se calerait
    sur la trame la plus proche : sur cinq jointures, ces arrondis
    s'accumuleraient en une dérive audible. Le prix est une génération de
    réencodage, négligeable sur une piste déjà compressée.

    Le silence intercalé est un extrait du donneur lui-même passé à `volume=0`,
    et non un `anullsrc` : il porte ainsi d'office la fréquence
    d'échantillonnage et la disposition de canaux de la piste, que `concat`
    exige identiques sur tous ses segments.
    """
    if not inserts:
        raise ValueError("Aucune insertion à appliquer.")

    src = f"[0:a:{audio_index}]"
    filtres, etiquettes = [], []
    precedent = 0.0
    for k, (position, duree) in enumerate(inserts):
        filtres.append(f"{src}atrim=start={precedent:.3f}:end={position:.3f},"
                       f"asetpts=PTS-STARTPTS[k{k}]")
        filtres.append(f"{src}atrim=start=0:end={duree:.3f},"
                       f"asetpts=PTS-STARTPTS,volume=0[g{k}]")
        etiquettes += [f"[k{k}]", f"[g{k}]"]
        precedent = position
    n = len(inserts)
    filtres.append(f"{src}atrim=start={precedent:.3f},asetpts=PTS-STARTPTS[k{n}]")
    etiquettes.append(f"[k{n}]")

    filtres.append(f"{''.join(etiquettes)}concat=n={len(etiquettes)}:v=0:a=1[out]")

    return [_ffmpeg_path, "-y", "-v", "error",
            # Progression sur stdout : le réencodage est la phase longue,
            # une barre figée pendant plusieurs minutes passe pour un blocage.
            "-progress", "pipe:1", "-nostats",
            "-i", str(donor),
            "-filter_complex", ";".join(filtres),
            "-map", "[out]",
            "-c:a", "aac", "-b:a", f"{bitrate_kbps}k",
            str(out)]


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


def _cross_validate(ref: np.ndarray, sig: np.ndarray,
                    lag: int) -> tuple[Optional[bool], int]:
    """
    Le décalage tient-il sur chaque tiers du film pris isolément ?

    C'est la preuve la plus solide dont on dispose, et elle ne dépend pas du
    niveau de corrélation. Mesuré sur un vrai film : un sous-titre juste donne
    trois tiers à 60 ms d'écart, un sous-titre mélangé les disperse sur
    192 secondes. Une corrélation de 0.20 peut donc être parfaitement bonne.

    Retourne (None, 0) si les segments sont trop courts pour conclure.
    """
    n = min(ref.size, sig.size)
    if n // 3 < _MIN_SEGMENT_BINS:
        return None, 0

    lags = []
    for k in range(3):
        a, b = k * n // 3, (k + 1) * n // 3
        seg_lag, _, _ = _best_lag(ref[a:b], sig[a:b])
        lags.append(seg_lag)

    dispersion = (max(lags) - min(lags)) * BIN_MS
    worst_gap  = max(abs(l - lag) for l in lags) * BIN_MS
    return worst_gap <= CROSS_TOLERANCE_MS, dispersion


def _refine_boundary(ref: np.ndarray, sig: np.ndarray, approx: int,
                     lag_left: int, lag_right: int, span: int) -> int:
    """
    Situe précisément la bascule entre deux plages voisines.

    La passe grossière ne sait que désigner la fenêtre où le décalage change ;
    la fenêtre qui chevauche la bascule reçoit celui de ses deux décalages qui
    y domine. On balaie donc l'intervalle en cherchant le point qui maximise la
    corrélation des deux côtés, chacun à *son* décalage.
    """
    n  = min(ref.size, sig.size)
    lo = max(0, approx - span)
    hi = min(n, approx + span)
    step = max(1, int(_BOUNDARY_STEP_S * 1000 / BIN_MS))
    if hi - lo < 4 * step:
        return approx

    best, best_score = approx, -2.0
    for split in range(lo + step, hi - step, step):
        score = (_pearson_at(ref[lo:split],  sig[lo:split],  lag_left)
                 + _pearson_at(ref[split:hi], sig[split:hi], lag_right))
        if score > best_score:
            best_score, best = score, split
    return best


# Bornes de la voie « accord entre fenêtres ». Un décalage de montage est
# petit — quelques secondes de coupure, pas des minutes. Chercher loin n'ajoute
# que des candidats fantômes : mesuré sur un cas réel, une recherche à ±90 s
# rendait douze réponses incohérentes là où ±12 s faisait apparaître l'escalier
# du premier coup.
_ACCORD_MAX_LAG_S   = 30.0
_ACCORD_WINDOW_S    = 150.0
_ACCORD_PAS_MS      = 100
# Part des fenêtres qui doivent avoir un pic exploitable. En deçà, il n'y a pas
# de structure à lire, seulement du bruit qui s'accorde par hasard.
_ACCORD_MIN_RETENUES = 0.55
# Part des fenêtres dont le décalage est partagé par au moins une autre, sur
# **tout** le film. Mesuré : 70 % sur un cas vrai, 25 % sur deux signaux sans
# rapport. C'est ce critère, et non l'accord entre voisines immédiates, qui
# sépare une structure d'une coïncidence — une seule fenêtre bruitée suffisait
# à casser une suite de voisines, alors qu'elle ne change rien à un décompte
# global.
_ACCORD_MIN_COHERENCE = 0.60


def _lag_borne(x: np.ndarray, y: np.ndarray, max_lag_s: float,
               pas_ms: int) -> tuple[Optional[int], float]:
    """Meilleur décalage dans une fenêtre de recherche bornée, et sa saillance.

    Retourne `None` quand le pic tombe **sur la borne** : c'est le signe qu'il
    n'y a pas de pic du tout et que la corrélation s'échappe. Ces fenêtres-là
    doivent être écartées, pas moyennées — c'est ce qui distingue un palier
    d'un artefact.
    """
    a = x.astype(float) - x.mean()
    b = y.astype(float) - y.mean()
    if a.std() == 0 or b.std() == 0:
        return None, 0.0
    m   = int(max_lag_s * 1000 / BIN_MS)
    pas = max(1, pas_ms // BIN_MS)
    scores: list[tuple[float, int]] = []
    for d in range(-m, m + 1, pas):
        u, v = (a[d:], b[:len(b) - d]) if d > 0 else                ((a, b) if d == 0 else (a[:len(a) + d], b[-d:]))
        k = min(len(u), len(v))
        if k < 400:
            continue
        c = float(np.dot(u[:k], v[:k])
                  / (np.linalg.norm(u[:k]) * np.linalg.norm(v[:k]) + 1e-9))
        scores.append((c, d))
    if not scores:
        return None, 0.0
    scores.sort(reverse=True)
    meilleur, d = scores[0]
    if abs(d) >= m - pas:
        return None, 0.0                 # collé à la borne : pas de pic
    saillance = meilleur - float(np.median([c for c, _ in scores]))
    return int(round(d * BIN_MS)), saillance


def _segments_par_accord(ref: np.ndarray, sig: np.ndarray) -> list[Segment]:
    """Paliers déduits de l'**accord entre fenêtres voisines**, non de l'amplitude.

    La voie ordinaire juge une corrélation sur sa force. Certains couples n'y
    arrivent jamais : un sous-titre dont l'adaptation diffère de celle du
    doublage ne décalque pas la parole, et plafonne — mesuré — à 0,117 pour un
    seuil de 0,25, *même parfaitement aligné*. Aucun seuil d'amplitude ne le
    sauvera.

    Mais son décalage, lui, est stable : des fenêtres voisines tombent sur la
    même valeur à quelques dizaines de millisecondes près, et cette régularité
    ne s'obtient pas par hasard. C'est elle qu'on lit ici.

    Rien n'est appliqué d'office : la fonction rend des plages, que
    l'utilisateur consulte puis applique. Le garde-fou contre un décalage faux
    reste entier.
    """
    n = min(ref.size, sig.size)
    if n < 2 * _MIN_SEGMENT_BINS:
        return []
    fen = int(_ACCORD_WINDOW_S * 1000 / BIN_MS)
    if n < 4 * fen:
        return []                        # moins de quatre fenêtres : rien à croiser

    mesures: list[tuple[int, int, Optional[int], float]] = []
    for k in range(n // fen):
        a, b = k * fen, min((k + 1) * fen, n)
        lag, sal = _lag_borne(ref[a:b], sig[a:b],
                              _ACCORD_MAX_LAG_S, _ACCORD_PAS_MS)
        mesures.append((a, b, lag, sal))

    trouves = [m[2] for m in mesures if m[2] is not None]
    if len(trouves) < _ACCORD_MIN_RETENUES * len(mesures):
        return []

    # Un décalage n'est crédible que s'il revient. On compte, sur tout le film,
    # combien de fenêtres partagent leur valeur avec au moins une autre : c'est
    # la cohérence. Elle ne dépend pas de l'ordre des fenêtres, donc une
    # fenêtre bruitée ne casse rien — là où une suite de voisines s'interrompt
    # au premier accroc.
    def _partage(lag: int) -> bool:
        return sum(1 for autre in trouves
                   if abs(autre - lag) <= CROSS_TOLERANCE_MS) >= 2

    coherents = [lag for lag in trouves if _partage(lag)]
    if len(coherents) < _ACCORD_MIN_COHERENCE * len(mesures):
        return []

    # Regroupement des fenêtres voisines. Une fenêtre sans pic, ou dont le
    # décalage n'est partagé par aucune autre, n'interrompt pas un palier :
    # elle le traverse sans rien dire.
    runs: list[list] = []
    for a, b, lag, sal in mesures:
        if lag is None or not _partage(lag):
            if runs:
                runs[-1][1] = b          # le palier court toujours
            continue
        if runs and abs(lag - runs[-1][2]) <= CROSS_TOLERANCE_MS:
            runs[-1][1] = b
            runs[-1][3] = max(runs[-1][3], sal)
            runs[-1][4] += 1
        else:
            runs.append([a, b, lag, sal, 1])

    # Un palier d'une seule fenêtre ne prouve rien : c'est le point de départ
    # de tout ce raisonnement, il ne peut pas en être la conclusion.
    runs = [r for r in runs if r[4] >= 2]
    if not runs:
        return []

    # Écarter les paliers isolés laisse des trous. Or `delay_at` lit la
    # première plage qui couvre l'instant : un trou lui ferait rendre le
    # décalage du palier *suivant* sur une zone qui appartient au précédent.
    # On recoud donc bout à bout, et la dernière plage court jusqu'à la fin.
    runs[0][0] = 0
    for i in range(len(runs) - 1):
        runs[i][1] = runs[i + 1][0]
    runs[-1][1] = n

    # Le décalage de la passe grossière a été mesuré sur une fenêtre étroite.
    # Remesuré sur l'étendue définitive, il gagne en précision — mesuré sur un
    # cas réel : +100 ms devient +300, +1000 devient +1500.
    for run in runs:
        a, b = run[0], run[1]
        if b - a >= _MIN_SEGMENT_BINS:
            lag, sal = _lag_borne(ref[a:b], sig[a:b],
                                  _ACCORD_MAX_LAG_S, _ACCORD_PAS_MS)
            if lag is not None:
                run[2], run[3] = lag, sal

    return [Segment(start_s=a * BIN_MS / 1000, end_s=b * BIN_MS / 1000,
                    delay_ms=lag, confidence=sal)
            for a, b, lag, sal, _ in runs]


def _segment_lags(ref: np.ndarray, sig: np.ndarray) -> list[Segment]:
    """
    Découpe le film en plages de décalage constant.

    N'est appelée qu'après l'échec du recoupement : si le décalage tient sur
    tout le film, il n'y a rien à découper. Retourne [] dès qu'on ne peut pas
    conclure — une plage unique n'apprend rien, et un film trop court ne donne
    pas de fenêtres exploitables.
    """
    n = min(ref.size, sig.size)
    if n < 2 * _MIN_SEGMENT_BINS:
        return []

    total_s = n * BIN_MS / 1000
    windows = int(round(total_s / _SEGMENT_WINDOW_S))
    windows = max(_SEGMENT_MIN_WINDOWS, min(_SEGMENT_MAX_WINDOWS, windows))
    win_len = n // windows
    if win_len < 100:                # moins d'une seconde : rien à corréler
        return []

    # 1. Décalage fenêtre par fenêtre
    coarse: list[tuple[int, int, int, float]] = []
    for k in range(windows):
        a, b = k * n // windows, (k + 1) * n // windows
        lag, conf, _ = _best_lag(ref[a:b], sig[a:b])
        coarse.append((a, b, lag, conf))

    # 2. Fusion des fenêtres voisines qui s'accordent. Même tolérance que le
    #    recoupement : en deçà, c'est du bruit de mesure, pas une bascule.
    runs: list[list] = []
    for a, b, lag, conf in coarse:
        if runs and abs(lag - runs[-1][2]) * BIN_MS <= CROSS_TOLERANCE_MS:
            runs[-1][1] = b
            runs[-1][3] = max(runs[-1][3], conf)
        else:
            runs.append([a, b, lag, conf])
    if len(runs) < 2:
        return []

    # 2 bis. Un découpage n'a de sens que s'il montre une structure. Quand
    #        presque chaque fenêtre tombe sur son propre décalage, il n'y a pas
    #        de paliers à lire : c'est du bruit de corrélation, et en exhiber
    #        vingt serait pire que de ne rien dire.
    if len(runs) > windows // 2:
        return []
    if float(np.median([r[3] for r in runs])) < MIN_CONFIDENCE:
        return []

    # 3. Affinage des frontières. La borne trouvée est bridée à l'intérieur des
    #    deux plages : sur des plages courtes, les intervalles de recherche se
    #    chevauchent et un point de bascule pourrait remonter avant le début de
    #    la plage de gauche.
    for i in range(len(runs) - 1):
        split = _refine_boundary(ref, sig, runs[i][1],
                                 runs[i][2], runs[i + 1][2], win_len)
        split = max(runs[i][0] + 1, min(split, runs[i + 1][1] - 1))
        runs[i][1]     = split
        runs[i + 1][0] = split

    # 4. Décalage repris sur l'étendue définitive de chaque plage. Celui de la
    #    passe grossière a été mesuré sur des fenêtres qui chevauchaient une
    #    bascule : il en portait la moyenne, à quelques dizaines de ms près.
    #    Seules les plages assez longues sont remesurées : sous une minute, le
    #    même raisonnement que pour le recoupement s'applique — un extrait
    #    court ne prouve rien, et la fenêtre large de la passe grossière reste
    #    le meilleur estimateur disponible.
    for run in runs:
        a, b = run[0], run[1]
        if b - a >= _MIN_SEGMENT_BINS:
            lag, conf, _ = _best_lag(ref[a:b], sig[a:b])
            run[2], run[3] = lag, conf

    return [Segment(start_s=a * BIN_MS / 1000, end_s=b * BIN_MS / 1000,
                    delay_ms=int(round(lag * BIN_MS)), confidence=conf)
            for a, b, lag, conf in runs]


def _segments(ref: np.ndarray, sig: np.ndarray) -> list[Segment]:
    """Paliers, par la voie ordinaire puis par l'accord entre fenêtres."""
    trouves = _segment_lags(ref, sig)
    return trouves if trouves else _segments_par_accord(ref, sig)


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
            speech_ratio: float = 0.0, agreed: Optional[bool] = None,
            dispersion_ms: int = 0,
            segments: Optional[list[Segment]] = None) -> SyncResult:
    candidate = int(round(lag * BIN_MS))
    common = dict(best_delay_ms=candidate, floor=floor,
                  n_events=n_events, speech_ratio=speech_ratio,
                  cross_checked=bool(agreed), dispersion_ms=dispersion_ms,
                  segments=segments or [])

    # Le recoupement par tiers tranche quand il est disponible : il constate
    # que le décalage tient sur tout le film, ce qu'aucun seuil de corrélation
    # ne sait faire. Mesuré sur un vrai film, un alignement juste sortait à
    # 0.20 — sous le seuil — avec trois tiers concordants à 60 ms.
    if agreed is not None:
        rejected = not agreed
    else:
        rejected = salience < MIN_SALIENCE or conf < floor

    if rejected:
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

    mask   = _speech_mask(ref)
    speech = float(mask.mean())
    drift  = abs(ref.size - sig.size) / max(ref.size, sig.size)
    lag, ratio, conf, salience = _search(
        ref, lambda r: _rescale(sig, r), progress)
    scaled = _rescale(sig, ratio)
    agreed, dispersion = _cross_validate(ref, scaled, lag)
    # Le découpage ne sert qu'à expliquer un refus : quand le décalage tient
    # sur tout le film, il n'y a rien à découper et le cas nominal ne paie rien.
    segments = _segments(ref, scaled) if agreed is False else []
    res = _finish(lag, ratio, conf, salience, speech_ratio=speech,
                  n_events=_count_speech_blocks(mask),
                  agreed=agreed, dispersion_ms=dispersion, segments=segments)
    if res.ok and ratio == (1, 1) and drift > MAX_DURATION_DRIFT:
        res.reason = (f"durées écartées de {drift:.0%} — vérifiez qu'il s'agit "
                      f"bien du même montage")
    return res


def retime_audio(donor: Path, audio_index: int, segments: list[Segment],
                 out: Path, bitrate_kbps: int = 192,
                 progress: Optional[Progress] = None
                 ) -> tuple[Optional[Path], list[str]]:
    """
    Fabrique une piste audio recalée sur le montage de la cible.

    Retourne (fichier produit, frontières non résolues). Le fichier est None
    si aucune coupure n'a pu être placée : mieux vaut ne rien produire qu'une
    piste amputée au mauvais endroit.

    Une piste corrigée se greffe ensuite avec un décalage nul, comme n'importe
    quel donneur — c'est ce qui permet de ne rien changer à l'aval.
    """
    envelope = _decode_envelope(
        donor, audio_index,
        (lambda f: progress(f * DECODE_SHARE)) if progress else None)
    if envelope.size == 0:
        return None, ["aucun audio exploitable dans le donneur"]

    inserts, approx = plan_inserts(envelope, segments)
    if not inserts:
        return None, approx or ["aucune insertion exploitable"]

    # Durée attendue en sortie : l'enveloppe du donneur, allongée des insertions
    duree = envelope.size * BIN_MS / 1000.0 + sum(d for _, d in inserts)

    cmd = build_retime_command(donor, audio_index, inserts, out, bitrate_kbps)
    try:
        # Voir scanner._ffprobe_json : lire dans l'encodage local
        # tue le thread de lecture dès qu'un nom de fichier en sort.
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, bufsize=1,
                                encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as e:
        return None, [f"ffmpeg a échoué : {e}"]

    if proc.stdout is not None:
        for ligne in proc.stdout:
            if progress and duree > 0 and ligne.startswith("out_time_ms="):
                try:
                    fait = int(ligne.split("=", 1)[1]) / 1_000_000.0
                except ValueError:
                    continue
                part = min(1.0, max(0.0, fait / duree))
                progress(DECODE_SHARE + (1 - DECODE_SHARE) * part)
    code   = proc.wait()
    erreur = proc.stderr.read().strip() if proc.stderr else ""

    if code != 0 or not out.exists() or out.stat().st_size == 0:
        detail = erreur.splitlines()
        return None, [f"ffmpeg a échoué : {detail[-1] if detail else f'code {code}'}"]

    if progress:
        progress(1.0)
    return out, approx


def measure_external_track(target: Path, track, progress=None,
                           duration: float = 0.0) -> "SyncResult":
    """Mesure une piste externe, quel que soit son type.

    **Traduit le tid mkvmerge en index ffmpeg**, ce qu'aucun appelant ne doit
    plus avoir à penser : les deux numérotations se ressemblent assez pour
    qu'on les confonde, et une piste mesurée sur le mauvais flux échoue sans
    dire pourquoi. Voir l'avertissement en tête de `core/muxer.py`.

    C'est le seul point d'entrée pour mesurer une `ExternalTrack` : l'écran de
    recalage et l'assistant s'en servent tous deux.
    """
    from .muxer import TrackKind, ffmpeg_stream_index

    idx = ffmpeg_stream_index(track.source_path, track.source_tid, track.kind)
    if track.kind == TrackKind.SUBTITLE:
        return measure_subtitle(target, track.source_path, progress=progress,
                                duration=duration, donor_track=idx)
    return measure_audio(target, track.source_path, idx, progress=progress,
                         duration=duration)


def measure_subtitle(video: Path, subtitle: Path,
                     progress: Optional[Progress] = None,
                     duration: float = 0.0,
                     donor_track: Optional[int] = None) -> SyncResult:
    """
    Décalage d'un sous-titre par rapport à la parole de la vidéo.

    `subtitle` est soit un fichier texte, soit un conteneur dont il faut
    extraire la piste `donor_track` (index ffmpeg parmi les sous-titres).
    """
    path = subtitle
    if subtitle.suffix.lower() not in _TEXT_SUB_EXT:
        if donor_track is None:
            return SyncResult(0, None, 0.0, False,
                              "piste embarquée sans index de piste — "
                              "impossible de l'extraire")
        path = extract_subtitle(subtitle, donor_track)
        if path is None:
            return SyncResult(0, None, 0.0, False,
                              "sous-titre image (PGS, VobSub) — aucun texte "
                              "à corréler")

    cues = read_cues(path)
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
    scaled = _cue_mask(cues, n_bins, ratio)
    agreed, dispersion = _cross_validate(ref, scaled, lag)
    segments = _segments(ref, scaled) if agreed is False else []
    return _finish(lag, ratio, conf, salience,
                   floor=confidence_floor(len(cues)),
                   n_events=len(cues), speech_ratio=float(ref.mean()),
                   agreed=agreed, dispersion_ms=dispersion, segments=segments)
