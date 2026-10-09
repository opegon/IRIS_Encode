"""
tests/test_dvd.py — Les titres d'un dossier DVD (IE-121).

Un DVD se présente par les titres de ses IFO, lus sans outil ; ffmpeg ne
sert qu'à les analyser et à les extraire, par l'outil DVD — un BtbN dans
`bin\\dvd\\`, à part du ffmpeg qui encode. Les IFO sont fabriqués ici octet par
octet ; le DVD d'essai (`resources_files/DVD5/DVD/CURE_IN_ORANGE.ISO`) a
servi à valider le lecteur contre ffprobe : un titre, 26 chapitres, 6 573,0 s
lus contre 6 572,5 s.
"""
from __future__ import annotations

import io
import struct
import zipfile
from pathlib import Path

import pytest

from core import dvd, preflight, scanner, updates

S = 2048


# ─── Fabrication d'un DVD ─────────────────────────────────────────────────────

def _bcd(n: int) -> int:
    return (n // 10) << 4 | (n % 10)


def _temps(secondes: int, images: int = 0, cadence25: bool = True) -> bytes:
    h, m, s = secondes // 3600, secondes // 60 % 60, secondes % 60
    return bytes([_bcd(h), _bcd(m), _bcd(s), (0x40 if cadence25 else 0xC0) | _bcd(images)])


def _vmg(titres: list[tuple[int, int, int]]) -> bytes:
    """VIDEO_TS.IFO : titres (vts, rang dans le vts, chapitres)."""
    tete = bytearray(S)
    tete[:12] = b"DVDVIDEO-VMG"
    struct.pack_into(">I", tete, 0xC4, 1)
    srpt = struct.pack(">HHI", len(titres), 0, 8 + 12 * len(titres) - 1)
    for vts, rang, chapitres in titres:
        srpt += struct.pack(">BBHHBBI", 0x3C, 1, chapitres, 0, vts, rang, 0)
    return bytes(tete) + srpt.ljust(S, b"\0")


def _vts(titres: list[list[int]], durees: list[bytes]) -> bytes:
    """VTS_xx_0.IFO : chaque titre (ses PGC par chapitre), chaque PGC (durée)."""
    tete = bytearray(S)
    tete[:12] = b"DVDVIDEO-VTS"
    struct.pack_into(">II", tete, 0xC8, 1, 2)
    corps, offsets = b"", []
    base = 8 + 4 * len(titres)
    for pgcs in titres:
        offsets.append(base + len(corps))
        corps += b"".join(struct.pack(">HH", p, 1) for p in pgcs)
    ptt = struct.pack(">HHI", len(titres), 0, base + len(corps) - 1)
    ptt += b"".join(struct.pack(">I", o) for o in offsets) + corps
    pgci = struct.pack(">HHI", len(durees), 0, 0)
    debut = 8 + 8 * len(durees)
    pgci += b"".join(struct.pack(">II", 0x81000000, debut + 16 * i) for i in range(len(durees)))
    pgci += b"".join(b"\0\0\x01\x01" + d + b"\0" * 8 for d in durees)
    return bytes(tete) + ptt.ljust(S, b"\0") + pgci.ljust(S, b"\0")


def _paquet(brouille: bool = False) -> bytes:
    """Un paquet MPEG-2 de 2 048 octets portant un PES vidéo."""
    pack = b"\x00\x00\x01\xba" + b"\x44\x00\x04\x00\x04\x01\x01\x89\xc3" + b"\xf8"
    pes = b"\x00\x00\x01\xe0\x07\xec" + bytes([0x80 | (0x10 if brouille else 0), 0x80, 5])
    return (pack + pes).ljust(S, b"\xff")


def _dvd(racine: Path, vmg: bytes, vts: dict[int, bytes],
         vobs: dict[int, int] | None = None, brouille: bool = False) -> Path:
    video_ts = racine / "VIDEO_TS"
    video_ts.mkdir(parents=True)
    (video_ts / "VIDEO_TS.IFO").write_bytes(vmg)
    for n, data in vts.items():
        (video_ts / f"VTS_{n:02d}_0.IFO").write_bytes(data)
        (video_ts / f"VTS_{n:02d}_0.VOB").write_bytes(b"menu")
        for k in range(1, (vobs or {}).get(n, 1) + 1):
            (video_ts / f"VTS_{n:02d}_{k}.VOB").write_bytes(_paquet(brouille) * 16)
    return racine


@pytest.fixture
def disque(tmp_path) -> Path:
    """Un film (VTS 1, titre 1, 26 chapitres), son double (titre 3), un bonus
    (VTS 1, titre 2), une bande-annonce courte (VTS 2)."""
    return _dvd(tmp_path / "Film (1999)",
                _vmg([(1, 1, 26), (1, 2, 3), (1, 1, 26), (2, 1, 1)]),
                {1: _vts([[1, 1, 1], [2]], [_temps(6572, 13), _temps(600)]),
                 2: _vts([[1]], [_temps(45)])},
                vobs={1: 3, 2: 1})


# ─── Lecture des IFO ──────────────────────────────────────────────────────────

def test_les_titres_et_leur_durée(disque):
    titres = {t.numero: t for t in dvd.titres(disque)}
    assert sorted(titres) == [1, 2, 4], "le titre 3 rejoue le titre 1"
    assert titres[1].duree == pytest.approx(6572 + 13 / 25)
    assert titres[2].duree == pytest.approx(600)
    assert titres[1].nb_chapitres == 26
    assert [v.name for v in titres[1].clips] == ["VTS_01_1.VOB", "VTS_01_2.VOB",
                                                 "VTS_01_3.VOB"]


def test_la_cadence_ntsc_compte_ses_images(tmp_path):
    racine = _dvd(tmp_path / "D", _vmg([(1, 1, 1)]),
                  {1: _vts([[1]], [_temps(10, 15, cadence25=False)])})
    assert dvd.titres(racine)[0].duree == pytest.approx(10 + 15 * 1001 / 30000)


def test_la_durée_minimale_et_le_principal(disque):
    assert [t.numero for t in dvd.titres(disque, 120)] == [1, 2]
    assert dvd.principal(disque).numero == 1
    titres = {t.numero: t for t in dvd.titres(disque)}
    assert titres[1].nom_sortie == "Film (1999)"
    assert titres[2].nom_sortie == "Film (1999) - TITLE_02"


def test_un_titre_s_identifie_par_un_nom_fictif(disque):
    t = dvd.titre(disque / "VIDEO_TS" / "TITLE_02.dvd")
    assert t.numero == 2 and t.est_dvd and t.a_extraire
    with pytest.raises(ValueError):
        dvd.titre(disque / "VIDEO_TS" / "TITLE_09.dvd")


def test_un_vts_sans_vob_ne_donne_pas_de_titre(tmp_path):
    racine = _dvd(tmp_path / "D", _vmg([(1, 1, 1)]), {1: _vts([[1]], [_temps(600)])})
    (racine / "VIDEO_TS" / "VTS_01_1.VOB").unlink()
    assert dvd.titres(racine) == []


def test_un_ifo_illisible_ne_donne_rien(tmp_path):
    (tmp_path / "VIDEO_TS").mkdir()
    (tmp_path / "VIDEO_TS" / "VIDEO_TS.IFO").write_bytes(b"pas un IFO")
    assert dvd.est_disque(tmp_path)
    assert dvd.titres(tmp_path) == []


def test_à_la_racine_d_un_lecteur_le_nom_par_défaut(monkeypatch):
    from core import bluray
    monkeypatch.setattr(bluray, "_etiquette_volume", lambda r: "")
    assert bluray.nom_disque(Path("E:\\"), defaut="DVD") == "DVD"


# ─── Chiffrement ──────────────────────────────────────────────────────────────

def test_un_vob_clair(tmp_path):
    vob = tmp_path / "a.VOB"
    vob.write_bytes(_paquet() * 32)
    assert not dvd.vob_chiffre(vob)


def test_un_vob_brouillé_par_css(tmp_path):
    vob = tmp_path / "a.VOB"
    vob.write_bytes(_paquet() * 4 + _paquet(brouille=True) * 28)
    assert dvd.vob_chiffre(vob)


def test_un_dvd_chiffré_ne_liste_rien(tmp_path, monkeypatch):
    from tui.widgets.file_tree import FileNavigator
    monkeypatch.setattr(dvd, "_ffprobe", "ffprobe")
    racine = _dvd(tmp_path / "D", _vmg([(1, 1, 1)]),
                  {1: _vts([[1]], [_temps(3600)])}, brouille=True)
    nav = FileNavigator(racine)
    assert nav.list_videos() == [] and nav.disque_chiffre


# ─── L'outil DVD ──────────────────────────────────────────────────────────────

def test_sans_outil_le_dossier_le_dit_et_ne_liste_pas_de_titre(disque, monkeypatch):
    from tui.widgets.file_tree import FileNavigator
    monkeypatch.setattr(dvd, "_ffprobe", None)
    nav = FileNavigator(disque)
    assert nav.list_videos() == [] and nav.dvd_sans_outil
    vobs = FileNavigator(disque / "VIDEO_TS").list_videos()
    assert all(p.suffix == ".VOB" for p in vobs) and vobs, "les VOB restent visibles"


def test_avec_outil_le_dossier_liste_ses_titres(disque, monkeypatch):
    from tui.widgets.file_tree import FileNavigator
    monkeypatch.setattr(dvd, "_ffprobe", "ffprobe")
    nav = FileNavigator(disque)
    assert [p.name for p in nav.list_videos()] == ["TITLE_01.dvd", "TITLE_02.dvd"]


def test_l_outil_de_bin_dvd_passe_avant_le_principal(tmp_path, monkeypatch):
    monkeypatch.setattr(dvd, "lit_les_dvd", lambda f: True)
    assert dvd.chercher_outils(tmp_path, "ff", "fp") == ("ff", "fp")
    (tmp_path / "dvd").mkdir()
    for nom in ("ffmpeg.exe", "ffprobe.exe"):
        (tmp_path / "dvd" / nom).write_bytes(b"")
    ff, fp = dvd.chercher_outils(tmp_path, "ff", "fp")
    assert Path(ff).parent.name == "dvd" and Path(fp).name == "ffprobe.exe"


def test_un_principal_sans_dvdvideo_ne_sert_pas(tmp_path, monkeypatch):
    monkeypatch.setattr(dvd, "lit_les_dvd", lambda f: False)
    assert dvd.chercher_outils(tmp_path, "ff", "fp") == (None, None)


def test_dvdvideo_se_lit_dans_la_liste_des_démultiplexeurs(monkeypatch):
    import subprocess
    sortie = " D   dv              DV (Digital Video)\n D   dvdvideo        DVD-Video\n"
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: type("R", (), {"stdout": sortie})())
    assert dvd.lit_les_dvd("ffmpeg")
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: type("R", (), {"stdout": " D   dv   DV\n"})())
    assert not dvd.lit_les_dvd("ffmpeg")


