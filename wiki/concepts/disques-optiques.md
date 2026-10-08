---
type: concept
maj: 2026-10-08
sources:
  - "[[source-2026-10-08-disques]]"
---

# Disques optiques : DVD, Blu-ray, ISO, flux MPEG

## Structure

- **DVD** — `VIDEO_TS` : les `.IFO` décrivent titres, chapitres, langues et
  palette des sous-titres ; les `.VOB` ne sont que des tranches de 1 Go
  (1 073 739 776 o) d'un même VTS (*mesuré*). `VIDEO_TS.VOB` et `VTS_xx_0.VOB`
  sont des menus. Un VOB isolé ne porte **aucune langue** (*mesuré*, ffprobe et
  mkvmerge).
- **Titres d'un DVD** — `VIDEO_TS.IFO` (TT_SRPT, secteur en `0xC4`) liste
  les titres et leur VTS ; `VTS_xx_0.IFO` (PTT_SRPT en `0xC8`, PGCI en `0xCC`)
  donne leurs PGC et leur durée en BCD. Lu sans outil sur le DVD d'essai :
  1 titre, 26 chapitres, 6 573,0 s, contre 6 572,5 s pour ffprobe
  `dvdvideo` (*mesuré*). Ses 512 premiers paquets portent des PES vidéo
  `0xE0` et audio `0xBD`, bits de brouillage nuls (*mesuré*) : c'est là que
  CSS se lirait (*documenté*, aucun DVD chiffré pour l'épreuve).
- **`dvdvideo`** — `-i E:\` (racine d'un lecteur monté) échoue : libdvdread y
  voit un périphérique et cherche libdvdcss ; `-i E:\VIDEO_TS` et `-i E:\.`
  passent (*mesuré*, BtbN 8.1.3). Des « Zero check failed » s'affichent en
  erreur sans effet. `-map 0 -c copy` vers MKV : 4,4 Go en 34 s, 26
  chapitres, langue de la piste AC-3 (*mesuré*) ; le MKV s'encode ensuite par
  le gyan « essentials ». Le BtbN n9.0 de la release `latest` s'installe
  (ffmpeg et ffprobe, ~160 Mo chacun) et lit le DVD (*mesuré*).
- **Blu-ray** — `BDMV` : `PLAYLIST\*.mpls` décrit un titre comme une suite de
  clips `STREAM\*.m2ts` ; `CLIPINF\*.clpi` porte les langues. ffprobe n'en lit
  aucune sur un `.m2ts`, mkvmerge les lit dans le `.clpi` voisin (*mesuré*).
  Sans langue, la règle des langues d'un profil n'a rien pour trier : sur le
  Blu-ray d'essai, une seule piste audio était retenue (*mesuré*). Une langue
  complétée ainsi n'est **pas** recopiée par ffmpeg, qui ne la voit pas dans le
  flux : il faut l'écrire (`-metadata:s:a:N language=…`, *mesuré*).
- **Playlists** — un disque publie souvent deux fois le même titre : sur le
  disque d'essai, `00001.mpls` et `01001.mpls` citent le même clip, la
  première avec 1 chapitre, la seconde avec 14 (*mesuré*) ; idem 00000/01000,
  00002/01002, 00003/01003. Le format MPLS se lit en quelques lignes (éléments
  clip / entrée / sortie à 45 kHz, marques d'entrée) : durées et nombres de
  chapitres identiques à ceux de `mkvmerge -J` (*mesuré*). `mkvmerge -o x.mkv
  titre.mpls` assemble un titre de plusieurs clips, durée complète, code 0
  (*mesuré* sur une playlist de deux clips fabriquée). IRIS : voir spec
  § 15.5.
- **AACS** — chaque unité de 6 144 octets (32 paquets de 192) d'un clip
  chiffré ne garde en clair que ses 16 premiers octets : la synchronisation
  `0x47` des paquets suivants disparaît. Le disque d'essai : 2 000 paquets sur
  2 000 synchronisés, bits de permission de copie à zéro (*mesuré*). Aucun
  disque chiffré disponible pour l'épreuve inverse (*documenté*).
- **Chapitres d'un clip seul** — le `.m2ts` n'en porte pas ; un fichier
  FFMETADATA en entrée `-f ffmetadata` avec `-map_chapters` les pose dans la
  sortie, coupés à la durée encodée (*mesuré*, 400 s : 2 chapitres sur 14).
- **TrueHD et cœur AC-3** — un même PID (0x1101 sur le disque d'essai), deux
  pistes pour ffprobe et pour mkvmerge (*mesuré*) : le cœur est la
  compatibilité AC-3 embarquée, pas une piste distincte. `-c:a copy` de ce cœur
  donne une AC-3 5.1 lisible (*mesuré*, 20 s).

## Pratique des outils de référence

*documenté* (HandBrake, MakeMKV, mkvmerge) : on ne travaille pas sur les
fichiers bruts mais sur des **titres**. DVD : IFO lus par libdvdnav ; recoller
les VOB échoue sur le multi-angle et sur un VTS à plusieurs titres, et perd la
palette VobSub. Blu-ray : playlists `.mpls` (seamless branching : un film sur
plusieurs clips) ; la plus longue est le titre principal par défaut (libbluray),
avec le piège connu de l'obfuscation de playlists. Menus et bonus s'écartent par
une **durée minimale** de titre, pas par la taille des fichiers. Les disques
chiffrés (CSS, AACS) restent hors de portée.

## Lecture par ffmpeg

Démultiplexeur `dvdvideo` (ffmpeg 7+) et protocole `bluray:` : seulement dans
un build avec libdvdnav / libbluray — le BtbN GPL, pas le gyan « essentials »
de `bin/` (*mesuré*, voir [[ffmpeg#Versions]]). Sans JVM, libbluray signale
« BD-J check: Failed to load JVM library » et lit quand même (*mesuré*).

## ISO monté

`Mount-DiskImage` (clic droit → Monter) donne un lecteur **en lecture seule** :
toute écriture y est refusée (`Errno 13`, *mesuré*), d'où le dossier de sortie
demandé par IRIS. Depuis un lecteur monté, `.m2ts` et `.VOB` s'encodent avec les
outils de `bin/` (*mesuré*, 15 s).

## Entrelacement

Le DVD d'essai est entrelacé et le dit (`field_order=tt`, chaque image
`interlaced_frame=1`) ; `idet` : 100 % TFF (*mesuré*). Les deux `.ts` TNT se
déclarent progressifs, images marquées progressives ; `idet` confirme pour
César, mais pas pour Olympe : 14 % BFF au début, 0 % au milieu, 80 % vers la
fin (*mesuré*) — un enregistrement qui ment par passages, sans doute pubs et
bandes-annonces. `bwdif … deint=interlaced` ne traite que les images marquées :
il laisse donc ces passages. Encodé NVENC H.264 3 Mb/s, le DVD sort sans peignes
avec bwdif (`idet` image par image : 1 sur 899 contre 686 sans, *mesuré*,
contrôlé à l'œil) ; la détection « multi » d'`idet` en voit encore 322 sur une
scène sombre, artefact de l'outil (images indécises). Voir spec § 8.1.

## Flux de transport `.ts`

Enregistrements TNT : `start_time` à 10 s, flux listés deux fois par ffprobe
(section `program`), langue parfois absente (*mesuré*) — mkvmerge n'en trouve
pas davantage, il lit la même table (*mesuré*). L'encodage repart à 0
(*mesuré*). Sous-titres possibles : `dvb_subtitle` (images, décodé par le
`dvbsub` de ffmpeg) et `dvb_teletext`, que ni MP4 ni MKV ne portent et que seul
un ffmpeg avec libzvbi décode — absent du gyan « essentials », présent dans le
BtbN (*mesuré*, `-buildconf`). Aucun échantillon avec sous-titres à ce jour.

## Voir aussi

[[conteneurs]] · [[ffmpeg]] · [[ffprobe]] · [[mkvmerge]] · [[sous-titres]]
