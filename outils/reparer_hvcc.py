"""Répare un MP4 HEVC dont la boîte `hvcC` est vide (IE-205).

La v0.9.3.12 recopiait en MP4 `hvc1` des flux HEVC qui portaient leurs
VPS/SPS/PPS dans le flux, pas dans l'en-tête de leur conteneur : la sortie avait
une `hvcC` de 8 octets, sans paramètres ni taille de préfixe des NAL, et plus
aucun lecteur ne l'ouvrait. Les images sont intactes, et les paramètres sont
recopiés dans le premier échantillon.

Le script en fait une `hvcC` (ffmpeg la construit sur ce seul échantillon,
passé en Annex B), l'insère à la place de la boîte vide, recale les tailles des
boîtes parentes et les positions des morceaux (`stco`/`co64`) de toutes les
pistes. La sortie est contrôlée (ffprobe l'ouvre, le début se décode) avant
d'être gardée.

    python outils/reparer_hvcc.py FICHIER_OU_DOSSIER... [--remplacer]

Sans `--remplacer`, la réparation s'écrit à côté (`<nom>.repare.mp4`) ; avec,
elle prend la place de l'original, une fois contrôlée.
"""
from __future__ import annotations

import argparse
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
# Parents à traverser jusqu'à la `hvcC`, et ce que chacun porte avant ses
# enfants : `stsd` (version, drapeaux, nombre d'entrées), l'entrée visuelle
# `hvc1`/`hev1` (78 octets de champs fixes).
_ENTETE_ENFANTS = {"moov": 0, "trak": 0, "mdia": 0, "minf": 0, "stbl": 0,
                   "stsd": 8, "hvc1": 78, "hev1": 78}


class Irreparable(Exception):
    """Le fichier n'a pas le défaut que ce script sait réparer."""


def _outil(nom: str) -> str:
    for candidat in (RACINE / "bin" / f"{nom}.exe", RACINE / "bin" / nom):
        if candidat.is_file():
            return str(candidat)
    trouve = shutil.which(nom)
    if not trouve:
        raise SystemExit(f"{nom} introuvable (ni dans bin/, ni dans le PATH)")
    return trouve


def _lire_entete(tete: bytes, pos: int, fin: int):
    taille, typ = struct.unpack_from(">I4s", tete)
    entete = 8
    if taille == 1:
        taille = struct.unpack_from(">Q", tete, 8)[0]
        entete = 16
    elif taille == 0:
        taille = fin - pos
    if taille < entete or pos + taille > fin:
        raise Irreparable(f"boîte {typ!r} mal formée à {pos}")
    return taille, typ.decode("latin-1"), entete


def _boites(data: bytes, debut: int, fin: int):
    """(position, taille, type, taille d'en-tête) des boîtes de data[debut:fin]."""
    pos = debut
    while pos + 8 <= fin:
        taille, typ, entete = _lire_entete(data[pos:pos + 16], pos, fin)
        yield pos, taille, typ, entete
        pos += taille


def _boites_fichier(fh, fin: int):
    pos = 0
    while pos + 8 <= fin:
        fh.seek(pos)
        taille, typ, entete = _lire_entete(fh.read(16), pos, fin)
        yield pos, taille, typ, entete
        pos += taille


def _chemin_hvcc(moov: bytes):
    """Les (position, en-tête, type) des parents de la `hvcC` vide, et la
    sienne. None si aucune piste n'a de `hvcC` vide."""
    def descendre(debut, fin, chemin):
        for pos, taille, typ, entete in _boites(moov, debut, fin):
            if typ == "hvcC" and chemin and chemin[-1][2] in ("hvc1", "hev1"):
                if taille == entete:
                    return chemin, (pos, taille, entete)
                continue
            if typ in _ENTETE_ENFANTS:
                trouve = descendre(pos + entete + _ENTETE_ENFANTS[typ],
                                   pos + taille, chemin + [(pos, entete, typ)])
                if trouve:
                    return trouve
        return None
    return descendre(0, len(moov), [])


def _table(moov: bytes, trak_pos: int, nom: str):
    """(position, taille, en-tête) de la table `nom` du `stbl` d'une trak."""
    def chercher(debut, fin):
        for pos, taille, typ, entete in _boites(moov, debut, fin):
            if typ == nom:
                return pos, taille, entete
            if typ in ("mdia", "minf", "stbl"):
                r = chercher(pos + entete, pos + taille)
                if r:
                    return r
        return None
    taille_trak, = struct.unpack_from(">I", moov, trak_pos)
    return chercher(trak_pos + 8, trak_pos + taille_trak)