# ─── Analyse et extraction ────────────────────────────────────────────────────

def test_l_analyse_passe_par_l_outil_dvd(disque, monkeypatch):
    appels = []

    def faux(args, outil=None):
        appels.append((args, outil))
        return {"streams": [{"codec_type": "video", "codec_name": "mpeg2video",
                             "width": 720, "height": 576, "r_frame_rate": "25/1"},
                            {"codec_type": "audio", "codec_name": "ac3", "channels": 6,
                             "tags": {"language": "fre"}}],
                "format": {"duration": "6572.5"}}
    monkeypatch.setattr(scanner, "_ffprobe_json", faux)
    monkeypatch.setattr(scanner, "_detect_dv", lambda p: pytest.fail("pas de DV"))
    monkeypatch.setattr(dvd, "_ffprobe", "ffprobe-dvd")
    info = scanner.scan(disque / "VIDEO_TS" / "TITLE_01.dvd")
    (args, outil), = appels
    assert outil == "ffprobe-dvd"
    assert args[-6:] == ["-f", "dvdvideo", "-title", "1", "-i",
                         str(disque / "VIDEO_TS")]
    assert info.titre.numero == 1 and info.dossier == disque
    assert info.lecture.name == "VTS_01_1.VOB"
    assert info.audio_tracks[0].language == "fre"
    assert info.bitrate > 0 and info.bitrate != 9_999_999, "débit estimé sur les VOB"


