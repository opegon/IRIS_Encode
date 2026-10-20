# 2026-10-20 — `.ts` IPTV : un paquet AAC corrompu fait échouer la recopie en MP4

Signalé par l'utilisateur : des conversions de `.ts` échouent dans IRIS v0.9.0.4.
Trois fichiers fournis : « La petite histoire de France » S02E001 à E003, `.TS`
(extension en majuscules), 72 à 77 Mo, ~3 min chacun.

Outils : ffmpeg / ffprobe n8.1.3-20260925 (BtbN, PATH).

## Les sources

ffprobe : `mpegts`, `start_time` 10,0 s ; flux 0 = AAC LC stéréo 48 kHz `fre`,
flux 1 = H.264 High 1280x720 25 i/s progressif. L'audio précède la vidéo dans
l'ordre des flux.

Paquets audio marqués corrompus (`flags=K_C`), S02E001 : à partir de
pts 16549920 (≈ 173,9 s du début), quatre paquets consécutifs ; tous commencent
par un en-tête ADTS valide (`fff1 4c80…`). Démuxeur : « PES packet size
mismatch », « Packet corrupt (stream = 0, dts = 16549920) ». Même défaut sur
E002 (dts 16008480) et E003 (dts 17089440).

## La commande d'IRIS (profil `series_hdr_delete`, NVENC)

`ffmpeg -hwaccel cuda -i <src>.TS -c:v h264_nvenc … -map 0:v:0 -map 0:a:0
-c:a:0 copy -movflags +faststart -y <sortie>.h264-iris.mp4`

Échec à 2 min 52 s sur 2 min 56 s :

```
[aac_adtstoasc] Error parsing ADTS frame header!
[mp4] Error applying bitstream filters to an output packet for stream #1: Invalid data found when processing input
Conversion failed!
```

Une simple recopie de l'audio (`-map 0:a:0 -c copy` vers `.m4a`) échoue de
même sur les trois fichiers.

## Avec `-fflags +discardcorrupt` en entrée

Les trois recopies passent ; « Packet corrupt …, dropping it. ». Durée audio
de sortie : 176,79 s, 171,84 s, 180,93 s (durées sources 176,76 / 171,80 /
180,88 s). La commande complète d'IRIS sur E001 : code 0, vidéo 176,76 s,
audio 176,79 s.

## Reproduction synthétique

`.ts` de 3 s (`testsrc` 320x240 + `sine`, libx264 + AAC, PID audio 0x101).
Chaque paquet TS audio qui n'ouvre pas un PES (143) retiré à tour de rôle,
puis `-map 0:v -map 0:a -c copy` vers MP4 : 136 échecs sur 143, même erreur
`aac_adtstoasc`. Avec `-fflags +discardcorrupt` : 0 échec sur 143.

Une simple troncature du fichier en fin de flux ne reproduit pas (4 essais) :
le dernier PES incomplet n'est pas marqué corrompu.
