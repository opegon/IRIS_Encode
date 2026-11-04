"""
tests/test_super_resolution.py — Chaîne de la super-résolution (IE-168).

Note `conception_upscaling_2026-11-03.md` § 3.2, § 10.2, § 10.3, § 10.12 :
`setparams` avec la colorimétrie de la source, libplacebo et ArtCNN C4F16 sur
Vulkan, copie du shader sans `//!WHEN`, chemin Windows échappé. Les essais
réels (dernière section) demandent un ffmpeg à libplacebo, un GPU Vulkan et le
shader dans `bin/shaders/` ; sans eux, ils sont sautés.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from core import decision, dovi, preflight, super_resolution as sr
from core.decision import VideoAction, decide
from core.encoder import build_command, filtre_super_resolution
from core.platform import GPU, OS, PlatformProfile
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo

FF_DV  = "C:/iris/bin/dv/ffmpeg.exe"
SHADER = Path("C:/iris/bin/shaders/ArtCNN_C4F16.glsl")
APP    = Path(__file__).resolve().parent.parent

_INTEL = PlatformProfile(os=OS.WINDOWS, gpu=GPU.INTEL, hwaccel="d3d11va",
                         encoder_hevc="hevc_qsv", encoder_h264="h264_qsv",
                         encoder_av1="av1_qsv",
                         encodeurs_ok=frozenset({"hevc_qsv", "h264_qsv"}))


@pytest.fixture(autouse=True)
def outils():
    decision._FACTEURS_CACHE = (1.2, 2.7)
    dovi.set_ffmpeg_dv(FF_DV)
    sr.set_shader(SHADER)
    sr._essais[(FF_DV, str(SHADER))] = None
    yield
    sr._essais.clear()


def _profil(passes: int = 1) -> Profile:
    return Profile(id="test", data={
        "bitrate_4k_kbps": 12000, "bitrate_1080p_kbps": 3000,
        "bitrate_720p_kbps": 1500, "bitrate_480p_kbps": 900, "keep_4k": False,
        "dolby_vision": "sdr", "preset_encoder": "medium",
        "audio_languages": ["fre"], "upscale": True, "upscale_passes": passes})


def _info(tmp_path: Path, w=720, h=400, sar="1:1", **over) -> VideoInfo:
    p = tmp_path / f"source_{w}x{h}.mkv"
    p.write_bytes(b"")
    return VideoInfo(path=p, width=w, height=h, bitrate=1_200_000, codec="h264",
                     duration=600.0, frame_count=15000, dv_profile=None,
                     audio_tracks=[AudioTrack(index=0, codec="aac", channels=2,
                                              language="fre", title="",
                                              bitrate=128_000)],
                     sar=sar, frame_rate="25/1", **{"pix_fmt": "yuv420p", **over})


def _vf(cmd: list[str]) -> str:
    return cmd[cmd.index("-vf") + 1]


# ─── Copie du shader ──────────────────────────────────────────────────────────

def test_copie_sans_when():
    data = (b"//!DESC a\r\n//!HOOK LUMA\r\n"
            b"//!WHEN OUTPUT.w LUMA.w / 1.3 > *\r\nvec4 hook() {}\r\n"
            b"  //!WHEN x\n//!DESC b\n")
    assert sr.sans_when(data) == (b"//!DESC a\r\n//!HOOK LUMA\r\n"
                                  b"vec4 hook() {}\r\n//!DESC b\n")


def _sources() -> dict:
    with (APP / "data" / "ffmpeg_releases.toml").open("rb") as f:
        return tomllib.load(f)


def test_installation_verifie_la_copie(tmp_path, monkeypatch, capsys):
    info = _sources()[sr.CLE_SHADER]
    asset = b"//!HOOK LUMA\n//!WHEN 1\nvec4 hook() {}\n"
    monkeypatch.setattr(preflight, "_download", lambda url, sha: asset)
    # L'empreinte épinglée n'est pas celle de cette copie : refusé.
    assert not preflight.install_shader(tmp_path, {sr.CLE_SHADER: info})
    assert not sr.chemin_shader(tmp_path).exists()
    # Empreinte de la copie juste : posée, sans `//!WHEN`.
    copie = hashlib.sha256(sr.sans_when(asset)).hexdigest()
    assert preflight.install_shader(
        tmp_path, {sr.CLE_SHADER: {**info, "sha256_copie": copie}})
    assert sr.chemin_shader(tmp_path).read_bytes() == b"//!HOOK LUMA\nvec4 hook() {}\n"


def test_empreinte_epinglee_de_la_copie():
    """`sha256_copie` est bien celle de l'asset publié, privé de `//!WHEN`."""
    info = _sources()[sr.CLE_SHADER]
    original = APP / "resources_files" / "mesure_igpu" / sr.SHADER
    if not original.is_file():
        pytest.skip("asset d'origine absent (resources_files/ n'est pas versionné)")
    data = original.read_bytes()
    assert hashlib.sha256(data).hexdigest() == info["sha256"]
    assert hashlib.sha256(sr.sans_when(data)).hexdigest() == info["sha256_copie"]


