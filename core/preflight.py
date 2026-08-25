"""
core/preflight.py — Vérification et auto-installation des outils.

Ordre de recherche : PATH système → dossier local ./bin/
Installation via téléchargement ZIP avec vérification SHA256.
"""
from __future__ import annotations

import hashlib
import io
import platform
import shutil
import subprocess
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

APP_DIR     = Path(__file__).resolve().parent.parent
DATA_DIR    = APP_DIR / "data"
CACHE_FILE  = DATA_DIR / "ffmpeg_releases_cache.toml"
STATIC_FILE = DATA_DIR / "ffmpeg_releases.toml"

ESSENTIAL_TOOLS = ("ffmpeg", "ffprobe")
OPTIONAL_TOOLS  = ("dovi_tool", "mkvmerge")
ALL_TOOLS       = ESSENTIAL_TOOLS + OPTIONAL_TOOLS


@dataclass
class ToolStatus:
    name:    str
    found:   bool
    path:    Optional[Path] = None
    version: str = ""


def _is_windows() -> bool:
    return platform.system() == "Windows"


def _exe(name: str) -> str:
    return name + ".exe" if _is_windows() else name


def _get_version(path: str) -> str:
    """
    Tente -version (ffmpeg/ffprobe) puis --version (dovi_tool, mkvmerge, GNU).
    Retourne la version extraite ou une chaîne vide.
    """
    for flag in ("-version", "--version"):
        try:
            r = subprocess.run(
                [path, flag],
                capture_output=True, text=True, timeout=5,
            )
            output = (r.stdout or r.stderr or "").strip()
            if not output or r.returncode not in (0, 1):
                continue
            # Cherche un numéro de version semver (X.Y ou X.Y.Z) en priorité.
            # Le 'v?' couvre les versions collées à leur préfixe (mkvmerge v99.0),
            # où \b ne s'applique pas entre la lettre et le premier chiffre.
            m = __import__('re').search(r'\bv?(\d+\.\d+(?:\.\d+)*)\b', output)
            if m:
                return m.group(1)
            # Fallback : dernier token de la première ligne (hash, build id…)
            first_line = output.splitlines()[0]
            tokens = first_line.split()
            return tokens[-1][:20] if tokens else first_line[:30]
        except Exception:
            continue
    return ""


def check_tools(bin_dir: Path) -> list[ToolStatus]:
    statuses: list[ToolStatus] = []
    for name in ALL_TOOLS:
        exe = _exe(name)
        # 1. PATH système
        p = shutil.which(exe) or shutil.which(name)
        if p:
            statuses.append(ToolStatus(
                name=name, found=True,
                path=Path(p), version=_get_version(p),
            ))
            continue
        # 2. ./bin/
        local = bin_dir / exe
        if local.exists():
            statuses.append(ToolStatus(
                name=name, found=True,
                path=local, version=_get_version(str(local)),
            ))
            continue
        statuses.append(ToolStatus(name=name, found=False))
    return statuses


def _load_releases() -> dict:
    for path in (CACHE_FILE, STATIC_FILE):
        if path.exists():
            try:
                with path.open("rb") as f:
                    return tomllib.load(f)
            except Exception:
                continue
    return {}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().lower()


def _download(url: str) -> Optional[bytes]:
    try:
        import requests
        r = requests.get(url, stream=True, timeout=120)
        r.raise_for_status()
        return r.content
    except Exception as e:
        print(f"  ✗ Téléchargement échoué : {e}")
        return None


