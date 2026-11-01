"""
core/sous_titres.py — Sous-titres texte vers du MP4 : combler les longs silences.

Défaut ffmpeg mesuré le 2026-10-04 (8.1.2 et 8.1.3), reproductible depuis un
simple `.srt` : le muxeur MP4/MOV (`movenc`) perd les horodatages d'une piste
`mov_text` dès qu'un silence entre deux répliques — ou avant la première —
dépasse 2³¹ µs, soit 2 147,48 s (35 min 47 s). La réplique suivante, et toutes
celles d'après, se retrouvent collées les unes aux autres au début du film.
Aucune erreur, code de retour nul ; mkvmerge relit le même MP4 avec les mêmes
temps faux : c'est l'écriture qui est fausse, pas la lecture.

Le cas typique est la piste « forced » : *Premier Contact* ouvre la sienne à
53 min 51 s, et sa VF forcée s'affichait dès les premières images.

Le même flux écrit en Matroska garde ses temps. D'où la parade : extraire les
pistes en SRT, intercaler toutes les `SEUIL_S` secondes de silence une réplique
invisible (`BOUCHE_TROU`, une espace insécable pendant 1 ms — une espace simple
est retirée par le décodeur SRT), puis les réunir dans un Matroska « porteur »
où l'encodage prend ses sous-titres à la place de ceux de la source.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .i18n import _

# Marge sous les 2 147,48 s du défaut.
SEUIL_S = 1800.0
BOUCHE_TROU = " "
DUREE_BOUCHE_TROU_S = 0.001

_TEMPS = re.compile(
    r"(\d+):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d+):(\d{2}):(\d{2})[,.](\d{3})")


def _secondes(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def _horodatage(t: float) -> str:
    ms = round(t * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _repliques(texte: str) -> list[tuple[float, float, str]]:
    """(début, fin, bloc) de chaque réplique, le bloc sans son numéro."""
    repliques = []
    for bloc in re.split(r"\n\s*\n", texte.replace("\r\n", "\n").strip()):
        lignes = bloc.split("\n")
        for i, ligne in enumerate(lignes):
            m = _TEMPS.search(ligne)
            if m:
                debut, fin = _secondes(*m.groups()[:4]), _secondes(*m.groups()[4:])
                repliques.append((debut, fin, "\n".join(lignes[i:])))
                break
    return repliques


def instants_bouche_trou(repliques: list[tuple[float, float]]) -> list[float]:
    """Où poser une réplique invisible pour qu'aucun silence ne dépasse `SEUIL_S`.

    Le silence compte depuis le début du film : c'est le cas de la piste
    forcée, dont la première réplique arrive tard.
    """
    instants: list[float] = []
    fin_precedente = 0.0
    for debut, fin in sorted(repliques):
        while debut - fin_precedente > SEUIL_S:
            fin_precedente += SEUIL_S
            instants.append(fin_precedente)
        fin_precedente = max(fin_precedente, fin)
    return instants


def combler_srt(texte: str) -> tuple[str, int]:
    """Le SRT avec ses bouche-trous, renuméroté, et leur nombre."""
    repliques = _repliques(texte)
    instants = instants_bouche_trou([(d, f) for d, f, _texte in repliques])
    if not instants:
        return texte, 0
    bouche_trous = [
        (t, t + DUREE_BOUCHE_TROU_S,
         f"{_horodatage(t)} --> {_horodatage(t + DUREE_BOUCHE_TROU_S)}\n{BOUCHE_TROU}")
        for t in instants]
    tout = sorted(repliques + bouche_trous, key=lambda r: r[0])
    blocs = [f"{n}\n{bloc}" for n, (_d, _f, bloc) in enumerate(tout, start=1)]
    return "\n\n".join(blocs) + "\n", len(instants)


# ─── WebVTT que ffmpeg ne lit pas ─────────────────────────────────────────────
#
# mkvmerge (au moins depuis v85) range un WebVTT sous le code Matroska
# `S_TEXT/WEBVTT`, que ffmpeg 8.1 ne connaît pas : la piste sort en
# `codec_name=unknown`, et toute commande qui la lit échoue — « no decoder
# found for: none » en conversion, « Subtitle codec none is not supported » en
# copie (mesuré le 2026-11-01, 8.1.2 et 8.1.3). ffprobe en lit pourtant les
# paquets : chacun est le texte d'une réplique, avec son début et sa durée. Le
# SRT se reconstruit donc à partir d'eux, sans ffmpeg.

ENTETE_WEBVTT = b"WEBVTT"
# Ce que SRT garde de la mise en forme WebVTT ; les autres balises (`<c.white>`,
# `<v Nom>`, `<ruby>`, horodatages internes) sont retirées, leur texte gardé.
_BALISES_SRT = {"i", "b", "u"}
_BALISE = re.compile(r"</?([A-Za-z]+)[^>]*>|<\d[\d:.]*>")
_ENTITES = {"&amp;": "&", "&lt;": "<", "&gt;": ">", "&nbsp;": "\u00a0",
            "&lrm;": "\u200e", "&rlm;": "\u200f"}


def octets_hexdump(dump: str) -> bytes:
    """Les octets d'un champ `data` ou `extradata` de ffprobe (`-show_data`),
    écrit en lignes `00000000: 5745 4256 …  WEBVTT…` : la zone hexadécimale
    occupe toujours les colonnes 10 à 48, complétée d'espaces en fin."""
    octets = bytearray()
    for ligne in dump.splitlines():
        if len(ligne) > 10 and ligne[8:10] == ": ":
            octets += bytes.fromhex(ligne[10:49].replace(" ", ""))
    return bytes(octets)


