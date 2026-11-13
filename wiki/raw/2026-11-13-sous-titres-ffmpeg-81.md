# 2026-11-13 — `.srt` UTF-16 et `mov_text` vers Matroska, rejoués en 8.1.2

Poste Windows de développement. Outils de `bin/` : ffmpeg 8.1.2 essentials
(gyan.dev), mkvmerge v103.0. Fichiers synthétiques : vidéo `color` ou
`testsrc` de quelques secondes, `.srt` de deux répliques accentuées
(« Été à Noël », « çà où »). Rejoue les deux relevés ffmpeg 6.1.1 de
[[2026-11-13-revue-code]], pendant IE-187 et IE-188.

## `.srt` en UTF-16 avec BOM (CR-123)

Deux fichiers, UTF-16 LE (`FF FE`) et BE (`FE FF`). Sortie Matroska, puis
`ffmpeg -i sortie.mkv -map 0:s:0 x.srt` pour relire la première réplique.

| Commande | LE | BE |
|---|---|---|
| ffmpeg, sans `-sub_charenc` | « Été à Noël » | « Été à Noël » |
| ffmpeg, `-sub_charenc UTF-16` | « 쎉瓃ꤠ쎠⁎濃꭬ » | idem |
| ffmpeg, `-sub_charenc CP1252` (vers `-c:s srt`) | code 0, « Ã‰tÃ© Ã  NoÃ«l » | — |
| mkvmerge, sans `--sub-charset` | « Été à Noël », code 0 | idem |
| mkvmerge, `--sub-charset 0:UTF-16` | « Été à Noël », code 0 | idem |
| mkvmerge, `--sub-charset 0:CP1252` | « Été à Noël », code 0 | idem |

`core.sous_titres.encodage_texte` (v0.9.2.8) rendait `CP1252` pour ces
fichiers ; `core.sync.read_cues` n'y lisait aucune réplique (`[]`).

## `mov_text` recopié vers Matroska (CR-117)

Source : MP4 `testsrc` 320×240 + un `.srt` converti en `mov_text`, langue
`fre`.

    ffmpeg -i src.mp4 -map 0 -c:v copy -c:s copy o1.mkv
    [matroska @ …] Subtitle codec mov_text (94213) is not supported.
    [out#0/matroska @ …] Could not write header (incorrect codec parameters ?): Function not implemented
    code 127

    ffmpeg -i src.mp4 -map 0 -c:v copy -c:s copy -c:s:0 srt o2.mkv
    code 0 ; ffprobe : subrip, language=fre ; « Été à Paris » relu intact

    mkvmerge -J src.mp4 → sous-titre « Timed Text »
    mkvmerge -o m.mkv src.mp4 → code 0 ; ffprobe : subrip
