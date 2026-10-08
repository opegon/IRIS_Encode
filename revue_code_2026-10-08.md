# Revue de code — 2026-10-08 (v0.8.9.96, IE-114)

Revue complète, niveau `max`, de `core/`, `tui/`, `main.py`, `updater.py` et
des lanceurs (`launch.bat`, `bootstrap.ps1`, `launcher/IrisEncodeLauncher.cs`,
`launcher/build.bat`). Branche `revue/ie-114`, partie de `main` à `6d175a3`
(release v0.8.9.96). Rapport daté ; **ce fichier est aussi le journal de
reprise** : la session peut être coupée à tout moment.

Aucune correction n'est faite pendant la revue : chaque constat est calibré
pour être corrigé seul, un incrément de version par entrée, après tri par
l'utilisateur.

## Reprise

1. Lire ce fichier en entier : cadre, critères, constats déjà écrits.
2. Reprendre au **premier fichier non coché** de « Fichiers ». Un fichier coché
   a ses constats sous « Constats » (ou « aucun constat ») ; un fichier non
   coché est à refaire en entier, même s'il était « en cours ».
3. Un fichier à la fois : le lire **en entier**, avec ses appelants si
   nécessaire ; écrire ses constats, cocher sa case, mettre à jour « Dernier
   état ». Rien n'est gardé en mémoire d'un fichier à l'autre.
4. Écriture **atomique** : le journal entier dans `revue_code_2026-10-08.md.tmp`
   (même dossier, ignoré par git via `*.tmp`), `flush` + `fsync`, puis
   `os.replace`. Refuser une écriture qui raccourcit le journal de plus de 10 %.
   (Outil de session : `journal.py`, dans le scratchpad, hors dépôt.)
5. Numérotation : `CR-NN`, à la suite du plus grand numéro déjà écrit.
6. Commit et push du journal sur `revue/ie-114` tous les trois à cinq fichiers.
   Seul ce fichier est modifié. Ni `main`, ni tag, ni release, ni
   `version.py`, CHANGELOG ou spec.
7. Quand tout est coché : « Synthèse » (constats par gravité, entrées de travail
   IE-123…, familles), puis pull request **en brouillon** contenant ce seul
   fichier.

## Dernier état

- 2026-10-08 — `core/opensubtitles.py` fait. 2 constats : .srt cp1252 vidé de ses accents à l'encodage (critique, reproduit avec ffmpeg), langue perdue hors de 8 langues.
- Prochain : `core/preview.py`.

### Pistes notées en route

Observations faites en lisant un appelant, à instruire quand leur fichier vient
(et à retirer une fois instruites).

