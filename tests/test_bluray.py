"""
tests/test_bluray.py — Les titres d'un dossier Blu-ray (IE-120).

Un disque se présente par ses playlists `.mpls` : au-dessus d'une durée
minimale, sans doublon, le plus long marqué principal. Les playlists sont
fabriquées ici, octet par octet, au format que `core/bluray.py` lit ; le
disque d'essai (`resources_files/bluray.iso`) a servi à valider le lecteur
contre mkvmerge (durées et nombres de chapitres identiques).
"""
from __future__ import annotations

import struct
import subprocess
from pathlib import Path

import pytest

from core import bluray
from core.decision import decide, sorties_bloquees
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo

TICS = 45_000
RACINE_DEPOT = Path(__file__).resolve().parent.parent


# ─── Fabrication d'un disque ──────────────────────────────────────────────────

def _mpls(elements: list[tuple[str, float, float]],
          chapitres: list[tuple[int, float]] = ()) -> bytes:
    """Une playlist : éléments (clip, entrée s, sortie s), marques (élément,
    temps s dans le clip)."""
    items = b""
    for clip, entree, sortie in elements:
        corps = (clip.encode() + b"M2TS" + b"\x00\x01" + b"\x00"
                 + struct.pack(">II", round(entree * TICS), round(sortie * TICS))
                 + b"\x00" * 12)
        items += struct.pack(">H", len(corps)) + corps
    liste = struct.pack(">HHH", 0, len(elements), 0) + items
    liste = struct.pack(">I", len(liste)) + liste
    marques = b"".join(
        struct.pack(">BBHIHI", 0, 1, el, round(t * TICS), 0xFFFF, 0)
        for el, t in chapitres)
    marques = struct.pack(">IH", 2 + len(marques), len(chapitres)) + marques
    debut_liste = 40
    entete = b"MPLS0200" + struct.pack(">III", debut_liste,
                                       debut_liste + len(liste), 0)
    entete += b"\x00" * (debut_liste - len(entete))
    return entete + liste + marques


def _disque(racine: Path, playlists: dict[str, bytes],
            clips: dict[str, bytes] | None = None) -> Path:
    bdmv = racine / "BDMV"
    for d in ("PLAYLIST", "STREAM", "CLIPINF"):
        (bdmv / d).mkdir(parents=True, exist_ok=True)
    (bdmv / "index.bdmv").write_bytes(b"INDX0200")
    for nom, data in playlists.items():
        (bdmv / "PLAYLIST" / f"{nom}.mpls").write_bytes(data)
    for nom, data in (clips or {}).items():
        (bdmv / "STREAM" / f"{nom}.m2ts").write_bytes(data)
    return racine


def _clip_clair(unites: int = 8) -> bytes:
    paquet = b"\x00\x00\x00\x00\x47" + b"\x00" * 187
    return paquet * 32 * unites


def _clip_chiffre(unites: int = 8) -> bytes:
    # Les 16 premiers octets de chaque unité restent clairs, le reste non.
    unite = _clip_clair(1)[:16] + bytes((i * 37 + 11) % 256 for i in range(6144 - 16))
    return unite * unites


@pytest.fixture
def disque(tmp_path) -> Path:
    """Le disque d'essai en réduit : un film en double (avec et sans
    chapitres), un bonus, un menu court."""
    film = [("00001", 10.0, 4434.0)]
    return _disque(tmp_path / "Film (2020)", {
        "00000": _mpls([("00000", 0, 15)]),
        "00001": _mpls(film, [(0, 10.0)]),
        "00002": _mpls([("00002", 0, 1185)], [(0, 0)]),
        "01001": _mpls(film, [(0, 10.0), (0, 340.0), (0, 614.0)]),
    }, {n: _clip_clair() for n in ("00000", "00001", "00002")})


# ─── Lecture d'une playlist ───────────────────────────────────────────────────

def test_durée_et_chapitres_relatifs_au_point_d_entrée(disque):
    t = bluray.titre(disque / "BDMV" / "PLAYLIST" / "01001.mpls")
    assert t.duree == pytest.approx(4424.0)
    assert t.chapitres == pytest.approx([0.0, 330.0, 604.0])
    assert [c.name for c in t.clips] == ["00001.m2ts"]


