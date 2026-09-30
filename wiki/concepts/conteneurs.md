---
type: concept
maj: 2026-09-30
sources:
  - "[[source-spec]]"
  - "[[source-2026-09-30-hev1-hvc1]]"
  - "[[source-changelog]]"
  - "[[source-2026-09-24-diagnostic]]"
---

# Conteneurs

## MP4 contre Matroska

| | MP4 | MKV |
|---|---|---|
| Sous-titres image (PGS, VobSub) | ✗ | ✓ |
| ASS / SSA stylés | ✗ | ✓ |
| Audio sans perte (TrueHD, DTS-HD MA) | ✗ (en pratique) | ✓ |
| SRT | en `mov_text` | tel quel |
| Écrit par | ffmpeg | mkvmerge (n'écrit **que** du Matroska), ffmpeg |
| Lecteurs | les plus stricts l'acceptent | « capricieux » sur le client LG webOS *(observé, README)* |

Politique d'IRIS (`container = "auto"`) : **MP4 quand tout y tient, MKV quand
quelque chose serait perdu**. Conséquence à connaître : une source WEB-DL en
E-AC3 + SRT sort en MP4, même traitée par un retrait du Dolby Vision. Des
pistes externes greffées ou un Dolby Vision conservé imposent le MKV. Détail :
spec § 8.6.

## Horodatages

Les problèmes d'horodatage produisent des fichiers **parfaits sur PC,
illisibles sur téléviseur** : les lecteurs de bureau (mpv, VLC) normalisent
en silence, les décodeurs matériels pas toujours. *(observé)*

- **Un flux brut (Annex-B, `.hevc`) n'a aucun horodatage.**
  - mkvmerge les reconstitue correctement, avec `--default-duration 0:<fps>p`.
    *(mesuré : paquets identiques à la source)*
  - ffmpeg vers MP4, même avec `-r`, écrit PTS = DTS sur chaque image
    (« pts has no value »). Faux dès qu'il y a des images B.
    *(mesuré, v0.8.8.15)*
  - **Ne jamais muxer un flux brut en MP4 avec ffmpeg** : partir d'un fichier
    conteneurisé, qui porte ses horodatages.
- **DTS négatifs en tête.** Un flux à images B commence avec des DTS négatifs.
  Le muxeur MP4 sait les porter (liste d'éditions), à condition de recevoir de
  vrais horodatages. Sur un flux brut, il jetait les premières images
  (2 268 sur 2 270). *(mesuré, v0.8.1.20)*
- **`start_time` décalé.** Un `-itsoffset` négatif fait refuser à ffmpeg des
  horodatages négatifs : il décale **tout le fichier** (vidéo à
  `start_time = 2.5 s` pour −2 500 ms). Certains décodeurs de téléviseur
  refusent la lecture. Traduire un décalage négatif en `-ss` sur l'entrée du
  donneur. *(mesuré, v0.8.1.0)*

## Chapitres

ffprobe voit, sur un MP4 issu d'une source chapitrée, un flux de plus que
demandé : `bin_data`, `codec_tag_string=text`, `handler_name=SubtitleHandler`,
une trame par chapitre. **C'est la piste de chapitres** : le MP4 ne sait porter
les chapitres que sous forme de piste texte QuickTime. `-map_chapters -1` la
fait disparaître, et les chapitres avec. *(mesuré, v0.8.2.9)*

## Tag HEVC en MP4 : `hev1` ou `hvc1`

ffmpeg écrit **`hev1`** par défaut pour du HEVC en MP4 (paramètres VPS/SPS/PPS
dans le flux). Les sources WEB-DL MP4 le portent aussi (Avatar). *(mesuré)*

`hvc1` (paramètres dans l'en-tête seulement) est exigé par les lecteurs
Apple. Sur le [[lg-oled-g3|G3]] via Jellyfin, les deux passent en **lecture
directe**, sauts quasi instantanés : même fichier, seule l'étiquette changée,
en SDR comme en HDR10. *(observé, 2026-09-30)*

## Réécrire un MKV

mkvmerge ne sait pas ajouter une piste **en place** : il réécrit le conteneur
entier. Un film de 30 Go veut dire une copie complète, une à trois minutes sur
SSD, et la place pour les deux fichiers le temps de l'opération. *(mesuré)*

Les intermédiaires volumineux (flux bruts, pistes audio) s'écrivent **à côté
de la source**, sur le même volume, pas dans le dossier temporaire du système.

## Coller des parties

`mkvmerge fichier1 + fichier2` : le `+` **enchaîne** en recalant les
horodatages de chaque partie. Sans lui, mkvmerge **superpose** les pistes.
Le démultiplexeur `concat` de ffmpeg exige des paramètres de flux strictement
identiques et gère mal les pistes multiples. *(documenté, spec § 9bis)*

mkvmerge refuse d'apparier des codecs ou des définitions différents. Si une
partie porte plus ou moins de pistes, il n'apparie que les rangs communs,
**sans refuser**. Deux parties inversées donnent un fichier de la bonne durée,
donc faux sans que rien ne le signale.

## Voir aussi

[[ffmpeg]] · [[mkvmerge]] · [[lg-oled-g3]] · [[sous-titres]] · [[audio]] · [[hdr-dolby-vision]]
