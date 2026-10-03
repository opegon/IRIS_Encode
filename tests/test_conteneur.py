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
    """Des sous-titres image d'autres langues que les SubRip.

    Doublés par un SubRip de même langue, ils seraient décochés dès la
    sélection (`_pgs_doubles`) et le conteneur n'aurait rien à écarter.
    """
    dec = decide(
        _info(tmp_path, [_st(0, "subrip"), _st(1, "subrip"),
                         _st(2, "hdmv_pgs_subtitle", "ger"),
                         _st(3, "dvd_subtitle", "ita")]),
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

def test_le_mp4_du_retrait_lit_la_source_et_filtre_le_rpu(tmp_path):
    """Le flux brut de `dovi_tool remove` n'a pas d'horodatage : ffmpeg y
    écrivait PTS = DTS, et le téléviseur jouait le son sans l'image. Le MP4
    part donc de la source, dont il garde les horodatages."""
    from core.dovi import build_strip_mp4

    cmd = build_strip_mp4(tmp_path / "s.mkv", tmp_path / "o.mp4", [0, 2])
    assert cmd.count("-i") == 1 and cmd[cmd.index("-i") + 1] == str(tmp_path / "s.mkv")
    assert cmd[cmd.index("-bsf:v") + 1] == "dovi_rpu=strip=1"
    assert "-r" not in cmd, "la cadence de la source fait foi"
    assert "0:s:0" in cmd and "0:s:2" in cmd
    assert cmd[cmd.index("-c:s") + 1] == "mov_text"


def test_le_remux_mp4_sans_sous_titre_ne_declare_pas_de_codec():
    from core.dovi import build_strip_mp4

    cmd = build_strip_mp4(Path("s.mkv"), Path("o.mp4"), [])
    assert "-c:s" not in cmd


# ─── Étiquette HEVC en MP4 : `hvc1` ───────────────────────────────────────────
# ffmpeg écrit `hev1` par défaut ; les lecteurs Apple exigent `hvc1`, et le G3
# lit les deux en lecture directe (IE-74).

def _plateforme():
    from core.platform import GPU, OS, PlatformProfile
    return PlatformProfile(os=OS.WINDOWS, gpu=GPU.NVIDIA, hwaccel="cuda",
                           encoder_hevc="hevc_nvenc", encoder_h264="h264_nvenc",
                           encoder_av1="av1_nvenc")


def _tag(cmd):
    return cmd[cmd.index("-tag:v") + 1] if "-tag:v" in cmd else None


def test_le_hevc_en_mp4_est_etiquete_hvc1(tmp_path):
    from core.decision import VideoAction
    from core.encoder import build_command

    dec = decide(_info(tmp_path, [_st(0, "subrip")]),
                 _profile(container="mp4", bitrate_1080p_kbps=2000))
    assert dec.video.action == VideoAction.ENCODE_HEVC
    assert dec.output_container == ".mp4"
    cmd = build_command(dec, _plateforme())
    assert _tag(cmd) == "hvc1"
    assert cmd.index("-tag:v") < cmd.index(str(dec.output_path)),         "une option après le fichier de sortie est ignorée"


def test_le_mkv_ne_recoit_pas_d_etiquette(tmp_path):
    from core.encoder import build_command

    dec = decide(_info(tmp_path, [_st(0, "subrip")]),
                 _profile(container="mkv", bitrate_1080p_kbps=2000))
    assert _tag(build_command(dec, _plateforme())) is None


@pytest.mark.parametrize("encodeur, codec_source, attendu", [
    ("hevc_nvenc", "h264", True),
    ("libx265",    "h264", True),
    ("hevc_videotoolbox", "h264", True),
    ("h264_nvenc", "hevc", False),
    ("av1_nvenc",  "hevc", False),
    ("copy",       "hevc", True),
    ("copy",       "h264", False),
])
def test_seule_une_sortie_hevc_est_etiquetee(encodeur, codec_source, attendu):
    from core.encoder import _sortie_hevc
    assert _sortie_hevc(["ffmpeg", "-c:v", encodeur], codec_source) is attendu


def test_le_mp4_du_retrait_est_etiquete_hvc1(tmp_path):
    from core.dovi import build_strip_mp4

    cmd = build_strip_mp4(tmp_path / "s.mkv", tmp_path / "o.mp4", [])
    assert _tag(cmd) == "hvc1"
    assert cmd[-1] == str(tmp_path / "o.mp4")


# ─── IE-109 : une copie Dolby Vision en MP4 garde sa boîte `dvcC` ────────────
# Sans `-strict unofficial`, ffmpeg 8.1.2 n'écrit pas `dvcC` : le fichier
# `.dv-iris.mp4` sortait sans Dolby Vision pour le téléviseur.

def _source_dv(tmp_path):
    info = _info(tmp_path, [_st(0, "subrip")])
    info.dv_profile, info.dv_bl_compat = 8, 1
    return info


def test_une_copie_dv_en_mp4_ecrit_la_configuration_dv(tmp_path, monkeypatch):
    import core.decision as decision
    from core.encoder import build_command, encodeur_de

    monkeypatch.setattr(decision, "peut_reencoder_en_dv", lambda *a: False)
    dec = decide(_source_dv(tmp_path),
                 _profile(container="mp4", dolby_vision="dv",
                          bitrate_1080p_kbps=2000))
    assert dec.output_container == ".mp4"
    cmd = build_command(dec, _plateforme())
    assert encodeur_de(cmd) == "copy"
    i = cmd.index("-strict")
    assert cmd[i + 1] == "unofficial"
    assert i < cmd.index(str(dec.output_path))


def test_un_encodage_sans_dv_n_a_pas_besoin_du_drapeau(tmp_path):
    from core.encoder import build_command

    dec = decide(_info(tmp_path, [_st(0, "subrip")]),
                 _profile(container="mp4", bitrate_1080p_kbps=2000))
    assert "-strict" not in build_command(dec, _plateforme())
