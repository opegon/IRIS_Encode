#!/usr/bin/env python3
"""
main.py — Point d'entrée IRIS ENCODE.

Peut être lancé directement (`python main.py`) ou via launch.bat.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Bibliothèque standard seulement : importable avant le contrôle des
# dépendances. Sans `init`, il rend l'anglais source.
from core import i18n
from core.i18n import _, pgettext


def force_utf8_output() -> None:
    """Force stdout/stderr en UTF-8.

    Sur Windows, Python n'utilise l'UTF-8 que face à une vraie console : dès que
    la sortie part dans un pipe, un fichier ou un terminal tiers (Git Bash), il
    retombe sur l'encodage local — cp1252 en français. Le cadre de la bannière
    et les coches ✓/✗ n'y existent pas, et le programme meurt sur un
    UnicodeEncodeError avant même d'avoir affiché quoi que ce soit.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _check_python_version() -> None:
    if sys.version_info < (3, 11):
        print(
            f"✗ Python 3.11+ required "
            f"(found: {sys.version_info.major}.{sys.version_info.minor})\n"
            "  Download Python from https://python.org"
        )
        sys.exit(1)


def _ensure_deps() -> None:
    """Vérifie que les dépendances Python sont installées."""
    missing = []
    # Doit couvrir requirements.txt : bs4 sert au scraping des métadonnées,
    # son absence ne se manifestait qu'au moment d'ouvrir une fiche film.
    for pkg in ("textual", "rich", "tomli_w", "requests", "bs4", "numpy"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(
            f"✗ Missing dependencies: {', '.join(missing)}\n"
            "  Install them with: pip install -r requirements.txt"
        )
        sys.exit(1)


def _environnement_python() -> str:
    """La version de l'interpréteur, et d'où il vient.

    `launch.bat` choisit entre trois candidats — le `.venv` local, le Python du
    PATH, celui que `bootstrap.ps1` installe. Le choix est silencieux, et rien
    à l'écran ne disait lequel avait gagné : une dépendance qui manque ou une
    version inattendue se diagnostiquent mal quand on ignore quel Python
    tourne.
    """
    v = sys.version_info
    racine = Path(__file__).resolve().parent
    exe    = Path(sys.executable).resolve()
    if exe.is_relative_to(racine / ".venv"):
        # TRANSLATORS: where the Python interpreter comes from, in the start banner.
        origine = pgettext("python origin", "local .venv")
    else:
        # TRANSLATORS: the Python installed on the computer, in the start banner.
        origine = pgettext("python origin", "system")
    return f"Python {v.major}.{v.minor}.{v.micro} · {origine}"


def banniere(lignes: list[str]) -> list[str]:
    """Le cadre de la bannière, à la largeur de sa plus longue ligne.

    Largeur comptée en cellules de terminal : une ligne traduite plus longue,
    ou en pleine chasse, ne crève plus le cadre (L-86). 43 au moins, la largeur
    d'origine.
    """
    from rich.cells import cell_len
    inner = max(43, max(cell_len(l) for l in lignes) + 4)
    corps = [f"║  {l}{' ' * (inner - 2 - cell_len(l))}║" for l in lignes]
    return ["╔" + "═" * inner + "╗", *corps, "╚" + "═" * inner + "╝"]


def main() -> None:
    force_utf8_output()    # avant tout print : la vérification ci-dessous en fait
    _check_python_version()
    _ensure_deps()

    parser = argparse.ArgumentParser(
        description="IRIS ENCODE — HEVC/H264 video re-encoding with a TUI",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Working directory (default: current directory)",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Check the tools and exit",
    )
    args = parser.parse_args()

    start_path = Path(args.path).resolve() if args.path else Path.cwd()
    if not start_path.exists():
        print(f"✗ Path not found: {start_path}")
        sys.exit(1)

    # ── Preflight ─────────────────────────────────────────────────────────────
    from core import config as cfg_mod
    from core.preflight import run_preflight
    from version import __version__

    cfg = cfg_mod.load()
    # La langue se charge ici, une fois, avant la bannière : tout ce qui suit —
    # bannière, preflight, interface — passe par le catalogue ; ce qui précède
    # (version de Python, dépendances, --help, chemin) reste en anglais seul,
    # comme les lanceurs (IE-91). `load()` n'affiche rien.
    i18n.init(cfg_mod.assurer_langue(cfg))    # premier lancement : celle de Windows

    print()
    for ligne in banniere([f"IRIS ENCODE  v{__version__}", _environnement_python()]):
        print(ligne)
    if cfg_mod.illisible():
        # Comme profiles.toml : la session tourne sur les défauts, le fichier
        # reste tel quel, réparable à la main (CR-43).
        print("⚠  " + _("config.toml unreadable ({error}). Session running on "
                        "the default settings — your file was not touched, and "
                        "will not be until it is fixed.").format(
                            error=cfg_mod.illisible()))
    print()
    print(_("Checking tools:"))
    ok  = run_preflight(cfg)

    if not ok:
        print("\n✗ " + _("Tools missing. Stopping."))
        sys.exit(1)

    if args.preflight_only:
        print("\n✓ " + _("Preflight OK."))
        sys.exit(0)

    # ── Lancement TUI ─────────────────────────────────────────────────────────
    from tui.app import IrisEncodeApp

    app = IrisEncodeApp(start_path=start_path)
    app.run()


if __name__ == "__main__":
    main()
