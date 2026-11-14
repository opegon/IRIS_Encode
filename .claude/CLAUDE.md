# IRIS ENCODE — Conventions du dépôt

Version partagée des règles de travail, pour toute session (locale ou cloud).
Le `CLAUDE.md` à la racine, s'il existe, est personnel et non versionné.

## Ce que c'est

Outil TUI Python de réencodage vidéo HEVC / H264 / AV1, sous Windows en premier
lieu (macOS / Linux prévus).

- Stack : Python 3.11+, Textual, ffmpeg (et mkvmerge, dovi_tool, mpv…).
- `core/` : logique métier (decision, encoder, scanner, platform…).
- `tui/` : interface Textual (screens, widgets, mixins).
- Profils : `profiles.toml` ; configuration : `config.toml` (personnels, non versionnés).
- Spécification : `iris_encode_spec.md` (nom fixe, version dans l'en-tête).
- Guide utilisateur : `GUIDE.md` (anglais), `GUIDE.fr.md` (français).
- Historique : `CHANGELOG.md`.

## Base de connaissance : `wiki/`

À consulter avant de répondre, diagnostiquer ou modifier : `wiki/index.md`, puis
les pages concernées. À enrichir dès qu'on apprend quelque chose, en suivant
`wiki/SCHEMA.md` (opérations ingest / query / lint, journal `wiki/log.md`).

## Environnement

- Les outils externes vivent dans `bin/` (non versionné, installé par le
  preflight). Les tests qui fabriquent des vidéos les cherchent là, puis dans
  le `PATH` (`tests/outils_reels.py`) ; introuvables, ces tests sont sautés.
- `resources_files/` (matériel réel) n'est pas versionné.
- Du code est propre à Windows (`ctypes.WinDLL`, `mpr`, `advapi32`) : il ne
  s'exécute pas ailleurs.
- Échec connu, dû à l'environnement : `tests/test_finalisation_mp4.py::
  test_octets_ecrits_compte_ce_que_le_processus_ecrit` quand Python est lancé
  par le redirecteur d'un venv.

## Conventions de code

- Imports absolus (`from core.xxx import ...`) depuis la racine.
- Textual : `call_from_thread` via `self.app` ; `height: 1fr` sur les DataTable.
- Pas de `bold red` : `bold dark_orange` pour les alertes.
- Un écran qui définit `on_key` **n'appelle pas** `super().on_key(event)` :
  Textual appelle déjà l'`on_key` de chaque classe de la MRO (mixins compris).
  Pour retenir un mixin sur une touche que l'écran consomme :
  `event.prevent_default()`.
- UI partagée : `tui/common.py` (formatage, noms de touches, groupes du pied de
  page), `tui/mixins.py` (TableNavMixin, ColumnResizeMixin),
  `tui/widgets/footer.py` (KeyFooter, ne tronque jamais),
  `tui/screens/confirm.py` (ConfirmModal : toute confirmation passe par elle).
- Pied de page : les touches visibles se déclarent dans `BINDINGS`
  (`show=True`) et s'affichent via `actions_ecran` ; la navigation de table et
  le redimensionnement des colonnes ne s'y annoncent pas (guide `H`). F10
  Quitter est annoncé dans l'en-tête (`AideEtHeure`), pas au pied ; retour
  par Backspace / Esc partout.

## Localisation

- **Tout texte affiché passe par le catalogue** : `_()`, ou `N_()` pour un texte
  défini au chargement d'un module ; `pgettext` pour un libellé court ambigu.
  Jamais de littéral à un point d'affichage, jamais de comparaison à un texte
  traduit (`tests/test_i18n.py`).
- L'anglais (US) est la langue source ; termes du glossaire
  `locales/glossaire.fr.csv`.
- Un `msgid` ajouté ou modifié : reporter la traduction dans
  `locales/fr/LC_MESSAGES/iris_encode.po`, puis `python outils/i18n.py tout`
  (régénère le `.pot`, fusionne, compile le `.mo` versionné).
- Documentation utilisateur en deux langues : une procédure qui change se
  corrige dans `GUIDE.md` et `GUIDE.fr.md` (et les README).

## Tests

- `python -m pytest tests` : la suite complète (plusieurs minutes).
- `python tests/smoke_tui.py` : smoke test headless de l'interface, en anglais
  puis en français (`en` ou `fr` en argument pour une seule langue). À lancer
  après toute modification d'écran.
- `python tests/shots_tui.py [--langue en]` : captures SVG dans
  `_shots/<langue>/` (non versionné), à la demande, pour regarder l'interface.
- **Contre-vérifier chaque nouveau test** : lancé sur le code sans la
  modification, il doit échouer, et échouer **sur le comportement** vérifié —
  pas sur un import ou une erreur de mise en place.

## Versions et documentation

- Schéma `MAJOR.MINOR.PATCH.BUILD`, source unique `version.py`.
- BUILD s'incrémente une fois par implémentation livrée ; MAJOR / MINOR / PATCH
  seulement sur instruction explicite.
- À chaque incrément : `version.py`, une section datée en tête de
  `CHANGELOG.md` (`## [vX.Y.Z.N] — AAAA-MM-JJ`), l'en-tête et l'historique
  (§ 20) de `iris_encode_spec.md`, les en-têtes de `README.md`, `README.fr.md`,
  `GUIDE.md`, `GUIDE.fr.md` (`tests/test_aide.py` le vérifie).
- La spec décrit ce que fait le **code** : la vérifier sur l'implémentation.
- Les rapports datés (audits, revues) ne se réécrivent pas.

## Publication

Le ZIP de release, `iris_encode_vX.Y.Z.N.zip`, est le `git archive` du tag
(sans dossier racine) : les fichiers personnels n'y sont pas, ce qui permet de
l'extraire par-dessus une installation.
