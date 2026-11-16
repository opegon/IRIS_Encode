# Mesure IE-201 : options de qualité NVENC en HEVC SDR, VMAF — 2026-11-16

Poste : RTX A4500 (Ampere), pilote 616.92, ffmpeg BtbN n8.1.3 (libvmaf).
Commande de base = celle d'IRIS pour une source H.264 1080p sans
redimensionnement : `-hwaccel cuda -hwaccel_output_format cuda`,
`scale_cuda=format=nv12` (`p010le` en 10 bits), `hevc_nvenc -b:v 3500000
-maxrate 5250000 -bufsize 10500k -rc vbr -preset <p> -profile:v main|main10`.

Extraits de 60 s (copie de flux, coupure à l'image clé), films libres Blender :

| Extrait | Source | Début | YAVG moyen |
|---|---|---|---|
| tos_jour | *Tears of Steel* 1080p (H.264 Main, 1920×800, 6,2 Mb/s) | 270 s | 105 |
| tos_sombre | idem | 600 s | 52 |
| sintel_clair | *Sintel* 1080p (H.264 High, 1920×818, ≈10 Mb/s) | 270 s | 124 |
| sintel_sombre | idem | 600 s | 33 |

VMAF (modèle par défaut v0.6.1) et PSNR-Y contre l'extrait source, les deux
en `yuv420p10le`, **appariés par rang d'image** (`settb=1/24,setpts=N`) :
l'appariement par horodatage (ms arrondies 0,083/0,084) décalait une image
sur trois (VMAF 73 au lieu de 97). Même nombre d'images des deux côtés.

## Correspondance des presets (sorties identiques bit à bit, 10 s)

`fast` = **P1** ; `medium` = **P4** ; `slow` = **P7 + `-multipass fullres`**.

## Résultats : VMAF moyen (1er centile)

| Preset | Réglage | tos_jour | tos_sombre | sintel_clair | sintel_sombre |
|---|---|---|---|---|---|
| fast | base (état actuel) | 97,55 (89,88) | 94,45 (79,86) | 99,00 (94,32) | 96,04 (89,51) |
| fast | main10 | 97,89 (90,33) | 94,71 (79,84) | 99,18 (95,02) | 96,45 (90,81) |
| fast | `-spatial-aq 1` | 97,06 | 94,11 | 98,73 | 95,40 |
| fast | `-temporal-aq 1` | 97,55 | 94,64 | 99,00 | 96,03 |
| fast | `-rc-lookahead 32` | 97,55 | 94,49 | 99,07 | 96,20 |
| fast | `-b_ref_mode middle` | = base, bit à bit | = base | = base | = base |
| fast | `-multipass fullres` | = base, bit à bit | = base | = base | = base |
| fast | main10 + taq | 97,89 | 94,96 | 99,16 | 96,45 |
| fast | main10 + taq + la32 | 97,90 (89,97) | 95,08 (81,75) | 99,24 (95,22) | 96,59 (91,22) |
| fast | tout, 8 bits | 97,13 | 94,54 | 98,82 | 95,53 |
| fast | tout, main10 | 97,51 | 94,78 | 99,02 | 96,02 |
| medium | base | 97,59 (90,56) | 95,33 (80,29) | 99,08 (94,34) | 96,17 (90,03) |
| medium | main10 | 97,77 | 95,44 | 99,17 | 96,45 |
| medium | `-spatial-aq 1` | 97,20 | 95,13 | 98,80 | 95,59 |
| medium | `-temporal-aq 1` | 97,57 | 95,47 | 99,07 | 96,15 |
| medium | `-rc-lookahead 32` | 97,69 | 95,38 | 99,12 | 96,25 |
| medium | bref / mp | = base, bit à bit | | | |
| medium | main10 + taq + la32 | 97,87 (90,77) | 95,65 (82,26) | 99,22 (94,75) | 96,56 (90,58) |
| medium | tout, main10 | 97,49 | 95,43 | 98,95 | 96,02 |
| slow | base | 97,68 (90,75) | 95,58 (81,35) | 99,14 (94,62) | 96,26 (90,07) |
| slow | main10 | 97,86 | 95,69 | 99,24 | 96,55 |
| slow | main10 + taq + la32 | 97,93 | 95,83 | 99,28 | 96,67 |

- `fast` (P1) n'émet aucune image B (`IPPP…`) : `-b_ref_mode` sans objet.
  `-multipass` ignoré en `fast` et en `medium` (alias une passe de ffmpeg).
- Débit tenu : 97 à 108 % de la cible, sans écart dû aux options (Sintel
  ≈ 106 % déjà en base).
- Vitesse (temps réel × , horloge murale, décodage compris) : `fast` et
  `medium` ≈ 13 à 17 ×, `slow` ≈ 5 à 5,7 ×. Le lookahead coûte ≈ 10 %. Les
  vitesses en `fast` sont **bruitées** (13 à 27 × pour des réglages voisins) :
  à remesurer à part avant de comparer `fast` et `medium`.
- `-spatial-aq` perd partout en VMAF/PSNR ; VMAF pénalise cette option par
  construction (redistribution vers les aplats) : non jugé à l'œil.
- Tous les écarts sont < 1 point VMAF.

## Propositions faites à l'utilisateur (en attente de décision)

1. Main10 pour toute sortie HEVC NVENC, SDR compris (seul gain net et
   régulier, gratuit). QSV, AMF, libx265 inchangés.
2. `-rc-lookahead 32` : optionnel, ≈ +0,1 VMAF pour ≈ 10 % de vitesse.
3. Hors IE-201 : `movie_1080p_basic` de `fast` à `medium` (+0,9 VMAF sur
   tos_sombre), après une mesure de vitesse propre.
4. Écartés : `-temporal-aq` (nul), `-b_ref_mode`, `-multipass` (sans effet),
   `-spatial-aq` (sauf jugement visuel, planche proposée).

Banc : `banc.py`, résultats `resultats.jsonl` (92 lignes), dans le
scratchpad de la session (`…\scratchpad\ie201\`), non conservés.
