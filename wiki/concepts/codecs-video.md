---
type: concept
maj: 2026-09-24
sources:
  - "[[source-spec]]"
  - "[[source-changelog]]"
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
| Windows sans NVIDIA, Linux | `libx265` | `libx264` | `libaom-av1` |
| macOS | `hevc_videotoolbox` | `h264_videotoolbox` | `libaom-av1` |

- **NVENC n'encode l'AV1 qu'à partir d'Ada (RTX 40).** Une carte antérieure ne
  le dit qu'au moment d'échouer : « No capable devices found ». Les encodeurs
  sont donc **sondés au lancement** (ouverts sur une image, ~0,7 s) plutôt que
  déduits du modèle de carte. *(mesuré : RTX A4500, `av1_nvenc` absent)*
- **`av1_nvenc` n'a pas d'option `-profile`.** La passer fait refuser la
  commande avant même d'interroger la carte. *(mesuré, v0.8.1.22)*
- **libx265 en 4K : 0,78 image/s**, soit ~70 h pour un long métrage.
  Praticable en 1080p seulement. *(mesuré)*
- Un ffmpeg peut être construit sans libx265 : `ffmpeg -encoders | findstr x265`.

## Profondeur : 10 bits dès que la sortie est HDR

Sur une courbe PQ, du 8 bits étale 10 bits de dégradés sur 256 niveaux :
**banding garanti** dans les ciels et les fondus.

- Sortie HDR : `yuv420p10le` (libx265) ou `p010le` (NVENC), `-profile:v main10`.
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

## Voir aussi

[[ffmpeg]] · [[ffprobe]] · [[hdr-dolby-vision]] · [[chaine-de-diffusion]] · [[noms-de-release]]
