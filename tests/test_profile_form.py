"""
tests/test_profile_form.py — Le couple audio sans perte ne peut plus se contredire.

`preserve_hd_audio` et `audio_hd_codec` étaient deux réglages indépendants dont
l'un l'emportait en silence : un profil pouvait porter « copier sans perte » et
« transcoder en E-AC3 » à la fois, et rien à l'écran ne disait lequel gagnait.
L'écran n'expose plus qu'un choix, et ces tests verrouillent la traduction dans
les deux sens.
"""
from __future__ import annotations

import pytest

from tui.widgets.profile_form import _hd_audio_cles, _hd_audio_depuis_cles


# ─── Du choix vers les clés ───────────────────────────────────────────────────

@pytest.mark.parametrize("branche, preserve, codec", [
    ("copy",    True,  "none"),
    ("eac3",    False, "eac3"),
    ("ac3",     False, "ac3"),
    ("forfait", False, "none"),
])
def test_ecriture_du_couple(branche, preserve, codec):
    d = _hd_audio_cles(branche)
    assert d["preserve_hd_audio"] is preserve
    assert d["audio_hd_codec"] == codec


def test_branche_inconnue_retombe_sur_le_forfait():
    """Une valeur inattendue ne doit pas activer la copie sans perte."""
    d = _hd_audio_cles("n_importe_quoi")
    assert d["preserve_hd_audio"] is False
    assert d["audio_hd_codec"] == "none"


# ─── Des clés vers le choix ───────────────────────────────────────────────────

@pytest.mark.parametrize("preserve, codec, attendu", [
    (True,  "none", "copy"),
    (False, "eac3", "eac3"),
    (False, "ac3",  "ac3"),
    (False, "none", "forfait"),
])
def test_lecture_du_couple(preserve, codec, attendu):
    assert _hd_audio_depuis_cles(preserve, codec) == attendu


@pytest.mark.parametrize("codec", ["eac3", "ac3"])
def test_couple_contradictoire_affiche_ce_qui_se_passe(codec):
    """La copie l'emporte dans le moteur : c'est elle que l'écran doit montrer,
    pas l'intention qu'exprimait le codec."""
    assert _hd_audio_depuis_cles(True, codec) == "copy"


def test_aller_retour_stable():
    for branche in ("copy", "eac3", "ac3", "forfait"):
        d = _hd_audio_cles(branche)
        relu = _hd_audio_depuis_cles(d["preserve_hd_audio"], d["audio_hd_codec"])
        assert relu == branche


# ─── UX-03 : une valeur hors liste ne vide plus le champ ─────────────────────

from textual.widgets import Select

from tui.widgets.profile_form import _BITRATE_4K, _avec_valeur, _est_vide


def test_la_sentinelle_vide_est_reconnue():
    assert _est_vide(getattr(Select, "NULL", Select.BLANK))
    assert not _est_vide(3500)


def test_une_valeur_hors_liste_s_ajoute_a_sa_place():
    opts = _avec_valeur(_BITRATE_4K, 3500)
    assert [v for _, v in opts] == [3000, 3500, 5000, 8000, 12000]
    assert ("3500k", 3500) in opts
    assert _avec_valeur(_BITRATE_4K, 5000) == _BITRATE_4K


def test_le_formulaire_garde_la_valeur_du_profil():
    """`serie_basic` : 3500k en 4K, absent de la liste."""
    import asyncio

    from textual.app import App
    from textual.widgets import Static

    from tui.widgets.profile_form import ProfileForm

    class _App(App):
        def compose(self):
            yield ProfileForm()

    async def _run():
        app = _App()
        async with app.run_test(size=(160, 50)) as pilot:
            form = app.query_one(ProfileForm)
            form.load("serie_basic", {"bitrate_4k_kbps": 3500,
                                      "bitrate_1080p_kbps": 1800})
            await pilot.pause(0.2)
            cons = str(app.query_one("#cons-seuils", Static).render())
            return form.dump(), cons

    data, cons = asyncio.run(_run())
    assert data["bitrate_4k_kbps"] == 3500
    assert data["bitrate_1080p_kbps"] == 1800
    assert "NULL" not in cons and "3500k en 4K" in cons


def test_les_libelles_du_formulaire_ont_une_casse():
    """
    UX-23 : « id », « preset », « traitement » en minuscules sous des titres
    en capitales, sauf « Identifiant » ; « Edition » sans accent. Titres en
    capitales, libellés en casse de phrase.
    """
    import ast
    from pathlib import Path
    arbre = ast.parse(Path("tui/widgets/profile_form.py").read_text(encoding="utf-8"))
    for n in ast.walk(arbre):
        if not (isinstance(n, ast.Call) and getattr(n.func, "id", "") in ("Label", "Static")
                and n.args and isinstance(n.args[0], ast.Constant)
                and isinstance(n.args[0].value, str) and n.args[0].value):
            continue
        texte = n.args[0].value
        classes = next((k.value.value for k in n.keywords if k.arg == "classes"), "")
        if classes == "section-hdr":
            titre = texte.split("(")[0]      # les marques gardent leur casse
            assert titre == titre.upper(), texte
        elif classes == "form-lbl":
            assert texte[0] == texte[0].upper(), texte
    assert "Edition" not in Path("tui/screens/config.py").read_text(encoding="utf-8")
