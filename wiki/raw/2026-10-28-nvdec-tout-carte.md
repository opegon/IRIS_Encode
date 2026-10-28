# Décodage NVDEC et `scale_cuda` sur le poste de développement — 2026-10-28

Poste Shadow, NVIDIA RTX A4500 (Ampere), pilote 616.92, ffmpeg du dossier bin
d'IRIS (gyan.dev 8.1.2). Extraits de 60 s à t=600, vidéo seule,
`hevc_nvenc -b:v 2500000 -maxrate 3750000 -bufsize 7500k -rc vbr -preset medium`
(`-profile:v main10` en HDR, `main` en SDR). Temps mesurés par `date` autour
de l'appel.

Variantes :

- cpu   : `-vf scale=W:H:force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1 -pix_fmt …`
- iris  : la même avec `-hwaccel cuda` (chemin d'IRIS jusqu'à v0.9.0.11)
- carte : `-hwaccel cuda -hwaccel_output_format cuda -vf scale_cuda=w=L:h=H:format=p010le|nv12 -aspect L:H`

## Temps

    Project Hail Mary 2160p HDR10 (3840×2160) → 1080p
      cpu 28,4 s   iris 28,0 s   carte 5,7 s
      second passage : cpu 28,0 s   iris 28,4 s   carte 5,6 s
    Spider-Man Brand New Day (3832×1600 HDR, DV) → 1920×802
      cpu 22,2 s   iris 22,0 s   carte 4,7 s
    Homejacking S01E01 (H264 1080p SDR) → 1280×720
      cpu 4,0 s    iris 6,1 s    carte 3,1 s

Tous code 0.

## Sorties (ffprobe, iris puis carte)

    hdr4k  Main 10,1920,1080,1:1,16:9,yuv420p10le,smpte2084,bt2020,1440 images
           Mastering display 10000000/10000, Content light level 1230 — identiques
    spider Main 10,1920,802,1:1,960:401,yuv420p10le,smpte2084,bt2020,1439 images
           Mastering display 10000000/10000, Content light level 705 — identiques
    sdr720 Main,1280,720,1:1,16:9,yuv420p,bt709,1500 images — identiques

PSNR moyen carte contre iris : 53,4 dB (hdr4k), 48,0 dB (spider),
49,6 dB (sdr720). Recadrage côte à côte d'une image de spider : aucune
différence visible.

## Cas limites de `scale_cuda` (5 s, code 0)

    sans réduction, H264 8 bits → format=nv12        Main,1920×1080,yuv420p
    HEVC 8 bits HDR (PQ) → format=p010le             Main 10,yuv420p10le,smpte2084
    HEVC 10 bits HDR → w=1280:h=720:format=nv12      High (h264_nvenc),yuv420p,smpte2084
    VP9 8 bits 3840×2160 → 1920×1080 nv12            Main,yuv420p,bt709
    AV1 10 bits 3840×1920 → 1920×960 p010le          Main 10,yuv420p10le,smpte2084

## Commande construite par IRIS (v0.9.0.12, `movie_hdr`)

    ffmpeg -hwaccel cuda -hwaccel_output_format cuda -i Project.Hail.Mary…2160p.mkv
      -vf scale_cuda=w=1920:h=1080:format=p010le -c:v hevc_nvenc -b:v 5000000
      -maxrate 7500000 -bufsize 15000k -rc vbr -preset medium -aspect 1920:1080
      -profile:v main10 … -c:a copy -c:s mov_text …
    60 s : code 0, 5,8 s ; sortie 1920×1080 1:1 yuv420p10le smpte2084,
    deux pistes audio et trois sous-titres

Sondage de la carte : `h264_nvenc`, `hevc_nvenc`, `hevc_nvenc@10`, `libx265` ;
pas d'`av1_nvenc` (Ampere).