def _install_from_zip(data: bytes, bin_dir: Path, targets: set[str]) -> bool:
    """Extrait les exécutables ciblés depuis un ZIP vers bin_dir."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    installed = 0
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for member in zf.namelist():
                fname = Path(member).name
                if fname in targets:
                    target = bin_dir / fname
                    target.write_bytes(zf.read(member))
                    if not _is_windows():
                        target.chmod(0o755)
                    print(f"  ✓ Installé : {target}")
                    installed += 1
    except zipfile.BadZipFile:
        print("  ✗ Archive invalide (non ZIP).")
        return False
    return installed > 0


def install_ffmpeg(bin_dir: Path, fetch_url: str) -> bool:
    targets = {_exe("ffmpeg"), _exe("ffprobe")}
    print(f"  Téléchargement depuis {fetch_url}")
    data = _download(fetch_url)
    if data is None:
        return False
    return _install_from_zip(data, bin_dir, targets)


def install_dovi_tool(bin_dir: Path, releases: dict) -> bool:
    """Télécharge et installe dovi_tool depuis GitHub."""
    os_key = "windows" if _is_windows() else "linux"
    info   = releases.get("dovi_tool", {}).get(os_key, {})
    url    = info.get("url", "")
    if not url:
        print("  ✗ URL dovi_tool introuvable dans les sources.")
        return False
    print(f"  Téléchargement depuis {url}")
    data = _download(url)
    if data is None:
        return False
    target_name = _exe("dovi_tool")
    # Tente d'abord l'extraction ZIP
    try:
        with __import__('io').BytesIO(data) as buf:
            ok = _install_from_zip(data, bin_dir, {target_name})
        if ok:
            return True
    except Exception:
        pass
    # Fallback : binaire direct (certaines releases ne sont pas zippées)
    bin_dir.mkdir(parents=True, exist_ok=True)
    dest = bin_dir / target_name
    dest.write_bytes(data)
    if not _is_windows():
        dest.chmod(0o755)
    print(f"  ✓ Installé : {dest}")
    return True


def install_mkvtoolnix(bin_dir: Path, releases: dict) -> bool:
    """
    Télécharge l'archive portable MKVToolNix et en extrait mkvmerge.

    Les exécutables CLI sont liés statiquement : mkvmerge.exe fonctionne seul,
    sorti de l'arborescence de l'archive. Windows uniquement — sous Linux,
    mkvtoolnix s'installe par le gestionnaire de paquets.
    """
    if not _is_windows():
        print("  Sous Linux, installez mkvtoolnix via votre gestionnaire de paquets.")
        return False
    info = releases.get("mkvtoolnix", {}).get("windows", {})
    url  = info.get("url", "")
    if not url:
        print("  ✗ URL mkvtoolnix introuvable dans les sources.")
        return False
    print(f"  Téléchargement depuis {url}")
    data = _download(url)
    if data is None:
        return False
    return _install_from_zip(data, bin_dir, {_exe("mkvmerge")})


def print_status(statuses: list[ToolStatus]) -> None:
    for s in statuses:
        icon = "✓" if s.found else "✗"
        ver  = f" — {s.version}" if s.version else ""
        opt  = " (optionnel)" if s.name in OPTIONAL_TOOLS and not s.found else ""
        print(f"  [{icon}] {s.name:<12}{ver}{opt}")


def run_preflight(cfg: dict) -> bool:
    """
    Vérifie les outils et installe ffmpeg si nécessaire.
    Retourne True si ffmpeg et ffprobe sont disponibles.
    """
    from . import config as cfg_mod
    bin_dir  = cfg_mod.get_bin_dir(cfg)
    statuses = check_tools(bin_dir)

    print()
    print_status(statuses)
    print()

    missing_essential = [
        s for s in statuses
        if s.name in ESSENTIAL_TOOLS and not s.found
    ]

    missing_dovi     = next((s for s in statuses if s.name == "dovi_tool" and not s.found), None)
    missing_mkvmerge = next((s for s in statuses if s.name == "mkvmerge"  and not s.found), None)

    if not missing_essential:
        # ffmpeg OK — proposer les outils optionnels absents
        if missing_dovi:
            print("  dovi_tool absent (optionnel — nécessaire pour le Dolby Vision).")
            _offer_dovi_install(bin_dir)
            print()
        if missing_mkvmerge:
            print("  mkvmerge absent (optionnel — nécessaire pour ajouter des pistes externes).")
            _offer_mkvmerge_install(bin_dir)
            print()
        return True

    fetch_url    = cfg.get("ffmpeg", {}).get("fetch_url", "")
    auto_install = cfg.get("ffmpeg", {}).get("auto_install", True)

    if not fetch_url:
        print(
            "  ✗ Aucune URL de téléchargement configurée.\n"
            "    Renseignez config.toml > [ffmpeg] > fetch_url"
        )
        return False

    if auto_install:
        answer = input(
            "  Télécharger et installer ffmpeg dans ./bin/ ? (o/N) : "
        ).strip().lower()
        if answer == "o":
            ok = install_ffmpeg(bin_dir, fetch_url)
            if ok:
                # Recheck
                statuses = check_tools(bin_dir)
                missing  = [s for s in statuses if s.name in ESSENTIAL_TOOLS and not s.found]
                return len(missing) == 0
        return False

    print("  Installez ffmpeg manuellement dans ./bin/ ou ajoutez-le au PATH.")
    return False


def _offer_dovi_install(bin_dir: Path) -> None:
    """Propose l'installation de dovi_tool si absent (optionnel)."""
    releases = _load_releases()
    answer   = input(
        "  Télécharger et installer dovi_tool (Dolby Vision) dans ./bin/ ? (o/N) : "
    ).strip().lower()
    if answer == "o":
        ok = install_dovi_tool(bin_dir, releases)
        if not ok:
            print("  ✗ Installation dovi_tool échouée — fonctionnalité Dolby Vision indisponible.")
    else:
        print("  dovi_tool ignoré — les fichiers Dolby Vision ne seront pas traités de façon optimale.")


def _offer_mkvmerge_install(bin_dir: Path) -> None:
    """Propose l'installation de mkvmerge si absent (optionnel)."""
    releases = _load_releases()
    answer   = input(
        "  Télécharger et installer mkvmerge (pistes externes) dans ./bin/ ? (o/N) : "
    ).strip().lower()
    if answer == "o":
        ok = install_mkvtoolnix(bin_dir, releases)
        if not ok:
            print("  ✗ Installation mkvmerge échouée — ajout de pistes externes indisponible.")
    else:
        print("  mkvmerge ignoré — l'ajout de pistes audio/sous-titres externes sera indisponible.")


def get_tool_path(name: str, bin_dir: Path) -> Optional[str]:
    """Retourne le chemin vers l'outil (PATH ou ./bin/), ou None."""
    p = shutil.which(_exe(name)) or shutil.which(name)
    if p:
        return p
    local = bin_dir / _exe(name)
    if local.exists():
        return str(local)
    return None
