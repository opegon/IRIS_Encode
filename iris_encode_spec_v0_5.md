\# IRIS ENCODE — Spécification Fonctionnelle

\*\*Version\*\* : 0.5 — Document de référence  

\*\*Date\*\* : 2026-05-13  

\*\*Statut\*\* : Approuvé — base de développement



\---



\## 1. Contexte et objectif



Réécriture complète du script batch `reencode\_hevc\_v3.6.bat` en outil Python autonome avec interface TUI (Terminal User Interface). Le script original sert de \*\*cahier des charges fonctionnel\*\* pour la logique d'encodage.



\*\*Objectif :\*\* outil portable, robuste, interactif, extensible.



\---



\## 2. Architecture générale



```

iris\_encode/

├── launch.bat                    ← vérification Python, point d'entrée Windows

├── main.py                       ← point d'entrée Python (autonome)

├── config.toml                   ← configuration générale (éditable à la main)

├── profiles.toml                 ← profils d'encodage (éditables à la main)

├── bin/                          ← ffmpeg/ffprobe/dovi\_tool (créé automatiquement si besoin)

├── data/

│   ├── ffmpeg\_releases.toml      ← sources statiques embarquées (fallback)

│   └── ffmpeg\_releases\_cache.toml← dernière version fetchée (cache)

├── core/

│   ├── platform.py               ← abstraction OS + accélération matérielle

│   ├── preflight.py              ← vérification + installation ffmpeg

│   ├── config.py                 ← lecture/écriture config.toml

│   ├── profiles.py               ← lecture/écriture profiles.toml

│   ├── scanner.py                ← analyse fichiers via ffprobe

│   ├── decision.py               ← logique métier encodage

│   └── encoder.py                ← construction commande ffmpeg + exécution

├── tui/

│   ├── app.py                    ← application Textual principale

│   ├── screens/

│   │   ├── browser.py            ← navigation fichiers + sélection

│   │   ├── tracks.py             ← sélection pistes audio par fichier

│   │   ├── dryrun.py             ← prévisualisation décisions

│   │   ├── run.py                ← encodage + progress

│   │   └── config.py             ← gestion profils (CRUD)

│   └── widgets/

│       ├── file\_tree.py          ← arbre fichiers navigable

│       └── profile\_form.py       ← formulaire création/édition profil

├── logger/

│   └── logger.py                 ← module inerte (API prête, non implémenté)

└── requirements.txt

```



\---



\## 3. Lancement



\### 3.1 Via `launch.bat` (Windows)

```bat

launch.bat

```

\- Vérifie la présence de Python 3.11+ dans le PATH

\- Si absent : message explicite + redirection vers python.org

\- Si présent : délègue à `main.py` en passant les arguments (`%\*`)

\- Utilise `%\~dp0` pour garantir la portabilité du chemin



\### 3.2 Via `main.py` (direct)

```bash

python main.py

```

\- Entièrement autonome, indépendant de `launch.bat`

\- Aucune logique critique ne réside dans `launch.bat`



\---



\## 4. Preflight — `core/preflight.py`



\### 4.1 Vérification ffmpeg/ffprobe/dovi\_tool

Ordre de recherche :

1\. PATH système

2\. Dossier local `./bin/`



\### 4.2 Auto-installation si absent

\- Proposition interactive à l'utilisateur

\- Téléchargement depuis `config.toml` → `\[ffmpeg] fetch\_url`

\- Fallback sur `data/ffmpeg\_releases.toml` si réseau indisponible

\- Vérification SHA256 après téléchargement

\- Extraction dans `./bin/`

\- Build cible : \*\*essentials\*\* (\~30MB)

\- Sources primaires : gyan.dev / BtbN (GitHub)

\- `dovi\_tool` : binaire Windows depuis GitHub (quietvoid/dovi\_tool)



\### 4.3 Fetch des sources

\- Fetch à \*\*chaque lancement\*\*

\- Résultat mis en cache dans `data/ffmpeg\_releases\_cache.toml`

\- En cas d'échec réseau : fallback silencieux sur `data/ffmpeg\_releases.toml` embarqué avec message d'information



\### 4.4 Sortie console

```

\[✓] ffmpeg      trouvé — 7.1.1

\[✓] ffprobe     trouvé — 7.1.1

\[✓] dovi\_tool   trouvé — 2.1.0

```

```

\[✗] ffmpeg   introuvable

&#x20;   Télécharger et installer dans ./bin/ ? (o/N)

```



\---



\## 5. Configuration — `config.toml`



