"""
tests/test_greffes_encodage.py — Pistes greffées à l'encodage et au mux (IE-125).

Constats CR-20, CR-23, CR-25 et CR-50 de `revue_code_2026-10-08.md`, et
l'arbitrage de la revue sur l'audio externe : une piste greffée suit la règle
audio du profil, comme une piste de la source.

Les cas de bout en bout passent par le ffmpeg et le mkvmerge de `bin/`.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from core import encoder, muxer, scanner
from core import sous_titres as ST
from core.decision import AudioAction, audio_greffee, decide, force_skip_to_encode
from core.encoder import build_command
from core.muxer import ExternalTrack, IdentifiedTrack, TrackKind
from core.platform import GPU, OS, PlatformProfile
from core.profiles import Profile
from core.scanner import AudioTrack, VideoInfo

_BIN = Path(__file__).resolve().parent.parent / "bin"
_FFMPEG, _FFPROBE, _MKVMERGE = (_BIN / "ffmpeg.exe", _BIN / "ffprobe.exe",
                                _BIN / "mkvmerge.exe")
outils = pytest.mark.skipif(
    not (_FFMPEG.exists() and _FFPROBE.exists() and _MKVMERGE.exists()),
    reason="outils du projet absents")

SRT_ACCENTS = ("1\r\n00:00:00,200 --> 00:00:00,600\r\nÉté à Paris\r\n\r\n"
               "2\r\n00:00:00,800 --> 00:00:01,200\r\nBonjour\r\n\r\n"
               "3\r\n00:00:01,400 --> 00:00:01,800\r\nDéjà vu\r\n")


def _plat() -> PlatformProfile:
    return PlatformProfile(os=OS.WINDOWS, gpu=GPU.NONE, hwaccel=None,
                           encoder_hevc="libx265", encoder_h264="libx264",
                           encoder_av1="libaom-av1")


def _profil(**extra) -> Profile:
    return Profile(id="test", data={
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps": 8000, "audio_languages": ["fre", "eng"],
        "audio_copy_compatible": True, "preserve_hd_audio": False,
        "preset_encoder": "ultrafast", **extra,
    })


@pytest.fixture
def vrais_outils():
    encoder.set_ffmpeg_path(str(_FFMPEG))
    scanner.set_ffprobe_path(str(_FFPROBE))
    muxer.set_mkvmerge_path(str(_MKVMERGE))


def _ff(*args: str) -> None:
    subprocess.run([str(_FFMPEG), "-y", "-loglevel", "error", *args],
                   check=True, stdin=subprocess.DEVNULL, capture_output=True)


def _flux(chemin: Path) -> list[dict]:
    r = subprocess.run([str(_FFPROBE), "-v", "error", "-print_format", "json",
                        "-show_streams", str(chemin)],
                       capture_output=True, encoding="utf-8", check=True)
    return json.loads(r.stdout)["streams"]


def _video_mkv(dossier: Path, nom: str, *extra: str) -> Path:
    """Deux secondes d'image et de son, en 1080p (sinon la décision saute)."""
    sortie = dossier / nom
    _ff("-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=25:duration=2",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        *extra, "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "20M",
        "-c:a", "aac", str(sortie))
    return sortie


def _decide(source: Path):
    """La décision d'une vidéo de test, encodée même sous le débit cible."""
    return force_skip_to_encode(decide(scanner.scan(source), _profil()))


def _encoder(dec) -> None:
    cmd = build_command(dec, _plat())
    assert cmd
    r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr[-800:]


def _repliques(chemin: Path, flux: int = 0) -> str:
    r = subprocess.run([str(_FFMPEG), "-loglevel", "error", "-i", str(chemin),
                        "-map", f"0:s:{flux}", "-f", "srt", "-"],
                       capture_output=True, check=True)
    return r.stdout.decode("utf-8")


# ─── CR-20 : polices jointes ─────────────────────────────────────────────────

