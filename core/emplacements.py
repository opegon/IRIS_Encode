r"""core/emplacements.py — Les partages réseau nommés de l'accueil (IE-161).

Un emplacement est un dossier qu'on ouvre depuis l'accueil comme un lecteur,
sous un libellé : « Films » pour `\\10.0.0.10\Films`. Ils se déclarent dans
`config.toml` :

    [[emplacements]]
    libelle = "Films"
    chemin  = '\\10.0.0.10\Films'

**L'identité.** Un partage porte souvent un autre compte que la session
Windows. Elle vit dans le Gestionnaire d'identifiants Windows, sous le nom du
serveur (`cmdkey /add:10.0.0.10 /user:nas\olivier /pass`) : le client SMB de
Windows s'en sert de lui-même, et aucun programme ne peut relire le mot de
passe. IRIS n'en garde rien.

**La connexion** s'ouvre par `WNetAddConnection2W`, sans lettre de lecteur. Elle
vaut pour toute la session Windows : ffmpeg, mkvmerge, dovi_tool et mpv lisent
le partage sans rien de plus. IRIS coupe à sa sortie celles qu'il a ouvertes,
et seulement celles-là — une connexion existante (lecteur réseau, `net use`)
reste en place.

**Une identité par serveur.** Windows refuse une seconde connexion au même
serveur sous un autre compte (erreur 1219). Deux partages du même NAS partagent
donc un compte ; Windows voit cependant `10.0.0.10` et `nas` comme deux
serveurs distincts.
"""
from __future__ import annotations

import logging
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.i18n import N_, _

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class Emplacement:
    libelle: str
    chemin:  Path

    @property
    def reseau(self) -> bool:
        r"""Un partage `\\serveur\partage` : il faut s'y connecter."""
        return str(self.chemin).startswith("\\\\")


def lire(cfg: dict[str, Any]) -> list[Emplacement]:
    """Les emplacements de `config.toml`, dans leur ordre.

    Une entrée sans libellé ou sans chemin est écartée (et notée au journal) :
    une faute de frappe dans le fichier ne doit pas empêcher l'accueil de
    s'afficher.
    """
    brut = cfg.get("emplacements", [])
    if not isinstance(brut, list):
        _LOG.warning("config.toml: [emplacements] is not a list, ignored")
        return []
    resultat = []
    for entree in brut:
        libelle = entree.get("libelle") if isinstance(entree, dict) else None
        chemin = entree.get("chemin") if isinstance(entree, dict) else None
        if not (isinstance(libelle, str) and libelle.strip()
                and isinstance(chemin, str) and chemin.strip()):
            _LOG.warning("config.toml: incomplete location ignored: %r", entree)
            continue
        # Path ignore une barre finale, sauf à une racine : `D:\` doit le
        # rester (`D:` désigne le dossier courant du lecteur).
        resultat.append(Emplacement(libelle.strip(), Path(chemin.strip())))
    return resultat


def contenant(emplacements: list[Emplacement], chemin: Path) -> Emplacement | None:
    """L'emplacement dont `chemin` est la racine ou un sous-dossier."""
    for e in emplacements:
        if chemin == e.chemin or e.chemin in chemin.parents:
            return e
    return None


def fil_d_ariane(emplacements: list[Emplacement], chemin: Path) -> str:
    r"""Le chemin tel qu'on le montre : « Films › Saison 1 » plutôt que
    `\\10.0.0.10\Films\Saison 1`."""
    e = contenant(emplacements, chemin)
    if e is None:
        return str(chemin)
    reste = chemin.relative_to(e.chemin)
    return e.libelle if reste == Path(".") else f"{e.libelle} › {reste}"


# ─── Gestion (IE-162) ─────────────────────────────────────────────────────────

def serveur(chemin: Path | str) -> str | None:
    r"""Le serveur d'un chemin `\\serveur\partage`, sinon None."""
    texte = str(chemin)
    if not texte.startswith("\\\\"):
        return None
    morceaux = texte[2:].split("\\")
    return morceaux[0] or None


def ecrire(cfg: dict[str, Any], liste: list[Emplacement]) -> None:
    """Remplace les emplacements de la configuration (à enregistrer ensuite)."""
    cfg["emplacements"] = [{"libelle": e.libelle, "chemin": texte(e.chemin)}
                           for e in liste]


