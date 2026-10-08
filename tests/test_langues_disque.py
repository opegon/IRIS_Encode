"""
tests/test_langues_disque.py — Langues, cœur AC-3, DVB et télétexte (IE-119).

Quatre arbitrages de l'utilisateur, le 2026-10-08 :

- les langues qu'ffprobe ne lit pas sur un `.m2ts` viennent de mkvmerge (les
  `.clpi` du disque), pistes appariées par PID ;
- une piste dont la langue reste inconnue est **gardée** : on n'écarte que ce
  qu'on sait étranger aux langues voulues ;
- une TrueHD et son cœur AC-3 (même PID) ne font qu'une piste : la TrueHD si
  le profil garde le sans perte, sinon le cœur recopié ;
- `dvb_subtitle` est un sous-titre image comme un PGS ; le télétexte est
  toujours écarté.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core import muxer, scanner
from core.decision import AudioAction, decide
from core.encoder import build_command
from core.muxer import IdentifiedTrack, TrackKind
from core.platform import GPU, OS, PlatformProfile
from core.profiles import Profile
from core.scanner import AudioTrack, SubtitleTrack, VideoInfo

_PLAT = PlatformProfile(os=OS.WINDOWS, gpu=GPU.NONE, hwaccel=None,
                        encoder_hevc="libx265", encoder_h264="libx264",
                        encoder_av1="libsvtav1")


def _a(index, codec, langue="", canaux=6, pid=None) -> AudioTrack:
    return AudioTrack(index=index, codec=codec, channels=canaux, language=langue,
                      title="", bitrate=640_000, pid=pid)


def _s(index, codec, langue="", pid=None, titre="") -> SubtitleTrack:
    return SubtitleTrack(index=index, codec=codec, language=langue, title=titre, pid=pid)


def _info(tmp_path, audio=(), subs=(), nom="titre.m2ts") -> VideoInfo:
    p = tmp_path / nom
    p.write_bytes(b"")
    return VideoInfo(path=p, width=1920, height=1080, bitrate=30_000_000,
                     codec="h264", duration=3600.0, frame_count=0, dv_profile=None,
                     audio_tracks=list(audio), subtitle_tracks=list(subs))


def _profile(**over) -> Profile:
    data = {"bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
            "bitrate_4k_kbps": 12000, "keep_4k": True,
            "audio_languages": ["fre", "eng"], "audio_copy_compatible": True,
            "preserve_hd_audio": False}
    data.update(over)
    return Profile(id="test", data=data)


# ─── Langues par mkvmerge ─────────────────────────────────────────────────────

def _identifie(monkeypatch, pistes):
    monkeypatch.setattr(muxer, "identify", lambda path: pistes)


def test_les_langues_manquantes_viennent_de_mkvmerge_par_pid(monkeypatch):
    """L'ordre de mkvmerge n'est pas celui de ffprobe : seul le PID apparie."""
    _identifie(monkeypatch, [
        IdentifiedTrack(tid=2, kind=TrackKind.AUDIO, codec="AC-3", language="fre", number=0x1101),
        IdentifiedTrack(tid=1, kind=TrackKind.AUDIO, codec="PCM", language="eng", number=0x1100),
        IdentifiedTrack(tid=3, kind=TrackKind.SUBTITLE, codec="PGS", language="fre", number=0x1200),
    ])
    pistes = [_a(0, "pcm_bluray", pid=0x1100), _a(1, "truehd", pid=0x1101),
              _a(2, "ac3", pid=0x1101), _s(0, "hdmv_pgs_subtitle", pid=0x1200)]
    scanner._completer_langues(Path("t.m2ts"), pistes)
    assert [p.language for p in pistes] == ["eng", "fre", "fre", "fre"]


def test_une_langue_lue_n_est_jamais_remplacee(monkeypatch):
    _identifie(monkeypatch, [IdentifiedTrack(tid=1, kind=TrackKind.AUDIO, codec="AC-3",
                                             language="eng", number=0x1100)])
    pistes = [_a(0, "ac3", "fre", pid=0x1100), _a(1, "ac3", "und", pid=0x1100)]
    scanner._completer_langues(Path("t.m2ts"), pistes)
    assert [p.language for p in pistes] == ["fre", "eng"]


def test_sans_mkvmerge_rien_ne_change(monkeypatch):
    _identifie(monkeypatch, [])
    pistes = [_a(0, "ac3", pid=0x1100)]
    scanner._completer_langues(Path("t.m2ts"), pistes)
    assert pistes[0].language == ""


def test_mkvmerge_n_est_pas_appele_si_tout_est_connu(monkeypatch):
    appels = []
    monkeypatch.setattr(muxer, "identify", lambda path: appels.append(path) or [])
    scanner._completer_langues(Path("t.m2ts"), [_a(0, "ac3", "fre", pid=1)])
    assert appels == []


@pytest.mark.parametrize("nom, appele", [("t.m2ts", True), ("t.MTS", True),
                                         ("t.ts", False), ("t.mkv", False)])
def test_seuls_les_m2ts_consultent_mkvmerge(monkeypatch, tmp_path, nom, appele):
    """Sur un `.ts` TNT, mkvmerge lit la même table que ffprobe (mesuré)."""
    flux = [{"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080},
            {"codec_type": "audio", "codec_name": "ac3", "channels": 6, "id": "0x1100"}]
    monkeypatch.setattr(scanner, "_ffprobe_json",
                        lambda args: {"streams": flux, "format": {"duration": "60"}})
    monkeypatch.setattr(scanner, "_detect_dv", lambda path: (None, None))
    appels = []
    monkeypatch.setattr(scanner, "_completer_langues", lambda p, pistes: appels.append(p))
    (tmp_path / nom).write_bytes(b"")
    info = scanner.scan(tmp_path / nom)
    assert bool(appels) is appele
    assert info.audio_tracks[0].pid == 0x1100


def test_le_pid_se_lit_en_hexadecimal():
    assert scanner._pid({"id": "0x1101"}) == 0x1101
    assert scanner._pid({}) is None
    assert scanner._pid({"id": "n/a"}) is None


# ─── Langue inconnue gardée ───────────────────────────────────────────────────

@pytest.mark.parametrize("langue", ["", "und"])
def test_une_piste_audio_sans_langue_est_gardee(tmp_path, langue):
    info = _info(tmp_path, audio=[_a(0, "ac3", "fre"), _a(1, "ac3", langue)])
    dec = decide(info, _profile())
    assert dec.audio[1].action != AudioAction.EXCLUDE


def test_une_langue_connue_et_non_voulue_reste_ecartee(tmp_path):
    info = _info(tmp_path, audio=[_a(0, "ac3", "fre"), _a(1, "ac3", "ger")])
    assert decide(info, _profile()).audio[1].action == AudioAction.EXCLUDE


def test_un_sous_titre_sans_langue_est_garde(tmp_path):
    info = _info(tmp_path, subs=[_s(0, "subrip", "fre"), _s(1, "subrip", ""),
                                 _s(2, "subrip", "ger")])
    dec = decide(info, _profile(subtitle_languages=["fre"]))
    assert dec.subtitle_indices == [0, 1]


def test_sans_langue_un_pgs_n_est_pas_dit_double(tmp_path):
    info = _info(tmp_path, subs=[_s(0, "subrip", ""), _s(1, "hdmv_pgs_subtitle", "")])
    assert decide(info, _profile()).subtitle_indices is None


# ─── Cœur AC-3 ────────────────────────────────────────────────────────────────

def _bluray(tmp_path):
    """Le Blu-ray d'essai : PCM stéréo, TrueHD et son cœur AC-3 (même PID)."""
    return _info(tmp_path, audio=[_a(0, "pcm_bluray", "eng", 2, pid=0x1100),
                                  _a(1, "truehd", "eng", 8, pid=0x1101),
                                  _a(2, "ac3", "eng", 6, pid=0x1101)])


