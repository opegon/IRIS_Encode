# CHANGELOG — IRIS ENCODE

## [v0.8.6.1] — 2026-08-29

### `GUIDE.md` remis à jour, et rattaché au code

Le guide d'utilisation était resté en **0.8.1.23** — quinze incréments en
arrière. Assez pour qu'on ne sache plus ce qu'il décrit.

**Une erreur réelle trouvée en le relisant** : il annonçait `` `Tab` `<` `>` |
Choisir une colonne, l'élargir, la rétrécir ``, ce qui donne `<` pour élargir.
C'est l'inverse. `Maj+Tab`, qui remonte d'une colonne, n'était pas mentionné
non plus.

Ce que la revue a changé pour l'utilisateur y entre :

- **§ 2.1** — l'application masque du navigateur ce qu'elle a encodé
  (`_[hevc]`, `_[H264]`, `_[av1]`, `_[hdr10]`), et laisse `_[mux]` visible.
  Un fichier qui « manque » après un encodage, c'est cela.
- **§ 4.2bis** — le nouveau cas « ⚠ … → durées écartées de N % », ce qu'il
  veut dire et comment trancher.
- **§ 4.5** — le message « point d'insertion en retrait », et l'avertissement
  sur les pistes produites par `P` avant la v0.8.4.5, qui peuvent porter un
  passage en double.
- **§ 4.6** — les greffes étirées faites avant la v0.8.4.3 peuvent avoir perdu
  leur piste : à refaire.
- **§ 4.12** — « libx265 indisponible ici » sur `cinema_4k_quality`, pourquoi
  c'était le cas sur toute machine à carte graphique, et comment distinguer le
  défaut corrigé d'un ffmpeg réellement construit sans libx265.
- **§ 5** — comment couper la vérification des mises à jour au lancement, et
  depuis quand ce réglage fonctionne.

### Quatre tests rattachent le guide au code

`tests/test_aide.py` tenait déjà le guide **embarqué**, qui dérive des
`BINDINGS`. `GUIDE.md` est écrit à la main, et rien ne le rattachait : c'est
ce qui lui a permis de dériver quinze versions durant.

- Toute touche annoncée par une table du guide doit exister dans les
  `BINDINGS` de l'écran concerné, mixins compris. Vérifié : le test attrape
  bien une touche fantôme.
- L'en-tête du guide doit porter la version de `version.py` (règle 5.4).
- Un troisième test vérifie que l'extracteur trouve encore des touches à
  contrôler — un balayage devenu muet passerait au vert en silence.

Le périmètre est étroit à dessein : ces tests ne jugent pas une explication,
qui est du texte. Ils attrapent la promesse d'un geste qui ne répond plus.

**778 tests.**

## [v0.8.6.0] — 2026-08-29

**Release.** Rassemble 0.8.5.1 à 0.8.5.3 — les neuf dernières entrées de la
revue de `core/`. **Elle est close** : les quinze constats sont traités.

Comme pour la v0.8.5.0, aucun de ces défauts ne levait d'erreur, et les tests
d'alors passaient tous.

- **Tous les profils de l'utilisateur pouvaient disparaître** (IE-50) — une
  écriture tronquée de `profiles.toml`, et `load_all` ne rendait plus que les
  profils livrés. Sans recours, et un redémarrage n'y changeait rien.
- **L'application reproposait ses propres sorties au réencodage** (IE-49) — un
  `_[av1]` reparu au scan, un codec que la chaîne ne lit pas, et une décision
  qui propose de le réencoder en HEVC. Sur `basic_delete`, en effaçant
  l'original.
- **Une mesure acceptée pouvait porter une réserve que personne ne voyait**
  (IE-52) — un donneur d'un autre montage passait en silence.
- **Un réglage mort** (IE-51) — couper la vérification des mises à jour ne la
  coupait pas.
- **Une mise à jour ne rangeait pas comme une installation** (IE-54) — dovi_tool
  publié en binaire nu échouait à chaque lancement, quand une installation
  neuve de la même release réussissait.
- **Le genre AlloCiné tronqué à cinq caractères** (IE-53).
- **Trois coûts** : dix sous-processus en série au démarrage (IE-56),
  vingt-six `mkvmerge` pour un seul remux (IE-55), un prédicat écrit deux fois
  qui pouvait désynchroniser l'encodeur et l'accélération matérielle (IE-57).

### Ce que la revue a appris

**Trois des quinze défauts étaient la récidive d'une correction déjà faite
ailleurs dans le dépôt** — IE-50 pour IE-39, IE-54 pour IE-40, IE-58 pour la
disposition que trois lanceurs sur seize appliquaient déjà. À chaque fois le
correctif existait, à côté, et personne n'avait cherché les autres occurrences
de la même forme.

C'est pourquoi cinq tests de cette revue sont **structurels** plutôt que
comportementaux : ils lisent le source et refusent une forme, là où un test
d'exécution n'aurait couvert qu'un chemin. Aucun lancement de sous-processus ne
garde l'entrée du terminal ; aucun suffixe de sortie n'est écrit en dur dans un
filtre ; le sondage des encodeurs couvre ce que la commande peut demander ; le
prédicat HDR10 n'existe qu'en un exemplaire ; la ligne de touches ne s'efface
jamais.

**771 tests** — 677 au début de la revue, soit 94 de plus.

## [v0.8.5.3] — 2026-08-29

Les trois dernières entrées de la revue de `core/`. **Elle est close** : les
quinze constats sont traités.

### Le genre AlloCiné était tronqué à cinq caractères (IE-53)

`data.get("genre", [])[:5]` s'appliquait **avant** l'`isinstance(genres, str)`
qui suit. AlloCiné rend une chaîne nue quand le film n'a qu'un genre :
« Science fiction »[:5] vaut « Scien », que la normalisation emballe ensuite
consciencieusement en `["Scien"]`.

Le casting, dix lignes plus haut dans la même fonction, faisait déjà les deux
dans le bon ordre. La limite à cinq reste : elle existe pour l'affichage, et
réparer l'ordre ne devait pas la lever.

### Vingt-six processus mkvmerge pour un seul remux (IE-55)

`build_strip_command` traduit un index par piste retenue, et chaque traduction
relançait `mkvmerge -J` : six pistes audio et vingt sous-titres coûtaient
26 sous-processus — timeout de 30 s chacun — sur le même fichier, qui ne change
pas entre deux. `encoder.build_command` en relançait un par piste externe.

- `identify()` mémorise son résultat, **par état de fichier** : la clé porte le
  chemin, la taille et la date de modification. Un donneur remplacé entre deux
  passages est relu au lieu d'être servi depuis un cache qui ne le décrit plus.
  Un `stat()` contre un sous-processus, le compte est vite fait.
- Un résultat **vide** n'est pas mémorisé : c'est aussi ce que rend un mkvmerge
  absent, et l'installer en cours de session doit suffire.
- `set_mkvmerge_path()` vide le cache : ce qu'il contient a été lu par
  l'exécutable précédent.
- Le résultat est rendu en copie, pour qu'un appelant ne puisse pas vider le
  cache par inadvertance.

### Le prédicat du mode HDR10 « quality » était écrit deux fois (IE-57)

`hdr10_quality_check` et `hdr10_quality` étaient la même expression à trois
termes, mot pour mot, dans la même fonction, sans que rien entre les deux ne
change leurs entrées. Un seul nom désormais.

Ce prédicat décide **deux choses à la fois** : l'encodeur (`libx265`) et
l'absence de `-hwaccel`. Les modifier séparément aurait passé `-hwaccel` à un
encodage processeur, ou l'aurait retiré à un NVENC. Deux tests verrouillent la
bascule conjointe, un troisième refuse que l'expression réapparaisse en double.

**771 tests** (contre 757), dont quatre échouent sur le code d'avant.

## [v0.8.5.2] — 2026-08-29

Les trois entrées de `core/preflight.py`, prises d'un bloc : elles vivent dans
le même fichier et deux d'entre elles touchent le même chemin.

### `check_on_startup` était lu dans la mauvaise section (IE-51)

`check_for_updates` interrogeait `cfg["ffmpeg"]["check_on_startup"]`, alors que
la clé vit sous `[updates]` — c'est là que `config._DEFAULTS` la pose, là que
`config.toml` l'écrit, et là que la spec la documente. Le `.get(..., True)`
retombait donc toujours sur le défaut : le réglage était mort, et l'utilisateur
qui coupait la vérification pour éviter l'aller-retour réseau au lancement
continuait de le payer à chaque démarrage.

### Une mise à jour ne rangeait pas comme une installation (IE-54)

`_installer_for` appelait `_install_from_zip` en direct, sautant
`install_dovi_tool` et son `zipfile.is_zipfile` — le garde-fou posé par IE-40
précisément parce que « certaines releases publient un ZIP, d'autres
l'exécutable nu ». Sur une release en binaire nu, la mise à jour échouait à
chaque lancement (`BadZipFile`, « Mise à jour de dovi_tool échouée ») pendant
qu'une installation neuve de la même release réussissait.

- **`preflight.poser()`** est désormais le point de passage unique : il sait
  sous quelle forme chaque outil publie, et l'installation initiale comme la
  mise à jour l'appellent. Un test vérifie l'invariant plutôt que le symptôme —
  un même contenu doit donner le même résultat par les deux chemins.
- Les lambdas d'avant transformaient aussi un `_download` échoué en `b""`,
  remis à un extracteur qui n'avait plus qu'à échouer sur une archive vide, en
  nommant la mauvaise cause. Le téléchargement raté est maintenant un refus net.
- **Sur l'empreinte** : ce chemin ne vérifie aucun sha256, et il n'y en a pas à
  vérifier. `Update` n'en porte pas, parce que l'URL vient d'une découverte
  dynamique et non d'une source épinglée — c'est la limite que `_download`
  documente déjà. Rien à corriger ici, contrairement à ce que la revue laissait
  entendre.

### Le relevé des versions bloquait le démarrage (IE-56)

`check_tools` appelait `_get_version` sur les cinq outils l'un après l'autre, et
`_get_version` essaie `-version` puis `--version` avec 5 s de délai chacun.
mkvmerge et dovi_tool échouent sur le premier : jusqu'à dix lancements de
sous-processus en série — et `check_tools` repasse une seconde fois après une
installation de ffmpeg.

`platform.sonder_encodeurs`, juste à côté, énonce la position du projet — « les
sondages tournent en parallèle pour que le lancement n'en pâtisse pas » — et
emploie un `ThreadPoolExecutor` pour exactement ça. Le relevé des versions
l'emploie désormais aussi ; la localisation reste séquentielle, elle ne coûte
qu'un parcours du PATH.

**757 tests** (contre 742), dont quatre échouent sur le code d'avant.

## [v0.8.5.1] — 2026-08-29

Trois entrées de la revue de `core/`, prises par ordre de ce que l'utilisateur
perd : d'abord l'irrécupérable.

### `profiles.toml` pouvait emporter tous les profils de l'utilisateur (IE-50)

`save_all` et `_write_defaults` ouvraient le fichier en `"wb"` : **tronquer,
puis écrire**. Une coupure à mi-course laisse un TOML invalide ; `load_all`
avale l'erreur de syntaxe, affiche un avertissement et rend les seuls profils
livrés. Tout ce que l'utilisateur a créé ou modifié est perdu, sans recours, et
un redémarrage n'y change rien.

C'est mot pour mot IE-39, corrigé en v0.8.3.12 pour `config.toml` et jamais
porté ici — alors que ce fichier-là pèse plus lourd : une configuration se
refait en trois réglages, une bibliothèque de profils non.

- Écriture dans un provisoire, `flush` + `fsync`, puis `os.replace` — atomique
  sur NTFS comme sur POSIX. Le provisoire est retiré si quoi que ce soit échoue.
- Un verrou de module, comme `config.save` : deux écrans peuvent enregistrer.
- Les tests sont ceux d'IE-39, repris à la lettre : le défaut est le même, il
  doit se vérifier de la même façon aux deux endroits.

### L'application proposait de réencoder ses propres sorties (IE-49)

Le filtre « déjà produit ici » connaissait deux littéraux, `_[hevc]` et
`_[H264]`, **recopiés à quatre endroits** sans jamais dériver de
`SUFFIX_BY_ACTION`. L'application a depuis appris à écrire `_[av1]` et
`_[hdr10]`, et aucune des quatre copies n'a suivi.

Le cas coûteux est l'AV1 : ce codec n'est pas dans `CODECS_LISIBLES`, donc un
`Film_[av1].mkv` reparu au scan fait tomber la décision en CAS 3 — « codec non
lu par la chaîne » — qui propose de le réencoder en HEVC. Sur le profil livré
`basic_delete`, qui a `delete_source = true`, l'AV1 est effacé au passage :
perte de génération irréversible sur un fichier que personne n'a demandé à
retoucher.

- Un seul prédicat, `scanner.deja_produit()`, dérivé de `SUFFIX_BY_ACTION` :
  ajouter un codec au projet suffit désormais, le filtre suit.
- **`MUX_SUFFIX` en est volontairement absent**, contrairement à ce que
  proposait la revue. Un `_[mux]` n'est pas un encodage mais une greffe de
  pistes, et l'encoder ensuite est un geste légitime — l'écarter du scan
  rendrait le fichier invisible dans le navigateur. La spec § 15.2 l'affirmait
  pourtant exclu ; elle avait tort, et elle est corrigée.
- Un test refuse tout nouveau littéral `_[hevc]`/`_[H264]` dans ces filtres :
  le défaut n'était pas la valeur, c'étaient les quatre copies.

### Une mesure acceptée pouvait porter une réserve que personne ne voyait (IE-52)

`measure_audio` écrivait « durées écartées de N % — vérifiez qu'il s'agit bien
du même montage » dans `reason`, **alors que `ok` est vrai**. Or `reason` n'est
lu que sur les échecs : `label()` ne le regarde que dans sa branche
`if not self.ok`, `report()` n'y touche pas, l'assistant non plus.

Un donneur dont la durée s'écarte de plus de 6 % — donc un autre montage — était
donc accepté sans que rien ne le signale nulle part.

- Un champ `warning` distinct, porté par le compte rendu de l'écran de recalage
  et par la note de l'assistant. Un succès sous réserve s'affiche `⚠`, plus `✓`.
- `reason` garde son seul rôle : dire pourquoi une mesure a été refusée.

**742 tests** (contre 721), dont treize échouent sur le code d'avant.

## [v0.8.5.0] — 2026-08-29

**Release.** Rassemble les six incréments 0.8.4.3 à 0.8.4.8, tous issus d'une
revue `max` des 6 082 lignes de `core/` — ou de sa clôture.

Aucun de ces défauts ne levait d'erreur. Trois produisaient un fichier ou une
configuration faux en silence, deux bloquaient ou refusaient une opération
valide, un rendait une fonction réelle invisible. Les 677 tests d'alors
passaient tous : ce sont des trous de couverture, pas des régressions.

- **La piste greffée disparaissait après un mux préalable** (IE-43) — succès
  affiché, code de retour nul, fichier sans la VF qu'on venait de recaler.
- **`_deep_merge` partageait encore la moitié de ses branches** (IE-44) — la
  v0.8.1.5 n'avait corrigé qu'un sens ; un `config.toml` sans `[tui]` faisait
  planter l'ouverture du navigateur.
- **`cinema_4k_quality` refusé sur toute machine à carte graphique** (IE-45) —
  `libx265` n'était pas sondé, et « jamais sondé » valait « indisponible ».
- **`retime_audio` se bloquait pour de bon** (IE-46) — deux tubes dont un seul
  lu ; passé 64 Ko, ffmpeg reste suspendu sur son écriture.
- **Le donneur sortait en double** (IE-47) — deux points d'insertion qui se
  croisent donnent un `atrim` à l'envers, et le segment déjà écrit repart dans
  le suivant.
- **Le forçage à 48 kHz de l'AAC visait le mauvais flux** (IE-48) — un
  spécificateur nu, qui glissait d'un cran dès que la vidéo était mappée en
  tête.
- **Treize sous-processus se disputaient le clavier avec l'interface** (IE-58,
  hors revue, sorti de la clôture d'IE-46) — un `q` de passage tuait
  l'encodage.
- **Les touches qui modifient une valeur étaient les seules invisibles**
  (IE-36) — le pied de page ne les porte pas, et le bandeau les cédait à ses
  messages exactement quand elles servent.

Deux de ces défauts sont la récidive d'une correction déjà faite ailleurs et
jamais portée aux autres appels de la même forme — IE-50, encore ouverte, est
du même genre. Trois tests structurels ferment cette famille : le sondage des
encodeurs doit couvrir ce que la commande demande, aucun lancement ne garde
l'entrée du terminal, et la ligne de touches ne s'efface jamais.

**721 tests** (contre 677), dont vingt-trois échouent sur le code d'avant et
deux suspendent la suite. Smoke TUI vert, 28 captures.

## [v0.8.4.8] — 2026-08-29

### Les touches qui modifient étaient les seules que l'écran ne montrait pas (IE-36)

Signalé comme une fonction manquante : « il n'existe pas de recalage manuel de
la piste audio comme pour les sous-titres ». **Il existe** — le champ `Décalage`
de l'écran de recalage s'édite pour n'importe quelle piste, audio comprise, avec
trois pas et une liste de valeurs. Ce qui manquait, c'est sa trace à l'écran.

