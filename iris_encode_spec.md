# IRIS ENCODE — Spécification Fonctionnelle

**Version** : 0.8.1.1 — document de référence courant
**Date** : 2026-08-26
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
├── launch.bat                    ← vérification Python, point d'entrée Windows
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
│   ├── test_deps.py              ← cohérence des listes de dépendances
│   ├── test_dovi.py
│   ├── test_muxer.py
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

- Vérifie la présence de Python 3.11+ dans le PATH
- Si absent : message explicite + redirection vers python.org
- Si présent : délègue à `main.py` en passant les arguments (`%*`)
- Utilise `%~dp0` pour garantir la portabilité du chemin
- Lit la version depuis `version.py` (aucune version en dur)

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
Piloté par `[updates] check_on_startup`.

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
# Moyenne mobile de vitesse relevée à chaque passe — alimente « Temps estim. »
hevc = 7.49
h264 = 21.43

[tui.browser.columns]
fichier = 62
taille = 30
resolution = 10
duree = 6
debit = 6
codec = 6
dolby_vision = 8
decision = 8
estim = 16
temps_estim = 14
audio = 34

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

Format TOML, éditable à la main. Les profils builtin sont toujours présents
(non supprimables, mais éditables).

Le champ `dolby_vision` accepte : `"hdr10"` (DV → HDR10), `"dv"` (DV → DV copy),
`"sdr"` (DV → SDR tone map).

**Profils builtin (9)** : `serie_anime`, `serie_basic`, `serie_hd`, `film_basic`,
`film_hd`, `cinema_4k_basic`, `cinema_4k_hd`, `cinema_4k_quality`, `basic_delete`.

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

### 6.2 Vue d'ensemble des builtins

| Profil | 1080p | 4K | Preset | DV | HD audio | Source |
|---|---|---|---|---|---|---|
| `serie_anime` | 2000k | →1080p | fast | sdr | non | gardée |
| `serie_basic` | 2200k | →1080p | medium | hdr10 | non | gardée |
| `serie_hd` | 2500k | →1080p | medium | hdr10 | non | gardée |
| `film_basic` | 3000k | →1080p | medium | sdr | non | gardée |
| `film_hd` | 5000k | →1080p | slow | hdr10 | oui | gardée |
| `cinema_4k_basic` | 5000k | 8000k | slow | hdr10 | oui | gardée |
| `cinema_4k_hd` | 5000k | 12000k | slow | dv | oui | gardée |
| `cinema_4k_quality` | 5000k | 12000k | slow | hdr10 *quality* | oui | gardée |
| `basic_delete` | 2000k | →1080p | fast | sdr | non | **supprimée** |

**Comportement sur erreur de syntaxe :**

```
⚠ profiles.toml illisible (erreur syntaxe ligne 12).
  Chargement du profil [default] intégré.
```

---

## 7. Dolby Vision — `core/dovi.py`

Module wrapper autour de `dovi_tool`, utilisé en deux phases :

1. **Scan** (`probe_file`) : enrichit chaque `VideoInfo` avec sous-profil, master
   display, MaxCLL/FALL
2. **Encodage** (`make_x265_hdr_params`) : fournit les `-x265-params` du mode HDR10 quality

### 7.1 API publique

| Fonction | Description |
|---|---|
| `get_path(bin_dir)` | Chemin vers `dovi_tool` (PATH puis `./bin/`) ou None |
| `is_available(bin_dir)` | Bool |
| `probe_file(path, dovi_path, ffmpeg_path)` | Sous-profil DV + master display + MaxCLL |
| `extract_hevc_stream(…)` | Extrait le flux HEVC brut Annex-B via ffmpeg |
| `extract_rpu(…)` | Extrait le RPU depuis un `.hevc` brut |
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

### 7.3 Paramètres x265 HDR10

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
| **CAS 3** | bitrate OK, résolution OK, codec non-standard | Réencodage H264, bitrate et taille conservés |
| **SKIP** | bitrate OK, résolution OK, codec H264 ou HEVC | Aucun traitement |

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
| `SKIP` | Aucun traitement |

### 8.4 Gestion Dolby Vision

