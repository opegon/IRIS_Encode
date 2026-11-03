# Note de conception — Agrandissement par super-résolution (2026-11-03)

**Statut : réflexion, rien n'est codé. Recherche et essais P0 faits le
2026-11-03 (§ 10) : ils corrigent plusieurs points ci-dessous, signalés « → § 10 ».** Cette note fixe les décisions prises en
discussion (session cloud du 2026-11-02/03), la règle de décision, les points
d'insertion dans le code, la pile technique retenue, les questions encore
ouvertes et ce qu'il reste à vérifier sur le web. Elle sert de point de reprise
pour une session Claude Code avec accès web complet.

Base de code lue : `main` à `3cc018e` (v0.9.1.16).

---

## 0. Résumé

- IRIS ne fait aujourd'hui que **réduire** (4K → 1080p, et < 1080p → cadre
  720p). Il n'agrandit jamais (`core/encoder.py`, chemin processeur : « une
  source qui tient dans la cible n'est pas agrandie »).
- Projet : **agrandir d'un seul palier** (480p, 720p, 1080p) les sources qui
  en sont assez éloignées, **uniquement par super-résolution matérielle**
  (pas d'interpolation classique), avec le **débit du palier atteint**.
- Règle : facteur `f` pour tenir dans le cadre du palier supérieur ;
  **agrandir si `1,2 ≤ f ≤ 1,5`**, sinon garder la définition d'origine.
  → § 10.3 : les shaders ne s'activent qu'au-delà de ×1,3.
- Pile retenue : **niveau 1** = `libplacebo` (Vulkan, NVIDIA/Intel/AMD) +
  shaders mpv (ArtCNN, Anime4K, FSRCNNX), en réutilisant le ffmpeg à
  libplacebo déjà présent pour le Dolby Vision profil 5 (`core/dovi.py`).
  **Niveau 2** (qualité, plus tard) = VapourSynth + vs-mlrt.
- Profil sans la nouvelle option = **comportement actuel inchangé** (aucune
  régression).

---

## 1. Décisions prises

| # | Décision | Justification |
|---|---|---|
| D1 | Agrandir **d'un palier au plus** par encodage, jamais en cascade | Limiter la quantité de détail à inventer ; deux rééchantillonnages successifs dégradent |
| D2 | Paliers : **480p, 720p, 1080p**. Pas d'agrandissement vers la 4K | Périmètre voulu |
| D3 | Le palier se juge sur le **cadre** (854×480, 1280×720, 1920×1080), pas sur la hauteur seule | Un 1920×800 (scope) est un 1080p, pas un « moins de 1080p » |
| D4 | Dimensions mesurées en **pixels carrés** (`VideoInfo.largeur_affichee`) | Les DVD et la TNT SD sont anamorphiques |
| D5 | **Zone morte** : pas d'agrandissement si `f < 1,2` | Un ×1,03 (700p → 720p) coûte un rééchantillonnage pour aucun gain visible |
| D6 | **Plafond** : pas d'agrandissement si `f > 1,5` | Les modèles sont fiables jusqu'à ×2 ; au-delà, ils hallucinent sur des sources dégradées. 1,5 couvre exactement 480 → 720 et 720 → 1080 |
| D7 | 480p → 720p et 720p → 1080p sont **voulus** | Choix explicite de l'utilisateur |
| D8 | Règle des « 10 % au-dessus du palier » **abandonnée** | Incohérente avec D7 : 480p → 720p (×1,50) et 481p → 720p (×1,497) demandent le même effort |
| D9 | **Débit = celui du palier atteint** (ex. 720p à 1 500 k → 1080p à 2 000 ou 2 500 k selon le profil) | On cherche la qualité ; la super-résolution crée du détail fin, coûteux à encoder |
| D10 | **Super-résolution uniquement**, sur le matériel (NVIDIA, Intel, AMD). Pas de repli sur lanczos ou bicubic | Un agrandissement classique n'apporte rien que le téléviseur ne fasse aussi bien |
| D11 | Première voie : **libplacebo + shaders** | Multi-constructeur, déjà embarqué, déjà maîtrisé dans le code |

---

## 2. La règle de décision

### 2.1 Pseudo-code

```python
PALIERS = [(854, 480, 480), (1280, 720, 720), (1920, 1080, 1080)]
ZONE_MORTE = 1.2   # config [decision] upscale_min_factor
PLAFOND    = 1.5   # config [decision] upscale_max_factor

def palier_superieur(w, h):
    """Premier cadre que la source ne remplit pas, avec son facteur."""
    for W, H, bucket in PALIERS:
        f = min(W / w, H / h)          # « tient dans le cadre »
        if f > 1.0:                    # la source ne touche aucun bord
            return W, H, bucket, f
    return None                        # source ≥ cadre 1080p : logique actuelle

w, h = info.largeur_affichee, info.height
p = palier_superieur(w, h)
if p is None:
    → logique actuelle (_resolve_limits : 4K → 1080p, etc.)
W, H, bucket, f = p
if f < ZONE_MORTE:
    → définition d'origine, débit du palier `bucket` (la source est « presque » ce palier)
elif f <= PLAFOND:
    → super-résolution vers (W, H), débit du palier `bucket`
else:
    → définition d'origine (trop basse, ex. 240p) ; débit : voir question Q3
```

Bornes : `f = 1,2` et `f = 1,5` sont **inclus** dans l'agrandissement
(1600×900 → 1080p ; 480p → 720p).

### 2.2 Vecteurs de test

Ces cas, calculés à la main, sont à transformer en tests (`tests/test_upscale_paliers.py`).

| Source (stockée) | SAR | Pixels carrés | Cadre visé | f | Résultat | Sortie attendue |
|---|---|---|---|---|---|---|
| 320×240 | 1:1 | 320×240 | 854×480 | 2,00 | garde | 320×240 |
| 426×240 | 1:1 | 426×240 | 854×480 | 2,00 | garde | 426×240 |
| 480×360 | 1:1 | 480×360 | 854×480 | 1,33 | **SR** | 640×480 |
| 640×360 | 1:1 | 640×360 | 854×480 | 1,33 | **SR** | 854×480 |
| 720×400 | 1:1 | 720×400 | 854×480 | 1,19 | garde (zone morte) | 720×400 |
| 640×480 | 1:1 | 640×480 | 1280×720 | 1,50 | **SR** | 960×720 |
| 854×480 | 1:1 | 854×480 | 1280×720 | 1,50 | **SR** | 1280×720 |
| 720×480 (DVD NTSC 4:3) | 8:9 | 640×480 | 1280×720 | 1,50 | **SR** | 960×720 |
| 720×480 (DVD NTSC 16:9) | 32:27 | 853×480 | 1280×720 | 1,50 | **SR** | 1280×720 (853 de large affichés, arrondi pair) |
| 720×576 (DVD PAL 4:3) | 16:15 | 768×576 | 1280×720 | 1,25 | **SR** | 960×720 |
| 720×576 (DVD PAL 16:9) | 64:45 | 1024×576 | 1280×720 | 1,25 | **SR** | 1280×720 |
| 960×540 | 1:1 | 960×540 | 1280×720 | 1,33 | **SR** | 1280×720 |
| 1100×620 | 1:1 | 1100×620 | 1280×720 | 1,16 | garde (zone morte) | 1100×620 |
| 1280×720 | 1:1 | 1280×720 | 1920×1080 | 1,50 | **SR** | 1920×1080 |
| 1280×536 (720p scope) | 1:1 | 1280×536 | 1920×1080 | 1,50 | **SR** | 1920×804 |
| 1440×850 | 1:1 | 1440×850 | 1920×1080 | 1,27 | **SR** | 1830×1080 |
| 1600×900 | 1:1 | 1600×900 | 1920×1080 | 1,20 | **SR** (borne) | 1920×1080 |
| 1700×960 | 1:1 | 1700×960 | 1920×1080 | 1,125 | garde (zone morte) | 1700×960 |
| 1920×800 | 1:1 | — | (remplit le cadre 1080) | — | logique actuelle | 1920×800 |
| 1440×1080 | 1:1 | — | (remplit le cadre 1080) | — | logique actuelle | 1440×1080 |

Les dimensions de sortie se calculent avec `dimensions_reduites()`
(`core/encoder.py:616`). Malgré son nom, cette fonction fait un « tient dans le
cadre » avec un arrondi pair identique à ffmpeg, et elle marche aussi bien à
l'agrandissement. Elle pourrait être renommée, par exemple `dimensions_cadre()`.

### 2.3 Effets de bord sur la logique actuelle

- **Seuils `near_1080p_min_width/height` (1600 / 850)** (`core/decision.py:793`).
  Avec l'agrandissement actif, ils sont remplacés par la règle ci-dessus : la
  zone morte joue le même rôle (1700×960 reste natif, en tranche 1080). Avec
  l'agrandissement **inactif**, ils restent tels quels (non-régression).
  → Recommandation : `_resolve_limits` choisit sa branche selon le profil.
- **Les sources entre 1080p et 4K** (ex. 2560×1440) : non concernées. Hors
  sujet, mais à noter : aujourd'hui, `is_4k` (≥ 3200 de large ou ≥ 1700 de
  haut) est faux pour du 1440p, qui est gardé natif en tranche 1080.
