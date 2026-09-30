"""
core/platform.py — Abstraction OS + accélération matérielle.

Retourne un PlatformProfile figé décrivant les encodeurs à utiliser.
Version v1 : Windows uniquement, abstraction en place pour macOS/Linux.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum, auto


class OS(Enum):
    WINDOWS = auto()
    MACOS   = auto()
    LINUX   = auto()
    UNKNOWN = auto()


class GPU(Enum):
    NVIDIA = auto()
    APPLE  = auto()
    NONE   = auto()


@dataclass(frozen=True)
class PlatformProfile:
    os:           OS
    gpu:          GPU
    hwaccel:      str | None   # None → pas d'accélération
    encoder_hevc: str
    encoder_h264: str
    encoder_av1:  str   # av1_nvenc (Ada/RTX40+) ou libaom-av1 (CPU, très lent)
    # Encodeurs réellement utilisables sur cette machine, mesurés au lancement.
    # None tant que le sondage n'a pas eu lieu : on ne préjuge alors de rien.
    encodeurs_ok: frozenset[str] | None = None
    # Pourquoi NVENC est refusé, quand c'est le pilote : dit au lancement et au
    # refus d'un fichier. None si NVENC passe ou si la cause est autre.
    alerte_nvenc: str | None = None

    def peut_encoder(self, encodeur: str) -> bool | None:
        """True / False si le sondage a eu lieu, None sinon."""
        if self.encodeurs_ok is None:
            return None
        return encodeur in self.encodeurs_ok

    def __str__(self) -> str:
        gpu_str = self.gpu.name
        return (
            f"{self.os.name}/{gpu_str} — "
            f"hwaccel={self.hwaccel or 'none'} "
            f"HEVC={self.encoder_hevc} H264={self.encoder_h264}"
        )


def encodeurs_a_sonder(profil: "PlatformProfile") -> list[str]:
    """Tous les encodeurs que `build_command` peut choisir sur cette machine.

    La liste doit être exhaustive : ce qui n'y figure pas n'est jamais sondé,
    et `peut_encoder` le rend alors `False` — indistinguable d'un encodeur
    essayé et refusé. C'est ce qui rendait `cinema_4k_quality` inutilisable sur
    toute machine à carte graphique : son mode HDR10 « quality » impose
    libx265, qu'on ne sondait pas, et le lancement le refusait au nom d'une
    mesure qui n'avait pas eu lieu.
    """
    from .encoder import ENCODEUR_HDR10_QUALITY
    return [profil.encoder_hevc, profil.encoder_h264, profil.encoder_av1,
            ENCODEUR_HDR10_QUALITY]


def sonder_encodeurs(encodeurs: list[str], ffmpeg_path: str = "ffmpeg",
                     refus: dict[str, str] | None = None) -> frozenset[str]:
    """Ceux de `encodeurs` que cette machine sait réellement ouvrir.

    La détection par le modèle de carte ne suffit pas : NVENC n'encode l'AV1
    qu'à partir d'Ada, et une carte antérieure répond « No capable devices
    found » — après avoir laissé croire que l'encodeur existait. On demande
    donc à ffmpeg d'ouvrir chacun sur une image, ce qui coûte environ 0,3 s ;
    les sondages tournent en parallèle pour que le lancement n'en pâtisse pas.

    `refus`, s'il est fourni, reçoit la sortie d'erreur de chaque encodeur
    refusé : c'est là que ffmpeg dit pourquoi (voir `alerte_pilote_nvenc`).
    """
    import concurrent.futures
    import subprocess

    def essai(nom: str) -> tuple[str, bool, str]:
        try:
            r = subprocess.run(
                [ffmpeg_path, "-v", "error",
                 "-f", "lavfi", "-i", "nullsrc=s=256x144:d=0.05:r=25",
                 "-c:v", nom, "-frames:v", "1", "-f", "null", "-"],
                stdin=subprocess.DEVNULL, capture_output=True, timeout=20)
            return nom, r.returncode == 0, r.stderr.decode("utf-8", "replace")
        except Exception as e:
            return nom, False, str(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        resultats = list(pool.map(essai, encodeurs))
    if refus is not None:
        refus.update({nom: err for nom, ok, err in resultats if not ok})
    return frozenset(nom for nom, ok, _ in resultats if ok)


def alerte_pilote_nvenc(sortie: str) -> str | None:
    """Message lisible si ffmpeg refuse NVENC parce que le pilote est trop ancien.

    Chaque build de ffmpeg est compilé contre une version de l'API NVENC, qui
    fixe un pilote minimal ; en dessous, **tous** les encodeurs NVENC sont
    refusés. Le numéro de ffmpeg n'en dit rien : gyan.dev 8.1.2 exige le
    pilote 610, BtbN n8.1.3 se contente du 597. ffmpeg l'annonce ainsi :

        Driver does not support the required nvenc API version. Required: 13.1 Found: 13.0
        The minimum required Nvidia driver for nvenc is 610.00 or newer
    """
    import re

    api = re.search(r"required nvenc api version\.\s*Required:\s*(\S+)\s*Found:\s*(\S+)",
                    sortie, re.IGNORECASE)
    if not api:
        return None
    pilote = re.search(r"minimum required Nvidia driver for nvenc is (\S+)",
                       sortie, re.IGNORECASE)
    exige = f"le pilote NVIDIA {pilote.group(1)} ou plus récent" if pilote \
        else "un pilote NVIDIA plus récent"
    return (f"NVENC refusé : ce ffmpeg exige {exige} (API NVENC "
            f"{api.group(1)}, le pilote installé fournit la {api.group(2)}). "
            f"Mettre à jour le pilote, ou prendre un ffmpeg compilé pour une "
            f"API plus ancienne. D'ici là, les encodages par la carte "
            f"graphique sont refusés.")


def _detect_os() -> OS:
    s = platform.system()
    if s == "Windows":
        return OS.WINDOWS
    if s == "Darwin":
        return OS.MACOS
    if s == "Linux":
        return OS.LINUX
    return OS.UNKNOWN


def _has_nvidia() -> bool:
    if shutil.which("nvidia-smi") is None:
        return False
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=5,
        )
        return r.returncode == 0 and bool(r.stdout.strip())
    except Exception:
        return False


def detect() -> PlatformProfile:
    """Détecte la plateforme courante et retourne le profil adapté."""
    os_ = _detect_os()

    if os_ == OS.WINDOWS:
        if _has_nvidia():
            return PlatformProfile(
                os=os_,
                gpu=GPU.NVIDIA,
                hwaccel="cuda",
                encoder_hevc="hevc_nvenc",
                encoder_h264="h264_nvenc",
                encoder_av1 ="av1_nvenc",
            )
        # Windows sans NVIDIA → CPU (libx265/libx264 via ffmpeg)
        return PlatformProfile(
            os=os_,
            gpu=GPU.NONE,
            hwaccel=None,
            encoder_hevc="libx265",
            encoder_h264="libx264",
            encoder_av1 ="libaom-av1",
        )

    if os_ == OS.MACOS:
        return PlatformProfile(
            os=os_,
            gpu=GPU.APPLE,
            hwaccel="videotoolbox",
            encoder_hevc="hevc_videotoolbox",
            encoder_h264="h264_videotoolbox",
            encoder_av1 ="libaom-av1",
        )

    # Linux / inconnu → CPU
    return PlatformProfile(
        os=os_,
        gpu=GPU.NONE,
        hwaccel=None,
        encoder_hevc="libx265",
        encoder_h264="libx264",
        encoder_av1 ="libaom-av1",
    )
