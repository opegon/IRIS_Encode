# IRIS ENCODE — Spécification Fonctionnelle

**Version** : 0.8.9.115 — document de référence courant
**Date** : 2026-10-09
**Statut** : stable

> Ce document suit la version de l'application (`version.py`). Toute implémentation
> incrémente la dernière composante et met à jour l'en-tête ci-dessus ainsi que la
> section 20 (historique). Il remplace `iris_encode_spec_v0_6.md`,
> `iris_encode_spec_v0_7_1.md` et `iris_encode_spec_pistes_externes.md`, tous trois
> absorbés ici.

---

## 1. Contexte et objectif

Réécriture complète du script batch `reencode_hevc_v3.6.bat` en outil Python autonome
avec interface TUI (Terminal User Interface).

**Objectif :** outil portable, robuste, interactif, extensible.

Deux familles d'opérations coexistent :

- **Réencodage** (ffmpeg) — réduire la taille d'un fichier selon un profil.
- **Remux** (mkvmerge) — greffer des pistes externes sans réencoder la vidéo.

---

## 2. Architecture générale

```
iris_encode/
├── README.md                     ← présentation et installation, en anglais (§ 2.1)
├── README.fr.md                  ← la même, en français
├── GUIDE.md                      ← guide d'utilisation (procédures, cas), en anglais
├── GUIDE.fr.md                   ← le même, en français
├── launch.bat                    ← choix de l'interpréteur, point d'entrée Windows
├── dependances.py                ← bornes de requirements.txt contrôlées (lanceurs)
├── bootstrap.ps1                 ← installe uv + CPython + .venv, sans droits admin
├── main.py                       ← point d'entrée Python (autonome)
├── version.py                    ← source unique de la version
├── config.toml                   ← configuration générale (éditable à la main)
├── profiles.toml                 ← profils d'encodage (éditables à la main)
├── bin/                          ← binaires externes (créé automatiquement si besoin)
├── data/
│   ├── ffmpeg_releases.toml      ← sources statiques embarquées (fallback)
│   └── ffmpeg_releases_cache.toml← dernières versions fetchées (cache)
├── core/
│   ├── platform.py               ← abstraction OS + accélération matérielle
│   ├── preflight.py              ← vérification + installation des outils
│   ├── updates.py                ← fraîcheur des outils au démarrage
│   ├── config.py                 ← lecture/écriture config.toml
│   ├── profiles.py               ← lecture/écriture profiles.toml
│   ├── scanner.py                ← analyse fichiers via ffprobe + enrichissement DV
│   ├── bluray.py                 ← titres d'un dossier Blu-ray (playlists .mpls, AACS)
│   ├── dvd.py                    ← titres d'un dossier DVD (IFO, CSS), outil DVD
│   ├── decision.py               ← logique métier encodage
│   ├── encoder.py                ← construction commande ffmpeg + exécution
│   ├── dovi.py                   ← wrapper dovi_tool (probe, RPU, x265-params HDR10)
│   ├── muxer.py                  ← wrapper mkvmerge (identify, mux, extrait)
│   ├── annexes.py                ← .nfo et images Jellyfin d'une vidéo (supprimés avec elle)
│   ├── sous_titres.py            ← sous-titres texte vers MP4 : longs silences comblés
│   ├── joiner.py                 ← collage bout à bout de plusieurs parties
│   ├── sync.py                   ← mesure de décalage par corrélation croisée
│   ├── preview.py                ← lancement mpv (visualisation)
│   ├── veille.py                 ← veille bloquée pendant les traitements, action d'après lot
│   ├── meta.py                   ← recherche métadonnées IMDB / AlloCiné
│   ├── opensubtitles.py          ← sous-titres OpenSubtitles.com (API REST v1)
│   └── i18n.py                   ← traduction de l'interface (gettext, § 2.1)
├── locales/
│   ├── iris_encode.pot           ← textes à traduire, extraits du code
│   ├── glossaire.fr.csv          ← glossaire anglais → français (importable dans Weblate)
│   └── fr/LC_MESSAGES/           ← iris_encode.po (traduction) et .mo (compilé, versionné)
├── outils/
│   └── i18n.py                   ← extraction, mise à jour, compilation (développement)
├── tui/
│   ├── app.py                    ← application Textual principale
│   ├── common.py                 ← formatage, styles DV, groupes de footer
│   ├── mixins.py                 ← TableNavMixin, ColumnResizeMixin
│   ├── screens/
│   │   ├── browser.py            ← navigation fichiers + sélection
│   │   ├── tracks.py             ← sélection pistes + édition décision vidéo
│   │   ├── donor_picker.py       ← choix du fichier donneur + de ses pistes
│   │   ├── opensubtitles.py      ← résultats OpenSubtitles, touche O du donneur
│   │   ├── sync.py               ← recalage des pistes externes
│   │   ├── mux_run.py            ← exécution mkvmerge + progression
│   │   ├── join.py               ← ordre des parties + collage + progression
│   │   ├── dryrun.py             ← prévisualisation décisions
│   │   ├── run.py                ← encodage + progression
│   │   ├── config.py             ← gestion profils (CRUD)
│   │   ├── options.py            ← options hors profil (énergie, langue)
│   │   ├── fin_lot.py            ← compte à rebours avant l'action d'après lot
│   │   ├── profile_picker.py     ← sélection de profil (table)
│   │   ├── value_picker.py       ← modal sélection de valeur
│   │   ├── meta_popup.py         ← popup métadonnées IMDB / AlloCiné
│   │   ├── segments.py           ← plages de décalage détectées (lecture seule)
│   │   ├── confirm.py            ← ConfirmModal générique
│   │   ├── delete_confirm.py     ← confirmation suppression fichier
│   │   ├── recursive_confirm.py  ← confirmation « Encoder le dossier »
│   │   └── quit.py               ← confirmation quitter
│   └── widgets/
│       ├── file_tree.py          ← FileNavigator (navigation virtuelle + répertoires)
│       ├── footer.py             ← KeyFooter (raccourcis, hauteur variable)
│       └── profile_form.py       ← formulaire création/édition profil
├── logger/
│   └── logger.py                 ← module inerte (API prête, non implémenté)
├── tests/
│   ├── smoke_tui.py              ← parcours TUI headless de bout en bout
│   ├── shots_tui.py              ← inventaire visuel des écrans (export SVG)
│   ├── test_deps.py              ← cohérence des listes de dépendances
│   ├── test_dovi.py
│   ├── test_muxer.py
│   ├── test_collage.py
│   ├── test_preview.py
│   ├── test_sync.py
│   ├── test_sous_titres_mp4.py
│   └── test_updates.py
└── requirements.txt
```

### 2.1 Localisation — l'interface en anglais et en français (v0.8.9.72 → v0.8.9.88)

`core/i18n.py`, sur le `gettext` de la bibliothèque standard. **L'anglais est
la langue source** : les textes du code sont en anglais, le français est une
traduction (`locales/fr/LC_MESSAGES/iris_encode.po`). `main.py` charge la langue
de `[app] language` juste après le contrôle des dépendances et l'analyse des
arguments, **avant la bannière** : bannière (origine de Python comprise),
« Checking tools: », preflight et interface passent par le catalogue. Ce qui
s'affiche avant — version de Python, dépendances manquantes, `--help`, chemin
introuvable — est en anglais seul, comme tout ce qui tourne avant `main.py`
(v0.8.9.83) : `launch.bat`, `bootstrap.ps1`, `launcher/` (`build.bat`, le
lanceur C#) et `updater.py`, dont l'invite `[Y/n]` accepte aussi `o`/`oui`.
Les `.bat` n'affichent que de l'ASCII (pas de `chcp 65001`). Le cadre de la
bannière se calcule en cellules depuis son contenu. `tests/test_console_anglais.py`
garde ces règles. Une langue sans catalogue, et
tout message non traduit ou flou, retombe sur l'anglais.

| Élément | Rôle |
|---|---|
| `_`, `ngettext`, `pgettext`, `npgettext` | Traduction, pluriels (règle de chaque `.po`), contexte d'un libellé ambigu |
| `N_` | Marque un texte défini au chargement d'un module (table, `BINDINGS`), traduit à l'affichage |
| `liste(éléments)` | « a, b and c » / « a, b et c » |
| `ErreurAffichable(msgid, **params)` | Erreur montrée à l'écran (hérite de `ValueError`) : `str(e)` en anglais pour le journal, `e.message()` traduit ; au pluriel `Nn_(singulier, pluriel)` + `count` ; `ErreurAffichable.brute(texte)` pour le message d'un service, montré tel quel |
| `texte_erreur(e)` | Le texte d'une erreur pour l'écran : traduit si c'est une `ErreurAffichable`, sinon tel quel |
| `tui.common.texte_style(gabarit, **champs)` | Phrase traduite dont certains champs (une touche) sont stylés, sans balise dans le message |

Les catalogues compilés (`.mo`) sont **versionnés** et livrés dans la release :
rien n'est compilé chez l'utilisateur. `outils/i18n.py` (sans dépendance)
extrait les textes vers le `.pot` (`extraire`), met les `.po` à jour (`maj`,
traductions gardées, disparus en obsolètes) et compile les `.mo` (`compiler`) ;
`tout` enchaîne les trois. `tests/test_i18n.py` vérifie que le `.pot` et les `.mo`
du dépôt sont à jour. Le détail des règles d'écriture est en tête de
`core/i18n.py`. **Les textes de `core/` sont extraits (v0.8.9.74)** : raisons
de décision, diagnostics, refus, mesures, console du preflight (dont la lettre
du « oui », `o` en français, `y` toujours accepté). **Ceux de `tui/` aussi
(v0.8.9.75)** : écrans, modales, en-têtes, notifications ; les descriptions
de touches (`BINDINGS`, listes du pied de page) sont marquées `N_()` et
traduites au rendu, dans le footer et `raccourci`. **Le guide des touches
aussi (v0.8.9.81)** : explications, titres et résumés d'écran de `aide.py`
marqués `N_()`, traduits au rendu ; les titres reprennent les `msgid` des
écrans ; un libellé ou une touche cités sont des paramètres (`{discarded}`,
`{key_mode}`…), la touche lue dans les `BINDINGS` ; repli en cellules
(`cell_len`). `core/texte.py` est
retiré : tous les pluriels passent par `ngettext`.
Les tests chargent le français par défaut (`tests/conftest.py`) : un test qui
vérifie un message français vérifie aussi sa traduction. Depuis la v0.8.9.87
(IE-94), ce qui rend du texte se vérifie **dans chaque langue** — fixture
`langue`, smoke en anglais puis en français, captures `--langue` — et
`tests/test_i18n.py` refuse, dans `core/` comme dans `tui/`, un texte passé en
dur à un point d'affichage, un littéral accentué hors `_()` et toute comparaison
à un texte traduit (§ 18).

**Formats (v0.8.9.82)** : ils suivent `[app] language`, jamais les paramètres
régionaux de Windows (pas de module `locale`). Seule l'unité d'octets de
`fmt_bytes` est traduite (`pgettext("bytes", …)` : TB/GB/MB/KB, To/Go/Mo/Ko en
français ; multiples de 1024). Identiques dans toutes les langues, hors
catalogue : point décimal, pourcentage collé au nombre (`12%`), durées
`H:MM:SS`, symboles `ms`, `s`, `k`, `kbps`, heure de l'en-tête `%H:%M:%S`.
Le texte de remise du quota OpenSubtitles est celui de l'API.
`tests/test_formats.py` garde ces règles.

**Choix de la langue (v0.8.9.84)** : section « Langue de l'interface » de
l'écran Options (`F5`, `U`). Les langues proposées sont l'anglais et chaque
catalogue compilé livré (`i18n.langues_disponibles`), chacune nommée dans sa
propre langue par sa traduction (`pgettext("language name", "English")`,
`i18n.nom_langue`). Le changement s'écrit dans `config.toml` et prend effet au
lancement suivant ; une notification le dit, dans la langue courante. Valeur
par défaut de `[app] language` : vide. Au premier lancement,
`config.assurer_langue` prend la langue d'affichage du système
(`GetUserDefaultUILanguage` sous Windows, `LC_ALL`/`LC_MESSAGES`/`LANG`
ailleurs), retenue si elle est traduite — exacte, puis sans variante
régionale —, sinon l'anglais : jamais un code sans catalogue. Elle est écrite
aussitôt ; un `config.toml` impossible à écrire n'empêche pas de démarrer.
`tests/test_choix_langue.py`.

Le **glossaire** (`locales/glossaire.fr.csv`, colonnes `source`, `target`,
`explanation`) fixe un terme anglais = une traduction, et les termes à ne
jamais traduire (« Do not translate » : SKIP, noms d'outils et de formats…).
Ses arbitrages et la politique de traduction sont au wiki, page `localisation`.
L'anglais source suit l'usage américain (*movie*, *canceled*, *-ize*) et cite
les écrans par leur nom, capitalisé (« the Tracks screen ») (v0.8.9.85).

**Ce qui ne se traduit pas**, quelle que soit `[app] language` :

| Quoi | Pourquoi |
|---|---|
| Termes « Do not translate » du glossaire : `SKIP`, `release`, `lossless` dans une raison, noms de formats (HEVC, DV, TrueHD…), d'outils (ffmpeg, mkvmerge…) et de services | Vocabulaire commun aux deux langues, ou nom propre |
| Noms de profils, y compris le suffixe `_copie` d'une copie ; clés de `config.toml` et `profiles.toml` | Identifiants, écrits dans des fichiers |
| Noms de piste proposés au recalage (`VF`, `Forced`, `Forcés`…) | Données écrites dans le fichier produit, choisies selon la langue **de la piste** (L-77) |
| Codes de langue des pistes (`fre`, `eng`) | Données ISO 639-2 |
| Unités et formats : `ms`, `s`, `k`, `kbps`, durées, point décimal, `%` | Règles fixes (v0.8.9.82) ; seule l'unité d'octets se traduit |
| Console avant `main.py` : `launch.bat`, `bootstrap.ps1`, `updater.py`, `launcher/` | Tournent avant que la langue soit connue : anglais seul (v0.8.9.83) |
| Messages d'un service en ligne (OpenSubtitles, OMDb) | Montrés tels que le service les envoie (`ErreurAffichable.brute`) |
| Journaux (`~/.iris_encode/iris_encode.log`), `str()` d'une erreur | Destinés au diagnostic, pas à l'écran |
| `CHANGELOG.md`, cette spec, le wiki | Documentation de développement, en français |

**Documentation utilisateur (v0.8.9.88)** : `README.md` et `GUIDE.md` sont en
anglais, `README.fr.md` et `GUIDE.fr.md` en français ; chacun renvoie à l'autre
en tête. Les deux langues sont tenues ensemble : une procédure modifiée l'est
dans les deux fichiers. L'anglais cite les libellés et messages tels que
l'interface anglaise les affiche, le français tels que l'interface française
les affiche. `tests/test_aide.py` vérifie les deux guides (toute touche annoncée
répond, en-tête à la version courante, lien croisé) et les deux README.

---

## 3. Lancement

### 3.1 Via `launch.bat` (Windows)

```bat
launch.bat
```

Choisit un interpréteur, dans cet ordre — le premier qui convient :

| Rang | Candidat | Retenu si |
|---|---|---|
| 1 | `.venv\Scripts\python.exe` | chaque paquet de `requirements.txt` est installé et dans ses bornes (`dependances.py`) |
| 2 | `python` du PATH | il est en 3.11 ou mieux (`sys.version_info`, jugé par Python lui-même) |
| 3 | `bootstrap.ps1` | les deux précédents ont échoué — il construit le rang 1 |

Le `.venv` passe devant le Python du système : c'est le seul dont les versions
de bibliothèques soient connues. Un Python système qui convient est *utilisé*,
jamais remplacé — mais si `pip` échoue dessus (poste verrouillé, dépôt interne,
permissions), le lanceur bascule sur `bootstrap.ps1` plutôt que de s'arrêter.

- Propose la mise à jour de l'application avant tout (§ 3.1.2), puis se
  relance sur la version neuve si elle a été installée
- Délègue à `main.py` en passant les arguments (`%*`)
- Utilise `%~dp0` pour garantir la portabilité du chemin, **sans expansion
  retardée** : avec elle, cmd effaçait tout `!` d'un chemin développé — dans
  un dossier `Test!x`, le `.venv` n'était pas trouvé et c'était le `main.py`
  du dossier courant qui démarrait (mesuré)
- Lit la version depuis `version.py` (aucune version en dur), avec
  l'interpréteur retenu — donc après son choix. Les `^"` encadrant l'appel
  `for /f` sont nécessaires : sans eux, une commande dont l'exécutable *et*
  l'argument sont entre guillemets se casse, et la version reste vide. Le
  dossier passe par la variable `IRIS_DIR`, jamais dans le code Python : une
  apostrophe du chemin y fermait la chaîne
- Ne purge plus les `__pycache__` : la purge descendait dans `.venv` et faisait
  recompiler toutes les dépendances à chaque lancement. Python invalide seul un
  `.pyc` dont la source a changé

**Bornes des dépendances.** `requirements.txt` porte pour chaque paquet un
plancher (ce que le code emploie : Textual 8.2) et un plafond (la version
majeure suivante, jamais éprouvée) — arbitrage du 2026-10-09, contre des
versions figées. `dependances.py`, bibliothèque standard seule, compare les
versions installées à ces bornes (`importlib.metadata`) et rend 1 sur un
paquet absent ou hors bornes ; `launch.bat` (rangs 1 et 2) et `bootstrap.ps1`
(`Test-EnvComplet`) l'appellent. Un `.venv` hors bornes est reconstruit par
`bootstrap.ps1` ; un Python du système hors bornes est remis dans les bornes
par `pip install -r requirements.txt`.

**Lanceur `IRIS_Encode.exe`** (`launcher/IrisEncodeLauncher.cs`) : le dossier
est passé à `wt.exe -d` avec ses `;` échappés en `\;` — `wt.exe` lit `;` comme
séparateur de sous-commandes, même entre guillemets (mesuré : dans `A;B`, la
TUI ne démarrait pas). `launcher/build.bat` passe le chemin du raccourci par
`$env:ROOT` : incrusté entre apostrophes PowerShell, un dossier `l'essai`
faisait échouer la création (mesuré).

### 3.1.1 `bootstrap.ps1` — l'environnement Python, sans droits admin

Le prérequis Python était le seul que l'application ne savait pas satisfaire
elle-même. Ce n'était pas un oubli mais une contrainte mécanique : le code qui
télécharge ffmpeg, mkvmerge et dovi_tool *est* du Python, et ne peut donc pas
s'exécuter avant lui. `bootstrap.ps1` est cette exception, écrite en PowerShell.

Il suit la convention de `core/preflight.py` — récupérer dans `bin/`, sans
droits administrateur, sans toucher au PATH ni au registre :

| Étape | Ce qui est récupéré | Où |
|---|---|---|
| 1 | `uv`, exécutable unique, depuis GitHub | `bin\uv.exe` |
| 2 | un CPython 3.12, que `uv` va chercher lui-même | `bin\python\` |
| 3 | l'environnement et `requirements.txt` | `.venv\` |

`UV_PYTHON_INSTALL_DIR` détourne l'installation de `%LOCALAPPDATA%` vers
`bin/python/` : sans elle, l'interpréteur survivrait à la suppression du dossier
et manquerait à une copie sur clé. `UV_LINK_MODE=copy` évite l'avertissement de
lien physique quand le cache de `uv` (sur `C:`) et l'application sont sur des
volumes différents — la copie *est* le comportement voulu ici.

3.12 plutôt que la version la plus récente : une version fraîche casse
régulièrement une roue binaire, et `numpy` en publie une pour 3.12.

**Le `.venv` est créé par le module `venv` de l'interpréteur, et non par
`uv venv`.** Smart App Control, actif par défaut sur une installation *propre* de
Windows 11, refuse d'exécuter les binaires sans réputation établie auprès de
l'ISG. `uv venv` pose dans `Scripts\` un trampoline qu'il fabrique à la volée,
avec le chemin de sa cible embarqué dedans : une empreinte unique par
environnement, donc aucune réputation possible, donc blocage à la première
exécution — `os error 4551`. Le module `venv` copie le redirecteur livré dans la
distribution (`Lib\venv\scripts\nt\python.exe`), identique chez tout le monde.
Ce n'est pas une affaire de signature : le CPython que `uv` télécharge n'est pas
signé non plus, et il s'exécute sans difficulté.

L'étape 3 reconstruit `.venv` de zéro à chaque fois qu'elle est atteinte — on ne
l'atteint que si l'environnement manquait ou était incomplet, et c'est ce qui
répare les postes où le trampoline avait été bloqué. Un échec dont la sortie
porte l'erreur 4551 est nommé comme tel, avec ses deux issues : un Python signé
depuis python.org, que `launch.bat` retiendra, ou la désactivation — définitive —
de Smart App Control. Le diagnostic s'appuie sur le texte de l'erreur et non sur
`VerifiedAndReputablePolicyState` : le registre dit que la politique existe, pas
qu'elle est en cause.

Le script est **idempotent** : relancé, il constate et ne retélécharge rien.
`-Force` reconstruit `.venv` de zéro.

Il vérifie sa sortie en important les six modules, plutôt que de se fier au code
de retour de `uv` — une installation interrompue laisse un `.venv` présent et
incomplet, exactement l'état qu'un code de retour nul ne distingue pas. Même
principe que `encoder.pistes_audio_vides`.

**Encodage** : le fichier porte une BOM UTF-8. Sans elle, Windows PowerShell 5.1
lit les accents en ANSI et le script ne se parse plus.

### 3.1.2 `updater.py` — mise à jour de l'application

Appelé par `launch.bat` une fois Python choisi et les dépendances vérifiées,
avant le bandeau et `main.py`. Il ne lit **que la release GitHub marquée
« Latest »** (`/repos/opegon/IRIS_Encode/releases/latest`), jamais l'état de
`main` : ce qui s'installe est exactement ce qui a été publié et vérifié.

```
1. [updates] app = "off"          → rien, aucun appel réseau
2. dossier .git présent           → rien : un clone ne s'écrase pas par une archive
3. release « Latest »             → cache .iris_update/release.json, 1 h, invalidé si version.py a changé ; délai 8 s
4. tag ≤ version.py               → rien
5. "ask" : « Install now? [Y/n] », Entrée, o, oui, y, yes valent oui ; "auto" : sans question
6. archive iris_encode_v….zip     → SHA256 comparé au `digest` publié par GitHub
7. contrôle de l'archive          → chemins, fichiers personnels, REQUIS, version
8. sauvegarde, remplacement, retrait de ce qui n'est plus livré (manifeste)
9. code 10                        → launch.bat se relance sur la version neuve
```

| Règle | Pourquoi |
|---|---|
| **Bibliothèque standard seulement** | il remplace les modules de l'application : il ne peut en importer aucun, ni une dépendance que la mise à jour changerait (`tests/test_updater.py` le vérifie) |
| **Jamais bloquant** | hors ligne, API en erreur, archive refusée : message, code 0, l'application démarre dans sa version actuelle |
| **Sans console, aucune installation** en mode `ask` | un « O » présélectionné n'est pas un consentement quand personne ne peut répondre ; Ctrl+C vaut non |
| **Empreinte obligatoire** | une release sans `digest` SHA256 n'est pas installée |
| **Fichiers personnels intouchables** | `config.toml`, `profiles.toml`, `CLAUDE.md`, et les dossiers `.venv`, `bin`, `.git`, `.iris_update`, `resources_files`, `_shots` : une archive qui voudrait y écrire est refusée en bloc |
| **`REQUIS`** : `version.py`, `main.py`, `launch.bat`, `updater.py` | une archive qui en manque n'est pas la nôtre, ou retirerait le mécanisme de mise à jour lui-même. La v0.8.9.0, antérieure à `updater.py`, est ainsi refusée (vérifié contre GitHub) |
| **Sauvegarde puis restauration** | tout fichier touché est copié dans `.iris_update/sauvegarde/` ; au moindre échec, il est remis et les fichiers créés sont retirés |
| **Manifeste** (`.iris_update/manifeste.txt`) | liste des fichiers livrés : ce que la version précédente livrait et que la nouvelle ne livre plus est retiré. Sans manifeste (première mise à jour), rien n'est retiré |
| **L'archive ne reste pas** | acceptée ou refusée, elle est supprimée |

**Le bloc de relance.** cmd.exe lit un `.bat` au fil de l'exécution, par
position dans le fichier. Remplacé pendant qu'il tourne, la suite serait lue
dans le nouveau fichier à l'ancienne position : un fragment de ligne exécuté
comme une commande (mesuré : `'xxx…' n'est pas reconnu en tant que commande`).
L'appel à `updater.py` et la relance (`"%~f0" %*`) tiennent donc dans **un seul
bloc `( )`**, que cmd lit en entier avant de l'exécuter. Vérifié sur un
`launch.bat` réel qu'un faux updater remplace : la nouvelle version s'exécute,
l'ancien `main.py` n'est jamais lancé.

**Le lanceur compilé** (`IRIS_Encode.exe`) n'est pas dans l'archive : si
`launcher/IrisEncodeLauncher.cs` change, l'utilisateur est invité à relancer
`launcher\build.bat`.

**Amorçage** : une installation antérieure à la v0.8.9.1 n'a pas `updater.py`.
Elle se met à jour une dernière fois à la main ; les suivantes se font seules.

### 3.2 Via `main.py` (direct)

```bash
python main.py
```

Entièrement autonome, indépendant de `launch.bat`. Aucune logique critique ne réside
dans `launch.bat`.

---

## 4. Preflight — `core/preflight.py`

### 4.1 Outils gérés

| Outil | Statut | Usage |
|---|---|---|
| `ffmpeg` | essentiel | encodage, extraction, décodage pour la mesure |
| `ffprobe` | essentiel | analyse des fichiers |
| `dovi_tool` | optionnel | Dolby Vision (probe RPU, métadonnées HDR10) |
| `mkvmerge` | optionnel | remux de pistes externes, identification `-J` |
| `mpv` | optionnel | visualisation d'un fichier ou d'un recalage |
| `ffmpeg_dvd` | optionnel | outil DVD : ffmpeg BtbN GPL dans `bin/dvd/`, analyse et extraction des titres de DVD (§ 15.6) |

Ordre de recherche : **PATH système**, puis dossier local `./bin/`. L'outil DVD
n'est cherché que dans `./bin/dvd/` (`chemin_local`) ; il n'est pas proposé
quand le ffmpeg principal a le démultiplexeur `dvdvideo` (`_dvd_manquant`).

L'absence d'un outil optionnel ne bloque jamais le lancement — elle désactive la
fonction correspondante avec un message explicite.

### 4.2 Auto-installation si absent

- Proposition à l'utilisateur (sans exiger un terminal interactif)
- Téléchargement depuis `config.toml` → `[ffmpeg] fetch_url`, ou `data/ffmpeg_releases.toml`
- **Empreinte SHA256 exigée** (`preflight._download`) : sans empreinte, rien n'est
  téléchargé ; une empreinte fausse fait rejeter l'archive. Elle est épinglée dans
  `data/ffmpeg_releases.toml` (dovi_tool, mkvmerge, mpv) ou lue chez l'amont : le
  `<url>.sha256` publié à côté de l'archive (gyan.dev, pour `fetch_url`), le `digest`
  des assets GitHub (BtbN, dovi_tool, mpv), `sha256sums.txt` de MKVToolNix
- Extraction dans `./bin/`, aplatie par nom de fichier, depuis un ZIP ou un tar
  (gz, xz — les builds Linux). dovi_tool publié en exécutable nu n'est écrit tel
  quel que s'il en a l'en-tête (`MZ`, `ELF`) : un `.tar.gz` y passait comme binaire
- **Tous ou aucun** (`preflight._poser_tous`) : chaque exécutable est écrit dans un
  provisoire du même dossier (`.iris_tmp`), puis tous sont remplacés par
  `os.replace`. Un échec d'écriture laisse les outils d'origine intacts, et
  l'archive doit contenir tous les exécutables attendus (ffmpeg **et** ffprobe)
- Build ffmpeg cible : **essentials** (~30 Mo)
- Outil DVD : `updates.latest_ffmpeg_dvd` choisit dans la release `latest` de
  BtbN le ZIP `ffmpeg-nX.Y-latest-win64-gpl-X.Y.zip` de la branche la plus
  haute (aujourd'hui n9.0), extrait `ffmpeg` et `ffprobe` dans `bin/dvd/`
  (`poser("ffmpeg_dvd")`). Les ZIP étant refaits chaque jour, seule la branche
  se compare : une mise à jour est proposée au changement de branche.
- Sources : gyan.dev / BtbN (ffmpeg), GitHub quietvoid (dovi_tool),
  mkvtoolnix.download (mkvmerge), sourceforge (mpv)

**Cas particulier mpv** : publié uniquement en `.7z`. L'extraction passe par le
`tar`/libarchive livré avec Windows 10/11 plutôt que par une dépendance Python nouvelle.

### 4.3 Fetch des sources

Les dernières versions publiées sont interrogées au plus une fois par jour (§ 4.4) et
mises en cache dans `data/ffmpeg_releases_cache.toml`, avec leur URL et leur empreinte.
Ce cache ne sert **qu'aux mises à jour** : l'installation d'un outil absent lit les
seules sources statiques, `data/ffmpeg_releases.toml` (`preflight._load_releases`).
Elle lisait le cache en priorité, sous une forme qui n'est pas la sienne : dès le second
lancement, installer dovi_tool, mkvmerge ou mpv échouait sur « URL not found ».

### 4.4 Vérification des mises à jour — `core/updates.py`

Au démarrage, au plus **une fois par jour**, sans bloquer hors ligne. Compare la version
installée de chaque outil à la dernière version publiée et signale les retards.
Piloté par `[updates] check_on_startup` — lu dans cette section-là, et non sous
`[ffmpeg]` comme ce fut le cas : le réglage retombait alors toujours sur son défaut.

**Une mise à jour range comme une installation.** Les deux passent par
`preflight.poser()`, point unique qui sait sous quelle forme chaque outil publie —
dovi_tool tantôt en ZIP, tantôt en exécutable nu, mpv en 7z, le reste en ZIP. La mise à
jour appelait auparavant l'extracteur ZIP en direct : une release dovi_tool livrée en
binaire nu échouait à chaque lancement, pendant qu'une installation neuve de la même
release réussissait. L'empreinte suit la release découverte (`Release.sha256`,
`Update.sha256`), et la mise à jour la vérifie comme l'installation (§ 4.2).

**Le relevé des versions est parallèle** (`check_tools`). `_get_version` essaie deux
drapeaux à 5 s de délai chacun, et mkvmerge comme dovi_tool échouent sur le premier :
en série, un démarrage payait jusqu'à dix lancements de sous-processus l'un après
l'autre, deux fois s'il fallait installer ffmpeg. Même position que
`platform.sonder_encodeurs` pour les encodeurs (§ 11). Le numéro lu est le
premier `X.Y[.Z]` de la sortie, préfixe `v` ou `n` admis (`mkvmerge v99.0`,
ffmpeg BtbN `n8.1.3-20260925`).

### 4.5 Sortie console

```
[✓] ffmpeg      trouvé — 7.1.1
[✓] ffprobe     trouvé — 7.1.1
[✓] dovi_tool   trouvé — 2.1.0
[✓] mkvmerge    trouvé — 99.0
[✗] mpv         introuvable (optionnel)
```

---

## 5. Configuration — `config.toml`

Fichier unique, éditable à la main, dans le dossier de l'application.

**Fichier illisible** (v0.8.9.98, CR-43) — comme `profiles.toml` (§ 6.2) : la
session tourne sur les valeurs par défaut et **ne réécrit pas** le fichier
(`config.illisible()` posé par `load()`, `save()` lève `ConfigIllisible`) ; la
console le dit avant l'interface, l'interface le redit au montage. Avant, la
langue écrite au démarrage (`assurer_langue`) remplaçait le fichier — clés
d'API et mot de passe compris — à la moindre faute de frappe.

**Écriture refusée** (v0.8.9.98, CR-64, CR-77) — `config.enregistrer(cfg)` rend
la cause d'un échec au lieu de lever ; l'interface écrit toujours par
`tui/common.sauver_config` / `signaler_config`, qui le notifient une fois par
cause. `set_active_profile` et `set_energie` rendent la cause de même. Un
antivirus ou un client de synchronisation qui tient le fichier ne ferme plus
l'application, ni le lot en cours. La vitesse mesurée s'enregistre sur le fil
de l'interface (`call_from_thread`) : toutes les modifications de la
configuration y vivent, l'écriture ne croise plus celle d'un autre fil (CR-44).

```toml
[app]
language = "fr"          # vide : celle de Windows au premier lancement (§ 2.1)
output_dir = ""          # proposé pour une source en lecture seule (§ 14.7) ; vide : ~/Videos
min_title_minutes = 2    # durée minimale d'un titre de disque listé (§ 15.5, § 15.6) ; 0 : tous

[ffmpeg]
fetch_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
auto_install = true
bin_dir = "./bin"

[updates]
check_on_startup = true   # fraîcheur des outils externes (§ 4.4)
app = "ask"               # mise à jour d'IRIS elle-même (§ 3.1.2) : ask / auto / off

[meta]
omdb_api_key = ""       # clé gratuite sur omdbapi.com — active note + synopsis IMDB

[energie]
empecher_veille = true    # veille bloquée pendant un traitement (§ 14.7)
action_fin = "rien"       # après un lot coché « Après le lot » : rien / veille / veille_prolongee / arret

[decision]
near_1080p_min_width  = 1600    # seuils de rattachement au bucket 1080p
near_1080p_min_height = 850

[stats.encode_speed]
# Moyenne mobile de vitesse relevée à chaque passe — alimente la colonne « ETA »
hevc = 7.49
h264 = 21.43

# L'écran d'accueil ignore cette section au lancement : il repart toujours des
# largeurs par défaut du code, pour retrouver la même disposition d'une session
# à l'autre. Le redimensionnement reste actif pendant la session.
[tui.browser.columns]
fichier = 50
taille = 8
resolution = 10
duree = 6
debit = 6
codec = 6
dolby_vision = 8
decision = 8
estim = 14
temps_estim = 9
audio = 20

[tui.dryrun.columns]
fichier = 48
conteneur = 10
audio = 54
estim = 18
action = 10
dv = 6

[tui.tracks.columns]
codec = 12
src = 26
```

Les largeurs de colonnes sont réécrites automatiquement après tout redimensionnement
manuel dans l'interface.

---

## 6. Profils d'encodage — `profiles.toml`

Format TOML, éditable à la main. **Le fichier fait foi** : les profils affichés,
et leur ordre, sont ceux qu'il décrit — rien de plus, rien de moins. Tous sont
éditables et supprimables ; l'application refuse seulement d'effacer le
dernier, une liste vide ne laissant rien à sélectionner. Le nom d'un profil ne
se saisit qu'à la création — pour renommer, on édite `profiles.toml`.

Le champ `dolby_vision` accepte : `"hdr10"` (DV → HDR10), `"dv"` (DV → DV copy),
`"sdr"` (DV → SDR tone map).

**`"dv"` réencode quand il le peut, copie sinon.** Le RPU vit *à l'intérieur*
du flux HEVC, entre les tranches d'image : ce n'est pas une piste qu'on laisse
passer, et tout réencodage le détruit. Deux issues, tranchées par
`decision.peut_reencoder_en_dv` (§ 7.4) :

| | Action | Libellé | Débit cible |
|---|---|---|---|
| RPU réinjectable | `ENCODE_DV` | `→ HEVC → DV` | **appliqué** |
| sinon | `ENCODE_HEVC` + `-c:v copy` | `→ DV (copie)` | sans effet |

Les deux sorties portent le suffixe `.dv-iris` (§ 8.7) — l'une comme l'autre rendent un
fichier Dolby Vision ; ce qui les sépare est le débit, que la raison affichée
explicite. La copie qui sort en MP4 reçoit `-strict unofficial` : sans lui,
ffmpeg n'écrit pas l'enregistrement de configuration `dvcC` et le téléviseur
ne voit plus de Dolby Vision (IE-109). Les sources sans DV sont encodées normalement par ce même profil.

**Trois niveaux, du plus légitime au plus dégradé.**

| | Source | Rôle |
|---|---|---|
| 1 | `profiles.toml` | le fichier de l'utilisateur — il fait foi |
| 2 | `data/profiles.default.toml` | les **profils livrés** : sèment le fichier au premier lancement, tiennent la session si le TOML de l'utilisateur devient illisible |
| 3 | `_default_` | plancher codé en dur, dernier recours si le fichier livré manque |

**Les profils livrés** (v0.8.8.4 ; quatorze depuis la v0.8.9.54) sont versionnés avec le code et donc
présents dans l'archive d'une release — `profiles.toml`, lui, est ignoré par
git : c'est le fichier de travail de chaque poste. Jusque-là le plancher semait
seul, et le sélecteur d'une installation neuve s'ouvrait sur une liste d'un
élément : rien qui montre ce qu'un profil règle, ni ce que change le fait d'en
changer.

Le premier du fichier livré est `series_anime`, et il porte
`delete_source = false` : c'est lui que `get_active_profile` retient au premier
lancement, tant que rien n'a été choisi (`tests/test_profils_livres.py` y
veille). Trois profils livrés portent `delete_source = true` —
`series_anime_delete`, `series_basic_delete` et `video_basic_delete` —, chacun
signalé « ⚠ suppr. » dans `F4` et `F5` ; aucun n'est en tête.

Depuis la v0.8.9.54, le fichier livré est la bibliothèque de profils de
l'auteur, recopiée telle quelle : une installation neuve la reçoit au premier
lancement, une mise à jour ne touche jamais le `profiles.toml` existant — à
une exception près, le renommage des profils livrés.

**Renommage `serie_*` → `series_*`** (v0.8.9.56, IE-112). Les noms de profils
ne se traduisent pas : ils doivent être neutres, et `serie_` était le seul
préfixe français. `load_all` migre le fichier de l'utilisateur au chargement
(`RENOMMAGES_LIVRES`, `_migrer_noms`) : un ancien nom de profil livré est
renommé si le nouveau est libre, dans l'ordre du fichier, réglages intacts,
et le fichier est réécrit une fois. Un `serie_*` créé par l'utilisateur garde
son nom. `config.get_active_profile` applique le même renommage au profil
actif mémorisé. `tests/test_migration_profils.py`.

Le fichier livré est une donnée, éditable à la main, que rien d'autre ne relit :
`tests/test_profils_livres.py` en contrôle la forme (champs connus, types,
domaines) et deux cohérences de fond — débits audio et vidéo croissants. Un
plafond 1080p supérieur au plafond 4K réencoderait des 1080p en épargnant des
4K plus lourdes.

**Profil plancher `_default_`** : le seul profil codé en dur. Il n'apparaît pas
tant qu'un autre niveau répond. Depuis la v0.8.8.4 il ne sème plus le premier
lancement — il ne sert que si `data/profiles.default.toml` est absent ou
illisible, c'est-à-dire sur une installation abîmée, pas sur une installation
neuve. Ses réglages recopient l'ancien profil livré `serie_basic` (2200k en
1080p, 5000k en 4K, preset `medium`, sans audio HD), à une exception près :
`dolby_vision = "sdr"` et non `"hdr10"` — il doit rendre un fichier qui se lit
partout, pas un HDR10 délavé sur un téléviseur qui ne le gère pas. **Un profil
qui n'a pas la clé `dolby_vision` se rabat sur `"sdr"`** pour la même raison ;
une valeur présente mais inconnue, elle, reste traitée en `hdr10`.

