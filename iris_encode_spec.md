# IRIS ENCODE — Spécification Fonctionnelle

**Version** : 0.8.8.4 — document de référence courant
**Date** : 2026-09-01
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
├── GUIDE.md                      ← guide d'utilisation (procédures, cas)
├── launch.bat                    ← choix de l'interpréteur, point d'entrée Windows
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
│   ├── decision.py               ← logique métier encodage
│   ├── encoder.py                ← construction commande ffmpeg + exécution
│   ├── dovi.py                   ← wrapper dovi_tool (probe, RPU, x265-params HDR10)
│   ├── muxer.py                  ← wrapper mkvmerge (identify, mux, extrait)
│   ├── joiner.py                 ← collage bout à bout de plusieurs parties
│   ├── sync.py                   ← mesure de décalage par corrélation croisée
│   ├── preview.py                ← lancement mpv (visualisation)
│   └── meta.py                   ← recherche métadonnées IMDB / AlloCiné
├── tui/
│   ├── app.py                    ← application Textual principale
│   ├── common.py                 ← formatage, styles DV, groupes de footer
│   ├── mixins.py                 ← TableNavMixin, ColumnResizeMixin
│   ├── screens/
│   │   ├── browser.py            ← navigation fichiers + sélection
│   │   ├── tracks.py             ← sélection pistes + édition décision vidéo
│   │   ├── donor_picker.py       ← choix du fichier donneur + de ses pistes
│   │   ├── sync.py               ← recalage des pistes externes
│   │   ├── mux_run.py            ← exécution mkvmerge + progression
│   │   ├── join.py               ← ordre des parties + collage + progression
│   │   ├── dryrun.py             ← prévisualisation décisions
│   │   ├── run.py                ← encodage + progression
│   │   ├── config.py             ← gestion profils (CRUD)
│   │   ├── profile_picker.py     ← sélection de profil (table)
│   │   ├── value_picker.py       ← modal sélection de valeur
│   │   ├── meta_popup.py         ← popup métadonnées IMDB / AlloCiné
│   │   ├── segments.py           ← plages de décalage détectées (lecture seule)
│   │   ├── confirm.py            ← ConfirmModal générique
│   │   ├── delete_confirm.py     ← confirmation suppression fichier
│   │   ├── recursive_confirm.py  ← confirmation run récursif
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
│   └── test_updates.py
└── requirements.txt
```

---

## 3. Lancement

### 3.1 Via `launch.bat` (Windows)

```bat
launch.bat
```

Choisit un interpréteur, dans cet ordre — le premier qui convient :

| Rang | Candidat | Retenu si |
|---|---|---|
| 1 | `.venv\Scripts\python.exe` | les six modules de `requirements.txt` s'importent |
| 2 | `python` du PATH | il annonce 3.11 ou mieux |
| 3 | `bootstrap.ps1` | les deux précédents ont échoué — il construit le rang 1 |

Le `.venv` passe devant le Python du système : c'est le seul dont les versions
de bibliothèques soient connues. Un Python système qui convient est *utilisé*,
jamais remplacé — mais si `pip` échoue dessus (poste verrouillé, dépôt interne,
permissions), le lanceur bascule sur `bootstrap.ps1` plutôt que de s'arrêter.

- Délègue à `main.py` en passant les arguments (`%*`)
- Utilise `%~dp0` pour garantir la portabilité du chemin
- Lit la version depuis `version.py` (aucune version en dur), avec
  l'interpréteur retenu — donc après son choix. Les `^"` encadrant l'appel
  `for /f` sont nécessaires : sans eux, une commande dont l'exécutable *et*
  l'argument sont entre guillemets se casse, et la version reste vide

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

Ordre de recherche : **PATH système**, puis dossier local `./bin/`.

L'absence d'un outil optionnel ne bloque jamais le lancement — elle désactive la
fonction correspondante avec un message explicite.

### 4.2 Auto-installation si absent

- Proposition à l'utilisateur (sans exiger un terminal interactif)
- Téléchargement depuis `config.toml` → `[ffmpeg] fetch_url`, ou `data/ffmpeg_releases.toml`
- Vérification SHA256 après téléchargement
- Extraction dans `./bin/`, aplatie par nom de fichier
- Build ffmpeg cible : **essentials** (~30 Mo)
- Sources : gyan.dev / BtbN (ffmpeg), GitHub quietvoid (dovi_tool),
  mkvtoolnix.download (mkvmerge), sourceforge (mpv)

