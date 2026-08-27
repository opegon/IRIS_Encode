"""
tests/test_conteneur.py — La clé `container` : auto / mp4 / mkv.

Le conteneur était déduit du seul contenu. Un profil peut désormais exprimer
une politique — certains lecteurs digèrent mal le Matroska — mais **jamais au
prix d'une piste perdue en silence** :

- en `mp4`, les sous-titres image sont écartés et la décision les compte ;
- s'ils sont les **seuls** du fichier, c'est le conteneur qui cède : mieux vaut
  un MKV qu'une sortie sans sous-titres ;
- une piste audio sans perte conservée ramène toujours au MKV — on n'échange
  pas une piste demandée contre un format.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.decision import decide
from core.profiles import Profile
from core.scanner import AudioTrack, SubtitleTrack, VideoInfo


def _info(tmp_path: Path, sous_titres, audio=None) -> VideoInfo:
    p = tmp_path / "film.mkv"
    p.write_bytes(b"")
    return VideoInfo(
        path=p, width=1920, height=1080, bitrate=3_000_000, codec="hevc",
        duration=5400.0, frame_count=0, dv_profile=None,
        audio_tracks=audio or [AudioTrack(index=0, codec="eac3", channels=6,
                                          language="fre", title="",
                                          bitrate=640_000)],
        subtitle_tracks=sous_titres,
    )


def _st(index, codec, langue="fre") -> SubtitleTrack:
    return SubtitleTrack(index=index, codec=codec, language=langue)


def _profile(**over) -> Profile:
    data = {
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps": 8000, "audio_languages": ["fre", "eng"],
        "audio_copy_compatible": True, "preserve_hd_audio": False,
        "container": "auto",
    }
    data.update(over)
    return Profile(id="test", data=data)


# ─── Les trois modes ──────────────────────────────────────────────────────────

def test_auto_laisse_le_contenu_decider(tmp_path):
    texte = decide(_info(tmp_path, [_st(0, "subrip")]), _profile())
    assert texte.output_container == ".mp4"

    image = decide(_info(tmp_path, [_st(0, "hdmv_pgs_subtitle")]), _profile())
    assert image.output_container == ".mkv"


def test_mkv_force_meme_quand_tout_tiendrait_en_mp4(tmp_path):
    dec = decide(_info(tmp_path, [_st(0, "subrip")]), _profile(container="mkv"))
    assert dec.output_container == ".mkv"
    assert dec.sous_titres_ecartes == [], "rien n'a à être écarté en MKV"


def test_mp4_ecarte_les_sous_titres_image(tmp_path):
    """Le cas courant : les PGS doublent des SubRip de mêmes langues."""
    dec = decide(
        _info(tmp_path, [_st(0, "subrip"), _st(1, "subrip"),
                         _st(2, "hdmv_pgs_subtitle"), _st(3, "dvd_subtitle")]),
        _profile(container="mp4"))
    assert dec.output_container == ".mp4"
    assert [st.index for st in dec.sous_titres_ecartes] == [2, 3]
    assert [st.index for st in dec.subtitles_finales] == [0, 1]


# ─── Ce qu'on ne sacrifie jamais ──────────────────────────────────────────────

def test_des_sous_titres_image_seuls_font_ceder_le_conteneur(tmp_path):
    """Le cas Colossus : son unique sous-titre est une piste image."""
    dec = decide(_info(tmp_path, [_st(0, "hdmv_pgs_subtitle", "ger")]),
                 _profile(container="mp4"))
    assert dec.output_container == ".mkv"
    assert dec.sous_titres_ecartes == []
    assert len(dec.subtitles_finales) == 1


def test_une_piste_sans_perte_conservee_ramene_au_mkv(tmp_path):
    """Écarter un sous-titre doublé ne coûte rien ; perdre une piste audio
    que l'utilisateur a demandé de garder, si."""
    audio = [AudioTrack(index=0, codec="truehd", channels=6, language="eng",
                        title="", bitrate=3_500_000)]
    dec = decide(_info(tmp_path, [_st(0, "subrip"), _st(1, "hdmv_pgs_subtitle")],
                       audio=audio),
                 _profile(container="mp4", preserve_hd_audio=True))
    assert dec.output_container == ".mkv"
    assert dec.sous_titres_ecartes == [], "sortie MKV : rien n'est écarté"


def test_sans_sous_titre_image_rien_n_est_ecarte(tmp_path):
    dec = decide(_info(tmp_path, [_st(0, "subrip")]), _profile(container="mp4"))
    assert dec.sous_titres_ecartes == []
    assert dec.output_container == ".mp4"


# ─── La commande ne mappe que ce qui atterrit ─────────────────────────────────

def test_l_encodage_ne_mappe_pas_les_sous_titres_ecartes(tmp_path):
    from core.encoder import build_command
    from core.platform import GPU, OS, PlatformProfile

    plat = PlatformProfile(os=OS.WINDOWS, gpu=GPU.NVIDIA, hwaccel="cuda",
                           encoder_hevc="hevc_nvenc", encoder_h264="h264_nvenc",
                           encoder_av1="av1_nvenc")
    info = _info(tmp_path, [_st(0, "subrip"), _st(1, "hdmv_pgs_subtitle")])
    dec  = decide(info, _profile(container="mp4", bitrate_1080p_kbps=2000))
    cmd  = build_command(dec, plat)

    assert "0:s:0" in cmd
    assert "0:s:1" not in cmd, "le sous-titre image est mappé malgré l'exclusion"
    assert "0:s?" not in cmd, "mapping global : l'exclusion serait ignorée"


# ─── Le remux MP4 du retrait de Dolby Vision ──────────────────────────────────

def test_le_remux_mp4_pose_la_cadence_et_le_correctif_de_base(tmp_path):
    """Un flux HEVC brut n'a pas d'horodatage, et ses premières images ont des
    DTS négatifs que le muxeur MP4 jetait — deux images perdues sur 2270."""
    from core.dovi import build_strip_remux_mp4

    cmd = build_strip_remux_mp4(tmp_path / "n.hevc", tmp_path / "s.mkv",
                                tmp_path / "o.mp4", "24000/1001", [0, 2])
    assert cmd[cmd.index("-r") + 1] == "24000/1001"
    assert cmd.index("-r") < cmd.index("-i"), "la cadence doit précéder l'entrée"
    assert cmd[cmd.index("-avoid_negative_ts") + 1] == "make_zero"
    assert "1:s:0" in cmd and "1:s:2" in cmd
    assert cmd[cmd.index("-c:s") + 1] == "mov_text"


def test_le_remux_mp4_sans_sous_titre_ne_declare_pas_de_codec():
    from core.dovi import build_strip_remux_mp4

    cmd = build_strip_remux_mp4(Path("n.hevc"), Path("s.mkv"), Path("o.mp4"),
                                "24/1", [])
    assert "-c:s" not in cmd