def test_sans_outil_l_analyse_échoue(disque, monkeypatch):
    monkeypatch.setattr(dvd, "_ffprobe", None)
    with pytest.raises(RuntimeError):
        scanner.scan(disque / "VIDEO_TS" / "TITLE_01.dvd")


def test_l_extraction_recopie_tout_sans_perte(disque, tmp_path, monkeypatch):
    monkeypatch.setattr(dvd, "_ffmpeg", "ffmpeg-dvd")
    cmd = dvd.build_extraction_command(dvd.principal(disque), tmp_path / "x.mkv")
    assert cmd[0] == "ffmpeg-dvd" and "-stats" in cmd
    assert cmd[-5:] == ["-map", "0", "-c", "copy", str(tmp_path / "x.mkv")]
    assert cmd[cmd.index("-title") + 1] == "1"


def test_le_mode_récursif_retient_le_film_du_dvd(disque, monkeypatch):
    vus = []
    monkeypatch.setattr(scanner, "scan", lambda p: vus.append(p) or None)
    monkeypatch.setattr(dvd, "_ffprobe", "ffprobe")
    scanner.scan_directory_recursive(disque.parent)
    assert [p.name for p in vus] == ["TITLE_01.dvd"]
    vus.clear()
    monkeypatch.setattr(dvd, "_ffprobe", None)
    scanner.scan_directory_recursive(disque.parent)
    assert vus == [], "sans outil, ni titre ni VOB"