def texte_webvtt_vers_srt(texte: str) -> str:
    """Le texte d'une réplique WebVTT, en SRT : balises et entités."""
    def balise(m: re.Match) -> str:
        nom = (m.group(1) or "").lower()
        return m.group(0).lower() if nom in _BALISES_SRT else ""
    texte = _BALISE.sub(balise, texte)
    for entite, car in _ENTITES.items():
        texte = texte.replace(entite, car)
    return texte.strip("\n")


def srt_depuis_paquets(paquets: list[dict]) -> tuple[str, int]:
    """Le SRT des paquets ffprobe d'une piste WebVTT brute, et son nombre de
    répliques. Un paquet sans durée finit au début du suivant."""
    repliques = []
    for n, pq in enumerate(paquets):
        try:
            debut = float(pq["pts_time"])
        except (KeyError, TypeError, ValueError):
            continue
        try:
            fin = debut + float(pq["duration_time"])
        except (KeyError, TypeError, ValueError):
            suivant = paquets[n + 1].get("pts_time") if n + 1 < len(paquets) else None
            fin = float(suivant) if suivant else debut + 2.0
        texte = texte_webvtt_vers_srt(
            octets_hexdump(pq.get("data", "")).decode("utf-8", "replace"))
        if texte.strip():
            repliques.append((debut, fin, texte))
    blocs = [f"{n}\n{_horodatage(d)} --> {_horodatage(f)}\n{t}"
             for n, (d, f, t) in enumerate(repliques, start=1)]
    return ("\n\n".join(blocs) + "\n" if blocs else ""), len(repliques)


def ecrire_srt_webvtt_brut(source: Path, index: int, chemin: Path,
                           ffprobe_path: str = "ffprobe") -> str | None:
    """Écrit en SRT la piste de sous-titres `index` (rang parmi les
    sous-titres) d'une source où elle est en WebVTT brut. None si c'est fait,
    sinon la cause, lisible.

    ffprobe lit tout le fichier — il n'y a pas d'index des paquets d'une
    seule piste : 5 s pour 9,5 Go et 3663 répliques, sur disque local.
    """
    import json
    import subprocess
    cmd = [ffprobe_path, "-v", "error", "-select_streams", f"s:{index}",
           "-show_entries", "packet=pts_time,duration_time,data", "-show_data",
           "-of", "json", str(source)]
    try:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                           encoding="utf-8", errors="replace")
    except OSError as e:
        return str(e)
    if r.returncode != 0:
        return (r.stderr.strip().splitlines() or [f"code {r.returncode}"])[-1]
    try:
        paquets = json.loads(r.stdout).get("packets", [])
    except ValueError as e:
        return str(e)
    texte, n = srt_depuis_paquets(paquets)
    if not n:
        return _("the track contains no readable cue")
    chemin.write_text(texte, encoding="utf-8")
    return None


_EXT_TEXTE = {".srt", ".ass", ".ssa", ".vtt", ".sub"}
# Début d'un paquet MPEG-PS : un `.sub` VobSub, binaire, pas un MicroDVD.
_ENTETE_VOBSUB = b"\x00\x00\x01\xba"


