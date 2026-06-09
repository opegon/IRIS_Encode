# CHANGELOG — IRIS ENCODE

## [Non publié]

- **Dry-run : colonne « Durée »** entre Taille et Estim. (Δ%) — durée de chaque
  fichier au format h:mm:ss, redimensionnable comme les autres colonnes
  (largeur persistée dans `config.toml`).
- **Sélecteur de profils (F4) en vraie table** (`tui/screens/profile_picker.py`) :
  colonnes alignées (Profil, 1080p, 4K, DV, Preset, HD audio, Source), profil
  actif marqué ✓, valeurs DV colorées, alerte `⚠ suppr.` sur les profils qui
  suppriment la source. Remplace les chaînes paddées à la main ; le callback
  reçoit l'id du profil (plus robuste qu'un index). Utilisé par Browser et
  TracksScreen.

---

## [v0.7.0] — 2026-06-10

### Normalisation UIX

- **Touches « Retour » unifiées** : `Backspace` / `Esc` sur tous les écrans. ConfigScreen
  utilisait `←` (et son footer affichait à tort `Backspace`) — corrigé.
- **Modale de confirmation générique** (`tui/screens/confirm.py`) : quitter, run récursif
  et suppression de profil partagent désormais le même style (bordure `$warning` si
  destructif), les mêmes touches (`←/→` focus, `↵` valide le bouton focalisé,
  `Esc`/`⌫` annule) et un rappel des touches intégré.
- **Modale Quitter sécurisée** : `Enter` validait la sortie même avec le focus sur
  *Annuler* (binding priority) — désormais `Enter` active le bouton focalisé.
- **Suppression de profil enfin câblée** : la colonne Actions de ConfigScreen affichait
  « ✕ suppr. » sans qu'aucune touche n'y mène. `D`/`Suppr` supprime le profil user
  sous le curseur (confirmation, builtins protégés avec message).
- **Footers normalisés** (`tui/common.py`) : libellés identiques pour les mêmes touches
  (Début/Fin/Page ↑/Page ↓), groupes navigation + resize partagés, `F10 Quitter`
  toujours en dernier, doublon `↵`/`F2` du dry-run supprimé.
- **Hints contextuels** : TracksScreen affiche les contrôles selon la ligne (champs
  ←/→ et +/- sur la ligne vidéo, Espace/↵ sur les pistes) — ils étaient documentés
  mais invisibles. ValuePicker affiche `↵ Choisir · Esc Annuler`.
- **Version unique** (`version.py`) : le header TUI affichait `v0.6` et la bannière
  console `v0.6.5` — les deux lisent la même constante.
- **Barre de statut commune** : classe CSS `.status-bar` au niveau App (le même bloc
  était dupliqué dans 5 écrans), couleurs DV des profils centralisées.
- ConfigScreen : compteur AV1 ajouté au résumé dry-run ; la barre profil du browser
  se rafraîchit après activation d'un profil dans ConfigScreen (elle restait sur
  l'ancien profil).

### Corrections

- **Home/End/PgUp/PgDn restaurés sur Tracks et Config** : leurs `on_key` locaux
  écrasaient celui de `TableNavMixin` (les touches scrollaient sans déplacer le
  curseur). Les écrans délèguent désormais à `super().on_key()`.
- Les erreurs de scan du browser sont logguées (`~/.iris_encode/iris_encode.log`)
  au lieu d'être avalées silencieusement.

### Optimisations

- **Scan parallèle** : le browser analyse les fichiers avec 4 workers ffprobe
  simultanés (ordre des résultats préservé) au lieu d'un scan séquentiel ; la
  navigation pendant un scan abandonne les analyses restantes au lieu de les
  terminer pour rien.