def texte(chemin: Path) -> str:
    r"""Le chemin tel qu'on l'écrit : `\\nas\films`, sans la barre que pathlib
    ajoute à la racine d'un partage ; `D:\` garde la sienne."""
    texte = str(chemin)
    return texte.rstrip("\\") if texte.startswith("\\\\") else texte


def valider(liste: list[Emplacement], libelle: str, chemin: str,
            ancien: Emplacement | None = None) -> str | None:
    """Ce qui empêche d'enregistrer cet emplacement, ou None."""
    autres = [e for e in liste if e != ancien]
    libelle, chemin = libelle.strip(), chemin.strip().rstrip("\\/")
    if not libelle:
        return _("The label is required.")
    if any(e.libelle.lower() == libelle.lower() for e in autres):
        return _("Another location already has this label.")
    if not chemin:
        return _("The path is required.")
    if chemin.startswith("\\\\"):
        morceaux = chemin[2:].split("\\")
        if len(morceaux) < 2 or not all(morceaux[:2]):
            return _(r"A network path reads \\server\share.")
    meme = next((e for e in autres if cle(e.chemin) == cle(Path(chemin))), None)
    if meme is not None:
        return _("This path is already the location “{label}”.").format(
            label=meme.libelle)
    return None


# ─── Connexion SMB ────────────────────────────────────────────────────────────

def cle(chemin: Path) -> str:
    r"""Le nom d'un partage tel que Windows le liste : `\nasilms`, sans la
    barre finale que pathlib ajoute à la racine d'un partage."""
    return str(chemin).rstrip("\\").lower()


class ConnexionRefusee(Exception):
    """Windows a refusé la connexion ; le message est affichable."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


# Codes de retour de WNetAddConnection2W, et ce qu'on dit à l'utilisateur.
_CONFLIT = 1219
_CAUSES: dict[int, str] = {
    5:    N_("access denied: this account has no right on the share"),
    53:   N_("server unreachable"),
    67:   N_("this share does not exist on the server"),
    86:   N_("password refused"),
    1203: N_("server unreachable"),
    1222: N_("no network"),
    _CONFLIT: N_("Windows is already connected to this server under another "
                 "account (a network drive, or another location). Windows "
                 "allows one account per server"),
    1326: N_("account or password refused. Is an identity saved for this "
             "server in the Windows Credential Manager?"),
    1327: N_("account restriction"),
    1330: N_("password expired"),
    1331: N_("account disabled"),
    1909: N_("account locked"),
    2202: N_("invalid user name"),
}

_RESOURCETYPE_DISK = 1
_CONNECT_TEMPORARY = 4
_RESOURCE_CONNECTED = 1
_ERROR_MORE_DATA = 234
_ERROR_NO_MORE_ITEMS = 259

# Les connexions ouvertes par cette session d'IRIS, à couper à la sortie.
_ouvertes: set[str] = set()
_verrou = threading.Lock()


def _cause(code: int) -> str:
    texte = _CAUSES.get(code)
    return _(texte) if texte else _("Windows error {code}").format(code=code)


def _mpr():
    import ctypes
    from ctypes import wintypes

    class NETRESOURCEW(ctypes.Structure):
        _fields_ = [("dwScope", wintypes.DWORD), ("dwType", wintypes.DWORD),
                    ("dwDisplayType", wintypes.DWORD), ("dwUsage", wintypes.DWORD),
                    ("lpLocalName", wintypes.LPWSTR), ("lpRemoteName", wintypes.LPWSTR),
                    ("lpComment", wintypes.LPWSTR), ("lpProvider", wintypes.LPWSTR)]

    mpr = ctypes.WinDLL("mpr")
    mpr.WNetAddConnection2W.argtypes = [ctypes.POINTER(NETRESOURCEW), wintypes.LPCWSTR,
                                        wintypes.LPCWSTR, wintypes.DWORD]
    mpr.WNetAddConnection2W.restype = wintypes.DWORD
    mpr.WNetCancelConnection2W.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL]
    mpr.WNetCancelConnection2W.restype = wintypes.DWORD
    mpr.WNetOpenEnumW.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, ctypes.POINTER(wintypes.HANDLE)]
    mpr.WNetOpenEnumW.restype = wintypes.DWORD
    mpr.WNetEnumResourceW.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD),
                                      ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)]
    mpr.WNetEnumResourceW.restype = wintypes.DWORD
    mpr.WNetCloseEnum.argtypes = [wintypes.HANDLE]
    return ctypes, wintypes, mpr, NETRESOURCEW


def connexions_existantes() -> set[str]:
    r"""Les partages auxquels la session Windows est connectée, en minuscules
    (`\\nas\films`) : lecteurs réseau, `net use`, connexions d'IRIS."""
    ctypes, wintypes, mpr, NETRESOURCEW = _mpr()
    poignee = wintypes.HANDLE()
    if mpr.WNetOpenEnumW(_RESOURCE_CONNECTED, _RESOURCETYPE_DISK, 0, None,
                         ctypes.byref(poignee)) != 0:
        return set()
    trouves: set[str] = set()
    try:
        taille = 16384
        tampon = ctypes.create_string_buffer(taille)
        while True:
            nombre = wintypes.DWORD(0xFFFFFFFF)
            octets = wintypes.DWORD(taille)
            rc = mpr.WNetEnumResourceW(poignee, ctypes.byref(nombre), tampon,
                                       ctypes.byref(octets))
            if rc == _ERROR_MORE_DATA:
                taille = max(octets.value, taille * 2)
                tampon = ctypes.create_string_buffer(taille)
                continue
            if rc != 0:
                break
            ressources = ctypes.cast(tampon, ctypes.POINTER(NETRESOURCEW))
            for i in range(nombre.value):
                nom = ressources[i].lpRemoteName
                if nom:
                    trouves.add(nom.rstrip("\\").lower())
    finally:
        mpr.WNetCloseEnum(poignee)
    return trouves


