---
type: index
maj: 2026-10-06
---

# Index du wiki IRIS ENCODE

Catalogue de toutes les pages, une ligne chacune. Tenu à jour à chaque
ingestion. Conventions et opérations : [[SCHEMA]]. Historique : [[log]].

## Synthèses

| Page | Résumé |
|---|---|
| [[chaine-de-diffusion]] | Jellyfin sans transcodage matériel → LG G3 : le seul jeu de formats accepté partout, ce qui fait transcoder, diagnostic d'une lecture qui échoue |
| [[pieges-et-lecons]] | Défauts silencieux rencontrés, règles qui en sont sorties, hypothèses infirmées |
| [[questions-ouvertes]] | Ce qui reste à vérifier, et comment le trancher |

## Concepts

| Page | Résumé |
|---|---|
| [[codecs-video]] | Codecs lus sans transcodage, encodeurs, 10 bits, contrôle de débit NVENC et x265 |
| [[hdr-dolby-vision]] | HDR10, HDR10+, profils DV, RPU et couche d'amélioration ; retrait, réencodage, SDR |
| [[audio]] | Formats acceptés, plafonds AC3/E-AC3, repli 7.1, Atmos, pièges ffmpeg |
| [[sous-titres]] | Texte contre image, incrustation, drapeaux, codes de langue `fra`/`fre` |
| [[conteneurs]] | MP4 contre MKV, horodatages, chapitres, `hev1`/`hvc1`, collage |
| [[synchronisation]] | Décalage, dérive PAL, montages différents, recalage par plages |
| [[noms-de-release]] | Marques d'un nom de fichier, pièges d'analyse, ce qu'une conversion rend faux |
| [[localisation]] | Ce qui se traduit ou jamais, noms de piste selon la langue de la piste, glossaire et ses arbitrages |
| [[sous-processus]] | Règles pour lancer un outil externe : chemin, `stdin`, UTF-8, tubes, codes retour ; `.bat` réécrit en cours d'exécution |

## Entités

| Page | Résumé |
|---|---|
| [[ffmpeg]] | Encodage et remux ; API NVENC contre pilote ; filtres `dovi_rpu` et `hevc_mp4toannexb`, pièges d'horodatage et de spécificateurs |
| [[ffprobe]] | Analyse ; débit vidéo réel, sous-profil DV, paquets, comptage des NAL |
| [[mkvmerge]] | Remux Matroska ; `--gui-mode`, ID global des pistes, drapeau par défaut, collage |
| [[dovi-tool]] | Dolby Vision ; `extract-rpu`, `remove`, `inject-rpu`, `info` en JSON |
| [[mpv]] | Lecteur de contrôle ; délais audio et sous-titres, tolérance trompeuse |
| [[jellyfin]] | Serveur de l'utilisateur ; méthodes de lecture, causes de transcodage, diagnostic |
| [[lg-oled-g3]] | Téléviseur de l'utilisateur ; formats acceptés, symptômes constatés |
| [[opensubtitles]] | Service de sous-titres ; empreinte, pagination, quotas |
| [[github]] | Releases : API « Latest », empreinte `digest`, 60 appels par heure, archives d'IRIS |

## Sources

| Page | Résumé |
|---|---|
| [[source-spec]] | `iris_encode_spec.md` : ce que fait le code, mesures de développement |
| [[source-changelog]] | `CHANGELOG.md` : pourquoi chaque chose a changé, défauts silencieux |
| [[source-guide]] | `GUIDE.md` : procédures et cas rencontrés |
| [[source-readme]] | `README.md` : chaîne de diffusion de référence, prérequis |
| [[source-2026-09-24-diagnostic]] | Relevés du diagnostic « son sans image » sur le retrait DV |
| [[source-2026-09-24-utilisateur]] | Déclarations de l'utilisateur : G3, Jellyfin sans transcodage matériel |
| [[source-2026-09-24-mise-a-jour]] | Relevés d'`updater.py` : cmd.exe et les `.bat` réécrits, essai réel contre GitHub |
| [[source-2026-09-26-nvenc-pilote]] | NVENC refusé après réinstallation : API NVENC du build contre version du pilote |
| [[source-2026-09-30-hev1-hvc1]] | `hev1` contre `hvc1` sur le G3 : les deux en lecture directe |
| [[source-2026-10-06-sar-scale]] | SAR non carré après `scale`, transcodage Jellyfin « anamorphique » |
| [[source-2026-09-30-lecture]] | Politique du PGS forcé, réglage de débit du client webOS |
| [[source-2026-10-01-entrelacement]] | Audio écrite par blocs loin de la vidéo : arrêt à 32 s sur TV |
| [[source-2026-10-03-dv81-mp4]] | DV 8.1 en MP4 `hvc1` lu en direct sur le G3 ; `dvh1` et MKV refusés |
| [[source-2026-10-04-mov-text]] | `mov_text` : temps écrasés après un silence de plus de 2³¹ µs |
| [[source-2026-10-04-localisation]] | Audit de localisation et décisions de l'utilisateur : politique de traduction, glossaire |

## Brut (`raw/`, immuable)

| Fichier | Contenu |
|---|---|
| [[2026-09-24-diagnostic-retrait-dv]] | Commandes et sorties du diagnostic, telles quelles |
| [[2026-09-24-declarations-utilisateur]] | Citations de l'utilisateur |
| [[2026-09-24-mise-a-jour-application]] | Expérience cmd.exe, sortie de la mise à jour réelle |
| [[2026-09-26-nvenc-pilote]] | Builds ffmpeg essayés sous le pilote 597, sorties NVENC, sonde d'IRIS |
| [[2026-09-30-hev1-hvc1-g3]] | `hev1` et `hvc1` sur le G3 : paires testées, citations de l'utilisateur |
| [[2026-09-30-declarations-lecture]] | PGS forcé, débit du client webOS : citations de l'utilisateur |
| [[2026-10-01-entrelacement-audio]] | *Film K* : relevés d'entrelacement, variantes ffmpeg mesurées |
| [[2026-10-03-essai-dv81-mp4]] | Essai DV 8.1 MP4/MKV sur le G3 : citations de l'utilisateur, variantes audio |
| [[2026-10-04-mov-text-silence]] | *Film J* : VF forcée désynchronisée, seuil mesuré, contournement |
| [[2026-10-06-sar-scale]] | Transcodage « anamorphique » de deux sorties ; SAR mesurés avec et sans `setsar=1` |
| [[2026-10-04-decisions-localisation]] | Choix de l'utilisateur après l'audit de localisation : citations et options retenues |
