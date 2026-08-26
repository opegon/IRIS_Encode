"""
tests/test_updates.py — Tests unitaires de core/updates.py

Aucun appel réseau : on injecte des versions et on vérifie le verdict.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from core import updates
from core.updates import Release


# ─── Comparaison de versions ──────────────────────────────────────────────────

@pytest.mark.parametrize("latest,installed,attendu", [
    ("9.0.1",  "8.1.2",  True),
    ("101.0",  "99.0",   True),     # 101 > 99 : comparaison numérique, pas lexicale
    ("2.3.3",  "2.1.0",  True),
    ("8.1.2",  "9.0.1",  False),
    ("99.0",   "101.0",  False),
    ("2.3.3",  "2.3.3",  False),
])
def test_is_newer_on_dotted_versions(latest, installed, attendu):
    assert updates.is_newer(latest, installed) is attendu


@pytest.mark.parametrize("latest,installed", [
    ("20260814", "0.41.0"),    # date shinchiro contre semver mpv
    ("0.41.0",   "20260814"),
    ("2.3.3",    "5717cab"),   # build git : que du hash
    ("2.3.3",    ""),
    ("",         "2.3.3"),
])
def test_incomparable_versions_never_claim_an_update(latest, installed):
    """
    Comparer des numérotations différentes signalerait une mise à jour à
    chaque lancement, indéfiniment. Mieux vaut ne rien dire.
    """
    assert updates.is_newer(latest, installed) is False


def test_dates_compare_between_themselves():
    assert updates.is_newer("20260901", "20260814") is True
    assert updates.is_newer("20260814", "20260901") is False


def test_parse_version_distinguishes_shapes():
    assert updates.parse_version("mpv v0.41.0")[0] == "dotted"
    assert updates.parse_version("20260814")[0]    == "date"
    assert updates.parse_version("5717cab") is None


# ─── Verdict ──────────────────────────────────────────────────────────────────

def test_pending_lists_only_outdated_tools():
    installed = {"mkvmerge": "99.0", "dovi_tool": "2.3.3", "mpv": "0.41.0"}
    releases  = {
        "mkvmerge":  Release("101.0", "http://x/mkv.zip"),
        "dovi_tool": Release("2.3.3", "http://x/dovi.zip"),
        "mpv":       Release("20260814", "http://x/mpv.7z"),
    }
    en_retard = updates.pending(installed, releases)
    assert [u.tool for u in en_retard] == ["mkvmerge"]
    assert en_retard[0].latest == "101.0"
    assert en_retard[0].url.endswith("mkv.zip")


def test_pending_ignores_tools_without_a_known_release():
    assert updates.pending({"inconnu": "1.0"}, {}) == []


def test_update_label_handles_an_unknown_installed_version():
    u = updates.Update("dovi_tool", "", "2.3.3", "http://x")
    assert "inconnue" in u.label()


# ─── Cache ────────────────────────────────────────────────────────────────────

def test_cache_roundtrip(tmp_path: Path):
    cache = tmp_path / "c.toml"
    rel = {"mkvmerge": Release("101.0", "http://x/mkv.zip")}
    updates.save_cache(cache, rel)
    lu = updates.load_cache(cache)
    assert lu is not None
    assert lu["mkvmerge"].version == "101.0"
    assert lu["mkvmerge"].url == "http://x/mkv.zip"


def test_missing_cache_is_not_an_error(tmp_path: Path):
    assert updates.load_cache(tmp_path / "absent.toml") is None


def test_expired_cache_is_refused(tmp_path: Path):
    """Au-delà du TTL, on réinterroge plutôt que de servir du périmé."""
    import tomli_w
    cache = tmp_path / "c.toml"
    with cache.open("wb") as f:
        tomli_w.dump({
            "checked_at": time.time() - updates.CACHE_TTL_SECONDS - 60,
            "tools": {"mkvmerge": {"version": "99.0", "url": "http://x"}},
        }, f)
    assert updates.load_cache(cache) is None


def test_corrupt_cache_is_not_an_error(tmp_path: Path):
    cache = tmp_path / "c.toml"
    cache.write_text("ceci n'est pas du toml [[[", encoding="utf-8")
    assert updates.load_cache(cache) is None
