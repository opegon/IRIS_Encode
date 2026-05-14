# CHANGELOG — IRIS ENCODE

## [v0.2] — 2026-05-14

### Correctifs
- **DryrunScreen** : passage d'un `dict` au lieu d'une liste lors du lancement F1 depuis TracksScreen — corrigé avec `[dec]` (fichier courant uniquement)
- **TracksScreen** : `_make_selection()` appelée avec un argument superflu — TypeError corrigé
- **BrowserScreen** : `action_open_run()` filtrait les fichiers SKIP même s'ils étaient cochés manuellement

### Nouveautés
- **TracksScreen** : la colonne Décision affiche désormais systématiquement l'info Dolby Vision : `DV - N/A` si la source n'en a pas, `DV → HDR10 / DV → DV / DV → SDR` selon le traitement actif
- **Fichiers SKIP forcés** : sélectionner manuellement un fichier SKIP dans le navigateur l'inclut dans le dry-run/run en le forçant en HEVC (ou H264 si < 1080p) au débit source — sans jamais augmenter le débit existant
- **DryrunScreen** : raccourci `R` remplacé par `F2` pour cohérence avec les autres écrans
- **RunScreen** : l'encodage démarre automatiquement à l'ouverture — confirmation Enter supprimée

---

## [v0.1] — 2026-05-13

- Version initiale : navigateur de fichiers, décisions vidéo/audio, profils, encodage HEVC/H264, support Dolby Vision (HDR10/DV/SDR), dry-run, run, récursif, métadonnées IMDB/OMDb
