# IRIS ENCODE — Spécification Fonctionnelle

**Version** : 0.6 — Document de référence

**Date** : 2026-05-15

**Statut** : Approuvé — base de développement



---



## 1. Contexte et objectif



Réécriture complète du script batch `reencode_hevc_v3.6.bat` en outil Python autonome avec interface TUI (Terminal User Interface).

**Objectif :** outil portable, robuste, interactif, extensible.



---



## 2. Architecture générale



```
iris_encode/
├── launch.bat                    ← vérification Python, point d'entrée Windows
├── main.py                       ← point d'entrée Python (autonome)
├── config.toml                   ← configuration générale (éditable à la main)
├── profiles.toml                 ← profils d'encodage (éditables à la main)
├── bin/                          ← ffmpeg/ffprobe/dovi_tool (créé automatiquement si besoin)
├── data/
│   ├── ffmpeg_releases.toml      ← sources statiques embarquées (fallback)
│   └── ffmpeg_releases_cache.toml← dernière version fetchée (cache)
├── core/
│   ├── platform.py               ← abstraction OS + accélération matérielle
│   ├── preflight.py              ← vérification + installation ffmpeg
│   ├── config.py                 ← lecture/écriture config.toml
│   ├── profiles.py               ← lecture/écriture profiles.toml
│   ├── scanner.py                ← analyse fichiers via ffprobe + enrichissement DV
│   ├── decision.py               ← logique métier encodage
│   ├── encoder.py                ← construction commande ffmpeg + exécution
│   ├── dovi.py                   ← wrapper dovi_tool (probe, RPU, x265-params HDR10)
│   └── meta.py                   ← recherche métadonnées IMDB / AlloCiné
├── tui/
│   ├── app.py                    ← application Textual principale
│   ├── mixins.py                 ← TableNavMixin (navigation DataTable)
│   ├── screens/
│   │   ├── browser.py            ← navigation fichiers + sélection
│   │   ├── tracks.py             ← sélection pistes + édition décision vidéo
│   │   ├── dryrun.py             ← prévisualisation décisions
│   │   ├── run.py                ← encodage + progress
│   │   ├── config.py             ← gestion profils (CRUD)
│   │   ├── value_picker.py       ← modal sélection de valeur
│   │   ├── meta_popup.py         ← popup métadonnées IMDB / AlloCiné
│   │   ├── recursive_confirm.py  ← modal confirmation run récursif
│   │   └── quit.py               ← modal confirmation quitter
│   └── widgets/
│       ├── file_tree.py          ← FileNavigator (navigation virtuelle + répertoires)
│       ├── footer.py             ← TwoLineFooter (footer 2 lignes)
│       └── profile_form.py       ← formulaire création/édition profil
├── logger/
│   └── logger.py                 ← module inerte (API prête, non implémenté)
└── requirements.txt
```



---



## 3. Lancement



### 3.1 Via `launch.bat` (Windows)

```bat
launch.bat
```

- Vérifie la présence de Python 3.11+ dans le PATH
- Si absent : message explicite + redirection vers python.org
- Si présent : délègue à `main.py` en passant les arguments (`%*`)
- Utilise `%~dp0` pour garantir la portabilité du chemin



### 3.2 Via `main.py` (direct)

```bash
python main.py
```

- Entièrement autonome, indépendant de `launch.bat`
- Aucune logique critique ne réside dans `launch.bat`



---



## 4. Preflight — `core/preflight.py`



### 4.1 Vérification ffmpeg/ffprobe/dovi_tool

Ordre de recherche :

1. PATH système
2. Dossier local `./bin/`



### 4.2 Auto-installation si absent

- Proposition interactive à l'utilisateur
- Téléchargement depuis `config.toml` → `[ffmpeg] fetch_url`
- Fallback sur `data/ffmpeg_releases.toml` si réseau indisponible
- Vérification SHA256 après téléchargement
- Extraction dans `./bin/`
- Build cible : **essentials** (~30MB)
- Sources primaires : gyan.dev / BtbN (GitHub)
- `dovi_tool` : binaire Windows depuis GitHub (quietvoid/dovi_tool)



### 4.3 Fetch des sources

- Fetch à **chaque lancement**
- Résultat mis en cache dans `data/ffmpeg_releases_cache.toml`
- En cas d'échec réseau : fallback silencieux sur `data/ffmpeg_releases.toml` embarqué avec message d'information



### 4.4 Sortie console

```
[✓] ffmpeg      trouvé — 7.1.1
[✓] ffprobe     trouvé — 7.1.1
[✓] dovi_tool   trouvé — 2.1.0
```

```
[✗] ffmpeg   introuvable
    Télécharger et installer dans ./bin/ ? (o/N)
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
omdb_api_key = ""   # clé gratuite sur omdbapi.com — active note + synopsis IMDB

[tui.browser.columns]
# Largeurs en caractères terminaux — persistées après redimensionnement manuel
fichier      = 50
taille       = 12
resolution   = 10
duree        = 7
debit        = 6
codec        = 6
dolby_vision = 8
decision     = 8
audio        = 16   # largeur fixe (pas de colonne extensible en v0.6)

[tui.dryrun.columns]
fichier    = 48
taille     = 10
estim      = 18
action     = 10
conteneur  = 10
dv         = 6
bitrate    = 10
res        = 12
audio      = 30

[tui.tracks.columns]
codec = 12
fmt   = 10   # "Format" (layout canaux / type sous-titre)
src   = 26
```



---



## 6. Profils d'encodage — `profiles.toml`



Format TOML, éditable à la main. Les profils builtin sont toujours présents (non supprimables).

Le champ `dolby_vision` accepte : `"hdr10"` (DV → HDR10), `"dv"` (DV → DV copy), `"sdr"` (DV → SDR tone map).

