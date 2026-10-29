---
type: source
maj: 2026-10-29
ingere: 2026-10-29
---

# Source : fichier collé et chaîne tout-carte (2026-10-29)

**Où** : [[2026-10-29-fichier-colle-tout-carte]]
**Nature** : relevés bruts, immuables

Un fichier signalé en échec par l'utilisateur, à l'origine de la reprise
hors puce de v0.9.1.2.

## Conclusions

- Un fichier fait de deux encodages collés change de paramètres en cours de
  route ; avec les images sur la carte, ffmpeg 8.1.2 ne sait pas reconstruire
  ses filtres au raccord et l'encodage s'arrête là.
- Ni `-reinit_filter 0` ni `setparams` n'y font rien ; descendre les images
  au processeur, si.
- Le décodage seul ne signale rien : un fichier sain au contrôle peut échouer.

## Pages alimentées

[[ffmpeg]] · [[pieges-et-lecons]]
