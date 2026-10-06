---
type: entite
categorie: materiel
maj: 2026-10-06
sources:
  - "[[source-2026-09-24-utilisateur]]"
  - "[[source-2026-09-30-hev1-hvc1]]"
  - "[[source-2026-10-03-dv81-mp4]]"
  - "[[source-readme]]"
---

# LG OLED G3

Téléviseur de l'utilisateur (2023, webOS 23), client Jellyfin webOS. Cible
principale des fichiers produits. Place dans la chaîne : [[chaine-de-diffusion]].

## Ce qu'il accepte

| Élément | Comportement | Niveau |
|---|---|---|
| HEVC Main 10, HDR10 | lu | observé |
| Dolby Vision 8.1 en MP4 `hvc1` | **lecture directe**, logo « Dolby Vision » (et « + Dolby Atmos » avec un E-AC3 JOC), sauts corrects ([[source-2026-10-03-dv81-mp4]]) | observé (2026-10-03) |
| Dolby Vision 8.1 en MP4 `dvh1` | **ne se lance pas** | observé (2026-10-03) |
| Dolby Vision 8.1 en MKV (extrait 94 s, 2 E-AC3, 6 SRT) | **plante l'application** | observé (2026-10-03) |
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
  Correction confirmée sur le téléviseur le 2026-10-06 (IE-72,
  [[2026-10-06-declaration-ie72]]).
- Refus de fichiers dont la vidéo ne démarre pas à zéro (`-itsoffset`
  négatif), corrigé en v0.8.1.0 ([[conteneurs#Horodatages]]).

- **Son instable (« wobble »)**, une fois, sur un MP4 DV `hvc1` à deux pistes
  E-AC3 (7.1 fre + 5.1 Atmos eng), juste après un plantage de l'application
  sur un MKV (2026-10-03). **Non reproduit** à la relecture : lecture directe,
  son propre. Deux pistes E-AC3 en MP4 ne posent pas de problème.

Le décodeur matériel est plus strict que [[mpv]] ou VLC : contrôler sur le
téléviseur, pas sur PC.
