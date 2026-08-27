"""
tests/test_markup.py — Les afficheurs de noms n'interprètent pas le markup Rich.

`Static.update()` interprète par défaut ce qui ressemble à une balise entre
crochets. Or la convention de nommage du projet est faite de cette syntaxe :
`_[mux]`, `_[hevc]`, `_[av1]`, `_[hdr10]`, `_[extrait]`, `_[premux]`. Un nom de
fichier affiché tel quel y perd son suffixe, et un identifiant de profil écrit
`[serie_basic]` disparaît en entier.

Le piège est d'autant plus vicieux qu'il est irrégulier : `_[H264]` survit, les
autres non — Rich ne consomme que ce qui ressemble à un nom de style valide.

Le smoke TUI vérifie deux écrans en rendu réel. Ce test verrouille les autres,
en lisant la construction des widgets concernés.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent / "tui"

# Widgets qui affichent un nom de fichier, un chemin ou un identifiant.
IDS_SANS_MARKUP = [
    "status-bar",          # browser, dryrun, mux_run, sync, tracks
    "mux-out",
    "mux-state",
    "cmd-lines",           # la commande ffmpeg contient le chemin de sortie
    "ffmpeg-line",
    "scan-notice",
    "donor-path",
    "sync-hint",
    "config-header-bar",
    "confirm-title",
]


def _constructions() -> list[tuple[Path, int, str, str]]:
    """(fichier, ligne, id, source) de chaque `Static(... id="…" ...)`."""
    trouvees = []
    motif = re.compile(r'Static\([^)]*id="([^"]+)"[^)]*\)', re.S)
    for f in sorted(RACINE.rglob("*.py")):
        src = f.read_text(encoding="utf-8")
        for m in motif.finditer(src):
            ligne = src[: m.start()].count("\n") + 1
            trouvees.append((f, ligne, m.group(1), m.group(0)))
    return trouvees


@pytest.mark.parametrize("widget_id", IDS_SANS_MARKUP)
def test_afficheur_de_noms_sans_markup(widget_id):
    """Chaque construction de ce widget doit désactiver le markup."""
    concernees = [c for c in _constructions() if c[2] == widget_id]
    assert concernees, f"aucun Static id={widget_id!r} trouvé — id renommé ?"
    for fichier, ligne, _, source in concernees:
        assert "markup=False" in source, (
            f"{fichier.name}:{ligne} — Static id={widget_id!r} interprète le "
            f"markup Rich ; un nom porteur de « _[hevc] » y perdrait son suffixe"
        )


def test_les_modales_echappent_les_noms_qu_elles_mettent_en_gras():
    """Les modales de confirmation, elles, utilisent du markup volontaire :
    le corps garde `markup=True`, mais tout nom interpolé passe par `escape()`."""
    for nom in ("delete_confirm.py", "recursive_confirm.py"):
        src = (RACINE / "screens" / nom).read_text(encoding="utf-8")
        for m in re.finditer(r"\[bold[^\]]*\]\{([^}]+)\}", src):
            assert "escape(" in m.group(1), (
                f"{nom} — {m.group(1)} mis en gras sans échappement"
            )
