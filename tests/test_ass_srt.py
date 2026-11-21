"""
tests/test_ass_srt.py — ASS/SSA convertis en SRT (IE-204).

Jellyfin incrustait l'ASS à la lecture sur un client qui ne le rend pas
(Firefox, raison du transcodage : le sous-titre). Avec `ass_to_srt`, un ASS de
dialogue devient un SRT ; une piste de panneaux ou de chansons reste en ASS.
Les polices jointes partent quand plus aucun ASS ne sort.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from core import ass, scanner
from core.decision import VideoAction, ass_converti, decide, force_skip_to_encode
from core.encoder import build_command
from core.profiles import Profile
from core.scanner import AudioTrack, SubtitleTrack, VideoInfo
from tests.test_greffes_encodage import (_flux, _ff, _plat, _repliques,  # noqa: F401
                                         _video_mkv, outils, vrais_outils)
from tests.test_greffes_encodage import _FFMPEG

_ENTETE = ("[Script Info]\nScriptType: v4.00+\n\n[V4+ Styles]\n"
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
           "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
           "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
           "MarginL, MarginR, MarginV, Encoding\n"
           "Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
           "0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1\n"
           "Style: Haut,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
           "0,-1,0,0,100,100,0,0,1,2,0,8,10,10,10,1\n\n"
           "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, "
           "MarginV, Effect, Text\n")


def _srt(*dialogues: str) -> str:
    return ass.ass_vers_srt(_ENTETE + "\n".join(dialogues) + "\n")[0]


# ─── La conversion ───────────────────────────────────────────────────────────

def test_texte_retours_et_virgules():
    srt = _srt("Dialogue: 0,0:00:01.50,0:00:03.00,Default,,0,0,0,,Oui, "
               "bien sûr\\Nseconde ligne")
    assert srt == "1\n00:00:01,500 --> 00:00:03,000\nOui, bien sûr\nseconde ligne\n"


def test_styles_couleurs_et_positions_partent():
    srt = _srt("Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,"
               "{\\pos(100,100)\\c&H0000FF&\\fs60\\blur3\\bord2}Positionné")
    assert srt.splitlines()[2] == "Positionné"
    assert "font" not in srt and "{" not in srt


def test_italique_et_gras_restent():
    srt = _srt("Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,"
               "{\\b1}Été{\\b0} à {\\i1}Paris{\\i0}")
    assert srt.splitlines()[2] == "<b>Été</b> à <i>Paris</i>"


def test_style_italique_et_haut():
    """L'italique et l'alignement du style comptent, pas seulement ceux de
    la ligne : seconv perdait les deux."""
    srt = _srt("Dialogue: 0,0:00:01.00,0:00:02.00,Haut,,0,0,0,,En haut")
    assert srt.splitlines()[2] == "{\\an8}<i>En haut</i>"


def test_un_dessin_ne_devient_pas_du_texte():
    """ffmpeg écrivait « m 0 0 l 100 0 … », seconv une réplique vide."""
    srt = _srt("Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,"
               "{\\p1}m 0 0 l 100 0 100 100 0 100{\\p0}",
               "Dialogue: 0,0:00:03.00,0:00:04.00,Default,,0,0,0,,Texte")
    assert "m 0 0" not in srt
    assert ass.ass_vers_srt(_ENTETE + "Dialogue: 0,0:00:01.00,0:00:02.00,"
                            "Default,,0,0,0,,{\\p1}m 0 0 l 1 1\n")[1] == 0
    assert srt.splitlines()[2] == "Texte"


def test_commentaires_ecartes_et_ordre_des_temps():
    srt = _srt("Dialogue: 0,0:00:05.00,0:00:06.00,Default,,0,0,0,,Deux",
               "Comment: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,note",
               "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,{\\k20}Un")
    assert [l for l in srt.splitlines() if l and not l[0].isdigit()] == ["Un", "Deux"]


def test_panneaux_reperes_par_le_titre():
    for titre in ("Signs", "Signs & Songs", "FR Songs", "Karaoké", "S&S",
                  "Panneaux", "Chansons"):
        assert ass.piste_de_panneaux(titre), titre
    for titre in ("", "FR Full", "Dialogues", "Forced", "Designer"):
        assert not ass.piste_de_panneaux(titre), titre


# ─── La décision ─────────────────────────────────────────────────────────────

def _profil(**extra) -> Profile:
    return Profile(id="t", data={"bitrate_1080p_kbps": 5000,
                                 "bitrate_720p_kbps": 2000,
                                 "audio_languages": ["fre", "eng"], **extra})


def _info(tmp_path: Path, sous_titres, bitrate=3_000_000, dv=None) -> VideoInfo:
    p = tmp_path / "Anime.1080p.mkv"
    p.write_bytes(b"")
    return VideoInfo(
        path=p, width=1920, height=1080, bitrate=bitrate, codec="hevc",
        duration=1400.0, frame_count=0, dv_profile=dv,
        audio_tracks=[AudioTrack(index=0, codec="aac", channels=2,
                                 language="jpn", title="", bitrate=128_000)],
        subtitle_tracks=list(sous_titres))


def _ass(index, titre="", langue="fre") -> SubtitleTrack:
    return SubtitleTrack(index=index, codec="ass", language=langue, title=titre)


def test_sans_la_cle_rien_ne_change(tmp_path):
    dec = decide(_info(tmp_path, [_ass(0)]), _profil())
    assert dec.sous_titres_ass == []
    assert dec.video.action == VideoAction.SKIP


def test_un_ass_fait_remuxer(tmp_path):
    dec = decide(_info(tmp_path, [_ass(0, "FR Full")]), _profil(ass_to_srt=True))
    assert [st.index for st in dec.sous_titres_ass] == [0]
    assert dec.video.action == VideoAction.REMUX
    assert "ASS" in dec.video.reason


def test_la_piste_de_panneaux_reste(tmp_path):
    st = [_ass(0, "FR Full"), _ass(1, "FR Signs & Songs")]
    dec = decide(_info(tmp_path, st), _profil(ass_to_srt=True))
    assert [s.index for s in dec.sous_titres_ass] == [0]
    assert dec.output_container == ".mkv"


def test_retrait_dv_pas_de_conversion(tmp_path, monkeypatch):
    """Le retrait du RPU écrit la sortie sans ffmpeg : rien n'y convertirait."""
    from core import decision
    monkeypatch.setattr(decision, "_STRIP_DV_AVAILABLE", True)
    info = _info(tmp_path, [_ass(0)], dv=8)
    info.dv_bl_compat = 1
    info.color_transfer = "smpte2084"
    dec = decide(info, _profil(dolby_vision="hdr10", ass_to_srt=True))
    assert dec.video.action == VideoAction.STRIP_DV
    assert dec.sous_titres_ass == []
    assert not ass_converti(dec, info.subtitle_tracks[0])


