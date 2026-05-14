# IRIS ENCODE — Guide d'installation

**Version** : 0.1 — Windows (support macOS/Linux prévu)

---

## Prérequis

| Composant | Version minimale | Obligatoire |
|-----------|-----------------|-------------|
| Windows   | 10 / 11         | ✓           |
| Python    | 3.11            | ✓           |
| ffmpeg    | 7.x             | ✓ (auto-installable) |
| ffprobe   | 7.x             | ✓ (inclus avec ffmpeg) |
| dovi_tool | 2.x             | ✗ (optionnel — Dolby Vision) |
| GPU NVIDIA | driver récent  | ✗ (recommandé — encodage accéléré CUDA) |

---

## 1. Installer Python

### 1.1 Téléchargement

Rendez-vous sur **https://www.python.org/downloads/** et téléchargez la dernière version **3.11 ou supérieure** (3.12, 3.13…).

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
| `cinemagoer`    | Recherche de métadonnées IMDB (F8) |
| `beautifulsoup4`| Scraping AlloCiné pour les métadonnées (F7) |

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

## 4. (Optionnel) Installer dovi_tool

`dovi_tool` est nécessaire uniquement pour traiter les contenus **Dolby Vision**.
Si vous ne travaillez pas avec des fichiers DV, vous pouvez répondre `N` à la question.

### Option A — Installation automatique (recommandée)

Au premier lancement, si `dovi_tool` est absent, IRIS ENCODE propose :

```
  dovi_tool absent (optionnel — nécessaire pour le Dolby Vision).
  Télécharger et installer dovi_tool (Dolby Vision) dans ./bin/ ? (o/N) :
```

Répondez `o`. Le binaire (~2 Mo) est téléchargé depuis GitHub
(quietvoid/dovi_tool) et extrait dans `bin/`.

### Option B — Installation manuelle dans `bin/`

1. Téléchargez le binaire Windows depuis :
   https://github.com/quietvoid/dovi_tool/releases
2. Extrayez `dovi_tool.exe` et placez-le dans le dossier `bin/` :
   ```
   iris_encode/
   └── bin/
       └── dovi_tool.exe
   ```

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
├── bin/                ← ffmpeg / ffprobe / dovi_tool (créé automatiquement)
├── data/               ← Sources de téléchargement (embarquées)
├── core/               ← Logique métier
├── tui/                ← Interface utilisateur
└── logger/             ← Module de journalisation (inactif en v0.1)
```

---

## 7. Personnalisation

Les fichiers `config.toml` et `profiles.toml` sont éditables à la main avec n'importe quel éditeur de texte (Notepad, VS Code, etc.).

**`config.toml`** — largeurs des colonnes de l'interface, langue, chemins :
```toml
[tui.browser.columns]
# La colonne "fichier" s'étend automatiquement à l'espace disponible
resolution   = 12     # largeur de la colonne résolution
audio        = 20     # largeur de la colonne pistes audio
decision     = 12     # largeur de la colonne décision
```

**`profiles.toml`** — profils d'encodage (bitrate, résolution, audio, Dolby Vision) :
```toml
[default]
bitrate_1080p_kbps = 2500
keep_4k            = false
dolby_vision       = "strip"
```

---

## 8. Terminal recommandé

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

**Vérifier son terminal hôte :** clic droit sur la barre de titre de la fenêtre.
Si le titre mentionne *Windows Terminal* ou l'icône est celle de WT, le rendu sera optimal.

---

## 9. Résolution des problèmes courants

| Symptôme | Cause probable | Solution |
|----------|---------------|----------|
| `python` non reconnu | Python absent du PATH | Réinstaller Python en cochant *Add to PATH* |
| `pip` non reconnu | pip absent | Utiliser `python -m pip` |
| Écran noir au lancement | Terminal ne supporte pas l'interface TUI | Utiliser Windows Terminal ou cmd.exe classique |
| Encodage lent | Pas de GPU NVIDIA détecté | Normal — encodage CPU activé automatiquement |
| `dovi_tool introuvable` | Optionnel non installé | Voir section 4 — uniquement si fichiers Dolby Vision |
| Erreur à l'import d'un module | Dépendances manquantes | Relancer `pip install -r requirements.txt` |

---

## 10. Désinstallation

IRIS ENCODE ne modifie aucun paramètre système. Pour désinstaller :

1. Supprimez le dossier `iris_encode/`
2. (Optionnel) Désinstallez les bibliothèques Python : `pip uninstall textual rich tomli-w requests cinemagoer beautifulsoup4`

Les fichiers `config.toml` et `profiles.toml` sont supprimés avec le dossier.

---

*IRIS ENCODE v0.1 — Interface Relationnelle d'Intelligence Servicielle*