def connectes() -> set[str]:
    """Les partages joignables sans nouvelle connexion, en minuscules."""
    if sys.platform != "win32":
        return set()
    with _verrou:
        return set(_ouvertes) | connexions_existantes()


def connecter(emplacement: Emplacement) -> None:
    """Ouvre la connexion au partage, si elle n'existe pas déjà.

    Lève `ConnexionRefusee` avec la cause en clair. Peut durer : un serveur
    éteint ne répond qu'au bout de plusieurs secondes — à appeler hors du fil
    de l'interface.
    """
    if not emplacement.reseau or sys.platform != "win32":
        return
    distant = str(emplacement.chemin).rstrip("\\")
    with _verrou:
        if cle(emplacement.chemin) in _ouvertes | connexions_existantes():
            return
        ctypes, _wt, mpr, NETRESOURCEW = _mpr()
        ressource = NETRESOURCEW(dwType=_RESOURCETYPE_DISK, lpRemoteName=distant)
        # Ni compte ni mot de passe : Windows prend l'identité enregistrée pour
        # ce serveur, sinon celle de la session.
        rc = mpr.WNetAddConnection2W(ctypes.byref(ressource), None, None,
                                     _CONNECT_TEMPORARY)
        if rc != 0:
            _LOG.warning("connection to %s refused: %d", distant, rc)
            raise ConnexionRefusee(rc, _("{location}: {cause}.").format(
                location=emplacement.libelle, cause=_cause(rc)))
        _ouvertes.add(cle(emplacement.chemin))
        _LOG.info("connected to %s", distant)


def deconnecter_tout() -> None:
    """Coupe les connexions ouvertes par IRIS — à la sortie.

    Sans forcer : un partage encore utilisé ailleurs (l'Explorateur ouvert
    dessus) reste connecté plutôt que de casser ce qui s'y fait.
    """
    if sys.platform != "win32":
        return
    with _verrou:
        if not _ouvertes:
            return
        _ctypes, _wt, mpr, _nr = _mpr()
        for distant in sorted(_ouvertes):
            rc = mpr.WNetCancelConnection2W(distant, 0, False)
            if rc != 0:
                _LOG.warning("disconnection from %s refused: %d", distant, rc)
        _ouvertes.clear()


def deconnecter_serveur(nom: str) -> None:
    """Coupe les connexions d'IRIS à ce serveur : la prochaine ouverture prend
    l'identité qu'on vient de changer."""
    if sys.platform != "win32":
        return
    prefixe = "\\\\" + nom.lower() + "\\"
    with _verrou:
        _ctypes, _wt, mpr, _nr = _mpr()
        for distant in sorted(d for d in _ouvertes if d.startswith(prefixe)):
            if mpr.WNetCancelConnection2W(distant, 0, False) == 0:
                _ouvertes.discard(distant)