**Cas particulier mpv** : publié uniquement en `.7z`. L'extraction passe par le
`tar`/libarchive livré avec Windows 10/11 plutôt que par une dépendance Python nouvelle.

### 4.3 Fetch des sources

Fetch à chaque lancement, mis en cache dans `data/ffmpeg_releases_cache.toml`. En cas
d'échec réseau, fallback silencieux sur `data/ffmpeg_releases.toml` embarqué, avec
message d'information.

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
release réussissait. Aucune empreinte n'est vérifiée sur ce chemin, et il n'y en a pas à
vérifier : l'URL vient d'une découverte dynamique, pas d'une source épinglée (§ 4.2).

**Le relevé des versions est parallèle** (`check_tools`). `_get_version` essaie deux
drapeaux à 5 s de délai chacun, et mkvmerge comme dovi_tool échouent sur le premier :
en série, un démarrage payait jusqu'à dix lancements de sous-processus l'un après
l'autre, deux fois s'il fallait installer ffmpeg. Même position que
`platform.sonder_encodeurs` pour les encodeurs (§ 11).

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

```toml
[app]
language = "fr"

[ffmpeg]
fetch_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
auto_install = true
bin_dir = "./bin"

[updates]
check_on_startup = true

[meta]
omdb_api_key = ""       # clé gratuite sur omdbapi.com — active note + synopsis IMDB

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

Les deux sorties portent le suffixe `_[dv]` — l'une comme l'autre rendent un
fichier Dolby Vision ; ce qui les sépare est le débit, que la raison affichée
explicite. Les sources sans DV sont encodées normalement par ce même profil.

**Trois niveaux, du plus légitime au plus dégradé.**

| | Source | Rôle |
|---|---|---|
| 1 | `profiles.toml` | le fichier de l'utilisateur — il fait foi |
| 2 | `data/profiles.default.toml` | les **profils livrés** : sèment le fichier au premier lancement, tiennent la session si le TOML de l'utilisateur devient illisible |
| 3 | `_default_` | plancher codé en dur, dernier recours si le fichier livré manque |

**Les profils livrés** (v0.8.8.4) sont dix, versionnés avec le code et donc
présents dans l'archive d'une release — `profiles.toml`, lui, est ignoré par
git : c'est le fichier de travail de chaque poste. Jusque-là le plancher semait
seul, et le sélecteur d'une installation neuve s'ouvrait sur une liste d'un
élément : rien qui montre ce qu'un profil règle, ni ce que change le fait d'en
changer.

Le premier du fichier livré est `serie_basic`, et il porte
`delete_source = false` : c'est lui que `get_active_profile` retient au premier
lancement, tant que rien n'a été choisi. Le seul profil livré à
`delete_source = true`, `video_basic_delete`, est **dernier** — il n'est jamais
actif par accident, et l'écran Config le signale « ⚠ oui ».

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
| `delete_source` | bool | supprimer la source après encodage réussi |
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
| TOML invalide | **ne réécrit rien** — le fichier de l'utilisateur est sa bibliothèque, il reste réparable à la main — et tient la session sur les profils livrés, chargés en mémoire seulement |
| TOML invalide **et** fichier livré absent | ne réécrit rien, tient la session sur `_default_` |
| fichier vide, ou sans table nommée | charge `_default_` |

**Comportement sur erreur de syntaxe :**

```
⚠ profiles.toml illisible (erreur syntaxe ligne 12).
  Session tenue sur les 10 profils livrés — votre fichier n'a pas été touché.
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
3. **Retrait du RPU** (`remove_dv`) : supprime le Dolby Vision sans réencoder, quand
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
| `remove_dv(hevc_in, hevc_out, dovi_path)` | `dovi_tool remove` : retire RPU et couche d'amélioration |
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

```
1. ffmpeg    : extrait le flux HEVC brut     (source     → *.iris_bl.hevc)
2. dovi_tool : remove                        (*.iris_bl  → *.iris_nodv.hevc)
3. ffmpeg    : pistes audio finales          (source     → *.iris_audio.mka)
4. mkvmerge  : remux                         (→ <nom>_[hdr10].mkv)
```

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

**Le conteneur est forcé en Matroska**, même si le profil demande du MP4 : le
remux passe par mkvmerge, et porter le RPU en MP4 demanderait de réécrire les
en-têtes. Un `container = "mp4"` rendrait sinon un fichier sans Dolby Vision,
soit exactement ce que l'opération cherche à éviter.

