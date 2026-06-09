#!/usr/bin/env python3
"""
main.py — Point d'entrée IRIS ENCODE.

Peut être lancé directement (`python main.py`) ou via launch.bat.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _check_python_version() -> None:
    if sys.version_info < (3, 11):
        print(
            f"✗ Python 3.11+ requis "
            f"(version détectée : {sys.version_info.major}.{sys.version_info.minor})\n"
            "  Téléchargez Python depuis https://python.org"
        )
        sys.exit(1)


def _ensure_deps() -> None:
    """Vérifie que les dépendances Python sont installées."""
    missing = []
    for pkg in ("textual", "rich", "tomli_w", "requests"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(
            f"✗ Dépendances manquantes : {', '.join(missing)}\n"
            "  Installez avec : pip install -r requirements.txt"
        )
        sys.exit(1)


def main() -> None:
    _check_python_version()
    _ensure_deps()

    parser = argparse.ArgumentParser(
        description="IRIS ENCODE — Réencodage vidéo HEVC/H264 avec TUI",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Répertoire de travail (défaut : répertoire courant)",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Vérifier les outils et quitter",
    )
    args = parser.parse_args()

    start_path = Path(args.path).resolve() if args.path else Path.cwd()
    if not start_path.exists():
        print(f"✗ Chemin introuvable : {start_path}")
        sys.exit(1)

    # ── Preflight ─────────────────────────────────────────────────────────────
    from core import config as cfg_mod
    from core.preflight import run_preflight
    from version import __version__

    inner = 43
    print()
    print("╔" + "═" * inner + "╗")
    print(f"║  {f'IRIS ENCODE  v{__version__}':<{inner - 2}}║")
    print("╚" + "═" * inner + "╝")
    print()
    print("Vérification des outils :")

    cfg = cfg_mod.load()
    ok  = run_preflight(cfg)

    if not ok:
        print("\n✗ Outils manquants. Arrêt.")
        sys.exit(1)

    if args.preflight_only:
        print("\n✓ Preflight OK.")
        sys.exit(0)

    # ── Lancement TUI ─────────────────────────────────────────────────────────
    from tui.app import IrisEncodeApp

    app = IrisEncodeApp(start_path=start_path)
    app.run()


if __name__ == "__main__":
    main()