@outils
def test_l_encodage_mkv_garde_les_polices_jointes(tmp_path, vrais_outils):
    ass = tmp_path / "st.ass"
    ass.write_text("[Script Info]\nScriptType: v4.00+\n\n[V4+ Styles]\n"
                   "Format: Name, Fontname, Fontsize\nStyle: Default,Arial,20\n\n"
                   "[Events]\nFormat: Layer, Start, End, Style, Text\n"
                   "Dialogue: 0,0:00:00.20,0:00:01.00,Default,Bonjour\n",
                   encoding="utf-8")
    police = tmp_path / "police.ttf"
    police.write_bytes(b"\x00\x01\x00\x00" + b"\x00" * 60)
    source = _video_mkv(tmp_path, "anime.mkv", "-i", str(ass),
                        "-attach", str(police),
                        "-metadata:s:t", "mimetype=application/x-truetype-font",
                        "-map", "0", "-map", "1", "-map", "2", "-c:s", "copy")
    dec = _decide(source)
    assert dec.output_container == ".mkv"
    _encoder(dec)
    def joints(chemin: Path) -> list[str]:
        return [s["tags"]["filename"] for s in _flux(chemin)
                if s["codec_type"] == "attachment"]
    assert len(joints(source)) == 1
    assert joints(dec.output_path) == joints(source)


def test_le_mp4_ne_demande_pas_de_pieces_jointes(tmp_path):
    p = tmp_path / "film.mkv"
    p.write_bytes(b"")
    info = VideoInfo(path=p, width=1920, height=1080, bitrate=20_000_000,
                     codec="h264", duration=60.0, frame_count=0, dv_profile=None,
                     audio_tracks=[AudioTrack(index=0, codec="aac", channels=2,
                                              language="fre", title="",
                                              bitrate=192_000)],
                     subtitle_tracks=[])
    dec = decide(info, _profil())
    assert dec.output_container == ".mp4"
    assert "0:t?" not in build_command(dec, _plat())


# ─── CR-50 : un .srt en cp1252 ───────────────────────────────────────────────

def test_l_encodage_d_un_srt_est_detecte(tmp_path):
    cp = tmp_path / "a.srt"
    cp.write_bytes(SRT_ACCENTS.encode("cp1252"))
    u8 = tmp_path / "b.srt"
    u8.write_bytes(SRT_ACCENTS.encode("utf-8"))
    vob = tmp_path / "c.sub"
    vob.write_bytes(b"\x00\x00\x01\xba" + bytes(range(256)))
    assert ST.encodage_texte(cp) == "CP1252"
    assert ST.encodage_texte(u8) == "UTF-8"
    assert ST.encodage_texte(vob) is None
    assert ST.encodage_texte(tmp_path / "d.mkv") is None


@outils
def test_un_srt_cp1252_greffe_a_l_encodage_garde_ses_accents(tmp_path, vrais_outils):
    source = _video_mkv(tmp_path, "film.mkv")
    srt = tmp_path / "film.fr.srt"
    srt.write_bytes(SRT_ACCENTS.encode("cp1252"))
    dec = _decide(source)
    dec.external_tracks.append(ExternalTrack(
        source_path=srt, source_tid=0, kind=TrackKind.SUBTITLE,
        codec="SubRip/SRT", language="fre"))
    assert dec.output_container == ".mp4"
    _encoder(dec)
    texte = _repliques(dec.output_path)
    for ligne in ("Été à Paris", "Bonjour", "Déjà vu"):
        assert ligne in texte, texte


@outils
def test_un_srt_cp1252_greffe_au_mux_garde_ses_accents(tmp_path, vrais_outils):
    source = _video_mkv(tmp_path, "film.mkv")
    srt = tmp_path / "film.fr.srt"
    srt.write_bytes(SRT_ACCENTS.encode("cp1252"))
    sortie = tmp_path / "film.mux.mkv"
    cmd = muxer.build_mux_command(source, [ExternalTrack(
        source_path=srt, source_tid=0, kind=TrackKind.SUBTITLE,
        codec="SubRip/SRT", language="fre")], sortie)
    r = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
    assert muxer.mkvmerge_reussi(r.returncode, sortie), r.stdout[-500:]
    texte = _repliques(sortie)
    for ligne in ("Été à Paris", "Bonjour", "Déjà vu"):
        assert ligne in texte, texte


def test_mkvmerge_recoit_le_jeu_de_caracteres_d_un_srt_utf8(tmp_path):
    """Sans BOM, mkvmerge ne devine pas l'UTF-8 sous tous les systèmes : il
    est toujours dit."""
    srt = tmp_path / "vf.srt"
    srt.write_bytes(SRT_ACCENTS.encode("utf-8"))
    args = muxer._track_options(ExternalTrack(
        source_path=srt, source_tid=0, kind=TrackKind.SUBTITLE, language="fre"))
    assert args[args.index("--sub-charset") + 1] == "0:UTF-8"


# ─── CR-23 / CR-25 : une seule piste par défaut par type ─────────────────────

