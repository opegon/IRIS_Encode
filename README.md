# IRIS ENCODE — Guide d'installation

**Version** : 0.8.5.0 — Windows (support macOS/Linux prévu)

> Ce document présente le projet puis couvre l'**installation**. Pour l'utilisation
> au quotidien — procédures par écran et cas rencontrés — voir `GUIDE.md`.

---

## Pourquoi cet outil

Une bibliothèque de films doit aujourd'hui atteindre plusieurs écrans, et chacun
n'accepte qu'un sous-ensemble différent des formats qu'un fichier peut contenir.
La réponse évidente — tout réencoder vers le plus petit dénominateur commun —
coûte des heures de calcul par film et dégrade une image qui, le plus souvent,
n'avait aucun besoin d'être retouchée. IRIS ENCODE part de l'hypothèse inverse :
**décider ce qu'il faut toucher, et ne toucher que cela.**

### La chaîne de diffusion et ses contraintes

| Maillon | Ce qu'il impose |
|---|---|
| **Serveur Jellyfin** | Tout format non reconnu par le client déclenche un transcodage à chaque lecture. Le vrai coût d'un mauvais format se paie à l'usage, pas une fois. |
| **Téléviseur LG OLED (webOS)** | Aucun format audio sans perte — ni TrueHD, ni DTS-HD MA. Le conteneur MKV est capricieux, le Dolby Vision profil 8 déclenche un remux HLS avec coupures audio, le DTS gèle au saut sur les modèles 2023. |
| **Barre de son en eARC** | Elle décode tout, mais dès que le téléviseur mixe ses propres haut-parleurs avec elle, c'est lui qui décode : aucun train binaire sans perte ne l'atteint. |
| **Clients iOS (Swiftfin)** | Permissifs via VLCKit, qui lit le MKV et le DTS. Le lecteur natif d'Apple est plus strict et ne sait pas changer de piste audio — donc inutilisable sur un fichier multilingue. |
| **Sous-titres image (PGS, VobSub)** | Aucun client ne peut les recevoir tels quels : le serveur les incruste, ce qui force un transcodage vidéo complet. |

L'intersection de ces contraintes est étroite : **HEVC en HDR10, audio E-AC3,
sous-titres texte**. C'est le seul jeu de formats que toute la chaîne accepte
sans qu'aucune machine n'ait à retoucher quoi que ce soit.

### Les choix qui en découlent

- **Ne pas réencoder par défaut.** Un fichier dont le débit vidéo, la résolution
  et le codec sont déjà dans les clous est laissé intact. Le débit comparé au
  seuil est celui de la vidéo seule — celui du conteneur, audio compris,
  enverrait au réencodage des fichiers dont l'image tient largement en dessous.
- **Retirer le Dolby Vision plutôt que de le convertir.** Sur un profil 8.1, la
  couche de base *est* du HDR10 : retirer les métadonnées suffit. Quelques
  minutes, une image identique au bit près, contre des heures de réencodage pour
  un résultat dégradé.
- **Transcoder l'audio au débit de la source**, plutôt qu'à un forfait qui jette
  bien plus que nécessaire sur une piste HD.
- **Laisser le conteneur suivre le contenu.** MP4 quand tout y tient, MKV quand
  quelque chose serait perdu.
- **Un profil par destination.** Les seuils, les langues conservées et le
  traitement du Dolby Vision se règlent par profil, parce qu'un salon et un
  téléphone ne demandent pas le même fichier.

Le reste de l'outil découle de là : une interface qui **montre sa décision avant
de l'appliquer**, fichier par fichier, et qui permet de la contredire.

---

## Prérequis

| Composant | Version minimale | Obligatoire |
|-----------|-----------------|-------------|
| Windows   | 10 / 11         | ✓           |
| Python    | 3.11            | ✓ (auto-installable) |
| ffmpeg    | 7.x             | ✓ (auto-installable) |
| ffprobe   | 7.x             | ✓ (inclus avec ffmpeg) |
| dovi_tool | 2.x             | ✗ (optionnel — Dolby Vision) |
| mkvmerge  | 99.x            | ✗ (optionnel — greffe de pistes externes) |
| mpv       | récent          | ✗ (optionnel — visualisation) |
| GPU NVIDIA | driver récent  | ✗ (recommandé — encodage accéléré CUDA) |

---

## 1. Installer Python et ses dépendances

### 1.1 Ne rien faire (recommandé)

Double-cliquez **`launch.bat`**. S'il ne trouve pas de Python 3.11+ utilisable,
il installe le sien et vous n'avez rien d'autre à faire :

