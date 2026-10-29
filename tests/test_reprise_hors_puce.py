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
