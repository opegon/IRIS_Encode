"""
tests/test_updater.py — Mise à jour d'IRIS ENCODE depuis la release « Latest ».

Réseau simulé, archives réelles fabriquées dans un dossier temporaire. Ce qui
est verrouillé : on ne met à jour que vers plus récent, on ne touche jamais aux
fichiers personnels, une archive douteuse est refusée, un échec restaure tout,
et rien de tout cela n'empêche l'application de démarrer.
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import updater  # noqa: E402

RACINE_DEPOT = Path(__file__).resolve().parent.parent


# ─── Fabrication ──────────────────────────────────────────────────────────────

def _archive(chemin: Path, version: str, extra: dict[str, str] | None = None,
             sans: set[str] = frozenset()) -> Path:
    fichiers = {
        "version.py": f'__version__ = "{version}"\n',
        "main.py": f"# main {version}\n",
        "launch.bat": f"REM {version}\n",
        "updater.py": "# updater\n",
        "core/decision.py": f"# decision {version}\n",
    }
    fichiers.update(extra or {})
    with zipfile.ZipFile(chemin, "w") as z:
        for nom, texte in fichiers.items():
            if nom not in sans:
                z.writestr(nom, texte)
    return chemin


def _installation(racine: Path, version: str = "0.8.9.0") -> Path:
    racine.mkdir(parents=True, exist_ok=True)
    (racine / "version.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    (racine / "main.py").write_text("# main ancien\n", encoding="utf-8")
    (racine / "launch.bat").write_text("REM ancien\n", encoding="utf-8")
    (racine / "updater.py").write_text("# updater ancien\n", encoding="utf-8")
    (racine / "core").mkdir(exist_ok=True)
    (racine / "core" / "decision.py").write_text("# decision ancien\n", encoding="utf-8")
    # Ce que l'utilisateur possède et que l'archive ne livre pas.
    (racine / "config.toml").write_text('[opensubtitles]\napi_key = "secret"\n', encoding="utf-8")
    (racine / "profiles.toml").write_text("[mon_profil]\n", encoding="utf-8")
    (racine / "bin").mkdir(exist_ok=True)
    (racine / "bin" / "ffmpeg.exe").write_bytes(b"binaire")
    (racine / ".venv").mkdir(exist_ok=True)
    (racine / ".venv" / "pyvenv.cfg").write_text("home = x\n", encoding="utf-8")
    return racine


class _Reponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def _reseau(api: dict | None = None, fichiers: dict[str, bytes] | None = None,
            appels: list | None = None):
    """Un faux `urlopen` : l'API rend `api`, une URL d'archive rend son contenu."""
    def ouvrir(requete, timeout=None):
        url = requete.full_url
        if appels is not None:
            appels.append(url)
        if url == updater.API:
            if api is None:
                raise OSError("réseau injoignable")
            return _Reponse(json.dumps(api).encode("utf-8"))
        return _Reponse((fichiers or {})[url])
    return ouvrir


def _release_pour(archive: Path, tag: str, digest: str | None = None) -> dict:
    contenu = archive.read_bytes()
    return {
        "tag_name": tag,
        "assets": [{
            "name": archive.name,
            "browser_download_url": f"https://example.invalid/{archive.name}",
            "digest": digest if digest is not None
                      else "sha256:" + hashlib.sha256(contenu).hexdigest(),
        }],
    }


def _scenario(tmp_path: Path, tag: str = "v0.8.9.1", **kw):
    racine = _installation(tmp_path / "iris")
    archive = _archive(tmp_path / f"iris_encode_{tag}.zip", tag.lstrip("v"), **kw)
    release = _release_pour(archive, tag)
    ouvrir = _reseau(release, {release["assets"][0]["browser_download_url"]: archive.read_bytes()})
    return racine, ouvrir


# ─── Versions et réglage ──────────────────────────────────────────────────────

def test_les_versions_se_comparent_en_nombres():
    assert updater.version_tuple("v0.8.10.0") > updater.version_tuple("0.8.9.1")
    assert updater.version_tuple("v0.8.9.1") > updater.version_tuple("0.8.9.0")
    assert updater.version_tuple("V0.9.0.0") == (0, 9, 0, 0)


def test_la_version_installee_est_celle_du_depot():
    from version import __version__
    assert updater.version_locale(RACINE_DEPOT) == __version__


@pytest.mark.parametrize("contenu, attendu", [
    (None, "ask"),
    ("[updates]\ncheck_on_startup = true\n", "ask"),
    ('[updates]\napp = "auto"\n', "auto"),
    ('[updates]\napp = "off"\n', "off"),
    ('[updates]\napp = "toujours"\n', "ask"),
    ("ceci n'est pas du toml [", "ask"),
])
def test_le_reglage_demande_par_defaut(tmp_path, contenu, attendu):
    if contenu is not None:
        (tmp_path / "config.toml").write_text(contenu, encoding="utf-8")
    assert updater.mode(tmp_path) == attendu


# ─── Confirmation ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("reponse, attendu", [
    ("", True), ("O", True), ("oui", True), ("y", True),
    ("n", False), ("non", False), ("plus tard", False),
])
def test_entree_vaut_oui(reponse, attendu):
    assert updater.demander("0.8.9.0", "v0.8.9.1", entree=lambda _: reponse,
                            interactif=lambda: True) is attendu


def test_sans_console_on_n_installe_rien():
    """Un « oui » présélectionné n'est pas un consentement quand personne ne
    peut répondre."""
    def jamais(_):
        raise AssertionError("aucune question ne doit être posée")
    assert updater.demander("0.8.9.0", "v0.8.9.1", entree=jamais,
                            interactif=lambda: False) is False


def test_ctrl_c_a_la_question_vaut_non():
    def interrompre(_):
        raise KeyboardInterrupt
    assert updater.demander("0.8.9.0", "v0.8.9.1", entree=interrompre,
                            interactif=lambda: True) is False


# ─── Le parcours complet ──────────────────────────────────────────────────────

def test_une_release_plus_recente_s_installe(tmp_path):
    racine, ouvrir = _scenario(tmp_path)
    code = updater.main(racine, ouvrir=ouvrir, entree=lambda _: "",
                        interactif=lambda: True)
    assert code == updater.CODE_MIS_A_JOUR
    assert updater.version_locale(racine) == "0.8.9.1"
    assert (racine / "core" / "decision.py").read_text() == "# decision 0.8.9.1\n"


def test_les_fichiers_personnels_ne_bougent_pas(tmp_path):
    racine, ouvrir = _scenario(tmp_path)
    avant = {p: p.read_bytes() for p in (
        racine / "config.toml", racine / "profiles.toml",
        racine / "bin" / "ffmpeg.exe", racine / ".venv" / "pyvenv.cfg")}
    updater.main(racine, ouvrir=ouvrir, entree=lambda _: "", interactif=lambda: True)
    assert {p: p.read_bytes() for p in avant} == avant


@pytest.mark.parametrize("tag", ["v0.8.9.0", "v0.8.8.10"])
def test_rien_quand_la_release_n_est_pas_plus_recente(tmp_path, tag):
    racine, ouvrir = _scenario(tmp_path, tag=tag)
    assert updater.main(racine, ouvrir=ouvrir, entree=lambda _: "",
                        interactif=lambda: True) == 0
    assert updater.version_locale(racine) == "0.8.9.0"


def test_un_refus_laisse_tout_en_place(tmp_path):
    racine, ouvrir = _scenario(tmp_path)
    assert updater.main(racine, ouvrir=ouvrir, entree=lambda _: "n",
                        interactif=lambda: True) == 0
    assert updater.version_locale(racine) == "0.8.9.0"


def test_le_mode_auto_ne_demande_rien(tmp_path):
    racine, ouvrir = _scenario(tmp_path)
    (racine / "config.toml").write_text('[updates]\napp = "auto"\n', encoding="utf-8")
    def jamais(_):
        raise AssertionError("le mode auto ne pose pas de question")
    assert updater.main(racine, ouvrir=ouvrir, entree=jamais,
                        interactif=lambda: True) == updater.CODE_MIS_A_JOUR


def test_le_mode_off_n_interroge_pas_github(tmp_path):
    racine, _ = _scenario(tmp_path)
    (racine / "config.toml").write_text('[updates]\napp = "off"\n', encoding="utf-8")
    appels: list = []
    assert updater.main(racine, ouvrir=_reseau(None, appels=appels)) == 0
    assert appels == []


def test_un_depot_git_n_est_jamais_mis_a_jour(tmp_path):
    """Écraser un clone par une archive détruirait le travail en cours."""
    racine, ouvrir = _scenario(tmp_path)
    (racine / ".git").mkdir()
    assert updater.main(racine, ouvrir=ouvrir, entree=lambda _: "",
                        interactif=lambda: True) == 0
    assert updater.version_locale(racine) == "0.8.9.0"


def test_hors_ligne_l_application_demarre(tmp_path):
    racine = _installation(tmp_path / "iris")
    assert updater.main(racine, ouvrir=_reseau(None), entree=lambda _: "",
                        interactif=lambda: True) == 0


# ─── Ce qui est refusé ────────────────────────────────────────────────────────

def test_une_empreinte_fausse_est_refusee(tmp_path, capsys):
    racine = _installation(tmp_path / "iris")
    archive = _archive(tmp_path / "iris_encode_v0.8.9.1.zip", "0.8.9.1")
    release = _release_pour(archive, "v0.8.9.1", digest="sha256:" + "0" * 64)
    ouvrir = _reseau(release, {release["assets"][0]["browser_download_url"]: archive.read_bytes()})
    assert updater.main(racine, ouvrir=ouvrir, entree=lambda _: "",
                        interactif=lambda: True) == 0
    assert updater.version_locale(racine) == "0.8.9.0"
    assert "digest" in capsys.readouterr().out


def test_une_release_sans_empreinte_est_refusee(tmp_path):
    racine = _installation(tmp_path / "iris")
    archive = _archive(tmp_path / "iris_encode_v0.8.9.1.zip", "0.8.9.1")
    release = _release_pour(archive, "v0.8.9.1", digest="")
    ouvrir = _reseau(release, {release["assets"][0]["browser_download_url"]: archive.read_bytes()})
    assert updater.main(racine, ouvrir=ouvrir, entree=lambda _: "",
                        interactif=lambda: True) == 0
    assert updater.version_locale(racine) == "0.8.9.0"


@pytest.mark.parametrize("fautive", [
    {"extra": {"config.toml": "[écrasé]\n"}},
    {"extra": {"bin/ffmpeg.exe": "remplacé"}},
    {"extra": {"../hors_du_dossier.txt": "x"}},
    {"sans": {"updater.py"}},
])
def test_une_archive_douteuse_est_refusee(tmp_path, fautive):
    racine, ouvrir = _scenario(tmp_path, **fautive)
    assert updater.main(racine, ouvrir=ouvrir, entree=lambda _: "",
                        interactif=lambda: True) == 0
    assert updater.version_locale(racine) == "0.8.9.0"
    assert "secret" in (racine / "config.toml").read_text()
    assert not (tmp_path / "hors_du_dossier.txt").exists()


def test_une_archive_refusee_ne_reste_pas_sur_le_disque(tmp_path):
    racine, ouvrir = _scenario(tmp_path, sans={"updater.py"})
    updater.main(racine, ouvrir=ouvrir, entree=lambda _: "", interactif=lambda: True)
    assert not list((racine / updater.TRAVAIL).glob("*.zip"))


def test_une_archive_d_une_autre_version_est_refusee(tmp_path):
    racine = _installation(tmp_path / "iris")
    archive = _archive(tmp_path / "iris_encode_v0.8.9.1.zip", "0.8.9.7")
    with pytest.raises(updater.ErreurMaj, match="version"):
        updater.appliquer(racine, archive, "v0.8.9.1")


# ─── Retrait, manifeste, restauration ─────────────────────────────────────────

def test_ce_qui_n_est_plus_livre_est_retire(tmp_path):
    racine = _installation(tmp_path / "iris")
    v1 = _archive(tmp_path / "v1.zip", "0.8.9.1", extra={"core/ancien.py": "# ancien\n"})
    updater.appliquer(racine, v1, "0.8.9.1")
    assert (racine / "core" / "ancien.py").exists()
    v2 = _archive(tmp_path / "v2.zip", "0.8.9.2")
    updater.appliquer(racine, v2, "0.8.9.2")
    assert not (racine / "core" / "ancien.py").exists()
    assert (racine / "config.toml").exists()


def test_sans_manifeste_rien_n_est_retire(tmp_path):
    """Première mise à jour : on ne supprime pas ce qu'on ne sait pas avoir installé."""
    racine = _installation(tmp_path / "iris")
    (racine / "core" / "a_moi.py").write_text("# à l'utilisateur\n", encoding="utf-8")
    updater.appliquer(racine, _archive(tmp_path / "v.zip", "0.8.9.1"), "0.8.9.1")
    assert (racine / "core" / "a_moi.py").exists()


