# Sondage des sources disque et TS — 2026-10-08

Demande de l'utilisateur : « avant la revue de code, nous allons ajouter une
fonctionnalité sur les sources possibles » ; formats `.ts .m2ts .mts .mpg .mpeg
.vob` acceptés ; « j'aimerai également que l'on traite les sources iso » ;
« dans un premier temps, on peut considérer qu'il suffit à l'utilisateur de
monter l'iso puis on navigue dans l'iso via le navigateur de fichier
normalement ». Dossier de sortie : « ok pour la demande du répertoire de sortie
avec un réglage de dossier de sortie dans la configuration. le choix est proposé
par défaut mais on peut choisir ailleurs via une navigation ». Pratiques connues
(titres par IFO / playlists, filtre de durée, quatre livraisons) : « oui ».

Échantillons : `resources_files/bluray.iso` (21 Go),
`resources_files/DVD5/DVD/CURE_IN_ORANGE.ISO`, `Cesar (1936).ts`,
`Olympe, une femme dans la Révolution_France 2_2025_03_03_21_10.ts`.

## ffprobe sur les `.ts` (bin/ffprobe 8.1.2 essentials)

    Cesar : aac (fra) + h264 1920x1080 ; start_time=10.000000 duration=8114 bit_rate=5216305
    Olympe : aac (pas de langue) + h264 1920x1080 ; start_time=10.000000 duration=5500

Les flux apparaissent deux fois (section `program` puis liste globale).

## ISO non monté

    bin/ffprobe (gyan 8.1.2 essentials) -f dvdvideo … → Unknown input format: dvdvideo
    bin/ffprobe bluray:…iso → Protocol not found
    ffmpeg -buildconf (gyan essentials) : ni libbluray, ni libdvdnav, ni libdvdread
    C:\Program Files\ffmpeg (BtbN n8.1.3 gpl) : --enable-libdvdread --enable-libdvdnav --enable-libbluray

    BtbN -f dvdvideo CURE_IN_ORANGE.ISO : mpeg2video 720x480 + ac3 (eng), duration=6572.5
      (avertissements libdvdread « Zero check failed … vmgi_mat->zero_3 », sans effet)
    BtbN bluray:bluray.iso : h264 1080p, pcm_bluray 2 can., truehd 8 can., ac3 6 can.,
      hdmv_pgs_subtitle ; duration=4424.8 ; aucune langue ; BD-J : « Failed to load JVM library »

## ISO montés (Mount-DiskImage -Access ReadOnly)

Blu-ray en E: — `BDMV\STREAM` : 00001.m2ts 18,3 Go (le film), 00003 1,5 Go,
00002 0,67 Go, 00000 0,55 Go ; `BDMV\PLAYLIST` : 00000–00003.mpls, 01000–01003.mpls.

    bin/ffprobe 00001.m2ts : mêmes pistes, aucune langue, duration=4424.9 bit_rate=33087299
    bin/mkvmerge -J 00001.m2ts : PCM eng, TrueHD Atmos eng, AC-3 eng, HDMV PGS eng

DVD en G: — `VIDEO_TS` : VTS_01_0.VOB 83 Mo (menu), VTS_01_1…4.VOB 1 073 739 776 o,
VTS_01_5.VOB 267 Mo ; VIDEO_TS.VOB 8 Ko.

    bin/ffprobe VTS_01_1.VOB : dvd_nav_packet (data), mpeg2video 720x480, ac3 ; duration=1449 (une partie)
    bin/mkvmerge -J VTS_01_1.VOB : MPEG-1/2, AC-3 ; aucune langue

Écriture dans `E:\BDMV\STREAM` et `G:\VIDEO_TS` : `[Errno 13] Permission denied`.

Décision d'IRIS (profil movie_hdr) sur 00001.m2ts sans langues : une seule piste
audio retenue (la PCM stéréo, en AAC), TrueHD, AC-3 et PGS écartés.

## Encodages courts (15 s, bin/ffmpeg, NVENC) depuis les lecteurs montés

    00001.m2ts → HEVC MP4, AAC : OK, start_time=0 duration=15.015
    VTS_01_1.VOB → H.264 MP4, AC-3 copié : OK, start_time=0 duration=15.015
    Cesar (1936).ts → HEVC MP4, AAC copié : OK, start_time=0 duration=15.019
