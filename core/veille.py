"""
core/veille.py — Tenir la machine éveillée pendant un traitement, et l'endormir
après, si on le demande.

Un encodage dure des heures ; la mise en veille sur inactivité de Windows ne
voit pas ffmpeg travailler et coupait le lot en plein milieu.

**Une demande d'alimentation, pas `SetThreadExecutionState`.** Cette dernière
est attachée au *thread* qui l'appelle, et l'encodage n'a pas de thread
durable : `RunScreen._encode_next` est un worker qui se relance à chaque
fichier. La demande de `PowerCreateRequest` appartient au processus, porte un
motif lisible dans `powercfg /requests`, et disparaît avec lui : une
application tuée ne laisse pas la machine éveillée pour toujours.
`SetThreadExecutionState` reste en secours, appelé depuis le fil principal,
qui vit autant que l'application.

Ce qui reste hors de portée, et doit le rester : la veille demandée à la main
(menu Démarrer, bouton, capot fermé), la batterie critique, et un
`powercfg /requestsoverride` posé par un administrateur.

Hors Windows, rien n'est fait pour l'instant : `disponible()` le dit, et les
appelants n'ont pas à le savoir.
"""
from __future__ import annotations

import logging
import platform
import subprocess
import threading

from .i18n import N_, _

log = logging.getLogger(__name__)

# Ce que la machine fait une fois le lot fini, si on l'a demandé. Le choix vit
# dans `[energie] action_fin` ; l'interrupteur, lui, est propre à chaque lot.
# « rien » est le défaut : la machine ne change d'état que si on l'a choisi.
# Les clés sont des valeurs de config.toml : elles ne se traduisent pas
# (IE-71 point 5). Les libellés, marqués ici, le sont à l'affichage.
ACTIONS_FIN: dict[str, str] = {
    "rien":             N_("do nothing"),
    "veille":           N_("sleep"),
    "veille_prolongee": N_("hibernate"),
    "arret":            N_("shut down"),
}
ACTION_FIN_DEFAUT = "rien"

# Le délai pendant lequel l'action se laisse annuler.
COMPTE_A_REBOURS_S = 60


def disponible() -> bool:
    """Vrai si ce système sait tenir la machine éveillée et l'endormir."""
    return platform.system() == "Windows"


def libelle_action(action: str) -> str:
    """« mise en veille », « arrêt »… ; l'action par défaut si inconnue."""
    return _(ACTIONS_FIN.get(action, ACTIONS_FIN[ACTION_FIN_DEFAUT]))


# ─── Le moteur Windows ────────────────────────────────────────────────────────

