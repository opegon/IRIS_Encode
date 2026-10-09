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

from core import i18n

# L'interface se teste en français, la langue de l'utilisateur : depuis que les
# textes sont en anglais dans le code (IE-87), un test qui vérifie un message
# français vérifie aussi que sa traduction n'a pas bougé.
i18n.init("fr")

@pytest.fixture(params=["en", "fr"])
def langue(request):
    """IE-94 : un test qui la demande tourne dans chaque langue livrée ; le
    français ci-dessus est rétabli après."""
    i18n.init(request.param)
    yield request.param
    i18n.init("fr")


# (module, nom de la variable) — l'état global que l'application pose.
_GLOBALES = [
    ("core.muxer",    "_mkvmerge_path"),
    ("core.scanner",  "_ffprobe_path"),
    ("core.encoder",  "_ffmpeg_path"),
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


@pytest.fixture(autouse=True)
def donneurs_factices(monkeypatch):
    """Un donneur fabriqué vide, ou seulement nommé, par un test ne se lit pas
    par ffprobe : sa
    piste audio est décrite comme un E-AC3 5.1, recopié par tout profil. Un
    vrai fichier reste lu (IE-125 : une greffe suit la règle audio du profil)."""
    from core import scanner
    from core.scanner import AudioTrack

    reelle = scanner.pistes_audio

    def pistes_audio(path):
        try:
            vide = path.stat().st_size == 0
        except OSError:
            vide = True
        if not vide:
            return reelle(path)
        return [AudioTrack(index=i, codec="eac3", channels=6, language="",
                           title="", bitrate=640_000) for i in range(8)]

    monkeypatch.setattr(scanner, "pistes_audio", pistes_audio)
