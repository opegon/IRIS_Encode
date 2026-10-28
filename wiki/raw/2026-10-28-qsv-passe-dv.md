# Passe DV sur la puce Intel — 2026-10-28

Essai lancé par l'utilisateur sur le portable (i5-1135G7), ffmpeg du dossier
bin d'IRIS installé (`C:\iris_encode\bin`). Source : Toy Story 5 2160p
WEBRip DV HDR10+ x265 (DV 8.1). Extrait de 60 s à t=600, `-map 0:v:0 -c:v
hevc_qsv -b:v 12000000 -maxrate 18000000 -bufsize 36000k -preset medium
-profile:v main10 -f hevc`. Temps par `Measure-Command`.

    actuel  (décodage processeur) … -pix_fmt p010le        code 0  51,2 s
    puce    -hwaccel qsv -hwaccel_output_format qsv …       code 0  38,4 s

    dv-actuel.hevc : yuv420p10le,1440
    dv-carte.hevc  : yuv420p10le,1440

ffprobe de la sortie puce, première image :

    Mastering display metadata,10000000/10000,Content light level metadata,343

Hachages : différents (`False`). PSNR puce contre actuel :

    PSNR y:62.075839 u:62.793018 v:64.597880 average:62.527569 min:56.440833 max:inf