@outils
def test_un_sous_titre_greffe_par_defaut_retire_celui_de_la_source(tmp_path,
                                                                   vrais_outils):
    st_en = tmp_path / "en.srt"
    st_en.write_text("1\n00:00:00,200 --> 00:00:01,000\nHello\n", encoding="utf-8")
    source = _video_mkv(tmp_path, "film.mkv", "-i", str(st_en),
                        "-map", "0", "-map", "1", "-map", "2",
                        "-metadata:s:s:0", "language=eng",
                        "-disposition:s:0", "default")
    srt = tmp_path / "film.fr.srt"
    srt.write_bytes(SRT_ACCENTS.encode("utf-8"))
    dec = _decide(source)
    dec.external_tracks.append(ExternalTrack(
        source_path=srt, source_tid=0, kind=TrackKind.SUBTITLE,
        language="fre", is_default=True))
    _encoder(dec)
    subs = [s for s in _flux(dec.output_path) if s["codec_type"] == "subtitle"]
    defaut = [s["tags"].get("language") for s in subs if s["disposition"]["default"]]
    assert defaut == ["fre"], subs


@outils
def test_au_mux_les_greffees_par_defaut_retirent_le_drapeau_de_la_source(
        tmp_path, vrais_outils):
    st_en = tmp_path / "en.srt"
    st_en.write_text("1\n00:00:00,200 --> 00:00:01,000\nHello\n", encoding="utf-8")
    source = _video_mkv(tmp_path, "film.mkv", "-i", str(st_en),
                        "-map", "0", "-map", "1", "-map", "2",
                        "-metadata:s:a:0", "language=eng",
                        "-metadata:s:s:0", "language=eng",
                        "-disposition:a:0", "default", "-disposition:s:0", "default")
    vf = tmp_path / "vf.mka"
    _ff("-f", "lavfi", "-i", "sine=frequency=880:duration=2", "-c:a", "ac3",
        str(vf))
    srt = tmp_path / "film.fr.srt"
    srt.write_bytes(SRT_ACCENTS.encode("utf-8"))
    sortie = tmp_path / "film.mux.mkv"
    cmd = muxer.build_mux_command(source, [
        ExternalTrack(source_path=vf, source_tid=0, kind=TrackKind.AUDIO,
                      language="fre", is_default=True),
        ExternalTrack(source_path=srt, source_tid=0, kind=TrackKind.SUBTITLE,
                      language="fre", is_default=True),
    ], sortie)
    r = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
    assert muxer.mkvmerge_reussi(r.returncode, sortie), r.stdout[-500:]
    for type_ in ("audio", "subtitle"):
        flux = [s for s in _flux(sortie) if s["codec_type"] == type_]
        defaut = [s["tags"].get("language") for s in flux
                  if s["disposition"]["default"]]
        assert defaut == ["fre"], (type_, flux)


def test_le_retrait_dv_retire_le_drapeau_sur_l_audio_produite_a_part(
        tmp_path, monkeypatch):
    """Quand l'audio vient d'un `.mka` produit à part, c'est lui qui perd le
    drapeau, pas la source dont l'audio n'est pas prise."""
    pistes = {
        "source.mkv": [IdentifiedTrack(tid=1, kind=TrackKind.AUDIO, codec="AC-3",
                                       language="eng"),
                       IdentifiedTrack(tid=2, kind=TrackKind.SUBTITLE,
                                       codec="SubRip", language="eng")],
        "audio.mka":  [IdentifiedTrack(tid=0, kind=TrackKind.AUDIO, codec="AC-3",
                                       language="eng")],
        "vf.mka":     [IdentifiedTrack(tid=0, kind=TrackKind.AUDIO, codec="AC-3",
                                       language="fre")],
    }
    monkeypatch.setattr(muxer, "identify", lambda p: pistes.get(p.name, []))
    for nom in pistes:
        (tmp_path / nom).write_bytes(b"")
    cmd = muxer.build_strip_command(
        tmp_path / "v.hevc", tmp_path / "source.mkv", tmp_path / "sortie.mkv",
        tracks=[ExternalTrack(source_path=tmp_path / "vf.mka", source_tid=0,
                              kind=TrackKind.AUDIO, language="fre",
                              is_default=True)],
        audio_source=tmp_path / "audio.mka")
    i_src, i_audio = cmd.index(str(tmp_path / "source.mkv")), cmd.index(
        str(tmp_path / "audio.mka"))
    avant_source = cmd[:i_src]
    assert "1:0" not in avant_source            # l'audio de la source n'est pas prise
    assert cmd[i_src + 1:i_audio].count("--default-track-flag") == 1
    assert "0:0" in cmd[i_src + 1:i_audio]


