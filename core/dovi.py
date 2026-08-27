"""
core/dovi.py — Wrapper autour de dovi_tool pour le traitement Dolby Vision.

Fonctions principales :
  - get_path()             : chemin vers dovi_tool ou None
  - probe_file()           : sous-profil DV + métadonnées HDR10 statiques (scan)
  - extract_hevc_stream()  : extrait le flux HEVC brut d'un fichier
  - extract_rpu()          : extrait le RPU depuis un .hevc brut
  - convert_p7_to_p8()     : convertit un RPU profil 7 vers profil 8
  - rpu_info()             : interroge un RPU pour metadata HDR10
  - make_x265_hdr_params() : forge la chaîne -x265-params pour HDR10

Retrait pur du DV (orchestré par tui/screens/run.py), sans réencodage :
  1. ffmpeg     : extract HEVC brut          (input.mkv  → temp.hevc)
  2. dovi_tool  : remove                     (temp.hevc  → temp.nodv.hevc)
  3. mkvmerge   : remux avec les pistes      (→ sortie_[hdr10].mkv)

Pipeline DV→HDR10 par réencodage (orchestré par encoder.py) :
  1. ffmpeg     : extract HEVC brut          (input.mkv → temp.hevc)
  2. dovi_tool  : extract RPU                (temp.hevc  → temp.rpu)
  3. dovi_tool  : convert P7→P8 si requis    (temp.rpu   → temp.p8.rpu)
  4. dovi_tool  : info → master_display, max_cll
  5. ffmpeg     : encode HEVC HDR10 avec x265-params injectés
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

_log = logging.getLogger("iris_encode.dovi")

_EXE_NAME = "dovi_tool.exe" if sys.platform == "win32" else "dovi_tool"


# ─── Détection ────────────────────────────────────────────────────────────────

def get_path(bin_dir: Optional[Path] = None) -> Optional[Path]:
    """Retourne le chemin vers dovi_tool (PATH puis ./bin/), None si absent."""
    p = shutil.which(_EXE_NAME) or shutil.which("dovi_tool")
    if p:
        return Path(p)
    if bin_dir is not None:
        local = bin_dir / _EXE_NAME
        if local.exists():
            return local
    return None


def is_available(bin_dir: Optional[Path] = None) -> bool:
    return get_path(bin_dir) is not None


# ─── Probing d'un fichier source ──────────────────────────────────────────────

def probe_file(input_path: Path, dovi_path: Path,
               ffmpeg_path: str = "ffmpeg") -> dict:
    """
    Récupère sous-profil DV + master display + MaxCLL/FALL d'un fichier source.

    Retourne un dict :
      {
        "dv_subprofile":   "5" | "7.06" | "8.1" | "8.4" | None,
        "master_display":  "G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1)" | None,
        "max_cll":         (1000, 400) | None,
      }

    Retourne dict vide en cas d'échec — ne lève pas.
    Coût : 1-3 appels subprocess, ~50-150ms.
    """
    import tempfile
    result: dict = {}
    try:
        with tempfile.TemporaryDirectory(prefix="iris_dovi_probe_") as tmpdir:
            tmp_p = Path(tmpdir)
            hevc  = tmp_p / "probe.hevc"
            rpu   = tmp_p / "probe.rpu"

            # 1) extract HEVC raw (très rapide en stream copy)
            if not extract_hevc_stream(input_path, hevc, ffmpeg_path,
                                       duration_limit=30):
                return result
            # 2) extract RPU
            if not extract_rpu(hevc, rpu, dovi_path):
                return result
            # 3) interroger le RPU
            info = rpu_info(rpu, dovi_path)
            result.update(info)
    except Exception as e:
        _log.debug("probe_file failed for %s: %s", input_path, e)
    return result


# ─── Étapes du pipeline ───────────────────────────────────────────────────────

def extract_hevc_stream(input_path: Path, output_hevc: Path,
                        ffmpeg_path: str = "ffmpeg",
                        duration_limit: Optional[int] = None,
                        timeout: Optional[int] = 120) -> bool:
    """
    Extrait le flux HEVC brut (.hevc Annex-B) via ffmpeg.
    duration_limit (secondes) : tronque la copie — utile pour probing.
    timeout : None pour un fichier entier — 120 s suffisent aux 30 s du
    probing, pas à recopier 30 Go.
    """
    cmd = build_extract_hevc_command(input_path, output_hevc, ffmpeg_path,
                                     duration_limit)
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.returncode == 0 and output_hevc.exists()
    except Exception as e:
        _log.warning("extract_hevc_stream failed: %s", e)
        return False


def build_extract_hevc_command(input_path: Path, output_hevc: Path,
                               ffmpeg_path: str = "ffmpeg",
                               duration_limit: Optional[int] = None,
                               quiet: bool = True) -> list[str]:
    """Commande ffmpeg d'extraction du flux HEVC brut (copie, pas d'encodage).

    quiet=False laisse ffmpeg écrire ses lignes de progression : l'écran
    d'encodage les affiche, une recopie de 30 Go n'étant pas instantanée.
    """
    cmd = [ffmpeg_path, "-y"]
    if quiet:
        cmd += ["-loglevel", "error"]
    cmd += ["-i", str(input_path)]
    if duration_limit is not None:
        cmd += ["-t", str(duration_limit)]
    cmd += [
        "-map", "0:v:0",
        "-c:v", "copy",
        "-bsf:v", "hevc_mp4toannexb",
        "-f", "hevc",
        str(output_hevc),
    ]
    return cmd


def extract_rpu(hevc_path: Path, rpu_path: Path, dovi_path: Path) -> bool:
    """Extrait le RPU DV depuis un flux HEVC Annex-B."""
    cmd = [str(dovi_path), "extract-rpu", str(hevc_path), "-o", str(rpu_path)]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=300)
        return r.returncode == 0 and rpu_path.exists()
    except Exception as e:
        _log.warning("extract_rpu failed: %s", e)
        return False


def remove_dv(hevc_in: Path, hevc_out: Path, dovi_path: Path) -> bool:
    """
    Retire le RPU — et la couche d'amélioration d'un profil 7 — d'un flux HEVC.

    Ne touche à rien d'autre : les SEI HDR10 statiques (master display,
    MaxCLL) et les SEI HDR10+ restent en place, et les tranches d'image ne
    sont pas retouchées. La sortie décode bit à bit comme l'entrée.
    N'a de sens que sur un flux dont la couche de base est déjà du HDR10
    (profils 7 et 8.1) — voir VideoInfo.can_strip_dv.
    """
    cmd = [str(dovi_path), "remove", "-i", str(hevc_in), "-o", str(hevc_out)]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=1800)
        return r.returncode == 0 and hevc_out.exists()
    except Exception as e:
        _log.warning("remove_dv failed: %s", e)
        return False


def convert_p7_to_p8(rpu_in: Path, rpu_out: Path, dovi_path: Path) -> bool:
    """Convertit un RPU profil 7 vers profil 8 (mode 2 = native to 8.1)."""
    cmd = [str(dovi_path), "convert", "-m", "2", "-i", str(rpu_in),
           "-o", str(rpu_out)]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=120)
        return r.returncode == 0 and rpu_out.exists()
    except Exception as e:
        _log.warning("convert_p7_to_p8 failed: %s", e)
        return False


def rpu_info(rpu_path: Path, dovi_path: Path) -> dict:
    """
    Interroge un RPU pour récupérer profil + master display + MaxCLL/FALL.

    Retourne :
      { "dv_subprofile": str|None, "master_display": str|None,
        "max_cll": (cll, fall)|None }
    """
    cmd = [str(dovi_path), "info", "-i", str(rpu_path), "-f", "1"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        out = (r.stdout or "") + "\n" + (r.stderr or "")
    except Exception as e:
        _log.warning("rpu_info failed: %s", e)
        return {}

    info: dict = {}
    # Sous-profil — exemples sortie dovi_tool :
    #   "Dolby Vision Profile: 8.1"  ou  "DV profile: 5"
    m = re.search(r"profile[:\s]+([0-9]+(?:\.[0-9]+)?)", out, re.IGNORECASE)
    if m:
        info["dv_subprofile"] = m.group(1)

    # Master display — format x265 : "G(x,y)B(x,y)R(x,y)WP(x,y)L(max,min)"
    m = re.search(r"(G\(\d+,\d+\)B\(\d+,\d+\)R\(\d+,\d+\)"
                  r"WP\(\d+,\d+\)L\(\d+,\d+\))", out)
    if m:
        info["master_display"] = m.group(1)

    # MaxCLL / MaxFALL — "MaxCLL: 1000  MaxFALL: 400"
    m_cll  = re.search(r"max[\s_-]*cll[:\s]+(\d+)",  out, re.IGNORECASE)
    m_fall = re.search(r"max[\s_-]*fall[:\s]+(\d+)", out, re.IGNORECASE)
    if m_cll and m_fall:
        info["max_cll"] = (int(m_cll.group(1)), int(m_fall.group(1)))

    return info


# ─── Construction des paramètres x265 ─────────────────────────────────────────

def make_x265_hdr_params(
    master_display: Optional[str] = None,
    max_cll:        Optional[tuple[int, int]] = None,
) -> list[str]:
    """
    Retourne la liste de tokens à passer à -x265-params pour HDR10 propre.
    Convient pour libx265 CPU. À utiliser après extraction RPU.
    """
    params = [
        "hdr10-opt=1",
        "repeat-headers=1",
        "colorprim=bt2020",
        "transfer=smpte2084",
        "colormatrix=bt2020nc",
        "chromaloc=2",
    ]
    if master_display:
        params.append(f"master-display={master_display}")
    if max_cll:
        params.append(f"max-cll={max_cll[0]},{max_cll[1]}")
    return params


def x265_params_string(params: list[str]) -> str:
    """Concatène les tokens en chaîne `key=val:key=val` pour -x265-params."""
    return ":".join(params)


# ─── Helpers temp dir ─────────────────────────────────────────────────────────

def get_temp_dir(bin_dir: Path) -> Path:
    """Retourne (et crée) le dossier temp pour les artefacts DV."""
    tmp = bin_dir / "temp"
    tmp.mkdir(parents=True, exist_ok=True)
    return tmp


def cleanup_temp_files(*paths: Path) -> None:
    """Supprime silencieusement les fichiers temporaires."""
    for p in paths:
        try:
            if p.exists():
                p.unlink()
        except Exception as e:
            _log.debug("cleanup_temp failed for %s: %s", p, e)
