"""
core/preflight.py — Vérification et auto-installation des outils.

Ordre de recherche : PATH système → dossier local ./bin/
Installation via téléchargement ZIP avec vérification SHA256.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import io
import platform
import shutil
import subprocess
import tempfile
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
OPTIONAL_TOOLS  = ("dovi_tool", "mkvmerge", "mpv")
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


def _ask(prompt: str) -> str:
    """
    Question oui/non tolérante à l'absence d'entrée.

    Sans terminal — tâche planifiée, sortie redirigée — input() lève EOFError
    et emportait tout le démarrage. Pas de réponse vaut refus.
    """
    try:
        return input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return "n"


def _get_version(path: str) -> str:
    """
    Tente -version (ffmpeg/ffprobe) puis --version (dovi_tool, mkvmerge, GNU).
    Retourne la version extraite ou une chaîne vide.
    """
    for flag in ("-version", "--version"):
        try:
            r = subprocess.run(
                [path, flag],
                stdin=subprocess.DEVNULL, capture_output=True, timeout=5,
                encoding="utf-8", errors="replace",
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


def _localiser(name: str, bin_dir: Path) -> Optional[Path]:
    """Chemin de l'outil : PATH système d'abord, puis ./bin/. None si absent."""
    exe = _exe(name)
    p = shutil.which(exe) or shutil.which(name)
    if p:
        return Path(p)
    local = bin_dir / exe
    return local if local.exists() else None


def check_tools(bin_dir: Path) -> list[ToolStatus]:
    """État des cinq outils : présence, chemin, version.

    Les versions sont relevées **en parallèle**. `_get_version` essaie deux
    drapeaux à 5 s de délai chacun, et mkvmerge comme dovi_tool échouent sur
    le premier : en série, un démarrage payait jusqu'à dix lancements de
    sous-processus l'un après l'autre — et `check_tools` repasse une seconde
    fois après une installation de ffmpeg. C'est la position que
    `platform.sonder_encodeurs` énonce déjà pour les encodeurs, appliquée ici.

    La localisation, elle, reste séquentielle : elle ne coûte qu'un parcours
    du PATH et un `exists()`.
    """
    chemins = {name: _localiser(name, bin_dir) for name in ALL_TOOLS}
    trouves = [name for name, chemin in chemins.items() if chemin is not None]

    versions: dict[str, str] = {}
    if trouves:
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=len(trouves)) as pool:
            versions = dict(zip(trouves, pool.map(
                lambda n: _get_version(str(chemins[n])), trouves)))

    return [ToolStatus(name=name, found=chemins[name] is not None,
                       path=chemins[name], version=versions.get(name, ""))
            for name in ALL_TOOLS]


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


def _download(url: str, expected_sha256: str = "") -> Optional[bytes]:
    """
    Télécharge, et vérifie l'empreinte quand la source en fournit une.

    Les URL découvertes dynamiquement n'ont pas d'empreinte connue : on ne
    vérifie que ce qui est épinglé dans les sources statiques.
    """
    try:
        import requests
        r = requests.get(url, stream=True, timeout=120)
        r.raise_for_status()
        data = r.content
    except Exception as e:
        print(f"  ✗ Téléchargement échoué : {e}")
        return None

    if expected_sha256:
        got = _sha256(data)
        if got != expected_sha256.lower():
            print("  ✗ Empreinte SHA256 incorrecte — téléchargement rejeté.")
            print(f"    attendu : {expected_sha256.lower()}")
            print(f"    obtenu  : {got}")
            return None
    return data


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


def poser(nom: str, data: bytes, bin_dir: Path) -> bool:
    """Range le contenu téléchargé, sous la forme que publie cet outil.

    Point de passage **unique** : l'installation initiale et la mise à jour
    doivent ranger un même téléchargement de la même façon. Elles ne le
    faisaient pas — `_installer_for` appelait `_install_from_zip` en direct et
    sautait donc le garde-fou d'IE-40, si bien qu'une release publiée en
    binaire nu échouait à chaque mise à jour pendant qu'une installation neuve
    de la même release réussissait.
    """
    if nom == "dovi_tool":
        cible = _exe("dovi_tool")
        # Certaines releases publient un ZIP, d'autres l'exécutable nu. On
        # demande au contenu ce qu'il est, plutôt que de le déduire de l'échec
        # d'une extraction.
        #
        # La version d'avant IE-40 tentait l'extraction sous
        # `except Exception: pass` et repliait sur l'écriture directe : une
        # erreur pendant l'extraction — disque plein, antivirus, archive
        # tronquée — faisait écrire **les octets du ZIP** dans `dovi_tool.exe`,
        # en annonçant « ✓ Installé ». Le défaut ne se serait vu qu'au premier
        # fichier Dolby Vision, très loin de sa cause.
        if zipfile.is_zipfile(io.BytesIO(data)):
            return _install_from_zip(data, bin_dir, {cible})
        bin_dir.mkdir(parents=True, exist_ok=True)
        dest = bin_dir / cible
        dest.write_bytes(data)
        if not _is_windows():
            dest.chmod(0o755)
        print(f"  ✓ Installé : {dest}")
        return True
    if nom == "mpv":
        return _install_from_7z(data, bin_dir, {_exe("mpv")})
    if nom == "ffmpeg":
        return _install_from_zip(data, bin_dir,
                                 {_exe("ffmpeg"), _exe("ffprobe")})
    return _install_from_zip(data, bin_dir, {_exe(nom)})


def install_ffmpeg(bin_dir: Path, fetch_url: str) -> bool:
    print(f"  Téléchargement depuis {fetch_url}")
    data = _download(fetch_url)
    if data is None:
        return False
    return poser("ffmpeg", data, bin_dir)


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
    return poser("dovi_tool", data, bin_dir)


def _install_from_7z(data: bytes, bin_dir: Path, targets: set[str]) -> bool:
    """
    Extrait les exécutables ciblés depuis une archive 7z.

    Passe par le tar de Windows, qui embarque libarchive et lit le 7z : cela
    évite une dépendance Python supplémentaire pour la seule archive du lot
    qui n'est pas publiée en ZIP.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    installed = 0
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        archive = tmp_dir / "download.7z"
        archive.write_bytes(data)
        extract_dir = tmp_dir / "x"
        extract_dir.mkdir()
        try:
            r = subprocess.run(
                ["tar", "-xf", str(archive), "-C", str(extract_dir)],
                stdin=subprocess.DEVNULL, capture_output=True, timeout=300,
            )
        except (OSError, subprocess.SubprocessError) as e:
            print(f"  ✗ Extraction impossible ({e}) — tar introuvable ?")
            return False
        if r.returncode != 0:
            print("  ✗ Archive 7z illisible par tar.")
            return False

        for found in extract_dir.rglob("*"):
            if found.is_file() and found.name in targets:
                target = bin_dir / found.name
                shutil.copy2(found, target)
                if not _is_windows():
                    target.chmod(0o755)
                print(f"  ✓ Installé : {target}")
                installed += 1
    return installed > 0


