"""
tests/test_hvcc_sans_parametres.py — Un HEVC dont l'en-tête ne porte aucun
VPS/SPS/PPS, recopié en MP4 (IE-205).

Signalement du 2026-11-24 : un répertoire de WEB-DL passé en v0.9.3.12, tous
les fichiers illisibles, sources supprimées (profil `delete_source`). La piste
AAC de secours les avait fait passer de SKIP à REMUX ; la vidéo recopiée en MP4
sous `-tag:v hvc1` sortait avec une `hvcC` de 8 octets — ni paramètres, ni
taille des préfixes de NAL. ffmpeg rendait 0, le contrôle de sortie prenait le
refus de ffprobe pour une durée illisible.

Reproduit ici : la source est un HEVC `hev1` dont la `hvcC` ne garde que son
en-tête fixe (23 octets, `numOfArrays` = 0), les paramètres restant dans le
flux (`repeat-headers`) — en MP4 et en Matroska, même effet.
"""
from __future__ import annotations

import struct
import subprocess
import sys
from pathlib import Path

import pytest

from core import encoder, scanner
from core.decision import VideoAction, decide
from core.encoder import build_command
from core.platform import GPU, OS, PlatformProfile
from core.profiles import Profile

from tests.outils_reels import RACINE, outil  # noqa: E402

sys.path.insert(0, str(RACINE / "outils"))
import reparer_hvcc  # noqa: E402  outils/reparer_hvcc.py

_FFMPEG, _FFPROBE = outil("ffmpeg"), outil("ffprobe")
outils = pytest.mark.skipif(not (_FFMPEG.exists() and _FFPROBE.exists()),
                            reason="outils du projet absents")


def _plat() -> PlatformProfile:
    return PlatformProfile(os=OS.WINDOWS, gpu=GPU.NONE, hwaccel=None,
                           encoder_hevc="libx265", encoder_h264="libx264",
                           encoder_av1="libaom-av1")


def _profil() -> Profile:
    return Profile(id="test", data={
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps": 8000, "audio_languages": ["fre"],
        "audio_copy_compatible": True, "preserve_hd_audio": False,
        "audio_stereo_kbps": 128, "audio_aac_fallback": True,
        "container": "mp4"})


def _run(cmd: list) -> subprocess.CompletedProcess:
    return subprocess.run([str(x) for x in cmd], stdin=subprocess.DEVNULL,
                          capture_output=True, encoding="utf-8", errors="replace")


def _hvcc(chemin: Path) -> bytes:
    """La charge utile de la `hvcC` d'un petit MP4."""
    data = chemin.read_bytes()

    def chercher(debut, fin):
        for pos, taille, typ, entete in reparer_hvcc._boites(data, debut, fin):
            if typ == "hvcC":
                return data[pos + entete:pos + taille]
            if typ in reparer_hvcc._ENTETE_ENFANTS:
                r = chercher(pos + entete + reparer_hvcc._ENTETE_ENFANTS[typ],
                             pos + taille)
                if r is not None:
                    return r
        return None
    return chercher(0, len(data))


def _vider_hvcc(source: Path, sortie: Path) -> None:
    """Réduit la `hvcC` de `source` à son en-tête fixe, sans tableau."""
    d = bytearray(source.read_bytes())

    def chercher(debut, fin, chemin):
        for pos, taille, typ, entete in reparer_hvcc._boites(bytes(d), debut, fin):
            if typ == "hvcC":
                return chemin + [pos], pos, taille, entete
            if typ in reparer_hvcc._ENTETE_ENFANTS:
                r = chercher(pos + entete + reparer_hvcc._ENTETE_ENFANTS[typ],
                             pos + taille, chemin + [pos])
                if r:
                    return r
        return None
    chemin, pos, taille, entete = chercher(0, len(d), [])
    charge = d[pos + entete:pos + entete + 22] + b"\x00"   # numOfArrays = 0
    delta = len(charge) - (taille - entete)
    d[pos + entete:pos + taille] = charge
    for p in chemin:
        struct.pack_into(">I", d, p, struct.unpack_from(">I", d, p)[0] + delta)
    moov = chemin[0]
    mdat = next(p for p, _t, typ, _e in reparer_hvcc._boites(bytes(d), 0, len(d))
                if typ == "mdat")
    if moov < mdat:
        fin = moov + struct.unpack_from(">I", d, moov)[0]
        contenu = bytearray(d[moov + 8:fin])
        reparer_hvcc._recaler_offsets(contenu, delta)
        d[moov + 8:fin] = contenu
    sortie.write_bytes(d)