Deux surfaces auraient pu la porter, aucune ne le faisait :

- le **pied de page** dérive des `BINDINGS` (IE-30), et `←/→`, `+/-`,
  `Shift+↑/↓`, `Ctrl+↑/↓` y sont tous `show=False` faute de place. Les touches
  qui modifient sont exactement celles que le pied ne montre pas ;
- le **bandeau** les portait, mais dans le même emplacement que ses messages.
  Un avertissement de langue les chassait à l'arrivée sur l'écran — c'est l'état
  d'ouverture quand une piste n'a pas de langue — et un compte rendu de mesure
  les chassait juste après une mesure. Il ne restait que l'état où toutes les
  pistes ont leur langue et où rien n'a été mesuré : celui où il n'y a rien à
  régler.

Les prises de vue le confirment : ni `12-sync` ni `12b-sync-mesure` ne portait
une seule touche d'édition.

- **Le bandeau porte désormais deux choses séparées.** Première ligne : ce que
  sait faire le champ sous le curseur, qui ne s'efface jamais. Lignes suivantes :
  le message du moment. La boîte passe de quatre à cinq lignes — un refus de
  mesure en occupe trois, et les tronquer serait revenir au défaut d'IE-32.
- **La ligne est propre au champ.** Seul le décalage a trois pas ; sur les
  autres, `_change` ignore le pas et fait défiler les valeurs. Y annoncer
  « ±10 ms » enverrait chercher un réglage qui n'existe pas.
- `_set_hint` passe par la même recomposition : il écrivait directement dans le
  bandeau, ce qui aurait effacé la ligne du champ.
- **Seize tests**, dont quatre montent l'écran et relèvent le bandeau dans les
  trois états qui comptent — arrivée, après mesure, après navigation.

**Documentation** — `Ctrl+↑/↓` (livré en v0.8.3.9) et `R` (v0.8.3.x) manquaient
aux tables de touches de la spec § 14.4 et du guide § 2.4. Les deux y entrent.

**Hors périmètre, tel qu'arbitré** : le point de repère `R` reste réservé aux
sous-titres. Sur une piste audio l'application n'a aucune réplique à proposer ;
il faudrait deux instants saisis à la main, ce qui est une autre fonction que
celle-ci.

## [v0.8.4.7] — 2026-08-29

### Le forçage à 48 kHz de l'AAC tombait sur le mauvais flux (IE-48)

`audio_args` écrivait `-ar:{i}` — un spécificateur de flux **nu**, qui désigne
le flux de sortie n° i tous types confondus. Toutes les options voisines
(`-c:a:{i}`, `-b:a:{i}`, `-ac:a:{i}`) désignent au contraire la i-ème piste
audio.

`build_command` et `build_strip_remux_mp4` mappent la vidéo en premier : le flux
0 y est donc la vidéo. `-ar:0` tombait dessus et était ignoré, `-ar:1` tombait
sur la première piste audio alors qu'il avait été écrit pour la seconde. Le
réglage glissait d'un cran, et la piste AAC qui l'avait demandé ne le recevait
jamais. Aucun avertissement : une option audio posée sur un flux vidéo est
simplement inutilisée.

- `-ar:a:{i}`, la forme par type, correcte quel que soit l'ordre des `-map`.
  Un seul endroit à corriger : les trois chemins partagent `audio_args`.
- **Quatre tests**, un par contexte, tous en échec sur le code d'avant.

Le défaut était invisible sur le troisième chemin : `build_audio_command`
n'écrit que de l'audio (`-vn -sn -dn`), le flux 0 y **est** la piste 0, et la
forme nue s'y trouvait juste par accident. Une suite qui n'aurait couvert que
celui-là serait restée verte sur les trois — c'est la raison pour laquelle il a
son propre test.

## [v0.8.4.6] — 2026-08-29

### Treize sous-processus se disputaient le clavier avec l'interface (IE-58)

Relevé en clôturant IE-46, où seul `retime_audio` était en cause. Le balayage
des seize lancements du projet en a trouvé **treize** sans `stdin` redirigé :
tous héritaient de l'entrée du terminal, que l'interface Textual est en train
d'écouter.

ffmpeg lit `stdin` pour son clavier interactif — `q` l'arrête, `+`/`-` changent
sa verbosité. Deux lecteurs sur la même entrée se partagent les octets au
hasard : une frappe attrapée par ffmpeg ne parvient jamais à l'écran, et un `q`
de passage tue le décodage ou l'encodage en cours. Les fenêtres sont larges —
un décodage d'enveloppe dure plusieurs minutes, un `remove_dv` jusqu'à trente.

- **`stdin=subprocess.DEVNULL` sur les seize lancements**, ffmpeg, ffprobe,
  dovi_tool, mkvmerge, nvidia-smi et tar compris. La règle vaut aussi pour les
  outils qui ne lisent pas l'entrée aujourd'hui : aucun n'en a besoin, et c'est
  ce qui la rend vérifiable — donc tenable.
- **Un test structurel** parcourt `core/` et `tui/` en AST et refuse tout
  `subprocess.run` ou `subprocess.Popen` sans `stdin=`. Le défaut n'est pas dans
  un chemin d'exécution, il est dans ce qu'un appel **omet** : seule une lecture
  du source le voit. Deux tests l'accompagnent pour vérifier qu'il ne passe pas
  sur du vide — un fichier fautif fabriqué doit le faire échouer, et le balayage
  doit continuer de voir les seize lancements.

`EncoderProcess`, `MuxProcess` et `preview.launch` fermaient déjà `stdin` : les
trois endroits où quelqu'un s'était posé la question.

## [v0.8.4.5] — 2026-08-29

### Points d'insertion non croissants : le donneur sortait en double (IE-47)

`build_retime_command` découpe le donneur en
`atrim=start=précédente:end=celle-ci`. Une position en retrait sur la
précédente rend donc un `atrim` **dont la fin précède le début** : l'étage sort
un segment vide, et le morceau compris entre les deux positions — déjà écrit par
le segment d'avant — repart dans le suivant. Il se retrouve deux fois dans la
piste produite.

Rien n'empêchait le cas. Chaque frontière cherche son silence pour elle dans
±15 s (`CUT_SEARCH_S`), `find_silence` recule encore de la moitié de l'insert
pour le centrer, et le centre lui-même — `end_s − delay_ms` — recule dès que le
saut dépasse l'écart entre deux bascules : deux plages à 4 s d'écart séparées
par un saut de 6 s suffisent, sans qu'aucun silence n'y soit pour rien.

La piste fausse passait le code retour de ffmpeg **et** le contrôle de taille de
`retime_audio`, puis se greffait comme correcte.

- `plan_inserts` **impose la croissance** : une position en retrait est
  repoussée d'un bin sur la précédente, et la correction est signalée dans les
  réserves comme l'est déjà une frontière posée sans silence. Les durées ne
  bougent pas — on repousse le point, on n'ampute rien, ce qui garde
  l'invariant du mode : allonger n'efface jamais de contenu.
- Une position nulle est écartée par la même règle : elle rendait déjà un
  premier segment `atrim=0:0` vide.
- `build_retime_command` **refuse** un plan non croissant au lieu de fabriquer
  la commande. `plan_inserts` l'assure ; le vérifier rend l'invariant explicite,
  et rien en aval ne rattraperait un `atrim` à l'envers.
- **Six tests**, dont quatre échouent sur le code d'avant.

## [v0.8.4.4] — 2026-08-29

### `retime_audio` se bloquait quand ffmpeg remplissait le tube d'erreur (IE-46)

`stdout` et `stderr` étaient deux tubes distincts, dont un seul était lu au fil
de l'eau : `proc.stderr.read()` n'arrivait qu'après `proc.wait()`. Passé les
~64 Ko de tampon du second, ffmpeg se bloque sur son écriture — il ne sort
jamais, `stdout` n'atteint jamais sa fin, et la boucle de lecture ne rend jamais
la main.

Le graphe monté par `build_retime_command` aligne `2N+1` étages `atrim`/`asetpts`
devant un `concat` : exactement la forme qui produit un diagnostic par étage.
Vu de l'utilisateur, la barre d'avancement se fige pour de bon, sans qu'aucune
erreur ne remonte et sans autre issue que de tuer l'application.

- **Un seul tube**, `stderr=subprocess.STDOUT` — la disposition qu'emploie déjà
  `muxer.MuxProcess`. Les lignes en `clé=valeur` sont l'avancement de
  `-progress`, les autres sont gardées comme journal d'erreur, bornées aux vingt
  dernières : un graphe en défaut peut en produire des centaines, et le message
  utile est le dernier.
- **Quatre tests**, dont deux **suspendent la suite** sur le code d'avant : ils
  substituent à ffmpeg un interpréteur Python qui écrit 300 Ko sur `stderr`, et
  bornent l'appel dans un thread — sans cette borne une régression ne ferait pas
  échouer la suite, elle la figerait, exactement comme l'utilisateur.

Les deux autres `Popen` de `core/` sont hors de cause : `_decode_envelope`
écarte `stderr` sur `DEVNULL`, `EncoderProcess` ne tube que `stderr`.

**Reste ouvert au même endroit** : `retime_audio` n'impose pas
`stdin=DEVNULL`, là où `EncoderProcess` et `MuxProcess` le font — ffmpeg hérite
donc de l'entrée du terminal. Constat séparé, non traité ici.

## [v0.8.4.3] — 2026-08-29

Trois défauts relevés par une revue de `core/`. Aucun ne lève d'erreur : deux
produisent un fichier ou une configuration faux en silence, le troisième refuse
un profil au nom d'une mesure qui n'a pas eu lieu.

### La piste greffée disparaissait après un mux préalable

Une piste étirée ne peut pas entrer par ffmpeg : mkvmerge la greffe d'abord vers
un intermédiaire, ffmpeg encode celui-ci. L'écran d'encodage vidait alors
`external_tracks` — à raison, ffmpeg ne doit pas rouvrir les donneurs — mais
`build_command` ne mappait plus que les pistes de la source. Les greffées, bien
présentes dans l'intermédiaire, n'étaient reprises nulle part.

ffmpeg ne s'en plaint pas : il encode ce qu'on lui demande, rend un code de
retour nul, et l'écran affiche un succès. L'utilisateur récupérait un fichier
sans la VF qu'il venait de mesurer et de recaler.

- Les pistes passent de `external_tracks` à **`FileDecision.premuxed_tracks`** :
  elles ne sont plus des entrées, mais elles restent à mapper.
- **`muxer.premux_track_order()`** donne l'ordre dans lequel mkvmerge les écrit
  — fichier par fichier, puis par tid croissant, et non dans l'ordre où elles
  ont été choisies. Prendre le second décalait chaque piste de son étiquette.
- Leur index part du nombre de pistes de la **source entière** : mkvmerge la
  recopie sans en écarter aucune, que la décision les garde toutes ou non.
- Langue, titre, drapeaux et `-c:a copy` s'appliquent comme pour une greffe
  directe — sans le `copy`, ffmpeg réencodait la piste dans le codec par défaut
  du conteneur.
- L'intermédiaire supprimé, les pistes **reviennent** dans `external_tracks` :
  un second essai sur la même décision doit repasser par le mux préalable.

### `_deep_merge` partageait encore la moitié de ses branches

La v0.8.1.5 avait corrigé `_deep_merge({}, _DEFAULTS)` — la machine **sans**
`config.toml`. L'autre sens restait entier : la récursion ne suivait
qu'`override`, si bien que `_deep_merge(_DEFAULTS, user)` rendait telles quelles
toutes les branches que le fichier utilisateur ne mentionne pas.

Un `config.toml` présent mais sans section `[tui]` donnait donc un `cfg` dont
`['tui']` **était** celui du module. Le premier `reset_browser_columns` y
supprimait les colonnes par défaut, et l'ouverture du browser mourait sur un
`KeyError: 'columns'`.

Les valeurs de `base` sont désormais recopiées par la même récursion que celles
d'`override`.

### `cinema_4k_quality` était refusé sur toute machine à carte graphique

Le mode HDR10 « quality » encode sur processeur avec `libx265` : les métadonnées
statiques qu'il injecte passent par `-x265-params`, que les encodeurs matériels
n'exposent pas. Mais le sondage du lancement n'essayait que les trois encodeurs
de la plateforme, et `peut_encoder` ne distingue pas « sondé et refusé » de
« jamais sondé » — les deux valent `False`. Le lancement refusait donc
l'encodage avec « libx265 indisponible ici », sur une machine où ffmpeg le
livre pourtant.

**`platform.encodeurs_a_sonder()`** énumère maintenant tout ce que
`build_command` peut choisir, `libx265` compris, et l'application sonde cette
liste-là. Un test relie les deux : ce que la commande demande, le sondage le
couvre.

## [v0.8.4.2] — 2026-08-29

### `bootstrap.ps1` échouait sur une installation neuve de Windows 11

Sur une machine vierge, l'installation s'arrêtait à la dernière étape :

```
error: Failed to inspect Python interpreter from provided path at `.venv\Scripts\python.exe`
  Caused by: Une stratégie de contrôle d'application a bloqué ce fichier. (os error 4551)
  Installation des dépendances impossible.
```

**Smart App Control**, actif par défaut sur une installation *propre* de
Windows 11 — jamais sur une machine mise à niveau, ce qui explique qu'aucun
poste de développement ne l'ait vu — refuse d'exécuter les binaires sans
réputation établie auprès de l'ISG.