- `tui/screens/run.py` `_extraire_dvd` (~l. 1300) et `_remux_titre` (~l. 1250) : le détail d'échec est la dernière ligne (`journal[-1]`, `proc.errors[-1]`), pas `encoder.diagnostiquer()` — pour l'LPCM de CR-05 on lirait « Error opening output files: Invalid argument ». Récidive de la règle « un échec nomme sa cause » ?
- `tui/screens/run.py` : après échec ou abandon d'un titre extrait, `dec.encode_source` est-il remis à None et le `.iris_titre.mkv` effacé ? (un réessai pointerait vers un fichier disparu).
- `tui/screens/browser.py:831-849` `_scan_one` : une analyse qui lève est seulement journalisée, la ligne disparaît de la liste sans message (titre de disque illisible, CSS non détecté sur lecteur physique : `clip_chiffre`/`vob_chiffre` rendent False sur OSError en promettant que « l'analyse dira pourquoi »). Message de journal en français (« Échec du scan »).
- `tui/screens/run.py` `ajouter()` : une décision ajoutée à un lot en cours passe-t-elle par `resoudre_sorties` avec les noms déjà réservés du lot ? Sinon deux sources de même stem (Film.mkv puis Film.mp4) visent la même sortie non encore écrite.
- `tui/screens/run.py` `_audio_prepass` (~l. 660) : échec résumé en « code N », sans `diagnostiquer` (même famille que la première piste).
- `tui/screens/run.py` arrêt (`_arreter`) d'un processus **en pause** : sous POSIX, `terminate()` (SIGTERM) sur un processus arrêté par SIGSTOP reste en attente jusqu'au SIGCONT, et `wait()` bloque. Reprendre avant de terminer ?
- `tui/screens/run.py` `_strip_dv` / `_encode_dv` : `dovi.remove_dv`, `inject_rpu`, `convert_p7_to_p8`, `extract_rpu_depuis_source` sont des appels bloquants qui ne publient pas leur processus : `X` (arrêt) et `F10` peuvent-ils les interrompre ? un dovi_tool orphelin continuerait d'écrire des dizaines de Go. Et `pistes_audio_vides` est-il vérifié après un retrait DV en MP4 (`build_strip_mp4` transcode sans passe préalable) ?
- `tui/screens/run.py` `_strip_dv` en MP4 : `dovi.build_strip_mp4` n'a pas de paramètre de pistes externes — une greffe sur une décision `STRIP_DV` sortant en MP4 est-elle perdue en silence ?
- `tui/screens/sync.py`, `tui/screens/wizard.py` : quel chemin reçoit la mesure pour une **cible titre de Blu-ray** (`info.path` = `.mpls`, que ffmpeg ne lit pas, ou `info.lecture` = premier clip seulement) ? et après un `_remux_titre` ?
- `main.py` : la console du preflight imprime `✓ ✗ ↑ …` ; sortie redirigée vers un fichier ou un tube sous Windows (cp1252) → `UnicodeEncodeError` au démarrage ? (`sys.stdout.reconfigure` ?)
- `core/opensubtitles.py`, `tui/screens/meta_popup.py` : pour un **titre de disque**, `parse_title(info.path)` lit `00800.mpls` / `TITLE_01.dvd` (titre « 00800 ») et l'empreinte se calcule sur une playlist de quelques centaines d'octets — utiliser `stem_sortie` et `lecture` ?

## Cadre (déjà tranché, ne pas re-signaler)

Choix assumés par la spec, le wiki ou le CHANGELOG. Un désaccord se pose en
**question**, pas en défaut.

- **Hors scope (spec § 19)** : pistes de commentaire repérées par leur titre,
  badges de langues, pistes externes en lot, IPC mpv, collage de codecs ou de
  définitions différents (refusé), `Ctrl+D` vers la corbeille (suppression
  définitive, assumée).
- **Passe audio préalable** gardée malgré la non-reproduction en ffmpeg 8.1.x
  (IE-80) ; sous-titres de la source par une entrée dédiée dès que l'audio
  vient d'une autre entrée (v0.8.9.41).
- **Désentrelacement** sur les seuls marqueurs (`field_order`,
  `bwdif … deint=interlaced`), sans sondage `idet` (IE-122).
- **Conteneur** : `auto` = MP4 quand tout y tient ; profil 7 en MKV
  (`needs_mkv`) ; DV conservé ou réencodé en MP4 `hvc1` + `-strict unofficial`
  (IE-108, IE-109) ; `-tag:v hvc1` sur tout HEVC en MP4 ; `setsar=1`.
- **Nommage** : `-iris` sensible à la casse, `.IRIS` plus reconnue ; groupe de
  release retiré ; collision → `(2)`, jamais d'écrasement ; nom figé par
  `resoudre_sorties` à la construction de `RunScreen`.
- **Sorties visibles** : la vue liste les sorties d'IRIS (grisées) ; seuls le
  scan récursif et les lots automatiques les écartent (`deja_produit`) ;
  `.mux-iris` et `.join-iris` restent des entrées (`ENTREES_IRIS`).
- **Décision** : débit comparé = vidéo seule ; CAS 1 avec tolérance de +10 % ;
  CAS 3 indépendant de la résolution ; piste sans langue gardée (v0.8.9.93) ;
  cœur AC-3 apparié à sa TrueHD par PID ; télétexte toujours écarté.
- **Profils** : le fichier fait foi ; TOML invalide → session sur les profils
  livrés sans réécrire ; sans clé `dolby_vision` → `sdr`, valeur inconnue →
  `hdr10` ; migration `serie_*` → `series_*`.
- **Outils** : `PATH` puis `bin/` ; l'outil DVD seulement dans `bin/dvd/` ;
  outil optionnel absent = fonction désactivée ; mise à jour des outils sans
  empreinte (URL découverte, spec § 4.4).
- **updater** : release « Latest » seule, rien sous `.git`, bibliothèque
  standard seulement, jamais bloquant, empreinte `digest` obligatoire, bloc
  `( … )` dans `launch.bat`.
- **Localisation** : anglais source ; jamais traduit ce qui s'écrit sur disque
  ou part vers un programme ; console avant `main.py` en anglais (ASCII dans
  les `.bat`) ; formats fixes (point décimal, `12%`) ; noms de piste proposés
  selon la langue de la piste.
- **Disques** : titres par playlists et IFO ; DV d'un titre de plusieurs clips
  refusé ; un titre n'est jamais supprimé (`delete_source`, `Ctrl+D`) ; mux et
  collage refusés sur un titre ; pas de greffe externe sur un titre de DVD ;
  disque chiffré refusé ; récursif = titre principal seul ; durée minimale
  2 min ; `_remux_titre` accepte le code 1 de mkvmerge.
- **Lecture seule** : dossier de sortie demandé à la mise en file
  (`sorties_bloquees`) ; mux et collage refusent un dossier en lecture seule
  sans en proposer un autre.
- **File d'encodage** : mode Textual dédié ; quitter la vue n'arrête rien ;
  `X` arrête après confirmation ; drapeau `_abandon` relu après chaque
  démarrage.
- **Veille** : `PowerCreateRequest`, pas `SetThreadExecutionState` ; relevé
  toutes les 5 s.
- **Intermédiaires** à côté de la source (ou dans `dossier_sortie`), sur le
  même volume ; extrait de contrôle et sous-titres OpenSubtitles dans le temp
  du système.
- **Revue du 2026-08-29** (IE-38 à IE-58) close, tests dans
  `tests/test_revue_code.py`.


### Base de tests (au départ)

`pip install -r requirements.txt pytest` puis `python -m pytest -q`, sous Linux
(Python 3.13.16, textual 8.2.8, rich 15.0.0, numpy 2.5.3, pytest 9.1.1), sans
GPU NVIDIA, sans `bin/` ni `resources_files/`. Outils présents pour les
reproductions : ffmpeg/ffprobe 6.1.1 (Ubuntu, sans `dvdvideo` ni `dovi_rpu`),
mkvmerge v82.0 (installé pour la revue) ; ni dovi_tool, ni mpv.

**1 644 tests : 1 630 réussis, 5 échecs, 9 ignorés.** Les cinq échecs sont
**d'environnement** (sémantique des chemins Windows sous Linux), aucun n'est un
défaut :

| Test | Cause |
|---|---|
| `test_bluray.py::test_à_la_racine_d_un_lecteur_l_étiquette_du_volume` | `Path("E:\\")` n'est pas une racine de lecteur sous Linux : `.name` vaut `E:\` |
| `test_dvd.py::test_à_la_racine_d_un_lecteur_le_nom_par_défaut` | idem |
| `test_densite.py::test_la_notice_ne_repete_pas_le_dossier_courant` (×2) | séparateur `\` attendu, `/` rendu par `PosixPath` |
| `test_dvd.py::test_l_outil_dvd_se_pose_dans_bin_dvd` | l'archive du test porte des noms en `.exe`, `_exe()` n'en ajoute pas sous Linux |

Ignorés (9) : ffmpeg absent de `bin/` (3), échantillons absents de
`resources_files/` (5), API Windows (`test_veille.py`, 1).

Ce qui ne peut pas être exécuté ici : NVENC, `ctypes.windll`,
`Mount-DiskImage`, lecteurs en lecture seule réels, cmd.exe et PowerShell.
Les constats qui en dépendent sont marqués `lu` ou `supposé`, jamais
`reproduit`.

## Critères

| Code | Ce qu'on cherche |
|---|---|
| J | Justesse : mauvaise sortie, crash, chemin d'erreur non géré, condition inversée |
| P | Perte de données : source supprimée ou écrasée, sortie partielle laissée ou effacée à tort, intermédiaires non nettoyés |
| C | Concurrence : workers Textual, threads, `call_from_thread`, travail long qui finit dans un monde qui a changé |
| S | Sous-processus : UTF-8, codes de retour, processus orphelins, délais |
| W | Windows : lecture seule, partages réseau, racine d'un lecteur, espaces, accents, casse |
| R | Récidive : défaut corrigé à un endroit, présent dans un appel de même forme ailleurs |
| G | Règles du projet : G1 `_()`/`N_()` ; G2 pas de comparaison à un texte traduit ; G3 rien de traduit qui s'écrit ou part vers un programme ; G4 `on_key` → `super().on_key(event)` ; G5 pas de `bold red` ; G6 confirmation par `ConfirmModal` |
| T | Trou de couverture : comportement important qu'aucun test ne verrouille |
| M | Code mort (signalé seulement) |

**Gravité** : `critique` (perte de données, résultat faux sans erreur),
`majeur` (fonction cassée dans un cas réel), `mineur`.
**Certitude** : `reproduit` (code réel exécuté, script ou test temporaire sur
fichiers synthétiques), `lu`, `supposé`.

Format :

```
- **CR-NN** · `fichier:ligne` · gravité · critère · certitude — titre
  - Scénario : entrée, état → obtenu, au lieu de attendu.
  - Correction : une ou deux phrases.
  - Test : le test structurel ou comportemental qui empêche la récidive.
```

## Fichiers

Ordre de revue : le code des sources disque d'abord (IE-118 à IE-122), puis
le reste de `core/`, `tui/`, la racine et les lanceurs.

### core/
- [x] core/bluray.py (305)
- [x] core/dvd.py (260)
- [x] core/scanner.py (1040)
- [x] core/decision.py (1386)
- [x] core/encoder.py (891)
- [x] core/annexes.py (68)
- [x] core/muxer.py (638)
- [x] core/joiner.py (244)
- [x] core/dovi.py (358)
- [x] core/sous_titres.py (141)
- [x] core/sync.py (1547)
- [x] core/preflight.py (629)
- [x] core/updates.py (233)
- [x] core/platform.py (213)
- [x] core/config.py (402)
- [x] core/profiles.py (299)
- [x] core/i18n.py (210)
- [x] core/cles.py (174)
- [x] core/meta.py (371)
- [x] core/opensubtitles.py (308)
- [ ] core/preview.py (118)
- [ ] core/veille.py (274)
- [ ] core/__init__.py (1)

### tui/
- [ ] tui/screens/run.py (1624)
- [ ] tui/screens/output_dir.py (133)
- [ ] tui/widgets/file_tree.py (150)
- [ ] tui/app.py (499)
- [ ] tui/screens/browser.py (1415)
- [ ] tui/common.py (600)
- [ ] tui/mixins.py (295)
- [ ] tui/screens/tracks.py (790)
- [ ] tui/screens/wizard.py (645)
- [ ] tui/screens/dryrun.py (427)
- [ ] tui/screens/mux_run.py (266)
- [ ] tui/screens/join.py (380)
- [ ] tui/screens/sync.py (1246)
- [ ] tui/screens/donor_picker.py (308)
- [ ] tui/screens/opensubtitles.py (160)
- [ ] tui/screens/ancrage.py (161)
- [ ] tui/screens/segments.py (137)
- [ ] tui/screens/options.py (176)
- [ ] tui/screens/config.py (349)
- [ ] tui/widgets/profile_form.py (668)
- [ ] tui/screens/profile_picker.py (119)
- [ ] tui/screens/value_picker.py (97)
- [ ] tui/screens/cles.py (233)
- [ ] tui/screens/meta_popup.py (215)
- [ ] tui/screens/aide.py (521)
- [ ] tui/screens/confirm.py (141)
- [ ] tui/screens/delete_confirm.py (45)
- [ ] tui/screens/recursive_confirm.py (32)
- [ ] tui/screens/quit.py (26)
- [ ] tui/screens/fin_lot.py (52)
- [ ] tui/widgets/entete.py (106)
- [ ] tui/widgets/footer.py (194)
- [ ] tui/__init__.py + tui/screens/__init__.py + tui/widgets/__init__.py (3)

### Racine et lanceurs
- [ ] main.py (156)
- [ ] updater.py (327)
- [ ] launch.bat (148)
- [ ] bootstrap.ps1 (262)
- [ ] launcher/IrisEncodeLauncher.cs (72)
- [ ] launcher/build.bat (66)

## Constats

<!-- Un bloc par fichier, dans l'ordre de revue. -->

### core/bluray.py

- **CR-01** · `core/bluray.py:61-66` (`a_extraire`), `core/scanner.py:933-944` · **critique** · J · reproduit — Un titre d'un seul clip qui n'en joue qu'une partie est encodé en entier.
  - Scénario : disque dont plusieurs playlists pointent dans le même clip avec des points d'entrée et de sortie différents (concert : une playlist par chanson ; série : un épisode par playlist). Disque synthétique : `00001.m2ts` de 60 s, `00010.mpls` = 0-20 s (deux chapitres), `00011.mpls` = 20-60 s. `titres()` les liste (20 s, 40 s), `scan()` annonce 20 s, mais `a_extraire` est faux (un seul clip) et `build_command` lit `00001.m2ts` sans `-ss`/`-t`. Obtenu : `Concert (2020) - 00010.h264-iris.mp4` dure **60,0 s** (tout le concert), code 0 ; idem pour `00011` ; les chapitres FFMETADATA sont décalés dès que l'entrée n'est pas au début du clip. Attendu : 20 s. mkvmerge v82, lui, respecte les bornes (`mkvmerge -o x.mkv 00010.mpls` → 20,006 s).
  - Correction : faire passer par l'assemblage mkvmerge (`_remux_titre`) tout titre dont les éléments ne couvrent pas leur clip — par exemple `_scan_titre` compare la durée du clip (ffprobe) à `t.duree` et marque le titre partiel au-delà de 1 s d'écart, `a_extraire` le lit.
  - Test : le disque synthétique ci-dessus (playlists fabriquées comme dans `tests/test_bluray.py`, clip par ffmpeg) : `00010` est `a_extraire`, et un titre qui couvre son clip ne l'est pas.
- **CR-02** · `core/bluray.py:233-245` (`titre`), `core/scanner.py:937-938` · mineur · J (coût) · reproduit — Analyser les titres d'un disque relit toutes ses playlists pour chacun : coût quadratique.
  - Scénario : `_scan_titre` appelle `bluray.titre(mpls)`, qui rappelle `titres(racine)` (toutes les playlists, un `is_file` par clip cité) pour retrouver un seul titre ; le navigateur analyse chaque titre listé, et `disque_chiffre` refait un `titres()` à chaque ouverture. Sur une sauvegarde déchiffrée d'un disque à playlists obscurcies (des centaines de playlists de pleine durée, toutes au-dessus de 2 min), mesuré sous Linux sur disque synthétique : 600 playlists × 100 clips → 0,70 s par `titre()`, soit **≈ 7 min** de seule lecture des playlists pour analyser les 600 titres, avant le moindre ffprobe ; davantage sur un ISO monté ou un partage.
  - Correction : mémoriser `titres(racine)` par (racine, date du dossier `PLAYLIST`), ou faire porter le `TitreDisque` déjà lu par le navigateur jusqu'à `scan()`.
  - Test : compter les appels à `lire_mpls` pendant l'analyse de N titres d'un disque synthétique : au plus N (+ constante), pas N².
- **CR-03** · `core/bluray.py:300-305`, `tui/screens/run.py:1218-1260` (`_remux_titre`) · mineur · J · supposé — Rien ne vérifie que l'assemblage mkvmerge a les pistes sur lesquelles la décision a été prise.
  - Scénario : la décision numérote les pistes par type d'après ffprobe sur le premier clip (`_scan_titre`), puis encode le Matroska de mkvmerge. Mesuré avec mkvmerge v82 : l'ordre suit la PMT dans les deux outils, même à PID inversés (bon) ; mais sur un `.m2ts` portant une AAC, ffprobe voit trois flux et mkvmerge deux (l'AAC manque). Une piste absente avant une piste gardée décale les index : `-map 0:a:1` prend une autre langue, étiquetée par `langue_completee` comme la piste voulue — faux sans erreur ; après, `-map` échoue (erreur visible).
  - Correction : après `_remux_titre`, relire le Matroska (ffprobe) et comparer, par type, la suite des codecs à celle de `dec.info` ; refuser avec un message en cas d'écart.
  - Test : `_remux_titre` avec un ffprobe simulé rendant une piste audio de moins → fichier en erreur, message explicite, intermédiaire effacé.
- **CR-04** · `core/bluray.py:185-195` (`nom_disque`) · mineur · W · supposé — L'étiquette de volume devient un nom de fichier sans être assainie.
  - Scénario : à la racine d'un lecteur, le nom des sorties est l'étiquette du volume (soulignés → espaces). Une étiquette UDF peut porter `:`, `?`, `"` ou `/` (ISO gravé soi-même, « Film: Director's Cut ») : `Film: Director's Cut.hevc-iris.mkv` est refusé par Windows, ffmpeg échoue après l'analyse, sur un message d'ouverture de sortie. Aucune fonction d'assainissement dans le dépôt.
  - Correction : remplacer les caractères interdits par Windows (`<>:"/\|?*`, contrôles, points et espaces finaux) dans `nom_disque`, défaut si rien ne reste.
  - Test : `nom_disque(Path("E:\\"))` avec une étiquette `A:B?C` simulée rend un nom sans caractère interdit.

### core/dvd.py

- **CR-05** · `core/dvd.py:255-260` (`build_extraction_command`) · **majeur** · J · reproduit (muxeur ; `dvdvideo` non disponible ici) — Un DVD à piste LPCM ne s'extrait pas : `-map 0 -c copy` vers Matroska refuse `pcm_dvd`.
  - Scénario : DVD musical, concert, ou film avec une piste LPCM 2.0 (courant). Le démultiplexeur `dvdvideo` livre l'LPCM en `pcm_dvd` ; le muxeur Matroska n'a pas d'étiquette pour ce codec. Mesuré (ffmpeg 6.1.1, VOB synthétique `mpeg2video` + `pcm_dvd`, `-map 0 -c copy x.mkv`) : « No wav codec tag found for codec pcm_dvd », « Could not write header », code 234. `_extraire_dvd` passe le titre en échec ; tout le DVD est inencodable, alors que l'IFO, la vidéo et les autres pistes sont lisibles. À confirmer sous BtbN n9.0 (même muxeur, sans changement connu).
  - Correction : convertir à l'extraction les pistes `pcm_dvd` connues par l'analyse (`dec.info.audio_tracks`) en un PCM ou un FLAC que Matroska accepte (`-c:a:N pcm_s24le` ou `flac`), le reste en copie.
  - Test : la commande d'extraction d'un titre dont l'analyse montre une piste `pcm_dvd` ne la recopie pas telle quelle ; avec le ffmpeg local, la même commande sur un MPEG-PS synthétique à `pcm_dvd` (entrée `-f mpeg` au lieu de `dvdvideo`) rend 0.
- **CR-06** · `core/dvd.py:182-190` (`clips = _vobs(vts)`), `core/bluray.py:68-77` (`taille`), `core/scanner.py:825-830` · mineur · J · lu — Un titre d'un VTS qui en porte plusieurs prend tous les VOB du VTS : taille, débit et visualisation faux.
  - Scénario : DVD de série, quatre épisodes = quatre titres d'un même VTS (`VTS_01_1…4.VOB`). Chaque titre a pour `clips` les quatre VOB : sa `taille` (colonne Taille, Estim. Δ%, bilan de l'aperçu) est celle du disque entier, son débit estimé (`taille × 8 / durée`) quatre fois trop haut, et `V` (mpv sur `lecture` = premier VOB) montre le premier épisode quel que soit le titre. La décision change rarement (MPEG-2 toujours réencodé), mais les chiffres affichés sont faux.
  - Correction : calculer la taille d'un titre sur ses cellules (table C_PBKT du PGC : premier et dernier secteur de chaque cellule, × 2 048), et ne garder dans `clips` que les VOB que ces secteurs couvrent.
  - Test : IFO synthétiques d'un VTS à deux titres de durées 1:3 : `taille` de chacun dans ce rapport, à ±1 %.
