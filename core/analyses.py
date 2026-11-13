"""
core/analyses.py — Les analyses d'entrelacement gardées sur disque.

Sonder l'entrelacement (IE-174) coûte 6 à 12 passages de ffmpeg par fichier :
28 s pour un 1080p marqué entrelacé, 4 à 7 s pour une source SD, à travers
un partage réseau (mesuré le 2026-11-09). Gardé en mémoire seulement, ce
travail se refaisait à chaque lancement de l'application.

Le fichier, `data/analyses.json` de l'installation, est propre à la machine :
ignoré par git, absent du ZIP de release, donc conservé par une mise à jour.

La clé ne contient pas le chemin : taille, date de modification, durée et
dimensions. Un fichier renommé ou déplacé garde sa date, donc son analyse ;
un fichier modifié change de taille ou de date, et se réanalyse. Une entrée
qui n'a servi à aucun fichier depuis `EXPIRATION_JOURS` disparaît au
chargement : c'est ainsi que partent celles des fichiers effacés.
"""
from __future__ import annotations

import atexit
import json
import logging
import os
import threading
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from .config import APP_DIR
from .entrelacement import Analyse, Nature

if TYPE_CHECKING:
    from .scanner import VideoInfo

_log = logging.getLogger("iris_encode.analyses")

CHEMIN           = APP_DIR / "data" / "analyses.json"
EXPIRATION_JOURS = 180

_verrou  = threading.Lock()
_entrees: Optional[dict] = None             # chargées au premier accès
_charge_depuis: Optional[Path] = None       # le chemin d'où elles viennent
# Clé → (verrou, nombre de fils qui le tiennent ou l'attendent).
_en_cours: dict[str, tuple[threading.Lock, int]] = {}
# Le jour du dernier `_sauver`, et des dates de lecture pas encore écrites.
_ecrit_le: Optional[str] = None
_a_ecrire = False


def cle(info: "VideoInfo", st: os.stat_result) -> str:
    """L'identité d'un fichier vidéo, sans son nom."""
    return (f"{st.st_size}|{st.st_mtime_ns}|{info.duration:.1f}"
            f"|{info.width}x{info.height}")


@contextmanager
def verrou_de(c: str):
    """Un verrou par fichier : deux fils qui veulent la même analyse
    l'attendent une fois, au lieu de la mesurer deux fois.

    Retiré quand le dernier fil le rend : un verrou par fichier jamais vu
    s'accumulait, une saison après l'autre, pendant toute la session (CR-145).
    """
    with _verrou:
        v, n = _en_cours.get(c, (None, 0))
        if v is None:
            v = threading.Lock()
        _en_cours[c] = (v, n + 1)
    try:
        with v:
            yield
    finally:
        with _verrou:
            v, n = _en_cours[c]
            if n <= 1:
                del _en_cours[c]
            else:
                _en_cours[c] = (v, n - 1)


def _vers_dict(a: Analyse) -> dict:
    return {"nature": a.nature.name, "ordre": a.ordre, "decime": a.decime,
            "peigne": a.peigne, "peigne_apparie": a.peigne_apparie}


def _depuis_dict(d: dict) -> Analyse:
    return Analyse(Nature[d["nature"]], d["ordre"], bool(d["decime"]),
                   float(d["peigne"]), float(d["peigne_apparie"]))


def _charger() -> dict:
    """Les entrées du fichier, sans les expirées. Appelé sous `_verrou`."""
    global _entrees, _charge_depuis
    if _entrees is not None and _charge_depuis == CHEMIN:
        return _entrees
    entrees: dict = {}
    try:
        brut = json.loads(CHEMIN.read_text(encoding="utf-8"))
        limite = (date.today() - timedelta(days=EXPIRATION_JOURS)).isoformat()
        for c, e in brut.items():
            if e.get("vu", "") >= limite:
                _depuis_dict(e["analyse"])  # une entrée illisible est écartée
                entrees[c] = e
    except FileNotFoundError:
        pass
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        _log.warning("analyses cache unreadable (%s), starting empty: %s", CHEMIN, e)
    _entrees, _charge_depuis = entrees, CHEMIN
    return entrees


def _sauver(entrees: dict) -> None:
    """Écrit le fichier entier, par remplacement : jamais à moitié écrit.
    Une installation en lecture seule garde les analyses en mémoire."""
    global _ecrit_le, _a_ecrire
    tmp = CHEMIN.with_suffix(".tmp")
    try:
        CHEMIN.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(entrees, indent=0, sort_keys=True), encoding="utf-8")
        os.replace(tmp, CHEMIN)
    except OSError as e:
        _log.warning("analyses cache not written (%s): %s", CHEMIN, e)
    _ecrit_le, _a_ecrire = date.today().isoformat(), False


def lire(c: str) -> Optional[Analyse]:
    """L'analyse gardée pour la clé `c`, ou None. Une entrée lue est
    marquée vue aujourd'hui, ce qui repousse son expiration.

    Le fichier se réécrit une fois par jour pour ces marques, pas une fois par
    entrée : un dossier de cent films le réécrivait cent fois (CR-145). Les
    marques suivantes partent avec la prochaine écriture, ou à la sortie."""
    global _a_ecrire
    with _verrou:
        entrees = _charger()
        e = entrees.get(c)
        if e is None:
            return None
        aujourd_hui = date.today().isoformat()
        if e.get("vu") != aujourd_hui:
            e["vu"] = aujourd_hui
            if _ecrit_le != aujourd_hui:
                _sauver(entrees)
            else:
                _a_ecrire = True
        return _depuis_dict(e["analyse"])


@atexit.register
def _ecrire_les_marques() -> None:
    """À la sortie : les dates de lecture que `lire` a gardées en mémoire."""
    with _verrou:
        if _a_ecrire and _entrees is not None and _charge_depuis == CHEMIN:
            _sauver(_entrees)


def ecrire(c: str, analyse: Analyse) -> None:
    """Garde une analyse. Un échec de mesure (None) ne s'écrit pas : une
    lecture réseau interrompue ne doit pas tenir lieu de résultat."""
    with _verrou:
        entrees = _charger()
        entrees[c] = {"analyse": _vers_dict(analyse), "vu": date.today().isoformat()}
        _sauver(entrees)
