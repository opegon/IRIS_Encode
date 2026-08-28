# IRIS ENCODE — Spécification Fonctionnelle

**Version** : 0.8.2.10 — document de référence courant
**Date** : 2026-08-28
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
│   ├── shots_tui.py              ← inventaire visuel des écrans (export SVG)
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
| `audio_hd_codec` | str | `none` / `ac3` / `eac3` — transcoder TrueHD et DTS au débit de la source (§ 8.5) |
| `container` | str | `auto` / `mp4` / `mkv` — conteneur de sortie (§ 8.6) |

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

**Pickers de codec.** `STRIP_DV` n'appartient pas à `ACTION_CYCLE` : ce n'est
pas un codec proposable. `cycle_index()` lui rend la position de `SKIP`, et
`same_intent()` fait que choisir `SKIP` sur un tel fichier lève la surcharge
plutôt que d'imposer un SKIP sec. Toute action doit avoir une position dans le
cycle — un `.index()` direct lève un `ValueError` et fait tomber l'écran.

**Prérequis** — `dovi_tool` *et* `mkvmerge`. Sans les deux,
`decision.set_strip_dv_available(False)` fait retomber la décision sur `SKIP` :
proposer une action qui échouera au lancement vaut moins que ne rien proposer.

### 7.4 Paramètres x265 HDR10

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
| 8 | **Dolby Vision et remux — vérifié pour le retrait (§ 7.3), pas pour la conservation.** Le chemin `STRIP_DV` est mesuré sur un fichier réel : sortie bit à bit identique, HDR10+ conservé. Porter un RPU *à travers* un remux mkvmerge (`dvcC`/`dvvC`) reste non testé. | Le profil 7 est éligible par construction mais n'a pas été essayé, faute de fichier. |

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
| **Retrait DV** | `action == STRIP_DV` | aucun — dovi_tool + mkvmerge | `build_command` retourne `[]`, ffmpeg n'est pas appelé (§ 7.3) |
| **DV copy** | `dv_action == DV` | `-c:v copy` | Pas de réencodage, pas de hwaccel |
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

Le parcours libre laisse le choix de l'ordre, ce qui suppose de le connaître.
L'assistant l'impose. Il est le **mode d'entrée** de l'application ; `F12`
bascule vers le parcours libre, et le choix tient pour la session.

Il ne calcule rien de neuf : `decide()` a déjà arbitré le codec, le débit, le
conteneur, le sort du Dolby Vision et chaque piste (§ 5, § 7, § 8). L'assistant
parcourt cette décision et rend la main aux écrans existants pour ce qu'ils
font déjà.

| Étape | Toujours ? | Ce qu'elle fait |
|---|---|---|
| 1 — Résumé | oui | Annonce la source, l'action vidéo, les pistes retenues et **le nom du fichier produit**. `A` ouvre l'écran des pistes |
| 2 — Langues | seulement si ambiguïté | Plusieurs pistes revendiquent la même langue voulue : l'utilisateur coche |
| 3 — Donneur | oui | `O` présente un fichier (sélecteur et recalage existants), `N` passe |
| 4 — Lancer | oui | Mux si rien n'est à réencoder et qu'il y a à greffer, encodage sinon |

**Ce qu'on retire, c'est la navigation — jamais l'information.** Un assistant
qui déciderait en silence remplacerait un doute de manipulation par un doute de
contenu, qui ne se voit qu'après l'encodage. Chaque étape montre donc ce qu'elle
a décidé, et avancer tient à une touche.

**Le doute se définit par un compte, pas par une heuristique.** Une seule piste
candidate pour une langue voulue : on la prend. Plusieurs : seul leur *titre*
les sépare — « Français » contre « Français canadien », « (forced) » contre
« (SDH) ». Un titre ne se devine pas, et une règle par motifs serait une liste
de mots-clés à maintenir sans fin. `decision.ambiguites()` compte, et l'étape 2
n'existe que si le compte l'exige.

**Aucun fichier donneur n'est cherché automatiquement.** Les conventions de
nommage des releases sont sans limite, et un mauvais appariement est
*silencieux* — il ne se découvre qu'à l'écoute du fichier produit. C'est
l'utilisateur qui présente le donneur, quand il y en a un.

**Les choix se réappliquent depuis une base, jamais par retranchement.**
`_relever()` fige la sélection d'avant tout arbitrage ; chaque validation
recalcule l'ensemble depuis elle. Retrancher de la sélection courante rendait
un choix irréversible : recocher une piste écartée ne la ramenait pas, alors
que l'écran laissait croire le contraire.

**Les bindings de l'écran sont tous `priority=True`.** Un `DataTable` étouffe
les touches avant que le système de bindings soit consulté (voir
l'avertissement en tête de `tui/mixins.py`) : sans cela, `↵` ne fait rien sur
les étapes qui affichent une table.

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
| ETA | `temps_estim` | durée d'encodage estimée |
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
