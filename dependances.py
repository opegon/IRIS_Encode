"""
dependances.py — Les dépendances installées sont-elles dans les bornes de
requirements.txt ?

Appelé par launch.bat et bootstrap.ps1 avec l'interpréteur à éprouver ; rend 0
si chaque paquet est présent et dans ses bornes, 1 sinon (la cause sur stderr).
Bibliothèque standard seule, et Python 3.11 : il tourne aussi sur un Python du
système, avant toute installation.

Un simple `import` ne suffisait pas : un Python du système avec un Textual 1.x
passait le test, puis l'application levait au premier écran qui emploie une
API récente (CR-109). Les bornes hautes sont celles de requirements.txt : une
version majeure que l'application n'a jamais vue n'est pas installée (CR-110).
"""
from __future__ import annotations

import re
import sys
from importlib import metadata
from pathlib import Path

REQUIREMENTS = Path(__file__).resolve().parent / "requirements.txt"

_BORNE = re.compile(r"(>=|<)\s*([0-9][0-9.]*)")


def _version(texte: str) -> tuple[int, ...]:
    """`8.2.8` → (8, 2, 8) ; un suffixe (`rc1`, `.post1`) est ignoré."""
    return tuple(int(p) for p in re.findall(r"\d+", re.match(r"[\d.]*", texte).group()))


def bornes(fichier: Path = REQUIREMENTS) -> dict[str, list[tuple[str, tuple[int, ...]]]]:
    """Paquet → bornes (`>=` ou `<`, version), ligne par ligne du fichier."""
    out: dict[str, list[tuple[str, tuple[int, ...]]]] = {}
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        ligne = ligne.split("#")[0].strip()
        if not ligne:
            continue
        nom = re.match(r"[A-Za-z0-9_.-]+", ligne).group()
        out[nom] = [(op, _version(v)) for op, v in _BORNE.findall(ligne)]
    return out


def ecarts(fichier: Path = REQUIREMENTS) -> list[str]:
    """Les paquets absents ou hors bornes, en clair ; vide si tout va."""
    out = []
    for nom, regles in bornes(fichier).items():
        try:
            installee = metadata.version(nom)
        except metadata.PackageNotFoundError:
            out.append(f"{nom}: not installed")
            continue
        v = _version(installee)
        for op, borne in regles:
            if (op == ">=" and v < borne) or (op == "<" and v >= borne):
                out.append(f"{nom} {installee}: outside {op}{'.'.join(map(str, borne))}")
    return out


if __name__ == "__main__":
    manque = ecarts()
    for ligne in manque:
        print(ligne, file=sys.stderr)
    sys.exit(1 if manque else 0)