- **CR-07** · `core/dvd.py:186-190` (`chapitres=[0.0] * chapitres`) · mineur · J · lu — Piège latent : le champ `chapitres` d'un titre de DVD ne porte que des zéros.
  - Scénario : `TitreDisque.chapitres` est documenté « débuts, en secondes » ; pour un DVD, il vaut `[0.0] * n` (le nombre seul). Aujourd'hui seul `ffmetadata_chapitres` le lit, et `_ecrire_chapitres` ne l'appelle pas pour un DVD parce que l'extraction a déjà posé `encode_source`. Le jour où un chemin écrit les chapitres d'un DVD sans extraction (visualisation, aperçu, réessai), il produira n chapitres à 0 s.
  - Correction : un champ distinct (`nb_chapitres`) pour le DVD, `chapitres` vide.
  - Test : `ffmetadata_chapitres` d'un titre de DVD rend « » ; ou un titre DVD a `chapitres == []`.
- **CR-08** · `core/dvd.py:258` (`_ffmpeg or "ffmpeg"`) · mineur · M · lu — Repli sur `ffmpeg` par son nom, inatteignable.
  - Scénario : `_extraire_dvd` refuse déjà quand `dvd.outils()[0]` est None, donc le repli ne sert jamais ; s'il servait, il appellerait un ffmpeg du `PATH` sans `dvdvideo`, contre la règle « jamais le nom nu ».
  - Correction : laisser `build_extraction_command` lever si l'outil manque.
  - Test : sans outil, `build_extraction_command` lève.
- **Question** — `core/dvd.py:194-198` : sur un DVD de série, le titre le plus long est souvent « Lire tout », qui devient le principal : le mode récursif encode alors le disque en un seul fichier au lieu de ses épisodes. Choix assumé (« principal = le plus long ») ou faut-il écarter un titre dont les PGC couvrent ceux d'autres titres ?

### core/scanner.py

- **CR-09** · `core/scanner.py:289` (`_LOSSLESS_PROFILES`), `:388-391` (`is_lossless`) · **critique** · J · reproduit — Un DTS:X IMAX n'est pas reconnu sans perte : `preserve_hd_audio` le transcode, et la sortie part en MP4.
  - Scénario : ffmpeg (≥ 6.1, et 8.x) nomme le profil « DTS-HD MA + DTS:X IMAX » (relevé dans `libavcodec.so.60`) ; la liste n'a que « dts-hd ma » et « dts-hd ma + dts:x », comparés à l'égalité. Profil `preserve_hd_audio = true`, `container = "auto"`, piste DTS-HD MA + DTS:X IMAX 7.1 : obtenu `→ ac3 5.1 640k`, sortie `.mp4` ; attendu `→ copy`, sortie `.mkv` (ce que rendent « DTS-HD MA » et « DTS-HD MA + DTS:X » dans le même essai). La passe audio préalable (`audio_prepass_needed`) et le garde-fou « sans perte conservé → MKV » ne la voient pas non plus. Avec `delete_source`, la piste sans perte est perdue pour de bon.
  - Correction : reconnaître toute variante dont le profil commence par « dts-hd ma » (préfixe, pas égalité), et le dire en un seul endroit.
  - Test : paramétré sur les profils `dca` de ffmpeg (DTS, DTS-ES, DTS 96/24, DTS-HD HRA, DTS-HD MA, … + DTS:X, … + DTS:X IMAX, DTS Express) : sans perte exactement pour les trois « DTS-HD MA… » ; décision `copy` + `.mkv` pour le troisième.
- **CR-10** · `core/scanner.py:128-135` (`_re_marques`, `(?![0-9A-Za-z+])`), avec `core/decision.py` (`JETONS_AUDIO`) · mineur · J · reproduit — Une famille audio collée à ses canaux (`DTS5.1`, `TrueHD7.1`, `DDP5.1`) n'est pas reconnue : la sortie garde la famille de la source.
  - Scénario : la marque doit être suivie d'un non-alphanumérique, or `DTS5.1` la colle à un chiffre. Obtenu par `decide` (DTS ou TrueHD transcodés en E-AC3) : `Film.1080p.BluRay.DTS5.1.x264-GRP.mkv` → `Film.1080p.BluRay.DTS5.1.hevc-iris.mp4` ; `Film.2160p.BluRay.TrueHD7.1.Atmos.x265-GRP.mkv` → `…TrueHD7.1.Atmos.hevc-iris.mp4`, alors que le fichier porte de l'E-AC3 5.1 sans Atmos. Avec un point (`DTS.5.1`), le nom est juste (`E-AC3.5.1`). Le nom ment là où la règle « ce que la conversion rend faux » (wiki `noms-de-release`) devait le corriger.
  - Correction : accepter comme fin de marque une disposition collée (`(?=\d\.\d)`) et réécrire ensemble famille et disposition (`TrueHD7.1` → `E-AC3.5.1`).
  - Test : les quatre noms ci-dessus passés par `decide` : famille, disposition et `Atmos` de la sortie.
