"""
tests/test_remux.py — Le remux (IE-175).

Une vidéo au bon débit, à la bonne définition et dans un codec lisible était
laissée telle quelle (SKIP), même quand une piste audio DTS ou TrueHD, ou un
PGS doublé par un SRT, faisait transcoder Jellyfin. La décision passe alors en
REMUX : l'image est recopiée, les pistes suivent la règle du profil.
"""
from __future__ import annotations

from pathlib import Path

from core.decision import (VideoAction, ajuster_remux, decide,
                           force_skip_to_encode)
from core.encoder import build_command
from core.profiles import Profile
from core.scanner import AudioTrack, SubtitleTrack, VideoInfo


def _profil() -> Profile:
    return Profile(id="t", data={"bitrate_1080p_kbps": 5000,
                                 "bitrate_720p_kbps": 2000,
                                 "audio_languages": ["fre", "eng"]})


def _a(index, codec, langue="fre", canaux=6) -> AudioTrack:
    return AudioTrack(index=index, codec=codec, channels=canaux,
                      language=langue, title="", bitrate=1_500_000)


def _info(tmp_path: Path, audio, sous_titres=(), nom="Film.1080p.DTS.mkv",
          dv=None) -> VideoInfo:
    p = tmp_path / nom
    p.write_bytes(b"")
    return VideoInfo(
        path=p, width=1920, height=1080, bitrate=3_000_000, codec="hevc",
        duration=5400.0, frame_count=0, dv_profile=dv,
        audio_tracks=list(audio), subtitle_tracks=list(sous_titres),
    )


def _plateforme():
    from core.platform import GPU, OS, PlatformProfile
    return PlatformProfile(os=OS.WINDOWS, gpu=GPU.NVIDIA, hwaccel="cuda",
                           encoder_hevc="hevc_nvenc", encoder_h264="h264_nvenc",
                           encoder_av1="av1_nvenc")


# ─── Le déclenchement ─────────────────────────────────────────────────────────

def test_un_dts_garde_fait_remuxer(tmp_path):
    dec = decide(_info(tmp_path, [_a(0, "dts")]), _profil())
    assert dec.video.action == VideoAction.REMUX
    assert dec.video.output_suffix == ".remux-iris"
    assert dec.video.label() == "→ remux"
    assert "DTS" in dec.video.reason


def test_un_audio_compatible_reste_skip(tmp_path):
    dec = decide(_info(tmp_path, [_a(0, "eac3"), _a(1, "ac3", "eng")]), _profil())
    assert dec.video.action == VideoAction.SKIP


def test_un_dts_ecarte_par_la_langue_ne_declenche_rien(tmp_path):
    """Le lecteur ne choisit pas une piste que le profil écarte."""
    dec = decide(_info(tmp_path, [_a(0, "ac3"), _a(1, "dts", "ger")]), _profil())
    assert dec.video.action == VideoAction.SKIP


def test_un_pgs_double_par_un_srt_fait_remuxer(tmp_path):
    st = [SubtitleTrack(index=0, codec="hdmv_pgs_subtitle", language="fre"),
          SubtitleTrack(index=1, codec="subrip", language="fre")]
    dec = decide(_info(tmp_path, [_a(0, "ac3")], st), _profil())
    assert dec.video.action == VideoAction.REMUX
    assert "PGS" in dec.video.reason


def test_un_pgs_seul_dans_sa_langue_reste_skip(tmp_path):
    """Le retirer coûterait le sous-titre : il reste, sans remux."""
    st = [SubtitleTrack(index=0, codec="hdmv_pgs_subtitle", language="fre")]
    dec = decide(_info(tmp_path, [_a(0, "ac3")], st), _profil())
    assert dec.video.action == VideoAction.SKIP


def test_une_video_a_reencoder_n_est_pas_un_remux(tmp_path):
    info = _info(tmp_path, [_a(0, "dts")])
    info.bitrate = 20_000_000
    assert decide(info, _profil()).video.action == VideoAction.ENCODE_HEVC


def test_le_remux_se_leve_quand_la_piste_part(tmp_path):
    """Écarter le DTS à la main : plus rien à convertir, retour au SKIP."""
    info = _info(tmp_path, [_a(0, "ac3"), _a(1, "dts", "eng")])
    dec = decide(info, _profil())
    assert dec.video.action == VideoAction.REMUX
    from core.decision import decide_audio
    dec.audio = decide_audio(info, _profil(), [0])
    assert ajuster_remux(dec).video.action == VideoAction.SKIP


def test_coche_une_ligne_remux_ne_la_reencode_pas(tmp_path):
    dec = decide(_info(tmp_path, [_a(0, "dts")]), _profil())
    assert force_skip_to_encode(dec).video.action == VideoAction.REMUX


# ─── Le nom et la commande ────────────────────────────────────────────────────

def test_le_nom_dit_le_format_audio_produit(tmp_path):
    dec = decide(_info(tmp_path, [_a(0, "dts")]), _profil())
    nom = dec.output_path.name
    assert nom.endswith(".remux-iris.mp4") or nom.endswith(".remux-iris.mkv")
    assert "DTS" not in nom and "AC3" in nom


def test_la_commande_recopie_la_video_et_convertit_l_audio(tmp_path):
    dec = decide(_info(tmp_path, [_a(0, "dts")]), _profil())
    cmd = build_command(dec, _plateforme())
    assert cmd[cmd.index("-c:v") + 1] == "copy"
    assert "-vf" not in cmd and "-hwaccel" not in cmd
    assert cmd[cmd.index("-c:a:0") + 1] == "ac3"
    assert cmd[-1].endswith(dec.output_path.name)


def test_un_remux_dolby_vision_garde_sa_boite_en_mp4(tmp_path):
    """La vidéo DV recopiée en MP4 a besoin de `-strict unofficial` (IE-109)."""
    info = _info(tmp_path, [_a(0, "dts")], dv=8)
    info.dv_bl_compat = 1
    dec = decide(info, Profile(id="t", data={**_profil().data,
                                             "dolby_vision": "dv"}))
    assert dec.video.action == VideoAction.REMUX
    assert dec.output_container == ".mp4"
    cmd = build_command(dec, _plateforme())
    assert cmd[cmd.index("-c:v") + 1] == "copy"
    assert "unofficial" in cmd


def test_un_remux_sans_dolby_vision_n_ajoute_pas_strict(tmp_path):
    cmd = build_command(decide(_info(tmp_path, [_a(0, "dts")]), _profil()),
                        _plateforme())
    assert "unofficial" not in cmd


# ─── Le filtre de l'accueil ───────────────────────────────────────────────────

def test_le_filtre_l_retrouve_les_remux(tmp_path):
    from tui.screens.browser import (FILTRE_REMUX, ligne_visible,
                                     options_filtre)
    remux = decide(_info(tmp_path, [_a(0, "dts")]), _profil())
    skip  = decide(_info(tmp_path, [_a(0, "ac3")], nom="Autre.mkv"), _profil())
    assert ligne_visible(remux, FILTRE_REMUX, False, False)
    assert not ligne_visible(skip, FILTRE_REMUX, False, False)
    assert FILTRE_REMUX in [cle for cle, _l in options_filtre([remux, skip])]
    assert FILTRE_REMUX not in [cle for cle, _l in options_filtre([skip])]