def test_un_echec_en_cours_restaure_la_version_precedente(tmp_path, monkeypatch):
    racine = _installation(tmp_path / "iris")
    archive = _archive(tmp_path / "v.zip", "0.8.9.1", extra={"core/nouveau.py": "# neuf\n"})
    vrai = updater.shutil.copyfileobj
    compte = {"n": 0}

    def casse(src, dst, *a):
        compte["n"] += 1
        if compte["n"] == 3:
            raise OSError("disque plein")
        return vrai(src, dst, *a)

    monkeypatch.setattr(updater.shutil, "copyfileobj", casse)
    with pytest.raises(OSError):
        updater.appliquer(racine, archive, "0.8.9.1")
    assert updater.version_locale(racine) == "0.8.9.0"
    assert (racine / "main.py").read_text() == "# main ancien\n"
    assert not (racine / "core" / "nouveau.py").exists()


# ─── Cache ────────────────────────────────────────────────────────────────────

def test_github_n_est_interroge_qu_une_fois_par_ttl(tmp_path):
    racine = _installation(tmp_path / "iris")
    archive = _archive(tmp_path / "iris_encode_v0.8.9.1.zip", "0.8.9.1")
    appels: list = []
    ouvrir = _reseau(_release_pour(archive, "v0.8.9.1"), appels=appels)
    updater.derniere_release(racine, maintenant=1000.0, ouvrir=ouvrir)
    updater.derniere_release(racine, maintenant=1000.0 + updater.TTL - 1, ouvrir=ouvrir)
    assert appels.count(updater.API) == 1
    updater.derniere_release(racine, maintenant=1000.0 + updater.TTL + 1, ouvrir=ouvrir)
    assert appels.count(updater.API) == 2


