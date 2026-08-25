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
from dataclasses import dataclass, field
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
    try:
        r = subprocess.run(
            [_mkvmerge_path, "-J", str(path)],
            capture_output=True, text=True, timeout=30,
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
    return tracks


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

    # Regroupement par fichier donneur, dans l'ordre de première apparition
    groups: dict[Path, list[ExternalTrack]] = {}
    for t in tracks:
        groups.setdefault(t.source_path, []).append(t)

    for donor, donor_tracks in groups.items():
        audio_tids = [str(t.source_tid) for t in donor_tracks if t.kind == TrackKind.AUDIO]
        sub_tids   = [str(t.source_tid) for t in donor_tracks if t.kind == TrackKind.SUBTITLE]

        # Ne prendre du donneur QUE les pistes demandées : sans ça mkvmerge
        # embarque tout le fichier (vidéo et chapitres compris).
        cmd += ["--no-video", "--no-chapters", "--no-global-tags"]
        cmd += ["--audio-tracks", ",".join(audio_tids)] if audio_tids else ["--no-audio"]
        cmd += ["--subtitle-tracks", ",".join(sub_tids)] if sub_tids else ["--no-subtitles"]

        for t in donor_tracks:
            cmd += _track_options(t)

        cmd.append(str(donor))

    return cmd


def mux_output_path(source: Path) -> Path:
    """Chemin de sortie d'un mux sans réencodage (toujours MKV, jamais la source)."""
    return source.parent / f"{source.stem}{MUX_SUFFIX}.mkv"


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
