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

## [2026-09-24] ingest | Mise à jour de l'application

Relevés d'`updater.py` (v0.8.9.1) : cmd.exe reprend un `.bat` remplacé à
l'ancienne position, un bloc `( … )` protège la relance ; essai réel contre
l'API des releases GitHub, empreinte `digest` conforme. Source :
[[source-2026-09-24-mise-a-jour]]. Pages touchées : [[github]] (créée),
[[sous-processus]], [[pieges-et-lecons]].


## [2026-09-26] ingest | NVENC refusé après réinstallation du poste

Poste Shadow réinstallé, pilote 597.16 (API NVENC 13.0) : le ffmpeg git master,
gyan.dev 8.1.2 et BtbN n9.0 exigent l'API 13.1 (pilote ≥ 610) et refusent tout
NVENC ; BtbN n8.1.3 passe, 8 et 10 bits. Hypothèse « une release 8.1 suffit »
infirmée. Source : [[source-2026-09-26-nvenc-pilote]]. Pages touchées :
[[ffmpeg]], [[codecs-video]], [[pieges-et-lecons]], [[questions-ouvertes]].


## [2026-09-29] ingest | Arrêter un encodage en cours

UX-01/UX-02 (v0.8.9.5) : quitter l'écran d'encodage ne tuait pas ffmpeg,
et rien n'empêchait l'étape suivante de démarrer après un arrêt. Règle
ajoutée à [[sous-processus]]. Constat annexe, non généralisé : un worker
Textual relancé depuis un écran déjà dépilé ne démarre pas toujours (test
intermittent) — ne pas y placer un nettoyage.


## [2026-09-29] ingest | Formulaire de profil sous Textual 8

UX-03 (v0.8.9.7) : `Select.BLANK` ne vaut plus que `False`, la valeur vide
est `Select.NULL` ; un débit hors liste (3500k de `serie_basic`) laissait le
champ vide, et `tomli_w` refusait d'écrire la sentinelle. Pages touchées :
[[pieges-et-lecons]].


## [2026-09-30] ingest | WebVTT illisible par ffprobe dans un MKV

UX-21 (v0.8.9.28) : un `.vtt` muxé par mkvmerge 102 dans un MKV sort
`codec_name=unknown` sous ffprobe 8.1.2 ; mkvmerge le nomme « WebVTT ». Le nom
affiché passe par `nom_codec()` (« ? »). La copie par ffmpeg reste à
vérifier. Pages touchées : [[questions-ouvertes]].


## [2026-09-30] ingest | File d'encodage et modes Textual

IE-100 (v0.8.9.34 à v0.8.9.36) : le lot d'encodage vit dans son propre mode
Textual, la navigation dans un autre ; basculer suspend sans démonter, ffmpeg
continue. Deux pièges : Textual ne revient pas au mode `_default`, et `F11`
est captée par Windows Terminal — la bascule prend `F12`. Pages touchées :
[[pieges-et-lecons]].


## [2026-09-30] ingest | `hev1` contre `hvc1` sur le G3

IE-74 : deux paires (Seven Nation Army SDR, Project Hail Mary HDR10 8 bits),
original `hev1` et copie `hvc1` ; les quatre en lecture directe via Jellyfin,
sauts quasi instantanés. Question retirée. Pages touchées : [[conteneurs]],
[[lg-oled-g3]], [[questions-ouvertes]].
