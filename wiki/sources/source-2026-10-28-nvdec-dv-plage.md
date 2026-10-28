---
type: source
maj: 2026-10-28
ingere: 2026-10-28
---

# Source : passe DV sur la carte, plage pleine (2026-10-28)

**Où** : [[2026-10-28-nvdec-dv-plage]]
**Nature** : relevés bruts, immuables

Essais sur la RTX A4500, à l'origine de v0.9.0.13.

## Conclusions

- La passe vidéo du réencodage DV avec `-hwaccel cuda` seul est plus lente
  que tout au processeur (21 s contre 18) ; sur la carte, 13,5 s, flux
  identique bit à bit.
- `scale_cuda` traite la plage pleine comme `scale` : valeurs 0-255 gardées,
  étiquette `pc` dans le flux.

## Pages alimentées

[[codecs-video]] · [[ffmpeg]]
