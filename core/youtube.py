"""
core/youtube.py — Une vidéo YouTube, téléchargée pour entrer dans la file (IE-180).

yt-dlp lit la page et télécharge ; Deno résout les défis JavaScript de YouTube,
sans lesquels yt-dlp ne voit plus les formats (wiki yt-dlp « EJS »). Les deux
sont posés par le preflight dans `bin/yt-dlp/` et cherchés là seulement : le
chemin de Deno est passé à yt-dlp, rien ne dépend du PATH.

Ce qui est téléchargé : la vidéo à la définition choisie — YouTube ne sert la
1440p et la 2160p qu'en VP9 ou AV1, elle sera réencodée de toute façon —,
l'audio AAC de la piste d'origine, et les sous-titres cochés, convertis en SRT
et intégrés. Le tout dans un MKV, que l'accueil analyse ensuite comme
n'importe quel fichier.

Les formats sont choisis ici, par leur identifiant, et non par un filtre
yt-dlp sur la hauteur : un film en 2,39:1 publié en « 2160p » fait 3840 × 1608,
et `height=2160` ne le trouverait pas. Le palier se lit dans la note du
format (« 2160p60 HDR »).
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .i18n import N_, ErreurAffichable

# Les définitions proposées, quand la vidéo les a.
PALIERS = (2160, 1440, 1080)

# Marques des lignes que l'on fait écrire à yt-dlp, pour les reconnaître dans
# le reste de sa sortie.
_PROGRES = "IRIS-PROGRES "
_FICHIER = "IRIS-FICHIER "

_DELAI_ANALYSE_S = 120


@dataclass(frozen=True)
class SousTitre:
    cle:   str            # clé yt-dlp : « fr », « en-orig »
    langue: str           # code de langue : « fr », « en »
    nom:   str            # nom donné par YouTube : « French »
    auto:  bool           # généré automatiquement (reconnaissance vocale)


@dataclass
class Video:
    url:       str
    ident:     str
    titre:     str
    duree:     Optional[float]
    # Palier → identifiant du meilleur format vidéo seul de ce palier, de la
    # plus haute définition à la plus basse.
    formats:   dict[int, str] = field(default_factory=dict)
    audio:     str = ""        # identifiant du format audio retenu
    audio_aac: bool = True     # faux : pas d'AAC, repli sur le meilleur audio
    sous_titres: list[SousTitre] = field(default_factory=list)

    @property
    def hauteurs(self) -> list[int]:
        return list(self.formats)


# ─── Outils ───────────────────────────────────────────────────────────────────

def outils(bin_dir: Path) -> Optional[tuple[Path, Path]]:
    """yt-dlp et Deno s'ils sont posés tous les deux, sinon None."""
    from .preflight import chemin_local
    ytdlp, deno = chemin_local("yt-dlp", bin_dir), chemin_local("deno", bin_dir)
    return (ytdlp, deno) if ytdlp.is_file() and deno.is_file() else None


# ─── Lecture de la page ───────────────────────────────────────────────────────

def _palier(f: dict) -> Optional[int]:
    """Le palier annoncé par YouTube (« 1080p60 » → 1080), à défaut la hauteur."""
    m = re.match(r"(\d{3,4})p", str(f.get("format_note") or ""))
    if m:
        return int(m.group(1))
    h = f.get("height")
    return h if isinstance(h, int) else None


def _video_seule(f: dict) -> bool:
    return (f.get("vcodec") not in (None, "none")
            and f.get("acodec") in (None, "none") and not f.get("has_drm"))


def _audio_seul(f: dict) -> bool:
    return (f.get("vcodec") in (None, "none")
            and f.get("acodec") not in (None, "none") and not f.get("has_drm"))


def _choisir_formats(formats: list[dict]) -> dict[int, str]:
    """Palier → meilleur format vidéo seul. yt-dlp liste les formats du moins
    bon au meilleur : le dernier d'un palier l'emporte."""
    par_palier: dict[int, str] = {}
    for f in formats:
        p = _palier(f) if _video_seule(f) else None
        if p is not None:
            par_palier[p] = str(f["format_id"])
    retenus = [p for p in PALIERS if p in par_palier]
    if not retenus and par_palier:
        # Une vidéo ancienne ou verticale : sa meilleure définition seule.
        retenus = [max(par_palier)]
    return {p: par_palier[p] for p in retenus}


