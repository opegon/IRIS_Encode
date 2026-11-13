---
type: entite
categorie: materiel
maj: 2026-11-13
sources:
  - "[[source-2026-11-13-transcodekiller]]"
  - "[[source-2026-10-06-sar-scale]]"
  - "[[source-2026-09-30-lecture]]"
  - "[[source-2026-09-24-utilisateur]]"
  - "[[source-readme]]"
---

# Jellyfin

Serveur multimédia de l'utilisateur. **Sans transcodage matériel.** *(observé)*
Place dans la chaîne : [[chaine-de-diffusion]].

## Ce qu'il fait d'un fichier

| Méthode | Coût |
|---|---|
| **Lecture directe** | aucun : le fichier part tel quel |
| Flux direct / remux | réempaquetage (HLS), léger mais source de coupures audio sur le client webOS |
| **Transcodage** | décodage et réencodage **logiciels** ; intenable en 4K HDR |

Tout format que le client ne déclare pas lisible déclenche un transcodage,
**à chaque lecture**. *(observé, README)*

## Ce qui le fait transcoder

- sous-titre image sélectionné : **incrustation**, donc transcodage vidéo
  complet ([[sous-titres]]) ;
- audio sans perte, ou DTS pour le [[lg-oled-g3]] ([[audio]]) ;
- Dolby Vision profil 8 vers le client webOS : remux HLS ;
- débit au-dessus de la limite du client ;
- vidéo **anamorphique** — tout SAR différent de 1:1, même 959:960 *(observé,
  sur deux sorties d'IRIS avant v0.8.9.79 ; [[ffmpeg]])*.

Qu'un PGS marqué forcé soit choisi d'office à côté d'un SRT forcé de même
langue est **supposé**, pas observé : IRIS ne lui en laisse plus l'occasion
([[sous-titres#Drapeaux par défaut et forcé|Sous-titres]]).

## Greffon TranscodeKiller

Le serveur porte le greffon **TranscodeKiller** : il arrête les sessions qui
transcodent, y compris un remux HLS dont seul l'audio est converti. Le
2026-11-13, dans le client web sous Chrome (qui ne lit pas l'E-AC3), il a tué
le ffmpeg 1,3 s après son lancement, puis sa relance, et la lecture s'est
arrêtée à 0 ms ; l'utilisateur l'a vu comme un fichier qui « plante au bout
de quelques secondes ». *(observé, [[source-2026-11-13-transcodekiller]])*
Les règles exactes du greffon (ce qu'il tue, ce qu'il laisse) ne sont pas
connues ici.

Un arrêt de lecture dans un navigateur se lit donc d'abord dans le journal du
serveur : une ligne `TranscodeKiller … Killing transcode process` met le
fichier hors de cause.

## Fichiers qu'il dépose

Une fois une vidéo référencée, Jellyfin écrit à côté d'elle des fichiers
nommés sur elle *(observé sur la bibliothèque de l'utilisateur, 2026-10-07)* :

```
<nom>.mkv
<nom>.nfo
<nom>-poster.jpg  <nom>-backdrop.jpg  <nom>-landscape.jpg  <nom>-logo.png
<nom>-thumb.jpg   (épisodes, et certains films)
season.nfo        (dossier de saison : à la saison, pas à un épisode)
```

Films côte à côte dans un dossier commun (`F:\_Aventures\Thunderbirds`) et
épisodes d'une saison (`S:\_Historiques\Un Village Français\Saison 1`)
suivent le même format. Quand IRIS supprime une source, ces annexes partent
avec elle (`core/annexes.py`, IE-116) ; `season.nfo`, les `.srt` et la sortie
restent — choix de l'utilisateur du 2026-10-07, pas d'option séparée : la
suppression suit `delete_source`.

## Diagnostiquer

Pendant la lecture, **tableau de bord → Activité** (appareils actifs) :
méthode de lecture et, en cas de transcodage, sa raison. Les journaux
`FFmpeg.Transcode-*.log` du serveur donnent la commande exacte.
*(documenté, fonctionnalité standard de Jellyfin)*