| Option profil | DV Action | Comportement |
|---|---|---|
| `"hdr10"` | `DVAction.HDR10` | DV → HDR10 (suppression RPU, réencodage HEVC) |
| `"dv"` | `DVAction.DV` | DV → DV (copy du flux vidéo, pas de réencodage) |
| `"sdr"` | `DVAction.SDR` | DV → SDR (tone map P5, CPU, lent) |
| Aucun DV | `DVAction.NONE` | Sans effet |

**Mode HDR10 quality (`hdr10_quality = "quality"`)** — activé par `cinema_4k_quality`.
Utilise `libx265` CPU + `-x265-params` avec `master_display` et `max_cll` extraits par
`dovi_tool`. Sortie HEVC HDR10 à métadonnées statiques correctes, compatible LG/Sony/
Samsung. Exige `dovi_tool` ; sans lui, un ⚠ s'affiche dans `TracksScreen`.

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
| Surround 7.1 | AC3 | `audio_surround_7_1_kbps` |
| TrueHD / DTS-HD MA | copy ou règle surround | selon `preserve_hd_audio` |

### 8.6 Sous-titres

- PGS / DVD (image) → conteneur MKV, `-c:s copy`
- SRT / ASS (texte) → conteneur MP4, `-c:s mov_text`
- Sélection par piste depuis `TracksScreen` (par défaut : toutes conservées)

**Conteneur de sortie** — `output_container` suit les pistes réellement conservées :
écarter les sous-titres image libère le MP4 ; `mov_text` n'est jamais proposé en
Matroska. La présence d'au moins une piste externe force le `.mkv` (§ 9).

### 8.7 Nommage des sorties

| Opération | Sortie |
|---|---|
| Réencodage HEVC | `nom_[hevc].mp4` / `.mkv` |
| Réencodage H264 | `nom_[H264].mp4` / `.mkv` |
| Réencodage AV1 | `nom_[av1].mp4` / `.mkv` |
| Remux mkvmerge | `nom_[mux].mkv` |
| Extrait de contrôle | `nom_[extrait].mkv` |

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
| `identify(path)` | Pistes du fichier via `mkvmerge -J` → `list[IdentifiedTrack]` |
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
| 8 | **Dolby Vision et remux — non vérifié.** mkvmerge sait porter le RPU HEVC (`dvcC`/`dvvC`), mais le comportement face au pipeline `core/dovi.py` n'est pas testé. | À valider sur un fichier DV réel avant de s'y fier. |

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

Vérifié sur un épisode réel — la piste produite mesure **+0 ms, confiance 0.72, trois
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

Le surcoût — une écriture complète du film — n'est payé que dans ce cas. Sans mkvmerge,
l'opération est refusée en amont plutôt que d'échouer en cours d'encodage.

### 12.1 Modes d'encodage vidéo

| Mode | Condition | Encodeur | Notes |
|---|---|---|---|
| **DV copy** | `dv_action == DV` | `-c:v copy` | Pas de réencodage, pas de hwaccel |
| **HDR10 quality** | `dv_action == HDR10` + `hdr10_quality == "quality"` | `libx265` CPU | Métadonnées via `-x265-params`, `pix_fmt yuv420p10le` |
| **SDR tone map** | `dv_action == SDR` | nvenc / libx265 (CPU) | Filtre `zscale+tonemap`, pas de hwaccel |
| **Standard** | Tous autres cas | nvenc / libx265 / libx264 / av1_nvenc | hwaccel si disponible |

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
mobile de `[stats.encode_speed]`, qui nourrit la colonne « Temps estim. ».

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

- **`TwoLineFooter`** — footer 2 lignes remplaçant le Footer natif. Ligne 1 : navigation.
  Ligne 2 : actions. `F10 Quitter` toujours en dernier.
- **Touches retour normalisées** : `Backspace` / `Esc` sur tous les écrans.
- **`ConfirmModal`** (`tui/screens/confirm.py`) — toute confirmation passe par elle.
  Bordure `$warning` si destructif, `←/→` déplacent le focus, `↵` active le bouton
  focalisé (jamais de validation aveugle), `Esc`/`⌫` annulent.
- **Pas de `bold red`** : les alertes utilisent `bold dark_orange`.
- Les colonnes des tables sont redimensionnables (`Tab`/`Sh+Tab` pour choisir,
  `<`/`>` pour ajuster), largeurs persistées dans `config.toml`.

### 14.1 Écran Browser — navigation fichiers

