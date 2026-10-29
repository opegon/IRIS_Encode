"""
tests/test_reprise_hors_puce.py — un fichier collé fait échouer le tout-puce.

Deux encodages mis bout à bout : le second annonce `bt709`, le premier rien.
Au raccord, le décodeur se réinitialise et ffmpeg 8.1 ne sait plus relier les
images restées sur la carte à l'encodeur — « Error reinitializing filters! »,
l'encodage s'arrête là. Le chemin processeur passe : l'écran d'encodage
relance le fichier par lui.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.test_nvdec import _nvidia
from tests.test_qsv import _apres

_FFMPEG = Path(__file__).resolve().parent.parent / "bin" / "ffmpeg.exe"
_SIGNATURE = "[vf#0:0 @ 000001ffee69a6c0] Error reinitializing filters!"


def _commande(source: Path, **kw):
    from dataclasses import replace

    from core.decision import VideoAction, decide, force_skip_to_encode
    from core.encoder import build_command
    from core.profiles import Profile
    from core.scanner import AudioTrack, VideoInfo

    info = VideoInfo(path=source, width=320, height=240, bitrate=12_000_000,
                     codec="h264", duration=4.0, frame_count=0, dv_profile=None,
                     audio_tracks=[AudioTrack(index=0, codec="aac", channels=2,
                                              language="fre", title="",
                                              bitrate=128_000)],
                     color_transfer="bt709", pix_fmt="yuv420p")
    prof = Profile(id="t", data={"bitrate_1080p_kbps": 2500,
                                 "bitrate_720p_kbps": 2000,
                                 "bitrate_4k_kbps": 5000, "keep_4k": False,
                                 "audio_languages": ["fre"]})
    dec = force_skip_to_encode(decide(info, prof))
    dec = replace(dec, video=replace(dec.video, action=VideoAction.ENCODE_HEVC))
    return build_command(dec, _nvidia(), **kw)


def test_la_reprise_ecarte_le_tout_puce(tmp_path):
    source = tmp_path / "film.mkv"
    source.write_bytes(b"")
    reprise = _commande(source, tout_puce_permis=False)
    assert _apres(reprise, "-hwaccel") == "cuda"
    assert "-hwaccel_output_format" not in reprise
    assert "scale_cuda" not in " ".join(reprise)
    assert _apres(reprise, "-pix_fmt") == "yuv420p"


def test_l_echec_au_raccord_demande_une_reprise(tmp_path):
    from core.encoder import relancer_hors_puce
    source = tmp_path / "film.mkv"
    source.write_bytes(b"")
    tout_puce = _commande(source)
    assert relancer_hors_puce(tout_puce, ["frame=1", _SIGNATURE, "Conversion failed!"])
    # Un autre échec n'a rien à gagner au chemin processeur.
    assert not relancer_hors_puce(tout_puce, ["No space left on device"])
    # La reprise elle-même n'en appelle pas une autre.
    assert not relancer_hors_puce(_commande(source, tout_puce_permis=False),
                                  [_SIGNATURE])


def _nvenc_ouvrable() -> bool:
    r = subprocess.run([str(_FFMPEG), "-v", "error", "-f", "lavfi", "-i",
                        "nullsrc=s=256x256", "-frames:v", "1", "-c:v",
                        "hevc_nvenc", "-f", "null", "-"], capture_output=True)
    return r.returncode == 0


@pytest.mark.skipif(not _FFMPEG.exists(), reason="ffmpeg du projet absent")
def test_fichier_colle_reel(tmp_path):
    """Le défaut et sa parade, sur un vrai ffmpeg et une vraie carte."""
    if not _nvenc_ouvrable():
        pytest.skip("pas de NVENC sur cette machine")
    from core.encoder import relancer_hors_puce

    def ff(*args):
        return subprocess.run([str(_FFMPEG), "-hide_banner", "-nostats",
                               "-v", "error", "-y", *args],
                              capture_output=True, text=True)

    a, b = tmp_path / "a.h264", tmp_path / "b.h264"
    for sortie, couleurs in ((a, []), (b, ["-color_range", "tv", "-colorspace",
                                           "bt709", "-color_primaries", "bt709",
                                           "-color_trc", "bt709"])):
        ff("-f", "lavfi", "-i", "testsrc2=s=320x240:r=25:d=2", "-c:v",
           "libx264", "-pix_fmt", "yuv420p", *couleurs, str(sortie))
    (tmp_path / "ab.h264").write_bytes(a.read_bytes() + b.read_bytes())
    source = tmp_path / "colle.mp4"
    ff("-r", "25", "-i", str(tmp_path / "ab.h264"), "-f", "lavfi", "-i",
       "sine=d=4", "-c:v", "copy", "-c:a", "aac", str(source))

    def encoder(cmd):
        # ffmpeg du projet ; la sortie prévue est à côté de la source.
        return subprocess.run([str(_FFMPEG), *cmd[1:]],
                              capture_output=True, text=True)

    echec = encoder(_commande(source))
    assert echec.returncode != 0
    assert relancer_hors_puce(_commande(source), echec.stderr.splitlines())
    assert encoder(_commande(source, tout_puce_permis=False)).returncode == 0


# ─── Passe vidéo Dolby Vision (IE-154) ───────────────────────────────────────
#
# Images sur la carte et aucun filtre : la reconstruction au raccord échoue
# quand même. L'ancien chemin de la passe (`-pix_fmt p010le`) passe.

def _passe_dv(source: Path, sortie: Path, **kw):
    from dataclasses import replace

    from core import decision as D
    from core.encoder import build_dv_video_command
    from core.profiles import Profile
    from core.scanner import AudioTrack, VideoInfo
    D.set_strip_dv_available(True)
    try:
        info = VideoInfo(path=source, width=1280, height=720,
                         bitrate=60_000_000, codec="hevc", duration=4.0,
                         frame_count=0, dv_profile=8, dv_bl_compat=1,
                         audio_tracks=[AudioTrack(index=0, codec="ac3",
                                                  channels=6, language="fre",
                                                  title="", bitrate=640_000)],
                         pix_fmt="yuv420p10le")
        prof = Profile(id="dv", data={"bitrate_4k_kbps": 12000,
                                      "keep_4k": True, "dolby_vision": "dv"})
        dec = D.decide(info, prof)
        # La décision ne réencode en DV qu'en 4K ; la commande ne lit que la
        # source et le débit — une mire 720p suffit, et va vite.
        dec = replace(dec, video=replace(dec.video,
                                         action=D.VideoAction.ENCODE_DV))
        return build_dv_video_command(dec, _nvidia(), sortie, str(_FFMPEG), **kw)
    finally:
        D.set_strip_dv_available(False)


def test_la_reprise_de_la_passe_dv_redescend_les_images(tmp_path):
    from core.encoder import relancer_hors_puce
    sur_carte = _passe_dv(tmp_path / "f.mkv", tmp_path / "v.hevc")
    assert relancer_hors_puce(sur_carte, [_SIGNATURE])
    reprise = _passe_dv(tmp_path / "f.mkv", tmp_path / "v.hevc",
                        sur_carte_permis=False)
    assert _apres(reprise, "-hwaccel") == "cuda"
    assert "-hwaccel_output_format" not in reprise
    assert _apres(reprise, "-pix_fmt") == "p010le"
    assert not relancer_hors_puce(reprise, [_SIGNATURE])


@pytest.mark.skipif(not _FFMPEG.exists(), reason="ffmpeg du projet absent")
def test_passe_dv_sur_un_fichier_colle_reel(tmp_path):
    if not _nvenc_ouvrable():
        pytest.skip("pas de NVENC sur cette machine")
    from core.encoder import relancer_hors_puce

    def ff(*args):
        return subprocess.run([str(_FFMPEG), "-hide_banner", "-nostats",
                               "-v", "error", "-y", *args],
                              capture_output=True, text=True)

    a, b = tmp_path / "a.hevc", tmp_path / "b.hevc"
    for sortie, couleurs in ((a, []), (b, ["-color_range", "tv", "-colorspace",
                                           "bt2020nc", "-color_primaries",
                                           "bt2020", "-color_trc", "smpte2084"])):
        ff("-f", "lavfi", "-i", "testsrc2=s=1280x720:r=24:d=2", "-c:v",
           "libx265", "-pix_fmt", "yuv420p10le", "-x265-params",
           "log-level=error", *couleurs, str(sortie))
    (tmp_path / "ab.hevc").write_bytes(a.read_bytes() + b.read_bytes())
    source = tmp_path / "colle.mp4"
    ff("-fflags", "+genpts", "-r", "24", "-i", str(tmp_path / "ab.hevc"),
       "-c", "copy", str(source))

    sortie = tmp_path / "video.hevc"
    sur_carte = _passe_dv(source, sortie)
    echec = subprocess.run(sur_carte, capture_output=True, text=True)
    assert echec.returncode != 0
    assert relancer_hors_puce(sur_carte, echec.stderr.splitlines())
    reprise = _passe_dv(source, sortie, sur_carte_permis=False)
    assert subprocess.run(reprise, capture_output=True).returncode == 0


class _Passe:
    """ffmpeg simulé : la passe sur la carte s'arrête au raccord, la reprise
    réussit et écrit sa sortie ; l'injection du RPU échoue, ce qui arrête le
    chemin DV là — la suite n'a rien à voir avec la reprise."""
    lances: list[list[str]] = []

    def __init__(self, cmd, duree=0.0):
        self.cmd, self.journal = cmd, []
        _Passe.lances.append(cmd)

    def start(self):
        if "-hwaccel_output_format" in self.cmd:
            self.journal = [_SIGNATURE, "Conversion failed!"]
        elif "-c:v" in self.cmd:
            Path(self.cmd[-1]).write_bytes(b"hevc")

    def iter_progress(self):
        return iter(())

    def wait(self):
        sur_carte = "-hwaccel_output_format" in self.cmd
        return 1 if sur_carte or "-c:v" not in self.cmd else 0


