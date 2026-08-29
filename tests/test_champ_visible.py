"""
tests/test_champ_visible.py — Une capacité qui ne se signale pas n'existe pas.

IE-36. L'utilisateur a cherché comment recaler une piste audio à la main et a
conclu que ça n'existait pas. Ça existe : le champ `Décalage` de l'écran de
recalage s'édite pour n'importe quelle piste, audio comprise.

Ce qui manquait n'était donc pas la fonction, mais sa trace à l'écran. Deux
surfaces auraient pu la porter, aucune ne le faisait :

- le **pied de page** dérive des `BINDINGS` (IE-30), et `←/→`, `+/-`,
  `Shift+↑/↓`, `Ctrl+↑/↓` y sont tous déclarés `show=False` faute de place :
  les touches qui modifient sont précisément les seules que le pied ne montre
  pas ;
- le **bandeau** les portait, mais dans le même emplacement que ses messages.
  Un avertissement de langue les chassait à l'arrivée sur l'écran, un compte
  rendu de mesure les chassait juste après une mesure. Il ne restait que
  l'état où toutes les pistes ont leur langue et où rien n'a été mesuré,
  c'est-à-dire celui où il n'y a rien à régler.

Les prises de vue le montraient : ni `12-sync` ni `12b-sync-mesure` ne
comportait une seule touche d'édition.

Le bandeau porte désormais deux choses séparées — la ligne du champ actif, qui
ne s'efface jamais, puis le message. Ces tests verrouillent le « jamais ».
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from textual.widgets import DataTable, Static

from core.decision import decide
from core.muxer import ExternalTrack, TrackKind
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo
from tui.app import IrisEncodeApp
from tui.screens.sync import SyncScreen, ligne_champ

DOSSIER = Path(__file__).resolve().parent.parent


def _decision(tmp_path: Path, langue: str):
    p = tmp_path / "film.mkv"
    p.write_bytes(b"")
    info = VideoInfo(
        path=p, width=1920, height=1080, bitrate=8_000_000, codec="h264",
        duration=3600.0, frame_count=0, dv_profile=None,
        audio_tracks=[AudioTrack(index=0, codec="eac3", channels=6,
                                 language="eng", title="", bitrate=640_000)],
        subtitle_tracks=[])
    profil = Profile(id="test", data={
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps": 8000, "audio_languages": ["fre", "eng"],
        "audio_copy_compatible": True, "preserve_hd_audio": False})
    dec = decide(info, profil)
    dec.external_tracks.append(ExternalTrack(
        source_path=tmp_path / "vf.mkv", source_tid=1, kind=TrackKind.AUDIO,
        codec="ac3", language=langue, track_name="VF"))
    return dec


def _bandeau(ecran) -> str:
    return str(ecran.query_one("#sync-hint", Static).render())


async def _releve(tmp_path: Path, langue: str) -> dict[str, str]:
    """Monte l'écran et relève le bandeau dans les trois états qui comptent."""
    # Construire l'application pose les chemins d'outils en variables de
    # module. Cette fixture étant à portée « module », elle s'exécute avant la
    # sauvegarde automatique du conftest : on restaure donc nous-mêmes, comme
    # `test_footer_focus`. Sans ça, `test_muxer` échoue — ou non, selon
    # l'ordre d'exécution.
    import importlib

    from tests.conftest import _GLOBALES

    avant = [(importlib.import_module(m), v,
              getattr(importlib.import_module(m), v)) for m, v in _GLOBALES]

    app = IrisEncodeApp(DOSSIER)
    vues: dict[str, str] = {}
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause(0.3)
        app.push_screen(SyncScreen(_decision(tmp_path, langue)))
        await pilot.pause(0.5)
        ecran = app.screen
        ecran.query_one(DataTable).focus()
        await pilot.pause(0.2)

        vues["arrivee"] = _bandeau(ecran)

        # Un compte rendu de mesure, tel que `_apply_measure` le pose.
        ecran._set_hint("✓ -2490 ms (confiance excellente)\n"
                        "confiance excellente (0.88 pour 0.34 requis)")
        await pilot.pause(0.2)
        vues["apres_mesure"] = _bandeau(ecran)

        # Et le champ suivant, message toujours affiché.
        await pilot.press("right")
        await pilot.pause(0.2)
        vues["champ_suivant"] = _bandeau(ecran)

    for module, nom, valeur in avant:
        setattr(module, nom, valeur)
    return vues


# Portée « module » : monter une application Textual coûte une seconde, et les
# trois relevés d'un même scénario se prennent en une passe.
@pytest.fixture(scope="module")
def vues_avec_langue(tmp_path_factory):
    return asyncio.run(_releve(tmp_path_factory.mktemp("ie36_fre"), langue="fre"))


@pytest.fixture(scope="module")
def vues_sans_langue(tmp_path_factory):
    return asyncio.run(_releve(tmp_path_factory.mktemp("ie36_sans"), langue=""))


# ─── La ligne du champ ne s'efface jamais ────────────────────────────────────

def test_les_touches_d_edition_sont_la_des_l_arrivee(vues_avec_langue):
    assert ligne_champ("delay") in vues_avec_langue["arrivee"]


def test_un_compte_rendu_de_mesure_ne_les_chasse_pas(vues_avec_langue):
    """Le cas qui a soulevé IE-36 : on vient de mesurer, on veut ajuster."""
    bandeau = vues_avec_langue["apres_mesure"]
    assert ligne_champ("delay") in bandeau
    assert "-2490 ms" in bandeau, "le message doit rester lui aussi"


def test_un_avertissement_de_langue_ne_les_chasse_pas(vues_sans_langue):
    """L'autre voleur d'emplacement : l'écran s'ouvre dessus sur ce cas."""
    bandeau = vues_sans_langue["arrivee"]
    assert "Langue manquante" in bandeau
    assert ligne_champ("lang") in bandeau


def test_la_ligne_suit_le_champ_actif(vues_avec_langue):
    """Elle décrit le champ sous le curseur, pas l'écran en général."""
    suivant = vues_avec_langue["champ_suivant"]
    assert ligne_champ("stretch") in suivant
    assert ligne_champ("delay") not in suivant
    assert "-2490 ms" in suivant, "le message survit à la navigation"


# ─── Ce que chaque champ annonce est vrai ────────────────────────────────────

def test_le_decalage_annonce_ses_trois_pas():
    """Les trois pas existent sur ce champ, et sur lui seul."""
    ligne = ligne_champ("delay")
    assert "±10 ms" in ligne and "±100 ms" in ligne and "±1 s" in ligne
    # La touche annoncée est celle sur laquelle on peut compter, pas ses alias
    assert "ctrl+↑/↓" in ligne.lower()


@pytest.mark.parametrize("champ", ["stretch", "lang", "name", "default", "forced"])
def test_les_autres_champs_n_annoncent_aucun_pas(champ):
    """`_change` y ignore le pas et fait défiler les valeurs : le dire en
    millisecondes enverrait l'utilisateur chercher un réglage inexistant."""
    ligne = ligne_champ(champ)
    assert "ms" not in ligne and "±" not in ligne, ligne


@pytest.mark.parametrize("champ", ["delay", "stretch", "lang", "name",
                                   "default", "forced"])
def test_chaque_champ_se_nomme_et_dit_comment_en_changer(champ):
    from tui.screens.sync import _FIELD_LABELS

    ligne = ligne_champ(champ)
    assert ligne.startswith(_FIELD_LABELS[champ] + " :"), ligne
    assert "Autre champ" in ligne
