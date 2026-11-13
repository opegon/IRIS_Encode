# 2026-11-13 — Relevés de la revue de code et d'interface (v0.9.2.6)

Session Linux, ffmpeg / ffprobe 6.1.1 (Ubuntu), mkvmerge v82.0, Python 3.13,
Textual 8.2. Fichiers synthétiques (`testsrc2`, `sine`). Rapport :
`revue_code_2026-11-13.md`.

## `mov_text` recopié vers Matroska (CR-117)

Source MP4 portant un sous-titre `mov_text`, sortie `.mkv`, `-c:s copy` :

    [matroska @ …] Subtitle codec 94213 is not supported.
    Could not write header (incorrect codec parameters ?): Function not implemented
    Conversion failed!

Code de sortie 218. La conversion `-c:s srt` n'a pas été essayée. Non
essayé en ffmpeg 8.1.

## `.srt` en UTF-16 avec BOM (CR-123)

`core.sous_titres.encodage_texte` rend `CP1252` pour un `.srt` en UTF-16 LE
avec BOM (UTF-8 échoue, cp1252 accepte). `-sub_charenc CP1252 -i fichier.srt`
vers `mov_text` : code 0, texte de sortie illisible (« Été à Noël » perdu).
Non essayé en ffmpeg 8.1.

## Analyse d'entrelacement d'une mire progressive

Mire `testsrc2` 720×480 à 25 i/s, MPEG-4 en AVI, encodée progressive :
l'analyse d'IRIS (`idet`) la classe `ENTRELACE`, part d'images en peigne
0,70. Une seule mire, pas de contenu réel essayé.

## Suite de tests hors Windows

`python -m pytest tests` : 2 456 réussis, 15 échecs, 54 ignorés (264 s), avec
ou sans mkvmerge dans le `PATH`. Les conditions de saut cherchent
`bin\ffmpeg.exe` et `bin\mkvmerge.exe`.