def install_mpv(bin_dir: Path, releases: dict) -> bool:
    """
    Télécharge le build portable mpv et en extrait l'exécutable.

    mpv.exe est autonome ; les DLL de l'archive ne servent qu'aux anciennes
    versions de Windows. Sous Linux, mpv passe par le gestionnaire de paquets.
    """
    if not _is_windows():
        print("  Sous Linux, installez mpv via votre gestionnaire de paquets.")
        return False
    info = releases.get("mpv", {}).get("windows", {})
    url  = info.get("url", "")
    if not url:
        print("  ✗ URL mpv introuvable dans les sources.")
        return False
    print(f"  Téléchargement depuis {url}")
    data = _download(url, info.get("sha256", ""))
    if data is None:
        return False
    return poser("mpv", data, bin_dir)


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
    data = _download(url, info.get("sha256", ""))
    if data is None:
        return False
    return poser("mkvmerge", data, bin_dir)


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
    missing_mpv      = next((s for s in statuses if s.name == "mpv"       and not s.found), None)

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
        if missing_mpv:
            print("  mpv absent (optionnel — sert à contrôler un recalage à l'œil).")
            _offer_mpv_install(bin_dir)
            print()
        check_for_updates(cfg, statuses, bin_dir)
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
        answer = _ask("  Télécharger et installer ffmpeg dans ./bin/ ? (o/N) : ")
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
    answer   = _ask(
        "  Télécharger et installer dovi_tool (Dolby Vision) dans ./bin/ ? (o/N) : ")
    if answer == "o":
        ok = install_dovi_tool(bin_dir, releases)
        if not ok:
            print("  ✗ Installation dovi_tool échouée — fonctionnalité Dolby Vision indisponible.")
    else:
        print("  dovi_tool ignoré — les fichiers Dolby Vision ne seront pas traités de façon optimale.")


