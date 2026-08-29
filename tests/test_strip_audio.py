"""
tests/test_strip_audio.py — La décision audio survit au retrait du Dolby Vision.

Le chemin STRIP_DV remuxait par `mkvmerge -o <sortie> <video_nodv> --no-video
<source>`. Aucune décision audio ne lui était transmise : l'écran annonçait
« → eac3 » et un titre corrigé, la sortie gardait le TrueHD et son ancien nom.
Trois des quatre lignes de la table d'IE-15 étaient ignorées en MKV.

Ce que ces tests verrouillent :

- un transcodage passe par une étape ffmpeg à part, parce que mkvmerge ne sait
  que recopier — et l'audio de la source est alors intégralement remplacée ;
- une exclusion seule ne déclenche aucune passe : mkvmerge sait ne pas prendre
  une piste, et recopier des gigaoctets pour en écarter un serait absurde ;
- le MP4 n'a jamais besoin de passe : ffmpeg y recompose déjà le fichier.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core import dovi
from core.decision import AudioAction, AudioDecision
from core.encoder import audio_pass_needed, build_audio_command
from core.muxer import build_strip_command
from core.scanner import AudioTrack


def _piste(index, codec, canaux=6, langue="fre", titre="", debit=640_000):
    return AudioTrack(index=index, codec=codec, channels=canaux,
                      language=langue, title=titre, bitrate=debit)


def _copy(index, **kw):
    return AudioDecision(track=_piste(index, "ac3", **kw), action=AudioAction.COPY,
                         reason="", output_codec="copy", output_bitrate=0)


def _transcode(index, **kw):
    return AudioDecision(
        track=_piste(index, "truehd", titre="ENG VO : TrueHD 5.1",
                     debit=3_501_000, **kw),
        action=AudioAction.TRANSCODE, reason="", output_codec="eac3",
        output_bitrate=3_501_000)


def _exclue(index, **kw):
    return AudioDecision(track=_piste(index, "dts", **kw), action=AudioAction.EXCLUDE,
                         reason="", output_codec="", output_bitrate=0)


# ─── Quand la passe audio est nécessaire ──────────────────────────────────────

def test_un_transcodage_impose_la_passe():
    assert audio_pass_needed([_copy(0), _transcode(1)]) is True


def test_une_recopie_seule_ne_l_impose_pas():
    assert audio_pass_needed([_copy(0), _copy(1)]) is False


def test_une_exclusion_seule_ne_l_impose_pas():
    """mkvmerge sait ne pas prendre une piste ; recopier pour ça serait absurde."""
    assert audio_pass_needed([_copy(0), _exclue(1)]) is False


# ─── La commande de transcodage ───────────────────────────────────────────────

def test_la_passe_ne_prend_que_les_pistes_gardees(tmp_path):
    cmd = build_audio_command(tmp_path / "src.mkv", tmp_path / "a.mka",
                              [_copy(0), _exclue(1), _transcode(2)])
    assert "-map" in cmd
    maps = [cmd[i + 1] for i, x in enumerate(cmd) if x == "-map"]
    assert maps == ["0:a:0", "0:a:2"], "la piste exclue ne doit pas être mappée"


def test_la_passe_recopie_ce_qui_n_a_pas_a_etre_transcode(tmp_path):
    cmd = build_audio_command(tmp_path / "src.mkv", tmp_path / "a.mka",
                              [_copy(0), _transcode(1)])
    assert cmd[cmd.index("-c:a:0") + 1] == "copy"
    assert cmd[cmd.index("-c:a:1") + 1] == "eac3"
    assert cmd[cmd.index("-b:a:1") + 1] == "3501000"


def test_la_passe_corrige_le_titre_de_la_piste_transcodee(tmp_path):
    """« ENG VO : TrueHD 5.1 » sur une piste E-AC3 est un mensonge visible."""
    cmd = build_audio_command(tmp_path / "src.mkv", tmp_path / "a.mka",
                              [_transcode(0)])
    titre = cmd[cmd.index("-metadata:s:a:0") + 1]
    assert "TrueHD" not in titre and "E-AC3" in titre


def test_la_passe_ne_touche_ni_video_ni_sous_titres(tmp_path):
    cmd = build_audio_command(tmp_path / "src.mkv", tmp_path / "a.mka", [_copy(0)])
    assert "-vn" in cmd and "-sn" in cmd


# ─── Le remux Matroska ────────────────────────────────────────────────────────

def test_l_audio_transcodee_remplace_celle_de_la_source(tmp_path):
    cmd = build_strip_command(tmp_path / "v.hevc", tmp_path / "src.mkv",
                              tmp_path / "out.mkv",
                              audio_source=tmp_path / "a.mka")
    assert "--no-audio" in cmd, "la source ne doit plus fournir l'audio"
    assert str(tmp_path / "a.mka") in cmd
    assert cmd.index("--no-audio") < cmd.index(str(tmp_path / "src.mkv"))


def test_sans_transcodage_les_pistes_gardees_sont_nommees(tmp_path):
    cmd = build_strip_command(tmp_path / "v.hevc", tmp_path / "src.mkv",
                              tmp_path / "out.mkv", audio_indices=[0, 2])
    assert cmd[cmd.index("--audio-tracks") + 1] == "0,2"
    assert "--no-audio" not in cmd


def test_les_sous_titres_ecartes_n_entrent_pas(tmp_path):
    cmd = build_strip_command(tmp_path / "v.hevc", tmp_path / "src.mkv",
                              tmp_path / "out.mkv", sous_titres=[1])
    assert cmd[cmd.index("--subtitle-tracks") + 1] == "1"


def test_aucun_sous_titre_garde_donne_no_subtitles(tmp_path):
    cmd = build_strip_command(tmp_path / "v.hevc", tmp_path / "src.mkv",
                              tmp_path / "out.mkv", sous_titres=[])
    assert "--no-subtitles" in cmd


def test_sans_decision_le_comportement_ne_change_pas(tmp_path):
    """Appel historique : toutes les pistes de la source, comme avant."""
    cmd = build_strip_command(tmp_path / "v.hevc", tmp_path / "src.mkv",
                              tmp_path / "out.mkv")
    for option in ("--no-audio", "--audio-tracks", "--subtitle-tracks",
                   "--no-subtitles"):
        assert option not in cmd


# ─── Le remux MP4 ─────────────────────────────────────────────────────────────

def test_le_mp4_transcode_dans_la_meme_passe(tmp_path):
    cmd = dovi.build_strip_remux_mp4(
        tmp_path / "v.hevc", tmp_path / "src.mkv", tmp_path / "out.mp4",
        fps="24/1", sous_titres=[], audio=[_copy(0), _exclue(1), _transcode(2)])
    maps = [cmd[i + 1] for i, x in enumerate(cmd) if x == "-map"]
    assert maps == ["0:v:0", "1:a:0", "1:a:2"]
    assert cmd[cmd.index("-c:a:1") + 1] == "eac3"
    assert "-metadata:s:a:1" in cmd


def test_le_mp4_sans_decision_recopie_tout(tmp_path):
    cmd = dovi.build_strip_remux_mp4(
        tmp_path / "v.hevc", tmp_path / "src.mkv", tmp_path / "out.mp4",
        fps="24/1", sous_titres=[])
    assert "1:a?" in cmd


# ─── IE-48 — le forçage à 48 kHz visait le mauvais flux ──────────────────────
#
# `audio_args` écrivait `-ar:{i}`, un spécificateur **nu** : il désigne le flux
# de sortie n° i tous types confondus, là où toutes les options voisines
# (`-c:a:{i}`, `-b:a:{i}`, `-ac:a:{i}`) désignent la i-ème piste audio.
#
# `build_command` et `build_strip_remux_mp4` mappent la vidéo en premier : le
# flux 0 est donc la vidéo. `-ar:0` tombait dessus et était ignoré, `-ar:1`
# tombait sur la première piste audio alors qu'il était écrit pour la seconde.
# Le réglage glissait d'un cran, silencieusement, et la piste AAC pour laquelle
# il avait été émis ne le recevait jamais.
#
# Le défaut était invisible sur le troisième chemin : `build_audio_command`
# n'écrit que de l'audio (`-vn -sn -dn`), le flux 0 y **est** la piste 0, et la
# forme nue s'y trouvait juste par accident. Un test qui n'aurait couvert que
# celui-là aurait été vert sur les trois.


def _aac(index, **kw):
    """Une piste transcodée en AAC — le seul cas qui force la fréquence."""
    return AudioDecision(
        track=_piste(index, "dts", **kw), action=AudioAction.TRANSCODE,
        reason="", output_codec="aac", output_bitrate=192_000)


def _valeur_de(cmd: list[str], option: str) -> str:
    return cmd[cmd.index(option) + 1]


def test_le_forcage_48k_nomme_le_type_de_flux():
    from core.encoder import audio_args

    args = audio_args([_aac(0), _aac(1)])
    assert _valeur_de(args, "-ar:a:0") == "48000"
    assert _valeur_de(args, "-ar:a:1") == "48000"
    assert "-ar:0" not in args and "-ar:1" not in args, args


def test_le_forcage_48k_vise_la_bonne_piste_a_l_encodage(tmp_path):
    """Vidéo mappée en tête : la forme nue visait la vidéo, puis l'audio #0."""
    from core.decision import decide
    from core.encoder import build_command
    from core.platform import GPU, OS, PlatformProfile
    from core.profiles import Profile
    from core.scanner import VideoInfo

    p = tmp_path / "film.mkv"
    p.write_bytes(b"")
    info = VideoInfo(
        path=p, width=1920, height=1080, bitrate=8_000_000, codec="h264",
        duration=3600.0, frame_count=0, dv_profile=None,
        audio_tracks=[_piste(0, "ac3"), _piste(1, "dts")], subtitle_tracks=[])
    profil = Profile(id="test", data={
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps": 8000, "audio_languages": ["fre"],
        "audio_copy_compatible": True, "preserve_hd_audio": False})
    plat = PlatformProfile(os=OS.WINDOWS, gpu=GPU.NVIDIA, hwaccel="cuda",
                           encoder_hevc="hevc_nvenc", encoder_h264="h264_nvenc",
                           encoder_av1="av1_nvenc")

    dec = decide(info, profil)
    # Seule la seconde piste est transcodée en AAC : c'est elle, et elle seule,
    # qui doit recevoir la fréquence.
    dec.audio = [_copy(0), _aac(1)]
    cmd = build_command(dec, plat)

    assert cmd.index("-map") < cmd.index("-ar:a:1"), "la vidéo est bien mappée avant"
    assert _valeur_de(cmd, "-ar:a:1") == "48000"
    assert "-ar:1" not in cmd, "cette forme visait la piste audio #0, une recopie"
    assert "-ar:a:0" not in cmd, "la piste recopiée n'a rien à rééchantillonner"


def test_le_mp4_du_retrait_dv_vise_aussi_la_bonne_piste(tmp_path):
    """Même disposition, même défaut : `build_strip_remux_mp4` mappe la vidéo en tête."""
    cmd = dovi.build_strip_remux_mp4(
        tmp_path / "nodv.hevc", tmp_path / "src.mkv", tmp_path / "out.mp4",
        fps="24/1", sous_titres=[], audio=[_copy(0), _aac(1)])
    assert _valeur_de(cmd, "-ar:a:1") == "48000"
    assert "-ar:1" not in cmd, cmd


def test_la_passe_audio_seule_reste_juste(tmp_path):
    """Le chemin où la forme nue était juste par accident : il doit le rester.

    `build_audio_command` n'écrit que de l'audio, le flux 0 y est la piste 0.
    La forme par type y donne le même résultat — c'est ce qui doit être vérifié,
    pas l'inverse.
    """
    cmd = build_audio_command(tmp_path / "src.mkv", tmp_path / "out.mka",
                              [_copy(0), _aac(1)])
    assert _valeur_de(cmd, "-ar:a:1") == "48000"
    assert "-vn" in cmd and "-sn" in cmd