def _premier_echantillon(moov: bytes, trak_pos: int, fh) -> bytes:
    stsz = _table(moov, trak_pos, "stsz")
    co = _table(moov, trak_pos, "stco") or _table(moov, trak_pos, "co64")
    if not stsz or not co:
        raise Irreparable("tables stsz/stco absentes")
    pos, _, ent = stsz
    taille, = struct.unpack_from(">I", moov, pos + ent + 4)
    if taille == 0:
        taille, = struct.unpack_from(">I", moov, pos + ent + 12)
    pos, _, ent = co
    if moov[pos + 4:pos + 8] == b"stco":
        offset, = struct.unpack_from(">I", moov, pos + ent + 8)
    else:
        offset, = struct.unpack_from(">Q", moov, pos + ent + 8)
    fh.seek(offset)
    return fh.read(taille)


def _annexe_b(echantillon: bytes) -> bytes:
    """Préfixes de 4 octets → codes de départ, en vérifiant le découpage."""
    sortie, pos, types = bytearray(), 0, set()
    while pos < len(echantillon):
        n = (struct.unpack_from(">I", echantillon, pos)[0]
             if pos + 4 <= len(echantillon) else 0)
        if n == 0 or pos + 4 + n > len(echantillon):
            raise Irreparable("le premier échantillon n'est pas en NAL "
                              "préfixés sur 4 octets")
        nal = echantillon[pos + 4:pos + 4 + n]
        types.add((nal[0] >> 1) & 0x3F)
        sortie += b"\x00\x00\x00\x01" + nal
        pos += 4 + n
    if not {32, 33, 34} <= types:
        raise Irreparable("VPS/SPS/PPS absents du premier échantillon")
    return bytes(sortie)


def _fabriquer_hvcc(annexe_b: bytes, ffmpeg: str) -> bytes:
    """La charge utile de la `hvcC` que ffmpeg écrit pour ce flux."""
    with tempfile.TemporaryDirectory() as tmp:
        brut, mp4 = Path(tmp, "p.hevc"), Path(tmp, "p.mp4")
        brut.write_bytes(annexe_b)
        subprocess.run([ffmpeg, "-v", "error", "-y", "-f", "hevc", "-i",
                        str(brut), "-c", "copy", "-tag:v", "hvc1", str(mp4)],
                       check=True, capture_output=True)
        data = mp4.read_bytes()

    def chercher(debut, fin):
        for pos, taille, typ, entete in _boites(data, debut, fin):
            if typ == "hvcC":
                return data[pos + entete:pos + taille]
            if typ in _ENTETE_ENFANTS:
                r = chercher(pos + entete + _ENTETE_ENFANTS[typ], pos + taille)
                if r is not None:
                    return r
        return None
    racine = {typ: (pos, taille, entete)
              for pos, taille, typ, entete in _boites(data, 0, len(data))}
    if "moov" not in racine:
        raise Irreparable("ffmpeg n'a pas écrit de moov")
    pos, taille, entete = racine["moov"]
    charge = chercher(pos + entete, pos + taille)
    if not charge or len(charge) < 23:
        raise Irreparable("ffmpeg n'a pas pu construire de hvcC")
    if charge[21] & 3 != 3:
        raise Irreparable("hvcC construite avec des préfixes autres que 4 octets")
    return charge


def _recaler_offsets(moov: bytearray, delta: int) -> None:
    """Ajoute `delta` à chaque entrée `stco`/`co64` de toutes les pistes."""
    def parcourir(debut, fin):
        for pos, taille, typ, entete in _boites(moov, debut, fin):
            if typ in ("trak", "mdia", "minf", "stbl"):
                parcourir(pos + entete, pos + taille)
            elif typ in ("stco", "co64"):
                nombre, = struct.unpack_from(">I", moov, pos + entete + 4)
                base = pos + entete + 8
                fmt, larg = (">I", 4) if typ == "stco" else (">Q", 8)
                for i in range(nombre):
                    v = struct.unpack_from(fmt, moov, base + i * larg)[0] + delta
                    if typ == "stco" and v > 0xFFFFFFFF:
                        raise Irreparable("offset au-delà de 4 Go en stco")
                    struct.pack_into(fmt, moov, base + i * larg, v)
    parcourir(0, len(moov))


