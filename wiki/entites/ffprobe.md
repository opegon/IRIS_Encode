---
type: entite
categorie: outil
maj: 2026-09-24
sources:
  - "[[source-spec]]"
  - "[[source-changelog]]"
  - "[[source-2026-09-24-diagnostic]]"
---

# ffprobe

Analyse des fichiers. Livré avec [[ffmpeg]], même version. Outil **essentiel**.

## Débit vidéo

`bit_rate` du flux vidéo est presque toujours **absent en Matroska**. Ordre
fiable :

1. `bit_rate` du flux ;
2. tag `BPS` posé par [[mkvmerge]], exact ;
3. débit du conteneur **moins** chaque piste non vidéo, résolues de la même
   façon (`bit_rate`, `BPS`, `NUMBER_OF_BYTES ÷ DURATION`).

Une pochette embarquée (second flux vidéo) ne se soustrait pas. Un TrueHD ou
DTS-HD MA n'annonce jamais de `bit_rate`. Pourquoi c'est important :
[[codecs-video#Mesurer le débit vidéo]].

## Champs utiles

| Besoin | Commande ou champ |
|---|---|
| Sous-profil Dolby Vision | `-show_entries stream_side_data=dv_profile,dv_bl_signal_compatibility_id` |
| Horodatages | `-select_streams v:0 -read_intervals "%+2" -show_entries packet=pts_time,dts_time,flags` |
| Nombre d'images | `-count_packets` puis `nb_read_packets` |
| Variante DTS | champ `profile` (« DTS-HD MA »), pas `codec_name` (toujours `dts`) |
| Métadonnées HDR10 | SEI du flux : master display, MaxCLL ([[hdr-dolby-vision]]) |
| Tag HEVC en MP4 | `codec_tag_string` (`hev1`, `hvc1`) |

Numérotation **par type** (`a:0`, `s:2`), incompatible avec l'ID global de
[[mkvmerge]].

## Compter les NAL d'un flux HEVC

Extraire en Annex-B avec `hevc_mp4toannexb`, parcourir les codes de début
`00 00 01`, type = `(octet suivant >> 1) & 0x3F`. RPU Dolby Vision = 62,
couche d'amélioration = 63, SEI préfixe = 39. Méthode employée dans
[[source-2026-09-24-diagnostic]].

## Piège d'encodage

Sa sortie est en UTF-8 : la lire en cp1252 fait disparaître un fichier de la
liste sans message ([[sous-processus]]).
