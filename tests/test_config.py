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


# ─── Le profil actif est un état de session, pas une propriété du fichier ────
#
# Sans mémoire, l'actif au démarrage était le premier de profiles.toml. Un
# profil `delete_source = true` posé en tête devenait donc actif au lancement,
# et effaçait les sources d'un lot lancé sans regarder.

def test_le_profil_actif_par_defaut_est_le_premier_du_fichier():
    """Rien de mémorisé : on prend le premier, pas un nom codé en dur."""
    cfg = cfg_mod._deep_merge({}, cfg_mod._DEFAULTS)
    assert cfg_mod.get_active_profile(cfg, ["b", "a", "c"]) == "b"


def test_le_profil_memorise_l_emporte_sur_l_ordre_du_fichier():
    cfg = cfg_mod._deep_merge(cfg_mod._DEFAULTS, {"app": {"active_profile": "c"}})
    assert cfg_mod.get_active_profile(cfg, ["b", "a", "c"]) == "c"


def test_un_profil_memorise_disparu_retombe_sur_le_premier():
    """Effacé ou renommé à la main dans profiles.toml : on ne plante pas."""
    cfg = cfg_mod._deep_merge(cfg_mod._DEFAULTS,
                              {"app": {"active_profile": "envole"}})
    assert cfg_mod.get_active_profile(cfg, ["b", "a"]) == "b"


def test_memoriser_le_profil_actif_ecrit_config_toml(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg_mod, "CONFIG_PATH", tmp_path / "config.toml")
    cfg = cfg_mod._deep_merge({}, cfg_mod._DEFAULTS)
    cfg_mod.set_active_profile(cfg, "film_hdr")
    assert cfg_mod.load()["app"]["active_profile"] == "film_hdr"


def test_lalerte_suppression_lit_le_profil_pas_le_libelle():
    """UX-29 : `"oui" in libellé` ne survivrait pas à la traduction."""
    from core.profiles import Profile
    from tui.common import cellules_profil

    sup = Profile.__new__(Profile); sup.data = {"delete_source": True}
    gar = Profile.__new__(Profile); gar.data = {"delete_source": False}
    assert "dark_orange" in str(cellules_profil("a", sup, False)[-1].style)
    assert "dark_orange" not in str(cellules_profil("b", gar, False)[-1].style)


def test_la_couleur_hd_audio_lit_le_profil_pas_le_libelle():
    """L-43 (IE-113) : récidive d'UX-29 sur la colonne HD audio. Le libellé
    traduit (« yes ») ne doit pas éteindre la colonne."""
    from core.profiles import Profile
    from tui.common import cellules_profil

    def profil(preserve: bool, libelle: str) -> Profile:
        p = Profile.__new__(Profile)
        p.data = {"preserve_hd_audio": preserve}
        champs = Profile.summary_fields(p) | {"hd_audio": libelle}
        p.summary_fields = lambda: champs
        return p

    assert "dim" not in str(cellules_profil("a", profil(True, "yes"), False)[5].style)
    assert "dim" in str(cellules_profil("b", profil(False, "no"), False)[5].style)


def test_aucune_couleur_ne_se_decide_sur_oui_ou_non():
    """L-43 : plus aucune comparaison à « oui »/« non » affichés."""
    import re
    from pathlib import Path
    racine = Path(__file__).resolve().parent.parent
    motif = re.compile(r"""(==|!=|\bin)\s*["'](⚠ )?(oui|non)["']""")
    fautifs = [f"{p.relative_to(racine)}:{n}"
               for d in ("core", "tui") for p in (racine / d).rglob("*.py")
               for n, l in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
               if motif.search(l)]
    assert not fautifs, fautifs


def test_choix_et_gestion_des_profils_ont_une_seule_presentation():
    """UX-13 : mêmes en-têtes, même 4K, même nom, des deux côtés."""
    import inspect
    from core.profiles import Profile
    from tui.common import PROFIL_COLONNES, cellules_profil, largeurs_colonnes
    from tui.screens import config, profile_picker
    for mod in (config, profile_picker):
        src = inspect.getsource(mod)
        assert "PROFIL_COLONNES" in src and "cellules_profil" in src, mod.__name__
    p = Profile.__new__(Profile)
    p.data = {"keep_4k": False, "bitrate_4k_kbps": 3500, "delete_source": True}
    cellules = cellules_profil("series_basic", p, True)
    assert cellules[0].plain == "series_basic ✓"          # ni crochets ni capitales
    assert cellules[2].plain == "→ 1080p"
    assert cellules[-1].plain == "⚠ suppr."
    assert largeurs_colonnes(PROFIL_COLONNES, [cellules])[-1] >= cellules[-1].cell_len