- Dry-run : un seul `stat()` par fichier (taille réutilisée entre la ligne et le
  résumé, soit 2-3× moins d'appels disque).
- **Dé-duplication** (~150 lignes) : sélecteur de profils (browser/tracks), resize
  de colonnes (`ColumnResizeMixin` — browser/tracks/dryrun), formatage
  tailles/durées, options des pickers codec/débit (`tui/common.py`).
- Code mort retiré : messages Textual jamais postés et `_update_progress` (run),
  styles `_STYLE_*` et imports inutilisés (browser), `_force_nav` (mixins),
  constante `_ROW_VALIDATE` (tracks).

### Tests

- `tests/smoke_tui.py` : smoke test headless (Textual `run_test`) — navigation,
  modales, resize, scan parallèle. Lancement manuel : `python tests/smoke_tui.py`.

---

## [v0.6.5] — 2026-06-09

### Décision d'encodage
- **Seuils `near_1080p` paramétrables** (`config.toml`, section `[decision]`, 1600×850 par défaut) : les sources rognées (typ. 1918×1040, 1920×800 HDLight) sont désormais traitées comme du 1080p — résolution d'origine conservée, codec HEVC. Auparavant rabattues en 720p H264.
- `_resolve_limits` dissocie `limit_h` (cap résolution) et `bucket_h` (référence bitrate) pour éviter les rabats incohérents quand la source est entre 720p et 1080p strict.

### Dry-run — édition par fichier
- **F6 / F7** sur l'écran dry-run : picker `Codec` (HEVC / H264 / AV1 / SKIP) et `Débit cible` (échelle dédiée si AV1), appliqués à la ligne sous le curseur.
- Cohérence garantie à la modif : `output_suffix` aligné sur le codec, `DV → HDR10` forcé si passage en H264 (RPU incompatible), débit source pré-rempli sur `SKIP → encodage`, snap d'échelle si passage à AV1, recalcul auto de l'estimation et du résumé.

### Profils
- `bitrate_4k_kbps` réduit sur `film_basic` (5000→3000), `film_hd` (8000→5000), `basic_delete` (3500→2000).

### Interne
- Constantes vidéo mutualisées dans `core/decision.py` : `ACTION_CYCLE`, `BITRATE_OPTS_KBPS`, `AV1_BITRATE_OPTS_KBPS`, `SUFFIX_BY_ACTION` (fin de duplication entre `tracks.py`, `browser.py`, `dryrun.py`).
- Spec `iris_encode_spec_v0_5.md` retirée (remplacée par v0.6 depuis `58a3923`).

---

## [v0.6] — 2026-05-14

### Intégration Dolby Vision via dovi_tool

Trois PRs internes pour intégrer pleinement `dovi_tool` dans le pipeline d'encodage.

#### PR1 — Module `core/dovi.py`
- Wrapper standalone autour de `dovi_tool` :
  - `get_path()` / `is_available()` : détection (PATH + `./bin/`)
  - `probe_file()` : extrait sous-profil DV + master display + MaxCLL en un appel (50-150ms)
  - `extract_hevc_stream()` / `extract_rpu()` / `convert_p7_to_p8()`
  - `rpu_info()` : parsing structuré de la sortie `dovi_tool info`
  - `make_x265_hdr_params()` : construction des tokens `-x265-params` HDR10
- 15 tests unitaires (mock subprocess)
- URL Linux ajoutée dans `data/ffmpeg_releases.toml` (l'install auto Windows était déjà gérée par `preflight.py`)

#### PR2 — Scanner enrichi
- `VideoInfo` gagne 3 champs optionnels : `dv_subprofile`, `hdr10_master_display`, `hdr10_max_cll`
- `scanner.scan()` appelle `dovi.probe_file()` si DV détecté et `dovi_tool` disponible — pas de surcoût sur les fichiers non-DV
- `TracksScreen` affiche désormais le sous-profil exact (`DV:P8.1`, `DV:P5`…) en colonne Source
- Avertissement inline `⚠ dovi_tool absent` si HDR10 demandé sans dovi_tool

#### PR3 — Pipeline HDR10 quality
- Nouveau champ profil `hdr10_quality` : `"compat"` (NVENC, défaut) | `"quality"` (libx265 CPU)
- Nouveau profil builtin **`cinema_4k_quality`** : `hdr10_quality = "quality"`, encodage CPU avec :
  - `libx265` + `yuv420p10le` + `profile main10`
  - `-x265-params` injecté avec `master-display`, `max-cll`, `hdr10-opt=1`, `colorprim=bt2020`, etc.
  - hwaccel désactivé automatiquement (CPU obligatoire pour metadata HDR10 fines)
- `ProfileForm` expose le champ HDR10 mode

### Reporté en v0.7
- **Conversion P7→P8 pour DV preserve** : pertinent uniquement quand `dv_action == DV` (LG préfère P8). Pour `dv_action == HDR10`, le RPU est de toute façon supprimé et la conversion P7→P8 du RPU n'apporte rien — donc non implémenté ici.

---

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
