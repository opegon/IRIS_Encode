---
type: source
maj: 2026-10-28
ingere: 2026-10-28
---

# Source : décodage matériel Quick Sync (2026-10-28)

**Où** : [[2026-10-28-qsv-decodage-materiel]]
**Nature** : relevés bruts, immuables

Essais de décodage matériel sur le portable (i5-1135G7), à l'origine de la
chaîne tout-puce de v0.9.0.11.

## Conclusions

- Décoder sur la puce puis filtrer au processeur ralentit (`d3d11va` : 76 s
  contre 60 s) ; `-hwaccel qsv` avec un filtre processeur échoue.
- Décoder, réduire (`vpp_qsv`) et encoder sur la puce : 18 s, HDR10 et écran
  de mastering conservés.
- Une mise à l'échelle matérielle garde un SAR compensateur ; `-aspect` le
  ramène à 1:1.
- L'arrondi de `scale` : au pair le plus proche, mi-chemin vers le haut.

## Pages alimentées

[[codecs-video]] · [[ffmpeg]]