Ce n'est pas la signature qui décide : le CPython téléchargé par `uv` n'est pas
signé non plus, et il s'exécute sans difficulté — il est assez répandu pour
avoir une réputation. Le fichier bloqué est le `python.exe` que **`uv venv`**
pose dans `Scripts\` : un trampoline que uv fabrique à la volée, avec le chemin
de sa cible embarqué dedans. Empreinte unique à chaque environnement, donc
réputation impossible à acquérir.

- **Le `.venv` est créé par le module `venv` de l'interpréteur**, et non plus
  par `uv venv`. Ce module copie le redirecteur livré dans la distribution
  (`Lib\venv\scripts\nt\python.exe`, 262 144 octets) — mêmes octets pour tout le
  monde, réputation acquise. Vérifié : le `python.exe` du `.venv` en est la
  copie exacte. `uv` garnit ensuite cet environnement comme avant, inchangé.
- **Le `.venv` est reconstruit de zéro** dès qu'on atteint l'étape 3, `-Force`
  ou non. On n'y arrive que s'il manquait ou était incomplet, et un
  environnement laissé à moitié construit se répare mal. C'est aussi ce qui
  répare les machines déjà touchées par le blocage.
- **`Test-EnvComplet` survit à un `python.exe` inexécutable.** Il lançait
  l'interpréteur sans filet : sur un `.venv` bloqué, le script mourait sur
  l'erreur PowerShell brute au lieu de constater l'environnement incomplet.
- **L'erreur 4551 est nommée et expliquée.** L'utilisateur recevait
  « Installation des dépendances impossible », qui ne lui apprenait rien. Le
  script reconnaît maintenant le blocage dans la sortie de la commande et
  indique les deux issues : installer Python depuis python.org (binaires signés
  PSF, `launch.bat` le retiendra), ou désactiver Smart App Control — en disant
  que cette désactivation est définitive.

**Le diagnostic porte sur le texte de l'erreur, pas sur l'état du registre.**
La première version de ce correctif interrogeait
`VerifiedAndReputablePolicyState` : elle annonçait Smart App Control sur une
machine en mode *évaluation*, où rien n'est bloqué, et l'aurait fait aussi bien
sur une panne réseau. Un message qui accuse le mauvais coupable coûte plus qu'il
ne rapporte.

Vérifié de bout en bout sur la machine cliente (blocage reproduit, correctif
validé) et par une installation complète depuis zéro sur poste de développement.


## [v0.8.4.1] — 2026-08-29

### Ménage du dépôt, devenu public

- **`CLAUDE.md`** — sorti du dépôt **et de son historique**. C'est un
  aide-mémoire local pour Claude Code, pas un document du produit : il restait à
  l'état v0.8.1.5 alors que le projet est en 0.8.4.x, renvoyait à un fichier
  n'existant que sur le poste de développement, et ses échappements markdown le
  rendaient illisible sur GitHub. Le fichier reste en place localement, ignoré.
- **`audit.md`** — retiré de l'arbre. Rapport d'audit de la v0.7, rédigé le
  10 juin 2026 pour un public non technique, devenu obsolète trois versions
  mineures plus tard.

**Pourquoi les deux ne sont pas traités pareil.** `CLAUDE.md` décrivait
faussement l'état courant du projet à qui le lisait : le laisser dans
l'historique d'un dépôt public n'apportait rien. `audit.md` est un **instantané
daté** — l'historique est exactement où ce genre de document doit vivre. L'en
effacer falsifierait le fait qu'un audit a bien eu lieu à cette date.

L'archive de la v0.8.4.0 contient encore `audit.md`, et c'est correct : elle
correspond à son tag, qui n'a pas bougé.

## [v0.8.4.0] — 2026-08-29

Release. Rassemble les six incréments depuis la v0.8.3.6, dont le détail suit
plus bas. Trois choses en ressortent.

### L'application embarque son guide

`H`, depuis n'importe quel écran, ouvre la liste de **toutes** les touches avec
ce que chacune fait — y compris celles qui ne s'affichent nulle part ailleurs.
L'en-tête le rappelle en haut à droite. La liste est **dérivée des `BINDINGS`** :
seules les explications sont rédigées, et attachées à une action plutôt qu'à une
touche. Un guide écrit à côté du code dériverait comme le pied de page avait
dérivé — en pire, puisqu'on le consulte justement quand on ne connaît pas la
réponse.

### Une piste alignée n'est plus refusée par la mesure

Le classement des ratios d'étirement se faisait à la saillance seule, qui n'est
pas comparable d'un ratio à l'autre. Sur *The Fall* S02E06, un ratio PAL
l'emportait à 160 secondes de la vérité, sur une corrélation de 0.26, pendant
que le vrai alignement — −10 ms, corrélation 0.83 — était écarté. La
corrélation choisit désormais le ratio.

Le réglage du décalage gagne au passage un **pas fin de 10 ms**
(`Ctrl+↑/↓`), pour finir d'approcher une valeur mesurée.

### Quatre défauts silencieux fermés

Revue de code complète de `core/` et `tui/`. Les quatre constats partageaient
un trait : aucun ne se signalait. Un décalage écrit sur la mauvaise piste, un
`config.toml` tronqué, un ZIP installé sous le nom d'un exécutable, un ffmpeg
mort dont l'enveloppe partielle passait pour le film entier.

Les correctifs sont couverts par douze tests dont **neuf échouent sur le code
d'avant**, mesuré en rejouant la suite contre l'ancien source.

---

**À l'installation** — rien n'a changé depuis la v0.8.3.6 : `launch.bat` installe
Python lui-même s'il n'en trouve pas (uv, un CPython, un `.venv`), sans droits
administrateur et sans rien écrire hors du dossier. La bannière nomme désormais
l'interpréteur retenu et son origine.

**677 tests**, smoke TUI de bout en bout, 28 captures d'écran.

## [v0.8.3.12] — 2026-08-29

Les quatre constats de la revue de code du 2026-08-29. Aucun ne se manifestait
par un message : c'est ce qu'ils ont en commun, et c'est ce qui les rendait
coûteux.

### IE-38 — La mesure vit sur la piste, plus sur son rang

Le worker de recalage emportait l'**index** de la piste et appliquait son
résultat à `self._tracks[i]` plusieurs minutes plus tard. Deux touches
n'étaient pas gardées pendant ce temps, alors que cinq autres l'étaient :

- **`D` retirait une piste** → les rangs glissaient. Trois pistes, mesure sur
  la deuxième, retrait de la première : le décalage s'écrivait sur la
  troisième, et `propager_recalage` le recopiait sur les sous-titres du
  **mauvais donneur**. La garde `0 ≤ i < len(...)` n'attrapait que le
  débordement, jamais le glissement.
- **`Backspace` quittait l'écran** → `dismiss` rendait la liste à l'écran des
  pistes, qui la tenait pour validée, et le worker continuait d'écrire dedans
  **après** cette validation.

La piste traverse désormais le worker, et `_rang()` la retrouve à l'arrivée —
par **identité**, pas par égalité : deux pistes du même fichier sont égales au
sens du dataclass, et comparer par égalité n'aurait fait que déplacer le
défaut. Si elle a disparu, le résultat est jeté. `_candidate` et `_segments`
suivent la même règle. Et le retour refuse pendant une mesure, comme les cinq
autres actions longues.

L'assistant gardait déjà toutes ses touches : le défaut était propre à l'écran
de recalage.

### IE-39 — `config.toml` : écriture atomique, et verrou entre threads

`save()` ouvrait en `"wb"` : **tronque, puis écrit**. Une coupure à mi-course
laissait un TOML invalide et l'application ne redémarrait plus — la famille de
la v0.8.1.4 par un autre chemin. On écrit désormais à côté, `fsync`, puis
`os.replace`, atomique sur NTFS comme sur POSIX.

Deux threads y écrivent : le worker d'encodage quand il enregistre une vitesse
mesurée, le thread d'interface quand une largeur de colonne change. Un verrou
module les sérialise.

### IE-40 — Le repli d'installation n'écrit plus un ZIP sous le nom d'un exe

L'extraction de `dovi_tool` était enveloppée d'un `except Exception: pass`, et
le repli « binaire direct » écrivait alors **les octets du ZIP** dans
`dovi_tool.exe` en annonçant « ✓ Installé ». Une erreur d'écriture pendant
l'extraction — disque plein, antivirus — produisait un exécutable corrompu
déclaré bon, dont le défaut ne se serait vu qu'au premier fichier Dolby Vision.

`zipfile.is_zipfile()` décide maintenant ce qu'est le contenu, et les erreurs
d'écriture remontent. Le repli garde sa raison d'être : certaines releases
publient l'exécutable nu.

### IE-41 — Un ffmpeg mort ne passe plus pour un film court

`_decode_envelope` appelait `proc.wait()` **sans regarder le code retour** :
fichier tronqué, ffmpeg tué, l'enveloppe partielle était rendue telle quelle et
la corrélation la prenait pour le film entier. Le recoupement par tiers
rattraperait une amputation grossière, pas quelques minutes.

Le code retour est vérifié, et un `try/except` tue le processus si la boucle
sort mal — un ffmpeg oublié décodait un film entier pour personne. L'`assert`
sur `proc.stdout` devient un vrai test : sous `python -O` il aurait disparu, et
le déréférencement aurait suivi.

### Vérification

`tests/test_revue_code.py` — douze tests, dont **neuf échouent sur le code
d'avant** (vérifié en rejouant la suite contre l'ancien source). Deux des trois
autres sont des non-régressions volontaires ; le troisième, le verrou entre
threads, passait au début sur le code défectueux — un `dump` réel dure quelques
microsecondes et huit threads peuvent se croiser sans se superposer. Une pause
rend désormais le chevauchement certain en l'absence de verrou.

677 tests, smoke TUI vert, et la mesure réelle sur *The Fall* rend toujours
−10 ms à confiance excellente.

## [v0.8.3.11] — 2026-08-29

### Le guide nomme les touches, le pied de page les abrège

`ENTER`, `BACKSPACE`, `SHIFT+TAB`, `ESPACE`, `CTRL+HAUT` — en toutes lettres et
en capitales, là où le guide affichait `↵`, `⌫`, `⇧Tab`, `␣`, `Ctrl+↑`.

Les deux endroits n'ont pas la même contrainte. Le pied de page tient en trois
lignes : un glyphe y vaut une colonne, et c'est ce qui décide. Le guide a de la
place et le devoir inverse — « ⇧Tab » se devine, « SHIFT+TAB » se lit. Un glyphe
se cherche sur le clavier, un nom s'y trouve, et on ouvre le guide justement
parce qu'on cherche.

Les capitales suivent `raccourcis()`, qui les impose déjà dans les bandeaux : une
touche s'écrit partout de la même façon. Elles détachent aussi le nom de son
explication, ce qui compte dans une colonne de quarante lignes.

`TOUCHES_LONGUES` ne couvre que les touches dont la forme courte est un symbole ;
les autres — TAB, HOME, F1, CTRL+D — étaient déjà écrites, et `touche_longue`
retombe sur `TOUCHES`. Deux tests tiennent la règle : aucun glyphe dans la
colonne des touches, et toutes en capitales.

## [v0.8.3.10] — 2026-08-29

### Le guide d'utilisation entre dans l'application

`H` ouvre, depuis n'importe quel écran, la liste de **toutes** les touches avec
ce que chacune fait. L'en-tête le rappelle en haut à droite : « H Aide », le seul
endroit visible depuis tous les écrans, y compris ceux dont le pied de page est
déjà plein.

**La liste est dérivée des `BINDINGS`.** Seules les explications sont rédigées, et
elles sont attachées à une *action* (`measure`, `apply_segments`…), pas à une
touche : une touche qu'on déplace emporte son explication avec elle.

C'est la leçon d'IE-30 appliquée au guide. Un pied de page écrit à côté des
`BINDINGS` avait fini par ne plus les décrire, sans que personne le voie. Un
guide dériverait de la même façon, en pire : on le consulte précisément parce
qu'on ne connaît pas la réponse, donc on n'est pas en position de repérer
qu'elle est fausse.

`tests/test_aide.py` vérifie les **deux sens** : toute touche déclarée est
expliquée, et toute explication porte sur une action qui existe encore. Le
premier attrape la touche ajoutée sans un mot ; le second l'explication d'une
fonction supprimée, qui survivrait en décrivant un comportement disparu.

Le guide couvre aussi les touches `show=False` — les champs éditables, le pas
fin, la navigation — celles-là mêmes qu'IE-36 signale comme invisibles.

### Trois pièges rencontrés

- **`H` dans une saisie.** Une liaison prioritaire au niveau de l'application
  passe avant le widget focalisé : taper « h » dans un nom de profil aurait
  ouvert le guide au lieu d'écrire la lettre. La liaison est donc sans priorité,
  et `action_aide` refuse en plus d'agir quand une saisie a le focus. Le smoke
  TUI tape la touche dans un champ et vérifie que la lettre s'écrit (`[18c]`).
- **L'horloge disparue.** Deux widgets `dock: right` se recouvrent au lieu de
  s'empiler — l'horloge s'était effacée sans que rien ne le signale, repéré à la
  capture. Un seul widget porte désormais les deux : « H Aide · 00:12:34 ».
- **Le nettoyage du smoke.** L'encodage lancé au scénario 13 tournait encore
  quand le dossier temporaire était supprimé : ffmpeg tenait le fichier, et le
  harnais sortait en erreur une fois sur deux. Le processus est coupé avant de
  quitter le scénario.

662 tests, smoke TUI vert trois fois d'affilée, 28 captures.

## [v0.8.3.9] — 2026-08-29

### Un pas de 10 ms pour affiner le décalage

Le réglage n'avait que deux pas : 100 ms et 1 s. Une mesure rend souvent la
bonne valeur à quelques dizaines de millisecondes près, et on ne pouvait pas
s'en approcher — de −1 100 on passait à −1 000, sans jamais atteindre −1 050.

`Ctrl+↑` / `Ctrl+↓` déplacent le décalage de dix millisecondes.

**Sur la touche demandée.** `Ctrl+±` n'est pas transmissible de façon fiable :
Textual n'a même pas de nom pour `ctrl+plus`, et en mode terminal virtuel —
celui qu'il active aussi sous Windows — `Ctrl+=` ne produit généralement aucun
code. Seul `Ctrl+-` passe, sous le nom `ctrl+underscore` (0x1F). Un pas qui ne
marcherait que dans un sens serait pire que pas de pas du tout.

Les deux directions sont donc portées par `Ctrl+↑/↓`, séquences VT standard
toujours transmises, avec les variantes `Ctrl+±` liées en alias pour les
terminaux qui savent les envoyer. Le bandeau annonce la flèche — celle sur
laquelle on peut compter.

**Vérifié là où c'était risqué.** La question n'était pas que la liaison soit
déclarée mais qu'elle traverse le `DataTable`, qui étouffe les touches avant le
système de bindings. Le smoke TUI presse les touches et lit la valeur obtenue
(`[11a]`). `tests/test_pas_decalage.py` vérifie en plus qu'au moins un nom
**connu de Textual** figure dans chaque liaison : une liaison sur un nom inconnu
ne déclenche jamais rien, et ne le dit pas.

## [v0.8.3.8] — 2026-08-29

### Une piste audio alignée était refusée par la mesure

Signalé sur *The Fall* S02E06 : le sous-titre se mesurait bien (−13 170 ms),
la piste audio VF était rejetée — alors que les deux fichiers durent 1:29:40 et
1:29:38, à deux secondes près.

Les deux pistes étaient en réalité **alignées à dix millisecondes près**.

`_search` essaie chaque ratio d'étirement de la grille et retenait le pic le plus
**saillant**. Sur cette paire :

| ratio | décalage | Pearson | saillance |
|---|---|---|---|
| (1, 1) | −10 ms | **0.83** | 546 |
| (24000, 25025) — PAL→film | +160 280 ms | 0.26 | **1008** |

Le ratio PAL l'emportait sur une corrélation de 0.26 — du bruit — à cent
soixante secondes de la vérité. Le recoupement par tiers refusait ensuite ce
résultat aberrant, à juste titre, et la mesure se soldait par un « montage
différent » qui n'expliquait rien.

**La saillance ne se compare pas d'un ratio à l'autre.** `_rescale` change la
longueur du signal ; la médiane et le MAD qui normalisent la saillance sont
calculés sur une courbe de corrélation d'une autre taille, donc sur une autre
échelle. Comparer ces nombres revient à comparer des degrés et des kelvins.

La corrélation choisit désormais le ratio ; la saillance garde son rôle —
dire si le pic vaut quelque chose — et départage à corrélation comparable
(0.10 d'écart). Le seuil est calé sur la situation que la grille doit
distinguer : sur une paire réellement étirée, le vrai ratio sort à 0.9955 et
son plus proche voisin — 24/25 contre 24000/25025, deux valeurs à 0.1 % l'une
de l'autre — à 0.7993.

Résultat sur la paire signalée : −10 ms, confiance **excellente** (0.83),
recoupée sur les trois tiers avec 0 ms de dispersion.

Le sous-titre, lui, reste à −13 170 ms — vérifié, la correction ne le déplace
pas. L'écart entre les deux valeurs est normal : le `.srt` vient d'un DVDRip
Netflix, une autre source que la VF 720p.

## [v0.8.3.7] — 2026-08-29

### La bannière dit quel Python tourne

```
╔═══════════════════════════════════════════╗
║  IRIS ENCODE  v0.8.3.7                    ║
║  Python 3.12.14 · .venv local             ║
╚═══════════════════════════════════════════╝
```

Depuis la v0.8.3.6, `launch.bat` choisit entre trois candidats — le `.venv`
local, le Python du PATH, celui que `bootstrap.ps1` installe. Le choix était
**silencieux** : rien à l'écran ne disait lequel avait gagné. C'est pourtant la
première chose à savoir quand une dépendance manque ou qu'une version surprend.

La version est donnée entière, correctif compris : `3.12.14`, pas `3.12`. Un
correctif de patch change des comportements, et un numéro tronqué empêche de
comparer deux postes.

Écrit dans `main.py`, pas dans `launch.bat` : `main.py` est le chemin autonome
et tourne quel que soit le lanceur. L'inscrire des deux côtés aurait dupliqué
l'information — la divergence silencieuse fermée en v0.8.3.5 pour le pied de
page et en v0.8.3.6 pour la liste des dépendances.

`tests/test_banniere.py` vérifie les deux branches de la détection, et que la
ligne tient dans le cadre — dessiné à largeur fixe, il se crèverait sur un
débordement, et c'est la première chose que voit l'utilisateur.

## [v0.8.3.6] — 2026-08-29

### L'installation ne demande plus rien

Python était le seul prérequis que l'application ne savait pas satisfaire
elle-même. Ce n'était pas un oubli mais une contrainte mécanique : le code qui
télécharge ffmpeg, mkvmerge et dovi_tool *est* du Python, et ne peut donc pas
s'exécuter avant lui.

`bootstrap.ps1` est cette exception, écrite en PowerShell. Il suit la convention
du reste de l'outillage — récupérer dans `bin/`, sans droits administrateur,
sans toucher au PATH ni au registre :

1. **`uv`** — un exécutable unique, téléchargé depuis GitHub, une dépendance de
   plus à côté de ffmpeg et mkvmerge ;
2. **un CPython 3.12**, que `uv` va chercher lui-même ;
3. **un `.venv` local**, garni depuis `requirements.txt`.

Tout tient dans le dossier de l'application. Copier le dossier sur une clé,
c'est copier l'installation entière — la portabilité que `launch.bat` protège
depuis l'origine.

`launch.bat` choisit désormais son interpréteur : le `.venv` s'il est complet,
sinon le Python du PATH s'il annonce 3.11 ou mieux, sinon le bootstrap. Un
Python système qui convient est *utilisé*, jamais remplacé — mais si `pip`
échoue dessus (poste verrouillé, dépôt interne, permissions), le lanceur bascule
sur l'environnement isolé plutôt que de s'arrêter sur un message.

Le script vérifie sa sortie en important les six modules, plutôt que de se fier
au code de retour de `uv` : une installation interrompue laisse un `.venv`
présent et incomplet, exactement l'état qu'un code de retour nul ne distingue
pas. Même principe que `pistes_audio_vides`.

Testé sur le chemin froid complet — sans uv, sans `.venv`, sans Python dans le
PATH : téléchargement, installation, vérification, lancement.

### Deux pièges rencontrés en chemin

- **La BOM.** Sans BOM UTF-8, Windows PowerShell 5.1 lit les accents du script
  en ANSI et ne parse plus les chaînes. Le fichier en porte une.
- **`for /f` et les guillemets.** L'appel qui lit `version.py` se cassait dès
  que l'exécutable *et* l'argument étaient entre guillemets — la version
  disparaissait du bandeau sans erreur. Les `^"` encadrants le corrigent.

### La liste des dépendances vit désormais en quatre endroits

Deux dans `launch.bat`, deux dans `bootstrap.ps1`, plus `main.py` — chacun
répondant à une question différente, aucun superflu. `tests/test_deps.py` exige
maintenant que **tous** disent la même chose que `requirements.txt`, et que les
quatre appels des deux scripts coïncident entre eux. C'est la même divergence
silencieuse que le pied de page en v0.8.3.5, fermée avant qu'elle s'ouvre.