def encodage_texte(chemin: Path) -> str | None:
    """Le jeu de caractères d'un fichier de sous-titres texte, pour ffmpeg
    (`-sub_charenc`) et mkvmerge (`--sub-charset`). None hors fichier texte.

    Mêmes essais que la mesure (`sync._read_text`) : un `.srt` que la mesure
    lisait en cp1252 partait ensuite chez ffmpeg, qui le lit en UTF-8, et
    perdait toutes ses répliques accentuées sans erreur (CR-50).
    """
    if chemin.suffix.lower() not in _EXT_TEXTE:
        return None
    try:
        brut = chemin.read_bytes()
    except OSError:
        return None
    if brut.startswith(_ENTETE_VOBSUB):
        return None
    for nom, codec in (("UTF-8", "utf-8-sig"), ("CP1252", "cp1252")):
        try:
            brut.decode(codec)
            return nom
        except UnicodeDecodeError:
            continue
    return "ISO-8859-1"


def pistes_a_porter(decision) -> list:
    """Les pistes texte de la source que la sortie MP4 garde, dans l'ordre.

    Vide hors MP4 : le défaut n'existe qu'à l'écriture du `mov_text`.
    """
    if decision.output_container != ".mp4":
        return []
    ecartes = {st.index for st in decision.sous_titres_ecartes}
    if decision.subtitle_indices is None and not ecartes:
        pistes = decision.info.subtitle_tracks
    else:
        pistes = decision.subtitles_finales
    return [st for st in pistes if not st.is_image_based]


def pistes_brutes_mkv(decision) -> list:
    """Les pistes WebVTT brutes qu'une sortie MKV garde : `build_command` les
    prend dans un `.srt` refait (`sous_titres_refaits`). En MP4, le porteur
    s'en charge (`pistes_a_porter`)."""
    if decision.output_container != ".mkv":
        return []
    tout_garder = (decision.subtitle_indices is None
                   and not decision.sous_titres_ecartes)
    pistes = (decision.info.subtitle_tracks if tout_garder
              else decision.subtitles_finales)
    return [st for st in pistes if st.brut]


@dataclass
class Greffe:
    """Un sous-titre greffé à faire passer par le porteur (CR-34)."""
    entree:      Path     # le donneur, ou l'intermédiaire d'un mux préalable
    flux:        int      # `0:s:N` dans cette entrée
    piste:       object   # SubtitleTrack : langue, titre, drapeaux du porteur
    jeu:         str | None = None   # `-sub_charenc`, hors UTF-8
    decalage_ms: int = 0


def greffes_a_porter(decision, recompose: Path | None = None) -> list[Greffe]:
    """Les sous-titres greffés d'une sortie MP4, dans l'ordre de sortie.

    Le porteur ne réécrivait que ceux de la source : un `.srt` forcé greffé,
    première réplique à 36 min, sortait en `mov_text` avec ses répliques à
    0 s et 2 s (CR-34). En MP4 ils sont tous du texte — un sous-titre image
    ou stylé impose le MKV. L'ordre est celui de `encoder.build_command` :
    greffes directes, puis celles d'un mux préalable (les deux s'excluent).

    `recompose` : le Matroska que mkvmerge a recomposé (réencodage Dolby
    Vision), où les greffes suivent les sous-titres gardés de la source,
    décalage **et étirement** appliqués. Elles y sont lues : depuis leur
    donneur, ffmpeg ne saurait pas les étirer.
    """
    if decision.output_container != ".mp4":
        return []
    from .i18n import N_, ErreurAffichable
    from .muxer import TrackKind, ffmpeg_stream_index, premux_track_order
    from .scanner import SubtitleTrack

    def piste(t) -> SubtitleTrack:
        return SubtitleTrack(index=0, codec="subrip", language=t.language,
                             title=t.track_name, forced=t.is_forced,
                             default=t.is_default)

    def sous_titres(pistes) -> list:
        return [t for t in premux_track_order(pistes) if t.kind == TrackKind.SUBTITLE]

    if recompose is not None:
        n_gardes = len(decision.subtitles_finales)
        return [Greffe(entree=recompose, flux=n_gardes + j, piste=piste(t))
                for j, t in enumerate(sous_titres(decision.external_tracks))]

    greffes: list[Greffe] = []
    for t in decision.external_tracks:
        if t.kind != TrackKind.SUBTITLE:
            continue
        if t.stretch:
            # Extraite de son donneur, elle n'aurait que son décalage : une
            # dérive de 4 % (24000/25025), cinq minutes en fin de film. Le
            # chemin principal l'étire par un mux préalable, le réencodage DV
            # par sa recomposition — y arriver ici est un chemin oublié.
            raise ErreurAffichable(N_(
                "The subtitle “{track}” needs a stretch factor, which cannot be "
                "applied while preparing the subtitles: it would drift."),
                track=t.source_path.name)
        jeu = encodage_texte(t.source_path)
        greffes.append(Greffe(
            entree=t.source_path,
            flux=ffmpeg_stream_index(t.source_path, t.source_tid, t.kind),
            piste=piste(t), jeu=jeu if jeu != "UTF-8" else None,
            decalage_ms=t.delay_ms))
    n_source = len(decision.info.subtitle_tracks)
    for j, t in enumerate(sous_titres(decision.premuxed_tracks)):
        # Déjà recalées et réencodées en UTF-8 par mkvmerge, à la suite des
        # sous-titres de la source dans l'intermédiaire.
        greffes.append(Greffe(entree=decision.encode_source,
                              flux=n_source + j, piste=piste(t)))
    return greffes