```
 [INFO] Aucun Python 3.11+ utilisable — installation de l'environnement.
 Aucun droit administrateur n'est requis ; tout est écrit dans ce dossier.

  Téléchargement de uv (x86_64-pc-windows-msvc)…
  uv installé : bin\uv.exe
  Python 3.12…
  Environnement .venv…
  Dépendances (requirements.txt)…

  Prêt — Python 3.12.14 dans .venv
```

Comptez deux à trois minutes et environ 140 Mo la première fois. Les fois
suivantes, `launch.bat` constate que tout est en place et démarre aussitôt.

**Aucun droit administrateur n'est requis, et rien n'est écrit hors du dossier
de l'application** — ni dans le PATH, ni dans le registre, ni dans les dossiers
système. Copier le dossier sur une clé, c'est copier l'installation entière :

| Ce qui arrive | Où |
|---|---|
| `uv`, l'exécutable qui va chercher le reste | `bin\uv.exe` |
| L'interpréteur CPython | `bin\python\` |
| L'environnement et ses bibliothèques | `.venv\` |

C'est la convention que suit déjà le reste de l'outillage : ffmpeg, mkvmerge et
dovi_tool arrivent dans `bin/` de la même façon (chapitre 3). Python faisait
exception pour une raison mécanique — le code qui télécharge les outils *est*
du Python, et ne pouvait pas s'exécuter avant lui. C'est ce que `bootstrap.ps1`
corrige, en PowerShell.

### 1.2 Quel interpréteur `launch.bat` retient

Dans cet ordre, le premier qui convient :

1. **`.venv\` local**, s'il est complet — le seul dont les versions de
   bibliothèques soient connues ;
2. **le Python du PATH**, s'il annonce 3.11 ou mieux — évite le téléchargement ;
3. **`bootstrap.ps1`** — installe uv, un CPython et le `.venv`.

Un Python système qui convient est *utilisé*, jamais remplacé. À l'inverse, si
`pip` échoue sur ce Python-là (poste verrouillé, dépôt interne, permissions),
`launch.bat` bascule tout seul sur l'environnement isolé plutôt que de s'arrêter.

### 1.3 Reconstruire l'environnement

Si quelque chose s'est mal passé, ou après une mise à jour de
`requirements.txt` :

```
powershell -ExecutionPolicy Bypass -File bootstrap.ps1 -Force
```

`-Force` reconstruit `.venv` de zéro. Sans lui, le script constate et ne
retélécharge rien : il est fait pour être relancé sans conséquence.

### 1.4 Si Windows bloque un fichier (erreur 4551)

Sur une installation *propre* de Windows 11, **Smart App Control** est actif par
défaut. Il refuse d'exécuter les binaires dont la réputation n'est pas établie,
et le signale par `os error 4551`. `bootstrap.ps1` reconnaît ce blocage et le
nomme.

Depuis la v0.8.4.2 il ne devrait plus le rencontrer : le `.venv` est construit
par le module `venv` de l'interpréteur, dont le lanceur est un fichier connu.
S'il survient malgré tout, deux issues :

- **installer Python 3.12 depuis python.org** (chapitre 2) : ces binaires sont
  signés par la Python Software Foundation, et `launch.bat` les retiendra ;
- **désactiver Smart App Control** — *Sécurité Windows* → *Contrôle des
  applications et du navigateur*. À savoir avant de le faire : la désactivation
  est **définitive**, seule une réinstallation de Windows le réactive.

---

## 2. Installer Python à la main (facultatif)

Rien n'oblige à passer par le chapitre 1. Un Python installé classiquement est
reconnu et utilisé tel quel.

Rendez-vous sur **https://www.python.org/downloads/** et téléchargez la dernière
version **3.11 ou supérieure**. Cochez impérativement, avant *Install Now* :

```
☑  Add Python X.XX to PATH
```

Sans cette case, `launch.bat` ne le verra pas — et installera le sien.

Puis, dans le dossier de l'application :

```
pip install -r requirements.txt
```

| Bibliothèque    | Rôle |
|-----------------|------|
| `textual`       | Interface TUI (Terminal User Interface) |
| `rich`          | Rendu console enrichi (couleurs, tableaux) |
| `tomli-w`       | Écriture de fichiers TOML (config, profils) |
| `requests`      | Téléchargement automatique de ffmpeg |
| `beautifulsoup4`| Scraping IMDB (F8) et AlloCiné (F7) pour les métadonnées |
| `numpy`         | Corrélation audio pour le recalage des pistes greffées |

Si `pip` est introuvable : `python -m pip install -r requirements.txt`. Sur un
poste à permissions restreintes : `pip install --user -r requirements.txt` —
ou, plus simplement, laissez le chapitre 1 faire le travail.

---

## 3. Installer ffmpeg

ffmpeg est le moteur d'encodage vidéo. IRIS ENCODE le détecte et propose de le télécharger automatiquement s'il est absent.

### Option A — Installation automatique (recommandée)

Lancez IRIS ENCODE (`launch.bat`). Si ffmpeg est absent, le programme propose :

```
[✗] ffmpeg   introuvable
    Télécharger et installer dans ./bin/ ? (o/N)
