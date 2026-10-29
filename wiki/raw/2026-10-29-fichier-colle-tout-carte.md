# Fichier collé et chaîne tout-carte NVIDIA — relevés du 2026-10-29

Poste de développement, RTX A4500, ffmpeg 8.1.2 (gyan.dev essentials).
Fichier signalé par l'utilisateur : `resources_files/error.1080p.avc.mp4`,
H264 High 1080p25 + AAC stéréo, 25 min 42 s, profil `video_basic_delete`.

Commande d'IRIS (v0.9.1.1) : `-hwaccel cuda -hwaccel_output_format cuda`,
`-vf scale_cuda=format=nv12`, `hevc_nvenc`. Arrêt à 52,6 s, code 127 (rc
Windows 4294967256) :

    Reconfiguring filter graph because video parameters changed to cuda(tv, bt709), 1920x1080
    Impossible to convert between the formats supported by the filter 'Parsed_scale_cuda_0' and the filter 'auto_scale_0'
      src: cuda
      dst: yuv420p yuyv422 … (formats processeur seulement)
    Error reinitializing filters!
    Task finished with error code: -40 (Function not implemented)
    Conversion failed!

ffprobe par image : jusqu'à 52,68 s `color_range=unknown color_space=unknown` ;
à 52,72 s `tv / bt709` et un SEI « user data unregistered » (en-tête x264) :
deux encodages collés. Le décodeur logue `Reinit context to 1920x1088`.
Décodage complet seul (`-f null`) : aucune erreur, 58 s.

Extrait 45 s → 65 s :

| Variante | Résultat |
|---|---|
| commande d'IRIS | échec à 7,6 s de l'extrait |
| `-reinit_filter 0` en option d'entrée | même échec |
| `setparams=range=tv:colorspace=bt709:…` devant `scale_cuda` | même échec |
| `-hwaccel cuda` sans `-hwaccel_output_format`, `-vf format=nv12` | passe |
| décodage processeur, `-pix_fmt yuv420p` | passe |

Reproduit sur une mire : deux segments `testsrc2` 320×240 x264 de 2 s, le
second avec `-color_range tv -colorspace bt709 …`, concaténés en Annex-B puis
remuxés en MP4.

Fichier entier, chemin processeur d'IRIS (`-hwaccel cuda`, `scale`,
`-pix_fmt yuv420p`) : 90 s, vidéo 1541,92 s, audio 1541,95 s.
