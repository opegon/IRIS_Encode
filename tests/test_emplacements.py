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

async def _accueil_affiche(pilot, ecran, delai: float = 15) -> None:
    """Attend que l'accueil montre son dernier listage. Mesurer l'espace d'un
    lecteur réseau peut prendre des secondes : une pause fixe ne suffit pas."""
    for _ in range(int(delai / 0.1)):
        if ecran._rows and ecran._epoch_affichee == ecran._scan_epoch:
            return
        await pilot.pause(0.1)


async def _accueil(cfg_emplacements: list, ouvrir: Path | None = None) -> dict:
    from tui.app import IrisEncodeApp
    releve: dict = {}
    app = IrisEncodeApp(start_path=Path.cwd())
    app.cfg["emplacements"] = cfg_emplacements
    notes: list[str] = []
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause(0.3)
        ecran = app.screen
        await _accueil_affiche(pilot, ecran)
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



# ═══ IE-162 — l'écran de gestion ═════════════════════════════════════════════

def test_le_serveur_d_un_chemin():
    assert emp.serveur(FILMS) == "10.0.0.10"
    assert emp.serveur(r"\\nas") == "nas"
    assert emp.serveur(r"D:\Films") is None
    assert emp.serveur("") is None


@pytest.mark.parametrize("libelle, chemin, attendu", [
    ("", r"\\nas\x", "The label is required."),
    ("films", r"\\nas\x", "Another location already has this label."),
    ("X", "", "The path is required."),
    ("X", r"\\nas", r"A network path reads \\server\share."),
    ("X", "\\\\nas\\\\", r"A network path reads \\server\share."),
])
def test_la_saisie_invalide_est_refusee(libelle, chemin, attendu):
    liste = [emp.Emplacement("Films", FILMS)]
    assert emp.valider(liste, libelle, chemin) == _(attendu)


def test_un_chemin_deja_pris_est_refuse_sauf_pour_lui_meme():
    films = emp.Emplacement("Films", FILMS)
    liste = [films]
    assert emp.valider(liste, "Autre", "\\\\10.0.0.10\\FILMS\\") == _(
        "This path is already the location “{label}”.").format(label="Films")
    assert emp.valider(liste, "Films", str(FILMS), ancien=films) is None


def test_ecrire_puis_lire_rend_la_meme_liste():
    liste = [emp.Emplacement("Films", FILMS), emp.Emplacement("Rushes", Path(r"D:\R")),
             emp.Emplacement("Disque", Path("E:\\"))]
    cfg: dict = {}
    emp.ecrire(cfg, liste)
    assert emp.lire(cfg) == liste
    # Sans barre finale pour un partage ; un lecteur garde la sienne : `E:`
    # désignerait le dossier courant du lecteur.
    assert [d["chemin"] for d in cfg["emplacements"]] == [
        r"\\10.0.0.10\Films", r"D:\R", "E:\\"]
    (disque,) = emp.lire(_cfg({"libelle": "D", "chemin": "E:\\"}))
    assert disque.chemin == Path("E:\\")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows seulement")
def test_l_identite_s_enregistre_se_relit_et_se_retire():
    """Vrai Gestionnaire d'identifiants, sur une cible qui ne sert à rien."""
    cible = "iris-test-emplacements.invalid"
    try:
        emp.enregistrer_identite(cible, r"nas\essai", "secret")
        assert emp.compte(cible) == r"nas\essai"
        emp.enregistrer_identite(cible, r"nas\autre", "secret2")
        assert emp.compte(cible) == r"nas\autre"
    finally:
        emp.retirer_identite(cible)
    assert emp.compte(cible) is None
    emp.retirer_identite(cible)                  # déjà retirée : pas d'erreur


def test_changer_d_identite_coupe_les_connexions_de_ce_serveur(faux_windows):
    faux, _existantes = faux_windows
    emp.connecter(emp.Emplacement("Films", FILMS))
    emp.connecter(emp.Emplacement("DL", Path(r"\\10.0.0.11\Download")))
    emp.deconnecter_serveur("10.0.0.10")
    assert [n for n, _f in faux.coupures] == [r"\\10.0.0.10\films"]
    assert emp.connectes() == {r"\\10.0.0.11\download"}


# ─── L'écran ─────────────────────────────────────────────────────────────────

class _Coffre:
    """Le Gestionnaire d'identifiants, simulé."""

    def __init__(self, monkeypatch, comptes: dict[str, str] | None = None):
        self.comptes = dict(comptes or {})
        self.ecrits: list[tuple[str, str, str]] = []
        self.retires: list[str] = []
        self.coupes: list[str] = []
        monkeypatch.setattr(emp, "compte", lambda s: self.comptes.get(s))
        monkeypatch.setattr(emp, "enregistrer_identite", self._ecrire)
        monkeypatch.setattr(emp, "retirer_identite", self._retirer)
        monkeypatch.setattr(emp, "deconnecter_serveur", self.coupes.append)

    def _ecrire(self, s, c, m):
        self.ecrits.append((s, c, m))
        self.comptes[s] = c

    def _retirer(self, s):
        self.retires.append(s)
        self.comptes.pop(s, None)


async def _gestion(cfg_emplacements: list, scenario) -> dict:
    from tui.app import IrisEncodeApp
    releve: dict = {}
    app = IrisEncodeApp(start_path=Path.cwd())
    app.cfg["emplacements"] = cfg_emplacements
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause(0.3)
        accueil = app.screen
        await _accueil_affiche(pilot, accueil)
        await scenario(app, pilot, releve)
        await pilot.pause(0.3)
        await _accueil_affiche(pilot, accueil)
        releve["ecran_final"] = type(app.screen).__name__
        releve["accueil"] = [p for _t, p in accueil._rows]
    releve["cfg"] = app.cfg.get("emplacements")
    return releve


