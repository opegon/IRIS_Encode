"""
tests/test_youtube.py — Télécharger une vidéo YouTube (IE-180).

Aucun appel réseau ni vrai yt-dlp : la description de la page est un JSON
fabriqué sur le modèle de `yt-dlp -J`, et le téléchargement est joué par un
petit script Python qui imite la sortie de yt-dlp.
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pytest

from core import config as cfg_mod
from core import preflight, updates, youtube
from core.i18n import ErreurAffichable


def _video_fmt(fid, note, h, vcodec="vp9"):
    return {"format_id": fid, "format_note": note, "height": h,
            "vcodec": vcodec, "acodec": "none"}


def _audio_fmt(fid, acodec, pref=None):
    return {"format_id": fid, "vcodec": "none", "acodec": acodec,
            "language_preference": pref}


def _page(**extra) -> dict:
    """Une page type : listée du moins bon au meilleur, comme yt-dlp le fait."""
    donnees = {
        "id": "abc123", "title": "Un film", "duration": 5400,
        "webpage_url": "https://www.youtube.com/watch?v=abc123",
        "formats": [
            _audio_fmt("140", "mp4a.40.2", pref=10),
            _audio_fmt("251", "opus", pref=10),
            _video_fmt("137", "1080p", 1080, "avc1.640028"),
            _video_fmt("248", "1080p", 1080, "vp9"),
            # Un 2,39:1 publié en 2160p : 3840 × 1608.
            _video_fmt("313", "2160p", 1608, "vp9"),
            _video_fmt("401", "2160p", 1608, "av01.0.12M.08"),
            {"format_id": "18", "format_note": "360p", "height": 360,
             "vcodec": "avc1", "acodec": "mp4a.40.2"},     # muxé : écarté
        ],
    }
    donnees.update(extra)
    return donnees


# ─── Lecture de la page ───────────────────────────────────────────────────────

def test_le_palier_se_lit_dans_la_note_et_non_la_hauteur():
    video = youtube.lire_infos(_page(), "u")
    assert video.hauteurs == [2160, 1080]
    # Le dernier listé d'un palier est le meilleur.
    assert video.formats == {2160: "401", 1080: "248"}


def test_une_video_sans_palier_standard_offre_sa_meilleure_definition():
    page = _page(formats=[_audio_fmt("140", "mp4a.40.2"),
                          _video_fmt("135", "480p", 480),
                          _video_fmt("136", "720p", 720)])
    assert youtube.lire_infos(page, "u").formats == {720: "136"}


def test_l_audio_est_l_aac_de_la_piste_d_origine():
    # L'origine listée avant le doublage : le rang seul choisirait le doublage.
    page = _page(formats=[_audio_fmt("140-1", "mp4a.40.2", pref=10),   # origine
                          _audio_fmt("140-0", "mp4a.40.2", pref=-1),   # doublage
                          _audio_fmt("251-1", "opus", pref=10),
                          _video_fmt("248", "1080p", 1080)])
    video = youtube.lire_infos(page, "u")
    assert (video.audio, video.audio_aac) == ("140-1", True)


def test_sans_aac_le_meilleur_audio_est_pris_et_signale():
    page = _page(formats=[_audio_fmt("250", "opus"), _audio_fmt("251", "opus"),
                          _video_fmt("248", "1080p", 1080)])
    video = youtube.lire_infos(page, "u")
    assert (video.audio, video.audio_aac) == ("251", False)


def test_sous_titres_deposes_puis_transcription_d_origine_seule():
    page = _page(
        subtitles={"fr": [{"ext": "vtt", "name": "French"}],
                   "live_chat": [{"ext": "json"}]},
        automatic_captions={"en-orig": [{"name": "English (Original)"}],
                            "en": [{"name": "English"}],
                            "fr": [{"name": "French"}],
                            "de": [{"name": "German"}]})
    subs = youtube.lire_infos(page, "u").sous_titres
    assert [(s.cle, s.langue, s.auto) for s in subs] == [
        ("fr", "fr", False), ("en-orig", "en", True)]
    assert subs[0].nom == "French"


def test_sans_cle_orig_la_langue_de_la_video_sert():
    page = _page(automatic_captions={"ja": [{"name": "Japanese"}],
                                     "fr": [{"name": "French"}]}, language="ja")
    subs = youtube.lire_infos(page, "u").sous_titres
    assert [(s.cle, s.auto) for s in subs] == [("ja", True)]


# ─── Ligne de commande ────────────────────────────────────────────────────────

def test_la_commande_vise_les_formats_choisis(tmp_path):
    video = youtube.lire_infos(_page(subtitles={"fr": [{"name": "French"}]},
                                     automatic_captions={"en-orig": [{}]}), "u")
    cmd = youtube.commande(Path("y.exe"), Path("d/deno.exe"), "ff.exe", video,
                           2160, video.sous_titres, tmp_path)
    assert cmd[cmd.index("-f") + 1] == "401+140"
    assert cmd[cmd.index("--js-runtimes") + 1] == f"deno:{Path('d/deno.exe')}"
    assert cmd[cmd.index("--ffmpeg-location") + 1] == "ff.exe"
    assert cmd[cmd.index("-P") + 1] == str(tmp_path)
    assert cmd[cmd.index("--merge-output-format") + 1] == "mkv"
    assert cmd[cmd.index("--sub-langs") + 1] == r"fr,en\-orig"
    assert {"--write-subs", "--write-auto-subs", "--embed-subs",
            "--no-config", "--no-playlist", "--progress"} <= set(cmd)
    assert cmd[cmd.index("--convert-subs") + 1] == "srt"
    assert cmd[-1] == "https://www.youtube.com/watch?v=abc123"


def test_sans_sous_titre_rien_n_est_demande(tmp_path):
    video = youtube.lire_infos(_page(), "u")
    cmd = youtube.commande(Path("y"), Path("d"), "ff", video, 1080, [], tmp_path)
    assert cmd[cmd.index("-f") + 1] == "248+140"
    assert not {"--sub-langs", "--write-subs", "--write-auto-subs",
                "--embed-subs"} & set(cmd)


# ─── Téléchargement ───────────────────────────────────────────────────────────

def _faux_ytdlp(tmp_path: Path, script: str) -> list[str]:
    """Une commande qui joue yt-dlp : un script Python à la place."""
    fichier = tmp_path / "faux_ytdlp.py"
    fichier.write_text(script, encoding="utf-8")
    return [sys.executable, str(fichier)]


def test_le_telechargement_rend_le_fichier_et_sa_progression(tmp_path):
    sortie = tmp_path / "Un film [abc123].mkv"
    cmd = _faux_ytdlp(tmp_path, f"""
