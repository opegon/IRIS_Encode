"""
tests/test_decision_accueil.py — La décision d'un fichier sur l'accueil (IE-123).

Constats de la revue IE-114 : la `FileDecision` de l'accueil était modifiée en
place par les écrans de travail et remplacée en bloc par chaque rescan.

- **CR-74** — pendant un lot, chaque retour à l'accueil rescannait et perdait
  codec, débit, suppression et greffes réglés sur un fichier ;
- **CR-81** — `F4` dans l'écran des pistes puis `⌫` gardait le profil choisi,
  suppression de la source comprise ; **CR-88**, même chose dans l'aperçu ;
- **CR-84** — l'assistant figeait le nom de sortie, qu'une greffe ASS rendait
  faux ; **CR-15** — un mux annonçait un `.mp4` que mkvmerge n'écrit pas ;
- **CR-82** — un SKIP muni de greffes finissait « ignoré » dans la file ;
- **CR-76** — renoncer au dossier de sortie décochait quand même ;
- **CR-87**, **CR-98** — lignes et dossier non relus au retour.
"""
from __future__ import annotations

import asyncio
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

from core.decision import (Reglages, VideoAction, appliquer_reglages, choisir_codec,
                           decide, reglages_explicites, sortie_prevue)
from core.muxer import ExternalTrack, TrackKind
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo

RACINE = Path(__file__).resolve().parent.parent


def _profil(pid: str = "actif", **extra) -> Profile:
    return Profile(id=pid, data={
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps": 12000, "keep_4k": True,
        "audio_languages": ["fre", "eng"], "audio_copy_compatible": True, **extra,
    })


def _info(path: Path, codec: str = "h264", bitrate: int = 20_000_000) -> VideoInfo:
    return VideoInfo(
        path=path, width=1920, height=1080, bitrate=bitrate, codec=codec,
        duration=3600.0, frame_count=0, dv_profile=None,
        audio_tracks=[AudioTrack(index=0, codec="ac3", channels=6, language="fre",
                                 title="", bitrate=448_000)])


def _piste(nom: str = "Film.fr.srt", codec: str = "SubRip/SRT") -> ExternalTrack:
    return ExternalTrack(source_path=Path(f"/films/{nom}"), source_tid=0,
                         kind=TrackKind.SUBTITLE, codec=codec, language="fre")


# ─── Le registre des réglages explicites ──────────────────────────────────────

def test_une_décision_automatique_n_a_rien_d_explicite(tmp_path):
    actif = _profil()
    dec = decide(_info(tmp_path / "Film.mkv"), actif)
    assert reglages_explicites(dec, actif).vide


def test_codec_débit_suppression_et_greffes_survivent_au_rescan(tmp_path):
    from dataclasses import replace
    actif = _profil()
    info  = _info(tmp_path / "Film.mkv")
    dec   = decide(info, actif)
    dec.video = replace(choisir_codec(dec, VideoAction.ENCODE_AV1), target_bitrate=2_500_000)
    dec.delete_source_override = True
    dec.external_tracks = [_piste()]
    reglages = reglages_explicites(dec, actif)

    refait = appliquer_reglages(info, actif, reglages, {"actif": actif})
    assert refait.video.action == VideoAction.ENCODE_AV1
    assert refait.video.target_bitrate == 2_500_000
    assert refait.delete_source_override is True
    assert [t.source_path.name for t in refait.external_tracks] == ["Film.fr.srt"]
    assert refait.external_tracks[0] is not reglages.external_tracks[0], "une copie"


def test_un_profil_propre_au_fichier_survit_au_rescan(tmp_path):
    actif, autre = _profil("actif"), _profil("autre", delete_source=True)
    info = _info(tmp_path / "Film.mkv")
    dec  = decide(info, autre)
    reglages = reglages_explicites(dec, actif)
    assert reglages.profil == "autre" and reglages.video is None
    refait = appliquer_reglages(info, actif, reglages, {"actif": actif, "autre": autre})
    assert refait.profile.id == "autre"


def test_un_profil_supprimé_rend_la_main_au_profil_actif(tmp_path):
    actif = _profil("actif")
    refait = appliquer_reglages(_info(tmp_path / "Film.mkv"), actif,
                                Reglages(profil="disparu"), {"actif": actif})
    assert refait.profile.id == "actif"


# ─── Le nom de sortie ─────────────────────────────────────────────────────────

