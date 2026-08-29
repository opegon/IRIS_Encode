"""
tests/test_greffe.py — La piste greffée doit être celle qu'on a choisie.

Le donneur entre dans ffmpeg **en entier**, et la commande mappait son flux
`:0` — ce qui suppose qu'il n'en porte qu'un. Vrai d'un `.srt` nu, faux d'un
conteneur : un rip qui embarque six pistes de sous-titres rendait toujours la
première, quelle que soit celle demandée.

Le défaut était invisible à la relecture de la commande, parce que la langue,
le titre et les drapeaux venaient de la **bonne** piste. Vu de l'utilisateur :
la piste apparaît dans le lecteur, correctement nommée, et n'affiche rien —
la première piste d'un rip est en général la « forced », vingt-trois répliques
sur un épisode entier.

Signalé sur un fichier réel : `Silo.S03E09.720p.FR.mkv`, six pistes françaises
dont deux forced en tête de liste.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core import muxer
from core.decision import decide
from core.encoder import build_command
from core.muxer import ExternalTrack, IdentifiedTrack, TrackKind
from core.platform import GPU, OS, PlatformProfile
from core.profiles import Profile
from core.scanner import AudioTrack, SubtitleTrack, VideoInfo


def _plat() -> PlatformProfile:
    return PlatformProfile(os=OS.WINDOWS, gpu=GPU.NVIDIA, hwaccel="cuda",
                           encoder_hevc="hevc_nvenc", encoder_h264="h264_nvenc",
                           encoder_av1="av1_nvenc")


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


# Un donneur au dessin de Silo.S03E09.720p.FR.mkv : une piste audio, puis six
# sous-titres dont les forced en tête.
_DONNEUR = [
    IdentifiedTrack(tid=1, kind=TrackKind.AUDIO,    codec="EAC3",   language="fre",
                    track_name="French"),
    IdentifiedTrack(tid=2, kind=TrackKind.SUBTITLE, codec="SubRip", language="fre",
                    track_name="Français (France) (forced)"),
    IdentifiedTrack(tid=3, kind=TrackKind.SUBTITLE, codec="SubRip", language="fre",
                    track_name="Français (France)"),
    IdentifiedTrack(tid=4, kind=TrackKind.SUBTITLE, codec="SubRip", language="fre",
                    track_name="Français (France) (SDH)"),
    IdentifiedTrack(tid=5, kind=TrackKind.SUBTITLE, codec="SubRip", language="fre",
                    track_name="Français (Canada) (forced)"),
    IdentifiedTrack(tid=6, kind=TrackKind.SUBTITLE, codec="SubRip", language="fre",
                    track_name="Français (Canada)"),
    IdentifiedTrack(tid=7, kind=TrackKind.SUBTITLE, codec="SubRip", language="fre",
                    track_name="Français (Canada) (SDH)"),
]


@pytest.fixture
def donneur(monkeypatch, tmp_path) -> Path:
    p = tmp_path / "donneur.mkv"
    p.write_bytes(b"")
    monkeypatch.setattr(muxer, "identify", lambda _path: list(_DONNEUR))
    return p


def _maps(cmd: list[str]) -> list[str]:
    return [cmd[i + 1] for i, x in enumerate(cmd) if x == "-map"]


def _commande(tmp_path, pistes: list[ExternalTrack]) -> list[str]:
    dec = decide(_info(tmp_path), _profile())
    dec.external_tracks.extend(pistes)
    return build_command(dec, _plat())


# ─── Le défaut ────────────────────────────────────────────────────────────────

def test_le_sous_titre_greffe_est_celui_qui_a_ete_choisi(tmp_path, donneur):
    """tid 3 = « Français (France) », deuxième sous-titre du donneur → s:1."""
    piste = ExternalTrack(source_path=donneur, source_tid=3,
                          kind=TrackKind.SUBTITLE, codec="SubRip",
                          language="fre", track_name="Français (France)")
    maps = _maps(_commande(tmp_path, [piste]))
    assert "1:s:1" in maps, maps
    assert "1:s:0" not in maps, "c'est la piste « forced » — 23 répliques"


def test_la_derniere_piste_du_donneur_est_atteignable(tmp_path, donneur):
    piste = ExternalTrack(source_path=donneur, source_tid=7,
                          kind=TrackKind.SUBTITLE, codec="SubRip",
                          language="fre", track_name="Français (Canada) (SDH)")
    assert "1:s:5" in _maps(_commande(tmp_path, [piste]))


def test_une_piste_audio_choisie_est_mappee_pareil(tmp_path, donneur):
    """Le même défaut frappait l'audio dès qu'un donneur en portait plusieurs."""
    piste = ExternalTrack(source_path=donneur, source_tid=1,
                          kind=TrackKind.AUDIO, codec="EAC3", language="fre")
    assert "1:a:0" in _maps(_commande(tmp_path, [piste]))


def test_deux_pistes_du_meme_donneur_gardent_chacune_la_sienne(tmp_path, donneur):
    """Chaque piste a sa propre entrée : leurs index ne doivent pas se mélanger."""
    pistes = [
        ExternalTrack(source_path=donneur, source_tid=1, kind=TrackKind.AUDIO,
                      codec="EAC3", language="fre"),
        ExternalTrack(source_path=donneur, source_tid=4, kind=TrackKind.SUBTITLE,
                      codec="SubRip", language="fre"),
    ]
    maps = _maps(_commande(tmp_path, pistes))
    assert "1:a:0" in maps and "2:s:2" in maps, maps


def test_un_srt_nu_reste_en_zero(tmp_path, monkeypatch):
    """Le cas d'origine : un fichier à une seule piste, tid 0."""
    p = tmp_path / "vf.srt"
    p.write_bytes(b"")
    monkeypatch.setattr(muxer, "identify", lambda _p: [
        IdentifiedTrack(tid=0, kind=TrackKind.SUBTITLE, codec="SubRip",
                        language="fre")])
    piste = ExternalTrack(source_path=p, source_tid=0, kind=TrackKind.SUBTITLE,
                          codec="SubRip", language="fre")
    assert "1:s:0" in _maps(_commande(tmp_path, [piste]))