> **Note :** les valeurs `"strip"` et `"preserve"` des versions antérieures sont remplacées par `"hdr10"` et `"dv"`.



**Profils builtin (9) :** `serie_anime`, `serie_basic`, `serie_hd`, `film_basic`, `film_hd`, `cinema_4k_basic`, `cinema_4k_hd`, `cinema_4k_quality`, `basic_delete` — éditables, non supprimables.



```toml
[serie_anime]
# Séries animées · 1080p max · fast · DV→SDR
bitrate_720p_kbps        = 1500
bitrate_1080p_kbps       = 2000
bitrate_4k_kbps          = 3500
keep_4k                  = false
delete_source            = false
preset_encoder           = "fast"
dolby_vision             = "sdr"
preserve_hd_audio        = false
audio_languages          = ["fre", "eng"]
audio_stereo_kbps        = 192
audio_surround_kbps      = 448
audio_surround_7_1_kbps  = 640
audio_copy_compatible    = true

[serie_basic]
# Séries · 1080p max · medium · DV→HDR10
bitrate_720p_kbps        = 1500
bitrate_1080p_kbps       = 2200
bitrate_4k_kbps          = 5000
keep_4k                  = false
delete_source            = false
preset_encoder           = "medium"
dolby_vision             = "hdr10"
preserve_hd_audio        = false
audio_languages          = ["fre", "eng"]
audio_stereo_kbps        = 192
audio_surround_kbps      = 448
audio_surround_7_1_kbps  = 640
audio_copy_compatible    = true

[serie_hd]
# Séries HD · 1080p max · medium · DV→HDR10
bitrate_720p_kbps        = 1500
bitrate_1080p_kbps       = 2500
bitrate_4k_kbps          = 5000
keep_4k                  = false
delete_source            = false
preset_encoder           = "medium"
dolby_vision             = "hdr10"
preserve_hd_audio        = false
audio_languages          = ["fre", "eng"]
audio_stereo_kbps        = 192
audio_surround_kbps      = 448
audio_surround_7_1_kbps  = 640
audio_copy_compatible    = true

[film_basic]
# Films · 1080p max · medium · DV→SDR
bitrate_720p_kbps        = 2000
bitrate_1080p_kbps       = 3000
bitrate_4k_kbps          = 5000
keep_4k                  = false
delete_source            = false
preset_encoder           = "medium"
dolby_vision             = "sdr"
preserve_hd_audio        = false
audio_languages          = ["fre", "eng"]
audio_stereo_kbps        = 192
audio_surround_kbps      = 448
audio_surround_7_1_kbps  = 640
audio_copy_compatible    = true

[film_hd]
# Films HD · 1080p max · slow · DV→HDR10 · HD audio
bitrate_720p_kbps        = 3000
bitrate_1080p_kbps       = 5000
bitrate_4k_kbps          = 8000
keep_4k                  = false
delete_source            = false
preset_encoder           = "slow"
dolby_vision             = "hdr10"
preserve_hd_audio        = true
audio_languages          = ["fre", "eng"]
audio_stereo_kbps        = 192
audio_surround_kbps      = 448
audio_surround_7_1_kbps  = 640
audio_copy_compatible    = true

[cinema_4k_basic]
# Cinéma 4K · keep_4k · slow · DV→HDR10 · HD audio
bitrate_720p_kbps        = 2000
bitrate_1080p_kbps       = 5000
bitrate_4k_kbps          = 8000
keep_4k                  = true
delete_source            = false
preset_encoder           = "slow"
dolby_vision             = "hdr10"
preserve_hd_audio        = true
audio_languages          = ["fre", "eng"]
audio_stereo_kbps        = 192
audio_surround_kbps      = 448
audio_surround_7_1_kbps  = 640
audio_copy_compatible    = true

[cinema_4k_hd]
# Cinéma 4K · keep_4k · slow · DV→DV copy · HD audio
bitrate_720p_kbps        = 2000
bitrate_1080p_kbps       = 5000
bitrate_4k_kbps          = 12000
keep_4k                  = true
delete_source            = false
preset_encoder           = "slow"
dolby_vision             = "dv"
preserve_hd_audio        = true
audio_languages          = ["fre", "eng"]
audio_stereo_kbps        = 192
audio_surround_kbps      = 448
audio_surround_7_1_kbps  = 640
audio_copy_compatible    = true

[cinema_4k_quality]
# Cinéma 4K · keep_4k · slow · HDR10 qualité libx265 · HD audio
# hdr10_quality="quality" → libx265 CPU + métadonnées HDR10 propres (master_display + max_cll)
bitrate_720p_kbps        = 2000
bitrate_1080p_kbps       = 5000
bitrate_4k_kbps          = 12000
keep_4k                  = true
delete_source            = false
preset_encoder           = "slow"
dolby_vision             = "hdr10"
hdr10_quality            = "quality"
preserve_hd_audio        = true
audio_languages          = ["fre", "eng"]
audio_stereo_kbps        = 192
audio_surround_kbps      = 448
audio_surround_7_1_kbps  = 640
audio_copy_compatible    = true

[basic_delete]
# Conversion + suppression source · fast · DV→SDR
bitrate_720p_kbps        = 1500
bitrate_1080p_kbps       = 2000
bitrate_4k_kbps          = 3500
keep_4k                  = false
delete_source            = true
preset_encoder           = "fast"
dolby_vision             = "sdr"
preserve_hd_audio        = false
audio_languages          = ["fre", "eng"]
audio_stereo_kbps        = 192
audio_surround_kbps      = 448
audio_surround_7_1_kbps  = 640
audio_copy_compatible    = true
```



**Comportement sur erreur de syntaxe :**

```
⚠ profiles.toml illisible (erreur syntaxe ligne 12).
  Chargement du profil [default] intégré.
```