def reparer(source: Path, sortie: Path, ffmpeg: str, ffprobe: str) -> None:
    taille_fichier = source.stat().st_size
    with open(source, "rb") as fh:
        racine = list(_boites_fichier(fh, taille_fichier))
        moov_b = next((b for b in racine if b[2] == "moov"), None)
        mdat_b = next((b for b in racine if b[2] == "mdat"), None)
        if moov_b is None or mdat_b is None:
            raise Irreparable("moov ou mdat absent")
        if moov_b[3] != 8:
            raise Irreparable("moov sur 64 bits non pris en charge")
        fh.seek(moov_b[0] + 8)
        moov = bytearray(fh.read(moov_b[1] - 8))   # contenu, sans l'en-tête
        trouve = _chemin_hvcc(bytes(moov))
        if not trouve:
            raise Irreparable("aucune hvcC vide : rien à réparer")
        chemin, (h_pos, _h_taille, h_ent) = trouve
        trak_pos = next(p for p, _e, typ in chemin if typ == "trak")
        echantillon = _premier_echantillon(bytes(moov), trak_pos, fh)

    charge = _fabriquer_hvcc(_annexe_b(echantillon), ffmpeg)
    delta = len(charge)

    # Insérer la charge dans la hvcC, grossir la hvcC et chacun de ses parents.
    moov[h_pos + h_ent:h_pos + h_ent] = charge
    for pos, entete, _typ in [*chemin, (h_pos, h_ent, "hvcC")]:
        if entete != 8:
            raise Irreparable("boîte parente sur 64 bits non prise en charge")
        taille, = struct.unpack_from(">I", moov, pos)
        struct.pack_into(">I", moov, pos, taille + delta)
    # Le moov devant le mdat (faststart) : tout le mdat recule de `delta`.
    if moov_b[0] < mdat_b[0]:
        _recaler_offsets(moov, delta)

    tmp = sortie.with_name(sortie.name + ".tmp")
    try:
        with open(source, "rb") as src, open(tmp, "wb") as dst:
            dst.write(src.read(moov_b[0]))
            dst.write(struct.pack(">I4s", moov_b[1] + delta, b"moov"))
            dst.write(moov)
            src.seek(moov_b[0] + moov_b[1])
            shutil.copyfileobj(src, dst, 16 << 20)
        if tmp.stat().st_size != taille_fichier + delta:
            raise Irreparable("copie incomplète")
        controler(tmp, ffprobe, ffmpeg)
        os.replace(tmp, sortie)
    finally:
        tmp.unlink(missing_ok=True)


def controler(chemin: Path, ffprobe: str, ffmpeg: str) -> None:
    """ffprobe ouvre le fichier et y voit du HEVC ; ses 30 premières
    secondes se décodent sans erreur."""
    r = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=codec_name",
                        "-of", "csv=p=0", str(chemin)],
                       capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.startswith("hevc"):
        raise Irreparable(f"contrôle ffprobe : {r.stderr.strip()[:200]}")
    # Les DTS que le remux d'origine a écrits ne sont pas toujours croissants
    # (mesuré : 1312, 1313, 2000, 2001…) ; la réparation n'y touche pas, et
    # les lecteurs les tolèrent. Seules les erreurs du décodeur comptent.
    r = subprocess.run([ffmpeg, "-v", "error", "-t", "30", "-i", str(chemin),
                        "-map", "0:v:0", "-f", "null", "-"],
                       capture_output=True, text=True)
    erreurs = [ligne for ligne in r.stderr.splitlines()
               if "non monotonically increasing dts" not in ligne]
    if r.returncode != 0 or erreurs:
        raise Irreparable(f"contrôle du décodage : {' '.join(erreurs)[:200]}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("chemins", nargs="+", type=Path)
    p.add_argument("--remplacer", action="store_true",
                   help="remplacer l'original une fois la réparation contrôlée")
    args = p.parse_args(argv)
    ffmpeg, ffprobe = _outil("ffmpeg"), _outil("ffprobe")

    fichiers = []
    for c in args.chemins:
        if c.is_dir():
            fichiers += sorted(x for x in c.rglob("*.mp4")
                               if not x.name.endswith(".repare.mp4"))
        else:
            fichiers.append(c)

    echecs = 0
    for fic in fichiers:
        sortie = (fic if args.remplacer
                  else fic.with_name(fic.stem + ".repare.mp4"))
        try:
            reparer(fic, sortie, ffmpeg, ffprobe)
        except Irreparable as e:
            print(f"--  {fic.name} : {e}")
            if "rien à réparer" not in str(e):
                echecs += 1
        except (OSError, subprocess.CalledProcessError) as e:
            print(f"!!  {fic.name} : {e}")
            echecs += 1
        else:
            print(f"OK  {fic.name}" + ("" if args.remplacer
                                       else f" -> {sortie.name}"))
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
