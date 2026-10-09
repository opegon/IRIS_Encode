"""
tests/test_outils_installation.py — Installation et mise à jour des outils
(IE-132 1/3, constats CR-38, CR-39, CR-40, CR-41 de `revue_code_2026-10-08.md`).

Aucun appel réseau : `_download` et `updates._get` sont remplacés.
"""
from __future__ import annotations

import hashlib
import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from core import preflight, updates
from core.updates import Release


def _zip(membres: dict[str, bytes]) -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as z:
        for nom, contenu in membres.items():
            z.writestr(nom, contenu)
    return tampon.getvalue()


def _tar_gz(membres: dict[str, bytes]) -> bytes:
    tampon = io.BytesIO()
    with tarfile.open(fileobj=tampon, mode="w:gz") as t:
        for nom, contenu in membres.items():
            info = tarfile.TarInfo(nom)
            info.size = len(contenu)
            t.addfile(info, io.BytesIO(contenu))
    return tampon.getvalue()


class _Reponse:
    def __init__(self, texte: str = "", ok: bool = True, donnees=None):
        self.text, self.ok, self._donnees = texte, ok, donnees

    def json(self):
        return self._donnees


# ─── CR-38 — tous ou aucun, jamais d'outil tronqué ───────────────────────────

def test_un_echec_au_second_outil_laisse_les_deux_anciens_intacts(tmp_path,
                                                                  monkeypatch):
    ffmpeg, ffprobe = preflight._exe("ffmpeg"), preflight._exe("ffprobe")
    (tmp_path / ffmpeg).write_bytes(b"ancien ffmpeg")
    (tmp_path / ffprobe).write_bytes(b"ancien ffprobe")
    archive = _zip({f"b/bin/{ffmpeg}": b"neuf ffmpeg",
                    f"b/bin/{ffprobe}": b"neuf ffprobe"})

    vrai = Path.write_bytes

    def disque_plein(self, data):
        if self.name.startswith(ffprobe):
            raise OSError(28, "No space left on device")
        return vrai(self, data)

    monkeypatch.setattr(Path, "write_bytes", disque_plein)
    assert preflight.poser("ffmpeg", archive, tmp_path) is False
    monkeypatch.undo()

    assert (tmp_path / ffmpeg).read_bytes() == b"ancien ffmpeg"
    assert (tmp_path / ffprobe).read_bytes() == b"ancien ffprobe"
    assert not list(tmp_path.glob("*.iris_tmp")), "provisoires laissés"


def test_la_mise_a_jour_ratee_dit_vrai(tmp_path, monkeypatch, capsys):
    """« previous version kept » doit l'être : l'échec d'écriture ne lève plus,
    il rend False, et `check_for_updates` l'annonce."""
    monkeypatch.setattr(preflight, "_download", lambda url, sha: _zip(
        {preflight._exe("ffmpeg"): b"x", preflight._exe("ffprobe"): b"y"}))
    monkeypatch.setattr(preflight, "_poser_tous", lambda f: False)
    assert preflight._installer_for("ffmpeg")(tmp_path, "u", "a" * 64) is False


def test_une_archive_incomplete_ne_pose_rien(tmp_path):
    """Un ffmpeg sans son ffprobe n'est pas une installation."""
    archive = _zip({preflight._exe("ffmpeg"): b"seul"})
    assert preflight.poser("ffmpeg", archive, tmp_path) is False
    assert not any(tmp_path.iterdir())


# ─── CR-39 — le tar.gz Linux est extrait, jamais écrit tel quel ──────────────

def test_dovi_tool_en_tar_gz_est_extrait(tmp_path):
    exe = preflight._exe("dovi_tool")
    archive = _tar_gz({f"dovi_tool-2.3.3/{exe}": b"\x7fELF binaire"})
    assert preflight.poser("dovi_tool", archive, tmp_path)
    assert (tmp_path / exe).read_bytes() == b"\x7fELF binaire"


def test_un_contenu_inconnu_n_est_jamais_ecrit_comme_executable(tmp_path):
    assert preflight.poser("dovi_tool", b"<html>404</html>", tmp_path) is False
    assert not any(tmp_path.iterdir())


@pytest.mark.parametrize("entete", [b"MZ\x90\x00", b"\x7fELF"])
def test_un_executable_nu_reste_accepte(tmp_path, entete):
    assert preflight.poser("dovi_tool", entete + b"corps", tmp_path)
    assert (tmp_path / preflight._exe("dovi_tool")).read_bytes() == entete + b"corps"


# ─── CR-40 — une empreinte pour chaque téléchargement ────────────────────────

def test_sans_empreinte_rien_n_est_telecharge(monkeypatch):
    appels = []
    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: appels.append(a))
    assert preflight._download("http://x/a.zip", "") is None
    assert not appels


def test_une_empreinte_fausse_refuse_l_archive(monkeypatch):
    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: type(
        "R", (), {"content": b"archive", "raise_for_status": lambda self: None})())
    assert preflight._download("http://x/a.zip", "0" * 64) is None
    juste = hashlib.sha256(b"archive").hexdigest()
    assert preflight._download("http://x/a.zip", juste.upper()) == b"archive"