**Pipeline** — `tui/screens/run.py:_encode_dv`, quatre à six étapes :

```
1. ffmpeg -c:v copy -f hevc -  |  dovi_tool extract-rpu -   →  film.rpu
2. (profil 7) dovi_tool convert -m 2                        →  RPU en 8.1
3. ffmpeg -c:v <encodeur> -f hevc                           →  enc.hevc
4. dovi_tool inject-rpu -i enc.hevc --rpu-in film.rpu       →  dv.hevc
5. (si transcodage audio) build_audio_command               →  audio.mka
6. mkvmerge dv.hevc + pistes de la source                   →  sortie_[dv].mkv
```

L'étape 1 est un tuyau : `dovi_tool extract-rpu` accepte `-` en entrée, ce qui
évite une recopie du film entier pour en tirer quelques kilo-octets.
L'injection, elle, exige de vrais fichiers — elle relit son entrée une première
fois pour reconstituer l'ordre des images.

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
| **CAS 1** | bitrate source ≥ seuil cible | Réencodage HEVC (ou H264 si cible < 1080p) au bitrate cible |
| **CAS 2** | bitrate OK mais résolution trop grande | Redimensionnement HEVC, bitrate original |
| **CAS 3** | bitrate OK, résolution OK, **codec hors `CODECS_LISIBLES`** | Réencodage, bitrate conservé — H264 sous 1080p, HEVC au-dessus |
| **ENCODE_DV** | un des trois cas ci-dessus, profil en `dv`, et RPU réinjectable (§ 7.4) | Réencodage au débit cible, RPU sorti puis remis |
| **STRIP_DV** | aucun des cas ci-dessus, mais RPU retirable (DV 8.1 ou 7) et profil en `hdr10` | Retrait du RPU par remux, sans réencodage (§ 7.3) |
| **SKIP** | bitrate OK, résolution OK, codec H264 ou HEVC | Aucun traitement |

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
`<nom>_[hdr10].mkv`, toutes pistes conservées.

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
Pour chaque piste audio :
  1. Index 0                     → toujours conservée (langue originale)
  2. Langue dans audio_languages → conservée
  3. Sinon                       → exclue (sauf sélection manuelle TUI)