def test_le_ttl_reste_sous_la_limite_de_github():
    """60 appels par heure et par IP sans jeton : une installation en fait au plus un."""
    assert updater.TTL >= 3600


def test_une_autre_version_installee_ne_croit_pas_le_cache(tmp_path):
    """Le cache écrit par la v0.8.9.0 ne doit pas cacher une release plus récente
    à la version qui lui succède — ni l'inverse."""
    racine = _installation(tmp_path / "iris")
    archive = _archive(tmp_path / "iris_encode_v0.8.9.1.zip", "0.8.9.1")
    appels: list = []
    ouvrir = _reseau(_release_pour(archive, "v0.8.9.1"), appels=appels)
    updater.derniere_release(racine, maintenant=1000.0, ouvrir=ouvrir, installee="0.8.9.0")
    updater.derniere_release(racine, maintenant=1001.0, ouvrir=ouvrir, installee="0.8.9.0")
    assert appels.count(updater.API) == 1
    updater.derniere_release(racine, maintenant=1002.0, ouvrir=ouvrir, installee="0.8.9.1")
    assert appels.count(updater.API) == 2


def test_hors_ligne_le_cache_perime_sert_encore(tmp_path):
    racine = _installation(tmp_path / "iris")
    archive = _archive(tmp_path / "iris_encode_v0.8.9.1.zip", "0.8.9.1")
    updater.derniere_release(racine, maintenant=0.0,
                             ouvrir=_reseau(_release_pour(archive, "v0.8.9.1")))
    connue = updater.derniere_release(racine, maintenant=10 * updater.TTL,
                                      ouvrir=_reseau(None))
    assert connue["tag"] == "v0.8.9.1"