def test_un_titre_de_plusieurs_clips_cumule_ses_éléments(tmp_path):
    racine = _disque(tmp_path / "D", {
        "00800": _mpls([("00010", 0, 600), ("00011", 5, 305)], [(0, 0), (1, 5), (1, 105)]),
    }, {"00010": b"", "00011": b""})
    t = bluray.titres(racine)[0]
    assert t.duree == pytest.approx(900)
    assert t.chapitres == pytest.approx([0, 600, 700])
    assert [c.stem for c in t.clips] == ["00010", "00011"]


def test_une_playlist_qui_cite_un_clip_absent_est_ignorée(tmp_path):
    racine = _disque(tmp_path / "D", {"00001": _mpls([("00009", 0, 600)])})
    assert bluray.titres(racine) == []


def test_un_fichier_qui_n_est_pas_une_playlist_est_ignoré(tmp_path):
    racine = _disque(tmp_path / "D", {"00001": b"pas une playlist"})
    assert bluray.titres(racine) == []


# ─── Le disque ────────────────────────────────────────────────────────────────

def test_les_doublons_gardent_celui_qui_a_le_plus_de_chapitres(disque):
    noms = [t.mpls.stem for t in bluray.titres(disque)]
    assert "01001" in noms and "00001" not in noms


def test_la_durée_minimale_écarte_menus_et_boucles(disque):
    assert [t.mpls.stem for t in bluray.titres(disque, 120)] == ["00002", "01001"]
    assert len(bluray.titres(disque, 0)) == 3


def test_le_plus_long_est_le_principal(disque):
    principal = bluray.principal(disque)
    assert principal.mpls.stem == "01001"
    assert [t.principal for t in bluray.titres(disque)].count(True) == 1


def test_un_doublon_écarté_reste_un_titre_à_part_entière(disque):
    t = bluray.titre(disque / "BDMV" / "PLAYLIST" / "00001.mpls")
    assert t.nom == "Film (2020)" and not t.principal


def test_le_nom_vient_du_dossier_du_disque(disque):
    titres = {t.mpls.stem: t for t in bluray.titres(disque)}
    assert titres["01001"].nom_sortie == "Film (2020)"
    assert titres["00002"].nom_sortie == "Film (2020) - 00002"


def test_à_la_racine_d_un_lecteur_l_étiquette_du_volume(monkeypatch):
    monkeypatch.setattr(bluray, "_etiquette_volume", lambda r: "WITHIN_TEMPTATION_")
    assert bluray.nom_disque(Path("E:\\")) == "WITHIN TEMPTATION"
    monkeypatch.setattr(bluray, "_etiquette_volume", lambda r: "")
    assert bluray.nom_disque(Path("E:\\")) == "BLURAY"


def test_la_taille_d_un_titre_est_celle_de_ses_clips(disque):
    t = bluray.principal(disque)
    assert t.taille == len(_clip_clair())


# ─── Chiffrement ──────────────────────────────────────────────────────────────

def test_un_clip_clair_n_est_pas_chiffré(tmp_path):
    clip = tmp_path / "a.m2ts"
    clip.write_bytes(_clip_clair())
    assert not bluray.clip_chiffre(clip)


def test_un_clip_aacs_est_reconnu(tmp_path):
    clip = tmp_path / "a.m2ts"
    clip.write_bytes(_clip_chiffre())
    assert bluray.clip_chiffre(clip)


def test_un_disque_chiffré_ne_donne_aucun_titre(tmp_path):
    from core.scanner import sources_du_dossier
    from tui.widgets.file_tree import FileNavigator
    racine = _disque(tmp_path / "D", {"00001": _mpls([("00001", 0, 4000)])},
                     {"00001": _clip_chiffre()})
    assert bluray.disque_chiffre(racine)
    assert sources_du_dossier(racine, 0) == []
    nav = FileNavigator(racine)
    assert nav.list_videos() == []
    assert nav.disque_chiffre


# ─── Navigateur ───────────────────────────────────────────────────────────────

def test_le_dossier_du_disque_liste_ses_titres(disque):
    from tui.widgets.file_tree import FileNavigator
    nav = FileNavigator(disque)
    assert [p.name for p in nav.list_videos()] == ["00002.mpls", "01001.mpls"]
    assert not nav.disque_chiffre
    nav.duree_min_titre = 0
    assert len(nav.list_videos()) == 3


def test_les_clips_restent_visibles_dans_stream(disque):
    from tui.widgets.file_tree import FileNavigator
    nav = FileNavigator(disque / "BDMV" / "STREAM")
    assert [p.suffix for p in nav.list_videos()] == [".m2ts"] * 3


