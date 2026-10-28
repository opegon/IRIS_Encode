"""
tests/test_lanceurs.py — Lanceurs et bornes des dépendances (IE-132 2/3,
constats CR-107 à CR-112 de `revue_code_2026-10-08.md`).

Les lanceurs sont des scripts cmd et PowerShell : leurs tests sont
structurels ici. Les essais réels sous Windows (dossiers `Test!`, `l'essai`,
`A;B`) sont consignés dans le CHANGELOG de la v0.8.9.115.
"""
from __future__ import annotations

import re
from importlib import metadata
from pathlib import Path

import pytest

import dependances

ROOT = Path(__file__).resolve().parent.parent


def _lire(nom: str) -> str:
    return (ROOT / nom).read_text(encoding="utf-8-sig")


# ─── CR-109, CR-110 — des bornes, contrôlées ─────────────────────────────────

def test_chaque_dependance_a_un_plancher_et_un_plafond():
    for nom, regles in dependances.bornes().items():
        ops = {op for op, _v in regles}
        assert ops == {">=", "<"}, f"{nom} : bornes {regles}"


def test_l_environnement_des_tests_est_dans_les_bornes():
    """Les bornes décrivent ce qui est éprouvé : les tests tournent dedans."""
    assert dependances.ecarts() == []


def test_le_plancher_de_textual_est_sa_version_majeure_eprouvee():
    (plancher,) = [v for op, v in dependances.bornes()["textual"] if op == ">="]
    installee = dependances._version(metadata.version("textual"))
    assert plancher[0] == installee[0]


def test_un_textual_trop_ancien_ou_trop_recent_est_refuse(tmp_path, monkeypatch):
    req = tmp_path / "requirements.txt"
    req.write_text("textual>=8.2,<9\n", encoding="utf-8")
    for version, attendu in (("1.0.0", 1), ("8.2.8", 0), ("8.10.0", 0),
                             ("9.0.0", 1), ("8.1.9", 1)):
        monkeypatch.setattr(metadata, "version", lambda n, v=version: v)
        assert len(dependances.ecarts(req)) == attendu, version


def test_un_paquet_absent_est_signale(tmp_path, monkeypatch):
    req = tmp_path / "requirements.txt"
    req.write_text("# commentaire\n\nabsent-xyz>=1,<2\n", encoding="utf-8")
    assert dependances.ecarts(req) == ["absent-xyz: not installed"]


@pytest.mark.parametrize("texte,attendu", [
    ("8.2.8", (8, 2, 8)), ("2.34.2", (2, 34, 2)), ("1.0rc1", (1, 0)),
    ("2026.7.22", (2026, 7, 22)), ("4.15.0.post1", (4, 15, 0)),
])
def test_lecture_des_versions(texte, attendu):
    assert dependances._version(texte) == attendu


def test_dependances_py_reste_en_bibliotheque_standard():
    """Il tourne sur un Python du système, avant toute installation."""
    imports = re.findall(r"^(?:from|import) (\w+)", _lire("dependances.py"), re.M)
    assert set(imports) <= {"__future__", "re", "sys", "importlib", "pathlib"}


# ─── CR-107 — la purge ne descend plus dans .venv ────────────────────────────

def test_launch_bat_ne_purge_plus_les_pycache():
    assert "__pycache__)" not in _lire("launch.bat")
    assert "rd /s /q" not in _lire("launch.bat")


# ─── CR-108 — ni « ! » ni apostrophe dans un chemin ne cassent le lanceur ────

def test_launch_bat_sans_expansion_retardee():
    txt = _lire("launch.bat")
    assert "enabledelayedexpansion" not in txt.lower()
    code = "\n".join(l for l in txt.splitlines() if not l.lstrip().upper().startswith("REM"))
    assert not re.search(r"![A-Za-z_]+!", code)


def test_le_chemin_n_est_plus_incruste_dans_du_code_python():
    """`r'%~dp0.'` : une apostrophe du chemin fermait la chaîne."""
    txt = _lire("launch.bat")
    assert "r'%~dp0" not in txt
    assert "os.environ['IRIS_DIR']" in txt


# ─── CR-111, CR-112 — « ; » pour wt.exe, apostrophe pour PowerShell ──────────

def test_le_lanceur_echappe_le_point_virgule_pour_wt():
    assert 'Replace(";", "\\\\;")' in _lire("launcher/IrisEncodeLauncher.cs")


def test_build_bat_passe_le_chemin_par_l_environnement():
    txt = _lire("launcher/build.bat")
    ligne = next(l for l in txt.splitlines() if "CreateShortcut" in l)
    assert "'%ROOT%" not in ligne and "$env:ROOT" in ligne


def test_le_lanceur_appelle_launch_bat_par_un_chemin_relatif():
    """`cmd /c launch.bat` échoue avec NoDefaultCurrentDirectoryInExePath."""
    cs = _lire("launcher/IrisEncodeLauncher.cs")
    assert cs.count('.\\\\launch.bat"') == 2
    assert 'c launch.bat"' not in cs


# ─── CR-40 — uv vérifié par son empreinte, comme tout binaire ────────────────

_CIBLES_UV = {"x86_64-pc-windows-msvc", "aarch64-pc-windows-msvc",
              "i686-pc-windows-msvc"}


def _etape_uv() -> str:
    """Le bloc « 1. uv » de bootstrap.ps1, jusqu'à l'étape 2."""
    txt = _lire("bootstrap.ps1")
    debut = txt.index("# ── 1. uv")
    return txt[debut:txt.index("# ── 2.", debut)]


def test_bootstrap_epingle_uv_avec_une_empreinte_par_cible():
    txt = _lire("bootstrap.ps1")
    assert "releases/latest" not in txt, "uv non épinglé : l'empreinte ne suivrait pas"
    assert re.search(r"^\$UvVersion\s*=\s*'\d+\.\d+\.\d+'", txt, re.M)
    assert "releases/download/$UvVersion/uv-$cible.zip" in _etape_uv()
    empreintes = dict(re.findall(
        r"'([a-z0-9_]+-pc-windows-msvc)'\s*=\s*'([0-9a-f]{64})'", txt))
    assert set(empreintes) == _CIBLES_UV
    # Chaque archive que l'architecture peut désigner a son empreinte.
    assert set(re.findall(r"\$cible = '([^']+)'", _etape_uv())) == _CIBLES_UV


def test_bootstrap_refuse_une_archive_uv_dont_l_empreinte_differe():
    etape = _etape_uv()
    telechargement = etape.index("Invoke-WebRequest")
    empreinte = etape.index("Get-FileHash")
    extraction = etape.index("ExtractToDirectory")
    assert telechargement < empreinte < extraction, (
        "l'empreinte doit être contrôlée avant toute extraction")
    assert "-Algorithm SHA256" in etape
    refus = etape[empreinte:extraction]
    assert re.search(r"if \(\$obtenue -ne \$attendue\)", refus)
    assert re.search(r"Remove-Item -LiteralPath \$zip", refus)
    assert re.search(r"^\s*exit [1-9]", refus, re.M)
