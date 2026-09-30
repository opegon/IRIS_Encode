---
type: source
maj: 2026-09-26
ingere: 2026-09-26
---

# Source : NVENC refusé après réinstallation (2026-09-26)

**Où** : [[2026-09-26-nvenc-pilote]]
**Nature** : relevés bruts d'une session, immuables

Diagnostic d'un `hevc_nvenc` absent d'IRIS_Encode sur un poste Shadow
réinstallé (RTX A4500, pilote 597.16).

## Conclusions

- Les builds ffmpeg compilés avec l'API NVENC 13.1 exigent un pilote 610 ou
  plus récent ; sous 597, NVENC entier est refusé.
- Le numéro de ffmpeg n'est pas le bon indicateur : gyan.dev 8.1.2 échoue,
  BtbN n8.1.3 réussit.
- La cause n'apparaît qu'en `-loglevel verbose`.

## Pages alimentées

[[ffmpeg]] · [[codecs-video]] · [[pieges-et-lecons]] · [[questions-ouvertes]]
