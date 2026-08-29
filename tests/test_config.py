"""
tests/test_config.py — Isolation de la configuration vis-à-vis des défauts.

Le piège que ces tests verrouillent : une fusion qui partage ses
sous-dictionnaires rend un `cfg` dont les branches *sont* celles de
`_DEFAULTS`. La moindre écriture corrompt alors les valeurs par défaut du
module pour tout le reste du processus.

Les deux sens comptent, et le second a été manqué. `_deep_merge({}, _DEFAULTS)`
— la machine sans `config.toml` — recopie tout, parce que la récursion suit
`override`. `_deep_merge(_DEFAULTS, user)` — la machine qui en a un — ne
recopiait que ce que `user` mentionnait : un `config.toml` sans section
`[tui]` rendait un cfg dont `['tui']` était celui du module, et le premier
`reset_browser_columns` y supprimait les colonnes par défaut.
"""
from __future__ import annotations

from core import config as cfg_mod


def test_merge_never_shares_a_branch():
    cfg = cfg_mod._deep_merge({}, cfg_mod._DEFAULTS)
    assert cfg["tui"] is not cfg_mod._DEFAULTS["tui"]
    assert cfg["tui"]["browser"] is not cfg_mod._DEFAULTS["tui"]["browser"]
    assert (cfg["tui"]["browser"]["columns"]
            is not cfg_mod._DEFAULTS["tui"]["browser"]["columns"])


def test_writing_to_cfg_leaves_the_defaults_alone():
    cfg = cfg_mod._deep_merge({}, cfg_mod._DEFAULTS)
    cfg_mod.set_column_width(cfg, "fichier", 999)
    assert cfg_mod._DEFAULTS["tui"]["browser"]["columns"]["fichier"] != 999


def test_resetting_columns_leaves_the_defaults_alone():
    """Le cas qui a cassé : sans config.toml, le reset vidait _DEFAULTS."""
    cfg = cfg_mod._deep_merge({}, cfg_mod._DEFAULTS)
    cfg_mod.reset_browser_columns(cfg)
    assert "columns" in cfg_mod._DEFAULTS["tui"]["browser"]
    # Et les largeurs restent lisibles ensuite
    assert cfg_mod.get_column_widths(cfg)["fichier"] == 50


def test_reset_then_read_gives_the_defaults():
    cfg = cfg_mod._deep_merge({}, cfg_mod._DEFAULTS)
    cfg_mod.set_column_width(cfg, "fichier", 999)
    cfg_mod.reset_browser_columns(cfg)
    assert cfg_mod.get_column_widths(cfg)["fichier"] == 50


def test_user_values_still_override_the_defaults():
    cfg = cfg_mod._deep_merge(
        cfg_mod._DEFAULTS, {"tui": {"browser": {"columns": {"audio": 42}}}})
    largeurs = cfg_mod.get_column_widths(cfg)
    assert largeurs["audio"] == 42
    assert largeurs["fichier"] == 50        # les autres restent aux défauts


def test_reset_is_harmless_without_the_section():
    cfg = {"app": {"language": "fr"}}
    cfg_mod.reset_browser_columns(cfg)      # ne doit pas lever
    assert cfg_mod.get_column_widths(cfg)["fichier"] == 50


# ─── L'autre sens : un config.toml qui ne dit rien d'une section ─────────────

def test_merge_never_shares_a_branch_absent_from_the_user_file():
    """La branche que l'utilisateur ne mentionne pas est recopiée elle aussi."""
    cfg = cfg_mod._deep_merge(cfg_mod._DEFAULTS, {"app": {"language": "en"}})
    assert cfg["tui"] is not cfg_mod._DEFAULTS["tui"]
    assert cfg["tui"]["browser"] is not cfg_mod._DEFAULTS["tui"]["browser"]
    assert (cfg["tui"]["browser"]["columns"]
            is not cfg_mod._DEFAULTS["tui"]["browser"]["columns"])


def test_a_config_without_the_tui_section_survives_a_reset():
    """Le cas qui cassait : config.toml présent, `[tui]` absent."""
    cfg = cfg_mod._deep_merge(cfg_mod._DEFAULTS, {"app": {"language": "fr"}})
    cfg_mod.reset_browser_columns(cfg)
    assert "columns" in cfg_mod._DEFAULTS["tui"]["browser"]
    assert cfg_mod.get_column_widths(cfg)["fichier"] == 50