Fichier unique, éditable à la main, dans le dossier de l'application.



```toml

\[app]

language = "fr"



\[ffmpeg]

fetch\_url = "https://..."

auto\_install = true

bin\_dir = "./bin"



\[updates]

check\_on\_startup = true



\[tui.browser.columns]

\# Largeurs en caractères terminaux — persistées après redimensionnement manuel

fichier      = 22

resolution   = 12

debit        = 8

codec        = 8

dolby\_vision = 8

decision     = 18

audio        = 0        # 0 = colonne extensible (prend l'espace restant)

```



\---



\## 6. Profils d'encodage — `profiles.toml`



Format TOML, éditable à la main, dans le dossier de l'application.  

Un profil `\[default]` est toujours présent.



\*\*Profils builtin :\*\* `default`, `serie\_hd`, `cinema\_4k\_basic`, `cinema\_4k\_hd`, `basic\_delete`, `archivage` — éditables, non supprimables depuis l'interface.



```toml

\[default]

\# Vidéo

bitrate\_720p\_kbps        = 1500

bitrate\_1080p\_kbps       = 2200

bitrate\_4k\_kbps          = 5000

keep\_4k                  = false

delete\_source            = false

preset\_encoder           = "medium"

dolby\_vision             = "strip"      # strip | preserve | sdr

\# Audio

audio\_languages          = \["fre", "eng"]   # piste 0 toujours conservée

preserve\_hd\_audio        = false            # TrueHD / DTS-HD MA

audio\_stereo\_kbps        = 192

audio\_surround\_kbps      = 448              # 5.1

audio\_surround\_7\_1\_kbps  = 640             # 7.1

audio\_copy\_compatible    = true            # copy si codec déjà AAC ou AC3



\[serie\_hd]

\# Vidéo

bitrate\_720p\_kbps        = 1500

bitrate\_1080p\_kbps       = 2500

bitrate\_4k\_kbps          = 5000

keep\_4k                  = false

delete\_source            = false

preset\_encoder           = "medium"

dolby\_vision             = "strip"

\# Audio

audio\_languages          = \["fre", "eng"]

preserve\_hd\_audio        = false

audio\_stereo\_kbps        = 192

audio\_surround\_kbps      = 448

audio\_surround\_7\_1\_kbps  = 640

audio\_copy\_compatible    = true



\[cinema\_4k\_basic]

\# Vidéo

bitrate\_720p\_kbps        = 2000

bitrate\_1080p\_kbps       = 5000

bitrate\_4k\_kbps          = 8000            # ⚠ valeur recommandée spec

keep\_4k                  = true

delete\_source            = false

preset\_encoder           = "slow"

dolby\_vision             = "strip"

\# Audio

audio\_languages          = \["fre", "eng"]

preserve\_hd\_audio        = true

audio\_stereo\_kbps        = 192

audio\_surround\_kbps      = 448

audio\_surround\_7\_1\_kbps  = 640

audio\_copy\_compatible    = true



\[cinema\_4k\_hd]

\# Vidéo

bitrate\_720p\_kbps        = 2000

bitrate\_1080p\_kbps       = 5000

bitrate\_4k\_kbps          = 12000

keep\_4k                  = true

delete\_source            = false

preset\_encoder           = "slow"

dolby\_vision             = "preserve"

\# Audio

audio\_languages          = \["fre", "eng"]

preserve\_hd\_audio        = true

audio\_stereo\_kbps        = 192

audio\_surround\_kbps      = 448

audio\_surround\_7\_1\_kbps  = 640

audio\_copy\_compatible    = true



\[basic\_delete]

\# Vidéo

bitrate\_720p\_kbps        = 1500

bitrate\_1080p\_kbps       = 2000

bitrate\_4k\_kbps          = 3000            # keep\_4k=false — valeur jamais utilisée

keep\_4k                  = false

delete\_source            = true

preset\_encoder           = "fast"

dolby\_vision             = "sdr"

\# Audio

audio\_languages          = \["fre", "eng"]

preserve\_hd\_audio        = false

audio\_stereo\_kbps        = 192

audio\_surround\_kbps      = 448

audio\_surround\_7\_1\_kbps  = 640

audio\_copy\_compatible    = true



\[archivage]

\# Vidéo

bitrate\_720p\_kbps        = 1500

bitrate\_1080p\_kbps       = 2000

bitrate\_4k\_kbps          = 5000

keep\_4k                  = false

delete\_source            = true

preset\_encoder           = "fast"

dolby\_vision             = "sdr"

\# Audio

audio\_languages          = \["fre", "eng"]

preserve\_hd\_audio        = false

audio\_stereo\_kbps        = 192

audio\_surround\_kbps      = 448

audio\_surround\_7\_1\_kbps  = 640

audio\_copy\_compatible    = true

```