def build_extraction_greffe(g: Greffe, chemin: Path,
                            ffmpeg_path: str = "ffmpeg") -> list[str]:
    """Le sous-titre greffé en `.srt`, son décalage appliqué comme à
    l'encodage (`-itsoffset`, ou `-ss` pour un décalage négatif)."""
    cmd = [ffmpeg_path, "-y", "-loglevel", "error"]
    if g.decalage_ms > 0:
        cmd += ["-itsoffset", f"{g.decalage_ms / 1000:.3f}"]
    elif g.decalage_ms < 0:
        cmd += ["-ss", f"{-g.decalage_ms / 1000:.3f}"]
    if g.jeu:
        cmd += ["-sub_charenc", g.jeu]
    cmd += ["-i", str(g.entree), "-map", f"0:s:{g.flux}", "-c:s", "srt", str(chemin)]
    return cmd


def build_extraction(source: Path, pistes: list, dossier: Path,
                     ffmpeg_path: str = "ffmpeg") -> tuple[list[str] | None, list[Path]]:
    """Une lecture de la source, un `.srt` par piste.

    Une piste WebVTT brute (`brut`) a son chemin dans la liste, à son rang,
    mais pas de place dans la commande : ffmpeg ne la lit pas, elle s'écrit
    avec `ecrire_srt_webvtt_brut`. Commande None s'il ne reste qu'elles.
    """
    cmd = [ffmpeg_path, "-y", "-loglevel", "error", "-i", str(source)]
    chemins = []
    for n, st in enumerate(pistes):
        chemin = dossier / f"{source.stem}.iris_st{n}.srt"
        if not getattr(st, "brut", False):
            cmd += ["-map", f"0:s:{st.index}", "-c:s", "srt", str(chemin)]
        chemins.append(chemin)
    return (cmd if "-map" in cmd else None), chemins


def build_porteur(pistes: list, chemins: list[Path], sortie: Path,
                  ffmpeg_path: str = "ffmpeg") -> list[str]:
    """Réunit les `.srt` en un Matroska, avec langue, titre et drapeaux.

    ffmpeg et non mkvmerge : le porteur ne doit pas dépendre d'un outil
    optionnel, et le défaut ne touche pas son écriture Matroska (mesuré).
    """
    cmd = [ffmpeg_path, "-y", "-loglevel", "error"]
    for chemin in chemins:
        cmd += ["-i", str(chemin)]
    for n in range(len(chemins)):
        cmd += ["-map", f"{n}:s:0"]
    cmd += ["-c:s", "copy"]
    for n, st in enumerate(pistes):
        if st.language:
            cmd += [f"-metadata:s:s:{n}", f"language={st.language}"]
        if st.title:
            cmd += [f"-metadata:s:s:{n}", f"title={st.title}"]
        drapeaux = [d for d, oui in (("default", st.default),
                                     ("forced", st.forced)) if oui]
        cmd += [f"-disposition:s:{n}", "+".join(drapeaux) or "0"]
    cmd += [str(sortie)]
    return cmd