def test_l_ecran_reprend_la_passe_dv_a_la_meme_etape(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from core import dovi
    from tests.test_dv_chemins import _Ecran
    from tui.screens import run as run_mod
    from tui.screens.run import FileState, RunScreen

    class Ecran(_Ecran):
        _refuser_encodeur = RunScreen._refuser_encodeur
        _cause            = staticmethod(RunScreen._cause)
        _afficher_chaine  = RunScreen._afficher_chaine
        _libelle_chaine   = staticmethod(RunScreen._libelle_chaine)

        def _update_ffmpeg_line(self, texte):
            self.lignes.append(texte)

        def query_one(self, *a):
            raise LookupError          # pas de tableau hors de Textual

    tuyau = SimpleNamespace(cmd=["ffmpeg"], cmd_dt=["dovi_tool"], journal=[],
                            start=lambda: None, iter_progress=lambda: iter(()),
                            wait=lambda: 0)
    monkeypatch.setattr(dovi, "TuyauRpu", lambda *a, **k: tuyau)
    monkeypatch.setattr(dovi, "rpu_valide", lambda rpu: True)
    monkeypatch.setattr(dovi, "build_inject_command",
                        lambda enc, rpu, inj, outil: ["dovi_tool", "inject-rpu"])
    monkeypatch.setattr(run_mod, "EncoderProcess", _Passe)
    _Passe.lances = []

    source = tmp_path / "film.mkv"
    source.write_bytes(b"")
    from dataclasses import replace

    from core import decision as D
    from core.profiles import Profile
    from core.scanner import AudioTrack, VideoInfo
    info = VideoInfo(path=source, width=1280, height=720, bitrate=60_000_000,
                     codec="hevc", duration=4.0, frame_count=0, dv_profile=8,
                     dv_bl_compat=1, pix_fmt="yuv420p10le",
                     audio_tracks=[AudioTrack(index=0, codec="ac3", channels=6,
                                              language="fre", title="",
                                              bitrate=640_000)])
    D.set_strip_dv_available(True)
    try:
        dec = D.decide(info, Profile(id="dv", data={"dolby_vision": "dv"}))
    finally:
        D.set_strip_dv_available(False)
    dec = replace(dec, video=replace(dec.video, action=D.VideoAction.ENCODE_DV))
    ecran = Ecran(dec)
    ecran.lignes = []
    ecran._platform = _nvidia()

    ecran._encode_dv(0, dec)

    passes = [c for c in _Passe.lances if "-c:v" in c]
    assert len(passes) == 2
    assert "-hwaccel_output_format" in passes[0]
    assert "-hwaccel_output_format" not in passes[1]
    assert ecran._statuses[0].chaine == ("gpu", "cpu", "gpu")
    # La reprise garde le numéro de l'étape vidéo ; l'injection suit.
    numero = [l.split()[1] for l in ecran.lignes]
    assert numero[1] == numero[2] and numero[3] != numero[2]
    assert int(numero[3].split("/")[0]) == int(numero[2].split("/")[0]) + 1
    assert ecran._statuses[0].state == FileState.ERROR   # l'injection simulée