def _choisir_audio(formats: list[dict]) -> tuple[str, bool]:
    """L'audio de la piste d'origine, en AAC si elle en a un.

    Une vidéo doublée publie une piste par langue ; yt-dlp donne à celle
    d'origine la plus forte `language_preference`. À préférence égale, le
    dernier listé — le meilleur.
    """
    audios = [(i, f) for i, f in enumerate(formats) if _audio_seul(f)]
    if not audios:
        return "", False
    aac = [(i, f) for i, f in audios
           if str(f.get("acodec", "")).startswith("mp4a")]
    candidats = aac or audios
    _i, meilleur = max(candidats,
                       key=lambda c: (c[1].get("language_preference") or 0, c[0]))
    return str(meilleur["format_id"]), bool(aac)


def _nom_piste(pistes: list[dict], cle: str) -> str:
    nom = next((p.get("name") for p in pistes if p.get("name")), "")
    return str(nom or cle)


def _choisir_sous_titres(donnees: dict) -> list[SousTitre]:
    """Les sous-titres déposés, puis ceux générés dans la langue d'origine.

    YouTube propose les seconds traduits automatiquement dans une centaine de
    langues : seule la transcription d'origine (`<langue>-orig`) est gardée.
    """
    out: list[SousTitre] = []
    for cle, pistes in sorted((donnees.get("subtitles") or {}).items()):
        if cle == "live_chat":
            continue
        out.append(SousTitre(cle, cle, _nom_piste(pistes, cle), auto=False))
    auto = donnees.get("automatic_captions") or {}
    originaux = sorted(c for c in auto if c.endswith("-orig"))
    if not originaux and donnees.get("language") in auto:
        originaux = [donnees["language"]]
    for cle in originaux:
        out.append(SousTitre(cle, cle.removesuffix("-orig"),
                             _nom_piste(auto[cle], cle), auto=True))
    return out


def lire_infos(donnees: dict, url: str) -> Video:
    """La vidéo telle que la décrit `yt-dlp -J`."""
    formats = donnees.get("formats") or []
    audio, aac = _choisir_audio(formats)
    duree = donnees.get("duration")
    return Video(
        url=donnees.get("webpage_url") or url,
        ident=str(donnees.get("id") or ""),
        titre=str(donnees.get("title") or ""),
        duree=float(duree) if isinstance(duree, (int, float)) else None,
        formats=_choisir_formats(formats),
        audio=audio, audio_aac=aac,
        sous_titres=_choisir_sous_titres(donnees),
    )


def _base(ytdlp: Path, deno: Path) -> list[str]:
    # `--no-config` : la configuration personnelle de yt-dlp, s'il y en a une,
    # changerait les noms, les formats, le dossier.
    return [str(ytdlp), "--no-config", "--no-playlist", "--encoding", "utf-8",
            "--js-runtimes", f"deno:{deno}"]


def _derniere_erreur(sortie: str) -> str:
    """La ligne `ERROR:` de yt-dlp, sans son préfixe ; à défaut la dernière."""
    lignes = [l.strip() for l in sortie.splitlines() if l.strip()]
    erreurs = [l for l in lignes if l.startswith("ERROR:")]
    texte = (erreurs or lignes or [""])[-1]
    return texte.removeprefix("ERROR:").strip()


def analyser(url: str, ytdlp: Path, deno: Path) -> Video:
    """Lit la page de la vidéo. Lève `ErreurAffichable` si yt-dlp échoue."""
    try:
        r = subprocess.run(_base(ytdlp, deno) + ["-J", url],
                           stdin=subprocess.DEVNULL, capture_output=True,
                           encoding="utf-8", errors="replace",
                           timeout=_DELAI_ANALYSE_S)
    except subprocess.TimeoutExpired:
        raise ErreurAffichable(N_("YouTube did not answer within {seconds} s."),
                               seconds=_DELAI_ANALYSE_S)
    except OSError as e:
        raise ErreurAffichable(N_("Cannot start yt-dlp: {error}"), error=e)
    if r.returncode != 0:
        raise ErreurAffichable.brute(_derniere_erreur(r.stderr or r.stdout))
    try:
        donnees = json.loads(r.stdout)
    except ValueError:
        raise ErreurAffichable(N_("yt-dlp returned an unreadable answer."))
    video = lire_infos(donnees, url)
    if not video.formats or not video.audio:
        raise ErreurAffichable(N_("This video has no downloadable format."))
    return video


