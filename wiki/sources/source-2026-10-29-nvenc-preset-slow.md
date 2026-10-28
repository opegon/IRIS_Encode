---
type: source
maj: 2026-10-29
ingere: 2026-10-29
---

# Source : DV → HDR10 en 4K, preset slow (2026-10-29)

**Où** : [[2026-10-29-nvenc-preset-slow-dv-hdr10]]
**Nature** : relevés bruts, immuables

## Conclusions

- Un réencodage DV → HDR10 par NVENC ne garde aucune donnée Dolby Vision
  (ni RPU, ni configuration) ; HDR10 statique conservé. dovi_tool n'y sert
  pas.
- En preset `slow` et en 4K, l'encodeur limite : garder les images sur la
  carte ne fait rien gagner (38 s dans les deux cas).

## Pages alimentées

[[codecs-video]]