- **CR-11** · `core/scanner.py:62-69` (`deja_produit`), intermédiaires de `tui/screens/run.py` · mineur · P · lu — Un intermédiaire Matroska laissé par une coupure passe pour une source : `A` le coche, `R` l'encode.
  - Scénario : coupure de courant pendant l'encodage d'un titre de DVD : `TITLE_01.iris_titre.mkv` (4,4 Go) reste dans le dossier de sortie ; de même `<n>.iris_dv.mkv` (réencodage DV vers MP4) et `<n>.iris_st.mkv` (porteur de sous-titres). `deja_produit` ne reconnaît que `-iris` en fin de nom : la ligne n'est pas grisée, `A` la coche, `R` la réencode en `TITLE_01.iris_titre.hevc-iris.mkv`, et rien ne signale ni ne nettoie ces gigaoctets.
  - Correction : reconnaître les intermédiaires (`.iris_<mot>` avant l'extension, une seule expression partagée avec `run.py`), les écarter du scan et les montrer comme restes à supprimer.
  - Test : `X.iris_titre.mkv`, `X.iris_dv.mkv`, `X.iris_st.mkv` absents de `scan_directory_recursive` et non cochés par `A` ; une source `Film.iris.mkv` reste une source.
- **CR-12** · `core/scanner.py:991-1004` · mineur · W (coût) · lu — Le mode récursif parcourt l'arborescence trois fois avant le premier ffprobe.
  - Scénario : `rglob("index.bdmv")`, `rglob("VIDEO_TS.IFO")` puis `rglob("*")` : trois parcours complets. Sur une bibliothèque d'un partage réseau (le cas qu'IE-117 visait), IE-121 a ajouté deux parcours de plus que la liste elle-même.
  - Correction : un seul parcours, qui note au passage les marqueurs de disque.
  - Test : sur une arborescence synthétique, compter les `os.scandir` (monkeypatch) : un par dossier.
- **CR-13** · `core/scanner.py:958-974`, `:1035-1040`, `:511-536`, `:340-342` · mineur · M · lu — Code mort : `scan_directory`, `scanner.list_subdirs`, `VideoInfo.is_already_encoded`, `VideoInfo.resolution_label`, `VideoInfo.has_image_subs`, `same_language` n'ont plus d'appelant hors des tests.
  - Scénario : la spec § 15.2 dit encore que `scan_directory` « alimente les lots que l'utilisateur ne compose pas lui-même » ; aucun écran ne l'appelle. Les tests qui l'exercent vérifient un filtre que l'application n'emprunte plus (le navigateur passe par `FileNavigator.list_videos`).
  - Correction : à trancher (supprimer, ou rattacher les tests à `scan_directory_recursive`).
  - Test : —
- **Question** — `core/scanner.py:991-1010` : en mode récursif, un disque chiffré ou un DVD sans outil est écarté sans un mot (« rien »). La règle « une perte doit se voir » (wiki `pieges-et-lecons`) voudrait que le bilan de `R` le dise. Voulu ?
- **Question** — `core/scanner.py:285-289` : LPCM (`pcm_bluray`, `pcm_dvd`), FLAC et ALAC ne sont pas « sans perte » au sens de `preserve_hd_audio` (la spec § 8.5 ne cite que TrueHD, DTS-HD MA, MLP) : la piste PCM d'un Blu-ray part en AAC même avec « copier telles quelles ». Voulu ?

### core/decision.py

