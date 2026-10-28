# Décodage matériel Quick Sync sur le portable — 2026-10-28

Essais lancés par l'utilisateur sur le portable (i5-1135G7), ffmpeg du dossier
bin d'IRIS (gyan.dev 8.1.2). Source : l'épisode 4K HDR10 (HEVC Main 10,
3840×2160). Extrait de 60 s à t=600, vidéo seule, ramené en 1080p,
`hevc_qsv -profile:v main10 -preset medium -b:v 2500k -maxrate 3750k
-bufsize 7500k`. Temps mesurés par `Measure-Command`.

## Décodage au processeur, `d3d11va`, `qsv` — filtre `scale` au processeur

    aucun    code 0  60,2 s pour 60 s de film
    d3d11va  code 0  76,2 s pour 60 s de film
    qsv      code -40  1,7 s pour 60 s de film

Erreur de `-hwaccel qsv -hwaccel_output_format` implicite (qsv) :

    Impossible to convert between the formats supported by the filter 'graph -1 input from stream 0:0' and the filter 'auto_scale_0'
    Link 'graph -1 input from stream 0:0.default' -> 'auto_scale_0.default':
      Pixel formats:
        src: qsv
    …
    [vf#0:0 @ …] Error reinitializing filters!
    … Task finished with error code: -40 (Function not implemented)

## Tout sur la puce

    ffmpeg -hwaccel qsv -hwaccel_output_format qsv -ss 600 -i <source> -t 60
      -map 0:v:0 -an -sn -vf "vpp_qsv=w=1920:h=1080"
      -c:v hevc_qsv -profile:v main10 -preset medium
      -b:v 2500k -maxrate 3750k -bufsize 7500k qsv_gpu.mkv

    tout-puce  code 0  18,1 s pour 60 s de film

ffprobe de `qsv_gpu.mkv` :

    profile=Main 10
    width=1920
    height=1080
    pix_fmt=yuv420p10le
    side_data_type=Mastering display metadata
    min_luminance=0/1
    max_luminance=1000/1
    color_range=tv
    color_space=bt2020nc
    color_transfer=smpte2084
    color_primaries=bt2020

L'utilisateur : « le visuel est vérifié et bon ».

## Constaté sur le poste de développement (Shadow, RTX A4500)

- `scale_cuda=w=1920:h=802` sur une source 3832×1600 (SAR 1:1) laisse un SAR
  de 192079:192000 ; avec `-aspect 1920:802`, SAR 1:1 (DAR 960:401).
- `scale=W:H:force_original_aspect_ratio=decrease:force_divisible_by=2`,
  ffprobe sur `nullsrc` : 3832×1600 → 1920×802, 3840×1606 → 1920×804,
  4096×2160 → 3840×2026 (cible 4K), 3840×1600 → 1280×534 (cible 720p).
