---
type: source
maj: 2026-09-24
ingere: 2026-09-24
---

# Source : Spécification fonctionnelle

**Où** : `iris_encode_spec.md` (dans le dépôt)
**Nature** : fichier du dépôt, versionné (en-tête 0.8.8.16 au moment de l'ingestion)

Référence de **ce que fait le code**, section par section. Riche en mesures
faites pendant le développement, rangées à côté de la fonction concernée.

## Ce qui en a été tiré

| Section | Pages alimentées |
|---|---|
| § 4 Preflight, § 17 portabilité et licences | [[sous-processus]], [[ffmpeg]], [[mkvmerge]], [[dovi-tool]], [[mpv]] |
| § 6 profils, § 8.1–8.4 décision vidéo et DV | [[codecs-video]], [[hdr-dolby-vision]] |
| § 7 Dolby Vision | [[hdr-dolby-vision]], [[dovi-tool]] |
| § 8.5 audio | [[audio]] |
| § 8.6 sous-titres et conteneur | [[sous-titres]], [[conteneurs]] |
| § 8.7 nommage | [[noms-de-release]] |
| § 9 pistes externes, pièges | [[mkvmerge]], [[synchronisation]], [[sous-titres]] |
| § 9.8 OpenSubtitles | [[opensubtitles]] |
| § 9bis collage | [[conteneurs]], [[mkvmerge]] |
| § 10 mesure du décalage | [[synchronisation]] |
| § 11 plateformes, § 12 encodeur | [[codecs-video]], [[audio]], [[conteneurs]] |
| § 15 scanner | [[ffprobe]], [[codecs-video]] |

La spec reste la source pour le détail d'implémentation : le wiki y renvoie
(`spec § 7.3`) sans le recopier.