# ─── Installation et mise à jour ──────────────────────────────────────────────

def test_l_outil_dvd_se_pose_dans_bin_dvd(tmp_path):
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as zf:
        for nom in ("ffmpeg.exe", "ffprobe.exe", "ffplay.exe"):
            zf.writestr(f"ffmpeg-n9.0-latest-win64-gpl-9.0/bin/{nom}", b"x")
    assert preflight.poser("ffmpeg_dvd", tampon.getvalue(), tmp_path)
    assert sorted(p.name for p in (tmp_path / "dvd").iterdir()) == [
        preflight._exe("ffmpeg"), preflight._exe("ffprobe")]
    assert not (tmp_path / preflight._exe("ffmpeg")).exists(), "le principal intact"
    assert preflight.chemin_local("ffmpeg_dvd", tmp_path) == tmp_path / "dvd" / preflight._exe("ffmpeg")


def test_l_outil_dvd_n_est_pas_cherché_dans_le_path(tmp_path, monkeypatch):
    monkeypatch.setattr(preflight.shutil, "which", lambda n: "C:/ffmpeg.exe")
    assert preflight._localiser("ffmpeg_dvd", tmp_path) is None


def test_pas_d_offre_si_le_principal_lit_les_dvd(monkeypatch):
    statuts = [preflight.ToolStatus("ffmpeg", True, Path("ff")),
               preflight.ToolStatus("ffmpeg_dvd", False)]
    monkeypatch.setattr(dvd, "lit_les_dvd", lambda f: True)
    assert not preflight._dvd_manquant(statuts)
    monkeypatch.setattr(dvd, "lit_les_dvd", lambda f: False)
    assert preflight._dvd_manquant(statuts)


def test_la_dernière_branche_btbn(monkeypatch):
    noms = ["ffmpeg-master-latest-win64-gpl.zip",
            "ffmpeg-n8.1-latest-win64-gpl-8.1.zip",
            "ffmpeg-n9.0-latest-win64-gpl-9.0.zip",
            "ffmpeg-n9.0-latest-win64-gpl-shared-9.0.zip",
            "ffmpeg-n9.0-latest-linux64-gpl-9.0.tar.xz"]
    reponse = type("R", (), {"ok": True, "json": lambda self: {
        "assets": [{"name": n, "browser_download_url": f"u/{n}"} for n in noms]}})()
    monkeypatch.setattr(updates, "_get", lambda url: reponse)
    rel = updates.latest_ffmpeg_dvd()
    assert rel.version == "9.0" and rel.url.endswith("win64-gpl-9.0.zip")
    assert not updates.is_newer("9.0", "9.0.2"), "un correctif de branche ne relance rien"
    assert updates.is_newer("9.0", "8.1.3")


# ─── IE-127 2/3 : cellules, « Lire tout », chapitres, LPCM ───────────────────
# Constats CR-05, CR-06 et CR-07 de `revue_code_2026-10-08.md`, et la question
# « Lire tout » de la même revue, tranchée le 2026-10-09.

def _pgc(secondes: int, cellules: list[tuple[int, int]]) -> bytes:
    """Un PGC avec sa table C_PBKT (en 0xEC) : 24 octets par cellule."""
    tete = bytearray(0xEC)
    tete[2], tete[3] = 1, len(cellules)
    tete[4:8] = _temps(secondes)
    struct.pack_into(">H", tete, 0xE8, 0xEC)
    table = b"".join(struct.pack(">8xI8xI", a, b) for a, b in cellules)
    return bytes(tete) + table


