"""
tests/test_ecran_pistes_suivi.py — L'écran des pistes et l'assistant suivent
ce qu'on y fait (IE-192 : CR-132, CR-133, CR-135, CR-136, CR-138).

Les bandeaux et la ligne vidéo se vérifient sur la capture de l'écran, pas
sur le widget : un texte présent dans `render()` peut ne jamais être dessiné
(CR-135).
"""
from __future__ import annotations

import asyncio
import html
import re
from dataclasses import replace as dc_replace
from pathlib import Path
from types import SimpleNamespace

from textual.widgets import DataTable

from core.decision import VideoAction, decide, force_skip_to_encode
from core.i18n import _
from core.profiles import Profile
from core.scanner import AudioTrack, SubtitleTrack, VideoInfo
from tui.app import IrisEncodeApp
from tui.common import libelle_ecartee
from tui.screens.tracks import TracksScreen
from tui.screens.wizard import Etape, WizardScreen, _L_AUDIO

_PROFIL = {"bitrate_480p_kbps": 1500, "bitrate_720p_kbps": 2500,
           "bitrate_1080p_kbps": 5000, "audio_languages": ["fre", "eng"]}


def _info(tmp_path: Path, codec="h264", bitrate=20_000_000) -> VideoInfo:
    p = tmp_path / "Film.mkv"
    p.write_bytes(b"")
    return VideoInfo(
        path=p, width=1920, height=1080, bitrate=bitrate, codec=codec,
        duration=6000.0, frame_count=0, dv_profile=None,
        audio_tracks=[AudioTrack(index=0, codec="ac3", channels=6, language="fre",
                                 title="", bitrate=448_000),
                      AudioTrack(index=1, codec="ac3", channels=6, language="eng",
                                 title="", bitrate=448_000)],
        # Allemand : ni l'OCR (français, anglais) ni un doublon texte n'y touchent.
        subtitle_tracks=[SubtitleTrack(index=0, codec="hdmv_pgs_subtitle",
                                       language="ger"),
                         SubtitleTrack(index=1, codec="subrip", language="eng")])


def _texte_ecran(app) -> str:
    """Ce que l'écran dessine vraiment, balises SVG retirées."""
    texte = html.unescape(re.sub(r"<[^>]+>", "", app.export_screenshot()))
    return texte.replace("\xa0", " ")


def _cellule(ecran, cle: str, colonne: str = "dec") -> str:
    table = ecran.query_one("#tracks-table", DataTable)
    return str(table.get_cell(cle, colonne))


def _sur_ligne(ecran, cle: str) -> None:
    table = ecran.query_one("#tracks-table", DataTable)
    table.move_cursor(row=table.get_row_index(cle))


# ─── CR-136 (a) : la ligne suit la case ──────────────────────────────────────

def test_decocher_une_piste_reecrit_sa_ligne_et_le_conteneur(tmp_path):
    dec = decide(_info(tmp_path), Profile(id="t", data=_PROFIL))
    assert dec.video.action == VideoAction.ENCODE_HEVC

    async def _scenario():
        app = IrisEncodeApp(start_path=tmp_path)
        async with app.run_test(size=(200, 50)) as pilot:
            await pilot.pause(0.3)
            app.push_screen(TracksScreen(dec))
            await pilot.pause(0.4)
            ecran = app.screen
            avant = (_cellule(ecran, "s:0"), _cellule(ecran, "v:0"))
            _sur_ligne(ecran, "s:0")
            await pilot.press("space")
            _sur_ligne(ecran, "a:1")
            await pilot.press("space")
            await pilot.pause(0.2)
            return avant, (_cellule(ecran, "s:0"), _cellule(ecran, "v:0"),
                           _cellule(ecran, "a:1"), _cellule(ecran, "a:1", "src"))

    (s_avant, v_avant), (s_apres, v_apres, a_apres, motif) = asyncio.run(_scenario())
    assert "MKV" in s_avant and "MKV" in v_avant      # le PGS impose le MKV
    assert s_apres == libelle_ecartee()
    assert "MP4" in v_apres and "MKV" not in v_apres
    assert a_apres == libelle_ecartee() and motif != _("selected")


# ─── CR-136 (b), CR-135 : ce qui est dessiné ─────────────────────────────────

def test_ligne_video_et_bandeau_d_aide_visibles_a_160_colonnes(tmp_path):
    dec = decide(_info(tmp_path), Profile(id="t", data=_PROFIL))

    async def _scenario():
        app = IrisEncodeApp(start_path=tmp_path)
        async with app.run_test(size=(160, 45)) as pilot:
            await pilot.pause(0.3)
            app.push_screen(TracksScreen(dec))
            await pilot.pause(0.4)
            return _texte_ecran(app)

    ecran = asyncio.run(_scenario())
    assert _("(profile)") in ecran               # le champ « original »
    assert _("Select / deselect") in ecran       # le bandeau d'aide