def test_sans_le_sans_perte_le_coeur_remplace_la_truehd(tmp_path):
    dec = decide(_bluray(tmp_path), _profile(preserve_hd_audio=False))
    actions = [a.action for a in dec.audio]
    assert actions[1] == AudioAction.EXCLUDE
    assert actions[2] == AudioAction.COPY


def test_avec_le_sans_perte_la_truehd_seule(tmp_path):
    dec = decide(_bluray(tmp_path), _profile(preserve_hd_audio=True))
    assert dec.audio[1].action == AudioAction.COPY
    assert dec.audio[2].action == AudioAction.EXCLUDE


def test_sans_pid_commun_pas_de_paire(tmp_path):
    """Un MKV qui porte une TrueHD et une AC-3 distinctes les garde toutes deux."""
    info = _info(tmp_path, nom="f.mkv", audio=[_a(0, "truehd", "eng", 8),
                                               _a(1, "ac3", "eng", 6)])
    dec = decide(info, _profile(preserve_hd_audio=True))
    assert all(a.action != AudioAction.EXCLUDE for a in dec.audio)


def test_le_coeur_herite_du_role_de_piste_originale(tmp_path):
    info = _info(tmp_path, audio=[_a(0, "truehd", "eng", 8, pid=7),
                                  _a(1, "ac3", "eng", 6, pid=7)])
    dec = decide(info, _profile(preserve_hd_audio=False))
    assert [a.locked for a in dec.audio] == [False, True]
    assert dec.audio[0].action == AudioAction.EXCLUDE