```

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
passait pour un DTS ordinaire et échappait à `preserve_hd_audio`.

### 8.6 Sous-titres et conteneur de sortie

- PGS / DVD (image) → conteneur MKV, `-c:s copy`
- SRT (texte) → MP4 possible, `-c:s mov_text`
- ASS / SSA → MKV : le style ne survit pas à `mov_text`
- Sélection par piste depuis `TracksScreen` (par défaut : toutes conservées)

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
quand la décision demande du MP4, le remux passe par
`dovi.build_strip_remux_mp4()`. Un flux HEVC brut n'a pas d'horodatage, d'où la
cadence donnée avant l'entrée ; et ses premières images portent des DTS
négatifs que le muxeur MP4 **jetait** — deux images perdues sur 2270, mesurées.
`-avoid_negative_ts make_zero` décale la base au lieu de rogner.

**Conteneur de sortie** — `output_container` suit les pistes réellement conservées :
écarter les sous-titres image libère le MP4 ; `mov_text` n'est jamais proposé en
Matroska. La présence d'au moins une piste externe force le `.mkv` (§ 9).

**Le flux `bin_data` d'un MP4 est sa piste de chapitres.** `ffprobe` rapporte,
sur une sortie MP4 issue d'une source chapitrée, un flux de plus que ceux
demandés : `bin_data`, `codec_tag_string=text`, `handler_name=SubtitleHandler`,
une trame par chapitre. Ce n'est pas une piste parasite — le MP4 ne sait porter
les chapitres que sous la forme d'une piste texte QuickTime, et c'est ainsi que
les lecteurs les retrouvent. Vérifié : `-map_chapters -1` le fait disparaître,
et les chapitres avec lui. Le Matroska, qui a un conteneur de chapitres propre,
n'affiche rien de tel.

### 8.7 Nommage des sorties

| Opération | Sortie |
|---|---|
| Réencodage HEVC | `nom_[hevc].mp4` / `.mkv` |
| Réencodage H264 | `nom_[H264].mp4` / `.mkv` |
| Réencodage AV1 | `nom_[av1].mp4` / `.mkv` |
| Remux mkvmerge | `nom_[mux].mkv` |
| Extrait de contrôle | `nom_[extrait].mkv` |

**Le suffixe d'encodage se remplace, il ne s'empile pas.** Réencoder un
`Film_[av1].mkv` en HEVC donne `Film_[hevc].mkv`, pas `Film_[av1]_[hevc].mkv`.
`scanner.stem_sans_suffixe_produit()` retire du nom le suffixe qu'il porte —
dérivé de `suffixes_produits()`, donc de `SUFFIX_BY_ACTION`, jamais recopié —
avant que le nouveau soit posé. `_[mux]`, `_[join]` et `_[extrait]` n'en font
pas partie : ils disent d'où vient le fichier, pas comment il a été encodé.

**Deux collisions, une numérotation.** Remplacer fait apparaître ce que
l'empilement masquait : la cible peut être la source elle-même
(`Film_[hevc].mkv` réencodé en HEVC — le geste courant, rebaisser un débit), ou
un fichier déjà présent (`Film_[av1].mkv` réencodé en HEVC quand un
`Film_[hevc].mkv` existe). Dans les deux cas, `decision.resoudre_sorties()`
numérote : `Film_[hevc](2).mkv`. Rien n'est écrasé, rien n'est refusé. Le
compteur repart avec le suffixe au passage suivant — `Film_[hevc](2)` réencodé
redonne une base `Film`, sans quoi l'empilement reviendrait par cette porte.

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

`FileDecision` porte `external_tracks: list[ExternalTrack]`, et `output_container`
retourne `.mkv` dès que cette liste n'est pas vide.

### 9.3 API du module

| Fonction | Rôle |
|---|---|
| `identify(path)` | Pistes du fichier via `mkvmerge -J` → `list[IdentifiedTrack]`. Mémorisé par (chemin, taille, date) : traduire vingt index ne relançait pas vingt processus |
| `ffmpeg_stream_index(path, tid, kind)` | Traduit un TID mkvmerge en index ffprobe |
| `guess_language(path)` | Déduit une langue du nom de fichier (`film.VF.mka`) |
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

Le fichier produit (`nom_[mux].mkv`) **devient le fichier de travail** : la décision est
réindexée dessus côté browser, et les sélections de pistes faites sur l'ancien fichier
ne s'appliquent plus.

---

## 9bis. Collage de parties — `core/joiner.py`

Un film livré en `part1` / `part2` n'est pas encodable tel quel : chaque partie prise
seule produirait sa propre sortie, et le profil déciderait deux fois au lieu d'une. Le
collage recoud les parties en un fichier unique, **avant** toute décision.

Numérotation `9bis` pour ne pas renuméroter les sections suivantes — même convention
que le `1bis` du `GUIDE.md`.

### 9bis.1 Décisions structurantes

| Choix | Raison |
|---|---|
| **mkvmerge en mode `append`** (`fichier1 + fichier2`) | Sans réencodage : il recale les horodatages de chaque partie sur la fin de la précédente. Le démultiplexeur `concat` de ffmpeg exige des paramètres de flux strictement identiques et gère mal les pistes multiples. |
| **Suffixe `_[join]`, absent de `SUFFIX_BY_ACTION`** | Le fichier collé est une *entrée* de travail, pas une sortie d'encodage : le scan doit continuer à le voir (§ 15.2). L'écarter comme `_[hevc]` rendrait le collage inutile. |
| **Contrôle avant lancement** | mkvmerge refuse d'apparier des pistes qui ne se correspondent pas. L'apprendre au bout d'une copie de 30 Go n'est pas une option. |
| **Ordre montré et corrigeable** | Deux parties inversées donnent un fichier de la **bonne durée**, donc faux sans que rien ne le signale. C'est la seule chose que le collage ne peut pas deviner sans risque. |
| **Les parties sont conservées** | Le collage n'efface rien. `Ctrl+D` reste le seul geste qui supprime. |

### 9bis.2 API du module

| Fonction | Rôle |
|---|---|
| `ordre_naturel(parts)` | Tri où les nombres comptent comme des nombres : `part1 < part2 < part10`. Clé faite de tuples homogènes, jamais un `int` face à une `str`. |
| `nom_commun(parts)` | Nom du tout, déduit du préfixe commun, marqueur de numérotation retiré (`part`, `CD`, `pt`, `disque`, `vol`, `tome`…). `Film part1` + `Film part2` → `Film`. |
| `join_output_path(parts)` | `<nom commun>_[join].mkv`, dans le dossier des parties. |
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
mkvmerge --gui-mode -o "D:/films/Film_[join].mkv"
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

`read_cues()` lit les timings SRT/ASS ; `_speech_mask()` construit le masque de parole.

Un sous-titre embarqué dans un conteneur n'a pas de timings lisibles tel quel :
`extract_subtitle(video, ffmpeg_index)` le sort d'abord vers un `.srt` temporaire
(`ffmpeg -map 0:s:N -c:s srt`). L'appelant fournit l'index via
`muxer.ffmpeg_stream_index()`. Un sous-titre image (PGS, VobSub) fait échouer la
conversion : il est refusé pour ce motif, et non pour un format « mal lu ».

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

### 12.1 Modes d'encodage vidéo

| Mode | Condition | Encodeur | Notes |
|---|---|---|---|
| **Retrait DV** | `action == STRIP_DV` | aucun — dovi_tool + mkvmerge | `build_command` retourne `[]`, ffmpeg n'est pas appelé (§ 7.3) |
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
légitime, y compris une piste de commentaires écourtée. Facteurs éliminés par mesure — le codec de sortie (l'AC3 meurt comme
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
fait échouer toute harmonisation.

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
- Sortie partielle supprimée en cas d'échec

---

## 13. Métadonnées — `core/meta.py`

### 13.1 Extraction du titre

`parse_title(path)` tronque le nom au premier marqueur de format (résolution, année,
source, épisode…) et retourne `(titre, année)`.

```python
parse_title(Path("The.Batman.2022.2160p.BluRay.mkv"))
# → ("The Batman", 2022)
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
  dès qu'il y a des heures. Ils s'appliquent **à la lecture** autant qu'au
  redimensionnement : une largeur trop courte a pu être persistée avant que le
  plancher existe, et corriger le seul défaut ne répare pas ces
  configurations. Les écrans reprennent cette table dans leur `RESIZE_MIN`
  plutôt que d'en tenir une seconde. Toute cellule numérique porte en outre
  `overflow="ellipsis"` : une coupe résiduelle se voit (`3:17:…`) au lieu de
  produire une valeur plausible et fausse (`3:17:2`).