- **Le codec** : `sub_1080 = bucket_h < 1080` (`core/decision.py:877`). Un
  480p agrandi en 720p reste en H264 ; un 720p agrandi en 1080p passe en HEVC.
  C'est cohérent, rien à changer.

---

## 3. Points d'insertion dans le code

### 3.1 `core/decision.py`

1. **`_resolve_limits(info, profile)`** (l. 812). Il renvoie aujourd'hui
   `(limit_w, limit_h, bucket_h)`. Il renverrait en plus un indicateur
   `agrandir: bool`, ou une petite dataclass `Cible(w, h, bucket, agrandir, facteur)`.
   - Agrandissement inactif dans le profil → code actuel, à l'identique.
   - Agrandissement actif → règle § 2.1, puis l'existant si `palier_superieur`
     renvoie None.
2. **`decide_video`** (l. 849). Il faut un nouveau cas **avant** le SKIP :
   aujourd'hui, un 720p au bon débit et dans un codec lisible tombe en
   `SKIP`. Avec l'agrandissement, il doit être encodé.
   - Nouveau cas « Résolution relevée » : raison du type
     `_("Upscale {w}x{h} → {tw}x{th} (super-resolution ×{f})")`,
     `target_bitrate = profile.bitrate_for_height(bucket)`, et non le débit
     de la source comme dans le CAS 2.
   - Dans les CAS 1, 1 bis et 2 existants, si `agrandir` est vrai, la raison
     devrait le mentionner (comme `_raison()` le fait pour le Dolby Vision).
3. **Garde-fous** (la décision refuse l'agrandissement et garde la définition
   d'origine, en disant pourquoi) :
   - pas de ffmpeg avec libplacebo (`dovi.ffmpeg_dv() is None`), ou pas de
     GPU Vulkan → raison explicite, **pas** de repli sur une interpolation
     classique (D10) ;
   - source HDR ou Dolby Vision → **exclue en v1** (les shaders sont prévus
     pour du SDR BT.709 ; les sources SD/720p HDR sont rarissimes) ;
   - vidéo recopiée (`video_recopiee`, Dolby Vision conservé) → impossible
     par construction.
4. **Nommage** (l. 650-655, `_definition_abaissee`). Aujourd'hui, le nom n'est
   corrigé que si la définition baisse (`stem_resolution_ramenee`). Il faut
   généraliser à « définition changée » : `Film.576p` → `Film.720p`. Voir la
   question Q5 sur le marquage des fichiers agrandis.
5. **`forcer_encodage`** (l. ~1528, qui utilise `_resolve_limits(...)[2]`) et
   la ligne 1524 : vérifier qu'ils restent cohérents avec la nouvelle
   signature.

### 3.2 `core/encoder.py`

1. **Choix du binaire.** Comme pour le profil 5 (l. 876-889) : si la décision
   agrandit, toute la commande passe par `dovi.ffmpeg_dv()` avec
   `-init_hw_device vulkan`. C'est un BtbN GPL, qui contient aussi NVENC, QSV,
   AMF et libvmaf (à confirmer pour sa version).
   → Renommer à terme `ffmpeg_dv` en `ffmpeg_libplacebo` : il ne servira plus
   seulement au Dolby Vision.
2. **`filtre_tout_puce`** (l. 666) : renvoyer None si la décision agrandit
   (le passage par libplacebo et Vulkan n'est pas compatible avec la chaîne
   `vpp_qsv` / `scale_cuda`).
3. **Pas de `-hwaccel`** dans ce cas, comme pour le profil 5 (« libplacebo
   prend les images en mémoire »).
4. **Nouvelle fonction `filtre_super_resolution(decision)`**, sur le modèle de
   `filtre_p5` (l. 140) :
   ```
   [bwdif=…,]                       # si decision.desentrelace (déjà en place)
   libplacebo=
       w=<tw>:h=<th>:
       force_original_aspect_ratio=decrease:force_divisible_by=2:
       custom_shader_path='<chemin échappé du .glsl>':
       upscaler=<voir ci-dessous>:
       colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv:
       format=yuv420p
   ,setsar=1
   ```
   - **Pixels non carrés** : aujourd'hui, `scale=trunc(iw*sar/2)*2:…` est
     appliqué d'abord (CR-14). Avec la super-résolution, il faut **une seule**
     étape de rééchantillonnage : libplacebo doit absorber le SAR. Vérifier
     l'option `normalize_sar` de `vf_libplacebo` (→ § 10.2 : c'est
     `reset_sar`), ou passer des `w`/`h` déjà
     calculés en pixels carrés.
   - **Facteur ×1,5 ou ×1,25 avec un shader ×2** : le shader double la
     luminance, puis l'agrandisseur de libplacebo (`upscaler` /
     `downscaler`) ramène au cadre. Il faut vérifier que la réduction
     d'après-shader passe bien par le `downscaler` (défaut à confirmer ;
     `ewa_lanczos` ou `mitchell` sont des candidats).
   - **Échappement des chemins sous Windows** : `C:\…` contient un `:`, qui
     est un séparateur de filtre. Il faut écrire `C\:/…` entre apostrophes, ou
     passer le shader par `custom_shader_bin`. C'est un piège classique, à
     couvrir par un test.
   - **Le 10 bits** : la sortie est en 8 bits (`yuv420p`) pour du H264. Pour
     du HEVC (720p → 1080p), `yuv420p10le` est envisageable (moins de
     banding). À trancher par la mesure.
