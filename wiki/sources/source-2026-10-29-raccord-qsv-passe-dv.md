---
type: source
maj: 2026-10-29
ingere: 2026-10-29
---

# Source : raccord, Quick Sync et passe DV (2026-10-29)

**Où** : [[2026-10-29-raccord-qsv-passe-dv]], [[2026-10-29-raccord-qsv-durees]]
**Nature** : relevés bruts, immuables

## Conclusions

- `vpp_qsv` passe le raccord qui arrête `scale_cuda` (observé, un fichier) :
  sortie aux durées exactes de la source, vidéo comme audio.
- La passe vidéo DV sur NVIDIA, sans aucun filtre, s'arrête au raccord comme
  le chemin standard ; son ancien chemin (`-pix_fmt p010le`) passe.

## Pages alimentées

[[ffmpeg]]