- **Un afficheur qui montre un nom se construit en `markup=False`.** `Static`
  interprète par défaut ce qui ressemble à une balise entre crochets, et la
  convention de nommage du projet — `_[mux]`, `_[hevc]`, `_[av1]`, `_[hdr10]`,
  `_[extrait]`, `_[premux]` — est faite de cette syntaxe. Un nom affiché sans
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
aussi banale que `↵` : la barre de profil (`[W] Assistant` / `[W] Manuel`), le
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
| 4 — Lancer | Muxer ou encoder — **les deux toujours offerts** | `M` `E` `↵` |
| 5 — Terminé | Le résultat, puis retour à l'accueil | `↵` |

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
rien n'est à réencoder mais qu'il y a à greffer, encodage sinon — et `M` / `E`
forcent l'autre. Un mux sans piste externe est refusé avec sa raison, pas
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
│ D:\Videos    2/4 sélectionné(s)  ·  Col : Résol. [</>] │
│                                                         │
│ [F4] 🎬 SERIE_BASIC 🎬  • 1080p 2200k  ·  4K→1080p     │
│      HD audio non                                       │
│ ⏳ Analyse en cours… 2 / 4                              │
├─ ──┬─ Fichier ──────┬─ Taille ─┬─ Résol. ──┬─ Durée ─┬─ Débit ─┬─ Codec ─┬─ Dolby V. ─┬─ Décision ─┬─ Estim. (Δ%) ─┬─ ETA ─┬─ Audio ─────┤
│    │ 📁 Films/      │          │           │         │         │         │            │            │               │                │             │
│[x] │ 🎬 film1.mkv   │   8,4 Go │ 3840x2160 │ 2:05:12 │ 25000k  │  hevc   │  DV:P8.1   │  → HEVC    │ 2,1 Go (−75%) │     0:38:12    │ TrueHD 7.1  │
│[ ] │ 🎬 film2.mp4   │   1,1 Go │  720x480  │ 1:32:00 │   900k  │  h264   │  —         │  ← SKIP    │       —       │        —       │ AAC 2.0     │
│[x] │ 🎬 film3.avi   │   2,3 Go │ 1280x720  │ 0:52:00 │  3200k  │  vp9    │  —         │  → H264    │ 1,2 Go (−48%) │     0:04:51    │ AC3 5.1     │
├────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Space Sélect  a Tout  n Aucun  Enter Ouvrir  v Visualiser  Ctrl+D Supprimer  Back Remonter  Home Début  End Fin  PgUp/PgDn                        │
│ F1 Dry-run  F2 Run  F3 Récursif  F4 Profil  F5 Gérer  F6 Coller  F7 AlloCiné  F8 IMDB  Sh+Tab/Tab Col  < Rétrécir  > Élargir  F10 Quitter         │
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
| `F1` | sélection | Dry-run |
| `F2` | sélection | Run |
| `F3` | dossier | Run récursif |
| `F4` | — | Choisir le profil actif |
| `F5` | — | Gérer les profils |
| `F6` | sélection | **Coller les parties cochées** en un fichier unique (§ 9bis) |
| `F7` / `F8` | fichier | AlloCiné / IMDB |
| `F10` | — | Quitter |

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

