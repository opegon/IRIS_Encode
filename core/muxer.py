"""
core/muxer.py — Greffe de pistes audio / sous-titres externes via mkvmerge.

Permet d'ajouter à un fichier une piste venue d'un autre fichier (VF, sous-titres)
sans réencoder la vidéo, avec un décalage propre à chaque piste.

⚠ Numérotation des pistes : mkvmerge utilise un ID **global** (vidéo, audio et
sous-titres dans la même suite), là où core/scanner.py numérote **par type** via
ffprobe. Les deux ne doivent jamais se croiser : tout fichier donneur passe par
identify(), jamais par les index de AudioTrack / SubtitleTrack.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Optional

# Suffixe appliqué quand on mux sans réencoder : le nom de sortie doit différer
# de la source, qu'on ne réécrit jamais en place.
MUX_SUFFIX = "_[mux]"

# ── Chemin mkvmerge (singleton, settable par l'app au démarrage) ─────────────
_mkvmerge_path: str = "mkvmerge"


def set_mkvmerge_path(path: str) -> None:
    """Précise l'exécutable mkvmerge à utiliser (défaut: 'mkvmerge' du PATH)."""
    global _mkvmerge_path
    _mkvmerge_path = path
    # Ce que le cache contient a été lu par l'exécutable précédent.
    _CACHE_IDENTIFY.clear()


# Résultat d'`identify`, par fichier et par état de ce fichier.
#
# `build_strip_command` traduit un index par piste retenue, et chaque
# traduction relançait un `mkvmerge -J` : six pistes audio et vingt
# sous-titres coûtaient **26 processus** — timeout de 30 s chacun — sur le
# même fichier, pour une seule commande. `encoder.build_command` en relance un
# par piste externe.
#
# La clé porte la taille et la date de modification plutôt que le seul chemin :
# un donneur remplacé entre deux passages est relu, au lieu d'être servi
# depuis un cache qui ne le décrit plus. Un `stat()` contre un sous-processus,
# le compte est vite fait.
_CACHE_IDENTIFY: dict[tuple[str, int, int], list["IdentifiedTrack"]] = {}


def _signature(path: Path) -> Optional[tuple[str, int, int]]:
    """Chemin, taille, date de modification. None si le fichier est illisible."""
    try:
        st = path.stat()
    except OSError:
        return None
    return (str(path), st.st_size, st.st_mtime_ns)


# ─── Modèles ──────────────────────────────────────────────────────────────────

class TrackKind(Enum):
    AUDIO    = auto()
    SUBTITLE = auto()


class SyncOrigin(Enum):
    NONE     = auto()   # pas encore recalé
    MEASURED = auto()   # corrélation automatique
    MANUAL   = auto()   # ajusté à la main
    COPIED   = auto()   # repris d'une autre piste externe


@dataclass
class IdentifiedTrack:
    """Piste telle que mkvmerge -J la voit dans un fichier donneur."""
    tid:        int          # ID global mkvmerge, à utiliser tel quel dans --sync
    kind:       TrackKind
    codec:      str
    language:   str
    track_name: str = ""

    def display(self) -> str:
        lang = self.language or "?"
        name = f" « {self.track_name} »" if self.track_name else ""
        return f"{self.codec} {lang}{name}"


@dataclass
class ExternalTrack:
    """Piste à greffer, avec son recalage propre."""
    source_path: Path
    source_tid:  int              # ID mkvmerge DANS source_path
    kind:        TrackKind
    codec:       str  = ""        # affichage seulement
    language:    str  = ""        # obligatoire au mux — sinon « und »
    track_name:  str  = ""
    delay_ms:    int  = 0
    stretch:     Optional[tuple[int, int]] = None   # (24000, 25025)
    is_default:  bool = False
    is_forced:   bool = False
    sync_origin: SyncOrigin  = SyncOrigin.NONE
    copied_from: Optional[int] = None   # index dans FileDecision.external_tracks

    @property
    def has_sync(self) -> bool:
        return self.delay_ms != 0 or self.stretch is not None

    def sync_label(self) -> str:
        """Résumé du recalage pour la TUI."""
        if not self.has_sync:
            return "—"
        out = f"{self.delay_ms:+d} ms"
        if self.stretch:
            out += f" ×{self.stretch[0]}/{self.stretch[1]}"
        return out


