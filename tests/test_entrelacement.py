"""
tests/test_entrelacement.py — Télécinéma inverse et entrelacement mesuré (IE-174).

Arbitrages de l'utilisateur (2026-11-08) : l'image est sondée pour toute
source SD à 25 ou 29,97 i/s, quels que soient ses marqueurs ; un télécinéma
garde la cadence de la source, sauf un 3:2 régulier, ramené à 23,976.

Mesuré le 2026-11-08 : The Kid (AVI, `field_order=unknown`) — 99 % d'images
en peigne, 5 % après appariement, 20 à 22,5 images uniques par seconde ;
Cure in Orange (ISO, se dit progressif) — 100 % en peigne, 51 % après
appariement : une vraie vidéo entrelacée.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from core import encoder, entrelacement as ent, scanner
from core.decision import VideoAction, decide
from core.encoder import build_command
from core.entrelacement import (FILTRE_BWDIF, Analyse, Apparie, Brut, Nature,
                                classer, filtre, lire_apparie, lire_brut)
from core.platform import GPU, OS, PlatformProfile
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo

APP    = Path(__file__).resolve().parent.parent
LE_KID = APP / "resources_files" / "The Kid (and A Dog's Life) - 1921.avi"
CURE   = APP / "resources_files" / "DVD5" / "DVD" / "CURE_IN_ORANGE.ISO"
FFMPEG = APP / "bin" / "ffmpeg.exe"
NTSC   = 30000 / 1001

PLAT = PlatformProfile(os=OS.WINDOWS, gpu=GPU.NONE, hwaccel=None, encoder_hevc="libx265",
                       encoder_h264="libx264", encoder_av1="libsvtav1")


def _info(field_order: str = "", h: int = 480, frame_rate: str = "2997/100",
          analyse: Analyse | None = None, **over) -> VideoInfo:
    champs = dict(
        path=Path("/films/kid.avi"), width=720, height=h, bitrate=1_500_000,
        codec="msmpeg4v3", duration=6000.0, frame_count=0, dv_profile=None,
        audio_tracks=[AudioTrack(index=0, codec="mp3", channels=2, language="eng",
                                 title="", bitrate=128_000)],
        field_order=field_order, frame_rate=frame_rate)
    info = VideoInfo(**{**champs, **over})
    info.entrelacement = analyse
    return info


def _profil() -> Profile:
    return Profile(id="test", data={
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps": 12000, "keep_4k": False,
        "audio_languages": ["eng"], "audio_copy_compatible": True})


def _vf(cmd: list[str]) -> str:
    return cmd[cmd.index("-vf") + 1] if "-vf" in cmd else ""


TELECINE = Analyse(Nature.TELECINE, "tff", False, 0.99, 0.05)
VIDEO    = Analyse(Nature.ENTRELACE, "tff", False, 1.0, 0.5)
PROGRESS = Analyse(Nature.PROGRESSIF, "tff", False, 0.0, 0.0)


# ─── Quelles sources ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("h, cadence", [(480, "2997/100"), (480, "30000/1001"),
                                        (576, "25/1"), (400, "25/1")])
def test_une_source_sd_est_sondée(h, cadence):
    assert ent.a_analyser(_info(h=h, frame_rate=cadence, field_order="progressive"))


@pytest.mark.parametrize("h, cadence", [(720, "25/1"), (1080, "30000/1001"),
                                        (480, "24000/1001"), (578, "25/1")])
def test_hd_ou_film_progressif_ne_l_est_pas(h, cadence):
    assert not ent.a_analyser(_info(h=h, frame_rate=cadence))


def test_une_hd_qui_se_dit_entrelacée_l_est():
    assert ent.a_analyser(_info(h=1080, frame_rate="25/1", field_order="tt"))


# ─── Lecture des journaux d'idet ──────────────────────────────────────────────

def _ligne(nom: str, type_: str, tff: int, bff: int, prog: int, und: int = 0) -> str:
    return (f"[idet@{nom} @ 000001f4ee5403c0] {type_} frame detection: "
            f"TFF: {tff:5} BFF: {bff:5} Progressive: {prog:5} Undetermined: {und:5}\n")


def test_lire_brut_garde_le_bilan_fourni():
    """ffmpeg écrit un premier bilan à zéro, d'un graphe jeté."""
    sortie = (_ligne("brut", "Multi", 600, 0, 0) + _ligne("brut", "Multi", 0, 0, 0)
              + _ligne("brut", "Single", 1, 1, 1))
    assert lire_brut(sortie) == Brut(600, 0, 600)