# ─── Arbitrage : l'audio greffée suit la règle du profil ─────────────────────

def _donneur_audio(monkeypatch, tmp_path, codec: str, canaux: int,
                   debit: int = 1_509_000, profil: str = "") -> Path:
    p = tmp_path / "vf.mkv"
    p.write_bytes(b"")
    monkeypatch.setattr(muxer, "identify", lambda _p: [
        IdentifiedTrack(tid=1, kind=TrackKind.AUDIO, codec=codec, language="fre")])
    monkeypatch.setattr(scanner, "pistes_audio", lambda _p: [AudioTrack(
        index=0, codec=codec, channels=canaux, language="fre", title="",
        bitrate=debit, profile=profil)])
    return p


def _commande_greffe(tmp_path, donneur: Path, profil: Profile, **piste) -> list[str]:
    p = tmp_path / "film.mkv"
    p.write_bytes(b"")
    info = VideoInfo(path=p, width=1920, height=1080, bitrate=20_000_000,
                     codec="h264", duration=60.0, frame_count=0, dv_profile=None,
                     audio_tracks=[AudioTrack(index=0, codec="eac3", channels=6,
                                              language="eng", title="",
                                              bitrate=640_000)],
                     subtitle_tracks=[])
    dec = decide(info, profil)
    dec.external_tracks.append(ExternalTrack(
        source_path=donneur, source_tid=1, kind=TrackKind.AUDIO,
        language="fre", **piste))
    return build_command(dec, _plat())


def _option(cmd: list[str], nom: str) -> str:
    return cmd[cmd.index(nom) + 1]


def test_un_dts_greffe_est_transcode_comme_celui_de_la_source(tmp_path, monkeypatch):
    donneur = _donneur_audio(monkeypatch, tmp_path, "dts", 6)
    cmd = _commande_greffe(tmp_path, donneur, _profil(audio_surround_kbps=448),
                           track_name="VF DTS 5.1")
    assert _option(cmd, "-c:a:1") == "ac3"
    assert _option(cmd, "-b:a:1") == "448000"
    titres = [x for i, x in enumerate(cmd) if cmd[i - 1] == "-metadata:s:a:1"]
    assert "title=VF AC3 5.1" in titres, titres
    assert "title=VF DTS 5.1" not in titres


def test_un_opus_stereo_greffe_part_en_aac(tmp_path, monkeypatch):
    donneur = _donneur_audio(monkeypatch, tmp_path, "opus", 2, debit=128_000)
    cmd = _commande_greffe(tmp_path, donneur, _profil())
    assert _option(cmd, "-c:a:1") == "aac"
    assert _option(cmd, "-ar:a:1") == "48000"


def test_un_eac3_greffe_compatible_reste_recopie(tmp_path, monkeypatch):
    donneur = _donneur_audio(monkeypatch, tmp_path, "eac3", 6, debit=640_000)
    cmd = _commande_greffe(tmp_path, donneur, _profil())
    assert _option(cmd, "-c:a:1") == "copy"


def test_une_truehd_greffee_garde_le_mp4_sauf_preserve_hd(tmp_path, monkeypatch):
    donneur = _donneur_audio(monkeypatch, tmp_path, "truehd", 8, debit=4_000_000)
    p = tmp_path / "film.mkv"
    p.write_bytes(b"")
    info = VideoInfo(path=p, width=1920, height=1080, bitrate=20_000_000,
                     codec="h264", duration=60.0, frame_count=0, dv_profile=None,
                     audio_tracks=[], subtitle_tracks=[])
    for preserve, conteneur, action in ((False, ".mp4", AudioAction.TRANSCODE),
                                        (True, ".mkv", AudioAction.COPY)):
        profil = _profil(preserve_hd_audio=preserve)
        dec = decide(info, profil)
        ext = ExternalTrack(source_path=donneur, source_tid=1, kind=TrackKind.AUDIO,
                            codec="TrueHD", language="fre")
        dec.external_tracks.append(ext)
        assert dec.output_container == conteneur
        assert audio_greffee(ext, profil).action == action


def test_un_donneur_audio_illisible_est_refuse(tmp_path, monkeypatch):
    donneur = _donneur_audio(monkeypatch, tmp_path, "dts", 6)
    monkeypatch.setattr(scanner, "pistes_audio", lambda _p: [])
    with pytest.raises(ValueError, match="vf.mkv"):
        _commande_greffe(tmp_path, donneur, _profil())
