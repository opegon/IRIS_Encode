"""
core/super_resolution.py — Ce dont l'agrandissement par super-résolution a
besoin (IE-168) : le shader, sa copie, son chemin dans un filtre, la
colorimétrie déclarée à libplacebo et l'essai de Vulkan.

Le filtre lui-même est construit par `encoder.filtre_super_resolution`.
Note de conception : `conception_upscaling_2026-11-03.md`, § 3.2, § 10.2,
§ 10.3.
"""
from __future__ import annotations

import logging
import subprocess
import threading
from pathlib import Path
from typing import Optional

from .i18n import _

_log = logging.getLogger("iris_encode.super_resolution")

# Clé de `data/ffmpeg_releases.toml` et nom du fichier posé dans `bin/shaders/`.
CLE_SHADER = "artcnn"
SHADER     = "ArtCNN_C4F16.glsl"


def chemin_shader(bin_dir: Path) -> Path:
    return bin_dir / "shaders" / SHADER


def sans_when(data: bytes) -> bytes:
    """Le shader sans ses lignes `//!WHEN` (note D13).

    Chaque passe d'ArtCNN ne s'exécute qu'au-delà de ×1,3 : en deçà,
    libplacebo agrandit seul, et un DVD PAL (×1,25) serait annoncé
    « super-résolution » sans l'être (note § 10.3). La licence MIT permet la
    modification ; l'empreinte de la copie est vérifiée à l'installation.
    """
    return b"".join(ligne for ligne in data.splitlines(keepends=True)
                    if not ligne.lstrip().startswith(b"//!WHEN"))


def chemin_filtre(chemin: Path) -> str:
    """Un chemin de fichier écrit comme valeur d'option dans `-vf`.

    Deux niveaux le relisent : le graphe de filtres (`, ; [ ]` séparent les
    filtres), puis les options du filtre (`:` les sépare). Sous Windows,
    `C:` coupait l'option en deux. Chaque niveau retire une barre oblique
    inverse devant les caractères qu'il réserve : on les échappe donc deux
    fois, en commençant par le niveau le plus interne. Les `\\` de Windows
    deviennent des `/`, que ffmpeg accepte.
    """
    valeur = str(chemin).replace("\\", "/")
    valeur = "".join("\\" + c if c in "\\':" else c for c in valeur)
    return "".join("\\" + c if c in "\\'[],;" else c for c in valeur)


# Valeurs de ffprobe que `setparams` accepte, pour les sources SDR qu'on
# agrandit (le HDR est exclu en v1).
_MATRICES  = frozenset({"bt709", "fcc", "bt470bg", "smpte170m", "smpte240m", "bt2020nc"})
_PRIMAIRES = frozenset({"bt709", "bt470m", "bt470bg", "smpte170m", "smpte240m",
                        "film", "bt2020"})


def colorimetrie_source(info) -> str:
    """Le `setparams` à placer avant libplacebo.

    Une source sans étiquette est devinée par libplacebo d'après sa
    définition (SD → BT.601) et la sortie aussi (HD → BT.709) : il convertit
    alors l'une vers l'autre, jusqu'à 14 dB de PSNR perdus sur certaines
    images (note § 10.2). Déclarée, la conversion n'a lieu que si elle est
    voulue. Absente, elle est choisie d'après la hauteur : BT.601 NTSC
    jusqu'à 480 lignes, PAL jusqu'à 576, BT.709 au-delà.

    La courbe de transfert est toujours `bt709` : les courbes des sources SDR
    (`smpte170m`, `bt470bg`, `bt709`) désignent en pratique la même courbe
    d'écran, et `bt470bg` serait lue comme un gamma 2,8 — l'image
    s'assombrirait à la conversion.
    """
    if info.height <= 480:
        defaut = "smpte170m", "smpte170m"
    elif info.height <= 576:
        defaut = "bt470bg", "bt470bg"
    else:
        defaut = "bt709", "bt709"
    matrice = info.color_space if info.color_space in _MATRICES else defaut[0]
    primaires = (info.color_primaries if info.color_primaries in _PRIMAIRES
                 else defaut[1])
    plage = ("pc" if info.color_range == "pc" or info.pix_fmt.startswith("yuvj")
             else "tv")
    return (f"setparams=colorspace={matrice}:color_primaries={primaires}"
            f":color_trc=bt709:range={plage}")


# ─── État retenu au lancement ────────────────────────────────────────────────

_shader: Optional[Path] = None
_essais: dict[tuple[str, str], Optional[str]] = {}
_verrou = threading.Lock()


def set_shader(chemin: Optional[Path]) -> None:
    global _shader
    _shader = chemin


def shader() -> Optional[Path]:
    """Le shader retenu au lancement, ou None s'il n'est pas installé."""
    return _shader


def chercher_shader(bin_dir: Path) -> Optional[Path]:
    chemin = chemin_shader(bin_dir)
    return chemin if chemin.is_file() else None


def _essayer(ffmpeg: str, chemin: Path) -> Optional[str]:
    """Un dixième de seconde d'image passé par libplacebo et le shader : None
    si cela marche, sinon la fin de l'erreur de ffmpeg.

    `a_libplacebo` ne lit que la liste des filtres ; un poste sans pilote
    Vulkan, ou un shader que le GPU ne compile pas, ne se voit qu'ici.
    Environ 3 s (initialisation de Vulkan, compilation du shader).
    """
    vf = f"libplacebo=w=256:h=192:custom_shader_path={chemin_filtre(chemin)}"
    try:
        r = subprocess.run(
            [ffmpeg, "-hide_banner", "-v", "error", "-init_hw_device", "vulkan",
             "-f", "lavfi", "-i", "color=c=gray:s=128x96:d=0.1",
             "-vf", vf, "-f", "null", "-"],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=60,
            encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as e:
        return str(e)
    if r.returncode == 0:
        return None
    return (r.stderr or "").strip()[-500:] or f"exit {r.returncode}"


def refus(ffmpeg: str) -> Optional[str]:
    """Pourquoi ce ffmpeg ne peut pas agrandir sur ce poste, ou None.

    L'essai n'est lancé qu'une fois par session, au premier fichier que la
    règle agrandirait : un profil sans `upscale` ne le paie jamais.
    """
    chemin = _shader
    if chemin is None:
        return _("super-resolution shader not installed")
    cle = (ffmpeg, str(chemin))
    with _verrou:
        if cle not in _essais:
            _essais[cle] = _essayer(ffmpeg, chemin)
            if _essais[cle] is not None:
                _log.warning("libplacebo test failed: %s", _essais[cle])
        echec = _essais[cle]
    return None if echec is None else _("Vulkan test failed")
