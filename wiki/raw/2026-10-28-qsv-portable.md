# Essais Intel Quick Sync sur le portable de l'utilisateur — 2026-10-28

Relevé transmis par l'utilisateur, depuis une conversation Claude (chat) sur son
portable Windows. Processeur : Intel Core i5-1135G7 (Tiger Lake, 4 cœurs).
ffmpeg du PATH du portable (pas celui d'IRIS), PowerShell.

## Commandes et résultats

    ffmpeg -hide_banner -loglevel error -init_hw_device qsv=hw -f lavfi -i "testsrc=duration=2:size=1280x720:rate=30" -c:v vp9_qsv -f null -
    (aucune sortie : succès)

    ffmpeg -hide_banner -loglevel error -init_hw_device qsv=hw -f lavfi -i "testsrc=duration=2:size=1280x720:rate=30" -pix_fmt p010le -c:v hevc_qsv -profile:v main10 -f null - ; $LASTEXITCODE
    0

Tableau rapporté par la conversation (H.264 et HEVC 8 bits essayés plus tôt,
commandes non transmises) :

| Codec | Encodage QSV |
|---|---|
| H.264 | ✅ |
| HEVC 8 bits | ✅ |
| HEVC 10 bits (Main10) | ✅ code retour 0 |
| VP9 | ✅ |
| AV1 | ❌ décodage seulement (encodage à partir de Meteor Lake / Arc) |

Réserve notée par la conversation : la mire est générée en 8 bits puis convertie
en `p010le` ; l'essai ne vérifie pas une chaîne HDR complète (métadonnées HDR10,
BT.2020).

## Constaté sur le poste de développement (Shadow, RTX A4500)

- Le ffmpeg fourni (`bin/ffmpeg.exe`, gyan.dev 8.1.2 essentials) contient
  `hevc_qsv`, `h264_qsv`, `av1_qsv` ; pas `libsvtav1`.
- `hevc_qsv` y refuse de s'ouvrir : « Error creating a MFX session: -9 », code 171.
- Presets de `hevc_qsv` : veryfast … veryslow (dont `fast`, `medium`, `slow`).
