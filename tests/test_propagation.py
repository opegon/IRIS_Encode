"""
tests/test_propagation.py — La mesure de l'audio se reporte sur ses sous-titres.

La piste audio est la base du recalage : c'est sur elle que la mesure tourne.
Des sous-titres livrés avec une VF sont écrits sur le timing de cette VF, donc
leur bon décalage **est** celui de l'audio — le guide le disait déjà, et il
fallait quand même le recopier à la main, piste par piste, avec `c`. Une copie
qui n'apporte aucune information n'est qu'une occasion de l'oublier, et une
piste oubliée sort décalée sans que rien ne le signale.

Le report est automatique, sous trois garde-fous que ces tests verrouillent :

- **même fichier donneur** — un sous-titre venu d'ailleurs n'a aucune raison de
  partager ce timing ;
- **rien qui porte déjà une décision** — une piste mesurée pour elle-même ou
  ajustée à la main reste intacte ;
- **une audio seulement** — reporter depuis un sous-titre n'aurait pas de sens.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.decision import decide
from core.muxer import ExternalTrack, SyncOrigin, TrackKind
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo
from tui.screens.sync import SyncScreen


def _profile() -> Profile:
    return Profile(id="test", data={
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps": 8000, "audio_languages": ["fre", "eng"],
        "audio_copy_compatible": True, "preserve_hd_audio": False,
    })


def _info(tmp_path: Path) -> VideoInfo:
    p = tmp_path / "episode.mkv"
    p.write_bytes(b"")
    return VideoInfo(
        path=p, width=1920, height=1080, bitrate=8_000_000, codec="h264",
        duration=3703.0, frame_count=0, dv_profile=None,
        audio_tracks=[AudioTrack(index=0, codec="eac3", channels=6,
                                 language="eng", title="", bitrate=640_000)],
        subtitle_tracks=[],
    )


def _piste(donneur: Path, tid: int, kind: TrackKind,
           origin: SyncOrigin = SyncOrigin.NONE, delay: int = 0) -> ExternalTrack:
    return ExternalTrack(source_path=donneur, source_tid=tid, kind=kind,
                         codec="SubRip" if kind == TrackKind.SUBTITLE else "EAC3",
                         language="fre", delay_ms=delay, sync_origin=origin)


@pytest.fixture
def ecran(tmp_path):
    """Un SyncScreen non monté : `_propager` ne touche qu'aux données."""
    def _construire(pistes: list[ExternalTrack]) -> SyncScreen:
        dec = decide(_info(tmp_path), _profile())
        dec.external_tracks.extend(pistes)
        scr = SyncScreen(dec)
        scr._refresh_row = lambda _i: None      # pas de widget monté
        return scr
    return _construire


# ─── Le report ────────────────────────────────────────────────────────────────

def test_le_sous_titre_du_meme_donneur_suit_l_audio(tmp_path, ecran):
    vf = tmp_path / "vf.mkv"
    scr = ecran([_piste(vf, 1, TrackKind.AUDIO, delay=-2490),
                 _piste(vf, 3, TrackKind.SUBTITLE)])
    assert scr._propager(0) == 1
    st = scr._tracks[1]
    assert st.delay_ms == -2490
    assert st.sync_origin == SyncOrigin.COPIED
    assert st.copied_from == 0


def test_l_etirement_suit_aussi(tmp_path, ecran):
    """Une source PAL dérive : recopier le seul décalage ne suffirait pas."""
    vf = tmp_path / "vf.mkv"
    scr = ecran([_piste(vf, 1, TrackKind.AUDIO, delay=100),
                 _piste(vf, 3, TrackKind.SUBTITLE)])
    scr._tracks[0].stretch = (24000, 25025)
    scr._propager(0)
    assert scr._tracks[1].stretch == (24000, 25025)


def test_plusieurs_sous_titres_du_meme_donneur_suivent(tmp_path, ecran):
    vf = tmp_path / "vf.mkv"
    scr = ecran([_piste(vf, 1, TrackKind.AUDIO, delay=500),
                 _piste(vf, 3, TrackKind.SUBTITLE),
                 _piste(vf, 4, TrackKind.SUBTITLE)])
    assert scr._propager(0) == 2
    assert all(t.delay_ms == 500 for t in scr._tracks[1:])


