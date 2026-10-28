# Réencodage DV → HDR10 en 4K, preset slow, sur la carte — 2026-10-29

Poste Shadow, RTX A4500, ffmpeg du dossier bin d'IRIS (8.1.2). Source :
Spider-Man Brand New Day 2160p (HEVC 10 bits 3832×1600, DV 8.1). Profil
`cinema_4k_hdr_basic` (`dolby_vision = "hdr10"`, `keep_4k`, preset `slow`).

Commande construite par IRIS v0.9.1.0, 60 s à t=600 :

    ffmpeg -hwaccel cuda -i <source> -c:v hevc_nvenc -pix_fmt yuv420p10le
      -b:v 8312343 -maxrate 12468514 -bufsize 24937k -rc vbr -preset slow
      -profile:v main10 … -tag:v hvc1 → .mp4
    code 0, 38,3 s
    sortie : hevc 3832×1600 yuv420p10le smpte2084, side data Mastering
    display + Content light level, aucun enregistrement DV ;
    flux : 0 NAL 62, 0 NAL 63, 245 SEI préfixe (10 s)

Vidéo seule, mêmes réglages :

    actuel  -hwaccel cuda … -pix_fmt yuv420p10le          38,0 s  1439 images
    carte   -hwaccel cuda -hwaccel_output_format cuda …   37,6 s  1439 images
    PSNR carte contre actuel : inf ; carte : 0 NAL 62