def test_un_mux_annonce_le_matroska_que_mkvmerge_écrit(tmp_path):
    """CR-15."""
    from core.muxer import mux_output_path
    dec = decide(_info(tmp_path / "Film.mkv", codec="hevc", bitrate=1_000_000), _profil())
    assert dec.video.action == VideoAction.SKIP
    dec.external_tracks = [_piste()]
    assert dec.output_path == mux_output_path(dec.info.path)


def test_le_nom_prévu_n_est_pas_figé_et_suit_la_greffe(tmp_path):
    """CR-84 : MP4 annoncé, greffe ASS ajoutée → le nom dit Matroska."""
    dec = decide(_info(tmp_path / "Film.mkv"), _profil())
    assert sortie_prevue(dec).suffix == ".mp4"
    assert dec.output_override is None, "afficher ne fige rien"
    dec.external_tracks = [_piste("Film.fr.ass", codec="SubStationAlpha")]
    assert sortie_prevue(dec).suffix == dec.output_container == ".mkv"


def test_le_nom_prévu_numérote_comme_la_file(tmp_path):
    dec = decide(_info(tmp_path / "Film.mkv"), _profil())
    dec.output_path.write_bytes(b"")
    assert sortie_prevue(dec).name.endswith("(2).mp4")


def test_l_assistant_ne_fige_plus_le_nom():
    texte = (RACINE / "tui" / "screens" / "wizard.py").read_text(encoding="utf-8")
    assert "resoudre_sorties" not in texte


# ─── Les écrans de travail ne touchent que des copies ─────────────────────────

def test_l_aperçu_travaille_sur_des_copies(tmp_path):
    """CR-88."""
    from tui.screens.dryrun import DryrunScreen
    dec = decide(_info(tmp_path / "Film.mkv"), _profil())
    ecran = DryrunScreen([dec])
    assert ecran._decisions[0] is not dec
    ecran._apply_codec(ecran._decisions[0], VideoAction.ENCODE_AV1)
    assert dec.video.action != VideoAction.ENCODE_AV1


def test_les_options_disent_à_l_accueil_de_relire():
    """CR-98 : l'écran de gestion des profils écoute le retour des options."""
    texte = (RACINE / "tui" / "screens" / "config.py").read_text(encoding="utf-8")
    assert "self.app.push_screen(OptionsScreen(), _enregistre)" in texte


# ─── La file : un SKIP muni de greffes est un mux ─────────────────────────────

from tests.test_arret_encodage import _App, faux  # noqa: E402,F401


class _FauxMux:
    def __init__(self, cmd):
        self.sortie = Path(cmd[cmd.index("-o") + 1])
        self.errors = []

    def start(self):
        self.sortie.write_bytes(b"mkv")

    def iter_progress(self):
        yield "", 100

    def wait(self):
        return 1                      # des avertissements : la sortie vaut

    def terminate(self):
        pass


def test_un_skip_muni_de_greffes_est_muxé_par_la_file(tmp_path, monkeypatch, faux):
    """CR-82."""
    from tui.screens import run as run_mod
    from tui.screens.run import FileState
    monkeypatch.setattr(run_mod, "MuxProcess", _FauxMux)
    monkeypatch.setattr(run_mod, "build_mux_command",
                        lambda src, pistes, sortie: ["mkvmerge", "-o", str(sortie)])
    source = tmp_path / "Film.mkv"
    source.write_bytes(b"")
    dec = decide(_info(source, codec="hevc", bitrate=1_000_000), _profil())
    dec.external_tracks = [_piste()]
    assert dec.video.action == VideoAction.SKIP

    async def scenario():
        app = _App([dec])
        app.mkvmerge_available = True
        async with app.run_test() as pilot:
            for _i in range(20):
                await pilot.pause(0.2)
                if app.lot.termine:
                    break
            s = app.lot.statuts[0]
            return s.state, s.decision.output_path

    etat, sortie = asyncio.run(scenario())
    assert etat == FileState.SUCCESS
    assert sortie.name == "Film.mux-iris.mkv" and sortie.exists()