def test_un_donneur_illisible_retombe_sur_le_premier_flux(tmp_path, monkeypatch):
    """mkvmerge absent ou muet : on ne devine pas, on garde l'ancien comportement."""
    p = tmp_path / "muet.mkv"
    p.write_bytes(b"")
    monkeypatch.setattr(muxer, "identify", lambda _p: [])
    piste = ExternalTrack(source_path=p, source_tid=3, kind=TrackKind.SUBTITLE,
                          codec="SubRip", language="fre")
    assert "1:s:0" in _maps(_commande(tmp_path, [piste]))


# ─── La greffe passée par un mux préalable ────────────────────────────────────
#
# Une piste étirée ne peut pas entrer par ffmpeg : mkvmerge la greffe d'abord,
# ffmpeg encode l'intermédiaire. L'écran d'encodage vidait alors
# `external_tracks` — à raison, ffmpeg ne doit pas rouvrir les donneurs — mais
# rien ne mappait plus les pistes greffées, que ffmpeg laissait donc tomber.
# Aucune erreur, code de retour nul : l'utilisateur récupérait un fichier sans
# la VF qu'il venait de recaler.

def _info_sous_titres(tmp_path: Path) -> VideoInfo:
    """La même source, mais avec deux sous-titres à elle."""
    info = _info(tmp_path)
    info.subtitle_tracks = [
        SubtitleTrack(index=0, codec="subrip", language="fre"),
        SubtitleTrack(index=1, codec="subrip", language="eng"),
    ]
    return info


def _commande_premux(tmp_path, pistes: list[ExternalTrack],
                     intermediaire: Path | None = None) -> list[str]:
    """La commande telle que l'écran d'encodage la construit après un mux."""
    dec = decide(_info(tmp_path), _profile())
    dec.encode_source   = intermediaire or (tmp_path / "premux.mkv")
    dec.premuxed_tracks = pistes
    return build_command(dec, _plat())


def _piste_etiree(donneur: Path, tid: int, kind: TrackKind) -> ExternalTrack:
    return ExternalTrack(source_path=donneur, source_tid=tid, kind=kind,
                         codec="EAC3" if kind == TrackKind.AUDIO else "SubRip",
                         language="fre", stretch=(24000, 25025))


