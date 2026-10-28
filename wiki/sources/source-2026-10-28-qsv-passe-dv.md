---
type: source
maj: 2026-10-28
ingere: 2026-10-28
---

# Source : passe DV sur la puce Intel (2026-10-28)

**Où** : [[2026-10-28-qsv-passe-dv]]
**Nature** : relevés bruts, immuables

Essai sur le portable (i5-1135G7), à l'origine de v0.9.0.14.

## Conclusions

- Garder les images sur la puce dans la passe vidéo du réencodage DV :
  38 s contre 51, même nombre d'images, HDR10 conservé.
- Contrairement à NVIDIA, le flux n'est pas identique bit à bit : PSNR
  62,5 dB en moyenne, 56 dB au pire.

## Pages alimentées

[[codecs-video]]