def test_lire_brut_sans_compte():
    assert lire_brut(_ligne("brut", "Multi", 0, 0, 0)) is None
    assert lire_brut("") is None


def test_lire_apparie():
    sortie = (_ligne("apparie", "Single", 43, 0, 531, 26)
              + _ligne("apparie", "Multi", 0, 0, 600)
              + _ligne("uniques", "Multi", 0, 0, 400))
    assert lire_apparie(sortie) == Apparie(43, 600, 400)


def test_lire_apparie_incomplet():
    assert lire_apparie(_ligne("apparie", "Single", 43, 0, 531)) is None


def test_commandes():
    info = _info()
    brut = ent.build_brut(info, 600.0, "ff")
    assert brut[brut.index("-filter_complex") + 1] == "[0:v:0]idet@brut[sortie]"
    graphe = ent.build_apparie(info, 600.0, "bff", "ff")
    graphe = graphe[graphe.index("-filter_complex") + 1]
    assert graphe.startswith("[0:v:0]fieldmatch=order=bff:combmatch=full,")
    assert "idet@apparie" in graphe and "mpdecimate,idet@uniques" in graphe


# ─── Classement ───────────────────────────────────────────────────────────────

def test_sans_peignes_progressif():
    a = classer([Brut(10, 0, 600), Brut(0, 5, 600)], [], 25.0)
    assert a.nature == Nature.PROGRESSIF


def test_peignes_que_l_appariement_efface_télécinéma():
    a = classer([Brut(560, 0, 600)] * 2, [Apparie(43, 600, 403)] * 2, NTSC)
    assert (a.nature, a.ordre, a.decime) == (Nature.TELECINE, "tff", False)


def test_peignes_qui_restent_vraie_vidéo():
    a = classer([Brut(600, 0, 600)], [Apparie(281, 600, 594)], NTSC)
    assert a.nature == Nature.ENTRELACE


def test_ordre_bff_majoritaire():
    a = classer([Brut(10, 500, 600)], [Apparie(10, 600, 600)], 25.0)
    assert a.ordre == "bff"


def test_peignes_sans_mesure_après_appariement_indécis():
    assert classer([Brut(600, 0, 600)], [], NTSC) is None
    assert classer([], [], NTSC) is None


def test_3_2_régulier_en_ntsc_décimé():
    a = classer([Brut(240, 0, 600)] * 3, [Apparie(5, 600, 480)] * 3, NTSC)
    assert a.decime


def test_cadence_irrégulière_non_décimée():
    """The Kid : 2 images sur 3 ici, 3 sur 4 là — aucun diviseur juste."""
    a = classer([Brut(560, 0, 600)] * 2,
                [Apparie(40, 600, 403), Apparie(40, 600, 440)], NTSC)
    assert a.nature == Nature.TELECINE and not a.decime


def test_un_passage_fixe_suffit_à_écarter_decimate():
    a = classer([Brut(240, 0, 600)] * 3,
                [Apparie(5, 600, 480), Apparie(5, 600, 480), Apparie(5, 600, 30)], NTSC)
    assert not a.decime


def test_pas_de_décimation_en_pal():
    a = classer([Brut(300, 0, 600)], [Apparie(5, 600, 480)], 25.0)
    assert a.nature == Nature.TELECINE and not a.decime


# ─── Le filtre ────────────────────────────────────────────────────────────────

def test_filtre_télécinéma():
    assert filtre(_info(analyse=TELECINE)) == (
        "fieldmatch=order=tff:combmatch=full," + FILTRE_BWDIF)


def test_filtre_télécinéma_3_2():
    a = Analyse(Nature.TELECINE, "bff", True, 0.4, 0.0)
    assert filtre(_info(analyse=a)) == (
        "fieldmatch=order=bff:combmatch=full," + FILTRE_BWDIF + ",decimate")


def test_vraie_vidéo_non_déclarée_désentrelacée_entière():
    """Cure in Orange se dit progressif : `deint=interlaced` ne suffit pas."""
    assert filtre(_info("progressive", analyse=VIDEO)) == (
        "bwdif=mode=send_frame:parity=tff:deint=all")


