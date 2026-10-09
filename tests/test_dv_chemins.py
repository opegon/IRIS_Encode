"""
tests/test_dv_chemins.py — Les chemins Dolby Vision de la file (IE-126).

Constats CR-31, CR-54, CR-65 et CR-85 de `revue_code_2026-10-08.md`.
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import dovi
from core.decision import VideoAction
from core.muxer import ExternalTrack, TrackKind
from tui.screens.run import FileState, RunScreen

RACINE = Path(__file__).resolve().parent.parent
RUN = (RACINE / "tui" / "screens" / "run.py").read_text(encoding="utf-8")


# ─── CR-54 : une seule suppression de la source ──────────────────────────────

def _dec(chemin: Path, titre=None, supprimer=True):
    return SimpleNamespace(
        info=SimpleNamespace(path=chemin, titre=titre),
        delete_source_override=supprimer, profile={})


def _statut(etat=FileState.RUNNING):
    return SimpleNamespace(state=etat)


def test_un_fichier_part_avec_ses_annexes(tmp_path):
    film = tmp_path / "Film.mkv"
    film.write_bytes(b"x")
    nfo = tmp_path / "Film.nfo"
    nfo.write_text("<movie/>", encoding="utf-8")
    RunScreen._supprimer_source(None, _dec(film), _statut())
    assert not film.exists() and not nfo.exists()


def test_un_titre_de_disque_n_est_jamais_supprime(tmp_path):
    clip = tmp_path / "BDMV" / "STREAM" / "00001.m2ts"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"x")
    RunScreen._supprimer_source(None, _dec(clip, titre=object()), _statut())
    assert clip.exists()


def test_un_fichier_abandonne_par_s_garde_sa_source(tmp_path):
    """Les chemins DV supprimaient avant de regarder `S` ; la sortie,
    abandonnée, était effacée ensuite : on perdait les deux."""
    film = tmp_path / "Film.mkv"
    film.write_bytes(b"x")
    RunScreen._supprimer_source(None, _dec(film), _statut(FileState.SKIPPED))
    assert film.exists()


def test_sans_demande_rien_n_est_supprime(tmp_path):
    film = tmp_path / "Film.mkv"
    film.write_bytes(b"x")
    RunScreen._supprimer_source(None, _dec(film, supprimer=False), _statut())
    assert film.exists()


def test_les_trois_chemins_passent_par_la_meme_regle():
    """Passe principale, retrait DV, réencodage DV."""
    assert RUN.count("self._supprimer_source(dec, s)") == 3
    assert "source.unlink()" not in RUN


# ─── CR-65 : le succès se vérifie aussi sur les chemins DV ───────────────────

def test_une_piste_audio_vide_est_un_echec(tmp_path, monkeypatch):
    import tui.screens.run as run
    monkeypatch.setattr(run, "pistes_audio_vides",
                        lambda sortie, duree: ["VF (eac3, 0.05 s)"])
    dec = SimpleNamespace(info=SimpleNamespace(duration=7200.0))
    assert "VF (eac3, 0.05 s)" in RunScreen._audio_vide(dec, tmp_path / "x.mp4")
    monkeypatch.setattr(run, "pistes_audio_vides", lambda sortie, duree: [])
    assert RunScreen._audio_vide(dec, tmp_path / "x.mp4") == ""


def test_chaque_sortie_finale_est_controlee():
    """Passe principale et les deux chemins DV, avant toute suppression."""
    assert len(re.findall(r"self\._audio_vide\(dec, ", RUN)) == 3


# ─── CR-31 : ffmpeg en erreur dans le tuyau du RPU ───────────────────────────

class _Processus:
    """Un Popen simulé : code de retour fixe, flux vides."""
    def __init__(self, code: int):
        import io
        self.code = self.returncode = code
        self.pid = 0
        self.stdout = SimpleNamespace(close=lambda: None)
        self.stderr = io.BytesIO(b"")

    def wait(self, timeout=None):
        return self.code

    def poll(self):
        return self.code


def _tuyau(tmp_path, monkeypatch, code_ff, code_dt) -> int:
    codes = iter([code_ff, code_dt])           # ffmpeg, puis dovi_tool
    monkeypatch.setattr(dovi.subprocess, "Popen",
                        lambda *a, **k: _Processus(next(codes)))
    tuyau = dovi.TuyauRpu(tmp_path / "s.mkv", tmp_path / "x.rpu",
                          tmp_path / "dovi_tool.exe")
    tuyau.start()
    list(tuyau.iter_progress())
    return tuyau.wait()


def test_un_ffmpeg_en_erreur_invalide_le_rpu(tmp_path, monkeypatch):
    """Une lecture cassée en route : dovi_tool rend 0 sur le flux tronqué."""
    assert _tuyau(tmp_path, monkeypatch, 1, 0) != 0


def test_les_deux_a_zero_rendent_le_rpu(tmp_path, monkeypatch):
    assert _tuyau(tmp_path, monkeypatch, 0, 0) == 0


def test_un_dovi_tool_en_erreur_invalide_le_rpu(tmp_path, monkeypatch):
    assert _tuyau(tmp_path, monkeypatch, 0, 2) != 0


def test_un_rpu_vide_n_est_pas_un_rpu(tmp_path):
    rpu = tmp_path / "x.rpu"
    assert not dovi.rpu_valide(rpu)
    rpu.write_bytes(b"")
    assert not dovi.rpu_valide(rpu)
    rpu.write_bytes(b"rpu")
    assert dovi.rpu_valide(rpu)


# ─── CR-85 : un retrait du DV avec greffe ne part pas en mux ─────────────────

@pytest.mark.parametrize("action,attendu", [
    (VideoAction.SKIP, True),
    (VideoAction.STRIP_DV, False),
])
def test_seul_un_skip_avec_greffe_se_contente_d_un_mux(tmp_path, action, attendu):
    from tui.screens.wizard import WizardScreen
    piste = ExternalTrack(source_path=tmp_path / "vf.mka", source_tid=0,
                          kind=TrackKind.AUDIO, language="fre")
    faux = SimpleNamespace(_dec=SimpleNamespace(
        video=SimpleNamespace(action=action), external_tracks=[piste]))
    assert WizardScreen._muxable(faux) is attendu


# ─── IE-126 2/3 : greffes, chapitres et langues des chemins DV ───────────────
# CR-55, CR-63 et la règle audio des greffes (reportée d'IE-125). Les cas de
# bout en bout passent par le ffmpeg, le dovi_tool et le mkvmerge de `bin/`.

import json
import subprocess

from core import encoder, muxer, scanner
from core.decision import AudioAction, decide
from core.profiles import Profile
from core.scanner import AudioTrack, SubtitleTrack
from tui.screens.run import FileRunStatus

_BIN = RACINE / "bin"
_FFMPEG, _FFPROBE, _MKVMERGE, _DOVI = (_BIN / "ffmpeg.exe", _BIN / "ffprobe.exe",
                                       _BIN / "mkvmerge.exe", _BIN / "dovi_tool.exe")
outils = pytest.mark.skipif(
    not all(p.exists() for p in (_FFMPEG, _FFPROBE, _MKVMERGE, _DOVI)),
    reason="outils du projet absents")

SRT = ("1\r\n00:00:00,200 --> 00:00:00,900\r\nBonjour\r\n\r\n"
       "2\r\n00:00:01,000 --> 00:00:01,800\r\nAu revoir\r\n")


def _ff(*args: str) -> None:
    subprocess.run([str(_FFMPEG), "-y", "-loglevel", "error", *args],
                   check=True, stdin=subprocess.DEVNULL, capture_output=True)


def _flux(chemin: Path) -> list[dict]:
    r = subprocess.run([str(_FFPROBE), "-v", "error", "-print_format", "json",
                        "-show_streams", str(chemin)],
                       capture_output=True, encoding="utf-8", check=True)
    return json.loads(r.stdout)["streams"]


class _Ecran:
    """Le strict nécessaire de RunScreen pour dérouler un chemin DV hors de
    Textual : ses vraies méthodes, un `app` qui exécute sur place."""
    _strip_dv           = RunScreen._strip_dv
    _encode_dv          = RunScreen._encode_dv
    _transcoder_greffes = RunScreen._transcoder_greffes
    _porter_sous_titres = RunScreen._porter_sous_titres
    _ecrire_chapitres   = RunScreen._ecrire_chapitres
    _supprimer_source   = RunScreen._supprimer_source
    _demarrer           = RunScreen._demarrer
    _arreter            = RunScreen._arreter
    _executer           = RunScreen._executer
    _playlist_chapitres = staticmethod(RunScreen._playlist_chapitres)
    _audio_vide         = staticmethod(RunScreen._audio_vide)

    def __init__(self, dec):
        self.app = SimpleNamespace(
            call_from_thread=lambda f, *a, **k: f(*a, **k),
            dovi_path=_DOVI, mkvmerge_available=True, ffmpeg_path=str(_FFMPEG))
        self._statuses = [FileRunStatus(decision=dec, state=FileState.RUNNING)]
        self._process = self._mux = None
        self._abandon = self._paused = False
        self._current_idx = 0

    def _update_row(self, *a): pass
    def _update_header(self, *a): pass
    def _update_cmd_lines(self, *a): pass
    def _update_ffmpeg_line(self, *a): pass
    def _encode_next(self): pass


@pytest.fixture
def vrais_outils():
    encoder.set_ffmpeg_path(str(_FFMPEG))
    scanner.set_ffprobe_path(str(_FFPROBE))
    muxer.set_mkvmerge_path(str(_MKVMERGE))


def _retrait_avec_greffes(tmp_path: Path, conteneur: str):
    """Une source HEVC (sans RPU : `dovi_tool remove` la traverse telle
    quelle), une VF en FLAC et un `.srt` français greffés."""
    source = tmp_path / "film.mkv"
    _ff("-f", "lavfi", "-i", "testsrc=size=640x360:rate=25:duration=2",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-c:v", "libx265", "-preset", "ultrafast", "-x265-params", "log-level=none",
        "-c:a", "aac", str(source))
    vf = tmp_path / "vf.mka"
    _ff("-f", "lavfi", "-i", "sine=frequency=660:duration=2", "-c:a", "flac", str(vf))
    srt = tmp_path / "vf.fr.srt"
    srt.write_text(SRT, encoding="utf-8")

    profil = Profile(id="test", data={
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps": 8000, "audio_languages": ["fre", "eng"],
        "audio_copy_compatible": True, "preserve_hd_audio": False,
        "container": conteneur})
    dec = decide(scanner.scan(source), profil)
    # Forcé sur une source sans DV : le suffixe resterait celui d'un SKIP
    # (`.mux-iris.mkv`), d'où un nom posé à la main.
    dec.video.action = VideoAction.STRIP_DV
    dec.output_override = tmp_path / f"film.hdr10-iris.{conteneur}"
    dec.external_tracks += [
        ExternalTrack(source_path=vf, source_tid=0, kind=TrackKind.AUDIO,
                      language="fre", track_name="VF"),
        ExternalTrack(source_path=srt, source_tid=0, kind=TrackKind.SUBTITLE,
                      language="fre")]
    return dec


@outils
@pytest.mark.parametrize("conteneur", ["mp4", "mkv"])
def test_le_retrait_du_dv_garde_les_greffes_a_la_regle_du_profil(
        tmp_path, vrais_outils, conteneur):
    """CR-55 : en MP4, la commande n'avait que la source pour entrée — VF et
    sous-titre perdus, succès annoncé. Et en MKV comme en MP4, mkvmerge
    recopiait le FLAC greffé que la règle du profil transcode."""
    dec = _retrait_avec_greffes(tmp_path, conteneur)
    assert dec.output_container == f".{conteneur}"
    ecran = _Ecran(dec)
    ecran._strip_dv(0, dec)

    s = ecran._statuses[0]
    assert s.state == FileState.SUCCESS, (s.error_msg, s.last_line)
    flux = _flux(dec.output_path)
    audio = [f for f in flux if f["codec_type"] == "audio"]
    st = [f for f in flux if f["codec_type"] == "subtitle"]
    assert len(audio) == 2 and audio[1]["codec_name"] != "flac"
    assert audio[1]["tags"].get("language") == "fre"
    assert len(st) == 1 and st[0]["tags"].get("language") == "fre"
    # Rien ne traîne : ni Matroska recomposé, ni audio greffée transcodée.
    assert not [p for p in tmp_path.iterdir() if ".iris_" in p.name]


def test_le_reencodage_dv_greffe_aussi_a_la_regle_du_profil():
    """Les deux chemins DV passent par la même préparation des greffes, et
    mkvmerge ne reçoit plus `dec.external_tracks` tels quels."""
    assert RUN.count("self._transcoder_greffes(index, dec, produits)") == 2
    assert "tracks=dec.external_tracks" not in RUN
    assert RUN.count("chapitres=self._playlist_chapitres(dec)") == 2


class _FauxFfmpeg:
    """Écrit la sortie demandée et réussit."""
    def __init__(self, cmd, duree=0.0):
        self.cmd = cmd
    def start(self):
        Path(self.cmd[-1]).write_bytes(b"mka")
    def iter_progress(self):
        return iter(())
    def wait(self):
        return 0


def test_un_donneur_qui_perd_son_audio_garde_sa_place(tmp_path, monkeypatch):
    """mkvmerge range les pistes par donneur : le sous-titre de X, dont
    l'audio part dans un `.mka`, doit rester avant celui de Y — c'est dans cet
    ordre que `greffes_a_porter` lit le Matroska recomposé."""
    import core.decision as decision
    import tui.screens.run as run
    monkeypatch.setattr(decision, "audio_greffee", lambda ext, profil: SimpleNamespace(
        action=AudioAction.TRANSCODE, output_title="VF E-AC3 5.1",
        track=SimpleNamespace(index=0, language="fre", langue_completee=False),
        output_codec="eac3", output_bitrate=640_000, output_channels=0))
    monkeypatch.setattr(run, "EncoderProcess", _FauxFfmpeg)
    x, y = tmp_path / "x.mkv", tmp_path / "y.srt"
    pistes = [ExternalTrack(source_path=x, source_tid=1, kind=TrackKind.AUDIO,
                            language="fre", track_name="VF DTS"),
              ExternalTrack(source_path=y, source_tid=0, kind=TrackKind.SUBTITLE,
                            language="fre"),
              ExternalTrack(source_path=x, source_tid=2, kind=TrackKind.SUBTITLE,
                            language="eng")]
    dec = SimpleNamespace(external_tracks=pistes, profile={}, dossier_sortie=tmp_path,
                          info=SimpleNamespace(lecture=tmp_path / "film.mkv",
                                               duration=60.0))
    ecran = _Ecran(dec)
    produits: list[Path] = []
    rendues = ecran._transcoder_greffes(0, dec, produits)

    assert [p.name for p in produits] == ["film.iris_greffe0.mka"]
    assert [(t.source_path.name, t.source_tid) for t in rendues] == [
        ("film.iris_greffe0.mka", 0), ("x.mkv", 2), ("y.srt", 0)]
    assert rendues[0].track_name == "VF E-AC3 5.1"
    assert [t.language for t in muxer.premux_track_order(rendues)
            if t.kind == TrackKind.SUBTITLE] == [
        t.language for t in muxer.premux_track_order(pistes)
        if t.kind == TrackKind.SUBTITLE]


# ─── CR-63 : chapitres et langues d'un titre de Blu-ray ──────────────────────

def _titre(chapitres, dvd=False):
    return SimpleNamespace(chemin=Path("BDMV/PLAYLIST/00800.mpls"),
                           chapitres=chapitres, est_dvd=dvd)


@pytest.mark.parametrize("titre,attendu", [
    (None, None),
    (_titre([0.0]), None),
    (_titre([0.0, 340.0], dvd=True), None),
    (_titre([0.0, 340.0]), Path("BDMV/PLAYLIST/00800.mpls")),
])
def test_la_playlist_donne_les_chapitres_a_mkvmerge(titre, attendu):
    dec = SimpleNamespace(info=SimpleNamespace(titre=titre))
    assert RunScreen._playlist_chapitres(dec) == attendu


def test_mkvmerge_recoit_les_chapitres_de_la_playlist(tmp_path):
    cmd = muxer.build_strip_command(tmp_path / "v.hevc", tmp_path / "00001.m2ts",
                                    tmp_path / "s.mkv",
                                    chapitres=tmp_path / "00800.mpls")
    i = cmd.index("--chapters")
    assert cmd[i + 1] == str(tmp_path / "00800.mpls")


def _audio(langue_completee):
    return SimpleNamespace(
        action=AudioAction.COPY, output_title=None,
        track=AudioTrack(index=0, codec="ac3", channels=6, language="fre",
                         title="", bitrate=640_000,
                         langue_completee=langue_completee))


def test_l_audio_produite_a_part_garde_la_langue_du_clpi(tmp_path):
    cmd = encoder.build_audio_command(tmp_path / "00001.m2ts", tmp_path / "a.mka",
                                      [_audio(True)])
    assert "language=fre" in cmd
    cmd = encoder.build_audio_command(tmp_path / "00001.m2ts", tmp_path / "a.mka",
                                      [_audio(False)])
    assert "language=fre" not in cmd


def test_le_retrait_vers_mp4_ecrit_chapitres_et_langues(tmp_path):
    st = SubtitleTrack(index=3, codec="subrip", language="fre", title="",
                       forced=False, default=False, langue_completee=True)
    cmd = dovi.build_strip_mp4(tmp_path / "00001.m2ts", tmp_path / "s.mp4",
                               sous_titres=[3], audio=[_audio(True)],
                               chapitres=tmp_path / "c.txt", pistes_st=[st])
    i = cmd.index("ffmetadata")
    assert cmd[i + 2] == str(tmp_path / "c.txt")
    assert cmd[cmd.index("-map_chapters") + 1] == "1"
    assert cmd[cmd.index("-metadata:s:a:0") + 1] == "language=fre"
    assert cmd[cmd.index("-metadata:s:s:0") + 1] == "language=fre"



# ─── CR-32, CR-61 : dovi_tool arrêtable, `S` sur mkvmerge, SKIPPED tenu ──────

DOVI = (RACINE / "core" / "dovi.py").read_text(encoding="utf-8")


def test_aucun_delai_fixe_sur_une_etape_qui_lit_le_film():
    """remove, inject-rpu et le tuyau du RPU passent par des processus
    publiés : plus de `subprocess.run(…, timeout=…)` qui les tue (CR-32)."""
    for ancien in ("def remove_dv", "def inject_rpu", "def extract_rpu_depuis_source"):
        assert ancien not in DOVI
    assert "dovi.TuyauRpu(" in RUN
    assert RUN.count("self._executer(index, ") == 3


class _Bloque:
    """Une étape dovi_tool qui ne finirait jamais seule ; `X` tombe pendant."""
    lances: list = []

    def __init__(self, cmd, duree=0.0):
        self.cmd, self.termine = cmd, False

    def start(self):
        _Bloque.lances.append(self)
        if self.cmd[1:2] == ["remove"]:
            ecran = _Bloque.ecran
            ecran._statuses[0].state = FileState.SKIPPED   # `X` : l'état d'abord
            ecran._abandon = True
        else:
            Path(self.cmd[-1]).write_bytes(b"hevc")

    def iter_progress(self):
        return iter(())

    def terminate(self):
        self.termine = True

    def wait(self):
        return 1 if self.termine else 0


@outils
def test_x_pendant_dovi_tool_l_arrete_et_rien_ne_suit(tmp_path, vrais_outils,
                                                      monkeypatch):
    """`X` pendant `dovi_tool remove` ne trouvait rien à arrêter : dovi_tool
    écrivait encore des dizaines de Go, puis l'échec de l'étape suivante
    réécrivait le SKIPPED en ERROR, contre le bilan affiché."""
    import tui.screens.run as run
    dec = _retrait_avec_greffes(tmp_path, "mkv")
    ecran = _Ecran(dec)
    _Bloque.ecran, _Bloque.lances = ecran, []
    monkeypatch.setattr(run, "EncoderProcess", _Bloque)
    monkeypatch.setattr(run, "MuxProcess", _Bloque)
    ecran._strip_dv(0, dec)

    assert [p.cmd[1:2] for p in _Bloque.lances][-1] == ["remove"]
    assert _Bloque.lances[-1].termine
    assert ecran._statuses[0].state == FileState.SKIPPED


def _ecran_skip(process=None, mux=None):
    statut = SimpleNamespace(state=FileState.RUNNING, last_line="")
    notes: list = []
    return SimpleNamespace(
        _done=False, _process=process, _mux=mux, _paused=False, _started=True,
        _current_idx=0, _statuses=[statut], _update_row=lambda i: None,
        notify=lambda msg, **k: notes.append(msg), notes=notes)


def test_s_arrete_aussi_une_etape_mkvmerge():
    mux = SimpleNamespace(termine=False)
    mux.terminate = lambda: setattr(mux, "termine", True)
    ecran = _ecran_skip(mux=mux)
    RunScreen.action_skip_current(ecran)
    assert mux.termine and ecran._statuses[0].state == FileState.SKIPPED


def test_s_entre_deux_etapes_le_dit():
    ecran = _ecran_skip()
    RunScreen.action_skip_current(ecran)
    assert ecran.notes and ecran._statuses[0].state == FileState.RUNNING


def test_un_abandon_n_est_jamais_reecrit_en_echec():
    """Après chaque étape mkvmerge hors DV, l'échec d'une étape interrompue
    par `S` ou `X` ne repasse pas le fichier en erreur."""
    assert RUN.count("if s.state == FileState.SKIPPED:          # `S` ou `X` (CR-61)") == 4
    assert RUN.count("# fichier reste abandonné, comme le bilan l'affiche (CR-61).") == 2
