"""
tests/test_sar.py — Source SD sans SAR (IE-173).

Un DVD converti en AVI sans redimensionnement perd son SAR et s'affiche
déformé (The Kid : 4:3 vu en 3:2). L'analyse estime l'hypothèse 4:3 ou 16:9
d'après la zone d'image utile et le format d'origine du film (Wikidata), et
l'impose : la décision, l'encodage et le remux la suivent.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from core import sar
from core.decision import VideoAction, decide
from core.encoder import build_command
from core.platform import GPU, OS, PlatformProfile
from core.profiles import Profile
from core.sar import Confiance, Raison, estimer
from core.scanner import VideoInfo

APP    = Path(__file__).resolve().parent.parent
LE_KID = APP / "resources_files" / "The Kid (and A Dog's Life) - 1921.avi"


def _info(tmp_path: Path, w=720, h=480, sar_flux="", codec="msmpeg4v3",
          bitrate=1_500_000, nom="The Kid 1921.avi") -> VideoInfo:
    p = tmp_path / nom
    p.write_bytes(b"")
    return VideoInfo(path=p, width=w, height=h, bitrate=bitrate, codec=codec,
                     duration=6000.0, frame_count=0, dv_profile=None, sar=sar_flux)


def _profil() -> Profile:
    return Profile(id="t", data={"bitrate_480p_kbps": 1500, "bitrate_720p_kbps": 2000,
                                 "bitrate_1080p_kbps": 5000, "audio_languages": ["fre"],
                                 "preset_encoder": "ultrafast"})


def _plat() -> PlatformProfile:
    return PlatformProfile(os=OS.WINDOWS, gpu=GPU.NONE, hwaccel=None,
                           encoder_hevc="libx265", encoder_h264="libx264",
                           encoder_av1="libaom-av1")


# ─── Le doute ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("w,h,s,attendu", [
    (720, 480, "", True), (720, 576, "N/A", True), (704, 576, "1:1", True),
    (720, 480, "0:1", True), (720, 480, "32:27", False), (720, 576, "16:15", False),
    (1920, 1080, "", False), (704, 528, "1:1", False),
])
def test_sar_douteux(tmp_path, w, h, s, attendu):
    assert sar.sar_douteux(_info(tmp_path, w, h, s)) is attendu


def test_un_titre_de_disque_n_est_jamais_douteux(tmp_path):
    info = _info(tmp_path)
    info.titre = object()
    assert not sar.sar_douteux(info)


@pytest.mark.parametrize("geo,h43,h169", [
    ((720, 480), 4 / 3, 16 / 9), ((720, 576), 4 / 3, 16 / 9),
    ((704, 480), 4 / 3, 16 / 9), ((704, 576), 4 / 3, 16 / 9),
])
def test_les_sar_donnent_les_formats(geo, h43, h169):
    assert sar.ratio_affiche(geo, sar.SAR[geo]["4:3"]) == pytest.approx(h43)
    assert sar.ratio_affiche(geo, sar.SAR[geo]["16:9"]) == pytest.approx(h169)


# ─── L'estimation ────────────────────────────────────────────────────────────

def test_the_kid_format_connu_tranche():
    """Mesuré : 690×468 utiles. Les deux hypothèses tombent sur un format
    standard (1,31 / 1,75) ; le 1,33 de Wikidata tranche."""
    e = estimer(720, 480, (690, 468), (4 / 3,))
    assert (e.hypothese, e.confiance, e.raison, e.sar) == (
        "4:3", Confiance.PROBABLE, Raison.FORMAT_CONNU, "8:9")


def test_image_pleine_sans_format_connu_reste_indeterminee():
    e = estimer(720, 480, (690, 468))
    assert (e.hypothese, e.confiance, e.raison) == ("4:3", Confiance.INDETERMINE, Raison.AUCUN)


def test_sans_mesure_ni_format_defaut_4_3():
    e = estimer(720, 576, None)
    assert (e.hypothese, e.sar, e.confiance) == ("4:3", "16:15", Confiance.INDETERMINE)


def test_bandes_laterales_donnent_16_9():
    """Un film 4:3 dans un cadre 16:9 : 540 px utiles sur 720."""
    e = estimer(720, 576, (540, 576))
    assert (e.hypothese, e.raison) == ("16:9", Raison.BANDES)


def test_film_large_en_boite_aux_lettres_4_3():
    """2,35 dans un cadre 4:3 : 245 lignes utiles. En 16:9 ce serait 3,1."""
    e = estimer(720, 576, (720, 326))
    assert (e.hypothese, e.raison) == ("4:3", Raison.BANDES)


def test_film_large_anamorphose_16_9():
    """2,35 dans un cadre 16:9 : 436 lignes utiles. En 4:3 ce serait 1,76…
    proche de 1,78 : le format connu tranche."""
    e = estimer(720, 576, (720, 436), (2.35,))
    assert (e.hypothese, e.raison) == ("16:9", Raison.FORMAT_CONNU)


def test_un_format_connu_hors_des_deux_hypotheses_ne_tranche_pas():
    e = estimer(720, 480, (690, 468), (2.35,))
    assert e.confiance == Confiance.INDETERMINE


# ─── Les mesures et les libellés ──────────────────────────────────────────────

def test_le_cadre_est_le_maximum_des_mesures():
    """Une scène sombre rétrécit la zone détectée, les bandes jamais."""
    journaux = ["[cropdetect] x1:8 crop=584:420:120:50\n",
                "crop=520:414:192:10\n... crop=684:450:28:22",
                "crop=680:468:24:10", "rien ici"]
    assert sar.cadre_mesure(journaux) == (684, 468)
    assert sar.cadre_mesure(["", "erreur"]) is None


def test_la_mesure_lit_le_decodeur_impose(tmp_path):
    info = _info(tmp_path)
    info.decodeur = "hevc"
    cmd = sar.build_cropdetect(info, 120.0, "ff")
    assert cmd[0] == "ff" and cmd[cmd.index("-c:v") + 1] == "hevc"
    assert cmd.index("-c:v") < cmd.index("-i")
    assert "-skip_frame" in cmd


@pytest.mark.parametrize("libelle,attendu", [
    ("4:3", 4 / 3), ("2.35:1", 2.35), ("16:9", 16 / 9),
    ("Academy ratio", 1.375), ("high-definition television", None), ("", None),
])
def test_format_du_libelle(libelle, attendu):
    f = sar.format_du_libelle(libelle)
    assert f == (pytest.approx(attendu) if attendu else None)


def test_titres_a_chercher():
    assert sar.titres_a_chercher("The Kid (and A Dog's Life)") == [
        "The Kid (and A Dog's Life)", "The Kid"]
    assert sar.titres_a_chercher("Le Monde Du Silence") == ["Le Monde Du Silence"]


# ─── Wikidata, sans réseau ────────────────────────────────────────────────────

def _faux_wikidata(monkeypatch, annee_film="+1921-02-06T00:00:00Z", leve=False):
    appels = []

    def _get(params):
        appels.append(params)
        if leve:
            raise OSError("hors ligne")
        if params.get("list") == "search":
            if "(" in params["srsearch"]:
                return {"query": {"search": []}}
            return {"query": {"search": [{"title": "Q1"}, {"title": "Q2"}]}}
        if params.get("props") == "claims":
            def _film(temps, ratio):
                return {"claims": {
                    "P577": [{"mainsnak": {"datavalue": {"value": {"time": temps}}}}],
                    "P2061": [{"mainsnak": {"datavalue": {"value": {"id": ratio}}}}]}}
            return {"entities": {"Q1": _film("+2000-01-01T00:00:00Z", "Q235"),
                                 "Q2": _film(annee_film, "Q43")}}
        return {"entities": {"Q43": {"labels": {"en": {"value": "4:3"}}},
                             "Q235": {"labels": {"en": {"value": "2.35:1"}}}}}

    sar.format_connu.cache_clear()
    monkeypatch.setattr(sar, "_get", _get)
    return appels


def test_format_connu_retient_le_film_de_l_annee(monkeypatch):
    appels = _faux_wikidata(monkeypatch)
    assert sar.format_connu("The Kid (and A Dog's Life)", 1921) == pytest.approx((4 / 3,))
    # Le titre entier ne trouve rien, le titre court oui.
    assert [a["srsearch"] for a in appels if a.get("list")] == [
        "The Kid (and A Dog's Life) haswbstatement:P2061", "The Kid haswbstatement:P2061"]


def test_format_connu_sans_annee_qui_concorde(monkeypatch):
    _faux_wikidata(monkeypatch, annee_film="+1950-01-01T00:00:00Z")
    assert sar.format_connu("The Kid", 1921) == ()


def test_format_connu_sans_annee_ne_cherche_pas(monkeypatch):
    appels = _faux_wikidata(monkeypatch)
    assert sar.format_connu("The Kid", None) == ()
    assert appels == []


def test_format_connu_hors_ligne(monkeypatch):
    _faux_wikidata(monkeypatch, leve=True)
    assert sar.format_connu("The Kid", 1921) == ()


# ─── Ce que le SAR imposé change ──────────────────────────────────────────────

def test_le_sar_impose_rend_l_image_non_carree(tmp_path):
    info = _info(tmp_path)
    assert (info.largeur_affichee, info.pixels_non_carres) == (720, False)
    info.sar_impose = "8:9"
    assert (info.largeur_affichee, info.pixels_non_carres) == (640, True)


def test_l_encodage_pose_le_sar_avant_les_pixels_carres(tmp_path):
    info = _info(tmp_path)
    info.sar_impose = "8:9"
    dec = decide(info, _profil())
    assert dec.video.action != VideoAction.SKIP
    vf = build_command(dec, _plat())
    vf = vf[vf.index("-vf") + 1]
    assert vf.startswith("setsar=8/9,scale=trunc(iw*sar/2)*2"), vf


def test_sans_sar_impose_pas_de_setsar(tmp_path):
    dec = decide(_info(tmp_path), _profil())
    cmd = build_command(dec, _plat())
    assert not any("setsar=8/9" in c for c in cmd)


def test_une_video_bonne_sans_sar_est_remuxee(tmp_path):
    """Un H.264 720×480 au bon débit restait tel quel, image déformée."""
    info = _info(tmp_path, codec="h264", bitrate=800_000, nom="Film.1921.mkv")
    assert decide(info, _profil()).video.action == VideoAction.SKIP
    info.sar_impose = "8:9"
    dec = decide(info, _profil())
    assert dec.video.action == VideoAction.REMUX and "SAR" in dec.video.reason
    cmd = build_command(dec, _plat())
    assert cmd[cmd.index("-c:v") + 1] == "copy"
    assert cmd[cmd.index("-aspect") + 1] == "5760:4320"     # 4:3


def test_l_analyse_impose_l_estimation(tmp_path, monkeypatch):
    from core import scanner
    info = _info(tmp_path)
    monkeypatch.setattr(sar, "estimer_source",
                        lambda i, f: estimer(720, 480, (540, 480)))
    scanner._estimer_sar(info)
    assert info.sar_impose == "32:27" and info.sar_estimation.raison == Raison.BANDES


def test_scan_estime_une_source_sans_sar(tmp_path, monkeypatch):
    from core import scanner
    p = tmp_path / "The Kid 1921.avi"
    p.write_bytes(b"")
    flux = {"streams": [{"codec_type": "video", "codec_name": "msmpeg4v3",
                         "width": 720, "height": 480, "r_frame_rate": "30000/1001"}],
            "format": {"duration": "6000", "bit_rate": "1500000"}}
    monkeypatch.setattr(scanner, "_ffprobe_json", lambda *a, **k: flux)
    monkeypatch.setattr(sar, "estimer_source",
                        lambda i, f: estimer(720, 480, (690, 468), (4 / 3,)))
    info = scanner.scan(p)
    assert info.sar_impose == "8:9" and info.largeur_affichee == 640


def test_l_analyse_ne_touche_pas_un_sar_declare(tmp_path, monkeypatch):
    from core import scanner
    info = _info(tmp_path, sar_flux="32:27")
    monkeypatch.setattr(sar, "estimer_source", lambda i, f: pytest.fail("appelée"))
    scanner._estimer_sar(info)
    assert info.sar_impose == "" and info.sar_estimation is None


def test_une_estimation_qui_echoue_laisse_le_defaut(tmp_path, monkeypatch):
    from core import scanner
    info = _info(tmp_path)

    def _casse(i, f):
        raise RuntimeError("ffmpeg absent")
    monkeypatch.setattr(sar, "estimer_source", _casse)
    scanner._estimer_sar(info)
    assert info.sar_impose == "8:9"
    assert info.sar_estimation.confiance == Confiance.INDETERMINE


# ─── Sur le fichier réel ─────────────────────────────────────────────────────

@pytest.mark.skipif(not LE_KID.exists() or not shutil.which("ffmpeg"),
                    reason="The Kid ou ffmpeg absent")
def test_cadre_mesure_sur_the_kid():
    from core.scanner import scan
    info = VideoInfo(path=LE_KID, width=720, height=480, bitrate=0, codec="msmpeg4v3",
                     duration=6237.0, frame_count=0, dv_profile=None)
    l, h = sar.mesurer_cadre(info, shutil.which("ffmpeg"))
    assert 670 <= l <= 700 and 460 <= h <= 480
    assert estimer(720, 480, (l, h)).confiance == Confiance.INDETERMINE


# ─── Le choix de l'utilisateur (IE-173 2/3) ───────────────────────────────────

def _info_douteuse(tmp_path, cadre=(690, 468), formats=()):
    info = _info(tmp_path)
    info.sar_estimation = estimer(720, 480, cadre, formats)
    info.sar_impose = info.sar_estimation.sar
    return info


def test_choix_proposes(tmp_path):
    assert sar.choix(_info(tmp_path)) == [("4:3", "8:9"), ("16:9", "32:27"), ("1:1", "")]
    assert sar.choix(_info(tmp_path, 720, 576)) == [
        ("4:3", "16:15"), ("16:9", "64:45"), ("1:1", "")]


def test_choisir_sar_refait_le_cadre(tmp_path):
    from core.decision import choisir_sar
    dec = decide(_info_douteuse(tmp_path), _profil())
    dec.output_override = tmp_path / "ancien.mkv"
    choisir_sar(dec, "32:27")
    assert dec.info.sar_impose == "32:27" and dec.info.sar_confirme
    assert dec.info.largeur_affichee == 853
    assert dec.output_override is None
    vf = build_command(dec, _plat())
    assert vf[vf.index("-vf") + 1].startswith("setsar=32/27,")


def test_pixels_carres_choisis_ne_remuxent_pas(tmp_path):
    from core.decision import choisir_sar
    info = _info_douteuse(tmp_path)
    info.codec, info.bitrate = "h264", 800_000
    dec = decide(info, _profil())
    assert dec.video.action == VideoAction.REMUX
    choisir_sar(dec, "")
    assert dec.video.action == VideoAction.SKIP
    assert not dec.info.pixels_non_carres


def test_le_choix_survit_a_la_reanalyse(tmp_path):
    """L'accueil refait ses décisions à chaque analyse : le choix est noté
    dans les réglages explicites, puis réappliqué à une info neuve."""
    from core.decision import appliquer_reglages, choisir_sar, reglages_explicites
    profil = _profil()
    dec = decide(_info_douteuse(tmp_path), profil)
    assert reglages_explicites(dec, profil).vide
    choisir_sar(dec, "32:27")
    reglages = reglages_explicites(dec, profil)
    assert reglages.sar == "32:27" and not reglages.vide
    neuve = _info_douteuse(tmp_path)
    assert neuve.sar_impose == "8:9"
    dec2 = appliquer_reglages(neuve, profil, reglages, {})
    assert dec2.info.sar_impose == "32:27" and dec2.info.sar_confirme
    assert dec2.info.largeur_affichee == 853


def test_le_choix_pixels_carres_survit_aussi(tmp_path):
    from core.decision import appliquer_reglages, choisir_sar, reglages_explicites
    profil = _profil()
    dec = decide(_info_douteuse(tmp_path), profil)
    choisir_sar(dec, "")
    reglages = reglages_explicites(dec, profil)
    assert reglages.sar == ""
    dec2 = appliquer_reglages(_info_douteuse(tmp_path), profil, reglages, {})
    assert dec2.info.sar_impose == "" and dec2.info.sar_confirme


def test_l_estimation_n_est_pas_refaite_a_chaque_analyse(tmp_path, monkeypatch):
    from core import scanner
    appels = []

    def _estimer(i, f):
        appels.append(i.path)
        return estimer(720, 480, (690, 468))
    monkeypatch.setattr(sar, "estimer_source", _estimer)
    info = _info(tmp_path)
    scanner._estimer_sar(info)
    scanner._estimer_sar(VideoInfo(path=info.path, width=720, height=480, bitrate=0,
                                   codec="msmpeg4v3", duration=60.0, frame_count=0,
                                   dv_profile=None))
    assert len(appels) == 1
    # Le fichier change : nouvelle mesure.
    p = tmp_path / "The Kid 1921.avi"
    p.write_bytes(b"autre contenu")
    info = VideoInfo(path=p, width=720, height=480, bitrate=0, codec="msmpeg4v3",
                     duration=60.0, frame_count=0, dv_profile=None)
    scanner._estimer_sar(info)
    assert len(appels) == 2


def test_choisir_sar_refait_le_cadre_de_l_agrandissement(tmp_path, monkeypatch):
    """Le cadre d'une super-résolution suit la largeur affichée : 1440x1080
    en 4:3, 1920x1080 en 16:9."""
    from core import decision, dovi, super_resolution as sr
    from core.decision import choisir_sar
    ff, shader = "C:/iris/bin/dv/ffmpeg.exe", Path("C:/iris/bin/shaders/ArtCNN_C4F16.glsl")
    monkeypatch.setattr(decision, "_FACTEURS_CACHE", (1.2, 2.7))
    monkeypatch.setattr(dovi, "_ffmpeg_dv", ff)
    monkeypatch.setattr(sr, "_shader", shader)
    monkeypatch.setitem(sr._essais, (ff, str(shader)), None)
    profil = Profile(id="t", data={
        "bitrate_4k_kbps": 12000, "bitrate_1080p_kbps": 3000,
        "bitrate_720p_kbps": 1500, "bitrate_480p_kbps": 900, "keep_4k": False,
        "dolby_vision": "sdr", "preset_encoder": "medium",
        "audio_languages": ["fre"], "upscale": True, "upscale_passes": 1})
    dec = decide(_info_douteuse(tmp_path), profil)
    assert (dec.video.target_width, dec.video.target_height) == (1440, 1080)
    choisir_sar(dec, "32:27")
    assert (dec.video.target_width, dec.video.target_height) == (1920, 1080)


# ─── L'aperçu côte à côte (IE-173 3/3) ────────────────────────────────────────

def test_largeur_affichee():
    assert [sar.largeur_affichee(720, s) for s in ("8:9", "32:27", "16:15", "64:45", "")] == [
        640, 852, 768, 1024, 720]


def test_build_apercu_pose_les_deux_hypotheses(tmp_path):
    info = _info(tmp_path)
    info.decodeur = "hevc"
    cmd = sar.build_apercu(info, tmp_path / "a.png", "ff", Path("C:/Windows/Fonts/arial.ttf"))
    graphe = cmd[cmd.index("-filter_complex") + 1]
    assert cmd[0] == "ff" and cmd[cmd.index("-ss") + 1] == "1500.0"
    assert cmd.index("-c:v") < cmd.index("-i") and cmd[-1] == str(tmp_path / "a.png")
    assert "thumbnail=" in graphe and "hstack=inputs=2" in graphe
    gauche, droite = graphe.split(";")[1:3]
    # Chaînes brutes : « \: » hors d'elles est une séquence d'échappement
    # invalide (SyntaxWarning, erreur dans une version future, CR-148).
    assert "setsar=8/9,scale=640:480" in gauche and r"text='4\:3  640x480'" in gauche
    assert "setsar=32/27,scale=852:480" in droite and r"text='16\:9  852x480'" in droite
    assert r"fontfile='C\:/Windows/Fonts/arial.ttf'" in gauche


def test_build_apercu_sans_police_ni_etiquette(tmp_path):
    info = _info(tmp_path, 720, 576)
    graphe = sar.build_apercu(info, tmp_path / "a.png")[-6]
    assert "drawtext" not in graphe
    assert "scale=768:576" in graphe and "scale=1024:576" in graphe


class _Run:
    """Faux `subprocess.run` : rend les codes donnés, écrit l'image sur 0."""
    def __init__(self, codes):
        self.codes, self.cmds = list(codes), []

    def __call__(self, cmd, **k):
        from types import SimpleNamespace
        self.cmds.append(cmd)
        code = self.codes.pop(0)
        if code == 0:
            Path(cmd[-1]).write_bytes(b"png")
        return SimpleNamespace(returncode=code, stderr="No such filter: 'drawtext'\n")


