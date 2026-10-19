"""
tests/test_entete_plein_ecran.py — « F11 Plein écran » dans l'en-tête.

F11 bascule le plein écran de Windows Terminal ; ailleurs la touche ne fait
rien, et l'en-tête ne l'annonce pas.
"""
from __future__ import annotations

from tui.widgets.entete import AideEtHeure


def test_f11_annonce_sous_windows_terminal(monkeypatch):
    monkeypatch.setenv("WT_SESSION", "0f1e2d3c")
    texte = AideEtHeure().render().plain
    assert texte.startswith("F11 ")
    assert texte.index("F11") < texte.index("H ")      # avant « H Aide »


def test_f11_absent_hors_windows_terminal(monkeypatch):
    monkeypatch.delenv("WT_SESSION", raising=False)
    assert "F11" not in AideEtHeure().render().plain