def _offer_mkvmerge_install(bin_dir: Path) -> None:
    """Propose l'installation de mkvmerge si absent (optionnel)."""
    releases = _load_releases()
    answer   = _ask(
        "  Télécharger et installer mkvmerge (pistes externes) dans ./bin/ ? (o/N) : ")
    if answer == "o":
        ok = install_mkvtoolnix(bin_dir, releases)
        if not ok:
            print("  ✗ Installation mkvmerge échouée — ajout de pistes externes indisponible.")
    else:
        print("  mkvmerge ignoré — l'ajout de pistes audio/sous-titres externes sera indisponible.")


def _offer_mpv_install(bin_dir: Path) -> None:
    """Propose l'installation de mpv si absent (optionnel)."""
    releases = _load_releases()
    answer   = _ask(
        "  Télécharger et installer mpv (contrôle du recalage) dans ./bin/ ? (o/N) : ")
    if answer == "o":
        ok = install_mpv(bin_dir, releases)
        if not ok:
            print("  ✗ Installation mpv échouée — le recalage restera réglable à l'aveugle.")
    else:
        print("  mpv ignoré — vous ne pourrez pas contrôler un recalage à l'œil.")


OUTILS_INSTALLABLES = frozenset({"ffmpeg", "mkvmerge", "dovi_tool", "mpv"})


def _installer_for(name: str):
    """Fonction de mise à jour associée à un outil, ou None.

    Elle télécharge puis passe par `poser`, exactement comme l'installation
    initiale. Les lambdas d'avant appelaient `_install_from_zip` en direct :
    dovi_tool y perdait son garde-fou `is_zipfile`, et un `_download` échoué
    devenait `b""` — remis à un extracteur qui n'avait plus qu'à échouer sur
    une archive vide, en nommant la mauvaise cause.

    Aucune empreinte à vérifier ici : `Update` n'en porte pas, et pour cause —
    l'URL vient d'une découverte dynamique, pas d'une source épinglée. C'est
    la limite que `_download` documente déjà.
    """
    if name not in OUTILS_INSTALLABLES:
        return None

    def _installer(bin_dir: Path, url: str) -> bool:
        print(f"  Téléchargement depuis {url}")
        data = _download(url)
        if data is None:
            return False
        return poser(name, data, bin_dir)

    return _installer


def check_for_updates(cfg: dict, statuses: list[ToolStatus],
                      bin_dir: Path) -> None:
    """
    Signale les outils dépassés et propose de les remettre à jour.

    Interrogé au plus une fois par jour : ces outils sortent au mieux
    mensuellement, et un démarrage ne doit pas attendre le réseau. Une source
    injoignable est ignorée — hors ligne, le lancement se poursuit.
    """
    # `[updates]`, pas `[ffmpeg]` : c'est là que `config._DEFAULTS` la pose et
    # que `config.toml` l'écrit. Lue au mauvais endroit, elle retombait
    # toujours sur le défaut `True` — le réglage était mort, et l'utilisateur
    # qui coupait la vérification pour éviter l'aller-retour réseau au
    # lancement continuait de le payer.
    if not cfg.get("updates", {}).get("check_on_startup", True):
        return

    from . import updates

    releases = updates.load_cache(CACHE_FILE)
    if releases is None:
        print("  Vérification des mises à jour…")
        releases = updates.fetch_latest()
        if releases:
            updates.save_cache(CACHE_FILE, releases)

    # Ne proposer que ce qu'on gère réellement : un outil trouvé dans le PATH
    # y reste prioritaire sur ./bin/, le mettre à jour ici ne changerait rien.
    installed = {
        s.name: s.version
        for s in statuses
        if s.found and s.path is not None and s.path.parent == bin_dir
    }
    # ffprobe suit ffmpeg : même archive, inutile de le traiter à part
    installed.pop("ffprobe", None)

    en_retard = updates.pending(installed, releases or {})
    if not en_retard:
        return

    print()
    for u in en_retard:
        print(f"  ↑ {u.label()}")
    answer = _ask("  Mettre à jour ces outils ? (o/N) : ")
    if answer != "o":
        print("  Mise à jour ignorée — les versions installées restent en place.")
        return

    for u in en_retard:
        installer = _installer_for(u.tool)
        if installer is None:
            continue
        print(f"  {u.tool} : téléchargement de {u.latest}…")
        try:
            ok = installer(bin_dir, u.url)
        except Exception as e:
            ok = False
            print(f"  ✗ {e}")
        if not ok:
            print(f"  ✗ Mise à jour de {u.tool} échouée — version précédente conservée.")


def get_tool_path(name: str, bin_dir: Path) -> Optional[str]:
    """Retourne le chemin vers l'outil (PATH ou ./bin/), ou None."""
    p = shutil.which(_exe(name)) or shutil.which(name)
    if p:
        return p
    local = bin_dir / _exe(name)
    if local.exists():
        return str(local)
    return None