**La colonne Estim. porte un dégradé continu**, du vert franc (gain de −50 % et
au-delà) au jaune (autour de zéro) puis à l'orange des alertes (perte de +25 %
et au-delà), interpolé en RGB entre ces trois teintes. L'échelle est bornée :
l'œil ne distingue pas −60 % de −80 %, et sans borne le gros du corpus — entre
−20 % et −50 % — deviendrait indiscernable. Une sortie plus grosse que sa source
garde le gras des alertes, que le seul virage de teinte ne rendrait pas.

C'est une **exception assumée** à la table d'emphases : le vert y dit « traité
sans réencodage », et il dit ici « la sortie est plus petite ». Sur une même
ligne, le vert de la colonne Décision et celui d'Estim ne parlent donc pas de la
même chose. L'exception vit dans une seule fonction, `_teinte_estimation()` ;
aucune autre couleur n'est écrite en dur dans cet écran.

Une ligne dont la vidéo est **recopiée** — remux, retrait de RPU, Dolby Vision
conservé — reste hors du dégradé : sa sortie pèsera la taille de la source,
l'écart vaut zéro, et la poser sur l'échelle la placerait en plein jaune, la
teinte la plus voyante, pour un cas où rien n'est recalculé. Le prédicat
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
dossier, avertissement), focus initial sur *Annuler*.

À la confirmation, le fichier est **définitivement supprimé** (pas de corbeille) et sa
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

#### Run récursif (F3)

Disponible uniquement sur un **dossier**. `RecursiveConfirmModal` affiche le répertoire
et le profil actif, puis lance un scan récursif illimité et un dry-run sur les fichiers à
encoder (SKIP exclus). Décisions automatiques, aucune sélection de pistes.

### 14.2 Écran Tracks — pistes et décision vidéo

Un `DataTable` à quatre sections : **VIDÉO**, **AUDIO**, **SOUS-TITRES**, **EXTERNES**.

```
┌─ Pistes — film1.mkv    Profil: [cinema_4k_hd] · Audio: 2/3 · Sous-titres: 1/1 ──┐
│ ── VIDÉO ──────────────────────────────────────────────────────────────────────  │
│ ✎ HEVC  0:v:0  hevc  3840x2160  DV:P8.1   ◄→ HEVC► · ◄12000 kbps► · ◄HDR10►     │
│ ── AUDIO ──────────────────────────────────────────────────────────────────────  │
│ [x]  0:a:0 ⚑   truehd  7.1  fre  défaut          → copy                          │
│ [x]  0:a:1     ac3     5.1  fre  sélectionné     → copy                          │
│ [ ]  0:a:2     dts     5.1  deu  exclu           —                               │
│ ── SOUS-TITRES ────────────────────────────────────────────────────────────────  │
│ [x]  0:s:0   hdmv_pgs  image  fre  défaut        → MKV copy                      │
│ ── EXTERNES ───────────────────────────────────────────────────────────────────  │
│ [x]  film.VF.mka  ac3  5.1  fre  « VF »          −2450 ms (mesuré)               │
│ [ ✓ ] Valider la sélection                                                        │
├──────────────────────────────────────────────────────────────────────────────────┤
│ Space Sélect  Enter Valider  F1 Dry-run  F2 Run  F4 Profil  F6 Codec  F7 Débit   │
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
piste : `→ copy` / `→ aac 192k` / `—`. Sous-titres : `image` → `MKV copy`,
`texte` → `MP4 copy`. Toutes sélectionnées par défaut.

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
| `A` | Applique le candidat mesuré |
| `R` | **Point de repère** — mesure guidée par une réplique, quand la mesure libre ne conclut pas |
| `S` | **Plages détectées** (§ 10.4) — lecture seule |
| `P` | **Applique les plages** à la piste sous le curseur — `.srt` réécrit (§ 10.5) ou piste audio rallongée et réencodée (§ 10.6). Le fichier produit devient la source, avec un décalage nul |
| `V` | **Visualiser dans mpv**, piste greffée et décalage appliqué |
| `K` | **Extrait de contrôle** réellement muxé |
| `C` | Copie le décalage d'une autre piste externe → `sync_origin = COPIED` |
| `D` | Retire la piste |
| `F1` | Dry-run |
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
│ Collage — 3 parties ── Film_[join].mkv                  │
├─ # ─┬─ Fichier ──────────┬─ Durée ─┬─ Pistes ─┬─ Collage ──────┤
│  1  │ Film part1.mkv     │ 1:04:12 │ V+2A+1S  │ référence      │
│  2  │ Film part2.mkv     │ 0:58:47 │ V+2A+1S  │ ✓              │
│  3  │ Film part10.mkv    │ 0:41:03 │ V+2A+0S  │ ✓ avec réserve │
├─────────────────────────────────────────────────────────────────┤
│ Durée attendue du tout : 2:44:02                                │
│ Sortie : Film_[join].mkv                                        │
│ Collage  ███████████████████████░░░░░░░░░░░░  62%               │
└─────────────────────────────────────────────────────────────────┘
```