def test_une_selection_manuelle_n_est_pas_corrigee(tmp_path):
    dec = decide(_bluray(tmp_path), _profile(), override_audio=[0, 1, 2])
    assert all(a.action != AudioAction.EXCLUDE for a in dec.audio)


# ─── DVB et télétexte ─────────────────────────────────────────────────────────

def test_le_dvb_est_un_sous_titre_image(tmp_path):
    info = _info(tmp_path, nom="tnt.ts", audio=[_a(0, "aac", "fre", 2)],
                 subs=[_s(0, "dvb_subtitle", "fre")])
    assert info.subtitle_tracks[0].is_image_based
    assert decide(info, _profile()).output_container == ".mkv"


def test_le_teletexte_n_est_jamais_retenu(tmp_path):
    info = _info(tmp_path, nom="tnt.ts", audio=[_a(0, "aac", "fre", 2)],
                 subs=[_s(0, "dvb_teletext", "fre"), _s(1, "dvb_subtitle", "fre")])
    assert decide(info, _profile()).subtitle_indices == [1]
    assert decide(info, _profile(subtitle_languages=["fre"])).subtitle_indices == [1]


def test_le_teletexte_coche_a_la_main_ne_passe_pas(tmp_path):
    info = _info(tmp_path, nom="tnt.ts", subs=[_s(0, "dvb_teletext", "fre")])
    dec = decide(info, _profile(), override_subtitles=[0])
    assert dec.kept_subtitles == []


def test_la_commande_ne_mappe_pas_le_teletexte(tmp_path):
    """`0:s?` l'aurait emporté, et ffmpeg aurait échoué à l'écriture."""
    info = _info(tmp_path, nom="tnt.ts", audio=[_a(0, "aac", "fre", 2)],
                 subs=[_s(0, "dvb_teletext", "fre"), _s(1, "dvb_subtitle", "fre")])
    cmd = build_command(decide(info, _profile()), _PLAT)
    assert "0:s?" not in cmd
    assert "0:s:1" in cmd and "0:s:0" not in cmd


# ─── Les langues complétées arrivent dans la sortie ───────────────────────────

def test_une_langue_completee_est_ecrite_dans_la_sortie(tmp_path):
    """ffmpeg ne recopie que ce qu'il lit : sans `-metadata`, la sortie d'un
    `.m2ts` n'avait aucune langue (mesuré le 2026-10-08)."""
    audio = [_a(0, "ac3", "fre", 6), _a(1, "ac3", "eng", 6)]
    audio[1].langue_completee = True
    subs = [_s(0, "hdmv_pgs_subtitle", "eng")]
    subs[0].langue_completee = True
    cmd = build_command(decide(_info(tmp_path, audio=audio, subs=subs), _profile()), _PLAT)
    assert "-metadata:s:a:1" in cmd and cmd[cmd.index("-metadata:s:a:1") + 1] == "language=eng"
    assert "-metadata:s:s:0" in cmd
    assert "-metadata:s:a:0" not in cmd      # lue dans le flux : ffmpeg la recopie