# ─── Téléchargement ───────────────────────────────────────────────────────────

def commande(ytdlp: Path, deno: Path, ffmpeg: str, video: Video, hauteur: int,
             sous_titres: list[SousTitre], dossier: Path) -> list[str]:
    """La ligne de commande du téléchargement."""
    cmd = _base(ytdlp, deno) + [
        "--ffmpeg-location", ffmpeg,
        "-f", f"{video.formats[hauteur]}+{video.audio}",
        "--merge-output-format", "mkv",
        # `--print` rend yt-dlp silencieux : `--progress` garde la progression.
        "--newline", "--progress",
        "--progress-template", "download:" + _PROGRES + "%(progress._percent_str)s",
        "--print", "after_move:" + _FICHIER + "%(filepath)s",
        "-P", str(dossier), "-o", "%(title)s [%(id)s].%(ext)s",
    ]
    if sous_titres:
        cmd += ["--sub-langs", ",".join(re.escape(s.cle) for s in sous_titres),
                "--convert-subs", "srt", "--embed-subs"]
        if any(not s.auto for s in sous_titres):
            cmd.append("--write-subs")
        if any(s.auto for s in sous_titres):
            cmd.append("--write-auto-subs")
    cmd.append(video.url)
    return cmd


def lire_progres(ligne: str) -> Optional[float]:
    """La part faite (0 à 1) d'une ligne de progression, ou None."""
    if not ligne.startswith(_PROGRES):
        return None
    m = re.search(r"(\d+(?:\.\d+)?)%", ligne)
    return min(float(m.group(1)) / 100, 1.0) if m else None


def lire_fichier(ligne: str) -> Optional[Path]:
    return Path(ligne[len(_FICHIER):].strip()) if ligne.startswith(_FICHIER) else None


class Telechargement:
    """Un téléchargement, arrêtable depuis un autre fil."""

    def __init__(self) -> None:
        self._proc: Optional[subprocess.Popen] = None
        self._annule = False

    def annuler(self) -> None:
        self._annule = True
        if self._proc is not None and self._proc.poll() is None:
            self._proc.kill()

    @property
    def annule(self) -> bool:
        return self._annule

    def lancer(self, cmd: list[str], video: Video, dossier: Path,
               progres: Callable[[float], None]) -> Optional[Path]:
        """Télécharge ; rend le fichier produit, ou None si annulé.

        Lève `ErreurAffichable` sur un échec. Un arrêt ou un échec retire les
        fichiers partiels de cette vidéo écrits pendant ce téléchargement.
        """
        debut = time.time()
        produit: Optional[Path] = None
        sortie: list[str] = []
        try:
            self._proc = subprocess.Popen(
                cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, encoding="utf-8", errors="replace")
        except OSError as e:
            raise ErreurAffichable(N_("Cannot start yt-dlp: {error}"), error=e)
        try:
            if self._annule:          # annulé avant que le processus n'existe
                self._proc.kill()
            for ligne in self._proc.stdout or ():
                ligne = ligne.rstrip("\r\n")
                part = lire_progres(ligne)
                if part is not None:
                    progres(part)
                    continue
                chemin = lire_fichier(ligne)
                if chemin is not None:
                    produit = chemin
                    continue
                sortie.append(ligne)
            code = self._proc.wait()
        except BaseException:
            self._proc.kill()
            _nettoyer(dossier, video.ident, debut)
            raise
        if self._annule:
            _nettoyer(dossier, video.ident, debut)
            return None
        if code != 0 or produit is None or not produit.is_file():
            _nettoyer(dossier, video.ident, debut)
            raise ErreurAffichable.brute(_derniere_erreur("\n".join(sortie))
                                         or f"yt-dlp: {code}")
        return produit


def _nettoyer(dossier: Path, ident: str, depuis: float) -> None:
    """Les fichiers de cette vidéo écrits depuis `depuis` : morceaux `.part`,
    flux avant assemblage, sous-titres. Un téléchargement plus ancien de la
    même vidéo n'est pas touché."""
    if not ident:
        return
    marque = f"[{ident}]"
    try:
        fichiers = list(dossier.iterdir())
    except OSError:
        return
    for f in fichiers:
        try:
            if marque in f.name and f.is_file() and f.stat().st_mtime >= depuis - 1:
                f.unlink()
        except OSError:
            pass
