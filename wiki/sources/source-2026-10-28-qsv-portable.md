---
type: source
maj: 2026-10-28
ingere: 2026-10-28
---

# Source : Intel Quick Sync sur le portable (2026-10-28)

**Où** : [[2026-10-28-qsv-portable]]
**Nature** : relevés bruts, immuables

Essais d'encodage QSV sur un i5-1135G7 (Tiger Lake), à l'origine du profil
Intel Quick Sync de v0.9.0.9.

## Conclusions

- Tiger Lake encode en QSV le H.264, le HEVC 8 et 10 bits, le VP9 ; pas l'AV1.
- Le ffmpeg fourni avec IRIS contient les encodeurs QSV, pas SVT-AV1.
- Non vérifié : chaîne HDR10 réelle, débit obtenu, décodage `-hwaccel qsv`.

## Pages alimentées

[[codecs-video]]