---



## 7. Dolby Vision — `core/dovi.py`



Module wrapper autour de `dovi_tool`. Utilisé en deux phases :

1. **Scan** (`probe_file`) : enrichit chaque `VideoInfo` avec sous-profil, master display, MaxCLL/FALL
2. **Encodage** (`make_x265_hdr_params`) : fournit les paramètres `-x265-params` pour le mode HDR10 quality



### 7.1 API publique

| Fonction | Description |
|----------|-------------|
| `get_path(bin_dir)` | Chemin vers `dovi_tool` (PATH puis `./bin/`) ou None |
| `is_available(bin_dir)` | Bool |
| `probe_file(path, dovi_path, ffmpeg_path)` | Sous-profil DV + master display + MaxCLL depuis un fichier source |
| `extract_hevc_stream(…)` | Extrait le flux HEVC brut Annex-B via ffmpeg |
| `extract_rpu(…)` | Extrait le RPU depuis un .hevc brut |
| `convert_p7_to_p8(…)` | Convertit RPU profil 7 → profil 8 (mode `-m 2`) |
| `rpu_info(…)` | Retourne `{dv_subprofile, master_display, max_cll}` |
| `make_x265_hdr_params(…)` | Construit la liste de tokens `-x265-params` HDR10 |
| `x265_params_string(params)` | Concatène en `key=val:key=val` |



### 7.2 Flux probe (au scan)

```
1. ffmpeg  : extrait 30 s de flux HEVC brut  (input.mkv → temp.hevc)
2. dovi_tool extract-rpu                     (temp.hevc  → temp.rpu)
3. dovi_tool info -f 1                       → sous-profil, master_display, MaxCLL
```

Coût : ~50–150 ms par fichier. Ne lève pas en cas d'échec (retourne dict vide).



### 7.3 Paramètres x265 HDR10

```python
params = [
    "hdr10-opt=1", "repeat-headers=1",
    "colorprim=bt2020", "transfer=smpte2084",
    "colormatrix=bt2020nc", "chromaloc=2",
    "master-display=G(…)B(…)R(…)WP(…)L(…)",   # si disponible
    "max-cll=MaxCLL,MaxFALL",                   # si disponible
]
```



---



## 8. Logique métier — `core/decision.py`



### 8.1 Décision encodage vidéo



| Cas | Condition | Action |
|-----|-----------|--------|
| **CAS 1** | bitrate source ≥ seuil cible | Réencodage HEVC (ou H264 si cible < 1080p) au bitrate cible |
| **CAS 2** | bitrate OK mais résolution trop grande | Redimensionnement HEVC, bitrate original |
| **CAS 3** | bitrate OK, résolution OK, codec non-standard (ni H264 ni HEVC) | Réencodage H264, bitrate et taille conservés |
| **SKIP** | bitrate OK, résolution OK, codec H264 ou HEVC | Aucun traitement |

Le seuil bitrate est calculé sur la **résolution cible** (après `keep_4k`) et non sur la résolution source. Exemple : source 1920×822 → bucket 1080p même si la source est techniquement sous-1080p.

**Force SKIP → encode (browser) :** si un fichier SKIP est sélectionné manuellement pour le run, il est forcé en `ENCODE_HEVC` (ou `ENCODE_H264` si < 1080p) au débit source, sans gonflement.



### 8.2 Bitrates vidéo cibles par résolution



| Résolution | Valeurs disponibles | Note |
|---|---|---|
| **720p** | 1500, 2000k | |
| **1080p** | 2000, 2200, 2500, 3000, 3500, 5000k | |
| **4K** | 3000, 3500, 5000, 8000, 12000k | 8000k recommandé pour `cinema_4k_basic` |



### 8.3 Actions vidéo



| Enum | Description |
|------|-------------|
| `ENCODE_HEVC` | Réencodage HEVC (CAS 1 ou CAS 2 sur source ≥ 1080p) |
| `ENCODE_H264` | Réencodage H264 (CAS 3, ou cible < 1080p, ou forçage manuel) |
| `ENCODE_AV1` | AV1 — **manuel uniquement** (très gourmand CPU/GPU RTX30+) |
| `SKIP` | Aucun traitement |



### 8.4 Gestion Dolby Vision



| Option profil | DV Action | Comportement |
|---|---|---|
| `"hdr10"` | `DVAction.HDR10` | DV → HDR10 (suppression RPU, ré-encodage HEVC) |
| `"dv"` | `DVAction.DV` | DV → DV (copy stream vidéo intégralement, pas de ré-encodage) |
| `"sdr"` | `DVAction.SDR` | DV → SDR (tone map P5, CPU, lent) |
| Aucun DV | `DVAction.NONE` | Sans effet |

> **Vocabulaire :** `"hdr10"` remplace l'ancienne option `"strip"`. `"dv"` remplace `"preserve"`.



**Mode HDR10 quality (`hdr10_quality = "quality"`) :**

Activé par le profil `cinema_4k_quality`. Utilise `libx265` CPU + `-x265-params` avec `master_display` et `max_cll` extraits par `dovi_tool`. La sortie est un HEVC HDR10 avec métadonnées statiques correctes — compatible LG/Sony/Samsung.

Ce mode exige `dovi_tool` dans PATH ou `./bin/`. Sans `dovi_tool`, un avertissement ⚠ s'affiche dans `TracksScreen`.



**Pipeline tone mapping P5 (SDR) :**

```
zscale=t=linear:npl=100,
format=gbrpf32le,
zscale=p=bt709,
tonemap=tonemap=hable:desat=0,
zscale=t=bt709:m=bt709:r=tv,
format=yuv420p
```

Algorithme `hable`. Exécuté CPU, impact performance significatif.



