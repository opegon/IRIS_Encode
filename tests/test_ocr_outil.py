"""L'outil d'OCR des sous-titres image (IE-176) : sources, installation, détection."""
from __future__ import annotations

import io
import re
import tomllib
import zipfile
from pathlib import Path

import pytest

from core import ocr, preflight

APP = Path(__file__).resolve().parent.parent


def _sources() -> dict:
    with (APP / "data" / "ffmpeg_releases.toml").open("rb") as f:
        return tomllib.load(f)


def test_sources_epinglees():
    """Chaque fichier a son empreinte, et une URL qui ne bouge pas : une
    release, ou un commit — jamais une branche, dont le contenu change."""
    info = _sources()["seconv"]
    assert "/releases/download/v" in info["windows"]["url"]
    assert re.fullmatch(r"[0-9a-f]{64}", info["windows"]["sha256"])
    noms = [d["nom"] for d in info["donnees"]]
    assert ocr.BASE_NOCR in noms
    assert f"{ocr.DICOS}/fra_OCRFixReplaceList.xml" in noms
    assert {f"{ocr.DICOS}/fr_FR.dic", f"{ocr.DICOS}/fr_FR.aff"} <= set(noms)
    for d in info["donnees"]:
        assert re.search(r"/[0-9a-f]{40}/", d["url"]), d["url"]
        assert re.fullmatch(r"[0-9a-f]{64}", d["sha256"]), d["nom"]
        assert ".." not in d["nom"] and not d["nom"].startswith("/")


def _archive() -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as zf:
        for nom in ("seconv.exe", *ocr.DLL, "LICENSE", "libse.xml"):
            zf.writestr(nom, f"<{nom}>")
    return tampon.getvalue()


@pytest.fixture
def windows(monkeypatch):
    monkeypatch.setattr(preflight, "_is_windows", lambda: True)
    monkeypatch.setattr(ocr.platform, "system", lambda: "Windows")


def test_installation_complete(tmp_path, monkeypatch, windows):
    sources = _sources()
    donnees = sources["seconv"]["donnees"]
    par_url = {d["url"]: d["nom"].encode() for d in donnees}
    par_url[sources["seconv"]["windows"]["url"]] = _archive()
    monkeypatch.setattr(preflight, "_download", lambda url, sha: par_url[url])

    assert ocr.chercher_seconv(tmp_path, donnees) is None
    assert preflight.install_seconv(tmp_path, sources)
    d = ocr.dossier(tmp_path)
    assert (d / "seconv.exe").read_bytes() == b"<seconv.exe>"
    assert all((d / dll).is_file() for dll in ocr.DLL)
    # Seul ce qui sert est extrait de l'archive.
    assert not (d / "libse.xml").exists()
    for x in donnees:
        assert (d / x["nom"]).is_file(), x["nom"]
    assert (d / ocr.DICOS / "fr_FR.dic").read_bytes() == b"dictionnaires/fr_FR.dic"
    assert ocr.chercher_seconv(tmp_path, donnees) == d / "seconv.exe"


def test_une_donnee_refusee_rien_n_est_pose(tmp_path, monkeypatch, windows):
    """Une empreinte fausse sur une seule donnée : ni l'exécutable ni le reste."""
    sources = _sources()
    donnees = sources["seconv"]["donnees"]
    refusee = donnees[-1]["url"]

    def telecharger(url, sha):
        if url == refusee:
            return None
        return _archive() if url.endswith(".zip") else b"x"

    monkeypatch.setattr(preflight, "_download", telecharger)
    assert not preflight.install_seconv(tmp_path, sources)
    assert not ocr.dossier(tmp_path).exists()


def test_incomplet_pas_d_ocr(tmp_path, windows):
    """Il manque une donnée, ou une DLL : l'OCR n'est pas proposé."""
    donnees = _sources()["seconv"]["donnees"]
    d = ocr.dossier(tmp_path)
    for nom in ("seconv.exe", *ocr.DLL, *(x["nom"] for x in donnees)):
        (d / nom).parent.mkdir(parents=True, exist_ok=True)
        (d / nom).write_bytes(b"x")
    assert ocr.chercher_seconv(tmp_path, donnees) is not None
    (ocr.dossier(tmp_path) / ocr.DICOS / "fr_FR.aff").unlink()
    assert ocr.chercher_seconv(tmp_path, donnees) is None
    (ocr.dossier(tmp_path) / ocr.DICOS / "fr_FR.aff").write_bytes(b"x")
    (ocr.dossier(tmp_path) / ocr.DLL[0]).unlink()
    assert ocr.chercher_seconv(tmp_path, donnees) is None


def test_sans_sources_pas_d_ocr(tmp_path):
    assert ocr.chercher_seconv(tmp_path, []) is None


def test_hors_windows_rien_n_est_telecharge(tmp_path, monkeypatch):
    monkeypatch.setattr(preflight, "_is_windows", lambda: False)
    monkeypatch.setattr(preflight, "_download",
                        lambda url, sha: pytest.fail("téléchargement hors Windows"))
    assert not preflight.install_seconv(tmp_path, _sources())
