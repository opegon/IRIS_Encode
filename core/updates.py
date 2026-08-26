"""
core/updates.py — Fraîcheur des outils externes.

Les sources de téléchargement étaient figées dans data/ffmpeg_releases.toml :
un outil installé une fois n'était jamais revu, et les URL pinnées vieillissaient
en silence. Ce module interroge l'amont, met le résultat en cache, et compare à
ce qui est réellement installé.

Le cache est ce à quoi servait `ffmpeg_releases_cache.toml`, jusqu'ici lu mais
jamais écrit.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

# Une interrogation par jour suffit : ces outils sortent au mieux
# mensuellement, et l'API GitHub n'autorise que 60 appels par heure sans jeton.
CACHE_TTL_SECONDS = 24 * 3600
HTTP_TIMEOUT      = 8

_UA = {"User-Agent": "iris-encode"}


@dataclass
class Release:
    version: str
    url:     str


@dataclass
class Update:
    tool:      str
    installed: str
    latest:    str
    url:       str

    def label(self) -> str:
        actuel = self.installed or "inconnue"
        return f"{self.tool} : {actuel} → {self.latest}"


# ─── Comparaison de versions ──────────────────────────────────────────────────

def parse_version(text: str) -> Optional[tuple[str, tuple[int, ...]]]:
    """
    Version en (forme, tuple comparable), ou None si le texte n'en contient pas.

    La forme distingue un numéro pointé d'un horodatage. Certains outils ne
    rapportent qu'un hash de commit (dovi_tool en build git) : impossible de
    comparer, on s'abstient plutôt que de deviner.
    """
    text = text or ""
    m = re.search(r"\b(\d{8})\b", text)
    if m:
        return ("date", (int(m.group(1)),))
    m = re.search(r"(\d+(?:\.\d+)+)", text)
    if m:
        return ("dotted", tuple(int(p) for p in m.group(1).split(".")))
    return None


def is_newer(latest: str, installed: str) -> bool:
    """
    Vrai seulement si les deux versions sont comparables et latest gagne.

    Comparer des formes différentes n'a pas de sens : mpv se déclare en
    0.41.0 quand shinchiro étiquette ses builds par date. Les confronter
    signalerait une mise à jour à chaque lancement, indéfiniment.
    """
    a, b = parse_version(latest), parse_version(installed)
    if a is None or b is None or a[0] != b[0]:
        return False
    return a[1] > b[1]


# ─── Interrogation de l'amont ─────────────────────────────────────────────────

def _get(url: str):
    import requests
    return requests.get(url, timeout=HTTP_TIMEOUT, headers=_UA)


def _github_asset(repo: str, pattern: str) -> Optional[Release]:
    """Dernière release d'un dépôt GitHub, et l'asset correspondant au motif."""
    r = _get(f"https://api.github.com/repos/{repo}/releases/latest")
    if not r.ok:
        return None
    data = r.json()
    rx   = re.compile(pattern)
    for asset in data.get("assets", []):
        if rx.fullmatch(asset["name"]):
            return Release(str(data["tag_name"]).lstrip("v"),
                           asset["browser_download_url"])
    return None


def _latest_ffmpeg() -> Optional[Release]:
    # L'URL de gyan.dev est roulante : elle pointe toujours la dernière release.
    r = _get("https://www.gyan.dev/ffmpeg/builds/release-version")
    if not r.ok:
        return None
    return Release(
        r.text.strip(),
        "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
    )


def _latest_mkvtoolnix() -> Optional[Release]:
    r = _get("https://mkvtoolnix.download/latest-release.xml")
    if not r.ok:
        return None
    m = re.search(r"<latest-source>.*?<version>([^<]+)</version>", r.text, re.S)
    if not m:
        return None
    v = m.group(1).strip()
    return Release(
        v,
        f"https://mkvtoolnix.download/windows/releases/{v}/"
        f"mkvtoolnix-64-bit-{v}.zip",
    )


def _latest_dovi_tool() -> Optional[Release]:
    return _github_asset("quietvoid/dovi_tool",
                         r"dovi_tool-[\d.]+-x86_64-pc-windows-msvc\.zip")


def _latest_mpv() -> Optional[Release]:
    # mpv-x86_64-<date>-git-<hash>.7z, à distinguer des variantes dev et v3
    return _github_asset("shinchiro/mpv-winbuild-cmake",
                         r"mpv-x86_64-\d{8}-git-[0-9a-f]+\.7z")


_SOURCES: dict[str, Callable[[], Optional[Release]]] = {
    "ffmpeg":     _latest_ffmpeg,
    "mkvmerge":   _latest_mkvtoolnix,
    "dovi_tool":  _latest_dovi_tool,
    "mpv":        _latest_mpv,
}


def fetch_latest() -> dict[str, Release]:
    """
    Interroge chaque source. Une source injoignable est simplement omise :
    un démarrage hors ligne ne doit rien casser.
    """
    out: dict[str, Release] = {}
    for tool, source in _SOURCES.items():
        try:
            rel = source()
        except Exception:
            rel = None
        if rel is not None and rel.version:
            out[tool] = rel
    return out


# ─── Cache ────────────────────────────────────────────────────────────────────

def load_cache(path: Path) -> Optional[dict[str, Release]]:
    """Contenu du cache s'il existe et n'a pas expiré, sinon None."""
    if not path.exists():
        return None
    try:
        import tomllib
        with path.open("rb") as f:
            data = tomllib.load(f)
    except Exception:
        return None
    if time.time() - float(data.get("checked_at", 0)) > CACHE_TTL_SECONDS:
        return None
    return {
        tool: Release(str(entry.get("version", "")), str(entry.get("url", "")))
        for tool, entry in data.get("tools", {}).items()
        if entry.get("version")
    }


def save_cache(path: Path, releases: dict[str, Release]) -> None:
    try:
        import tomli_w
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            tomli_w.dump({
                "checked_at": time.time(),
                "tools": {t: {"version": r.version, "url": r.url}
                          for t, r in releases.items()},
            }, f)
    except Exception:
        pass          # un cache non écrit coûte un appel réseau, rien de plus


# ─── Verdict ──────────────────────────────────────────────────────────────────

def pending(installed: dict[str, str],
            releases: dict[str, Release]) -> list[Update]:
    """Outils installés pour lesquels une version plus récente existe."""
    out: list[Update] = []
    for tool, version in installed.items():
        rel = releases.get(tool)
        if rel and is_newer(rel.version, version):
            out.append(Update(tool, version, rel.version, rel.url))
    return out
