"""
tests/test_hdr10.py — Le mode « HDR10 quality » injecte enfin ses métadonnées.

Ce mode existe pour produire un HDR10 aux métadonnées statiques correctes —
master display et MaxCLL — que certains téléviseurs exigent pour appliquer leur
tone mapping. Il ne les a **jamais** injectées : `dovi.rpu_info()` analysait la
sortie de `dovi_tool info` avec des expressions régulières attendant du texte,
alors que l'outil rend du JSON. `master_display` et `max_cll` valaient donc
toujours `None`.

Trois tests passaient pourtant, parce qu'ils fabriquaient eux-mêmes le format
attendu. C'est exactement ainsi qu'un défaut survit à une suite verte.

Les métadonnées viennent désormais des **SEI du flux**, lus par ffprobe : c'est
là qu'un lecteur les cherche, et cela vaut pour toute source HDR, avec ou sans
Dolby Vision.
"""
from __future__ import annotations

import pytest

from core.scanner import _fraction, _hdr10_metadata


# ─── Conversion des fractions ffprobe ─────────────────────────────────────────

@pytest.mark.parametrize("valeur, unite, attendu", [
    ("35400/50000", 50000, 35400),      # chromaticité, dénominateur usuel
    ("10000000/10000", 10000, 10000000),  # 1000 cd/m²
    ("1/10000", 10000, 1),              # 0,0001 cd/m²
    ("17700/25000", 50000, 35400),      # dénominateur inhabituel : rééchelonné
    ("680/1000", 50000, 34000),
])
def test_fraction(valeur, unite, attendu):
    assert _fraction(valeur, unite) == attendu


@pytest.mark.parametrize("valeur", ["", "abc", "1/0"])
def test_fraction_illisible(valeur):
    assert _fraction(valeur, 50000) is None


@pytest.mark.parametrize("valeur", ["3", "3/"])
def test_une_valeur_sans_denominateur_vaut_l_entier(valeur):
    """Tous les muxeurs n'écrivent pas la fraction : « 3 » vaut 3."""
    assert _fraction(valeur, 50000) == 150000


# ─── Lecture d'un fichier réel ────────────────────────────────────────────────

def _fichier(nom: str):
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / "resources_files" / nom
    if not p.exists():
        pytest.skip(f"{nom} absent du dossier de travail")
    return p


def test_une_source_hdr_rend_son_master_display():
    """Le format attendu par x265 : G(x,y)B(x,y)R(x,y)WP(x,y)L(max,min)."""
    import re

    master, _ = _hdr10_metadata(_fichier(
        "Kingdom.of.the.Planet.of.the.Apes.2024.MULTi.VFF.4K.2160p."
        "HDR10Plus.DV.WEBRip.DDP.Atmos.7.1.x265.mkv"))
    assert master is not None, "aucune métadonnée lue"
    assert re.fullmatch(
        r"G\(\d+,\d+\)B\(\d+,\d+\)R\(\d+,\d+\)WP\(\d+,\d+\)L\(\d+,\d+\)", master
    ), master


def test_maxcll_non_mesure_n_est_pas_invente():
    """Un flux qui déclare 0,0 dit « non mesuré ». Injecter `max-cll=0,0`
    affirmerait que le pic lumineux est nul."""
    _, cll = _hdr10_metadata(_fichier(
        "Watchmen.2009.MULTi.2160p.BluRay.AC3.5.1.original.mkv"))
    assert cll is None


def test_une_source_sdr_ne_rend_rien():
    master, cll = _hdr10_metadata(_fichier("The zookeeper s wife 2017.mkv"))
    assert master is None and cll is None


def test_un_fichier_absent_ne_leve_pas():
    """L'échec de lecture fait retomber le mode quality sur un encodage sans
    métadonnées fines, pas sur une erreur."""
    from pathlib import Path

    assert _hdr10_metadata(Path("inexistant_pour_le_test.mkv")) == (None, None)


# ─── La commande d'encodage porte enfin les métadonnées ───────────────────────

def test_le_mode_quality_injecte_master_display_et_max_cll():
    from core import profiles as pm
    from core.decision import decide, force_skip_to_encode
    from core.encoder import build_command
    from core.platform import GPU, OS, PlatformProfile
    from core.scanner import scan

    info = scan(_fichier(
        "Kingdom.of.the.Planet.of.the.Apes.2024.MULTi.VFF.4K.2160p."
        "HDR10Plus.DV.WEBRip.DDP.Atmos.7.1.x265.mkv"))
    plat = PlatformProfile(os=OS.WINDOWS, gpu=GPU.NVIDIA, hwaccel="cuda",
                           encoder_hevc="hevc_nvenc", encoder_h264="h264_nvenc",
                           encoder_av1="av1_nvenc")
    dec = force_skip_to_encode(decide(info, pm.load_all()["cinema_4k_quality"]))
    params = build_command(dec, plat)[
        build_command(dec, plat).index("-x265-params") + 1]

    assert "master-display=G(" in params, params
    assert "max-cll=" in params, params
    # Et le mode reste sur libx265 : c'est sa raison d'être.
    assert "libx265" in build_command(dec, plat)
