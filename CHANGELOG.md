# CHANGELOG — IRIS ENCODE

## [v0.8.1.2] — 2026-08-27

- **Le footer ne se calait plus en bas de la fenêtre.** En passant le footer à
  hauteur variable en v0.8.1.0, son ancrage avait été retiré du browser au
  profit du `1fr` de la table — mais ce `1fr` ne s'appliquait pas : le
  sélecteur de type `DataTable` perd contre le style par défaut du widget, là
  où les autres écrans utilisent un sélecteur d'id. L'ancrage masquait le
  défaut depuis toujours. Corrigé sur le browser et le dry-run.
- La hauteur du footer est désormais posée explicitement plutôt que calculée
  en `auto` : une hauteur `auto` dépend de la largeur, qui dépend de la mise
  en page, qui dépend du `1fr` du contenu — la boucle laissait la table à
  trois lignes.
- Le footer reste dans le flux vertical, jamais ancré : ancré, il recouvrirait
  les dernières lignes de la table au lieu de lui laisser la place.
- **Les raccourcis sont rangés par rôle**, du haut vers le bas : propres à
  l'écran, globaux, puis touches de fonction `F1` à `F10` toujours en dernière
  ligne et triées par numéro. Une place fixe par rôle vaut mieux qu'un ordre
  de déclaration : l'œil apprend où regarder, et les touches qui lancent un
  encodage sont toujours au même endroit.

## [v0.8.1.1] — 2026-08-27

- **`GUIDE.md`** — guide d'utilisation : le parcours en trois temps, les
  raccourcis de chaque écran, une recette pour greffer une VF, et une section
  par cas rencontré (mesure refusée, montage différent, sous-titre image,
  étirement PAL, fichier illisible sur téléviseur…). Les raccourcis sont
  relevés depuis les `BINDINGS` du code, pas rédigés de mémoire.
- Le README précise qu'il couvre l'installation et renvoie au guide pour
  l'utilisation.

## [v0.8.1.0] — 2026-08-27

### Greffe d'une piste venue d'un autre montage

Ajouter une VF et ses sous-titres échouait dès que le donneur n'était pas le
même montage que la cible — le cas courant d'un rip broadcast face à un rip
streaming, dont les coupures publicitaires décalent tout ce qui suit.

- **Détection des plages** (`s`). Quand le recoupement par tiers constate que
  le décalage ne tient pas sur tout le film, la mesure cherche désormais s'il
  tient *par morceaux* : fenêtres de 2 min, fusion des voisines concordantes,
  affinage de chaque frontière à la seconde, puis remesure sur l'étendue
  définitive. Deux garde-fous écartent un découpage qui ne serait que du bruit
  de corrélation. Le refus nomme ce qu'il a vu au lieu d'une hypothèse
  générique.
- **Recalage des sous-titres** (`p`). Exact : il n'y a que des horodatages à
  décaler. `shift_srt()` réécrit chaque réplique avec le décalage de sa plage
  et produit un `.srt` recalé qui devient la source de la piste.
- **Recalage de l'audio** (`p`). L'opération est une **insertion**, pas une
  coupe : le décalage croissant signifie que la cible porte du contenu que le
  donneur n'a pas — celui-ci peut être plus long au total, ses minutes
  excédentaires étant dans le générique. Les insertions s'ancrent sur le
  silence le plus proche, la frontière de corrélation étant juste à une ou
  deux secondes près. Faute de silence, l'insertion est posée quand même et
  signalée : contrairement à une coupe, allonger n'efface rien.
- Les plages viennent toujours de l'audio du donneur : le signal d'un
  sous-titre est trop creux pour les retrouver seul, et les pistes d'un même
  donneur portent le même montage.
- **Sous-titres embarqués mesurables.** Une piste `mov_text` ou SRT logée dans
  un conteneur n'avait aucune réplique lisible et la mesure refusait pour
  « format inconnu ». Elle est désormais extraite vers un `.srt` temporaire.
  Un sous-titre image (PGS, VobSub) est refusé pour ce motif propre.