def test_seconde_ligne_du_bandeau_de_profil_visible(tmp_path):
    async def _scenario():
        app = IrisEncodeApp(start_path=tmp_path)
        async with app.run_test(size=(160, 45)) as pilot:
            await pilot.pause(0.3)
            app.screen._nav.enter(tmp_path)       # un dossier : le bandeau s'affiche
            app.screen._refresh_view()
            await pilot.pause(0.5)
            return _("HD audio"), _texte_ecran(app)

    libelle, ecran = asyncio.run(_scenario())
    assert libelle in ecran


# ─── CR-136 (c) : pas de « 0 kbps » ──────────────────────────────────────────

def test_skip_sans_debit_puis_debit_du_codec_choisi(tmp_path):
    dec = decide(_info(tmp_path, codec="hevc", bitrate=5_000_000),
                 Profile(id="t", data=_PROFIL))
    dec.info.subtitle_tracks = []          # rien qui ferait remuxer
    dec.subtitle_indices = None
    assert dec.video.action == VideoAction.SKIP

    async def _scenario():
        app = IrisEncodeApp(start_path=tmp_path)
        async with app.run_test(size=(200, 50)) as pilot:
            await pilot.pause(0.3)
            app.push_screen(TracksScreen(dec))
            await pilot.pause(0.4)
            ecran = app.screen
            skip = _cellule(ecran, "v:0")
            ecran._ov_action = VideoAction.ENCODE_HEVC
            ecran._build_table(keep_cursor=True)
            await pilot.pause(0.2)
            return skip, _cellule(ecran, "v:0")

    skip, hevc = asyncio.run(_scenario())
    assert "0 kbps" not in skip and "—" in skip
    assert "5000 kbps" in hevc


# ─── CR-132 : F4 refait la décision et les cases ─────────────────────────────

def test_f4_vers_un_profil_sans_anglais_decoche_l_anglais(tmp_path):
    dec = decide(_info(tmp_path), Profile(id="a", data=_PROFIL))
    autre = Profile(id="b", data={**_PROFIL, "audio_languages": ["fre"],
                                  "subtitle_languages": ["ger"]})

    async def _scenario():
        app = IrisEncodeApp(start_path=tmp_path)
        async with app.run_test(size=(200, 50)) as pilot:
            await pilot.pause(0.3)
            app.profiles = {"a": dec.profile, "b": autre}
            app.push_screen(TracksScreen(dec))
            await pilot.pause(0.4)
            ecran = app.screen
            ecran.action_change_profile()
            await pilot.pause(0.3)
            app.screen.dismiss("b")
            await pilot.pause(0.3)
            return ecran._make_selection(), _cellule(ecran, "a:1")

    sel, ligne = asyncio.run(_scenario())
    assert sel.audio == [0]
    assert sel.subtitle_indices == [0]           # subtitle_languages appliqué
    assert ligne == libelle_ecartee()


# ─── CR-133 : un débit choisi sur un SKIP survit au forçage ──────────────────

def test_debit_choisi_sur_un_skip_garde_au_forcage(tmp_path):
    dec = decide(_info(tmp_path, codec="hevc", bitrate=5_000_000),
                 Profile(id="t", data=_PROFIL))
    dec.info.subtitle_tracks = []
    dec.subtitle_indices = None
    assert dec.video.action == VideoAction.SKIP
    assert force_skip_to_encode(dec).video.target_bitrate == 5_000_000
    dec.video = dc_replace(dec.video, target_bitrate=2_000_000)   # F7 → 2000k
    assert force_skip_to_encode(dec).video.target_bitrate == 2_000_000
    a_encoder = WizardScreen._a_encoder(SimpleNamespace(_dec=dec))
    assert a_encoder.video.target_bitrate == 2_000_000


# ─── CR-138 : l'assistant garde la piste d'origine ───────────────────────────

def test_assistant_ne_laisse_pas_ecarter_la_piste_d_origine(tmp_path):
    dec = decide(_info(tmp_path), Profile(id="t", data=_PROFIL))

    async def _scenario():
        app = IrisEncodeApp(start_path=tmp_path)
        async with app.run_test(size=(180, 50)) as pilot:
            await pilot.pause(0.3)
            app.push_screen(WizardScreen(dec))
            await pilot.pause(0.3)
            ecran = app.screen
            await pilot.press("enter")
            await pilot.pause(0.3)
            assert ecran._etape == Etape.DECISION
            ecran.query_one(DataTable).move_cursor(
                row=ecran._lignes.index((_L_AUDIO, 0)))
            ecran.action_basculer()
            await pilot.pause(0.2)
            return [a.action.name for a in ecran._dec.audio]

    actions = asyncio.run(_scenario())
    assert actions[0] != "EXCLUDE"