#### Touches

| Touche | Action |
|---|---|
| `Ctrl+↑` / `Ctrl+↓` | Déplace la partie sous le curseur d'un rang |
| `F2` | Lance le collage |
| `⌫` / `Esc` | Retour. Un collage en cours est interrompu, son fichier partiel effacé |
| `Ctrl+Début` | Accueil |

L'ordre proposé vient de `ordre_naturel()` ; le tableau est ce qui sera collé. La colonne
**Collage** dit, partie par partie, si elle s'apparie sur la référence — le détail du
refus ou de la réserve s'affiche sous le tableau.

**La colonne du nom reprend la largeur réglée sur l'accueil** (`get_column_widths()`,
clé `fichier`), planchers compris : l'écran montre les mêmes fichiers, une largeur
propre y tronquerait des noms qui se lisent entiers dans le navigateur. Les autres
colonnes portent des libellés bornés et gardent une largeur fixe.

`F2` est refusé sur un blocage (§ 9bis.3) ou si le fichier de sortie existe déjà : le
collage n'écrase jamais rien.

### 14.6 Écran Dry-run

Prévisualise les décisions de tous les fichiers sélectionnés, sans écriture disque.

**Colonnes :** Fichier · Taille · Durée · Estim. (Δ%) · Action · Conteneur · DV ·
Débit cible · Résolution · Audio

**Barre de bilan :**

```
À encoder : HEVC 3  ·  H264 1  ·  SKIP 2
·  Source : 12,4 Go  →  Estimé : 3,2 Go (−74%)
```

`Espace` désélectionne un fichier, `F6`/`F7` éditent codec et débit avant lancement,
`F2` ou `↵` passe à l'écran Run (SKIP exclus).

### 14.7 Écran Run — encodage

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
- Suppression source après succès selon `delete_source` (ou override par fichier)
- En cas d'erreur : fichier marqué ✗, les suivants continuent, source conservée

### 14.8 Écran Config — gestion des profils

Tous les profils sont éditables et supprimables (`D` / `Suppr`, avec
confirmation) — ils viennent tous de `profiles.toml`, qui fait foi. Seule
exception : le dernier de la liste, dont la suppression est refusée par un
message explicite. Un nouveau profil part des réglages du profil actif. Le
champ **Nom** n'est saisissable qu'à la création : renommer se fait dans
`profiles.toml`.

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
et TracksScreen (F4).

### 14.11 Retour à l'accueil — `Ctrl+Home`

Traiter plusieurs fichiers d'affilée revenait à remonter les écrans un par un.
`Ctrl+Home` dépile jusqu'au browser, depuis les sept écrans non modaux :
dry-run, run, mux, assistant, config, pistes et recalage.

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
| `QuitConfirmScreen` | `F10` / `Ctrl+C` | Annuler |
| `DeleteConfirmModal` | `Ctrl+D` (browser) | Annuler |
| `RecursiveConfirmModal` | `F3` (browser, dossier) | Confirmer |
| Suppression de profil | `D` (config) | Annuler |