def test_renoncer_au_dossier_de_sortie_ne_décoche_rien(tmp_path, monkeypatch, faux):
    """CR-76 : `apres` n'est appelé qu'une fois la mise en file faite."""
    import core.decision as decision_mod
    from tests.test_arret_encodage import _dec
    from tui.screens.output_dir import OutputDirScreen

    (tmp_path / "iso").mkdir()
    monkeypatch.setattr(decision_mod, "dossier_inscriptible", lambda d: d.name != "iso")
    appels = []

    async def scenario():
        app = _App([])
        app.cfg = {"app": {"output_dir": str(tmp_path)}}
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            app.encoder([_dec(tmp_path / "iso" / "titre.m2ts")],
                        apres=lambda: appels.append(1))
            await pilot.pause(0.5)
            assert isinstance(app.screen, OutputDirScreen)
            await pilot.press("escape")
            await pilot.pause(0.3)

    asyncio.run(scenario())
    assert appels == []


# ─── L'accueil, de bout en bout ───────────────────────────────────────────────

def _clip(dossier: Path) -> Path:
    from core import config as cfg_mod
    from core.preflight import get_tool_path
    ffmpeg = get_tool_path("ffmpeg", cfg_mod.get_bin_dir(cfg_mod.load()))
    if not ffmpeg:
        pytest.skip("ffmpeg absent")
    clip = dossier / "Film.mkv"
    subprocess.run([str(ffmpeg), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "testsrc=duration=2:size=1920x1080:rate=10", "-c:v", "libx264",
                    "-b:v", "20M", str(clip)], check=True, capture_output=True)
    return clip


async def _accueil(dossier: Path, scenario):
    from tui.app import IrisEncodeApp
    from tui.screens.browser import BrowserScreen
    app = IrisEncodeApp(start_path=dossier)
    async with app.run_test(size=(180, 40)) as pilot:
        await pilot.pause(0.5)
        app.push_screen(BrowserScreen(dossier, start_virtual=False))
        await pilot.pause(3.0)
        return await scenario(app, app.screen, pilot)


def test_les_réglages_d_un_fichier_survivent_au_rescan(tmp_path):
    """CR-74 : un codec et une greffe réglés, puis l'accueil rescanne."""
    clip = _clip(tmp_path)

    async def scenario(app, ecran, pilot):
        dec = deepcopy(ecran._decisions[clip])
        dec.video = choisir_codec(dec, VideoAction.ENCODE_AV1)
        dec.external_tracks = [_piste()]
        ecran._decisions[clip] = dec
        ecran._retenir(clip, dec)
        ecran._refresh_view()
        await pilot.pause(3.0)
        refait = ecran._decisions[clip]
        return refait is not dec, refait.video.action, len(refait.external_tracks)

    nouveau, action, greffes = asyncio.run(_accueil(tmp_path, scenario))
    assert nouveau, "le rescan a bien refait la décision"
    assert action == VideoAction.ENCODE_AV1 and greffes == 1


def test_pendant_un_lot_le_retour_ne_rescanne_qu_après_une_réussite(tmp_path, monkeypatch):
    """CR-74 : un ffprobe par fichier à chaque fermeture d'écran, c'était trop."""
    from tui.screens import browser as browser_mod
    clip = _clip(tmp_path)

    async def scenario(app, ecran, pilot):
        appels = []
        monkeypatch.setattr(ecran, "_refresh_view", lambda: appels.append(1))
        reussies = set()
        monkeypatch.setattr(browser_mod, "sources_reussies", lambda lots: set(reussies))
        app.lots_encodes = [[object()]]
        ecran.on_screen_resume()
        ecran.on_screen_resume()
        avant = len(appels)
        reussies.add(clip)
        app.lots_encodes = [[object()]]
        ecran.on_screen_resume()
        app.lots_encodes = [[object()]]
        ecran.on_screen_resume()
        return avant, len(appels)

    avant, apres = asyncio.run(_accueil(tmp_path, scenario))
    assert avant == 0, "aucune réussite nouvelle : pas de rescan"
    assert apres == 1, "une réussite : un rescan, une seule fois"


def test_l_écran_des_pistes_reçoit_une_copie(tmp_path):
    """CR-81 : `⌫` n'en garde rien, pas même un profil changé."""
    clip = _clip(tmp_path)

    async def scenario(app, ecran, pilot):
        maison = ecran._decisions[clip]
        ecran.action_open_tracks()
        await pilot.pause(1.0)
        pistes = app.screen
        copie = pistes._decision
        copie.profile = _profil("autre", delete_source=True)
        await pilot.press("backspace")
        await pilot.pause(0.5)
        return copie is not maison, ecran._decisions[clip] is maison, maison.profile.id

    copie, garde, profil = asyncio.run(_accueil(tmp_path, scenario))
    assert copie and garde
    assert profil != "autre"