```

Répondez `o`. Le téléchargement (~30 Mo) s'effectue depuis **gyan.dev** (source officielle Windows) et ffmpeg est extrait dans le dossier `bin/` à côté de `launch.bat`.

### Option B — Installation manuelle dans `bin/`

1. Téléchargez **ffmpeg-release-essentials.zip** depuis : https://www.gyan.dev/ffmpeg/builds/
2. Extrayez les fichiers `ffmpeg.exe` et `ffprobe.exe` depuis le sous-dossier `bin/` de l'archive
3. Placez-les dans le dossier `bin/` d'IRIS ENCODE :
   ```
   iris_encode/
   └── bin/
       ├── ffmpeg.exe
       └── ffprobe.exe
   ```

### Option C — ffmpeg déjà installé dans le PATH

Si ffmpeg est déjà installé sur le système (accessible via `ffmpeg` dans un terminal), IRIS ENCODE le détecte automatiquement — aucune action requise.

---

## 4. (Optionnel) Installer les outils complémentaires

Trois outils sont optionnels. Aucun n'est nécessaire pour encoder : leur absence
désactive une fonction, elle ne bloque jamais le lancement.

| Outil | Nécessaire pour | Taille |
|---|---|---|
| `dovi_tool` | contenus **Dolby Vision** (probe RPU, métadonnées HDR10) | ~2 Mo |
| `mkvmerge` | **greffe de pistes externes** (VF, sous-titres) et extraits de contrôle | ~22 Mo |
| `mpv` | **visualisation** d'un fichier ou d'un recalage | ~50 Mo |

### Option A — Installation automatique (recommandée)

Au premier lancement, IRIS ENCODE propose d'installer chaque outil manquant :

```
  dovi_tool absent (optionnel — nécessaire pour le Dolby Vision).
  Télécharger et installer dovi_tool (Dolby Vision) dans ./bin/ ? (o/N) :
```

Répondez `o`. Le binaire est téléchargé depuis la source officielle, vérifié par son
empreinte SHA256, puis extrait dans `bin/`.

> `mpv` n'est publié qu'en archive `.7z` : l'extraction passe par le `tar` livré avec
> Windows 10/11, sans dépendance supplémentaire.

### Option B — Installation manuelle dans `bin/`

Téléchargez les binaires Windows et placez les exécutables directement dans `bin/`
(sans sous-dossier) :

| Outil | Source |
|---|---|
| `dovi_tool.exe` | https://github.com/quietvoid/dovi_tool/releases |
| `mkvmerge.exe` | https://mkvtoolnix.download/downloads.html (archive ZIP 64-bit) |
| `mpv.exe` | https://mpv.io/installation/ (build Windows portable) |

```
iris_encode/
└── bin/
    ├── dovi_tool.exe
    ├── mkvmerge.exe
    └── mpv.exe
```

> Un outil déjà présent dans le PATH système est détecté automatiquement — rien à faire.

---

## 5. Lancer IRIS ENCODE

Double-cliquez sur **`launch.bat`** ou exécutez dans un terminal :

```
launch.bat
```

Le lanceur vérifie, et installe ce qui manque :
- un Python 3.11+ utilisable — sinon il en installe un (chapitre 1) ;
- les dépendances Python listées dans `requirements.txt` ;
- ffmpeg / ffprobe, téléchargés dans `bin/` au premier besoin ;
- la validité de la configuration.

---

## 6. Structure des fichiers

```
iris_encode/
├── launch.bat          ← Point d'entrée Windows (double-clic)
├── bootstrap.ps1       ← Installe Python et ses dépendances, sans droits admin
├── main.py             ← Point d'entrée Python
├── config.toml         ← Configuration générale (éditable)
├── profiles.toml       ← Profils d'encodage (éditable)
├── requirements.txt    ← Dépendances Python
├── version.py          ← Version de l'application (source unique)
├── .venv/              ← Environnement Python local (auto)
├── bin/                ← uv / python / ffmpeg / ffprobe / dovi_tool / mkvmerge / mpv (auto)
├── data/               ← Sources de téléchargement (embarquées)
├── core/               ← Logique métier
├── tui/                ← Interface utilisateur
├── tests/              ← Tests et smoke test TUI
└── logger/             ← Module de journalisation
```

---

## 7. Personnalisation

Les fichiers `config.toml` et `profiles.toml` sont éditables à la main avec n'importe quel éditeur de texte (Notepad, VS Code, etc.).

**`config.toml`** — largeurs des colonnes, langue, chemins, clé OMDb :
```toml
[tui.browser.columns]
# La colonne "fichier" s'étend automatiquement à l'espace disponible
taille       = 8      # largeur de la colonne taille fichier
resolution   = 12     # largeur de la colonne résolution
audio        = 20     # largeur de la colonne pistes audio
decision     = 12     # largeur de la colonne décision