class _MoteurWindows:
    """Les appels `kernel32`, isolés pour qu'un test les remplace."""

    _SYSTEM_REQUIRED = 1           # POWER_REQUEST_TYPE.PowerRequestSystemRequired
    _SIMPLE_STRING   = 0x1         # POWER_REQUEST_CONTEXT_SIMPLE_STRING
    _ES_CONTINUOUS      = 0x80000000
    _ES_SYSTEM_REQUIRED = 0x00000001

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        class _Detail(ctypes.Structure):
            _fields_ = [("LocalizedReasonModule", wintypes.HMODULE),
                        ("LocalizedReasonId",     wintypes.ULONG),
                        ("ReasonStringCount",     wintypes.ULONG),
                        ("ReasonStrings",         ctypes.POINTER(wintypes.LPWSTR))]

        class _Motif(ctypes.Union):
            _fields_ = [("Detailed",           _Detail),
                        ("SimpleReasonString", wintypes.LPWSTR)]

        class _Contexte(ctypes.Structure):      # REASON_CONTEXT
            _fields_ = [("Version", wintypes.ULONG),
                        ("Flags",   wintypes.DWORD),
                        ("Reason",  _Motif)]

        self._ct       = ctypes
        self._Contexte = _Contexte
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.PowerCreateRequest.argtypes = [ctypes.POINTER(_Contexte)]
        k.PowerCreateRequest.restype  = wintypes.HANDLE
        k.PowerSetRequest.argtypes    = [wintypes.HANDLE, ctypes.c_int]
        k.PowerSetRequest.restype     = wintypes.BOOL
        k.PowerClearRequest.argtypes  = [wintypes.HANDLE, ctypes.c_int]
        k.PowerClearRequest.restype   = wintypes.BOOL
        k.CloseHandle.argtypes        = [wintypes.HANDLE]
        k.CloseHandle.restype         = wintypes.BOOL
        k.SetThreadExecutionState.argtypes = [wintypes.DWORD]
        k.SetThreadExecutionState.restype  = wintypes.DWORD
        self._k = k

    def poser(self, motif: str):
        """Pose la demande ; rend de quoi la retirer, ou None en cas d'échec."""
        texte = self._ct.c_wchar_p(motif)
        ctx = self._Contexte(Version=0, Flags=self._SIMPLE_STRING)
        ctx.Reason.SimpleReasonString = texte
        h = self._k.PowerCreateRequest(self._ct.byref(ctx))
        if h and h != self._ct.c_void_p(-1).value:
            if self._k.PowerSetRequest(h, self._SYSTEM_REQUIRED):
                return ("demande", h)
            self._k.CloseHandle(h)
        # Secours : lié au thread appelant — le fil principal, qui dure.
        etat = self._ES_CONTINUOUS | self._ES_SYSTEM_REQUIRED
        if self._k.SetThreadExecutionState(etat):
            return ("thread", None)
        log.warning("sleep: no power request accepted (error %s)",
                    self._ct.get_last_error())
        return None

    def retirer(self, jeton) -> None:
        genre, h = jeton
        if genre == "demande":
            self._k.PowerClearRequest(h, self._SYSTEM_REQUIRED)
            self._k.CloseHandle(h)
        else:
            self._k.SetThreadExecutionState(self._ES_CONTINUOUS)

    # ── Après le lot ──────────────────────────────────────────────────────────

    def _privilege_arret(self) -> None:
        """Active SeShutdownPrivilege, présent mais éteint dans le jeton.

        `SetSuspendState` l'exige. Au mieux : un échec ici se lira dans celui
        de l'appel qui suit.
        """
        ct = self._ct
        from ctypes import wintypes

        class _Luid(ct.Structure):
            _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]

        class _Privileges(ct.Structure):        # TOKEN_PRIVILEGES, une entrée
            _fields_ = [("PrivilegeCount", wintypes.DWORD),
                        ("Luid",           _Luid),
                        ("Attributes",     wintypes.DWORD)]

        # Signatures déclarées : sans elles, ctypes passe le pseudo-handle du
        # processus (-1, lu en 64 bits non signé) comme un int 32 bits et lève.
        advapi = ct.WinDLL("advapi32", use_last_error=True)
        advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                            ct.POINTER(wintypes.HANDLE)]
        advapi.OpenProcessToken.restype  = wintypes.BOOL
        advapi.LookupPrivilegeValueW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR,
                                                 ct.POINTER(_Luid)]
        advapi.LookupPrivilegeValueW.restype  = wintypes.BOOL
        advapi.AdjustTokenPrivileges.argtypes = [wintypes.HANDLE, wintypes.BOOL,
                                                 ct.POINTER(_Privileges), wintypes.DWORD,
                                                 ct.c_void_p, ct.c_void_p]
        advapi.AdjustTokenPrivileges.restype  = wintypes.BOOL
        jeton  = wintypes.HANDLE()
        TOKEN_ADJUST_PRIVILEGES, TOKEN_QUERY = 0x20, 0x8
        processus = ct.WinDLL("kernel32").GetCurrentProcess
        processus.argtypes = []
        processus.restype  = wintypes.HANDLE
        if not advapi.OpenProcessToken(processus(),
                                       TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
                                       ct.byref(jeton)):
            return
        try:
            p = _Privileges(PrivilegeCount=1, Attributes=0x2)  # SE_PRIVILEGE_ENABLED
            if advapi.LookupPrivilegeValueW(None, "SeShutdownPrivilege",
                                            ct.byref(p.Luid)):
                advapi.AdjustTokenPrivileges(jeton, False, ct.byref(p), 0,
                                             None, None)
        finally:
            self._k.CloseHandle(jeton)

    def executer(self, action: str) -> str | None:
        """Lance l'action. Rend None, ou ce qui l'en a empêché."""
        if action == "veille":
            self._privilege_arret()
            powrprof = self._ct.WinDLL("powrprof", use_last_error=True)
            powrprof.SetSuspendState.argtypes = [self._ct.c_ubyte] * 3  # BOOLEAN
            powrprof.SetSuspendState.restype  = self._ct.c_ubyte
            # bHibernate=False : la veille, pas l'hibernation. La confusion
            # célèbre vient de `rundll32 powrprof.dll,SetSuspendState`, qui
            # passe mal ses arguments — pas de l'appel direct.
            if powrprof.SetSuspendState(False, False, False):
                return None
            return _("sleep was refused (error {code})").format(
                code=self._ct.get_last_error())
        cmd = {"veille_prolongee": ["shutdown", "/h"],
               "arret":            ["shutdown", "/s", "/t", "0"]}.get(action)
        if cmd is None:
            return _("unknown action: {action}").format(action=action)
        try:
            # shutdown.exe écrit dans la page de code OEM de la console.
            r = subprocess.run(cmd, stdin=subprocess.DEVNULL,
                               capture_output=True, encoding="oem",
                               errors="replace", timeout=30)
        except (OSError, subprocess.SubprocessError) as e:
            return str(e)
        if r.returncode != 0:
            return (r.stderr or r.stdout).strip() or f"code {r.returncode}"
        return None


