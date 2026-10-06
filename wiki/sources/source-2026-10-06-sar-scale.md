---
type: source
maj: 2026-10-06
ingere: 2026-10-06
---

# Source : SAR non carré après `scale`, transcodage Jellyfin

**Où** : [[2026-10-06-sar-scale]]
**Nature** : déclarations de l'utilisateur, mesures ffmpeg

Deux fichiers produits par IRIS transcodés par Jellyfin, raison « anamorphique »
(*observé*). Cause *mesurée* : `scale` avec `force_original_aspect_ratio` compense
l'arrondi des dimensions par un SAR proche de 1:1 mais pas égal. Corrigé en
v0.8.9.79 par `setsar=1`.

## Pages alimentées

[[jellyfin]] · [[ffmpeg]] · [[pieges-et-lecons]]