## [v0.8.3.5] — 2026-08-29

Les huit constats de la revue du 2026-08-28 (IE-28 à IE-33), plus deux défauts
d'avancement rapportés en cours d'encodage.

### Ce qui déborde se voit déborder

Sept constats sur huit étaient la même famille : une valeur coupée net, qui
reste plausible une fois coupée. `→ HEVC → HDR10` rendu `→ HEVC →` se lit comme
une décision complète — le sort du Dolby Vision avait disparu sans laisser de
trace, et les trois sorties possibles s'affichaient à l'identique.

Corriger une colonne à la fois n'avait jamais suffi ; la famille revenait à
chaque version depuis IE-01. Trois garde-fous la remplacent :

- **`cellule()`** — toute cellule de table passe par elle, et elle pose
  l'ellipse. `hdmv_pgs_sub`, `→ HEVC → HDR10`, `34.6 Go` : ce qui manque se
  voit manquer.
- **Des planchers qui tiennent le contenu** — `COLUMN_MIN_WIDTHS` couvrait deux
  colonnes sur onze. Les colonnes à valeurs énumérables (décision, Dolby Vision)
  ont désormais un plancher, et `tests/test_troncature.py` énumère les libellés
  que chacune peut produire : un libellé qui s'allonge sans que le plancher
  suive fait échouer la suite.
- **Un plafond au redimensionnement** — IE-02 avait donné un plancher par
  colonne, rien ne limitait la somme. Mesuré sur le dry-run : 186 colonnes
  persistées pour un terminal de 160. `>` s'arrête à la largeur réelle, donne
  la place qui reste plutôt que rien, et dit pourquoi il s'arrête.

### Une touche déclarée s'annonce

La touche `R` du point de repère était déclarée `show=True` et n'apparaissait
nulle part : la liste du pied de page était écrite à la main, à côté des
`BINDINGS`, et les deux ont divergé en silence. L'assistant, lui, construisait
son pied de page avec `actions=[]` — ses huit touches n'étaient annoncées nulle
part.

`actions_ecran()` lit les `BINDINGS`. L'assistant filtre par étape : proposer
« Encoder » au moment de choisir le fichier n'aide personne, et `↵` garde le
même sens d'un bout à l'autre — avancer.

`tests/test_footer_bindings.py` porte sur le pied de page **complet**, bande 2
comprise, en relisant l'appel `footer_line2` de chaque `compose()`. C'est ce
test qui a rattrapé le `⌫ Retour` que la dérivation venait de faire disparaître
de quatre écrans.

### Trois défauts d'affichage dans l'écran des pistes

- `── SOUS-TI` : les intitulés de section vivaient dans une colonne de dix
  caractères. Le trait décoratif part dans les autres cellules — la ligne se lit
  comme une règle en travers de la table — et la colonne prend la largeur du
  plus long intitulé.
- La colonne **Source** portait deux sens : le motif de sélection pour l'audio,
  le titre déclaré pour les sous-titres. Les deux comptent : ce sont deux
  colonnes.
- Une piste écartée laissait une case **vide**, qui se lit comme une donnée
  manquante et non comme une décision. Elle dit `← écartée`, du même mot
  partout.

### L'avancement, rapporté en cours d'encodage

- **La barre globale restait à 0 %.** Le compte ne portait que sur les fichiers
  *achevés* : sur un encodage d'un seul fichier — le cas ordinaire depuis
  l'assistant — elle affichait 0 % pendant deux heures pendant que la ligne du
  fichier annonçait 69 %. Deux chiffres contradictoires à l'écran, dont le plus
  visible était le faux. Le fichier en cours compte désormais pour sa fraction,
  et l'en-tête dit aussi `2/7 terminés`.
- **La ligne d'avancement était chassée par la commande.** La zone du bas avait
  une hauteur fixe de cinq lignes ; la commande ffmpeg s'y enroule sur quatre ou
  plus et occupait tout, poussant hors champ frame, fps, vitesse et temps
  restant. La zone suit son contenu, et l'avancement passe devant la commande.

### Outillage

`tests/shots_tui.py` — le générateur des vingt-sept captures — est **versionné**.
Il était ignoré par git depuis la première revue : c'est pourtant lui qui a
trouvé le détournement de la touche `T`, qu'aucun test ni relecture ne voyait.
Un garde-fou qui n'existe que sur une machine disparaît au premier clone.

## [v0.8.3.4] — 2026-08-28

### `T` ouvrait l'assistant au lieu de l'écran des pistes

La bascule de mode avait été branchée sur `action_open_tracks`, qui sert à la
fois à `↵` et à `T`. Les deux touches ont été détournées d'un coup, et l'écran
des pistes devenait **inatteignable en mode assistant** — alors que la consigne
ne visait que `↵`.

Seul `↵` dépend du mode désormais ; `T` garde son sens partout.

Ni la suite de tests ni la relecture ne le voyaient. C'est le harnais de captures
qui a buté dessus pendant la revue d'interface, en cherchant `TracksScreen` et en
trouvant `WizardScreen` — et le guide, audité la veille, affirmait pourtant que
`T` fonctionnait « quel que soit le mode ». Le scénario 15 du smoke TUI le
verrouille.

## [v0.8.3.3] — 2026-08-28

### Le guide rattrape le code

Audit des tables de raccourcis contre les `BINDINGS` réellement déclarés. Sept
écarts, dont trois qui rendaient une fonction introuvable :

- la touche **`W`** — qui change ce que fait `↵` sur un fichier — n'était nulle
  part dans le tableau du browser ;
- **`R`**, le point de repère, manquait dans celui du recalage ;
- le choix des pistes d'un donneur se fait à l'**espace**, ce que la section ne
  disait pas : on pouvait croire qu'`↵` suffisait.

`Ctrl+Home` avait son propre chapitre, coincé **après** les sous-sections de
dépannage. Une touche valable partout appartient aux conventions communes : elle
y est passée, et le chapitre orphelin a disparu.

Deux affirmations devenues fausses ont été corrigées : le mode se lit désormais
à trois endroits et non plus seulement dans la barre de profil, et « le signal
d'un sous-titre est trop creux pour retrouver les plages seul » n'est plus vrai
depuis la détection par accord.

### Un chapitre « Cas d'usage »

Cinq parcours complets, du besoin au fichier produit : ajouter une VF et ses
sous-titres à une VO, réencoder une arborescence entière selon le profil, rendre
lisible un 4K Dolby Vision qui bloque à la lecture, ne garder que certaines
langues, recaler un sous-titre trouvé sur internet.

Chacun est vérifié contre le code, pas rédigé de mémoire : `F3` n'agit que sur
un dossier et écarte les fichiers déjà assez compressés — le guide le dit
maintenant, parce qu'un fichier absent de la liste inquiète.

### `subtitle_languages` devient réglable

La clé existait depuis la v0.8.2.0 mais le formulaire de profil ne l'exposait
pas : il fallait éditer `profiles.toml` à la main. Elle a désormais son champ,
sous les langues audio. **Vide = toutes**, comme avant l'existence de la clé.

Écrire un cas d'usage sur les langues est ce qui l'a révélé.

## [v0.8.3.2] — 2026-08-28

### Le point de repère propose la réplique, au lieu de la demander

La première version demandait **deux** instants : celui écrit dans le
sous-titre et celui entendu. C'était obliger à charger le fichier dans un
lecteur rien que pour relire une valeur que l'application connaît déjà.

`R` propose désormais une réplique et son horodatage ; il ne reste qu'un nombre
à trouver. `↓` et `↑` en proposent une autre — une réplique peut tomber dans un
passage muet, ou ne pas se retrouver à l'oreille.

Six répliques sont proposées, réparties dans le film. Sont écartées celles de
moins de dix-huit lettres, qui ne se repèrent pas — « Oui. » n'aide personne —
et celles des trente premières et dernières secondes, souvent des cartons de
générique communs à toutes les versions.

## [v0.8.3.1] — 2026-08-28

### Un point de repère quand la mesure ne peut pas conclure

Certains couples ne se mesurent pas, et aucun réglage n'y changera rien : un
sous-titre dont l'adaptation diffère de celle du doublage plafonne à **0,117**
pour un seuil de 0,25, *même parfaitement aligné*. La corrélation n'y est pas
fiable — mais elle reste utilisable si on lui dit **où** chercher.

`R`, sur l'écran de recalage, demande deux instants : celui écrit dans le
sous-titre, celui où on l'entend. La recherche se centre alors sur leur écart
et se resserre à ±12 s. Sur le fichier du signalement, elle retrouve les trois
plages — +280 / +1480 / +5580 ms là où la vérité établie à l'oreille est
+300 / +1500 / +5600.

**Un ancrage faux ne reste pas muet, et c'est le piège.** La recherche
mal centrée trouve un pic secondaire dont la régularité compose des plages
d'allure honnête — mesuré : +1600 ms là où l'utilisateur annonçait −8000. C'est
le **désaccord** entre les deux qui trahit l'erreur, pas l'absence de résultat.
`accord_avec_ancre()` le vérifie, et le refus nomme les deux valeurs pour que
l'utilisateur sache quoi corriger.

Deux défauts trouvés en chemin par les tests, pas à la relecture : le centre de
recherche était nommé `c`, **écrasé par la variable de corrélation** dans la
boucle — le contrôle de borne comparait un décalage à un coefficient, et ne se
déclenchait donc jamais près de zéro ni jamais loin. Et écarter un palier isolé
pouvait couper en deux un palier qui n'en formait qu'un : les plages voisines de
même décalage sont désormais recollées.

### Du code mort retiré

`decision.ambiguites()` détectait les langues revendiquées par plusieurs pistes.
La refonte de l'assistant l'a rendue inutile — sa table montre toutes les pistes
avec leur nom et se coche à l'espace — et elle n'avait plus d'appelant depuis.
Retirée avec ses tests : c'est ce changement-là qui l'avait orpheline.

## [v0.8.3.0] — 2026-08-28

Version publiée. Elle rassemble treize incréments, dont trois qui changent ce
que l'application sait faire — le détail de chacun reste dans les sections
0.8.2.5 à 0.8.2.17 ci-dessous.

**L'assistant devient un écran autonome.** Cinq étapes, `↵` pour avancer, un
fichier à la fois. `W` bascule depuis l'accueil, et le mode se lit dans la barre
de profil, dans le libellé de la touche et dans la couleur du footer. La mesure
d'une piste greffée se lance et s'applique toute seule, jauge à l'appui.

**Une piste audio transcodée pouvait disparaître sans un mot.** Deuxième
exemplaire d'un défaut ouvert puis classé faute d'explication : quand une même
invocation ffmpeg décode une piste sans perte et mappe un sous-titre au premier
repère tardif, la piste n'est pas écrite — code de retour nul, fichier amputé.
Une passe audio séparée le contourne, et la sortie est désormais relue : un
succès se vérifie, il ne se déduit pas d'un code de retour.

**Des plages de décalage détectées par accord plutôt que par force.** Certains
sous-titres plafonnent sous le seuil de confiance même parfaitement alignés ;
leur décalage est pourtant stable, et c'est cette régularité qui est lue.

Le reste : `Ctrl+Home` pour revenir à l'accueil depuis tout écran, la confiance
affichée en mots, la piste greffée qui est enfin celle qu'on a choisie, le nom
des sous-titres lu et affiché en entier, et le plafond de transcodage E-AC3
ramené au palier utile.

## [v0.8.2.17] — 2026-08-28

### Des plages détectées par accord entre fenêtres, non par force de corrélation

Certains sous-titres ne peuvent pas être validés par l'amplitude d'une
corrélation. Mesuré sur un cas réel : un `.srt` dont l'adaptation diffère de
celle du doublage plafonne à **0,117** pour un seuil de 0,25 — *même
parfaitement aligné*, vérifié à l'oreille en six points. Le texte n'obéit pas
aux mêmes contraintes qu'un doublage lip-syncé, les répliques sont découpées et
condensées autrement, et la structure des repères ne décalque plus celle de la
parole. Aucun seuil d'amplitude ne rattrapera ça.

Son décalage, lui, est stable. `_segments_par_accord()` lit cette régularité
plutôt que la force du signal, et retrouve sur ce fichier **+300 / +1400 /
+5600 ms** là où la vérité établie à l'oreille est +300 / +1500 / +5600.

Trois garde-fous, chacun mesuré :

- **la recherche est bornée à ±30 s** — un décalage de montage se compte en
  secondes ; à ±90 s, douze fenêtres rendaient douze réponses incohérentes ;
- **une fenêtre dont le pic touche la borne est écartée**, pas moyennée : c'est
  le signe qu'il n'y a pas de pic ;
- **la cohérence se compte sur tout le film**, non entre voisines immédiates.
  70 % des fenêtres partagent leur valeur sur un cas vrai, 25 % sur deux
  signaux sans rapport. Le critère par adjacence, essayé d'abord, acceptait
  deux fenêtres tombées d'accord par hasard et étendait ce palier fortuit sur
  tout le film — c'est le test qui l'a montré.

Rien n'est appliqué d'office : la fonction rend des plages, que l'utilisateur
consulte avec `S` et applique avec `P`. Le garde-fou contre un décalage faux
reste entier.

## [v0.8.2.16] — 2026-08-28

### La confiance d'une mesure s'affiche en mots

« confiance 0.09 » ne dit rien à qui n'a pas le seuil en tête — et le seuil
n'est pas fixe : il monte quand les repères se raréfient (`confidence_floor`),
si bien qu'un même chiffre n'a pas le même sens d'une mesure à l'autre. 0,30
est une bonne mesure sur un sous-titre bavard, une mauvaise sur une piste de
forcés.

Quatre niveaux, calculés **relativement au seuil** : `aucune`, `faible`,
`moyenne`, `excellente`. Les deux premiers correspondent à une mesure refusée,
les deux autres à une mesure retenue — la frontière n'est donc pas arbitraire,
c'est celle de la décision.

Le panneau de diagnostic garde les nombres derrière le mot — il existe pour
qu'un refus soit analysable — mais personne n'a plus à traduire « 0,09 » de
tête. La table des plages et le libellé compact, eux, n'affichent que le mot.

## [v0.8.2.15] — 2026-08-28

### Les touches du footer redeviennent lisibles en mode assistant

Le fond du footer passe à l'accent du thème en mode assistant, mais les noms de
touches restaient en `bold yellow` — la couleur choisie pour le bleu du mode
manuel. Deux couleurs chaudes de luminosité voisine : les touches disparaissaient
dans le fond, précisément sur les écrans où l'on découvre le parcours.

Elles passent au blanc sur ce fond, et gardent le jaune sur le bleu, qui n'avait
aucune raison de changer.

Le smoke test vérifie les deux : la couleur des touches suit le mode.

## [v0.8.2.14] — 2026-08-28

### La mesure de l'assistant visait un flux qui n'existait pas

Signalé à l'usage : mesurer une piste audio marchait en mode manuel, pas dans
l'assistant. L'écran de recalage traduisait le **tid mkvmerge en index ffmpeg**,
l'assistant passait le tid tel quel. Sur un donneur ordinaire, la première piste
audio porte le tid 1 et l'index 0 : la mesure portait sur un flux absent.

C'est le piège documenté en tête de `core/muxer.py`, et le second fichier où il
se produit — après la commande de greffe (v0.8.2.2). La cause n'était pas
l'inattention mais la duplication : la traduction vivait à deux endroits, et le
troisième appelant l'a oubliée.

`sync.measure_external_track()` devient le point d'entrée unique. Il reçoit une
piste externe, traduit, et appelle la bonne mesure. L'écran de recalage et
l'assistant s'en servent tous deux ; plus personne n'a à y penser.
`tests/test_mesure_piste.py` verrouille la traduction dans les deux sens et ses
cas limites.

### Une jauge pendant la mesure

L'assistant affichait « Mesure du décalage en cours… » et plus rien pendant
plusieurs minutes, ce qui se lit comme un blocage. Une barre d'avancement suit
désormais le décodage, chaque piste occupant sa part de la jauge — sinon elle
repartirait de zéro à chaque piste, ce qui se lit comme un recommencement.

## [v0.8.2.13] — 2026-08-28

### L'assistant rappelle sur quel fichier il travaille

Seule la première étape nommait le fichier. Les quatre suivantes parlaient d'un
codec, de pistes, d'un lancement — sans jamais redire de quoi. Le bandeau porte
désormais le nom du fichier traité à chaque étape.

Le nom seul, jamais le chemin : c'est lui qui identifie. Il est tronqué au
milieu selon la largeur disponible, pour que sa fin survive — c'est là que
vivent la résolution, le codec et le groupe qui distinguent deux versions d'un
même film.

## [v0.8.2.12] — 2026-08-28

### Le mode se lit dans le footer, et dans sa couleur

La barre de profil annonçait déjà le mode, mais le footer disait seulement
« W Mode » — ce qui n'apprend rien sur celui qui est actif. Il nomme désormais
le mode courant : `W Assistant` ou `W Manuel`.

Et le fond du footer change : le **manuel garde le code couleur par défaut**,
l'assistant prend l'accent du thème. Sur l'accueil comme sur les écrans de
l'assistant lui-même.

Une couleur se remarque sans être lue. Le mode commande ce que fait une touche
aussi banale que `↵` sur un fichier : il ne devait pas demander qu'on aille le
chercher.

## [v0.8.2.11] — 2026-08-28

