---
type: source
maj: 2026-11-04
ingere: 2026-11-04
---

# Source : libplacebo, chemin du shader et sonde Vulkan (2026-11-04)

**Où** : [[2026-11-04-libplacebo-shader-chemin]]
**Nature** : essais de la session IE-168, relevés bruts, immuables

## Conclusions

- Un chemin dans `-vf` est relu à deux niveaux (graphe, puis options du
  filtre) ; chacun retire une barre d'échappement. `C:` doit s'écrire
  `C\:` sans apostrophes, ou `'C\:'` entre apostrophes.
- Un essai d'une image par libplacebo avec le shader dit si Vulkan et le
  shader marchent : environ 2 à 3,5 s.
- La chaîne de super-résolution d'IRIS encode de bout en bout en une et deux
  passes.

## Pages alimentées

[[ffmpeg]]