```
┌─ IRIS ENCODE ────────────────────────────────── 14:22 ─┐
│ D:\Videos    2/4 sélectionné(s)  ·  Col : Résol. [</>] │
│                                                         │
│ [F4] 🎬 SERIE_BASIC 🎬  • 1080p 2200k  ·  4K→1080p     │
│      HD audio non                                       │
│ ⏳ Analyse en cours… 2 / 4                              │
├─ ──┬─ Fichier ──────┬─ Taille ─┬─ Résol. ──┬─ Durée ─┬─ Débit ─┬─ Codec ─┬─ Dolby V. ─┬─ Décision ─┬─ Estim. (Δ%) ─┬─ Temps estim. ─┬─ Audio ─────┤
│    │ 📁 Films/      │          │           │         │         │         │            │            │               │                │             │
│[x] │ 🎬 film1.mkv   │   8,4 Go │ 3840x2160 │ 2:05:12 │ 25000k  │  hevc   │  DV:P8.1   │  → HEVC    │ 2,1 Go (−75%) │     0:38:12    │ TrueHD 7.1  │
│[ ] │ 🎬 film2.mp4   │   1,1 Go │  720x480  │ 1:32:00 │   900k  │  h264   │  —         │  ← SKIP    │       —       │        —       │ AAC 2.0     │
│[x] │ 🎬 film3.avi   │   2,3 Go │ 1280x720  │ 0:52:00 │  3200k  │  vp9    │  —         │  → H264    │ 1,2 Go (−48%) │     0:04:51    │ AC3 5.1     │
├────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Space Sélect  a Tout  n Aucun  Enter Ouvrir  v Visualiser  Ctrl+D Supprimer  Back Remonter  Home Début  End Fin  PgUp/PgDn                        │
│ F1 Dry-run  F2 Run  F3 Récursif  F4 Profil  F5 Gérer profils  F7 AlloCiné  F8 IMDB  Sh+Tab/Tab Col  < Rétrécir  > Élargir  F10 Quitter            │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Touches

| Touche | Cible | Action |
|---|---|---|
| `↑` `↓` `PgUp` `PgDn` `Home` `End` | — | Navigation |
| `Espace` | fichier | Sélection unitaire |
| `A` / `N` | — | Tout / aucun |
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
| Temps estim. | `temps_estim` | durée d'encodage estimée |
| Audio | `audio` | résumé des pistes conservées |

Code couleur décision : HEVC → magenta · H264 → cyan · SDR → jaune · SKIP → gris dim.
Delta d'estimation : vert si réduction, `dark_orange` si gonflement.

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

| Touche | Action |
|---|---|
| `←` / `→` | Champ précédent / suivant |
| `+` / `-` | ±100 ms sur le champ décalage |
| `Shift+↑` / `Shift+↓` | ±1 s |
| `↵` | Ouvre la liste des valeurs du champ courant |
| `M` | **Mesure automatique** (§ 10) |
| `A` | Applique le candidat mesuré |
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

Profils **builtin** (9) : éditables, non supprimables (message explicite si tentative).
Profils **user** : éditables et supprimables (`D` / `Suppr`, avec confirmation).

Le formulaire `ProfileForm` expose tous les champs, `hdr10_quality` compris.

### 14.9 Sélection de profil — `ProfilePickerScreen`

Vraie table : Profil · 1080p · 4K · DV · Preset · HD audio · Source. Profil actif marqué
`✓`, valeurs DV colorées, `⚠ suppr.` sur les profils qui suppriment la source. Le
callback renvoie l'**id** du profil (plus robuste qu'un index). Utilisé par Browser (F4)
et TracksScreen (F4).

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
des fichiers déjà encodés (`_[hevc]`, `_[H264]`, `_[mux]`…).

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

`tests/test_deps.py` vérifie que les listes de `main.py` et `launch.bat` couvrent
`requirements.txt`.

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
| `tests/test_deps.py` | Cohérence des listes de dépendances |
| `tests/test_dovi.py` | Wrapper dovi_tool |
| `tests/test_muxer.py` | Génération des commandes mkvmerge, parsing `--gui-mode` |
| `tests/test_preview.py` | Construction des commandes mpv |
| `tests/test_sync.py` | Mesure de décalage sur paires connues |
| `tests/test_updates.py` | Vérification de fraîcheur des outils |

```bash
python tests/smoke_tui.py     # headless, encode réellement de petits clips
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
