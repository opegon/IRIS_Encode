"""core/i18n.py — Traduction de l'interface (IE-86).

`gettext` de la bibliothèque standard. **L'anglais est la langue source**
(IE-111) : les textes du code sont en anglais, le français est une traduction
(`locales/fr/LC_MESSAGES/iris_encode.po`). Une langue sans catalogue, comme un
texte que le catalogue ne traduit pas, retombe sur l'anglais.

Les noms sont ceux que connaissent les outils de traduction — `_`, `N_`,
`ngettext`, `pgettext`, `npgettext` — et c'est sur eux que `outils/i18n.py`
extrait les textes. Règles d'écriture (IE-111 point 5) :

- le gabarit passe à `_()`, les valeurs ensuite, par nom :
  `_("{count} files").format(count=n)`, jamais `_(f"…")` ;
- une phrase entière par message ; un pluriel par `ngettext` ;
- hors du message : puces et symboles, indentation, retours à la ligne de mise
  en page, capitales décoratives, balises Rich ;
- un texte défini au chargement d'un module (table, `BINDINGS`) est marqué
  `N_()` et traduit à l'affichage : à l'import, la langue n'est pas encore
  chargée ;
- un commentaire `# TRANSLATORS: …` juste au-dessus de l'appel arrive au
  traducteur (contexte, longueur maximale, touche citée).

Ce qui ne se traduit jamais (IE-71 point 5) : ce qui s'écrit sur le disque ou
part vers un autre programme, et les journaux.
"""
from __future__ import annotations

import gettext as _gettext
from pathlib import Path
from typing import Iterable

DOMAINE       = "iris_encode"
LOCALES       = Path(__file__).resolve().parent.parent / "locales"
LANGUE_SOURCE = "en"

_traduction: _gettext.NullTranslations = _gettext.NullTranslations()
_langue: str = LANGUE_SOURCE


def init(langue: str | None, dossier: Path = LOCALES) -> str:
    """Charge le catalogue de `langue` (« fr », « fr_CA »…) ; rend la langue
    effectivement chargée. Langue vide, source ou sans catalogue : anglais.

    Appelé une fois, au démarrage, après la lecture de `config.toml` : un
    changement de langue prend effet au redémarrage (IE-71 point 3).
    """
    global _traduction, _langue
    code = (langue or "").strip().replace("-", "_")
    _traduction, _langue = _gettext.NullTranslations(), LANGUE_SOURCE
    if not code or code.split("_")[0].lower() == LANGUE_SOURCE:
        return _langue
    try:
        _traduction = _gettext.translation(DOMAINE, dossier, languages=[code])
        _langue = code
    except OSError:
        pass
    return _langue


def langue() -> str:
    """La langue chargée par `init` (« en » sans catalogue)."""
    return _langue


def _(message: str) -> str:
    return _traduction.gettext(message)


def N_(message: str) -> str:
    """Marque un texte pour l'extraction sans le traduire : il le sera à
    l'affichage, par `_(variable)`."""
    return message


def ngettext(singulier: str, pluriel: str, n: int) -> str:
    return _traduction.ngettext(singulier, pluriel, n)


def pgettext(contexte: str, message: str) -> str:
    return _traduction.pgettext(contexte, message)


def npgettext(contexte: str, singulier: str, pluriel: str, n: int) -> str:
    return _traduction.npgettext(contexte, singulier, pluriel, n)


def liste(elements: Iterable[object]) -> str:
    """« a, b and c » dans la langue chargée (« a, b et c » en français)."""
    el = [str(e) for e in elements]
    if len(el) < 2:
        return el[0] if el else ""
    # TRANSLATORS: separator between the first items of a list ("a, b and c").
    sep = pgettext("list", ", ")
    # TRANSLATORS: joins the last item of a list; {items} is "a, b".
    return pgettext("list", "{items} and {last}").format(
        items=sep.join(el[:-1]), last=el[-1])


class ErreurAffichable(ValueError):
    """Une erreur dont le message est montré à l'utilisateur (L-18).

    Elle porte le message **source** et ses paramètres, pas une phrase
    traduite : `str(e)` rend l'anglais formaté, c'est ce qu'écrit le journal
    (hors catalogue, dans une langue stable) ; `e.message()` le rend traduit,
    pour l'écran. Le message se marque à la levée :
    `raise ErreurAffichable(N_("Cannot read {path}."), path=p)`.

    Elle hérite de `ValueError` : les appelants qui attrapaient les
    `ValueError` d'avant l'attrapent toujours. Pour l'écran, `texte_erreur`.
    """

    def __init__(self, msgid: str, **params: object) -> None:
        self.msgid  = msgid
        self.params = params
        super().__init__(msgid.format(**params))

    def message(self) -> str:
        return _(self.msgid).format(**self.params)


def texte_erreur(e: BaseException) -> str:
    """Le texte d'une erreur pour l'écran : traduit si elle le permet, sinon
    tel quel (erreur d'un outil, du système, d'une bibliothèque)."""
    return e.message() if isinstance(e, ErreurAffichable) else str(e)