\*\*Comportement sur erreur de syntaxe :\*\*

```

⚠ profiles.toml illisible (erreur syntaxe ligne 12).

&#x20; Chargement du profil \[default] intégré.

```



\---



\## 7. Logique métier — `core/decision.py`



\### 7.1 Décision encodage vidéo



| Cas | Condition | Action |

|-----|-----------|--------|

| \*\*CAS 1\*\* | bitrate source ≥ seuil cible | Réencodage HEVC au bitrate cible |

| \*\*CAS 2\*\* | bitrate OK mais résolution trop grande | Redimensionnement HEVC, bitrate original |

| \*\*CAS 3\*\* | bitrate OK, résolution OK, codec non-standard (ni H264 ni HEVC) | Réencodage H264, bitrate et taille conservés |

| \*\*SKIP\*\* | bitrate OK, résolution OK, codec H264 ou HEVC | Aucun traitement |



\### 7.2 Bitrates vidéo cibles par résolution



| Résolution | Valeurs disponibles | Défaut | Note |

|---|---|---|---|

| \*\*720p\*\* | 1500 / 2000k | 1500k | |

| \*\*1080p\*\* | 2000 / 2200 / 2500 / 3000 / 3500 / 5000k | 2500k | |

| \*\*4K\*\* | 3000 / 5000 / 8000 / 12000k | 5000k | ⚠ 8000k recommandé |



`decision.py` sélectionne automatiquement la valeur correspondant à la résolution détectée.



\### 7.3 Gestion Dolby Vision



| Profil DV | Option `strip` | Option `preserve` | Option `sdr` |

|---|---|---|---|

| \*\*P7/P8\*\* | Strip RPU → HDR10 | Copy sans modification | Strip RPU → HDR10 |

| \*\*P5\*\* | Tone map → SDR ⚠ lent | Copy ⚠ compat. limitée | Tone map → SDR ⚠ lent |

| \*\*Aucun\*\* | Sans effet | Sans effet | Sans effet |



\*\*Pipeline tone mapping P5 (SDR) :\*\*

```

zscale=t=linear:npl=100,

format=gbrpf32le,

zscale=p=bt709,

tonemap=tonemap=hable:desat=0,

zscale=t=bt709:m=bt709:r=tv,

format=yuv420p

```

Algorithme `hable` — référence pour contenu cinéma. Exécuté CPU, impact performance significatif.



\*\*Détection profil DV :\*\* `dovi\_tool --probe` (retourne JSON) + `ffprobe` (color metadata).



\### 7.4 Décision encodage audio



\#### Règle de sélection des pistes



```

Pour chaque piste audio :

&#x20; 1. Index 0                    → toujours conservée (langue originale)

&#x20; 2. Langue dans audio\_languages → conservée

&#x20; 3. Sinon                      → exclue (sauf sélection manuelle TUI)

```



La piste d'index 0 est conservée inconditionnellement, quelle que soit sa langue.

Cela couvre les films en VO sans nécessiter de référencer explicitement toutes les langues possibles.



\#### Règle de transcodage par piste conservée



```

Pour chaque piste conservée :

&#x20; 1. Codec lossless (TrueHD / DTS-HD MA) ?

&#x20;      preserve\_hd\_audio = true  → copy

&#x20;      preserve\_hd\_audio = false → appliquer règle canal (tableau ci-dessous)

&#x20; 2. Codec compatible (AAC / AC3) ET audio\_copy\_compatible = true ?

&#x20;      → copy (pas de recompression)

&#x20; 3. Sinon → transcoder selon règle canal

```



\#### Codec et bitrate de sortie par configuration de canaux



| Canaux source | Codec sortie | Paramètre bitrate |

|---|---|---|

| Mono (1.0) | AAC | 64k (fixe) |

| Stéréo (2.0) | AAC | `audio\_stereo\_kbps` |

| Surround 5.1 | AC3 | `audio\_surround\_kbps` |

| Surround 7.1 | AC3 | `audio\_surround\_7\_1\_kbps` |

| TrueHD / DTS-HD MA | copy ou règle surround | selon `preserve\_hd\_audio` |



\### 7.5 Sous-titres



\- PGS / DVD (image) → conteneur MKV, `-c:s copy`

\- SRT / ASS (texte) → conteneur MP4, `-c:s mov\_text`