def test_le_mode_récursif_retient_le_titre_principal(disque, monkeypatch):
    from core import scanner
    vus = []
    monkeypatch.setattr(scanner, "scan", lambda p: vus.append(p) or None)
    (disque.parent / "autre.mkv").write_bytes(b"")
    scanner.scan_directory_recursive(disque.parent)
    assert sorted(p.name for p in vus) == ["01001.mpls", "autre.mkv"]


def test_le_réglage_de_durée_minimale():
    from core import config as cfg_mod
    assert cfg_mod.get_min_title_minutes({}) == bluray.DUREE_MIN_DEFAUT_MIN
    assert cfg_mod.get_min_title_minutes({"app": {"min_title_minutes": 0}}) == 0
    assert cfg_mod.get_min_title_minutes({"app": {"min_title_minutes": "x"}}) == 2


# ─── Analyse et décision ──────────────────────────────────────────────────────

def _info_titre(disque: Path) -> VideoInfo:
    t = bluray.principal(disque)
    return VideoInfo(
        path=t.mpls, width=1920, height=1080, bitrate=30_000_000, codec="h264",
        duration=t.duree, frame_count=0, dv_profile=None,
        audio_tracks=[AudioTrack(index=0, codec="ac3", channels=6,
                                 language="eng", title="", bitrate=640_000)],
        titre=t,
    )


def _profile() -> Profile:
    return Profile(id="test", data={
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps": 12000, "keep_4k": True,
        "audio_languages": ["eng"], "audio_copy_compatible": True,
    })


def test_scan_d_une_playlist_lit_son_clip(disque, monkeypatch):
    from core import scanner
    clip_info = _info_titre(disque)
    clip_info.titre, clip_info.duration, clip_info.frame_count = None, 2212.0, 53_000
    lus = []

    def faux_scan(p):
        lus.append(p)
        clip_info.path = p
        return clip_info
    monkeypatch.setattr(scanner, "_ffprobe_json", None)
    reel = scanner.scan
    monkeypatch.setattr(scanner, "scan",
                        lambda p: reel(p) if p.suffix == ".mpls" else faux_scan(p))
    info = scanner.scan(disque / "BDMV" / "PLAYLIST" / "01001.mpls")
    assert lus == [disque / "BDMV" / "STREAM" / "00001.m2ts"]
    assert info.path.name == "01001.mpls" and info.lecture == lus[0]
    assert info.duration == pytest.approx(4424.0)
    assert info.frame_count == 106_000


def test_la_sortie_s_écrit_à_côté_du_disque_sous_son_nom(disque):
    dec = decide(_info_titre(disque), _profile())
    assert dec.output_path.parent == disque
    assert dec.output_path.name.startswith("Film (2020).")


def test_un_disque_en_lecture_seule_fait_choisir_le_dossier(disque, monkeypatch):
    import core.decision as decision_mod
    essais = []
    monkeypatch.setattr(decision_mod, "dossier_inscriptible",
                        lambda d: essais.append(d) or False)
    dec = decide(_info_titre(disque), _profile())
    assert sorties_bloquees([dec]) == [dec]
    assert essais == [disque]


def test_chapitres_au_format_ffmetadata(disque):
    texte = bluray.ffmetadata_chapitres(bluray.principal(disque))
    assert texte.startswith(";FFMETADATA1\n")
    assert texte.count("[CHAPTER]") == 3
    assert "START=330000\nEND=604000\ntitle=Chapter 02" in texte
    assert texte.rstrip().endswith("END=4424000\ntitle=Chapter 03")


def test_un_seul_chapitre_n_en_fait_pas(tmp_path):
    racine = _disque(tmp_path / "D", {"00001": _mpls([("00001", 0, 600)], [(0, 0)])},
                     {"00001": b""})
    assert bluray.ffmetadata_chapitres(bluray.principal(racine)) == ""


def test_la_commande_lit_le_clip_et_pose_les_chapitres(disque, tmp_path):
    from core.encoder import build_command
    from core.platform import PlatformProfile, OS, GPU
    dec = decide(_info_titre(disque), _profile())
    chap = tmp_path / "c.txt"
    plat = PlatformProfile(os=OS.WINDOWS, gpu=GPU.NONE, encoder_hevc="libx265",
                           encoder_h264="libx264", encoder_av1="libsvtav1", hwaccel=None)
    cmd = build_command(dec, plat, chapitres=chap)
    entrees = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-i"]
    assert entrees[0].endswith("00001.m2ts")
    assert entrees[-1] == str(chap)
    assert cmd[cmd.index("-map_chapters") + 1] == str(len(entrees) - 1)
    assert cmd[cmd.index(str(chap)) - 2:cmd.index(str(chap))] == ["ffmetadata", "-i"]