Vérifié sur un épisode réel : 6 plages, cinq paliers de +2 000 ms, et les
pistes produites mesurent **+0 ms de décalage résiduel** — l'audio avec une
confiance de 0,72 et trois tiers concordants à 0 ms.

### Corrections

- **Fichiers illisibles sur téléviseur après un encodage `F2` avec piste
  greffée en décalage négatif.** Un `-itsoffset` négatif rend négatifs les
  horodatages du donneur ; ffmpeg refuse de les écrire et décale *tout le
  fichier* vers l'avant. Mesuré pour −2 500 ms : la vidéo sortait avec
  `start_time = 2.5 s`. mpv et VLC normalisent sans broncher, un décodeur
  matériel de TV non. Le décalage négatif passe désormais par `-ss` sur
  l'entrée du donneur.
- **Une piste étirée n'interdit plus l'encodage.** `F2` refusait et renvoyait
  l'utilisateur muxer lui-même avant de revenir encoder — un travail que
  l'outil sait faire. mkvmerge greffe vers un intermédiaire temporaire juste
  avant l'encodage. Le surcoût n'est payé que dans ce cas ; sans mkvmerge, le
  refus a lieu en amont plutôt qu'au milieu d'un encodage.
- `tests/smoke_tui.py` mourait sur le même `UnicodeEncodeError` que `main.py`
  corrigeait en v0.8.0.2, ce point d'entrée ne passant pas par `main()`.

### Interface

- **Footer réparti sur plusieurs lignes.** Il tenait sur deux lignes fixes et
  tronquait l'excédent en silence : au-delà de ~147 colonnes, soit dès un
  1920×1080, `F1`, `F2`, `F3` et `Back` disparaissaient sans que rien ne
  signale leur existence. `KeyFooter` répartit les raccourcis sur autant de
  lignes qu'il en faut ; aucun n'est jamais coupé ni omis. Libellés raccourcis
  en complément — l'écran de recalage passe de 245 à 166 colonnes.
- **Troisième ligne du bandeau de recalage invisible.** `height: 3` avec une
  bordure haute ne laissait que deux lignes de texte, la perdue étant toujours
  celle qui renvoie vers `a` ou `s`. Défaut présent depuis la v0.8.0.
- **Le recalage audio ne donnait aucun signe d'activité** : la barre atteignait
  85 % puis restait figée pendant tout le réencodage — 65 des 82 secondes de
  l'opération. ffmpeg rapporte désormais sa progression. Le libellé annonçait
  par ailleurs « Mesure en cours » pendant un recalage.

## [v0.8.0.2] — 2026-08-26

- **Démarrage hors console corrigé.** `main.py` mourait sur un
  `UnicodeEncodeError` avant d'afficher quoi que ce soit dès que sa sortie
  n'était pas une vraie console Windows — redirection vers un fichier, pipe,
  lancement depuis Git Bash, WSL ou une tâche planifiée. Python retombe alors
  sur l'encodage local (cp1252 en français), où le cadre de la bannière et les
  coches `✓`/`✗` n'existent pas. `stdout` et `stderr` sont désormais forcés en
  UTF-8 avant le premier `print`. Le double-clic sur `launch.bat` n'était pas
  affecté, ce qui explique que le défaut ait survécu depuis la v0.7.0.

## [v0.8.0.1] — 2026-08-26

- **`Ctrl+D` — supprimer le fichier sous le curseur** depuis le browser, avec
  confirmation (`tui/screens/delete_confirm.py`, bâtie sur `ConfirmModal`, focus
  initial sur *Annuler*). Pendant de `v` : juger une source amène parfois à
  constater qu'elle ne vaut rien. Suppression définitive, sans corbeille ; la
  ligne disparaît sans re-scanner le dossier. Un fichier encore ouvert dans mpv
  fait échouer la suppression sous Windows — le message le dit.