def test_la_piste_audio_muxee_en_amont_est_mappee(tmp_path, donneur):
    """La source porte une piste audio : la greffée est la deuxième."""
    cmd  = _commande_premux(tmp_path, [_piste_etiree(donneur, 1, TrackKind.AUDIO)])
    maps = _maps(cmd)
    assert "0:a:1" in maps, maps
    # Et elle est recopiée, pas réencodée dans le codec par défaut du conteneur
    assert "-c:a:1" in cmd and cmd[cmd.index("-c:a:1") + 1] == "copy"


def test_le_sous_titre_muxe_en_amont_est_mappe(tmp_path, donneur):
    """Sélection explicite de sous-titres — ce que font tous les profils livrés.

    C'est le cas qui perdait la piste : `0:s?` prend tout l'intermédiaire, une
    liste d'index ne prend que ce qu'elle nomme.
    """
    dec = decide(_info_sous_titres(tmp_path), _profile())
    dec.subtitle_indices  = [0]
    dec.encode_source     = tmp_path / "premux.mkv"
    dec.premuxed_tracks   = [_piste_etiree(donneur, 3, TrackKind.SUBTITLE)]
    maps = _maps(build_command(dec, _plat()))
    assert "0:s:0" in maps and "0:s:2" in maps, maps
    assert "0:s:1" not in maps, "l'anglais n'était pas retenu"


def test_le_sous_titre_muxe_est_pris_une_seule_fois_par_0s(tmp_path, donneur):
    """Sans sélection, `0:s?` prend déjà la greffée : la mapper doublerait."""
    maps = _maps(_commande_premux(
        tmp_path, [_piste_etiree(donneur, 3, TrackKind.SUBTITLE)]))
    assert maps.count("0:s?") == 1 and not any(m.startswith("0:s:") for m in maps), maps


def test_les_donneurs_ne_sont_pas_rouverts(tmp_path, donneur):
    """mkvmerge les a déjà absorbés : une seconde entrée les doublerait."""
    cmd = _commande_premux(tmp_path, [_piste_etiree(donneur, 1, TrackKind.AUDIO)])
    entrees = [cmd[i + 1] for i, x in enumerate(cmd) if x == "-i"]
    assert entrees == [str(tmp_path / "premux.mkv")], entrees


def test_la_langue_et_les_drapeaux_survivent_au_mux_prealable(tmp_path, donneur):
    piste = _piste_etiree(donneur, 1, TrackKind.AUDIO)
    piste.track_name = "VF"
    piste.is_default = True
    cmd = _commande_premux(tmp_path, [piste])
    assert "-metadata:s:a:1" in cmd
    assert "language=fre" in cmd and "title=VF" in cmd
    # Le drapeau « défaut » se retire de la piste source, sinon deux le portent
    assert cmd[cmd.index("-disposition:a:0") + 1] == "0"
    assert cmd[cmd.index("-disposition:a:1") + 1] == "default"


def test_l_ordre_des_greffees_est_celui_de_mkvmerge(tmp_path, donneur):
    """mkvmerge écrit les pistes d'un donneur dans l'ordre de ses tid.

    L'ordre où l'utilisateur les a choisies n'y change rien : prendre le sien
    donnerait un décalage d'un cran entre chaque piste et son étiquette.
    """
    pistes = [_piste_etiree(donneur, 6, TrackKind.SUBTITLE),   # choisie en 1er
              _piste_etiree(donneur, 3, TrackKind.SUBTITLE)]
    pistes[0].track_name = "Canada"
    pistes[1].track_name = "France"
    cmd = _commande_premux(tmp_path, pistes)
    # tid 3 avant tid 6 dans l'intermédiaire → « France » porte s:0
    titres = [cmd[i + 1] for i, x in enumerate(cmd) if x == "-metadata:s:s:0"]
    assert "title=France" in titres, cmd


def test_une_piste_etiree_encore_externe_reste_refusee(tmp_path, donneur):
    """Le garde-fou vaut toujours : ffmpeg ne sait pas étirer en une passe."""
    dec = decide(_info(tmp_path), _profile())
    dec.external_tracks.append(_piste_etiree(donneur, 1, TrackKind.AUDIO))
    with pytest.raises(ValueError, match="étirement"):
        build_command(dec, _plat())
