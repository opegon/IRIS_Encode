---
type: concept
maj: 2026-11-05
sources:
  - "[[source-spec]]"
  - "[[source-changelog]]"
  - "[[source-2026-09-26-nvenc-pilote]]"
  - "[[source-2026-10-28-qsv-portable]]"
  - "[[source-2026-10-28-qsv-decodage]]"
  - "[[source-2026-10-28-nvdec-tout-carte]]"
  - "[[source-2026-10-28-nvdec-dv-plage]]"
  - "[[source-2026-10-28-qsv-passe-dv]]"
  - "[[source-2026-10-29-nvenc-preset-slow]]"
  - "[[source-conception-upscaling]]"
  - "[[source-2026-11-04-libplacebo-shader-chemin]]"
---

# Codecs vidéo

## Ce qui se lit sans transcodage

**H264 et HEVC**, et rien d'autre. Code : `CODECS_LISIBLES`, spec § 8.1.

Tout le reste est réencodé, **quelle que soit la résolution** : un fichier
illisible chez le destinataire ne devient pas lisible parce que son débit est
raisonnable.

| Codec source | Traitement | Pourquoi |
|---|---|---|
| H264, HEVC | gardés si débit et résolution conviennent | lisibles partout |
| **AV1** | réencodé | décodage matériel seulement sur les modèles récents ; jamais une cible implicite |
| VP9 (WebM) | réencodé | idem |
| VC-1, MPEG-2, DivX, codec inconnu | réencodé | |

Cible : **H264 sous 1080p** (il y compresse mieux), **HEVC au-dessus**.

Vérifié de bout en bout (mesuré, v0.8.1.21) :

| Source | Sortie |
|---|---|
| WebM VP9 1080p + Opus 2.0 | HEVC Main + AAC LC 192k, MP4 |
| WebM AV1 720p + Opus 5.1 | H264 High + AC3 5.1 448k, MP4 |

## Encodeurs

| Plateforme | HEVC | H264 | AV1 |
|---|---|---|---|
| Windows + NVIDIA | `hevc_nvenc` | `h264_nvenc` | `av1_nvenc` |
| Windows + AMD AMF, sans NVIDIA *(expérimental)* | `hevc_amf` | `h264_amf` | `av1_amf` |
| Windows + Intel QSV, sans NVIDIA ni AMD | `hevc_qsv` | `h264_qsv` | `av1_qsv` |
| Windows sans NVIDIA, Linux | `libx265` | `libx264` | `libaom-av1` |
| macOS | `hevc_videotoolbox` | `h264_videotoolbox` | `libaom-av1` |

- **NVENC n'encode l'AV1 qu'à partir d'Ada (RTX 40).** Une carte antérieure ne
  le dit qu'au moment d'échouer : « No capable devices found ». Les encodeurs
  sont donc **sondés au lancement** (ouverts sur une image, ~0,7 s) plutôt que
  déduits du modèle de carte. *(mesuré : RTX A4500, `av1_nvenc` absent)*