# ─── Les polices jointes ─────────────────────────────────────────────────────

def _polices_retirees(cmd: list[str]) -> bool:
    return any(a.startswith("-0:t:m:mimetype:") for a in cmd)


def test_polices_retirees_quand_tous_les_ass_sont_convertis(tmp_path):
    dec = force_skip_to_encode(decide(_info(tmp_path, [_ass(0), _ass(1, langue="eng")]),
                                      _profil(ass_to_srt=True)))
    cmd = build_command(dec, _plat(), sous_titres_refaits={
        0: tmp_path / "a0.srt", 1: tmp_path / "a1.srt"})
    assert "0:t?" in cmd and _polices_retirees(cmd)


def test_polices_gardees_si_un_ass_reste(tmp_path):
    st = [_ass(0), _ass(1, "Signs")]
    dec = force_skip_to_encode(decide(_info(tmp_path, st), _profil(ass_to_srt=True)))
    cmd = build_command(dec, _plat(), sous_titres_refaits={0: tmp_path / "a0.srt"})
    assert "0:t?" in cmd and not _polices_retirees(cmd)


def test_polices_gardees_sans_conversion(tmp_path):
    dec = force_skip_to_encode(decide(_info(tmp_path, [_ass(0)]), _profil()))
    cmd = build_command(dec, _plat())
    assert not _polices_retirees(cmd)


# ─── De bout en bout ─────────────────────────────────────────────────────────

@outils
def test_un_ass_ressort_en_srt_sans_police(tmp_path, vrais_outils):
    st = tmp_path / "st.ass"
    st.write_text(_ENTETE + "Dialogue: 0,0:00:00.20,0:00:01.00,Default,,0,0,0,,"
                  "{\\fs80\\c&H0000FF&}Été{\\p1}m 0 0 l 9 9{\\p0}\n", encoding="utf-8")
    police = tmp_path / "police.ttf"
    police.write_bytes(b"\x00\x01\x00\x00" + b"\x00" * 60)
    notes = tmp_path / "notes.txt"
    notes.write_text("notes", encoding="utf-8")
    source = _video_mkv(tmp_path, "anime.mkv", "-i", str(st),
                        "-attach", str(police), "-attach", str(notes),
                        "-metadata:s:t:0", "mimetype=application/x-truetype-font",
                        "-metadata:s:t:1", "mimetype=text/plain",
                        "-map", "0", "-map", "1", "-map", "2", "-c:s", "copy",
                        "-metadata:s:s:0", "language=fre")
    dec = force_skip_to_encode(decide(scanner.scan(source), _profil(ass_to_srt=True)))
    pistes = dec.sous_titres_ass
    assert [p.index for p in pistes] == [0]

    cmd, chemins = ass.build_extraction(source, pistes, tmp_path, str(_FFMPEG))
    subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL, capture_output=True)
    assert ass.ecrire_srt(chemins[0]) == 1
    cmd = build_command(dec, _plat(), sous_titres_refaits={0: ass.sortie_srt(chemins[0])})
    r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr[-800:]

    flux = _flux(dec.output_path)
    sous_titres = [s for s in flux if s["codec_type"] == "subtitle"]
    assert [s["codec_name"] for s in sous_titres] == ["subrip"]
    assert sous_titres[0]["tags"]["language"] == "fre"
    assert [s["tags"]["mimetype"] for s in flux
            if s["codec_type"] == "attachment"] == ["text/plain"]
    texte = _repliques(dec.output_path)
    assert "Été" in texte and "m 0 0" not in texte and "font" not in texte