# ─── Langue déduite du nom de fichier ─────────────────────────────────────────

# Un .srt nu ne porte aucune métadonnée : mkvmerge le rapporte sans langue.
# Le nom du fichier est en pratique la seule source disponible.
_LANG_TOKENS: dict[str, str] = {
    "fr": "fre", "fre": "fre", "fra": "fre", "french": "fre",
    "vf": "fre", "vff": "fre", "vfq": "fre", "truefrench": "fre",
    "vostfr": "fre", "francais": "fre",
    "en": "eng", "eng": "eng", "english": "eng", "vo": "eng",
    "de": "ger", "ger": "ger", "deu": "ger", "german": "ger",
    "es": "spa", "spa": "spa", "esp": "spa", "spanish": "spa",
    "it": "ita", "ita": "ita", "italian": "ita",
    "ja": "jpn", "jp": "jpn", "jpn": "jpn", "japanese": "jpn",
    "pt": "por", "por": "por", "portuguese": "por",
    "ru": "rus", "rus": "rus", "russian": "rus",
}

_TOKEN_SPLIT = re.compile(r"[.\-_ \[\]()]+")


def guess_language(path: Path) -> str:
    """
    Déduit une langue ISO 639-2 du nom de fichier ("film.fr.srt" → "fre").

    Les marqueurs de langue sont en fin de nom : on parcourt les fragments
    de droite à gauche et on retient le premier reconnu. "" si aucun.
    """
    for token in reversed(_TOKEN_SPLIT.split(path.stem.lower())):
        lang = _LANG_TOKENS.get(token)
        if lang:
            return lang
    return ""


# ─── Identification d'un fichier donneur ──────────────────────────────────────

_KIND_BY_TYPE = {
    "audio":     TrackKind.AUDIO,
    "subtitles": TrackKind.SUBTITLE,
}


