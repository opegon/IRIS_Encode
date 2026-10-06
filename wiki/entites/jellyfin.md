---
type: entite
categorie: materiel
maj: 2026-10-06
sources:
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

## Diagnostiquer

Pendant la lecture, **tableau de bord → Activité** (appareils actifs) :
méthode de lecture et, en cas de transcodage, sa raison. Les journaux
`FFmpeg.Transcode-*.log` du serveur donnent la commande exacte.
*(documenté, fonctionnalité standard de Jellyfin)*
