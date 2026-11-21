"""
core/ass.py — Sous-titres ASS/SSA convertis en SRT (IE-204).

Jellyfin incruste un ASS à la lecture quand le client ne le rend pas, donc
transcode la vidéo (observé sur Firefox, raison du transcodage : le sous-titre).
Avec `ass_to_srt` dans le profil, un ASS de dialogue devient un SRT : styles,
positions et polices jointes partent.

La conversion est faite ici, pas par un outil. Mesuré le 2026-11-21 sur un ASS
d'essai : ffmpeg 8.1.3 (`-c:s srt`) écrit `<font size="48">` autour de chaque
réplique, garde les couleurs et sort un dessin (`{\\p1}m 0 0 l 100 0…`) comme
du texte ; seconv perd l'italique d'un style et laisse une réplique vide à la
place du dessin. Restent ici : le texte, les retours à la ligne, l'italique et
le gras (du style ou de la ligne), et `{\\an8}` pour une réplique en haut.

Une piste de panneaux ou de chansons (« Signs », « Songs »…) reste en ASS :
convertie, elle empilerait en bas de l'image des textes faits pour être posés
sur les écriteaux.
"""
from __future__ import annotations

import re
from pathlib import Path

from .sous_titres import _horodatage


def est_ass(codec: str) -> bool:
    """ASS ou SSA : `ass`/`ssa` pour ffprobe, « SubStationAlpha » pour mkvmerge."""
    low = (codec or "").lower()
    return low in ("ass", "ssa") or "substation" in low


_PANNEAUX = re.compile(
    r"\b(signs?|songs?|karaok\w*|panneaux?|chansons?|typeset\w*|s\s*&\s*s)\b",
    re.IGNORECASE)


def piste_de_panneaux(titre: str) -> bool:
    """Le titre dit-il une piste de panneaux ou de chansons ?"""
    return bool(_PANNEAUX.search(titre or ""))


# Les types MIME qu'une police jointe porte dans un Matroska : ceux que
# mkvmerge pose, et les officiels (RFC 8081).
MIME_POLICES = (
    "application/x-truetype-font", "application/vnd.ms-opentype",
    "application/x-font-ttf", "application/x-font-otf", "application/x-font",
    "application/font-sfnt", "font/ttf", "font/otf", "font/sfnt",
    "font/collection", "font/woff", "font/woff2",
)


def build_extraction(source: Path, pistes: list, dossier: Path,
                     ffmpeg_path: str = "ffmpeg") -> tuple[list[str], list[Path]]:
    """Une lecture de la source, un `.ass` par piste, recopié tel quel."""
    cmd = [ffmpeg_path, "-y", "-loglevel", "error", "-i", str(source)]
    chemins = []
    for st in pistes:
        chemin = dossier / f"{source.stem}.iris_ass{st.index}.ass"
        cmd += ["-map", f"0:s:{st.index}", "-c:s", "copy", str(chemin)]
        chemins.append(chemin)
    return cmd, chemins


def sortie_srt(chemin_ass: Path) -> Path:
    return chemin_ass.with_suffix(".srt")


def _temps(valeur: str) -> float:
    h, m, s = valeur.strip().split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def _vrai(v: str) -> bool:
    """Un booléen de style ASS : -1 (v4+) ou 1."""
    return v.strip() not in ("", "0")


_BLOC     = re.compile(r"\{([^}]*)\}")
_DESSIN   = re.compile(r"\\p(\d+)")
_ITALIQUE = re.compile(r"\\i(\d?)(?![a-z])")
_GRAS     = re.compile(r"\\b(\d*)(?![a-z])")
_ALIGNE   = re.compile(r"\\(an?)(\d+)")