### 8.5 Décision encodage audio



#### Règle de sélection des pistes

```
Pour chaque piste audio :
  1. Index 0                    → toujours conservée (langue originale)
  2. Langue dans audio_languages → conservée
  3. Sinon                      → exclue (sauf sélection manuelle TUI)
```

#### Règle de transcodage par piste conservée

```
Pour chaque piste conservée :
  1. Codec lossless (TrueHD / DTS-HD MA / MLP) ?
       preserve_hd_audio = true  → copy
       preserve_hd_audio = false → appliquer règle canal
  2. Codec compatible (AAC / AC3 / EAC3) ET audio_copy_compatible = true ?
       → copy
  3. Sinon → transcoder selon règle canal
```

#### Codec et bitrate de sortie par configuration de canaux

| Canaux source | Codec sortie | Paramètre bitrate |
|---|---|---|
| Mono (1.0) | AAC | 64k (fixe) |
| Stéréo (2.0) | AAC | `audio_stereo_kbps` |
| Surround 5.1 | AC3 | `audio_surround_kbps` |
| Surround 7.1 | AC3 | `audio_surround_7_1_kbps` |
| TrueHD / DTS-HD MA | copy ou règle surround | selon `preserve_hd_audio` |

> **v0.6 :** `eac3` est maintenant reconnu comme codec copy-compatible au même titre que `aac` et `ac3`.



### 8.6 Sous-titres

- PGS / DVD (image) → conteneur MKV, `-c:s copy`
- SRT / ASS (texte) → conteneur MP4, `-c:s mov_text`
- Sélection par piste possible depuis `TracksScreen` (par défaut : toutes conservées)



### 8.7 Nommage des sorties

- `nom_fichier_[hevc].mp4/.mkv`
- `nom_fichier_[H264].mp4/.mkv`
- `nom_fichier_[av1].mp4/.mkv` (si AV1 manuel)



---



## 9. Abstraction plateforme — `core/platform.py`



| Paramètre | Windows/NVIDIA | Windows/CPU | macOS | Linux/CPU |
|-----------|---------------|-------------|-------|-----------|
| hwaccel | `cuda` | *(absent)* | `videotoolbox` | *(absent)* |
| encoder HEVC | `hevc_nvenc` | `libx265` | `hevc_videotoolbox` | `libx265` |
| encoder H264 | `h264_nvenc` | `libx264` | `h264_videotoolbox` | `libx264` |
| encoder AV1 | `av1_nvenc` | `libaom-av1` | `libaom-av1` | `libaom-av1` |

La détection GPU NVIDIA se fait via `nvidia-smi`. Sans NVIDIA sur Windows, fallback sur CPU.



---



## 10. Encodeur — `core/encoder.py`



### 10.1 Modes d'encodage vidéo

| Mode | Condition | Encodeur | Notes |
|---|---|---|---|
| **DV copy** | `dv_action == DV` | `-c:v copy` | Pas de ré-encodage, pas de hwaccel |
| **HDR10 quality** | `dv_action == HDR10` + `hdr10_quality == "quality"` | `libx265` CPU | Métadonnées HDR10 via `-x265-params`, `pix_fmt yuv420p10le` |
| **SDR tone map** | `dv_action == SDR` | nvenc/libx265 (CPU) | Filtre `zscale+tonemap`, pas de hwaccel |
| **Standard** | Tous autres cas | nvenc / libx265 / libx264 / av1_nvenc | hwaccel activé si disponible |



### 10.2 Pause / Reprise

- Windows : `NtSuspendProcess` / `NtResumeProcess` via ctypes
- POSIX : `SIGSTOP` / `SIGCONT`



### 10.3 Progression

Parsing de la ligne `stderr` ffmpeg :

```
frame= N fps= N q=N.N size= NkB time=HH:MM:SS.ss bitrate=N.Nkbits/s speed=Nx
```

Retourne un `ProgressInfo` (frame, fps, elapsed, bitrate, speed, percent). Percent = -1.0 si durée inconnue.



### 10.4 Garde-fous

- Chemin de sortie identique à la source : `ValueError` levée avant lancement



---



## 11. Métadonnées — `core/meta.py`



### 11.1 Extraction titre depuis le nom de fichier

`parse_title(path)` tronque le nom au premier marqueur de format (résolution, année, source, épisode…) et retourne `(titre, année)`.

```python
parse_title(Path("The.Batman.2022.2160p.BluRay.mkv"))
# → ("The Batman", 2022)
```



### 11.2 IMDB — deux modes

| Mode | Condition | Données retournées |
|---|---|---|
| **OMDb API** | `omdb_api_key` renseigné dans `config.toml` | Note, synopsis, genres, réalisateurs, casting |
| **Suggestions API** | Pas de clé (sans login, sans scraping) | Titre, année, casting partiel — pas de note ni synopsis |

L'API suggestions IMDB est l'endpoint JSON (`v2.sg.media-imdb.com/suggests/`) — non officielle mais stable et sans clé.



### 11.3 AlloCiné — scraping

Deux appels HTTP :

1. Autocomplete JSON → `entity_id` + `entity_type`
2. Fiche HTML → JSON-LD → note, synopsis, genres, réalisateurs, casting

Note sur 5.0.



### 11.4 Modèle `MovieMeta`

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



## 12. Interface TUI — `tui/`



Framework : **Textual** (Python)

Widget global : **`TwoLineFooter`** — footer 2 lignes configurable remplaçant le Footer Textual natif (1 ligne). Ligne 1 : navigation. Ligne 2 : actions.



---



### 12.1 Écran Browser — navigation fichiers