# ─── Les garde-fous ───────────────────────────────────────────────────────────

def test_un_sous_titre_d_un_autre_fichier_reste_intact(tmp_path, ecran):
    vf, ailleurs = tmp_path / "vf.mkv", tmp_path / "autre.srt"
    scr = ecran([_piste(vf, 1, TrackKind.AUDIO, delay=-2490),
                 _piste(ailleurs, 0, TrackKind.SUBTITLE)])
    assert scr._propager(0) == 0
    assert scr._tracks[1].delay_ms == 0
    assert scr._tracks[1].sync_origin == SyncOrigin.NONE


@pytest.mark.parametrize("origine", [SyncOrigin.MEASURED, SyncOrigin.MANUAL])
def test_une_piste_deja_decidee_n_est_pas_ecrasee(tmp_path, ecran, origine):
    """Mesurée pour elle-même ou réglée à la main : c'est une décision."""
    vf = tmp_path / "vf.mkv"
    scr = ecran([_piste(vf, 1, TrackKind.AUDIO, delay=-2490),
                 _piste(vf, 3, TrackKind.SUBTITLE, origin=origine, delay=120)])
    assert scr._propager(0) == 0
    assert scr._tracks[1].delay_ms == 120
    assert scr._tracks[1].sync_origin == origine


def test_une_seconde_mesure_met_a_jour_ce_qui_la_suivait(tmp_path, ecran):
    """Une piste reprise de cette audio doit suivre sa correction."""
    vf = tmp_path / "vf.mkv"
    scr = ecran([_piste(vf, 1, TrackKind.AUDIO, delay=-2490),
                 _piste(vf, 3, TrackKind.SUBTITLE)])
    scr._propager(0)
    scr._tracks[0].delay_ms = -1000
    assert scr._propager(0) == 1
    assert scr._tracks[1].delay_ms == -1000


def test_une_piste_reprise_d_une_autre_source_n_est_pas_reprise(tmp_path, ecran):
    """`copied_from` pointe ailleurs : l'utilisateur a choisi cette référence."""
    vf = tmp_path / "vf.mkv"
    scr = ecran([_piste(vf, 1, TrackKind.AUDIO, delay=-2490),
                 _piste(vf, 2, TrackKind.AUDIO, delay=300),
                 _piste(vf, 3, TrackKind.SUBTITLE,
                        origin=SyncOrigin.COPIED, delay=300)])
    scr._tracks[2].copied_from = 1
    assert scr._propager(0) == 0
    assert scr._tracks[2].delay_ms == 300


def test_on_ne_propage_pas_depuis_un_sous_titre(tmp_path, ecran):
    vf = tmp_path / "vf.mkv"
    scr = ecran([_piste(vf, 3, TrackKind.SUBTITLE, delay=-2490),
                 _piste(vf, 4, TrackKind.SUBTITLE)])
    assert scr._propager(0) == 0
    assert scr._tracks[1].delay_ms == 0


def test_les_autres_pistes_audio_ne_sont_pas_touchees(tmp_path, ecran):
    """Deux VF du même fichier n'ont aucune raison de partager un décalage."""
    vf = tmp_path / "vf.mkv"
    scr = ecran([_piste(vf, 1, TrackKind.AUDIO, delay=-2490),
                 _piste(vf, 2, TrackKind.AUDIO)])
    assert scr._propager(0) == 0
    assert scr._tracks[1].delay_ms == 0


# ─── Ce que l'écran en dit ────────────────────────────────────────────────────

def test_le_report_est_annonce():
    assert SyncScreen._note_propagation(0) == ""
    assert "1 sous-titre" in SyncScreen._note_propagation(1)
    assert "recalé d'autant" in SyncScreen._note_propagation(1)
    assert "3 sous-titres" in SyncScreen._note_propagation(3)
    assert "recalés d'autant" in SyncScreen._note_propagation(3)
