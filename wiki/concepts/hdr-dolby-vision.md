---
type: concept
maj: 2026-10-03
sources:
  - "[[source-spec]]"
  - "[[source-changelog]]"
  - "[[source-2026-09-24-diagnostic]]"
  - "[[source-2026-10-03-dv81-mp4]]"
---

# HDR et Dolby Vision

## HDR10 et HDR10+

- **HDR10** : courbe PQ (`smpte2084`), primaires BT.2020, matrice `bt2020nc`,
  10 bits. Métadonnées **statiques** dans des SEI du flux HEVC :
  - *master display* : `G(8500,39850)B(6550,2300)R(35400,14600)WP(15635,16450)L(10000000,50)`
  - *MaxCLL / MaxFALL* : `988,382`

  Certains téléviseurs les exigent pour appliquer leur tone mapping.
- **HDR10+** : métadonnées **dynamiques** en SEI (ITU-T T.35), par-dessus une
  base HDR10. Le retrait du RPU Dolby Vision le laisse intact ; **aucun
  réencodage ne le conserve**. *(mesuré)*
- Ces métadonnées se lisent **dans les SEI, par ffprobe**. Elles valent pour
  toute source HDR, Dolby Vision ou non, et la lecture est trois fois moins
  chère que l'extraction du RPU (0,62 s contre 1,86 s par fichier).
  *(mesuré, v0.8.1.19)*
- Un `max_content` / `max_average` à `0,0` veut dire « non mesuré » : ne rien
  injecter plutôt qu'annoncer un pic lumineux nul.

## Dolby Vision : couche de base, RPU, couche d'amélioration

Un flux Dolby Vision HEVC est fait de trois choses :

| Élément | Où il vit | Rôle |
|---|---|---|
| **Couche de base (BL)** | tranches d'image HEVC ordinaires | l'image que lit un appareil sans Dolby Vision |
| **RPU** | NAL de type **62**, un par image, entre les tranches | métadonnées dynamiques Dolby Vision |
| **Couche d'amélioration (EL)** | NAL de type **63** dans une piste unique (profil 7), ou piste séparée | complément d'image du profil 7 |

Le conteneur porte en plus un **enregistrement de configuration DV**
(`dvcC`/`dvvC` en MP4, `BlockAdditionMapping` en MKV), que ffprobe affiche en
`DOVI configuration record`. *(mesuré : comptage des NAL sur Kingdom of the
Planet of the Apes, P8.1)*

**En MP4, ffmpeg n'écrit `dvcC` qu'avec `-strict unofficial`.** Sans l'option,
une copie `-c copy` garde le RPU dans le flux mais perd l'enregistrement : pas
de Dolby Vision pour le lecteur. Un MP4 écrit depuis un flux HEVC brut (Annex-B)
n'a pas `dvcC` même avec l'option : ffmpeg n'y trouve pas la configuration. Il
faut partir d'un conteneur qui la porte (MKV de mkvmerge). Étiquette : `hvc1`
lu en Dolby Vision par le G3, `dvh1` refusé ([[lg-oled-g3]]). *(mesuré,
ffmpeg 8.1.2, 2026-10-03 ; corrigé dans IRIS en v0.8.9.49)*

**Le RPU n'est pas une piste.** Aucun `-map` ne le laisse passer : tout
réencodage le détruit.

## Profils

Le sous-profil se lit dans `dv_bl_signal_compatibility_id` : il dit ce qu'est
la couche de base.

| Profil | Couche de base | Retirer le RPU donne | Éligible |
|---|---|---|---|
| **8.1** (compat 1) | HDR10 | un HDR10 valide | retrait et réencodage DV |
| **7** (compat 6, UHD Blu-ray) | HDR10 + couche d'amélioration | un HDR10 valide, si l'EL part aussi | retrait par `dovi_tool` seulement |
| 8.2 (compat 2) | SDR | du SDR | non |
| **8.4** (compat 4) | HLG | du HLG, pas du HDR10 | non |
| **5** (compat 0) | IPT-PQ, propre à Dolby | une image **aux couleurs fausses** (violet/vert) | non |
| 10 | AV1 | — | non (le chemin est HEVC) |

Un profil 8 sans compatibilité annoncée n'est pas deviné.

Relevé sur `resources_files` : Kingdom, Starship Troopers et Watchmen en
**P8.1** ; Good Luck Have Fun Don't Die en **P5**. Aucun échantillon P7.

## Trois traitements

### Retrait du RPU

*Quand le profil demande `hdr10` et qu'il n'y a rien d'autre à réencoder
(spec § 7.3).*