### L'assistant devient un écran à lui seul

La première version enchaînait les écrans existants — pistes, donneur,
recalage — en leur donnant seulement un ordre. C'était un mélange, pas un
parcours : chaque écran gardait ses propres touches, ses propres colonnes et
ses propres détours.

L'assistant est désormais **autonome**, cinq étapes, `↵` pour avancer :

| Étape | Ce qu'on y fait |
|---|---|
| 1 — Fichier | Le nom du fichier et le profil actif |
| 2 — Décision | Codec, débit et pistes conservées, **sur un seul écran** |
| 3 — Pistes externes | Présenter un donneur ; la mesure suit aussitôt |
| 4 — Lancer | Muxer ou encoder, les deux toujours offerts |
| 5 — Terminé | Le résultat, puis retour à l'accueil |

**L'accueil ne change pas.** `W` y bascule entre assistant et parcours libre, et
la barre de profil affiche lequel est actif : le mode change ce que fait `↵` sur
un fichier, cela devait se lire sans l'essayer. En mode assistant, `↵` ouvre le
parcours — un fichier à la fois.

**La mesure ne se demande plus.** Une piste greffée sans recalage est une piste
décalée : il n'y a rien à arbitrer. L'audio est mesurée dès l'ajout et son
décalage reporté sur les sous-titres du même donneur. Une mesure refusée laisse
le décalage à zéro et le dit, plutôt que d'appliquer un candidat non confirmé.

**Les deux lancements restent offerts.** `↵` prend le recommandé, `M` et `E`
forcent l'autre. Un mux sans piste externe est refusé avec sa raison au lieu
d'être exécuté à vide.

`muxer.propager_recalage()` sort de l'écran de recalage pour que la règle
n'existe qu'une fois : l'assistant s'en sert aussi.

## [v0.8.2.10] — 2026-08-28

### `Ctrl+Home` — revenir à l'accueil d'une touche

Enchaîner plusieurs fichiers demandait de remonter les écrans un par un.
`Ctrl+Home` dépile jusqu'au browser depuis les sept écrans non modaux :
dry-run, run, mux, assistant, config, pistes et recalage.

`Home` n'était pas disponible : elle appartient à la navigation dans les tables,
et `TableNavMixin` l'intercepte avant même que les bindings soient consultés.
Lui donner un second sens aurait cassé le premier.

**Deux écrans demandent confirmation.** Le dépilage ne rend aucun résultat, donc
les rappels des écrans traversés ne sont pas appelés. Sans conséquence pour ceux
qui n'ont rien à rendre — mais les pistes et le recalage portent une sélection,
une greffe, une mesure de plusieurs minutes. Perdre cela sur deux touches n'était
pas acceptable : ils passent par la modale de confirmation.

Les bindings sont tous `priority=True` : un `DataTable` étouffe la touche avant
le système de bindings, et sans cela le raccourci ne faisait rien sur les écrans
qui affichent une table — presque tous. C'est le smoke test qui l'a montré.

Quatre cas verrouillés par le scénario 17 : retour direct depuis un écran sans
état, confirmation demandée depuis les pistes, refus respecté, et la touche sans
effet quand on est déjà à l'accueil.

## [v0.8.2.9] — 2026-08-28

### Le flux `bin_data` des sorties MP4 : c'est la piste de chapitres

Relevé en vérifiant la passe audio, sur une sortie MP4 qui portait un flux de
plus que ceux demandés. Identifié plutôt que soupçonné :
`codec_tag_string=text`, `handler_name=SubtitleHandler`, une trame par
chapitre — et `-map_chapters -1` le fait disparaître, emportant les chapitres
avec lui.

Le MP4 ne sait porter les chapitres que sous la forme d'une piste texte
QuickTime ; c'est ainsi que les lecteurs les retrouvent. Rien à corriger. C'est
noté dans la spec (§ 8.6) pour que personne ne réenquête, la mention `bin_data`
d'ffprobe ayant tout d'une piste parasite.

## [v0.8.2.8] — 2026-08-28

### La passe audio ne se paie plus que là où elle sert

Elle se déclenchait sur « transcodage + sous-titres conservés », soit la
plupart des encodages. La mesure exige davantage : la source décodée doit être
**sans perte**. Transcoder l'AC3 du même fichier, au lieu de son TrueHD, sort
indemne. Le déclencheur est donc restreint à TrueHD, MLP et DTS-HD MA.

### Un code de retour nul ne vaut plus succès

La restriction ci-dessus repose sur deux mesures — un codec sans perte qui
échoue, un codec avec perte qui passe. C'est une inférence, pas une loi. Et le
défaut qu'elle contourne est silencieux : ffmpeg rend un code nul et un fichier
amputé d'une piste.

La sortie est donc relue après chaque encodage. La durée de chaque piste audio
est comparée à celle attendue ; en dessous du dixième, le fichier est déclaré en
erreur au lieu d'être compté comme réussi, avec le nom des pistes en cause. Le
seuil est grossier à dessein : il sépare « 54 millisecondes au lieu de trois
heures et demie » de tout ce qui est légitime, une piste de commentaires
écourtée comprise.

Vérifié sur un fichier délibérément cassé : `ENG VO (eac3, 0.06 s)` signalée,
le même encodage sans le sous-titre déclaré sain. Le filet ne peut pas devenir
lui-même une cause d'échec — une sortie illisible le laisse muet.

## [v0.8.2.7] — 2026-08-28

### Le défaut d'audio tient à la simultanéité, pas à la sortie

La v0.8.2.6 décrivait le défaut comme « transcoder une piste audio **et
recopier** un sous-titre » — ce qui laissait croire que le partage d'un même
fichier de sortie était en cause. La mesure dit autre chose :

| Disposition | Paquets audio sur 60 s |
|---|---|
| une seule sortie, tout ensemble | 2 |
| deux sorties, l'audio seule dans la sienne | 2 |
| deux sorties, le sous-titre seul dans la sienne | 2 |
| sous-titre présent dans l'entrée, **non mappé** | 1 875 |
| **appel ffmpeg distinct** | 1 875 |

Il suffit que le sous-titre soit **mappé** quelque part dans l'invocation. Le
muxeur est hors de cause : aucune disposition des sorties ne sauve la piste,
seul un processus séparé le fait — ce que la parade fait déjà.

Deux facteurs de plus éliminés au passage : transcoder l'AC3 de la même source
au lieu du TrueHD sort indemne, et un sous-titre laissé dans l'entrée sans être
mappé est sans effet.

Aucun changement de comportement : la parade était juste, et pour la bonne
raison. Seule sa description l'était à moitié.

## [v0.8.2.6] — 2026-08-28

### Une piste audio transcodée pouvait disparaître sans un mot

Signalé sur une conversion refaite : la piste anglaise du fichier produit était
vide. C'est le **second** exemplaire du défaut qui avait fait ouvrir IE-12 puis
IE-16, et qui avait été classé « cause non identifiée, non reproductible ».

Elle l'est désormais. Quand une même commande ffmpeg transcode une piste audio
**et** recopie un flux de sous-titres dont le premier repère arrive tardivement,
la piste transcodée n'est pas écrite. Deux trames sortent, puis plus rien — sans
erreur, sans code de retour non nul, et le bilan de ffmpeg ne compte que l'audio
recopiée. Sur un film dont les sous-titres « forced » n'ouvrent qu'à 6 min 20,
mesuré sur soixante secondes :

| Sous-titres mappés | Paquets audio produits |
|---|---|
| aucun | 1 875 — correct |
| les denses seules (premier repère à 23 s) | 1 875 — correct |
| la seule piste « forced » (premier repère à 380 s) | **2** |

Le défaut ne dépend ni du codec — l'AC3 meurt comme l'E-AC3 — ni de la durée, et
aucun réglage n'y change rien : ni `max_muxing_queue_size`, ni
`max_interleave_delta`, ni `avoid_negative_ts`, ni `copyts`, ni l'ordre des
`-map`. Les pistes simplement recopiées survivent, et la vidéo aussi.

D'où la parade : produire les pistes finales dans une passe à part, puis les
**recopier** dans la passe d'encodage. Elle n'est payée que lorsque les deux
conditions sont réunies, et coûte un transcodage audio là où la passe vidéo se
compte en heures. Vérifié sur le fichier du signalement : la piste anglaise
passe de 2 à 1 876 paquets, avec sa langue, son titre et les six sous-titres.

### Ce que cela clôt

IE-12 et IE-16 avaient diagnostiqué un « mauvais entrelacement » et cherché la
cause dans la durée du film et le nombre de pistes. Le fichier n'était pas mal
entrelacé : **il n'avait pas de piste anglaise**, et les sondages ne trouvaient
donc aucun paquet audio. Mars Express, réencodé avec huit sous-titres, sortait
propre parce que tous ses sous-titres ouvrent tôt.

## [v0.8.2.5] — 2026-08-28

### Le mode « HDR10 quality » gardera son plafond serré — c'est mesuré

Le mode standard (NVENC) a reçu en v0.8.1.24 un plafond à 1,5 × la cible : son
CBR traitait le débit demandé comme un plafond qu'il n'avait pas à atteindre.
Le mode « HDR10 quality », qui passe par libx265, portait le même `-maxrate`
égal à la cible et avait été laissé en l'état faute de mesure.

La mesure dit l'inverse de l'intuition. L'ABR de x265 distribue un budget selon
son modèle de qualité ; c'est un **VBV serré qui le force à le dépenser**, là où
le CBR de NVENC n'y voyait qu'un plafond. Desserrer le plafond fait donc
sous-consommer. Sur un film 1080p 10 bits, extraits de 120 s, cible 5 000k :

| Réglage | t=1800 | t=4200 |
|---|---|---|
| `maxrate` = cible — **celui en place** | 99,9 % | 100,0 % |
| `maxrate` = 1,5 × la cible | 93,6 % | 99,9 % |
| ABR seul, sans VBV | 93,7 % | — |

Au preset `slow`, celui de `cinema_4k_basic` : 99,6 %.

Aucun changement de comportement, donc : appliquer la correction NVENC ici
aurait coûté six points. Les deux branches de `build_command` se ressemblent et
doivent différer — `tests/test_x265_debit.py` le verrouille, pour qu'une passe
d'harmonisation échoue bruyamment plutôt que de casser ce mode en silence.

## [v0.8.2.4] — 2026-08-28

### Savoir quelle piste de sous-titres est laquelle

Deux défauts se cumulaient pour rendre six pistes indiscernables.

**Le nom n'était pas lu.** `SubtitleTrack` portait l'index, le codec et la
langue ; le scanner lisait les tags du flux et jetait le titre. Or « Français
(France) », « Français (France) (forced) » et « Français (Canada) (SDH) » ont
le même codec et la même langue : **seul le titre les sépare**. L'assistant
affichait « — » sur chacune, et l'écran des pistes n'en disait rien.

