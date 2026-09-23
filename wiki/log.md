---
type: log
---

# Journal du wiki

Registre chronologique, **en ajout seul** : une entrée par opération, la plus
récente en bas. Format fixe, lisible par `grep "^## \[" wiki/log.md` :

```
## [AAAA-MM-JJ] ingest|query|lint | titre
```

## [2026-09-24] ingest | Spécification, CHANGELOG, GUIDE, README

Première compilation du wiki à partir des quatre documents du dépôt
(spec v0.8.8.15, CHANGELOG jusqu'à v0.8.8.15). Pages créées : concepts
(codecs vidéo, HDR et DV, audio, sous-titres, conteneurs, synchronisation,
noms de release), synthèses (chaîne de diffusion, pièges et leçons, questions
ouvertes). Sources : [[source-spec]], [[source-changelog]], [[source-guide]],
[[source-readme]].

## [2026-09-24] ingest | Diagnostic du retrait Dolby Vision

Relevés de la session « son sans image puis plantage » : MKV sain, MP4 aux
horodatages perdus, filtre `dovi_rpu` vérifié, profils DV et sous-titres des
fichiers de test. Source : [[source-2026-09-24-diagnostic]]. Pages touchées :
[[hdr-dolby-vision]], [[conteneurs]], [[ffmpeg]], [[ffprobe]], [[mkvmerge]],
[[dovi-tool]], [[sous-titres]], [[lg-oled-g3]], [[pieges-et-lecons]],
[[questions-ouvertes]].

## [2026-09-24] ingest | Déclarations de l'utilisateur

LG OLED G3 ; Jellyfin sans transcodage matériel ; préférence des suffixes en
minuscules. Source : [[source-2026-09-24-utilisateur]]. Pages touchées :
[[chaine-de-diffusion]], [[jellyfin]], [[lg-oled-g3]], [[noms-de-release]].

## [2026-09-24] query | Pourquoi le téléviseur joue le son sans l'image

Réponse versée au wiki : la lecture directe est le seul critère sur un serveur
sans transcodage matériel ; les causes qui en font sortir ; la méthode de
diagnostic par le tableau de bord Jellyfin. Pages : [[chaine-de-diffusion]],
[[jellyfin]]. Réponse de l'utilisateur en attente ([[questions-ouvertes]]).

## [2026-09-24] lint | Alignement sur le modèle « LLM Wiki » de Karpathy

Réorganisation en couches : `raw/` immuable, pages de sources, entités,
concepts, synthèses ; [[index]] et journal ; frontmatter YAML ; liens
`[[…]]`. La page « Outils » est éclatée en entités ([[ffmpeg]], [[ffprobe]],
[[mkvmerge]], [[dovi-tool]], [[mpv]]) et en un concept ([[sous-processus]]) ;
[[jellyfin]], [[lg-oled-g3]] et [[opensubtitles]] reçoivent leur page. Les
conventions passent dans le schéma (`CLAUDE.md`). Contrôle automatique :
`tests/test_wiki.py` (liens, orphelins, index, frontmatter, journal).

## [2026-09-24] lint | Le schéma rejoint le wiki

Les conventions et les opérations quittent le `CLAUDE.md` du projet, exclu du
dépôt, pour [[SCHEMA]] : un clone du dépôt a désormais le wiki et son mode
d'emploi. `CLAUDE.md` n'en garde qu'un renvoi.
