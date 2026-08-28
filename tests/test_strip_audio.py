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
