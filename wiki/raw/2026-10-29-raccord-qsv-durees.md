# Raccord sur Quick Sync : durées de la sortie — relevé du 2026-10-29

Complète [[2026-10-29-raccord-qsv-passe-dv]]. Relevé par l'utilisateur sur le
portable (i5-1135G7), ffprobe de l'installation :

    > ffprobe -v error -show_entries stream=codec_type,duration -of csv=p=0 error.1080p.avc.mp4
    video,1541.920000
    audio,1541.951000
    > ffprobe ... error.1080p.avc.hevc-iris.mp4
    video,1541.920000
    audio,1541.951000