Le profil actif est **mémorisé dans `config.toml`** (`[app] active_profile`) :
l'application rouvre sur celui qu'on utilisait la dernière fois. À défaut —
premier lancement, ou profil disparu depuis — elle prend le premier du fichier.

### 6.1 Champs d'un profil

| Champ | Type | Rôle |
|---|---|---|
| `bitrate_720p_kbps` | int | débit cible en bucket 720p |
| `bitrate_1080p_kbps` | int | débit cible en bucket 1080p |
| `bitrate_4k_kbps` | int | débit cible en bucket 4K |
| `keep_4k` | bool | conserver la 4K, sinon downscale 1080p |
| `delete_source` | bool | supprimer la source après encodage réussi, avec son `.nfo` et ses images Jellyfin (§ 14.7) |
| `preset_encoder` | str | `fast` / `medium` / `slow` |
| `dolby_vision` | str | `hdr10` / `dv` / `sdr` |
| `hdr10_quality` | str | `"quality"` → libx265 CPU + métadonnées HDR10 propres |
| `preserve_hd_audio` | bool | copier TrueHD / DTS-HD MA au lieu de transcoder |
| `audio_languages` | list | langues conservées (l'index 0 l'est toujours) |
| `audio_stereo_kbps` | int | débit AAC stéréo |
| `audio_surround_kbps` | int | débit AC3 5.1 |
| `audio_surround_7_1_kbps` | int | débit AC3 7.1 |
| `audio_copy_compatible` | bool | copier AAC / AC3 / EAC3 sans transcoder |
| `audio_hd_codec` | str | `none` / `ac3` / `eac3` — transcoder TrueHD et DTS au débit de la source (§ 8.5) |
| `container` | str | `auto` / `mp4` / `mkv` — conteneur de sortie (§ 8.6) |

### 6.2 Comportement quand le fichier ne fournit rien

| Cas | Ce que fait l'application |
|---|---|
| `profiles.toml` absent | écrit les **profils livrés** dans un fichier neuf, et les charge |
| `profiles.toml` absent **et** fichier livré absent | écrit `[_default_]` dans un fichier neuf, et le charge |
| TOML invalide | **ne réécrit rien** — le fichier de l'utilisateur est sa bibliothèque, il reste réparable à la main — et tient la session sur les profils livrés, chargés en mémoire seulement. `save_all` refuse jusqu'à la fin de la session (`ProfilsIllisibles`, v0.8.9.98, CR-45) : l'écran de gestion le dit à l'ouverture et à chaque enregistrement, l'interface au montage |
| TOML invalide **et** fichier livré absent | ne réécrit rien, tient la session sur `_default_` |
| fichier vide, ou sans table nommée | charge `_default_` |

**Comportement sur erreur de syntaxe :**

```
⚠ profiles.toml illisible (erreur syntaxe ligne 12).
  Session tenue sur les 14 profils livrés — votre fichier n'a pas été touché.
```

L'écriture du fichier semé passe par `save_all`, donc par l'écriture atomique de
`_ecrire` (§ 6) : une coupure pendant le premier lancement ne laisse pas un TOML
tronqué derrière elle.

---

## 7. Dolby Vision — `core/dovi.py`

Module wrapper autour de `dovi_tool`, utilisé en trois phases :

1. **Scan** (`probe_file`) : enrichit chaque `VideoInfo` avec sous-profil, master
   display, MaxCLL/FALL
2. **Encodage** (`make_x265_hdr_params`) : fournit les `-x265-params` du mode HDR10 quality
3. **Retrait du RPU** (`build_remove_command`) : supprime le Dolby Vision sans réencoder, quand
   la couche de base est déjà du HDR10 (§ 7.3)

### 7.1 API publique

| Fonction | Description |
|---|---|
| `get_path(bin_dir)` | Chemin vers `dovi_tool` (PATH puis `./bin/`) ou None |
| `is_available(bin_dir)` | Bool |
| `probe_file(path, dovi_path, ffmpeg_path)` | Sous-profil DV + master display + MaxCLL |
| `extract_hevc_stream(…)` | Extrait le flux HEVC brut Annex-B via ffmpeg |
| `extract_rpu(…)` | Extrait le RPU depuis un `.hevc` brut |
| `build_extract_hevc_command(…)` | Commande ffmpeg de l'extraction (progression côté TUI) |
| `build_remove_command(hevc_in, hevc_out, dovi_path)` | `dovi_tool remove` : retire RPU et couche d'amélioration — lancée par l'écran, arrêtable, sans délai fixe |
| `build_inject_command(hevc_in, rpu_in, hevc_out, dovi_path)` | `dovi_tool inject-rpu`, même régime |
| `TuyauRpu(source, rpu, dovi_path, ffmpeg_path, duration)` | ffmpeg en tuyau sur `dovi_tool extract-rpu`, avec l'interface d'`EncoderProcess` (progression de ffmpeg, pause, arrêt) ; `wait()` n'est nul que si les deux le sont (CR-31) |
| `rpu_valide(rpu)` | Le RPU existe et n'est pas vide (une source sans RPU donne un fichier vide, code 0) |
| `build_strip_mp4(source, output, …)` | Retrait vers du MP4 sans greffe : une passe ffmpeg depuis la source, filtre `dovi_rpu=strip=1` ; `chapitres` (FFMETADATA) et langues complétées d'un titre de Blu-ray |
| `strip_bsf_disponible(ffmpeg_path)` | ffmpeg connaît-il le filtre `dovi_rpu` (7.1+) ? |
| `convert_p7_to_p8(…)` | Convertit RPU profil 7 → profil 8 (mode `-m 2`) |
| `rpu_info(…)` | `{dv_subprofile, master_display, max_cll}` |
| `make_x265_hdr_params(…)` | Liste de tokens `-x265-params` HDR10 |
| `x265_params_string(params)` | Concatène en `key=val:key=val` |

### 7.2 Flux probe (au scan)

```
1. ffmpeg  : extrait 30 s de flux HEVC brut  (input.mkv → temp.hevc)
2. dovi_tool extract-rpu                     (temp.hevc  → temp.rpu)
3. dovi_tool info -f 1                       → sous-profil, master_display, MaxCLL
```

Coût : ~50–150 ms par fichier. Ne lève pas en cas d'échec (retourne un dict vide).

### 7.3 Retrait du Dolby Vision sans réencodage

Un profil **8.1** annonce `dv_bl_signal_compatibility_id = 1` : sa couche de base
*est* du HDR10, et le RPU n'est qu'un jeu de NAL supplémentaire. Un profil **7** a
lui aussi une couche de base HDR10, doublée d'une couche d'amélioration. Dans ces
deux cas, retirer le RPU suffit à obtenir un HDR10 valide — aucune image n'est
recalculée, et le HDR10+ éventuel survit, ce qu'aucun réencodage ne permet.

En Matroska :

```
1. ffmpeg    : extrait le flux HEVC brut     (source     → *.iris_bl.hevc)
2. dovi_tool : remove                        (*.iris_bl  → *.iris_nodv.hevc)
3. ffmpeg    : pistes audio finales          (source     → *.iris_audio.mka)
4. mkvmerge  : remux                         (→ <nom>.hdr10-iris.mkv)
```

En MP4, une seule passe, depuis la source :

```
1. ffmpeg -c copy -bsf:v dovi_rpu=strip=1   (source → <nom>.hdr10-iris.mp4)
```

En MP4 **avec des pistes greffées** (v0.8.9.107, CR-55), le chemin Matroska, puis
un remux :

```
1–4. comme en Matroska, vers                 (→ *.iris_strip.mkv)
5.   ffmpeg : remux MP4 (build_dv_mp4_remux) (→ <nom>.hdr10-iris.mp4)
```

La passe unique n'avait que la source pour entrée : VF et sous-titres greffés
disparaissaient, l'encodage était déclaré réussi. ffmpeg ne saurait pas étirer une
greffe ; mkvmerge décale, étire et nomme, et ffmpeg remuxe son Matroska comme au
réencodage DV — les horodatages du flux brut sont reconstitués par mkvmerge,
le défaut décrit plus bas ne s'y présente pas.

**Les greffes des deux chemins DV** (v0.8.9.107) passent par
`RunScreen._transcoder_greffes` avant mkvmerge : une piste audio que la règle du
profil transcode (§ 12.0) est produite par `build_audio_command` depuis son
donneur, dans un `*.iris_greffe<n>.mka` qui le remplace (piste 0) ; décalage,
étirement, langue et drapeaux restent à mkvmerge. Les pistes sont prises dans
l'ordre de `premux_track_order` : un donneur qui perd son audio garde sa place, et
les sous-titres du Matroska recomposé restent dans l'ordre que lit
`greffes_a_porter`.

**Un titre de Blu-ray** (IE-120) garde ses chapitres et ses langues sur les chemins
DV (v0.8.9.107, CR-63) : mkvmerge reçoit sa playlist en `--chapters` (il y lit les
marques, mesuré) — `_playlist_chapitres`, deux chapitres au moins comme
`ffmetadata_chapitres` ; la passe MP4 directe reçoit le fichier FFMETADATA de
`_ecrire_chapitres`. Les langues lues dans le `.clpi` sont écrites par
`build_audio_command`, dont le `.mka` remplace l'audio de la source, et par
`build_strip_mp4`.

**Pourquoi deux chemins.** mkvmerge n'écrit que du Matroska. Jusqu'à la
v0.8.8.14, le MP4 était recomposé par ffmpeg **à partir du flux brut** de
l'étape 2. Or un flux Annex-B ne porte aucun horodatage : ffmpeg écrivait
PTS = DTS sur chaque image (« pts has no value »), ce qui donne un ordre
d'affichage faux dès qu'il y a des images B. Sur téléviseur, la lecture
démarrait sur le son seul, sans image, puis plantait. mkvmerge, lui,
reconstitue les horodatages d'un flux brut ; le MKV n'a jamais eu ce défaut
(vérifié : paquets identiques à la source, seuls les NAL 62 en moins). Le MP4
lit maintenant la source, dont il garde les horodatages, et le filtre
`dovi_rpu` de ffmpeg (7.1+) retire le RPU et l'enregistrement de configuration
DV. Un ffmpeg plus ancien fait échouer le fichier avec un message explicite
(`strip_bsf_disponible`).

**Le profil 7 reste en MKV** (`needs_mkv`) : le filtre ffmpeg ne retire que le
RPU, et seul `dovi_tool remove` enlève aussi la couche d'amélioration.

Avec `container = "auto"`, le retrait ne sort en MKV que si l'audio ou les
sous-titres l'imposent (§ 8.6) : une source WEB-DL en E-AC3 + SubRip sort en MP4.

**La décision audio s'applique ici aussi.** Ce chemin ne portait que la vidéo :
mkvmerge recopiait les pistes de la source en bloc, quoi qu'ait annoncé l'écran
— un TrueHD annoncé « → E-AC3 » sortait en TrueHD, sous son ancien titre. Ce que
chaque opération coûte n'est pas le même, et le chemin le reflète :

| Opération | Comment |
|---|---|
| Exclure une piste par langue | `--audio-tracks` sur la commande existante, aucune passe |
| Écarter des sous-titres | `--subtitle-tracks`, aucune passe |
| Transcoder (TrueHD/DTS → E-AC3) | étape 3, puis `--no-audio` sur la source |
| Retitrer une piste transcodée | `-metadata` de l'étape 3 |

L'étape 3 n'existe **que** si une piste est à transcoder : mkvmerge sait ne pas
prendre une piste, et recopier des gigaoctets pour en écarter une serait absurde.
Elle produit toutes les pistes finales — les recopies comprises, pour que leur
ordre et leurs métadonnées ne dépendent pas de deux entrées différentes. En MP4,
il n'y a jamais d'étape 3 : ffmpeg recompose déjà le fichier et transcode dans
la même passe.

Mesuré sur un film 4K de 5,7 Go (2 h 24) : **2 min 16 s** au total, sortie
bit à bit identique à la source (`framemd5`). Le même fichier réencodé en
`libx265` prendrait ~74 h et perdrait le HDR10+.

Les intermédiaires sont écrits **à côté de la source**, pas dans le temp du
système : ils pèsent le poids du film, et le disque système n'a pas 30 Go à
prêter. Ils sont supprimés que l'opération aboutisse ou non.

**Exclusions** — profil 5 (couche de base IPT-PQ, illisible sans RPU) et profil
8.4 (couche de base HLG). Ces fichiers suivent le chemin de réencodage.

**Pickers de codec.** Ni `STRIP_DV` ni `ENCODE_DV` n'appartiennent à
`ACTION_CYCLE` : ce ne sont pas des codecs proposables, mais ce que la décision
retient d'elle-même. Chacun se range là où son intention le place —
`cycle_index()` rend la position de `SKIP` pour `STRIP_DV` (ne pas réencoder)
et celle d'`ENCODE_HEVC` pour `ENCODE_DV` (réencoder en HEVC). `same_intent()`
fait que choisir cette position-là lève la surcharge plutôt que de l'imposer :
un `SKIP` sec laisserait le RPU en place sans rien dire, un `ENCODE_HEVC` sec
ferait perdre le Dolby Vision. Toute action doit avoir une position dans le
cycle — un `.index()` direct lève un `ValueError` et fait tomber l'écran.

**Prérequis** — `dovi_tool` *et* `mkvmerge`. Sans les deux,
`decision.set_strip_dv_available(False)` fait retomber la décision sur `SKIP` :
proposer une action qui échouera au lancement vaut moins que ne rien proposer.

### 7.4 Réencodage préservant le Dolby Vision — `ENCODE_DV`

Écrêter le débit d'une source Dolby Vision, ou la faire passer en HEVC, sans
perdre le DV. Le RPU vit entre les tranches d'image du flux HEVC : on le sort
avant l'encodage, on le remet après.

**Éligibilité** — `decision.peut_reencoder_en_dv(info, w, h)`, trois conditions
toutes nécessaires :

| Condition | Pourquoi |
|---|---|
| couche de base HDR10 (`can_strip_dv` : profil 7, ou 8 avec `bl_compat = 1`) | réinjecter le RPU d'un profil 5 (base IPT-PQ) ou 8.4 (base HLG) dans un flux HDR10 donne des couleurs fausses |
| `w == info.width` et `h == info.height` | le RPU est indexé image par image et décrit un cadrage ; redimensionner le rend faux |
| dovi_tool **et** mkvmerge présents | les deux outils du pipeline |

À défaut, la décision retombe sur la copie du flux — libellé « → DV (copie) ».

**Le conteneur suit la règle commune** (v0.8.9.57, IE-108) : MP4 dès que le
contenu le permet avec `container = "auto"`, MKV sinon (§ 8.6). Sur le G3, un
DV 8.1 en MP4 `hvc1` passe en lecture directe avec le Dolby Vision ; le même
en MKV plante l'appli Jellyfin, et `dvh1` ne se lance pas (IE-75). Le profil 7,
converti en 8.1 à l'étape 2, sort aussi en MP4.

**Pipeline** — `tui/screens/run.py:_encode_dv`, quatre à sept étapes :

```
1. ffmpeg -c:v copy -f hevc -  |  dovi_tool extract-rpu -   →  film.rpu
2. (profil 7) dovi_tool convert -m 2                        →  RPU en 8.1
3. ffmpeg -c:v <encodeur> -f hevc                           →  enc.hevc
4. dovi_tool inject-rpu -i enc.hevc --rpu-in film.rpu       →  dv.hevc
5. (si transcodage audio) build_audio_command               →  audio.mka
6. mkvmerge dv.hevc + pistes de la source                   →  sortie.dv-iris.mkv
                                                               (ou iris_dv.mkv)
7. (sortie MP4) dovi.build_dv_mp4_remux                     →  sortie.dv-iris.mp4
```

**L'étape 7 part du Matroska, pas du flux brut.** Depuis `dv.hevc`, ffmpeg
écrit un MP4 sans boîte `dvcC`, même avec `-strict unofficial` : le RPU est
dans le flux, mais le téléviseur ne voit plus de Dolby Vision. Depuis le MKV
de mkvmerge, qui porte l'enregistrement de configuration, il la recopie —
à condition de `-strict unofficial` (IE-109). Options : `-c copy -c:s
mov_text -tag:v hvc1 -strict unofficial -movflags +faststart`, vidéo, audio et
sous-titres seuls (une pièce jointe ne tient pas en MP4). Mesuré sur un
extrait DV 8.1 de 2 270 images (2026-10-03) : `hvc1`, `dvcC` profil 8 compat. 1,
RPU de 2 270 images, SRT passés en `mov_text`. L'intermédiaire est effacé
comme les autres.

L'étape 1 est un tuyau : `dovi_tool extract-rpu` accepte `-` en entrée, ce qui
évite une recopie du film entier pour en tirer quelques kilo-octets.
L'injection, elle, exige de vrais fichiers — elle relit son entrée une première
fois pour reconstituer l'ordre des images.

**Les étapes dovi_tool sont des processus du lot** (v0.8.9.108, CR-32, CR-61) : le
tuyau (`TuyauRpu`), `remove` et `inject-rpu` passent par `RunScreen._executer`,
publiés comme ffmpeg. `S`, `X`, la pause et la sortie les atteignent ; aucun délai
fixe ne les tue — 30 min pour `remove`, 2 h pour `inject-rpu`, 1 h pour le tuyau
pouvaient ne pas suffire sur un disque USB ou un partage, et l'étape mourait après
des dizaines de minutes de travail. Seul `convert` (quelques kilo-octets de RPU)
garde un appel bloquant court.

**La passe vidéo ne porte aucun filtre**, pas même un `scale` aux dimensions
d'origine : le nombre d'images doit correspondre au RPU, et un `-vf` ajouté
plus tard sans voir la contrainte rendrait des fichiers faux sans rien dire.
Elle sort en 10 bits (`p010le` pour NVENC, `yuv420p10le` pour libx265).

**Les métadonnées HDR10 statiques n'ont pas à être reposées.** ffmpeg recopie
primaires BT.2020, courbe PQ, master display et MaxCLL de la source vers la
sortie en SEI, y compris à travers NVENC — mesuré, pas supposé.

**Coût en disque** : deux flux Annex-B coexistent (avant et après injection),
soit environ deux fois la taille de la vidéo encodée. Ils sont écrits à côté de
la source, sur le même volume, et effacés que l'opération aboutisse ou non.

### 7.5 Paramètres x265 HDR10

```python
params = [
    "hdr10-opt=1", "repeat-headers=1",
    "colorprim=bt2020", "transfer=smpte2084",
    "colormatrix=bt2020nc", "chromaloc=2",
    "master-display=G(…)B(…)R(…)WP(…)L(…)",   # si disponible
    "max-cll=MaxCLL,MaxFALL",                  # si disponible
]
```

---

## 8. Logique métier — `core/decision.py`

### 8.1 Décision encodage vidéo

