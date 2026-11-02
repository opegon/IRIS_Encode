"""
tests/test_outils_couverts.py — Un outil que le ffmpeg principal remplace n'est
pas « manquant ».

Avec un ffmpeg principal qui lit les DVD et a `libplacebo`, IRIS ne propose ni
l'outil DVD ni l'outil Dolby Vision — à raison — mais la liste du lancement les
marquait « [✗] … (optionnel) » à chaque démarrage, comme s'il fallait les
installer (constaté par l'utilisateur le 2026-11-02).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core import dovi, dvd, preflight
from core.i18n import _


def _lancer(monkeypatch, capsys, lit_les_dvd: bool, libplacebo: bool) -> str:
    statuts = [preflight.ToolStatus("ffmpeg", True, Path("ff"), "8.1.3"),
               preflight.ToolStatus("ffprobe", True, Path("fp"), "8.1.3"),
               preflight.ToolStatus("dovi_tool", True, Path("d"), "2.3.4"),
               preflight.ToolStatus("mkvmerge", True, Path("m"), "103.0"),
               preflight.ToolStatus("mpv", True, Path("v"), "0.41.0"),
               preflight.ToolStatus("ffmpeg_dvd", False),
               preflight.ToolStatus("ffmpeg_dv", False)]
    monkeypatch.setattr(preflight, "check_tools", lambda b: statuts)
    monkeypatch.setattr(dvd, "lit_les_dvd", lambda f: lit_les_dvd)
    monkeypatch.setattr(dovi, "a_libplacebo", lambda f: libplacebo)
    monkeypatch.setattr(preflight, "_oui_non", lambda q: False)   # rien n'est installé
    monkeypatch.setattr(preflight, "check_for_updates", lambda *a: None)
    assert preflight.run_preflight({})
    return capsys.readouterr().out


def _ligne(sortie: str, nom: str) -> str:
    return next(l for l in sortie.splitlines() if f"] {nom} " in l)


def test_le_ffmpeg_principal_couvre_les_deux_outils(monkeypatch, capsys):
    sortie = _lancer(monkeypatch, capsys, lit_les_dvd=True, libplacebo=True)
    for nom in ("ffmpeg_dvd", "ffmpeg_dv"):
        ligne = _ligne(sortie, nom)
        assert ligne.startswith("  [✓]"), ligne
        assert _("provided by the main ffmpeg") in ligne
        assert _("optional") not in ligne


def test_un_outil_vraiment_absent_reste_optionnel(monkeypatch, capsys):
    sortie = _lancer(monkeypatch, capsys, lit_les_dvd=False, libplacebo=True)
    dvd_ligne = _ligne(sortie, "ffmpeg_dvd")
    assert dvd_ligne.startswith("  [✗]") and _("optional") in dvd_ligne
    assert _ligne(sortie, "ffmpeg_dv").startswith("  [✓]")
