"""core/texte.py — Accords des textes affichés. **Transitoire.**

Remplacé par `ngettext` (`core/i18n.py`), qui prend la phrase entière et la
règle de pluriel de chaque langue (L-37). `core/` ne l'emploie plus depuis
IE-87 ; il ne sert qu'à `tui/`, jusqu'à l'extraction de ses textes (IE-88).

« 1 fichiers », « 1/1 terminés », et « (s) » partout (UX-15). Un nombre
commande l'accord de ce qui le suit ; le choix se fait ici, une fois, et la
localisation n'aura qu'un endroit à reprendre.
"""
from __future__ import annotations


def accorde(n: int, singulier: str, pluriel: str | None = None) -> str:
    """La forme qui s'accorde avec `n`. Français : singulier jusqu'à 1.

    `pluriel` par défaut : un « s » à chaque mot — « piste greffée » →
    « pistes greffées ». À donner quand ce n'est pas la règle (« piste audio »).
    """
    if abs(n) <= 1:
        return singulier
    return pluriel if pluriel is not None else " ".join(
        m + "s" for m in singulier.split(" "))


def pluriel(n: int, singulier: str, pluriel_: str | None = None) -> str:
    """« 3 pistes greffées » — le nombre et sa forme accordée."""
    return f"{n} {accorde(n, singulier, pluriel_)}"
