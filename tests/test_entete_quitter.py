"""
tests/test_entete_quitter.py — « F10 Quitter » passe du pied de page à
l'en-tête, à côté de « F11 Plein écran » (v0.9.3.2).

Le pied de page répétait F10 sur chaque écran, souvent seul sur sa ligne.
L'en-tête est visible de partout : la touche y est annoncée une fois.
"""
from __future__ import annotations

from tui.common import footer_line2
from tui.widgets.entete import AideEtHeure


def test_f10_annonce_dans_l_en_tete(monkeypatch):
    monkeypatch.delenv("WT_SESSION", raising=False)
    texte = AideEtHeure().render().plain
    assert texte.startswith("F10 "), texte
    assert texte.index("F10") < texte.index("H ")      # avant « H Aide »


def test_f10_avant_f11_sous_windows_terminal(monkeypatch):
    monkeypatch.setenv("WT_SESSION", "0f1e2d3c")
    texte = AideEtHeure().render().plain
    assert texte.index("F10") < texte.index("F11") < texte.index("H "), texte


def test_le_pied_de_page_n_annonce_plus_f10():
    for nav in (footer_line2(), footer_line2(back=True, accueil=True),
                footer_line2(extra=(("f1", "x"),))):
        assert "f10" not in {k for k, _ in nav}, nav