from pathlib import Path
print("[youtube] abc123: Downloading webpage", flush=True)
print("IRIS-PROGRES  42.5%", flush=True)
print("IRIS-PROGRES 100.0%", flush=True)
Path({str(sortie)!r}).write_bytes(b"mkv")
print("IRIS-FICHIER " + {str(sortie)!r}, flush=True)
""")
    parts: list[float] = []
    video = youtube.lire_infos(_page(), "u")
    produit = youtube.Telechargement().lancer(cmd, video, tmp_path, parts.append)
    assert produit == sortie
    assert parts == [0.425, 1.0]


def test_un_echec_dit_l_erreur_et_retire_les_morceaux(tmp_path):
    ancien = tmp_path / "Un film [abc123].mkv.old"
    ancien.write_bytes(b"x")
    import os
    os.utime(ancien, (1_000_000, 1_000_000))      # téléchargement d'avant
    cmd = _faux_ytdlp(tmp_path, f"""
import sys
from pathlib import Path
Path({str(tmp_path / "Un film [abc123].f401.webm.part")!r}).write_bytes(b"p")
print("ERROR: [youtube] abc123: Sign in to confirm your age", flush=True)
sys.exit(1)
""")
    video = youtube.lire_infos(_page(), "u")
    with pytest.raises(ErreurAffichable) as e:
        youtube.Telechargement().lancer(cmd, video, tmp_path, lambda p: None)
    assert str(e.value) == "[youtube] abc123: Sign in to confirm your age"
    restants = sorted(f.name for f in tmp_path.iterdir() if "[abc123]" in f.name)
    assert restants == [ancien.name]


def test_un_code_nul_sans_fichier_produit_est_un_echec(tmp_path):
    cmd = _faux_ytdlp(tmp_path, 'print("rien", flush=True)\n')
    video = youtube.lire_infos(_page(), "u")
    with pytest.raises(ErreurAffichable):
        youtube.Telechargement().lancer(cmd, video, tmp_path, lambda p: None)


def test_annuler_arrete_et_ne_rend_rien(tmp_path):
    cmd = _faux_ytdlp(tmp_path, f"""