def test_apercu_refait_sans_etiquettes_si_drawtext_manque(tmp_path, monkeypatch):
    monkeypatch.setattr(sar, "chemin_apercu", lambda i: tmp_path / "a.png")
    monkeypatch.setattr(sar, "_POLICE", Path(__file__))     # une police « présente »
    faux = _Run([1, 0])
    monkeypatch.setattr(sar.subprocess, "run", faux)
    assert sar.apercu(_info(tmp_path)) == tmp_path / "a.png"
    graphes = [c[c.index("-filter_complex") + 1] for c in faux.cmds]
    assert "drawtext" in graphes[0] and "drawtext" not in graphes[1]


def test_apercu_qui_echoue_ne_rend_pas_une_ancienne_image(tmp_path, monkeypatch):
    sortie = tmp_path / "a.png"
    sortie.write_bytes(b"ancienne")
    monkeypatch.setattr(sar, "chemin_apercu", lambda i: sortie)
    monkeypatch.setattr(sar, "_POLICE", tmp_path / "absente.ttf")
    monkeypatch.setattr(sar.subprocess, "run", _Run([1]))
    with pytest.raises(RuntimeError, match="drawtext"):
        sar.apercu(_info(tmp_path))
    assert not sortie.exists()


@pytest.mark.skipif(not LE_KID.exists() or not shutil.which("ffmpeg"),
                    reason="The Kid ou ffmpeg absent")
def test_apercu_reel_sur_the_kid(tmp_path, monkeypatch):
    import subprocess
    monkeypatch.setattr(sar, "chemin_apercu", lambda i: tmp_path / "kid.png")
    info = VideoInfo(path=LE_KID, width=720, height=480, bitrate=0, codec="msmpeg4v3",
                     duration=6237.0, frame_count=0, dv_profile=None)
    p = sar.apercu(info, shutil.which("ffmpeg"))
    dims = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height",
                           "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout
    assert dims.strip() == "1508,480"      # 640 + 16 + 852