def test_l_assemblage_remplace_le_clip(disque, tmp_path):
    from core.encoder import build_command
    from core.platform import PlatformProfile, OS, GPU
    dec = decide(_info_titre(disque), _profile())
    dec.encode_source = tmp_path / "01001.iris_titre.mkv"
    plat = PlatformProfile(os=OS.WINDOWS, gpu=GPU.NONE, encoder_hevc="libx265",
                           encoder_h264="libx264", encoder_av1="libsvtav1", hwaccel=None)
    cmd = build_command(dec, plat)
    assert cmd[cmd.index("-i") + 1] == str(dec.encode_source)
    assert "-map_chapters" not in cmd


def test_l_assemblage_est_confié_à_mkvmerge_sur_la_playlist(disque, tmp_path):
    t = bluray.principal(disque)
    cmd = bluray.build_remux_command(t, tmp_path / "x.mkv")
    assert cmd[1:4] == ["--gui-mode", "-o", str(tmp_path / "x.mkv")]
    assert cmd[-1] == str(t.mpls)


# ─── Garde-fous ───────────────────────────────────────────────────────────────

def test_un_titre_n_est_jamais_supprimé_après_encodage():
    """`delete_source` viserait la playlist, et ses clips sont ceux du disque."""
    texte = (RACINE_DEPOT / "tui" / "screens" / "run.py").read_text(encoding="utf-8")
    assert "should_delete and dec.info.titre is None" in texte


def test_les_outils_lisent_le_clip_pas_la_playlist():
    """Tout ce qui ouvre la source passe par `lecture`, jamais par `path`."""
    texte = (RACINE_DEPOT / "tui" / "screens" / "run.py").read_text(encoding="utf-8")
    assert "source = dec.info.path" not in texte
    assert "or dec.info.path" not in texte


# ─── Dans l'application ───────────────────────────────────────────────────────

async def _parcours_disque(racine: Path) -> dict:
    import asyncio
    from tui.app import IrisEncodeApp
    from tui.screens.browser import BrowserScreen

    releve: dict = {}
    app = IrisEncodeApp(start_path=racine)
    async with app.run_test(size=(180, 40)) as pilot:
        await pilot.pause(0.5)
        app.push_screen(BrowserScreen(racine, start_virtual=False))
        await pilot.pause(3.0)
        ecran = app.screen
        releve["coches"] = sorted(p.name for p in ecran._selected)
        releve["tailles"] = {p.name: t for p, t in ecran._tailles.items()}
        ecran._selected.clear()
        ecran._refresh_view()
        await pilot.pause(3.0)
        releve["apres_rescan"] = sorted(p.name for p in ecran._selected)
    return releve


def test_le_titre_principal_est_coché_une_fois_par_visite(tmp_path):
    """Coché à l'entrée du disque ; décoché, un rescan ne le recoche pas."""
    import asyncio
    from core import config as cfg_mod
    from core.preflight import get_tool_path
    ffmpeg = get_tool_path("ffmpeg", cfg_mod.get_bin_dir(cfg_mod.load()))
    if not ffmpeg:
        pytest.skip("ffmpeg absent")
    racine = _disque(tmp_path / "Film (2020)", {
        "00001": _mpls([("00001", 0, 4000)], [(0, 0), (0, 600)]),
        "00002": _mpls([("00002", 0, 900)]),
    })
    for n in ("00001", "00002"):
        subprocess.run(
            [str(ffmpeg), "-y", "-loglevel", "error",
             "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
             "-c:v", "libx264", "-f", "mpegts", "-mpegts_m2ts_mode", "1",
             str(racine / "BDMV" / "STREAM" / f"{n}.m2ts")],
            check=True, capture_output=True)
    releve = asyncio.run(_parcours_disque(racine))
    assert releve["coches"] == ["00001.mpls"]
    taille = (racine / "BDMV" / "STREAM" / "00001.m2ts").stat().st_size
    assert releve["tailles"]["00001.mpls"] == taille
    assert releve["apres_rescan"] == []