- **Un ffmpeg trop récent pour le pilote perd tout NVENC** (HEVC, H264, AV1) :
  la sonde ne garde alors que `libx265`. Voir [[ffmpeg#NVENC et version du pilote]].
  *(mesuré, pilote 597.16)*
- **Intel Quick Sync est retenu sur sondage** (v0.9.0.9) : sans NVIDIA, IRIS
  ouvre `hevc_qsv` sur une image au lancement. Tiger Lake (i5-1135G7) encode le
  H.264 et le HEVC 8 et 10 bits, pas l'AV1 (Arc / Meteor Lake et après) :
  `av1_qsv` répond « Current codec type is unsupported », en 8 comme en 10 bits.
  *(observé sur le portable de l'utilisateur, ffmpeg de son PATH)* Le ffmpeg
  fourni contient les encodeurs QSV, pas SVT-AV1 : l'AV1 sans matériel passe
  par libaom. *(mesuré, gyan.dev 8.1.2)*
- **Intel : tout sur la puce, ou le décodage au processeur.** Décoder sur la
  puce puis réduire au processeur fait faire l'aller-retour à chaque image :
  `d3d11va` est *plus lent* (76 s contre 60 s pour 60 s de 4K HDR10 →
  1080p). Décoder, réduire avec `vpp_qsv` et encoder sans quitter la puce :
  **18 s**, HDR10 conservé. *(observé, i5-1135G7)* IRIS le fait pour le cas
  courant (v0.9.0.11) ; voir [[ffmpeg#Mise à l'échelle matérielle et SAR]].
- **AMD AMF, retenu sur sondage, avant Quick Sync** (v0.9.1.9,
  **expérimental**) : sans NVIDIA, IRIS ouvre `hevc_amf` ; sans carte AMD,
  ffmpeg refuse en code 171. *(mesuré sur le Shadow, gyan.dev 8.1.2)* Ce que
  dit `ffmpeg -h encoder=hevc_amf` *(lu, même build)* :
  - pas de `-preset medium` (« Unable to parse "preset" option value ») : trois
    vitesses seulement, `-quality speed|balanced|quality` ;
  - formats `nv12`, `yuv420p`, `p010le`… mais **pas `yuv420p10le`** ;
  - débit : `-rc vbr_peak` (VBR plafonné par `-maxrate`) ;
  - profils `main`/`main10` (HEVC), `main`/`high` (H264) ; `av1_amf` a un
    niveau de plus, `high_quality`.
  Encodage seul sur la carte : lecture et filtres au processeur, rien
  n'ayant été mesuré sur une carte AMD. Le ffmpeg fourni a aussi `vpp_amf`,
  l'équivalent de `vpp_qsv` pour une future chaîne tout-carte.
- **NVIDIA : même règle.** `-hwaccel cuda` suivi de `scale` au processeur
  ne gagne rien (28 s, comme tout au processeur, pour 60 s de 4K HDR10 →
  1080p ; plus lent en H264 SDR). Décoder, réduire avec `scale_cuda` et
  encoder sur la carte : **5,6 s**, sorties identiques. *(mesuré, RTX A4500)*
  IRIS le fait depuis v0.9.0.12, à partir de Pascal (garanti par un
  `hevc_nvenc` ouvert en 10 bits) ; l'AV1 seulement si `av1_nvenc` s'ouvre.
  La passe vidéo du réencodage DV aussi (v0.9.0.13) : 21 s → 13,5 s pour
  60 s de 4K, flux identique bit à bit. Sur Intel (v0.9.0.14) : 51 s → 38 s
  sur un i5-1135G7, mêmes images, PSNR 62,5 dB — pas identique.
- **Le gain dépend du preset.** En `slow` et en 4K, c'est l'encodeur qui
  limite : DV → HDR10 sur la A4500, 38 s pour 60 s, sur la carte ou non.
  *(mesuré, 2026-10-29)*
- **`av1_nvenc` n'a pas d'option `-profile`.** La passer fait refuser la
  commande avant même d'interroger la carte. *(mesuré, v0.8.1.22)*
- **libx265 en 4K : 0,78 image/s**, soit ~70 h pour un long métrage.
  Praticable en 1080p seulement. *(mesuré)*
- Un ffmpeg peut être construit sans libx265 : `ffmpeg -encoders | findstr x265`.

## Profondeur : 10 bits dès que la sortie est HDR

Sur une courbe PQ, du 8 bits étale 10 bits de dégradés sur 256 niveaux :
**banding garanti** dans les ciels et les fondus.

- Sortie HDR : `yuv420p10le` (libx265) ou `p010le` (NVENC, QSV, AMF), `-profile:v main10`.
  QSV : HDR10 conservé à travers `hevc_qsv` (BT.2020, PQ, écran de mastering),
  source 4K ramenée en 1080p : écran de mastering identique à la source (la
  source n'a pas de MaxCLL). *(observé, i5-1135G7, v0.9.0.9)*
- **H264 n'a pas de profil 10 bits chez NVENC** : une source HDR ramenée en
  H264 reste en 8 bits. Ne concerne que les cibles sous 1080p.
- Le 10 bits ne coûte pas de qualité quand il dépense moins : sur une
  animation, 10 bits à 2 911k donne SSIM **0,9991**, 8 bits à 4 727k donne
  **0,9970**. Le 8 bits consomme 62 % de bits en plus pour un résultat moins
  fidèle. *(mesuré, v0.8.1.24)*

## Contrôle de débit

Le débit d'un profil est une **cible moyenne**, jamais un plancher.

### NVENC : VBR avec marge

`-b:v <cible> -maxrate <cible × 1,5> -bufsize <2 × maxrate> -rc vbr`

Avec un plafond égal à la cible (`-rc cbr`), les scènes faciles tirent la
moyenne vers le bas et aucune scène difficile ne peut la remonter. Mesuré sur
180 s de film 2160p 10 bits, cible 6 035k : **92 %** du débit demandé avec
plafond égal, **99 %** avec la marge. *(mesuré)*

Un fichier très en dessous de sa cible n'est pas forcément un défaut : une
animation au dessin plat rend 54 % de la cible, parce que le contenu n'a pas
besoin des bits. *(mesuré)*

### QSV : la marge de NVENC, la meilleure des trois

IRIS lui passe la règle de NVENC sans `-rc` : un `-maxrate` au-dessus de
`-b:v` sélectionne le VBR chez QSV. *(documenté)* Résultat : **92-93 %** de la
cible sur deux épisodes (SDR 2 320k, HDR10 2 309k, cible 2 500k), plafond
3 750k bien appliqué. *(observé, i5-1135G7)* Ce n'est **pas** le comportement de
libx265 : serrer le plafond fait chuter le débit, le desserrer n'apporte rien.

| Plafond (extraits de 180 s, 1080p 10 bits, cible 2 500k) | t=600 | t=1800 |
|---|---|---|
| `maxrate` = cible | 74 % | — |
| `maxrate` = 1,5 × cible (IRIS) | 93 % | 96 % |
| `maxrate` = 2 × cible | 91 % | 95 % |

*(observé, i5-1135G7, voir [[2026-10-28-qsv-essai-plafond]])* La règle reste
celle de NVENC.

### libx265 : le réglage inverse

L'ABR de x265 répartit un budget selon son modèle de qualité. C'est un VBV
serré qui l'oblige à le dépenser. Desserrer le plafond le fait **sous-consommer**.

| Réglage (1080p 10 bits, extraits de 120 s, cible 5 000k) | t=1800 | t=4200 |
|---|---|---|
| `maxrate` = cible | 99,9 % | 100,0 % |
| `maxrate` = 1,5 × cible | 93,6 % | 99,9 % |
| ABR seul, sans VBV | 93,7 % | — |

*(mesuré)* Les deux branches doivent différer ; `tests/test_x265_debit.py` y veille.

## Mesurer le débit vidéo

Le seuil d'un profil se compare au débit de la **vidéo seule**, jamais à celui
du conteneur. Sur un film porteur d'un TrueHD : 9 611 kbps de conteneur pour
**5 364 kbps de vidéo**, soit 44 % d'écart. *(mesuré)*

Le débit vidéo est rarement annoncé directement, voir [[ffprobe]].

## Paliers de débit des profils

| Définition | Valeurs proposées |
|---|---|
| 720p | 1500, 2000k |
| 1080p | 2000, 2200, 2500, 3000, 3500, 5000k |
| 4K | 3000, 3500, 5000, 8000, 12000k |

Une source 1920×822 (cinémascope) est rattachée au palier 1080p : réglable par
`[decision] near_1080p_min_width / near_1080p_min_height`.

Une source est 4K dès 3200 px de large ou 1700 de haut (`VideoInfo.is_4k`) : les
WEB-DL scope recadrés sortent en 3832×1600, sous les 3840×2160 nominaux.

## Agrandissement par super-résolution

Une source sous le 1080p peut être agrandie au plus haut cadre qu'elle atteint
à ×2,7 au plus (480p, 720p, 1080p ; un DVD va en 1080p), par `libplacebo` sur
Vulkan et le shader mpv **ArtCNN C4F16**. Règle et clés de profil : spec
§ 6.1 et § 8.1 ; note [[source-conception-upscaling|de conception]].

**Le gain grandit avec le facteur** (*mesuré*, libvmaf, ffmpeg 8.1.3, *Sintel*
et *Tears of Steel* réduits, recompressés en x264 puis ré-agrandis) :

| Facteur | Une passe sur lanczos | Deux passes sur une passe |
|---|---|---|
| ×1,25 à ×1,5 | +1,0 à +2,3 VMAF, PSNR inchangé | +0,0 à +0,2 VMAF |
| ×2,67 (DVD → 1080p) | +4,1 à +5,8 VMAF, PSNR +0,1 à +0,6 dB | +0,9 à +1,2 VMAF |

Un écart visible commence vers 6 points de VMAF. ArtCNN C4F32 n'apporte rien
sur C4F16 pour 2 à 7 fois le coût ; la variante `_DN` lisse (moins de VMAF).
Jugement de l'utilisateur (*observé*) : à ×1,5 les différences sont « trop
subtiles » ; à ×2,67 en deux passes, « propre » sur le PC, confirmé sur le
téléviseur le 2026-11-04.

**Real-ESRGAN (`realesr-animevideov3`) est écarté pour la prise de vue
réelle** (*observé* sur planches, 2026-11-04) : visages « peints », rides et
inscriptions effacées. *Mesuré* : 4 à 7 dB de PSNR perdus, derrière ArtCNN à
×2,67. VMAF récompense par endroits ce qu'il invente.

Pièges (*mesuré*), qui donnent un fichier faux sans erreur :

- **Colorimétrie devinée.** Sans étiquette, `libplacebo` suppose BT.601 en SD
  et BT.709 en HD, et convertit l'une vers l'autre : jusqu'à 14 dB de PSNR
  perdus sur certaines images. Toujours poser `setparams` (colorimétrie lue,
  sinon choisie d'après la hauteur) avant `libplacebo`, courbe `bt709`.
- **Shaders inactifs sous ×1,3.** Leur ligne `//!WHEN` les saute : à ×1,25,
  les six shaders essayés rendent exactement `spline36`. IRIS livre une copie
  d'ArtCNN sans `//!WHEN` (licence MIT).
- **`normalize_sar` recadre** au lieu d'étirer : `reset_sar=1` est l'option voulue.
- Chemin du shader dans `-vf` : [[ffmpeg]].

**Vitesse** du seul agrandissement vers 1920×1066 (*mesuré* le 2026-11-04,
Cactus Jack 720×400, ffmpeg BtbN n8.1.3) :

| Carte | Une passe | Deux passes |
|---|---|---|
| RTX A4500 | 161 i/s | 30 i/s |
| Intel Iris Xe (i5-1135G7) | 38,2 i/s (1,5× le temps réel) | 9,3 i/s (0,37×, ~5 h 30 pour 2 h) |

Sur l'iGPU, le shader est le goulot, pas l'encodeur : `hevc_qsv` derrière
deux passes ne coûte presque rien (9,3 → 9,1 i/s). Sur la RTX, c'est l'encodeur.
L'extrait de comparaison du Dry run (2 min, une passe et deux passes
ensemble, `hevc_nvenc` 3 000 k) a pris 154 s sur la RTX A4500.

## Voir aussi

[[ffmpeg]] · [[ffprobe]] · [[hdr-dolby-vision]] · [[chaine-de-diffusion]] · [[noms-de-release]]
