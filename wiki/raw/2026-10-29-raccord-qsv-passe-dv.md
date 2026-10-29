# Raccord : Quick Sync et passe vidéo DV — relevés du 2026-10-29

Suite de [[2026-10-29-fichier-colle-tout-carte]].

## Quick Sync (observé par l'utilisateur)

Portable i5-1135G7, IRIS v0.9.1.4, fichier `error.1080p.avc.mp4` : « il n'y a
pas eu de bascule, tout est resté sur le gpu » — encodage tout-puce `vpp_qsv`
abouti, sans reprise hors puce. Durées de la sortie non relevées.

## Passe vidéo DV sur NVIDIA (mesuré, RTX A4500, ffmpeg 8.1.2)

Mire HEVC 10 bits 1280×720 24 i/s : deux segments libx265 de 2 s, le second
étiqueté `bt2020nc / smpte2084`, collés en Annex-B, remuxés en MP4
(`-fflags +genpts`) — 94 images, raccord à l'image 45.

Commande de `build_dv_video_command` sur la carte (`-hwaccel cuda
-hwaccel_output_format cuda`, aucun `-vf`, `hevc_nvenc`, `-f hevc`) : même
échec que le chemin standard, « Error reinitializing filters! », code 127,
44 images écrites.

Ancien chemin de la passe (`-hwaccel cuda`, `-pix_fmt p010le`) : code 0,
93 images. La 94e manque aussi au processeur seul ; avec `-fps_mode
passthrough`, 94 partout — horodatages irréguliers du collage synthétique,
pas un effet du chemin.

Dans IRIS, l'échec de la passe arrête le fichier proprement (« Encoding the
video failed »), source conservée ; un écart d'images ferait échouer
l'injection du RPU (dovi_tool), pas une sortie fausse.
