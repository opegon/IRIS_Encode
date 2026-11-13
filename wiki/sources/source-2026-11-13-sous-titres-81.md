---
type: source
maj: 2026-11-13
ingere: 2026-11-13
---

# Source : sous-titres UTF-16 et `mov_text`, rejoués en ffmpeg 8.1.2

**Où** : [[2026-11-13-sous-titres-ffmpeg-81]]
**Nature** : mesures sur fichiers synthétiques, ffmpeg 8.1.2 (gyan.dev) et
mkvmerge v103.0 de `bin/`, poste Windows

Les deux comportements de ffmpeg relevés en 6.1.1 par la revue
([[source-2026-11-13-revue]]) se reproduisent dans le 8.1.2 que
l'application installe :

- un `mov_text` recopié vers Matroska est refusé ; `-c:s:N srt` sur la piste
  le convertit sans perte de texte ;
- un `.srt` UTF-16 à BOM est lu juste **sans** `-sub_charenc`, et détruit
  avec (`CP1252` comme `UTF-16`).

Côté mkvmerge, rien à corriger : il suit le BOM quel que soit
`--sub-charset`, et convertit seul un « Timed Text » en SubRip.

Corrections : v0.9.2.9 (IE-187, UTF-16) et IE-188 (`mov_text`).

## Pages alimentées

[[ffmpeg]] · [[mkvmerge]] · [[sous-titres]] · [[questions-ouvertes]]