```
┌─ IRIS ENCODE ────────────────────────────────── 14:22 ─┐
│ D:\Videos    2/4 sélectionné(s)  ·  Col : Résol. [</>] │
│                                                         │
│ [F4] 🎬 SERIE_BASIC 🎬  • 1080p 2200k  ·  4K→1080p    │
│      HD audio non  (2ème ligne de la barre profil)      │
│ ⏳ Analyse en cours… 2 / 4                              │
├─ ──┬─ Fichier ────────────┬─ Taille ─┬─ Résol. ─┬─ Durée ─┬─ Débit ─┬─ Codec ─┬─ Dolby V. ─┬─ Décision ─┬─ Audio ──────┤
│    │ 📁 Films/            │          │          │         │         │         │             │            │              │
│[x] │ 🎬 film1.mkv         │   8,4 Go │ 3840x2160│ 2:05:12 │ 25000k  │  hevc   │  DV:P8.1   │  → HEVC    │  TrueHD 7.1  │
│[ ] │ 🎬 film2.mp4         │   1,1 Go │  720x480 │ 1:32:00 │   900k  │  h264   │  —         │  ← SKIP    │  AAC 2.0     │
│[x] │ 🎬 film3.avi         │   2,3 Go │ 1280x720 │ 0:52:00 │  3200k  │  vp9    │  —         │  → H264    │  AC3 5.1     │
│ 💾 D:\                   │          │          │         │         │         │             │            │              │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Space Sélect   a Tout   n Aucun   Enter Détails fichier   Back Remonter   PgUp Haut   PgDn Bas   Home Début   End Fin    │
│ F1 Dry-run   F2 Run   F3 Récursif   F4 Profil   F5 Config   F7 AlloCiné   F8 IMDB   Sh+Tab Col   < Rétrécir   > Élargir   F10 Quitter │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```



#### Navigation

- Déplacement ligne : ↑ / ↓
- Déplacement page : `[PageUp]` / `[PageDown]`
- Saut début / fin : `[Home]` / `[End]`
- Sélection unitaire : `[Espace]`
- Sélection globale : `[A]` tout / `[N]` aucun
- Entrer dans un sous-dossier : `[↵ Entrée]`
- Remonter au dossier parent : `[Back]`
- Entrer sur un fichier : `[↵ Entrée]` → ouvre `TracksScreen`
- Actions : `[F1]` Dry-run · `[F2]` Run · `[F3]` Run récursif · `[F4]` Profil · `[F5]` Config · `[F7]` AlloCiné · `[F8]` IMDB · `[F10]` Quitter



#### Démarrage virtuel

L'application démarre en **mode virtuel** (`start_virtual=True`) : la première vue affiche les lecteurs/volumes disponibles (icône 💾), pas un chemin fixe. L'utilisateur navigue ensuite dans le lecteur choisi.



#### Colonnes du browser

| Colonne | Clé config | Contenu |
|---------|-----------|---------|
| *(check)* | — | `[x]` / `[ ]` |
| Fichier | `fichier` | 🎬 nom du fichier (tronqué avec `…`) |
| Taille | `taille` | taille du fichier source |
| Résolution | `resolution` | `WxH` |
| Durée | `duree` | `H:MM:SS` |
| Débit | `debit` | `NNNNk` |
| Codec | `codec` | codec vidéo |
| Dolby V. | `dolby_vision` | `DV:P8.1` ou `—` |
| Décision | `decision` | `→ HEVC → HDR10` (coloré) |
| Audio | `audio` | résumé pistes conservées |

Toutes les colonnes sont redimensionnables via `[Tab]`/`[Sh+Tab]` (sélection) + `[<]`/`[>]` (resize). Largeurs persistées dans `config.toml`.

Code couleur décision : HEVC → magenta · H264 → cyan · SDR → jaune · SKIP → gris dim.



#### Barre de profil actif (2 lignes)

Ligne fixe sous la barre de statut. Affiche en permanence :

**Ligne 1 :** `[F4]` + `🎬 NOM_PROFIL 🎬` · `1080p Nk` · `4K→1080p` ou `4K Nk` (vert) · `DV hdr10/dv/sdr` (coloré) · `preset medium/slow/fast`

**Ligne 2 :** `HD audio oui/non` · `⚠ SUPPRESSION` si `delete_source = true`

Couleurs DV : `hdr10` → jaune · `dv` → vert · `sdr` → bold dark_orange.

`[F4]` ouvre `ValuePickerScreen` (modal de sélection de profil).



#### Sélection de profil — ValuePickerScreen

Chaque ligne affiche le nom du profil aligné + caractéristiques :

```
   serie_basic        2200k  ·  4K→1080p    ·  DV hdr10    ·  medium
   serie_hd           2500k  ·  4K→1080p    ·  DV hdr10    ·  medium
   film_basic         3000k  ·  4K→1080p    ·  DV sdr      ·  medium
   film_hd            5000k  ·  4K→1080p    ·  DV hdr10    ·  slow    ·  HD audio
→  cinema_4k_basic    5000k  ·  4K 8000k ✓  ·  DV hdr10    ·  slow    ·  HD audio
   cinema_4k_hd       5000k  ·  4K 12000k ✓ ·  DV dv       ·  slow    ·  HD audio
   cinema_4k_quality  5000k  ·  4K 12000k ✓ ·  DV hdr10    ·  slow    ·  HD audio
   basic_delete       2000k  ·  4K→1080p    ·  DV sdr      ·  fast    ·  ⚠ suppr.
```

Largeur calculée automatiquement sur le contenu (minimum 40 caractères). Marqueur `→` sur l'entrée active.



#### Scan progressif

Un worker thread scanne les fichiers un par un. La notice `#scan-notice` affiche :

```
⏳ Analyse en cours… 3 / 12
```

Une fois terminée, la notice affiche le chemin du fichier survolé.



#### Barre de statut

```
D:\Videos\Films    2/4 sélectionné(s)  ·  Col : Résol. [</>]
```