5. **Débruitage** (DVD, MPEG-2). La super-résolution amplifie les blocs et le
   bruit. Deux options :
   - un shader « DN » (ArtCNN `*_DN` débruite et adoucit ; `*_DS` débruite et
     accentue) ;
   - un `hqdn3d` léger, au processeur, avant libplacebo.
   → À départager par la mesure.

### 3.3 `core/profiles.py` et `data/profiles.default.toml`

Nouvelles clés de profil (noms provisoires) :

| Clé | Valeurs | Défaut | Rôle |
|---|---|---|---|
| `upscale` | `false` / `true` | `false` | Active la règle § 2 |
| `upscale_engine` | `"libplacebo"` (v1), puis `"vsmlrt"`, `"nvidia_vfx"`, `"amf"` | `"libplacebo"` | Moteur |
| `upscale_model` | `"film"` / `"anime"` / nom de shader | `"film"` ; `"anime"` pour `series_anime` | Choix du shader |
| `bitrate_480p_kbps` | entier | à définir (Q3) | Nouvelle tranche, utilisée si l'agrandissement vise 480p |

Il faut aussi :
- `bitrate_for_height` (l. 107) : ajouter la tranche 480 (`height >= 720` →
  720, `>= 480` → 480, sinon ?) ;
- une migration des profils existants (voir `tests/test_migration_profils.py`) ;
- l'affichage dans la TUI (`tui/common.py`, `PROFIL_COLONNES`) et le
  formulaire de profil (`tests/test_profile_form.py`).

Nouvelles clés de configuration, section `[decision]` de `config.toml` :
`upscale_min_factor = 1.2`, `upscale_max_factor = 1.5`.

### 3.4 Dépendances (`dependances.py`, `data/ffmpeg_releases.toml`, `core/preflight.py`)

- Les **shaders** sont à télécharger dans `bin/shaders/`, avec url + sha256,
  comme les autres outils. Une entrée par shader.
- Leur **présence** doit être vérifiée au préflight. L'agrandissement est
  désactivé, avec une raison, si un shader manque.
- Il faut **sonder Vulkan** : `a_libplacebo()` ne vérifie que la présence du
  filtre. Un essai court (`-init_hw_device vulkan -f lavfi -i
  color=…:d=0.1 -vf libplacebo -f null -`) dirait si le GPU est utilisable.

### 3.5 Interface, traduction et documentation

