# Audit de localisation — 2026-10-04 (v0.8.9.62)

Volet localisation d'IE-83 (`D:\_Claude\TODO.md`). Rapport daté, non versionné.
**Ce fichier est aussi le journal de reprise** : la session peut être coupée
(veille, limite de crédit) à tout moment.

## Reprise

1. Lire ce fichier en entier (méthode, critères, constats déjà écrits).
2. Reprendre au **premier fichier non coché** de la liste. Un fichier coché a
   ses constats écrits sous « Constats » ; un fichier non coché est à refaire
   en entier, même s'il était « en cours ».
3. Après chaque fichier : écrire ses constats, cocher la case, mettre à jour
   « Dernier état ». Rien n'est gardé en mémoire d'un fichier à l'autre.
   Outil : `python _audit_log.py <fichier> <prochain> "<résumé>" < constats.md`
   (constats lus en UTF-8, écriture atomique). `_audit_log.py` est temporaire,
   à supprimer avec la fin de l'audit.
4. Aucun code n'est modifié pendant l'audit.
5. Quand tout est coché : synthèse (section « Synthèse »), puis une entrée de
   phase 4 par groupe de constats dans `TODO.md`, rattachée à IE-86…IE-95.

## Dernier état

- 2026-10-04 — `updater.py` fait (L-87). Synthèse écrite ; entrées de phase 4 reportées dans `TODO.md`. **Audit terminé.**

## Cadre (déjà tranché, ne pas re-signaler)

- Mécanisme `gettext`, **anglais source** (`msgid` anglais), `fr.po` = textes
  actuels (IE-111). Contexte `pgettext` pour les libellés courts ambigus,
  `ngettext` pour les pluriels, paramètres nommés.
- On traduit ce qui s'affiche, **jamais** ce qui s'écrit sur disque ou part vers
  un autre programme (IE-71 point 5) : suffixes/marques, titres de pistes
  réécrits, codes langue, clés/valeurs TOML, noms de profils, arguments des
  outils, jetons de release lus, journaux `logger/`, termes techniques.
- Formats (unités, séparateur, durées) suivent `[app] language` ; le français
  garde le point décimal (L-05, IE-90).
- Lanceurs `launch.bat`, `bootstrap.ps1`, `launcher/*.cs` : anglais seul,
  couverts par IE-91 → **hors audit**.
- Déjà corrigés : UX-27 (plancher de colonne = en-tête), UX-28, UX-29
  (couleur décidée sur un libellé).

## Critères (ce qu'on cherche)

- **C1 Concaténation** : phrase assemblée par morceaux (`"x " + y + " z"`,
  listes jointes avec « et », suffixes ajoutés à un mot).
- **C2 Pluriels / accords** : « piste(s) », `"s" if n > 1`, accords de genre.
- **C3 Largeurs** : `len()` ou largeur fixe calculée sur un texte affiché,
  padding / `ljust`, colonnes calées sur le français.
- **C4 Texte et donnée mêlés** : une même chaîne sert à l'affichage et à
  l'écriture disque / aux arguments / à la logique.
- **C5 Logique sur libellé** : comparaison, `in`, `startswith`, clé de dict,
  tri sur un texte affiché.
- **C6 Texte hors catalogue** : texte affiché construit hors d'un endroit
  extractible (constantes de module évaluées à l'import avant le chargement de
  la langue, textes dans des structures de données, CSS `content`, `Binding`).
- **C7 Formats** : nombres, dates, unités, durées formatés en dur (hors IE-90
  déjà connu, sauf cas non listé).
- **C8 Divers** : ambiguïté qui exige un contexte, majuscules/typographie
  françaises (espace avant `:`, guillemets « »), noms de touches affichés.

Format d'un constat : `L-NN` · critère · `fichier:ligne` · ce qui ne va pas ·
entrée de phase 4 visée.

**Motifs généraux** (signalés une fois, ne plus les répéter fichier par
fichier sauf cas particulier) : L-06 tables de module porteuses de texte,
L-07 f-strings → gabarits à paramètres nommés, L-09 touches citées dans le
texte, L-18 exceptions porteuses d'un texte affiché, L-20 pluriels via
`core/texte.pluriel`.

## Fichiers

L-01 à L-04 : constats d'un essai précédent interrompu, perdus ; la
numérotation reprend à L-06 (L-05 = séparateur décimal, tranché).

### core/
- [x] core/cles.py (167)
- [x] core/config.py (347)
- [x] core/decision.py (1238)
- [x] core/dovi.py (358)
- [x] core/encoder.py (839)
- [x] core/joiner.py (234)
- [x] core/meta.py (331)
- [x] core/muxer.py (607)
- [x] core/opensubtitles.py (289)
- [x] core/platform.py (204)
- [x] core/preflight.py (548)
- [x] core/preview.py (115)
- [x] core/profiles.py (292)
- [x] core/scanner.py (816)
- [x] core/sous_titres.py (141)
- [x] core/sync.py (1514)
- [x] core/texte.py (24)
- [x] core/updates.py (207)
- [x] core/veille.py (270)

### tui/
- [x] tui/app.py (457)
- [x] tui/common.py (531)
- [x] tui/mixins.py (291)
- [x] tui/widgets/entete.py (98)
- [x] tui/widgets/file_tree.py (130)
- [x] tui/widgets/footer.py (188)
- [x] tui/widgets/profile_form.py (655)
- [x] tui/screens/aide.py (439)
- [x] tui/screens/ancrage.py (154)
- [x] tui/screens/browser.py (1351)
- [x] tui/screens/cles.py (230)
- [x] tui/screens/config.py (343)
- [x] tui/screens/confirm.py (140)
- [x] tui/screens/delete_confirm.py (30)
- [x] tui/screens/donor_picker.py (296)
- [x] tui/screens/dryrun.py (424)
- [x] tui/screens/fin_lot.py (49)
- [x] tui/screens/join.py (350)
- [x] tui/screens/meta_popup.py (192)
- [x] tui/screens/mux_run.py (244)
- [x] tui/screens/opensubtitles.py (151)
- [x] tui/screens/options.py (104)
- [x] tui/screens/profile_picker.py (117)
- [x] tui/screens/quit.py (26)
- [x] tui/screens/recursive_confirm.py (30)
- [x] tui/screens/run.py (1444)
- [x] tui/screens/segments.py (134)
- [x] tui/screens/sync.py (1201)
- [x] tui/screens/tracks.py (765)
- [x] tui/screens/value_picker.py (96)
- [x] tui/screens/wizard.py (617)

### Racine
- [x] main.py (131)
- [x] updater.py (327)

## Constats

<!-- Un bloc par fichier, dans l'ordre de la liste. -->

### core/cles.py

- **L-06** · C6 · `core/cles.py:45-62` · `SERVICES` est un tuple de module
  construit à l'import : `usage`, `sans_cle` et les `Champ.libelle` (« Clé
  d'API », « Identifiant », « Mot de passe ») sont des textes affichés figés
  avant le chargement de la langue. Marquer avec `N_()` et traduire à
  l'affichage (`_(service.usage)`), ou faire de ces champs des propriétés.
  **Motif général** : toute table de module qui porte du texte affiché.
  → IE-86 (fournir `N_`), IE-87.
- **L-07** · C1 · `core/cles.py:122,126,129,154,163` · f-strings
  (`f"OMDb a répondu {r.status_code}."`). Avec `gettext`, `_()` doit
  recevoir le gabarit, pas la chaîne déjà formatée :
  `_("OMDb answered {status}.").format(status=…)`. **Motif général**, valable
  pour tout le code. → IE-87/IE-88, test structurel IE-94 (`_(f"…")`
  interdit).