#### Run récursif (F3)

Disponible uniquement si le curseur est sur un **dossier**. Ouvre `RecursiveConfirmModal` :

- Affiche le répertoire cible et le profil actif
- `[Enter]` : lance un scan récursif illimité (`scan_directory_recursive`) + dry-run sur tous les fichiers à encoder (SKIP exclus)
- `[Esc]` : annuler

Aucune sélection de pistes manuelle dans ce mode — décisions automatiques du profil.



#### Métadonnées (F7/F8)

Disponible uniquement si le curseur est sur un **fichier**.

- `[F7]` → `MetaPopup` source AlloCiné
- `[F8]` → `MetaPopup` source IMDB

Le titre est extrait du nom de fichier via `core/meta.parse_title()`. La requête s'effectue dans un thread worker. Affichage : type, année, note, genres, réalisateurs, casting, synopsis, URL.



---



### 12.2 Écran Tracks — sélection pistes + édition décision vidéo



Un seul `DataTable` avec trois sections :

```
┌─ Pistes — film1.mkv    Profil: [cinema_4k_hd]  · Audio: 2/3 · Sous-titres: 1/1 ──┐
│                                                                                     │
│ ── VIDÉO ─────────────────────────────────────────────────────────────────────────  │
│ ✎ HEVC  0:v:0    hevc    3840x2160  —   3840x2160 25000k DV:P8.1  ◄→ HEVC◄ · ◄12000 kbps◄ · … │
│                                                                                     │
│ ── AUDIO ─────────────────────────────────────────────────────────────────────────  │
│ [x]  0:a:0 ⚑   truehd   7.1   fre   défaut            → copy                      │
│ [x]  0:a:1      ac3      5.1   fre   sélectionné       → copy                      │
│ [ ]  0:a:2      dts      5.1   deu   exclu manuellement —                          │
│                                                                                     │
│ ── SOUS-TITRES ────────────────────────────────────────────────────────────────────  │
│ [x]  0:s:0   hdmv_pgs   image  fre   défaut            → MKV copy                  │
│ [ ]  0:s:1   hdmv_pgs   image  deu   exclu manuellement —                          │
│                                                                                     │
│ [ ✓ ] Valider la sélection                                                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│ Space Sélect   Enter Valider   F1 Dry-run   F2 Run   F4 Profil   F6 Codec   F7 Débit   F8 Suppr./Garder │
│ F10 Quitter   Back Retour   Sh+Tab Col préc.   Tab Col suiv.   < Rétrécir   > Élargir │
└─────────────────────────────────────────────────────────────────────────────────────┘
```



#### Ligne VIDÉO — édition inline

Champs éditables : **action** (codec), **bitrate**, **DV**, **original** (delete_source).

| Raccourci | Zone vidéo | Effet |
|-----------|-----------|-------|
| `[←]` / `[→]` | Oui | Cycle entre les champs éditables (◄ actif ►) |
| `[+]` / `[-]` | Oui | Change la valeur du champ actif |
| `[↵ Entrée]` | Oui | Ouvre `ValuePickerScreen` pour le champ actif |
| `[F6]` | — | Picker codec (action) |
| `[F7]` | — | Picker débit |
| `[F8]` | — | Toggle suppression/conservation source |

Cycles disponibles :

| Champ | Valeurs |
|-------|---------|
| action | ENCODE_HEVC · ENCODE_H264 · ENCODE_AV1 · SKIP |
| bitrate | 500, 800, 1000, 1500, 2000, 2200, 2500, 3000, 3500, 5000, 8000, 12000k |
| bitrate (AV1) | 300, 500, 800, 1000, 1500, 2000, 2500, 3000, 4000, 6000k |
| dv | HDR10 · DV · SDR |
| orig | Profil (suivre) · Garder · Supprimer |

La colonne **Source** affiche le sous-profil DV si connu (ex: `DV:P8.1` vs `DV:P8`). Avertissement ⚠ si mode HDR10 demandé mais `dovi_tool` absent.

Un indicateur `✎` dans la colonne check signale qu'un override est actif.



#### Pistes AUDIO

- `[Espace]` : toggle sélection (piste 0 verrouillée — ⚑)
- Décision affichée par piste : `→ copy` / `→ aac 192k` / `—` (exclue)

#### Pistes SOUS-TITRES

- `[Espace]` : toggle sélection
- Type affiché : `image` (PGS/DVD) → `→ MKV copy` / `texte` (SRT/ASS) → `→ MP4 copy`
- Sélection par défaut : toutes les pistes



#### Changement de profil (F4)

Ouvre `ValuePickerScreen` liste des profils. Le changement recalcule immédiatement la décision vidéo et audio du fichier courant.



#### Lancement direct

`[F1]` Dry-run · `[F2]` Run — ferme TracksScreen et ouvre directement l'écran correspondant.



#### Retour

`[Back]` / `[Esc]` : retour browser (annulation). `[↵ Entrée]` sur ligne Valider : retour avec validation. Les overrides sont appliqués côté browser.



#### Colonnes redimensionnables

`Codec`, `Format` (layout canaux / type sous-titre), `Source`. Persistées dans `[tui.tracks.columns]`.



---



### 12.3 Écran Dry-run



Prévisualise les décisions pour tous les fichiers sélectionnés, sans écriture disque.

**Colonnes :** Fichier · Taille · Estim. (Δ%) · Action · Conteneur · DV · Débit cible · Résolution · Audio

La colonne **Estim.** affiche la taille de sortie estimée (vidéo + audio) et le delta en % par rapport à la source (vert si réduction, orange si gonflement).

**Barre de bilan :**

```
À encoder : HEVC 3  ·  H264 1  ·  SKIP 2
·  Source : 12,4 Go  →  Estimé : 3,2 Go (−74%)
```