- **CR-14** · `core/encoder.py:604-626` (filtre vidéo), `core/scanner.py:836-931` (SAR jamais lu) · **majeur** · J · reproduit — Une source anamorphique garde son SAR : toute sortie de DVD (et de TNT SD, de HDV 1440×1080) sera transcodée par Jellyfin.
  - Scénario : `setsar=1` n'est posé que si l'image est réduite ou a une dimension impaire. Un DVD est anamorphique par nature (720×480 en SAR 8:9 ou 32:27, 720×576 en 16:15 ou 64:45) et tient dans la boîte 1280×720 : aucun filtre. Mesuré (ffmpeg 6.1, VOB synthétique 720×480 SAR 32:27 analysé et décidé par IRIS, commande de `build_command` exécutée) : `ENCODE_H264`, pas de `-vf`, sortie `720×480 SAR 32:27`. Or Jellyfin transcode « tout SAR différent de 1:1, même 959:960 » (wiki `jellyfin`, *observé* sur deux sorties d'IRIS) : la fonction DVD d'IE-121 produit des fichiers que la chaîne ne lit pas en direct.
  - Correction : lire `sample_aspect_ratio` à l'analyse ; s'il diffère de 1:1, ramener à des pixels carrés en largeur (`scale=trunc(iw*sar/2)*2:ih,setsar=1`, combiné avec la boîte de taille), comme le fait déjà la v0.8.9.79 pour l'arrondi.
  - Test : la source synthétique ci-dessus encodée par la commande d'IRIS sort en SAR 1:1 et garde son rapport d'affichage 16:9 (±1 %) ; une source 1:1 ne reçoit aucun filtre de plus.
- **CR-15** · `core/decision.py:579-582` (`output_path` d'un SKIP + pistes externes), `tui/screens/wizard.py:388`, `:417`, `:629` · **majeur** · J · reproduit — L'assistant annonce `.mux-iris.mp4` et conclut « aucun fichier produit » après un mux réussi.
  - Scénario : MKV H.264 + AC-3 en SKIP, un `.srt` greffé (le cas typique). `output_path` suit `output_container`, qui rend `.mp4` (un SubRip tient en MP4) : l'étape 4 annonce `Film.1080p.mux-iris.mp4`. `F3` lance mkvmerge, qui écrit `mux_output_path` = `Film.1080p.mux-iris.mkv` (toujours Matroska). `MuxScreen` rebascule la décision sur le fichier produit ; `_apres` teste alors `self._dec.output_path.exists()`, qui vise `Film.1080p.mux-iris.mp4` : faux. Reproduit avec mkvmerge v82 et la décision réindexée comme `MuxScreen` le fait : bilan « The operation produced no file. Go back to the previous step. », alors que le fichier est là. L'étape 5 affiche aussi le mauvais nom. Le test `tests/test_muxer.py::test_skip_with_external_track_gets_a_distinct_name` verrouille ce `Film.mux-iris.mp4` qu'aucun chemin n'écrit. (La spec § 8.6, § 9.2 et le wiki `conteneurs` disent encore qu'une piste externe impose le MKV ; les tests de l'encodage disent le contraire, à dessein : la documentation a dérivé.)
  - Correction : pour un SKIP avec pistes externes (un mux), `output_path` = `muxer.mux_output_path` ; après le mux, l'assistant vérifie le fichier que `MuxScreen` a écrit (rendu par `dismiss`), pas une décision recalculée.
  - Test : décision SKIP + SRT externe → `output_path == mux_output_path(source)` ; `_apres` d'un faux `MuxScreen` réussi → bilan de réussite.
- **CR-16** · `core/decision.py:1318-1319` (`force_skip_to_encode`) · **majeur** · J · reproduit — Forcer un film 1080p au format scope l'encode en H264, là où la règle choisit HEVC.
  - Scénario : `sub_1080 = info.height < 1080` ; or la décision automatique raisonne par tranche (`_resolve_limits` : 1920 de large → tranche 1080p → HEVC). Mesuré : 1920×800 HEVC à 1 500k (SKIP) forcé → `ENCODE_H264` à 1 500k, `Film.1920x800.h264-iris.mp4` ; le même à 9 000k → `ENCODE_HEVC` automatiquement. La plupart des films sont au format scope (1920×800 à 1036) : coche forcée à l'accueil, `F2` de l'assistant sur un SKIP, enchaînement après mux, tous réencodent un HEVC en H264 au même débit, donc en moins bonne qualité.
  - Correction : choisir le codec forcé par la tranche (`_resolve_limits(...)[2] < 1080`), comme `decide_video`.
  - Test : 1920×800 SKIP forcé → `ENCODE_HEVC` ; 1280×720 forcé → `ENCODE_H264`.
- **CR-17** · `core/decision.py:142-146` (`VideoDecision.label`) · mineur · J · reproduit — Un encodage AV1 s'affiche « → H264 ».
  - Scénario : `codec = "HEVC" if action in (ENCODE_HEVC, ENCODE_DV) else "H264"`. `ENCODE_AV1` → « → H264 » (et « → H264 → HDR10 » sur une source DV). Lu par la colonne Décision de l'accueil, l'aperçu, l'assistant, la file d'encodage et l'écran de mux. Le suffixe `.av1-iris` est juste : seul l'écran ment, au moment de choisir.
  - Correction : nommer chaque action (table `VideoAction → libellé`), AV1 compris.
  - Test : `label()` de chaque action de `ACTION_CYCLE` contient son codec ; structurel : toute `VideoAction` a un libellé.
- **CR-18** · `core/decision.py:633-664` (`_stem_audio_a_jour`) · mineur · J · reproduit — La famille d'une piste écartée reste dans le nom.
  - Scénario : seules les pistes transcodées réécrivent la marque audio. `Film.2160p.UHD.BluRay.REMUX.HEVC.TrueHD.7.1.Atmos-GRP.m2ts`, TrueHD et cœur AC-3 de même PID, `preserve_hd_audio = false` : la TrueHD est écartée au profit du cœur (IE-119) et la sortie s'appelle `Film.1080p.BluRay.REMUX.TrueHD.7.1.Atmos.hevc-iris.mp4` avec une AC-3 5.1 seule. Même chose pour une piste écartée par la langue quand le nom citait sa famille.
  - Correction : traiter une famille qu'aucune piste conservée ne porte plus comme une famille transcodée vers le codec de la piste qui la remplace (ou retirer la marque).
  - Test : le nom ci-dessus → `…AC3.5.1…`, sans `TrueHD` ni `Atmos`.
- **CR-19** · `core/scanner.py:845-847` (`9_999_999`), `core/decision.py:847`, `:875-885` · mineur · J · reproduit — Le débit « inconnu » n'impose pas le réencodage qu'il annonce et devient une cible inventée.
  - Scénario : « inconnu → on suppose élevé (force re-encode) », mais 9 999 999 bps reste sous une cible 4K de 12 000k + 10 %. Mesuré : 4K HEVC au débit inconnu → SKIP, raison « Bitrate OK » ; 4K VP9 → CAS 3 à `target_bitrate = 9 999 999` (« bitrate conservé » d'une valeur fabriquée). Rare (ffprobe donne presque toujours un débit de conteneur : fichier en cours d'enregistrement, flux sans durée).
  - Correction : porter l'inconnu tel quel (0) et le traiter en CAS 1 à la cible, raison « débit inconnu ».
  - Test : débit inconnu sous un profil 4K à 12 000k → réencodage à la cible, raison qui dit « inconnu ».
- **Question** — `core/decision.py:1063-1100` (`_paires_coeur`) : avec `audio_hd_codec = "eac3"`, une TrueHD de Blu-ray est remplacée par son cœur AC-3 à 640k au lieu d'être transcodée en E-AC3 jusqu'à 1 024k ; avec `audio_copy_compatible = false`, c'est le cœur avec perte qui est retranscodé (une génération de plus) au lieu de la TrueHD. Le CHANGELOG (v0.8.9.93) parle de « même résultat », vrai pour le forfait AC-3 seulement. Voulu ?
- **Question** — `core/decision.py:1292-1293` (`choisir_codec`) : choisir H264 (`F6`) sur une source HDR10 non DV donne une sortie PQ en 8 bits (le « banding dans les ciels » de `pieges-et-lecons`), sans avertissement ni tone mapping. Assumé pour un choix manuel ?

### core/encoder.py

- **CR-20** · `core/encoder.py:706-758` (mapping de `build_command`) · **critique** · P · reproduit — L'encodage vers Matroska perd les polices jointes : les sous-titres ASS d'un animé sortent sans leurs polices.
  - Scénario : `build_command` mappe `0:v:0`, l'audio et les sous-titres, jamais `0:t` (pièces jointes). MKV H.264 + AAC + ASS + police TTF jointe, encodé par la commande d'IRIS (ffmpeg 6.1) : source `[video, audio, subtitle ass, attachment ttf]`, sortie `[video hevc, audio, subtitle ass]`, code 0. L'ASS est gardé en MKV précisément pour son style (§ 8.6), mais il s'affiche ensuite dans une police de repli : panneaux et karaokés faux, sans erreur. Le premier profil livré est `series_anime` ; avec `series_anime_delete`, la source part après le « succès » et les polices avec elle. (Le retrait et le réencodage DV, par mkvmerge, les gardent : seul le chemin ffmpeg les perd.)
  - Correction : en sortie Matroska, ajouter `-map 0:t? -c:t copy` (depuis l'entrée qui porte les sous-titres de la source) ; en MP4, rien ne change (l'ASS y impose déjà le MKV).
  - Test : le MKV synthétique ci-dessus encodé par la commande d'IRIS garde sa pièce jointe (`codec_type == attachment`, même `filename`).
- **CR-21** · `core/encoder.py:251-270` (`build_audio_command` : `-loglevel error` sans `-stats`), `:94-100` (`_PROGRESS_RE` exige `frame=`) · mineur · S · reproduit — Les passes audio (passe préalable, retrait et réencodage DV) n'affichent aucune progression.
  - Scénario : avec `-loglevel error`, ffmpeg n'écrit plus la ligne de progression (mesuré, ffmpeg 6.1 : 0 octet sur stderr) ; avec `-stats`, une sortie sans vidéo écrit `size= … time= … bitrate= … speed=`, sans `frame=` ni `fps=`, que la regex refuse. La barre reste indéterminée pendant tout le transcodage d'une TrueHD de trois heures — le « blocage apparent » que la spec § 10.6 avait corrigé pour `retime_audio`.
  - Correction : `-stats` dans `build_audio_command`, et une regex qui accepte une ligne sans `frame=`/`fps=` (le `time=` suffit au pourcentage).
  - Test : `parse_progress("size=  711kB time=00:00:29.97 bitrate= 194.2kbits/s speed= 194x", 60)` rend 0,5 ; `build_audio_command` contient `-stats`.
- **CR-22** · `core/encoder.py:679-697` (branche standard), `:444-453` (`build_dv_video_command`) · mineur · R · lu — La règle x265 (`maxrate` = cible, mesurée) n'est appliquée que dans le mode « HDR10 quality ».
  - Scénario : sur un poste sans NVIDIA, `platform.encoder_hevc` vaut `libx265` et la branche standard lui applique la marge de NVENC (`maxrate` = 1,5 × cible, `-rc vbr` ignoré avec un avertissement) ; `build_dv_video_command` fait de même. Or le wiki (`codecs-video`, *mesuré*) et `tests/test_x265_debit.py` établissent que x265 sous-consomme alors (93,6 % au lieu de 99,9 % à t = 1800). Le test ne vérifie que l'écart entre les deux branches avec une plateforme NVENC : il ne voit pas libx265 dans la branche standard.
  - Correction : choisir la règle de débit d'après l'encodeur effectif (`libx265` → `maxrate` = cible, sans `-rc`), aux trois endroits.
  - Test : avec une plateforme CPU (`encoder_hevc="libx265"`), `build_command` (standard) et `build_dv_video_command` posent `-maxrate` égal à `-b:v` et pas de `-rc`.
- **CR-23** · `core/encoder.py:788-810` · mineur · J · reproduit — Un sous-titre externe marqué « par défaut » laisse le drapeau du sous-titre de la source : deux pistes par défaut.
  - Scénario : l'audio externe « défaut » retire le drapeau des pistes de la source (`-disposition:a:N 0`), les sous-titres non. MKV dont le sous-titre anglais est par défaut, `.srt` français greffé et marqué défaut, encodé par la commande d'IRIS : sortie `[(eng, default=1), (fre, default=1)]`. Le lecteur prend le premier : le choix de l'utilisateur est sans effet.
  - Correction : même traitement que l'audio — `-disposition:s:N 0` sur les sous-titres de la source dès qu'un sous-titre greffé est par défaut.
  - Test : le cas ci-dessus rend un seul sous-titre par défaut, le français.
- **Question** — `core/encoder.py:793-795` : une piste audio **externe** est toujours recopiée (`-c:a copy`), alors que la même piste dans la source serait transcodée par le profil (Opus, Vorbis, FLAC, PCM, DTS : le G3 ne les lit pas, le DTS gèle au saut). ffmpeg 6.1 les accepte en MP4 sans erreur (mesuré) : la sortie fera transcoder Jellyfin. Appliquer à une greffe la règle audio du profil ?
- **Question** — `core/encoder.py:633-634`, `:821-829` : une copie Dolby Vision **profil 5** sort en MP4 étiquetée `hvc1` avec `dvcC`, comme un 8.1 ; seul le 8.1 a été essayé sur le G3 (IE-75). Un P5 n'a pas de couche de base lisible : si le lecteur l'ouvre en HEVC simple, couleurs fausses. À vérifier sur le téléviseur (Film H est un P5) ?

### core/annexes.py

- **CR-24** · `core/annexes.py:52-58` (`rivales`) · mineur · P · supposé — Deux vidéos de même nom dans un dossier (`Film.mkv`, `Film.avi`) partagent leurs annexes : supprimer l'une emporte le `.nfo` et les images de l'autre.
  - Scénario : seules les vidéos au nom **plus long** sont protégées. Avec `Film.mkv` encodé sous un profil `delete_source` à côté d'un `Film.avi` (ou d'un `Film.iso`, extension hors `SUPPORTED_EXTENSIONS`, qui n'est jamais une rivale), `Film.nfo` et `Film-poster.jpg` partent alors que Jellyfin les rattache aussi à la vidéo qui reste. Rare ; perte réparable (Jellyfin refait ses fichiers).
  - Correction : ne rien supprimer quand une autre vidéo du dossier a le même nom de base (ou une extension vidéo connue de Jellyfin hors liste).
  - Test : dossier `Film.mkv`, `Film.avi`, `Film.nfo` : `annexes_jellyfin(Film.mkv)` est vide.

### core/muxer.py

- **CR-25** · `core/muxer.py:310-323` (`_track_options`), `:357` · mineur · R · reproduit — Au mux, une piste greffée « par défaut » laisse le drapeau des pistes de la source : deux pistes audio et deux sous-titres par défaut.
  - Scénario : `--default-track-flag` ne vise que la piste du donneur ; la source garde les siens. Mesuré (mkvmerge v82) : source avec audio et sous-titre anglais par défaut, VF `.mka` et `.srt` français greffés et marqués défaut → `[(und, True), (fre, True)]` en audio, `[(eng, True), (fre, True)]` en sous-titres. Le lecteur prend la première : le choix est sans effet. Même famille que CR-23 (chemin ffmpeg, sous-titres) ; le chemin ffmpeg traite l'audio, celui-ci rien.
  - Correction : quand une piste greffée d'un type est par défaut, poser `--default-track-flag TID:0` sur les pistes de ce type de la source (ids par `identify`) ; une seule fonction pour les deux chemins.
  - Test : le cas ci-dessus rend une seule piste par défaut par type, la greffée ; structurel : `build_mux_command` et `build_command` passent par la même règle.
- **CR-26** · `core/muxer.py:155-182` (`guess_language`), `tui/screens/donor_picker.py:71-74` · mineur · J · reproduit — Un mot du titre est pris pour une langue : « de » donne l'allemand à un sous-titre français.
  - Scénario : les fragments du nom sont lus de droite à gauche et le premier connu gagne, mot de titre compris. `La.Cite.de.la.peur.1994.srt` → `ger`, `Le.Pont.de.la.Riviere.Kwai.1957.srt` → `ger`, `It.2017.srt` → `ita`, `Parasite.VO.srt` → `eng` (« VO » n'est pas l'anglais). Le sélecteur de donneur pose cette langue sur la piste ; l'assistant l'affiche sans permettre de la changer, et elle est écrite dans le fichier produit (« German » dans Jellyfin).
  - Correction : ne reconnaître qu'un marqueur en **dernière** position (avant l'extension) ou dans une liste de marqueurs non ambigus (`fr`, `fre`, `vff`, `en`…), jamais `de`, `it`, `es`, `pt`, `vo` au milieu d'un titre ; sans marqueur, laisser vide pour que l'écran demande.
  - Test : les quatre noms ci-dessus rendent `""` (ou `fre` pour un `.fr.srt` ajouté) ; `Film.fr.srt` → `fre`.
- **CR-27** · `core/muxer.py:241-253` (`ffmpeg_stream_index` → 0), `:256-266` (`mkvmerge_tid` → l'index lui-même) · mineur · J · lu — Une traduction d'index qui échoue devine au lieu de refuser.
  - Scénario : si `identify` rend `[]` au moment de l'encodage (mkvmerge en délai de 30 s sur un partage lent, exécutable déplacé), `ffmpeg_stream_index` rend 0 et `build_command` mappe la **première** piste du donneur sous la langue et le nom de celle qui était choisie — exactement le défaut que le commentaire de `encoder.py:748-754` dit corrigé ; `mkvmerge_tid` rend l'index ffprobe comme un tid mkvmerge (0 = la vidéo), et `--audio-tracks 0` du retrait DV ne garde aucune audio. Rare (le cache d'`identify` sert le plus souvent), mais « un refus vaut mieux qu'un chiffre faux ».
  - Correction : lever une `ErreurAffichable` quand le tid ou l'index n'est pas trouvé.
  - Test : `identify` simulé vide → `ffmpeg_stream_index` et `mkvmerge_tid` lèvent ; `build_command` d'une décision à piste externe aussi.
- **CR-28** · `core/muxer.py:556-565` (`premux_output_path`) · mineur · P · lu — Le mux préalable (piste étirée) écrit le film entier dans le dossier temporaire du système.
  - Scénario : `tempfile.gettempdir()` est sur le disque système ; l'intermédiaire pèse le film (30 à 60 Go en 4K). La règle du projet dit l'inverse pour tout gros intermédiaire (spec § 7.3 : « le disque système n'a pas 30 Go à prêter » ; wiki `conteneurs`), et IE-118 a rangé les autres dans `dossier_sortie`. Disque système trop petit : échec du mux ; coupure ou plantage : 30 Go oubliés dans `%TEMP%`, invisibles, jamais nettoyés.
  - Correction : écrire l'intermédiaire dans `dec.dossier_sortie` sous un nom d'intermédiaire (`<stem>.iris_premux.mkv`, reconnu par CR-11).
  - Test : `premux_output_path` (ou son remplaçant) rend un chemin dans le dossier de sortie de la décision.

### core/joiner.py

- **CR-29** · `core/joiner.py:80-92` (`nom_commun`) · mineur · J · reproduit — Le marqueur de numérotation est retiré sans borne de mot : il ronge la fin du titre.
  - Scénario : `bas.endswith(marqueur)` en boucle. Mesuré : `Le Fantome 1` + `Le Fantome 2` → `Le Fan.join-iris.mkv` ; `Concept.CD1` + `Concept.CD2` → `Conce.join-iris.mkv` (« CD » puis « pt ») ; `Le Depart 1/2` → `Le De` ; `Envol.part1/2` → `En`. Le nom s'affiche avant le collage (« Sortie : … »), mais rien ne permet de le corriger dans l'écran.
  - Correction : ne retirer un marqueur que s'il est un mot entier (précédé d'un séparateur ou en tête), une seule fois.
  - Test : les quatre paires ci-dessus donnent `Le Fantome`, `Concept`, `Le Depart`, `Envol` ; `Film part1/part2` → `Film`.
- **CR-30** · `core/joiner.py:151-166` (`controler`) · mineur · J · lu — L'appariement ne compare ni la langue ni la fréquence des pistes audio de même rang.
  - Scénario : mkvmerge colle les pistes rang par rang. Deux parties de releases différentes, `[fre, eng]` puis `[eng, fre]`, mêmes codecs et canaux : aucun blocage ni avertissement, et la piste « fre » du fichier produit passe à l'anglais au milieu du film, sans erreur. Une fréquence différente (48 / 44,1 kHz) n'est pas vue non plus : mkvmerge refuse alors lui-même, avec son message anglais brut.
  - Correction : avertir quand les langues de deux pistes de même rang diffèrent (langues normalisées) ; bloquer sur une fréquence différente (à lire au scan).
  - Test : `controler` de deux `VideoInfo` aux langues inversées rend un avertissement nommant la piste.

### core/dovi.py

- **CR-31** · `core/dovi.py:229-248` (`extract_rpu_depuis_source`) · mineur · R · lu — Le code de retour de ffmpeg n'est pas lu dans le tuyau ffmpeg → `dovi_tool extract-rpu`.
  - Scénario : seul `dt.returncode` est testé ; `ff.wait(timeout=30)` est appelé sans regarder son résultat. Une lecture qui casse en route (partage réseau, fichier abîmé) termine ffmpeg en erreur, dovi_tool reçoit un flux tronqué et rend 0 avec un RPU partiel, accepté (taille > 0). La suite dépend de `inject-rpu` face à un RPU plus court que la vidéo encodée. C'est la règle d'IE-41 (« un ffmpeg tué rend une sortie partielle qui passe pour un film court ») non appliquée ici.
  - Correction : exiger `ff.wait() == 0` en plus, et comparer le nombre d'images du RPU (`dovi_tool info --summary`) à celui de la source.
  - Test : `Popen` simulés, ffmpeg à 1 et dovi_tool à 0 → `False`.
- **CR-32** · `core/dovi.py:283-299` (`remove_dv`, `timeout=1800`), `:258-280` (`inject_rpu`, 7 200 s), `:215-217` (3 600 s) · mineur · S · lu — Des délais fixes peuvent tuer une étape légitime, après des dizaines de minutes de travail.
  - Scénario : `dovi_tool remove` lit et réécrit tout le flux vidéo brut (60 à 80 Go pour un remux UHD) ; sur un disque dur USB ou un partage à ~100 Mo/s partagés entre lecture et écriture, 120 Go d'entrées-sorties dépassent 1 800 s. `subprocess.run` tue alors dovi_tool et le retrait échoue sans autre cause que « remove failed ». Ces appels bloquants ne publient pas non plus leur processus : voir la piste sur l'arrêt dans `run.py`.
  - Correction : pas de délai fixe pour ces étapes ; les lancer comme les autres (processus publié, arrêtable, progression), et ne tuer que sur arrêt demandé.
  - Test : structurel — aucun `subprocess.run(..., timeout=…)` sur une étape qui traite le film entier.
- **CR-33** · `core/dovi.py:62-79`, `:204-212`, `:344-358`, `core/scanner.py:346-356` · mineur · M · lu — Code mort et documentation qui décrit des fonctions absentes.
  - Scénario : `extract_hevc_stream`, `extract_rpu`, `get_temp_dir`, `cleanup_temp_files` n'ont aucun appelant ; `scanner._dovi_path`, posé par `app.py` via `set_dovi_path`, n'est jamais lu. La spec (§ 7.1, § 7.2, § 15.3) et l'en-tête du module décrivent `probe_file()` et `rpu_info()`, qui n'existent plus (les métadonnées HDR10 viennent de ffprobe depuis la v0.8.1.19) : l'« enrichissement DV au scan » documenté n'a pas lieu.
  - Correction : à trancher (supprimer, ou remettre la spec d'accord).
  - Test : —

### core/sous_titres.py

- **CR-34** · `core/sous_titres.py:92-104` (`pistes_a_porter` : pistes de la source seulement), `core/encoder.py:745-758`, `:803-818` · **critique** · R · reproduit — Un sous-titre **greffé** à première réplique tardive garde le défaut `mov_text` que la v0.8.9.62 a corrigé pour la source : la VF forcée s'affiche dès les premières images.
  - Scénario : le porteur ne réécrit que les sous-titres texte de la source ; une piste externe (ou greffée par un mux préalable) est mappée telle quelle avec `-c:s mov_text`, et un `.srt` ne force pas le MKV (CR-15). Reproduit de bout en bout (ffmpeg 6.1.1 — le défaut est aussi mesuré en 8.1.2/8.1.3) : MKV de 2 400 s sans sous-titres, `.srt` forcé greffé dont les répliques sont à 2 200 s et 2 300 s, commande de `build_command` → `Film.1080p.h264-iris.mp4`, code 0, répliques à **0,000 s et 2,000 s**. C'est le cas typique : un sous-titre forcé trouvé sur OpenSubtitles et greffé.
  - Correction : faire passer aussi les sous-titres texte greffés (externes et pré-muxés) par `combler_srt` et le porteur, ou forcer le MKV dès qu'un sous-titre greffé a un silence de plus de `SEUIL_S`.
  - Test : le cas ci-dessus rend des répliques à 2 200 s et 2 300 s (±0,01 s) ; structurel : toute piste mappée en `mov_text` provient du porteur ou a été contrôlée par `instants_bouche_trou`.

### core/sync.py

- **CR-35** · `core/sync.py:535-557` (`extract_subtitle`, `timeout=120`), `:1424-1431`, `:1511-1520` · **majeur** · W · lu — Extraire un sous-titre embarqué lit tout le donneur en 120 s au plus ; au-delà, le refus accuse un « sous-titre image ».
  - Scénario : `ffmpeg -map 0:s:N -c:s srt` doit démultiplexer le fichier entier (les paquets de sous-titres sont entrelacés jusqu'à la fin). Un donneur de 20 Go sur un partage à ~110 Mo/s demande ~3 min ; un remux UHD de 50 Go sur un disque dur, davantage. `subprocess.run(..., timeout=120)` tue ffmpeg, `extract_subtitle` rend None, et la mesure répond « image subtitle (PGS, VobSub) — no text to correlate » pour un SRT : cause fausse, mesure impossible pour tout gros donneur hors SSD (la bibliothèque de l'utilisateur vit sur un partage, spec § 19). Deux minutes sans progression, aussi.
  - Correction : pas de délai fixe (ou proportionnel à la taille), progression par `-progress`, et un refus « image » seulement si le codec de la piste est un codec image (connu par `identify`) ; sinon dire « extraction impossible : … ».
  - Test : `subprocess.run` simulé levant `TimeoutExpired` pour une piste `SubRip/SRT` → raison qui ne parle pas d'image ; structurel : aucun `timeout=` sur une commande qui lit un film entier.
- **CR-36** · `core/sync.py:576-580` (`_srt_stamp`) · mineur · J · reproduit — `shift_srt` peut écrire une milliseconde à quatre chiffres (`00:00:05,1000`), que mkvmerge lit 900 ms trop tôt.
  - Scénario : `int(s)` puis `round((s % 1) * 1000)` : quand la somme flottante tombe juste sous l'entier (`8.450 − 2.450` = 5,999999999999999), on obtient `,1000`. Mesuré : 8 horodatages sur 597 539 combinaisons (première minute, dix décalages), soit de l'ordre d'une réplique sur 20 000 ; sur un film de 1 500 répliques, quelques pour cent de chances d'en toucher une. ffmpeg relit `05,1000` comme 6,000 s, mkvmerge v82 comme **5,100 s** (trois premiers chiffres) : au mux (`F3`), la réplique part 0,9 s trop tôt.
  - Correction : arrondir d'abord en millisecondes entières (`ms = round(s * 1000)`), puis découper par `divmod` (comme `core/sous_titres._horodatage`).
  - Test : `_srt_stamp(8.450 - 2.450) == "00:00:06,000"` ; balayage de toutes les millisecondes d'une heure × décalages usuels : jamais quatre chiffres.
- **CR-37** · `core/sync.py:121` (`_TEXT_SUB_EXT`), `:416-460` (`read_cues`), `tui/screens/donor_picker.py:40-43` · mineur · J · reproduit — `.sub` et `.vtt` sont proposés comme sous-titres texte, mais `read_cues` n'en lit rien.
  - Scénario : `read_cues` ne connaît que la forme SRT `h:mm:ss,mmm`. Mesuré : un `.vtt` aux temps sans heures (`00:01.000 --> 00:02.500`, permis par WebVTT) → 0 réplique ; un `.sub` MicroDVD (`{25}{50}…`) → 0 ; un `.sub` VobSub est binaire. Le donneur les propose, la mesure répond « no readable subtitle line — unknown format or empty file ». Au passage, `\d{1,3}` lit `00:00:01,5` comme 1,005 s.
  - Correction : lire les temps WebVTT sans heures, convertir MicroDVD et VobSub par ffmpeg (`extract_subtitle`) au lieu de les lire comme du texte, compléter une fraction de moins de trois chiffres à droite.
  - Test : les deux fichiers ci-dessus rendent leurs répliques (MicroDVD à la cadence de la cible) ; `.sub` VobSub → refus « image ».

### core/preflight.py

- **CR-38** · `core/preflight.py:209-227` (`_install_from_zip`), `:323-330`, `:612-618` · mineur · R · lu — Installation et mise à jour écrivent l'exécutable en place ; un échec en route laisse un outil tronqué, et le message dit « previous version kept ».
  - Scénario : `target.write_bytes(zf.read(member))` directement sur `bin/ffmpeg.exe`, puis sur `bin/ffprobe.exe`. Disque plein, antivirus ou coupure pendant la mise à jour : `ffmpeg.exe` est déjà neuf ou tronqué quand `ffprobe.exe` échoue ; l'exception remonte, `check_for_updates` affiche « ffmpeg update failed — previous version kept », et au lancement suivant `_localiser` trouve un `ffmpeg.exe` présent mais inutilisable — l'outil essentiel. C'est la famille d'IE-39 et d'IE-50 (écriture non atomique), ici pour des binaires.
  - Correction : extraire dans un provisoire du même dossier puis `os.replace`, outil par outil, tous ou aucun.
  - Test : `write_bytes` qui échoue au second membre → les deux exécutables d'origine intacts, message conforme.
- **CR-39** · `core/preflight.py:240-260` (`poser("dovi_tool")`), `data/ffmpeg_releases.toml` (`[dovi_tool.linux]`) · mineur · R · reproduit — Sous Linux, l'archive `.tar.gz` de dovi_tool est écrite telle quelle comme exécutable, avec « ✓ Installed ».
  - Scénario : la source statique Linux pointe un `.tar.gz` ; `poser` ne reconnaît que le ZIP et écrit sinon les octets bruts. Mesuré : `poser("dovi_tool", <tar.gz>)` rend True et pose un `bin/dovi_tool` qui commence par `1f 8b` (gzip). C'est le défaut d'IE-40 (« les octets du ZIP dans dovi_tool.exe, ✓ Installé ») par une autre forme d'archive. Sans effet sous Windows (ZIP).
  - Correction : reconnaître tar.gz / tar.xz (`tarfile`) ; n'écrire en binaire nu qu'un contenu qui a l'en-tête d'un exécutable (MZ, ELF).
  - Test : `poser("dovi_tool", <tar.gz>)` extrait le membre ou échoue, jamais d'écriture brute.
- **CR-40** · `core/preflight.py:272-277` (`install_ffmpeg`), `:288-292`, `:513` · mineur · J · lu — La spec promet une vérification SHA256 à l'installation (§ 4.2, wiki `ffmpeg` : « SHA256 vérifié ») qui n'a lieu que pour mpv et mkvmerge.
  - Scénario : ffmpeg (l'outil essentiel), dovi_tool et l'outil DVD (190 Mo) sont téléchargés sans aucune empreinte : `install_ffmpeg` n'en lit pas, et les sources statiques portent `sha256 = ""`. gyan.dev publie pourtant `…essentials.zip.sha256` à côté de l'archive, et GitHub un `digest` par asset (déjà exploité par `updater.py`).
  - Correction : lire l'empreinte publiée (fichier `.sha256` de gyan.dev, `digest` des assets GitHub pour BtbN et dovi_tool) et refuser sans elle ; ou corriger la spec.
  - Test : `install_ffmpeg` avec une empreinte publiée fausse refuse l'archive.

### core/updates.py

- **CR-41** · `core/updates.py:209-220` (`save_cache`), `core/preflight.py:167-175` (`_load_releases`) · **majeur** · J · reproduit — Dès que le cache des mises à jour existe, installer dovi_tool, mkvmerge ou mpv échoue : « URL not found in the sources ».
  - Scénario : `check_for_updates` écrit `data/ffmpeg_releases_cache.toml` sous la forme `{checked_at, tools: {outil: {version, url}}}` ; `_load_releases` lit **ce même fichier en priorité**, avec la forme du fichier statique (`[dovi_tool.windows] url = …`). Premier lancement : les offres d'installation passent (pas encore de cache), puis le cache est écrit. À tout lancement suivant, accepter dovi_tool, mkvmerge ou mpv (refusés la première fois, ou supprimés depuis) : `releases.get("dovi_tool", {}).get("windows", {})` est vide, aucun téléchargement n'est tenté. Reproduit : avec le cache écrit par `save_cache`, `install_dovi_tool` et `install_mkvtoolnix` rendent False sans appeler `_download`. Le cache n'expire jamais pour ce lecteur-là (le fichier existe).
  - Correction : `_load_releases` ne lit que le fichier statique (ou traduit `tools` vers la forme statique) ; mieux, prendre l'URL fraîche de `updates.fetch_latest()` quand elle existe, comme le fait déjà l'outil DVD.
  - Test : cache écrit par `save_cache` + sources statiques : `install_dovi_tool` tente le téléchargement de l'URL statique (ou de celle du cache).

### core/platform.py

- **CR-42** · `core/platform.py:92-98` (`sonder_encodeurs`) · mineur · J · supposé — La sonde n'ouvre chaque encodeur qu'en 8 bits ; une sortie HDR (`p010le`, `main10`) n'est jamais vérifiée.
  - Scénario : `nullsrc` en `yuv420p`, sans `-pix_fmt` ni `-profile:v`. Une carte qui encode le HEVC en 8 bits mais pas en 10 bits (Maxwell, GTX 9xx) est dite capable ; un fichier HDR (sortie `p010le main10`) passe le contrôle du lancement puis échoue dans ffmpeg, sur un message qu'aucune signature de `diagnostiquer` ne reconnaît. Le principe « les capacités sont mesurées, jamais supposées » (spec § 14) ne couvre donc que la moitié des sorties.
  - Correction : sonder aussi `hevc_nvenc`/`av1_nvenc` en `p010le` + `main10` (une entrée de plus dans le pool), et refuser un fichier HDR quand seul le 8 bits passe.
  - Test : sonde simulée où l'essai 10 bits échoue → un fichier HDR est refusé au lancement avec la cause, un SDR passe.

### core/config.py

- **CR-43** · `core/config.py:125-134` (`load`), `:172-187` (`assurer_langue`), `main.py:126-131` · **critique** · P · reproduit — Une faute de frappe dans `config.toml` le fait écraser au lancement suivant par les valeurs par défaut : identifiants et réglages perdus, sans un mot.
  - Scénario : `load()` avale l'erreur de syntaxe et rend les défauts ; `main.py` appelle aussitôt `assurer_langue(cfg)`, qui trouve une langue vide et **réécrit** le fichier. Reproduit : `config.toml` avec un guillemet oublié dans `output_dir` et une section `[opensubtitles]` (clé, compte, mot de passe) → après `load()` + `assurer_langue()`, le fichier est remplacé et `CLE-SECRETE` n'y est plus. Toute autre écriture (largeur de colonne, vitesse mesurée) ferait de même. La spec dit le fichier « éditable à la main » ; `profiles.toml` est explicitement protégé de ce cas (« ne réécrit rien — il reste réparable à la main », spec § 6.2), `config.toml` non.
  - Correction : sur erreur de lecture, garder le fichier intact (copie `config.toml.illisible`, ou interdiction d'écrire pendant la session) et l'annoncer dans la console, comme les profils.
  - Test : `config.toml` invalide → `load()` + `assurer_langue()` + `save()` laissent le fichier octet pour octet, et un avertissement est émis.
- **CR-44** · `core/config.py:142-169` (`_VERROU_ECRITURE`), `tui/common.py:41-47` · mineur · C · supposé — Le verrou sérialise l'écriture du fichier, pas les modifications du dictionnaire partagé.
  - Scénario : le worker d'encodage ajoute une clé (`stats.encode_speed[<codec>]`, première mesure d'un codec) pendant que le fil d'interface est dans `tomli_w.dump(cfg)` après un redimensionnement de colonne (ou l'inverse) : « dictionary changed size during iteration », exception dans l'un des deux fils. Fenêtre de quelques microsecondes.
  - Correction : prendre le verrou autour de la modification **et** de l'écriture (fonctions `config.modifier(cfg, fn)`), ou sérialiser une copie profonde.
  - Test : deux fils, l'un qui ajoute des clés en boucle, l'autre qui sauve, avec un `dump` ralenti : aucune exception.

### core/profiles.py

- **CR-45** · `core/profiles.py:194-213` (`load_all`, TOML illisible), `tui/screens/config.py:286-298`, `:321-328` · **critique** · P · reproduit — Après un `profiles.toml` illisible, le premier enregistrement de la session écrase la bibliothèque de l'utilisateur par les profils livrés.
  - Scénario : la session tient sur les 14 profils livrés « en mémoire seulement » et la console dit « your file was not touched » — message imprimé avant que l'interface ne prenne l'écran. Dans `F5`, créer, modifier ou supprimer un profil appelle `save_all(profiles)` sans condition : le fichier est remplacé par les profils livrés plus la modification. Reproduit : fichier à deux profils personnels avec un guillemet oublié → `load_all()` → ajout d'un profil → `save_all()` : `mon_profil_4k` et `mon_anime` ont disparu du fichier. C'est la perte qu'IE-50 voulait rendre impossible (« une bibliothèque de profils ne se refait pas »), par un autre chemin.
  - Correction : retenir l'état « fichier illisible » (`load_all` le rend), refuser tout `save_all` pendant la session tant qu'il dure, et le dire dans l'écran de configuration (bandeau d'alerte), pas seulement dans la console.
  - Test : `PROFILES_PATH` invalide → `load_all()` puis `save_all()` laissent le fichier octet pour octet (ou lèvent une erreur affichable) ; l'écran Config affiche l'alerte.
- **CR-46** · `core/profiles.py:116-122` (`summary_line`, « oui »/« non » en dur), `:47`, `:292-299` (`ID_PATTERN`, `validate_id`, `parse_languages`) · mineur · M · lu — Fonctions sans appelant, ni dans l'application ni dans les tests ; `summary_line` porte du français hors catalogue.
  - Scénario : `summary_fields` a remplacé `summary_line` ; la saisie des langues et la validation du nom passent ailleurs (`profile_form`). Une réutilisation de `summary_line` afficherait « hd-audio: oui » dans l'interface anglaise.
  - Correction : à trancher (supprimer).
  - Test : —

### core/i18n.py

Aucun constat. (Champs des traductions vérifiés par `tests/test_i18n.py` ; `ErreurAffichable.brute` ne formate pas le texte d'un service.)

### core/cles.py

- **CR-47** · `core/cles.py:122`, `core/meta.py:130` · mineur · J (sécurité) · lu — La clé OMDb part en clair, en HTTP.
  - Scénario : la vérification (`verifier_omdb`) et chaque fiche IMDB (`meta.py`) appellent `http://www.omdbapi.com/?apikey=…` ; OMDb répond en HTTPS (le lien d'inscription du même module l'emploie). Sur un réseau partagé, la clé et les titres consultés se lisent en clair. Les autres services (OpenSubtitles, GitHub, gyan.dev) passent tous en HTTPS.
  - Correction : `https://www.omdbapi.com/` aux deux endroits.
  - Test : structurel — aucune URL `http://` dans `core/` et `tui/` hors liste blanche commentée.

### core/meta.py

- **CR-48** · `core/meta.py:127` (`type=movie`), `:112-119` · **majeur** · J · lu — Dès qu'une clé OMDb est saisie, la fiche IMDB d'une série échoue (« OMDb: “Movie not found!” »).
  - Scénario : la requête OMDb filtre `type=movie` ; une série (`Show.S01E01…` → titre « Show ») n'y figure pas, et `fetch_imdb` ne retombe pas sur les suggestions IMDB, qui, elles, connaissent `tvSeries` et `tvMiniSeries`. La table `NATURE_OMDB` prévoit pourtant `series` et `episode`. Sans clé, la même fiche s'affiche : configurer la clé dégrade donc toutes les séries (profils `series_*`). Comportement documenté de l'API OMDb (`type` : movie, series, episode), non rejoué ici faute de clé.
  - Correction : ne pas filtrer le type (ou `type=series` quand le nom porte `SxxEyy`), et retomber sur les suggestions quand OMDb répond « not found ».
  - Test : `requests.get` simulé rendant « Movie not found! » pour `type=movie` → la fiche d'un `Show.S01E01.mkv` vient des suggestions ; la requête d'un nom d'épisode ne porte pas `type=movie`.
- **CR-49** · `core/meta.py:16-52` (`parse_title`) · mineur · J · reproduit — Un titre qui commence par une année est vidé ; un titre qui contient une année prend la mauvaise.
  - Scénario : l'année est un marqueur de coupe, prise où qu'elle soit. Mesuré : `2001.A.Space.Odyssey.1968.1080p` → `('', 2001)` ; `1917.2019.1080p` → `('', 1917)` ; `Blade.Runner.2049.2017.2160p` → `('Blade Runner', 2049)`. La fiche (`I`) et la recherche OpenSubtitles par nom (spec § 9.8) partent d'un titre vide ou d'une année fausse.
  - Correction : ne couper sur une année qu'au-delà du premier mot, et retenir la **dernière** année plausible avant les marqueurs techniques.
  - Test : les trois noms ci-dessus → `('2001 A Space Odyssey', 1968)`, `('1917', 2019)`, `('Blade Runner 2049', 2017)`.

### core/opensubtitles.py

- **CR-50** · `core/encoder.py:546-559` (entrées externes), `core/muxer.py:310-323` (pas de `--sub-charset`), à rapprocher de `core/sync.py:424-437` (`_read_text`) · **critique** · J · reproduit (ffmpeg) / supposé (mkvmerge sous Windows) — Un `.srt` greffé en cp1252 perd à l'encodage toutes ses répliques accentuées, sans erreur.
  - Scénario : la mesure lit le fichier en essayant utf-8 puis cp1252 (`_read_text`, qui note que « beaucoup de .srt circulent en cp1252 ») et trouve un bon recalage ; l'encodage le donne ensuite à ffmpeg sans `-sub_charenc`. Reproduit (ffmpeg 6.1.1) : `.srt` cp1252 de trois répliques (« Été à Paris », « Bonjour », « Déjà vu ») greffé en `mov_text` → « Invalid UTF-8 in decoded subtitles text », code **0**, une seule réplique en sortie ; la mesure, elle, en lit trois. En français, presque chaque réplique a un accent. Au mux, mkvmerge v82 sous Linux tronque aussi (« D… ») ; sous Windows il suit, sans BOM, le jeu de caractères du système : à vérifier, dans un sens ou dans l'autre (un UTF-8 sans BOM pourrait alors sortir en « Ã© »).
  - Correction : déterminer l'encodage du `.srt` greffé comme le fait `_read_text`, puis le passer explicitement (`-sub_charenc` avant l'`-i` de ffmpeg, `--sub-charset TID:…` pour mkvmerge), ou réécrire le fichier en UTF-8 avant la greffe.
  - Test : le `.srt` cp1252 ci-dessus greffé par la commande de `build_command` (et de `build_mux_command`) rend trois répliques, accents intacts.
- **CR-51** · `core/opensubtitles.py:255-258`, `core/muxer.py:155-166` · mineur · J · lu — Un sous-titre téléchargé dans une langue hors de `_LANG_TOKENS` sort sans langue.
  - Scénario : la langue n'est transmise que par le nom du fichier (`Film.<id>.nl.srt`), relu par `guess_language`, qui ne connaît que fr, en, de, es, it, ja, pt et ru. Un sous-titre néerlandais, polonais, suédois… choisi dans la liste (où sa langue est pourtant connue, `Resultat.langue`) devient « und » à la greffe ; `zh-cn` aussi.
  - Correction : rendre la langue connue avec le fichier (le `Resultat` la porte) plutôt que la faire relire dans le nom, ou étendre `_LANG_TOKENS` à toute la table `_VERS_API`.
  - Test : un téléchargement simulé en `nl` donne une piste externe de langue `dut`.

## Synthèse

*(à écrire quand tous les fichiers sont cochés)*