@pytest.fixture
def source(tmp_path) -> Path:
    """Matroska HEVC 10 bits + E-AC3 fre, paramètres dans le flux seulement."""
    encoder.set_ffmpeg_path(str(_FFMPEG))
    scanner.set_ffprobe_path(str(_FFPROBE))
    complet, vide = tmp_path / "complet.mp4", tmp_path / "vide.mp4"
    r = _run([_FFMPEG, "-y", "-v", "error",
              "-f", "lavfi", "-i", "testsrc2=s=320x240:r=24:d=3",
              "-f", "lavfi", "-i", "sine=d=3",
              "-c:v", "libx265", "-pix_fmt", "yuv420p10le", "-b:v", "300k",
              "-x265-params", "repeat-headers=1:log-level=error", "-tag:v", "hev1",
              "-c:a", "eac3", "-metadata:s:a:0", "language=fre", "-shortest",
              complet])
    assert r.returncode == 0, r.stderr
    _vider_hvcc(complet, vide)
    mkv = tmp_path / "Serie.S01E01.1080p.NF.WEB.DDP.H265.mkv"
    assert _run([_FFMPEG, "-y", "-v", "error", "-i", vide, "-c", "copy",
                 mkv]).returncode == 0
    return mkv


def _lisible(chemin: Path) -> bool:
    r = _run([_FFMPEG, "-v", "error", "-i", chemin, "-map", "0:v:0",
              "-f", "null", "-"])
    return r.returncode == 0 and not r.stderr.strip()


@outils
def test_le_scanner_voit_les_parametres_hors_entete(source, tmp_path):
    assert scanner.scan(source).parametres_hors_entete
    sain = tmp_path / "sain.mp4"                # hvcC reconstruite, complète
    assert _run([_FFMPEG, "-y", "-v", "error", "-i", source, "-c", "copy",
                 "-bsf:v", "hevc_mp4toannexb", "-tag:v", "hvc1",
                 sain]).returncode == 0
    assert not scanner.scan(sain).parametres_hors_entete


@outils
def test_le_remux_en_mp4_reste_lisible(source):
    dec = decide(scanner.scan(source), _profil())
    assert dec.video.action == VideoAction.REMUX, "prémisse : remux « AAC »"
    assert dec.output_container == ".mp4"
    r = _run(build_command(dec, _plat()))
    assert r.returncode == 0, r.stderr
    assert len(_hvcc(dec.output_path)) > 23, "hvcC sans paramètres"
    assert encoder.defaut_sortie(dec.output_path, 3.0) == ""
    assert _lisible(dec.output_path)


@outils
def test_le_controle_refuse_une_hvcc_vide_et_l_outil_la_repare(source, tmp_path):
    """La sortie qu'écrivait la v0.9.3.12, puis sa réparation."""
    casse = tmp_path / "casse.mp4"
    r = _run([_FFMPEG, "-y", "-v", "error", "-i", source, "-map", "0",
              "-c", "copy", "-tag:v", "hvc1", "-movflags", "+faststart", casse])
    assert r.returncode == 0, "ffmpeg rend 0 sur ce fichier"
    assert _hvcc(casse) == b"", "prémisse : la hvcC est vide"
    assert encoder.defaut_sortie(casse, 3.0)

    repare = tmp_path / "repare.mp4"
    reparer_hvcc.reparer(casse, repare, str(_FFMPEG), str(_FFPROBE))
    assert len(_hvcc(repare)) > 23
    assert encoder.defaut_sortie(repare, 3.0) == ""
    assert _lisible(repare)


@outils
def test_le_retrait_dv_vers_mp4_reste_lisible(source, tmp_path):
    """`build_strip_mp4` impose aussi `hvc1` à une copie, mais n'a pas le
    défaut : le filtre `dovi_rpu` réécrit l'en-tête depuis les paramètres du
    flux (mesuré, ffmpeg 8.1.2). Sans lui, la même copie sort illisible —
    ce test garde la propriété si le filtre change."""
    from core import dovi
    if not dovi.strip_bsf_disponible(str(_FFMPEG)):
        pytest.skip("ffmpeg sans le filtre dovi_rpu")
    sortie = tmp_path / "retrait.mp4"
    r = _run(dovi.build_strip_mp4(source, sortie, sous_titres=[],
                                  ffmpeg_path=str(_FFMPEG)))
    assert r.returncode == 0, r.stderr
    assert len(_hvcc(sortie)) > 23, "hvcC sans paramètres"
    assert encoder.defaut_sortie(sortie, 3.0) == ""
    assert _lisible(sortie)