\### 7.6 Nommage des sorties



\- `nom\_fichier\_\[hevc].mp4/.mkv`

\- `nom\_fichier\_\[H264].mp4/.mkv`



\---



\## 8. Interface TUI — `tui/`



Framework : \*\*Textual\*\* (Python)



\### 8.1 Écran Browser — navigation fichiers



```

┌─ IRIS ENCODE ────────────────────────────────────────────────────────────────┐

│ 📁 D:\\Videos                              3/7 sélectionnés · Profil: default │

├─ Fichier ⇔──────┬─ Résolution ─┬─ Débit ─┬─ Codec ─┬─ Dolby V. ─┬─ Décision ──────┬─ Audio ──────────────┤

│ \[x] 📁 Films/   │              │         │         │             │                 │                      │

│ ▶\[x] film1.mkv  │  1920x1080   │  8400k  │  hevc   │  DV:P8      │  → HDR10        │  TrueHD 7.1 fre+eng  │

│   \[ ] film2.mp4 │   720x480    │   900k  │  h264   │  —          │  ← SKIP         │  AAC 2.0 fre         │

│   \[x] film3.avi │  1280x720    │  3200k  │  vp9    │  —          │  → H264         │  AC3 5.1 fre         │

│   \[x] film4.mkv │  3840x2160   │ 25000k  │  hevc   │  DV:P5      │  → SDR ⚠        │  DTS-HD 5.1 eng      │

│ \[ ] 📁 Séries/  │              │         │         │             │                 │                      │

├─────────────────┴──────────────┴─────────┴─────────┴─────────────┴─────────────────┴──────────────────────┤

│ film1.mkv — D:\\Videos\\Films\\film1.mkv                                              ligne 2 / 47            │

│ \[ESPACE] sélect  \[A] tout  \[N] aucun  \[↵] entrer  \[Back] remonter  \[T] pistes  \[PgUp/PgDn]  \[Home/End]   │

│ \[F1] dry-run     \[F2] run  \[F5] config  \[−/+] profil  \[Tab/Sh+Tab] col  \[</>/\[>] resize  \[F10] quitter   │

└────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

```



\#### Navigation

\- Déplacement ligne : ↑ / ↓

\- Déplacement page : `\[PageUp]` / `\[PageDown]`

\- Saut début / fin de liste : `\[Home]` / `\[End]`

\- Sélection unitaire : `\[Espace]`

\- Sélection globale : `\[A]` tout / `\[N]` aucun

\- Entrer dans un sous-dossier : `\[↵ Entrée]`

\- Remonter au dossier parent : `\[Back]`

\- Accès pistes audio du fichier courant : `\[T]`

\- Actions : `\[F1]` Dry-run · `\[F2]` Run · `\[F5]` Config · `\[F10]` Quitter



\#### Colonnes redimensionnables — implémentation `DataTable`



Le browser utilise le widget `DataTable` de Textual, qui expose nativement la gestion des colonnes.



\*\*Configuration obligatoire `DataTable` :\*\*

\- `cursor\_type="row"` — active le curseur ligne et le scroll automatique curseur-visible

\- `show\_cursor=True` — curseur visible à tout moment

\- CSS : `height: 1fr` sur le `DataTable` directement — \*\*ne pas l'encapsuler dans un conteneur à hauteur fixe\*\*, ce qui clipperait le contenu au lieu de le faire défiler



\*\*Comportement de scroll :\*\*

\- La liste défile automatiquement pour maintenir la ligne curseur visible lors de la navigation ↑ / ↓ / `\[PageUp]` / `\[PageDown]` / `\[Home]` / `\[End]`

\- Aucune logique de scroll manuelle n'est nécessaire : c'est le comportement natif de `DataTable` avec `cursor\_type="row"`