Toutes dérivent de `ConfirmModal`. Le focus initial part sur *Annuler* dès que
l'opération est destructive.

---

## 15. Scanner — `core/scanner.py`

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

`scan_directory_recursive(root)` — tous les fichiers vidéo sous `root`, tous niveaux,
triés par chemin. Mêmes filtres que `scan_directory` : extensions supportées, exclusion
de ce que l'application a elle-même encodé.

**Cette exclusion est dérivée, jamais recopiée.** `scanner.suffixes_produits()` la
construit depuis `SUFFIX_BY_ACTION` — donc `_[hevc]`, `_[H264]`, `_[av1]` et `_[hdr10]`,
et tout suffixe qu'une action vidéo apprendrait à écrire. La paire en dur qui la
précédait ne connaissait que les deux premiers, à quatre endroits distincts : une sortie
AV1 reparaissait au scan, `av1` n'est pas dans `CODECS_LISIBLES`, et la décision tombait
en CAS 3 pour proposer de la réencoder en HEVC — sur `basic_delete`, qui a
`delete_source = true`, en effaçant l'original au passage.

`MUX_SUFFIX` en est **volontairement absent** : un `_[mux]` n'est pas un encodage mais
une greffe de pistes, et l'encoder ensuite est un geste légitime que l'écarter du scan
rendrait impossible — le fichier ne serait même pas visible.

`JOIN_SUFFIX` (`_[join]`) en est absent pour la même raison, en plus forte : un fichier
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

`tests/test_deps.py` vérifie que les listes de `main.py`, `launch.bat` et
`bootstrap.ps1` couvrent `requirements.txt` — et que les quatre appels répartis
sur les deux scripts disent tous la même chose.

### 17.3 Binaires externes et licences

| Élément | Nature | Licence | Remarque |
|---|---|---|---|
| ffmpeg | essentiel | GPL (build libx265) | Build *essentials*, ~30 Mo |
| dovi_tool | optionnel | MIT | Binaire Windows unique |
| mkvmerge | optionnel | **GPL-2.0** | ZIP officiel statique, sans DLL, 22 Mo |
| mpv | optionnel | GPL-2.0+ | Publié en `.7z`, extrait via le tar de Windows |

**Licence.** Redistribuer mkvmerge et mpv dans les ZIP de release entraîne les
obligations GPL correspondantes. Ce n'est pas une situation nouvelle — le ffmpeg embarqué
avec libx265 est déjà GPL — mais autant le décider sciemment.

---

## 18. Tests

| Fichier | Portée |
|---|---|
| `tests/smoke_tui.py` | Parcours TUI headless de bout en bout (14 scénarios) — **à lancer après toute modification d'écran** |
| `tests/shots_tui.py` | Inventaire visuel : exporte chaque écran en SVG (rendu réel, pas maquette) |
| `tests/test_deps.py` | Cohérence des listes de dépendances |
| `tests/test_dovi.py` | Wrapper dovi_tool |
| `tests/test_muxer.py` | Génération des commandes mkvmerge, parsing `--gui-mode` |
| `tests/test_preview.py` | Construction des commandes mpv |
| `tests/test_sync.py` | Mesure de décalage sur paires connues |
| `tests/test_updates.py` | Vérification de fraîcheur des outils |

```bash
python tests/smoke_tui.py     # headless, encode réellement de petits clips
python tests/shots_tui.py     # inventaire visuel -> _shots/*.svg
python -m pytest tests/
```

---

## 19. Hors scope

- Logs applicatifs persistants (architecture en place, backend non branché)
- Python embarqué
- Interface de mise à jour des sources ffmpeg
- File de traitement multi-dossiers (hors mode récursif)
- Gestion des commentary tracks par heuristique (titre de piste)
- Widget multi-langue par badges pour `audio_languages` (champ texte libre)
- Timeout ou concurrence sur le mode récursif
- Pistes externes en traitement par lot (un fichier à la fois)
- IPC mpv sur named pipe (ajustement en OSD, valeur retapée dans la TUI)
- Collage de parties aux codecs ou définitions différents : refusé et nommé, jamais
  rattrapé par un réencodage (§ 9bis.3)
- Dolby Vision au remux mkvmerge — non vérifié (§ 9.5 piège 8)
- Suppression de fichier vers la corbeille (`Ctrl+D` supprime définitivement)

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
