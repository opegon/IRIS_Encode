# Revue de code et d'interface — 2026-11-13 (v0.9.2.6)

Revue de `core/`, `tui/`, `main.py`, `updater.py`, `dependances.py`, de
l'interface en exécution, de la documentation et des tests. Branche
`claude/laughing-darwin-hlz6wj`, partie de `9d667e2`. Rapport daté : il ne se
réécrit pas. **Aucune correction n'a été faite** : chaque constat est calibré
pour être corrigé seul, après tri.

Numérotation à la suite de la revue du 2026-10-08 : constats `CR-113` à
`CR-148`, entrées de travail proposées `IE-185` à `IE-197` (à reporter dans
`TODO.md`, qui n'est pas dans le dépôt). Cas de recette `RC-nn`.

## 1. Résumé

- **36 constats** : 3 critiques, 5 majeurs, 28 mineurs. 24 reproduits (code
  réel exécuté sur fichiers synthétiques, écrans pilotés), 11 lus, 1 supposé.
- **Cahier de recette** : 74 cas, 41 conformes, 33 non conformes — chacun
  rattaché à un constat.
- **Tests** : 2 525 collectés ; avec ffmpeg 6.1.1 et mkvmerge v82 dans le
  `PATH`, 2 456 réussis, 15 échecs, 54 ignorés (§ 3). Les échecs sont d'environnement, sauf un test qui
  dépend d'un état global laissé par un autre (CR-146). Dix mutations
  ponctuelles du code : neuf tuées par la suite, la dixième survit ici parce
  que son test est sauté sans `bin\ffmpeg.exe` (CR-147).
- **Documentation** : versions alignées sur 0.9.2.6 dans les sept fichiers ;
  guides anglais et français de même structure (43 titres) ; catalogue de
  traduction à jour (`outils/i18n.py tout` ne produit aucun écart, 0 entrée
  non traduite, 0 `fuzzy`) ; wiki conforme (`tests/test_wiki.py`). Écarts :
  le README donne l'ancienne règle 4K, la spec affirme deux choses que le
  chemin automatique ne fait pas, le guide intégré se dit complet et ne l'est
  pas (CR-142, CR-143).

Les trois critiques :

| Constat | Ce qui se passe |
|---|---|
| CR-113 | Le mux d'un fichier (`F3`) écrase un `.mux-iris.mkv` déjà présent, et l'efface si l'on revient en arrière pendant le mux |
| CR-114 | Une vidéo verticale 1080×1920 est prise pour de la 4K : réduite à 608×1080 par un profil sans `keep_4k`, jugée au débit 4K sinon |
| CR-115 | Deux sous-titres de même langue recalés par plages s'écrivent dans le même fichier : la sortie porte deux fois le même |

## 2. Cadre et méthode

### Ce qui a été lu

| Zone | Lecture |
|---|---|
| `core/` (30 modules, 13 100 lignes) | en entier, sauf `core/__init__.py` (vide) |
| `tui/app.py`, `common.py`, `mixins.py`, `widgets/` | en entier |
| `tui/screens/` : `browser`, `run`, `tracks`, `wizard`, `dryrun`, `sync`, `mux_run`, `join`, `donor_picker`, `config`, `options`, `emplacements`, `youtube`, `youtube_chaine`, `aide`, `meta_popup`, `opensubtitles`, `output_dir`, `fin_lot`, `delete_confirm`, `value_picker` | en entier |
| `tui/screens/` : `cles`, `sar`, `segments`, `ancrage`, `confirm`, `quit`, `profile_picker`, `recursive_confirm` | **non relus** (exercés par le smoke test et les captures seulement) |
| `main.py`, `updater.py`, `dependances.py`, `logger/` | en entier |
| `launch.bat`, `bootstrap.ps1`, `launcher/`, `outils/i18n.py` | **non relus** (inchangés dans leur principe depuis la revue du 2026-10-08 ; `outils/i18n.py` exécuté) |

Les choix déjà tranchés listés dans le cadre de la revue du 2026-10-08 ne sont
pas re-signalés ; un désaccord est posé en question (§ 8).

### Environnement

Linux, Python 3.13.18, textual 8.2.x, ffmpeg/ffprobe 6.1.1 (Ubuntu, sans
`dvdvideo`, `dovi_rpu` ni `libplacebo`), mkvmerge v82.0 (installé pendant la
revue). Ni GPU, ni `bin/`, ni `resources_files/`, ni dovi_tool, mpv, seconv,
yt-dlp.

**Non exécutable ici** : NVENC, QSV, AMF, les API Windows (`mpr`, `advapi32`,
`kernel32`), les chemins Dolby Vision réels, l'OCR, YouTube, les lecteurs
réseau. Ce qui en dépend est marqué `lu` ou `supposé`. Les reproductions
ffmpeg sont faites en 6.1.1 : à confirmer en 8.1.x pour CR-117 et CR-123.

### Outils de session (hors dépôt)

Scripts dans le dossier de travail de la session, non versionnés : `r1.py`,
`r2.py`, `r3.py` (reproductions sur le cœur), `ui_review.py`, `ui2.py` (écrans
pilotés par `App.run_test`, exports SVG en 160×45, 100×30 et 80×24, en français
et en anglais), `mutate.py` (mutations sur une copie `git archive`). Jeu de
vidéos synthétiques : un 1080p H264 à 27 Mb/s avec DTS 5.1, AC3 5.1 et deux
SRT ; un 720p HEVC sous la cible ; un 1080×1920 ; un AVI MPEG-4 720×480 sans
SAR ; une sortie `.hevc-iris.mp4`. Les fichiers que ces essais et les outils
du dépôt ont écrits dans le clone (`config.toml`, `profiles.toml`,
`data/analyses.json`, `_shots/`) ont été retirés.

### Critères, gravité, certitude

Ceux de la revue du 2026-10-08 : **J** justesse, **P** perte de données,
**C** concurrence, **S** sous-processus, **W** Windows, **R** récidive,
**G** règles du projet, **T** trou de couverture, **M** code mort ; plus
**UI** (ce que l'écran montre) et **D** (documentation).
`critique` : perte de données, résultat faux sans erreur ; `majeur` : fonction
cassée dans un cas réel ; `mineur`. `reproduit`, `lu`, `supposé`.

## 3. Base de tests

`pip install -r requirements.txt pytest`, puis `python -m pytest tests -q`.

| Passe | Outils | Résultat |
|---|---|---|
| 1 | ffmpeg 6.1.1 seul | 2 456 réussis, 15 échecs, 54 ignorés, 264 s |
| 2 | ffmpeg 6.1.1 + mkvmerge v82 | 2 456 réussis, 15 échecs, 54 ignorés, 266 s — identique |

Les 15 échecs de la passe 1 :

| Test | Cause | Nature |
|---|---|---|
| `test_bluray.py::test_à_la_racine_d_un_lecteur_l_étiquette_du_volume` | `Path("E:\\")` n'est pas une racine sous Linux | environnement |
| `test_dvd.py::test_à_la_racine_d_un_lecteur_le_nom_par_défaut` | idem | environnement |
| `test_densite.py::test_la_notice_ne_repete_pas_le_dossier_courant` (×2) | séparateur `\` attendu | environnement |
| `test_dvd.py::test_l_outil_dvd_se_pose_dans_bin_dvd`, `test_dv_p5.py::test_l_outil_dv_se_pose_dans_bin_dv` | l'archive du test porte des `.exe`, `_exe()` n'en ajoute pas sous Linux | environnement |
| `test_emplacements.py` (×6) | chemins UNC sous `PosixPath`, API Windows | environnement |
| `test_revue_interface.py::test_les_volumes_nomment_le_partage` | lettre de lecteur | environnement |
| `test_finalisation_mp4.py::test_remux_mp4_rend_sa_progression[strip]` | filtre `dovi_rpu` absent de ffmpeg 6.1 | environnement |
| `test_dvd.py::test_le_lpcm_devient_un_pcm_de_meme_profondeur` | le test ne pose pas l'outil DVD : il ne passe que si un test d'application précédent l'a laissé dans `core.dvd._ffmpeg` | **défaut du test** (CR-146) |

Autres relevés :

- `tests/test_sar.py:424-426` : `SyntaxWarning: invalid escape sequence '\:'`
  à chaque collecte (CR-148).
- 1 707 fonctions de test ; 9 sans `assert` direct, toutes déléguant à une
  fonction d'aide ou à `pytest.raises` — aucune vide.
- `python tests/smoke_tui.py` : `SMOKE OK dans 2 langues`.
- `python tests/shots_tui.py --langue fr` : 7 prises sur 28 ; le contexte A
  (matériel réel) est `NON CAPTURE` sans `resources_files/`.

Les 54 tests ignorés, par motif : outils du projet absents de `bin/` (29,
dont ceux que mkvmerge et ffmpeg du `PATH` auraient permis — CR-147),
matériel réel absent de `resources_files/` (10), Windows seulement (15 : SMB,
API, jonction NTFS). La passe 2 ne change rien : les tests cherchent
`bin\ffmpeg.exe` et `bin\mkvmerge.exe`, pas le `PATH`.

## 4. Cahier de recette

Verdict **OK** : conforme à l'attendu. **KO** : non conforme, avec le constat.
« Attendu » est ce que la spec, le guide ou une règle du projet annonce.

### 4.1 Décision vidéo et nom de sortie

| Cas | Scénario | Attendu | Obtenu | Verdict |
|---|---|---|---|---|
| RC-01 | 1920×1080 HEVC 9 Mb/s, profil `movie_1080p_std` | HEVC à 5 000k | `→ HEVC`, 5 000k | OK |
| RC-02 | 1280×720 HEVC 694 kb/s | SKIP | `← SKIP` | OK |
| RC-03 | 1080×1920 (vertical) 6 Mb/s, `movie_1080p_std` | définition gardée | `scale=1920:1080:…decrease` → 608×1080 | KO · CR-114 |
| RC-04 | 1080×1920, `movie_4k_std` (`keep_4k`) | tranche 1080p | tranche 4K (8 000k) : SKIP | KO · CR-114 |
| RC-05 | 1280×720 HDR10 (PQ, 10 bits) 9 Mb/s, décision automatique | pas de H264 en HDR (spec § 14.0) | `→ H264`, `libx264 -pix_fmt yuv420p`, sans conversion SDR | KO · CR-118 |
| RC-06 | même fichier, H264 choisi à la main | SDR, averti | `dv_action = SDR` | OK |
| RC-07 | fichier sans flux vidéo | écarté ou dit | `→ H264 · Unknown bitrate`, `-map 0:v:0` | KO · CR-129 |
| RC-08 | `Film.Exemple.2019.1080p.BluRay.x264.DTS-GROUPE.mkv`, DTS → E-AC3 | nom à jour | `Film.Exemple.2019.1080p.BluRay.E-AC3.hevc-iris.mp4` | OK |
| RC-09 | sortie visée déjà sur le disque, dans la file | numérotée | `(2)` (`resoudre_sorties`, mutation M9 tuée) | OK |
| RC-10 | source 720×480, écrans Aperçu et Pistes | définition de sortie | « 1280x720 » : le cadre maximal | KO · CR-140 |

### 4.2 Audio, sous-titres, conteneur

| Cas | Scénario | Attendu | Obtenu | Verdict |
|---|---|---|---|---|
| RC-11 | DTS 5.1 768k, profil `audio_hd_codec = "eac3"` | E-AC3 768k | `→ eac3 768k` | OK |
| RC-12 | `fra` face à `audio_languages = ["fre"]` | gardée | gardée (mutation M6 tuée) | OK |
| RC-13 | MP4 à sous-titre `mov_text`, profil `container = "mkv"`, ligne cochée | sortie MKV | ffmpeg code 218, « Subtitle codec 94213 is not supported » | KO · CR-117 |
| RC-14 | `container = "mp4"`, ASS français + SRT anglais | « les sous-titres image sont écartés » (spec § 8.6, formulaire) | l'ASS français est écarté | KO · CR-119 |
| RC-15 | `.srt` greffé en UTF-16 avec BOM | texte juste | `encodage_texte` → `CP1252`, ffmpeg code 0, « Ã‰tÃ© » | KO · CR-123 |
| RC-16 | `.srt` greffé en cp1252 | `-sub_charenc CP1252` | posé (lu) ; mutation M10 non tuée ici (tests sautés) | OK · CR-147 |
| RC-17 | profil `audio_languages = "fre"` (chaîne) | refusé ou lu comme `["fre"]` | piste `fre` exclue en silence | KO · CR-120 |
| RC-18 | profil `bitrate_1080p_kbps = "5000"` | refusé ou converti | `TypeError` dans `decide` : tout fichier « illisible » | KO · CR-120 |

### 4.3 Greffe, recalage, mux, collage

| Cas | Scénario | Attendu | Obtenu | Verdict |
|---|---|---|---|---|
| RC-19 | mux, `Film.mux-iris.mkv` déjà présent | refus ou numérotation | écrasé (22 octets → 36 840) | KO · CR-113 |
| RC-20 | collage, sortie déjà présente | refus | refus, message | OK |
| RC-21 | deux sous-titres `fre` d'un donneur, recalés par plages (`P`) | deux fichiers | `Film2_fre.iris_recale.srt` pour les deux | KO · CR-115 |
| RC-22 | extrait de contrôle (`K`), sous-titre embarqué dans un conteneur de 150 Mo | extraction de la piste | `read_cues` lit le conteneur : 5,2 s, 629 Mo de mémoire | KO · CR-116 |
| RC-23 | code 1 de mkvmerge | succès | succès (mutation M3 tuée) | OK |
| RC-24 | collage réel de deux parties (smoke 19d) | `Film.join-iris.mkv`, durée vérifiée | écrit, relu | OK |
| RC-25 | greffe d'un `.srt`, mesure, propagation (smoke 21b) | langue `fre`, décalage mesuré | conforme | OK |

### 4.4 File d'encodage et suppression

| Cas | Scénario | Attendu | Obtenu | Verdict |
|---|---|---|---|---|
| RC-26 | titre de disque, `delete_source` | jamais supprimé | conservé (mutation M4 tuée) | OK |
| RC-27 | `S` pendant un fichier, `delete_source` | source gardée | gardée (mutation M8 tuée) | OK |
| RC-28 | passe principale, ffmpeg code 0 | sortie vérifiée avant suppression | seule la piste audio est contrôlée, si la sortie existe | KO · CR-127 |
| RC-29 | copie Dolby Vision (`-c:v copy`) réussie | vitesse non retenue | `record_measured_speed(…, ENCODE_HEVC, …)` | KO · CR-126 |
| RC-30 | exception autre que `ValueError` dans le worker | fichier en échec, lot poursuivi | worker en erreur : l'application se ferme | KO · CR-125 |
| RC-31 | encodage réel d'un fichier (prises 16, 16b) | bilan, sortie nommée | conforme | OK |

### 4.5 Fichiers de réglages et lancement

| Cas | Scénario | Attendu | Obtenu | Verdict |
|---|---|---|---|---|
| RC-32 | `config.toml` à la syntaxe invalide | session sur les défauts, fichier intact | conforme (tests) | OK |
| RC-33 | `config.toml` : `tui = 1` | idem | `AttributeError` (`get_column_widths`) | KO · CR-121 |
| RC-34 | `config.toml` : `app = "x"` | idem | `AttributeError` dans `assurer_langue`, avant la bannière | KO · CR-121 |
| RC-35 | `[stats.encode_speed] hevc = "vite"` | idem | `ValueError` | KO · CR-121 |
| RC-36 | premier lancement, `profiles.toml` impossible à écrire | démarrage sur les profils livrés | `OSError` non rattrapée | KO · CR-122 |
| RC-37 | versions des sept fichiers | 0.9.2.6 partout | conforme | OK |
| RC-38 | bornes de `requirements.txt` (`dependances.py`) | contrôlées | conforme | OK |

### 4.6 Interface — accueil

| Cas | Scénario | Attendu | Obtenu | Verdict |
|---|---|---|---|---|
| RC-39 | liste d'un dossier, 160×45 | colonnes lisibles, rien de coupé en silence | conforme ; nom de fichier coupé au milieu à 22 caractères | OK |
| RC-40 | sortie d'IRIS dans le dossier | grisée, hors de `A` | conforme | OK |
| RC-41 | barre du profil, seconde ligne (« Audio HD », « ⚠ SUPPRESSION ») | visible | jamais rendue | KO · CR-135 |
| RC-42 | `Ctrl+P` | rien, ou une fonction de l'application | palette de commandes Textual, en anglais | KO · CR-139 |
| RC-43 | chemin long dans la barre d'état | compteurs visibles | le chemin pousse les compteurs hors de l'écran | KO · CR-141 |
| RC-44 | « Estim. » d'une sortie de même taille | « 0 % » | « 2 Mo (-0%) » | KO · CR-141 |
| RC-45 | langue de piste inconnue | une seule notation | « ? » et « und » | KO · CR-141 |
| RC-46 | 80×24 | utilisable, ou largeur minimale dite | colonne Décision hors écran ; rien ne le dit | KO · CR-141 |
| RC-47 | `F1` / `F2` sans rien de coché | message | message | OK |
| RC-48 | `R` hors d'un dossier | message | message | OK |
| RC-49 | `R` deux fois, ou navigation pendant l'analyse | un seul aperçu, là où il a été demandé | worker non exclusif ; l'aperçu se pose sur l'écran courant | KO · CR-128 |
| RC-50 | `H` depuis l'accueil, l'aperçu, une saisie | guide ; lettre dans la saisie | conforme | OK |
| RC-51 | `Esc` pendant le chargement d'une fiche (`I`) ou d'OpenSubtitles | pas de fermeture | application en vie | OK |

### 4.7 Interface — pistes, assistant, aperçu, profils

| Cas | Scénario | Attendu | Obtenu | Verdict |
|---|---|---|---|---|
| RC-52 | Pistes : `␣` sur un sous-titre | la ligne suit | case `[ ]`, mais « sélectionné » et « → copie MP4 » restent | KO · CR-136 |
| RC-53 | Pistes : bandeau d'aide du champ | visible | jamais rendu | KO · CR-135 |
| RC-54 | Pistes : ligne vidéo à 160 colonnes | champs visibles | « DV » et « original » hors écran | KO · CR-136 |
| RC-55 | Pistes : ligne vidéo d'un SKIP | pas de débit | « 0 kbps » | KO · CR-136 |
| RC-56 | Pistes : `␣` sur la piste d'origine `⚑` | refus dit | refus muet | KO · CR-141 |
| RC-57 | Pistes : `F4`, autre profil | cases et décisions cohérentes | décisions refaites, cases gardées ; `subtitle_languages` non appliqué | KO · CR-132 |
| RC-58 | Assistant : `␣` sur la piste audio d'origine | même règle que Pistes | écartée | KO · CR-138 |
| RC-59 | Assistant : `F7` sur un SKIP, puis `F2` | débit choisi | débit de la source | KO · CR-133 |
| RC-60 | Assistant : cinq étapes, retour, `F3` sans piste | conforme au guide | conforme (smoke 15) | OK |
| RC-61 | Aperçu : décocher une ligne | compte à jour | « 4 fichiers sélectionnés », « HEVC 2 · H264 2 » inchangés | KO · CR-137 |
| RC-62 | Aperçu : colonne Estim. | entière ou ellipse | « 435 Ko (+28% » | KO · CR-137 |
| RC-63 | Aperçu : mention « désentrelacé » | lisible | « 1280x720 · … » | KO · CR-137 |
| RC-64 | Profils : `+` / `-` sur une liste | valeur suivante / précédente | sans effet | KO · CR-134 |
| RC-65 | Profils : éditer un profil à `preset_encoder = "slower"`, `Ctrl+S` | valeur gardée | `medium` | KO · CR-131 |
| RC-66 | Profils : débit hors liste (4 321) | gardé | gardé | OK |
| RC-67 | Options, emplacements, quitter, choix du profil | conformes aux captures attendues | conformes | OK |

### 4.8 Documentation et tests

| Cas | Scénario | Attendu | Obtenu | Verdict |
|---|---|---|---|---|
| RC-68 | `python outils/i18n.py tout` | aucun écart | aucun | OK |
| RC-69 | `.po` français | tout traduit | 1 129 entrées, 0 vide, 0 `fuzzy` | OK |
| RC-70 | guides et README, deux langues | même structure, liens valides | 43 / 43 et 38 / 38 titres, aucun lien cassé | OK |
| RC-71 | README, règle 4K | celle du code (3 200 / 1 700) | « ≥ 2160 high or ≥ 3840 wide » | KO · CR-143 |
| RC-72 | guide intégré | « chaque touche de chaque écran » | neuf écrans sur une vingtaine ; deux explications inexactes | KO · CR-142 |
| RC-73 | mutations M1 à M9 | tuées | tuées | OK |
| RC-74 | `tests/test_dvd.py` seul | passe | un échec lié à l'ordre | KO · CR-146 |

## 5. Constats

### 5.1 Critiques

- **CR-113** · `tui/screens/mux_run.py:83,146,177,259` · critique · P, R · reproduit — Le mux écrase une sortie existante, et l'efface en cas d'arrêt.
  - Scénario : `Film.mkv` a déjà été muxé (`Film.mux-iris.mkv`). On y greffe une autre piste, `F3` : `mux_output_path` rend le même nom, `MuxScreen._run` ne regarde pas s'il existe, mkvmerge le remplace. `⌫`, `Ctrl+Début` ou `F10` pendant le mux, ou un échec, appellent `self._output.unlink()` : le fichier d'avant a disparu. La file numérote (`resoudre_sorties`), le collage refuse (`JoinScreen.action_coller`) ; le mux ne fait ni l'un ni l'autre.
  - Correction : même règle que la file — numéroter (`_sans_collision`) — et n'effacer que le fichier que ce mux a créé.
  - Test : `MuxScreen` sur une source dont le `.mux-iris.mkv` existe ; l'ancien fichier garde son contenu, le nouveau porte `(2)`.

- **CR-114** · `core/scanner.py:642`, `core/decision.py:888` · critique · J · reproduit — Une vidéo verticale est prise pour de la 4K.
  - Scénario : `is_4k` vaut `width >= 3200 or height >= 1700`. Un 1080×1920 (téléphone, Short téléchargé par `U`) y répond. Profil sans `keep_4k` : limites 1920×1080, donc `scale=1920:1080:force_original_aspect_ratio=decrease` → 608×1080, et le nom perd sa marque de définition. Profil `keep_4k` : jugé à la tranche 4K (8 000k pour `movie_4k_std`), donc SKIP là où un 1080p serait réencodé.
  - Correction : classer sur les deux dimensions triées (grand côté ≥ 3 200 **et** petit côté ≥ 1 700, ou l'aire), et appliquer les limites dans l'orientation de la source.
  - Test : `decide` sur 1080×1920 → tranche 1080p, cadre de sortie 1080×1920.

- **CR-115** · `tui/screens/sync.py:1133` · critique · J · reproduit — Deux pistes de même langue recalées par plages partagent leur fichier.
  - Scénario : un donneur porte « Français (complet) » et « Français (forced) » ; la mesure trouve un autre montage, `P` sur chacune. `_fichier_recale` nomme `<source>_<langue>.iris_recale.srt` : les deux pistes écrivent `Film_fre.iris_recale.srt`, la seconde remplace la première, et les deux `ExternalTrack` pointent dessus (`source_tid = 0`). La sortie porte deux fois le même sous-titre ; l'autre est perdu, sans message. Même nom pour une audio et un sous-titre recalés deux fois de suite.
  - Correction : nommer sur l'identité de la piste (rang ou `source_tid` d'origine), et refuser un nom déjà pris par une autre piste de la liste.
  - Test : deux `ExternalTrack` `fre` du même donneur → deux chemins distincts.

### 5.2 Majeurs

- **CR-116** · `tui/screens/sync.py:1096`, `core/sync.py:449` · majeur · J, C · reproduit — `K` lit le donneur entier en mémoire.
  - Scénario : la première piste de sous-titres vient d'un conteneur (un autre `.mkv` du film — le cas courant). `_build_sample` appelle `read_cues(subs.source_path)` : `_read_text` charge tout le fichier et tente quatre décodages. Mesuré sur 150 Mo : 5,2 s et 629 Mo ; un donneur de 8 Go en demanderait une trentaine. L'appel est hors du `try` : un `MemoryError` met le worker en erreur. `_ouvrir_mpv` extrait d'abord la piste (CR-52), pas l'extrait.
  - Correction : passer par `_en_texte` comme `V` et `R`, ou ne lire que les fichiers de `_TEXT_SUB_EXT`.
  - Test : `_build_sample` avec un donneur `.mkv` → `read_cues` n'est jamais appelé sur lui.

- **CR-117** · `core/encoder.py:1390` · majeur · S, J · reproduit (ffmpeg 6.1.1) — Un `mov_text` recopié vers Matroska fait échouer l'encodage.
  - Scénario : source MP4 à sous-titres `mov_text`, sortie MKV (profil `container = "mkv"`, piste sans perte gardée, greffe ASS ou PGS). `build_command` pose `-c:s copy` ; le muxeur Matroska refuse : « Subtitle codec 94213 is not supported », code 218. L'écran dit « Conversion failed! ».
  - Correction : en sortie MKV, `-c:s:N srt` pour une piste `mov_text` (par flux, pas globalement), ou passer ces pistes par le porteur.
  - Test : `build_command` sur une source à `mov_text` et sortie `.mkv`, puis ffmpeg réel sur une mire.

- **CR-118** · `core/decision.py:1094-1097`, `core/encoder.py:751-778` · majeur · J, R · reproduit — Le chemin automatique encode du HDR en H264 8 bits.
  - Scénario : source HDR10 sous la tranche 1080p (un 720p HDR). `_decide_video_classique` choisit `ENCODE_H264` sans passer par `h264_force_sdr` : `libx264 -pix_fmt yuv420p`, courbe PQ gardée, ni conversion ni avertissement. `choisir_codec` — le chemin manuel — passe en SDR depuis l'arbitrage du 2026-10-09 ; la spec (§ 14.0, « Pas de H264 en HDR ») ne décrit que lui. Le docstring de `_encodeur_et_format` assume encore l'ancien comportement.
  - Correction : une seule règle — HEVC pour une source HDR quelle que soit la tranche (ce que fait déjà `force_skip_to_encode`), ou `dv_action = SDR` dès la décision automatique.
  - Test : `decide` sur 1280×720 `smpte2084` → jamais `ENCODE_H264` avec `dv_action != SDR`.

- **CR-119** · `core/decision.py:590-594` · majeur · J, D · reproduit — `container = "mp4"` écarte aussi les sous-titres stylés, sans regarder la langue.
  - Scénario : animé avec un ASS français et un SRT anglais. `sous_titres_ecartes` retient « image **ou** `_needs_mkv_codec` » et écarte dès qu'il reste un sous-titre texte : l'ASS français part, le SRT anglais reste. Le docstring parle d'« une piste doublée par un SubRip » ; la spec (§ 8.6) et le formulaire de profil n'annoncent que les sous-titres **image**. L'aperçu dit « −1 st », sans dire lequel.
  - Correction : n'écarter que ce qu'un texte de même langue et de même nature double (la règle de `_pgs_doubles`), convertir un ASS seul de sa langue en `mov_text`, ou céder le conteneur ; et nommer la piste écartée.
  - Test : ASS `fre` + SRT `eng`, `container = "mp4"` → le français n'est pas perdu.

- **CR-120** · `core/profiles.py:105-118`, `core/decision.py:1353-1356` · majeur · J · reproduit — `profiles.toml` n'est contrôlé ni en type ni en valeur.
  - Scénario : (a) `audio_languages = "fre"` — une chaîne au lieu d'une liste : `{normalize_language(l) for l in languages}` itère ses lettres, aucune piste hors de l'originale ne correspond, la piste française est exclue sans un mot. (b) `bitrate_1080p_kbps = "5000"` : `"5000" * 1000`, puis `TypeError` dans `debit_au_dessus_de_la_cible` ; sur l'accueil chaque fichier s'affiche « illisible : '>' not supported… ». Le fichier est annoncé « réparable à la main ».
  - Correction : valider à `load_all` (types, valeurs connues de `dolby_vision`, `container`, `audio_hd_codec`…), dire le profil et la clé fautifs, et retomber sur le défaut de la clé.
  - Test : chaque clé avec un type faux → message, pas d'exception ni d'exclusion.

### 5.3 Mineurs — justesse, robustesse, concurrence

- **CR-121** · `core/config.py:162,230,312,330,343` · mineur · J · reproduit — Un `config.toml` valide mais mal typé ferme l'application au lancement.
  - Scénario : `tui = 1` → `AttributeError` dans `get_column_widths` ; `app = "x"` → `AttributeError` dans `assurer_langue`, avant même la bannière ; `[stats.encode_speed] hevc = "vite"` → `ValueError`. `illisible()` reste `None` : la protection de CR-43 ne voit que les erreurs de syntaxe.
  - Correction : après `_deep_merge`, ramener au défaut toute branche dont le type diffère de celui de `_DEFAULTS`, et le dire comme pour un fichier illisible.
  - Test : les trois fichiers ci-dessus → session sur les défauts, fichier intact.

- **CR-122** · `core/profiles.py:199-205`, `tui/app.py:26,107` · mineur · W · reproduit — Premier lancement dans un dossier non inscriptible : trace Python.
  - Scénario : `profiles.toml` absent, écriture refusée (dossier protégé, disque plein). `load_all` → `save_all` → `OSError`, levée dans `IrisEncodeApp.__init__`. `_setup_logging` (`mkdir` et `basicConfig` sur `~/.iris_encode`) a la même forme.
  - Correction : rattraper `OSError`, tenir la session sur les profils livrés, le dire une fois.
  - Test : `PROFILES_PATH` sous un dossier absent → `load_all` rend les profils livrés.

- **CR-123** · `core/sous_titres.py:212-218`, `core/sync.py:449-455` · mineur · J · reproduit (ffmpeg 6.1.1) — Un `.srt` en UTF-16 est déclaré cp1252.
  - Scénario : fichier enregistré « Unicode » par un éditeur Windows. `encodage_texte` essaie UTF-8 puis cp1252, qui accepte presque tout octet : `-sub_charenc CP1252`, code 0, « Ã‰tÃ© Ã  NoÃ«l ». `_read_text` suit la même liste : aucune réplique lue, la mesure est refusée.
  - Correction : reconnaître les BOM `FF FE` / `FE FF` avant les essais ; réécrire le fichier en UTF-8 dans un intermédiaire.
  - Test : `.srt` UTF-16 accentué greffé → texte identique en sortie.

- **CR-124** · `tui/screens/mux_run.py:182-220`, `tui/screens/run.py:277-293` · mineur · C, R · lu — Analyses lancées sur le fil d'interface.
  - Scénario : (a) après un mux réussi, `_adopt_output` appelle `scanner.scan` sur le fil d'interface — ffprobe, et pour une source SD sans SAR huit passages de `cropdetect` et trois requêtes Wikidata. L'information neuve a `entrelacement_lu = False` : `F1` (`DryrunScreen._build_table` → `dec.telecine_inverse`) ou `F2` (`RunScreen._build_table` → `chaine_prevue` → `build_command` → `decision.desentrelace`) lancent alors l'analyse d'entrelacement, 4 à 30 s de ffmpeg, interface figée — ce que la v0.9.2.2 avait sorti du listage. (b) `RunScreen._build_table` construit une commande par fichier sur le fil d'interface : `mkvmerge -J` (délai 30 s), ffprobe du donneur, lecture des `.srt`, `resolve()` ; seule `ValueError` y est rattrapée.
  - Correction : relire le fichier muxé dans le worker du mux et y faire l'analyse ; calculer la chaîne prévue hors du fil, ou la lire sans construire la commande.
  - Test : après adoption, aucune commande ffmpeg ne part du fil d'interface (espion sur `subprocess.run`).

- **CR-125** · `tui/screens/run.py:508`, `tui/screens/opensubtitles.py` (workers) · mineur · C, R · lu — Une exception imprévue dans un worker ferme l'application.
  - Scénario : `_encode_next` ne rattrape que `ValueError` autour de `build_command`. Une `OSError` (`unlink`, `write_text`, `stat` sur un partage qui tombe), une `UnicodeDecodeError` à la lecture d'un `.srt` extrait, une réponse inattendue d'un outil : le worker (`exit_on_error` par défaut) arrête l'application au milieu du lot. Même forme pour `os-search` et `os-download`, qui n'attrapent que `(ErreurOpenSubtitles, OSError)` — un JSON de forme inattendue passe au travers. C'est la famille 4 de la revue précédente, traitée cas par cas.
  - Correction : un filet par fichier dans la boucle d'encodage — état `ERROR`, cause au journal, fichier suivant ; `except Exception` dans les workers de service.
  - Test : `build_command` remplacé par une fonction qui lève `RuntimeError` → fichier en échec, lot terminé, application en vie.

- **CR-126** · `tui/screens/run.py:722-724`, `tui/common.py:31-56,351-357` · mineur · J · lu — La vitesse mesurée mélange des chemins sans rapport.
  - Scénario : `record_measured_speed(cfg, dec.video.action, vitesse)` range tout sous la clé du codec. Une copie Dolby Vision (`ENCODE_HEVC` avec `-c:v copy`, plus de 100×) entre dans la moyenne « hevc » ; un `libx265` en mode `quality` (0,3×), une conversion SDR ou une super-résolution aussi. La colonne ETA suivante est fausse d'un ordre de grandeur. À l'inverse `ENCODE_DV` n'a ni clé ni facteur : jamais mesuré, estimé au facteur 1,0.
  - Correction : ne rien enregistrer quand la vidéo est recopiée ; une clé par encodeur effectif (`encodeur_de(cmd)`) plutôt que par codec.
  - Test : un succès `video_recopiee` ne change pas `[stats.encode_speed]`.

- **CR-127** · `tui/screens/run.py:701-727` · mineur · P, R · lu — La passe principale supprime la source sans vérifier la sortie.
  - Scénario : `success = rc == 0` ; le contrôle des pistes vides n'a lieu que si `dec.output_path.exists()`, et rien n'est dit s'il n'existe pas. Avec `delete_source`, `_supprimer_source` suit. Les chemins Dolby Vision, le mux et le collage exigent `sortie.exists()` ; le collage compare la durée.
  - Correction : exiger une sortie présente, non vide et de durée cohérente avant de dire « réussi », dans une fonction commune aux quatre chemins.
  - Test : ffmpeg simulé rendant 0 sans rien écrire → `ERROR`, source intacte.

- **CR-128** · `tui/screens/browser.py:2098-2146` · mineur · C · lu — Le scan récursif finit dans un monde qui a changé.
  - Scénario : `R` sur un dossier, analyse de plusieurs minutes. Le worker n'est pas exclusif : `R` une seconde fois lance un second scan et deux aperçus. À la fin, `_push` empile l'aperçu sur l'écran courant quel qu'il soit — un autre dossier, l'écran des pistes, une modale, la vue des encodages après `F12`.
  - Correction : `exclusive=True`, et n'ouvrir l'aperçu que si l'accueil est au premier plan ; sinon une notification.
  - Test : `R`, puis `T` pendant l'analyse → pas d'aperçu par-dessus l'écran des pistes.

- **CR-129** · `core/scanner.py:1025-1029`, `core/decision.py:1125` · mineur · J · reproduit — Un fichier sans flux vidéo reçoit une décision d'encodage.
  - Scénario : un `.mp4` ou un `.ts` qui ne porte que de l'audio. `vid = {}` : 0×0, codec `unknown`, débit 0 → « → H264 · Unknown bitrate → 3000k target », puis ffmpeg échoue sur `-map 0:v:0`.
  - Correction : lever dans `scan` (« no video stream ») : la ligne s'affiche illisible, avec sa cause.
  - Test : `scan` d'un fichier audio seul → erreur nommée.

- **CR-130** · `core/scanner.py:1269-1280` · mineur · W · supposé — Le scan récursif entre dans la corbeille.
  - Scénario : `R` sur la racine d'un lecteur. `os.walk` descend dans `$RECYCLE.BIN` et `System Volume Information` : des vidéos supprimées (`$R….mkv`) seraient analysées et mises dans l'aperçu.
  - Correction : écarter les dossiers système et cachés (`FILE_ATTRIBUTE_HIDDEN | SYSTEM`, noms en `$` ou `.`).
  - Test : arborescence avec un `$RECYCLE.BIN` factice → ses fichiers ne sortent pas.

- **CR-131** · `tui/widgets/profile_form.py:129-138,542-552` · mineur · J · reproduit — Éditer un profil remplace une valeur texte hors liste.
  - Scénario : `preset_encoder = "slower"` (accepté par ffmpeg, et prévu par `_QUALITE_AMF`). `_avec_valeur` ne complète la liste que pour un entier ; `sel.value = "slower"` lève, l'exception est avalée, le champ reste vide et `dump()` rend `"medium"`. `Ctrl+S` écrit `medium` dans `profiles.toml`.
  - Correction : compléter la liste pour toute valeur, ou refuser d'enregistrer un champ que le formulaire n'a pas su afficher.
  - Test : `load` puis `dump` d'un profil à `preset_encoder = "slower"` → `slower`.

- **CR-132** · `tui/screens/tracks.py:759-778` · mineur · J · lu — `F4` dans l'écran des pistes laisse cases et décisions en désaccord.
  - Scénario : nouveau profil aux langues différentes. `decide_video` et `decide_audio` sont refaits, `_sel_audio` et `_sel_subs` non : une ligne « ← écartée » reste cochée, et `↵` rend l'ancienne sélection. `subtitle_indices` n'est pas recalculé : `subtitle_languages` du nouveau profil ne s'applique pas.
  - Correction : refaire la décision entière (`decide`) et réinitialiser la sélection.
  - Test : `F4` vers un profil sans `eng` → la piste anglaise n'est plus cochée.

- **CR-133** · `tui/screens/wizard.py:429-440,562-577` · mineur · J · lu — Dans l'assistant, un débit choisi sur un SKIP est perdu.
  - Scénario : fichier SKIP, étape 2, `F7` → 2 000k ; l'écran affiche « ← SKIP · 2000k visés ». `F2` passe par `force_skip_to_encode`, qui repose le débit de la source.
  - Correction : garder un débit explicite au forçage, ou refuser `F7` tant que rien n'est réencodé, en le disant.
  - Test : `F7` puis `_a_encoder()` → le débit choisi.

### 5.4 Mineurs — interface

- **CR-134** · `tui/widgets/profile_form.py:726` · mineur · UI · reproduit — `+` et `-` ne font rien dans le formulaire de profil.
  - Scénario : Textual nomme ces touches `plus` et `minus` ; `on_key` compare à `"+"` et `"-"`. Le pied de page annonce « +/-  Valeur suiv./préc. ».
  - Correction : comparer `event.character`, ou les noms `plus`, `minus`, `kp_plus`, `kp_minus`.
  - Test : `pilot.press("+")` sur une liste focalisée → la valeur change.

- **CR-135** · `tui/screens/tracks.py:163-169`, `tui/screens/browser.py:461-467` · mineur · UI · reproduit — Deux bandeaux ne s'affichent jamais.
  - Scénario : `#hint-bar` a `height: 1` et `border-top` — la bordure prend la ligne : l'aide du champ (« ←/→ Champ  +/- Valeur… ») n'est jamais rendue. `#profile-bar` a `height: 2` et `border-bottom` : sa seconde ligne — « Audio HD » et « ⚠ SUPPRESSION » d'un profil qui efface les sources — non plus. Les deux textes existent dans le widget : un test qui lit `render()` les voit, l'écran non.
  - Correction : `height: 2` et `height: 3` (ou retirer la bordure).
  - Test : chercher le texte dans `app.export_screenshot()`, pas dans le widget.

- **CR-136** · `tui/screens/tracks.py:390-483,494-501` · mineur · UI · reproduit — L'écran des pistes ne suit pas ce qu'on y fait.
  - Scénario : (a) `␣` ne réécrit que la case : « sélectionné » et « → copie MP4 » restent en vert sur une piste décochée, et le conteneur de la ligne vidéo (MP4 / MKV) ne bouge pas quand on décoche le PGS qui l'imposait. (b) À 160 colonnes la ligne vidéo déborde : les champs « DV » et « original », atteignables par `←/→`, sont hors écran. (c) Un SKIP affiche « 0 kbps », et le garde après avoir choisi HEVC.
  - Correction : reconstruire la ligne à chaque bascule, sur la sélection en cours ; replier la ligne vidéo sur deux lignes ; « — » sans débit.
  - Test : après `␣`, la colonne Décision de la ligne dit « ← écartée ».

- **CR-137** · `tui/screens/dryrun.py:58-87,247-262,302-342,601-603`, `core/config.py:355-367` · mineur · UI, R · reproduit — L'aperçu compte et coupe mal.
  - Scénario : (a) décocher une ligne ne change ni « 4 fichiers sélectionnés » ni « À encoder : HEVC 2 · H264 2 » ni les totaux. (b) Estim. fait 12 colonnes et écrit un `Text` nu : « 435 Ko (+28% » sans ellipse (l'accueil en donne 14 et passe par `cellule`). (c) La mention « · désentrelacé » ajoutée à Résolution (12) sort en « 1280x720 · … ». (d) `_estimate_output_bytes` est une copie de celle de l'accueil, et la teinte diffère (dégradé là, alerte ici ; « (+0%) » pour une sortie recopiée). (e) `action_run` parcourt un `set` — l'ordre que `browser._cochees` trie exprès. (f) L'ETA lit le preset du profil actif, pas celui de la décision. (g) Chaque touche reconstruit la table et relit la taille de chaque fichier sur le disque.
  - Correction : compter sur `_selected` ; une seule fonction d'estimation et de teinte ; largeurs et `cellule` comme sur l'accueil ; `sorted(self._selected)`.
  - Test : décocher une ligne → le compte baisse ; `tests/test_troncature.py` étendu à l'aperçu.

- **CR-138** · `tui/screens/wizard.py:517-536` · mineur · UI, J · reproduit — L'assistant laisse écarter la piste audio d'origine.
  - Scénario : étape 2, `␣` sur `0:a:0` : `['TRANSCODE', 'COPY']` → `['EXCLUDE', 'COPY']`. L'écran des pistes la verrouille (`⚑`). On peut écarter toutes les pistes : sortie sans son.
  - Correction : la même garde `locked` que `TracksScreen.action_toggle_row`, avec un message.
  - Test : `action_basculer` sur la piste verrouillée → inchangée.

- **CR-139** · `tui/app.py:47` · mineur · G1 · reproduit — La palette de commandes de Textual est ouverte à l'utilisateur.
  - Scénario : `Ctrl+P`, ou un clic sur l'icône de l'en-tête : « Keys », « Maximize », « Quit », « Screenshot », « Theme », en anglais dans les deux langues, hors catalogue, absente du guide. « Theme » change les couleurs de la session.
  - Correction : `ENABLE_COMMAND_PALETTE = False` (et l'icône de l'en-tête sans action), ou l'assumer et la traduire.
  - Test : `pilot.press("ctrl+p")` → l'écran ne change pas.

- **CR-140** · `core/decision.py:880-898`, `tui/screens/dryrun.py:205`, `tui/screens/tracks.py:443` · mineur · UI · reproduit — La « résolution » affichée est le cadre maximal.
  - Scénario : source 720×480 : l'aperçu et l'écran des pistes écrivent « 1280x720 », `target_width` × `target_height` étant les limites. Rien n'est agrandi (hors super-résolution), mais l'écran le laisse croire.
  - Correction : afficher `dimensions_reduites(largeur_affichee, hauteur, cible)` quand la source tient dans le cadre.
  - Test : libellé d'une source 720×480 → sa définition de sortie.

- **CR-141** · divers · mineur · UI · reproduit et lu — Touches muettes et libellés.
  - (a) `␣` sur la piste verrouillée, `+/-` sur « DV » quand H264 impose le SDR, `P` pendant une étape mkvmerge de la file : sans effet ni message — la règle « une touche sans effet se lit comme une touche cassée » (UX-17) n'y est pas tenue.
  - (b) « 2 Mo (-0%) » : le signe d'un écart arrondi à zéro (`browser._row_cells`, `run._taille`).
  - (c) Langue inconnue : « ? » (vide) et « und » dans la même colonne.
  - (d) Barre d'état de l'accueil : un chemin long n'est pas raccourci, les compteurs sortent de l'écran ; à 80 colonnes il n'y a plus que lui. Aucune largeur minimale n'est dite ; à 80×24 la colonne Décision est hors écran.
  - (e) « CTRL+↑/↓ » sur le recalage, « Ctrl+Début » ailleurs (`touche()` met en capitales une notation composée).
  - (f) `mixins._refus_elargir` : « rétrécissez-en une autre ({column} peut encore être réduite) » nomme la colonne qu'on élargit.
  - (g) `_LANGS` du recalage : neuf langues — une piste sans langue ne peut pas recevoir `kor`, `dut`, `pol`…
  - (h) Assistant, étape « Lancer », sur un retrait Dolby Vision : « Recommandé : encoder ».
  - (i) Guide intégré en français : un « : » en début de ligne (espace sécable dans la traduction).

### 5.5 Mineurs — documentation

- **CR-142** · `tui/screens/aide.py:132-134,153-154,352-365,492-495` · mineur · D · lu — Le guide intégré dit autre chose que l'application.
  - Scénario : (a) « Chaque touche de chaque écran » : `classes_documentees` en compte neuf. Manquent YouTube et sa liste de chaîne (`+`), les emplacements (`Inser`, `Ctrl+D`, `Ctrl+T`), les options, le choix du donneur (`O`), OpenSubtitles, la fiche (`Tab`), la proportion, les plages, le point d'ancrage, les clés. (b) `filtre_type` ne cite ni « remux », ni « audio DTS », ni « sous-titres image », ajoutés le 2026-11-08. (c) `TracksScreen.enter_action` : « ouvre la liste des valeurs » — sur une piste, `↵` **valide** la sélection ; sur une piste externe, il ouvre le recalage. (d) « Resync » et « Sync » pour le même écran dans la source anglaise.
  - Correction : dériver aussi les modales ; corriger les deux explications ; `tests/test_aide.py` compare la liste des écrans à ceux qui déclarent des `BINDINGS`.
  - Test : tout écran à `BINDINGS` figure dans le guide ou dans une liste d'exclusions motivée.

- **CR-143** · `README.md:91`, `README.fr.md:91`, `iris_encode_spec.md` § 8.6 et § 14.0, commentaires · mineur · D · lu — Textes en retard sur le code.
  - (a) README : « 4K source? (≥ 2160 high or ≥ 3840 wide) » — le code et la spec § 8.1 disent 3 200 de large ou 1 700 de haut depuis la v0.8.9.77.
  - (b) Spec § 14.0 « Pas de H264 en HDR » : vrai du choix manuel seulement (CR-118). Spec § 8.6 `mp4` : « les sous-titres image sont écartés » — les ASS aussi (CR-119).
  - (c) `tui/widgets/profile_form.py` `_CONTENEUR_TXT["mp4"]` : même écart, affiché à l'utilisateur.
  - (d) Commentaires périmés : « Ctrl+A » pour la touche `A` (`browser.py`, quatre endroits), « Tri de la vue (S) » pour `O`, `file_tree.list_videos` cite `scanner.scan_directory`, disparue ; `scanner.set_ffprobe_path` dit « ffmpeg » ; `encoder._encodeur_et_format` décrit le H264 HDR 8 bits comme voulu.
  - (e) `core/emplacements.py:146` : la docstring contient un caractère de saut de page — `\\nas\films` devenu `\nas<FF>ilms`.

### 5.6 Mineurs — hygiène et performance

- **CR-144** · divers · mineur · M · lu — Code mort.
  - `logger/logger.py` : une API inerte importée nulle part (la spec § 19 la décrit « sans backend »).
  - Imports inutiles : `core/meta.py:128-129` (`json`, `requests`, `quote`), `core/encoder.py:15` (`Callable`), `core/dovi.py:30` (`json`), `tui/screens/profile_picker.py:20` et `config.py:21` (`PROFIL_COLONNES`), `tui/screens/dryrun.py:21` (`DVAction`), `tui/widgets/profile_form.py:9,20` (`dataclass`, `raccourcis`).
  - `scanner._LOSSLESS_CODECS` et `_HD_AUDIO_CODECS` portent `dts-hd ma` et `dtshd`, que ffprobe ne rend jamais.
  - `BrowserScreen._resize_persist` écrit `config.toml` (avec `fsync`) à chaque `<` / `>`, alors que `on_mount` jette ces largeurs à chaque lancement (`reset_browser_columns`).
  - `core/sync.py:1003` : une ligne coupée par une longue suite d'espaces.

- **CR-145** · divers · mineur · performance · lu — Coûts répétés.
  - `analyses.lire` réécrit tout `analyses.json` à la première lecture du jour de **chaque** entrée ; `_en_cours` grandit sans borne.
  - `EncoderProcess.iter_progress` appelle `octets_ecrits` à chaque ligne de ffmpeg : sous Windows, une classe `ctypes` et un `WinDLL` recréés à chaque ligne.
  - `DonorTrackScreen.__init__` lance `mkvmerge -J` sur le fil d'interface ; `DonorFileScreen._populate` fait `is_dir`, `resolve` et `stat` par entrée.

### 5.7 Mineurs — tests

- **CR-146** · `tests/test_dvd.py:413`, `tests/conftest.py:35-47` · mineur · T · reproduit — Un test dépend d'un état global laissé par un autre.
  - Scénario : `test_le_lpcm_devient_un_pcm_de_meme_profondeur` appelle `build_extraction_command`, qui lève depuis CR-08 quand `core.dvd._ffmpeg` est `None`. Le test ne le pose pas : il ne passe que si un test d'application précédent a appelé `dvd.set_outils` (`tui/app.py:167`) sur une machine où un outil DVD existe. Seul, ou ici, il échoue. `_GLOBALES` de `conftest.py` restaure neuf variables, pas `core.dvd._ffmpeg` / `_ffprobe`, `core.super_resolution._shader`, `core.decision._NEAR_1080P_CACHE`, `core.scanner._ESTIMATIONS_SAR` / `_ECHECS_ENTRELACEMENT`, `core.config._illisible`, `core.profiles._illisible`.
  - Correction : `monkeypatch.setattr(dvd, "_ffmpeg", "ffmpeg-dvd")` dans le test ; compléter `_GLOBALES`.
  - Test : `python -m pytest tests/test_dvd.py -p no:randomly` seul, et la suite dans l'ordre inverse.

- **CR-147** · `tests/` (16 marqueurs `skipif`) · mineur · T · reproduit — Les tests à outils réels ne tournent que sous Windows avec `bin\`.
  - Scénario : `skipif(not (_BIN / "ffmpeg.exe").exists())`. Avec ffmpeg et mkvmerge dans le `PATH` (Linux, macOS — les portages IE-183 et IE-184), ils restent sautés : la mutation qui retire `-sub_charenc` (CR-50) survit ici. À l'inverse, quatorze tests propres à Windows (racine de lecteur, UNC, `.exe`) **échouent** hors de Windows au lieu d'être sautés : une suite rouge par construction masque un vrai échec.
  - Correction : chercher l'outil comme l'application (`get_tool_path`) ; `skipif(sys.platform != "win32")` sur les quatorze.
  - Test : la suite est verte sous Linux avec les outils du `PATH`.

- **CR-148** · `tests/smoke_tui.py`, `tests/shots_tui.py`, `tests/test_opensubtitles.py`, `tests/test_sar.py:424-426` · mineur · T · reproduit — Les outils de test écrivent hors de leur bac à sable.
  - Scénario : après `python tests/smoke_tui.py` et `python tests/shots_tui.py`, le dossier de l'application porte un `profiles.toml`, un `config.toml` et un `data/analyses.json` : ceux de l'utilisateur seraient modifiés sur son poste (largeurs, vitesses mesurées, dossier YouTube). `_profils_isoles` n'isole que les profils, et pas dans tous les scénarios. `test_opensubtitles` écrit dans le vrai dossier temporaire (`iris_opensubtitles/Film.2019.1080p.42.*.srt`). `test_sar.py` : trois `'\:'` dans des chaînes non brutes (`SyntaxWarning`, erreur dans une version future de Python). Pas de `pytest.ini` : ni `filterwarnings = error`, ni marqueurs déclarés. `shots_tui.py` ne capture rien du contexte A sans `resources_files/` : sur un clone, la revue d'interface n'a que 7 écrans sur 28.
  - Correction : rediriger `CONFIG_PATH`, `PROFILES_PATH` et `analyses.CHEMIN` en tête des deux scripts ; `tmp_path` pour OpenSubtitles ; chaînes brutes ; un jeu synthétique de repli pour les captures.
  - Test : après le smoke, `git status --ignored` ne montre rien de neuf.

## 6. Documentation — état

| Point | État |
|---|---|
| En-têtes de version (`version.py`, `CHANGELOG.md`, spec, deux README, deux guides) | alignés sur 0.9.2.6 |
| CHANGELOG, section de tête | datée, renvoie à la spec et au test |
| Spec § 20, historique | à jour jusqu'à 0.9.2.6 |
| Guides anglais et français | même plan (43 titres), mêmes touches citées, liens valides |
| README anglais et français | même plan (38 titres) ; règle 4K périmée (CR-143) |
| Catalogue `locales/` | régénéré sans écart ; 1 129 entrées simples, 0 vide, 0 `fuzzy` ; 7 identiques à la source (noms propres, codes) |
| Wiki | `tests/test_wiki.py` passe ; relevés de cette revue ingérés (`source-2026-11-13-revue`) |
| Guide intégré (`H`) | incomplet et deux explications inexactes (CR-142) |
| Spec contre code | deux écarts trouvés (CR-118, CR-119) ; non vérifiée ligne à ligne |

## 7. Synthèse

### Entrées de travail proposées

Par ordre de priorité. Estimation en jours, tests compris.

| Entrée | Objet | Constats | Gravité max | Fichiers | Estimation |
|---|---|---|---|---|---|
| IE-185 | Ne jamais écraser hors de la file : mux numéroté, source supprimée après contrôle de la sortie | CR-113, CR-127 | critique | `tui/screens/mux_run.py`, `run.py`, `core/muxer.py` | 0,5 j |
| IE-186 | Géométrie : vidéo verticale, fichier sans image, définition affichée | CR-114, CR-129, CR-140 | critique | `core/scanner.py`, `decision.py`, `tui/screens/dryrun.py`, `tracks.py` | 1 j |
| IE-187 | Recalage : un fichier par piste recalée, extrait `K` sans lire le conteneur, `.srt` UTF-16 | CR-115, CR-116, CR-123 | critique | `tui/screens/sync.py`, `core/sync.py`, `sous_titres.py` | 1 j |
| IE-188 | Sous-titres et conteneur : `mov_text` vers MKV, ce que `mp4` écarte | CR-117, CR-119 | majeur | `core/encoder.py`, `decision.py`, `tui/widgets/profile_form.py`, spec § 8.6 | 1 j |
| IE-189 | HDR sous la tranche 1080p : une règle pour l'automatique et le manuel | CR-118 | majeur | `core/decision.py`, `encoder.py`, spec § 14.0 | 0,5 j |
| IE-190 | Fichiers de réglages : types contrôlés, premier lancement sans écriture, formulaire qui garde ce qu'il ne connaît pas | CR-120, CR-121, CR-122, CR-131 | majeur | `core/profiles.py`, `config.py`, `tui/app.py`, `tui/widgets/profile_form.py` | 1 j |
| IE-191 | Fil d'interface et workers : analyse après un mux, chaîne prévue, filet de la boucle d'encodage, scan récursif | CR-124, CR-125, CR-128 | mineur | `tui/screens/mux_run.py`, `run.py`, `browser.py`, `opensubtitles.py` | 1,5 j |
| IE-192 | Écran des pistes et assistant : lignes qui suivent la sélection, bandeau d'aide, `F4`, piste d'origine, débit d'un SKIP | CR-132, CR-133, CR-135, CR-136, CR-138 | mineur | `tui/screens/tracks.py`, `wizard.py`, `browser.py` | 1,5 j |
| IE-193 | Aperçu et estimation : comptes, largeurs, une seule estimation, vitesse mesurée par encodeur | CR-126, CR-137 | mineur | `tui/screens/dryrun.py`, `run.py`, `tui/common.py`, `core/config.py` | 1 j |
| IE-194 | Interface : `+/-` du formulaire, palette Textual, touches muettes, libellés | CR-134, CR-139, CR-141 | mineur | `tui/widgets/profile_form.py`, `tui/app.py`, `tui/mixins.py`, `tui/screens/sync.py`, `locales/` | 1 j |
| IE-195 | Documentation : guide intégré, README, spec, commentaires | CR-142, CR-143 | mineur | `tui/screens/aide.py`, `README*.md`, `iris_encode_spec.md` | 0,5 j |
| IE-196 | Tests : isolation des globales, sauts selon l'outil et le système, écritures hors bac à sable, captures sans matériel réel | CR-146, CR-147, CR-148 | mineur | `tests/conftest.py`, `tests/*.py` | 1 j |
| IE-197 | Hygiène : code mort, coûts répétés, dossiers système au scan récursif — après décision | CR-130, CR-144, CR-145 | mineur | `logger/`, `core/analyses.py`, `scanner.py`, `encoder.py`, divers | 0,5 j |

Total : environ 12 jours. IE-185 est le plus rentable (une demi-journée pour
une perte évitée) ; IE-186 et IE-189 touchent ce que le téléchargement YouTube
vient de rendre courant (vidéos verticales, 720p HDR).

### Familles de défauts

1. **Les chemins parallèles ont encore divergé.** Le mux hors file ne numérote
   pas (CR-113) et la passe principale ne vérifie pas sa sortie (CR-127), quand
   la file et les chemins Dolby Vision le font ; l'automatique et le manuel ne
   traitent pas le HDR pareil (CR-118) ; l'extrait `K` lit ce que `V` extrait
   (CR-116) ; l'aperçu recopie l'estimation de l'accueil (CR-137) ; l'assistant
   n'a pas la garde de l'écran des pistes (CR-138). C'est la famille 2 de la
   revue précédente.
2. **Une règle écrite pour le paysage.** Le classement 4K et les limites
   supposent une image plus large que haute (CR-114, CR-140).
3. **Ce que l'utilisateur écrit à la main est cru sur parole.** Types de
   `profiles.toml` et de `config.toml` (CR-120, CR-121), valeur hors liste du
   formulaire (CR-131), encodage d'un `.srt` (CR-123).
4. **L'écran dit ce que le widget contient, pas ce qu'il rend.** Bandeaux
   jamais affichés (CR-135), colonnes hors écran (CR-136, CR-141), cellules
   coupées (CR-137), lignes non rafraîchies (CR-136) : les tests lisent le
   contenu du widget et passent.
5. **Du travail long sur le fil d'interface, ou qui finit ailleurs**
   (CR-124, CR-125, CR-128).
6. **Ce qui documente le code est en retard sur lui** (CR-142, CR-143), et
   les tests ne tournent en entier que sur le poste de développement
   (CR-146 à CR-148).

## 8. Questions et décisions à prendre

- **Wikidata au listage.** `_estimer_sar` envoie le titre et l'année d'un film
  à wikidata.org pour toute source SD sans SAR, sans réglage pour le couper ni
  mention ailleurs que dans le guide (§ sur la proportion). À dire dans le
  README, ou à ranger derrière une option ?
- **Analyse d'entrelacement sur image de synthèse.** La mire `testsrc2`
  720×480 à 25 i/s, progressive, est classée `ENTRELACE` (70 % d'images en
  peigne selon `idet`) : `bwdif … deint=all` s'y applique. Portée réelle
  inconnue — animation, images de synthèse à motifs fins ? À essayer sur un
  échantillon progressif réel avant de s'en inquiéter.
- **`dolby_vision = "sdr"`** ne concerne que les sources Dolby Vision : un
  HDR10 simple reste HDR10 avec le profil plancher, dont le commentaire dit
  qu'il « doit produire un fichier qui se lit partout ».
- **Valider l'écran des pistes sans rien changer** fige la sélection en
  « manuelle » : un changement de profil ensuite n'applique plus ses langues à
  ce fichier.
- **Enregistrer un profil l'active** (`ConfigScreen._on_profile_saved`), y
  compris un profil à `delete_source`. Dit par la notice ; voulu ?
- **Le ZIP de release** emporte `tests/` (29 000 lignes), `wiki/`, les rapports
  datés et `outils/` : `.gitattributes` n'exclut que `.claude`. L'updater
  remplace donc trois cents fichiers à chaque version.
- **API privées de Textual** : `App._check_bindings`, `App._screen_stacks`,
  `textual.widgets._header`. Bornées par `textual<9`, à surveiller à la montée
  de version.
- **Vérifications sous Windows et ffmpeg 8.1** : CR-117 et CR-123 (reproduits
  en 6.1.1), CR-130 (corbeille), CR-125 sur un partage qui tombe.