\- Indicateur de position affiché dans la barre de statut (en bas d'écran) : `ligne N / N`



\*\*Largeurs par défaut\*\* (en caractères terminaux) :



| Colonne | Largeur défaut | Extensible |

|---------|---------------|------------|

| Fichier | 22 | non |

| Résolution | 12 | non |

| Débit | 8 | non |

| Codec | 8 | non |

| Dolby Vision | 8 | non |

| Décision | 18 | non |

| Audio | — | \*\*oui\*\* (prend l'espace restant) |



\*\*Redimensionnement :\*\*

\- Indicateur visuel `⇔` dans l'en-tête des colonnes fixes

\- Redimensionnement clavier : focus sur l'en-tête de colonne → `\[<]` / `\[>]`

\- Redimensionnement souris : glisser la bordure d'en-tête (si terminal supporte les événements souris)

\- Largeur minimale par colonne : 6 caractères

\- Les largeurs ajustées sont persistées dans `config.toml` sous `\[tui.browser.columns]`

\- La colonne Audio absorbe toujours l'espace résiduel (pas de largeur fixe)



\*\*Noms de fichiers longs :\*\* tronqués avec `…` à droite si la colonne Fichier ne suffit pas. Le nom complet et le chemin absolu sont affichés dans la barre de statut au bas de l'écran lors du survol / focus, avec l'indicateur de position `ligne N / N` aligné à droite.



\#### Affichage par ligne (fichier)

\- Résolution, bitrate, codec vidéo, profil DV, décision vidéo colorée, résumé pistes audio conservées

\- Code couleur décision : HEVC → violet · H264 → cyan · SDR ⚠ → orange · SKIP → gris



\---



\### 8.2 Écran Tracks — sélection pistes audio



Accessible depuis le browser via `\[T]` sur le fichier courant.  

Retour au browser via `\[←]`.



```

┌─ Pistes audio — film1.mkv ──────────────────────────────────────────────────┐

│                                                                              │

│  \[x] 0:a:0  TrueHD   7.1  fre  — conservée (piste originale) ⚑  → copy     │

│  \[x] 0:a:1  AC3      5.1  fre  — conservée (langue)              → copy     │

│  \[x] 0:a:2  TrueHD   7.1  eng  — conservée (langue)              → copy     │

│  \[x] 0:a:3  AAC      2.0  eng  commentary — inclus               → copy     │

│  \[ ] 0:a:4  AC3      5.1  deu  — exclue (langue)                            │

│  \[ ] 0:a:5  DTS      5.1  fre  — exclue (doublon fre)                       │

│                                                                              │

│  Langues actives : \[FR] \[EN]   \[+ autre]                                     │

│  \[ESPACE] sélect  \[L] modifier langues  \[Entrée] valider  \[←] retour        │

└──────────────────────────────────────────────────────────────────────────────┘

```



\- Affichage par piste : index ffmpeg, codec, canaux, langue, raison de sélection, décision

\- `⚑` : piste 0 (verrouillée par défaut — désélection possible avec confirmation explicite)

\- Sélection/déselection manuelle : `\[Espace]`

\- Modification des langues actives pour ce fichier uniquement : `\[L]`

\- Les modifications sont locales au fichier, sans impact sur le profil

\- `\[←]` retour browser (validation implicite des modifications)

\- `\[Entrée]` validation explicite + retour browser



\---



\### 8.3 Écran Dry-run



\- Prévisualisation des décisions pour tous les fichiers sélectionnés

\- Aucune écriture disque

\- Affichage par fichier : action vidéo, conteneur de sortie, traitement DV, pistes audio retenues et leur décision (copy / transcode / codec de sortie)

\- Bilan en pied : nombre de fichiers par type d'action (HEVC / H264 / SDR / SKIP)

\- Fichiers ignorés listés avec raison



\---



\### 8.4 Écran Run



```

┌─ Encodage — 5 fichiers · Profil : default ──────────── Global : 42% ────────┐

│                                                                              │

│  ✓  film1.mkv    HEVC 2500k → HDR10      ✓ SUCCÈS                           │

│     ████████████████████████                                                  │

│  ▶  film3.avi    H264 3200k               38%                                │

│     █████████░░░░░░░░░░░░░░░                                                  │

│  ○  film4.mkv    HEVC 5000k → SDR        en attente                          │

│  ○  ep01.mkv     HEVC 2500k              en attente                          │

│  ○  ep02.mkv     HEVC 2500k              en attente                          │

│                                                                              │

│  \[▶ Démarrer] / \[⏸ Pause]   ████████████░░░░░░░░░░░░░░░░░░░  42%           │

├──────────────────────────────────────────────────────────────────────────────┤

│ $ ffmpeg -hwaccel cuda -i "film3.avi" -c:v h264\_nvenc -pix\_fmt yuv420p      │

│   -b:v 3200000 -maxrate 3200000 -bufsize 6400k -rc cbr -preset medium …     │

│ frame=  1094 fps= 89 q=27.0 size=   36864kB time=00:00:45.58                │

│   bitrate=6627.4kbits/s speed=3.71x                                          │

└──────────────────────────────────────────────────────────────────────────────┘

```



\#### Liste de progression

\- Une ligne par fichier : icône état (○ / ▶ / ✓ / ✗) + nom + action + pourcentage

\- Barre de progression individuelle sous le fichier actif ou terminé

\- Barre de progression globale en pied de liste



\#### Zone commande ffmpeg (bas d'écran, séparée par une bordure)

\- \*\*Ligne commande\*\* : commande `ffmpeg` complète du fichier en cours d'encodage

&#x20; - Affichée sur une ou deux lignes selon la largeur du terminal

&#x20; - Tronquée avec `…` si dépasse la capacité d'affichage

\- \*\*Ligne de retour\*\* : dernière ligne stdout capturée depuis ffmpeg

&#x20; - Format type : `frame= N fps= N q=N size= NkB time=HH:MM:SS.ss bitrate=N.Nkbits/s speed=Nx`

&#x20; - Mise à jour à chaque ligne lue (non scrollable — uniquement la dernière)

&#x20; - Affichage fixe : pas de défilement, pas de log accumulé

\- En cas d'erreur : ligne de retour colorée en rouge avec le message d'erreur ffmpeg



\#### Comportement

\- `\[▶ Démarrer]` : lance l'encodage séquentiel des fichiers sélectionnés

\- `\[⏸ Pause]` : suspend le processus ffmpeg en cours (`SIGSTOP` / `subprocess.send\_signal`)

\- `\[↩ Recommencer]` (après fin) : remet à zéro l'état et la liste

\- Suppression source après succès : selon `delete\_source` du profil actif

\- En cas d'erreur ffmpeg : fichier marqué ✗, encodage des suivants continue, source conservée



\---



\### 8.5 Écran Config — gestion des profils



\#### Vue liste (état par défaut)



```

┌─ Configuration — Profils d'encodage ─────── profiles.toml · Actif : default ┐

│                                                                              │

│  \[default]                                               \[ACTIF] \[✎ éditer] │

│  Usage général · 1080p max · 2200k                                           │

│  dv: strip  · 1080p: 2200k  · preset: medium  · hd-audio: non               │

│                                                                              │

│  \[serie\_hd]                                                     \[✎ éditer]  │

│  Séries HD · 1080p max · 2500k                                               │

│  dv: strip  · 1080p: 2500k  · preset: medium  · hd-audio: non               │

│                                                                              │

│  \[cinema\_4k\_basic]                                              \[✎ éditer]  │

│  Cinéma 4K · keep\_4k · 8000k · strip DV                                     │

│  dv: strip  · 1080p: 5000k  · preset: slow   · hd-audio: oui                │

│                                                                              │

│  \[cinema\_4k\_hd]                                                 \[✎ éditer]  │

│  Cinéma 4K HD · keep\_4k · 12000k · preserve DV                              │

│  dv: preserve · 1080p: 5000k  · preset: slow   · hd-audio: oui              │

│                                                                              │

│  \[basic\_delete]                                                 \[✎ éditer]  │

│  Conversion + suppression source · 2000k                                     │

│  dv: sdr    · 1080p: 2000k  · preset: fast   · hd-audio: non                │

│                                                                              │

│  \[archivage]                                                    \[✎ éditer]  │

│  Archivage · 2000k · delete\_source                                           │

│  dv: sdr    · 1080p: 2000k  · preset: fast   · hd-audio: non                │

│                                                                              │

│  \[mon\_profil]                           \[user] \[ACTIF] \[✎ éditer] \[× del]  │

│  ...                                                                         │

│                                                                              │

├──────────────────────────────────────────────────────────────────────────────┤

│ \[+ Nouveau profil]   \[E] éditer profiles.toml directement   \[←] retour      │

└──────────────────────────────────────────────────────────────────────────────┘

```



\*\*Règles :\*\*

\- Profils \*\*builtin\*\* (`default`, `serie\_hd`, `cinema\_4k\_basic`, `cinema\_4k\_hd`, `basic\_delete`, `archivage`) : éditables, \*\*non supprimables\*\*

\- Profils \*\*user\*\* (créés via l'interface) : éditables et supprimables

\- Cliquer sur un profil (ou `\[Entrée]`) : l'active comme profil courant

\- `\[✎ éditer]` : ouvre le formulaire inline sur ce profil

\- `\[× del]` : supprime le profil user après confirmation (popup)

\- `\[E]` : ouvre `profiles.toml` dans l'éditeur système (`$EDITOR` ou notepad.exe)



\#### Vue formulaire (création / édition)



Le formulaire remplace la liste dans l'écran Config. Retour à la liste par `\[Échap]` ou `\[✕ Annuler]`.



```

┌─ Éditer \[default] ─────────────────────────────────── profiles.toml ────────┐

│                                                                              │

│  id (nom du profil)    \[default\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_]  (identifiant figé)        │

│                                                                              │

│  ── Vidéo ────────────────────────────────────────────────────────────────  │

│  bitrate\_720p\_kbps     \[1500 ▼]    bitrate\_1080p\_kbps   \[2500 ▼]            │

│  bitrate\_4k\_kbps       \[5000 ▼]    keep\_4k              \[☐]  ⚠ 8000k rec.   │

│  dolby\_vision          \[strip ▼]   preset\_encoder        \[medium ▼]          │

│  delete\_source         \[☐]  supprimer les originaux                          │

│                                                                              │

│  ── Audio ────────────────────────────────────────────────────────────────  │

│  audio\_languages       \[fre, eng\_\_\_\_\_\_\_\_\_\_\_]  ISO 639-2, séparées virgule    │

│  preserve\_hd\_audio     \[☐]  TrueHD/DTS-HD MA → copy                         │

│  audio\_stereo\_kbps     \[192 ▼]    audio\_surround\_kbps   \[448 ▼]  5.1        │

│  audio\_7\_1\_kbps        \[640 ▼]    audio\_copy\_compatible \[☑]                  │

│                                                                              │

│  \[✓ Enregistrer]  \[✕ Annuler]                                                │

└──────────────────────────────────────────────────────────────────────────────┘

```



\*\*Champs et valeurs :\*\*



| Champ | Type | Valeurs |

|-------|------|---------|

| `id` | texte | libre (création) · figé (édition) |

| `bitrate\_720p\_kbps` | select | 1500, 2000 |

| `bitrate\_1080p\_kbps` | select | 2000, 2200, 2500, 3000, 3500, 5000 |

| `bitrate\_4k\_kbps` | select | 3000, 5000, 8000 ⚠, 12000 |

| `keep\_4k` | checkbox | |

| `dolby\_vision` | select | strip, preserve, sdr |

| `preset\_encoder` | select | fast, medium, slow |

| `delete\_source` | checkbox | |

| `audio\_languages` | texte libre | codes ISO 639-2 séparés par virgule |

| `preserve\_hd\_audio` | checkbox | |

| `audio\_stereo\_kbps` | select | 96, 128, 192, 320 |

| `audio\_surround\_kbps` | select | 320, 448, 640 |

| `audio\_surround\_7\_1\_kbps` | select | 448, 640, 768 |

| `audio\_copy\_compatible` | checkbox | |



\*\*Comportement de sauvegarde :\*\*

1\. Validation de l'`id` : caractères alphanumériques, `\_`, `-`, max 32 chars

2\. Écriture dans `profiles.toml` via `core/profiles.py`

3\. Le profil sauvegardé devient immédiatement le profil actif

4\. Retour automatique à la vue liste



\*\*Note — `audio\_languages` en v1 :\*\*  

Le champ est un texte libre (ex. `fre, eng`). Un widget dédié de sélection multi-langue par badges (similaire à l'écran Tracks) est prévu pour une version ultérieure. Le parsing accepte les séparateurs `,`, `;` et espace.



\#### Implémentation — `tui/widgets/profile\_form.py`

\- Widget Textual autonome `ProfileForm`

\- Composé d'`Input`, `Select` et `Checkbox` Textual natifs

\- Méthodes : `load(profile\_data)`, `dump() → dict`, `validate() → bool | list\[str]`

\- Émets un message `ProfileSaved(data)` à la validation

\- Réutilisable depuis tout écran (Config, mais aussi potentiellement un futur écran de premier lancement)



\---



\## 9. Abstraction plateforme — `core/platform.py`



| Paramètre | Windows/NVIDIA | macOS | Linux/CPU |

|-----------|---------------|-------|-----------|

| hwaccel | `cuda` | `videotoolbox` | \*(absent)\* |

| encoder HEVC | `hevc\_nvenc` | `hevc\_videotoolbox` | `libx265` |

| encoder H264 | `h264\_nvenc` | `h264\_videotoolbox` | `libx264` |



\*\*Version actuelle : Windows uniquement.\*\*  

L'abstraction est en place pour faciliter une future extension multiplateforme.



\---



\## 10. Logger — `logger/logger.py`



Module \*\*inerte\*\* en v1 — API définie, aucun backend branché.



```python

logger.info("scan terminé", files=12)

logger.error("encodage échoué", file="video.mkv")

logger.session\_start(profile="default", path="D:/Videos")

```



Backend prévu : fichier JSON ou SQLite, branché dans une release ultérieure.



\---



\## 11. Portabilité



\- Tout `pathlib.Path`, aucune string de chemin en dur

\- `./bin/` pour ffmpeg/ffprobe/dovi\_tool embarqués

\- `config.toml` et `profiles.toml` dans le dossier application

\- Aucune dépendance au registre Windows ni à `%APPDATA%`

\- Fonctionne depuis une clé USB



\*\*Future release :\*\* Python embarqué (embeddable package) pour zéro prérequis système.



\---



\## 12. Dépendances Python



```

textual        ← TUI

rich           ← affichage console

tomli-w        ← écriture TOML (lecture native Python 3.11+)

requests       ← téléchargement ffmpeg

```



\---



\## 13. Ordre de développement



```

1\.  core/platform.py

2\.  core/preflight.py

3\.  core/config.py

4\.  core/profiles.py

5\.  core/scanner.py               ← inclut détection pistes audio (codec, canaux, langue)

6\.  core/decision.py              ← inclut logique audio (sélection + transcodage)

7\.  core/encoder.py

8\.  tui/widgets/file\_tree.py

9\.  tui/widgets/profile\_form.py   ← formulaire création/édition profil (ProfileForm)

10\. tui/screens/browser.py        ← DataTable + colonnes redimensionnables

11\. tui/screens/tracks.py         ← sélection pistes audio, retour \[←]

12\. tui/screens/dryrun.py

13\. tui/screens/run.py            ← zone commande ffmpeg + ligne de retour live

14\. tui/screens/config.py         ← CRUD profils, ProfileForm intégré

15\. tui/app.py

16\. main.py

17\. launch.bat

```



\---



\## 14. Hors scope v1



\- Logs persistants (architecture prévue, non implémentée)

\- Python embarqué

\- Support multiplateforme (macOS, Linux)

\- File de traitement multi-dossiers

\- Interface de mise à jour des sources ffmpeg

\- Gestion des commentary tracks par heuristique (titre de piste)

\- Règles audio par piste au-delà du filtre langue + index 0

\- Widget multi-langue par badges pour `audio\_languages` (champ texte libre en v1)



\---



\## 15. Changelog



| Version | Date | Modifications |

|---|---|---|

| 0.1 | 2026-05-12 | Document initial |

| 0.2 | 2026-05-12 | Dolby Vision (strip/preserve/sdr), bitrates vidéo par résolution, dovi\_tool dans preflight |

| 0.3 | 2026-05-12 | Politique audio complète : sélection pistes (index 0 + filtre langue), transcodage (AAC stéréo / AC3 surround / copy lossless), profils audio, écran Tracks |

| 0.4 | 2026-05-12 | Browser : colonnes redimensionnables via `DataTable` (largeurs par défaut, persistance `config.toml`, colonne Audio extensible, troncature nom fichier) · Navigation : `\[←]` remonter dossier parent et retour Tracks → Browser · Run : zone commande ffmpeg complète + ligne de retour live (non scrollable) · Config : CRUD profils complet — formulaire inline `ProfileForm`, protection builtin, validation id, écriture `profiles.toml` · Architecture : ajout `tui/widgets/profile\_form.py` · Note `audio\_languages` texte libre v1, widget badges prévu v2 |

| 0.5 | 2026-05-13 | Browser : correction scroll — spécification explicite `cursor\_type="row"`, `show\_cursor=True`, CSS `height: 1fr` sur `DataTable` (pas de conteneur à hauteur fixe) · Navigation : ajout `\[PageUp]` / `\[PageDown]` / `\[Home]` / `\[End]` · Barre de statut : ajout chemin absolu complet + indicateur `ligne N / N` aligné à droite · Profils : remplacement des builtins (`cinema\_4k` → `serie\_hd`, `cinema\_4k\_basic`, `cinema\_4k\_hd`, `basic\_delete`) — 6 profils builtin au total · `\[default]` : `bitrate\_1080p\_kbps` 2500k → 2200k · `\[basic\_delete]` : `bitrate\_4k\_kbps` corrigé 3500 → 3000 (hors spec) · §8.5 : mockup Config mis à jour |

| 0.6 | 2026-05-14 | Browser — raccourcis clavier : `\[F1]` dry-run · `\[F2]` run · `\[F5]` config · `\[F10]` quitter (remplace D/R/C/Q et Ctrl+X) · suppression flèches ←/→ pour navigation dossier (Enter/Back conservés) · `\[PgUp]` `\[PgDn]` `\[Home]` `\[End]` documentés dans le footer · footer mis à jour (2 lignes) |