`[F2]` ou `[↵ Entrée]` : passe à l'écran Run (SKIP exclus).

Colonnes redimensionnables (9 colonnes). Persistées dans `[tui.dryrun.columns]`.



---



### 12.4 Écran Run



```
┌─ Encodage — 5 fichiers · Profil : cinema_4k_basic ──────────── Global : 42% ─┐
│                                                                                │
│  ✓  film1.mkv    HEVC 8000k → HDR10      ✓ SUCCÈS                            │
│     ████████████████████████████████████                                       │
│  ▶  film3.avi    H264 3200k               38%                                 │
│     █████████░░░░░░░░░░░░░░░                                                   │
│  ○  film4.mkv    HEVC 12000k → DV        en attente                           │
│  ○  ep01.mkv     HEVC 5000k              en attente                           │
│                                                                                │
│  [▶ Démarrer] / [⏸ Pause]   ████████████░░░░░░░░░░░░░░░░░  42%               │
├────────────────────────────────────────────────────────────────────────────────┤
│ $ ffmpeg -hwaccel cuda -i "film3.avi" -c:v h264_nvenc …                       │
│ frame= 1094 fps= 89 q=27.0 size= 36864kB time=00:00:45.58                     │
│   bitrate=6627.4kbits/s speed=3.71x                                            │
└────────────────────────────────────────────────────────────────────────────────┘
```



#### Liste de progression

- Une ligne par fichier : icône état (○ / ▶ / ✓ / ✗) + nom + action + pourcentage
- Barre de progression individuelle sous le fichier actif ou terminé
- Barre de progression globale en pied de liste



#### Zone commande ffmpeg (bas d'écran, séparée par une bordure)

- **Ligne commande** : commande `ffmpeg` complète du fichier en cours d'encodage
- **Ligne de retour** : dernière ligne stdout capturée depuis ffmpeg (mise à jour live, non scrollable)
- En cas d'erreur : ligne colorée dark_orange avec le message d'erreur ffmpeg



#### Comportement

- `[▶ Démarrer]` : lance l'encodage séquentiel des fichiers sélectionnés
- `[⏸ Pause]` : suspend le processus ffmpeg en cours (multiplateforme)
- `[↩ Recommencer]` (après fin) : remet à zéro l'état et la liste
- Suppression source après succès : selon `delete_source` du profil (ou override par fichier)
- En cas d'erreur ffmpeg : fichier marqué ✗, encodage des suivants continue, source conservée



---



### 12.5 Écran Config — gestion des profils



Structure et comportement identiques à la v0.5.

Profils **builtin** (9) : éditables, non supprimables.