# ─── Identité : le Gestionnaire d'identifiants Windows (IE-162) ──────────────
#
# Une identité de type « domaine » (`CRED_TYPE_DOMAIN_PASSWORD`), comme
# `cmdkey /add` : le client SMB s'en sert, mais aucun programme ne relit son
# mot de passe — seul le nom du compte se lit.

_CRED_TYPE_DOMAIN_PASSWORD = 2
_CRED_PERSIST_LOCAL_MACHINE = 2
_ERROR_NOT_FOUND = 1168


class IdentiteRefusee(Exception):
    """Windows a refusé d'enregistrer ou de retirer l'identité."""


def _advapi():
    import ctypes
    from ctypes import wintypes

    class CREDENTIALW(ctypes.Structure):
        _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
                    ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
                    ("LastWritten", wintypes.FILETIME),
                    ("CredentialBlobSize", wintypes.DWORD),
                    ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                    ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD),
                    ("Attributes", ctypes.c_void_p), ("TargetAlias", wintypes.LPWSTR),
                    ("UserName", wintypes.LPWSTR)]

    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    adv.CredWriteW.argtypes = [ctypes.POINTER(CREDENTIALW), wintypes.DWORD]
    adv.CredWriteW.restype = wintypes.BOOL
    adv.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                              ctypes.POINTER(ctypes.POINTER(CREDENTIALW))]
    adv.CredReadW.restype = wintypes.BOOL
    adv.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    adv.CredDeleteW.restype = wintypes.BOOL
    adv.CredFree.argtypes = [ctypes.c_void_p]
    return ctypes, adv, CREDENTIALW


def compte(nom_serveur: str) -> str | None:
    """Le compte enregistré pour ce serveur, ou None."""
    if sys.platform != "win32":
        return None
    ctypes, adv, CREDENTIALW = _advapi()
    lu = ctypes.POINTER(CREDENTIALW)()
    if not adv.CredReadW(nom_serveur, _CRED_TYPE_DOMAIN_PASSWORD, 0, ctypes.byref(lu)):
        return None
    try:
        return lu.contents.UserName or None
    finally:
        adv.CredFree(lu)


def enregistrer_identite(nom_serveur: str, nom_compte: str, mot_de_passe: str) -> None:
    """Enregistre (ou remplace) l'identité de ce serveur."""
    if sys.platform != "win32":
        raise IdentiteRefusee(_("Saving an identity needs Windows."))
    ctypes, adv, CREDENTIALW = _advapi()
    octets = mot_de_passe.encode("utf-16-le")
    tampon = (ctypes.c_ubyte * len(octets)).from_buffer_copy(octets) if octets else None
    cred = CREDENTIALW(Type=_CRED_TYPE_DOMAIN_PASSWORD, TargetName=nom_serveur,
                       CredentialBlobSize=len(octets),
                       CredentialBlob=ctypes.cast(tampon, ctypes.POINTER(ctypes.c_ubyte))
                       if tampon is not None else None,
                       Persist=_CRED_PERSIST_LOCAL_MACHINE, UserName=nom_compte)
    if not adv.CredWriteW(ctypes.byref(cred), 0):
        code = ctypes.get_last_error()
        _LOG.warning("credential for %s not saved: %d", nom_serveur, code)
        raise IdentiteRefusee(_("Windows refused to save the identity "
                                "(error {code}).").format(code=code))
    _LOG.info("credential saved for %s", nom_serveur)


def retirer_identite(nom_serveur: str) -> None:
    """Retire l'identité de ce serveur ; rien s'il n'en a pas."""
    if sys.platform != "win32":
        return
    ctypes, adv, _c = _advapi()
    if not adv.CredDeleteW(nom_serveur, _CRED_TYPE_DOMAIN_PASSWORD, 0):
        code = ctypes.get_last_error()
        if code != _ERROR_NOT_FOUND:
            raise IdentiteRefusee(_("Windows refused to remove the identity "
                                    "(error {code}).").format(code=code))
    else:
        _LOG.info("credential removed for %s", nom_serveur)