- **Documentation** : consolidation des trois specs concurrentes en un document
  unique à nom fixe (`iris_encode_spec.md`) suivant la version.

## [v0.8.0] — 2026-08-26

### Greffe de pistes externes

Ajouter à un fichier une piste audio ou des sous-titres venus d'un autre
fichier, sans réencoder la vidéo, chaque piste portant son propre décalage.

- **`F9` — piste externe** depuis l'écran des pistes ou celui du recalage :
  choix du fichier donneur, puis de ses pistes via `mkvmerge -J`. Plusieurs
  donneurs s'enchaînent sans quitter l'écran.
- **Écran de recalage** : décalage réglable au clavier (`+/-` par 100 ms,
  `Shift+↑/↓` par seconde), facteur d'étirement PAL↔film, langue, nom,
  drapeaux défaut et forcé. `c` reprend le décalage d'une autre piste — le cas
  d'une VF et de ses sous-titres écrits sur le même timing.
- **`m` — mesure automatique du décalage** par corrélation croisée. Pour une
  piste audio, les deux enveloppes d'énergie ; pour un sous-titre, les
  répliques contre un VAD appliqué à la parole du film. Le facteur d'étirement
  est cherché sur une grille de ratios. Le résultat est recoupé sur trois
  tiers du film : un vrai alignement tient sur chacun, du bruit se disperse.
- **`v` — visualiser dans mpv** avec la piste greffée et le décalage appliqué,
  positionné sur un passage dialogué.
- **`k` — extrait de contrôle** réellement muxé, découpé par mkvmerge sur le
  flux de sortie. Deux fenêtres quand un étirement est en jeu, la dérive
  s'accumulant.
- **`F3` — mux** par mkvmerge, ou **`F2` — encodage** : ffmpeg absorbe alors
  les pistes dans la même passe, sans fichier intermédiaire.
- Après un mux, le fichier produit devient le fichier de travail.

### Outils

- **mkvmerge et mpv** rejoignent les outils optionnels, installés depuis leur
  archive portable. mpv n'étant publié qu'en `.7z`, l'extraction passe par le
  tar/libarchive livré avec Windows plutôt que par une dépendance nouvelle.
- **Vérification des mises à jour au démarrage**, au plus une fois par jour et
  sans bloquer hors ligne. `check_on_startup`, le cache des versions et la
  vérification SHA256 étaient déclarés mais inertes.

### Estimation

- Colonne **Temps estim.** au dry-run, appuyée sur une moyenne mobile de vitesse
  d'encodage relevée à chaque passe. (`Estim. (Δ%)` avait été ajoutée en v0.6.5,
  `Durée` en v0.7.1.)

### Corrections

- Le conteneur de sortie suit les pistes réellement conservées : écarter les
  sous-titres image libère le MP4. `mov_text` n'est plus proposé en Matroska.
- Les listes de dépendances de `main.py` et `launch.bat` couvrent
  `requirements.txt` ; un test les compare.
- Le preflight ne dépend plus d'un terminal interactif.
- `.gitattributes` impose le CRLF aux scripts Windows.

## [v0.7.1] — 2026-08-06

- **Dry-run : colonne « Durée »** entre Taille et Estim. (Δ%) — durée de chaque
  fichier au format h:mm:ss, redimensionnable comme les autres colonnes
  (largeur persistée dans `config.toml`).
- **Sélecteur de profils (F4) en vraie table** (`tui/screens/profile_picker.py`) :
  colonnes alignées (Profil, 1080p, 4K, DV, Preset, HD audio, Source), profil
  actif marqué ✓, valeurs DV colorées, alerte `⚠ suppr.` sur les profils qui
  suppriment la source. Remplace les chaînes paddées à la main ; le callback
  reçoit l'id du profil (plus robuste qu'un index). Utilisé par Browser et
  TracksScreen.
- Correction du crash `NoMatches` sur `Backspace` pendant un encodage.
- Gestion des événements clavier dans les modales de saisie.

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
