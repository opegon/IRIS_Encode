---
type: source
maj: 2026-11-01
ingere: 2026-11-01
---

# Source : DV profil 5 vert, conversion par libplacebo (2026-11-01)

**Où** : [[2026-11-01-dv-p5-libplacebo]]
**Nature** : signalement de l'utilisateur, relevés bruts, immuables

## Conclusions

- Un profil 5 réencodé comme du YUV sort vert et violet, sans balise de
  couleur : la couche de base est en IPT-PQ.
- `libplacebo=apply_dolbyvision=1` (Vulkan) rend des couleurs justes, en
  HDR10 comme en SDR ; les balises de couleur suivent jusqu'au flux NVENC.
- Le gyan « essentials » n'a pas `libplacebo`, le BtbN GPL l'a.

## Pages alimentées

[[hdr-dolby-vision]] · [[ffmpeg]]