import time
from pathlib import Path
Path({str(tmp_path / "Un film [abc123].f401.webm.part")!r}).write_bytes(b"p")
print("IRIS-PROGRES 10.0%", flush=True)
time.sleep(30)
""")
    dl = youtube.Telechargement()
    video = youtube.lire_infos(_page(), "u")
    produit = dl.lancer(cmd, video, tmp_path, lambda p: dl.annuler())
    assert produit is None and dl.annule
    assert not [f for f in tmp_path.iterdir() if "[abc123]" in f.name]


def test_l_analyse_rend_l_erreur_de_yt_dlp(monkeypatch):
    class _R:
        returncode, stdout = 1, ""
        stderr = "WARNING: x\nERROR: [youtube] zz: Video unavailable\n"
    monkeypatch.setattr(youtube.subprocess, "run", lambda *a, **k: _R())
    with pytest.raises(ErreurAffichable) as e:
        youtube.analyser("u", Path("y"), Path("d"))
    assert str(e.value) == "[youtube] zz: Video unavailable"


# ─── Installation, mises à jour, réglage ─────────────────────────────────────

def test_les_deux_outils_vivent_dans_bin_yt_dlp(tmp_path):
    assert preflight.chemin_local("yt-dlp", tmp_path).parent == tmp_path / "yt-dlp"
    assert preflight.chemin_local("deno", tmp_path).parent == tmp_path / "yt-dlp"
    assert youtube.outils(tmp_path) is None
    for nom in ("yt-dlp", "deno"):
        chemin = preflight.chemin_local(nom, tmp_path)
        chemin.parent.mkdir(exist_ok=True)
        chemin.write_bytes(b"MZ")
    assert youtube.outils(tmp_path) == (preflight.chemin_local("yt-dlp", tmp_path),
                                        preflight.chemin_local("deno", tmp_path))


def test_poser_range_yt_dlp_nu_et_extrait_deno(tmp_path):
    assert preflight.poser("yt-dlp", b"MZ-exe", tmp_path)
    assert preflight.chemin_local("yt-dlp", tmp_path).read_bytes() == b"MZ-exe"
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr(preflight._exe("deno"), b"MZ-deno")
    assert preflight.poser("deno", archive.getvalue(), tmp_path)
    assert preflight.chemin_local("deno", tmp_path).read_bytes() == b"MZ-deno"


def test_un_yt_dlp_qui_n_est_pas_un_executable_n_est_pas_pose(tmp_path):
    assert not preflight.poser("yt-dlp", b"<html>", tmp_path)
    assert not preflight.chemin_local("yt-dlp", tmp_path).exists()


def test_install_youtube_ne_pose_rien_si_un_telechargement_echoue(tmp_path,
                                                                  monkeypatch):
    monkeypatch.setattr(preflight, "_is_windows", lambda: True)
    monkeypatch.setattr(preflight, "_download",
                        lambda url, sha: None if "deno" in url else b"MZ")
    assert not preflight.install_youtube(tmp_path, preflight._load_releases())
    assert not (tmp_path / "yt-dlp").exists()


def test_les_sources_statiques_epinglent_yt_dlp_et_deno():
    sources = preflight._load_releases()
    for nom in ("yt-dlp", "deno"):
        assert len(sources[nom]["windows"]["sha256"]) == 64, nom
        assert sources[nom]["windows"]["url"].startswith("https://github.com/")


def test_la_veille_suit_yt_dlp_et_deno(monkeypatch):
    class _R:
        ok = True

        def __init__(self, donnees):
            self._d = donnees

        def json(self):
            return self._d

    def _get(url):
        if "yt-dlp" in url:
            return _R({"tag_name": "2026.11.01", "assets": [
                {"name": "yt-dlp_x86.exe", "browser_download_url": "x86",
                 "digest": "sha256:" + "0" * 64},
                {"name": "yt-dlp.exe", "browser_download_url": "u/yt-dlp.exe",
                 "digest": "sha256:" + "a" * 64}]})
        return _R({"tag_name": "v2.9.9", "assets": [
            {"name": "deno-x86_64-pc-windows-msvc.zip",
             "browser_download_url": "u/deno.zip", "digest": "sha256:" + "b" * 64}]})

    monkeypatch.setattr(updates, "_get", _get)
    yt, deno = updates._SOURCES["yt-dlp"](), updates._SOURCES["deno"]()
    assert (yt.version, yt.url) == ("2026.11.01", "u/yt-dlp.exe")
    assert (deno.version, deno.url) == ("2.9.9", "u/deno.zip")
    assert updates.is_newer(yt.version, "2026.10.26")
    assert {"yt-dlp", "deno"} <= preflight.OUTILS_INSTALLABLES


def test_la_version_de_yt_dlp_se_demande_en_option_longue(monkeypatch):
    vus: list[str] = []

    class _R:
        returncode, stdout, stderr = 0, "2026.10.26\n", ""

    def _run(cmd, **k):
        vus.append(cmd[1])
        return _R()

    monkeypatch.setattr(preflight.subprocess, "run", _run)
    assert preflight._get_version("bin/yt-dlp/yt-dlp.exe") == "2026.10.26"
    assert vus == ["--version"]


def test_le_dossier_youtube_non_choisi_ou_disparu_se_redemande(tmp_path):
    assert cfg_mod.get_youtube_dir({}) is None
    assert cfg_mod.get_youtube_dir({"app": {"youtube_dir": str(tmp_path / "x")}}) is None
    assert cfg_mod.get_youtube_dir({"app": {"youtube_dir": str(tmp_path)}}) == tmp_path