- **L-08** · C8 · `core/cles.py:129` · le texte d'erreur d'OMDb
  (`r.json()['Error']`, en anglais) est affiché tel quel derrière un préfixe
  traduit : phrase bilingue en français. Acceptable (texte d'un service),
  mais à présenter comme citation (`_("OMDb: “{error}”")`), et le repli
  « réponse négative » passe au catalogue. → IE-87.
- **L-09** · C8 · `core/cles.py:49,58` · touches citées dans le texte
  (« O depuis le fichier donneur », « I, puis Tab ») : si une touche change,
  le texte ment, dans toutes les langues. Passer la touche en paramètre
  (`{key}`) depuis la table des `Binding`, avec commentaire au traducteur.
  **Motif général** (voir aussi `core/opensubtitles.py`, et `tui/`). → IE-88.

### core/config.py

- **L-10** · C3 · `core/config.py:76-88,203-220,277-314` · largeurs par défaut
  et planchers calés sur le **contenu français** : « 999.9 Go » (8),
  « → HEVC → HDR10 » (14), « exclu manuellement » (18), commentaires à
  l'appui. Ils deviennent faux dès qu'une traduction est plus longue. Le
  plancher doit se calculer depuis les libellés **traduits** à l'exécution
  (même idée qu'UX-27), et `tests/test_troncature.py` doit énumérer les
  libellés dans chaque langue livrée. → IE-88, IE-94.
- RAS sinon : `"language": "fr"` déjà traité (IE-71 point 3) ; `action_fin =
  "rien"` est une valeur enregistrée (affichage à vérifier dans
  `core/veille.py`) ; `ValueError("aucun profil à activer")` n'est pas
  affiché.

### core/decision.py

- **L-11** · C1 · `core/decision.py:800-803` · `_raison(base)` colle
  « · DV préservé, RPU réinjecté » / « · DV conservé → vidéo copiée » derrière
  la raison de chaque cas. Le collage par « · » est neutre, mais chaque
  morceau doit être un `msgid` complet, et la combinaison
  `"{reason} · {dv_note}"` un gabarit du catalogue. Même motif pour l'audio,
  `:1048,1055,1064,1072` (`f"{reason} · lossless → {out_codec}"`), où se
  mêlent en plus des mots anglais en dur dans le texte français (« lossless »,
  « copy », `preserve_hd_audio`, nom de clé de profil). → IE-87 ; trancher au
  glossaire (IE-85) si « lossless »/« copy » restent des termes.
- **L-12** · C7/C8 · `core/decision.py:809-810,822,834,849,860-863` ·
  raisons vidéo : unités et nombres dans le texte (`{info.kbps}k`, `+10 %`
  avec espace française, `1920x1080`). Gabarits à paramètres nommés ; « % » et
  l'espace avant relèvent de la traduction (IE-90). Les raisons sont bâties
  **une fois, au moment de la décision**, et stockées dans
  `VideoDecision.reason` / `AudioDecision.reason` : elles restent dans la
  langue du moment du calcul. Acceptable puisque la langue change au
  redémarrage (IE-71 point 3) ; **ne jamais** persister une raison sur
  disque. → IE-87.
- **L-13** · C6 · `core/decision.py:114-127,199-207` · `VideoDecision.label()`
  et `AudioDecision.display()` : seuls « (copie) » et « → copie » sont des
  mots ; « SKIP », « HDR10 », « DV », codecs sont des termes (glossaire).
  Libellés recopiés **localement** ailleurs : `tui/screens/dryrun.py:178`
  (« → HDR10 »), `tui/screens/tracks.py:310` (« → copie MKV/MP4 »),
  `tui/screens/wizard.py:292` (« → copie ») — un même mot à traduire à
  quatre endroits. Centraliser avant l'extraction. → IE-87/IE-88, IE-85
  (« SKIP » traduit ou non ?).
- **L-14** · C4 · `core/decision.py:732-751` · `_resolve_limits` rend un
  libellé « Original WxH » / « 1080p » jamais lu (`_` à l'appel, `:771`).
  Code mort : à retirer plutôt qu'à extraire. → IE-87.
- **L-15** · C3 · `core/decision.py:1023` et `tui/screens/tracks.py:275,316`
  · « exclu manuellement » écrit à deux endroits comme raison. Pas de
  comparaison trouvée (grep `reason ==`/`in` : rien), mais la largeur de la
  colonne `src` (18, `core/config.py:312`) est calée sur ce texte (L-10).
- **L-16** · C8 · `core/decision.py:1179-1181` · « Forcé manuellement (était
  SKIP) » / « (était retrait DV) » : deux phrases complètes, bien. RAS hors
  extraction.
- Donnée, ne se traduit pas : `SUFFIX_*`, `JETONS_*`, `_CODEC_TOKENS`,
  `_CODEC_LABELS` (écrits dans les titres de pistes), `retitle()`,
  `channel_layout_label` dans le stem — conforme à IE-71 point 5.

### core/dovi.py

- RAS. Uniquement des arguments d'outils (`dovi_tool`, ffmpeg, paramètres
  x265) et des messages de journal `_log` (hors catalogue). Aucun texte
  affiché.

### core/encoder.py

- **L-17** · C6 · `core/encoder.py:170-195` · `_CAUSES` : table de module
  (signature ffmpeg → message affiché). Phrases complètes, bien ; marquer
  `N_()` et traduire au retour de `diagnostiquer` (appelé par
  `tui/screens/run.py:583`). Les **signatures** restent en anglais (texte de
  ffmpeg, donnée). Motif L-06. → IE-87.
- **L-18** · C4 · `core/encoder.py:471-475,523-528` · `ValueError` dont le
  message est montré à l'utilisateur (`run.py:450,1173`, `join.py:268`,
  `mux_run.py:128` l'affichent). Une exception qui transporte un texte
  affiché mêle diagnostic et interface : soit elle porte un code +
  paramètres et l'écran traduit, soit le message est bâti avec `_()` au
  `raise`. Convention à fixer une fois (IE-86). Le second message contient un
  argument ffmpeg (`-itsoffset`) : commentaire au traducteur. **Motif
  général.** → IE-86, IE-87.
- **L-19** · C7 · `core/encoder.py:105-113,134-140,293` · `_seconds_to_time`
  (`H:MM:SS`) et `f"{duree:.2f} s"` (`pistes_audio_vides`, affiché par
  `run.py:530`) : formats en dur. Les deux premiers sont déjà dans IE-90 ;
  y ajouter `pistes_audio_vides` (unité, séparateur décimal). → IE-90.
- Donnée : `_SDR_TONEMAP_FILTER`, `_PROGRESS_RE` (lit la sortie **anglaise**
  de ffmpeg — ne jamais lancer ffmpeg sous une locale traduite), arguments,
  `title={titre}` (IE-71 point 5).

### core/joiner.py

- **L-20** · C2 · `core/joiner.py:130,165,171,194` · pluriels par
  `core/texte.pluriel` (règle française, voir `core/texte.py` : 18 appels
  dans le code, plus des accords à la main `tui/app.py:432-433`,
  `tui/screens/sync.py:618`, `tui/screens/run.py:1439`). Certains sans nom
  explicite : `pluriel(n, 'sélectionnée')` / `'donnée'` accorde un participe
  à un nom sous-entendu (« parties ») — intraduisible hors contexte. Chaque
  message doit devenir **une** phrase `ngettext` complète avec `{count}`.
  `:165` et `:171` portent **deux** nombres (« 3 pistes audio contre 2 : …
  n'en gardera que 2 ») : `ngettext` sur le premier, ou deux phrases.
  **Motif général.** → IE-87.
- **L-21** · C1 · `core/joiner.py:139-160` · constats bâtis
  `f"{nom} — vidéo en {codec}, {ref} en {codec}."` : phrases elliptiques,
  l'ordre des compléments dépend de la langue → gabarits à paramètres nommés.
  `ValueError` affichés (`:193-205`) : L-18. → IE-87.

### core/meta.py

- **L-22** · C4 · `core/meta.py:98-99,159-161,315-316` · `MovieMeta.kind`
  stocke le **libellé français** (« Film », « Série », « Mini-série »,
  « Téléfilm », « Épisode ») au lieu d'un code ; trois `kind_map` le
  recopient. Stocker un code (`movie`, `series`, `miniseries`, `tvmovie`,
  `episode`) et traduire à l'affichage (`meta_popup`). → IE-87/IE-88.
- **L-23** · C5 · `core/meta.py:234-235` + `tui/screens/meta_popup.py:160` ·
  `confiance` est un texte affiché (« titre et année », « titre »,
  « incertaine — le titre ne correspond pas ») et l'écran **teste**
  `meta.confiance.startswith("incertaine")` pour choisir la couleur. Traduit,
  le test tombe (même famille qu'UX-29). Rendre un niveau (enum) + un
  libellé. → IE-87, IE-88 ; test structurel IE-94.
- **L-24** · C6/C8 · `core/meta.py:96,144,157,175,253,269` · messages
  (`RuntimeError` affichés, synopsis de substitution « Note et synopsis
  disponibles avec une clé OMDb… ») : extraire ; l'erreur d'OMDb est citée
  (L-08). `.removeprefix("Avec")` (`:296`) lit le HTML d'AlloCiné :
  **donnée**, ne pas traduire. Genres et synopsis viennent du service dans
  **sa** langue (AlloCiné = français) : à dire dans le guide anglais, pas un
  défaut. → IE-87.

### core/muxer.py

- **L-25** · C8/C7 · `core/muxer.py:88-91,114-121` · `IdentifiedTrack.display`
  insère des guillemets français « … » ; `sync_label` écrit
  `+120 ms ×24000/25025`. Les guillemets passent au gabarit traduit, l'unité
  « ms » à IE-90. Langue affichée en code ISO (`fre`) : c'est un code, pas un
  nom de langue en clair — cohérent avec IE-71 point 5.
- `ValueError` affichés `:311,315,322,408` : L-18. Donnée : `_LANG_TOKENS`
  (jetons lus dans les noms de fichiers), `--track-name` (titre écrit dans le
  fichier).

### core/opensubtitles.py

- **L-26** · C8 · `core/opensubtitles.py:122,153,171` · touches citées dans
  les messages (« F5, puis K « Clés d'API » ») : motif L-09, plus le **nom
  d'un écran** cité entre guillemets, qui doit rester identique au titre
  traduit de cet écran → même `msgid` réutilisé, ou paramètre. → IE-87/IE-88.
- **L-27** · C1 · `core/opensubtitles.py:282-288` · `_message_quota` :
  « Quota … épuisé » + `f" — {remise}"` + « . » ; `remise` est le texte brut
  de l'API (anglais, ou une date ISO `reset_time` jamais formatée). Deux
  gabarits complets (avec / sans remise) ; formater la date selon la langue
  (IE-90). `:146,160,163` : f-strings (L-07), `{secondes}` à mettre au
  pluriel (L-20). → IE-87, IE-90.

### core/platform.py

- **L-28** · C1 · `core/platform.py:127-133` · `exige` est un morceau de
  phrase (« le pilote NVIDIA 610 ou plus récent » / « un pilote NVIDIA plus
  récent ») inséré dans une autre phrase : l'article et l'accord dépendent
  de la langue. Deux messages complets (version connue / inconnue). Le texte
  recopie en partie `_CAUSES` de `core/encoder.py:175-178` : un seul message
  dans le catalogue. → IE-87.
- Donnée : les regex lisent la sortie **anglaise** de ffmpeg (`:121,125`) ;
  `__str__` (`:50-56`) sert au journal et à la console, pas à l'interface.

### core/preflight.py

- **L-29** · C5 · `core/preflight.py:396-397,414-415,427-428,440-441,521-522`
  · questions console « … ? (o/N) : » et réponse testée `answer == "o"`. En
  anglais, l'invite devient « (y/N) » et la lettre attendue `y` : la lettre
  d'acceptation doit venir du **même** catalogue que l'invite (`pgettext("yes
  key", "y")`), et accepter les deux (`o`/`y`) évite qu'un français tapant
  `o` sur une console anglaise soit refusé. Même contrôle à faire dans
  `updater.py` (IE-97). → IE-91 (console), IE-87.
- **L-30** · C6 · `core/preflight.py:158-537` · une quarantaine de messages
  console (`print`) avec puces `✓`/`✗` et indentation en tête de chaîne. Les
  puces et l'indentation sont de la mise en forme : les sortir du `msgid`
  (`print("  ✗ " + _("…"))`) pour que le traducteur ne les recopie pas.
  `:390` (« Renseignez config.toml > [ffmpeg] > fetch_url ») cite une clé de
  config : donnée dans le texte, commentaire au traducteur. Selon IE-91, le
  preflight tourne **après** le chargement de la langue : il passe par le
  catalogue. Vérifier l'ordre réel dans `main.py` (fait au passage de
  `main.py`). → IE-91.

### core/preview.py

- **L-31** · C8 · `core/preview.py:114-115` · aide affichée sur les touches de
  **mpv** (« z / Z », « Ctrl++ / Ctrl+- ») : ces touches appartiennent à mpv,
  pas à IRIS — elles restent telles quelles, seul le texte autour se
  traduit ; commentaire au traducteur. `:62,107` : messages simples. → IE-87.

### core/profiles.py

- **L-32** · C2 · `core/profiles.py:198,203` · avertissements console (`⚠`)
  avec `{n} profils` (pluriel, L-20) et cible `[{id}]` (nom de profil =
  donnée). Préfixe `⚠  ` hors `msgid` (comme L-30). → IE-87.
- Les profils livrés ne portent **aucun** texte affiché (pas de champ
  description/libellé) : leurs identifiants `series_*`, `movie_*`… sont des
  noms neutres (IE-71 point 2). Les valeurs `dolby_vision = "sdr"`,
  `container = "auto"`, `preset_encoder = "fast"` sont des valeurs
  enregistrées : leur **libellé** affiché se traduit dans
  `tui/widgets/profile_form.py` (à vérifier là).

### core/scanner.py

- RAS. `display()`, `resolution_label`, `dv_label`, `channel_layout_label`
  ne produisent que des termes techniques et des codes (`DV:P8.1`, `5.1`,
  `1080p`, codes ISO) : rien à traduire. Le seul mot, le « ? » de langue
  inconnue, est universel.
- Donnée, à ne **pas** lier à la langue de l'interface : `is_forced` lit
  « forced »/« forcé » dans le **titre de piste** (`:388`) — c'est la langue
  du fichier, pas de l'interface ; `MARQUE_IRIS`, jetons de release, motifs
  lus dans la sortie de `dovi_tool` (« Mastering display », « light level »,
  `:613,635`). `RuntimeError(f"ffprobe: …")` porte la sortie de ffprobe :
  diagnostic, L-18 si affiché.

### core/sous_titres.py

- RAS. Aucun texte affiché : SRT écrits sur disque (réplique invisible =
  espace insécable, donnée), arguments ffmpeg, journal.

### core/sync.py

- **L-33** · C2/C6 · `core/sync.py:69-81` · `NIVEAUX_CONFIANCE = ("aucune",
  "faible", "moyenne", "excellente")` : adjectifs **accordés au féminin** de
  « confiance », figés dans un tuple de module. Utilisés hors de la phrase
  qui porte le nom (`tui/screens/segments.py:87`, colonne seule) : en
  français l'accord tient par chance, d'autres langues accordent autrement
  ou pas du tout. Rendre un **niveau** (enum 0-3) et traduire le mot avec un
  contexte (`pgettext("confidence level", "low")`). → IE-87, IE-88.
- **L-34** · C1 · `core/sync.py:212-253` · `SyncResult.label()` et
  `report()` empilent des morceaux (`out += " (confiance …)"`,
  `head += "  → contrôlez avant de muxer"`, `" · ".join(...)`, « plages
  (ms) : … — G pour le détail »). Le rapport est un tableau de mesures : le
  garder en **lignes clé : valeur** (un gabarit par ligne), et la touche `G`
  en paramètre (L-09). `{speech_ratio:.0%}`, `{confidence:.2f}` : formats
  numériques (IE-90). → IE-87, IE-90.
- **L-35** · C4 · `core/sync.py:215,1257-1499` · `SyncResult.reason` et les
  raisons de refus (`"aucun audio exploitable"`, `"sous-titre image — aucun
  texte à corréler"`…) sont des textes stockés dans le résultat, puis
  recollés derrière « échec — » / « Mesure refusée — ». Aucune comparaison
  trouvée, mais deux variantes quasi identiques du même message coexistent
  (`:1399` / `:1481`, `:1403` / `:1486`, `:1407` / `:1492`, `:1412` /
  `:1499`) : deux `msgid` pour une même idée. Les unifier avant extraction.
  → IE-87.
- **L-36** · C7 · `core/sync.py:666-693,734` · messages d'approximation du
  recalage avec `mmss()` et secondes (`{…} s`) : formats (IE-90) ; `ValueError`
  affichés (L-18). `diagnosis()` (`:255-275`) : phrases complètes, bien.

### core/texte.py

- **L-37** · C2 · `core/texte.py:10-24` · `accorde()` code la règle
  **française** (singulier jusqu'à 1, donc « 0 fichier ») et fabrique le
  pluriel en ajoutant « s » à chaque mot. En anglais 0 prend le pluriel
  (« 0 files ») ; d'autres langues ont 3 formes ou plus (polonais, russe).
  Le module entier est remplacé par `ngettext`, dont les règles viennent de
  l'en-tête `Plural-Forms` de chaque `.po`. Le point d'entrée unique voulu
  par UX-15 est le bon réflexe : c'est **là** que se branche `ngettext`, mais
  la signature doit changer — `ngettext` veut la phrase entière (avec le
  nombre en `{count}`), pas un mot à accorder. Tous les appels (L-20) sont à
  réécrire. → IE-86 (fournir l'helper), IE-87/IE-88.

### core/updates.py

- RAS. `UpdateInfo.label()` (`:41-43`) : « outil : version → version », sans
  mot à traduire hors l'espace avant « : » (typographie française, au gabarit).
  URL et noms d'archives : donnée.

### core/veille.py

- **L-38** · C6 · `core/veille.py:35-41` · `ACTIONS_FIN` : clés enregistrées
  dans `config.toml` (`rien`, `veille`, `veille_prolongee`, `arret` — valeurs
  françaises mais **données**, IE-71 point 5 : ne pas les renommer) → libellés
  affichés dans une table de module (motif L-06). `config.py:341` compare bien
  la **clé**, pas le libellé : conforme. `:190,195,268` : messages simples.
  → IE-87.

### tui/app.py

- **L-39** · C6 · `tui/app.py:58-71` (et chaque écran) · `BINDINGS` : les
  descriptions de `Binding` sont des **attributs de classe**, évalués à
  l'import du module, avant tout chargement de langue. Deux voies : traduire
  au rendu (le `KeyFooter` maison, `tui/widgets/footer.py`, lit
  `binding.description` → y appliquer `_()`, descriptions marquées `N_()`),
  ou construire `BINDINGS` après `i18n.init()`. La première est la seule
  qui tienne avec des écrans importés tôt. **Motif général** pour les ~150
  `Binding` (IE-88). → IE-86, IE-88.
- **L-40** · C8 · `tui/app.py:59` · description « F10 Quitter » : le nom de
  la touche est **dans** le texte de l'action (convention du projet pour F10,
  « en dernier dans les footers »). Le traducteur ne doit pas toucher « F10 »
  et la touche ne peut plus changer sans retraduire : séparer touche et
  libellé, le footer les recompose. À vérifier dans `footer.py`. → IE-88.
- **L-41** · C2 · `tui/app.py:431-433` · accord **à la main** sur trois mots
  (« ne seront pas encodés » / « ne sera pas encodé ») en plus de
  `pluriel()` : cas d'école pour `ngettext` (phrase entière). `:238` :
  `pluriel(n, 'fichier ajouté')` suivi de « à la file — F12 pour la suivre »,
  phrase coupée en deux autour du pluriel. → IE-88 (L-20, L-37).
- **L-42** · C6/C1 · `tui/app.py:405-416,280-282,336` · `_TRAVAUX` : table de
  classe (motif L-06), phrases complètes, bien. Titre de la barre :
  `f"{f12} Encodages en cours · {done}/{total} · {pct} %"` — gabarit à
  paramètres, `%` et espace avant à la traduction (IE-90). `:233`
  `', '.join(noms)` : séparateur de liste à la langue (souvent « , », mais à
  passer par le catalogue ou une fonction de liste). → IE-88, IE-90.
- CSS (`:40-56`) : aucun texte affiché (pas de `content:`).

### tui/common.py

- **L-43** · C5 · `tui/common.py:486` + `core/profiles.py:131-132` · **récidive
  d'UX-29** : la couleur de la colonne « HD audio » se décide sur
  `f["hd_audio"] == "oui"`, texte produit par `Profile.summary_fields()`
  (« oui »/« non », « ⚠ oui »). Traduit, la colonne ne s'allume plus. Lire
  `prof.data["preserve_hd_audio"]` comme le fait déjà la colonne Source.
  `summary_fields` mêle en outre libellés et valeurs (`"4k": "3500k ✓"`) :
  il rendrait mieux des valeurs brutes, l'écran les met en mots. Correction
  à faire **avant** l'extraction, comme UX-29. → IE-88 ; test IE-94 (aucune
  comparaison à un littéral affiché).
- **L-44** · C6/C1 · `tui/common.py:275-300` · `CODEC_PICKER_OPTS` (liste de
  module, « AV1  (⚠ très gourmand) ») et `opts[i] += "  ✗ indisponible ici"`
  (mention collée au libellé). L-06 + gabarit `"{codec}  ✗ {unavailable}"`.
  Vérifier que le picker rend un **index** et non le texte choisi (à voir
  dans `value_picker.py`). → IE-88.
- **L-45** · C6/C8 · `tui/common.py:55-79,326-345,468-469,185` · tables de
  module : `TOUCHES` (noms de touches **affichés** — « Suppr » est français,
  « Del » en anglais ; les flèches et symboles restent), `FOOTER_NAV`,
  `FOOTER_RESIZE`, `FOOTER_BACK`, `FOOTER_ACCUEIL`, `FOOTER_QUIT` (libellés
  « Début », « Col préc. »…), `PROFIL_COLONNES` (en-têtes, dont l'abréviation
  « Dolby V. »), `ECARTEE`. Motif L-06 ; les abréviations (« Col préc. »,
  « suppr. », « Dolby V. ») exigent un commentaire de longueur maximale.
  → IE-88.
- **L-46** · C3 · `tui/common.py:157-166` · `largeur_entete` mesure
  `len(libelle)` alors que `largeurs_colonnes` (`:494`) mesure déjà
  `cell_len`. Différence nulle en français/anglais, fausse pour toute langue
  à caractères pleine chasse (CJK) ou avec signes combinants. Utiliser
  `cell_len` partout ; idem pour toute largeur calculée à partir d'un texte
  traduit. → IE-88.
- **L-47** · C7 · `tui/common.py:188-211,316` · `fmt_bytes` (`To/Go/Mo/Ko`),
  `fmt_duration`, `f"{v} kbps"`, `f"{n}k"` (`cellules_profil`,
  `summary_fields`) : IE-90 couvre `fmt_bytes` ; y ajouter les débits
  (`kbps`, suffixe `k`). → IE-90.
- `barre_etat`, `raccourci(s)`, `SEP_*` : séparateurs typographiques
  neutres, OK. `_CODECS_MKVMERGE`, `nom_codec`, `langue_affichee` : donnée.

### tui/mixins.py

- **L-48** · C6 · `tui/mixins.py:32-37,136-141,285` · `BINDINGS` des mixins
  (« Début », « Col préc. »…) : **mêmes textes** que `FOOTER_NAV` /
  `FOOTER_RESIZE` de `tui/common.py` — même `msgid`, donc une seule
  traduction, mais deux sources à garder identiques : faire lire l'une par
  l'autre. Motif L-39. `:285` : message avec deux paramètres, f-string (L-07).
  → IE-88.

### tui/widgets/entete.py

- **L-49** · C3/C7 · `tui/widgets/entete.py:28-54` · `AideEtHeure` a une
  **largeur fixe** `_LARGEUR = 21` calée sur « H Aide · 00:12:34 ». « Help »
  tient, une langue plus longue (« Hilfe », « Ayuda » tiennent ; « Справка »
  aussi, mais une langue CJK ou un mot plus long non) serait coupée par
  l'ellipse. Calculer la largeur depuis le libellé traduit (`cell_len`).
  L'heure : `strftime("%X")` dépend de la locale C du processus — aujourd'hui
  `HH:MM:SS` parce que personne n'appelle `setlocale` ; IE-71 point 4 exclut
  le module `locale` : écrire le format explicitement (`%H:%M:%S`) pour qu'un
  `setlocale` futur ne le change pas en douce. → IE-88, IE-90.

### tui/widgets/file_tree.py

- RAS. Aucun texte affiché (arborescence de fichiers : noms du disque).

### tui/widgets/footer.py

- **L-50** · C3 · `tui/widgets/footer.py:47-48` · `_entry_width` mesure
  `len()` de la touche et de la description : même défaut que L-46 (pleine
  chasse) — `cell_len`. Le footer sépare bien touche et libellé
  (`_render_line`) : la traduction ne porte que sur la description, bonne
  base. Conséquence pour L-40 : « F10 Quitter » dans `tui/app.py:59` n'est pas
  la source du footer (qui prend `FOOTER_QUIT = ("f10", "Quitter")`) ; il ne
  reste visible que dans les vues Textual qui lisent `Binding.description`
  (palette de commandes) — l'aligner sur « Quitter ». → IE-88.

### tui/widgets/profile_form.py

- **L-51** · C6 · `tui/widgets/profile_form.py:36-64,600-…` · tables de
  module des options (`_BITRATE_4K` « 8000k ⚠ recommandé », `_HDR10_QUALITY`,
  `_CONTENEUR`, `_HD_AUDIO`) et `_PRESET_TXT` / `_HD_AUDIO_TXT` (textes de
  conséquence) : motif L-06. **Bon point** : chaque option est un couple
  (libellé, valeur) et la logique lit la **valeur** (`:427-434`,
  `_HD_AUDIO_VERS_CLES`) — conforme à IE-71 point 5. Les valeurs affichées
  dans les libellés (`hdr10`, `fast`, `compat`, `quality`, `auto`, `mp4`) sont
  des valeurs de `profiles.toml` : les garder telles quelles dans le libellé
  traduit, commentaire au traducteur. → IE-88.
- **L-52** · C1/C8 · `tui/widgets/profile_form.py:228-…,414-439` · titres de
  section `"── QUAND RÉENCODER"` : le filet `── ` et les **capitales** sont de
  la mise en forme dans le `msgid` — sortir le filet, et faire les capitales
  au rendu (`.upper()`) ou laisser le traducteur décider (les capitales
  pleines ne conviennent pas à toutes les écritures). Conséquences
  (`refresh_consequences`) : phrases complètes avec paramètres
  (`{k4}k en 4K…`), plus un collage « Ne s'applique qu'aux fichiers
  réellement réencodés — {texte du preset} » (`:422`) : gabarit unique.
  `kbps` dans les libellés : IE-90. Messages de validation `:587-594` :
  simples. → IE-88.

### tui/screens/aide.py

- **L-53** · C6 · `tui/screens/aide.py:42-247,251-270` · `_COMMUNES`,
  `_PAR_ECRAN` (≈120 explications) et `_ORDRE` (titres et résumés des écrans)
  : tables de module (L-06), à traduire au rendu. Le guide lit **aussi** les
  `Binding.description` (`touches_de`, `:302-318`) : il hérite de L-39 —
  traduire `description` au rendu, ici comme dans le footer. `_ORDRE` répète
  les titres d'écran (« Accueil », « Pistes », « Recalage »…) : même `msgid`
  que les titres réels des écrans, sinon le guide et l'écran divergent.
  → IE-89.
- **L-54** · C3 · `tui/screens/aide.py:410-433,44,73` · repli **manuel** des
  explications : découpe sur les espaces, mesure en `len()`, largeur fixe
  74 − 14, touche alignée par `f"{touche:<12}"`. Faux pour une écriture sans
  espaces (CJK) ou pleine chasse, et l'intro (`:36-39`) porte des **retours à
  la ligne en dur** dans le texte (« construite à partir des raccourcis\n »)
  : le traducteur devrait recouper à la main. Replier avec `cell_len` (ou
  `rich` avec une grille à deux colonnes), et retirer les `\n` des `msgid`.
  `titre.upper()` (`:74`) : capitales au rendu, bien (cf. L-52). → IE-89.
- **L-55** · C8 · `tui/screens/aide.py:98,107,121,…` · les explications
  **citent** d'autres libellés de l'interface (« ← écartée » dans la colonne
  Décision, « ⚠ SUPPRIMER », « Activé par W », « AlloCiné, puis IMDB avec
  Tab ») : touche (L-09) et libellés cités doivent suivre leur traduction.
  Passer le libellé cité en paramètre (`{discarded}` = `_(ECARTEE)`), sinon
  le guide anglais citera un libellé qui n'existe pas. `tests/test_aide.py`
  pourrait vérifier qu'un libellé cité existe dans le catalogue. → IE-89,
  IE-94.

### tui/screens/ancrage.py

- **L-56** · C7 · `tui/screens/ancrage.py:100,141` + `core/sync.py:136` · la
  saisie accepte `13:22,5` **et** `13:22.5` (la virgule est remplacée) — bien,
  indépendant de la langue. Mais l'exemple affiché écrit « 13:22,5 » alors
  que l'application garde le point décimal en français (L-05) : incohérent
  dès aujourd'hui ; l'exemple doit suivre le séparateur de la langue (IE-90).
- **L-57** · C1 · `tui/screens/ancrage.py:112-114,98-99` · « Réplique {i} sur
  {n}   ·   écrite à » puis l'instant ajouté à part (pour le style gras) :
  phrase coupée. Avec Rich, un gabarit traduit peut porter un marqueur que
  l'on remplace par le segment stylé (`Text.assemble` après découpe sur
  `{time}`) : prévoir cet helper une fois pour tous les écrans (IE-86).
  Retours à la ligne en dur (`:98`) : L-54 ; « ↓ » dans le texte : L-09.
  → IE-86, IE-88.

### tui/screens/browser.py

- **L-58** · C1/C2 · `tui/screens/browser.py:518-531` · barre d'état bâtie
  par morceaux : `f"{sel}/{total} {accorde(sel, 'sélectionné')}"` (accord
  sur le premier nombre seul, L-37), filtres joints par `" + "` (« Dolby
  Vision + sans SKIP »), « Filtre : … (3 masqués) », « Col : {label}  </> ».
  Chaque élément de la barre doit être un gabarit complet ; la jointure des
  filtres passe par une fonction de liste. → IE-88.
- **L-59** · C8 · `tui/screens/browser.py:764-765` · « {nom} n'était pas à
  réencoder : cochée, elle sera encodée… » : l'accord au féminin vise la
  **ligne** sous-entendue, pas le fichier nommé — contexte indispensable
  pour le traducteur (commentaire), ou réécrire avec le sujet explicite
  (« la ligne {nom} »). `:767` : pluriel déguisé par « : {n} » en fin de
  phrase — le garder (formulation qui évite l'accord) ou `ngettext`. → IE-88.
- **L-60** · C6 · `tui/screens/browser.py:253-298,442-496` · `BINDINGS`,
  `RESIZE_LABELS` (attributs de classe) et listes de raccourcis du footer qui
  **recopient** les descriptions des `Binding` (« Aperçu », « Encoder »,
  « Profil », « Gérer » écrits 3 fois : `:276-279`, `:369-372`, `:495-496`,
  `:1216`) : L-39 + L-48. Le libellé variable de `W` (« Assistant » /
  « Manuel ») et de `Z` (« Afficher SKIP » / « Masquer SKIP ») est choisi par
  **touche**, pas par texte : conforme. → IE-88.
- **L-61** · C4 · `tui/screens/browser.py:201-245` · `type_image` rend des
  **codes** (`DV:P8.1`, `HDR`, `SDR`) qui servent à la fois de valeur de
  filtre (`ligne_visible`, `startswith("DV:")`) et de libellé affiché
  (`options_filtre`, `libelle_filtre`). Tant que ce sont des termes
  techniques non traduits (glossaire IE-85), ça tient ; si « SDR »/« HDR »
  devaient un jour se traduire, le filtre casserait. Garder la valeur (code)
  et le libellé distincts dans `options_filtre`, déjà en couples : seul
  `libelle_filtre` rend le code tel quel. → IE-85, IE-88.
- Rien d'autre que les motifs connus : f-strings (L-07), pluriels (L-20),
  touches dans les messages (`:1114-1116,1196-1199`, L-09).

### tui/screens/cles.py

- **L-62** · C1 · `tui/screens/cles.py:115-117,221` · boutons avec puce
  (« ✓  Vérifier et enregistrer », « ✗  Plus tard ») qui doublent les
  libellés des `Binding` sans puce (`:119-120`) : deux `msgid` pour une même
  action, sortir la puce. `:221` colle l'erreur du vérificateur (déjà une
  phrase, `core/cles.py`) et « Rien n'est enregistré pour ce service. » :
  deux phrases juxtaposées, acceptable si chacune est complète. Panneau
  `width: 88` avec `max-width: 96%` : tient. → IE-88.

### tui/screens/config.py

- **L-63** · C1/C3 · `tui/screens/config.py:118-121,250-255,312` · colonne
  « Actions » remplie du texte fixe « ✎ éditer  ✕ suppr. » (abréviation,
  longueur à surveiller ; largeur calculée par `largeurs_colonnes` en
  `cell_len` : bien). En-tête de formulaire bâti par morceaux :
  `f" {lbl}   —   " + raccourcis(...)` — séparateurs de mise en forme,
  acceptable ; « Copie de {id} », « Édition — {id} » : gabarits.
  `:312` : titre d'écran + message de succès dans **une** chaîne (« Configuration
  — Profils d'encodage   ✓ Profil [{id}] enregistré et actif ») : deux
  `msgid` (titre, message), assemblés par le code. → IE-88.

### tui/screens/confirm.py

- **L-64** · C1 · `tui/screens/confirm.py:43-44,64,68` · `ConfirmModal`
  colle la puce au libellé reçu (`f"✓  {confirm_label}"`) : la puce reste hors
  `msgid`, **bien** — c'est le modèle à suivre ailleurs (L-30, L-62). Défauts
  `confirm_label="Confirmer"` / `"Annuler"` en **valeurs par défaut de
  paramètre** : évaluées à l'import, avant la langue (L-06) → `None` par
  défaut et `_()` dans le corps. Panneau `width: 70` fixe : les boutons
  traduits plus longs (allemand) peuvent ne pas tenir côte à côte — à
  vérifier sur captures anglaises (IE-94). → IE-88.

### tui/screens/delete_confirm.py

- **L-65** · C8 · `tui/screens/delete_confirm.py:16-22` · corps en **markup
  Rich** (`[bold]…[/bold]`, `[bold dark_orange]…`) mêlé au texte : le
  traducteur verrait et pourrait casser les balises, et le style est une
  décision d'interface, pas de langue. Garder des gabarits sans balises
  (« File: {name} ») et appliquer le style par le code (`Text.assemble`, cf.
  L-57). Le titre « Ctrl+D — Supprimer le fichier » porte la touche dans le
  texte (L-09). **Motif général** : tout `markup=True` sur un texte traduit.
  → IE-86 (règle), IE-88.

### tui/screens/donor_picker.py

- **L-66** · C3 · `tui/screens/donor_picker.py:252-257,272` · en-têtes
  « Piste », « Type », « Langue »… écrits **deux fois** (`add_column(label,
  width=largeur_entete(label, n))`) : il faudra traduire les deux de la même
  façon — passer par une variable. Planchers de contenu calés sur le
  français : « Type » à 11 pour « sous-titre » (10), « Langue » à 8.
  `Text("audio" if … else "sous-titre")` : libellé de type (aussi dans
  `tui/screens/sync.py:314`) → une fonction commune. « (aucune piste
  lisible) » : simple. → IE-88.

### tui/screens/dryrun.py

- **L-67** · C1 · `tui/screens/dryrun.py:282-296` · résumé bâti par
  morceaux optionnels (`av1_str`, `dv_str`, `strip_str`, `gain_str`) collés
  dans « À encoder : HEVC {n} · H264 {n}… · SKIP {n} » ; « Source : … →
  Estimé : … ({sign}{pct}%) ». Les compteurs par codec sont des termes, mais
  « À encoder », « Source », « Estimé » doivent être des gabarits, et la
  liste des éléments présents se joint par le code (`SEP_ETAT`), pas dans le
  texte. `{pct:.0f}%` sans espace ici, `{pct} %` ailleurs (`tui/app.py:282`) :
  incohérence déjà en français, à régler par IE-90. Bloc `dv_str` (`:176-181`)
  : quatrième copie des libellés DV (L-13). → IE-88, IE-90.
- **L-68** · C4 · `tui/screens/dryrun.py:354,364` · raisons écrites à la
  main : `f"Modifié manuellement (dry-run) : {new_action.name}"` affiche le
  **nom de l'énumération** (`ENCODE_HEVC`) — donnée de code montrée à
  l'utilisateur, et « (dry-run) » / « (aperçu) » désignent le même écran sous
  deux noms. Utiliser le libellé de l'action (`choisir_codec(...).label()`)
  et un seul nom d'écran (glossaire IE-85). → IE-85, IE-88.

### tui/screens/fin_lot.py

- **L-69** · C1/C8 · `tui/screens/fin_lot.py:32-33` · titre
  `f"{libelle.capitalize()} dans {n} s"` : le libellé de l'action (« mise en
  veille », `core/veille.ACTIONS_FIN`) est inséré **en tête** de phrase et
  capitalisé par le code. `capitalize()` met aussi en minuscules le reste
  (« Veille prolongée » ok, mais un sigle ou un nom propre traduit serait
  abîmé), et l'ordre « action dans N s » dépend de la langue. Gabarit
  `"{action} in {seconds} s"` traduit, avec `ngettext` sur les secondes ; la
  majuscule initiale relève du traducteur (fournir un libellé de titre). →
  IE-88.

### tui/screens/join.py

- **L-70** · C1 · `tui/screens/join.py:194-199,249-251` · en-tête + liste à
  puces assemblés par le code (`"…:\n  · " + "\n  · ".join(...)`) : la puce
  et l'indentation sont dans le `msgid` de l'en-tête. Traduire l'en-tête
  seul, le code ajoute les puces. `:202,324` : touches dans le texte
  (« Ctrl+↑/↓ », « F2 », « BACKSPACE », « Ctrl+D », L-09) — « BACKSPACE » en
  toutes lettres et en capitales, alors que le reste de l'interface écrit
  « ⌫ » (`TOUCHES`) : incohérent dès aujourd'hui. `:319` : « {durée} pour
  {attendu} attendues ({n} s) » — accord de « attendues » sur « minutes »
  implicites, contexte requis. → IE-88.

### tui/screens/meta_popup.py

- **L-71** · C5/C7 · `tui/screens/meta_popup.py:160,166-173,153-155` ·
  confirme L-23 (`confiance.startswith("incertaine")`) et L-22 (`meta.kind`
  affiché tel quel). « Réalisateur » au singulier pour une liste de jusqu'à
  trois noms (`ngettext` sur `len(directors)`), listes jointes par `", "`
  (L-42). Note `f"{rating:.1f} / {max:.0f}"` : séparateur décimal (IE-90).
  `_LIBELLES` (« AlloCiné », « IMDB ») : noms propres. → IE-88, IE-90.

### tui/screens/mux_run.py

- Motifs connus seulement : `pluriel(n, 'piste greffée')` (`:105`, L-20),
  touches dans le texte (« F2 encodera ce fichier », `:194`, L-09), messages à
  puce `✓`/`✗`/`▶` en tête de `msgid` (L-30/L-64), `ValueError` affiché
  (`:128`, L-18). Rien de propre à l'écran.

### tui/screens/opensubtitles.py

- **L-72** · C8 · `tui/screens/opensubtitles.py:80-82` · en-têtes abrégés
  « Téléch. » et **sigle français** « SME » (sourds et malentendants) : en
  anglais « HI » ou « SDH » — un sigle se traduit, il faut un commentaire qui
  dit ce qu'il abrège et la largeur disponible (4). « Release » est déjà un
  emprunt anglais en français : terme du glossaire (IE-85). `:120` : deux
  nombres dans une phrase (`pluriel` + « dont {n} … déjà synchronisés ») ;
  `:147` « {n} restant(s) aujourd'hui » : `ngettext`. → IE-85, IE-88.

### tui/screens/options.py

- Motifs connus : `:68` « Après le lot ({touche} pendant l'encodage) » (touche
  en paramètre, bien), `:74` secondes (`ngettext`). `:78` « Windows
  seulement » : nom propre. Panneau `width: 76` / `max-width: 96%`.

### tui/screens/profile_picker.py

- RAS. Titre simple ; les noms de profils listés sont des identifiants
  (donnée, IE-71 point 2).

### tui/screens/quit.py

- RAS. Titre et repli simples ; la liste des travaux vient de
  `tui/app.py` (L-41, L-42). « IRIS ENCODE » : nom propre.

### tui/screens/recursive_confirm.py

- Corps en markup Rich (`[bold]…`) : motif L-65. Titre « R — Encoder le
  dossier » : touche dans le texte (L-09). « (illimités) » s'accorde avec
  « sous-répertoires » : phrase complète, bien.

### tui/screens/run.py

- **L-73** · C1 · `tui/screens/run.py:763,790,807,843,870` · étapes
  numérotées dans le texte (« ▶ 1/{n} Extraction du flux HEVC… », « ▶ 3/4
  Transcodage… ») : le compteur est de la mise en forme, à sortir du `msgid`
  (`"▶ {step}/{total} " + _("Extracting the HEVC stream…")`). Au passage :
  `:807` écrit « 3/4 » **en dur** quand ses voisines calculent le total —
  défaut d'affichage indépendant de la langue, à signaler à IE-83 (revue de
  code). `:695` : message + dernière ligne de stderr collés (`"… a échoué : "
  + …`) → gabarit `{detail}`. → IE-88.
- **L-74** · C3 · `tui/screens/run.py:296-311` · cellule d'état : `échec :
  {s.error_msg[:30]}` coupe le message **traduit** à 30 caractères par
  tranche de chaîne (peut couper au milieu d'un mot, ou d'un graphème
  composé) — passer par `tronquer_milieu`/`cell_len` ou laisser `cellule()`
  ellipser. Progression `f"{pct:.0f}% ({écoulé} / {restant} · {vitesse:.2f}x)"` :
  formats IE-90. **Bon point** : l'état est un `FileState` (enum), le texte
  n'est choisi qu'à l'affichage. → IE-88, IE-90.
- **L-75** · C1/C2 · `tui/screens/run.py:1223,1436-1442,1319` · bilan
  « réussis : {n} · en échec : {n} · ignorés : {n} » (trois pluriels
  implicites) ; corps de confirmation assemblé par `+` avec `\n` en tête de
  la seconde phrase, et accord manuel `restants > 1` (`:1438-1440`, L-41) ;
  `:1319` « (… {touche}, puis {touche}) » : touches en paramètre, bien.
  `s.last_line = "Arrêté"` / « Passé manuellement » : texte affiché stocké
  dans l'état, non comparé (grep) — acceptable. `:1318` compare la **clé**
  `"rien"` (donnée de config, L-38) : conforme. → IE-88.

### tui/screens/segments.py

- **L-76** · C2/C8 · `tui/screens/segments.py:22,87,125` · colonne de
  confiance remplie par `libelle_confiance` (adjectif féminin seul, L-33) ;
  en-têtes « Décalage », « Écart », « Durée » (table de module, L-06) ;
  `:125` texte long avec `\n` en dur au milieu d'une phrase (L-54). → IE-88.

### tui/screens/sync.py

- **L-77** · C4 · `tui/screens/sync.py:77` · `_NAMES = ["—", "VF", "VOSTFR",
  "VO", "Forcés", "Commentaires", "SDH"]` : noms de piste **proposés** au
  choix, puis **écrits dans le fichier** (`--track-name`, `title=`). Selon
  IE-71 point 5 ce sont des données : ils **ne passent pas** par le catalogue
  (un même fichier source doit donner la même sortie quelle que soit la
  langue de l'interface). Mais la liste est française par nature (« VF »,
  « VOSTFR », « Forcés ») : un utilisateur anglais voudra « Forced »,
  « Commentary ». Décision à prendre : liste dans `config.toml` (réglage,
  pas traduction), ou liste par langue **de la piste**. À trancher, pas à
  extraire. → IE-71 (complément), IE-92.
- **L-78** · C2 · `tui/screens/sync.py:614-620` · `_note_propagation` : trois
  accords à la main (« sous-titre(s) », « recalé(s) ») — cas d'école
  `ngettext` (L-41). `:990` `" et ".join(timecodes)` : conjonction française
  dans le code → fonction de liste traduite (L-42). → IE-88.
- **L-79** · C6/C3 · `tui/screens/sync.py:55-62,121-142,268-281` ·
  `_FIELD_LABELS` (table de module, L-06) et en-têtes de colonnes **réécrits
  en dur** dans `add_column` au lieu de lire `_FIELD_LABELS` (« Décalage »,
  « Étirement », « Défaut », « Forcé » existent deux fois) ; planchers de
  contenu (`28`, `14`, `12`…) calés sur le français (L-10). Descriptions de
  `Binding` dupliquées (« Valeur suivante » ×3, `:102-104`) : même `msgid`,
  sans conséquence. Le reste : touches dans les messages (L-09 — « avec M »,
  « F3 », « F9 », « +/- ou ↵ »), `\n` en dur (`:1139,1147`, L-54), formats
  `ms`/`s` (IE-90). → IE-88.

### tui/screens/tracks.py

- **L-80** · C3/C6 · `tui/screens/tracks.py:67-68` · `SECTIONS` (tuple de
  module, en capitales) et `_W_IDX = max(10, len(...))` : largeur calculée **à
  l'import** sur les intitulés français, avec `len()`. Une fois traduits, il
  faut la recalculer après chargement de la langue, en `cell_len` (L-46).
  Capitales dans le `msgid` : L-52. → IE-88.
- **L-81** · C8 · `tui/screens/tracks.py:274-279,312-316` · raisons courtes
  « défaut », « sélectionné », « exclu manuellement » : « défaut » est
  **ambigu** (piste par défaut / anomalie) → `pgettext("track", "default")` ;
  « sélectionné » au masculin pour une piste (féminin) — le mot qualifie un
  état, pas la piste, mais le traducteur doit le savoir (commentaire).
  « exclu manuellement » existe aussi dans `core/decision.py:1023` (L-15) :
  une seule source. `"image"`/`"texte"`, `"→ copie MKV/MP4"` : L-13. → IE-88.
- **L-82** · C1 · `tui/screens/tracks.py:416-422,461` · `orig_lbl = ("⚠
  supprimer" | "○ garder") + " (profil)"` : suffixe collé ; et
  « ⚠ SUPPRIMER » / « ○ GARDER » en capitales pour la même idée que
  « supprimer » / « garder » en minuscules — quatre `msgid` pour deux mots,
  la casse devrait venir du code (`.upper()`) si elle porte un sens d'état
  forcé. `f"DV → {dv_lbl}"`, « ★ vidéo modifiée » : symboles hors `msgid`
  (L-64). → IE-88.

### tui/screens/value_picker.py

- RAS. Le picker rend un **index** (`dismiss(cursor_row)`), jamais le texte
  choisi : les options peuvent être traduites sans toucher à la logique —
  répond à la question laissée ouverte par L-44.

### tui/screens/wizard.py

- **L-83** · C3 · `tui/screens/wizard.py:255,264-268` · alignement **par
  espaces dans le texte** : « Profil actif   {id} », « Sortie   {nom} »,
  « Vidéo    {label} », puis la raison décalée de 11 espaces sous « Vidéo ».
  Les espaces supposent que « Sortie » et « Vidéo » ont la même longueur ;
  traduits (« Output », « Video »), la colonne se décale. Construire une
  grille clé/valeur (`Table.grid` de Rich) et mesurer les libellés traduits
  (`cell_len`). → IE-88.
- **L-84** · C1/C3 · `tui/screens/wizard.py:322,368-386,217,565-573` ·
  paragraphes avec retours à la ligne **en dur** et indentation de deux
  espaces dans le texte (L-54) ; « Les deux restent offerts : F3 muxer, F2
  encoder. » assemblé en cinq `append` pour styler les touches (L-57) ; notes
  de mesure bâties par `+` de morceaux optionnels (« , reporté sur {n}
  sous-titres », « — ⚠ {réserve} ») ; en-tête « Assistant · étape {i} sur
  {n} · … ». `:338-341` états de recalage (« non mesuré », « réglé à la
  main ») : choisis par `SyncOrigin` (enum), bien. → IE-88.

### main.py

- **L-85** · C6 · `main.py:25-110` · **ordre de démarrage** : la version de
  Python (`:31`), les dépendances (`:50`), l'aide `argparse` (`:78-89`),
  « Chemin introuvable » (`:95`), la bannière et « Vérification des outils : »
  (`:104-110`) s'affichent **avant** `cfg_mod.load()` (`:112`), donc avant
  que `[app] language` soit connue. IE-91 suppose que « la bannière de
  `main.py` et la sortie console du preflight tournent après le chargement
  de la langue » : c'est faux aujourd'hui pour la bannière. Choix à faire :
  charger la config (et la langue) juste après le contrôle des dépendances,
  ou classer ces messages-là avec les lanceurs (anglais seul, IE-91). Les
  deux premiers ne peuvent de toute façon pas dépendre de `config.toml`
  (dépendances manquantes = `tomli_w` absent) : **anglais seul**. Corrige
  aussi la remarque laissée ouverte par L-30 (le preflight, lui, tourne bien
  après `load()`). → IE-91, IE-86.
- **L-86** · C3 · `main.py:102-108` · cadre de bannière à largeur fixe
  (`inner = 43`) rempli par `:<{inner-2}` : un libellé d'environnement
  traduit plus long (« système » / « .venv local ») déborderait le cadre, et
  `ljust` compte en caractères (L-46). Calculer `inner` depuis le contenu.
  → IE-91.

### updater.py

- **L-87** · C5/C6 · `updater.py:166-170,296-315` · lancé par `launch.bat`
  (`:110`) **avant** l'application, comme les lanceurs. **Bon point** : la
  réponse accepte `o`, `oui`, `y`, `yes` (`:170`) — le modèle pour L-29.
  Rattachement à trancher : texte de lanceur (anglais seul, IE-91) ou
  catalogue (il peut lire `config.toml`, qu'il lit déjà pour `[updates]
  app`). Par cohérence avec L-85, **anglais seul** est le plus simple ; si
  catalogue, l'invite `[O/n]` doit suivre la langue (`[Y/n]`). Messages
  d'erreur (`:181-218`) : simples. → IE-91.

## Synthèse

52 fichiers audités, **82 constats** (L-06 à L-87). Aucun code modifié.
Constat d'ensemble : le code est **localisable sans refonte**. La logique
s'appuie presque partout sur des énumérations et des valeurs, pas sur des
libellés : `FileState`, `SyncOrigin`, couples (libellé, valeur) du
formulaire de profil, picker qui rend un index, filtres en couples. Le gros
du travail est de l'extraction mécanique. Quelques défauts sont à corriger
**avant** l'extraction, parce qu'ils cassent dès qu'un texte est traduit.

### 1. À corriger avant l'extraction (indépendant de la langue)

Défauts qui existent déjà ou qui casseront à la première traduction. Un
incrément chacun, comme UX-29.

| Constat | Quoi |
|---|---|
| L-43 | **Récidive d'UX-29** : couleur « HD audio » décidée sur `== "oui"` (`tui/common.py:486`) |
| L-23 | Couleur de la fiche décidée sur `confiance.startswith("incertaine")` |
| L-22 | `MovieMeta.kind` stocke un libellé français au lieu d'un code |
| L-68 | Raison affichant le nom d'énumération (`ENCODE_HEVC`) ; « dry-run » et « aperçu » pour le même écran |
| L-13, L-15, L-66, L-79, L-81 | Libellés recopiés à plusieurs endroits (« → copie », « exclu manuellement », types de piste, en-têtes) : une source chacun |
| L-14 | Libellé mort de `_resolve_limits` |
| L-56, L-70 | Incohérences déjà visibles : exemple « 13:22,5 » (virgule) quand l'appli écrit le point ; « BACKSPACE » en toutes lettres au lieu de « ⌫ » |
| — | Hors localisation, vu au passage : `tui/screens/run.py:807` écrit « 3/4 » en dur (à verser à IE-83) |

### 2. Socle à fournir par IE-86

- `N_()` pour marquer les textes des tables de module, traduits au rendu
  (L-06 ; concerne aussi `BINDINGS`, L-39).
- Remplaçant de `core/texte.py` adossé à `ngettext` : phrase entière avec
  `{count}`, plus aucun mot accordé seul (L-37, L-20).
- Convention pour les exceptions qui portent un texte affiché (L-18).
- Helper « gabarit traduit → `Text` stylé » (marqueurs remplacés par des
  segments stylés), pour les touches et valeurs en gras sans couper la phrase
  ni mettre de markup dans le `msgid` (L-57, L-65).
- Fonction de liste traduite (« a, b et c ») (L-42, L-78).
- Mesure de largeur en `cell_len` partout (L-46, L-50, L-54, L-80, L-86).
- **Règles d'écriture** à joindre à IE-111 point 5 : hors `msgid` — puces et
  symboles (`✓ ✗ ⚠ ▶ ★ ──`), indentation, retours à la ligne de mise en
  page, capitales décoratives, markup Rich, compteurs d'étape (L-30, L-52,
  L-54, L-64, L-65, L-73) ; touches et libellés cités en paramètres (L-09,
  L-26, L-55).

### 3. Extraction `core/` — IE-87

L-06, L-07, L-08, L-11, L-12, L-16, L-17, L-18, L-20, L-21, L-24, L-26,
L-27, L-28, L-31, L-32, L-33, L-34, L-35, L-36, L-38. Points saillants :
raisons de décision assemblées (L-11, L-12), niveaux de confiance accordés
au féminin (L-33), doublons de messages de refus dans `sync.py` (L-35).

### 4. Extraction `tui/` — IE-88

L-10, L-39, L-40, L-41, L-42, L-44, L-45, L-48, L-50, L-51, L-52, L-57,
L-58, L-59, L-60, L-62, L-63, L-64, L-65, L-66, L-69, L-70, L-71, L-72,
L-74, L-75, L-76, L-78, L-79, L-80, L-81, L-82, L-83, L-84. Points
saillants : descriptions de `Binding` évaluées à l'import (L-39),
alignements faits avec des espaces (L-83), planchers de colonnes calés sur
le français (L-10, L-80).

### 5. Guide embarqué — IE-89

L-53 (tables d'explications et titres d'écrans), L-54 (repli manuel en
`len()`, `
` en dur), L-55 (libellés et touches cités).

### 6. Formats — IE-90 (à ajouter à sa liste)

Débits `k`/`kbps` (L-12, L-47), `ms`/`s` (L-19, L-25, L-36), pourcentages
avec et sans espace (L-67), heure `%X` (L-49), date de remise du quota
(L-27), note `x.x / 10` (L-71), progression (L-74), exemple de saisie
(L-56), mesures du rapport de recalage (L-34).

### 7. Console — IE-91

L-29 (lettre de réponse `o` testée en dur), L-30 (preflight), L-85 (la
bannière et les premiers messages de `main.py` s'affichent **avant** que la
langue soit connue — l'hypothèse d'IE-91 ne tient pas), L-86 (cadre à
largeur fixe), L-87 (`updater.py`).

### 8. Glossaire — IE-85

Termes à trancher : « SKIP » (L-13), « lossless »/« copy » dans les raisons
(L-11), « Release » (L-72), sigle « SME » (L-72), « aperçu » contre
« dry-run » (L-68), codes `HDR`/`SDR`/`DV:P8.1` gardés comme termes (L-61).

### 9. Tests — IE-94

`_(f"…")` interdit (L-07) ; troncature vérifiée dans chaque langue (L-10) ;
aucune comparaison à un littéral affiché (L-23, L-43) ; libellés cités par
le guide présents au catalogue (L-55) ; modales sur captures anglaises
(L-64).

### 10. Décisions (tranchées le 2026-10-04)

- **L-77** — noms de piste proposés au recalage : la liste proposée dépend de la **langue de la piste** (champ Langue, déjà
  saisi au recalage) : `fre` → « VF », « VFF », « VFQ », « VOSTFR », « Forcés »,
  « Commentaires », « SDH » ; `eng` → « English », « Forced », « Commentary »,
  « SDH » ; autre langue → liste neutre (« Forced », « SDH »). Ces noms sont
  écrits dans le fichier : table de **données** par code de langue, jamais
  le catalogue — même source, même sortie, quelle que soit l'interface.
- **L-85 / L-87** — **anglais seul**, sans catalogue, comme les lanceurs : bannière et
  messages de `main.py` antérieurs à `cfg_mod.load()`, et tout `updater.py`.
  L'invite d'`updater.py` devient `[Y/n]` et garde l'acceptation de
  `o`/`oui`/`y`/`yes`. Le preflight, lancé après `load()`, passe par le
  catalogue ; sa lettre de réponse suit L-29.
- **L-18** — exceptions affichées : tranché par IRIS (délégué) : **l'erreur porte un identifiant de
  message et ses paramètres, l'écran traduit**. Une classe unique, p. ex.
  `ErreurAffichable(msgid, **params)` dans le module i18n : `msgid` marqué
  `N_()` (texte source anglais), `str(e)` rend l'anglais formaté — c'est ce
  qu'écrit le journal, qui reste hors catalogue (IE-71 point 5) —, et
  `e.message()` rend `_(msgid).format(**params)` pour l'interface. Raisons :
  les journaux restent dans une langue stable quel que soit le réglage ;
  aucun texte traduit ne naît dans un thread de travail ; les tests
  comparent un `msgid`, pas une phrase ; l'extraction voit chaque message
  grâce à `N_()`. Les écrans qui affichent `str(e)` aujourd'hui (`run.py`,
  `join.py`, `mux_run.py`, `meta_popup.py`…) passent à `e.message()` ; une
  exception étrangère (OSError, requests) reste affichée telle quelle,
  derrière un gabarit traduit (« Lecture impossible : {detail} »).
