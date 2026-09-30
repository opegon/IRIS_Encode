---
type: entite
categorie: materiel
maj: 2026-09-30
sources:
  - "[[source-2026-09-24-utilisateur]]"
  - "[[source-2026-09-30-hev1-hvc1]]"
  - "[[source-readme]]"
---

# LG OLED G3

Téléviseur de l'utilisateur (2023, webOS 23), client Jellyfin webOS. Cible
principale des fichiers produits. Place dans la chaîne : [[chaine-de-diffusion]].

## Ce qu'il accepte

| Élément | Comportement | Niveau |
|---|---|---|
| HEVC Main 10, HDR10 | lu | observé |
| Dolby Vision | lu nativement | supposé |
| Dolby Vision profil 8 via le client Jellyfin | remux HLS, coupures audio | observé (README) |
| HDR10+ | ignoré, sans gêne | supposé |
| E-AC3, AC3, AAC | lus | observé (README) |
| TrueHD, DTS-HD MA | **refusés** | observé (README) |
| DTS | **gèle au saut** (modèles 2023) | observé (README) |
| Matroska | « capricieux » | observé (README) |
| MP4 HEVC `hev1` et `hvc1` | lecture directe via Jellyfin, sauts quasi instantanés ([[conteneurs#Tag HEVC en MP4 : `hev1` ou `hvc1`]]) | observé (2026-09-30) |
| HDR10 en 8 bits (`yuv420p`) | lecture directe, HDR10 reconnu | observé (2026-09-30) |

## Symptômes constatés

- **Son sans image, puis plantage quelques dizaines de secondes plus tard**,
  sur des fichiers issus du retrait du Dolby Vision (2026-09-24). Cause
  trouvée côté MP4 : horodatages perdus ([[hdr-dolby-vision#Retrait du RPU]]).
  Confirmation sur le téléviseur en attente ([[questions-ouvertes]]).
- Refus de fichiers dont la vidéo ne démarre pas à zéro (`-itsoffset`
  négatif), corrigé en v0.8.1.0 ([[conteneurs#Horodatages]]).

Le décodeur matériel est plus strict que [[mpv]] ou VLC : contrôler sur le
téléviseur, pas sur PC.
