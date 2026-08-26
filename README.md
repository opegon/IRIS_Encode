# IRIS ENCODE — Guide d'installation

**Version** : 0.8.0.9 — Windows (support macOS/Linux prévu)

---

## Prérequis

| Composant | Version minimale | Obligatoire |
|-----------|-----------------|-------------|
| Windows   | 10 / 11         | ✓           |
| Python    | 3.11            | ✓           |
| ffmpeg    | 7.x             | ✓ (auto-installable) |
| ffprobe   | 7.x             | ✓ (inclus avec ffmpeg) |
| dovi_tool | 2.x             | ✗ (optionnel — Dolby Vision) |
| mkvmerge  | 99.x            | ✗ (optionnel — greffe de pistes externes) |
| mpv       | récent          | ✗ (optionnel — visualisation) |
| GPU NVIDIA | driver récent  | ✗ (recommandé — encodage accéléré CUDA) |

---

## 1. Installer Python

### 1.1 Téléchargement

Rendez-vous sur **https://www.python.org/downloads/** et téléchargez la dernière version **3.11 ou supérieure** (3.12, 3.13, 3.14…).

> ⚠ Ne pas utiliser Python 3.10 ou antérieur — IRIS ENCODE utilise des fonctionnalités de syntaxe introduites en 3.11.

### 1.2 Installation

Lancez l'installateur téléchargé. **Important : cochez impérativement** l'option suivante avant de cliquer sur *Install Now* :

```
☑  Add Python X.XX to PATH
```

Sans cette case cochée, Python ne sera pas accessible depuis le terminal et `launch.bat` échouera.

### 1.3 Vérification

Ouvrez un terminal (`cmd` ou PowerShell) et tapez :

```
python --version
```

Résultat attendu : `Python 3.11.x` (ou version supérieure).

---

## 2. Installer les dépendances Python

IRIS ENCODE utilise plusieurs bibliothèques tierces listées dans `requirements.txt`.

### 2.1 Installation automatique (recommandée)

Ouvrez un terminal dans le dossier d'IRIS ENCODE et exécutez :

```
pip install -r requirements.txt
```

Cette commande installe :

| Bibliothèque    | Rôle |
|-----------------|------|
| `textual`       | Interface TUI (Terminal User Interface) |
| `rich`          | Rendu console enrichi (couleurs, tableaux) |
| `tomli-w`       | Écriture de fichiers TOML (config, profils) |
| `requests`      | Téléchargement automatique de ffmpeg |
| `beautifulsoup4`| Scraping IMDB (F8) et AlloCiné (F7) pour les métadonnées |

> `launch.bat` vérifie les dépendances à chaque démarrage et lance automatiquement
> `pip install -r requirements.txt` si l'une d'elles est manquante.

### 2.2 En cas d'erreur `pip introuvable`

Si `pip` n'est pas reconnu, essayez :

```
python -m pip install -r requirements.txt
```

### 2.3 En cas d'erreur de permissions

Sur certains postes avec restrictions, ajoutez `--user` :

```
pip install --user -r requirements.txt
```

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

Le lanceur vérifie automatiquement :
- La présence de Python 3.11+
- La présence et l'installation des dépendances Python
- La présence de ffmpeg / ffprobe
- La validité de la configuration

---

## 6. Structure des fichiers

```
iris_encode/
├── launch.bat          ← Point d'entrée Windows (double-clic)
├── main.py             ← Point d'entrée Python
├── config.toml         ← Configuration générale (éditable)
├── profiles.toml       ← Profils d'encodage (éditable)
├── requirements.txt    ← Dépendances Python
├── version.py          ← Version de l'application (source unique)
├── bin/                ← ffmpeg / ffprobe / dovi_tool / mkvmerge / mpv (auto)
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
| IMDB : note/synopsis absents | Clé OMDb non configurée | Voir section 9 |

---

## 12. Désinstallation

IRIS ENCODE ne modifie aucun paramètre système. Pour désinstaller :

1. Supprimez le dossier `iris_encode/`
2. (Optionnel) Désinstallez les bibliothèques Python : `pip uninstall textual rich tomli-w requests beautifulsoup4`

Les fichiers `config.toml` et `profiles.toml` sont supprimés avec le dossier.

---

*IRIS ENCODE — Interface Relationnelle d'Intelligence Servicielle*