**Les colonnes tronquaient par la droite**, c'est-à-dire exactement là où se
trouve ce qui distingue ces noms. La colonne `Nom` du recalage faisait quatorze
caractères : les trois variantes d'une même région s'y écrivaient toutes
« Français (Fran… ».

Le titre est désormais lu et affiché — dans l'assistant, sur l'écran des pistes,
dans le sélecteur du donneur et sur celui du recalage. Les colonnes qui le
portent ont la largeur d'un nom entier, et `tronquer_milieu` coupe au milieu
quand la place manque quand même : « França…(forced) » plutôt que
« Français (Fran… ». La fin l'emporte, parce que c'est elle qui porte le sens.

Le sélecteur du donneur passe de 84 à 104 colonnes ; son champ Codec, qui
réservait 22 caractères pour écrire « SubRip », les rend au nom.

C'est le défaut de fond derrière le signalement précédent : une piste « forced »
de vingt-trois répliques greffée à la place de la piste complète de 949.

## [v0.8.2.3] — 2026-08-28

### Le recalage mesuré se reporte seul sur les sous-titres

La piste audio est la base du recalage : c'est sur elle que la mesure tourne.
Il fallait ensuite recopier son décalage sur chaque sous-titre, avec `c`. Or le
guide affirmait déjà que ce décalage **est** le bon pour eux — des sous-titres
livrés avec une VF sont écrits sur le timing de cette VF. Une copie qui
n'apporte aucune information n'est qu'une occasion de l'oublier, et une piste
oubliée sort décalée sans que rien ne le signale.

Une mesure réussie s'applique désormais d'elle-même aux sous-titres du même
fichier donneur. Le bandeau annonce combien de pistes ont suivi ; leur colonne
d'origine affiche « repris de #N », exactement comme après un `c` manuel.

Trois garde-fous, parce qu'un report automatique doit rester un service et
jamais une surprise : il ne quitte pas le **fichier donneur** de l'audio ; il
n'écrase jamais une piste **déjà mesurée ou réglée à la main** ; et il ne part
que d'une piste **audio**. `c` reste pour tout le reste — un sous-titre venu
d'ailleurs, ou une référence choisie exprès.

Un candidat forcé (`a`) se reporte comme une mesure : c'est aussi une décision.

## [v0.8.2.2] — 2026-08-28

### La piste greffée n'était pas celle qu'on avait choisie

Signalé à l'usage : des sous-titres ajoutés apparaissaient dans le lecteur, au
bon nom, et n'affichaient rien.

Le fichier donneur entre dans ffmpeg **en entier**, et la commande mappait son
flux `:0` — ce qui suppose qu'il n'en porte qu'un. Vrai d'un `.srt` nu, faux
d'un conteneur. Un rip qui embarque six pistes françaises rendait donc toujours
la première, quelle que soit celle demandée ; et la première d'un rip est en
général la piste « **forced** », vingt-trois répliques sur un épisode entier.

Le défaut résistait à la relecture de la commande, parce que la langue, le titre
et les drapeaux venaient bien de la piste choisie : le lecteur affichait
« Français (France) » sur le contenu de « Français (France) (forced) ».

`muxer.ffmpeg_stream_index` traduit désormais le tid choisi en index ffmpeg —
c'est déjà le seul endroit du code où les deux numérotations se croisent. Un
donneur illisible retombe sur le premier flux, comme avant.

Vérifié sur les fichiers du signalement : la piste tid 3 se mappe `1:s:1` et
rend 949 repères, là où l'ancienne commande en rendait 23.

**Le chemin mkvmerge n'était pas touché** — il raisonne en tid de bout en bout.
Le défaut ne frappait que les fichiers réencodés.

## [v0.8.2.1] — 2026-08-28

### Trois défauts de l'assistant, dont deux silencieux

Signalés par un `IndexError` à l'usage. Le plantage était le moins grave des trois.

**Revenir sur l'étape des langues plantait.** En validant la dernière ambiguïté,
le compteur dépassait la fin ; `action_retour` ne le recadrait pas, parce qu'au
moment du test l'étape courante était déjà la suivante.

**Un choix révisé ne pouvait que retirer.** Les arbitrages se retranchaient de
la sélection *courante* : une piste écartée avait déjà quitté la liste, et la
recocher ne la ramenait pas — l'écran affichait pourtant sa case cochée. Les
choix repartent désormais d'une base figée avant tout arbitrage.

**Les flèches ne répondaient plus.** Masquer la table lui retire le focus :
en revenant sur l'étape, le curseur restait bloqué sur la première ligne.

Au passage, les cases partent cochées sur ce que la décision garde déjà :
valider sans rien toucher ne retire plus rien.

Scénario 16 du smoke TUI : il rejoue les trois, sur un clip fabriqué avec deux
pistes « fre » — et c'est lui qui a trouvé le troisième.

## [v0.8.2.0] — 2026-08-28

### L'assistant

L'application s'ouvre désormais sur un assistant : **un fichier, quatre étapes,
une touche pour avancer**. `F12` bascule vers le parcours libre, et le choix
tient pour la session.

Il ne calcule rien de neuf. `decide()` arbitrait déjà le codec, le débit, le
conteneur, le sort du Dolby Vision et chaque piste ; l'assistant parcourt cette
décision et rend la main aux écrans existants — sélection des pistes, choix du
donneur, recalage — pour ce qu'ils font déjà.

Deux étapes seulement sont conditionnelles :

- **les langues ambiguës**, quand plusieurs pistes revendiquent la même langue
  voulue. Le doute se définit par un **compte**, pas par une heuristique : une
  seule candidate, on la prend ; plusieurs, seul leur titre les sépare
  (« Français » contre « Français canadien »), et un titre ne se devine pas ;
- **les pistes additionnelles**. Aucun fichier donneur n'est cherché
  automatiquement : les conventions de nommage des releases sont sans limite et
  un mauvais appariement est *silencieux*. C'est l'utilisateur qui le présente,
  quand il y en a un — il peut n'y en avoir aucun.

Ce qui est retiré, c'est la navigation, jamais l'information : chaque étape
montre ce qu'elle a décidé, et l'étape 1 nomme le fichier produit. Un assistant
qui déciderait en silence remplacerait un doute de manipulation par un doute de
contenu, qui ne se voit qu'après l'encodage.

### « fra » n'était pas « fre », et une VF disparaissait sans un mot

ISO 639-2 a deux jeux de codes pour vingt langues — un bibliographique (`fre`,
`ger`, `dut`), un terminologique (`fra`, `deu`, `nld`) — et les conteneurs
emploient l'un ou l'autre sans règle. La comparaison portait sur les chaînes
brutes : `audio_languages = ["fre"]` **excluait une piste étiquetée « fra »**,
qui n'atteignait jamais le fichier produit.

Mesuré sur un épisode réel : ses sous-titres portent `fra`, `ces`, `nld`, `deu`,
`ell`, `ron`, `slk`, `zho` — huit codes terminologiques dans un seul fichier.
`scanner.normalize_language` les réconcilie ; l'affichage garde ce que le
fichier déclare.

### Les sous-titres n'étaient filtrés par rien

Le profil filtrait l'audio par langue, jamais les sous-titres :
`subtitle_indices = None` vaut « toutes », et aucune règle ne s'y appliquait.
Un épisode de rip streaming en embarque quarante-trois ; les quarante-trois
traversaient la chaîne. La clé `subtitle_languages` pose la règle, et les dix
profils intégrés la portent désormais aux mêmes langues que leur audio. Sur le
fichier de test : 43 pistes en entrée, 4 retenues.

Une clé absente ne change rien — les profils personnels gardent leur
comportement.

## [v0.8.1.27] — 2026-08-28

### La recette de greffe s'arrêtait avant les sous-titres

`GUIDE.md` § 3 menait jusqu'à la mesure de la piste audio, puis renvoyait à
« § 4 selon le résultat » — et § 4.1, le cas nominal, ne dit rien des
sous-titres. La réponse existait bien, mais éclatée : § 2.4 conseille `C`,
§ 4.3 et § 4.4 le rappellent pour les cas mesurables, § 4.5 décrit `P` pour un
montage différent. Personne ne suit une recette en la recomposant à partir de
trois sections.

L'étape 4 porte désormais une table des quatre suites possibles selon ce que la
mesure a rendu, et dit ce qui n'allait pas de soi : la mesure ne vaut que pour
la ligne sur laquelle elle a tourné. § 4.1 le répète sur place.

La recette s'ouvre aussi sur un rappel : regarder ce que la cible contient déjà.
Un rip streaming embarque trente sous-titres, français compris — il n'y a alors
qu'une piste audio à greffer.

## [v0.8.1.26] — 2026-08-28

### Le transcodage des pistes sans perte ne suit plus le débit de la source

`CODEC_MAX_BPS["eac3"]` valait 6 144k — la limite de l'encodeur ffmpeg, pas un
choix. Une piste sans perte étant transcodée **au débit présent dans la piste**,
un TrueHD 5.1 à 3 501k donnait un E-AC3 à 3 501k : 5,66 Go pour un film de
3 h 35, quand aucun décodeur ne tire quoi que ce soit d'un Dolby Digital Plus
5.1 au-delà du palier haut usuel. Le plafond passe à 1 024k, et la même piste y
pèse 1,65 Go.

Le plafond AC3 ne bouge pas : ses 640k sont ceux de l'encodeur, qui ramène
silencieusement toute demande supérieure. Les sources déjà sous le nouveau
plafond gardent leur débit — un DTS à 768k reste à 768k.

## [v0.8.1.25] — 2026-08-28

### La décision audio survit au retrait du Dolby Vision

L'écran annonçait `→ eac3 3501k` et le titre corrigé `ENG VO : E-AC3 5.1` ; la
sortie contenait un TrueHD inchangé, sous son ancien titre. Le retrait du DV
remuxait par `mkvmerge -o <sortie> <video_nodv> --no-video <source>` : aucune
décision audio ne lui était transmise. Transcodage, exclusion d'une piste par
langue et retitrage étaient perdus, en MKV comme en MP4.

Les quatre opérations n'ont pas le même prix, et le chemin le reflète
désormais. Exclure une piste audio ou un sous-titre passe par des options de la
commande mkvmerge existante — aucune étape, aucun octet recopié. Seul le
transcodage coûte une passe : une étape 3 produit les pistes finales dans un
Matroska audio, que le remux prend comme seconde entrée. Elle n'existe que
lorsqu'une piste est réellement à transcoder. En MP4, il n'y a jamais d'étape
supplémentaire : ffmpeg recompose déjà le fichier et transcode au passage.

Vérifié sur un extrait de 60 s de `Watchmen` 2160p DV P8.1, profil
`cinema_4k_basic` : ce que l'écran annonce et ce que `ffprobe` lit dans la
sortie coïncident piste par piste, titres compris — `ac3 6ch fre « FR VFF :
AC3 5.1 »` recopié, `eac3 6ch eng 3501k « ENG VO : E-AC3 5.1 »` transcodé, six
sous-titres conservés, RPU Dolby Vision absent, transfert `smpte2084` intact.

## [v0.8.1.24] — 2026-08-28

### Le débit demandé redevient une cible, et non un plafond

Un film pouvait sortir à 57 % du débit que le profil promet et que l'écran
affiche. La commande passait `-b:v <cible> -maxrate <cible> -rc cbr` : le débit
demandé servait à la fois de cible et de plafond. Chaque scène facile tire alors
la moyenne vers le bas, et aucune scène difficile ne peut la remonter — la
moyenne ne peut, par construction, que tomber sous la cible.

La commande passe désormais en VBR avec 50 % de marge au-dessus de la cible et
un tampon qui couvre ce plafond. Mesuré sur un extrait de 180 s d'un film en
prises de vues réelles 2160p 10 bits, cible 6 035k : **92 % du débit demandé
avant, 99 % après**.

### Ce qui n'était pas un défaut, et qui est maintenant écrit

Le même retrait, mesuré sur une animation au dessin plat, ne se comble pas : le
même extrait rend 41 % avant, 54 % après. Ce n'est pas l'encodeur qui échoue,
c'est le contenu qui n'a pas besoin de ces bits — un encodage piloté par la
qualité (`-cq 16`, quasi transparent) en dépense encore moins.

La suspicion portait sur le 10 bits, qui creuse effectivement l'écart (41 %
contre 72 % en 8 bits sur le même extrait). La mesure de fidélité renverse la
conclusion : contre la source, le 10 bits à 2 911k obtient un SSIM de **0,9991**,
le 8 bits à 4 727k un SSIM de **0,9970**. Le 8 bits consomme 62 % de bits en plus
pour un résultat nettement moins fidèle. Le retrait de débit en 10 bits ne coûte
donc pas de qualité, et la spécification le dit désormais (§ 12.1).

## [v0.8.1.23] — 2026-08-28

### Un fichier pouvait disparaître de la liste sans un mot

Un WebM déposé dans le dossier n'apparaissait pas. Ni l'extension ni le codec
n'étaient en cause : le fichier portait un tag `DESCRIPTION` contenant « ❤️ ».

ffprobe écrit sa sortie en UTF-8. La lire avec `text=True` laisse Python choisir
l'encodage de la machine — cp1252 sur un Windows français — et le premier
caractère hors de cette table lève `UnicodeDecodeError` **dans le thread de
lecture de subprocess**. L'exception n'y remonte pas jusqu'à l'appelant :
`stdout` vaut simplement `None`, `json.loads(None)` échoue, et le fichier est
écarté comme illisible. `scan_directory` avalant les erreurs par fichier, il n'en
restait rien à l'écran — une ligne de moins, sans message.

Six appels lisaient ainsi la sortie de ffprobe, ffmpeg et mkvmerge, dont les
lignes de progression citent les noms de fichiers : `scanner`, `encoder`,
`muxer` (deux), `preflight` et `sync`. Tous lisent désormais en UTF-8, les
octets invalides étant remplacés plutôt que fatals. Un test interdit le motif
`text=True` dans `core/`, et deux autres vérifient sur un fichier réel qu'un
titre hors cp1252 ne fait plus perdre le fichier.

Vu de l'utilisateur : les WebM VP9/Opus et les MKV AV1/Opus sont listés,
décidés et encodés comme le reste — VP9 et AV1 vers HEVC, Opus vers AAC ou AC3,
le HDR10 conservé en 10 bits.

## [v0.8.1.22] — 2026-08-28

### L'AV1 était cassé sur toute machine

Découvert en cherchant pourquoi il échouait sur une RTX A4500 : la commande
passait `-profile:v main` à `av1_nvenc`, **qui n'a pas d'option `profile`**.
ffmpeg refusait donc la commande avant même d'interroger la carte —
« Unable to parse "profile" option value "main" ». Le défaut ne dépendait pas
du matériel : l'AV1 n'aurait pas davantage fonctionné sur une RTX 40.

### Les capacités d'encodage sont mesurées, plus supposées

`detect()` déduisait les encodeurs du modèle de carte. Or NVENC n'encode l'AV1
qu'à partir d'Ada (RTX 40), et une carte antérieure ne le dit qu'au moment
d'échouer. Les trois encodeurs sont désormais **sondés au lancement** — ouverts
sur une image, en parallèle, ~0,7 s — et le résultat suit l'application.

Relevé sur la machine de développement : `hevc_nvenc` ✓, `h264_nvenc` ✓,
`av1_nvenc` ✗ (« No capable devices found »).

**Le choix AV1 n'est pas retiré du picker.** Une carte se remplace, un pilote se
met à jour, et masquer l'option laisserait croire qu'elle n'existe pas. Elle
s'affiche « ✗ indisponible ici », et le lancement **refuse avant d'appeler
ffmpeg**, en nommant la cause :

```
✗ ERREUR : av1_nvenc indisponible ici
Cette machine ne sait pas encoder avec « av1_nvenc » — sondé au lancement.
L'AV1 par NVENC demande une RTX 40 ou plus récente ; le HEVC et le H264
restent disponibles.
```

`peut_encoder()` rend `None` tant que rien n'a été sondé : ne rien savoir
n'autorise pas à refuser.

### Un échec d'encodage nomme sa cause

ffmpeg annonce la cause puis constate l'échec. L'écran ne gardait que la
**dernière** ligne — « Error opening output files: Invalid argument » —
c'est-à-dire la seule qui n'apprend rien.

`diagnostiquer()` cherche des signatures connues dans les quarante dernières
lignes : encodeur indisponible, pilote absent, débit hors plage, disposition de
canaux refusée, disque plein, écriture refusée. Chacune a été reproduite avant
d'être ajoutée. Sans cause reconnue, la ligne brute reste affichée : mieux vaut
un message opaque qu'un message inventé.

Correspond à l'entrée **IE-13** de `TODO.md`.

## [v0.8.1.21] — 2026-08-28

### Les sources WebM, VP9, AV1 et Opus traversent la chaîne

`.webm` était déjà une extension reconnue, et l'Opus déjà transcodé. Mais la
règle du codec non standard **ne se déclenchait qu'en dessous de 1080p** : un
VP9 ou un AV1 en 1080p ou en 4K, dont le débit et la résolution tenaient dans
les seuils du profil, ressortait en `← SKIP`. Il restait donc illisible chez le
destinataire — un fichier ne devient pas lisible parce que son débit est
raisonnable.

Le critère porte désormais sur le codec seul. `CODECS_LISIBLES` — `h264` et
`hevc` — nomme ce qu'une chaîne grand public prend sans transcodage ; tout le
reste est réencodé, à toute résolution : VP9, AV1, VC-1, MPEG-2, DivX, et un
codec que ffprobe ne reconnaît pas.

La cible suit le bucket de résolution, comme les autres cas : H264 sous 1080p
où il compresse mieux, HEVC au-dessus.

Vérifié de bout en bout sur des fichiers réels :

| Source | Sortie |
|---|---|
| WebM VP9 1080p + Opus 2.0 | **HEVC Main + AAC LC 192k**, MP4 |
| WebM AV1 720p + Opus 5.1 | **H264 High + AC3 5.1 448k**, MP4 |

Les deux se lisent en direct sur un téléviseur récent comme sur un client
mobile, sans que le serveur ait à transcoder.

Le débit et la résolution gardent la priorité : un VP9 trop gros reste traité
par le cas du débit, et le motif affiché dit lequel a tranché.

## [v0.8.1.20] — 2026-08-28

### Le conteneur de sortie se règle par profil

Il se déduisait du seul contenu. Or le choix ne s'en déduit pas : certains
lecteurs digèrent mal le Matroska, et c'est une politique, pas une propriété du
fichier. Nouvelle clé **`container`**, réglable dans l'écran des profils :

| Valeur | Effet |
|---|---|
| `auto` | Le contenu décide — comportement inchangé |
| `mkv` | Toujours du Matroska, rien n'est écarté |
| `mp4` | Les sous-titres image sont écartés, et la décision les compte |

**Deux garde-fous, parce qu'une politique ne vaut pas une perte silencieuse :**

- Si les sous-titres image sont les **seuls** du fichier, c'est le conteneur
  qui cède. Mieux vaut un MKV qu'une sortie sans sous-titres.
- Une piste audio sans perte **conservée** ramène toujours au MKV. On écarte un
  sous-titre doublé par un SubRip ; on n'échange pas contre un format une piste
  que l'utilisateur a demandé de garder.

Et l'exclusion **se voit avant le lancement** : le dry-run affiche `MP4 −3 st`
dans la colonne Conteneur, en style « modifié ». L'encodeur mappe la liste
finale au lieu de `0:s?`, sans quoi l'exclusion aurait été purement décorative.

Relevé sur le dossier de travail en mode `mp4` :

| Fichier | Sortie | Écartés |
|---|---|---|
| Watchmen | MP4 | 3 PGS, doublés par 3 SubRip de mêmes langues |
| Starship Troopers | MP4 | 3 PGS, doublés |
| The Zookeeper's Wife | MP4 | 1 VobSub anglais ; le SubRip néerlandais reste |
| **Colossus** | **MKV** | aucun — son unique sous-titre est une piste image |

### Le retrait de Dolby Vision sait sortir en MP4

Il passait par mkvmerge, qui ne sait écrire que du Matroska : la décision
imposait donc le MKV, ce qui contredisait une politique `mp4`. Quand le
conteneur demandé est le MP4, le remux passe désormais par ffmpeg.

**Deux images étaient perdues.** Un flux HEVC brut n'a pas d'horodatage — d'où
la cadence donnée avant l'entrée — et ses premières images portent des DTS
négatifs que le muxeur MP4 refuse : il les jetait. Mesuré sur un extrait de
2 270 images, la sortie n'en avait que 2 268, et la première manquait.
`-avoid_negative_ts make_zero` décale la base au lieu de rogner.

Vérifié après correction : **2 270 images des deux côtés, et les empreintes de
200 images décodées sont identiques**.

## [v0.8.1.19] — 2026-08-28

### Le mode « HDR10 quality » n'a jamais injecté ses métadonnées

Ce mode existe pour produire un HDR10 aux métadonnées statiques correctes —
master display et MaxCLL — que certains téléviseurs exigent pour appliquer leur
tone mapping. Il ne les a **jamais** écrites.

`dovi.rpu_info()` analysait la sortie de `dovi_tool info` avec des expressions
régulières attendant du texte — `Dolby Vision Profile: 8.1`, `MaxCLL: 1000` —
alors que l'outil livré rend du **JSON**. `master_display` et `max_cll` valaient
donc toujours `None`, et les `-x265-params` sortaient sans elles.

**Trois tests passaient pourtant**, parce qu'ils fabriquaient eux-mêmes le
format attendu. C'est exactement ainsi qu'un défaut survit à une suite verte :
un test qui invente son entrée ne prouve rien sur ce que produit l'outil réel.

Les métadonnées sont désormais lues **dans les SEI du flux, par ffprobe** :

```
master-display=G(8500,39850)B(6550,2300)R(35400,14600)WP(15635,16450)L(10000000,50)
max-cll=988,382
```

Trois conséquences, toutes des améliorations :

- **Cela vaut pour toute source HDR**, avec ou sans Dolby Vision. L'ancienne
  voie ne s'activait que sur un fichier DV.
- **`dovi_tool` n'est plus requis** pour ce mode.
- **Le scan est trois fois moins cher** sur un fichier DV : l'ancienne voie
  extrayait 30 s de flux HEVC, en tirait le RPU puis l'interrogeait — 1,86 s
  par fichier, contre 0,62 s pour une lecture d'image.

Un `max_content`/`max_average` à `0,0` signifie « non mesuré » : rien n'est
injecté plutôt que d'affirmer un pic lumineux nul. `probe_file()` et
`rpu_info()`, sans appelant, sont retirés.

⚠ **Le coût du mode reste ce qu'il est** : `libx265` mesuré à 0,78 image/s en
4K, soit de l'ordre de 70 heures pour un long métrage. Il est réparé, pas rendu
praticable en 4K — l'écran des profils l'annonce.

### Ni ffprobe ni ffmpeg n'étaient trouvés sur une installation neuve

Découvert en réparant ce qui précède. Le preflight installe les binaires dans
`./bin/` **sans toucher au `PATH`**, or `scanner._ffprobe_json` et
`encoder.build_command` les appelaient par leur nom nu.

Vérifié en retirant ffprobe du `PATH` : `scan()` lève `FileNotFoundError`, et
le browser écarte alors **tous les fichiers comme illisibles**. L'encodage
aurait échoué de la même façon.

`scanner.set_ffprobe_path()` et `encoder.set_ffmpeg_path()` sont posés au
démarrage, comme `muxer.set_mkvmerge_path()` et `sync.set_ffmpeg_path()` le
faisaient déjà. Le défaut ne se voyait pas ici parce que cette machine a
ffmpeg dans son `PATH` — c'est précisément ce que le test en dossier vierge ne
pouvait pas attraper.

## [v0.8.1.18] — 2026-08-28

### Le chemin du dossier était écrit deux fois

La barre d'état donne le dossier courant ; quatre lignes plus bas, la notice
donnait le chemin **complet** du fichier survolé, qui recommence par ce même
dossier. Une quarantaine de colonnes payées deux fois — et sur un partage
réseau, il ne restait plus la place d'afficher le nom du fichier.

La notice ne montre désormais que ce que la barre d'état n'a pas déjà dit :

| Dossier courant | Fichier survolé | Notice |
|---|---|---|
| `D:\films` | `D:\films\Watchmen.mkv` | `Watchmen.mkv` |
| `D:\films` | `D:\films\2009\Watchmen.mkv` | `2009\Watchmen.mkv` |
| `D:\films` | `C:\ailleurs\Autre.mkv` | chemin complet |
| `D:
ilms` | `D:
ilms9\Watchmen.mkv` | `2009\Watchmen.mkv` |
| `D:
ilms` | `C:illeurs\Autre.mkv` | chemin complet |

Le deuxième cas compte : un scan récursif remonte des fichiers de sous-dossiers,
et là le chemin relatif dit quelque chose que la barre d'état ignore.

### Le footer passait à la ligne avant d'être plein

Les raccourcis étaient répartis en trois bandes — propres à l'écran, globaux,
touches de fonction — et **chaque bande était enroulée séparément**. Chacune
démarrait donc sa ligne, même pour une seule entrée : `⌫ Retour` au dry-run et
au mux, `F10 Quitter` à l'encodage et à la configuration.

Les bandes fixent toujours l'ordre, mais plus le découpage : elles sont
enchaînées puis enroulées ensemble, et la ligne ne se coupe qu'au débordement.

| Écran | Avant | Après |
|---|---|---|
| Encodage | 2 lignes | **1** |
| Configuration (150 col.) | 3 lignes | **1** |
| Dry-run | 3 à 4 lignes | **2** |
| Browser | 3 à 4 lignes | **3** |

**Contrepartie assumée** : la v0.8.1.2 avait rangé les raccourcis par rôle pour
qu'« une place fixe par rôle vaille mieux qu'un ordre de déclaration ». Les
touches de fonction restent en fin de séquence, mais ne démarrent plus
forcément leur propre ligne. C'est de la place rendue au contenu au prix d'un
repère un peu moins strict — arbitrage de la revue, inscrit ici pour qu'il ne
se perde pas.

Correspond aux entrées **IE-08** et **IE-09** de `TODO.md`.

## [v0.8.1.17] — 2026-08-28

### L'écran d'accueil promettait dix colonnes vides

Premier écran de l'application, il listait les volumes sous l'en-tête complet du
tableau de fichiers — Taille, Résolution, Durée, Débit, Codec, Dolby V.,
Décision, Estim., ETA, Audio — **dont aucune ne peut avoir de valeur pour un
volume**. S'y ajoutaient « 0/0 sélectionné(s) » alors que rien n'y est
sélectionnable, le bandeau détaillé du profil d'encodage alors qu'aucun fichier
n'est en vue, et un pied proposant `F1 Dry-run`, `F2 Run`, `F7 AlloCiné`.

L'écran des volumes porte désormais **ses propres colonnes** :

| Volume | Espace libre | Total | Occupé |
|---|---|---|---|
| 💾 `C:\` | 407.3 Go | 510.5 Go | 20 % |
| 💾 `D:\` | 305.0 Go | 2.0 To | 85 % |

- La barre d'état compte des volumes au lieu d'annoncer une sélection
  impossible, et ne parle plus de redimensionner des colonnes qui ne le sont
  pas.
- Le bandeau de profil attend qu'un fichier soit en vue : le profil décide de
  ce qu'on fera des fichiers, il n'a rien à dire avant.
- Le footer ne propose que **`↵ Ouvrir le volume`**. Sélectionner, encoder ou
  interroger AlloCiné n'a pas de sens ici — c'est le même défaut que le footer
  de l'écran Config corrigé en v0.8.1.15, au même endroit du raisonnement.
- **Un taux d'occupation d'au moins 90 % passe en alerte** : c'est là qu'un
  encodage échouera faute de place.
- Un volume injoignable — lecteur vide, partage réseau coupé — rend des tirets
  plutôt que de faire disparaître sa ligne : le volume existe, c'est sa mesure
  qui manque.

Le jeu de colonnes et les raccourcis basculent au changement de mode, dans les
deux sens.

### `fmt_bytes` connaît le téraoctet

Un partage réseau s'affichait `35726.4 Go`, ce qui ne se lit pas. Il rend
maintenant `34.9 To`.

Correspond à l'entrée **IE-07** de `TODO.md`.

## [v0.8.1.16] — 2026-08-28

### Une modale laisse voir l'écran sur lequel elle porte

Les modales effaçaient tout — titre, barre d'état, liste des fichiers, footer.
Il ne restait qu'une boîte au milieu du vide, au moment précis où l'on voudrait
voir sur quoi le choix va s'appliquer.

**La cause n'était pas Textual**, qui rend ses modales translucides par défaut,
mais une règle de confort de l'application : `Screen { background: $surface; }`.
`ModalScreen` héritant de `Screen`, la règle s'appliquait à elle aussi et
écrasait la transparence. Une ligne posée après elle rétablit le filigrane :

```css
ModalScreen { background: $background 40%; }
```

La boîte, elle, garde son fond opaque : **son texte ne perd rien en
lisibilité**, seul son pourtour laisse voir l'écran d'origine. Mesuré sur le
rendu : 137 fragments de texte visibles contre 9 auparavant.

### Un seul cadre

Deux familles graphiques coexistaient sans rapport avec le rôle : demi-blocs
`█ ▀ ▄` pour les listes de choix — profil, valeur, donneur, plages — et traits
`┌ ─ │` pour les confirmations et la fiche AlloCiné. Les cinq cadres en
demi-blocs passent au trait fin.

Les couleurs, elles, restent : elles portent le rôle et non la famille — le
`$warning` de l'écran des plages continue d'alerter.

Rendu vérifié sur quatre modales — confirmation, quitter, liste de valeurs,
choix de profil : parent visible, trait fin, plus aucun demi-bloc.

Correspond à l'entrée **IE-06** de `TODO.md`, dont les deux arbitrages ont été
tranchés par le propriétaire du projet.

## [v0.8.1.15] — 2026-08-28

### Le footer suivait l'écran, pas le focus

Pendant l'édition d'un profil, le footer annonçait encore les touches de
l'écran Config — `N Nouveau`, `E Éditer`, `D Supprimer`, `↵ Activer profil` —
alors que le formulaire tenait le focus et que **taper « n » écrivait un « n »
dans le champ courant**. Les vraies touches n'étaient annoncées que par un
bandeau propre au formulaire.

Le comportement était juste : `check_action` neutralisait déjà ces touches.
C'est l'affichage seul qui mentait — et un footer faux vaut moins qu'un footer
vide, puisqu'il invite à des gestes sans effet.

- Le formulaire publie ses raccourcis dans `ProfileForm.RACCOURCIS` ; l'écran
  bascule le footer dessus à l'ouverture et restaure les siens à la fermeture.
- **`F10 Quitter` reste dans les deux états**, comme la convention du projet
  l'exige — la première version le faisait disparaître avec la ligne de
  navigation, ce que le rendu à l'écran a montré.
- **Le formulaire perd son bandeau propre.** Il disait vrai pendant que le
  footer mentait ; maintenant que le footer dit vrai, deux bandeaux répétant la
  même chose, c'en est un de trop.
- La liste des raccourcis de l'écran n'est plus écrite deux fois — elle l'était
  dans les `BINDINGS` et dans la construction du footer.

Rendu vérifié à l'écran, dans les trois états :

```
liste       ↵ Activer profil   N Nouveau   E Éditer   D Supprimer   ⌫ Retour
formulaire  Tab Champ suivant   ⇧Tab Champ précédent   ↵ Ouvrir une liste …
retour      ↵ Activer profil   N Nouveau   E Éditer   D Supprimer   ⌫ Retour
```

### Les tests ne se contaminent plus entre eux

Écrire ce test a révélé un piège : construire l'application pose les chemins
d'outils en **variables de module**, qui survivaient au test et faussaient les
suivants. `test_muxer` attendait `"mkvmerge"` et recevait le chemin absolu du
binaire — selon l'ordre d'exécution, ce qui est la pire forme d'échec.

`tests/conftest.py` sauvegarde et restaure ces variables autour de chaque test.
Un test peut désormais construire l'application sans y penser.

Correspond à l'entrée **IE-05** de `TODO.md`.

## [v0.8.1.14] — 2026-08-27

### Un seul rendu pour les noms de touches

Trois notations coexistaient pour la même information :

| Endroit | Ce qui s'affichait |
|---|---|
| Footer permanent | `Space Sélect` · `Enter Ouvrir` · `Back Retour` |
| Modales et bandeaux | `Espace  Sélectionner` · `↵  Valider` · `Esc  Annuler` |
| Formulaire de profil | `Tab / Shift+Tab : champ suiv./préc.` |

Le nom anglais côtoyait le mot français, le glyphe côtoyait le mot, et
l'espacement changeait d'un écran à l'autre. **Douze bandeaux réécrivaient les
touches à la main.**

- `tui.common` porte désormais la table `TOUCHES` et les fonctions `touche()`,
  `raccourci()` et `raccourcis()` ; `SEP_TOUCHE` et `SEP_ENTREE` fixent
  l'espacement. Le footer lit la même table — son `_fmt_key` n'en est plus
  qu'un alias.
- **Les glyphes sont préférés là où ils existent** : `↵`, `⌫`, `␣`, `←`, `→`,
  `↑`, `↓`. Ils tiennent en une colonne, ce qui compte sur un footer de trois
  lignes — `Space` occupait cinq colonnes pour la même information.
- Une notation composée — `+/-`, `Shift+↑/↓` — traverse intacte : elle ne
  correspond à aucun nom de touche et n'avait pas à être défigurée.

Rendu vérifié à l'écran :

```
␣  Sélect   A  Tout   N  Aucun   ↵  Ouvrir   V  Visualiser   ⌫  Remonter
```

Un test interdit qu'une quatrième notation réapparaisse : il parcourt les
écrans à la recherche des anciennes graphies et échoue si l'une revient.

Le `␣` est le seul glyphe que le projet n'employait pas encore. S'il rend mal
dans un terminal, il se change en une ligne — c'est tout l'intérêt d'une source
unique.

Correspond à l'entrée **IE-04** de `TODO.md`.

## [v0.8.1.13] — 2026-08-27

### Une seule table de couleurs, exprimée en rôles

La même décision portait deux teintes selon l'écran : `→ HEVC` était magenta au
browser et `dark_orange` sur l'écran des pistes. Trois tables indépendantes
coloraient les mêmes notions — celle de `core/decision.py`, celle de
`tracks.py`, et `DV_VALUE_STYLES` dans `tui/common.py` — et le vert signifiait
« gain de taille » ici, « décision de piste » là.

Les couleurs se décident désormais **une fois**, en nommant leur rôle plutôt
qu'en choisissant une teinte :

| Rôle | Ce qu'il signale | Teinte |
|---|---|---|
| `INACTION` | rien ne sera fait | `dim` |
| `SANS_PERTE` | traité sans réencodage, image intacte | `green` |
| `ORDINAIRE` | le cas courant | **aucune** |
| `MODIFIEE` | l'utilisateur a écarté la décision automatique | `bold yellow` |
| `ALERTE` | coûteux, lent, ou destructeur | `bold dark_orange` |

Deux arbitrages, qui étaient les points d'attention du rapport :

- **Le cas ordinaire ne porte plus aucune couleur.** `→ HEVC` occupe presque
  chaque ligne de l'écran le plus dense et portait le magenta, la teinte la plus
  criarde. Ce qui se répète partout n'a pas à attirer l'œil.
- **`dark_orange` n'appartient plus qu'aux alertes** — le tone mapping SDR, qui
  détruit la plage dynamique, et l'AV1, qui coûte des heures. L'écran des pistes
  l'employait pour un encodage HEVC ordinaire, ce qui vidait la réserve de son
  sens.

Le vert, du coup, ne dit plus qu'une chose. La colonne d'estimation de taille
l'utilisait pour « plus petit que la source » : une réduction étant le résultat
attendu, elle ne porte plus de couleur, et seule une sortie **plus grosse** —
une anomalie — passe en alerte.

### Une décision « → HDR10 » s'affichait « ? »

`_ACTION_SHORT` n'avait pas reçu d'entrée pour `VideoAction.STRIP_DV`, introduit
en v0.8.1.6 : l'écran des pistes affichait un point d'interrogation sans couleur
sur tout fichier promis au retrait de Dolby Vision. Un test parcourt désormais
tous les membres de l'énumération.

**Vérification** — sur les huit films du dossier de travail, la décision porte
la même couleur au browser, au dry-run, à l'écran d'encodage et à l'écran des
pistes.

Hors périmètre, à traiter avec le constat 10 : les marqueurs de curseur `◄►`
restent en jaune, qui relève de la navigation et non de la décision.

Correspond à l'entrée **IE-03** de `TODO.md`.

## [v0.8.1.12] — 2026-08-27

### Toute durée d'au moins une heure perdait son dernier chiffre

`fmt_duration` rend sept caractères dès qu'il y a des heures — `3:17:24`. La
colonne en réservait six. Le résultat, `3:17:2`, s'affichait **sans ellipse** :
non pas une valeur visiblement coupée, mais une durée valide et fausse. Tous les
films étaient concernés.

Trois protections, parce que la première seule ne suffisait pas :

- **Le défaut de la colonne passe de 6 à 7.** Mesuré sur le dossier de travail,
  c'était la seule colonne dont le contenu réel dépassait sa largeur — mais
  `debit` et `estim` y tiennent tout juste, à un caractère près.
- **Les planchers remontent dans `core.config.COLUMN_MIN_WIDTHS`**, et
  s'appliquent **à la lecture** autant qu'au redimensionnement. C'est ce qui
  répare les installations existantes : un `config.toml` portant déjà
  `duree = 6`, écrit avant que le plancher existe, l'emportait sur le défaut
  corrigé. Les écrans reprennent cette table plutôt que d'en tenir une seconde.
- **Les cellules numériques portent une ellipse.** Rendu vérifié dans une vraie
  `DataTable` : `3:17:…` avec, `3:17:2` sans. Une coupe qui se voit fait perdre
  une information ; une coupe invisible en invente une.

**Vérification** — sur `resources_files/`, les neuf durées s'affichent entières,
dont le `3:35:23` du plus long film. Et la lecture du `config.toml` réel, qui
portait `duree = 6` au dry-run, rend désormais 7.

Correspond à l'entrée **IE-02** de `TODO.md`.

## [v0.8.1.11] — 2026-08-27

### Le markup Rich mangeait les noms de fichiers et de profils

`Static.update()` interprète par défaut ce qui ressemble à une balise entre
crochets. Or **la convention de nommage du projet est faite de cette syntaxe**.
Mesuré sur le rendu réel :

| Écrit | Affiché |
|---|---|
| `film_[mux].mkv` | `film_.mkv` |
| `film_[hevc].mkv` | `film_.mkv` |
| `film_[av1].mkv` · `film_[hdr10].mkv` | `film_.mkv` |
| `Profil : [serie_basic]` | `Profil :` |
| `film_[H264].mkv` | `film_[H264].mkv` — intact |

L'irrégularité aggravait le piège : `_[H264]` survivait, les autres non, Rich ne
consommant que ce qui ressemble à un nom de style valide. Deux conséquences
visibles à l'écran : **le nom du profil actif était invisible** sur l'écran des
pistes, quel que soit le profil ; et **l'écran de mux annonçait `film_.mkv`**
alors que le fichier produit s'appelait `film_[mux].mkv`.

- **Quatorze afficheurs passent en `markup=False`** — barres d'état des cinq
  écrans, sortie et état du mux, lignes de commande ffmpeg et de progression,
  notice de scan, chemin du donneur, bandeau de recalage, en-tête de
  configuration, titre des modales. Aucun n'utilisait de balise volontaire.
- **Les modales de confirmation gardent leur markup** : elles s'en servent
  réellement, et échappaient déjà les noms interpolés.
- L'audit a porté sur les 32 appels d'affichage des huit écrans concernés ;
  les sites recensés sont ceux qui interpolent un nom, un chemin ou un
  identifiant, pas l'ensemble.

**Vérifications** — le smoke TUI lit désormais ce qui est *rendu*, pas ce qui a
été demandé : le suffixe `_[mux]` doit survivre sur l'écran de mux, et le nom du
profil apparaître dans la barre d'état des pistes. Les deux contrôles ont été
falsifiés — correctif retiré, ils échouent en affichant `Profil :   ·` ; remis,
ils passent. `tests/test_markup.py` verrouille les douze autres afficheurs.

Correspond à l'entrée **IE-01** de `TODO.md`.

## [v0.8.1.10] — 2026-08-27

### L'écran des profils dit ce que chaque réglage entraîne

Un profil se réglait à l'aveugle : les champs portaient le nom de la clé TOML,
et rien ne disait ce qu'un choix impliquait. Le formulaire est réorganisé en
**six sections**, chacune suivie d'une ligne qui énonce la conséquence des
valeurs choisies — recalculée à chaque changement, pas un texte d'aide figé.

| Section | Ce que la conséquence annonce |
|---|---|
| **Quand réencoder** | les seuils en clair, et le sort réservé à une source 4K |
| **Comment encoder** | que le preset ne concerne que les fichiers réellement réencodés |
| **Dolby Vision** | retrait par remux, conservation, ou tone mapping — et l'ordre de grandeur du mode `quality` |
| **Audio sans perte** | ce que devient une piste TrueHD, et le conteneur que le choix impose |
| **Autres pistes audio** | si les pistes déjà compatibles sont recopiées ou retranscodées |
| **Fichier source** | l'irréversibilité de la suppression, en style d'alerte |

### Deux réglages audio qui se contredisaient en silence

`preserve_hd_audio` et `audio_hd_codec` étaient indépendants. Un profil pouvait
donc porter « copier sans perte » **et** « transcoder en E-AC3 », l'un
l'emportant sans que rien ne l'indique — c'est précisément ce qui a produit un
fichier gardant son TrueHD alors que l'E-AC3 était attendu.

L'écran n'expose plus qu'un **choix à quatre branches** : copier telles quelles,
transcoder en E-AC3 au débit de la source, en AC3, ou au forfait. Les deux clés
restent dans `profiles.toml` — le moteur est inchangé et les profils existants
restent lisibles — mais l'écran les écrit toujours cohérentes.

Un profil hérité portant une combinaison contradictoire s'affiche sur la branche
**qui décrit ce qui se passe réellement**, la copie, et non sur l'intention
qu'exprimait le codec.

### Documentation

- Spec § 14.8 réécrite : les six sections et la table de correspondance du choix
  audio vers le couple de clés.
- **L'historique des versions de la spec était en désordre.** Mes quatre
  dernières entrées s'étaient insérées en ordre décroissant, chacune s'ancrant
  sur la précédente, alors que le tableau se lit du plus ancien au plus récent.
  Remis en ordre.

## [v0.8.1.10] — 2026-08-27

### L'interface peut enfin être regardée sans être lancée

Travailler l'UI supposait jusqu'ici de lancer l'application et de naviguer
jusqu'à l'écran en question — ce qui rend toute comparaison impossible : on ne
voit jamais deux écrans côte à côte, et on juge de mémoire.

`tests/shots_tui.py` pilote la TUI en headless, presse les mêmes touches qu'un
utilisateur et exporte chaque écran en SVG dans `_shots/`. **Vingt prises,
couvrant les dix-sept classes d'écran** de `tui/screens/`, à grille fixe
(160 × 45) pour qu'elles soient comparables entre elles.

Le point qui compte : ce sont des rendus, pas des maquettes. Le contexte
principal tourne sur `resources_files/`, c'est-à-dire sur de vrais films — noms
de fichiers à rallonge, 4K, HDR, Dolby Vision, pistes multiples. Ce qui déborde
sur ces captures déborde réellement chez l'utilisateur. Les écrans qui écrivent
(suppression, mux, encodage) sont joués à part, dans un dossier temporaire :
aucune touche destructrice n'est pressée sur le matériel réel.

Deux écrans n'étaient pas atteignables sans matériel taillé pour eux, et le
harnais le fabrique : `RecursiveConfirmModal` exige un dossier sous le curseur,
`SegmentsScreen` n'existe qu'après une mesure ayant constaté deux montages
différents — un SRT à décalage volontairement rompu en son milieu la provoque.

Le matériel mesurable est repris de `smoke_tui.py` plutôt que redéfini.
Aucun changement dans l'application elle-même.

## [v0.8.1.9] — 2026-08-27

### Le README dit enfin à quel problème l'outil répond

Il s'ouvrait sur ses prérequis, c'est-à-dire sur le « comment » d'un « pourquoi »
que rien n'exposait. Une section d'introduction décrit désormais la chaîne de
diffusion — serveur Jellyfin, téléviseur webOS, barre en eARC, clients iOS,
sous-titres image — et **ce que chaque maillon impose**.

L'intersection de ces contraintes est étroite : HEVC en HDR10, audio E-AC3,
sous-titres texte. C'est de là que découlent les partis pris de l'outil, et la
section les énonce comme des conséquences plutôt que comme des préférences : ne
pas réencoder par défaut, retirer le Dolby Vision plutôt que le convertir,
transcoder l'audio au débit de la source, laisser le conteneur suivre le
contenu, et régler tout cela par profil parce qu'un salon et un téléphone ne
demandent pas le même fichier.

Aucun changement de code.

## [v0.8.1.8] — 2026-08-27

### Le débit comparé au seuil est celui de la vidéo, pas celui du fichier

Un profil fixe un débit **vidéo** cible, et c'est un débit vidéo que reçoit
l'encodeur (`-b:v`). Le scanner, lui, comparait le débit du **conteneur** :
vidéo, audio et sous-titres confondus. Les deux termes ne portaient pas sur la
même chose, et l'écart part directement en réencodages injustifiés — d'autant
plus grands que les pistes audio sont grosses.

Relevé sur le dossier de travail :

| Fichier | Conteneur | Vidéo réelle | Écart |
|---|---|---|---|
| Watchmen (TrueHD + AC3) | 9 611k | **5 364k** | **−44 %** |
| Kingdom of the Planet of the Apes | 5 658k | **4 248k** | −25 % |
| Colossus (DTS-HD MA) | 12 241k | **10 209k** | −17 % |
| The Zookeeper's Wife | 11 528k | **9 608k** | −17 % |
| Starship Troopers | 8 148k | **6 784k** | −17 % |

Conséquence concrète, avec le profil `cinema_4k_basic` inchangé (seuil 4K à
8 000k) : **Watchmen et Starship Troopers ne partent plus en réencodage** —
leur vidéo est sous le seuil. Ils basculent sur le retrait de Dolby Vision,
soit quelques minutes et une image intacte au lieu d'heures de GPU et d'une
image dégradée.

- `_video_bitrate()` résout le débit dans l'ordre : `bit_rate` du flux vidéo
  (presque toujours absent en Matroska), puis le tag `BPS` posé par mkvmerge,
  puis le débit du conteneur **moins celui des autres pistes**.
- **Une piste dont le débit reste introuvable ne retire rien** : le résultat
  penche alors du côté prudent, celui du réencodage. Une soustraction qui
  donnerait un résultat nul ou négatif est écartée au profit du total.
- Un second flux vidéo — une pochette embarquée — n'est jamais soustrait.
- La colonne « Débit » de l'accueil affiche désormais le débit vidéo. Elle ne
  correspondra plus à ce qu'annonce un explorateur de fichiers, qui montre le
  débit du conteneur ; c'est en revanche la valeur que le seuil compare.

Le défaut existait depuis l'origine et se voyait d'autant moins que les
fichiers testés portaient de l'audio léger.

## [v0.8.1.7] — 2026-08-27

### Transcoder les pistes HD au débit de la source — `audio_hd_codec`

Le forfait par canaux (`audio_surround_kbps`, 448 kbps par défaut) convient à
une piste déjà compressée. Appliqué à un TrueHD à 3,5 Mbps, il jette beaucoup
plus que nécessaire — surtout quand la destination accepte mieux.

- **Nouvelle clé de profil `audio_hd_codec`** : `none` (défaut, comportement
  inchangé), `ac3` ou `eac3`. Les pistes **TrueHD et DTS, toutes variantes**,
  sont alors transcodées **au débit présent dans la piste**.
- **Plafonds mesurés, pas déduits de la norme.** L'encodeur AC3 de ffmpeg
  ramène en silence toute demande au-dessus de **640 kbps** — demander 6144 en
  produit 640 sans le moindre avertissement. L'E-AC3 honore jusqu'à
  **6 144 kbps** puis refuse la commande. La décision annonce donc le débit
  réellement obtenu, pas celui demandé.
- **Le débit de la source est lu même quand le flux n'en déclare pas.** Un
  TrueHD ou un DTS-HD MA rend `bit_rate=N/A` sous ffprobe : le débit est repris
  du tag Matroska `BPS`, sinon calculé par `NUMBER_OF_BYTES ÷ DURATION`. Sans
  aucune de ces sources, la piste retombe sur le forfait du profil — mieux vaut
  ça qu'une valeur inventée.
- **Réglable depuis l'écran Profils** (`F5` → éditer), à côté du débit 7.1.
- `preserve_hd_audio` garde la priorité : copier sans perte prime sur
  transcoder au débit source.

Mesuré sur les fichiers du dossier de travail :

| Source | `none` | `eac3` |
|---|---|---|
| Watchmen — TrueHD 5.1 @ 3 501 887 | ac3 448k | **eac3 3501k** |
| Colossus — DTS-HD MA 2.0 @ 2 008 937 | aac 192k | **eac3 2008k** |
| The Zookeeper's Wife — DTS 5.1 @ 1 536 000 | ac3 448k | **eac3 1536k** |
| Pilgrimage — DTS 5.1 @ 768 000 | ac3 448k | **eac3 768k** |

### DTS-HD MA reconnu comme sans perte

ffprobe nomme `dts` toutes les déclinaisons et met la famille dans `profile` :
« DTS », « DTS-ES », « DTS-HD HR », « DTS-HD MA ». `is_lossless` ne comparait
que le nom du codec — un **DTS-HD MA passait donc pour un DTS ordinaire**, et
échappait à `preserve_hd_audio` comme à la contrainte de conteneur MKV.
`AudioTrack` porte désormais le champ `profile`, lu au scan.

### Repli 7.1 → 5.1 rendu visible

Les encodeurs `ac3` et `eac3` s'arrêtent au 5.1. ffmpeg replie une source 7.1
de lui-même — vérifié, la sortie est identique à l'octet près avec ou sans
`-ac` — mais rien ne le disait : la décision annonçait « → ac3 640k » sur une
piste 7.1 sans mentionner la perte de deux canaux. La commande pose désormais
`-ac:a:N` explicitement et la décision affiche « → ac3 5.1 640k ».

### Titres de pistes corrigés au transcodage

Le titre d'une piste survivait tel quel à sa conversion : un « ENG VO :
TrueHD 5.1 » devenu E-AC3 continuait d'annoncer un codec absent du fichier —
et c'est précisément ce que lisent les lecteurs, la seule chose que voit
l'utilisateur au moment de choisir sa piste.

- Le jeton de codec est remplacé (`TrueHD`, `DTS-HD MA`, `DDP`, `AC3`…), la
  disposition suit quand elle change, et la mention **Atmos est retirée** :
  les objets sonores ne survivent pas à une conversion vers AC3 ou E-AC3.
- **Un titre qui ne dit rien du format est laissé intact.** « English »,
  « Commentaire du réalisateur » n'ont jamais menti : les réécrire serait une
  modification gratuite. Seul ce qui devient faux est corrigé.
- Une piste **copiée** n'est jamais retitrée : rien n'a changé.

| Titre source | Après transcodage en E-AC3 |
|---|---|
| `ENG VO : TrueHD 5.1` | `ENG VO : E-AC3 5.1` |
| `VO DDP Atmos 5.1` | `VO E-AC3 5.1` |
| `VFF DDP 7.1` (→ AC3 5.1) | `VFF AC3 5.1` |
| `DTS-HD MA 7.1` | `E-AC3 5.1` |
| `English` | inchangé |

Vérifié sur un extrait réel de Watchmen : le fichier produit porte bien
`ENG VO : E-AC3 5.1`, et la piste AC3 recopiée garde son titre d'origine.

## [v0.8.1.6] — 2026-08-27

### Retrait du Dolby Vision sans réencodage

Un fichier Dolby Vision **profil 8.1** porte une couche de base qui *est* du
HDR10 : le RPU n'est qu'un jeu de NAL en plus. Jusqu'ici, demander « DV → HDR10 »
passait forcément par un réencodage — qui dégrade l'image, coûte des heures, et
détruit le HDR10+ au passage. Mesuré sur *La Planète des singes* (4K, 2 h 24) :
1 h 40 en NVENC, **74 h** en libx265.

- **`VideoAction.STRIP_DV`.** Quand le profil demande du HDR10 et que le fichier
  n'a par ailleurs aucune raison d'être réencodé — débit sous le seuil,
  résolution dans les clous, codec standard — la décision devient un retrait de
  RPU : ffmpeg recopie le flux HEVC, `dovi_tool remove` en retire le RPU,
  mkvmerge remuxe avec les pistes de la source. Sortie `<nom>_[hdr10].mkv`.
- **Le profil garde la main.** Dès qu'un des trois cas d'encodage s'applique,
  c'est l'encodage qui l'emporte : il supprime le RPU de lui-même, et stripper
  d'abord réécrirait le film pour rien.
- **Mesuré sur le fichier réel**, pas seulement en test unitaire : 5,7 Go
  traités en **2 min 16 s**, durée du conteneur inchangée à la milliseconde,
  image **bit à bit identique** à la source (`framemd5` concordant à 30 min et à
  1 h 10), **HDR10+ conservé**, master display et MaxCLL conservés, les deux
  pistes audio et les six sous-titres avec leurs titres et leurs drapeaux.
- **Sous-profil détecté pour de bon.** `dv_bl_signal_compatibility_id` distingue
  le 8.1 (couche de base HDR10) du 8.4 (HLG) et du 8.2 (SDR). Le browser affiche
  `DV:P8.1` au lieu de `DV:P8`. Seuls les profils **8.1 et 7** sont éligibles :
  retirer le RPU d'un profil 5 laisse une image aux couleurs fausses.
- **Rien n'est proposé qui ne puisse aboutir.** Sans `dovi_tool` *et* mkvmerge,
  la décision retombe sur `SKIP` plutôt que d'afficher une action qui échouera au
  lancement.
- **Dans les pickers de codec, le retrait de DV se range avec `SKIP`.** Ce n'est
  pas un choix de codec : `ACTION_CYCLE` ne le contient pas, et `cycle_index()`
  lui donne la position de `SKIP` — les deux voulant dire « ne pas réencoder ».
  Choisir `SKIP` sur un tel fichier lève la surcharge au lieu d'imposer un SKIP
  sec, qui laisserait le Dolby Vision en place sans que rien ne l'explique.
- Les intermédiaires sont écrits à côté de la source, pas dans le temp du
  système : ils pèsent le poids du film. Ils sont supprimés dans tous les cas.

### Sortie HDR10 en 10 bits

Le mode d'encodage standard posait `-pix_fmt yuv420p` — 8 bits — quelle que soit
la source. Sur une courbe PQ, cela étale 10 bits de dégradés sur 256 niveaux :
banding garanti dans les ciels et les fondus. Toute source HDR réencodée depuis
la v0.6 en sortait abîmée, y compris sans Dolby Vision.

- Sortie en `yuv420p10le` + `-profile:v main10` dès que le résultat est HDR
  (source PQ/HLG, ou `dv_action == HDR10`) et que l'encodeur sait le porter :
  HEVC et AV1. H264 n'a pas de profil 10 bits chez NVENC — une source HDR
  ramenée en H264 reste en 8 bits, ce qui ne concerne que les cibles < 1080p.

### Documentation

- `iris_encode_spec.md` : nouvelle section 7.3, tables de décision et d'encodage
  mises à jour, et **historique des versions complété** — il s'était arrêté à la
  0.8.0.1 alors que le CHANGELOG suivait.

## [v0.8.1.5] — 2026-08-27

- **Crash au lancement sur toute installation neuve** (v0.8.1.4 uniquement).
  `_deep_merge` ne copiait que le premier niveau : les sous-dictionnaires
  absents du fichier utilisateur étaient assignés *par référence*. Sans
  `config.toml` — donc sur toute machine qui vient de télécharger l'archive —
  `cfg["tui"]["browser"]` **était** `_DEFAULTS["tui"]["browser"]`, et la
  réinitialisation des colonnes introduite en v0.8.1.4 vidait les valeurs par
  défaut du module. Tout accès ultérieur levait `KeyError: 'columns'`.
- La fusion recurse désormais sur toute valeur de type dict, y compris absente
  du fichier utilisateur : aucune branche n'est plus partagée. Le piège
  préexistait et attendait la première écriture en configuration.
- `tests/test_config.py` verrouille l'isolation : une écriture dans la
  configuration ne doit jamais atteindre les défauts du module.

## [v0.8.1.4] — 2026-08-27

- **Largeurs de colonnes de l'accueil revues** : les colonnes numériques n'ont
  besoin que de leur contenu, et la place gagnée revient au nom de fichier et
  aux pistes audio — les deux seules qui débordent vraiment. Résolution 12→10,
  durée 12→6, débit 10→6, codec 8→6, Dolby Vision 12→8, décision 12→8,
  Estim. 16→14.
- **L'écran d'accueil repart des largeurs par défaut à chaque lancement.** La
  section `[tui.browser.columns]` de `config.toml` n'est plus lue au
  démarrage : une disposition stable, identique d'une session à l'autre, vaut
  mieux qu'un réglage qui dérive au fil des redimensionnements ponctuels. Le
  redimensionnement reste actif pendant la session, et les autres écrans
  gardent leurs largeurs mémorisées.

## [v0.8.1.3] — 2026-08-27

- La colonne **« Temps estim. »** devient **« ETA »** au browser et au dry-run,
  et sa largeur par défaut passe de 14 à 9 colonnes. Douze caractères d'en-tête
  pour une valeur qui en fait cinq, c'était de la place prise aux noms de
  fichiers. La clé `temps_estim` est inchangée : les largeurs déjà mémorisées
  dans `config.toml` restent valides.

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