def _vts_cellules(titres: list[list[int]], pgcs: list[bytes]) -> bytes:
    """Comme `_vts`, des PGC complets au lieu de leurs seules durées."""
    tete = bytearray(S)
    tete[:12] = b"DVDVIDEO-VTS"
    struct.pack_into(">II", tete, 0xC8, 1, 2)
    corps, offsets = b"", []
    base = 8 + 4 * len(titres)
    for liste in titres:
        offsets.append(base + len(corps))
        corps += b"".join(struct.pack(">HH", p, 1) for p in liste)
    ptt = struct.pack(">HHI", len(titres), 0, base + len(corps) - 1)
    ptt += b"".join(struct.pack(">I", o) for o in offsets) + corps
    debut, positions = 8 + 8 * len(pgcs), []
    for data in pgcs:
        positions.append(debut)
        debut += len(data)
    pgci = struct.pack(">HHI", len(pgcs), 0, 0)
    pgci += b"".join(struct.pack(">II", 0x81000000, d) for d in positions)
    pgci += b"".join(pgcs)
    return bytes(tete) + ptt.ljust(S, b"\0") + pgci.ljust(4 * S, b"\0")


@pytest.fixture
def serie(tmp_path) -> Path:
    """Deux épisodes d'un même VTS, de 10 et 30 min (1:3 en secteurs), et un
    « Lire tout » de 40 min dont les cellules couvrent les deux. Le contenu
    du VTS tient en deux VOB de 1 500 et 2 500 secteurs."""
    racine = tmp_path / "Série S01D1"
    video_ts = racine / "VIDEO_TS"
    video_ts.mkdir(parents=True)
    (video_ts / "VIDEO_TS.IFO").write_bytes(_vmg([(1, 1, 4), (1, 2, 8), (1, 3, 12)]))
    (video_ts / "VTS_01_0.IFO").write_bytes(_vts_cellules(
        [[1], [2], [3]],
        [_pgc(600, [(0, 999)]), _pgc(1800, [(1000, 2499), (2500, 3999)]),
         _pgc(2400, [(0, 3999)])]))
    (video_ts / "VTS_01_0.VOB").write_bytes(b"menu")
    (video_ts / "VTS_01_1.VOB").write_bytes(b"\0" * 1500 * S)
    (video_ts / "VTS_01_2.VOB").write_bytes(b"\0" * 2500 * S)
    return racine


def test_un_titre_pese_ses_cellules_et_non_tout_son_vts(serie):
    """CR-06 : chaque épisode pesait le disque entier, et son débit estimé
    (taille × 8 / durée) en était faussé d'autant."""
    t = {t.numero: t for t in dvd.titres(serie)}
    assert t[1].taille == 1000 * S and t[2].taille == 3000 * S
    assert t[2].taille / t[1].taille == pytest.approx(3, rel=0.01)
    assert [v.name for v in t[1].clips] == ["VTS_01_1.VOB"]
    assert [v.name for v in t[2].clips] == ["VTS_01_1.VOB", "VTS_01_2.VOB"]


def test_lire_tout_n_est_pas_le_titre_principal(serie):
    """Le plus long, il devenait le principal : le mode récursif sortait le
    disque en un seul fichier. Il reste listé, cochable à la main."""
    assert dvd.principal(serie).numero == 2
    assert 3 in [t.numero for t in dvd.titres(serie)]


def test_lire_tout_par_ses_pgc(tmp_path):
    """L'autre forme : un titre qui enchaîne les PGC des épisodes."""
    racine = _dvd(tmp_path / "Série", _vmg([(1, 1, 1), (1, 2, 1), (1, 3, 2)]),
                  {1: _vts([[1], [2], [1, 2]], [_temps(1500), _temps(1400)])})
    assert dvd.principal(racine).numero == 1


def test_un_film_et_son_bonus_gardent_le_plus_long(disque):
    assert dvd.principal(disque).numero == 1


def test_un_titre_de_dvd_n_a_pas_de_temps_de_chapitre(disque):
    """CR-07 : `chapitres` portait n zéros ; écrits un jour, n chapitres à 0 s."""
    from core.bluray import ffmetadata_chapitres
    t = dvd.principal(disque)
    assert t.chapitres == [] and t.nb_chapitres == 26
    assert ffmetadata_chapitres(t) == ""


def test_la_profondeur_d_un_pcm_est_lue():
    [piste] = scanner._pistes_audio([{"codec_type": "audio", "codec_name": "pcm_dvd",
                                      "bits_per_raw_sample": "24"}])
    assert piste.bits == 24


