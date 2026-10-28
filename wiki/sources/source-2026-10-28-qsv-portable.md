---
type: source
maj: 2026-10-28
ingere: 2026-10-28
---

# Source : Intel Quick Sync sur le portable (2026-10-28)

**Où** : [[2026-10-28-qsv-portable]], [[2026-10-28-qsv-portable-encodages]], [[2026-10-28-qsv-essai-plafond]], [[2026-10-28-qsv-source-hdr10]], [[2026-10-28-qsv-av1-refuse]]
**Nature** : relevés bruts, immuables

Essais d'encodage QSV sur un i5-1135G7 (Tiger Lake), à l'origine du profil
Intel Quick Sync de v0.9.0.9.

## Conclusions

- Tiger Lake encode en QSV le H.264, le HEVC 8 et 10 bits, le VP9 ; pas l'AV1.
- Le ffmpeg fourni avec IRIS contient les encodeurs QSV, pas SVT-AV1.
- IRIS v0.9.0.9 en QSV : SDR et HDR10 corrects ; HDR10 conservé (Main 10,
  BT.2020, PQ, écran de mastering). Débit à 92-93 % de la cible avec
  `-maxrate` à 1,5 × (deux épisodes). Plafond égal à la cible : 74 % ;
  à 2 × : 91-95 %. La marge à 1,5 × est la meilleure des trois.
- Écran de mastering identique à la source ; la source n'a pas de
  MaxCLL/MaxFALL, rien n'est donc perdu.
- Non vérifié : décodage `-hwaccel qsv`.

## Pages alimentées

[[codecs-video]]
