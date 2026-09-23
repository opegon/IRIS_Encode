---
type: synthese
maj: 2026-09-24
sources:
  - "[[source-readme]]"
  - "[[source-2026-09-24-utilisateur]]"
  - "[[source-2026-09-24-diagnostic]]"
---

# Chaîne de diffusion

La bibliothèque est servie par Jellyfin et regardée surtout sur un téléviseur
LG. Une sortie IRIS n'est réussie que si toute la chaîne la lit **sans rien
transcoder**.

## Les maillons

| Maillon | Ce qu'il impose | Niveau |
|---|---|---|
| **[[jellyfin|Serveur Jellyfin]], sans transcodage matériel** | Tout format que le client refuse déclenche un transcodage **logiciel**, à chaque lecture. En 4K HDR, le processeur ne tient pas le temps réel. | observé |
| **[[lg-oled-g3|Téléviseur LG OLED G3]]** (2023, webOS 23), client Jellyfin webOS | Aucun audio sans perte (ni TrueHD, ni DTS-HD MA). Matroska capricieux. Dolby Vision profil 8 : remux HLS avec coupures audio. DTS : gel au saut sur les modèles 2023. | observé (README) |
| **Barre de son en eARC** | Décode tout. Mais dès que le téléviseur mixe ses propres haut-parleurs avec elle, c'est lui qui décode, et aucun flux sans perte ne l'atteint. | observé (README) |
| **Clients iOS (Swiftfin)** | Permissifs via VLCKit, qui lit le MKV et le DTS. Le lecteur natif d'Apple est plus strict et ne sait pas changer de piste audio : inutilisable sur un fichier multilingue. | observé (README) |

Le G3 lit le Dolby Vision nativement et **ignore le HDR10+** : le laisser dans
le flux ne gêne pas. *(supposé : connaissance générale des téléviseurs LG, pas
vérifié ici)*

## Le seul jeu de formats que tout le monde accepte

**HEVC en HDR10 (10 bits), audio E-AC3, sous-titres texte.**

Toute la chaîne le lit sans qu'aucune machine ne retouche rien. L'E-AC3 est
décodé nativement par le téléviseur et transporté en eARC vers la barre de son.
L'AC3 reste le repli universel. Voir [[audio|Audio]], [[sous-titres|Sous-titres]].

## Ce qui fait sortir Jellyfin de la lecture directe

| Cause | Effet |
|---|---|
| Sous-titre image (PGS, VobSub) sélectionné | Incrustation dans l'image, donc **transcodage vidéo complet** |
| Audio sans perte (TrueHD, DTS-HD MA), ou DTS sur le G3 | Transcodage audio. Peu coûteux seul, mais peut entraîner un remux HLS |
| Dolby Vision profil 8 sur le client webOS | Remux HLS, coupures audio |
| Conteneur ou codec non déclaré lisible par le client | Remux ou transcodage |
| Débit au-dessus de la limite réglée dans le client | Transcodage pour réduire le débit |

Sans transcodage matériel, **tout transcodage vidéo d'une source 4K est
perdu d'avance**.

## Symptôme : le son part, l'image ne vient pas, puis plantage

*Rapporté le 2026-09-24 sur des retraits du Dolby Vision (observé).*

Deux explications, de nature différente :

1. **Fichier cassé** : un MP4 dont les images ont perdu leurs horodatages.
   Cause trouvée et corrigée en v0.8.8.15 (voir
   [[hdr-dolby-vision#Retrait du RPU|HDR et Dolby Vision]],
   [[conteneurs#Horodatages|Conteneurs]]).
2. **Transcodage intenable** : Jellyfin sort de la lecture directe, le serveur
   envoie le son, plus léger, mais n'arrive pas à produire la vidéo 4K en
   temps réel, et le client abandonne.

Pour les départager, voir ci-dessous. Le résultat est en attente, voir
[[questions-ouvertes|Questions ouvertes]].

## Diagnostiquer une lecture qui échoue

Ne rien modifier dans le code avant de savoir **ce que Jellyfin a fait** :
méthode de lecture et raison du transcodage, dans le tableau de bord
([[jellyfin#Diagnostiquer]]).

Lecture directe et plantage quand même : le fichier lui-même est en cause.
Inspecter ses paquets avec [[ffprobe]].

## Voir aussi

[[jellyfin]] · [[lg-oled-g3]] · [[audio]] · [[sous-titres]] · [[conteneurs]] · [[hdr-dolby-vision]] · [[questions-ouvertes]]