- Les raisons de décision sont à marquer `_()`/`N_()` (traduction) :
  `locales/` (voir `tests/test_console_anglais.py` et l'audit de localisation).
- Il faut une colonne ou un indicateur « SR » dans la liste des fichiers.
- `core/preview.py` : un aperçu avant/après serait très utile pour juger.
- Documentation à mettre à jour : `iris_encode_spec.md` (§ 6.1 champs de
  profil, et une nouvelle section), `wiki/concepts/codecs-video.md`,
  `wiki/syntheses/questions-ouvertes.md`, `GUIDE*.md`, `CHANGELOG.md`.

---

## 4. Pile technique

### 4.1 État de l'art (recherche du 2026-11-02, à revérifier)

| Famille | Projets | Matériel | Qualité / coût | Pour IRIS |
|---|---|---|---|---|
| **Shaders GPU** (temps réel) | **ArtCNN** série C (C4F32 ≈ 48 k paramètres, C4F16 ≈ 12 k), **Anime4K** v4, **FSRCNNX**, RAVU, ports de FSR 1 et NIS | Tout GPU Vulkan via libplacebo | Bonne, rapide | **Niveau 1** |
| **Réseaux image par image** | ArtCNN série R (ONNX), Real-ESRGAN (`realesr-animevideov3`), Real-CUGAN, waifu2x/nunif, SPAN, Compact (catalogue **OpenModelDB**) | vs-mlrt : TensorRT, OpenVINO, DirectML ; ou ncnn-Vulkan | Très bonne, lente, scintillement possible | **Niveau 2** |
| **Vidéo temporelle / diffusion** | BasicVSR++, RealBasicVSR, VRT/RVRT ; SeedVR2 (Apache 2.0, 3B/7B, ≥ 18 Go de VRAM) | Gros GPU | Maximale, hallucinations, coût extrême | Écarté |

### 4.2 Voies par constructeur

| GPU (`core/platform.py`, `GPU`) | Niveau 1 | Niveau 2 | Option propre au constructeur |
|---|---|---|---|
| NVIDIA | libplacebo / Vulkan | vs-mlrt TensorRT (moteur compilé sur la machine cible) | **`nvidia-vfx`** (paquet Python, RTX, pilote ≥ 570.65 selon des sources communautaires) ; pas d'intégration dans ffmpeg principal (builds tiers seulement : FFmpegForge `vsr_cuda`) |
| Intel | libplacebo / Vulkan | vs-mlrt OpenVINO GPU (Gen 8 et plus récents, Arc ; précision parfois réduite) ; NPU expérimental | **Pas** de super-résolution IA dans `vpp_qsv` (seulement `scale_mode`, choix de l'unité matérielle). Filtres DNN de ffmpeg (BasicVSR… via LibTorch) selon le build. Intel VSR Library (RAISR, ×1,5 et ×2), orientation processeur à vérifier |
| AMD | libplacebo / Vulkan | vs-mlrt DirectML (tout GPU DX12) | **`sr_amf`** (algorithmes `sr1-0` et `sr1-1`), intégré à ffmpeg vers février 2025, donc probablement ffmpeg ≥ 8.0 |
| APPLE | hors périmètre (pas de BtbN macOS ; MoltenVK à étudier) | — | — |
| NONE | **pas d'agrandissement** (lavapipe, le Vulkan logiciel, serait bien trop lent) | — | — |

### 4.3 Shaders du niveau 1 et licences

| Shader | Contenu visé | Licence | Compatibilité avec IRIS (GPL-3.0) |
|---|---|---|---|
| ArtCNN C4F32 / C4F16 (`_DS`, `_DN`, `_Chroma`) | Animation surtout ; à tester sur film | MIT (README du dépôt) | OK |
| Anime4K v4 (modes A, B, C, A+A, B+B, C+A) | Animation | MIT | OK |
| FSRCNNX (x2, 8/16 filtres) | Film | GPL-3.0 (licence du dépôt, → § 10.5) | OK dans les deux cas (IRIS est sous GPL-3.0) |

Ce qui a été vérifié dans le code de ffmpeg (`libavfilter/vf_libplacebo.c`,
branche master) : les options `custom_shader_path` (« Path to custom user
shader (mpv .hook format) ») et `custom_shader_bin` existent. `upscaler` est
une chaîne libre, `spline36` par défaut ; `upscaler=help` liste les préréglages.

---

## 5. Questions ouvertes

| # | Question | Pistes |
|---|---|---|
| Q1 | La réduction après le shader (×2 → ×1,5) est-elle de bonne qualité dans `vf_libplacebo` ? Quel `downscaler` ? | Essai et VMAF (§ 6) |
| Q2 | Un shader « film » est-il assez bon en prise de vue réelle, ou faut-il le niveau 2 pour le film ? | ArtCNN est pensé pour l'animation ; FSRCNNX pour le général. Mesurer |
| Q3 | Le débit d'une source **non agrandie** sous 480p (f > 1,5), ou en zone morte sous 480p : tranche 480p, ou débit 720p comme aujourd'hui ? Valeur de `bitrate_480p_kbps` ? | Proposition : la tranche 480p ne sert qu'aux sorties en 480p ; le reste ne change pas tant que l'option est inactive |
| Q4 | Faut-il débruiter les DVD par défaut ? Avec quoi (shader `_DN` ou `hqdn3d`) ? | Mesurer sur des DVD réels |
| Q5 | **Nommage et outils de médiathèque** : un `Film.576p` agrandi devient `Film.720p`. Radarr et Sonarr le classeraient en 720p et pourraient **cesser de chercher** un vrai 720p ou 1080p. Faut-il un marqueur (`.SR`, `.upscaled`, ou le suffixe IRIS) ? | À trancher : honnêteté du nom contre compatibilité avec ces outils |
| Q6 | Sortie 10 bits pour le HEVC agrandi (720p → 1080p) ? | Moins de banding ; vérifier la lecture sur la chaîne cible (Jellyfin) |
| Q7 | Les sources HDR en dessous de 1080p : exclues en v1. Les traiter plus tard ? | libplacebo sait faire du tone mapping ; cas rarissime |
| Q8 | Le temps de calcul sur un iGPU Intel (i5-1135G7, la machine de référence des mesures IE-147) : acceptable ? | Mesures (§ 6.3) |
| Q9 | Scintillement temporel (les shaders et réseaux image par image) : visible ? | Juger sur des plans fixes et de lents panoramiques |
| Q10 | Faut-il une **zone morte et un plafond par profil**, plutôt qu'en configuration globale ? | Proposition : globale en v1 |

---

## 6. Protocole de validation (avant de coder)

### 6.1 Essai manuel de la chaîne (niveau 1)

Avec le ffmpeg de `bin/dv/` (BtbN GPL) :

```bash
ffmpeg -hide_banner -init_hw_device vulkan -i source_576p.mkv -t 60 \
  -vf "bwdif=mode=send_frame:parity=auto:deint=interlaced,libplacebo=w=1280:h=720:force_original_aspect_ratio=decrease:force_divisible_by=2:custom_shader_path='shaders/ArtCNN_C4F32.glsl':colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv:format=yuv420p,setsar=1" \
  -c:v libx264 -crf 16 -preset slow -an essai_sr.mkv
```

Sous Windows, le chemin du shader s'écrit `'C\:/…/ArtCNN_C4F32.glsl'`.

À comparer avec le même encodage sans `custom_shader_path` (agrandisseur
seul : `spline36` puis `ewa_lanczos`), et avec la source lue directement par
le téléviseur ou le lecteur de la chaîne cible.

### 6.2 Mesure objective (falsification)

1. Prendre un **vrai** 1080p propre (film et animation), et un vrai 720p.
2. Le réduire à la définition source simulée :
   `scale=1280:720:flags=lanczos` (ou 960×540, 854×480).
3. Le recompresser comme une source réelle (x264, débit SD ou 720p) pour
   simuler les artefacts. Sans cette étape, la mesure est trop flatteuse.
4. Le ré-agrandir avec chaque méthode : `spline36`, `ewa_lanczos`, ArtCNN,
   FSRCNNX, Anime4K, puis (niveau 2) Real-ESRGAN, ArtCNN série R.
5. Calculer VMAF, SSIM et PSNR contre l'original :
   `ffmpeg -i agrandi.mkv -i original.mkv -lavfi libvmaf=n_threads=8 -f null -`
6. Juger **à l'œil** (VMAF récompense mal le détail inventé) : visages,
   textures, texte, scintillement.

**Critère d'abandon :** si la super-résolution ne bat pas nettement
`ewa_lanczos` ni la lecture brute sur la chaîne cible, la fonction n'a pas
lieu d'être pour ce type de contenu.

### 6.3 Mesures de performance

Images par seconde en sortie, par GPU (iGPU Intel, RTX A4500, AMD si
disponible) et par shader, pour 480 → 720 et 720 → 1080. On les compare au
temps d'encodage actuel d'un fichier équivalent.

---

## 7. Phasage proposé

| Phase | Contenu | Livrable |
|---|---|---|
| P0 | Recherche web complémentaire (§ 8) et essais manuels (§ 6) | Résultats de mesure ajoutés à cette note |
| P1 | Règle de décision seule (§ 2), tests à partir du tableau § 2.2, sans encodage (la décision s'affiche, l'encodage reste comme aujourd'hui) | `decision.py` et ses tests |
| P2 | Chaîne libplacebo + shaders, garde-fous, sonde Vulkan, shaders dans les dépendances | `encoder.py`, `dovi.py`/préflight, `dependances.py` |
| P3 | Profils (clés, migration, TUI, formulaire), nommage (Q5), traduction | Version utilisable |
| P4 | Documentation (spec, wiki, guide, CHANGELOG) | Release |
| P5 (plus tard) | Niveau 2 : vs-mlrt (TensorRT, OpenVINO, DirectML) ; options `nvidia-vfx` et `sr_amf` | Mode « qualité » |

Chaque phase suit la convention du dépôt : un incrément de version et une
entrée de CHANGELOG.

---

## 8. À vérifier sur le web (la session cloud n'avait pas accès à ffmpeg.org)

1. `vf_libplacebo` (doc officielle `ffmpeg-filters.html`) : options
   `normalize_sar`, `downscaler`, `upscaler`, comportement d'un shader ×2 vers
   un cadre ×1,5, entrée en images logicielles sans `hwupload`.
2. Version du ffmpeg BtbN de `bin/dv/` : présence de libplacebo récent et de
   libvmaf.
3. Licence exacte des shaders **FSRCNNX** (dépôt igv : GPL-3.0 et MIT) ; liste
   et poids des shaders ArtCNN série C ; dernière version d'Anime4K.
4. **vs-mlrt** : dernière version (v14 vue), modèles fournis à part depuis la
   v14, distribution portable de VapourSynth sous Windows.
5. **`sr_amf`** : version de ffmpeg qui l'inclut, et si les algorithmes
   `sr1-x` correspondent à FSR.
6. **`nvidia-vfx`** et le RTX Video SDK : licence de redistribution,
   pilote minimal, API Python.
7. Intel : une super-résolution IA exposée par VPL ou oneVPL dans une version
   récente de ffmpeg ou du runtime ; la cible matérielle de la Video Super
   Resolution Library (RAISR).
8. Video2X 6.x : architecture du pipeline (décodage → libplacebo ou ncnn →
   encodage), comme référence.

---

## 9. Sources (recherche du 2026-11-02)

- FFmpeg — `vf_libplacebo.c` : https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/libavfilter/vf_libplacebo.c
- Phoronix — FFmpeg Adds AMD AMF Decoder, FSR-Based Upscaling : https://www.phoronix.com/news/FFmpeg-AMD-AMF-Decoder-FSR
- FFmpeg-devel — AMF VPP & super resolution filters : https://ffmpeg.org/pipermail/ffmpeg-devel/2024-May/328491.html
- Intel — VPL in FFmpeg : https://www.intel.com/content/www/us/en/developer/articles/technical/onevpl-in-ffmpeg-for-great-streaming-on-intel-gpus.html
- Intel — media framework upstream patches 2022 Q3 : https://www.intel.com/content/www/us/en/developer/articles/technical/media-framework-upstream-patches-2022-q3.html
- OpenVisualCloud — Video Super Resolution Library : https://github.com/OpenVisualCloud/Video-Super-Resolution-Library
- vs-mlrt : https://github.com/AmusementClub/vs-mlrt — v13.2 (DirectML) : https://github.com/AmusementClub/vs-mlrt/releases/tag/v13.2
- Video2X : https://github.com/k4yt3x/video2x
- ArtCNN : https://github.com/Artoriuz/ArtCNN
- Anime4K : https://github.com/bloc97/Anime4K/releases
- FSRCNN-TensorFlow (FSRCNNX) : https://github.com/igv/FSRCNN-TensorFlow
- NVIDIA RTX Video SDK : https://developer.nvidia.com/rtx-video-sdk
- FFmpegForge (intégration tierce RTX VSR) : https://github.com/Aaronstanley78/FFmpegForge/releases/tag/1.1.1
- SeedVR2 (ComfyUI) : https://docs.comfy.org/tutorials/utility/seedvr2.md

---

## 10. Résultats de P0 (recherche et essais du 2026-11-03)

Session Claude Code locale, PC Shadow (RTX A4500), base de code `main` à
`b93ad59` (v0.9.1.17). Le ffmpeg utilisé est le BtbN `n8.1.3-20260925` du PATH
(`C:\Program Files\ffmpeg`).

### 10.1 Conclusion d'abord

- **La chaîne fonctionne** : libplacebo + Vulkan + shader mpv, chemin Windows
  échappé, SAR absorbé, sortie aux bonnes dimensions. Du premier coup.
- **Le gain du niveau 1 est réel mais faible** : de +0,9 à +2,2 points de VMAF
  sur le meilleur agrandisseur classique, PSNR et SSIM inchangés (§ 10.4). Un
  écart visible commence vers 6 points de VMAF. À l'œil (Cactus Jack, The Kid,
  Le Monde du silence), les contours sont un peu plus nets, sans artefact,
  sans transformation.
- **Le critère d'abandon du § 6.2 (« battre *nettement* `ewa_lanczos` ») n'est
  pas atteint** par le niveau 1. Le niveau 2 (Real-ESRGAN, ArtCNN série R)
  n'est pas encore mesuré : c'est lui qui peut faire basculer la décision.
- Trois pièges trouvés, qui auraient produit des fichiers faux sans erreur
  visible : la colorimétrie devinée par libplacebo (§ 10.2), les shaders
  inactifs sous ×1,3 (§ 10.3), `normalize_sar` qui recadre au lieu d'étirer
  (§ 10.2).

### 10.2 `vf_libplacebo` (§ 8, point 1)

Lu dans `ffmpeg -h filter=libplacebo` (ffmpeg 8.1.3) :

| Option | Constat |
|---|---|
| `normalize_sar` | « like reset_sar, but **pad/crop** instead of stretching » : **à ne pas utiliser** |
| `reset_sar` | ramène le SAR à 1:1 **en étirant** : c'est l'option voulue. Essai : DVDRip 720×400 → `w=1280:h=720:force_original_aspect_ratio=decrease:reset_sar=1` → 1280×712, SAR 1:1 |
| `upscaler` / `downscaler` | défauts `spline36` / `mitchell`. Après un shader ×2 ramené à ×1,5, `downscaler=ewa_lanczos` gagne 1,3 à 1,5 point de VMAF sur `mitchell` (réponse à Q1) |
| `deinterlace` | libplacebo désentrelace lui-même (`weave`, `bob`, `yadif`, `bwdif`) : on peut se passer du `bwdif` processeur en amont |
| `colorspace`, `color_primaries`, `color_trc`, `range` | sortie seulement. Voir le piège ci-dessous |
| `sigmoid` | sans effet mesurable ici (défaut `true`) |
| `dithering` | sans effet mesurable sur les métriques |
| entrée logicielle | acceptée sans `hwupload` (images en mémoire, comme le profil 5) |

**Piège de la colorimétrie.** Une source **sans étiquette de couleur** est
devinée par libplacebo d'après sa définition (SD → BT.601), et la sortie
aussi (HD → BT.709). Il convertit alors l'une vers l'autre. Mesuré : luminance
moyenne 111,6 → 110,1 sur une image, et jusqu'à 14 dB de PSNR perdus sur
certaines images. Avec `setparams=colorspace=…:color_primaries=…:color_trc=…:range=tv`
avant libplacebo, plus aucun écart.
→ **Règle d'implémentation** : toujours poser `setparams` avec la
colorimétrie lue par ffprobe ; si elle est absente, la choisir explicitement
(SD : `smpte170m` en 480 lignes, `bt470bg` en 576 ; HD : `bt709`) et sortir en
BT.709. Une source SD réellement BT.601 agrandie en HD **doit** être convertie
en BT.709 : c'est voulu, à condition que l'entrée soit déclarée.

### 10.3 Seuil d'activation des shaders : ×1,3

Les six shaders essayés portent la même condition :

```
//!WHEN OUTPUT.w LUMA.w / 1.3 > OUTPUT.h LUMA.h / 1.3 > *
```

Sous ×1,3, le shader **ne s'exécute pas** et libplacebo agrandit avec son
seul `upscaler`. Mesuré à ×1,25 : les six shaders donnent **exactement** le
résultat de `spline36`. Cela touche les DVD PAL (×1,25), 1440×850 (×1,27) et
1600×900 (×1,2) du tableau § 2.2, qui seraient annoncés « super-résolution »
sans l'être (contraire à D10).

Une copie d'ArtCNN C4F16 **sans la ligne `//!WHEN`** fonctionne à ×1,25 :
VMAF 75,60 contre 74,59 pour `ewa_lanczos` (+1,0).

Deux options, à trancher (nouvelle question Q11) :
1. relever la zone morte à `f > 1,3` (strict) : simple, mais les DVD PAL
   restent natifs ;
2. livrer des copies des shaders sans `//!WHEN` (licences MIT et GPL-3.0 :
   modification permise), avec l'empreinte de la copie dans les dépendances.

### 10.4 Mesure objective (§ 6.2)

Protocole : référence → réduite (`scale` lanczos) → **recompressée en x264**
au débit indiqué → ré-agrandie à la définition d'origine → VMAF / PSNR-Y / SSIM
(libvmaf, ffmpeg 8.1.3). Les deux entrées sont étiquetées BT.709 à
l'identique (sinon la mesure est faussée, voir § 10.2). Shaders :
`downscaler=ewa_lanczos`. Sources : *Tears of Steel* 720p (prise de vue
réelle, 20 s) et *Sintel* 1080p (animation, 1920×818, 20 s), films libres de
la fondation Blender.

| Méthode | ToS ×1,5 @1000k | ToS ×1,5 @4000k | ToS ×1,25 @1200k | Sintel ×1,5 @1500k | Sintel ×1,5 @5000k |
|---|---|---|---|---|---|
| lanczos (swscale) | 73,25 | 78,85 | 74,72 | 93,91 | 96,29 |
| libplacebo `ewa_lanczos` | 73,11 | 78,66 | 74,59 | 93,80 | 96,12 |
| FSRCNNX x2 8 | 73,96 | 79,64 | (inactif) | 95,87 | 98,10 |
| FSRCNNX x2 16 | 73,86 | 79,58 | (inactif) | 95,79 | 98,05 |
| **ArtCNN C4F16** | **74,55** | **80,16** | 75,60 (forcé) | **96,15** | **98,27** |
| ArtCNN C4F32 | 74,48 | 80,12 | (inactif) | 96,12 | 98,26 |
| ArtCNN C4F16_DN | 73,12 | 78,55 | (inactif) | 94,76 | 96,89 |

(VMAF. PSNR-Y et SSIM : écarts inférieurs à 0,5 dB et 0,002 entre toutes les
méthodes ; `_DN` a les meilleurs, il lisse.)

Lecture :
- ArtCNN **C4F16** est le meilleur partout, et **C4F32 n'apporte rien** pour
  un coût 2 à 7 fois plus élevé → C4F16 par défaut (réponse partielle à Q2 :
  il convient aussi à la prise de vue réelle).
- Le gain sur lanczos est de **+1,3 / +1,3 / +0,9 / +2,2 / +2,0** VMAF : plus
  net en animation qu'en prise de vue réelle.
- `_DN` (débruitage) fait perdre du VMAF, mais gagne en PSNR et SSIM : à juger
  à l'œil sur de vrais DVD (Q4), pas à la métrique.
- Biais connu : VMAF favorise la netteté accentuée. Le gain des shaders est
  donc plutôt un plafond qu'un plancher.

### 10.5 Vitesse (§ 6.3, RTX A4500 seulement)

Filtre seul (décodage + libplacebo, sans encodage), DVDRip 720×400, 750 images :

| Shader | → 1280×720 | → 1920×1080 |
|---|---|---|
| aucun (spline36) | 290 i/s | 260 i/s |
| ArtCNN C4F16 | 190 i/s | 170 i/s |
| FSRCNNX x2 8 | 180 i/s | 170 i/s |
| FSRCNNX x2 16 | 115 i/s | 120 i/s |
| ArtCNN C4F32 | ~90 i/s (1er passage 25 i/s : compilation du shader) | 90 i/s |

L'encodeur reste le goulot. **Q8 (iGPU Intel i5-1135G7) reste à mesurer**, sur
le portable de l'utilisateur.

### 10.6 Le ffmpeg (§ 8, point 2)

- Le ffmpeg **livré** dans `bin/` (gyan 8.1.2 « essentials ») **n'a pas**
  libplacebo. Il a `libvmaf` et `sr_amf`.
- Le BtbN GPL (PATH de ce poste, ou `bin/dv/` posé par
  `install_ffmpeg_dvd(…, "ffmpeg_dv")`) a **libplacebo, libvmaf et `sr_amf`**.
- Donc `dovi.ffmpeg_dv()` reste le bon point d'entrée : il rend `bin/dv/` ou
  le principal s'il a libplacebo (IE-164). Le renommer `ffmpeg_libplacebo`
  reste pertinent.
- Le sondage Vulkan du § 3.4 reste nécessaire : `a_libplacebo()` ne lit que
  la liste des filtres.

### 10.7 Shaders, licences, versions (§ 8, point 3)

| Projet | Licence (vérifiée) | Version | Fichiers |
|---|---|---|---|
| ArtCNN | MIT (dépôt et en-tête de chaque `.glsl`) | v1.6.2 du 2026-03-14, dépôt actif | `ArtCNN_C4F16{,_DN,_DS}.glsl` (~213 Ko), `ArtCNN_C4F32{,_DN,_DS}.glsl` (~761 Ko). Série R (R8F64, R16F96, `_Chroma`, `_JPEG420`) en ONNX seulement → niveau 2. **sha256 publiés par GitHub** (champ `digest` des assets), directement utilisables dans `ffmpeg_releases.toml` |
| FSRCNNX | GPL-3.0 (licence du dépôt) | 1.1 du 2017-11-09, dépôt inactif depuis 2021 | `FSRCNNX_x2_8-0-4-1.glsl`, `FSRCNNX_x2_16-0-4-1.glsl` |
| Anime4K | MIT | v4.0.1 du 2021-09-17, dépôt inactif | `Anime4K_v4.0.zip` (non essayé : ArtCNN est donné pour supérieur sur l'animation et l'est déjà sur *Sintel* face à FSRCNNX) |

Empreintes sha256 relevées :

| Fichier | sha256 |
|---|---|
| `ArtCNN_C4F16.glsl` | `03d0b3d31cb82c898a94a46663021a3e8f02c5a21d69c5cfdf0208de4bfd453e` |
| `ArtCNN_C4F16_DN.glsl` | `047f33cd43ca3751b00c7c81206e076ac921c1fbc06d49f23010a0b428271acf` |
| `ArtCNN_C4F16_DS.glsl` | `57df650fddec3969e17799f5522c9b03dd2d33b1aeace237fef216bf3858125a` |
| `ArtCNN_C4F32.glsl` | `f773bce6cf5fe7e5e5d599a695edd40df5cd7a20c3d08c4d164d07591d5bead3` |
| `FSRCNNX_x2_8-0-4-1.glsl` | `e800dbc5c1c95185cc82216c597724533ff5f2880179f256eef600f03e8dc2ae` |
| `FSRCNNX_x2_16-0-4-1.glsl` | `d5a24a271e5d9a3f7f7a053b150c460a44c25b3cf7f770857d57cc3a2e1c9965` |

### 10.8 Niveau 2 et options par constructeur (§ 8, points 4 à 8)

| Point | Constat |
|---|---|
| **vs-mlrt** | Dernière stable **v15.16** (2026-03-26) ; série **v16.x en préversion** (`v16.4.test1`, 2026-10-30). Paquets Windows séparés par moteur : `vsmlrt-windows-x64-{tensorrt,cuda,generic-gpu,cpu,migraphx}`, `VSOV` (OpenVINO), `VSNCNN`, `VSTRT-RTX` ; modèles à part (`models.*.7z`, `contrib-models.*.7z`). GPL-3.0. VapourSynth : **R82** du 2026-11-01 (LGPL-2.1) |
| **`sr_amf`** | Présent dans ffmpeg 8.1 (gyan et BtbN). Options : `algorithm` = `bilinear`, `bicubic`, `point`, **`sr1-0`**, **`sr1-1`** (« Video SR1.0/1.1 »), `sharpness`, `keep-ratio`. Ajouté début 2025 (Phoronix), avec `vpp_amf`, pour l'agrandissement façon FSR. **Non essayé** (pas de GPU AMD ici) |
| **`nvidia-vfx`** | PyPI v0.2.0.0, **licence propriétaire NVIDIA** (`LicenseRef-NvidiaProprietary`) : **non redistribuable** avec IRIS (GPL-3.0). Possible seulement si l'utilisateur l'installe lui-même (`pip`). Python ≥ 3.10, GPU à Tensor Cores (Turing et suivants), pilote Windows ≥ 570.65. Jusqu'à ×4 |
| **Intel** | `vpp_qsv` (ffmpeg 8.1.3) n'expose **aucune** super-résolution IA : seulement `detail` (accentuation) et `scale_mode`. L'API VPL 2.14 ajoute des modes de super-résolution IA, mais **rien dans ffmpeg** à ce jour (aucune source trouvée). La *Video Super Resolution Library* (RAISR, BSD-3) vise surtout les **Xeon AVX-512** et l'OpenCL des GPU Intel, en greffon ffmpeg compilé à part (conteneur Docker) : écartée |
| **Video2X** | 6.4.0 (2025-01-24), AGPL-3.0. Même architecture que la voie retenue : décodage ffmpeg → libplacebo (shaders mpv) **ou** ncnn-Vulkan (Real-ESRGAN, Real-CUGAN, RIFE) → encodage. Conforte la pile niveau 1, et ncnn-Vulkan comme alternative à vs-mlrt pour le niveau 2 |

### 10.9 Les fichiers d'essai de l'utilisateur (`resources_files/`)

| Fichier | Caractéristiques | Avec la règle § 2 | Constats |
|---|---|---|---|
| **Cactus Jack** (1979), DVDRip | H264 720×400, SAR 1:1, 25 i/s, progressif, `smpte170m` | cadre 854×480, f = 1,19 → **zone morte, gardé natif** | L'utilisateur le cite comme « bon exemple d'upscaling » → **contradiction avec D5/D6** : le passer en 720p demande ×1,78, au-delà du plafond. Question Q12 |
| **The Kid** (1921) | MS-MPEG4v3 720×480, **SAR absent**, 29,97 i/s, 0,8 Mb/s, AVI | pris tel quel : cadre 1280×720, f = 1,5 → SR → 1080×720 | **Image 4:3 étirée en 3:2** (un DVD NTSC 4:3 dont le SAR 8:9 a été perdu en AVI). **Entrelacé** (idet : 895 TFF sur 899) : un télécinéma, pour lequel `fieldmatch,decimate` vaut mieux que `bwdif`. Bandes noires 8 px à gauche, 10 en haut. Avec SAR 8:9 supposé : 640×480 → 960×720 (×1,5). Ces défauts existent **sans** agrandissement : hors périmètre, question Q14 |
| **Le Monde du silence** (1955) | MPEG-4 ASP 704×528, SAR 1:1 (4:3), 25 i/s, progressif, 1 Mb/s | ne tient pas dans 854×480 (528 > 480) → cadre 1280×720, f = 1,36 → **SR → 960×720** | Image très douce et peu détaillée : la super-résolution a peu à exploiter (le filet du plongeur gagne un peu en netteté, rien d'autre) |

Planches comparatives faites (lanczos / ArtCNN C4F16 / C4F16_DN / FSRCNNX 16,
même image, même coupe). La différence la plus visible est sur The Kid
(visages, bord du chapeau), qui montre aussi qu'ArtCNN accentue légèrement
les blocs du MPEG-4 : `_DN` les atténue.

### 10.10 Questions nouvelles

| # | Question | Pistes |
|---|---|---|
| Q11 | Les shaders ne s'activent qu'au-delà de ×1,3 (§ 10.3) : relever la zone morte à 1,3, ou livrer des shaders sans `//!WHEN` ? | Mesure : forcé à ×1,25, +1,0 VMAF |
| Q12 | Cactus Jack (720×400) reste natif avec la règle. Faut-il relever le plafond (≈ ×1,8), au prix des hallucinations que D6 voulait éviter ? Ou réserver ce cas au niveau 2 ? | À ×1,78, ArtCNN C4F16 n'a montré aucun artefact, mais le gain y reste faible |
| Q13 | Vu le gain faible du niveau 1 (§ 10.4), faut-il **mesurer le niveau 2 avant P1** (Real-ESRGAN ncnn-Vulkan, ArtCNN R8F64 via vs-mlrt), pour décider si la fonction vaut son coût (débit du palier supérieur, D9) ? | Recommandation : oui, sur les mêmes extraits, avant d'écrire du code |
| Q14 | Source sans SAR (AVI) et source télécinée (The Kid) : faut-il les traiter, indépendamment de l'agrandissement ? | Deux entrées séparées dans `TODO.md` si oui |

### 10.11 Sources ajoutées

- `ffmpeg -h filter=libplacebo`, `-h filter=sr_amf`, `-h filter=vpp_qsv` (ffmpeg BtbN n8.1.3-20260925)
- ArtCNN v1.6.2 : https://github.com/Artoriuz/ArtCNN/releases/tag/v1.6.2
- FSRCNNX 1.1 : https://github.com/igv/FSRCNN-TensorFlow/releases/tag/1.1
- vs-mlrt (releases) : https://github.com/AmusementClub/vs-mlrt/releases
- VapourSynth R82 : https://github.com/vapoursynth/vapoursynth/releases
- nvidia-vfx (PyPI, licence) : https://pypi.org/project/nvidia-vfx/
- Phoronix, AMF et `sr_amf` : https://www.phoronix.com/news/FFmpeg-AMD-AMF-Decoder-FSR
- Intel VPL 2.14 / 2.16 (journal libvpl) : https://src.opensuse.org/pool/libvpl/src/branch/factory/libvpl.changes
- Video Super Resolution Library (README) : https://github.com/OpenVisualCloud/Video-Super-Resolution-Library
- Video2X (README) : https://github.com/k4yt3x/video2x
- Tears of Steel 720p : https://download.blender.org/demo/movies/ToS/tears_of_steel_720p.mov
- Sintel 1080p : https://download.blender.org/durian/movies/Sintel.2010.1080p.mkv

### 10.12 Extraits de jugement (2026-11-03)

Dans `resources_files/essais_sr/` (ignoré par git), 3 min par titre, son
compris. Versions 1 à 3 : même pré-traitement, mêmes couleurs, même encodage ;
seul le shader change.

| Titre | Début | Agrandissement | Encodage |
|---|---|---|---|
| Cactus Jack | 19:00 | 720×400 → 1280×712 (×1,78, plafond relevé) | H264 1 500 k |
| The Kid | 24:00 | 720×480, SAR 8:9 supposé, bwdif → 960×720 (×1,5) | H264 2 000 k |
| Le Monde du silence | 10:00 | 704×528 → 960×720 (×1,36) | H264 2 000 k |
| Blade Runner Black Lotus S01E01 | 5:00 | 1280×720 → 1920×1080 (×1,5) | HEVC 2 000 k |

Fichiers : `_0_source` (copie), `_1_classique_ewa_lanczos`, `_2_SR_ArtCNN_C4F16`,
`_3_SR_ArtCNN_C4F16_DN`, `_4_meme_zone_cote_a_cote` (Cactus Jack, The Kid ;
étiqueté), `_5_aveugle` (même zone des deux côtés, côté tiré au hasard, clé
gardée hors du dossier), et `CactusJack_6_SR_2passes_puis_reduction_1920x1066`.

Chaîne du fichier 6 (agrandissement « au maximum ») :

```
setparams=colorspace=smpte170m:color_primaries=smpte170m:color_trc=bt709:range=tv,
libplacebo=w=1440:h=800:custom_shader_path='…/ArtCNN_C4F16.glsl':<bt709>:format=yuv444p16le,
libplacebo=w=2880:h=1600:custom_shader_path='…/ArtCNN_C4F16.glsl':<bt709>:format=yuv444p16le,
libplacebo=w=1920:h=1066:downscaler=ewa_lanczos:<bt709>:format=yuv420p,setsar=1
```

HEVC 3 000 k. Vitesse : 18 i/s (0,73× le temps réel) sur RTX A4500, contre
plus de 150 i/s pour une passe.

Avis de l'utilisateur :
- versions 1 à 3 : « les différences sont trop subtiles » à première vue ;
  test à l'aveugle en cours ;
- fichier 6 (2 passes puis réduction) : **« propre » sur le PC** ; à vérifier
  sur la TV le 2026-11-04. Si ce résultat se confirme, il ouvre une variante
  de la règle : agrandir ×4 par deux passes puis réduire au cadre, plutôt que
  ×2 réduit à ×1,5. Elle est à mesurer selon le protocole § 10.4 avant d'être
  retenue.
