---
type: source
maj: 2026-11-13
ingere: 2026-11-13
---

# Source : une lecture arrêtée par le greffon TranscodeKiller

**Où** : [[2026-11-13-jellyfin-transcodekiller]]
**Nature** : journal du serveur Jellyfin 10.11.11 et log ffmpeg, fournis par
l'utilisateur ; client web dans Chrome 151 sous Windows

Une sortie IRIS (HEVC HDR10, deux E-AC3 5.1, `mov_text`) « plante au bout de
quelques secondes » dans le client web. Le journal montre :

- Chrome ne lit pas l'E-AC3 : Jellyfin réempaquette en HLS, vidéo recopiée,
  audio converti en AAC stéréo ;
- le greffon **TranscodeKiller** du serveur tue ce ffmpeg 1,3 s après son
  lancement, puis la relance de 6,5 s, puis toute la session ; le client
  rapporte l'arrêt à 0 ms ;
- ffmpeg sort chaque fois avec le code 0 : le fichier ne cause aucune erreur.

## Pages alimentées

[[jellyfin]] · [[chaine-de-diffusion]]