def _texte(brut: str, italique: bool, gras: bool, haut: bool) -> str:
    """Le texte d'une ligne Dialogue en SRT. Vide si ce n'est qu'un dessin."""
    sortie: list[str] = []
    dessin = False
    it, gr = italique, gras
    ouvert_it = ouvert_gr = False

    def poser(morceau: str) -> None:
        nonlocal ouvert_it, ouvert_gr
        if not morceau:
            return
        # Balises refermées et rouvertes à chaque changement : toujours bien
        # imbriquées.
        if ouvert_gr != gr or ouvert_it != it:
            if ouvert_it:
                sortie.append("</i>")
            if ouvert_gr:
                sortie.append("</b>")
            if gr:
                sortie.append("<b>")
            if it:
                sortie.append("<i>")
            ouvert_gr, ouvert_it = gr, it
        sortie.append(morceau)

    pos = 0
    for m in _BLOC.finditer(brut):
        if not dessin:
            poser(brut[pos:m.start()])
        pos = m.end()
        bloc = m.group(1)
        for d in _DESSIN.finditer(bloc):
            dessin = d.group(1) != "0"
        for i in _ITALIQUE.finditer(bloc):
            it = italique if i.group(1) == "" else i.group(1) == "1"
        for g in _GRAS.finditer(bloc):
            gr = gras if g.group(1) == "" else g.group(1) != "0"
        for a in _ALIGNE.finditer(bloc):
            n = int(a.group(2))
            # `\an` : pavé numérique ; `\a` (SSA) : 5 à 7 en haut.
            haut = n in (7, 8, 9) if a.group(1) == "an" else n in (5, 6, 7)
    if not dessin:
        poser(brut[pos:])
    if ouvert_it:
        sortie.append("</i>")
    if ouvert_gr:
        sortie.append("</b>")

    texte = ("".join(sortie).replace("\\N", "\n").replace("\\n", "\n")
             .replace("\\h", "\u00a0"))
    texte = "\n".join(l.strip() for l in texte.split("\n"))
    texte = re.sub(r"\n{2,}", "\n", texte).strip("\n")
    if not re.sub(r"</?[ib]>", "", texte).strip():
        return ""
    return ("{\\an8}" + texte) if haut else texte


def ass_vers_srt(texte: str) -> tuple[str, int]:
    """Le SRT d'un fichier ASS/SSA, et son nombre de répliques.

    Lignes `Dialogue` seules (pas les `Comment`), dans l'ordre des temps ; le
    champ Text est le dernier de `Format`, il peut contenir des virgules.
    """
    section = ""
    fmt_styles: list[str] = []
    fmt_events: list[str] = []
    styles: dict[str, tuple[bool, bool, bool]] = {}
    repliques: list[tuple[float, float, str]] = []

    for ligne in texte.splitlines():
        ligne = ligne.strip().lstrip("\ufeff")
        if ligne.startswith("[") and ligne.endswith("]"):
            section = ligne.lower()
            continue
        cle, sep, valeur = ligne.partition(":")
        cle = cle.strip().lower()
        if not sep:
            continue
        if section.endswith("styles]"):
            if cle == "format":
                fmt_styles = [c.strip().lower() for c in valeur.split(",")]
            elif cle == "style" and fmt_styles:
                champs = dict(zip(fmt_styles, (c.strip() for c in
                                               valeur.split(",", len(fmt_styles) - 1))))
                try:
                    align = int(champs.get("alignment", "2"))
                except ValueError:
                    align = 2
                v4plus = "outlinecolour" in fmt_styles
                haut = align in (7, 8, 9) if v4plus else align in (5, 6, 7)
                styles[champs.get("name", "")] = (
                    _vrai(champs.get("italic", "0")), _vrai(champs.get("bold", "0")), haut)
        elif section == "[events]":
            if cle == "format":
                fmt_events = [c.strip().lower() for c in valeur.split(",")]
            elif cle == "dialogue" and fmt_events:
                champs = dict(zip(fmt_events,
                                  valeur.lstrip().split(",", len(fmt_events) - 1)))
                try:
                    debut, fin = _temps(champs["start"]), _temps(champs["end"])
                except (KeyError, ValueError):
                    continue
                if fin <= debut:
                    continue
                it, gr, haut = styles.get(champs.get("style", "").strip().lstrip("*"),
                                          (False, False, False))
                rendu = _texte(champs.get("text", ""), it, gr, haut)
                if rendu:
                    repliques.append((debut, fin, rendu))

    repliques.sort(key=lambda r: r[0])
    blocs = [f"{n}\n{_horodatage(d)} --> {_horodatage(f)}\n{x}"
             for n, (d, f, x) in enumerate(repliques, start=1)]
    return ("\n\n".join(blocs) + "\n" if blocs else ""), len(repliques)


def ecrire_srt(chemin_ass: Path) -> int:
    """Écrit le SRT à côté de l'ASS (`sortie_srt`). Rend le nombre de
    répliques : 0, rien d'écrit — la piste reste en ASS."""
    try:
        texte = chemin_ass.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return 0
    srt, n = ass_vers_srt(texte)
    if n:
        try:
            sortie_srt(chemin_ass).write_text(srt, encoding="utf-8")
        except OSError:
            return 0
    return n