| Cas | Condition | Action |
|---|---|---|
| **CAS 1 bis** | débit vidéo **inconnu** (0 : fichier en cours d'écriture, flux sans durée) | Réencodage au débit cible, raison « Débit inconnu » (v0.8.9.113, CR-19 — l'analyse posait 9 999 999 b/s, qui restait sous une cible 4K et devenait la cible d'un codec à convertir) |
| **CAS 1** | bitrate source > seuil cible + 10 % (`TOLERANCE_DEBIT_PCT`) | Réencodage HEVC (ou H264 si cible < 1080p) au bitrate cible |
| **CAS 2** | bitrate OK mais résolution trop grande | Redimensionnement HEVC, bitrate original |
| **CAS 3** | bitrate OK, résolution OK, **codec hors `CODECS_LISIBLES`** | Réencodage, bitrate conservé — H264 sous 1080p, HEVC au-dessus |
| **ENCODE_DV** | un des trois cas ci-dessus, profil en `dv`, et RPU réinjectable (§ 7.4) | Réencodage au débit cible, RPU sorti puis remis |
| **STRIP_DV** | aucun des cas ci-dessus, mais RPU retirable (DV 8.1 ou 7) et profil en `hdr10` | Retrait du RPU par remux, sans réencodage (§ 7.3) |
| **SKIP** | bitrate OK, résolution OK, codec H264 ou HEVC | Aucun traitement |

**Le CAS 1 tolère ±10 % autour de la cible** (v0.8.9.55). La cible est une
moyenne visée : en VBR avec 50 % de marge (§ 12.1), une sortie réussie la
dépasse de quelques pourcents. Sans tolérance, une sortie à 2 100k pour
2 000k visés repartait en CAS 1 au scan suivant, pour 5 % de gain et une
génération de perte. Seul le côté haut joue : une source sous la cible n'est
jamais réencodée pour son débit. Le SKIP d'une source dans la tolérance le dit
(« Débit dans la cible ±10 % »).

**Le CAS 3 ne regarde plus la résolution.** `CODECS_LISIBLES` — `h264` et
`hevc` — énumère ce qu'une chaîne de lecture grand public prend sans
transcodage. Tout le reste (VP9, AV1, VC-1, MPEG-2, DivX, codec inconnu) est
réencodé **quelle que soit sa résolution** : un fichier illisible chez le
destinataire ne devient pas lisible parce que son débit est raisonnable. La
règle ne se déclenchait auparavant qu'en dessous de 1080p, et un WebM VP9 en
1080p ou en 4K ressortait donc en `← SKIP`.

L'AV1 y figure comme **source à convertir**, jamais comme cible implicite : son
décodage matériel n'existe que sur les modèles récents.

**Le débit comparé est celui de la vidéo seule.** Un profil fixe un débit
vidéo cible, et c'est un débit vidéo que reçoit l'encodeur (`-b:v`) : les
deux termes de la comparaison doivent porter sur la même chose. Le débit du
conteneur inclut l'audio et les sous-titres, et l'utiliser fait basculer en
réencodage des fichiers dont la vidéo tient largement sous le seuil —
d'autant plus que les pistes sont grosses. Mesuré sur un film porteur d'un
TrueHD : 9 611 kbps de conteneur pour **5 364 kbps de vidéo**, soit 44 %
d'écart. Voir `_video_bitrate` (§ 15.1).

Le seuil bitrate est calculé sur la **résolution cible** (après `keep_4k`), pas sur la
résolution source. Les seuils de rattachement au bucket 1080p sont paramétrables via
`[decision] near_1080p_min_width / near_1080p_min_height` : une source 1920×822 tombe
en bucket 1080p bien qu'elle soit techniquement sous-1080p.

Une source est **4K** dès qu'elle atteint 3200 px de large ou 1700 px de haut
(`VideoInfo.is_4k`, les seuils du « presque 1080p » à l'échelle) : un scope recadré
en 3832×1600 n'a ni 3840 de large ni 2160 de haut, et passait pour un 1080p gardé
à sa définition. Sans `keep_4k`, il est rabattu en 1920×1080 comme toute 4K.

**Pixels carrés** : le filtre `scale=W:H:force_original_aspect_ratio=decrease:force_divisible_by=2` est suivi de `setsar=1`. Sans lui, `scale` rattrape l'arrondi par un SAR (3832×1600 → 1920×802 en 192079:192000 ; 1918×802, étiré à 1920, en 959:960) et Jellyfin transcode une vidéo qu'il croit anamorphique. Le filtre n'est posé que si la source dépasse la cible en largeur ou en hauteur : une source qui y tient garde sa définition (1918×802 était étiré en 1920×802). Seule exception, une dimension impaire, que le 4:2:0 refuse : `scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1` lui retire un pixel.

**Source anamorphique** (v0.8.9.113, CR-14) — un DVD (720×480 en 8:9 ou 32:27, 720×576 en 16:15 ou 64:45), la TNT SD, le HDV 1440×1080 tiennent dans la cible et gardaient leur SAR : Jellyfin les transcodait. L'analyse lit `sample_aspect_ratio` (`VideoInfo.sar`, `pixels_non_carres`, `largeur_affichee`) ; une source non carrée passe d'abord par `scale=trunc(iw*sar/2)*2:trunc(ih/2)*2,setsar=1` (en largeur, rien n'est perdu en hauteur), puis par la boîte de la cible si sa largeur affichée la dépasse. Mesuré : 720×480 en 32:27 → 852×480 en 1:1, rapport 1,775 pour 1,778.

**Désentrelacement** (v0.8.9.96, IE-122) : `VideoInfo.field_order` (lu au
scan) en `tt`, `bb`, `tb` ou `bt` fait `entrelace` ; `FileDecision.desentrelace`
le retient quand l'image est recalculée (encodage HEVC, H264 ou AV1, pas une
copie Dolby Vision, ni SKIP, ni retrait du RPU, ni `ENCODE_DV`). `build_command`
pose alors `FILTRE_DESENTRELACEMENT` =
`bwdif=mode=send_frame:parity=auto:deint=interlaced` **avant** `scale` : une
image par image (cadence de la source, même débit cible), et seules les images
que le flux marque entrelacées sont traitées. Arbitrage de l'utilisateur : les
**marqueurs** seulement, sans sondage `idet` — une source qui se dit
progressive n'est pas touchée, même mal marquée (mesuré : un `.ts` France 2
déclaré progressif, entrelacé par passages). Avec `-hwaccel cuda`, les images
décodées redescendent en mémoire système : bwdif (processeur) s'applique comme
`scale`. Affiché dans l'assistant et l'aperçu (« désentrelacé »). Mesuré sur le
DVD d'essai (`tt`, NVENC H.264 3 Mb/s) : `idet` image par image, 686 images
entrelacées sur 899 sans le filtre, 1 avec ; sur une scène sombre, la détection
« multi » d'`idet` en compte encore 322, artefact de l'outil (les images sont
indécises, il reporte son verdict précédent).

**Force SKIP → encode (browser)** : un fichier SKIP sélectionné manuellement pour le run
est forcé en `ENCODE_HEVC` (ou `ENCODE_H264` si < 1080p) au débit source, sans gonflement.

### 8.2 Bitrates vidéo cibles par résolution

| Résolution | Valeurs disponibles |
|---|---|
| **720p** | 1500, 2000k |
| **1080p** | 2000, 2200, 2500, 3000, 3500, 5000k |
| **4K** | 3000, 3500, 5000, 8000, 12000k |

### 8.3 Actions vidéo

| Enum | Description |
|---|---|
| `ENCODE_HEVC` | Réencodage HEVC (CAS 1 ou CAS 2 sur source ≥ 1080p) |
| `ENCODE_H264` | Réencodage H264 (CAS 3, cible < 1080p, ou forçage manuel) |
| `ENCODE_AV1` | AV1 — **manuel uniquement** (très gourmand CPU/GPU RTX30+) |
| `ENCODE_DV` | Réencodage HEVC préservant le Dolby Vision — RPU extrait puis réinjecté (§ 7.4) |
| `STRIP_DV` | Retrait du RPU Dolby Vision par remux — aucune image recalculée |
| `SKIP` | Aucun traitement |

### 8.4 Gestion Dolby Vision

| Option profil | DV Action | Comportement |
|---|---|---|
| `"hdr10"` | `DVAction.HDR10` | DV → HDR10 (suppression RPU, réencodage HEVC) |
| `"dv"` | `DVAction.DV` | DV → DV (copy du flux vidéo, pas de réencodage) |
| `"sdr"` | `DVAction.SDR` | DV → SDR (tone map P5, CPU, lent) |
| Aucun DV | `DVAction.NONE` | Sans effet |

**Le profil garde la main sur le réencodage.** Le retrait du RPU seul
(`VideoAction.STRIP_DV`, § 7.3) n'est proposé que lorsque le profil ne demande
*aucun* réencodage — débit sous le seuil, résolution dans les clous, codec
standard. Dès qu'un des cas 1 à 3 s'applique, c'est l'encodage qui l'emporte :
il supprime le RPU de lui-même, et stripper d'abord réécrirait le film pour
rien. Une source 8.1 ou 7 qui n'a rien à réencoder sort donc en
`<nom>.hdr10-iris.mkv` ou `.mp4` selon le conteneur retenu (§ 7.3), toutes
pistes conservées.

**Mode HDR10 quality (`hdr10_quality = "quality"`)** — activé par
`cinema_4k_quality`. Utilise `libx265` CPU + `-x265-params` avec `master-display`
et `max-cll`, pour une sortie HDR10 aux métadonnées statiques correctes.

Ces valeurs sont lues **dans les SEI du flux, par ffprobe**
(`scanner._hdr10_metadata`), et non extraites du RPU Dolby Vision : c'est là
qu'un lecteur les cherche, et cela vaut pour toute source HDR, avec ou sans
Dolby Vision. `dovi_tool` n'est plus requis pour ce mode.

Un `max_content`/`max_average` à `0,0` signifie « non mesuré » : rien n'est
injecté plutôt que d'affirmer un pic lumineux nul. Une lecture qui échoue fait
retomber le mode sur un encodage sans métadonnées fines, jamais sur une erreur.

⚠ **Coût réel** : `libx265` mesuré à 0,78 image/s sur du 4K, soit de l'ordre de
70 heures pour un long métrage. Le mode reste réservé au 1080p en pratique.

**Pipeline tone mapping P5 (SDR) :**

```
zscale=t=linear:npl=100,
format=gbrpf32le,
zscale=p=bt709,
tonemap=tonemap=hable:desat=0,
zscale=t=bt709:m=bt709:r=tv,
format=yuv420p
```

Algorithme `hable`, exécuté CPU, impact performance significatif.

### 8.5 Décision encodage audio

**Sélection des pistes :**

```
Pour chaque piste audio (sauf sélection manuelle TUI, qui fait foi) :
  0. Paire sans perte + cœur (même PID) → une seule des deux (voir ci-dessous)
  1. Index 0                     → toujours conservée (langue originale)
  2. Langue inconnue (vide, und) → conservée (v0.8.9.93)
  3. Langue dans audio_languages → conservée
  4. Sinon                       → exclue
```

**TrueHD et cœur AC-3** (v0.8.9.93, IE-119) — un Blu-ray porte la TrueHD et sa
compatibilité AC-3 dans un même flux de transport, que ffprobe montre en deux
pistes de même PID (`AudioTrack.pid`, lu dans `id`). `decision._paires_coeur`
les apparie (une piste sans perte, une qui ne l'est pas). `preserve_hd_audio =
true` : la TrueHD est gardée, le cœur exclu. Sinon : la TrueHD est exclue et le
cœur suit les règles ordinaires (recopié s'il est compatible). Si la TrueHD est
la piste 0, son cœur hérite du rôle de piste originale (`locked`, ⚑ dans
l'écran Pistes).

**Transcodage par piste conservée :**

```
1. Codec lossless (TrueHD / DTS-HD MA / MLP) ?
     preserve_hd_audio = true  → copy
     preserve_hd_audio = false → appliquer règle canal
2. Codec compatible (AAC / AC3 / EAC3) ET audio_copy_compatible = true ?
     → copy
3. Sinon → transcoder selon règle canal
```

**Codec et bitrate de sortie par configuration de canaux :**

| Canaux source | Codec sortie | Paramètre bitrate |
|---|---|---|
| Mono (1.0) | AAC | 64k (fixe) |
| Stéréo (2.0) | AAC | `audio_stereo_kbps` |
| Surround 5.1 | AC3 | `audio_surround_kbps` |
| Surround 7.1 | AC3 | `audio_surround_7_1_kbps`, replié en 5.1 |
| TrueHD / DTS-HD MA | copy ou règle surround | selon `preserve_hd_audio` |

**Transcodage HD au débit de la source — `audio_hd_codec`**

Le forfait par canaux convient à une piste déjà compressée ; il fait perdre
inutilement sur une source HD. `audio_hd_codec = "ac3"` ou `"eac3"` transcode
les pistes **TrueHD et DTS, toutes variantes**, au **débit présent dans la
piste**, plafonné à ce que l'encodeur sait réellement produire :

| Codec | Plafond mesuré | Comportement au-delà |
|---|---|---|
| `ac3` | **640 000 bps** | ramené en silence par l'encodeur |
| `eac3` | **6 144 000 bps** | commande refusée par ffmpeg |

Le débit de la source est lu dans cet ordre : `bit_rate` du flux, puis le tag
Matroska `BPS`, puis `NUMBER_OF_BYTES ÷ DURATION`. Un flux TrueHD ou DTS-HD MA
n'annonce **jamais** de `bit_rate` — sans les tags de statistiques posés par
mkvmerge, la piste retombe sur le forfait du profil plutôt que sur une valeur
inventée.

`preserve_hd_audio` garde la priorité : copier sans perte prime sur
transcoder au débit source.

**Repli des canaux.** Les encodeurs `ac3` et `eac3` s'arrêtent au 5.1. ffmpeg
replie une source 7.1 de lui-même — vérifié, sortie identique à l'octet près
avec ou sans `-ac` — mais la commande le pose explicitement pour que ce qui
s'affiche à l'écran d'encodage corresponde à ce qui sort, et la décision
annonce « → eac3 5.1 » plutôt que de laisser croire à du 7.1 préservé.

**Titre de la piste.** Un titre de piste survit au transcodage et annonce
alors un codec absent du fichier. `AudioDecision.output_title` rend le titre
corrigé, ou `None` quand il n'y a rien à corriger ; l'encodeur le pose en
`-metadata:s:a:N title=…`. La règle : remplacer le jeton de codec, suivre la
disposition si elle change, retirer la mention `Atmos` — perdue de toute façon
— et **ne rien toucher à un titre muet sur le format** (« English »), qui n'a
jamais menti. Une piste copiée n'est jamais retitrée.

**Détection des variantes DTS.** ffprobe nomme `dts` toutes les déclinaisons et
met la famille dans `profile` : « DTS », « DTS-ES », « DTS-HD HR »,
« DTS-HD MA ». `AudioTrack.profile` est donc lu au scan — sans lui, un DTS-HD MA
passait pour un DTS ordinaire et échappait à `preserve_hd_audio`. Est sans perte
tout profil qui **commence** par « DTS-HD MA » (`_PREFIXE_DTS_SANS_PERTE`,
v0.8.9.112, CR-09) : ffmpeg écrit aussi « DTS-HD MA + DTS:X » et « DTS-HD MA +
DTS:X IMAX », et ce dernier, comparé à l'égalité, était transcodé malgré
`preserve_hd_audio`, sortie en MP4.

### 8.6 Sous-titres et conteneur de sortie

- PGS / DVD / DVB (image) → conteneur MKV, `-c:s copy` (`dvb_subtitle`
  depuis la v0.8.9.93)
- Télétexte (`dvb_teletext`) → **toujours écarté** (`SubtitleTrack.portable`) :
  ni MP4 ni MKV ne le portent. `decide_subtitles` ne le retient jamais,
  `kept_subtitles` l'écarte même coché à la main, l'écran Pistes refuse de le
  cocher (« télétexte — non transportable »)
- `subtitle_languages` garde aussi une piste **sans langue** (v0.8.9.93)
- SRT (texte) → MP4 possible, `-c:s mov_text`
- ASS / SSA → MKV : le style ne survit pas à `mov_text`
- Sélection par piste depuis `TracksScreen` (par défaut : toutes conservées)
- **PGS doublé** : sans sélection manuelle, un sous-titre image est écarté
  quand un sous-titre texte de même langue **et de même nature** est retenu
  (`decision._pgs_doubles`) : un SRT forcé double un PGS forcé, un SRT complet
  un PGS complet, jamais l'un l'autre. Jellyfin incruste un sous-titre image,
  donc transcode ; le SRT dit la même chose. Seul de sa langue et de sa
  nature, le PGS reste. Sans langue déclarée, un PGS n'est jamais dit doublé.
  Forcé = `disposition.forced` ou « forced » / « forcé » dans le titre
  (`SubtitleTrack.is_forced`).

**La clé `container`** exprime une politique de profil, parce que le choix ne
se déduit pas du seul contenu : certains lecteurs digèrent mal le Matroska.

| Valeur | Effet |
|---|---|
| `auto` | Le contenu décide. MP4 quand tout y tient. |
| `mkv` | Toujours du Matroska, rien n'est écarté. |
| `mp4` | Les sous-titres image sont **écartés**, et `sous_titres_ecartes` les liste pour que la décision les affiche. |

**Deux garde-fous, parce qu'une politique ne vaut pas une perte silencieuse :**

1. Si les sous-titres image sont les **seuls** du fichier, c'est le conteneur
   qui cède — mieux vaut un MKV qu'une sortie sans sous-titres.
2. Une piste audio sans perte **conservée** ramène toujours au MKV. On écarte
   un sous-titre doublé par un SubRip ; on n'échange pas contre un format une
   piste que l'utilisateur a demandé de garder.

`subtitles_finales` donne ce qui atterrit réellement : l'encodeur mappe cette
liste au lieu de `0:s?`, et le dry-run affiche `MP4 −3 st` en style « modifié ».

**Retrait de Dolby Vision en MP4.** mkvmerge ne sait écrire que du Matroska :
quand la décision demande du MP4, ffmpeg produit le fichier en une passe depuis
la source, avec `dovi.build_strip_mp4()` (§ 7.3). Il ne lit plus le flux brut
sans horodatage, et le correctif de cadence (`-r`) et de DTS négatifs
(`-avoid_negative_ts`) que ce flux exigeait n'a plus d'objet.

**Le HEVC en MP4 est étiqueté `hvc1`.** ffmpeg écrit `hev1` par défaut
(paramètres de décodage répétés dans le flux) ; les lecteurs Apple exigent
`hvc1` (paramètres dans l'en-tête). `build_command` ajoute `-tag:v hvc1` à
toute sortie MP4 dont la vidéo est du HEVC — encodeur `hevc_*` ou `libx265`,
ou copie d'une source HEVC (`_sortie_hevc`) — et `build_strip_mp4` toujours.
Le LG G3 lit les deux étiquettes en lecture directe *(observé, IE-74)*.

**Conteneur de sortie** — `output_container` suit les pistes réellement conservées :
écarter les sous-titres image libère le MP4 ; `mov_text` n'est jamais proposé en
Matroska. Une piste externe n'impose le `.mkv` que si son codec l'exige
(`_needs_mkv_codec` : ASS, PGS…) : un `.srt` greffé sur un encodage tient en MP4.
Un **mux** (SKIP + pistes externes) s'écrit toujours en `.mux-iris.mkv`, le seul
format de mkvmerge : `output_path` rend ce nom, celui de
`muxer.mux_output_path` (v0.8.9.97, CR-15).

**Le flux `bin_data` d'un MP4 est sa piste de chapitres.** `ffprobe` rapporte,
sur une sortie MP4 issue d'une source chapitrée, un flux de plus que ceux
demandés : `bin_data`, `codec_tag_string=text`, `handler_name=SubtitleHandler`,
une trame par chapitre. Ce n'est pas une piste parasite — le MP4 ne sait porter
les chapitres que sous la forme d'une piste texte QuickTime, et c'est ainsi que
les lecteurs les retrouvent. Vérifié : `-map_chapters -1` le fait disparaître,
et les chapitres avec lui. Le Matroska, qui a un conteneur de chapitres propre,
n'affiche rien de tel.

**Un long silence dans un sous-titre texte en MP4** (v0.8.9.62,
`core/sous_titres.py`). Le muxeur MP4 de ffmpeg (8.1.2, 8.1.3) écrase les temps
d'une piste `mov_text` après un silence de plus de 2³¹ µs (2 147,48 s), avant
la première réplique ou entre deux : la suivante et toutes les autres se collent
au début, code retour nul. Une piste forcée y tombe presque toujours. Avant une
sortie MP4 qui garde du texte (`pistes_a_porter`), RunScreen extrait ces pistes
en SRT, une lecture de la source (`_porter_sous_titres`). Si l'une a un silence
de plus de `SEUIL_S` (1 800 s), une réplique `BOUCHE_TROU` (espace insécable,
1 ms ; une espace simple est retirée par le décodeur) coupe chaque tranche, et
toutes vont dans un Matroska porteur (`build_porteur`, langue, titre et
drapeaux reportés ; ffmpeg et non mkvmerge, le MKV n'ayant pas le défaut).
`build_command`, `build_strip_mp4` et `build_dv_mp4_remux` y lisent alors les
sous-titres à la place de la source. Sans long silence, pas de porteur.

**Les sous-titres greffés y passent aussi** (v0.8.9.104, CR-34) : un `.srt` forcé
trouvé sur OpenSubtitles, première réplique à 36 min, sortait avec ses répliques à
0 s et 2 s. `greffes_a_porter` les liste dans l'ordre de sortie — greffes directes
(donneur, index traduit, jeu de caractères, décalage) ou celles d'un mux préalable
(lues dans l'intermédiaire, à la suite des sous-titres de la source) ;
`build_extraction_greffe` les extrait une à une, décalage appliqué comme à
l'encodage (`-itsoffset`, `-ss` pour un négatif). Avec un porteur, `build_command`
les mappe depuis lui, jamais depuis leur donneur. Une greffe **étirée** n'est jamais
extraite de son donneur — ffmpeg n'y appliquerait que le décalage, une dérive de 4 %
— : le chemin principal l'a déjà absorbée par un mux préalable, et
`greffes_a_porter` refuse celle qui arriverait autrement. Le réencodage DV vers MP4
lit ses greffes dans le Matroska que mkvmerge vient de recomposer
(`greffes_a_porter(dec, recompose=mkv)`), à la suite des sous-titres gardés de la
source : décalage et étirement y sont déjà appliqués. Le retrait DV vers MP4 qui
porte des greffes recompose lui aussi un Matroska et les y lit (v0.8.9.107, CR-55,
§ 7.3) ; sans greffe, sa passe unique ne lit que la source.

### 8.7 Nommage des sorties

Depuis la v0.8.8.11, le nom suit l'usage des noms de release : les marques
sont séparées par des **points**, et toute sortie finit par **`-iris`**
(`.IRIS` jusqu'à la v0.8.9.43), précédée de la caractéristique qui dit ce que
le traitement a fait. Le tiret détache la marque comme le groupe d'une
release, dont elle prend la place (voir plus bas).

| Opération | Sortie |
|---|---|
| Réencodage HEVC | `nom.hevc-iris.mp4` / `.mkv` |
| Réencodage H264 | `nom.h264-iris.mp4` / `.mkv` |
| Réencodage AV1 | `nom.av1-iris.mp4` / `.mkv` |
| Dolby Vision conservé (copie ou RPU réinjecté) | `nom.dv-iris.mkv` |
| Retrait du RPU (remux HDR10) | `nom.hdr10-iris.mkv` |
| Greffe de pistes (mkvmerge) | `nom.mux-iris.mkv` |
| Jonction de parties (§ 9bis) | `nom.join-iris.mkv` |
| Extrait de contrôle (dossier temporaire) | `nom_[extrait].mkv` |

`SUFFIX_BY_ACTION` porte les suffixes d'encodage, `MUX_SUFFIX` et
`JOIN_SUFFIX` les deux autres ; tous dérivent de `scanner.MARQUE_IRIS`. Depuis
la v0.8.8.14, la caractéristique ajoutée s'écrit **en minuscules**, et
depuis la v0.8.9.44 la marque aussi. Les marques de la source gardent leur
casse : un `DV` réécrit en `HDR10` reste une marque de release, pas un
suffixe. La casse de `-iris` compte : c'est ce qui distingue une sortie d'un
titre qui finirait par `-Iris`. Celle de `mux` / `join` ne compte pas, pour
que les sorties écrites en capitales avant la v0.8.8.14 restent des entrées.

**L'ancienne marque `.IRIS` n'est plus reconnue** (choix de l'utilisateur,
v0.8.9.44) : une sortie qui la porte redevient une source ordinaire, et un
réencodage la garde dans le nom comme n'importe quel mot —
`Film.1080p.hevc.IRIS` sort `Film.1080p.IRIS.hevc-iris`.

**Le groupe de la release part.** Le dernier terme d'un nom, détaché par un
tiret (`Film.1080p.x265-GROUPE`, `Film 1080p - GROUPE`), signe la source et
non le fichier produit : `scanner.stem_sans_groupe()` le retire avant toute
autre réécriture, juste après la marque `-iris` d'une sortie réencodée — sans
quoi `-iris` passerait pour un groupe. Trois gardes : le terme est un mot
seul (sans espace, point ni crochet) ; il n'est ni une marque ni un morceau
de marque (`Film.1080p-x265`, `Film.DTS-HD`, `Film.WEB-DL` le gardent) ; le
reste du nom porte au moins une marque de `scanner.JETONS_RELEASE`
(définition, codec, HDR, audio, langue, source) — sans elle, `Titre-Film` ou
`Titre - Sous-titre` sont des titres. Le retrait vaut pour les trois
sorties : encodage (`FileDecision.output_path`), greffe
(`muxer.mux_output_path`) et jonction (`joiner.join_output_path`).

**Une caractéristique que le nom annonce déjà n'est pas répétée**
(`decision.suffixe_sans_redite()`) : `Film.2160p.DV` dont le Dolby Vision est
conservé sort `Film.2160p.DV-iris`, pas `…DV.dv-iris` ; ramené en HDR10, son
`DV` devient `HDR10` (voir plus bas) et le suffixe se réduit à `-iris`. Un nom
muet la reçoit : `Film.2160p` → `Film.2160p.hdr10-iris`. `HDR10+` vaut
annonce du HDR10. La caractéristique reste quand la retirer ferait passer une
sortie d'encodage pour un collage ou une greffe (`Film.DV.join` → `.dv-iris`).

**La marque se remplace, elle ne s'empile pas.** Réencoder un
`Film.av1-iris.mkv` en HEVC donne `Film.hevc-iris.mkv`, pas
`Film.av1-iris.hevc-iris.mkv`. `scanner.stem_sans_suffixe_produit()` retire la
marque `-iris` finale (et son compteur de collision) ; la caractéristique qui
la précède est une marque comme une autre, que les réécritures ci-dessous
effacent si elle est devenue fausse — `AV1` part avec les marques de codec.
`mux` et `join` restent : ils disent d'où vient le fichier
(`Film.join-iris` → `Film.join.hevc-iris`).

Les noms de l'ancien schéma (`_[hevc]`, `_[av1]`…) ne sont plus reconnus comme
sorties : ils redeviennent des sources. Leur `[hevc]` reste une marque de
codec, qu'un réencodage efface comme un `x265`.

**La marque de résolution suit la définition de sortie.** Un `Film.2160p.mkv`
rabattu en 1080p sortait `Film.2160p.hevc-iris.mkv` : le nom promettait une
définition que le fichier n'a plus, et deux fichiers de définitions
différentes se lisaient pareil dans une médiathèque.
`scanner.stem_resolution_ramenee()` remplace la marque de la source par celle
de la sortie — `2160p`, `4K`, `4KLight` (avec ou sans séparateur), `UHD` →
`1080p` — prise comme mot entier : le `4K` de `H4K` et le `2160` de
`3840x2160` ne sont pas des marques de release. Rien n'est ajouté à un nom
qui n'en porte pas, et un nom qui en porte deux à la suite n'en garde qu'une
(`2160p.UHD.BluRay` → `1080p.BluRay`).

La substitution ne joue que sur le **nom du fichier produit**, et seulement
quand la définition baisse vraiment : `keep_4k` la laisse tranquille, et une
vidéo recopiée (DV conservé, § 6) sort à la définition d'origine quoi
qu'annoncent `target_width/height` — annoncer 1080p là serait exactement le
mensonge que ce renommage supprime. La source n'est jamais renommée.

**La marque de codec s'efface derrière le suffixe.** Même raison, autre
promesse du nom : un `Film.1080p.x264` réencodé en HEVC sortait
`Film.1080p.x264.hevc-iris`, deux codecs annoncés dont un faux.
`scanner.stem_sans_marque_codec()` retire du nom écrit les marques `x264`,
`x265`, `H264`, `H265` (avec ou sans point), `HEVC`, `AV1` et `VP9` — prises
comme mot entier, avec leur paire de crochets ou de parenthèses s'ils en ont
une, la ponctuation du nom se recollant derrière (`Film.1080p.x265-GROUP` →
`Film.1080p-GROUP`). Une marque qui tombe juste part aussi : à côté de
`.hevc-iris`, un `x265` répète la même chose deux fois.

Le retrait ne joue que pour les actions de `ACTIONS_CODEC_NOMME` —
`ENCODE_HEVC`, `ENCODE_H264`, `ENCODE_AV1` — et hors vidéo recopiée : un
remux HDR10 (`.hdr10-iris`, aucun réencodage) et une vidéo copiée pour conserver
le Dolby Vision (`.dv-iris`) sortent dans le codec de la source, que le suffixe
ne nomme pas. Un nom fait des seules marques est rendu tel quel.

**La marque HDR suit le sort du Dolby Vision.** `dv_action` décide seul :
ramené en HDR10, `DV`, `DoVi`, `Dolby Vision`, `HDR` et `HDR10` deviennent
`HDR10`, seule la première étant réécrite et les suivantes retirées
(`Film.DV.HDR10` → `Film.HDR10`, `Film 4K DV 2160p` → `Film 1080p DV`) ; ramené en SDR, elles partent toutes,
`HDR10+` et la profondeur (`10bit`, `10bits`, `10 bits`) comprises, et rien
ne les remplace — une sortie SDR ne s'annonce pas, et le tone mapping finit
sur `format=yuv420p` : le fichier ressort en 8 bits. En sortie HDR10 la
profondeur reste vraie (`yuv420p10le`) et n'est pas touchée.
`HDR10+` survit au passage en HDR10 : le retrait du RPU le laisse intact, et
l'écraser effacerait une métadonnée présente. Ses graphies `HDR10Plus` et
`HDR10P` valent `HDR10+` partout (`decision.JETONS_HDR_PLUS`). DV conservé (§ 6) : rien ne
bouge.

**La marque audio dit le format écrit.** La famille de la piste transcodée —
`TrueHD`, `True-HD`, `MLP`, `DTS-HD MA`, `DTS-X`, `DTS`, `FLAC`, `LPCM`,
`DD+`… (`JETONS_AUDIO`, mêmes jetons que les titres de pistes, § 8.5) —
devient l'étiquette du codec de sortie, `E-AC3` ou `AC3`. Suivent ce que la
conversion emporte : la disposition si elle se replie (`7.1` → `5.1`) et la
mention `Atmos`, les objets sonores ne survivant pas à une conversion vers
AC3 ou E-AC3. Une famille qu'une autre piste conserve n'est pas touchée — un
AC3 recopié à côté d'un TrueHD transcodé garde sa marque. Une piste **écartée**
dont plus aucune piste gardée ne porte la famille la cède au format de la première
piste gardée (v0.8.9.112, CR-18) : une TrueHD Atmos écartée au profit de son cœur
AC-3 laissait `TrueHD.7.1.Atmos` sur un fichier en AC-3 5.1.

**Marque collée à sa disposition** (v0.8.9.112, CR-10) — `DTS5.1`, `TrueHD7.1`,
`DDP5.1` : une marque suivie sans séparateur d'une disposition (`[1-9].[0-9]`)
reste une marque. Remplacée, elle reçoit un point (`TrueHD7.1` → `E-AC3.7.1`, puis
`E-AC3.5.1` si la disposition se replie) ; retirée, elle laisse son séparateur
(`Film.DTS5.1` → `Film.5.1`).

**SKIP est écarté d'un bloc.** La seule sortie qu'il produit est une greffe
de pistes (`.mux-iris`, § 10.4), que mkvmerge recopie sans rien convertir : le
fichier y garde jusqu'à son RPU quand `dovi_tool` manque et que la décision
retombe sur SKIP en gardant son `dv_action`.

Les quatre réécritures se composent dans `FileDecision._stem_a_jour()` :
`Film.2160p.DV.HDR10.x265.TrueHD.7.1-GROUP` ressort
`Film.1080p.HDR10.E-AC3.5.1.hevc-iris`. Elles s'appuient sur une seule
machinerie dans le scanner — `stem_marques_retirees()` et
`stem_marques_remplacees()` — qui porte les précautions une fois pour
toutes : jeton le plus long d'abord (sans quoi `DTS` l'emporterait sur
`DTS-HD MA` en laissant un `.MA` orphelin), séparateurs interchangeables
(`DTS-HD.MA`, `DTS-HD-MA`, `DTS HD MA`), mot entier, `HDR10+` qui ne perd pas
son `HDR10`, paire de crochets emportée avec la marque, et nom qui ne finit
jamais sur un séparateur nu.

**Deux collisions, une numérotation.** Remplacer fait apparaître ce que
l'empilement masquait : la cible peut être la source elle-même
(`Film.hevc-iris.mkv` réencodé en HEVC — le geste courant, rebaisser un débit), ou
un fichier déjà présent (`Film.av1-iris.mkv` réencodé en HEVC quand un
`Film.hevc-iris.mkv` existe). Dans les deux cas, `decision.resoudre_sorties()`
numérote : `Film.hevc-iris(2).mkv`. Rien n'est écrasé, rien n'est refusé. Le
compteur repart avec la marque au passage suivant — `Film.hevc-iris(2)` réencodé
redonne `Film.hevc-iris`, sans quoi l'empilement reviendrait par cette porte.

**Le nom est figé une fois.** `resoudre_sorties()` est appelé à la construction
de `RunScreen` — dernier moment avant l'écriture — et pose `output_override` sur
chaque décision du lot ; les collisions internes au lot se résolvent dans la
même passe. L'appel est idempotent. `FileDecision.output_path` ne consulte
jamais le disque de lui-même : l'écran d'encodage le relit *après* coup pour
vérifier la sortie et pour effacer un fichier partiel après un abandon, et une
valeur qui deviendrait `(3)` une fois `(2)` écrit ferait effacer un fichier
étranger. L'assistant, qui annonce le nom de sortie à trois étapes, appelle la
même fonction pour ne pas annoncer autre chose que ce qui sera écrit.

Le garde-fou « chemin de sortie identique à la source » (§ 12.4) reste en place :
la numérotation le rend inatteignable sur ce chemin, il couvre toujours le cas
d'un suffixe vide avec conteneur identique.

---

## 9. Pistes externes — `core/muxer.py`

Greffer une piste audio ou un sous-titre venu d'un autre fichier dans le fichier
courant, **sans réencoder la vidéo**, chaque piste portant son propre décalage.

### 9.1 Décisions structurantes

| Sujet | Décision | Conséquence |
|---|---|---|
| **Portée** | Un fichier à la fois | Pas de batch. L'état vit dans le `FileDecision` en mémoire, de l'écran de recalage au mux. |
| **Exécution** | Opération immédiate depuis l'écran des pistes | Chemin distinct de la file d'encodage, progression propre. |
| **Multiplicité** | N pistes externes, audio et sous-titres mélangés | Chaque piste porte son décalage, réglé indépendamment. |
| **Conteneur** | Sortie MKV obligatoire | Le MP4 ne porte ni ASS ni la plupart des audio HD. |
| **Hors périmètre** | Montages divergents (version longue, censure) | Un décalage unique ne peut pas les recaler. |

### 9.2 Modèle de données

```python
class TrackKind(Enum):
    AUDIO    = auto()
    SUBTITLE = auto()

class SyncOrigin(Enum):
    NONE     = auto()   # pas encore recalé
    MEASURED = auto()   # corrélation automatique
    MANUAL   = auto()   # ajusté à la main
    COPIED   = auto()   # repris d'une autre piste externe

@dataclass
class ExternalTrack:
    source_path:  Path                   # .mkv, .ac3, .srt, .ass…
    source_tid:   int                    # ID mkvmerge DANS ce fichier
    kind:         TrackKind
    codec:        str                    # affichage seulement
    language:     str                    # obligatoire — sinon « und »
    track_name:   str  = ""              # « VF », « Forcés »…
    delay_ms:     int  = 0
    stretch:      tuple[int, int] | None = None   # (24000, 25025)
    is_default:   bool = False
    is_forced:    bool = False
    sync_origin:  SyncOrigin = SyncOrigin.NONE
    copied_from:  int | None = None      # index dans external_tracks
```

`FileDecision` porte `external_tracks: list[ExternalTrack]`. Une greffe n'impose
le `.mkv` que si son codec ne tient pas en MP4 (ASS, sous-titre image) ; une piste
audio sans perte greffée ne l'impose qu'avec `preserve_hd_audio`, seul cas où elle
est recopiée (v0.8.9.103, § 12.0).

### 9.3 API du module

| Fonction | Rôle |
|---|---|
| `identify(path)` | Pistes du fichier via `mkvmerge -J` → `list[IdentifiedTrack]`. Mémorisé par (chemin, taille, date) : traduire vingt index ne relançait pas vingt processus |
| `ffmpeg_stream_index(path, tid, kind)` | Traduit un TID mkvmerge en index ffprobe ; `mkvmerge_tid` fait l'inverse. Une piste que mkvmerge ne retrouve pas lève `ErreurAffichable` : deviner 0 greffait une autre piste sous le nom de celle choisie (CR-27) |
| `guess_language(path)` | Déduit une langue du nom de fichier (`film.VF.mka`). Le dernier fragment peut être tout marqueur connu ou un code ISO 639-2 de la table OpenSubtitles (`CODES_ISO`) ; plus à gauche, seuls les marqueurs qui ne sont pas des mots de titre (`FRENCH`, `VFF`, `eng`…) — jamais `de`, `it`, `en`, `es` (CR-26). « VO » ne désigne aucune langue |
| `noms_proposes(langue)` | Noms que le champ Nom du recalage propose, selon la langue **de la piste** : `fre` → VF, VFF, VFQ, VOSTFR, Forcés, Commentaires, SDH ; `eng` → English, Forced, Commentary, SDH ; autre → Forced, SDH. Écrits dans le fichier, ce sont des données : ils ne suivent jamais la langue de l'interface (v0.8.9.70) |
| `build_mux_command(…)` | Arguments mkvmerge complets |
| `build_sample_command(…)` | Extrait de contrôle muxé |
| `sample_windows(duration, has_stretch, …)` | Fenêtres à découper (deux si étirement) |
| `parse_progress(line)` / `parse_error(line)` | Lecture du protocole `--gui-mode` |
| `MuxProcess` | Exécution, progression, erreurs, arrêt |

### 9.4 Commande type

```bash
mkvmerge --gui-mode -o sortie.mkv \
  cible.mkv \
  --sync 0:-2450,24000/25025 --language 0:fre --track-name 0:VF \
  --default-track-flag 0:1 donneur.mka \
  --sync 0:850 --language 0:fre --track-name 0:Francais subs.srt
```

`--gui-mode` n'apparaît pas dans `--help` mais fonctionne : il émet sur stdout
`#GUI#progress N%` et `#GUI#error <message>`. C'est la sortie parsée par le runner.

### 9.5 Pièges traités

Chacun produit un résultat faux **sans erreur visible** — d'où leur coût.

| # | Piège | Traitement |
|---|---|---|
| 1 | **Deux numérotations incompatibles.** `AudioTrack.index` (ffprobe) compte par type ; mkvmerge utilise un ID global. Une piste audio unique est `id=1` chez mkvmerge, `index=0` chez ffprobe. | Tout donneur est identifié par `mkvmerge -J`. Les deux numérotations ne se croisent jamais ; `ffmpeg_stream_index()` fait la traduction explicite. |
| 2 | **Extrait découpé en copie de flux.** Avec `-c copy`, chaque fichier se cale sur son keyframe le plus proche, ce qui **modifie le décalage relatif** et invalide le test. | L'audio de l'extrait est réencodé (60 s, instantané). |
| 3 | **Donneur embarqué en entier** sans `--no-video --no-subtitles`. | Options systématiques dans `build_mux_command()`. |
| 4 | **Premier sous-titre `default` d'office.** mkvmerge le pose sans qu'on le demande : les sous-titres s'affichent chez l'utilisateur. | `--default-track-flag TID:0` émis explicitement quand `is_default` est faux. |
| 4 bis | **Deux pistes par défaut.** Une greffée marquée « par défaut » laissait le drapeau des pistes de la source de même type ; le lecteur prend la première, le choix restait sans effet (CR-25). | `types_par_defaut()` : les pistes de ce type venues de la source reçoivent `--default-track-flag TID:0` (ids par `identify`), sur l'audio produite à part quand c'est elle qui fournit l'audio. Même règle côté ffmpeg (§ 12.0). |
| 4 ter | **Jeu de caractères d'un `.srt`.** Sans BOM, mkvmerge suit celui du système : juste sous un Windows français (mesuré), un `.srt` en cp1252 tronqué à la première lettre accentuée sous Linux (CR-50). | `--sub-charset TID:<jeu>` toujours posé pour un sous-titre texte, jeu lu par `sous_titres.encodage_texte()` (UTF-8, sinon CP1252, sinon ISO-8859-1). |
| 5 | **Une seule piste audio à la fois dans mpv.** `audio-delay` et `sub-delay` sont distincts : un audio + un sous-titre se calibrent ensemble, deux audio demandent deux passes. | L'écran le dit au lieu de laisser croire à un réglage simultané. |
| 6 | **Métadonnées absentes des fichiers externes.** Un `.srt` n'a aucune langue → « und » dans tous les lecteurs. | Champs saisis dans l'écran, jamais déduits silencieusement ; `guess_language()` ne fait que pré-remplir. |
| 7 | **mkvmerge réécrit le conteneur entier.** Pas d'ajout in-place en MKV : 30 Go = copie disque complète, une à trois minutes sur SSD. | Barre de progression réelle. Les deux fichiers coexistent le temps du mux — prévoir l'espace. |
| 8 | **Dolby Vision — les deux chemins sont mesurés, sur des clips courts.** `STRIP_DV` (§ 7.3) : sortie bit à bit identique, HDR10+ conservé, sur un film 4K réel. `ENCODE_DV` (§ 7.4) : chaîne complète vérifiée — RPU réextrait octet pour octet identique après injection, nombre d'images conservé, `DV:P8.1` reconnu par le scanner, débit 6541k → 1992k. Mais sur **48 images de mire synthétique**, faute de source Dolby Vision réelle. | Restent non vérifiés : un film entier avec changements de plans, le rendu sur un téléviseur Dolby Vision, et le profil 7 — éligible par construction, converti en 8.1 au passage, jamais essayé. Le premier encodage réel est à contrôler sur le matériel de lecture. |

### 9.6 Fichier déjà en réencodage

Si le fichier part de toute façon en encodage, mkvmerge ne sert à rien : **ffmpeg absorbe
les pistes externes dans la même passe**, à coût nul et sans fichier intermédiaire.
`build_command()` lit `external_tracks` et émet les entrées supplémentaires avec
`-itsoffset`.

**Limite :** `-itsoffset` ne fait qu'un décalage constant. Une piste demandant un facteur
d'étirement passe obligatoirement par mkvmerge.

### 9.7 Après un mux

Le fichier produit (`nom.mux-iris.mkv`) **devient le fichier de travail** : la décision est
réindexée dessus côté browser, et les sélections de pistes faites sur l'ancien fichier
ne s'appliquent plus.

### 9.8 Sous-titres OpenSubtitles.com — `core/opensubtitles.py`

`O` dans le choix du donneur (`DonorFileScreen`, donc depuis les pistes, le
recalage et l'assistant) ouvre `OpenSubtitlesScreen`. Le `.srt` téléchargé est
rendu au donneur **comme un fichier choisi sur le disque** : pistes, langue,
recalage suivent sans rien savoir de sa provenance.

| Décision | Raison |
|---|---|
| **Deux recherches fusionnées** | Par empreinte (`moviehash`) : sous-titres déposés pour cette release exacte, donc synchronisés — marqués `≡`, classés en tête. Par nom (`meta.parse_title`, plus `season_number`/`episode_number` sur un `SxxEyy`, sinon `year`) : rattrape un fichier réencodé, dont l'empreinte n'est plus celle de sa release. Fusion par `file_id`. Tri : release exacte, puis langue dans l'ordre du profil, puis téléchargements. |
| **Pages lues jusqu'à 5** | L'API rend 50 résultats par page ; la première seule perdait des sous-titres français derrière des anglais plus téléchargés (Film Q : 44 résultats lus sur 72, contre 64 après). Au-delà de 250, la liste ne se lit plus. |
| **Langues du profil** | `subtitle_languages` (ISO 639-2) traduites au format de l'API ; `fre`/`eng` si le profil n'en dit rien. Paramètres triés : l'API redirige une requête qui ne l'est pas. |
| **Dossier temporaire** | `<tmp>/iris_opensubtitles/<stem>.<file_id>.<langue>.srt`, la langue en ISO 639-2 (`dut`, `pol`…). Le fichier ne sert qu'à la greffe : rien ne s'ajoute à la médiathèque, aucun lecteur ne l'affichera en double. La langue en dernier fragment est lue par `muxer.guess_language` ; le code de l'API (`nl`) n'y était reconnu que pour huit langues (CR-51). |
| **Sous-titres en plusieurs CD écartés** | Ils ne se greffent pas sur un fichier unique. |

Empreinte : taille du fichier + somme des mots 64 bits little-endian des 64
premiers et 64 derniers Kio, modulo 2⁶⁴, sur 16 chiffres hexadécimaux ; aucune
sous 128 Kio (algorithme de l'extension Kodi officielle).

Configuration, section `[opensubtitles]` de `config.toml` (non suivi par git) :
`api_key` (clé d'application, opensubtitles.com/consumers — exigée à chaque
appel), `username` et `password` (exigés au téléchargement seulement ; 20 par
jour en compte gratuit). Ils se saisissent dans l'application (§ 14.8,
v0.8.9.37) ; les messages d'erreur y renvoient (`F5`, `K`), plus à
config.toml. Une clé refusée répond **403**, un compte refusé **401**. `User-Agent` : `IRIS Encode v<version>`. Le jeton de
connexion vit le temps de l'écran ; un compte VIP est servi par l'hôte que
`login` annonce (`base_url`).

Les refus se lisent en français, sans trace Python : clé absente ou compte
manquant avant tout appel, 401 (identifiants), 406 (quota du jour, heure de
remise), 429 (`Retry-After`), réseau injoignable. Le quota restant est notifié
après chaque téléchargement.

---

## 9bis. Jonction de parties — `core/joiner.py`

Un film livré en `part1` / `part2` n'est pas encodable tel quel : chaque partie prise
seule produirait sa propre sortie, et le profil déciderait deux fois au lieu d'une. Le
collage recoud les parties en un fichier unique, **avant** toute décision.

Numérotation `9bis` pour ne pas renuméroter les sections suivantes — même convention
que le `1bis` du `GUIDE.md`.

### 9bis.1 Décisions structurantes

| Choix | Raison |
|---|---|
| **mkvmerge en mode `append`** (`fichier1 + fichier2`) | Sans réencodage : il recale les horodatages de chaque partie sur la fin de la précédente. Le démultiplexeur `concat` de ffmpeg exige des paramètres de flux strictement identiques et gère mal les pistes multiples. |
| **Suffixe `.join-iris`, absent de `SUFFIX_BY_ACTION`** | Le fichier collé est une *entrée* de travail, pas une sortie d'encodage : le scan doit continuer à le voir (`ENTREES_IRIS`, § 15.2). L'écarter comme un `.hevc-iris` rendrait le collage inutile. |
| **Contrôle avant lancement** | mkvmerge refuse d'apparier des pistes qui ne se correspondent pas. L'apprendre au bout d'une copie de 30 Go n'est pas une option. |
| **Ordre montré et corrigeable** | Deux parties inversées donnent un fichier de la **bonne durée**, donc faux sans que rien ne le signale. C'est la seule chose que le collage ne peut pas deviner sans risque. |
| **Les parties sont conservées** | Le collage n'efface rien. `Ctrl+D` reste le seul geste qui supprime. |

### 9bis.2 API du module

| Fonction | Rôle |
|---|---|
| `ordre_naturel(parts)` | Tri où les nombres comptent comme des nombres : `part1 < part2 < part10`. Clé faite de tuples homogènes, jamais un `int` face à une `str`. |
| `nom_commun(parts)` | Nom du tout, déduit du préfixe commun, marqueur de numérotation retiré (`part`, `CD`, `pt`, `disque`, `vol`, `tome`…). `Film part1` + `Film part2` → `Film`. |
| `join_output_path(parts)` | `<nom commun>.join-iris.mkv`, dans le dossier des parties. |
| `controler(infos)` | Rend un `Controle(blocages, avertissements)` — voir 9bis.3. |
| `build_join_command(parts, out)` | La commande mkvmerge. Lève `ValueError` sur moins de deux parties, une partie en double, ou une sortie qui écrase une partie. |
| `duree_attendue(infos)` | Somme des durées des parties. |
| `derive_duree(attendue, obtenue)` | L'écart, s'il dépasse le bruit d'arrondi (2 s ou 1 %). |

L'exécution réutilise `muxer.MuxProcess` : mkvmerge écrit la même progression
`#GUI#progress` qu'au mux, il n'y avait pas de second runner à écrire.

### 9bis.3 Deux niveaux de refus

mkvmerge lui-même en a deux, et les confondre serait soit refuser un collage possible,
soit laisser produire un fichier amputé sans le dire (même leçon qu'IE-52) :

- **Blocages** — le collage est refusé : codec vidéo différent, définition différente,
  codec ou nombre de canaux différent sur une piste audio appariée.
- **Avertissements** — le collage est possible, avec une perte annoncée : une partie
  porte plus (ou moins) de pistes audio ou de sous-titres que la référence, et mkvmerge
  n'appariera que les rangs communs.

**La première partie est la référence** : c'est elle qui donne au fichier produit ses
codecs, sa définition et son jeu de pistes.

### 9bis.4 Commande type

```
mkvmerge --gui-mode -o "D:/films/Film.join-iris.mkv"
         "D:/films/Film part1.mkv" + "D:/films/Film part2.mkv"
```

Le `+` est ce qui distingue un collage d'un mux : sans lui, mkvmerge **superposerait**
les pistes au lieu de les enchaîner.

### 9bis.5 Après le collage

La durée du fichier produit est relue et comparée à la somme des parties. Un mkvmerge
tué en cours de route laisse un fichier lisible et court : sans ce contrôle, il passerait
pour un collage réussi — le piège d'IE-41, où un ffmpeg mort passait pour un film court.
Un écart au-delà de 2 s ou 1 % est annoncé, le fichier n'est pas effacé.

L'écran n'enchaîne **pas** sur le dry-run ou l'encodage comme `MuxScreen` le fait
(§ 9.7) : le fichier recousu est une entrée ordinaire, et `Backspace` le retrouve dans
le navigateur, où toutes les touches valent pour lui comme pour les autres.

---

**Revue IE-114** (v0.8.9.102, IE-136) — `nom_commun` ne retire un marqueur de
numérotation (`part`, `cd`, `tome`…) que s'il est un **mot entier** — en tête ou
après un séparateur — et une seule fois : la boucle d'avant rongeait la fin du
titre (`Le Fantome 1` → `Le Fan`, CR-29). `controler` compare aussi, rang par
rang, la **langue** des pistes audio (avertissement : la piste recollée
changerait de langue en cours de route) et leur **fréquence** (blocage : mkvmerge
refuserait), lue au scan dans `AudioTrack.sample_rate` (CR-30).

## 10. Mesure du décalage — `core/sync.py`

Corrélation croisée par FFT (numpy), en Python pur — ffmpeg est déjà présent pour le
décodage.

### 10.1 Principe

Plusieurs sondes réparties dans le fichier. À chaque point, ~30 s décodées en mono 8 kHz
de part et d'autre, puis corrélation croisée.

| Sonde | Cas constant | Conf. | Cas dérive PAL | Conf. |
|---|---|---|---|---|
| 00:12:00 | −2 450 ms | 0.94 | −2 450 ms | 0.92 |
| 00:48:00 | −2 451 ms | 0.91 | −1 021 ms | 0.90 |
| 01:24:00 | −2 449 ms | 0.93 | +410 ms | 0.88 |
| 01:48:00 | −2 452 ms | 0.89 | +1 180 ms | 0.87 |
| **Verdict** | **offset −2450 ms** | | **−2450 ms + 24000/25025** | |

Décalage stable → offset constant. Décalage qui dérive → facteur d'étirement, cherché
sur une grille de ratios.

### 10.2 Deux natures de signal

| Fonction | Référence | Signal comparé |
|---|---|---|
| `measure_audio(target, donor, …)` | enveloppe d'énergie de la cible | enveloppe d'énergie du donneur |
| `measure_subtitle(video, subtitle, …, donor_track)` | VAD appliqué à la parole du film | répliques du sous-titre |

`read_cues()` lit les timings SRT, WebVTT (heure facultative) et ASS ; une fraction
de moins de trois chiffres se complète à droite (`,5` = 500 ms, CR-37).
`_speech_mask()` construit le masque de parole. Formats lus comme du texte
(`_TEXT_SUB_EXT`) : `.srt`, `.ass`, `.ssa`, `.vtt`. Un `.sub` n'en est pas : VobSub
est binaire, et un MicroDVD n'est reconnu ni par mkvmerge ni par ffmpeg (mesuré,
2026-10-09) — il ne peut donc pas être greffé.

Un sous-titre embarqué dans un conteneur n'a pas de timings lisibles tel quel :
`extract_subtitle(video, ffmpeg_index, progress, duration)` le sort d'abord vers un
`.srt` temporaire (`ffmpeg -map 0:s:N -c:s srt`). L'appelant fournit l'index via
`muxer.ffmpeg_stream_index()`. Le conteneur se lit en entier : **aucun délai fixe**
(les 120 s d'avant tuaient ffmpeg sur tout gros donneur hors SSD, CR-35), une
progression par `-progress`. L'échec lève `ExtractionImpossible` avec sa cause : un
sous-titre image (PGS, VobSub) — ffmpeg répond « only possible from text to text or
bitmap to bitmap » — est dit tel ; tout autre échec rend la dernière ligne de
ffmpeg, jamais « image ». Dans l'écran de recalage, l'extraction (repère `A`,
correction par plages, aperçu mpv) tourne hors du fil de l'écran, avec sa barre
(`SyncScreen._en_texte`).

### 10.3 Garde-fou

Le résultat porte une **confiance** (pic de corrélation normalisé) et une **saillance**.
Le seuil d'acceptation dépend du nombre d'événements comparés (`confidence_floor()`).
Le résultat est recoupé sur trois tiers du film : un vrai alignement tient sur chacun,
du bruit se disperse.

Sous le seuil, ou si les sondes se contredisent sans dériver linéairement, le résultat
est **refusé** plutôt que proposé. *Un chiffre faux est pire que pas de chiffre.*

### 10.4 Découpage en plages

Un refus par recoupement discordant a deux causes possibles : les fichiers n'ont rien
à voir, ou ce sont deux **montages** du même contenu. `_segment_lags()` tranche.

Le film est découpé en fenêtres de 2 min ; les voisines qui s'accordent à moins de
`CROSS_TOLERANCE_MS` fusionnent ; chaque frontière est ensuite affinée au pas de 1 s, en
cherchant le point de bascule qui maximise la corrélation des deux côtés — chacun à
*son* décalage. Le décalage de chaque plage est enfin repris sur son étendue
définitive, les fenêtres de la passe grossière ayant pu chevaucher une bascule.

Deux garde-fous, parce qu'un découpage inventé est pire qu'un refus sec :

- plus de la moitié des fenêtres formant leur propre plage → aucune structure, on rend `[]` ;
- confiance médiane des plages sous `MIN_CONFIDENCE` → idem.

Le calcul n'est lancé **que** lorsque le recoupement a échoué : le cas nominal ne le
paie jamais, et les enveloppes sont déjà décodées.

Mesuré sur deux rips d'un même épisode (broadcast VFF contre streaming VO) :
6 plages, cinq paliers de +2 000 ms — les noirs de coupure publicitaire — aux
confiances 0.64 à 0.87.

`--sync` de mkvmerge et `-itsoffset` de ffmpeg n'expriment qu'une transformation
linéaire : un décalage par plages ne peut pas être passé en option. Corriger suppose
donc de **fabriquer une piste corrigée**, greffée ensuite avec un décalage nul —
l'aval (mpv, extrait, mux, encodage) la traite alors comme n'importe quel fichier.

### 10.5 Correction d'un sous-titre — `shift_srt()`

Un sous-titre se corrige **exactement** : il n'y a que des horodatages à décaler,
rien à rééchantillonner. `shift_srt()` réécrit chaque cue avec le décalage de sa
plage (`delay_at()`), en ne touchant qu'aux horodatages — texte, numérotation et
balisage passent tels quels, quel que soit l'encodage du fichier source.

Au-delà de la dernière plage, celle-ci est prolongée plutôt que ramenée à zéro : un
générique de fin suit le même montage que ce qui le précède.

`_srt_stamp()` arrondit aux millisecondes **avant** de découper : arrondir la seule
fraction écrivait `00:00:05,1000` pour 5,999999999999999 s, que mkvmerge lit 5,100 s —
900 ms trop tôt (CR-36).

Le recalage d'une piste audio désigne sa piste par l'**objet**, comme la mesure :
par son rang, `D` pendant le recalage faisait écrire l'audio recalée sur la piste
voisine (CR-92). `D` est en outre refusé tant qu'une opération tourne.

Les plages viennent de l'**audio du donneur**, jamais du sous-titre lui-même : son
signal est trop creux pour les retrouver seul, et les trois pistes d'un même donneur
portent le même montage. Vérifié sur un épisode réel — le sous-titre corrigé sort à
**+0 ms de décalage résiduel, trois tiers concordants à 100 ms**, donc accepté par le
garde-fou du § 10.3 alors que sa corrélation brute (0.17) reste sous le seuil.

### 10.6 Correction d'une piste audio — `retime_audio()`

L'audio ne se corrige pas en décalant des nombres : il faut le rallonger aux points
de bascule et le réencoder.

**Sens de l'opération.** `temps_cible = temps_donneur + décalage`, et le décalage
*croît* d'une plage à l'autre : la cible porte donc du contenu que le donneur n'a
pas. Il faut **intercaler** du silence, jamais en retirer — un donneur peut être plus
long au total tout en manquant de contenu dans le corps du film, ses minutes
excédentaires étant dans le générique.

**Placement des insertions.** La frontière rendue par la corrélation est juste à une
ou deux secondes près — assez pour tomber au milieu d'une réplique. `find_silence()`
s'accroche donc au silence le plus proche (`CUT_SEARCH_S`, 15 s de fenêtre) et centre
l'insertion dessus : allonger une pause existante ne s'entend pas.

Sans silence exploitable, l'insertion est **quand même posée** sur la frontière estimée
au lieu d'abandonner : contrairement à une coupe, allonger n'efface rien — au pire on
entend une pause un peu longue. La frontière concernée est signalée.

**Les positions croissent strictement**, et rien ne l'assurait. Chaque frontière cherche
son silence pour elle dans ±15 s, `find_silence()` recule encore de la moitié de
l'insert pour le centrer, et le centre lui-même (`end_s − delay_ms`) recule dès que le
saut dépasse l'écart entre deux bascules. Une position en retrait donnait un
`atrim=start=précédente:end=celle-ci` **à l'envers** : segment vide, et le morceau
compris entre les deux — déjà écrit — reparti dans le suivant, donc présent deux fois
dans la piste produite, qui passait pourtant le code retour et le contrôle de taille.
La position est désormais repoussée d'un bin sur la précédente et la correction
signalée ; `build_retime_command()` refuse un plan non croissant plutôt que de
fabriquer la commande.

**Fabrication.** `atrim` découpe à l'échantillon près, là où une copie de flux se
calerait sur la trame la plus proche ; sur cinq jointures, ces arrondis dériveraient
audiblement. Le silence intercalé est un extrait du donneur passé à `volume=0`, et non
un `anullsrc` : il porte ainsi d'office la fréquence et la disposition de canaux que
`concat` exige identiques sur tous ses segments. Le prix est une génération de
réencodage AAC, négligeable sur une piste déjà compressée.

**Progression.** Le décodage occupe `DECODE_SHARE` de la barre, le réencodage le reste,
suivi par `-progress pipe:1` sur `out_time_ms`. Sans lui, la barre se figeait à 85 %
pendant toute la phase longue — l'opération semblait bloquée alors qu'elle tournait
(mesuré : 14 s de décodage, puis 65 s de réencodage muet sur 82 s au total).

Progression et diagnostics arrivent par **un seul tube** (`stderr=STDOUT`, comme
`muxer.MuxProcess`) : les lignes en `clé=valeur` sont l'avancement, les autres sont
gardées comme journal d'erreur. Deux tubes dont un seul est lu au fil de l'eau se
bloquent dès que le second est plein — ffmpeg reste suspendu sur son écriture, la
lecture de l'autre n'atteint jamais la fin, et la barre se fige pour de bon.

**Tout sous-processus du projet ferme son entrée standard** (`stdin=DEVNULL`), sans
exception. ffmpeg lit `stdin` pour son clavier interactif — `q` l'arrête — et hérite
sinon de celle du terminal, que l'interface écoute : les deux se disputent alors les
frappes. La règle vaut aussi pour les outils qui ne lisent pas l'entrée, parce
qu'aucun n'en a besoin et que c'est ce qui la rend vérifiable — un test parcourt les
sources et refuse tout lancement sans `stdin=`.

Vérifié sur un épisode réel — la piste produite mesure **+0 ms, confiance excellente (0,72), trois
tiers concordants à 0 ms**, et passe donc sans réserve.

Un saut négatif (donneur plus long à cet endroit) est **ignoré et signalé** : le corriger
supposerait de supprimer du contenu.

---

## 11. Abstraction plateforme — `core/platform.py`

| Paramètre | Windows/NVIDIA | Windows/CPU | macOS | Linux/CPU |
|---|---|---|---|---|
| hwaccel | `cuda` | *(absent)* | `videotoolbox` | *(absent)* |
| encoder HEVC | `hevc_nvenc` | `libx265` | `hevc_videotoolbox` | `libx265` |
| encoder H264 | `h264_nvenc` | `libx264` | `h264_videotoolbox` | `libx264` |
| encoder AV1 | `av1_nvenc` | `libaom-av1` | `libaom-av1` | `libaom-av1` |

Détection GPU NVIDIA via `nvidia-smi`. Sans NVIDIA sur Windows, fallback CPU.

---

## 12. Encodeur — `core/encoder.py`

### 12.0 Pistes externes absorbées en une passe

ffmpeg prend chaque piste greffée comme entrée supplémentaire et sort le fichier
final directement : **muxer au préalable est inutile** quand le fichier est de toute
façon réencodé. Le mux (`F3`) n'est pas une étape antérieure à l'encodage, c'est
l'alternative pour quand on ne veut pas toucher à la vidéo.

**Le décalage négatif ne passe pas par `-itsoffset`.** Un `-itsoffset` négatif rend
négatifs les horodatages du donneur ; ffmpeg refuse de les écrire et décale *tout le
fichier* vers l'avant. Mesuré pour −2 500 ms : la vidéo sort avec
`start_time = 2.5 s` et le conteneur gagne 2,5 s. Les lecteurs de bureau normalisent,
les décodeurs matériels de téléviseur pas toujours — d'où des fichiers qui plantent à
la lecture sur TV alors qu'ils sont parfaits sur PC.

Un décalage négatif est donc traduit en `-ss` sur l'entrée du donneur : on saute son
début au lieu de le repousser. Résultat identique, tous les flux à `start_time = 0`,
durée du conteneur correcte. Un décalage **positif** garde `-itsoffset` : il ne crée
aucun horodatage négatif, et seule la piste greffée démarre plus tard — ce que
mkvmerge produit également.

**L'étirement passe par un mux préalable, automatiquement.** ffmpeg ne sait pas le
appliquer en une passe ; mkvmerge si. `needs_premux()` le détecte, `RunScreen._premux()`
greffe les pistes vers un intermédiaire temporaire (`premux_output_path()`, hors du
dossier du film), puis ffmpeg encode celui-ci. L'utilisateur n'enchaîne plus deux écrans
à la main.

`FileDecision.encode_source` porte cet intermédiaire ; `info.path` reste la source,
dont dépendent le nom et le dossier de sortie — l'intermédiaire ne doit pas décider où
le résultat atterrit. Il est supprimé à la fin de la passe, réussie ou non.

Les pistes greffées quittent alors `external_tracks` — ffmpeg ne doit pas rouvrir les
donneurs, mkvmerge les ayant déjà absorbés — pour `premuxed_tracks`. Elles restent
entièrement à mapper : dans l'intermédiaire elles suivent celles de la source, dans
l'ordre où mkvmerge les écrit (`premux_track_order()` : fichier par fichier, puis par
tid croissant), et leur index part donc du nombre de pistes de la source, que la
décision les garde toutes ou non. Une fois l'intermédiaire supprimé, elles reviennent
dans `external_tracks` : un second essai doit repasser par le mux préalable.

Le surcoût — une écriture complète du film — n'est payé que dans ce cas. Sans mkvmerge,
l'opération est refusée en amont plutôt que d'échouer en cours d'encodage.

**Une piste audio greffée suit la règle audio du profil** (v0.8.9.103, arbitrage de
la revue IE-114) : `decision.audio_greffee()` relit le donneur par ffprobe
(`scanner.pistes_audio()`) et passe la piste par `decide_codec_audio()`, la règle des
pistes de la source. Un DTS, un Opus, un FLAC greffés étaient recopiés et faisaient
transcoder Jellyfin. Un donneur illisible est refusé plutôt que recopié. Le titre de la
piste est réécrit comme celui d'une piste de la source transcodée (`retitle`).
Les chemins Dolby Vision, qui greffent par mkvmerge, appliquent la même règle depuis
la v0.8.9.107 (`_transcoder_greffes`, § 7.3). Le mux seul (SKIP + greffes,
`_muxer`, écran du mux) recopie toujours la piste telle quelle.

**Drapeau par défaut.** Une greffée marquée « par défaut » ôte celui des pistes de la
source de même type, audio comme sous-titres (`-disposition:s:N 0`, CR-23) — même
règle que le mux (§ 9.5, piège 4 bis).

**Jeu de caractères.** ffmpeg lit un sous-titre texte en UTF-8 : un `.srt` en cp1252
perdait toutes ses répliques accentuées, code de retour nul. `-sub_charenc` précède
l'entrée quand `encodage_texte()` trouve un autre jeu (CR-50).

**Polices jointes.** En sortie Matroska, `-map 0:t? -c:t copy` recopie les pièces
jointes de la source : sans elles, les sous-titres ASS d'un animé s'affichaient dans
une police de repli (CR-20).

### 12.1 Modes d'encodage vidéo

| Mode | Condition | Encodeur | Notes |
|---|---|---|---|
| **Retrait DV** | `action == STRIP_DV` | aucun — dovi_tool + mkvmerge (MKV), filtre `dovi_rpu` de ffmpeg (MP4) | `build_command` retourne `[]` ; le chemin est dans `RunScreen._strip_dv` (§ 7.3) |
| **Réencodage DV** | `action == ENCODE_DV` | nvenc / libx265 | Passe vidéo seule en Annex-B, sans filtre ; RPU réinjecté après (§ 7.4) |
| **DV copy** | `dv_action == DV`, RPU non réinjectable | `-c:v copy` | Pas de réencodage, pas de hwaccel |
| **HDR10 quality** | `dv_action == HDR10` + `hdr10_quality == "quality"` | `libx265` CPU | Métadonnées via `-x265-params`, `pix_fmt yuv420p10le` |
| **SDR tone map** | `dv_action == SDR` | nvenc / libx265 (CPU) | Filtre `zscale+tonemap`, pas de hwaccel |
| **Standard** | Tous autres cas | nvenc / libx265 / libx264 / av1_nvenc | hwaccel si disponible |

**Passe audio préalable.** Quand une invocation ffmpeg décode une piste audio
sans perte *et* mappe un flux de sous-titres dont le premier repère arrive
tardivement, la piste transcodée n'est pas écrite : deux trames sortent, puis
plus rien, sans erreur ni code de retour non nul. Mesuré et reproductible sur
soixante secondes.

**C'est la simultanéité, pas la sortie** — le tableau ci-dessous le tranche :

| Disposition | Paquets audio sur 60 s |
|---|---|
| une seule sortie, tout ensemble | 2 |
| deux sorties, l'audio seule dans la sienne | 2 |
| deux sorties, le sous-titre seul dans la sienne | 2 |
| sous-titre présent dans l'entrée, **non mappé** | 1 875 |
| **appel ffmpeg distinct** | 1 875 |

Aucune disposition des sorties ne sauve la piste : seul un processus séparé le
fait. La passe n'est payée que si la source décodée est **sans
perte** (TrueHD, MLP, DTS-HD MA) : transcoder l'AC3 du même fichier sort
indemne. Cette restriction repose sur deux mesures, un codec de chaque famille
— d'où le filet ci-dessous.

**Le succès se vérifie.** ffmpeg rend ici un code nul et un fichier amputé :
`encoder.pistes_audio_vides()` relit la sortie et compare la durée de chaque
piste audio à celle attendue. En dessous du dixième, le fichier est déclaré en
erreur au lieu d'être compté comme réussi. Le seuil est grossier à dessein — il
sépare « 54 millisecondes au lieu de trois heures et demie » de tout ce qui est
légitime, y compris une piste de commentaires écourtée. Le contrôle vaut pour
chaque sortie finale, chemins Dolby Vision compris (`RunScreen._audio_vide`,
v0.8.9.106, CR-65). Facteurs éliminés par mesure — le codec de sortie (l'AC3 meurt comme
l'E-AC3), la durée, l'encodage matériel, les drapeaux de piste, et six réglages
de muxeur (`max_muxing_queue_size`, `max_interleave_delta`,
`avoid_negative_ts`, `copyts`, `muxdelay`, l'ordre des `-map`). Transcoder
l'AC3 de la même source au lieu du TrueHD sort indemne, et ne mapper que les
sous-titres denses aussi.

`encoder.audio_prepass_needed()` détecte la conjonction ; les pistes finales
sont alors produites par `build_audio_command()` puis **recopiées** dans la
passe d'encodage, une copie ne se perdant jamais. Le coût est un transcodage
audio, là où la passe vidéo se compte en heures — et il n'est payé que lorsque
les deux conditions sont réunies.

**Le défaut ne se reproduit plus en ffmpeg 8.1.2 (gyan.dev) ni 8.1.3 (BtbN)**
(IE-80, 2026-10-07) : ni sur le fichier qui le déclenchait (piste forcée à
380 s), ni sur de vrais TrueHD et DTS-HD MA, ni sur MLP, FLAC ou PCM, même avec
la commande complète de `build_command` sans passe préalable. La version de
ffmpeg du 2026-08-28 n'ayant pas été notée, la correction n'est pas datée. La
passe est **gardée** (choix de l'utilisateur) : un ffmpeg plus ancien au `PATH`
reste possible, et elle ne coûte qu'un transcodage audio.

**Les sous-titres de la source ont alors leur propre entrée.** Dès que l'audio
vient d'une autre entrée que la vidéo (passe audio préalable, ou piste audio
greffée), `build_command()` rouvre la source en entrée supplémentaire, la
dernière, et y prend les sous-titres. Lus avec la vidéo, ils rendaient un
fichier dont l'audio s'interrompait : le muxeur écrivait des centaines de
secondes de vidéo seule, puis l'audio en bloc. Le fichier reste lisible par
ffmpeg et mpv, mais un lecteur matériel s'arrête quand l'audio manque, et les
sauts font perdre le son. Mesuré sur *Film K* (DTS-HD MA, ffmpeg
8.1) : aucun audio entre 31,9 s et 122,6 s du fichier, jusqu'à 1 150 s de
retard plus loin. `-max_interleave_delta 0` répare aussi, mais le muxeur garde
alors en mémoire tout ce qui précède la réplique suivante de la piste la plus
creuse — 2 168 s sur la piste « forced » de ce film. La parade retenue coûte
une seconde lecture de la source, et rien quand tout vient de l'entrée 0.

**Profondeur de bits.** Le mode standard sortait en `yuv420p` — 8 bits — quelle que
soit la source. Sur une courbe PQ, cela étale 10 bits de dégradés sur 256 niveaux :
banding garanti. La sortie passe en `yuv420p10le` + `-profile:v main10` dès que la
sortie est HDR (source PQ/HLG, ou `dv_action == HDR10`) et que l'encodeur sait le
porter — HEVC et AV1. H264 n'a pas de profil 10 bits chez NVENC : une source HDR
ramenée en H264 reste en 8 bits, ce qui ne concerne que les cibles sous 1080p.

**Contrôle de débit.** Le débit du profil est une **cible moyenne**, jamais un
plancher : NVENC ne dépense que ce que le contenu exige. Le mode standard passe
donc `-b:v <cible> -maxrate <cible × 1,5> -bufsize <2 × maxrate> -rc vbr`. La
marge de 50 % au-dessus de la cible existe pour que les scènes difficiles
compensent les scènes faciles — avec un plafond égal à la cible, seules les
pertes jouent et la moyenne ne peut que tomber en dessous. Mesuré sur 180 s de
film en prises de vues réelles 2160p 10 bits, cible 6 035k : 92 % du débit
demandé sous l'ancien réglage, 99 % sous le nouveau.

Un fichier peut rester très en dessous de sa cible sans que ce soit un défaut :
sur une animation au dessin plat, le même extrait rend 41 % (ancien) et 54 %
(nouveau), et un encodage piloté par la qualité (`-cq 16`) dépense encore moins.
La fidélité mesurée reste supérieure à celle d'un encodage 8 bits qui, lui,
consomme 62 % de bits en plus (SSIM 0,9991 contre 0,9970).

**libx265 veut le réglage inverse, et c'est mesuré.** Le mode « HDR10 quality »
(§ 12.1) garde `-maxrate` **égal** à la cible. L'ABR de x265 distribue un budget
selon son modèle de qualité ; c'est un VBV serré qui le force à le dépenser, là
où le CBR de NVENC ne voyait qu'un plafond. Desserrer le plafond y fait donc
*sous*-consommer. Mesuré sur un film 1080p 10 bits, extraits de 120 s, cible
5 000k :

| Réglage | t=1800 | t=4200 |
|---|---|---|
| `maxrate` = cible (en place) | 99,9 % | 100,0 % |
| `maxrate` = 1,5 × la cible | 93,6 % | 99,9 % |
| ABR seul, sans VBV | 93,7 % | — |

Au preset `slow`, celui de `cinema_4k_basic` : 99,6 %. Les deux branches de
`build_command` se ressemblent et **doivent différer** ; `tests/test_x265_debit.py`
fait échouer toute harmonisation. Depuis la v0.8.9.113 (CR-22), la règle suit
l'**encodeur effectif** (`encoder.regle_debit`) : sur un poste sans NVIDIA, la
branche standard et la passe vidéo du réencodage DV donnent aussi à libx265 un
`-maxrate` égal à la cible ; `-rc vbr` n'est posé que pour NVENC.

### 12.2 Pause / Reprise

- Windows : `NtSuspendProcess` / `NtResumeProcess` via ctypes
- POSIX : `SIGSTOP` / `SIGCONT`

### 12.3 Progression

Parsing de la ligne `stderr` ffmpeg :

```
frame= N fps= N q=N.N size= NkB time=HH:MM:SS.ss bitrate=N.Nkbits/s speed=Nx
```

Retourne un `ProgressInfo` (frame, fps, elapsed, bitrate, speed, percent).
`percent = -1.0` si la durée est inconnue. La vitesse relevée alimente la moyenne
mobile de `[stats.encode_speed]`, qui nourrit la colonne « ETA ».

### 12.4 Garde-fous

- Chemin de sortie identique à la source : `ValueError` levée avant lancement
- Sortie partielle supprimée en cas d'échec — **sur tous les chemins**
  (v0.8.9.99, CR-57, CR-90) : passe principale (échec de ffmpeg, piste audio
  vidée, `S`), retrait et réencodage Dolby Vision (`finally` : état autre que
  SUCCESS), mux. Le nom est le nôtre, figé à la mise en file sur un fichier qui
  n'existait pas. Avant, seul l'arrêt (`X`, `F10`) l'effaçait.
- **Intermédiaires** (v0.8.9.99) — une seule forme, `<nom>.iris_<étape>.<ext>`
  (`scanner.intermediaire`, reconnue par `est_intermediaire`) : `titre`,
  `audio`, `st`/`st<n>`, `chap`, `dv`, `enc`, `p8`, `premux`, `recale`…
  `deja_produit` les compte comme des sorties : laissés par une coupure, ils
  sont grisés, hors de `Ctrl+A` et du mode récursif, visibles pour être
  supprimés (CR-11). `RunScreen._liberer(dec, *tmps)` les efface sur **chaque**
  sortie de la passe principale, anticipée comprise (CR-58) ; il ne rend les
  greffes à `external_tracks` que si un mux préalable les avait absorbées.
  Le mux préalable (`premux_output_path(source, dossier)`) et la piste recalée
  (`SyncScreen._fichier_recale`) s'écrivent dans `dossier_sortie`, plus dans
  le temp du disque système (CR-28, CR-93 ; temp en dernier recours si le
  dossier refuse l'écriture). Une piste recalée est effacée après un encodage
  réussi, qui l'a recopiée.
- **Code 1 de mkvmerge** (v0.8.9.99, CR-89) — des avertissements, une sortie
  complète : `muxer.mkvmerge_reussi(code, sortie)` (0 ou 1, et la sortie
  existe) est la seule règle — mux, jonction, extrait, mux préalable,
  assemblage, remux Dolby Vision. Un `.srt` aux répliques désordonnées faisait
  jeter un réencodage DV de plusieurs heures.
- **Arrêts et sorties** (v0.8.9.100, IE-131) — `S` sur un encodage en pause
  le reprend avant de l'arrêter : sous POSIX, l'arrêt d'un processus suspendu
  restait en attente (CR-60). `Ctrl+Home` pendant un mux ou une jonction passe
  par `_interrompre`, comme `⌫` (CR-91). Quitter (`_on_quit_answer`) arrête les
  écrans de **tous** les modes (`_screen_stacks`), pas seulement la pile
  affichée (CR-71) ; une seule confirmation de sortie à la fois (CR-103) ;
  `travaux_en_cours` ne traduit que les workers de `_TRAVAUX` — `_("")` rendait
  l'en-tête du catalogue (CR-70). Le compte à rebours d'après lot
  (`FinDeLotModal`) n'agit qu'au sommet de la pile (`is_active`) et une seule
  fois : recouvert, il faisait retirer l'écran du dessus (CR-104).
  `list_volumes` interroge les lettres par `os.path.isdir`, qui ne lève jamais :
  un lecteur non reconnu ou verrouillé empêchait IRIS de démarrer (CR-67).
  OpenSubtitles : une réponse 200 qui n'est pas du JSON (portail captif) devient
  une `ErreurOpenSubtitles`, et les deux workers attrapent aussi `OSError`
  (CR-95).
- **`S` sur une étape mkvmerge** (v0.8.9.108, CR-61) — assemblage d'un titre, mux
  préalable, mux, remux Dolby Vision : `S` l'arrête aussi (`self._mux`) ; entre deux
  étapes, un message dit d'attendre un instant au lieu de ne rien faire. **Un
  abandon reste un abandon** : l'échec d'une étape que `S` ou `X` vient
  d'interrompre ne réécrit plus l'état SKIPPED en ERROR (chemins DV,
  `_porter_sous_titres`, `_muxer`, `_remux_titre`, `_extraire_dvd`, `_premux`) — le
  bilan affiché « Arrêté » était contredit ensuite.
- **Annexes partagées** (CR-24) — `annexes_jellyfin` ne rend rien quand une
  autre vidéo du dossier porte le même nom (`Film.avi`, `Film.iso`) : Jellyfin
  rattache les annexes aux deux.

---

## 13. Métadonnées — `core/meta.py`

### 13.1 Extraction du titre

`parse_title(path)` tronque le nom au premier marqueur de format (résolution, année,
source, épisode…) et retourne `(titre, année)`.

```python
parse_title(Path("Titre.Film.2022.2160p.BluRay.mkv"))
# → ("Titre Film", 2022)
```

### 13.2 IMDB — deux modes

| Mode | Condition | Données |
|---|---|---|
| **OMDb API** | `omdb_api_key` renseigné | Note, synopsis, genres, réalisateurs, casting |
| **Suggestions API** | Pas de clé | Titre, année, casting partiel — ni note ni synopsis |

L'API suggestions est l'endpoint JSON `v2.sg.media-imdb.com/suggests/` — non officielle
mais stable et sans clé.

### 13.3 AlloCiné — scraping

Deux appels HTTP : autocomplete JSON → `entity_id`, puis fiche HTML → JSON-LD.
Note sur 5.0.

### 13.4 Modèle `MovieMeta`

```python
@dataclass
class MovieMeta:
    source:     str          # "imdb" | "allocine"
    title:      str
    year:       int | None
    kind:       str          # "Film" | "Série" | "Téléfilm" | …
    rating:     float | None
    rating_max: float        # 10.0 IMDB, 5.0 AlloCiné
    genres:     list[str]
    directors:  list[str]
    cast:       list[str]
    synopsis:   str
    url:        str
```

---

## 14. Interface TUI — `tui/`

Framework : **Textual**.

**Vocabulaire affiché** (v0.8.9.20, UX-08). L'action d'encoder s'appelle
**Encoder** partout (`F2`), son écran **Encodage** (`RunScreen`) ;
l'encodage d'une arborescence, **Encoder le dossier** (`R`). Le dry-run
s'affiche **Aperçu** (`DryrunScreen`, `F1`). Le collage des parties d'un
film s'affiche **Joindre** / **Jonction** (`JoinScreen`, `core/joiner.py`).
Les noms internes — classes, actions, `dry-run` dans cette spec — ne
changent pas.

Conventions transverses :

- **Les capacités d'encodage sont mesurées, jamais supposées.** `detect()`
  déduit les encodeurs du modèle de carte, ce qui ment : NVENC n'encode l'AV1
  qu'à partir d'Ada, et une carte antérieure ne le dit qu'au moment d'échouer.
  `sonder_encodeurs()` ouvre chacun sur une image au lancement — trois
  sondages en parallèle, ~0,7 s — et remplit `PlatformProfile.encodeurs_ok`.
  `peut_encoder()` rend `None` tant que rien n'a été sondé : **ne rien savoir
  n'autorise pas à refuser**.
  Le choix n'est jamais retiré du picker — une carte se remplace, un pilote se
  met à jour — mais il est annoté « ✗ indisponible ici », et le lancement
  refuse en nommant la cause plutôt que de laisser ffmpeg échouer.
  Une vidéo recopiée (`-c:v copy`) n'est pas contrôlée : `copy` n'est pas un
  encodeur (`encodeur_a_controler`, v0.8.9.60).
  **Le 10 bits aussi** (v0.8.9.113, CR-42) : `hevc_nvenc` et `av1_nvenc` sont
  sondés une seconde fois en `p010le` (`main10` pour le HEVC), rangés sous
  `<encodeur>@10`. Une carte qui ouvre le HEVC en 8 bits seulement (Maxwell)
  était dite capable, et un fichier HDR échouait dans ffmpeg sur un message
  inconnu. `RunScreen._refuser_encodeur` refuse alors une commande 10 bits
  (`sortie_10_bits`), cause nommée, avant la passe principale comme avant la
  passe vidéo du réencodage DV. Les encodeurs logiciels ne sont pas sondés en
  10 bits (`peut_encoder_10_bits` → None).
  La sonde garde la sortie d'erreur des refus (`refus=`) : si ffmpeg y dit que
  le pilote est trop ancien pour son API NVENC, `alerte_pilote_nvenc()` en tire
  un message (pilote exigé, API exigée et fournie), rangé dans
  `PlatformProfile.alerte_nvenc`, notifié au lancement et repris au refus d'un
  fichier NVENC. Tout NVENC tombe dans ce cas, pas seulement l'AV1.
- **Un échec d'encodage nomme sa cause.** ffmpeg annonce la cause puis constate
  l'échec ; l'écran ne gardait que la dernière ligne, la seule qui n'apprend
  rien. `encoder.diagnostiquer()` cherche des signatures connues dans les
  quarante dernières lignes — chacune reproduite avant d'être ajoutée — et
  retombe sur la ligne brute plutôt que d'inventer un message.
- **Les binaires viennent de la configuration, jamais du `PATH`.** Le preflight
  installe ffmpeg, ffprobe, dovi_tool, mkvmerge et mpv dans `./bin/` **sans
  toucher au `PATH`**. Les appeler par leur nom nu échoue donc sur une
  installation neuve : `scanner.set_ffprobe_path()` et
  `encoder.set_ffmpeg_path()` sont posés au démarrage par `tui/app.py`, comme
  `muxer.set_mkvmerge_path()` et `sync.set_ffmpeg_path()` le faisaient déjà.
- **Deux zones ne disent pas la même chose.** La barre d'état porte le dossier
  courant ; la notice de survol ne montre donc que ce qu'elle n'a pas déjà dit —
  le nom du fichier, ou son chemin relatif quand un scan récursif le remonte
  d'un sous-dossier. Répéter le préfixe coûtait une quarantaine de colonnes.
- **Le footer ne passe à la ligne qu'au débordement.** `split_bands()` fixe
  l'ordre — propres à l'écran, globaux, touches de fonction — mais plus le
  découpage : les trois bandes sont enchaînées puis enroulées ensemble. Une
  bande d'une seule entrée n'occupe plus une ligne entière. Contrepartie
  assumée, qui revient sur un choix de la v0.8.1.2 : les touches de fonction
  restent en fin de séquence, mais ne démarrent plus forcément leur ligne.
- **Un écran ne promet que ce qu'il peut tenir.** Le browser en mode volumes
  (`start_virtual=True`) porte ses propres colonnes — Volume, Espace libre,
  Total, Occupé — et non les dix du tableau de fichiers, dont aucune ne peut
  avoir de valeur pour un volume. La barre d'état y compte des volumes plutôt
  qu'une sélection impossible, le bandeau de profil attend qu'un fichier soit
  en vue, et le footer ne propose que l'ouverture. Le jeu de colonnes et les
  raccourcis basculent dans `_refresh_view()` au changement de mode.
- **Une modale laisse voir l'écran sur lequel elle porte.** La règle globale
  `Screen { background: $surface; }` s'appliquait aussi aux modales, qui
  héritent de `Screen`, et écrasait la translucidité que Textual leur donne :
  il ne restait qu'une boîte au milieu du vide. `ModalScreen { background:
  $background 40%; }`, posée **après** elle, rétablit le filigrane. La boîte
  garde son fond opaque : son texte ne perd rien en lisibilité.
- **Un seul cadre pour toutes les modales** : le trait fin (`border: solid`).
  Les demi-blocs `█ ▀ ▄` distinguaient les listes de choix des confirmations,
  une frontière graphique qui ne correspondait à aucune différence de rôle.
- **Le footer annonce les touches qui répondent.** Un écran qui héberge un
  widget prenant le focus — `ConfigScreen` et son `ProfileForm` — bascule le
  contenu du footer par `KeyFooter.update_line()` tant que ce widget est monté.
  Le widget publie ses raccourcis (`ProfileForm.RACCOURCIS`), l'écran garde les
  siens, et `F10` reste en dernier dans les deux états. Un footer faux est pire
  qu'un footer vide : il invite à des gestes sans effet.
- **Les noms de touches se rendent par `tui.common.touche()`.** Trois
  notations coexistaient — `Space Sélect` au footer, `Espace  Sélectionner`
  dans les modales, `Tab / Shift+Tab : champ suiv./préc.` au formulaire de
  profil. La table `TOUCHES` et les fonctions `touche()`, `raccourci()`,
  `raccourcis()` sont la seule source ; `SEP_TOUCHE` et `SEP_ENTREE` fixent
  l'espacement. Les glyphes (`↵`, `⌫`, `␣`, `←`) sont préférés là où ils
  existent : ils tiennent en une colonne, ce qui compte sur un footer de trois
  lignes. Une notation composée (`+/-`, `Shift+↑/↓`) traverse intacte.
- **Les couleurs porteuses de sens se décident dans `core.decision`, en rôles.**
  `Emphase` nomme ce qu'une couleur veut dire — `INACTION`, `SANS_PERTE`,
  `ORDINAIRE`, `MODIFIEE`, `ALERTE` — et `STYLE_PAR_EMPHASE` seule choisit les
  teintes. Deux arbitrages y sont inscrits : le cas ordinaire ne porte **aucune
  couleur**, parce que ce qui se répète à chaque ligne d'un écran dense ne doit
  pas attirer l'œil ; et `dark_orange` n'appartient qu'aux alertes, une réserve
  n'ayant de valeur que si rien d'autre ne l'emploie. Les écrans lisent cette
  table (`style_video`, `style_dv`) au lieu d'en tenir chacun une.
- **Une colonne ne descend pas sous ce que son contenu exige.**
  `core.config.COLUMN_MIN_WIDTHS` porte les planchers imposés par le contenu —
  `duree` et `temps_estim` à 7, parce que `fmt_duration` rend sept caractères
  dès qu'il y a des heures ; `taille` à 8, pour « 999.9 Go » (v0.8.9.15). Ils s'appliquent **à la lecture** autant qu'au
  redimensionnement : une largeur trop courte a pu être persistée avant que le
  plancher existe, et corriger le seul défaut ne répare pas ces
  configurations. Les écrans reprennent cette table dans leur `RESIZE_MIN`
  plutôt que d'en tenir une seconde. Toute cellule numérique porte en outre
  `overflow="ellipsis"` : une coupe résiduelle se voit (`3:17:…`) au lieu de
  produire une valeur plausible et fausse (`3:17:2`).
- **Une colonne redimensionnable tient son en-tête** (v0.8.9.13, UX-27).
  Textual rogne un en-tête trop long, sans ellipse. Le plancher effectif
  (`ColumnResizeMixin.resize_plancher`) est le plus grand de `RESIZE_MIN` et
  de `len(libellé)`. Calculé depuis le libellé à l'exécution, il vaut pour
  toute langue ; il s'applique à la construction de la table
  (`resize_largeur`) comme au rétrécissement. La colonne active se repère à
  son en-tête **en vidéo inverse** (v0.8.9.14) : le repère « ◄► » ajoutait
  trois caractères que chaque colonne devait réserver.
- **Une barre d'état a une forme** (v0.8.9.22, UX-14) : « Titre — élément ·
  élément », construite par `tui.common.barre_etat`. `tests/test_barres.py`
  refuse le séparateur « ── » dans un texte affiché.
- **Une colonne fixe tient aussi son en-tête** (v0.8.9.16, UX-28). Toute
  colonne nommée à largeur figée passe par `tui.common.largeur_entete`
  (`max(largeur, len(libellé))`) : « Langue » en 7 ne tiendrait pas
  « Language ». `tests/test_troncature.py` refuse une largeur littérale.
- **La table tient dans le terminal** (v0.8.9.14, UX-19). Le total compte la
  marge de chaque cellule (`MARGE_CELLULE`, un caractère de chaque côté) et,
  dans `RESIZE_FIXE`, les colonnes hors cycle avec leurs marges et la barre de
  défilement verticale : 164 colonnes déclarées en occupaient 188. Sur
  l'accueil et le dry-run, **Fichier prend la place que les autres laissent**
  (`resize_remplissage`), plancher 20, sauf largeur réglée au clavier dans la
  session ; à 160 colonnes, la table en occupe 158. Sur l'accueil, la largeur
  se recalcule à l'entrée dans un dossier et **suit la fenêtre** (v0.8.9.45) :
  `BrowserScreen.on_resize` reconstruit la table 0,15 s après le dernier
  changement de taille, si la largeur voulue pour Fichier a changé.
- **Filtre de l'accueil** (v0.8.9.46). `L` choisit un type d'image
  (`browser.type_image` : profil DV `DV:P8.1`…, sinon `HDR` si la courbe est
  PQ ou HLG, sinon `SDR`) parmi ceux du dossier (`options_filtre`), ou
  « Dolby Vision » tous profils ; `Z` masque les lignes dont la décision est
  `SKIP`. `ligne_visible` applique les deux, et laisse toujours passer une
  ligne cochée. Le filtre vit sur l'écran (session, pas `config.toml`) ;
  `_dossier` garde tous les fichiers du dossier pour pouvoir refiltrer sans
  rescanner. La barre d'état nomme le filtre et compte les masqués.
- **Un afficheur qui montre un nom se construit en `markup=False`.** `Static`
  interprète par défaut ce qui ressemble à une balise entre crochets, et la
  convention de nommage du projet jusqu'à la v0.8.8.10 — `_[mux]`, `_[hevc]`,
  `_[av1]`, `_[hdr10]` — et ses fichiers temporaires `_[extrait]`, `.iris_premux`
  sont faits de cette syntaxe. Un nom affiché sans
  précaution y perd son suffixe, et un identifiant de profil écrit
  `[serie_basic]` disparaît en entier. Le piège est irrégulier : `_[H264]`
  survit, Rich ne consommant que ce qui ressemble à un nom de style valide.
  Les modales de confirmation font exception — elles utilisent du markup
  volontaire et échappent les noms interpolés par `rich.markup.escape`.
  `tests/test_markup.py` verrouille la liste des afficheurs concernés.
- **`TwoLineFooter`** — footer 2 lignes remplaçant le Footer natif. Ligne 1 : navigation.
  Ligne 2 : actions. `F10 Quitter` toujours en dernier.
- **Touches retour normalisées** : `Backspace` / `Esc` sur tous les écrans.
- **`ConfirmModal`** (`tui/screens/confirm.py`) — toute confirmation passe par elle.
  Bordure `$warning` si destructif, `←/→` déplacent le focus, `↵` active le bouton
  focalisé (jamais de validation aveugle), `Esc`/`⌫` annulent.
- **Pas de `bold red`** : les alertes utilisent `bold dark_orange`.
- Les colonnes des tables sont redimensionnables (`Tab`/`Sh+Tab` pour choisir,
  `<`/`>` pour ajuster), largeurs persistées dans `config.toml`.

### 14.0 Écran Wizard — l'assistant

Écran **autonome**, et non un enchaînement des écrans existants. Il est le mode
d'entrée de l'application ; `W`, depuis l'accueil, bascule vers le parcours
libre, et le choix tient pour la session. La barre de profil affiche lequel des
deux est actif — le mode change ce que fait `↵` sur un fichier, cela doit se
lire sans avoir à l'essayer.

En mode assistant, `↵` sur un fichier ouvre le parcours. Un fichier à la fois.

**Le bandeau rappelle le fichier traité à chaque étape.** Sans lui, les quatre
écrans qui suivent le premier parlent d'un travail dont on a perdu le sujet. Le
chemin n'apporte rien — c'est le nom qui identifie — et il est tronqué au milieu
selon la largeur disponible, pour que sa fin survive (voir
`common.tronquer_milieu`).

**Le mode se lit à trois endroits**, parce qu'il commande ce que fait une touche
aussi banale que `↵` : la barre de profil (`W Assistant` / `W Manuel`), le
libellé de la touche `W` dans le footer, et **la couleur du footer**. Le manuel
garde le code couleur par défaut (`$primary-darken-2`) ; l'assistant prend
l'accent du thème (`KeyFooter.assistant`), sur l'accueil comme sur ses propres
écrans. Les noms de touches suivent : jaune sur le bleu,
**blanc sur l'accent** — deux couleurs chaudes de luminosité voisine rendaient
le footer illisible là où il compte le plus. Une couleur se remarque sans être lue — c'est le seul des trois qui ne
demande aucune attention.

| Étape | Ce qu'on y fait | Touches |
|---|---|---|
| 1 — Fichier | Le nom du fichier, ses caractéristiques, le profil actif | `↵` |
| 2 — Décision | Codec, débit et pistes conservées, sur un seul écran | `Espace` `F6` `F7` `↵` |
| 3 — Pistes externes | Présenter un donneur ; la mesure suit aussitôt | `F9` `D` `↵` |
| 4 — Lancer | Muxer ou encoder — **les deux toujours offerts** | `F3` `F2` `↵` |
| 5 — Terminé | Le résultat, puis retour à l'accueil | `↵` |

**`F2` sur un SKIP force l'encodage** (v0.8.9.61), comme une ligne cochée au
navigateur : la file l'aurait marqué « ignoré » (`WizardScreen._a_encoder`).
L'étape 4 annonce la décision forcée et le nom qui en sort. Un retrait du DV
part tel quel.

**Un codec choisi à la main** (`F6` ici, dans l'aperçu et l'écran des pistes,
et la coche forcée) passe par `decision.choisir_codec` : HEVC avec le DV
conservé devient `ENCODE_DV` quand `peut_reencoder_en_dv` l'accepte, et un débit
nul hérité d'un SKIP prend celui de la source — ou la cible du profil si le
débit est inconnu (`debit_source_ou_cible`, CR-19).

**Pas de H264 en HDR** (v0.8.9.113, question de la revue tranchée le
2026-10-09) — NVENC n'encode pas le H264 en 10 bits : une source HDR (PQ, HLG ou
Dolby Vision) en H264 sortait en PQ sur 8 bits, du banding dans chaque dégradé,
sans un mot. `h264_force_sdr` : H264 sur une source HDR sort en **SDR** (tone
mapping, `dv_action = SDR`), et chaque point de choix l'annonce
(`tui.common.avertir_h264_sdr` : assistant, aperçu, écran des pistes, dont la
colonne DV montre SDR). La coche forcée, qui n'est pas un choix de codec, garde
une source HDR en HEVC quelle que soit sa tranche. Elle suit la **tranche** de
définition et non la hauteur (CR-16) : un 1920×800 au format scope se force en
HEVC, plus en H264 au même débit. Le libellé de décision nomme chaque codec
(`CODEC_PAR_ACTION`) : un AV1 s'affichait « → H264 » (CR-17). La conversion SDR
demande une source étiquetée (primaires et courbe) : sans étiquettes, zscale
répond « no path between colorspaces » (mesuré).

**La mesure passe par `sync.measure_external_track`**, seul point d'entrée pour
mesurer une piste externe. Il traduit le tid mkvmerge en index ffmpeg — les deux
numérotations se ressemblent assez pour qu'on les confonde, et une mesure lancée
sur le mauvais flux échoue sans dire pourquoi. Le défaut s'est produit deux fois
avant que la traduction ne soit centralisée. Une jauge suit l'avancement, chaque
piste occupant sa part : plusieurs minutes sans retour se lisent comme un blocage.

**La mesure ne se demande pas.** Une piste greffée sans recalage est une piste
décalée : il n'y a rien à arbitrer. L'audio est mesurée dès l'ajout, et son
décalage reporté sur les sous-titres du même donneur par
`muxer.propager_recalage()` — leur bon décalage *est* le sien. Une mesure
refusée laisse le décalage à zéro et le dit, plutôt que d'appliquer un candidat
non confirmé.

**Les deux lancements sont toujours proposés.** `↵` prend le recommandé — mux si
rien n'est à réencoder mais qu'il y a à greffer, encodage sinon — et `F3` / `F2`
forcent l'autre. Un retrait du Dolby Vision n'est pas « rien à réencoder » : le mux
recopierait la vidéo RPU compris, en MKV Dolby Vision (CR-85) ; il part par la file,
qui greffe elle-même (`_muxable` ne vaut que pour un SKIP). Un mux sans piste externe est refusé avec sa raison, pas
exécuté à vide.

**Ce qu'on retire, c'est la navigation, jamais l'information.** Un assistant qui
déciderait en silence remplacerait un doute de manipulation par un doute de
contenu, qui ne se voit qu'après l'encodage. L'étape 2 nomme donc le fichier
produit, et chaque étape montre ce qu'elle a décidé.

**Aucun donneur n'est cherché automatiquement.** Les conventions de nommage des
releases sont sans limite, et un mauvais appariement est *silencieux* — il ne se
découvre qu'à l'écoute. C'est l'utilisateur qui présente le fichier, s'il y en a
un.

**Les bindings sont tous `priority=True`** : un `DataTable` étouffe les touches
avant le système de bindings (voir l'avertissement en tête de `tui/mixins.py`).

### 14.1 Écran Browser — navigation fichiers

```
┌─ IRIS ENCODE ────────────────────────────────── 14:22 ─┐
│ D:\Videos  ·  2/4 sélectionnés  ·  Col : Résol.  </>   │
│                                                         │
│ F4 🎬 series_basic 🎬    • 1080p 2200k  ·  4K→1080p     │
│      HD audio non                                       │
│ ⏳ Analyse en cours… 2 / 4                              │
├─ ──┬─ Fichier ──────┬─ Taille ─┬─ Résol. ──┬─ Durée ─┬─ Débit ─┬─ Codec ─┬─ Dolby V. ─┬─ Décision ─┬─ Estim. (Δ%) ─┬─ ETA ─┬─ Audio ─────┤
│    │ 📁 Films/      │          │           │         │         │         │            │            │               │                │             │
│[x] │ 🎬 film1.mkv   │   8,4 Go │ 3840x2160 │ 2:05:12 │ 25000k  │  hevc   │  DV:P8.1   │  → HEVC    │ 2,1 Go (−75%) │     0:38:12    │ TrueHD 7.1  │
│[ ] │ 🎬 film2.mp4   │   1,1 Go │  720x480  │ 1:32:00 │   900k  │  h264   │  —         │  ← SKIP    │       —       │        —       │ AAC 2.0     │
│[x] │ 🎬 film3.avi   │   2,3 Go │ 1280x720  │ 0:52:00 │  3200k  │  vp9    │  —         │  → H264    │ 1,2 Go (−48%) │     0:04:51    │ AC3 5.1     │
├────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Space Sélect  a Tout  n Aucun  Enter Ouvrir  w Mode  t Pistes  v Visualiser  r Encoder le dossier  j Joindre  i Fiche  Ctrl+D Supprimer            │
│ Back Remonter  Home/End/PgUp/PgDn  F1 Aperçu  F2 Encoder  F4 Profil  F5 Gérer  Sh+Tab/Tab Col  < Rétrécir  > Élargir  F10 Quitter                  │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Touches

| Touche | Cible | Action |
|---|---|---|
| `↑` `↓` `PgUp` `PgDn` `Home` `End` | — | Navigation |
| `Espace` | fichier | Sélection unitaire |
| `A` / `N` | — | Tout / aucun — `A` saute les sorties de l'application |
| `↵` | dossier | Entrer |
| `↵` | fichier | Ouvre `TracksScreen` |
| `⌫` | — | Remonter au parent |
| `V` | fichier | Visualiser dans mpv |
| `Ctrl+D` | fichier | **Supprimer le fichier**, après confirmation |
| `F1` | sélection | Aperçu |
| `F2` | sélection | Encoder |
| `R` | dossier | Encoder le dossier (récursif) |
| `F4` | — | Choisir le profil actif |
| `F5` | — | Gérer les profils |
| `J` | sélection | **Joindre les parties cochées** en un fichier unique (§ 9bis) |
| `I` | fichier | Fiche du film : AlloCiné, `Tab` bascule sur IMDB |
| `F10` | — | Quitter |

**Une touche de fonction, un seul sens** (v0.8.9.18, UX-07). Sur tous les
écrans : `F1` dry-run, `F2` action principale (encoder ; joindre sur l'écran
de collage, valider un ancrage), `F3` muxer, `F4` profil, `F5` gérer les
profils, `F6` codec, `F7` débit, `F8` suppression de la source, `F9` piste
externe, `F10` quitter. Une action propre à un écran prend une lettre —
l'accueil `R`, `J`, `I`. `tests/test_touches.py` tient la table.
Les lettres `M` (Mesurer), `S` (Passer le fichier), `A` (Tout), `F`
(Forcer), `G` (Plages) et `O` (OpenSubtitles) n'ont qu'un sens dans toute
l'application (v0.8.9.19, UX-12).

`F1`/`F2` sans rien de coché : notification d'avertissement, qui dit comment
cocher (v0.8.9.11). Même chose pour `F2` du dry-run quand aucune ligne retenue
n'est à réencoder.

**Ligne forcée** (v0.8.9.12) — une ligne `SKIP` ou `STRIP_DV` cochée part en
réencodage par `force_skip_to_encode()`. `_row_cells()` rend alors la décision
forcée, en `bold dark_orange`, avec l'estimation et l'ETA qui vont avec ;
`_update_row_check()` redessine la ligne entière pour ces deux actions, et la
coche (`Espace`, `A`) le notifie. Une source Dolby Vision forcée sous un profil
`dolby_vision = "dv"` part en `ENCODE_DV` (§ 7.4) quand `peut_reencoder_en_dv`
l'accepte, au débit de la source ; sinon en copie du flux, suffixe `.dv-iris`
(v0.8.9.59).

**Retour d'un encodage** (v0.8.9.8) — `RunScreen` inscrit ses statuts dans
`app.lots_encodes` au montage. `BrowserScreen.on_screen_resume()` les consomme :
les sources réussies quittent la sélection (`sources_reussies()`), la vue est
relue. Un fichier en échec ou interrompu reste coché. Pendant un lot, la vue
n'est relue que lorsqu'une **nouvelle** réussite est apparue
(`_reussites_vues`) : un retour d'écran sans changement sur le disque ne
relance pas un ffprobe par fichier (v0.8.9.97, CR-74).

**La décision d'un fichier** (v0.8.9.97, IE-123) — l'accueil est le seul
propriétaire de ses `FileDecision`. L'écran des pistes reçoit une **copie**
(`deepcopy`) qui ne remplace la décision qu'au retour d'une sélection : `⌫`
n'en garde rien, pas même un profil changé par `F4` (CR-81) ; l'aperçu `F1`
travaille sur des copies, que seul `F2` met en file (CR-88). L'assistant,
parcours guidé, garde ses choix sur la décision elle-même ; la ligne est
redessinée à son retour (`_redessiner`, CR-87). Ce que l'utilisateur règle à la
main — profil propre au fichier, codec et débit, suppression de la source,
pistes greffées — est noté au retour de ces écrans dans un registre
(`decision.Reglages`, `reglages_explicites`, `BrowserScreen._retenir`) et
réappliqué après chaque `decide` du scan (`appliquer_reglages`), comme les
sélections de pistes : un rescan ne le perd plus (CR-74). La vidéo se compare à
la décision automatique du profil du fichier ; un profil supprimé entre-temps
rend la main au profil actif. Les fichiers confiés à la file ne se décochent
qu'une fois en file : renoncer au dossier de sortie ne décoche rien
(`app.encoder(…, apres=…)`, CR-76). Des options enregistrées depuis la gestion
des profils font relire le dossier au retour (CR-98).

**Nom de sortie annoncé** — l'assistant affiche `decision.sortie_prevue()` :
le nom que la file donnerait, numérotation comprise, **sans le figer** ; il ne
se fige qu'au lancement (`resoudre_sorties`). Un nom figé à l'étape 1 restait
`.mp4` après une greffe ASS qui imposait le Matroska, et ffmpeg refusait
(CR-84). Après un mux, l'assistant juge le résultat sur le rendu de
`MuxScreen` et le fichier que mkvmerge a écrit, pas sur la décision adoptée
(CR-15).

**Un SKIP muni de greffes est un mux** (v0.8.9.97, CR-82) — dans la file,
`_a_muxer(dec)` (SKIP, pistes externes, pas un titre de disque) lance
`RunScreen._muxer` : `build_mux_command` vers `output_path`, code 0 ou 1 de
mkvmerge accepté, sortie partielle effacée sur échec. Il finissait « ignoré »
sans rien écrire quand `F2` partait de l'écran des pistes.

#### Démarrage virtuel

L'application démarre en mode virtuel (`start_virtual=True`) : la première vue liste les
volumes disponibles (icône 💾), pas un chemin fixe.

#### Colonnes

| Colonne | Clé config | Contenu |
|---|---|---|
| *(check)* | — | `[x]` / `[ ]` |
| Fichier | `fichier` | 🎬 nom (tronqué avec `…`) |
| Taille | `taille` | taille source |
| Résolution | `resolution` | `WxH` |
| Durée | `duree` | `H:MM:SS` |
| Débit | `debit` | `NNNNk` |
| Codec | `codec` | codec vidéo |
| Dolby V. | `dolby_vision` | `DV:P8.1` ou `—` |
| Décision | `decision` | `→ HEVC` (coloré) |
| Estim. (Δ%) | `estim` | taille de sortie estimée + delta |
| ETA | `temps_estim` | durée d'encodage estimée |
| Audio | `audio` | résumé des pistes conservées |

Code couleur décision : table unique `core.decision.Emphase` (§ 8.3) — le cas
ordinaire ne porte aucune couleur, le vert dit « sans réencodage », le
`dark_orange` gras est réservé aux alertes.

**La colonne Estim. porte un dégradé continu** centré sur le gris : tant que
la cellule affiche un écart de 5 % au plus (valeur arrondie, `_SEUIL_NEUTRE`),
elle est grise (`rgb(138,138,138)`). Au-delà, la teinte se lit d'emblée : un
gain part du vert clair (`rgb(120,200,120)`) vers le vert vif
(`rgb(0,230,60)`), atteint à −100 % ; une sortie plus grosse que sa source part
de l'orange clair (`rgb(255,190,90)`) vers l'orange sombre des alertes
(`rgb(255,135,0)`), atteint à +100 % et conservé au-delà. La progression entre
le seuil et la borne est **logarithmique** (`log1p(20·x) / log1p(20)`,
`_COURBURE`) : un écart de −30 % fait déjà plus de la moitié du chemin.
Interpolation RGB, bornes `_DEGRADE_GAIN` / `_DEGRADE_PERTE`.

C'est une **exception assumée** à la table d'emphases : le vert y dit « traité
sans réencodage », et il dit ici « la sortie est plus petite ». Sur une même
ligne, le vert de la colonne Décision et celui d'Estim ne parlent donc pas de la
même chose. L'exception vit dans une seule fonction, `_teinte_estimation()` ;
aucune autre couleur n'est écrite en dur dans cet écran.

Une ligne dont la vidéo est **recopiée** — remux, retrait de RPU, Dolby Vision
conservé — reste hors du dégradé : sa sortie pèsera la taille de la source,
l'écart vaut zéro ; elle s'affiche en `dim`, sans pourcentage, pour un cas où
rien n'est recalculé. Le prédicat
`_sortie_recopiee()` sert à la fois l'estimation et la couleur.

#### Les sorties de l'application restent visibles

Jusqu'à la v0.8.8.3, `deja_produit()` écartait de la vue tout fichier portant un
suffixe d'encodage : un film encodé la veille disparaissait de l'écran, et rien
ne distinguait « déjà produit » de « jamais existé ». `FileNavigator.list_videos()`
ne filtre plus — la ligne est là, **grisée d'un bloc**, toutes ses colonnes
renseignées comme les autres (le ffprobe est fait ; le prix est un temps
d'analyse doublé sur un dossier entièrement traité).

La colonne Décision garde la **vraie** décision, `→ HEVC` ou `← SKIP` : la ligne
part à l'encodage comme n'importe quelle autre, et un libellé « déjà traité »
mentirait sur le contenu du lot. Seul le gris dit « ceci vient d'ici ». La case
à cocher n'est pas grisée — sinon on ne verrait plus si la ligne est prise.

`Espace` la coche, `F1`/`F2` l'encodent. Seul `A` (tout sélectionner) l'ignore :
il coche « tout ce qu'il y a à faire ici », et une sortie n'en est pas. Le
filtre reste entier dans `core/scanner.py`, qui alimente le scan récursif et les
lots automatiques — c'est là qu'il protégeait vraiment (§ 15.2).

#### Suppression d'un fichier (`Ctrl+D`)

Disponible uniquement sur une ligne **fichier**. Ouvre `DeleteConfirmModal` (nom, taille,
dossier, annexes Jellyfin qui partiront avec lui, avertissement), focus initial sur
*Annuler*.

À la confirmation, le fichier est **définitivement supprimé** (pas de corbeille), avec
ses annexes Jellyfin (§ 14.7, mêmes règles qu'après un encodage), et sa
ligne retirée sans re-scanner le dossier. Si le dossier se vide, la vue est reconstruite
pour afficher le placeholder.

> Sous Windows, mpv garde un verrou sur un fichier ouvert : enchaîner `V` puis `Ctrl+D`
> sans fermer mpv fait échouer la suppression. Le message d'erreur est affiché en barre
> d'état.

#### Barre de profil actif (2 lignes)

**Ligne 1 :** `[F4]` + `🎬 NOM_PROFIL 🎬` · `1080p Nk` · `4K→1080p` ou `4K Nk` (vert) ·
`DV hdr10/dv/sdr` (coloré) · `preset`
**Ligne 2 :** `HD audio oui/non` · `⚠ SUPPRESSION` si `delete_source`

Couleurs DV : `hdr10` → jaune · `dv` → vert · `sdr` → `bold dark_orange`.

#### Scan progressif

Un pool de 4 workers scanne les fichiers en parallèle (ffprobe est I/O bound). La notice
affiche `⏳ Analyse en cours… 3 / 12`. Un compteur d'époque invalide les résultats d'un
scan devenu obsolète si l'utilisateur navigue entre-temps. Une fois terminé, la notice
affiche le chemin du fichier survolé.

#### Encoder le dossier (`R`)

Disponible uniquement sur un **dossier**. `RecursiveConfirmModal` affiche le répertoire
et le profil actif, puis lance un scan récursif illimité et un aperçu sur les fichiers à
encoder (SKIP exclus). Décisions automatiques, aucune sélection de pistes. La barre
d'état compte les fichiers analysés (« Analyzing… n / total », § 15.2).

### 14.2 Écran Tracks — pistes et décision vidéo

Un `DataTable` à quatre sections : **VIDÉO**, **AUDIO**, **SOUS-TITRES**, **EXTERNES**.

```
┌─ Pistes — film1.mkv    Profil: [cinema_4k_hd] · Audio: 2/3 · Sous-titres: 1/1 ──┐
│ ── VIDÉO ──────────────────────────────────────────────────────────────────────  │
│ ✎ HEVC  0:v:0  hevc  3840x2160  DV:P8.1   ◄→ HEVC► · ◄12000 kbps► · ◄HDR10►     │
│ ── AUDIO ──────────────────────────────────────────────────────────────────────  │
│ [x]  0:a:0 ⚑   truehd  7.1  fre  défaut          → copie                         │
│ [x]  0:a:1     ac3     5.1  fre  sélectionné     → copie                         │
│ [ ]  0:a:2     dts     5.1  deu  exclu           —                               │
│ ── SOUS-TITRES ────────────────────────────────────────────────────────────────  │
│ [x]  0:s:0   hdmv_pgs  image  fre  défaut        → copie MKV                     │
│ ── EXTERNES ───────────────────────────────────────────────────────────────────  │
│ [x]  film.VF.mka  ac3  5.1  fre  « VF »          −2450 ms (mesuré)               │
│ [ ✓ ] Valider la sélection                                                        │
├──────────────────────────────────────────────────────────────────────────────────┤
│ Space Sélect  Enter Valider  F1 Aperçu  F2 Encoder  F4 Profil  F6 Codec F7 Débit │
│ F8 Suppr./garder source   F9 Piste externe   Back Retour   F10 Quitter           │
└──────────────────────────────────────────────────────────────────────────────────┘
```

#### Ligne VIDÉO — édition inline

Champs éditables : **action** (codec), **bitrate**, **DV**, **original**
(`delete_source`).

| Raccourci | Effet |
|---|---|
| `←` / `→` | Cycle entre les champs éditables (◄ actif ►) |
| `+` / `-` | Change la valeur du champ actif |
| `↵` | Ouvre `ValuePickerScreen` pour le champ actif |
| `F6` | Picker codec |
| `F7` | Picker débit |
| `F8` | Toggle suppression / conservation de la source |

| Champ | Valeurs |
|---|---|
| action | ENCODE_HEVC · ENCODE_H264 · ENCODE_AV1 · SKIP |
| bitrate | 500 … 12000k |
| bitrate (AV1) | 300 … 6000k |
| dv | HDR10 · DV · SDR |
| orig | Profil (suivre) · Garder · Supprimer |

Un `✎` dans la colonne check signale un override actif. La colonne **Source** affiche le
sous-profil DV connu. ⚠ si HDR10 quality demandé sans `dovi_tool`.

#### Pistes AUDIO / SOUS-TITRES

`Espace` bascule la sélection (piste audio 0 verrouillée — ⚑). Décision affichée par
piste : `→ copie` / `→ aac 192k` / `—`. Sous-titres : `image` → `→ copie MKV`,
`texte` → `→ copie MP4`. Toutes sélectionnées par défaut.

#### `F9` — ajouter une piste externe

Ouvre `DonorPickerScreen` (§ 14.3). Au retour, les pistes choisies rejoignent la section
EXTERNES et l'écran de recalage s'ouvre.

### 14.3 Écran DonorPicker — choix du donneur

Deux temps dans le même écran :

1. **Fichier donneur** — navigation dans le dossier courant. Le fichier cible est exclu
   de la liste.
2. **Pistes du donneur** — listées via `mkvmerge -J`. `Espace` sélectionne, `↵` valide.
   Sélection multiple dans le même fichier ; plusieurs donneurs s'enchaînent sans quitter
   l'écran.

### 14.4 Écran Sync — recalage

Une piste externe = une ligne. Champs éditables par ligne : **décalage**, **étirement**,
**langue**, **nom**, **défaut**, **forcé**.

**Le bandeau porte deux choses distinctes.** Sa première ligne dit ce que sait faire le
champ sous le curseur, et ne s'efface jamais ; les suivantes portent le message du
moment. Les deux partageaient un seul emplacement, et le message gagnait : les touches
d'édition disparaissaient sur un avertissement de langue — l'état d'arrivée quand une
piste en manque — comme sur un compte rendu de mesure, c'est-à-dire dans les deux
situations où l'on vient justement régler une valeur. Le pied de page ne les porte pas
non plus : elles y sont `show=False` faute de place. Une capacité réelle ne se signalait
donc nulle part, et a été rapportée comme absente.

La ligne est propre au champ : seul le décalage a trois pas, les autres font défiler
leurs valeurs — y annoncer un pas en millisecondes serait faux.

| Touche | Action |
|---|---|
| `←` / `→` | Champ précédent / suivant |
| `Ctrl+↑` / `Ctrl+↓` | ±10 ms sur le champ décalage — pas fin, pour finir d'approcher une mesure |
| `+` / `-` | ±100 ms sur le champ décalage |
| `Shift+↑` / `Shift+↓` | ±1 s |
| `↵` | Ouvre la liste des valeurs du champ courant |
| `M` | **Mesure automatique** (§ 10) |
| `F` | Applique le candidat mesuré |
| `R` | **Point de repère** — mesure guidée par une réplique, quand la mesure libre ne conclut pas |
| `G` | **Plages détectées** (§ 10.4) — lecture seule |
| `P` | **Applique les plages** à la piste sous le curseur — `.srt` réécrit (§ 10.5) ou piste audio rallongée et réencodée (§ 10.6). Le fichier produit devient la source, avec un décalage nul |
| `V` | **Visualiser dans mpv**, piste greffée et décalage appliqué |
| `K` | **Extrait de contrôle** réellement muxé |
| `C` | Copie le décalage d'une autre piste externe → `sync_origin = COPIED` |
| `D` | Retire la piste |
| `F1` | Aperçu |
| `F2` | Encoder (ffmpeg absorbe les pistes, § 9.6) |
| `F3` | **Muxer** (mkvmerge) |
| `F9` | Ajouter une autre piste |
| `⌫` / `Esc` | Retour sans muxer — l'état reste dans le `FileDecision` |

> **Pourquoi `C` compte.** En ajoutant une VF *et* ses sous-titres français, les
> sous-titres ont presque toujours été écrits sur le timing du donneur : leur bon
> décalage *est* celui de la piste audio. Une mesure indépendante contre la vidéo cible
> serait du travail perdu, et souvent moins fiable.

**Visualisation (`V`)** — mpv s'ouvre sur un passage dialogué (25 % du film à défaut de
mieux), piste greffée et décalage appliqué. L'ajustement fin se fait aux touches mpv,
qui affiche la valeur en OSD :

```
audio        Ctrl++  /  Ctrl+-     pas de 100 ms
sous-titres  z  /  Z               pas de 100 ms
```

**Extrait (`K`)** — 60 s réellement passées par mkvmerge. Seule façon honnête de vérifier
un facteur d'étirement, que mpv ne prévisualise pas (`audio-delay` ne fait qu'un décalage
constant). Deux fenêtres quand un étirement est en jeu, la dérive s'accumulant.

### 14.5 Écran MuxRun — exécution du remux

Progression lue sur le protocole `--gui-mode` de mkvmerge. À la fin :

- `F1` — dry-run sur le fichier produit
- `F2` — encoder le fichier produit
- `⌫` / `Esc` — retour

Le fichier muxé devient le fichier de travail (§ 9.7). Une sortie partielle est supprimée
si le mux échoue.

### 14.5bis Écran Join — collage des parties

Ouvert par `F6` depuis l'accueil, sur les fichiers cochés (deux au minimum). Il ne
rescanne rien : les `VideoInfo` sont déjà en mémoire côté browser.

```
┌─ IRIS ENCODE ────────────────────────────────── 14:22 ─┐
│ Jonction — 3 parties ── Film.join-iris.mkv              │
├─ # ─┬─ Fichier ──────────┬─ Durée ─┬─ Pistes ─┬─ Jonction ─────┤
│  1  │ Film part1.mkv     │ 1:04:12 │ V+2A+1S  │ référence      │
│  2  │ Film part2.mkv     │ 0:58:47 │ V+2A+1S  │ ✓              │
│  3  │ Film part10.mkv    │ 0:41:03 │ V+2A+0S  │ ✓ avec réserve │
├─────────────────────────────────────────────────────────────────┤
│ Durée attendue du tout : 2:44:02                                │
│ Sortie : Film.join-iris.mkv                                     │
│ Jonction ███████████████████████░░░░░░░░░░░░  62%               │
└─────────────────────────────────────────────────────────────────┘
```

#### Touches

| Touche | Action |
|---|---|
| `Ctrl+↑` / `Ctrl+↓` | Déplace la partie sous le curseur d'un rang |
| `F2` | Joindre — lance la jonction |
| `⌫` / `Esc` | Retour. Une jonction en cours est interrompue, son fichier partiel effacé |
| `Ctrl+Début` | Accueil |

L'ordre proposé vient de `ordre_naturel()` ; le tableau est ce qui sera joint. La colonne
**Jonction** dit, partie par partie, si elle s'apparie sur la référence — le détail du
refus ou de la réserve s'affiche sous le tableau.

**La colonne du nom reprend la largeur réglée sur l'accueil** (`get_column_widths()`,
clé `fichier`), planchers compris : l'écran montre les mêmes fichiers, une largeur
propre y tronquerait des noms qui se lisent entiers dans le navigateur. Les autres
colonnes portent des libellés bornés et gardent une largeur fixe.

`F2` est refusé sur un blocage (§ 9bis.3) ou si le fichier de sortie existe déjà : le
collage n'écrase jamais rien.

### 14.6 Écran Aperçu (`DryrunScreen`)

Prévisualise les décisions de tous les fichiers sélectionnés, sans écriture disque.

**Colonnes :** Fichier · Taille · Durée · Estim. (Δ%) · Action · Conteneur · DV ·
Débit cible · Résolution · Audio

**Barre de bilan :**

```
À encoder : HEVC 3  ·  H264 1  ·  SKIP 2
·  Source : 12,4 Go  →  Estimé : 3,2 Go (−74%)
```

`Espace` désélectionne un fichier, `F6`/`F7` éditent codec et débit avant lancement,
`F2` passe à l'écran Encodage (SKIP exclus). `↵` n'y est pas liée (v0.8.9.6) :
partout ailleurs elle ouvre ou valide, ici elle lançait l'encodage sans confirmation.

### 14.7 Écran Encodage (`RunScreen`)

```
┌─ Encodage — 5 fichiers · Profil : cinema_4k_basic ──────────── Global : 42% ─┐
│  ✓  film1.mkv    HEVC 8000k → HDR10      ✓ SUCCÈS                            │
│     ████████████████████████████████████                                      │
│  ▶  film3.avi    H264 3200k               38%                                │
│     █████████░░░░░░░░░░░░░░░                                                  │
│  ○  film4.mkv    HEVC 12000k → DV        en attente                          │
│  [▶ Démarrer] / [⏸ Pause]   ████████████░░░░░░░░░░░░  42%                    │
├───────────────────────────────────────────────────────────────────────────────┤
│ $ ffmpeg -hwaccel cuda -i "film3.avi" -c:v h264_nvenc …                       │
│ frame= 1094 fps= 89 q=27.0 size= 36864kB time=00:00:45.58 speed=3.71x         │
└───────────────────────────────────────────────────────────────────────────────┘
```

- Une ligne par fichier : état (○ / ▶ / ✓ / ✗), nom, action, pourcentage
- Barre individuelle sous le fichier actif, barre globale en pied de liste
- Zone basse : commande ffmpeg complète + dernière ligne de retour (live)
- `⏸ Pause` suspend le processus (multiplateforme)
- Suppression source après succès selon `delete_source` (ou override par fichier),
  par une seule fonction pour les trois chemins — passe principale, retrait et
  réencodage du Dolby Vision (`_supprimer_source`, v0.8.9.106, CR-54) : jamais un
  titre de disque, jamais un fichier abandonné par `S`. Les chemins DV refaisaient
  leur propre règle : ils effaçaient le `.m2ts` d'un titre, oubliaient les annexes,
  et supprimaient avant de regarder `S` — la sortie abandonnée partait ensuite.
  Ses **annexes Jellyfin** partent avec elle (`core/annexes.py`, v0.8.9.86) :
  `<nom>.nfo` et `<nom>-*.jpg|jpeg|png|webp`, le format observé sur la
  bibliothèque. Restent : les fichiers du dossier (`season.nfo`, `poster.jpg`,
  `movie.nfo`), les sous-titres externes (`<nom>.fr.srt`, parfois seul
  exemplaire), la sortie et ses propres annexes. Un fichier qui répond aussi
  au nom plus long d'une autre vidéo du dossier est à celle-ci. Pas de motif
  `<nom>.*` : la sortie `<nom>.hevc-iris.mkv` y répondrait.
- En cas d'erreur : fichier marqué ✗, les suivants continuent, source conservée
- **La file d'encodage** (v0.8.9.34, IE-100). L'écran **est** la file, et il
  vit dans son propre mode Textual (`MODE_ENCODAGES`) ; la navigation a le
  sien (`MODE_FICHIERS`, où l'application démarre — Textual ne sait pas
  revenir au mode `_default`). Changer de mode suspend un écran sans le
  démonter : le worker et ffmpeg continuent. `F12` (liaison de l'application)
  bascule — `F11` est prise par Windows Terminal. Toute demande d'encodage
  passe par `IrisEncodeApp.encoder()` : doublon de source refusé, décision
  **copiée** (réglages figés à l'ajout), puis `RunScreen.ajouter()` si un lot
  tourne, sinon un nouveau lot qui s'affiche. Hors accueil,
  `confier_a_la_file()` ramène d'abord la navigation à la liste des fichiers.
  Les fichiers cochés partent dans l'ordre alphabétique du tableau
  (`BrowserScreen._cochees`, même tri que `list_videos`, v0.8.9.58) ; un
  ajout à un lot en cours se place à la suite.
  L'ajout et le choix du fichier suivant se font sous un verrou : sans lui, un
  ajout tombé entre « plus rien » et « lot fini » serait perdu. Aucun appel au
  fil principal sous verrou. `⌫`, `Esc` et `Ctrl+Home` rendent la navigation
  **sans rien arrêter** ; `X` arrête tout après confirmation. Le bilan d'un lot
  fini reste jusqu'à ce qu'il ait été vu, puis le mode est retiré à la sortie
  de la vue (`_liberer_lot`). `Ctrl+D` refuse un fichier en file ; `F10`
  annonce les fichiers en attente et arrête le lot, même hors de la pile
  affichée.
- **Réordonner la file** (v0.8.9.36) : `Ctrl+↑/↓` échange deux fichiers **en
  attente**, `Suppr` en retire un ; le fichier en cours et les fichiers finis
  ne bougent pas (message). Sous le même verrou que le choix du suivant : le
  worker prend toujours `_current_idx + 1`, et seules des lignes au-delà
  changent de place.
- **Le bandeau de la file** (v0.8.9.35) : `Entete.format_title` ajoute au
  titre centré l'état rendu par `IrisEncodeApp.etat_file()`, rafraîchi chaque
  seconde — « F12 Encodages en cours · 1/3 · 42 % », « F12 Lot terminé », et
  « F12 Fichiers » depuis la vue des encodages. Vide sans lot.
- **Arrêter se confirme** (v0.8.9.5, par `X` depuis la v0.8.9.34) : une
  `ConfirmModal` (« Arrêter » / « Continuer », focus sur Continuer).
  Confirmer lève `_abandon` et arrête le processus en cours, ffmpeg ou
  mkvmerge. Tout démarrage passe par `_demarrer()`, qui publie le processus
  **après** l'avoir lancé et relit le drapeau ensuite : un arrêt survenu entre
  deux étapes coupe l'étape suivante dès son départ, et `_encode_next()` ne
  démarre plus rien. `_arreter()` attend la sortie du processus puis efface la
  sortie du fichier en cours, sauf code 0 (fini juste avant l'arrêt) — pas en
  fin de boucle : le worker suivant d'un écran dépilé ne démarre pas toujours.
  Lot terminé : aucune confirmation.
- **La veille bloquée pendant les traitements** (v0.8.9.43) —
  `core/veille.py`. Windows met la machine en veille sur inactivité sans voir
  ffmpeg travailler. `GardeVeille` pose une demande d'alimentation
  (`PowerCreateRequest` + `PowerSetRequest(PowerRequestSystemRequired)`) au
  motif lisible dans `powercfg /requests` (« IRIS ENCODE : encodage, mesure en
  cours »). **Pas `SetThreadExecutionState`** : son état appartient au thread
  appelant, et `_encode_next` est un worker qui se relance à chaque fichier —
  la demande tomberait entre deux fichiers. Elle ne sert qu'en secours, depuis
  le fil principal. `IrisEncodeApp.surveiller_veille()` relève l'état toutes
  les 5 s plutôt que de compter entrées et sorties qu'un chemin d'erreur
  déséquilibrerait : un lot non terminé, ou un worker de `_NATURES` — les
  mêmes que `_TRAVAUX`, ce que `F10` annonce interrompre (test). `maintenir()`
  est idempotent ; un nouveau motif pose la nouvelle demande **avant** de
  retirer l'ancienne ; une demande refusée n'est pas retentée au relevé
  suivant. Le processus mort, Windows la retire : rien ne peut laisser la
  machine éveillée. Hors de portée : la veille demandée à la main, la
  batterie critique, `powercfg /requestsoverride`. `ES_DISPLAY_REQUIRED`
  n'est pas demandé : l'écran s'éteint. L'en-tête affiche « ☾ veille
  bloquée » (`etat_veille()`), à droite de l'état de la file : une mesure
  sans lot la bloque aussi. Option `[energie] empecher_veille`, vraie par
  défaut. Hors Windows, `disponible()` est faux et rien n'est fait.
- **Après le lot** (v0.8.9.43) — `E` arme l'action de `[energie] action_fin`
  (veille, veille prolongée, arrêt). **« Ne rien faire » (`rien`) est le
  défaut** (v0.8.9.53) : `E` n'arme alors rien et renvoie aux options ;
  choisi pendant un lot déjà coché, il désarme (`fin_prevue()` faux, pas de
  `FinDeLotModal`, `executer_fin("rien")` n'appelle pas le système). `RunScreen.apres_lot` part de `False` à
  chaque lot, jamais hérité. Un lot fini **sans abandon** appelle
  `armer_fin_de_lot()` ; un lot arrêté par `X` ou `F10` ne déclenche rien.
  L'action attend que `natures_en_cours()` soit vide — au plus un relevé
  après la fin, puisque le worker du dernier fichier vit encore quand le lot
  se dit fini —, puis `FinDeLotModal` décompte 60 s, focus sur Annuler.
  Annuler ou `Esc` : rien. Un nouveau lot efface une action en attente.
  `executer_fin()` relâche la demande, puis : veille par
  `SetSuspendState(FALSE, …)` après activation de `SeShutdownPrivilege`,
  veille prolongée par `shutdown /h`, arrêt par `shutdown /s /t 0`. Un refus
  (veille S3 absente en Modern Standby, hibernation désactivée) s'affiche
  en notification.
- **Fin du lot** (v0.8.9.10) : le pied ne garde que la navigation (Pause et
  Passer n'ont plus d'objet), la zone de commande fait le bilan — réussis, en
  échec, ignorés, puis le chemin des sorties (six au plus, le reste compté).
  L'état d'une ligne n'a plus de symbole (« terminé », « échec : … ») : il est
  déjà dans la colonne d'icône.

**Source en lecture seule** (v0.8.9.92, IE-118) — un ISO monté, un partage
sans droit d'écriture. `app.encoder()`, seule porte de la file, passe les
décisions à `decision.sorties_bloquees()` : celles qui écrivent quelque chose
(pas un SKIP sans piste externe), sans `output_dir` ni nom figé, dont le
dossier refuse un fichier d'essai (`dossier_inscriptible()`, un essai par
dossier ; ni `os.access`, qui ne lit que l'attribut sous Windows, ni
`tempfile`, qui réessaie dix mille noms sur un refus). S'il y en a,
`OutputDirScreen` s'ouvre sur `config.get_output_dir()` — le réglage
`[app] output_dir` s'il existe, sinon `~/Videos`, sinon `~` : `↵` sur la
première ligne (« Écrire dans ce dossier ») le retient, après un essai
d'écriture ; les autres lignes y naviguent, `⌫` remonte jusqu'aux volumes,
`Esc` ne met rien en file. Le dossier choisi va dans `FileDecision.output_dir`
des décisions bloquées ; `dossier_sortie` (lui, ou le dossier de la source)
porte la sortie **et** les intermédiaires de `RunScreen` (`.iris_audio.mka`,
`.iris_st*.srt`, flux et RPU Dolby Vision). Le mux et le collage, qui écrivent
à côté de la source, refusent un dossier en lecture seule avec un message.

### 14.8 Écran Config — gestion des profils

**Options** (v0.8.9.43) — `U` ouvre `OptionsScreen` : la case « Bloquer la
mise en veille pendant les traitements » et le choix de l'action d'après lot,
écrits dans `[energie]` par `Ctrl+S` (`config.set_energie`), `Esc` annule.
Enregistrer relève aussitôt l'état (`surveiller_veille`) : décocher relâche
la machine sans attendre. `O` aurait été plus parlant, mais il est
OpenSubtitles chez le donneur (UX-12). Une action inconnue dans le fichier
vaut `rien` (v0.8.9.53 ; `veille` avant). Section « Dossier de sortie »
(v0.8.9.92) : le dossier proposé pour une source en lecture seule (§ 14.7),
changé par `OutputDirScreen`, écrit dans `[app] output_dir` au `Ctrl+S`.
Section « Titres de disque » (v0.8.9.94, étendue au DVD en v0.8.9.95) : la durée minimale d'un titre listé,
en minutes (§ 15.5), écrite dans `[app] min_title_minutes` ; une saisie non
numérique est ignorée.

**Clés d'API** (v0.8.9.37, IE-101) — `K` ouvre `ClesScreen` pour tous les
services de `core/cles.py` (OpenSubtitles : clé, identifiant, mot de passe
masqué ; OMDb : clé), champs pré-remplis. Au lancement, hors mode sans
terminal, `IrisEncodeApp.demander_cles()` l'ouvre pour les services dont un
champ **requis** manque (la clé ; le compte OpenSubtitles ne l'est pas) et qui
ne sont pas dans `[cles] ne_plus_demander`. Chaque service : un bouton qui
ouvre sa page (`webbrowser`), une case « Ne plus demander » (au lancement
seulement), un état. Les boutons **Vérifier et enregistrer** (`Ctrl+S`) et
**Plus tard** (`Échap`) restent sous la zone des services, qui défile si le
terminal est trop bas (`on_resize` borne sa hauteur ; tout tient dès 40
lignes). `Ctrl+S` vérifie chaque service modifié, dans un worker,
avant d'enregistrer : OMDb par une requête (`401` = clé refusée) ;
OpenSubtitles par la **connexion**, seul appel qui contrôle la clé — la
recherche accepte une clé inventée *(mesuré)*. Sans compte, la connexion se
fait avec un compte inventé : `401` prouve la clé, sans consommer les
tentatives d'un compte réel. Un service refusé n'est pas enregistré et la
fenêtre reste ouverte ; une clé inchangée n'est pas re-vérifiée.

Tous les profils sont éditables et supprimables (`D` / `Suppr`, avec
confirmation) — ils viennent tous de `profiles.toml`, qui fait foi. Seule
exception : le dernier de la liste, dont la suppression est refusée par un
message explicite. Un nouveau profil (`N`) part des réglages du profil actif.
**Copier** (`C`, v0.8.9.52) ouvre le même formulaire de création avec les
réglages du profil sous le curseur et un nom libre proposé par
`nom_de_copie()` (`<nom>_copie`, puis `_copie2`…, tenu dans 32 caractères).
Le champ **Nom** n'est saisissable qu'à la création : renommer se fait dans
`profiles.toml`. Une création refuse un nom déjà pris (`ProfileForm.validate`,
`ids_pris`) : avant, `_on_profile_saved` voyait un profil existant et y
fusionnait les valeurs saisies, sans rien dire.

**Valeur hors liste** (v0.8.9.7) — un débit que la liste ne propose pas
(`serie_basic` : 3500k en 4K) s'y ajoute à sa place (`_avec_valeur()`), au lieu
de laisser le champ vide. La sentinelle « rien de choisi » est `Select.NULL`
sous Textual 8 (`Select.BLANK` n'y vaut que `False`) : `_est_vide()` teste les
deux. Sans cela, le formulaire affichait « Select.NULLk » et `dump()` rendait
`Select.NULL`, enregistré dans le profil en mémoire.

Le formulaire `ProfileForm` est organisé en **six sections**, chacune suivie
d'une ligne qui énonce **la conséquence des valeurs choisies** — recalculée à
chaque changement, pas un texte d'aide figé :

| Section | Champs | Ce que la conséquence annonce |
|---|---|---|
| Quand réencoder | seuils 720p / 1080p / 4K, `keep_4k` | les seuils en clair, et le sort d'une source 4K |
| Comment encoder | `preset_encoder` | qu'il ne concerne que les fichiers réencodés |
| Dolby Vision | `dolby_vision`, `hdr10_quality` | retrait par remux, conservation, ou tone mapping ; l'ordre de grandeur du mode `quality` |
| Audio sans perte | choix unique (voir ci-dessous) | ce que devient une piste TrueHD, et le conteneur imposé |
| Autres pistes audio | langues, forfaits, `audio_copy_compatible` | si les pistes déjà compatibles sont recopiées |
| Fichier source | `delete_source` | l'irréversibilité, en style d'alerte |

**Le couple audio sans perte ne peut plus se contredire.** `preserve_hd_audio`
et `audio_hd_codec` étaient deux réglages indépendants dont l'un l'emportait en
silence : un profil pouvait porter « copier sans perte » *et* « transcoder en
E-AC3 », sans que rien n'indique lequel gagnait. L'écran n'expose plus qu'un
choix à quatre branches, traduit en couple à l'écriture :

| Branche affichée | `preserve_hd_audio` | `audio_hd_codec` |
|---|---|---|
| copier telles quelles | `true` | `none` |
| → E-AC3 au débit de la source | `false` | `eac3` |
| → AC3 au débit de la source | `false` | `ac3` |
| → forfait 5.1 / 7.1 | `false` | `none` |

Les deux clés restent dans `profiles.toml` : le moteur est inchangé, et un
profil écrit avant cet écran reste lisible. Un couple contradictoire hérité
s'affiche sur la branche **qui décrit ce qui se passe réellement** — la copie,
puisqu'elle l'emporte dans `decide_audio` — et non sur l'intention qu'exprimait
le codec.

### 14.9 Sélection de profil — `ProfilePickerScreen`

Vraie table : Profil · 1080p · 4K · DV · Preset · HD audio · Source. Profil actif marqué
`✓`, valeurs DV colorées, `⚠ suppr.` sur les profils qui suppriment la source. Le
callback renvoie l'**id** du profil (plus robuste qu'un index). Utilisé par Browser (F4)
et TracksScreen (F4). Largeur du panneau : somme des colonnes, plus 2 par colonne
(`cell_padding=1` de chaque côté), 6 pour bordure et padding, 2 pour une barre de
défilement (v0.8.9.52 ; à 1 par colonne, `⚠ suppr.` sortait tronqué).

### 14.11 Retour à l'accueil — `Ctrl+Home`

Traiter plusieurs fichiers d'affilée revenait à remonter les écrans un par un.
`Ctrl+Home` dépile jusqu'au browser, depuis les sept écrans non modaux :
dry-run, run, mux, assistant, config, pistes et recalage. Pistes, recalage
et run tant qu'un encodage tourne confirment d'abord (§ 14.7).

**L'accueil, c'est la liste des volumes** (v0.8.9.3) — la racine, pas le
dossier de travail. Après le dépilage, `retour_accueil()` appelle
`BrowserScreen.action_accueil()`, qui passe par
`FileNavigator.aller_aux_volumes()` et vide la sélection. Le browser porte
lui-même le binding : `Ctrl+Home` y ramène aussi aux volumes. Entrer dans un
volume depuis cette liste n'empile pas le dossier précédent — `⌫` à la racine
du volume retombe sur les volumes.

**Pourquoi pas `Home`** — elle appartient à la navigation dans les tables
(`TableNavMixin`, `FOOTER_NAV`), et le mixin l'intercepte en `on_key` avant que
les bindings soient consultés. Lui donner un second sens aurait cassé le premier.

**Tous les bindings sont `priority=True`** : un `DataTable` étouffe la touche
avant le système de bindings. Sans cela, la touche ne fait rien sur les écrans
qui affichent une table — c'est-à-dire presque tous.

**Deux écrans confirment.** Le dépilage ne rend aucun résultat : les rappels des
écrans traversés ne sont pas appelés. C'est sans conséquence pour ceux qui n'ont
rien à rendre, mais les pistes et le recalage portent un travail non validé —
une sélection, une greffe, une mesure de plusieurs minutes. Ceux-là passent par
`ConfirmModal` avant de le perdre.

Sans accueil dans la pile, `retour_accueil()` ne touche à rien : mieux vaut ne
rien faire que de vider la pile jusqu'à l'écran par défaut.

### 14.10 Modales de confirmation

| Modale | Déclencheur | Focus initial |
|---|---|---|
| `QuitConfirmScreen` | `F10` / `Ctrl+C` | Annuler — le corps liste ce qui tourne, que quitter arrête (v0.8.9.9) |
| `DeleteConfirmModal` | `Ctrl+D` (browser) | Annuler |
| `RecursiveConfirmModal` | `R` (browser, dossier) | Confirmer |
| Suppression de profil | `D` (config) | Annuler |

Toutes dérivent de `ConfirmModal`. Le focus initial part sur *Annuler* dès que
l'opération est destructive.

---

## 15. Scanner — `core/scanner.py`

**Langues complétées** (v0.8.9.93, IE-119) — sur un `.m2ts` / `.mts` dont une
piste n'a pas de langue, `_completer_langues` appelle `muxer.identify`
(`mkvmerge -J`, qui lit les `.clpi` du disque) et reporte les langues par PID
(`IdentifiedTrack.number`) ; une langue lue par ffprobe n'est jamais remplacée,
mkvmerge absent ne change rien. Une piste complétée porte
`langue_completee = True` : `build_command` écrit pour elle
`-metadata:s:a:N language=…` (ou `s:s:N`), sans quoi la sortie n'en aurait
aucune. Les chemins par mkvmerge (retrait et réencodage Dolby Vision) relisent
les `.clpi` eux-mêmes.

**Extensions** — `SUPPORTED_EXTENSIONS` : `.mp4 .avi .mkv .mov .wmv .flv .webm
.m4v .3gp`, et depuis la v0.8.9.92 (IE-118) les flux MPEG `.ts .m2ts .mts .mpg
.mpeg .vob`. Seule liste des vidéos : le navigateur, le mode récursif, les
annexes et le choix du donneur la lisent (`DONOR_EXTS` l'étend des pistes
isolées). Le conteneur de sortie n'en dépend pas (§ 8.6).

### 15.1 `VideoInfo`

`bitrate` porte le débit du **flux vidéo**, jamais celui du conteneur.
`_video_bitrate()` le résout dans cet ordre :

1. `bit_rate` du flux vidéo — presque toujours absent en Matroska ;
2. le tag `BPS` posé par mkvmerge — exact, mesuré sur le fichier entier ;
3. le débit du conteneur **moins** celui de chaque piste non vidéo, ces
   dernières étant résolues de la même façon (`bit_rate`, `BPS`, puis
   `NUMBER_OF_BYTES ÷ DURATION`).

Une piste dont le débit reste introuvable ne retire rien : le résultat penche
alors du côté prudent, celui du réencodage. Une soustraction qui donnerait un
résultat nul ou négatif est écartée au profit du total. Un second flux vidéo
— une pochette embarquée — n'est jamais soustrait.

```python
@dataclass
class VideoInfo:
    path:                 Path
    width:                int
    height:               int
    bitrate:              int          # bps — VIDÉO seule, voir ci-dessous
    codec:                str
    duration:             float        # secondes
    frame_count:          int
    dv_profile:           int | None
    audio_tracks:         list[AudioTrack]
    subtitle_tracks:      list[SubtitleTrack]
    # Enrichissement DV (dovi_tool, optionnel)
    dv_subprofile:        str | None            # "5", "7.06", "8.1", "8.4"…
    hdr10_master_display: str | None
    hdr10_max_cll:        tuple[int, int] | None
```

> **Attention** — `AudioTrack.index` est un compteur **par type** (ffprobe), incompatible
> avec les TID globaux de mkvmerge. Voir § 9.5 piège 1.

### 15.2 Scan récursif

`scan_directory_recursive(root, progres=None)` — tous les fichiers vidéo sous `root`,
tous niveaux, triés par chemin. Mêmes filtres que `scan_directory` : extensions
supportées, exclusion de ce que l'application a elle-même encodé. Depuis la v0.8.9.90
(IE-117), les ffprobe tournent à `scanner.SCAN_WORKERS` (4) à la fois, comme sur
l'accueil ; l'ordre des résultats reste celui du tri, un échec n'arrête pas le reste.
`progres(fait, total)` est appelé après chaque fichier (sur 38 fichiers locaux :
8,3 s en série, 3,0 s en parallèle). `tests/test_scan_recursif.py`.

**Cette exclusion tient à une seule marque.** `scanner.deja_produit()` écarte tout
nom qui finit par `-iris` (compteur de collision `(n)` admis) — donc toute
sortie d'encodage, quelle que soit sa caractéristique, et tout suffixe qu'une action
vidéo apprendrait à écrire. Jusqu'à la v0.8.8.10 elle était dérivée de la liste des
suffixes `_[…]` ; la paire en dur qui la précédait encore ne connaissait que les deux premiers, à quatre endroits distincts : une sortie
AV1 reparaissait au scan, `av1` n'est pas dans `CODECS_LISIBLES`, et la décision tombait
en CAS 3 pour proposer de la réencoder en HEVC — sur `basic_delete`, qui a
`delete_source = true`, en effaçant l'original au passage.

`.mux-iris` en est **volontairement excepté** (`ENTREES_IRIS`) : une greffe n'est pas un encodage mais
une greffe de pistes, et l'encoder ensuite est un geste légitime que l'écarter du scan
rendrait impossible — le fichier ne serait même pas visible.

`.join-iris` en est excepté pour la même raison, en plus forte : un fichier
collé n'existe **que** pour être encodé ensuite (§ 9bis). L'écarter du scan viderait la
fonction de son objet.

**L'exclusion ne vaut que pour le scan, plus pour la vue.** Depuis la v0.8.8.3,
`FileNavigator.list_videos()` liste aussi les sorties de l'application, grisées
(§ 14.1). Les deux fonctions ci-dessus gardent leur filtre : ce sont elles qui
alimentent le scan récursif et les lots que l'utilisateur ne compose pas
lui-même, et c'est là que le garde-fou porte. Cocher soi-même une sortie pour la
réencoder demande deux gestes explicites ; `delete_source` reste actif sur ce
chemin.

### 15.3 Enrichissement DV au scan

Si `dovi_tool` est disponible (câblé dans `app.py` via `scanner.set_dovi_path()`), chaque
fichier DV est enrichi via `dovi.probe_file()`.

### 15.4 Navigation virtuelle

`FileNavigator` (`tui/widgets/file_tree.py`) supporte `start_virtual=True` : la vue
initiale liste les volumes disponibles (icône 💾, chemin complet). Entrer dans un volume
bascule en mode normal.

---

### 15.5 Titres de Blu-ray — `core/bluray.py`

(v0.8.9.94, IE-120) Un dossier qui contient `BDMV\index.bdmv` — racine d'un
ISO monté, ou rip copié — présente ses **titres** : `FileNavigator.list_videos`
ajoute à ses fichiers les playlists `BDMV\PLAYLIST\*.mpls` de
`bluray.titres(racine, durée_min)` (`[app] min_title_minutes`, 2 par défaut,
celle de MakeMKV). Les playlists sont lues sans outil (`lire_mpls` : éléments
de lecture clip / entrée / sortie à 45 kHz, marques d'entrée = chapitres) ;
validé contre mkvmerge sur le disque d'essai (durées et nombres de chapitres
identiques). Une playlist qui cite un clip absent est ignorée ; les doublons
(mêmes clips, même durée) se réduisent à celle qui porte le plus de
chapitres ; la plus longue est `principal`. `BDMV\STREAM` liste toujours les
clips bruts (IE-118).

`scanner.scan(*.mpls)` analyse le premier clip, puis pose `path` = la
playlist (identité dans le navigateur, la file, les réglages par fichier),
`titre`, la durée de la playlist et un `frame_count` mis à l'échelle. Trois
propriétés de `VideoInfo` en découlent : `lecture` (le fichier que lisent
ffmpeg, mkvmerge et mpv — le premier clip), `dossier` (le dossier qui contient
`BDMV`, jamais dedans ; base de `dossier_sortie` et de `sorties_bloquees`),
`stem_sortie` (`nom_disque` : le nom de ce dossier, ou à la racine d'un lecteur
son étiquette, soulignés en espaces ; suivi de ` - 01000` hors du titre
principal). `taille` : la somme des clips. L'étiquette perd ce que Windows refuse
dans un nom (`<>:"/\|?*`, contrôles, points et espaces finaux), remplacé par des
espaces : « Film: Director's Cut » faisait échouer ffmpeg à l'ouverture de la
sortie (v0.8.9.109, CR-04).

**Titre partiel** (v0.8.9.109, CR-01) — plusieurs playlists peuvent pointer dans
un même clip avec des bornes différentes (une chanson par playlist d'un concert,
un épisode par playlist). `_scan_titre` compare la durée du clip (ffprobe) à celle
de la playlist : au-delà d'une seconde d'écart, `TitreDisque.partiel`, et le titre
est `a_extraire` comme un titre de plusieurs clips. Lu tel quel, le clip donnait
tout le concert pour une chanson de 20 s ; mkvmerge respecte les bornes (mesuré
par la revue, v82).

À l'encodage (`RunScreen`) : un titre de plusieurs clips est d'abord assemblé
par `mkvmerge --gui-mode -o <dossier_sortie>\<n>.iris_titre.mkv <playlist>`
(`_remux_titre`, code 1 = avertissements accepté), qui devient
`encode_source` et part après l'encodage comme l'intermédiaire d'un mux
préalable ; ses pistes suivent l'ordre de celles du premier clip, que la
décision a numérotées. L'assemblage est **relu** (ffprobe) et comparé par type à
l'analyse (`bluray.ecart_pistes`, v0.8.9.109, CR-03 ; un `pcm_bluray` réécrit en PCM
reste la même piste) : une AAC que ffprobe voit dans le `.m2ts` et mkvmerge non
décalait les index, et `-map 0:a:1` prenait une autre langue sous le nom de la
piste voulue. Un écart met le fichier en erreur avec les deux listes, et
l'assemblage est effacé. Dolby Vision sur un titre de plusieurs clips, ou partiel :
refusé avec un message. Un titre d'un seul clip lit son `.m2ts` ; ses chapitres
(deux au moins) sont écrits en FFMETADATA (`<n>.iris_chap.txt`, « Chapter
01 »…) et passés à `build_command(chapitres=…)` : `-f ffmetadata -i …` en
dernière entrée, `-map_chapters`. Un titre n'est jamais supprimé après
encodage (`delete_source`), ni par `Ctrl+D` ; mux (`F3`) et collage le
refusent.

**Disque chiffré** — `clip_chiffre` lit les premières unités de 6 144 octets
du premier clip du titre principal : AACS chiffre chaque unité au-delà de ses
16 premiers octets, la synchronisation `0x47` des paquets 2 à 32 disparaît.
Chiffré, le dossier ne liste aucun titre et le navigateur le dit.

**Mode récursif** — un disque n'y donne que son titre principal (non chiffré) ;
ses fichiers sous `BDMV` sont écartés. Un seul parcours (`os.walk`), qui note les
disques en passant et n'entre ni dans `BDMV` ni dans `VIDEO_TS` ; lancé depuis l'un
d'eux, le disque est le dossier parent (v0.8.9.111, CR-12 : trois `rglob`
parcouraient l'arborescence avant le premier ffprobe, et un disque hybride
comptait deux fois).

**Titres mémorisés** (v0.8.9.111, CR-02) — `bluray.titres` et `dvd.titres` passent
par `bluray.memoriser` : la liste d'un disque est gardée par (racine, dates des
dossiers `PLAYLIST` et `STREAM`, ou `VIDEO_TS`), et ne se relit que si l'un change.
Retrouver un titre (`titre`, `principal`, `disque_chiffre`) relisait toutes les
playlists, et l'analyse le fait pour chacun : 600 playlists obscurcies, ≈ 7 min de
lecture avant le moindre ffprobe. Les `TitreDisque` rendus sont partagés.


### 15.6 Titres de DVD — `core/dvd.py`

(v0.8.9.95, IE-121) Un dossier qui contient `VIDEO_TS\VIDEO_TS.IFO` présente
ses titres, sur le modèle du Blu-ray (§ 15.5) et avec le même `TitreDisque` :
`scanner.module_disque` rend `bluray` ou `dvd`, que `FileNavigator` et le mode
récursif interrogent pareil (`titres`, `principal`, `disque_chiffre`).

**IFO lus sans outil** — `VIDEO_TS.IFO` (secteur pointé en `0xC4`, TT_SRPT) :
pour chaque titre, son VTS, son rang dans le VTS, ses chapitres ;
`VTS_xx_0.IFO` (PTT_SRPT en `0xC8`, PGCI en `0xCC`) : les PGC du titre et leur
durée (BCD, cadence dans les deux bits de poids fort des images). Validé sur
le DVD d'essai : un titre, 26 chapitres, 6 573,0 s contre 6 572,5 s pour
ffprobe. Deux titres jouant les mêmes PGC d'un même VTS n'en font qu'un ; un
VTS sans VOB ne donne rien. Identité : un nom fictif
`VIDEO_TS\TITLE_nn.dvd` (`chemin`), le numéro dans `numero` ; `nom_disque(…,
defaut="DVD")`. Le nombre de chapitres de l'IFO va dans `nb_chapitres` ;
`chapitres` (des temps) reste vide — il portait n zéros (v0.8.9.110, CR-07).

**Cellules** (v0.8.9.110, CR-06) — un VTS porte souvent plusieurs titres (les
épisodes d'une série). Chaque PGC donne sa table C_PBKT (pointée en `0xE8` du
PGC, 24 octets par cellule : premier secteur en +8, dernier en +20, relatifs au
début de `VTS_xx_1.VOB`) ; `_lire_vts` en réunit les plages par titre. `octets`
= leurs secteurs × 2 048 (`TitreDisque.taille` le préfère à la somme des clips),
`clips` = les VOB que ces secteurs touchent (`lecture` : le premier, pour mpv).
Chaque épisode pesait le VTS entier, son débit estimé en était multiplié
d'autant. Sans table lisible, l'ancien comportement : tous les VOB du VTS. Validé
sur le DVD d'essai (lu dans l'ISO, sans montage) : 2 227 717 secteurs, la
somme exacte des cinq VOB du contenu.

**« Lire tout » n'est pas le principal** (v0.8.9.110, question de la revue
tranchée le 2026-10-09) — un titre qui enchaîne au moins deux autres titres de
son VTS (`_lire_tout` : leurs PGC parmi les siens, ou leurs cellules couvertes
par les siennes), chacun d'au moins un dixième de sa durée, n'est pas retenu
comme principal ; il reste listé et cochable. Le plus long devenait le principal
d'un DVD de série, et le mode récursif sortait le disque en un seul fichier. Le
dixième garde le film d'un disque dont chaque scène est aussi publiée en titre.

**Outil DVD** — le démultiplexeur `dvdvideo` (libdvdnav) n'est que dans un
build comme le BtbN GPL. `dvd.chercher_outils` : `bin/dvd/ffmpeg(.exe)` et
`ffprobe` s'ils existent, sinon le ffmpeg principal si `-demuxers` liste
`dvdvideo`, sinon rien ; câblé au lancement (`dvd.set_outils`). Il ne fait
qu'analyser (`ffprobe -v quiet -f dvdvideo -title N -i <VIDEO_TS>` — le
dossier `VIDEO_TS`, pas la racine du lecteur, que libdvdread prend pour un
périphérique ; `-v quiet` car il signale en erreur des « Zero check failed »
sans effet) et extraire ; l'encodage reste au ffmpeg principal. Sans outil :
aucun titre, un message ; `VIDEO_TS` liste toujours les VOB (IE-118). Débit :
`dvdvideo` n'en donne pas, il est estimé sur la taille des VOB et la durée.

**Extraction** — tout titre de DVD est `a_extraire` : `RunScreen._extraire_dvd`
lance `ffmpeg -y -loglevel error -stats -f dvdvideo -title N -i <VIDEO_TS>
-map 0 -c copy <dossier_sortie>\TITLE_nn.iris_titre.mkv` (progression par
`EncoderProcess`), qui devient `encode_source` et part après l'encodage.
Langues, chapitres et palette des sous-titres viennent de l'IFO. Mesuré :
4,4 Go en 34 s, 26 chapitres. Une piste **LPCM** (`pcm_dvd`) n'a pas d'étiquette
Matroska : recopiée, l'extraction échouait (« No wav codec tag found ») et tout
le titre avec elle. Elle devient un PCM de même profondeur (`-c:a:N pcm_s16le`,
ou `pcm_s24le` pour 20 et 24 bits ; `AudioTrack.bits`, lu dans
`bits_per_raw_sample`), sans perte ni calcul (v0.8.9.110, CR-05, arbitrage du
2026-10-09) ; la décision audio la traite ensuite comme une autre piste.

**CSS** — `vob_chiffre` lit les 512 premiers paquets de 2 048 octets du
premier VOB du titre principal : un PES vidéo (`0xE0`), audio (`0xBD`,
`0xC0`–`0xDF`) dont `PES_scrambling_control` n'est pas nul trahit un disque
brouillé, refusé comme un AACS.

**Garde-fous** — en plus de ceux du Blu-ray : pas de greffe de piste externe
sur un titre de DVD (`pick_external_tracks`) — la mesure lirait un VOB, dont
les pistes ne sont pas numérotées comme celles du titre. Depuis la v0.8.9.101
(IE-134, CR-86, CR-94), la règle vaut pour **tout titre `a_extraire`** : sur un
Blu-ray de plusieurs clips, mesure, ancrage, aperçu et extrait lisaient le seul
premier clip avec la durée du titre entier. Pour un titre d'un clip, la greffe
reste possible : le donneur reçoit le clip (`lecture`, pour l'empreinte
OpenSubtitles) et le nom du disque (`stem_sortie`), que `Client.chercher(…,
nom=…)` cherche à la place de « 00800 » (CR-96) ; la fiche `I` cherche aussi
le nom du disque (CR-100).

## 16. Logging

### 16.1 Logging Python standard (opérationnel)

Configuré dans `app.py` à chaque lancement :

```python
log_path = Path.home() / ".iris_encode" / "iris_encode.log"
logging.basicConfig(level=logging.WARNING, …)
```

Les modules `core/` logguent via `logging.getLogger("iris_encode.*")`. Warnings et
erreurs persistés silencieusement.

### 16.2 Logger applicatif (inerte)

`logger/logger.py` — API définie, aucun backend branché.

```python
logger.info("scan terminé", files=12)
logger.error("encodage échoué", file="video.mkv")
logger.session_start(profile="default", path="D:/Videos")
```

Backend prévu (JSON ou SQLite) dans une release ultérieure.

---

## 17. Portabilité et dépendances

### 17.1 Portabilité

- Tout `pathlib.Path`, aucune string de chemin en dur
- `./bin/` pour les binaires externes embarqués
- `config.toml` et `profiles.toml` dans le dossier application
- Aucune dépendance au registre Windows ni à `%APPDATA%`
- Fonctionne depuis une clé USB

**Future release :** Python embarqué (embeddable package) pour zéro prérequis système.

### 17.2 Dépendances Python

```
textual        ← TUI
rich           ← affichage console
tomli-w        ← écriture TOML (lecture native Python 3.11+)
requests       ← téléchargement des outils + API métadonnées
beautifulsoup4 ← scraping AlloCiné
numpy          ← corrélation FFT (core/sync.py)
```

Chaque ligne porte un plancher et un plafond (§ 3.1). `tests/test_deps.py`
vérifie que la liste de `main.py` couvre `requirements.txt`, et que
`launch.bat` et `bootstrap.ps1` passent par `dependances.py` plutôt que par une
liste à tenir à la main ; `tests/test_lanceurs.py`, que l'environnement des
tests est dans les bornes.

### 17.3 Binaires externes et licences

| Élément | Nature | Licence | Remarque |
|---|---|---|---|
| ffmpeg | essentiel | GPL-3.0 (build `--enable-gpl --enable-version3`, libx265) | Build *essentials*, ~30 Mo |
| dovi_tool | optionnel | MIT | Binaire Windows unique |
| mkvmerge | optionnel | **GPL-2.0** | ZIP officiel statique, sans DLL, 22 Mo |
| mpv | optionnel | GPL-2.0+ | Publié en `.7z`, extrait via le tar de Windows |

**Licence d'IRIS ENCODE.** GPL-3.0-or-later, texte dans `LICENSE` à la racine.
Choisie pour s'aligner sur l'outil central (ce build de ffmpeg est GPL-3.0) et pour
que les contributions, traductions comprises, restent libres. Les dépendances
Python (`textual`, `rich`, `tomli-w`, `beautifulsoup4` : MIT ; `requests` :
Apache-2.0 ; `numpy` : BSD-3-Clause) sont toutes compatibles.

**Binaires externes.** Ils ne sont pas redistribués : `bin/` n'est pas versionné,
le ZIP de release est le `git archive` du tag, et `core/preflight.py` télécharge
chaque outil depuis sa source. IRIS les lance en sous-processus, sans liaison :
leurs licences ne s'étendent pas à son code. Embarquer un jour mkvmerge, mpv ou
ffmpeg dans un ZIP entraînerait les obligations GPL de redistribution (texte de
licence, accès aux sources) — à décider sciemment.

---

## 18. Tests

| Fichier | Portée |
|---|---|
| `tests/smoke_tui.py` | Parcours TUI headless de bout en bout (14 scénarios), **en anglais puis en français**, un processus par langue — **à lancer après toute modification d'écran** |
| `tests/shots_tui.py` | Inventaire visuel : exporte chaque écran en SVG (rendu réel, pas maquette), dans la langue demandée |
| `tests/test_i18n.py` | Socle de la traduction ; règles structurelles : aucun texte en dur aux points d'affichage (`notify`, `Static`, `Binding`…) hors termes intraduisibles du glossaire, aucun texte accentué hors `_()` dans `core/` et `tui/`, aucune comparaison à un texte traduit |
| `tests/test_troncature.py` | Planchers de colonnes : chaque valeur possible tient, **dans chaque langue** |
| `tests/test_deps.py` | Cohérence des listes de dépendances |
| `tests/test_dovi.py` | Wrapper dovi_tool |
| `tests/test_muxer.py` | Génération des commandes mkvmerge, parsing `--gui-mode` |
| `tests/test_preview.py` | Construction des commandes mpv |
| `tests/test_sync.py` | Mesure de décalage sur paires connues |
| `tests/test_updates.py` | Vérification de fraîcheur des outils |
| `tests/test_veille.py` | Veille bloquée pendant un lot, action d'après lot (moteur Windows simulé) |

```bash
python tests/smoke_tui.py     # headless, encode réellement de petits clips, en + fr
python tests/smoke_tui.py fr  # une seule langue
python tests/shots_tui.py --langue en   # inventaire visuel -> _shots/en/*.svg
python -m pytest tests/
```

---

## 19. Hors scope

Arbitré ligne par ligne par l'utilisateur le 2026-10-07 (IE-82). Ce qui reste
hors scope, et pourquoi :

| Hors scope | Raison |
|---|---|
| Pistes de commentaire repérées par leur titre | Confort : une piste de commentaire dans une langue gardée est conservée, ce qui ne coûte que de la place ; l'écran des pistes l'écarte d'un `Espace` |
| Badges de langues pour `audio_languages` | Le champ texte (`fre, eng`) suffit, et les deux jeux de codes ISO sont réconciliés |
| Pistes externes en traitement par lot | Chaque greffe demande sa mesure et son contrôle : un fichier à la fois, par construction |
| IPC mpv (réglage dans mpv repris par l'application) | La valeur se retape dans l'écran de recalage ; le gain ne justifie pas un canal nommé par plateforme |
| Collage de parties aux codecs ou définitions différents | Décision de conception : refusé et nommé, jamais rattrapé par un réencodage (§ 9bis.3) |
| `Ctrl+D` vers la corbeille | Windows ne met pas en corbeille un fichier d'un partage réseau, là où vit l'essentiel d'une bibliothèque : la promesse serait fausse. La suppression reste définitive et le dit |

Retirées le même jour, parce que faites : journal persistant
(`~/.iris_encode/iris_encode.log`, avertissements et erreurs ; `logger/logger.py`
reste un module inerte), Python embarqué (`bootstrap.ps1`, § 3.1.1), mise à
jour des outils au lancement (`core/updates.py`, § 4.4), file multi-dossiers (la
file d'encodage, § 14.7), Dolby Vision au remux mkvmerge (vérifié le
2026-09-24). Entrée en v0.9.0 : l'analyse en parallèle du mode récursif (IE-117, livrée en v0.8.9.90).

---


## 20. Historique des versions

| Version | Date | Modifications |
|---|---|---|
| 0.1 | 2026-05-12 | Document initial |
| 0.2 | 2026-05-12 | Dolby Vision (strip/preserve/sdr), bitrates par résolution, dovi_tool au preflight |
| 0.3 | 2026-05-12 | Politique audio complète : sélection pistes, transcodage, profils audio, écran Tracks |
| 0.4 | 2026-05-12 | Colonnes redimensionnables · `←` remonter · zone commande ffmpeg · CRUD profils |
| 0.5 | 2026-05-13 | Correction scroll DataTable · PgUp/PgDn/Home/End · refonte builtins · barre de statut |
| 0.6 | 2026-05-14 | **core/dovi.py** · **core/meta.py** (IMDB + AlloCiné) · enrichissement DV au scan, scan récursif, eac3 copy-compat · 9 profils builtin, `strip`→`hdr10`, `preserve`→`dv` · ENCODE_AV1, seuil sur résolution cible, force SKIP→encode · mode HDR10 quality, suspend/resume · TwoLineFooter, barre profil 2 lignes, F3/F7/F8 · refonte TracksScreen · logging · QuitConfirmScreen |
| 0.6.5 | 2026-06-09 | Seuils `near_1080p` paramétrables (`[decision]`, 1600×850) : les sources rognées restent en 1080p HEVC au lieu d'être rabattues en 720p H264 · `_resolve_limits` dissocie cap de résolution et bucket de débit · `F6`/`F7` au dry-run (picker codec et débit par fichier, avec recalcul de l'estimation) · `bitrate_4k_kbps` réduit sur `film_basic`, `film_hd`, `basic_delete` · constantes vidéo mutualisées dans `core/decision.py` |
| 0.7.0 | 2026-06-10 | Normalisation UIX, footer ancré · optimisations Textual · édition codec/débit au dry-run · seuils `near_1080p` paramétrables · profil `cinema_4k_quality` · corrections (affichage version, ancrage footer, seuils de débit) |
| 0.7.1 | 2026-08-06 | Colonne Durée au dry-run · sélecteur de profils en table · correction crash `NoMatches` sur backspace pendant encodage · gestion des événements clavier dans les modales de saisie |
| 0.8.0 | 2026-08-26 | **Greffe de pistes externes** : `core/muxer.py` (mkvmerge), `core/sync.py` (mesure par corrélation), `core/preview.py` (mpv) · écrans DonorPicker, Sync, MuxRun · `F9` piste externe, `m` mesurer, `v` visualiser, `k` extrait, `c` copier décalage, `F3` muxer · **Outils** : mkvmerge et mpv en optionnels, vérification des mises à jour au démarrage (`core/updates.py`) · **Estimation** : colonnes Estim. (Δ%) et Temps estim. adossées à une moyenne mobile de vitesse · **Corrections** : conteneur de sortie suivant les pistes conservées, listes de dépendances vérifiées par test, preflight sans terminal interactif |
| 0.8.0.1 | 2026-08-26 | **`Ctrl+D`** — suppression du fichier sous le curseur depuis le browser, avec confirmation (`DeleteConfirmModal`), sans re-scan du dossier · **Documentation** : consolidation des trois specs en un document unique suivant la version |
| 0.8.0.2 | 2026-08-26 | `stdout`/`stderr` forcés en UTF-8 avant le premier `print` : le démarrage mourait sur un `UnicodeEncodeError` hors console Windows (pipe, fichier, Git Bash, tâche planifiée) |
| 0.8.1.0 | 2026-08-27 | **Greffe d'une piste venue d'un autre montage** : détection des plages par fenêtres de 2 min (`s`), recalage exact des sous-titres et par insertion sur silence pour l'audio (`p`), sous-titres embarqués mesurables · mux préalable par mkvmerge quand une piste est étirée · décalage négatif traduit en `-ss` (fichiers illisibles sur TV) |
| 0.8.1.1 | 2026-08-27 | `GUIDE.md` — guide d'utilisation par écran et par cas, raccourcis relevés depuis les `BINDINGS` |
| 0.8.1.2 | 2026-08-27 | Footer réancré en bas (le `1fr` de la table ne s'appliquait pas : sélecteur de type contre style par défaut du widget), hauteur posée explicitement · raccourcis rangés par rôle, `F1`–`F10` en dernière ligne |
| 0.8.1.3 | 2026-08-27 | Colonne « Temps estim. » renommée « ETA », largeur 14 → 9 |
| 0.8.1.4 | 2026-08-27 | Largeurs de colonnes du browser revues au profit du nom de fichier et des pistes audio · l'accueil repart des largeurs par défaut à chaque lancement |
| 0.8.1.5 | 2026-08-27 | **Crash au lancement sur toute installation neuve** : `_deep_merge` assignait les sous-dictionnaires par référence, la réinitialisation des colonnes vidait `_DEFAULTS` |
| 0.8.1.6 | 2026-08-27 | **Retrait du Dolby Vision sans réencodage** (`VideoAction.STRIP_DV`, § 7.3) : une source 8.1 ou 7 que le profil n'a aucune raison de réencoder sort en `_[hdr10].mkv` par `dovi_tool remove` + mkvmerge — image bit à bit identique, HDR10+ conservé, 2 min 16 s pour un film 4K de 5,7 Go · détection du sous-profil par `dv_bl_signal_compatibility_id` · **sortie HDR10 en 10 bits** : le mode standard encodait en `yuv420p` quelle que soit la source |
| 0.8.1.7 | 2026-08-27 | **`audio_hd_codec`** : transcodage des pistes TrueHD et DTS en AC3/E-AC3 **au débit présent dans la piste** (§ 8.5), plafonds d'encodeur mesurés, repli 7.1 → 5.1 annoncé · débit réel lu via les tags `BPS`/`NUMBER_OF_BYTES` quand le flux n'en déclare pas · **DTS-HD MA enfin reconnu sans perte** (lecture de `AudioTrack.profile`) |
| 0.8.1.8 | 2026-08-27 | **Le débit comparé au seuil est celui de la vidéo seule** (§ 8.1, § 15.1) : le débit du conteneur, audio compris, envoyait au réencodage des fichiers dont la vidéo tenait sous le seuil — 44 % d'écart sur un film porteur d'un TrueHD |
| 0.8.1.9 | 2026-08-27 | Introduction du README : la chaîne de diffusion, les contraintes de chaque maillon, et les choix de conception qui en découlent |
| 0.8.9.115 | 2026-10-09 | **Lanceurs** (§ 3.1, § 17.2, IE-132 2/3) : bornes hautes et basses des dépendances, contrôlées par `dependances.py` au lancement et au bootstrap (CR-109, CR-110) · `launch.bat` sans expansion retardée, dossier par `IRIS_DIR` (CR-108), sans purge des `__pycache__` (CR-107) · `;` échappé pour `wt.exe` (CR-111) · raccourci par `$env:ROOT` (CR-112) · essais réels sous Windows dans `Test!x`, `l'essai`, `A;B` · `tests/test_lanceurs.py` |
| 0.8.9.114 | 2026-10-09 | **Installation des outils** (§ 4.2 à 4.4, IE-132 1/3) : empreinte SHA256 exigée pour tout téléchargement, lue chez l'amont ou épinglée (CR-40) · tous ou aucun, par provisoires et `os.replace` (CR-38) · tar.gz/tar.xz extraits, exécutable nu reconnu à son en-tête (CR-39) · installation sur les seules sources statiques, le cache ne les masque plus (CR-41) · `tests/test_outils_installation.py` |
| 0.8.9.113 | 2026-10-09 | **Vidéo et encodeurs** (§ 8.1, § 11, § 12, § 14.0, IE-130) : pixels carrés pour une source anamorphique (`VideoInfo.sar`, CR-14) ; forçage par tranche, HDR gardé en HEVC (CR-16) ; `CODEC_PAR_ACTION` (CR-17) ; débit inconnu réencodé à la cible (CR-19) ; `regle_debit` selon l'encodeur effectif (CR-22) ; sonde 10 bits NVENC, `_refuser_encodeur` (CR-42) ; H264 sur une source HDR → SDR, averti (`h264_force_sdr`, arbitrage du 2026-10-09) · `tests/test_video_revue.py` |
| 0.8.9.112 | 2026-10-09 | **Audio : DTS:X IMAX, marques collées, pistes écartées** (§ 8.5, § 8.7, IE-128) : profil DTS sans perte par préfixe (CR-09) ; marque collée à sa disposition reconnue et réécrite (`colle_a_une_disposition`, CR-10) ; famille d'une piste écartée réécrite vers la piste gardée (CR-18) · `tests/test_audio_revue.py` |
| 0.8.9.111 | 2026-10-09 | **Titres de disque : coûts de lecture** (§ 15.5, IE-127 3/3) : `bluray.memoriser` / `signature` pour les titres des deux modules (CR-02) ; mode récursif en un seul `os.walk` (CR-12) · `tests/test_bluray.py`, `tests/test_scan_recursif.py` |
| 0.8.9.110 | 2026-10-09 | **Titres de DVD : cellules, « Lire tout », chapitres, LPCM** (§ 15.6, IE-127 2/3) : taille et VOB d'un titre par ses cellules (`_cellules`, `TitreDisque.octets`, CR-06) ; un « Lire tout » n'est plus le principal (`_lire_tout`) ; `nb_chapitres` (CR-07) ; `pcm_dvd` extrait en PCM de même profondeur (`AudioTrack.bits`, CR-05) · `tests/test_dvd.py` |
| 0.8.9.109 | 2026-10-09 | **Titres de Blu-ray : partiel, assemblage vérifié, étiquette** (§ 15.5, IE-127 1/3) : `TitreDisque.partiel` posé par `_scan_titre`, extrait par mkvmerge (CR-01) ; `bluray.ecart_pistes` après `_remux_titre` (CR-03) ; `nom_disque` assainit l'étiquette du volume (CR-04) · `tests/test_bluray.py` |
| 0.8.9.108 | 2026-10-09 | **Chemins Dolby Vision : dovi_tool arrêtable** (§ 7.1, § 7.4, § 12.4, IE-126 3/3) : `TuyauRpu`, `build_remove_command`, `build_inject_command`, `rpu_valide` remplacent les appels bloquants à délai fixe (CR-32) ; `RunScreen._executer` les publie ; `S` arrête aussi mkvmerge, un SKIPPED n'est plus réécrit en ERROR (CR-61) · `tests/test_dv_chemins.py` |
| 0.8.9.107 | 2026-10-09 | **Chemins Dolby Vision : greffes, chapitres, langues** (§ 7.3, § 8.6, § 12.0, IE-126 2/3) : retrait DV vers MP4 avec greffes recomposé par mkvmerge puis remuxé (CR-55) ; audio greffée à la règle du profil sur les deux chemins DV (`_transcoder_greffes`, reporté d'IE-125) ; chapitres d'un titre de Blu-ray par `--chapters <playlist>` ou FFMETADATA, langues du `.clpi` écrites par `build_audio_command` et `build_strip_mp4` (CR-63) ; CR-56 vérifié couvert depuis la v0.8.9.104 · `tests/test_dv_chemins.py` |
| 0.8.9.106 | 2026-10-09 | **Chemins Dolby Vision : source, pistes vides, RPU, mux** (§ 14.0, § 14.7, IE-126 1/3) : `RunScreen._supprimer_source`, une règle pour les trois chemins — titre de disque gardé, annexes supprimées, rien après `S` (CR-54) ; `_audio_vide` sur chaque sortie finale (CR-65) ; code de retour de ffmpeg exigé dans le tuyau du RPU (CR-31) ; `_muxable` limité au SKIP (CR-85) · `tests/test_dv_chemins.py` |
| 0.8.9.105 | 2026-10-09 | **Écran de recalage** (§ 10.2, § 10.5, IE-125 3/3) : `extract_subtitle` sans délai fixe, avec progression et `ExtractionImpossible` qui dit la cause (CR-35), hors du fil de l'écran (`SyncScreen._en_texte`) ; `_srt_stamp` arrondit avant de découper (CR-36) ; WebVTT sans heures, fractions courtes complétées, `.sub` hors des formats texte (CR-37) ; mpv reçoit la piste extraite (`preview.build_command(…, sub_file=)`, CR-52) ; recalage audio désigné par l'objet, `D` refusé pendant une opération (CR-92) · `tests/test_recalage_ecran.py`, `tests/test_sync.py` |
| 0.8.9.104 | 2026-10-09 | **Greffes : temps en MP4, langue, index** (§ 8.6, § 9.3, § 9.8, IE-125 2/3) : les sous-titres greffés passent par le porteur (`greffes_a_porter`, `build_extraction_greffe`, CR-34 ; réencodage DV : lus dans le Matroska recomposé, étirement compris) ; `guess_language` ne prend plus un mot du titre pour une langue (CR-26) ; un téléchargement OpenSubtitles porte son code ISO 639-2 (CR-51) ; `ffmpeg_stream_index` et `mkvmerge_tid` refusent au lieu de deviner (CR-27) · `tests/test_greffes_encodage.py` |
| 0.8.9.103 | 2026-10-09 | **Greffes : règle audio du profil, jeu de caractères, drapeaux, polices** (§ 9.5, § 12.0, IE-125 1/3) : `decision.audio_greffee`, `decide_codec_audio`, `scanner.pistes_audio` ; `sous_titres.encodage_texte` (CR-50) ; `muxer.types_par_defaut` (CR-23, CR-25) ; `-map 0:t?` en MKV (CR-20) · `tests/test_greffes_encodage.py` |
| 0.8.9.102 | 2026-10-08 | **Jonction** (§ 9bis, IE-136) : marqueur de numérotation retiré seulement comme mot entier, une fois (`Le Fantome 1` ne devient plus `Le Fan`) · langues inversées de même rang annoncées, fréquence différente bloquante (`AudioTrack.sample_rate`, lu au scan) · CR-29, 30 · `tests/test_collage.py` |
| 0.8.9.101 | 2026-10-08 | **Titres de disque dans les écrans annexes** (§ 15.6, IE-134) : pas de greffe sur un titre à assembler (Blu-ray de plusieurs clips comme DVD) · OpenSubtitles et fiche cherchent le nom du disque, empreinte sur le clip · CR-86, 94, 96, 100 · `tests/test_titres_ecrans.py` |
| 0.8.9.100 | 2026-10-08 | **Arrêts et sorties** (§ 12.4, IE-131) : `S` en pause, `Ctrl+Home` pendant un mux, quitter tous les modes, confirmation unique, en-tête du catalogue, compte à rebours recouvert, lecteur inhabituel, réponse OpenSubtitles non JSON · CR-60, 67, 70, 71, 91, 95, 103, 104 · `tests/test_arrets_sorties.py` |
| 0.8.9.99 | 2026-10-08 | **Restes sur le disque** (§ 12.4, IE-129) : sortie partielle effacée sur tous les chemins · forme unique des intermédiaires, reconnus comme des sorties · `_liberer` sur chaque sortie de la passe principale · mux préalable et piste recalée dans le dossier de sortie · `mkvmerge_reussi` (code 1 accepté) partout · annexes gardées pour une vidéo de même nom · CR-11, 24, 28, 57, 58, 89, 90, 93 · `tests/test_restes_disque.py` |
| 0.8.9.98 | 2026-10-08 | **Fichiers de réglages** (§ 5, § 6.2, IE-124) : `config.toml` et `profiles.toml` illisibles jamais réécrits (`illisible()`, `ConfigIllisible`, `ProfilsIllisibles`), alerte console et interface · écriture refusée sans fermer l'application (`enregistrer`, `sauver_config`, `signaler_config`) · vitesse mesurée enregistrée sur le fil de l'interface · CR-43, 44, 45, 64, 77 · `tests/test_fichiers_reglages.py` |
| 0.8.9.97 | 2026-10-08 | **La décision de l'accueil** (§ 8.6, § 14.1, IE-123) : copies de travail pour les pistes et l'aperçu, registre des réglages explicites réappliqué au rescan, rescan pendant un lot seulement sur nouvelle réussite, nom de sortie prévu sans être figé (`sortie_prevue`), mux nommé `.mux-iris.mkv`, SKIP + greffes muxé par la file, décoche après mise en file, options relues · CR-15, 74, 76, 81, 82, 84, 87, 88, 98 · `tests/test_decision_accueil.py` |
| 0.8.9.96 | 2026-10-08 | **Désentrelacement** (§ 8.1, IE-122) : `VideoInfo.field_order`, `entrelace` ; `FileDecision.desentrelace` ; bwdif `send_frame`, `deint=interlaced`, avant `scale` ; affiché dans l'assistant et l'aperçu · `tests/test_desentrelacement.py` |
| 0.8.9.95 | 2026-10-08 | **Titres de DVD** (§ 4.1, § 4.2, § 15.6, IE-121) : dossier `VIDEO_TS` présenté par les titres de ses IFO lus sans outil · outil DVD à part (`ffmpeg_dvd`, BtbN GPL dans `bin/dvd/`, ou le principal s'il a `dvdvideo`), proposé au preflight, mis à jour par branche · titre extrait sans perte en Matroska avant l'encodage par le ffmpeg principal · CSS refusé · pas de greffe sur un titre de DVD · `TitreDisque.chemin` (ex-`mpls`), `numero`, `a_extraire` · Options « Titres de disque » · `tests/test_dvd.py` |
| 0.8.9.94 | 2026-10-08 | **Titres de Blu-ray** (§ 5, § 14.8, § 15.5, IE-120) : dossier `BDMV` présenté par playlists `.mpls` lues sans outil, durée minimale `[app] min_title_minutes` (Options), doublons réduits, titre principal · `VideoInfo.titre`, `lecture`, `dossier`, `stem_sortie`, `taille` · sortie nommée d'après le disque, à côté de `BDMV` · titre de plusieurs clips assemblé par mkvmerge avant l'encodage, chapitres FFMETADATA pour un clip seul · AACS refusé · mode récursif : titre principal seul · `tests/test_bluray.py` |
| 0.8.9.93 | 2026-10-08 | **Langues des Blu-ray, cœur AC-3, DVB, télétexte** (§ 8.5, § 8.6, § 15, IE-119) : langues d'un `.m2ts` complétées par mkvmerge (PID), écrites dans la sortie · piste sans langue gardée (audio, sous-titres), jamais dite doublée · paire TrueHD + cœur AC-3 réduite à une piste selon `preserve_hd_audio`, verrou de piste originale suivant `AudioDecision.locked` · `dvb_subtitle` image, `dvb_teletext` toujours écarté · `tests/test_langues_disque.py` |
| 0.8.9.92 | 2026-10-08 | **Flux MPEG et sources en lecture seule** (§ 14.7, § 15, IE-118) : `.ts .m2ts .mts .mpg .mpeg .vob` reconnus, liste vidéo du donneur dérivée du scan · dossier de sortie demandé à la mise en file quand celui de la source refuse l'écriture (ISO monté), réglage `[app] output_dir` dans Options, sortie et intermédiaires dans `FileDecision.dossier_sortie` · mux et collage refusés en lecture seule · `tests/test_sources_lecture_seule.py` |
| 0.8.9.91 | 2026-10-07 | **Passe audio préalable : défaut plus reproduit** (§ 14.7, IE-80) : ffmpeg 8.1.2 et 8.1.3 écrivent la piste sans perte transcodée en entier, fichier du signalement compris ; passe gardée par choix de l'utilisateur ; docstring d'`audio_prepass_needed` · aucun changement de comportement |
| 0.8.9.90 | 2026-10-07 | **Analyse récursive en parallèle** (§ 15.2, IE-117) : `R` analyse quatre fichiers à la fois, comme l'accueil, et compte sa progression ; `SCAN_WORKERS` passe de `tui/screens/browser.py` à `core/scanner.py` · `tests/test_scan_recursif.py` |
| 0.8.9.89 | 2026-10-07 | **Hors scope arbitré** (§ 19, IE-82) : six lignes gardées avec leur raison, cinq retirées parce que faites, l'analyse récursive en parallèle entre en v0.9.0 (IE-117) ; aucun changement de code |
| 0.8.9.88 | 2026-10-07 | **Documentation de la localisation** (§ 2.1, IE-95) : `README.md` et `GUIDE.md` en anglais, versions françaises en `README.fr.md` et `GUIDE.fr.md` (`git mv`), lien croisé en tête ; § 2.1 « Localisation » : ce qui ne se traduit pas, documentation en deux langues · corrigés au passage dans les deux langues : touche de la fiche (`I`, plus `F7`/`F8`), colonne « Raison » disparue, champ audio sans perte et mode HDR10 renommés, profils cités qui n'existent plus, report automatique de la mesure · `install.txt` en anglais · `tests/test_aide.py` vérifie les deux guides et les deux README |
| 0.8.9.87 | 2026-10-07 | **Tests de la localisation** (§ 18, IE-94) : smoke dans les deux langues, captures avec `--langue`, guide et planchers de colonnes testés dans chaque langue, garde-fous structurels (textes en dur aux points d'affichage, accents dans `core/`, comparaisons à un texte traduit) · corrigés : « Jonction », « Choisir », « Annuler » affichés en dur ; colonne « Sync » à 15 |
| 0.8.9.86 | 2026-10-07 | **Annexes Jellyfin supprimées avec la source** (§ 14.7, IE-116) : `<nom>.nfo` et `<nom>-*.jpg|png…` partent avec la source après encodage (`delete_source`) et avec `Ctrl+D`, que la confirmation liste ; sous-titres externes, fichiers du dossier et sortie conservés · `core/annexes.py`, `tests/test_annexes.py` |
| 0.8.9.85 | 2026-10-07 | **Relecture de l'anglais source** (IE-93) : termes du glossaire partout (*segment*, *anchor point*, *added track*, *check sample*), orthographe US (*movie*, *canceled*, *Analyzing*), noms d'écrans capitalisés (« the Tracks screen ») ; traductions françaises reportées · colonne « Sync » du recalage à largeur plancher, libellés du formulaire de profil élargis d'un caractère |
| 0.8.9.84 | 2026-10-07 | **Choix de la langue** (§ 2.1, IE-92) : section de l'écran Options, une langue par catalogue livré, nommée dans sa langue ; détection de la langue de Windows au premier lancement (`[app] language` vide par défaut), anglais si elle n'est pas traduite ; effet au redémarrage, annoncé · panneau Options défilant · `tests/test_choix_langue.py` |
| 0.8.9.83 | 2026-10-07 | **Lanceurs et console** (§ 2.1, IE-91) : textes affichés de `launch.bat`, `bootstrap.ps1`, `build.bat`, du lanceur C# et d'`updater.py` en anglais (`[Y/n]`, `o`/`oui` acceptés) ; langue chargée avant la bannière ; cadre calculé en cellules · `tests/test_console_anglais.py`, `tests/test_banniere.py` |
| 0.8.9.82 | 2026-10-07 | **Formats localisés** (§ 2.1, IE-90) : unités d'octets traduites (TB/GB/MB/KB ↔ To/Go/Mo/Ko), point décimal fixe, « 12% » sans espace partout (raisons de décision, barre d'état, volumes, aide du preset) · `tests/test_formats.py` |
| 0.8.9.81 | 2026-10-06 | **Guide des touches traduit** (§ 2.1, IE-89) : 113 messages, rendu français identique à l'octet ; libellés et touches cités en paramètres, touches lues dans les `BINDINGS` ; repli en cellules · `tests/test_aide.py` (traduction exigée, paramètres fournis), exception d'IE-88 retirée de `tests/test_i18n.py` |
| 0.8.9.80 | 2026-10-06 | **Pas d'agrandissement** (§ 8.1) : `scale` n'est posé que si la source dépasse la cible — un 1918×802 réencodé sortait étiré en 1920×802. Une dimension impaire perd un pixel (`trunc(iw/2)*2`) · `tests/test_resolution_nom.py` |
| 0.8.9.79 | 2026-10-06 | **Pixels carrés après redimensionnement** (§ 8.1) : `scale` rattrapait l'arrondi de la hauteur par un SAR — 3832×1600 → 1920×802 en 192079:192000, 1918×802 → 1920×802 en 959:960 — et Jellyfin transcodait la vidéo, prise pour anamorphique. Le filtre vidéo pose `setsar=1` après `scale` · `tests/test_resolution_nom.py` |
| 0.8.9.78 | 2026-10-06 | **Une marque dite une seule fois** (§ 8.7) : `Film 4K DV HDR10 2160p` ramené en 1080p sortait `1080p … 1080p` — seules les marques voisines étaient fondues. `stem_marques_remplacees` remplace la première marque et retire les suivantes (résolution, HDR, audio) · `tests/test_resolution_nom.py` |
| 0.8.9.77 | 2026-10-06 | **4K recadrée prise pour un 1080p** (§ 8.1) : une source 3832×1600 n'atteignait ni 3840 ni 2160, gardait sa définition sous `keep_4k = false` et sortait nommée `2160p.4Klight` · seuils 4K à 3200 px de large ou 1700 de haut (`VideoInfo.is_4k`), partagés par `_resolve_limits` et `resolution_label` · `tests/test_resolution_nom.py` |
| 0.8.9.76 | 2026-10-05 | **Version de ffmpeg mal lue** (§ 3, IE-115) : un build BtbN (`n8.1.3-…`) se lisait « 1.3 », et toute 8.x paraissait plus récente · `tests/test_updates.py` |
| 0.8.9.75 | 2026-10-05 | **Textes de `tui/` extraits** (§ 2.1, IE-88) : environ 575 messages, français repris à l'identique (phrases autrefois coupées à la main repliées d'elles-mêmes) ; descriptions de touches marquées `N_()` et traduites au rendu ; largeurs d'en-têtes sur le texte affiché, en cellules ; capitales décoratives au rendu ; `core/texte.py` retiré · `tests/test_i18n.py` (garde-fou du français en dur dans `tui/`) |
| 0.8.9.74 | 2026-10-04 | **Textes de `core/` extraits** (§ 2.1, IE-87) : messages en anglais source, français au catalogue à l'identique (181 messages) ; erreurs affichées en `ErreurAffichable`, montrées par `texte_erreur` ; pluriels par `ngettext` ; niveaux de confiance, oui/non des profils et actions d'après lot traduits à l'affichage ; lettre du « oui » de la console au catalogue · `tests/test_i18n.py` |
| 0.8.9.73 | 2026-10-04 | **Glossaire anglais → français** (§ 2.1, IE-85) : `locales/glossaire.fr.csv`, un terme = une traduction, termes à ne pas traduire ; arbitrages de l'utilisateur (SKIP invariant, Dry run, Guided, « lossless » gardé) au wiki, page `localisation` · `tests/test_i18n.py` |
| 0.8.9.72 | 2026-10-04 | **Socle de la traduction** (§ 2.1, IE-86) : `core/i18n.py` (gettext, anglais source, repli), `locales/` avec le catalogue français et son `.mo` versionné, `outils/i18n.py` sans dépendance (extraction, mise à jour, compilation), `ErreurAffichable`, `liste`, `texte_style` ; `main.py` charge la langue après `config.toml` ; aucun texte encore extrait, rien ne change à l'écran · `tests/test_i18n.py` |
| 0.8.9.71 | 2026-10-04 | Retrait DV en MKV : le compteur de l'étape audio (« ▶ 3/4 ») se calcule comme ses voisines ; aucun changement visible (clôture d'IE-83) |
| 0.8.9.70 | 2026-10-04 | **Noms de piste proposés selon la langue de la piste** (IE-113, L-77, § 9.3) : le champ Nom du recalage proposait la même liste française à toute piste ; `muxer.noms_proposes` la tire de la langue de la piste (`fre`, `eng`, sinon Forced/SDH). Données écrites dans le fichier, hors traduction de l'interface · `tests/test_muxer.py` |
| 0.8.9.69 | 2026-10-04 | **Exemple décimal et nom de touche alignés sur le reste** (IE-113, L-56, L-70) : le point de repère montre « 13:22.5 » (la virgule reste acceptée), la fin de jonction écrit « ⌫ » et non « BACKSPACE » · `tests/test_revue_code.py` |
| 0.8.9.68 | 2026-10-04 | **Libellé mort retiré de `_resolve_limits`** (IE-113, L-14) : la fonction rendait aussi « Original WxH » / « 1080p », jamais lu · `tests/test_revue_code.py` |
| 0.8.9.67 | 2026-10-04 | **Un libellé, une source** (IE-113, L-13, L-15, L-66, L-79, L-81) : sort du Dolby Vision (`decision.DV_SORTIE`), « → copie », « exclu manuellement », type de piste (`libelle_type_piste`) et en-têtes de colonnes fixes (`colonne_fixe`) écrits une seule fois · l'aperçu n'affiche plus « (→ → copie) » dans la colonne audio · `tests/test_revue_code.py` |
| 0.8.9.66 | 2026-10-04 | **L'aperçu ne montre plus de nom interne** (IE-113, L-68) : un codec changé dans l'aperçu donnait la raison « Modifié manuellement (dry-run) : ENCODE_H264 » ; elle devient « Choisi dans l'aperçu », comme l'assistant, et le guide dit « Aperçu » au lieu de « Dry-run » · `tests/test_revue_code.py` |
| 0.8.9.65 | 2026-10-04 | **Nature de la fiche : une valeur, pas un libellé** (IE-113, L-22) : `MovieMeta.kind` porte une `Nature` (film, série, mini-série, téléfilm, épisode) ; les codes d'OMDb, d'IMDB et d'AlloCiné y sont ramenés par trois tables, l'écran de la fiche met le mot · `tests/test_revue_code.py` |
| 0.8.9.64 | 2026-10-04 | **Correspondance de la fiche : une valeur, pas un libellé** (IE-113, L-23) : `choisir_allocine` rend un `Correspondance` (titre et année, titre, incertaine) ; l'écran de la fiche en tire libellé et couleur au lieu de tester le début du texte · `tests/test_revue_code.py` |
| 0.8.9.63 | 2026-10-04 | **Couleur « HD audio » lue sur le profil** (IE-113, L-43) : la colonne s'allumait en comparant le libellé à « oui », récidive d'UX-29 qu'une traduction aurait éteinte ; elle lit `preserve_hd_audio` · `tests/test_config.py` |
| 0.8.9.62 | 2026-10-04 | **Sous-titre texte en MP4 : plus de temps écrasés après un long silence** (§ 8.6) : ffmpeg perd les temps d'un `mov_text` après plus de 2³¹ µs de silence ; `core/sous_titres.py` intercale des répliques invisibles dans un Matroska porteur, lu par l'encodage, le retrait et le réencodage DV · `tests/test_sous_titres_mp4.py` |
| 0.8.9.61 | 2026-10-04 | **Réencodage DV forcé depuis l'assistant** (§ 14.0) : `F2` sur un SKIP le force au lieu de le laisser « ignoré » ; `decision.choisir_codec`, règle unique du codec choisi à la main (assistant, aperçu, pistes, coche), connaît `ENCODE_DV` et reprend le débit de la source · `tests/test_dv_reencodage.py` |
| 0.8.9.60 | 2026-10-04 | **Une vidéo recopiée n'échoue plus sur « copy indisponible ici »** (§ 14.7) : le contrôle des encodeurs sondés lisait `-c:v copy` comme un encodeur ; `encoder.encodeur_a_controler` l'en exclut · `tests/test_capacites.py` |
| 0.8.9.59 | 2026-10-04 | **Une ligne DV forcée se réencode en DV** (§ 14) : `force_skip_to_encode` passait en `ENCODE_HEVC`, donc en copie du flux nommée `.hevc-iris` ; il retient désormais `ENCODE_DV` quand la source s'y prête · `tests/test_dv_reencodage.py` |
| 0.8.9.58 | 2026-10-04 | **Le lot suit l'ordre alphabétique** (§ 14.7) : l'aperçu, `F2` et le collage parcouraient la sélection — un ensemble — dans l'ordre des hachages ; `BrowserScreen._cochees` la rend triée comme le tableau · `tests/test_ordre_lot.py` |
| 0.8.9.57 | 2026-10-03 | **Réencodage DV en MP4** (§ 7.4, IE-108) : `ENCODE_DV` ne force plus le Matroska ; MP4 `hvc1` dès que le contenu le permet — mkvmerge recompose un MKV, que ffmpeg remuxe avec `-strict unofficial` pour garder la boîte `dvcC` (`dovi.build_dv_mp4_remux`, étape 7 de `_encode_dv`) ; profil 7 inclus, converti en 8.1 · mesuré sur un extrait DV 8.1 : `dvcC` P8 compat. 1, RPU de 2 270 images intact · `tests/test_dv_reencodage.py` |
| 0.8.9.56 | 2026-10-03 | **Profils livrés `serie_*` renommés `series_*`** (§ 6, IE-112) : noms neutres, non traduits ; migration du `profiles.toml` existant au chargement (seulement si le nouveau nom est libre, ordre et réglages conservés, profils de l'utilisateur intouchés) et du profil actif mémorisé · `tests/test_migration_profils.py` |
| 0.8.9.55 | 2026-10-03 | **Tolérance de ±10 % sur le débit cible** (§ 8.1) : le CAS 1 ne se déclenche qu'au-delà de la cible + 10 % (`TOLERANCE_DEBIT_PCT`) ; une sortie VBR qui dépasse légèrement sa cible n'est plus reproposée au réencodage · `tests/test_tolerance_debit.py` |
| 0.8.9.54 | 2026-10-03 | **Nouveaux profils livrés** (§ 6) : `data/profiles.default.toml` reprend tel quel le `profiles.toml` de l'auteur — quatorze profils, `serie_anime` en tête, `film_*` devenus `movie_*`, variantes `_delete` ; semé à la première installation, jamais écrasé par une mise à jour ; aucun changement de code |
| 0.8.9.53 | 2026-10-03 | **« Ne rien faire » après le lot, par défaut** (§ 14.7, § 14.8) : `ACTIONS_FIN` gagne `rien`, en tête et par défaut (`ACTION_FIN_DEFAUT`, `[energie] action_fin`) ; `E` refuse d'armer quand c'est le choix ; choisi pendant un lot coché, il désarme · `tests/test_veille.py` |
| 0.8.9.52 | 2026-10-03 | **Copier un profil** (§ 14, `F5`) : `C` ouvre le formulaire de création sur les réglages du profil sous le curseur, nom proposé par `nom_de_copie()` ; une création refuse un nom déjà pris (elle écrasait le profil existant) · **`F4` élargi** (§ 14.9) : la marge de cellule comptée des deux côtés, `⚠ suppr.` n'est plus tronqué · `tests/test_copie_profil.py` |
| 0.8.9.51 | 2026-10-03 | **Licence GPL-3.0-or-later** (§ 17.3) : fichier `LICENSE`, section Licence du README ; préalable à la traduction participative (IE-111) ; aucun changement de code |
| 0.8.9.50 | 2026-10-03 | **README : arbre de décision illustré** : six schémas Mermaid (vue d'ensemble, définition et palier, vidéo et Dolby Vision, audio, sous-titres, conteneur) et le tableau des noms de sortie, établis sur `core/decision.py` et `core/encoder.py` ; aucun changement de code |
| 0.8.9.49 | 2026-10-03 | **Copie Dolby Vision en MP4 : `dvcC` écrit** (§ 6, IE-109) : `build_command` ajoute `-strict unofficial` quand la vidéo DV est copiée vers un MP4 ; sans lui ffmpeg 8.1.2 omettait l'enregistrement de configuration DV et la sortie `.dv-iris.mp4` n'était que du HDR10 pour le téléviseur · `tests/test_conteneur.py` |
| 0.8.9.48 | 2026-10-03 | **`HDR10Plus` et `HDR10P` reconnus comme `HDR10+`** (§ 8.7, IE-81) : ajoutés à `JETONS_HDR_PLUS` ; une sortie SDR ne garde plus la marque, et un nom qui la porte ne reçoit plus `.hdr10` en redite · `tests/test_hdr_audio_nom.py` |
| 0.8.9.47 | 2026-10-02 | **PGS complet doublé écarté** (§ 8.6) : la règle du PGS forcé (0.8.9.40) s'étend aux sous-titres complets ; sans sélection manuelle, un sous-titre image est décoché quand un sous-titre texte de même langue et de même nature (forcé / complet) est retenu (`decision._pgs_doubles`) · `tests/test_langues.py`, `tests/test_conteneur.py` |
| 0.8.9.46 | 2026-10-02 | **Filtre de l'accueil** (§ 14) : `L` filtre par type d'image (DV, un profil DV, HDR sans DV, SDR), `Z` masque les SKIP ; une ligne cochée reste visible · `tests/test_filtre_accueil.py` |
| 0.8.9.45 | 2026-10-01 | **La colonne Fichier suit la fenêtre** (§ 14, accueil) : `BrowserScreen.on_resize` recalcule la place laissée à Fichier quand la fenêtre change de taille, une fois la rafale d'événements finie · `tests/test_accueil.py` |
| 0.8.9.44 | 2026-10-01 | **Marque `-iris` et groupe retiré** (§ 8.7) : toute sortie finit par `-iris` au lieu de `.IRIS` (`scanner.MARQUE_IRIS`), l'ancienne marque n'est plus reconnue · le groupe de la release (`-GROUPE`, ` - GROUPE`) ne passe plus dans la sortie (`scanner.stem_sans_groupe`, `JETONS_RELEASE`), encodage, greffe et jonction · `tests/test_nom_iris.py` |
| 0.8.9.43 | 2026-10-01 | **La veille bloquée pendant les traitements** (§ 14.7) : `core/veille.py`, demande d'alimentation `PowerCreateRequest` au motif lisible dans `powercfg /requests`, relevée toutes les 5 s sur les mêmes travaux que `F10` · indicateur « ☾ » dans l'en-tête · **après le lot** (`E`) : veille, veille prolongée ou arrêt une fois tout fini, après 60 s annulables, interrupteur décoché à chaque lot · **options** (§ 14.8, `F5` → `U`) : `[energie] empecher_veille` (vrai) et `action_fin` (`veille`) · `tests/test_veille.py` |
| 0.8.9.42 | 2026-10-01 | **Fenêtre des clés : boutons et case OMDb visibles** (§ 14.8, IE-101) : boutons « Vérifier et enregistrer » et « Plus tard » ; la zone des services défile sous eux au lieu de les pousser hors du cadre, et se compacte pour que la case « Ne plus demander » d'OMDb se voie dès 40 lignes · `tests/test_cles.py` |
| 0.8.9.41 | 2026-10-01 | **Audio entrelacée quand elle vient d'une autre entrée** (§ 12.1) : les sous-titres de la source sont lus par une entrée dédiée dès que l'audio vient de la passe préalable ou d'une greffe ; sans cela, l'audio s'arrêtait à 32 s sur lecteur matériel · `tests/test_prepass_audio.py` |
| 0.8.9.40 | 2026-09-30 | **PGS forcé doublé écarté** (§ 8.6, IE-73) : sans sélection manuelle, un sous-titre image forcé doublé par un sous-titre texte forcé de même langue ne passe plus dans la sortie ; seul forcé de sa langue, il reste · `SubtitleTrack.forced` lu depuis `disposition` · `tests/test_langues.py` |
| 0.8.9.39 | 2026-09-30 | **Le HEVC en MP4 est étiqueté `hvc1`** (§ 8.6, IE-74) : `-tag:v hvc1` sur toute sortie MP4 dont la vidéo est du HEVC (`_sortie_hevc`) et sur le retrait DV en MP4 ; le G3 lit `hev1` et `hvc1` en lecture directe, les lecteurs Apple exigent `hvc1` · `tests/test_conteneur.py` |
| 0.8.9.38 | 2026-09-30 | **Une release publiée se voit dans l'heure** : cache de `updater.py` ramené de 24 h à 1 h, et invalidé quand la version installée a changé · `tests/test_updater.py` |
| 0.8.9.37 | 2026-09-30 | **Les clés d'API se saisissent dans l'application** (§ 14.8, IE-101) : fenêtre au lancement si une clé manque et depuis `F5` → `K`, lien vers la page du service, vérification avant enregistrement, « Ne plus demander » · `tests/test_cles.py` |
| 0.8.9.36 | 2026-09-30 | **La file se réordonne** (§ 14.7, IE-100) : `Ctrl+↑/↓` déplace, `Suppr` retire un fichier en attente · `tests/test_arret_encodage.py` |
| 0.8.9.35 | 2026-09-30 | **L'en-tête annonce la file** (§ 14.7, IE-100) : « F12 Encodages en cours · n/N · % », « F12 Lot terminé », « F12 Fichiers » · `tests/test_arret_encodage.py` |
| 0.8.9.34 | 2026-09-30 | **Une file d'encodage, la navigation reste libre** (§ 14.7, IE-100) : `F2` ajoute à la file, `F12` bascule, `⌫` ne stoppe plus, `X` arrête tout ; doublons refusés, réglages figés, `Ctrl+D` et `F10` gardés · `tests/test_arret_encodage.py` |
| 0.8.9.33 | 2026-09-30 | Écran des pistes : « Profil : serie_basic » sans crochets, comme ailleurs depuis UX-13 · captures `shots_tui.py` : le donneur se cherche sans son icône |
| 0.8.9.32 | 2026-09-30 | **La fiche AlloCiné désigne le bon film** (§ 14, UX-24) : appariement sur le titre français et original puis l'année (`choisir_allocine`), séries reconnues (`series`), confiance affichée · `tests/test_revue_code.py` |
| 0.8.9.31 | 2026-09-30 | **La commande du mux est repliée** (§ 14, UX-26) : noms de fichier au lieu des chemins, quatre lignes au plus · `tests/test_muxer.py` |
| 0.8.9.30 | 2026-09-30 | **L'explorateur du donneur ressemble à l'accueil** (§ 14, UX-22) : icônes, colonne Taille, `⌫` remonte, plus de ligne « .. » · `tests/test_modales.py` |
| 0.8.9.29 | 2026-09-30 | **Le formulaire de profil a une casse** (§ 14, UX-23) : titres en capitales, libellés en casse de phrase avec unité, « Édition » · `tests/test_profile_form.py` |
| 0.8.9.28 | 2026-09-30 | **Une donnée, une forme** (§ 14, UX-21) : noms de codec ramenés à ceux de ffprobe (`nom_codec`), langue inconnue « ? » (`langue_affichee`), résolution « 1920x1080 » partout · WebVTT muxé par mkvmerge illisible par ffprobe 8.1.2, à vérifier · `tests/test_barres.py` |
| 0.8.9.27 | 2026-09-30 | **Les profils ont une seule présentation** (§ 14, UX-13) : `F4` et `F5` partagent colonnes et cellules (`cellules_profil`), nom sans crochets ni capitales, écran « Gérer les profils » · `tests/test_config.py` |
| 0.8.9.26 | 2026-09-30 | **Les nombres s'accordent** (§ 14, UX-15) : `core/texte.py` (`accorde`, `pluriel`) remplace les « (s) » ; « (s) » refusé par test · `tests/test_barres.py` |
| 0.8.9.25 | 2026-09-30 | **Les décisions de piste parlent une seule langue** (§ 14, UX-09) : « → copie », « → copie MKV/MP4 », états « terminé » / « échec » ; « ← SKIP » conservé · `tests/test_audio_hd.py` |
| 0.8.9.24 | 2026-09-30 | **L'assistant ne dit ses touches qu'une fois** (§ 14, UX-11) : libellés du pied de page propres à chaque étape, ligne d'aide réservée aux notes de mesure · `tests/test_touches.py` |
| 0.8.9.23 | 2026-09-30 | **Une seule notation de touches** (§ 14, UX-10) : le guide `H` écrit les touches comme le pied de page (`touche()`), plus de crochets ni d'apostrophes dans les messages · `tests/test_touches.py` |
| 0.8.9.22 | 2026-09-30 | **Une seule forme de barre d'état** : « Titre — élément · élément » (`barre_etat`, § 14, UX-14) · `R` s'annonce « Encoder le dossier » · `tests/test_barres.py` |
| 0.8.9.21 | 2026-09-30 | **`T` Pistes figure dans le pied de page de l'accueil** (§ 14.1, UX-25) — seul accès aux pistes en mode assistant |
| 0.8.9.20 | 2026-09-30 | **Un nom par action** (§ 14, UX-08) : Encoder partout (Run, Lancer), Aperçu (Dry-run), Encoder le dossier (Run récursif), Joindre / Jonction (Coller / Collage) · `tests/test_collage.py`, `tests/test_volumes.py` |
| 0.8.9.19 | 2026-09-30 | **Une lettre, un sens entre écrans voisins** (§ 14, UX-12) : l'assistant muxe par `F3` et encode par `F2` (étaient `M`, `E`) ; le recalage montre les plages par `G` et force le candidat par `F` (étaient `S`, `A`) · `tests/test_touches.py` |
| 0.8.9.18 | 2026-09-30 | **Une touche de fonction, un seul sens** (§ 14.1, UX-07) : l'accueil passe Récursif sur `R`, le collage sur `J` (« Joindre »), AlloCiné et IMDB sur `I` — une fiche, `Tab` bascule · `tests/test_touches.py`, `tests/test_modales.py` |
| 0.8.9.17 | 2026-09-30 | **L'alerte « Suppr. » de la gestion des profils lit le booléen du profil**, plus le libellé « oui » (UX-29) · `tests/test_config.py` |
| 0.8.9.16 | 2026-09-30 | **Les colonnes à largeur fixe tiennent leur en-tête** (`largeur_entete`, § 14, UX-28) — donneur, OpenSubtitles, encodage, recalage, pistes, assistant ; largeur littérale refusée par test · `tests/test_troncature.py` |
| 0.8.9.15 | 2026-09-30 | **La colonne Taille tient « 999.9 Go »** : plancher de contenu à 8, accueil et dry-run, largeurs persistées comprises (§ 14, UX-20) · `tests/test_troncature.py` |
| 0.8.9.14 | 2026-09-30 | **L'accueil tient en 160 colonnes** (§ 14, UX-19) : Fichier prend la place restante, le plafond compte les marges des cellules et la barre de défilement, la colonne active se repère en vidéo inverse au lieu de « ◄► » · `tests/test_troncature.py` |
| 0.8.9.13 | 2026-09-30 | **Une colonne redimensionnable tient son en-tête**, marqueur « ◄► » compris (§ 14, UX-27) — accueil, dry-run, pistes · `tests/test_troncature.py` |
| 0.8.9.12 | 2026-09-29 | **Une ligne SKIP cochée montre la décision forcée** (§ 14.1, UX-18), en orange, retrait DV compris ; la coche le notifie · `tests/test_arret_encodage.py` |
| 0.8.9.11 | 2026-09-29 | **`F1`/`F2` sans sélection, `F2` du dry-run sans rien à encoder le disent** (§ 14.1, UX-17) · `tests/test_arret_encodage.py` |
| 0.8.9.10 | 2026-09-29 | **Fin d'encodage** (§ 14.7, UX-16) : pied réduit à la navigation, bilan et chemins des sorties ; plus de « ✓ » en double sur la ligne · `tests/test_arret_encodage.py` |
| 0.8.9.9 | 2026-09-29 | **Quitter dit ce qui tourne** (§ 14.10, UX-06) : message tiré des workers en cours, « Aucun traitement en cours » sinon ; encodage, mux et collage arrêtés, sortie partielle effacée · `tests/test_arret_encodage.py` |
| 0.8.9.8 | 2026-09-29 | **L'accueil suit un encodage** (§ 14.1, UX-04) : vue relue, sources réussies décochées · `tests/test_arret_encodage.py` |
| 0.8.9.7 | 2026-09-29 | **Formulaire de profil : valeur hors liste conservée** (§ 14.8, UX-03) : « Select.NULLk » et `Select.NULL` enregistré en mémoire · `tests/test_profile_form.py` |
| 0.8.9.6 | 2026-09-29 | **`↵` ne lance plus l'encodage depuis le dry-run** (§ 14.6, UX-05) : seule `F2` lance · `tests/test_arret_encodage.py` |
| 0.8.9.5 | 2026-09-29 | **Quitter un encodage en cours se confirme** (§ 14.7, UX-01, UX-02) : `⌫`/`Esc` arrêtaient et effaçaient la sortie sans rien demander, `Ctrl+Home` dépilait en laissant ffmpeg tourner · drapeau `_abandon` et `_demarrer()` : rien ne démarre après l'arrêt, mkvmerge compris · l'intermédiaire d'un mux préalable échoué ou interrompu est effacé · `tests/test_arret_encodage.py` |
| 0.8.9.4 | 2026-09-28 | **Dégradé Estim. plus lisible** (§ 14.1) : gris dans ±5 %, puis vert clair → vert vif et orange clair → orange sombre, progression logarithmique ; remplace le vert profond et le départ jaune, trop sombres · `tests/test_sorties_visibles.py` |
| 0.8.9.3 | 2026-09-28 | **Redimensionner les colonnes de l'accueil ne relit plus le disque** : la taille des fichiers est relevée par le worker de scan (`BrowserScreen._tailles`), plusieurs secondes par frappe sur un partage réseau auparavant · **`Ctrl+Home` ramène aux volumes** (§ 14.11), y compris depuis l'accueil · `Tab` sur l'écran des volumes ne fait plus tomber l'application · `tests/test_accueil.py` |
| 0.8.9.2 | 2026-09-26 | **NVENC refusé par le pilote, dit au lancement** (§ 14) : la sonde garde la sortie d'erreur, `alerte_pilote_nvenc()` reconnaît « required nvenc API version » et nomme le pilote exigé ; notification au lancement, message au refus d'un fichier, cause ajoutée à `diagnostiquer()` avant « could not open encoder » |
| 0.8.9.1 | 2026-09-24 | **Mise à jour de l'application depuis la release GitHub « Latest »** (§ 3.1.2) : `updater.py` (bibliothèque standard seule), appelé par `launch.bat` avant `main.py` ; confirmation `[O/n]` par défaut, réglable par `[updates] app` (`ask`/`auto`/`off`) ; empreinte SHA256 exigée, fichiers personnels intouchables, sauvegarde et restauration, manifeste ; relance depuis un bloc `( )` unique, cmd relisant un `.bat` réécrit à l'ancienne position (mesuré) · `tests/test_updater.py` |
| 0.8.9.0 | 2026-09-24 | **Release** — rassemble 0.8.8.11 à 0.8.8.17 : sorties signées `.<caractéristique>.IRIS` en minuscules, OpenSubtitles.com depuis F9, dégradé Estim., **retrait du Dolby Vision en MP4 réparé** (§ 7.3), wiki du projet · le schéma du wiki passe dans `wiki/SCHEMA.md`, versionné |
| 0.8.8.17 | 2026-09-24 | **Wiki sur le modèle « LLM Wiki » de Karpathy** : couches `raw/` (immuable), `sources/`, `entites/`, `concepts/`, `syntheses/` ; `index.md` et `log.md` ; frontmatter YAML, liens `[[…]]` ; schéma et opérations ingest / query / lint dans `CLAUDE.md` · `tests/test_wiki.py` : liens, orphelins, index, frontmatter, journal · aucun changement de code applicatif |
| 0.8.8.16 | 2026-09-24 | **Wiki du projet** (`wiki/`) : base de connaissance rangée par sujet — chaîne de diffusion, codecs vidéo, HDR et Dolby Vision, audio, sous-titres, conteneurs, outils, synchronisation, noms de release, pièges et leçons, questions ouvertes — chaque fait avec son niveau de preuve · `CLAUDE.md` en fait la référence à consulter et à enrichir · aucun changement de code |
| 0.8.8.15 | 2026-09-24 | **Retrait du DV en MP4 : son sans image, puis plantage sur téléviseur** (§ 7.3) : le MP4 était recomposé à partir du flux brut de `dovi_tool remove`, sans horodatage, et ffmpeg y écrivait PTS = DTS sur chaque image. Il passe maintenant en une passe ffmpeg depuis la source avec `-bsf:v dovi_rpu=strip=1` (`build_strip_mp4`, remplace `build_strip_remux_mp4`), et les horodatages de la source sont conservés · le profil 7 reste en MKV · un ffmpeg sans filtre `dovi_rpu` échoue avec un message (`strip_bsf_disponible`) · le MKV, vérifié sain, est inchangé |
| 0.8.8.14 | 2026-09-23 | **Caractéristiques du suffixe en minuscules** (§ 8.7) : `.hevc.IRIS`, `.h264.IRIS`, `.av1.IRIS`, `.dv.IRIS`, `.hdr10.IRIS`, `.mux.IRIS`, `.join.IRIS` — seule la marque reste en capitales · `mux` / `join` reconnus sans casse, les greffes et collages écrits en capitales restent des entrées |
| 0.8.8.13 | 2026-09-23 | **Sous-titres OpenSubtitles.com depuis F9** (§ 9.8) : `O` dans le choix du donneur cherche par empreinte puis par nom dans les langues du profil, les sous-titres de la release exacte en tête (`≡`) ; `↵` télécharge dans le dossier temporaire et le `.srt` reprend le chemin ordinaire du donneur — pistes, langue déduite du nom, recalage · section `[opensubtitles]` de `config.toml` (`api_key`, `username`, `password`) · refus de l'API lus en français · `tests/test_opensubtitles.py`, smoke [21] et [21b] |
| 0.8.8.12 | 2026-09-23 | **Le dégradé de la colonne Estim. part du gris** (§ 14.1) : 0 % gris (écart arrondi nul), gain → vert profond atteint à −100 %, perte → du jaune à l'orange des alertes, atteint à +100 % et conservé au-delà. Remplace l'échelle vert → jaune → orange bornée à −50 % / +25 %, qui mettait le jaune — la teinte la plus voyante — sur les écarts nuls, et saturait le vert dès −50 % · plus de gras sur les pertes · `tests/test_sorties_visibles.py` |
| 0.8.8.11 | 2026-09-23 | **Nommage des sorties à la manière des releases** (§ 8.7, § 15.2) : les marques se séparent par des points et toute sortie finit par `.IRIS`, précédée de sa caractéristique — `.HEVC.IRIS`, `.H264.IRIS`, `.AV1.IRIS`, `.DV.IRIS`, `.HDR10.IRIS`, et `.MUX.IRIS` / `.JOIN.IRIS` pour la greffe et le collage · une caractéristique que le nom annonce déjà n'est pas répétée (`suffixe_sans_redite`) · le filtre ne regarde plus que la marque `.IRIS` finale, `MUX` et `JOIN` exceptés ; les noms `_[…]` ne sont plus reconnus · `scanner.suffixes_produits` disparaît · `tests/test_nom_iris.py` |
| 0.8.8.10 | 2026-09-02 | **La colonne Audio d'un retrait de RPU dit ce que le fichier contiendra** : `audio_summary` faisait une exception pour `STRIP_DV` et affichait toutes les pistes de la source — vrai jusqu'à la v0.8.8.0, où le retrait a appris à appliquer la décision audio (Matroska produit à part pour les transcodées, `--audio-tracks` pour les exclues). Depuis, c'est l'exception qui promettait des pistes que le fichier n'aurait pas, avec un commentaire affirmant l'inverse du code · `tests/test_strip_dv.py` verrouille le sens neuf |
| 0.8.8.9 | 2026-09-02 | **Une sortie SDR perd aussi sa profondeur** (§ 8.7) : les marques HDR partaient déjà, celle de la profondeur restait — or le tone mapping finit sur `format=yuv420p`, le fichier ressort en 8 bits et un `10bits` dans son nom promet une précision qu'il n'a plus. `10bit`, `10bits`, `10 bits`, `10-bit` partent avec le reste ; en sortie HDR10 la profondeur reste vraie (`yuv420p10le`) et n'est pas touchée · `Dolby Video` rejoint les marques Dolby Vision reconnues |
| 0.8.8.8 | 2026-09-02 | **`UHD` est une marque de définition comme les autres** (§ 8.7) : `Titre.Film.2017.2160p.UHD.BluRay` rabattu en 1080p ressortait `1080p.UHD.BluRay` — une moitié corrigée, l'autre toujours fausse. `UHD` rejoint `JETONS_RESOLUTION_4K`, et la fusion des marques voisines devenues identiques rend `1080p.BluRay` là où deux substitutions auraient écrit `1080p.1080p.BluRay` |
| 0.8.8.7 | 2026-09-02 | **Le nom de sortie dit le HDR et l'audio de sortie** (§ 8.7) : un `Film.2160p.DV` ramené en HDR10 n'est plus du Dolby Vision, un `Film.TrueHD.7.1` sorti en E-AC3 5.1 annonce un format absent du fichier · `dv_action` décide des marques HDR — `DV`, `DoVi`, `Dolby Vision`, `HDR`, `HDR10` deviennent `HDR10` en sortie HDR10, deux marques voisines devenues la même étant fondues, et partent toutes en sortie SDR, `HDR10+` compris ; `HDR10+` survit au passage en HDR10, que le retrait du RPU laisse intact · la marque audio de la famille transcodée devient l'étiquette du codec écrit (mêmes jetons que les titres de pistes), avec la disposition qui se replie et la mention `Atmos` que la conversion emporte ; une famille qu'une autre piste conserve n'est pas touchée · SKIP est écarté d'un bloc, sa seule sortie étant une greffe `_[mux]` que mkvmerge recopie sans rien convertir · les quatre réécritures se composent dans `_stem_a_jour()` et partagent une seule machinerie de marques (`stem_marques_retirees`, `stem_marques_remplacees`) — trois expressions régulières presque identiques dans un même fichier étaient le début d'une divergence · `tests/test_hdr_audio_nom.py` |
| 0.8.8.6 | 2026-09-02 | **Le nom de sortie dit le codec de sortie** (§ 8.7) : un `Film.1080p.x264` réencodé en HEVC ressortait `Film.1080p.x264_[hevc]` — deux codecs annoncés, dont un que le fichier n'a plus. `scanner.stem_sans_marque_codec()` retire `x264`, `x265`, `H264`, `H265` (avec ou sans point), `HEVC`, `AV1` et `VP9`, prises comme mot entier — `AV1ator` et `MVP9` intacts — avec leur paire de crochets ou de parenthèses, la ponctuation se recollant derrière (`Film.1080p.x265-GROUP` → `Film.1080p-GROUP_[hevc]`) · une marque juste part aussi : à côté de `_[hevc]`, un `x265` répète la même chose deux fois · le retrait ne joue que pour `ACTIONS_CODEC_NOMME` et hors vidéo recopiée — un remux HDR10 et un DV copié sortent dans le codec de la source, que `_[hdr10]` et `_[dv]` ne nomment pas · `tests/test_codec_nom.py` |
| 0.8.8.5 | 2026-09-02 | **Le nom de sortie dit la définition de sortie** (§ 8.7) : un `Film.2160p.BluRay` rabattu en 1080p ressortait `Film.2160p.BluRay_[hevc]` — le nom promettait une définition que le fichier n'a plus, et dans une médiathèque c'est le nom qu'on regarde pour choisir. `scanner.stem_resolution_ramenee()` remplace la marque de la source par celle de la sortie — `2160p`, `4K`, `4KLight` avec ou sans séparateur → `1080p` — prise comme mot entier, le `4K` de `H4K` et le `2160` de `3840x2160` restant intacts · la substitution ne touche que le nom du fichier produit, jamais la source, et ne joue que si la définition baisse vraiment : `keep_4k` et une vidéo recopiée (DV conservé, `-c:v copy`) gardent leur marque, y écrire `1080p` serait le mensonge que ce renommage supprime · `tests/test_resolution_nom.py` |
| 0.8.8.4 | 2026-09-01 | **Dix profils livrés au lieu d'un** (§ 6) : `data/profiles.default.toml`, versionné donc présent dans l'archive d'une release, sème `profiles.toml` au premier lancement. Une installation neuve ouvrait jusqu'ici sur un sélecteur d'un seul élément — le besoin d'origine, ne pas rester bloqué faute de fichier, était couvert au minimum vital · **trois niveaux** : fichier de l'utilisateur, profils livrés, plancher `_default_` codé en dur si l'installation a perdu son fichier livré · un TOML illisible tient désormais la session sur les dix profils livrés, en mémoire seulement — le fichier de l'utilisateur n'est toujours pas réécrit · `serie_basic` en tête (`delete_source = false`) est l'actif du premier lancement ; `video_basic_delete`, seul à effacer la source, est dernier · le fichier livré est une donnée que rien d'autre ne relit : `tests/test_profils_livres.py` en contrôle champs, types, domaines et la croissance des débits audio et vidéo · `smoke_tui._profils_isoles` n'a plus de second profil à fabriquer (IE-60) et exerce ce que reçoit vraiment un nouvel utilisateur |
| 0.8.8.3 | 2026-09-01 | **Les sorties de l'application restent visibles** (§ 14.1) : `deja_produit()` les écartait de la vue depuis IE-49, si bien qu'un film encodé la veille disparaissait de l'écran et que rien ne distinguait « déjà produit » de « jamais existé ». La ligne est là, grisée d'un bloc, décision réelle en clair, sélectionnable et encodable — seul `A` l'ignore. Le filtre reste entier dans le scanner, qui alimente le scan récursif et les lots automatiques (§ 15.2) · **le suffixe d'encodage se remplace au lieu de s'empiler** (§ 8.7) : `Film_[av1]` réencodé en HEVC donne `Film_[hevc]`, plus `Film_[av1]_[hevc]` ; les deux collisions que l'empilement masquait — cible égale à la source, cible existante — se numérotent en `(2)`, et le nom est figé une fois par `resoudre_sorties()` parce que l'écran d'encodage relit `output_path` après coup pour nettoyer une sortie partielle · **la colonne Estim. passe à un dégradé continu vert → orange**, borné à −50 % et +25 %, exception assumée à la table d'emphases ; une vidéo recopiée en reste dehors, son écart nul l'aurait placée en plein jaune · `tests/test_sorties_visibles.py`, smoke [20] à [20c] |
| 0.8.8.2 | 2026-08-30 | **Le profil plancher ramène le Dolby Vision en SDR** (`dolby_vision = "sdr"`, § 6) : `_default_` recopiait `serie_basic` jusque dans son `"hdr10"`, si bien qu'une installation neuve — et toute session retombée sur le plancher faute d'un TOML lisible — sortait du HDR10, délavé sur un téléviseur qui ne le gère pas. Le plancher s'aligne sur `film_basic`, seul réglage qui l'en écarte désormais avec les débits · **le repli d'un profil sans la clé passe lui aussi à `"sdr"`** — cinq sites lisaient `dolby_vision` avec `"hdr10"` en défaut (décision, résumé et colonnes de l'écran Config, pré-sélection et lecture du formulaire) ; les laisser désaccordés aurait affiché « hdr10 » sur un profil que la décision traite en SDR · trois tests du chemin HDR10 s'appuyaient sur ce défaut implicite : ils portent désormais `dolby_vision = "hdr10"` en clair · une valeur *inconnue* reste traitée en HDR10, cas distinct d'une clé absente |
| 0.8.8.1 | 2026-08-30 | **Le smoke test ne dépendait plus du poste de développement** : `tests/smoke_tui.py` échouait sur l'archive publiée à l'étape [5] — une installation neuve n'a pas de `profiles.toml` et l'app en génère un seul, or `ConfigScreen` refuse à raison d'effacer le dernier profil, si bien qu'aucune confirmation ne s'ouvrait. Le dépôt en portant dix, le scénario passait en local et le garde-fou était inopérant là où il sert · `_profils_isoles()` donne au smoke son propre fichier, semé de deux profils, et cesse au passage d'écrire dans la bibliothèque de l'utilisateur · assertion explicite sur le nombre de profils avant la touche `d` |
| 0.8.8.0 | 2026-08-30 | **Réencoder sans perdre le Dolby Vision** (`VideoAction.ENCODE_DV`, § 6 et § 7.4) : le RPU vit entre les tranches d'image du flux HEVC, tout réencodage le détruisait — conserver le DV imposait `-c:v copy`, et le débit cible d'un profil `dolby_vision = "dv"` restait lettre morte · `dovi_tool extract-rpu` en tuyau sur ffmpeg (aucun intermédiaire), encodage vidéo seul en Annex-B sans filtre, `inject-rpu`, remux mkvmerge · RPU du profil 7 converti en 8.1 au passage · garde-fous : couche de base HDR10 obligatoire (5 et 8.4 exclus), résolution inchangée, outils présents — à défaut la copie reprend, annoncée comme telle · Matroska forcé, un MP4 perdrait le RPU · métadonnées HDR10 statiques préservées par NVENC sans drapeau, mesuré · `tests/test_dv_reencodage.py` |
| 0.8.7.4 | 2026-08-30 | **La décision ne promet plus un encodage qu'elle ne fait pas** (§ 6) : conserver le Dolby Vision impose `-c:v copy`, mais l'écran annonçait « → HEVC → DV » et nommait la sortie `_[hevc]` — un fichier de 60 Mb/s ressortait à 60 Mb/s sous un nom qui promettait l'inverse · libellé « → DV (copie) », suffixe `_[dv]`, mention « DV conservé → vidéo copiée » accolée à la raison, emphase verte comme un remux · `scanner.suffixes_produits` connaît `_[dv]`, sans quoi la sortie serait reproposée au scan suivant et un profil `delete_source` effacerait l'original · `tests/test_dv_copie.py` |
| 0.8.7.3 | 2026-08-30 | **Le profil actif survit à la fermeture** (`[app] active_profile` dans `config.toml`, § 6) : il était repris sur le premier profil du fichier à chaque lancement, si bien qu'un profil `delete_source = true` posé en tête devenait actif au démarrage et effaçait les sources d'un lot lancé sans regarder · repli sur le premier du fichier si le profil mémorisé a disparu · la persistance tient dans une propriété de `IrisEncodeApp`, non dans les trois écrans qui changent le profil · champ **Nom** du formulaire reverrouillé en édition : la sauvegarde réenregistre sous l'ancien nom, une frappe y aurait été perdue sans le dire |
| 0.8.7.2 | 2026-08-30 | **`profiles.toml` fait foi** (§ 6) : les profils affichés, et leur ordre, sont ceux du fichier — `load_all` posait d'abord neuf profils codés en dur puis superposait le fichier, imposant l'ordre du code et ressuscitant à chaque lancement un profil livré que l'utilisateur avait retiré, sans pouvoir le supprimer · un seul profil reste en dur, `_default_` (recopie de l'ancien `serie_basic`), qui sème le fichier au premier lancement et tient lieu de secours si le TOML est illisible · la distinction builtin / user disparaît : tout profil s'édite, se renomme et s'efface, sauf le dernier · profil actif au démarrage et point de départ d'un nouveau profil pris sur le fichier, non plus sur un nom codé en dur (§ 14.8) |
| 0.8.7.1 | 2026-08-29 | **Collage de parties** (`core/joiner.py`, § 9bis) : `F6` sur les fichiers cochés recoud un film livré en `part1` / `part2` en un `_[join].mkv` unique, par `mkvmerge` en mode append — sans réencodage · ordre déduit des noms (`part10` après `part2`), montré et corrigeable par `Ctrl+↑/↓` avant lancement · appariement des pistes contrôlé **avant** la copie, blocages et réserves distingués (§ 9bis.3) · durée du fichier produit comparée à la somme des parties (§ 9bis.5) · les parties sont conservées |
| **0.8.7.0** | 2026-08-29 | **Release.** Le raccourci Bureau entre dans le parcours d'installation : README § 5, § 10 et § 11 y renvoient, et le guide s'ouvre désormais sur « comment ouvrir l'application ». Rassemble 0.8.6.1 (guide rattaché au code) et 0.8.6.2 (lanceur `IRIS_Encode.exe`) |
| 0.8.6.2 | 2026-08-29 | **Raccourci Bureau `IRIS_Encode.exe`** (dossier `launcher/`) : un lanceur d'une trentaine de lignes de C#, compilé sur place par `launcher/build.bat` avec le `csc.exe` livré avec Windows, qui ouvre `launch.bat` dans Windows Terminal (console classique à défaut) · icône versionnée en base64 (`iris.ico.b64`), décodée par `certutil` au build, générée de façon déterministe par `make_icon.py` · aucun binaire versionné · README § 5.1 |
| 0.8.6.1 | 2026-08-29 | **`GUIDE.md` remis à jour** après la revue de `core/` — il était resté en 0.8.1.23 · correction d'une inversion `<`/`>` · quatre tests rattachent le guide au code : toute touche annoncée doit répondre, et son en-tête suivre `version.py` |
| **0.8.6.0** | 2026-08-29 | **Release.** Rassemble 0.8.5.1 à 0.8.5.3 : les neuf dernières entrées de la revue de `core/` — profils perdus par une écriture tronquée, sorties de l'application reproposées au réencodage, réserve de mesure invisible, réglage mort, mise à jour qui ne rangeait pas comme l'installation, genre tronqué, et trois coûts de démarrage ou de remux. **La revue est close.** |
| 0.8.5.3 | 2026-08-29 | **IE-53** le genre AlloCiné n'est plus tronqué à cinq caractères (normalisation avant découpage) · **IE-55** `identify()` mémorisé par état de fichier (§ 9.3) : 26 processus mkvmerge pour un remux devenaient un seul · **IE-57** le prédicat du mode HDR10 « quality » n'est plus écrit deux fois. **La revue de `core/` est close.** |
| 0.8.5.2 | 2026-08-29 | **IE-51** `check_on_startup` lu sous `[updates]`, la section où il vit · **IE-54** mise à jour et installation rangent par le même `poser()`, garde-fou d'IE-40 compris · **IE-56** relevé des versions en parallèle au démarrage (§ 4.4) |
| 0.8.5.1 | 2026-08-29 | **IE-50** `profiles.toml` écrit atomiquement et sous verrou — la parade d'IE-39, jamais portée · **IE-49** le filtre du scan dérive de `SUFFIX_BY_ACTION` (§ 15.2) au lieu d'une paire recopiée à quatre endroits · **IE-52** une réserve sur une mesure acceptée a son propre champ, `reason` n'étant lu que sur les échecs |
| **0.8.5.0** | 2026-08-29 | **Release.** Rassemble 0.8.4.3 à 0.8.4.8 : revue de code de `core/` (IE-43 à IE-48), entrée standard des sous-processus (IE-58), touches d'édition visibles à l'écran de recalage (IE-36) |
| 0.8.4.8 | 2026-08-29 | **IE-36** — les touches qui modifient une valeur étaient les seules que l'écran de recalage ne montrait jamais : le bandeau leur donne une ligne propre au champ actif, qu'aucun message ne chasse (§ 14.4) · `Ctrl+↑/↓` et `R`, absents des tables de touches de la spec et du guide, y entrent |
| 0.8.4.7 | 2026-08-29 | **IE-48** — le forçage à 48 kHz de l'AAC employait un spécificateur de flux nu (`-ar:{i}`) : il visait la vidéo puis glissait d'un cran sur les pistes audio, sur les deux chemins qui mappent la vidéo en tête |
| 0.8.4.6 | 2026-08-29 | **IE-58** — treize sous-processus héritaient de l'entrée du terminal, que l'interface écoute : `stdin=DEVNULL` sur les seize lancements du projet (§ 10.6), et un test structurel qui refuse le prochain lancement sans |
| 0.8.4.5 | 2026-08-29 | **IE-47** — points d'insertion non croissants : un `atrim` à l'envers rendait un segment vide et dupliquait le donneur compris entre les deux positions (§ 10.6) · six tests, dont quatre échouent sur le code d'avant |
| 0.8.4.4 | 2026-08-29 | **IE-46** — `retime_audio` se bloquait quand ffmpeg remplissait le tube d'erreur : progression et diagnostics passent désormais par un seul tube (§ 10.6), quatre tests dont deux suspendent la suite sur le code d'avant |
| 0.8.4.3 | 2026-08-29 | **Revue de code, trois défauts silencieux** : après un mux préalable, les pistes greffées n'étaient plus mappées et disparaissaient du fichier produit (§ 12) · `_deep_merge` partageait encore les branches absentes du `config.toml`, et la réinitialisation des colonnes vidait `_DEFAULTS` · `libx265` absent du sondage de lancement rendait `cinema_4k_quality` inutilisable sur toute machine à carte graphique |
| 0.8.4.2 | 2026-08-29 | **`bootstrap.ps1` échouait sur une installation neuve de Windows 11** : Smart App Control bloque le trampoline posé par `uv venv` (erreur 4551) · le `.venv` est créé par le module `venv` de l'interpréteur, qui copie un redirecteur à réputation établie · reconstruction systématique de `.venv`, et blocage nommé au lieu d'un « installation impossible » muet |
| 0.8.4.1 | 2026-08-29 | Ménage du dépôt public : `CLAUDE.md` (aide-mémoire local) sorti du dépôt et de son historique, `audit.md` (rapport v0.7) retiré de l'arbre |
| **0.8.4.0** | 2026-08-29 | **Release.** Rassemble 0.8.3.7 à 0.8.3.12 : guide embarqué (`H`), pas fin de 10 ms, correction de l'arbitrage des ratios de recalage, revue de code IE-38 à IE-41 |
| 0.8.3.12 | 2026-08-29 | **Revue de code, IE-38 à IE-41** : la mesure porte la piste et non son rang · `config.toml` écrit atomiquement et sous verrou · le repli d'installation n'écrit plus un ZIP sous le nom d'un exe · un ffmpeg mort ne passe plus pour un film court |
| 0.8.3.11 | 2026-08-29 | Le guide nomme les touches **en toutes lettres et en capitales** (BACKSPACE, SHIFT+TAB) là où le pied de page garde ses glyphes |
| 0.8.3.10 | 2026-08-29 | **Le guide embarqué** : `H` sur tout écran ouvre la liste des touches, dérivée des `BINDINGS` · rappel « H Aide » dans l'en-tête |
| 0.8.3.9 | 2026-08-29 | **Pas fin de 10 ms** sur le décalage (`Ctrl+↑/↓`), pour finir d'approcher une valeur mesurée |
| 0.8.3.8 | 2026-08-29 | **Le ratio se choisit à la corrélation, plus à la saillance** : une saillance ne se compare pas d'un ratio à l'autre, `_rescale` changeant la longueur du signal donc l'échelle de normalisation — une paire alignée à 10 ms était refusée au profit d'un ratio PAL à 160 s |
| 0.8.3.7 | 2026-08-29 | **La bannière nomme l'interpréteur** : version complète et origine (`.venv` local ou système), le choix de `launch.bat` n'étant plus silencieux |
| 0.8.3.6 | 2026-08-29 | **Installation autonome de Python** : `bootstrap.ps1` récupère uv, un CPython et un `.venv`, sans droits administrateur et sans rien écrire hors du dossier · `launch.bat` choisit entre `.venv`, le Python du PATH et le bootstrap |
| 0.8.3.5 | 2026-08-29 | **Revue d'interface, IE-28 à IE-33** : troncatures rendues visibles (`cellule()` partout), planchers de colonnes tenant les libellés énumérables, plafond de redimensionnement, pied de page dérivé des `BINDINGS`, intitulés de section lisibles, colonnes Source/Titre séparées, « ← écartée » explicite · **avancement global** comptant le fichier en cours, ligne ffmpeg qui n'est plus chassée par la commande |
| 0.8.3.4 | 2026-08-28 | **`T` ouvrait l'assistant** au lieu de l'écran des pistes : la bascule de mode était branchée sur `action_open_tracks`, qui sert aux deux touches · seul `↵` dépend du mode désormais · trouvé par le harnais de captures |
| 0.8.3.3 | 2026-08-28 | **Guide remis à jour** : sept écarts entre ce qu'il annonçait et ce que le code lie · chapitre **Cas d'usage** (§ 3) · `subtitle_languages` devient éditable dans le formulaire de profil, elle ne l'était pas depuis sa création |
| 0.8.3.2 | 2026-08-28 | **Le point de repère propose la réplique** : l'application connaît déjà l'horodatage écrit, il ne reste qu'un nombre à trouver · six répliques réparties dans le film, `↓/↑` pour en changer |
| 0.8.3.1 | 2026-08-28 | **Point de repère** (`R` sur l'écran de recalage) : deux instants donnés à l'oreille bornent la recherche là où la corrélation ne peut pas conclure · un ancrage faux est reconnu comme tel plutôt que suivi · `decision.ambiguites()`, sans appelant depuis la refonte de l'assistant, est retirée |
| **0.8.3.0** | 2026-08-28 | **Version publiée.** Rassemble l'assistant refondu en écran autonome (§ 14.0), la perte silencieuse d'une piste audio transcodée (§ 12.1), la détection de plages par accord entre fenêtres (§ 10), et treize incréments de 0.8.2.5 à 0.8.2.17 |
| 0.8.2.17 | 2026-08-28 | **Détection de plages par accord entre fenêtres** : certains couples plafonnent sous le seuil de confiance même parfaitement alignés — leur décalage est pourtant stable, et c'est cette régularité qu'on lit · recherche bornée à ±30 s, cohérence globale des valeurs, jamais appliqué d'office |
| 0.8.2.16 | 2026-08-28 | **La confiance s'affiche en mots** — aucune / faible / moyenne / excellente — et relativement au seuil, qui varie avec le nombre de repères : un même chiffre n'avait pas le même sens d'une mesure à l'autre |
| 0.8.2.15 | 2026-08-28 | **Touches du footer illisibles en mode assistant** : le jaune se noyait dans l'accent orange · elles passent au blanc sur ce fond, et gardent le jaune sur le bleu du mode manuel |
| 0.8.2.14 | 2026-08-28 | **La mesure de l'assistant visait le mauvais flux** : le tid mkvmerge était passé tel quel au lieu de l'index ffmpeg · `sync.measure_external_track` devient le point d'entrée unique, la traduction n'existe plus qu'une fois · jauge d'avancement pendant la mesure |
| 0.8.2.13 | 2026-08-28 | **Le fichier traité est rappelé sur les cinq étapes** de l'assistant, dans le bandeau — nom seul, tronqué au milieu, jamais le chemin |
| 0.8.2.12 | 2026-08-28 | **Le mode se lit dans le footer et dans sa couleur** : touche `W` nommée par le mode actif, et fond du footer à l'accent du thème en mode assistant — le manuel garde le code couleur par défaut |
| 0.8.2.11 | 2026-08-28 | **Assistant refondu** : écran autonome de cinq étapes au lieu d'un enchaînement des écrans existants · bascule par `W` depuis l'accueil, mode affiché dans la barre de profil, `↵` sur un fichier ouvre le parcours · codec, débit et pistes sur un seul écran · une piste greffée est mesurée et appliquée aussitôt · mux et encodage toujours offerts, puis retour à l'accueil |
| 0.8.2.10 | 2026-08-28 | **`Ctrl+Home` — retour à l'accueil** depuis les sept écrans non modaux, pour enchaîner les fichiers sans remonter la pile un écran à la fois. `Home` reste la navigation dans les tables · les deux écrans qui portent un travail non validé confirment avant de le perdre |
| 0.8.2.9 | 2026-08-28 | **Le flux `bin_data` des sorties MP4 identifié** : c'est la piste de chapitres, seule forme sous laquelle le MP4 sait les porter. Pas une piste parasite, rien à corriger — noté pour ne pas le réenquêter (§ 8.6) |
| 0.8.2.8 | 2026-08-28 | **Passe audio restreinte aux sources sans perte** — l'AC3 du même fichier sort indemne, la passe ne se paie donc plus sur la plupart des encodages · **`pistes_audio_vides`** : un code de retour nul ne vaut plus succès, la sortie est relue et une piste écourtée fait échouer le fichier au lieu de passer |
| 0.8.2.7 | 2026-08-28 | **Le défaut d'IE-22 tient à la simultanéité, pas à la sortie** : séparer les fichiers de sortie ne sauve pas la piste, il suffit que le sous-titre soit *mappé* dans l'invocation. Seul un processus distinct protège — ce que fait la parade. Caractérisation corrigée dans la spec, le code et les tests |
| 0.8.2.6 | 2026-08-28 | **Une piste audio transcodée disparaissait en silence** quand la même commande recopiait un sous-titre au premier repère tardif — deux trames produites au lieu de 1 875. Cause d'IE-12 et IE-16, closes faute d'explication : le fichier « mal entrelacé » n'avait pas de piste anglaise. Passe audio préalable, payée seulement quand les deux conditions sont réunies |
| 0.8.2.5 | 2026-08-28 | **IE-17 clos par la mesure** : le mode « HDR10 quality » (libx265) garde `-maxrate` égal à la cible, et c'est le bon réglage — 99,9 % du débit visé, contre 93,6 % avec la marge appliquée à NVENC. Les deux encodeurs veulent des réglages opposés · `tests/test_x265_debit.py` fait échouer une harmonisation |
| 0.8.2.4 | 2026-08-28 | **`SubtitleTrack.title`** : le nom déclaré était lu par le scanner puis jeté — six pistes « Français (…) » ne se distinguent que par lui · colonnes élargies (sélecteur du donneur, `Nom` du recalage) et `tronquer_milieu`, qui coupe au milieu parce que le sens est à la fin |
| 0.8.2.3 | 2026-08-28 | **Le recalage mesuré se reporte seul sur les sous-titres du même donneur** : il fallait le recopier piste par piste avec `c`, une copie sans information dont l'oubli sortait une piste décalée en silence · trois garde-fous — même fichier, jamais une piste déjà décidée, depuis une audio seulement |
| 0.8.2.2 | 2026-08-28 | **La piste greffée n'était pas celle choisie** sur le chemin de réencodage : le donneur entrant en entier, `-map {n}:s:0` rendait toujours son premier flux — la piste « forced » d'un rip, 23 répliques par épisode. Langue et titre venaient de la bonne piste, d'où une piste nommée correctement et vide à l'écran. Le chemin mkvmerge n'était pas touché, il raisonne en tid |
| 0.8.2.1 | 2026-08-28 | **Trois défauts de l'assistant** : revenir sur l'étape des langues levait un `IndexError` · un choix révisé ne pouvait que retirer une piste, jamais la rendre · la table perdait le focus, les flèches ne déplaçaient plus le curseur · les cases partent cochées sur ce que la décision garde déjà |
| 0.8.2.0 | 2026-08-28 | **Assistant** (§ 14.0) : mode d'entrée de l'application, un fichier à la fois, quatre étapes dont deux conditionnelles · `F12` bascule vers le parcours libre pour la session · **codes ISO 639-2 réconciliés** — `audio_languages = ["fre"]` excluait silencieusement une piste étiquetée « fra » · clé `subtitle_languages` : les sous-titres n'étaient filtrés par rien, 43 pistes traversaient la chaîne |
| 0.8.1.27 | 2026-08-28 | **Recette de greffe complétée** (`GUIDE.md` § 3) : elle s'arrêtait après la mesure de l'audio et ne disait pas quoi faire des sous-titres — la réponse existait, éclatée entre § 2.4, § 4.3 et § 4.5 · table des quatre suites possibles selon le résultat de la mesure · rappel de vérifier ce que la cible contient déjà |
| 0.8.1.26 | 2026-08-28 | **Plafond de transcodage E-AC3 ramené à 1 024k** : suivre le débit de la source donnait un E-AC3 à 3 501k face à un TrueHD, soit 5,66 Go de piste sur un film de 3 h 35 — l'encodeur monte à 6 144k, mais aucun décodeur ne tire quoi que ce soit d'un DD+ 5.1 au-delà du palier haut usuel |
| 0.8.1.25 | 2026-08-28 | **La décision audio s'applique au retrait du Dolby Vision** (§ 7.3) : le chemin ne portait que la vidéo, un TrueHD annoncé « → E-AC3 » sortait en TrueHD sous son ancien titre · transcodage en étape 3 puis `--no-audio` sur la source ; exclusion de piste et de sous-titre par options mkvmerge, sans passe · le MP4 transcode dans sa passe ffmpeg existante |
| 0.8.1.24 | 2026-08-28 | **Le débit demandé redevient une cible** : `-rc cbr` avec `-maxrate` égal à `-b:v` en faisait un plafond que seules les pertes pouvaient déplacer · VBR avec 50 % de marge, tampon doublé — 92 % → 99 % du débit demandé sur un film en prises de vues réelles · le retrait sur contenu facile (animation, 10 bits) n'est pas un défaut : mesuré plus fidèle qu'un 8 bits consommant 62 % de bits en plus |
| 0.8.1.23 | 2026-08-28 | **Sortie des outils lue en UTF-8** : `text=True` laissait Python décoder ffprobe en cp1252 ; un tag contenant « ❤️ » tuait le thread de lecture, `stdout` valait `None` et le fichier disparaissait de la liste sans message · six appels corrigés (`scanner`, `encoder`, `muxer` ×2, `preflight`, `sync`) |
| 0.8.1.22 | 2026-08-28 | **L'AV1 était cassé sur toute machine** : `-profile:v` passé à `av1_nvenc`, qui n'a pas cette option · capacités d'encodage sondées au lancement, option conservée mais annotée, refus qui nomme la cause · diagnostic des échecs ffmpeg |
| 0.8.1.21 | 2026-08-28 | **Sources WebM / VP9 / AV1 / Opus** : le CAS 3 ne regarde plus la résolution — un VP9 ou AV1 en 1080p ou 4K restait en `← SKIP`, donc illisible chez le destinataire · `CODECS_LISIBLES` nomme le critère |
| 0.8.1.20 | 2026-08-28 | **Clé `container`** (`auto` / `mp4` / `mkv`, § 8.6) : le profil exprime une politique, jamais au prix d'une piste perdue en silence · le retrait de Dolby Vision sait sortir en MP4, remuxé par ffmpeg · deux images perdues au remux MP4 (DTS négatifs) |
| 0.8.1.19 | 2026-08-28 | **Le mode HDR10 quality n'injectait rien** : `rpu_info()` analysait du texte quand `dovi_tool` rend du JSON · métadonnées lues dans les SEI par ffprobe, pour toute source HDR, trois fois moins cher au scan · **ffprobe et ffmpeg appelés par leur nom nu** échouaient sur une installation où les binaires ne sont que dans `./bin/` |
| 0.8.1.18 | 2026-08-28 | **Densité** : la notice de survol ne répète plus le dossier de la barre d'état (IE-08) · le footer enchaîne ses trois bandes et ne passe à la ligne qu'au débordement, une à deux lignes rendues au contenu selon l'écran (IE-09) |
| 0.8.1.17 | 2026-08-28 | **L'écran des volumes promettait dix colonnes vides** : colonnes propres (Volume, Espace libre, Total, Occupé), barre d'état, bandeau de profil et footer adaptés au mode (IE-07) · `fmt_bytes` connaît le téraoctet |
| 0.8.1.16 | 2026-08-28 | **Les modales laissent voir l'écran** — la règle globale `Screen { background }` écrasait leur translucidité — et **un seul cadre**, le trait fin, à la place des deux familles graphiques (IE-06) |
| 0.8.1.15 | 2026-08-28 | **Le footer suivait l'écran, pas le focus** : il annonçait « N Nouveau » pendant l'édition d'un profil, où taper « n » écrivait un « n » · les raccourcis basculent avec le formulaire, `F10` reste (IE-05) · isolation des variables de module entre tests (`tests/conftest.py`) |
| 0.8.1.14 | 2026-08-27 | **Un seul rendu pour les noms de touches** : trois notations coexistaient, douze bandeaux les réécrivaient à la main · `TOUCHES` + `touche()`/`raccourcis()` dans `tui.common`, glyphes d'une colonne (IE-04) |
| 0.8.1.13 | 2026-08-27 | **Une seule table de couleurs**, exprimée en rôles (`Emphase`) : la même décision portait deux teintes selon l'écran, le magenta signalait le cas le plus banal et `dark_orange` servait de couleur ordinaire · une décision `STRIP_DV` s'affichait « ? » sur l'écran des pistes (IE-03) |
| 0.8.1.12 | 2026-08-27 | **Toute durée d'au moins une heure perdait son dernier chiffre** : défaut à 6 pour un contenu de 7 · planchers de colonne remontés dans `core.config`, appliqués aussi à la lecture des largeurs déjà persistées · ellipse sur les cellules numériques (IE-02) |
| 0.8.1.11 | 2026-08-27 | **Le markup Rich mangeait les noms** portant `_[mux]`, `_[hevc]`, `_[av1]`, `_[hdr10]`, et les identifiants de profil : 14 afficheurs passent en `markup=False` (IE-01) |
| 0.8.1.10 | 2026-08-27 | Écran des profils réorganisé en six sections, chacune énonçant la conséquence des valeurs choisies (§ 14.8) · `preserve_hd_audio` et `audio_hd_codec` fusionnés en un choix unique : réglés séparément, ils pouvaient se contredire sans que rien ne dise lequel l'emportait |
