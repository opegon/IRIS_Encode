# CHANGELOG — IRIS ENCODE

## [v0.5] — 2026-05-14

### Correctifs critiques
- **Garde-fou anti-écrasement source** dans `build_command` : refuse l'encodage si `output_path == input_path` (évite la corruption irréversible)
- **Fallback DV obsolète** : `profiles.py` retournait `"hdr"` (ancien nom) à la place de `"hdr10"` pour les profils sans champ explicite — styling cassé corrigé
- **Forçage SKIP : `dv_action` désormais cohérent** avec l'action forcée (H264 + source DV → HDR10 obligatoire, le RPU étant incompatible)

### Correctifs importants
- **`_eff_*` falsy bug** (`tracks.py`) : `or` retournait la valeur source quand l'override valait `0` ou `VideoAction.SKIP` (truthy). Remplacé par `is not None`.
- **Override `action` recalcule `output_suffix`** dans BrowserScreen : un passage HEVC→H264 via TracksScreen ne laisse plus un nom `_[hevc]` incorrect
- **Override SKIP→encode** : si la décision originale était SKIP (bitrate=0) et qu'on passe à une action d'encodage, le débit source est appliqué par défaut
- **Code mort retiré** : `_extract_dv_to_hdr10_json` jamais appelée — supprimée (dette technique). Réintégration prévue avec dovi_tool complet en v0.6.
- **Run récursif filtrait SKIP par `.name`** (string) au lieu d'enum — uniformisé
- **DryrunScreen footer** : `ctrl+x` (binding inexistant) → `f10`
- **Helper `_force_skip_to_encode`** : extraction de la duplication entre `action_open_dryrun` et `action_open_run`

### Nouveautés
- **DryrunScreen** : nouvelle colonne **Estim. (Δ%)** avec la taille de sortie estimée par fichier (`bitrate × durée / 8`) et le ratio de compression vs source. Summary global avec total source → estimé.
- **RunScreen** :
  - Nouveau raccourci `s` pour **passer le fichier en cours** sans annuler tout le batch
  - Le binding `enter` "Démarrer" (devenu menteur depuis le démarrage auto) a été retiré
  - Gestion propre des erreurs `build_command` (fichier en erreur, on enchaîne sur le suivant)
- **TracksScreen** : le **profil actif** est désormais affiché dans la status bar
- **Logging** : les erreurs de scan ne sont plus avalées silencieusement — fichier de log dans `~/.iris_encode/iris_encode.log` (niveau WARNING)

---

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
