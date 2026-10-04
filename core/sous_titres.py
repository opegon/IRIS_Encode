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
from pathlib import Path

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
    instants = instants_bouche_trou([(d, f) for d, f, _ in repliques])
    if not instants:
        return texte, 0
    bouche_trous = [
        (t, t + DUREE_BOUCHE_TROU_S,
         f"{_horodatage(t)} --> {_horodatage(t + DUREE_BOUCHE_TROU_S)}\n{BOUCHE_TROU}")
        for t in instants]
    tout = sorted(repliques + bouche_trous, key=lambda r: r[0])
    blocs = [f"{n}\n{bloc}" for n, (_, _, bloc) in enumerate(tout, start=1)]
    return "\n\n".join(blocs) + "\n", len(instants)


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


def build_extraction(source: Path, pistes: list, dossier: Path,
                     ffmpeg_path: str = "ffmpeg") -> tuple[list[str], list[Path]]:
    """Une lecture de la source, un `.srt` par piste."""
    cmd = [ffmpeg_path, "-y", "-loglevel", "error", "-i", str(source)]
    chemins = []
    for n, st in enumerate(pistes):
        chemin = dossier / f"{source.stem}.iris_st{n}.srt"
        cmd += ["-map", f"0:s:{st.index}", "-c:s", "srt", str(chemin)]
        chemins.append(chemin)
    return cmd, chemins


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
