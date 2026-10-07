"""
tests/test_console_anglais.py — Ce qui s'affiche avant la langue est en anglais (IE-91).

Les lanceurs (`launch.bat`, `bootstrap.ps1`, `launcher/`), `updater.py` et les
premiers messages de `main.py` tournent avant la lecture de `config.toml` :
ils ne peuvent pas suivre `[app] language` et sont écrits en anglais seul.
Les commentaires restent en français, comme dans tout le code : on ne vérifie
que les lignes qui affichent.

Les `.bat` n'affichent que de l'ASCII : sans `chcp 65001`, cmd lit le fichier
dans la page de code de la console, et un « é » ou un « — » en UTF-8 s'y
affichait en caractères parasites.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import updater

ROOT = Path(__file__).resolve().parent.parent
_ACCENTS = re.compile(r"[àâçéèêëîïôûùüÿœæÀÂÇÉÈÊËÎÏÔÛÙÜŸŒÆ«»]")


def _lignes(chemin: Path, affiche: re.Pattern) -> list[str]:
    texte = chemin.read_text(encoding="utf-8-sig")
    return [f"{chemin.name}:{n}: {l.strip()}"
            for n, l in enumerate(texte.splitlines(), 1) if affiche.search(l)]


@pytest.mark.parametrize("nom", ["launch.bat", "launcher/build.bat"])
def test_les_bat_affichent_de_l_ascii_anglais(nom):
    lignes = _lignes(ROOT / nom, re.compile(r"^\s*(echo|choice|title)\b", re.I))
    assert lignes, f"aucune ligne affichée trouvée dans {nom}"
    fautives = [l for l in lignes if not l.isascii()]
    assert not fautives, "\n".join(fautives)


@pytest.mark.parametrize("nom, affiche", [
    ("bootstrap.ps1",                  r"\b(Dire|Sortir|Write-Host)\b"),
    ("launcher/IrisEncodeLauncher.cs", r'"'),
    ("updater.py",                     r"\b(print|ErreurMaj|entree)\("),
    ("main.py",                        r'\b(print|help=|description=)|^\s*f?"(?!"")'),
])
def test_aucun_texte_affiche_en_francais(nom, affiche):
    lignes = _lignes(ROOT / nom, re.compile(affiche))
    fautives = [l for l in lignes
                if _ACCENTS.search(l.split("#", 1)[0].split("//", 1)[0])]
    assert not fautives, "\n".join(fautives)


def test_bootstrap_garde_sa_bom():
    """PowerShell 5.1 lit un .ps1 sans BOM dans la page de code ANSI."""
    assert (ROOT / "bootstrap.ps1").read_bytes().startswith(b"\xef\xbb\xbf")


def test_l_invite_de_mise_a_jour_est_anglaise_et_accepte_le_francais():
    invites = []

    def entree(invite):
        invites.append(invite)
        return "o"

    assert updater.demander("0.8.9.0", "v0.8.9.1", entree=entree, interactif=lambda: True)
    assert "[Y/n]" in invites[0]
    for reponse in ("oui", "y", "yes", ""):
        assert updater.demander("0.8.9.0", "v0.8.9.1", entree=lambda _: reponse,
                                interactif=lambda: True)