Profils **user** (créés via l'interface) : éditables et supprimables.

Le formulaire inline `ProfileForm` expose tous les champs incluant le nouveau champ `hdr10_quality` (case à cocher ou select) pour les profils `cinema_4k_quality`.



---



### 12.6 Modal de confirmation quitter — `QuitConfirmScreen`

Déclenchée par `[F10]` ou `[Ctrl+C]` depuis n'importe quel écran.

```
┌─────────────────────────────────────┐
│  ⚠  Quitter IRIS ENCODE ?           │
│  L'encodage en cours sera interrompu│
│                                     │
│  [✓ Confirmer]   [✗ Annuler]        │
└─────────────────────────────────────┘
```

Focus par défaut sur `[✗ Annuler]`. `[←]` / `[→]` : focus entre les boutons. `[Enter]` : valider le bouton actif. `[Esc]` : annuler.



---



## 13. Scanner enrichi — `core/scanner.py`



### 13.1 `VideoInfo` — champs v0.6

```python
@dataclass
class VideoInfo:
    path:                 Path
    width:                int
    height:               int
    bitrate:              int          # bps
    codec:                str
    duration:             float        # secondes
    frame_count:          int
    dv_profile:           int | None   # entier du profil (5, 7, 8…)
    audio_tracks:         list[AudioTrack]
    subtitle_tracks:      list[SubtitleTrack]
    # Enrichissement DV (dovi_tool, optionnel)
    dv_subprofile:        str | None         # "5", "7.06", "8.1", "8.4"…
    hdr10_master_display: str | None         # "G(…)B(…)R(…)WP(…)L(…)"
    hdr10_max_cll:        tuple[int,int]|None  # (MaxCLL, MaxFALL)
```



### 13.2 Scan récursif

`scan_directory_recursive(root)` — scanne tous les fichiers vidéo sous `root` (tous niveaux), triés par chemin complet. Mêmes filtres que `scan_directory` : extensions supportées, pas d'encodés (`_[hevc]`/`_[H264]`).



### 13.3 Enrichissement DV au scan

Si `dovi_tool` est disponible (câblé dans `app.py` via `scanner.set_dovi_path()`), chaque fichier DV détecté est enrichi avec `dv_subprofile`, `hdr10_master_display`, `hdr10_max_cll` via `dovi.probe_file()`.



### 13.4 Navigation virtuelle

`FileNavigator` (dans `tui/widgets/file_tree.py`) supporte un mode `start_virtual=True` : la vue initiale liste les volumes/lecteurs disponibles (icône 💾, chemin complet affiché). Naviguer dans un volume entre en mode normal.



---



## 14. Logging — `app.py` + `logger/logger.py`



### 14.1 Logging Python standard (opérationnel)

Configuré dans `app.py` à chaque lancement :

```python
log_path = Path.home() / ".iris_encode" / "iris_encode.log"
logging.basicConfig(level=logging.WARNING, …)
```

Les modules `core/` logguent via `logging.getLogger("iris_encode.*")`. Warnings et erreurs sont persistés silencieusement.



### 14.2 Logger applicatif (inerte)

Module `logger/logger.py` — API définie, aucun backend branché.

```python
logger.info("scan terminé", files=12)
logger.error("encodage échoué", file="video.mkv")
logger.session_start(profile="default", path="D:/Videos")
```

Backend prévu (fichier JSON ou SQLite) dans une release ultérieure.



---



## 15. Portabilité



- Tout `pathlib.Path`, aucune string de chemin en dur
- `./bin/` pour ffmpeg/ffprobe/dovi_tool embarqués
- `config.toml` et `profiles.toml` dans le dossier application
- Aucune dépendance au registre Windows ni à `%APPDATA%`
- Fonctionne depuis une clé USB

**Future release :** Python embarqué (embeddable package) pour zéro prérequis système.



---



## 16. Dépendances Python



```
textual        ← TUI
rich           ← affichage console
tomli-w        ← écriture TOML (lecture native Python 3.11+)
requests       ← téléchargement ffmpeg + API métadonnées
beautifulsoup4 ← scraping AlloCiné (core/meta.py)
```



---



## 17. Ordre de développement



```
1.  core/platform.py
2.  core/preflight.py
3.  core/config.py
4.  core/profiles.py
5.  core/scanner.py               ← pistes audio/sous-titres + enrichissement DV
6.  core/dovi.py                  ← probe_file, RPU, x265-params HDR10
7.  core/decision.py              ← 4 cas + audio + AV1 + HDR10 quality
8.  core/encoder.py               ← AV1, HDR10 quality, suspend/resume
9.  core/meta.py                  ← IMDB (OMDb + suggestions) + AlloCiné
10. tui/widgets/footer.py         ← TwoLineFooter
11. tui/widgets/file_tree.py      ← FileNavigator (mode virtuel)
12. tui/widgets/profile_form.py   ← ProfileForm
13. tui/screens/value_picker.py   ← ValuePickerScreen
14. tui/screens/quit.py           ← QuitConfirmScreen
15. tui/screens/browser.py        ← DataTable + colonnes + F3/F7/F8
16. tui/screens/tracks.py         ← VIDÉO + AUDIO + SOUS-TITRES
17. tui/screens/dryrun.py         ← estimation taille + colonnes
18. tui/screens/run.py            ← progress + pause
19. tui/screens/config.py         ← CRUD profils
20. tui/screens/meta_popup.py     ← popup IMDB/AlloCiné
21. tui/screens/recursive_confirm.py
22. tui/app.py
23. main.py
24. launch.bat
```



---



## 18. Hors scope v0.6



- Logs persistants applicatifs (architecture en place, backend non branché)
- Python embarqué
- Interface de mise à jour des sources ffmpeg
- File de traitement multi-dossiers (hors mode récursif)
- Gestion des commentary tracks par heuristique (titre de piste)
- Widget multi-langue par badges pour `audio_languages` (champ texte libre)
- Sous-titres externes (.srt hors MKV/MP4) — scan ne les détecte pas
- Timeout ou concurrence sur le mode récursif



---



## 19. Changelog



| Version | Date | Modifications |
|---|---|---|
| 0.1 | 2026-05-12 | Document initial |
| 0.2 | 2026-05-12 | Dolby Vision (strip/preserve/sdr), bitrates vidéo par résolution, dovi_tool dans preflight |
| 0.3 | 2026-05-12 | Politique audio complète : sélection pistes (index 0 + filtre langue), transcodage (AAC stéréo / AC3 surround / copy lossless), profils audio, écran Tracks |
| 0.4 | 2026-05-12 | Browser : colonnes redimensionnables via DataTable · Navigation : [←] remonter dossier parent · Run : zone commande ffmpeg + ligne de retour live · Config : CRUD profils complet — ProfileForm, protection builtin |
| 0.5 | 2026-05-13 | Browser : correction scroll DataTable (cursor_type="row", show_cursor=True, CSS height:1fr) · [PageUp]/[PageDown]/[Home]/[End] · Profils : refonte builtins (6 profils) · Barre de statut : chemin absolu + ligne N/N |
| 0.6 | 2026-05-14 | **core/dovi.py** : module wrapper dovi_tool (probe, RPU, x265-params) · **core/meta.py** : IMDB (OMDb + suggestions) + AlloCiné (scraping) · **Scanner** : enrichissement DV au scan (dv_subprofile, hdr10_master_display, hdr10_max_cll), scan_directory_recursive, eac3 copy-compat · **Profils** : refonte en 9 builtins (serie_anime, film_basic, film_hd, cinema_4k_quality ajoutés ; archivage supprimé) ; dolby_vision : strip→hdr10, preserve→dv · **Decision** : ENCODE_AV1, DVAction renommés (HDR10/DV/SDR), seuil bitrate basé sur résolution cible, force SKIP→encode · **Encoder** : mode AV1, mode HDR10 quality (libx265 + x265-params), suspend/resume multiplateforme · **Platform** : encoder_av1, macOS + Linux CPU · **Browser** : colonnes Taille+Durée, start_virtual, F3 récursif, F7 AlloCiné, F8 IMDB, Enter sur fichier → TracksScreen, TwoLineFooter, profil bar 2 lignes · **TracksScreen** : refonte complète — 3 sections (VIDÉO+AUDIO+SOUS-TITRES), édition vidéo inline (action/bitrate/DV/orig), F4 change profil, F6/F7 pickers, F8 toggle delete, sous-titres sélectionnables, colonnes resize · **DryrunScreen** : colonnes Taille+Estim.(Δ%)+DV+Résolution, bilan total source/estimé · **config.toml** : [meta] omdb_api_key, [tui.dryrun.columns], [tui.tracks.columns] · **Logging** : ~/.iris_encode/iris_encode.log · **QuitConfirmScreen** : modal confirmation F10/Ctrl+C |