def test_install_ffmpeg_lit_le_sha256_publie(tmp_path, monkeypatch):
    vus = {}
    monkeypatch.setattr(updates, "_get", lambda url: vus.setdefault(url, _Reponse(
        "60F467265B1E312373DBCD92200C2618A74850F98D3D078E94296BB3FA2047BA "
        "*ffmpeg-9.0.2-essentials_build.zip\n")))
    monkeypatch.setattr(preflight, "_download",
                        lambda url, sha: vus.setdefault("sha", sha) and None)
    preflight.install_ffmpeg(tmp_path, "https://g/ffmpeg-release-essentials.zip")
    assert "https://g/ffmpeg-release-essentials.zip.sha256" in vus
    assert vus["sha"] == "60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba"


def test_sha256_publie_absent_rend_vide(monkeypatch):
    monkeypatch.setattr(updates, "_get", lambda url: _Reponse("", ok=False))
    assert updates.sha256_publie("http://x/a.zip") == ""


def test_les_releases_github_portent_leur_digest(monkeypatch):
    monkeypatch.setattr(updates, "_get", lambda url: _Reponse(donnees={
        "tag_name": "2.3.4", "assets": [{
            "name": "dovi_tool-2.3.4-x86_64-pc-windows-msvc.zip",
            "browser_download_url": "u/dovi.zip",
            "digest": "sha256:" + "AB" * 32}]}))
    assert updates._latest_dovi_tool().sha256 == "ab" * 32


def test_l_outil_dvd_porte_son_digest(monkeypatch):
    monkeypatch.setattr(updates, "_get", lambda url: _Reponse(donnees={"assets": [{
        "name": "ffmpeg-n9.0-latest-win64-gpl-9.0.zip",
        "browser_download_url": "u/b.zip", "digest": "sha256:" + "c" * 64}]}))
    assert updates.latest_ffmpeg_dvd().sha256 == "c" * 64


def test_mkvtoolnix_lit_sa_liste_d_empreintes(monkeypatch):
    def get(url):
        if url.endswith(".xml"):
            return _Reponse("<latest-source><version>101.0</version>")
        return _Reponse(
            "7f8d6c  mkvtoolnix-32-bit-101.0.zip\n"
            "59A807B4  mkvtoolnix-64-bit-101.0.zip\n")
    monkeypatch.setattr(updates, "_get", get)
    assert updates._latest_mkvtoolnix().sha256 == "59a807b4"


def test_l_empreinte_traverse_cache_et_mise_a_jour(tmp_path, monkeypatch):
    cache = tmp_path / "c.toml"
    updates.save_cache(cache, {"dovi_tool": Release("2.3.4", "u", "d" * 64)})
    lu = updates.load_cache(cache)
    (maj,) = updates.pending({"dovi_tool": "2.3.3"}, lu)
    assert maj.sha256 == "d" * 64

    recu = []
    monkeypatch.setattr(preflight, "_download",
                        lambda url, sha: recu.append(sha) or None)
    monkeypatch.setattr(preflight, "_oui_non", lambda q: True)
    monkeypatch.setattr(updates, "load_cache", lambda p: lu)
    statut = preflight.ToolStatus("dovi_tool", True,
                                  preflight.chemin_local("dovi_tool", tmp_path),
                                  "2.3.3")
    preflight.check_for_updates({}, [statut], tmp_path)
    assert recu == ["d" * 64]


def test_les_sources_statiques_epinglent_dovi_tool():
    sources = preflight._load_releases()
    for os_key in ("windows", "linux"):
        assert len(sources["dovi_tool"][os_key]["sha256"]) == 64, os_key


# ─── CR-41 — le cache des mises à jour ne masque plus les sources ───────────

def test_avec_le_cache_ecrit_dovi_tool_s_installe_encore(tmp_path, monkeypatch):
    cache = tmp_path / "ffmpeg_releases_cache.toml"
    updates.save_cache(cache, {"dovi_tool": Release("2.3.4", "u/frais.zip", "e" * 64)})
    monkeypatch.setattr(preflight, "CACHE_FILE", cache)

    tentes = []
    monkeypatch.setattr(preflight, "_download",
                        lambda url, sha: tentes.append((url, sha)) or None)
    preflight.install_dovi_tool(tmp_path / "bin", preflight._load_releases())
    os_key = "windows" if preflight._is_windows() else "linux"
    statique = preflight._load_releases()["dovi_tool"][os_key]
    assert tentes == [(statique["url"], statique["sha256"])]


def test_mkvmerge_et_mpv_trouvent_leur_source(monkeypatch):
    if not preflight._is_windows():
        pytest.skip("installés par le gestionnaire de paquets hors Windows")
    tentes = []
    monkeypatch.setattr(preflight, "_download",
                        lambda url, sha: tentes.append(sha) or None)
    sources = preflight._load_releases()
    preflight.install_mkvtoolnix(Path("bin"), sources)
    preflight.install_mpv(Path("bin"), sources)
    assert len(tentes) == 2 and all(len(s) == 64 for s in tentes)