Aucune image recalculée : la sortie décode **bit à bit** comme la source
(`framemd5` concordant). Durée du conteneur inchangée, HDR10+, master display
et MaxCLL conservés. Un film 4K de 5,7 Go traité en **2 min 16 s**, contre
1 h 40 en NVENC et **74 h** en libx265 pour un réencodage. *(mesuré, v0.8.1.6)*

Deux chemins selon le conteneur :

| Sortie | Chemin | Horodatages |
|---|---|---|
| **MKV** | ffmpeg extrait le flux brut → `dovi_tool remove` → mkvmerge remuxe | mkvmerge les reconstitue : paquets identiques à la source, NAL 62 en moins *(mesuré)* |
| **MP4** | une passe ffmpeg depuis la source, `-c copy -bsf:v dovi_rpu=strip=1` | ceux de la source, conservés *(mesuré, v0.8.8.15)* |

**Le piège du MP4 (v0.8.1.20 à v0.8.8.14).** Le MP4 était recomposé par
ffmpeg à partir du **flux brut** Annex-B. Un flux brut ne porte aucun
horodatage : ffmpeg écrivait PTS = DTS sur chaque image (« pts has no value »,
1 444 fois sur une minute d'Avatar). Pour un flux à images B
(`has_b_frames=4`), cela donne un ordre d'affichage faux et une cadence
irrégulière (0,035 s au lieu de 0,0417 s). Symptôme sur le téléviseur : le son
sans l'image, puis un plantage. *(mesuré ; symptôme observé)*

Le filtre `dovi_rpu=strip=1` (ffmpeg **7.1+**) retire les NAL 62 **et**
l'enregistrement de configuration DV. Vérifié sur Kingdom (90 s) : 2 157 images
sur 2 157, horodatages identiques à la source, 0 NAL 62/63, SEI HDR10/HDR10+
conservés, décodage complet sans erreur. *(mesuré, ffmpeg 8.1.2)*

**Le profil 7 reste en MKV** : `dovi_tool remove` retire RPU **et** couche
d'amélioration (*documenté* : « Removes the enhancement layer and RPU data »).
Rien ne garantit que le filtre ffmpeg retire l'EL : voir
[[questions-ouvertes|Questions ouvertes]].

### Réencodage qui garde le Dolby Vision

*Profil en `dv`, spec § 7.4.*

Le RPU est sorti avant l'encodage et remis après :
`extract-rpu` → (P7 : `convert -m 2`) → encodage → `inject-rpu` → mkvmerge.

Trois conditions, sans quoi la vidéo est **recopiée** (« → DV (copie) ») :

| Condition | Pourquoi |
|---|---|
| couche de base HDR10 (8.1 ou 7) | réinjecter le RPU d'un P5 ou d'un 8.4 dans du HDR10 donne des couleurs fausses |
| **aucun redimensionnement, aucun filtre** | le RPU est indexé image par image et décrit un cadrage ; le nombre d'images doit correspondre |
| dovi_tool et mkvmerge présents | outils du pipeline |

- La sortie est **toujours en MKV** : porter le RPU en MP4 demanderait de
  réécrire les en-têtes.
- ffmpeg recopie primaires, courbe PQ, master display et MaxCLL de la source
  vers la sortie en SEI, **y compris à travers NVENC**. *(mesuré)*
- RPU réextrait **octet pour octet identique** après injection, nombre d'images
  conservé. *(mesuré, mais sur 48 images de mire synthétique seulement)*

### Conversion en SDR

*Profil en `sdr`.* Tone mapping CPU, lent :

```
zscale=t=linear:npl=100, format=gbrpf32le, zscale=p=bt709,
tonemap=tonemap=hable:desat=0, zscale=t=bt709:m=bt709:r=tv, format=yuv420p
```

La sortie est en **8 bits** (`yuv420p`). `DV`, `HDR`, `HDR10+` et `10bit`
disparaissent du nom. Un profil sans clé `dolby_vision` se rabat sur `sdr` :
un HDR10 délavé sur un téléviseur qui ne le gère pas est pire qu'un SDR propre.

## Paramètres x265 pour un HDR10 propre

```
hdr10-opt=1:repeat-headers=1:colorprim=bt2020:transfer=smpte2084:
colormatrix=bt2020nc:chromaloc=2:master-display=…:max-cll=…
```

Aucun encodeur de carte graphique n'expose master display et MaxCLL : c'est la
raison d'être du mode `hdr10_quality = "quality"` (libx265, voir
[[codecs-video#Encodeurs|Codecs vidéo]] pour son coût).

## Voir aussi

[[dovi-tool]] · [[ffmpeg]] · [[mkvmerge]] · [[ffprobe]] · [[lg-oled-g3]] · [[codecs-video]] · [[conteneurs]]
