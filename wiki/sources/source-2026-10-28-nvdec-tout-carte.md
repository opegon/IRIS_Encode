---
type: source
maj: 2026-10-28
ingere: 2026-10-28
---

# Source : décodage NVDEC et `scale_cuda` (2026-10-28)

**Où** : [[2026-10-28-nvdec-tout-carte]]
**Nature** : relevés bruts, immuables

Essais sur la RTX A4500 du poste de développement, à l'origine de la chaîne
tout-carte NVIDIA de v0.9.0.12.

## Conclusions

- `-hwaccel cuda` suivi de `scale` au processeur ne gagne rien : 28 s, comme
  sans décodage matériel, pour 60 s de 4K HDR10 → 1080p ; plus lent en H264
  SDR (6,1 s contre 4,0 s).
- Décoder, réduire (`scale_cuda`) et encoder sur la carte : 5,6 s, sorties
  identiques (dimensions, SAR avec `-aspect`, HDR10, mastering, nombre
  d'images), PSNR 48-53 dB contre le chemin processeur.
- `scale_cuda` convertit 8 ↔ 10 bits et accepte VP9 et AV1 décodés.

## Pages alimentées

[[codecs-video]] · [[ffmpeg]]