# ─── La garde ─────────────────────────────────────────────────────────────────

class GardeVeille:
    """La demande d'éveil, tenue tant qu'un motif est donné.

    `maintenir()` est idempotent : l'application l'appelle à intervalle
    régulier avec l'état du moment, plutôt que de compter des entrées et des
    sorties qu'un chemin d'erreur finirait par déséquilibrer.
    """

    def __init__(self, moteur=None) -> None:
        self._moteur = moteur
        self._jeton  = None
        self._motif: str | None = None
        self._verrou = threading.Lock()

    def _le_moteur(self):
        if self._moteur is None and disponible():
            try:
                self._moteur = _MoteurWindows()
            except (OSError, AttributeError) as e:
                log.warning("sleep: power API unavailable (%s)", e)
                self._moteur = False
        return self._moteur or None

    @property
    def active(self) -> bool:
        return self._jeton is not None

    def maintenir(self, motif: str | None) -> None:
        """Tient la machine éveillée pour `motif` ; None relâche."""
        with self._verrou:
            # Même motif : rien à faire. Une demande refusée n'est pas
            # retentée à chaque appel — le journal se remplirait toutes les
            # cinq secondes pendant des heures ; un nouveau motif la retente.
            if motif == self._motif:
                return
            moteur = self._le_moteur()
            if moteur is None:
                return
            # Le motif est figé à la création : un autre motif, une autre demande.
            # La nouvelle d'abord, l'ancienne ensuite : jamais de trou entre les deux.
            ancien = self._jeton
            self._jeton = moteur.poser(motif) if motif else None
            self._motif = motif
            if ancien is not None:
                moteur.retirer(ancien)
            log.info("sleep: %s", f"blocked — {motif}" if self._jeton
                     else "back to the system")

    def relacher(self) -> None:
        self.maintenir(None)

    def executer_fin(self, action: str) -> str | None:
        """Relâche la demande, puis lance `action`. Rend l'erreur, ou None."""
        self.relacher()
        if action == "rien":
            return None
        moteur = self._le_moteur()
        if moteur is None:
            return _("unavailable on this system")
        log.info("sleep: end of batch, %s", action)   # le journal garde la clé
        return moteur.executer(action)