# ─── Ce que le code doit rester ───────────────────────────────────────────────

def test_updater_ne_depend_que_de_la_bibliotheque_standard():
    """Il remplace les modules de l'application : il ne peut en importer aucun,
    ni une dépendance que la mise à jour elle-même pourrait changer."""
    arbre = ast.parse((RACINE_DEPOT / "updater.py").read_text(encoding="utf-8"))
    modules = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            modules |= {a.name.split(".")[0] for a in noeud.names}
        elif isinstance(noeud, ast.ImportFrom) and noeud.module:
            modules.add(noeud.module.split(".")[0])
    etrangers = modules - set(sys.stdlib_module_names) - {"__future__"}
    assert not etrangers, etrangers


def test_launch_bat_relance_depuis_un_bloc_unique():
    """cmd relit un .bat par position : remplacé en cours d'exécution, la suite
    serait lue de travers. L'appel et la relance doivent tenir dans un bloc
    ( ), lu en entier avant de s'exécuter, et précéder le lancement de main.py."""
    texte = (RACINE_DEPOT / "launch.bat").read_text(encoding="utf-8")
    m = re.search(r'^\(\n(.*?)^\)\n', texte.replace("\r\n", "\n"), re.S | re.M)
    assert m, "bloc ( ) introuvable"
    bloc = m.group(1)
    assert "updater.py" in bloc
    assert re.search(r'if errorlevel 10\b', bloc)
    assert '"%~f0" %*' in bloc and "exit /b" in bloc
    commandes = [l for l in texte.splitlines() if not l.lstrip().upper().startswith("REM")]
    appels = [l for l in commandes if "updater.py" in l]
    assert len(appels) == 1, "updater.py n'est appelé qu'une fois, dans le bloc"
    assert texte.index(appels[0]) < texte.index('"%PY%" main.py')


# ─── CR-106 — fichiers protégés, sans égard à la casse ───────────────────────

@pytest.mark.parametrize("nom", ["Config.toml", "PROFILES.TOML", "claude.md",
                                 "BIN/ffmpeg.exe", ".VENV/Scripts/python.exe",
                                 "Resources_Files/a.mkv"])
def test_la_casse_ne_contourne_pas_la_protection(nom):
    assert updater._protege(nom)


def test_une_archive_avec_config_en_majuscule_est_refusee(tmp_path):
    archive = _archive(tmp_path / "iris_encode_v0.8.9.1.zip", "0.8.9.1",
                       extra={"Config.toml": "[pirate]\n"})
    with pytest.raises(updater.ErreurMaj, match="personal file"):
        updater.contenu_archive(archive, "0.8.9.1")


def test_un_fichier_au_nom_voisin_reste_livrable():
    assert not updater._protege("core/config.py")
    assert not updater._protege("binaire.txt")