def _remplir(app, **champs):
    from textual.widgets import Input
    for cle, valeur in champs.items():
        app.screen.query_one(f"#champ-{cle}", Input).value = valeur


@pytest.fixture
def sans_ecriture(monkeypatch):
    from core import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "save", lambda *a, **k: None)


def test_ajouter_un_emplacement_avec_son_compte(monkeypatch, sans_ecriture):
    coffre = _Coffre(monkeypatch)

    async def scenario(app, pilot, r):
        await pilot.press("e")
        await pilot.pause(0.2)
        r["liste"] = type(app.screen).__name__
        await pilot.press("insert")
        await pilot.pause(0.2)
        _remplir(app, libelle="Films", chemin=r"\\10.0.0.10\Films",
                 compte=r"nas\olivier", mdp="secret")
        await pilot.press("ctrl+s")
        await pilot.pause(0.2)
        r["apres"] = type(app.screen).__name__
        await pilot.press("escape")

    r = asyncio.run(_gestion([], scenario))
    assert r["liste"] == "EmplacementsScreen"
    assert r["apres"] == "EmplacementsScreen"
    assert r["cfg"] == [{"libelle": "Films", "chemin": r"\\10.0.0.10\Films"}]
    assert coffre.ecrits == [("10.0.0.10", r"nas\olivier", "secret")]
    assert coffre.coupes == ["10.0.0.10"]
    assert r["ecran_final"] == "BrowserScreen"
    assert r["accueil"][-1] == FILMS                # l'accueil s'est rechargé


def test_un_nouveau_compte_sans_mot_de_passe_est_refuse(monkeypatch, sans_ecriture):
    coffre = _Coffre(monkeypatch, {"10.0.0.10": r"nas\olivier"})

    async def scenario(app, pilot, r):
        from textual.widgets import Input, Static
        await pilot.press("e")
        await pilot.pause(0.2)
        await pilot.press("enter")
        await pilot.pause(0.2)
        r["compte_affiche"] = app.screen.query_one("#champ-compte", Input).value
        _remplir(app, compte=r"nas\autre")
        await pilot.press("ctrl+s")
        await pilot.pause(0.2)
        r["ecran"] = type(app.screen).__name__
        r["erreur"] = str(app.screen.query_one("#empl-erreur", Static).render())

    r = asyncio.run(_gestion([{"libelle": "Films", "chemin": str(FILMS)}], scenario))
    assert r["compte_affiche"] == r"nas\olivier"
    assert r["ecran"] == "EmplacementForm"
    assert _("Type the password of this account.") in r["erreur"]
    assert coffre.ecrits == []


def test_modifier_sans_toucher_au_compte_garde_l_identite(monkeypatch, sans_ecriture):
    coffre = _Coffre(monkeypatch, {"10.0.0.10": r"nas\olivier"})

    async def scenario(app, pilot, r):
        await pilot.press("e")
        await pilot.pause(0.2)
        await pilot.press("enter")
        await pilot.pause(0.2)
        _remplir(app, libelle="Cinéma")
        await pilot.press("ctrl+s")
        await pilot.pause(0.2)

    r = asyncio.run(_gestion([{"libelle": "Films", "chemin": str(FILMS)}], scenario))
    assert r["cfg"] == [{"libelle": "Cinéma", "chemin": r"\\10.0.0.10\Films"}]
    assert coffre.ecrits == [] and coffre.retires == [] and coffre.coupes == []


def test_vider_le_compte_retire_l_identite_du_serveur(monkeypatch, sans_ecriture):
    coffre = _Coffre(monkeypatch, {"10.0.0.10": r"nas\olivier"})

    async def scenario(app, pilot, r):
        await pilot.press("e")
        await pilot.pause(0.2)
        await pilot.press("enter")
        await pilot.pause(0.2)
        _remplir(app, compte="")
        await pilot.press("ctrl+s")
        await pilot.pause(0.2)

    asyncio.run(_gestion([{"libelle": "Films", "chemin": str(FILMS)}], scenario))
    assert coffre.retires == ["10.0.0.10"] and coffre.coupes == ["10.0.0.10"]


def test_supprimer_un_emplacement_garde_l_identite(monkeypatch, sans_ecriture):
    coffre = _Coffre(monkeypatch, {"10.0.0.10": r"nas\olivier"})

    async def scenario(app, pilot, r):
        from textual.widgets import Button
        await pilot.press("e")
        await pilot.pause(0.2)
        await pilot.press("ctrl+d")
        await pilot.pause(0.2)
        r["confirmation"] = type(app.screen).__name__
        app.screen.query_one("#btn-confirm", Button).press()
        await pilot.pause(0.2)
        await pilot.press("escape")

    r = asyncio.run(_gestion([{"libelle": "Films", "chemin": str(FILMS)},
                              {"libelle": "DL", "chemin": r"\\10.0.0.11\Download"}],
                             scenario))
    assert r["confirmation"] == "ConfirmModal"
    assert r["cfg"] == [{"libelle": "DL", "chemin": r"\\10.0.0.11\Download"}]
    assert coffre.retires == []
    assert FILMS not in r["accueil"]


def test_la_touche_e_n_agit_que_sur_la_liste_des_volumes(monkeypatch, sans_ecriture,
                                                        tmp_path):
    _Coffre(monkeypatch)

    async def scenario(app, pilot, r):
        app.screen._nav.enter(tmp_path)
        app.screen._refresh_view()
        await pilot.pause(0.3)
        await pilot.press("e")
        await pilot.pause(0.2)

    r = asyncio.run(_gestion([], scenario))
    assert r["ecran_final"] == "BrowserScreen"
