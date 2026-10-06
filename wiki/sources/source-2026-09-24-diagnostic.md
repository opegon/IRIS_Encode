---
type: source
maj: 2026-09-24
ingere: 2026-09-24
---

# Source : Diagnostic du retrait Dolby Vision (2026-09-24)

**Où** : [[2026-09-24-diagnostic-retrait-dv]]
**Nature** : relevés bruts d'une session, immuables

Relevés faits pour expliquer « le son sans l'image, puis plantage » sur le
téléviseur. Comparaison paquet par paquet des sorties MKV et MP4 du retrait
Dolby Vision avec leurs sources, essai du filtre `dovi_rpu` de ffmpeg,
inventaire des profils DV et des sous-titres de `resources_files`.

## Conclusions

- Le chemin MKV (dovi_tool + mkvmerge) est sain : paquets identiques à la
  source, NAL 62 en moins.
- Le chemin MP4 d'alors écrivait PTS = DTS : ordre d'affichage faux. Corrigé
  en v0.8.8.15 par `dovi_rpu=strip=1`, vérifié sur 90 s de Film C.
- Aucun échantillon de profil 7.

## Pages alimentées

[[hdr-dolby-vision]] · [[conteneurs]] · [[ffmpeg]] · [[ffprobe]] · [[mkvmerge]] · [[dovi-tool]] · [[sous-titres]] · [[lg-oled-g3]] · [[pieges-et-lecons]] · [[questions-ouvertes]]