# ─── Chemin et colorimétrie ───────────────────────────────────────────────────

def test_chemin_windows_echappe():
    # `:` échappé pour les options, puis la barre pour le graphe.
    assert sr.chemin_filtre(Path("C:\\iris\\bin\\a.glsl")) == "C\\\\:/iris/bin/a.glsl"
    assert sr.chemin_filtre(Path("D:/d'O, [x];y/a.glsl")) == (
        "D\\\\:/d\\\\\\'O\\, \\[x\\]\\;y/a.glsl")


@pytest.mark.parametrize("h, attendu", [
    (400, "colorspace=smpte170m:color_primaries=smpte170m"),
    (480, "colorspace=smpte170m:color_primaries=smpte170m"),
    (576, "colorspace=bt470bg:color_primaries=bt470bg"),
    (720, "colorspace=bt709:color_primaries=bt709"),
])
def test_colorimetrie_absente_choisie_par_la_hauteur(tmp_path, h, attendu):
    assert sr.colorimetrie_source(_info(tmp_path, h=h)) == (
        f"setparams={attendu}:color_trc=bt709:range=tv")


def test_colorimetrie_declaree_gardee(tmp_path):
    info = _info(tmp_path, h=576, color_space="bt709", color_primaries="bt709",
                 color_transfer="bt470bg", color_range="pc")
    # La courbe reste bt709 : bt470bg serait lue comme un gamma 2,8.
    assert sr.colorimetrie_source(info) == (
        "setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=pc")
    inconnue = _info(tmp_path, h=480, color_space="reserved", pix_fmt="yuvj420p")
    assert sr.colorimetrie_source(inconnue).startswith(
        "setparams=colorspace=smpte170m:")
    assert sr.colorimetrie_source(inconnue).endswith(":range=pc")


# ─── Refus ────────────────────────────────────────────────────────────────────

def test_sans_shader_pas_d_agrandissement(tmp_path):
    sr.set_shader(None)
    dec = decide(_info(tmp_path), _profil())
    assert dec.video.upscale is None
    assert "shader" in dec.video.reason


def test_vulkan_en_echec_pas_d_agrandissement(tmp_path):
    sr._essais[(FF_DV, str(SHADER))] = "vkCreateInstance failed"
    dec = decide(_info(tmp_path), _profil())
    assert dec.video.upscale is None
    assert "Vulkan" in dec.video.reason


# ─── Filtre et commande ───────────────────────────────────────────────────────

def test_une_passe_cactus_jack(tmp_path):
    dec = decide(_info(tmp_path), _profil())
    assert (dec.video.target_width, dec.video.target_height) == (1920, 1066)
    shader = sr.chemin_filtre(SHADER)
    assert filtre_super_resolution(dec) == (
        "setparams=colorspace=smpte170m:color_primaries=smpte170m"
        ":color_trc=bt709:range=tv,"
        f"libplacebo=w=1920:h=1066:reset_sar=1:custom_shader_path={shader}"
        ":upscaler=ewa_lanczos:downscaler=ewa_lanczos"
        ":colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv"
        ":format=yuv420p,setsar=1")


