# DV profil 5 converti en HDR10 : vert et violet ; libplacebo (2026-11-01)

Signalé par l'utilisateur : « la conversion avec iris_encode […] est "verte"
comme si il manquait la couche rouge. je l'ai réencodé avec la session de
iris_encode ouvert en mémoire ».

Source : `Smile.2.2024.MULTI.DV.2160p.WEB.H265-LOST.mkv` (resources_files).
Sortie fautive : `Smile.2.2024.MULTI.HDR10.1080p.WEB.hevc-iris.mp4` (v0.9.1.11).

ffprobe (bin, gyan 8.1.2), source :
  hevc Main 10, 3840x1920, yuv420p10le, color_space/transfer/primaries unknown
  DOVI configuration record : dv_profile=5, dv_level=6, rpu=1, el=0, bl=1,
  dv_bl_signal_compatibility_id=0
Sortie fautive : 1920x960, yuv420p10le, color_space/transfer/primaries unknown.
Image à 600 s extraite : dominante violette (lue BT.709), verte au lecteur.

Filtres :
  bin/ffmpeg.exe 8.1.2 essentials (gyan.dev) : ni libplacebo ; zscale, tonemap.
  C:\Program Files\ffmpeg\bin\ffmpeg.exe n8.1.3-20260925 (BtbN) : libplacebo,
  option apply_dolbyvision (défaut true), force_original_aspect_ratio,
  force_divisible_by.

Mesures (BtbN n8.1.3, RTX A4500, pilote 616.92) :
  - `-init_hw_device vulkan -f lavfi -i color=black:s=64x64:d=0.04
    -vf libplacebo=apply_dolbyvision=1:format=yuv420p -f null -` : rc 0, 1,2 s.
  - `ffmpeg -filters` : 0,1 s.
  - Image 600 s, libplacebo apply_dolbyvision → bt709 : couleurs naturelles.
  - 5 s depuis 600 s, libplacebo w=1920:h=1080:force_original_aspect_ratio=decrease
    :force_divisible_by=2:colorspace=bt2020nc:color_primaries=bt2020
    :color_trc=smpte2084:range=tv:format=yuv420p10le,setsar=1, hevc_nvenc
    p010le 8M : 5,2 s. Sortie 1920x960 SAR 1:1, bt2020nc/smpte2084/bt2020, tv.
    Les balises suivent sans -color_* explicite.
  - Commande produite par IRIS v0.9.1.12 (scan, decide, build_command),
    profils movie_hdr et movie_basic, 20 s depuis 600 s : rc 0 ;
    HDR10 Main 10 bt2020nc/smpte2084/bt2020, SDR Main 8 bits bt709 ;
    images vérifiées, couleurs justes.
