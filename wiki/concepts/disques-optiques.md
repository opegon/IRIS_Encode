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
- **Blu-ray** — `BDMV` : `PLAYLIST\*.mpls` décrit un titre comme une suite de
  clips `STREAM\*.m2ts` ; `CLIPINF\*.clpi` porte les langues. ffprobe n'en lit
  aucune sur un `.m2ts`, mkvmerge les lit dans le `.clpi` voisin (*mesuré*).
  Sans langue, la règle des langues d'un profil n'a rien pour trier : sur le
  Blu-ray d'essai, une seule piste audio était retenue (*mesuré*). Une langue
  complétée ainsi n'est **pas** recopiée par ffmpeg, qui ne la voit pas dans le
  flux : il faut l'écrire (`-metadata:s:a:N language=…`, *mesuré*).
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
