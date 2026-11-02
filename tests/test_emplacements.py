r"""
tests/test_emplacements.py — Les partages nommés de l'accueil (IE-161).

« Films » ouvre `\\10.0.0.10\Films` comme un lecteur. La connexion passe par
Windows (`WNetAddConnection2W`), avec l'identité du Gestionnaire
d'identifiants ; IRIS coupe à sa sortie ce qu'il a ouvert, et rien d'autre.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from textual.widgets import DataTable

from core import emplacements as emp
from core.i18n import _

FILMS = Path(r"\\10.0.0.10\Films")


def _cfg(*entrees) -> dict:
    return {"emplacements": list(entrees)}


# ─── Lecture de config.toml ──────────────────────────────────────────────────

def test_les_emplacements_se_lisent_dans_l_ordre():
    lus = emp.lire(_cfg({"libelle": "Films", "chemin": "\\\\10.0.0.10\\Films\\"},
                        {"libelle": "Download", "chemin": r"\\10.0.0.11\Download"}))
    assert [(e.libelle, e.chemin) for e in lus] == [
        ("Films", FILMS), ("Download", Path(r"\\10.0.0.11\Download"))]
    assert all(e.reseau for e in lus)


def test_une_entree_incomplete_est_ecartee_sans_bloquer_les_autres():
    lus = emp.lire(_cfg({"libelle": "", "chemin": r"\\a\b"}, {"chemin": r"\\a\c"},
                        "texte", {"libelle": "Films", "chemin": str(FILMS)}))
    assert [e.libelle for e in lus] == ["Films"]
    assert emp.lire({"emplacements": "pas une liste"}) == []
    assert emp.lire({}) == []


def test_un_dossier_local_est_un_emplacement_sans_connexion():
    (e,) = emp.lire(_cfg({"libelle": "Rushes", "chemin": r"D:\Rushes"}))
    assert not e.reseau


# ─── Fil d'Ariane ────────────────────────────────────────────────────────────

def test_le_fil_d_ariane_montre_le_libelle():
    lus = emp.lire(_cfg({"libelle": "Films", "chemin": str(FILMS)}))
    assert emp.fil_d_ariane(lus, FILMS) == "Films"
    assert emp.fil_d_ariane(lus, FILMS / "Saison 1") == "Films › Saison 1"
    assert emp.fil_d_ariane(lus, Path(r"D:\Films")) == r"D:\Films"


def test_le_navigateur_liste_les_emplacements_sous_les_volumes():
    from tui.widgets.file_tree import FileNavigator, list_volumes
    nav = FileNavigator(Path.cwd(), start_virtual=True)
    nav.emplacements = emp.lire(_cfg({"libelle": "Films", "chemin": str(FILMS)}))
    assert nav.list_subdirs() == list_volumes() + [FILMS]
    nav._current, nav._virtual = FILMS / "Saison 1", False
    assert nav.breadcrumb() == "Films › Saison 1"
    assert nav.go_up() and nav.current == FILMS
    assert nav.go_up() and nav.is_virtual     # ⌫ à la racine du partage : l'accueil


# ─── Connexion ───────────────────────────────────────────────────────────────

class _FauxMpr:
    def __init__(self, code: int = 0) -> None:
        self.code = code
        self.ajouts: list[str] = []
        self.coupures: list[tuple[str, bool]] = []

    def WNetAddConnection2W(self, ressource, mdp, compte, drapeaux):
        self.ajouts.append(ressource._obj.lpRemoteName)
        assert mdp is None and compte is None      # l'identité vient de Windows
        return self.code

    def WNetCancelConnection2W(self, nom, drapeaux, forcer):
        self.coupures.append((nom, forcer))
        return 0


@pytest.fixture
def faux_windows(monkeypatch):
    if sys.platform != "win32":
        pytest.skip("connexion SMB : Windows seulement")
    vrai = emp._mpr
    faux = _FauxMpr()

    def _mpr():
        ctypes, wintypes, _m, ressource = vrai()
        return ctypes, wintypes, faux, ressource

    existantes: set[str] = set()
    monkeypatch.setattr(emp, "_mpr", _mpr)
    monkeypatch.setattr(emp, "connexions_existantes", lambda: set(existantes))
    monkeypatch.setattr(emp, "_ouvertes", set())
    return faux, existantes


def test_iris_coupe_a_la_sortie_ce_qu_il_a_ouvert(faux_windows):
    faux, _existantes = faux_windows
    films = emp.Emplacement("Films", FILMS)
    emp.connecter(films)
    emp.connecter(films)                       # déjà ouverte : pas de second appel
    assert faux.ajouts == [r"\\10.0.0.10\Films"]
    assert emp.cle(FILMS) in emp.connectes()
    emp.deconnecter_tout()
    # Sans forcer : un Explorateur ouvert sur le partage n'est pas cassé.
    # Windows ignore la casse d'un nom de partage.
    assert faux.coupures == [(r"\\10.0.0.10\films", False)]


def test_une_connexion_existante_n_est_ni_rouverte_ni_coupee(faux_windows):
    faux, existantes = faux_windows
    existantes.add(r"\\10.0.0.10\films")         # un lecteur réseau de l'utilisateur
    emp.connecter(emp.Emplacement("Films", FILMS))
    emp.deconnecter_tout()
    assert faux.ajouts == [] and faux.coupures == []


@pytest.mark.parametrize("code", [1219, 1326, 53, 99999])
def test_un_refus_donne_sa_cause_en_clair(faux_windows, code):
    faux, _existantes = faux_windows
    faux.code = code
    with pytest.raises(emp.ConnexionRefusee) as refus:
        emp.connecter(emp.Emplacement("Films", FILMS))
    assert refus.value.code == code
    assert str(refus.value).startswith("Films")
    assert str(refus.value) == _("{location}: {cause}.").format(
        location="Films", cause=emp._cause(code))
    assert emp.connectes() == set()              # rien à couper à la sortie


@pytest.mark.skipif(sys.platform != "win32", reason="Windows seulement")
def test_un_partage_inexistant_est_refuse_par_windows(monkeypatch):
    monkeypatch.setattr(emp, "_ouvertes", set())
    with pytest.raises(emp.ConnexionRefusee) as refus:
        emp.connecter(emp.Emplacement("Essai", Path(r"\\127.0.0.1\iris_inexistant")))
    assert refus.value.code == 67


# ─── Accueil ─────────────────────────────────────────────────────────────────

async def _accueil(cfg_emplacements: list, ouvrir: Path | None = None) -> dict:
    from tui.app import IrisEncodeApp
    releve: dict = {}
    app = IrisEncodeApp(start_path=Path.cwd())
    app.cfg["emplacements"] = cfg_emplacements
    notes: list[str] = []
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause(0.5)
        ecran = app.screen
        ecran.notify = lambda msg, **k: notes.append(str(msg))
        table = ecran.query_one(DataTable)
        releve["lignes"] = [str(table.get_row_at(i)[0]) for i in range(table.row_count)]
        releve["chemins"] = [p for _t, p in ecran._rows]
        if ouvrir is not None:
            ecran._nav.enter(ouvrir)
            ecran._refresh_view()
            for _ in range(50):
                await pilot.pause(0.1)
                if ecran._nav.is_virtual or not ecran._nav.current == ouvrir:
                    break
            await pilot.pause(0.3)
            releve["revenu"] = ecran._nav.is_virtual
            releve["ariane"] = ecran._nav.breadcrumb()
    releve["notes"] = notes
    return releve


def test_l_accueil_montre_l_emplacement_sous_son_libelle(tmp_path, monkeypatch):
    from core import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "save", lambda *a, **k: None)
    r = asyncio.run(_accueil([{"libelle": "Rushes", "chemin": str(tmp_path)}]))
    assert r["chemins"][-1] == tmp_path
    assert r["lignes"][-1].startswith("🌐 Rushes")


def test_un_emplacement_refuse_ramene_a_l_accueil_avec_la_cause(tmp_path, monkeypatch):
    from core import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "save", lambda *a, **k: None)

    def refuser(e):
        raise emp.ConnexionRefusee(1326, f"{e.libelle}: refusé.")

    monkeypatch.setattr(emp, "connecter", refuser)
    r = asyncio.run(_accueil([{"libelle": "Rushes", "chemin": str(tmp_path)}],
                             ouvrir=tmp_path))
    assert r["revenu"]
    assert r["notes"] == ["Rushes: refusé."]


def test_un_emplacement_ouvert_montre_son_libelle_dans_le_fil(tmp_path, monkeypatch):
    from core import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "save", lambda *a, **k: None)
    (tmp_path / "Saison 1").mkdir()
    r = asyncio.run(_accueil([{"libelle": "Rushes", "chemin": str(tmp_path)}],
                             ouvrir=tmp_path / "Saison 1"))
    assert not r["revenu"]
    assert r["ariane"] == "Rushes › Saison 1"
