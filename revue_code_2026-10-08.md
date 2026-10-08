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

- 2026-10-08 — Journal créé, base de tests relevée. Aucun fichier revu.
- Prochain : `core/bluray.py`.

### Base de tests (au départ)

`pip install -r requirements.txt pytest` puis `python -m pytest -q`, sous Linux
(Python 3.13.16, textual 8.2.8, rich 15.0.0, numpy 2.5.3, pytest 9.1.1), sans
GPU NVIDIA, sans `bin/` ni `resources_files/`.

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
- [ ] core/bluray.py (305)
- [ ] core/dvd.py (260)
- [ ] core/scanner.py (1040)
- [ ] core/decision.py (1386)
- [ ] core/encoder.py (891)
- [ ] core/annexes.py (68)
- [ ] core/muxer.py (638)
- [ ] core/joiner.py (244)
- [ ] core/dovi.py (358)
- [ ] core/sous_titres.py (141)
- [ ] core/sync.py (1547)
- [ ] core/preflight.py (629)
- [ ] core/updates.py (233)
- [ ] core/platform.py (213)
- [ ] core/config.py (402)
- [ ] core/profiles.py (299)
- [ ] core/i18n.py (210)
- [ ] core/cles.py (174)
- [ ] core/meta.py (371)
- [ ] core/opensubtitles.py (308)
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

## Synthèse

*(à écrire quand tous les fichiers sont cochés)*
