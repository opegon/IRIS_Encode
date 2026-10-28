# Essai du plafond de débit QSV sur le portable — 2026-10-28

Script fourni à l'utilisateur, lancé sur le portable (i5-1135G7, ffmpeg du
dossier bin d'IRIS v0.9.0.9). Source : l'épisode 4K HDR10 de l'essai
précédent. Extraits de 180 s à t=600 et t=1800, vidéo seule, ramenés en
1080p, `hevc_qsv -pix_fmt p010le -profile:v main10 -preset medium`,
`-b:v 2500k`, décodage au processeur. Débit = taille du fichier × 8 / 180.

Commande par extrait :

    ffmpeg -ss <t> -i <source> -t 180 -map 0:v:0 -an -sn
      -vf scale=1920:1080:force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1
      -c:v hevc_qsv -pix_fmt p010le -profile:v main10 -preset medium
      -b:v 2500k -maxrate <M> -bufsize <B> <sortie>.mkv

Résultats rapportés par l'utilisateur :

    marge  t=600    2314 kb/s  93 %     (maxrate 3750k, bufsize 7500k)
    serre  t=600    1855 kb/s  74 %     (maxrate 2500k, bufsize 5000k)
    x1.5   t=600    2314 kb/s  93 %     (maxrate 3750k, bufsize 7500k)
    x2     t=600    2273 kb/s  91 %     (maxrate 5000k, bufsize 10000k)
    x1.5   t=1800   2395 kb/s  96 %
    x2     t=1800   2378 kb/s  95 %

(« serre » à t=1800 non transmis.)
