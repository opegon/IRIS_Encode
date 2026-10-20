---
type: source
maj: 2026-10-20
ingere: 2026-10-20
---

# Source : `.ts` IPTV et paquet AAC corrompu

**Où** : [[2026-10-20-ts-aac-corrompu]]
**Nature** : mesures de session sur trois `.ts` fournis par l'utilisateur, puis
sur un `.ts` de synthèse

Un seul paquet TS audio perdu à la réception suffit à faire échouer la recopie
de l'AAC en MP4 (`aac_adtstoasc`). `-fflags +discardcorrupt` en entrée écarte
le paquet et sauve la sortie entière. Correctif : v0.9.0.5.

## Pages alimentées

[[audio]] · [[ffmpeg]]