def _pcm(index, bits):
    return scanner.AudioTrack(index=index, codec="pcm_dvd", channels=2,
                              language="fre", title="", bitrate=0, bits=bits)


def test_le_lpcm_devient_un_pcm_de_meme_profondeur(disque):
    """CR-05 : recopié, le `pcm_dvd` faisait échouer l'extraction du titre."""
    ac3 = scanner.AudioTrack(index=0, codec="ac3", channels=6, language="eng",
                             title="", bitrate=448_000)
    cmd = dvd.build_extraction_command(dvd.principal(disque), disque / "x.mkv",
                                       [ac3, _pcm(1, 16), _pcm(2, 24), _pcm(3, 20)])
    assert cmd[cmd.index("-c") + 1] == "copy"
    assert "-c:a:0" not in cmd
    assert cmd[cmd.index("-c:a:1") + 1] == "pcm_s16le"
    assert cmd[cmd.index("-c:a:2") + 1] == "pcm_s24le"
    assert cmd[cmd.index("-c:a:3") + 1] == "pcm_s24le"


_BIN = Path(__file__).resolve().parent.parent / "bin"


@pytest.mark.skipif(not (_BIN / "ffmpeg.exe").exists(), reason="ffmpeg du projet absent")
@pytest.mark.parametrize("fmt,bits,attendu", [("s16", 16, "pcm_s16le"),
                                              ("s32", 24, "pcm_s24le")])
def test_l_extraction_d_un_lpcm_reussit(tmp_path, disque, monkeypatch, fmt, bits, attendu):
    """Avec le ffmpeg du projet, sur un MPEG-PS synthétique à `pcm_dvd` lu par
    `-f mpeg` au lieu de `dvdvideo` (absent de ce build). `+genpts` : la vidéo
    du VOB fabriqué par ffmpeg n'a pas tous ses horodatages (mesuré), ce que
    le démultiplexeur `dvdvideo` donne, lui."""
    import json
    import subprocess
    ffmpeg = str(_BIN / "ffmpeg.exe")
    vob = tmp_path / "t.vob"
    subprocess.run([ffmpeg, "-y", "-loglevel", "error",
                    "-f", "lavfi", "-i", "testsrc=size=720x576:rate=25:duration=2",
                    "-f", "lavfi", "-i", "sine=duration=2:sample_rate=48000",
                    "-c:v", "mpeg2video", "-c:a", "pcm_dvd", "-sample_fmt", fmt,
                    "-f", "vob", str(vob)], check=True, capture_output=True)
    monkeypatch.setattr(dvd, "_ffmpeg", ffmpeg)
    monkeypatch.setattr(dvd, "entree",
                        lambda t: ["-fflags", "+genpts", "-f", "mpeg", "-i", str(vob)])
    sortie = tmp_path / "x.mkv"
    cmd = dvd.build_extraction_command(dvd.principal(disque), sortie, [_pcm(0, bits)])
    r = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr[-500:]
    flux = json.loads(subprocess.run(
        [str(_BIN / "ffprobe.exe"), "-v", "error", "-print_format", "json",
         "-show_streams", "-select_streams", "a", str(sortie)],
        capture_output=True, encoding="utf-8", check=True).stdout)["streams"]
    assert [f["codec_name"] for f in flux] == [attendu]


def test_un_film_a_acces_aux_scenes_reste_le_principal(tmp_path):
    """Chaque scène publiée en titre est couverte par le film : il ne devient
    pas un « Lire tout » pour autant — elles font moins d'un dixième de lui."""
    scenes = [_pgc(300, [(k * 100, k * 100 + 99)]) for k in range(20)]
    film = _pgc(6000, [(0, 1999)])
    racine = tmp_path / "Film"
    video_ts = racine / "VIDEO_TS"
    video_ts.mkdir(parents=True)
    (video_ts / "VIDEO_TS.IFO").write_bytes(
        _vmg([(1, 1, 20)] + [(1, k + 2, 1) for k in range(20)]))
    (video_ts / "VTS_01_0.IFO").write_bytes(
        _vts_cellules([[1]] + [[k + 2] for k in range(20)], [film] + scenes))
    (video_ts / "VTS_01_1.VOB").write_bytes(b"\0" * 2000 * S)
    assert dvd.principal(racine).numero == 1
