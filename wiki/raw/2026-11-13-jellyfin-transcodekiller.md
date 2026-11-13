# Jellyfin : lecture d'une sortie IRIS arrêtée dans Chrome (2026-11-13)

Relevé fourni par l'utilisateur : journal du serveur Jellyfin 10.11.11 et log
ffmpeg de la session. Identifiants de session et d'utilisateur, nom de compte et
adresses retirés.

Fichier lu : `Alien (1979) … 1080p 10bit HDR10+ BluRay DDP 5.1.hevc-iris.mp4`
— sortie IRIS, HEVC Main 10 HDR10 1920x800 (`hevc_nvenc`), deux E-AC3 5.1,
trois `mov_text`, piste de chapitres.

Client : « Jellyfin Web » 10.11.11, « Chrome », Chrome 151 sous Windows 10/11.

Constat de l'utilisateur : « une fois réencodé, ce stream plante au bout de
quelques secondes ». La source (MKV Dolby Vision) se lit sur le même PC.

Extrait du journal (heures UTC) :

```
19:28:18.629 [INF] TranscodeManager: ffmpeg … -i file:"…hevc-iris.mp4" … -map 0:0 -map 0:1 -map -0:s
             -codec:v:0 copy -tag:v:0 hvc1 -bsf:v hevc_mp4toannexb -start_at_zero
             -codec:a:0 libfdk_aac -ac 2 -ab 256000 -af "volume=2" … -f hls … -hls_segment_type fmp4 …
19:28:19.932 [WRN] Jellyfin.Plugin.TranscodeKiller.KillerEntrypoint: Killing transcode process for session "…"
19:28:19.932 [INF] TranscodingJob: Stopping ffmpeg process with q command for "…m3u8"
19:28:20.250 [INF] TranscodeManager: FFmpeg exited with code 0
19:28:21.298 [WRN] Jellyfin.Plugin.TranscodeKiller.KillerEntrypoint: Killing transcode process for session "…"
19:28:24.171 [INF] TranscodeManager: ffmpeg … -ss 00:00:06.500 -noaccurate_seek … (même commande)
19:28:24.255 [WRN] Jellyfin.Plugin.TranscodeKiller.KillerEntrypoint: Killing transcode process for session "…"
19:28:24.255 [INF] TranscodingJob: Stopping ffmpeg process with q command for "…m3u8"
19:28:24.256 [ERR] ExceptionMiddleware: Error processing request: "A task was canceled". URL "GET" "/videos/…/hls1/main/1.mp4".
19:28:24.791 [INF] TranscodeManager: FFmpeg exited with code 0
19:28:25.255 … 19:28:29.254 [WRN] TranscodeKiller: Killing transcode process for session "…" (une fois par seconde)
19:28:29.516 [INF] SessionManager: Playback stopped reported by app "Jellyfin Web" "10.11.11" … Stopped at "0" ms
```

Le log ffmpeg de la seconde session se termine sans erreur : quatre segments
HLS écrits (945 images), puis `[q] command received. Exiting.`