def test_vraie_vidéo_déclarée_comme_avant():
    assert filtre(_info("tt", analyse=VIDEO)) == FILTRE_BWDIF


@pytest.mark.parametrize("analyse", [None, PROGRESS])
def test_sans_analyse_ou_progressif_les_marqueurs_décident(analyse):
    assert filtre(_info("tt", analyse=analyse)) == FILTRE_BWDIF
    assert filtre(_info("", analyse=analyse)) is None


# ─── Décision et commande ─────────────────────────────────────────────────────

def test_la_commande_réapparie_avant_les_pixels_carrés():
    dec = decide(_info(analyse=TELECINE, sar="8:9"), _profil())
    assert dec.video.action in (VideoAction.ENCODE_HEVC, VideoAction.ENCODE_H264)
    assert dec.desentrelace and dec.telecine_inverse
    filtres = _vf(build_command(dec, PLAT))
    assert filtres.startswith("fieldmatch=order=tff:combmatch=full,bwdif=")
    assert filtres.index("fieldmatch") < filtres.index("scale=")


def test_avant_agrandissement():
    dec = decide(_info(analyse=TELECINE), _profil())
    assert encoder._avant_agrandissement(dec)[0].startswith("fieldmatch=")


def test_une_vraie_vidéo_n_est_pas_un_télécinéma():
    dec = decide(_info(analyse=VIDEO), _profil())
    assert dec.desentrelace and not dec.telecine_inverse
    assert "deint=all" in _vf(build_command(dec, PLAT))


def test_une_source_gardée_telle_quelle_n_est_pas_touchée():
    info = _info(analyse=TELECINE, codec="hevc", bitrate=300_000)
    dec = decide(info, _profil())
    assert dec.video.action in (VideoAction.SKIP, VideoAction.REMUX)
    assert dec.filtre_entrelacement is None and not dec.telecine_inverse


# ─── Le scanner ───────────────────────────────────────────────────────────────

def test_le_scanner_analyse_une_fois(tmp_path, monkeypatch):
    p = tmp_path / "kid.avi"
    p.write_bytes(b"x")
    appels = []
    monkeypatch.setattr(ent, "analyser", lambda info, ff: appels.append(1) or TELECINE)
    monkeypatch.setattr(scanner, "_ANALYSES_ENTRELACEMENT", {})
    for _ in range(2):
        info = _info()
        info.path = p
        scanner._analyser_entrelacement(info)
        assert info.entrelacement is TELECINE
    assert appels == [1]


def test_le_scanner_saute_un_fichier_absent(monkeypatch):
    monkeypatch.setattr(ent, "analyser", lambda info, ff: pytest.fail("sondé"))
    info = _info()
    scanner._analyser_entrelacement(info)
    assert info.entrelacement is None


def test_le_scanner_saute_la_hd(tmp_path, monkeypatch):
    p = tmp_path / "film.mkv"
    p.write_bytes(b"x")
    monkeypatch.setattr(ent, "analyser", lambda info, ff: pytest.fail("sondé"))
    info = _info(h=1080, frame_rate="24000/1001")
    info.path = p
    scanner._analyser_entrelacement(info)
    assert info.entrelacement is None


# ─── Sur les fichiers réels ───────────────────────────────────────────────────

def _reelle(chemin: Path, field_order: str, frame_rate: str, duree: float) -> VideoInfo:
    return VideoInfo(path=chemin, width=720, height=480, bitrate=0, codec="",
                     duration=duree, frame_count=0, dv_profile=None,
                     field_order=field_order, frame_rate=frame_rate)


@pytest.mark.skipif(not LE_KID.exists() or not FFMPEG.exists(),
                    reason="The Kid ou ffmpeg absent")
def test_the_kid_est_un_télécinéma_irrégulier():
    a = ent.analyser(_reelle(LE_KID, "unknown", "2997/100", 6237.0), str(FFMPEG))
    assert (a.nature, a.ordre, a.decime) == (Nature.TELECINE, "tff", False)


@pytest.mark.skipif(not CURE.exists() or not FFMPEG.exists(),
                    reason="Cure in Orange ou ffmpeg absent")
def test_cure_in_orange_est_une_vraie_vidéo():
    a = ent.analyser(_reelle(CURE, "progressive", "30000/1001", 6579.0), str(FFMPEG))
    assert a.nature == Nature.ENTRELACE