def test_deux_passes(tmp_path):
    dec = decide(_info(tmp_path), _profil(passes=2))
    vf = filtre_super_resolution(dec)
    etapes = [f.split(":")[0] for f in vf.split(",libplacebo=")[1:]]
    assert etapes == ["w=1440", "w=2880", "w=1920"]
    assert vf.count("custom_shader_path=") == 2
    assert vf.count("format=yuv444p16le") == 2
    assert "w=1920:h=1066:downscaler=ewa_lanczos" in vf


def test_pixels_non_carres_un_seul_reechantillonnage(tmp_path):
    # The Kid : 720×480 en 8:9 → 640×480 affichés, puis 1440×1080.
    dec = decide(_info(tmp_path, w=720, h=480, sar="8:9",
                       field_order="tt"), _profil(passes=2))
    vf = filtre_super_resolution(dec)
    assert "scale=" not in vf
    assert vf.startswith("bwdif=")
    assert "libplacebo=w=1280:h=960:reset_sar=1:" in vf
    assert "w=1440:h=1080:downscaler" in vf


def test_commande_par_le_ffmpeg_a_libplacebo(tmp_path):
    dec = decide(_info(tmp_path), _profil())
    assert dec.video.action == VideoAction.ENCODE_HEVC
    cmd = build_command(dec, _INTEL)
    assert cmd[:3] == [FF_DV, "-init_hw_device", "vulkan"]
    # Ni décodage matériel ni chaîne tout-puce : libplacebo prend les images
    # en mémoire.
    assert "-hwaccel" not in cmd
    assert _vf(cmd).startswith("setparams=")
    assert cmd[cmd.index("-c:v") + 1] == "hevc_qsv"


# ─── Essais réels (GPU Vulkan) ────────────────────────────────────────────────

_FFMPEG = shutil.which("ffmpeg")
_SHADER_LOCAL = sr.chemin_shader(APP / "bin")


def _reel():
    if not (_FFMPEG and dovi.a_libplacebo(_FFMPEG) and _SHADER_LOCAL.is_file()):
        pytest.skip("ffmpeg à libplacebo ou shader installé absent")
    # Sans shader : la garde ne doit pas dépendre de ce que les essais vérifient.
    r = subprocess.run(
        [_FFMPEG, "-hide_banner", "-v", "error", "-init_hw_device", "vulkan",
         "-f", "lavfi", "-i", "color=s=64x64:d=0.1", "-vf", "libplacebo",
         "-f", "null", "-"], capture_output=True, timeout=60)
    if r.returncode != 0:
        pytest.skip("Vulkan indisponible sur ce poste")


def _empreinte(vf: str) -> str:
    r = subprocess.run(
        [_FFMPEG, "-hide_banner", "-v", "error", "-init_hw_device", "vulkan",
         "-f", "lavfi", "-i", "testsrc2=s=256x144:d=0.2:r=25",
         "-vf", vf, "-f", "md5", "-"],
        capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-400:]
    return r.stdout.strip()


def test_reel_chemin_difficile(tmp_path):
    _reel()
    dossier = tmp_path / "d'Oli, [x];y"
    dossier.mkdir()
    shutil.copy(_SHADER_LOCAL, dossier / sr.SHADER)
    assert sr._essayer(_FFMPEG, dossier / sr.SHADER) is None


def test_reel_le_shader_agit_sous_x1_3():
    """À ×1,25, la copie sans `//!WHEN` change l'image ; l'original, non :
    il laisse libplacebo agrandir seul (note § 10.3)."""
    _reel()
    base = "libplacebo=w=320:h=180:upscaler=ewa_lanczos:downscaler=ewa_lanczos"
    seul = _empreinte(base)
    copie = _empreinte(f"{base}:custom_shader_path={sr.chemin_filtre(_SHADER_LOCAL)}")
    assert copie != seul
    original = APP / "resources_files" / "mesure_igpu" / sr.SHADER
    if original.is_file():
        assert _empreinte(f"{base}:custom_shader_path="
                          f"{sr.chemin_filtre(original)}") == seul