[meta]
omdb_api_key = ""     # clé gratuite sur omdbapi.com (données IMDB complètes)
```

**`profiles.toml`** — profils d'encodage (bitrate, résolution, audio, Dolby Vision) :
```toml
[serie_basic]
bitrate_1080p_kbps = 2500
keep_4k            = false
dolby_vision       = "hdr"
```

---

## 8. Raccourcis clavier (écran Browser)

| Touche | Action |
|--------|--------|
| `Space` | Sélectionner / désélectionner un fichier |
| `A` / `N` | Tout sélectionner / Aucun |
| `Enter` | Entrer dans un dossier |
| `Backspace` | Remonter d'un niveau |
| `T` | Sélection manuelle des pistes (audio, sous-titres) |
| `F1` | Dry-run (prévisualisation) |
| `F2` | Lancer l'encodage |
| `F3` | Run récursif (dossier sélectionné + tous ses sous-dossiers) |
| `F4` | Changer de profil d'encodage |
| `F5` | Gérer les profils (créer `N`, éditer `E`, supprimer `D`) |
| `F7` | Recherche AlloCiné (métadonnées film/série) |
| `F8` | Recherche IMDB (métadonnées film/série) |
| `Tab` / `Shift+Tab` | Colonne suivante / précédente (redimensionnement) |
| `<` / `>` | Rétrécir / élargir la colonne active |
| `F10` | Quitter |

---

## 9. Métadonnées IMDB (F8)

IMDB bloque le scraping direct. IRIS ENCODE utilise deux modes :

- **Sans clé** : données partielles via l'API de suggestions IMDB (titre, année, type, stars de base)
- **Avec clé OMDb** : données complètes (note, réalisateur, synopsis, genres)

Pour obtenir une clé gratuite (1 000 req/jour) :
1. S'inscrire sur [omdbapi.com](https://www.omdbapi.com/apikey.aspx)
2. Ajouter dans `config.toml` :
   ```toml
   [meta]
   omdb_api_key = "votre_clé"
   ```

---

## 10. Terminal recommandé

IRIS ENCODE utilise Textual pour son interface graphique TUI. Le rendu dépend du **terminal hôte**, pas du shell (cmd ou PowerShell).

| Terminal | Rendu | Notes |
|----------|-------|-------|
| **Windows Terminal** | ✓ Optimal | Recommandé — VT100/ANSI complet, Unicode natif |
| **PowerShell** dans Windows Terminal | ✓ Optimal | Le shell n'a pas d'importance, c'est l'hôte qui compte |
| **cmd.exe** dans Windows Terminal | ✓ Optimal | Idem |
| **cmd.exe** fenêtre classique (conhost) | ⚠ Dégradé | Support ANSI partiel, bordures approximatives |
| **PowerShell** fenêtre classique (conhost) | ⚠ Variable | Même limitation que cmd classique |

> **Windows Terminal** est disponible gratuitement sur le Microsoft Store
> et est installé par défaut sur Windows 11.
> Pour Windows 10 : https://aka.ms/terminal

---

## 11. Résolution des problèmes courants

| Symptôme | Cause probable | Solution |
|----------|---------------|----------|
| `python` non reconnu | Python absent du PATH | Réinstaller Python en cochant *Add to PATH* |
| `pip` non reconnu | pip absent | Utiliser `python -m pip` |
| Écran noir au lancement | Terminal ne supporte pas l'interface TUI | Utiliser Windows Terminal ou cmd.exe classique |
| Encodage lent | Pas de GPU NVIDIA détecté | Normal — encodage CPU activé automatiquement |
| `dovi_tool introuvable` | Optionnel non installé | Voir section 4 — uniquement si fichiers Dolby Vision |
| Erreur à l'import d'un module | Dépendances manquantes | Relancer `pip install -r requirements.txt` |
| `os error 4551` à l'installation | Smart App Control refuse un binaire sans réputation | Voir chapitre 1.4 |
| IMDB : note/synopsis absents | Clé OMDb non configurée | Voir section 9 |

---

## 12. Désinstallation

IRIS ENCODE ne modifie aucun paramètre système. Pour désinstaller :

1. Supprimez le dossier `iris_encode/`
2. (Optionnel) Désinstallez les bibliothèques Python : `pip uninstall textual rich tomli-w requests beautifulsoup4`

Les fichiers `config.toml` et `profiles.toml` sont supprimés avec le dossier.

---

*IRIS ENCODE — Interface Relationnelle d'Intelligence Servicielle*
