# CHANGELOG — IRIS ENCODE

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