def identify(path: Path) -> list[IdentifiedTrack]:
    """
    Liste les pistes audio et sous-titres d'un fichier via `mkvmerge -J`.

    Les pistes vidéo sont ignorées (on ne greffe jamais de vidéo) mais elles
    comptent dans la numérotation : les tid retournés restent ceux de mkvmerge.
    Retourne [] si mkvmerge échoue ou ne reconnaît pas le fichier.
    """
    signature = _signature(path)
    if signature is not None and signature in _CACHE_IDENTIFY:
        return list(_CACHE_IDENTIFY[signature])

    try:
        r = subprocess.run(
            [_mkvmerge_path, "-J", str(path)],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=30,
            # Voir scanner._ffprobe_json : lire dans l'encodage local tue le
            # thread de lecture dès qu'un nom de fichier en sort.
            encoding="utf-8", errors="replace",
        )
        # 0 = OK, 1 = avertissements non bloquants
        if r.returncode not in (0, 1) or not r.stdout:
            return []
        data = json.loads(r.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return []

    tracks: list[IdentifiedTrack] = []
    for t in data.get("tracks", []):
        kind = _KIND_BY_TYPE.get(t.get("type", ""))
        if kind is None:
            continue
        props = t.get("properties", {})
        tracks.append(IdentifiedTrack(
            tid=int(t.get("id", 0)),
            kind=kind,
            codec=t.get("codec", "?"),
            language=props.get("language", ""),
            track_name=props.get("track_name", ""),
        ))
    # Un résultat vide n'est pas mémorisé : c'est aussi ce que rend un
    # mkvmerge absent, et l'installer en cours de session doit suffire.
    if signature is not None and tracks:
        _CACHE_IDENTIFY[signature] = tracks
    return list(tracks)


def ffmpeg_stream_index(path: Path, tid: int, kind: TrackKind) -> int:
    """
    Traduit un tid mkvmerge en index ffmpeg (`0:a:N`) pour le même fichier.

    C'est le seul endroit où les deux numérotations se croisent : mkvmerge
    numérote globalement, ffmpeg par type. Partout ailleurs, on ne manipule
    que des tid.
    """
    same_kind = [t for t in identify(path) if t.kind == kind]
    for i, t in enumerate(same_kind):
        if t.tid == tid:
            return i
    return 0


def mkvmerge_tid(path: Path, index: int, kind: TrackKind) -> int:
    """Traduit un index ffmpeg par type (`0:s:N`) en tid mkvmerge.

    Réciproque de `ffmpeg_stream_index`. Les décisions manipulent des index
    par type, hérités de ffprobe ; mkvmerge numérote globalement. Voir
    l'avertissement en tête de module.
    """
    same_kind = [t for t in identify(path) if t.kind == kind]
    if 0 <= index < len(same_kind):
        return same_kind[index].tid
    return index


def propager_recalage(tracks: list[ExternalTrack], source: int) -> list[int]:
    """Reporte le décalage d'une piste audio sur les sous-titres du même donneur.

    Retourne les index modifiés. Des sous-titres livrés avec une VF sont écrits
    sur le timing de cette VF : leur bon décalage *est* celui de la piste audio.

    Trois garde-fous, parce qu'un report automatique doit rester un service et
    jamais une surprise : même fichier donneur ; ni piste mesurée pour
    elle-même ni piste réglée à la main ; et seulement depuis une piste audio.
    """
    if not (0 <= source < len(tracks)) or tracks[source].kind != TrackKind.AUDIO:
        return []
    src = tracks[source]
    touches: list[int] = []
    for j, t in enumerate(tracks):
        if j == source or t.kind == TrackKind.AUDIO:
            continue
        if t.source_path != src.source_path:
            continue
        if t.sync_origin not in (SyncOrigin.NONE, SyncOrigin.COPIED):
            continue
        if t.sync_origin == SyncOrigin.COPIED and t.copied_from != source:
            continue
        t.delay_ms    = src.delay_ms
        t.stretch     = src.stretch
        t.sync_origin = SyncOrigin.COPIED
        t.copied_from = source
        touches.append(j)
    return touches


# ─── Construction de la commande ──────────────────────────────────────────────

def _sync_arg(t: ExternalTrack) -> str:
    """Valeur de --sync : décalage en ms, plus facteur d'étirement si besoin."""
    if t.stretch:
        num, den = t.stretch
        return f"{t.source_tid}:{t.delay_ms},{num}/{den}"
    return f"{t.source_tid}:{t.delay_ms}"


def _track_options(t: ExternalTrack) -> list[str]:
    """Options propres à une piste (précèdent le nom du fichier donneur)."""
    args: list[str] = []
    if t.has_sync:
        args += ["--sync", _sync_arg(t)]
    args += ["--language", f"{t.source_tid}:{t.language}"]
    if t.track_name:
        args += ["--track-name", f"{t.source_tid}:{t.track_name}"]
    # Toujours explicite : mkvmerge met le premier sous-titre en « default »
    # de lui-même si on ne dit rien.
    args += ["--default-track-flag", f"{t.source_tid}:{1 if t.is_default else 0}"]
    if t.is_forced:
        args += ["--forced-display-flag", f"{t.source_tid}:1"]
    return args


def build_mux_command(
    source:  Path,
    tracks:  list[ExternalTrack],
    output:  Path,
) -> list[str]:
    """
    Retourne la commande mkvmerge greffant `tracks` sur `source` vers `output`.

    Les pistes venant d'un même fichier donneur sont regroupées : mkvmerge lit
    chaque fichier une seule fois, avec les options de chacune de ses pistes.
    Lève ValueError si la sortie écrase la source ou si une langue manque.
    """
    if not tracks:
        raise ValueError("Aucune piste externe à greffer.")

    if output.resolve() == source.resolve():
        raise ValueError(
            f"Chemin de sortie identique à la source ({source}). "
            f"Mux refusé pour éviter la corruption du fichier source."
        )

    for t in tracks:
        if not t.language:
            raise ValueError(
                f"Langue manquante pour la piste {t.source_tid} de {t.source_path.name}. "
                f"Sans langue, la piste apparaît en « und » dans tous les lecteurs."
            )

    cmd = [_mkvmerge_path, "--gui-mode", "-o", str(output), str(source)]
    cmd += _donor_args(tracks)
    return cmd


def _group_by_donor(tracks: list[ExternalTrack]) -> dict[Path, list[ExternalTrack]]:
    """Pistes regroupées par fichier donneur, dans l'ordre de première apparition."""
    groups: dict[Path, list[ExternalTrack]] = {}
    for t in tracks:
        groups.setdefault(t.source_path, []).append(t)
    return groups


def premux_track_order(tracks: list[ExternalTrack]) -> list[ExternalTrack]:
    """L'ordre dans lequel mkvmerge écrit ces pistes dans l'intermédiaire.

    Il ne suit pas l'ordre où on les a choisies : mkvmerge écrit fichier par
    fichier, dans l'ordre où ils lui sont donnés, et à l'intérieur d'un fichier
    dans l'ordre de ses propres pistes. C'est cet ordre-là, et lui seul, qui
    donne l'index des pistes greffées quand ffmpeg reprend l'intermédiaire.
    """
    ordonnees: list[ExternalTrack] = []
    for donor_tracks in _group_by_donor(tracks).values():
        ordonnees += sorted(donor_tracks, key=lambda t: t.source_tid)
    return ordonnees


def _donor_args(tracks: list[ExternalTrack]) -> list[str]:
    """Arguments mkvmerge des fichiers donneurs, groupés par fichier.

    Les pistes venant d'un même donneur sont regroupées : mkvmerge lit chaque
    fichier une seule fois, avec les options de chacune de ses pistes.
    """
    args: list[str] = []

    for donor, donor_tracks in _group_by_donor(tracks).items():
        audio_tids = [str(t.source_tid) for t in donor_tracks if t.kind == TrackKind.AUDIO]
        sub_tids   = [str(t.source_tid) for t in donor_tracks if t.kind == TrackKind.SUBTITLE]

        # Ne prendre du donneur QUE les pistes demandées : sans ça mkvmerge
        # embarque tout le fichier (vidéo et chapitres compris).
        args += ["--no-video", "--no-chapters", "--no-global-tags"]
        args += ["--audio-tracks", ",".join(audio_tids)] if audio_tids else ["--no-audio"]
        args += ["--subtitle-tracks", ",".join(sub_tids)] if sub_tids else ["--no-subtitles"]

        for t in donor_tracks:
            args += _track_options(t)

        args.append(str(donor))

    return args


def build_strip_command(
    video:   Path,
    source:  Path,
    output:  Path,
    fps:     str = "",
    tracks:  list[ExternalTrack] | None = None,
    audio_source:    Path | None      = None,
    audio_indices:   list[int] | None = None,
    sous_titres:     list[int] | None = None,
) -> list[str]:
    """
    Remuxe le flux HEVC `video` (RPU retiré) avec les pistes de `source`.

    Un flux HEVC brut ne porte aucun horodatage : sans `fps`, mkvmerge se
    rabat sur ce qu'annonce le VUI du flux, qui peut manquer. On lui donne la
    cadence lue sur la source — sinon la vidéo dérive de l'audio.

    La décision ne portait ici que sur la vidéo : l'audio et les sous-titres
    de la source étaient recopiés en bloc, quoi qu'ait annoncé l'écran.

    - `audio_source` : Matroska audio produit à part (voir
      `encoder.build_audio_command`). Présent, il remplace entièrement l'audio
      de la source — c'est le cas dès qu'une piste est transcodée.
    - `audio_indices` : index ffmpeg des pistes de la source à garder, quand
      il n'y a rien à transcoder mais des pistes à écarter.
    - `sous_titres` : index ffmpeg des sous-titres à garder. `None` = tous.
    """
    if output.resolve() == source.resolve():
        raise ValueError(
            f"Chemin de sortie identique à la source ({source}). "
            f"Remux refusé pour éviter la corruption du fichier source."
        )

    cmd = [_mkvmerge_path, "--gui-mode", "-o", str(output)]
    if fps:
        # ffprobe donne "24/1" ou "24000/1001" ; mkvmerge accepte la fraction,
        # mais "24/1p" se lit plus mal que "24p" dans le journal.
        num, _, den = fps.partition("/")
        cmd += ["--default-duration",
                f"0:{num}p" if den in ("", "1") else f"0:{fps}p"]
    cmd += [str(video), "--no-video"]

    if audio_source is not None:
        cmd += ["--no-audio"]
    elif audio_indices is not None:
        tids = [str(mkvmerge_tid(source, i, TrackKind.AUDIO)) for i in audio_indices]
        cmd += ["--audio-tracks", ",".join(tids)] if tids else ["--no-audio"]

    if sous_titres is not None:
        tids = [str(mkvmerge_tid(source, i, TrackKind.SUBTITLE)) for i in sous_titres]
        cmd += ["--subtitle-tracks", ",".join(tids)] if tids else ["--no-subtitles"]

    cmd += [str(source)]

    if audio_source is not None:
        cmd += ["--no-video", "--no-chapters", "--no-global-tags", "--no-subtitles",
                str(audio_source)]

    cmd += _donor_args(tracks or [])
    return cmd


# ─── Extrait de contrôle ──────────────────────────────────────────────────────

SAMPLE_SECONDS = 60


def timecode(seconds: float) -> str:
    """Secondes → HH:MM:SS, format attendu par --split."""
    s = max(0, int(seconds))
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def sample_windows(duration: float, has_stretch: bool,
                   first_cue: Optional[float] = None) -> list[float]:
    """
    Positions de départ des extraits de contrôle.

    Sans étirement, un seul extrait suffit : le décalage est constant, le
    vérifier une fois le vérifie partout. Avec étirement, la dérive
    s'accumule — il faut regarder tôt *et* tard, sinon on valide un début
    correct au-dessus d'une fin qui part.
    """
    if duration <= 0:
        return [0.0]
    if has_stretch:
        return [duration * 0.10, duration * 0.85]
    if first_cue is not None and first_cue > 3:
        return [first_cue - 3.0]
    return [duration * 0.25]


def build_sample_command(
    source:  Path,
    tracks:  list[ExternalTrack],
    output:  Path,
    starts:  list[float],
    length:  int = SAMPLE_SECONDS,
) -> list[str]:
    """
    Commande produisant un court extrait du résultat muxé.

    Le découpage est confié à mkvmerge, qui l'applique au flux **de sortie**,
    une fois le décalage et l'étirement posés. Découper les fichiers d'entrée
    séparément serait faux : chacun se calerait sur son propre keyframe et
    leur décalage relatif changerait, ce qui invaliderait justement ce qu'on
    cherche à vérifier.

    Plusieurs fenêtres sont concaténées dans un seul fichier (« + »), pour
    juger début et fin d'affilée.
    """
    cmd = build_mux_command(source, tracks, output)
    parts = ",+".join(
        f"{timecode(s)}-{timecode(s + length)}" for s in sorted(starts)
    )
    # Option globale : elle doit précéder le premier fichier d'entrée
    insert_at = cmd.index("-o")
    return cmd[:insert_at] + ["--split", f"parts:{parts}"] + cmd[insert_at:]


def sample_output_path(source: Path) -> Path:
    """Extrait de contrôle, écrit hors du dossier du film."""
    import tempfile
    return Path(tempfile.gettempdir()) / f"{source.stem}_[extrait].mkv"


def mux_output_path(source: Path) -> Path:
    """Chemin de sortie d'un mux sans réencodage (toujours MKV, jamais la source)."""
    return source.parent / f"{source.stem}{MUX_SUFFIX}.mkv"


# ─── Mux préalable à un encodage ──────────────────────────────────────────────

def needs_premux(tracks: list[ExternalTrack]) -> bool:
    """
    Ces pistes exigent-elles un mux avant l'encodage ?

    ffmpeg absorbe une piste greffée en une passe, décalage compris — mais pas
    un facteur d'étirement : `-itsoffset` ne fait qu'un décalage constant.
    mkvmerge, lui, sait étirer. On lui confie donc la greffe, puis ffmpeg
    encode le résultat.
    """
    return any(t.stretch for t in tracks)


def premux_output_path(source: Path) -> Path:
    """
    Intermédiaire d'un mux préalable, écrit hors du dossier du film.

    Il ne survit pas à l'encodage et n'a rien à faire à côté des originaux ;
    son nom ne doit pas non plus ressembler à une sortie que l'utilisateur
    voudrait garder.
    """
    import tempfile
    return Path(tempfile.gettempdir()) / f"{source.stem}_[premux].mkv"


# ─── Progression (--gui-mode) ─────────────────────────────────────────────────

_PROGRESS_RE = re.compile(r"^#GUI#progress\s+(\d+)%")
_ERROR_RE    = re.compile(r"^#GUI#error\s+(.*)")


def parse_progress(line: str) -> Optional[int]:
    """Pourcentage d'une ligne `#GUI#progress 42%`, ou None."""
    m = _PROGRESS_RE.match(line.strip())
    return int(m.group(1)) if m else None


def parse_error(line: str) -> Optional[str]:
    """Message d'une ligne `#GUI#error ...`, ou None."""
    m = _ERROR_RE.match(line.strip())
    return m.group(1).strip() if m else None


# ─── Processus de mux ─────────────────────────────────────────────────────────

class MuxProcess:
    """
    Wraps un processus mkvmerge actif.

    mkvmerge écrit sa progression sur stdout (--gui-mode), là où ffmpeg
    utilise stderr : les deux runners ne sont donc pas interchangeables.
    """

    def __init__(self, cmd: list[str]):
        self.cmd = cmd
        self._proc: Optional[subprocess.Popen] = None
        self._errors: list[str] = []

    def start(self) -> None:
        self._proc = subprocess.Popen(
            self.cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        # Voir scanner._ffprobe_json : lire dans l'encodage local
        # tue le thread de lecture dès qu'un nom de fichier en sort.
            encoding="utf-8", errors="replace",
            bufsize=1,
        )

    def iter_progress(self):
        """Itère en retournant (ligne_brute, pourcentage|None)."""
        if self._proc is None or self._proc.stdout is None:
            return
        for raw in self._proc.stdout:
            line = raw.rstrip()
            err = parse_error(line)
            if err:
                self._errors.append(err)
            yield line, parse_progress(line)

    @property
    def errors(self) -> list[str]:
        """Messages #GUI#error rencontrés pendant le mux."""
        return self._errors

    def terminate(self) -> None:
        if self._proc:
            self._proc.terminate()

    @property
    def returncode(self) -> Optional[int]:
        return self._proc.poll() if self._proc else None

    def wait(self) -> int:
        return self._proc.wait() if self._proc else -1
