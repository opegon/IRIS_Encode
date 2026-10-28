# Passe DV sur la carte et plage pleine avec `scale_cuda` — 2026-10-28

Poste Shadow, RTX A4500, pilote 616.92, ffmpeg du dossier bin d'IRIS
(gyan.dev 8.1.2).

## Passe vidéo du réencodage Dolby Vision

Source : Spider-Man Brand New Day 2160p (HEVC 10 bits 3832×1600, DV 8.1).
Extrait de 60 s à t=600, `-map 0:v:0 -c:v hevc_nvenc -b:v 12000000
-maxrate 18000000 -bufsize 36000k -rc vbr -preset medium -profile:v main10
-f hevc`.

    actuel  -hwaccel cuda … -pix_fmt p010le                 21,4 s / 21,2 s  1439 images
    carte   -hwaccel cuda -hwaccel_output_format cuda       13,5 s / 13,5 s  1439 images
    cpu     (pas de -hwaccel) … -pix_fmt p010le             18,0 s           1439 images

Sorties actuel / carte : Main 10, yuv420p10le, BT.2020, PQ, Mastering display
10000000/10000, Content light level 705 — identiques. PSNR carte contre
actuel : inf (images identiques).

Commande construite par IRIS (`build_dv_video_command`, v0.9.0.13), même
extrait : 12,4 s, 1439 images ; fichier identique octet pour octet
(`cmp`) à celui de la commande de v0.9.0.12 sur le même extrait.

## H264 en plage pleine

Mire fabriquée : moitié noire, moitié blanche, 1920×1080, `libx264 -crf 0
-pix_fmt yuvj420p -color_range pc` → ffprobe `yuvj420p,pc`.

Encodages `hevc_nvenc -b:v 5M -profile:v main`, puis `signalstats` sur la
première image, sans conversion :

    source      yuvj420p,pc  YMIN=0 YMAX=255
    cpu         (scale 1280×720,setsar=1 -pix_fmt yuv420p)            yuvj420p,pc  YMIN=0 YMAX=255
    iris        (-hwaccel cuda + la même)                             yuvj420p,pc  YMIN=0 YMAX=255
    carte       (scale_cuda=w=1280:h=720:format=nv12 -aspect 1280:720) yuvj420p,pc  YMIN=0 YMAX=255
    carte, sans réduction (scale_cuda=format=nv12)                    yuvj420p,pc  YMIN=0 YMAX=255

Étiquette dans le flux HEVC brut (`-c copy -f hevc`) et en MP4 : `pc` pour
cpu comme pour carte. Ni `scale` ni `scale_cuda` ne convertissent la plage ;
tous deux la gardent et l'étiquettent.
