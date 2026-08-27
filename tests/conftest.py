"""
tests/conftest.py — Aucun test ne laisse de trace dans les modules.

Les chemins d'outils et le drapeau de disponibilité vivent en variables de
module, posés une fois au démarrage par `IrisEncodeApp.__init__`. Un test qui
construit l'application les modifie donc **pour tous les tests suivants** :
`test_muxer` attendait `"mkvmerge"` et recevait le chemin absolu du binaire,
selon l'ordre d'exécution. Le symptôme se déplaçait avec l'ordre, ce qui est la
pire forme d'échec.

Cette sauvegarde-restauration rend l'isolation automatique : un test peut
construire l'application sans y penser.
"""
from __future__ import annotations

import pytest

# (module, nom de la variable) — l'état global que l'application pose.
_GLOBALES = [
    ("core.muxer",    "_mkvmerge_path"),
    ("core.scanner",  "_dovi_path"),
    ("core.scanner",  "_ffmpeg_path"),
    ("core.sync",     "_ffmpeg_path"),
    ("core.preview",  "_mpv_path"),
    ("core.decision", "_STRIP_DV_AVAILABLE"),
]


@pytest.fixture(autouse=True)
def globales_isolees():
    """Restaure les variables de module après chaque test."""
    import importlib

    avant = []
    for nom_module, nom_var in _GLOBALES:
        module = importlib.import_module(nom_module)
        avant.append((module, nom_var, getattr(module, nom_var)))

    yield

    for module, nom_var, valeur in avant:
        setattr(module, nom_var, valeur)
