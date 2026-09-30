# NVENC refusé après réinstallation du poste — relevés bruts

Session du 2026-09-26. PC cloud Shadow (offre Power) fraîchement réinstallé,
Windows 11 Home 10.0.26200.
**Fichier immuable** : ne pas modifier, ajouter un nouveau relevé à côté.

## Symptôme rapporté par l'utilisateur

« ma session réinstallée fraichement avec les pilote nvidia rtx 4500 ne semble
pas fournir de hevc_nvenc à iris_encode ? »

## Matériel et pilote

`nvidia-smi` : NVIDIA RTX A4500 (Ampere), Driver Version 597.16, CUDA 13.2.
`C:\Windows\System32\nvEncodeAPI64.dll` : 32.0.15.9716.

## Commande d'essai

```
ffmpeg -hide_banner -loglevel verbose -f lavfi -i testsrc2=s=1280x720:d=1 -c:v hevc_nvenc -f null -
```

## Builds essayés

| Build | Où | Résultat |
|---|---|---|
| N-126856-ged27b2c498-20260925 (git master) | `C:\Program Files\ffmpeg\bin` | échec |
| 8.1.2-essentials_build-www.gyan.dev | `IRIS_Encode\bin` | échec |
| BtbN `ffmpeg-n9.0-latest-win64-gpl-9.0` | essai | échec |
| BtbN `ffmpeg-n8.1-latest-win64-gpl-8.1` (n8.1.3-20260925) | essai, puis installé par l'utilisateur dans `C:\Program Files\ffmpeg\bin` | succès |

Sortie des échecs (identique pour les trois) :

```
[hevc_nvenc] Loaded Nvenc version 13.0
[hevc_nvenc] Driver does not support the required nvenc API version. Required: 13.1 Found: 13.0
[hevc_nvenc] The minimum required Nvidia driver for nvenc is 610.00 or newer
[vf#0:0] Error sending frames to consumers: Function not implemented
[vost#0:0/hevc_nvenc] Could not open encoder before EOF
Conversion failed!
```

Sans `-loglevel verbose`, seules les lignes « Function not implemented » et
« Could not open encoder before EOF » apparaissent : la cause est invisible.

Avec BtbN n8.1.3 : `hevc_nvenc` 8 bits OK, `hevc_nvenc` Main10 en `p010le`
(1080p) OK, `h264_nvenc` 8 bits OK. `h264_nvenc` en `p010le` : échec (attendu,
pas de H.264 10 bits sur NVENC).

## Sonde d'IRIS_Encode après installation

```
encodeurs_a_sonder -> ['hevc_nvenc', 'h264_nvenc', 'av1_nvenc', 'libx265']
sonder_encodeurs   -> ['h264_nvenc', 'hevc_nvenc', 'libx265']
```

`get_tool_path` prend le `PATH` avant `bin/` : c'est le build du `PATH` qui sert.

## Pilote 610 sur Shadow (recherche web)

- Shadow documente la mise à jour manuelle du pilote NVIDIA (NVIDIA App ou
  site NVIDIA, installation propre en cas de souci) ; ses pilotes sont testés
  puis installés automatiquement, avec retard sur NVIDIA.
- R610 U2 (610.88) : branche « New Feature » RTX Enterprise, 2026-05-26.
- Aucune source trouvée sur la 610 validée pour l'offre Power / RTX A4500.
