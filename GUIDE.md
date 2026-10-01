# IRIS ENCODE — Guide d'utilisation

**Version** : 0.8.9.45
**Date** : 2026-10-01

Installation : voir `README.md`. Fonctionnement interne : voir `iris_encode_spec.md`.

---

## 0. Ouvrir l'application

**Le raccourci « IRIS ENCODE » du Bureau**, s'il a été créé. C'est le seul
chemin qui garantit le bon terminal : un raccourci visant `launch.bat`
directement ouvre la console héritée de Windows, au rendu dégradé — bordures
approximatives, glyphes manquants.

Pour le créer, une fois l'installation faite : double-clic sur
**`launcher\build.bat`**, qui compile le lanceur et propose le raccourci.
Détail et alternative sans exécutable au **README § 5.1**.

À défaut, `launch.bat` fonctionne — de préférence lancé *depuis* Windows
Terminal plutôt qu'au double-clic.

**Quand une nouvelle version est publiée**, le lancement le dit avant d'ouvrir
l'application :

```
  Mise à jour disponible : v0.8.9.1 → v0.9.0.0
  Installer maintenant ? [O/n]
```

`Entrée` installe, puis l'application redémarre sur la version neuve ; `n`
remet à plus tard (la question revient au lancement suivant). Vos réglages,
vos profils et les outils de `bin/` ne sont jamais touchés. Hors ligne, rien ne
s'affiche. Pour installer sans question ou ne plus rien vérifier : `app =
"auto"` ou `app = "off"` sous `[updates]` dans `config.toml`. Détail au
**README § 5.2**.

---

## 1. Le parcours en trois temps

```
Browser  ──F1──>  Aperçu  ──F2──>  Encodage
   │                                  
   └──T──>  Pistes  ──F9──>  Recalage  ──F3──>  Mux
```

**Toujours passer par l'aperçu.** Il montre ce qui *va* se produire — codec,
débit, conteneur, taille estimée, durée d'encodage — avant d'y consacrer des
heures. C'est là qu'on repère un conteneur inattendu ou un fichier qui n'aurait
pas dû être sélectionné.

Deux opérations distinctes, à ne pas confondre :

| | Ce que ça fait | Quand |
|---|---|---|
| **Encoder** (`F2`) | Réencode la vidéo, absorbe les pistes greffées dans la même passe | On veut réduire la taille |
| **Muxer** (`F3`) | Greffe les pistes sans toucher à la vidéo | On veut juste ajouter une VF |

Muxer n'est **pas** une étape préalable à l'encodage : `F2` fait les deux en
une passe. Voir § 4.6 pour la seule exception.

---

## 1bis. L'assistant

L'application s'ouvre en **mode assistant** : un fichier à la fois, cinq étapes,
`↵` pour avancer et `⌫` pour revenir.

Le mode se lit à trois endroits, parce qu'il change ce que fait `↵` sur un
fichier : la barre de profil (`[W] Assistant`), le libellé de la touche `W` dans
le pied de page, et **la couleur de ce pied de page** — le mode manuel garde le
bleu habituel, l'assistant prend l'accent du thème.

`W` bascule entre assistant et parcours libre. Le choix tient pour la session.

Dans la liste, `↵` sur un fichier ouvre le parcours :

| Étape | Ce qu'on y fait |
|---|---|
| 1 — Fichier | Vérifier le fichier et le profil actif |
| 2 — Décision | Codec (`F6`), débit (`F7`), pistes à garder (`Espace`) — tout sur le même écran, et le nom du fichier qui sortira |
| 3 — Pistes externes | `F9` présente un fichier portant une VF ou des sous-titres, `D` retire la dernière |
| 4 — Lancer | `↵` prend le choix recommandé ; `F3` force le mux, `F2` force l'encodage |
| 5 — Terminé | Le résultat, `↵` ramène à la liste |

**La mesure du décalage est automatique.** Dès qu'une piste est ajoutée, elle
est mesurée, et le décalage trouvé sur l'audio est reporté sur les sous-titres
venus du même fichier. Vous n'avez rien à lancer.

Si la mesure échoue — montage différent, piste trop courte — le décalage reste à
zéro et l'assistant le dit. Passez alors par le parcours libre (`W`), où l'écran
de recalage offre `G`, `P`, `C` (§ 4.5) et le point de repère `R` (§ 4.5bis).

**En mode manuel**, `↵` sur un fichier ouvre l'écran des pistes, et le parcours
reste celui décrit ci-dessous.

---

## 2. Écran par écran

### 2.1 Browser — navigation et sélection

Le point d'entrée. Une ligne par fichier, avec sa décision d'encodage calculée
d'après le profil actif.

| Touche | Action |
|---|---|
| `↵` | Sur un dossier : l'ouvrir. Sur un fichier : **ouvrir l'assistant**, ou l'écran des pistes en mode manuel |
| `W` | Basculer **assistant / manuel** — change ce que fait `↵` sur un fichier |
| `⌫` | Remonter |
| `Espace` | Cocher / décocher le fichier |
| `A` / `N` | Tout cocher / tout décocher |
| `T` | Écran des pistes du fichier sous le curseur, quel que soit le mode |
| `V` | Ouvrir dans mpv |
| `Ctrl+D` | **Supprimer définitivement** le fichier (confirmation, pas de corbeille) |
| `F1` / `F2` | Aperçu / Encoder la sélection |
| `R` | Encoder récursivement le dossier sous le curseur |
| `F4` / `F5` | Choisir un profil / gérer les profils |
| `J` | **Joindre** les fichiers cochés bout à bout en un seul (§ 2.1bis) |
| `I` | Fiche du film : AlloCiné, puis IMDB avec `Tab` |
| `Tab` / `Maj+Tab` | Colonne suivante / précédente |
| `<` / `>` | Rétrécir / élargir la colonne choisie (largeurs mémorisées) |

La colonne **Décision** dit ce qui sera fait : `HEVC`, `H264`, `AV1` ou `SKIP`.
Un fichier `SKIP` est déjà assez compressé — le cocher quand même le force à
l'encodage au débit de la source. **La colonne le montre dès la coche** : la
décision forcée remplace `← SKIP`, en orange, et un message le rappelle. Même
chose pour une ligne `→ HDR10` (retrait du Dolby Vision) : cochée, elle est
réencodée. `F1` et `F2` sans rien de coché le disent au lieu de ne rien faire.

**Au retour d'un encodage**, la liste est relue — les sorties apparaissent — et
les fichiers réussis sont décochés. Un fichier en échec ou interrompu reste
coché, prêt à relancer.

**Ce que l'application a encodé se reconnaît à son nom.** Toute sortie finit
par `-iris`, précédée de ce que le traitement a fait : `Film.2160p.hevc-iris.mkv`,
`Film.720p.h264-iris.mp4`, `Film.av1-iris.mkv`, `Film.dv-iris.mkv` (Dolby Vision
conservé), `Film.hdr10-iris.mkv` (RPU retiré). Une caractéristique que le nom
porte déjà n'est pas répétée — `Film.2160p.DV` sort `Film.2160p.DV-iris`. Ces
fichiers sont grisés dans la liste et écartés du scan récursif et de `A` : les
reproposer reviendrait à offrir de réencoder par-dessus un fichier déjà traité,
avec la perte de génération que cela implique.

Un `.mux-iris` fait exception et **reste proposé** : ce n'est pas un encodage
mais une greffe de pistes, et l'encoder ensuite est un enchaînement normal. Un
`.join-iris` aussi, et pour une raison plus forte encore : un fichier collé
n'existe que pour être encodé ensuite (§ 2.1bis).

**Le groupe de la release ne suit pas.** Le dernier terme d'un nom de release,
détaché par un tiret — `Film.1080p.x265-GROUPE`, `Film 1080p - GROUPE` —
signe la source ; la sortie le perd : `Film.1080p.hevc-iris.mkv`. Il ne part
que si le reste du nom porte une marque de release (`1080p`, `x265`, `HDR`,
`BluRay`, `MULTi`…) et s'il n'en est pas une lui-même : `Spider-Man.mkv`,
`Titre - Sous-titre.mkv`, `Film.1080p.DTS-HD.mkv` gardent leur fin.

> Depuis la v0.8.8.11, les anciens noms (`_[hevc]`, `_[av1]`…) ne sont plus
> reconnus : ils se traitent comme des sources ordinaires. Réencodé, un
> `Film_[hevc]` sort `Film.hevc-iris`.

> Depuis la v0.8.9.44, la marque est `-iris` (elle était `.IRIS`). Les
> sorties à l'ancienne marque ne sont plus reconnues : elles redeviennent des
> sources, et un réencodage garde leur `.IRIS` dans le nom —
> `Film.1080p.hevc.IRIS` sort `Film.1080p.IRIS.hevc-iris`.

> Avant la v0.8.5.1, seuls `_[hevc]` et `_[H264]` étaient reconnus. Une sortie
> AV1 reparaissait donc dans la liste, et comme l'AV1 n'est pas un codec que la
> chaîne sait relire, elle était classée « à réencoder en HEVC » — avec, sur un
> profil `⚠ suppr.`, l'effacement de l'AV1 d'origine.

### 2.1bis Jonction — recoudre un film livré en parties

Un film en `part1` / `part2` ne s'encode pas tel quel : chaque partie prise
seule sortirait de son côté, et vous auriez deux fichiers là où il en faut un.
`J`, sur l'accueil, recoud d'abord — ensuite le fichier se travaille comme
n'importe quel autre.

**Cocher les parties avec `Espace`** (deux au minimum), puis `J`.

| Touche | Action |
|---|---|
| `Ctrl+↑` / `Ctrl+↓` | Déplacer d'un rang la partie sous le curseur |
| `F2` | Joindre — lancer la jonction |
| `⌫` | Retour à l'accueil — une jonction en cours est interrompue et son fichier partiel effacé |

**L'ordre est la seule chose à vérifier.** Il est déduit des noms, et les
nombres y comptent comme des nombres : `part10` arrive bien après `part2`, là
où un tri alphabétique le glisserait entre `part1` et `part2`. Le tableau est
ce qui sera collé — s'il est faux, `Ctrl+↑/↓` le corrigent. Deux parties
inversées produisent un fichier de la **bonne durée**, donc faux sans que rien
ne vous le signale.

La colonne **Jonction** dit, ligne par ligne, si la partie s'apparie sur la
première :

| Ce qui s'affiche | Ce que ça veut dire |
|---|---|
| **référence** | La première partie. C'est elle qui donne au fichier produit ses codecs, sa définition et son jeu de pistes |
| **✓** | Elle s'y colle sans rien perdre |
| **✓ avec réserve** | Elle s'y colle, mais elle porte plus (ou moins) de pistes audio ou de sous-titres : seuls les rangs communs survivront. Le détail s'affiche sous le tableau |
| **✗ incompatible** | Codec vidéo, définition ou format audio différents — `F2` est refusé |

La colonne du nom de fichier est aussi large que celle de l'accueil : si vous
l'y avez élargie (`Tab` puis `>`), l'écran de jonction en profite.

La jonction **ne réencode rien** : mkvmerge recale les horodatages de chaque
partie sur la fin de la précédente. C'est une copie disque — comptez le temps
d'écrire la somme des parties, et prévoyez la place, les originaux restant en
place.

**Rien n'est effacé.** Les parties sont conservées ; `Ctrl+D` sur l'accueil
reste le seul geste qui supprime. Le fichier produit s'appelle
`<nom commun>.join-iris.mkv` — `Film part1.mkv` + `Film part2.mkv` donnent
`Film.join-iris.mkv` — et la jonction refuse d'écraser un fichier existant.

À la fin, l'écran compare la durée obtenue à la somme des parties. Un écart
est annoncé plutôt que passé sous silence : un mkvmerge interrompu laisse un
fichier lisible et **court**, qui passerait sinon pour une jonction réussie.

`⌫` ramène à l'accueil, où le fichier collé apparaît avec sa décision — à
partir de là, `F1`, `F2`, `T` et le reste valent pour lui comme pour les
autres.

### 2.2 Pistes — choisir ce qu'on garde

Depuis le browser par `T`. Une ligne par piste audio et sous-titre, plus une
ligne vidéo en tête.

| Touche | Action |
|---|---|
| `Espace` | Garder / écarter la piste |
| `↵` | Valider le choix de la ligne |
| `←/→` `+/-` | Sur la ligne vidéo : changer codec, débit, traitement Dolby Vision |
| `F6` / `F7` | Codec / débit cible |
| `F8` | Supprimer ou garder le fichier source après encodage |
| `F9` | **Greffer une piste externe** — mène au choix du donneur |
| `F4` | Changer de profil |
| `F1` / `F2` | Aperçu / Encoder ce seul fichier, sans repasser par la liste |

Écarter tous les sous-titres image (PGS, VobSub) libère le conteneur MP4 ;
en garder un impose le MKV.

Un PGS forcé qu'un SRT forcé de même langue double arrive **décoché** : Jellyfin
l'incrusterait, donc transcoderait, pour afficher ce que le SRT dit déjà. Seul
forcé de sa langue, il reste coché. Le recocher à la main suffit à le garder.

### 2.3 Choix du donneur

Après `F9`. On choisit d'abord le fichier qui porte la piste à greffer, puis
ses pistes dans ce fichier. Le fichier de travail est exclu de la liste.

`↵` choisit le fichier, puis `Espace` coche les pistes à greffer et `↵` valide.
`Esc` annule. Une piste seule est présélectionnée. Plusieurs donneurs
s'enchaînent sans quitter l'écran suivant.

**Pas de sous-titre sur le disque ? `O` le cherche sur OpenSubtitles.com**,
dans les langues de sous-titres du profil. Les lignes marquées `≡` ont été
déposées pour cette release exacte : elles sont déjà synchronisées, prenez-les
en priorité. `SME` signale un sous-titre pour sourds et malentendants. `↵`
télécharge la ligne ; le fichier revient ici comme si vous l'aviez choisi, et
la suite est la même — piste présélectionnée, langue déduite, recalage.

Il faut une clé d'application et un compte (gratuits, 20 téléchargements par
jour). Au lancement, si la clé manque, une fenêtre la demande : **Obtenir une
clé** ouvre opensubtitles.com/consumers, on colle la clé, l'identifiant et le
mot de passe, **Vérifier et enregistrer** (ou `Ctrl+S`) les vérifie auprès d'OpenSubtitles et les enregistre.
Pour les saisir ou les changer plus tard : `F5`, puis `K` (§ 2.7).

Sans eux, l'écran dit ce qui manque. Le `.srt` est écrit dans le dossier
temporaire, pas à côté du film : il n'existe que pour la greffe.

**Lisez la colonne Nom jusqu'au bout.** Un rip livre couramment six pistes
françaises : France et Canada, chacune en normal, `(forced)` et `(SDH)`. Elles
ont le même codec et la même langue — **le nom est la seule chose qui les
sépare**, et il est affiché en entier.

Une piste `(forced)` ne contient que les répliques en langue étrangère :
vingt-trois sur un épisode. Choisie par erreur, elle apparaît dans le lecteur
et n'affiche presque jamais rien. C'est en général la **première** de la liste.

### 2.4 Recalage — l'écran qui demande le plus d'attention

Une ligne par piste greffée. Les champs se parcourent avec `←/→`, les valeurs
se changent avec `+/-`.

**La première ligne du bandeau dit ce que fait le champ sous le curseur**, et
elle ne s'efface jamais — ni pour un avertissement, ni pour un compte rendu de
mesure, qui prennent les lignes suivantes. C'est là qu'on lit quelles touches
modifient la valeur affichée, et elles diffèrent d'un champ à l'autre : seul le
décalage a trois pas, les autres champs font défiler leurs valeurs.

| Touche | Action |
|---|---|
| `←/→` | Champ précédent / suivant |
| `Ctrl+↑/↓` | ±10 ms sur le décalage — pour finir d'approcher une valeur mesurée |
| `+/-` | ±100 ms sur le décalage, valeur suivante sur les autres champs |
| `Maj+↑/↓` | ±1 s sur le décalage |
| `↵` | Liste de valeurs du champ courant |
| `M` | **Mesurer** le décalage automatiquement |
| `F` | Forcer le candidat d'une mesure refusée |
| `G` | Détail des **plages** détectées |
| `P` | **Appliquer les plages** à la piste sous le curseur |
| `C` | Reprendre le décalage d'une autre piste |
| `R` | **Point de repère** — quand la mesure ne conclut pas (§ 4.5bis) |
| `V` | Contrôler dans mpv |
| `K` | Extrait de contrôle réellement muxé |
| `D` | Retirer la piste |
| `F9` | Ajouter une autre piste |
| `F1` `F2` `F3` | Aperçu / Encoder / Muxer |

**La langue est obligatoire.** Sans elle, la piste sortirait en « und » dans
tous les lecteurs, et le mux est refusé. L'écran ouvre directement sur ce champ
quand une piste en manque.

**Le report est automatique.** Une mesure réussie sur une piste audio
s'applique aussitôt aux sous-titres venus du **même fichier** : leur bon
décalage *est* celui de l'audio, puisqu'ils ont été écrits sur son timing. Le
bandeau annonce combien de pistes ont suivi, et leur colonne d'origine affiche
« repris de #N ».

Deux pistes ne suivent jamais : celles d'un **autre fichier**, et celles que
vous avez déjà mesurées ou réglées à la main — une décision prise ne s'écrase
pas. `C` sert pour ces cas-là.

### 2.5 Aperçu — ce qui sera fait

| Touche | Action |
|---|---|
| `Espace` | Inclure / exclure la ligne |
| `F6` / `F7` | Changer codec / débit **de cette ligne seulement** |
| `F2` | Lancer l'encodage — `↵` ne lance rien, par sécurité |

Les colonnes **Estim. (Δ%)** et **ETA** — la durée d'encodage prévue —
reposent sur une moyenne
mobile de vitesse relevée à chaque encodage : elles s'affinent à l'usage et
sont approximatives aux premières passes.

### 2.6 Encodage — la file

**L'encodage ne bloque plus la navigation.** `F2` — depuis l'accueil, l'aperçu,
les pistes, le recalage ou l'assistant — met les fichiers dans **une file**, qui
démarre dès qu'elle a une entrée et les traite dans l'ordre. Pendant qu'elle
tourne, revenez aux fichiers (`⌫` ou `F12`), choisissez-en d'autres et `F2` :
ils s'ajoutent à la suite. `F12` bascule entre les fichiers et la file. Tant
qu'un lot existe, l'en-tête l'annonce au centre, sur tous les écrans :
« F12 Encodages en cours · 1/3 · 42 % », puis « F12 Lot terminé » ; depuis la
file, « F12 Fichiers ».

- Un fichier déjà dans la file est refusé, avec un message.
- Chaque fichier garde les réglages qu'il avait au moment de l'ajout : changer
  de profil ensuite ne le touche pas.
- Les fichiers confiés se décochent sur l'accueil.
- Un fichier en file ou en cours ne peut pas être supprimé (`Ctrl+D`).
- Quitter (`F10`) dit combien de fichiers attendent encore.

| Touche | Action |
|---|---|
| `P` | Pause / reprendre |
| `S` | Passer le fichier en cours, sans annuler le reste |
| `Ctrl+↑` / `Ctrl+↓` | Avancer / reculer d'un rang le fichier en attente sous le curseur |
| `Suppr` | Retirer de la file le fichier en attente sous le curseur |
| `X` | **Arrêter tout** — le fichier en cours et la file ; confirmation demandée |
| `E` | **Après le lot** — mettre en veille, en veille prolongée ou éteindre la machine une fois tout fini |
| `⌫` / `Esc` / `F12` | Revenir aux fichiers — **l'encodage continue** |

Une fois le lot fini, le pied de page ne garde que la navigation, et la zone du
bas fait le bilan : réussis, en échec, ignorés, puis le chemin de chaque
fichier produit. Si vous étiez dans les fichiers, une notification l'annonce ;
le bilan attend que vous l'ayez vu (`F12`), puis s'efface quand vous quittez la
vue. Un nouvel ajout démarre un nouveau lot.

**La machine ne se met plus en veille pendant un traitement** — encodage, mux,
jonction, mesure ou recalage. L'en-tête affiche alors « ☾ veille bloquée ».
L'écran peut toujours s'éteindre, et une veille demandée à la main (menu
Démarrer, capot fermé) passe quand même. Se désactive dans les options
(`F5`, `U`).

**Après le lot** (`E`) : une fois **tous** les traitements finis, la machine
se met en veille, en veille prolongée ou s'éteint — au choix, dans les
options. L'en-tête l'annonce (« ☾ … · puis arrêt »). Un compte à rebours de
60 s le précède : `↵` sur « Annuler » (présélectionné) ou `Esc` l'arrête.
L'interrupteur repart décoché à chaque nouveau lot, et un lot arrêté par `X`
ne déclenche rien. Windows seulement.

### 2.7 Profils (`F5`)

`N` crée, `E` édite, `D` supprime, `↵` active. `U` ouvre les **options** :
bloquer la mise en veille pendant les traitements (activé par défaut), et ce
que fait la machine après un lot dont on a coché « Après le lot ». `K` ouvre les **clés d'API**
des services en ligne — OpenSubtitles et OMDb (fiche IMDB complète) : chaque
service a son bouton vers la page qui délivre la clé, et une clé est vérifiée
auprès du service avant d'être enregistrée. La même fenêtre s'ouvre au
lancement tant qu'une clé manque ; « Ne plus demander » l'écarte pour ce
service. La liste est exactement celle
de `profiles.toml`, dans l'ordre du fichier : vous pouvez l'éditer à la main,
l'application ne rajoute ni ne réordonne rien. Tous les profils s'effacent,
sauf le dernier de la liste. Renommer un profil se fait dans le fichier : le
champ **Nom** du formulaire ne se saisit qu'à la création. Un profil marqué `⚠ suppr.` efface le fichier
source après un encodage réussi — à vérifier avant de lancer un lot.

---

## 3. Cas d'usage

### 3.1 Ajouter une VF et ses sous-titres à une VO

**Avant tout, regardez ce que la cible contient déjà.** Un rip streaming
embarque souvent trente sous-titres, français compris : il n'y a alors qu'une
piste audio à greffer, et aucun recalage de sous-titre à faire. L'écran des
pistes (`T`) les liste toutes.

1. Browser : curseur sur le film, `T`.
2. `F9`, choisir le fichier qui porte la VF, puis ses pistes.
3. Sur l'écran de recalage, curseur sur la piste **audio**, `M`.
4. **Les sous-titres se recalent après l'audio, jamais avant** : c'est sa
   mesure qui leur sert de référence. Selon ce qu'elle a rendu —

   | Résultat de la mesure | Sur chaque sous-titre |
   |---|---|
   | `✓` ou `⚠` (§ 4.1, § 4.2) | **rien — le report est automatique** |
   | `✗ montage différent — N plages` (§ 4.5) | `P` — et `P` aussi sur l'audio |
   | `✗ trop peu de repères` (§ 4.3) | rien, sauf autre donneur → `C` |
   | `✗ sous-titre image` (§ 4.4) | rien, sauf autre donneur → `C` |
   | `✗ aucun alignement commun` (§ 4.5bis) | `R` — donner un point de repère |

   Une mesure réussie se **reporte d'elle-même** sur les sous-titres venus du
   même fichier : leur colonne d'origine passe à « repris de #N ». C'est
   voulu — des sous-titres livrés avec une VF sont écrits sur le timing de
   cette VF, donc leur bon décalage **est** le sien.

   Le report ne touche jamais une piste que vous avez déjà réglée, ni une
   piste venue d'un autre fichier. Pour celles-là, `C` reste là.
5. Renseigner la **langue** de chaque piste si elle manque.
6. `V` ou `K` pour contrôler.
7. `F3` pour muxer sans réencoder, ou `F2` pour réencoder aussi la vidéo.

### 3.2 Réencoder toute une arborescence selon le profil

Pour une saison entière, ou une bibliothèque rangée en sous-dossiers.

1. Placez le curseur **sur un dossier** — `R` ne fait rien sur un fichier.
2. `R`, puis confirmez. Tous les fichiers vidéo du dossier **et de ses
   sous-dossiers**, sans limite de profondeur, sont analysés avec le profil
   actif.
3. L'aperçu s'ouvre sur le résultat. `Espace` retire une ligne, `F6` et `F7`
   changent le codec ou le débit **de cette ligne seulement**.
4. `F2` lance.

Deux choses à savoir avant de lancer :

- **Les fichiers déjà assez compressés sont écartés** de la liste. L'aperçu ne
  montre que ce qui sera réellement encodé — si un fichier manque, c'est qu'il
  n'avait rien à gagner.
- **Aucune sélection manuelle de pistes.** Les décisions viennent du profil, y
  compris le sort des langues. Vérifiez-les sur un fichier seul (`T`) avant de
  lancer un lot.

Un profil marqué `⚠ suppr.` efface chaque source après un encodage réussi. Sur
une arborescence entière, relisez ce point deux fois.

### 3.3 Rendre lisible un 4K Dolby Vision qui bloque à la lecture

Certains lecteurs — dont les clients webOS — refusent la lecture directe d'un
Dolby Vision profil 8 et basculent en transcodage, avec des coupures de son.
Retirer le DV **améliore** la lecture, contrairement à ce qu'on croirait.

Avec un profil réglé sur `dolby_vision = hdr10` (`F5`, champ **DV**), une source
DV que le profil n'a aucune raison de réencoder sort en `.hdr10-iris.mkv` ou
`.hdr10-iris.mp4`, selon ce que ses pistes permettent :

- le RPU est retiré, **aucune image n'est recalculée** ;
- le HDR10+ éventuel survit, ce qu'aucun réencodage ne permet ;
- comptez deux à trois minutes pour un film de 15 Go, contre plusieurs heures.

La colonne **Décision** affiche `→ HDR10` sur ces fichiers. C'est le cas le plus
rentable de l'application : beaucoup gagné, presque rien dépensé.

### 3.4 Alléger un Dolby Vision sans le perdre

Un profil réglé sur `dolby_vision = dv` (`F5`, champ **DV**) garde le Dolby
Vision. Jusqu'à la v0.8.8.0 il gardait aussi le débit : la vidéo était recopiée
telle quelle, et un film de 60 Mb/s ressortait à 60 Mb/s. Désormais
l'application sort les métadonnées DV avant l'encodage et les remet après.

La colonne **Décision** distingue les deux cas :

| Ce qui s'affiche | Ce qui se passe |
|---|---|
| `→ HEVC → DV` | la vidéo est réencodée au débit du profil, le Dolby Vision est conservé |
| `→ DV (copie)` | la vidéo est recopiée — le débit du profil ne s'applique pas |

Quand vous voyez `→ DV (copie)`, la colonne **Raison** dit pourquoi. Trois
causes possibles :

- **le profil demande un downscale** (`keep_4k` décoché sur une source 4K). Les
  métadonnées DV décrivent le cadrage image par image : redimensionner les rend
  fausses. Cochez `keep_4k` pour que le réencodage soit possible.
- **la source est en Dolby Vision profil 5 ou 8.4.** Leur couche de base n'est
  pas du HDR10 ; il n'y a rien à quoi rattacher les métadonnées. Rien à faire —
  sinon passer le profil en `hdr10` ou `sdr` si la taille prime.
- **dovi_tool ou mkvmerge manquent.** Relancez le preflight.

À savoir avant de lancer un lot :

- **la sortie est toujours un `.mkv`**, même si le profil demande du MP4 — le
  MP4 ne porte pas ces métadonnées sans réécriture ;
- **comptez deux fois la taille de la vidéo encodée en espace disque
  temporaire**, à côté du fichier source. Les fichiers sont effacés à la fin,
  que l'encodage réussisse ou non ;
- **l'encodage est plus long** qu'un encodage ordinaire : trois passes sur le
  flux s'ajoutent à l'encodage lui-même.

> Le premier fichier produit mérite un contrôle sur votre téléviseur : la chaîne
> est vérifiée sur des extraits courts, pas encore sur un film entier.

### 3.5 Ne garder que certaines langues

Un rip streaming embarque couramment deux pistes audio et **quarante
sous-titres**. Le profil décide ce qui traverse.

`F5`, puis `E` sur le profil :

| Champ | Effet |
|---|---|
| **Langues** | Pistes audio conservées, par code ISO — `fre, eng` |
| **Langues sous-titres** | Idem pour les sous-titres. **Vide = toutes** |

Les deux jeux de codes ISO sont réconciliés : écrire `fre` retient aussi les
pistes étiquetées `fra`, et de même pour `ger`/`deu`, `dut`/`nld`, `cze`/`ces`.

La première piste audio est toujours gardée, quelle que soit sa langue : c'est
la piste d'origine, et la perdre serait perdre le film.

Pour un contrôle piste par piste sur un seul fichier, `T` puis `Espace` — le
profil ne décide que du cas général.

### 3.6 Recaler un sous-titre trouvé sur internet

Un `.srt` téléchargé n'est presque jamais synchronisé sur votre fichier.

1. Sur le film, `T` puis `F9`, et choisissez le `.srt`.
2. Sur l'écran de recalage, `M` sur la ligne du sous-titre.
3. Selon ce que la mesure rend, voir § 4 — et si elle ne conclut pas du tout,
   `R` donne un point de repère (§ 4.5bis).
4. `V` pour contrôler à l'œil, `K` pour un extrait réellement muxé.
5. `F3` muxe sans réencoder — quelques minutes, image intacte.

Un sous-titre est corrigé **exactement** : il n'y a que des nombres à décaler,
rien à rééchantillonner. C'est ce qui rend ce cas beaucoup plus sûr qu'un
recalage audio.

---

## 4. Les cas rencontrés

### 4.1 « ✓ +2450 ms (confiance excellente) »

Le cas nominal. Le décalage est posé. Un contrôle `V` reste une bonne habitude
mais n'est pas indispensable.

La confiance se lit en mots — **aucune**, **faible**, **moyenne**,
**excellente** — et non en nombres : le seuil d'acceptation varie avec le
nombre de répliques mesurées, si bien qu'un même chiffre n'a pas le même sens
d'une mesure à l'autre. « Moyenne » ou « excellente » signifie que la mesure a
été retenue ; « faible » ou « aucune », qu'elle a été refusée.

**Les sous-titres ne sont pas recalés pour autant** : la mesure ne vaut que
pour la ligne sur laquelle elle a tourné. Curseur sur chaque sous-titre, `C`,
puis choisir la piste audio (§ 3, étape 4).

### 4.2 « ⚠ … — à vérifier »

La corrélation est moyenne et les tiers n'ont pas tranché. La valeur est
appliquée mais **contrôlez avant de muxer** : `V` pour l'oreille, `K` pour un
extrait réellement muxé.

### 4.2bis « ⚠ … → durées écartées de N % »

La mesure a trouvé un décalage cohérent, mais les deux fichiers ne durent pas
la même chose à plus de **6 %** près. C'est beaucoup : deux copies d'un même
film ne diffèrent que par leurs génériques.

Le décalage trouvé peut être juste — un donneur amputé de son générique de fin
reste alignable sur toute sa longueur. Il peut aussi signaler que vous avez
pris **le mauvais fichier**, ou une autre version du film. `K` tranche en
quelques minutes : un extrait muxé en fin de film montre immédiatement si
l'alignement tient jusqu'au bout.

> Cet avertissement existait depuis longtemps mais **n'était affiché nulle
> part** avant la v0.8.5.1 : il était rangé avec les messages d'échec, que
> l'application ne lit que sur une mesure refusée. Un donneur d'un autre
> montage passait donc en silence.

### 4.3 « ✗ trop peu de repères »

Le sous-titre est trop court pour être mesuré — typiquement une piste de
**forcés**, qui ne contient que quelques répliques. Ce n'est pas une erreur.
Utilisez `C` pour reprendre le décalage de la piste audio.

### 4.4 « ✗ sous-titre image (PGS, VobSub) »

Ces sous-titres sont des images, sans texte à corréler. Aucune mesure n'est
possible ; réglez le décalage à la main ou par `C`.

### 4.5 « ✗ montage différent — N plages »

Les deux fichiers portent le même contenu dans deux montages différents —
typiquement un rip broadcast, dont les coupures publicitaires décalent tout ce
qui suit, face à un rip streaming.

**Procédure :**

1. `G` pour voir les plages. Des paliers réguliers (par exemple cinq fois
   +2 000 ms) confirment le diagnostic ; des valeurs erratiques signifient
   plutôt que les fichiers n'ont rien à voir.
2. Curseur sur la piste **audio**, `P`. Le recalage prend quelques minutes —
   décodage puis réencodage, avec barre de progression.
3. Curseur sur chaque **sous-titre**, `P`. Instantané.
4. `V` ou `K` pour contrôler, puis `F2` ou `F3`.

Les plages restent en mémoire tant qu'aucune nouvelle mesure n'est lancée :
une seule détection, sur l'audio, sert aux trois pistes. C'est le chemin le plus
sûr — le signal d'une piste audio est dense, celui d'un sous-titre est creux.
L'application sait tout de même retrouver des plages sur un sous-titre seul,
mais elle y arrive moins souvent ; si elle n'y parvient pas, `R` (§ 4.5bis).

Si le compte rendu signale « aucun silence trouvé » sur une frontière,
l'insertion a été posée sur la position estimée. Rien n'est perdu, mais cette
zone mérite une écoute.

Si le compte rendu signale « point d'insertion en retrait sur le précédent,
repoussé de N s », deux frontières étaient trop proches pour que le silence de
chacune tienne : la seconde a été décalée juste après la première. La durée
insérée est intacte, seul son emplacement bouge — écoutez cette jonction.

> **Sur une piste audio produite par `P` avant la v0.8.4.5** : deux points
> d'insertion pouvaient se croiser, et le passage compris entre eux se
> retrouvait alors **deux fois** dans la piste. Le fichier passait tous les
> contrôles. Si vous entendez une réplique répétée sur une greffe ancienne,
> c'est cela : relancez `P` avec cette version.

> **Le recalage se figeait parfois** avant la v0.8.4.4 — barre d'avancement
> bloquée, sans message, sans autre issue que de quitter l'application. C'était
> ffmpeg suspendu sur un tube d'erreur plein. Corrigé.

### 4.5bis Rien n'y fait — le point de repère (`R`)

Certains sous-titres ne se mesurent pas, quel que soit le réglage. Le cas
typique : un `.srt` communautaire dont **l'adaptation du texte diffère de celle
du doublage**. Les répliques sont découpées et condensées autrement, donc leur
rythme ne décalque pas celui de la parole — mesuré sur un cas réel, la
corrélation y plafonne à moins de la moitié du seuil *même parfaitement
alignée*.

La corrélation reste pourtant utilisable si on lui dit **où** chercher.

1. `R` **propose une réplique** et l'instant où elle est écrite. `↓` et `↑` en
   proposent une autre, si celle-ci ne se retrouve pas.
2. Écoutez le film à cet endroit, et donnez l'instant où vous l'entendez
   réellement. Formats acceptés : `13:22`, `1:13:22`, `13:22,5`, `802`.
3. La recherche se centre sur l'écart entre les deux. Elle retrouve alors le
   décalage, et les plages s'il y a plusieurs coupures.

Si l'analyse trouve un décalage **très différent** de celui que vous avez
donné, elle le dit et n'applique rien : c'est le signe que l'un des deux
instants est faux. Revérifiez-les plutôt que d'insister.

### 4.6 « demande un facteur d'étirement »

Une source PAL accélérée (25 vs 23,976 images/s) dérive au lieu d'être
simplement décalée. mkvmerge sait l'étirer, ffmpeg non : la greffe passe
automatiquement par un mux préalable juste avant l'encodage. Rien à faire, sauf
si mkvmerge est absent — dans ce cas, relancez le preflight pour l'installer.

Un étirement ne se prévisualise pas dans mpv (`audio-delay` ne fait qu'un
décalage constant) : utilisez `K`, qui produit deux fenêtres, début et fin, la
dérive s'accumulant.

> **Vérifiez les fichiers produits par ce chemin avant la v0.8.4.3.** La piste
> greffée était bien muxée dans l'intermédiaire, puis **perdue** au moment du
> réencodage : l'application annonçait un succès et rendait un fichier sans la
> VF qu'on venait de recaler. Rien ne le signalait. Si un fichier étiré vous
> semble amputé, il l'est — refaites la greffe.

### 4.7 Le fichier produit ne se lit pas sur le téléviseur

Corrigé en v0.8.1.0 : un décalage négatif déplaçait toute la vidéo hors de
zéro, ce que les décodeurs matériels refusent parfois alors que mpv et VLC le
normalisent en silence. Si le problème persiste sur un fichier plus ancien,
réencodez-le avec cette version.

### 4.8 La suppression échoue sous Windows

`Ctrl+D` sur un fichier encore ouvert dans mpv échoue : Windows le tient
verrouillé. Fermez le lecteur et recommencez.

### 4.9 « → HDR10 » sur un fichier qui n'a rien à réencoder

La décision **`→ HDR10`**, en vert, n'est pas un encodage : c'est un retrait du
Dolby Vision. Elle apparaît quand le fichier est en DV **profil 8.1** (ou 7),
que le profil actif demande `dolby_vision = "hdr10"`, et qu'il n'y a par
ailleurs rien à réencoder — débit sous le seuil, résolution dans les clous.

En 8.1, la couche de base *est* déjà du HDR10 : il suffit d'en retirer les
métadonnées Dolby Vision. L'image ressort **identique au bit près**, le HDR10+
éventuel est conservé, et un film 4K de 5,7 Go y passe en un peu plus de deux
minutes — contre plusieurs heures pour un réencodage, qui abîmerait l'image et
perdrait le HDR10+. La sortie est un `<nom>.hdr10-iris.mkv` ou `.mp4` portant
les pistes retenues de la source ; un profil 7 sort toujours en MKV.

> **MP4 produits avant la v0.8.8.15 : à refaire.** Leur vidéo avait perdu ses
> horodatages. Sur téléviseur, la lecture démarrait sur le son seul, sans
> image, puis plantait. Relancez le retrait depuis la source ; les `.mkv` ne
> sont pas concernés.

Pour réencoder quand même, `F6` sur la ligne force le codec : la décision
repart du débit source.

Rien ne s'affiche si `dovi_tool` ou mkvmerge manque — le fichier reste en
`← SKIP` plutôt que de promettre une opération impossible.

### 4.10 La colonne « Débit » ne dit pas la même chose que mon explorateur

La colonne affiche le **débit vidéo seul**, tandis qu'un explorateur de
fichiers ou MediaInfo montre le débit du conteneur — audio et sous-titres
compris. Sur un film porteur d'une piste TrueHD, l'écart dépasse 40 %.

C'est voulu : le seuil que tu fixes dans un profil est un débit vidéo, et
c'est un débit vidéo que reçoit l'encodeur. Comparer un total à un seuil vidéo
enverrait au réencodage des fichiers dont l'image tient largement en dessous.

Pour retrouver le débit total, additionne les pistes : l'écran Pistes (`↵`)
donne le détail de chacune.

### 4.11 Une piste TrueHD ou DTS sort trop dégradée

Par défaut, une piste transcodée suit le forfait du profil : 448 kbps en AC3
pour du 5.1. C'est correct pour une source déjà compressée, généreux pour rien
sur un TrueHD à 3,5 Mbps.

Le champ **« TrueHD/DTS → débit source »** de l'écran Profils (`F5`, puis
éditer) change la règle pour ces pistes :

- **`none`** — le forfait s'applique, comportement d'origine.
- **`ac3`** — transcodage au débit de la source, plafonné à **640 kbps** :
  c'est le maximum de l'AC3, l'encodeur ramène tout le reste sans le dire.
- **`eac3`** — transcodage au débit de la source, plafonné à **6 144 kbps**.
  Un TrueHD à 3 501 kbps ressort en E-AC3 à 3 501 kbps.

L'E-AC3 est le bon choix pour un téléviseur récent : il est décodé nativement
et transporté en eARC vers une barre de son. L'AC3 reste le repli universel.

Une limite à connaître : les encodeurs AC3 et E-AC3 ne dépassent pas le 5.1,
une source 7.1 est donc repliée — la décision l'affiche (« → eac3 5.1 »).

Le titre de la piste est corrigé au passage : « ENG VO : TrueHD 5.1 » devient
« ENG VO : E-AC3 5.1 », et la mention Atmos disparaît puisqu'elle ne survit pas
à la conversion. Un titre qui ne parle pas du format (« English ») est laissé
tel quel.

Si tu veux au contraire garder la piste intacte, c'est `preserve_hd_audio`
qu'il faut cocher : la copie sans perte l'emporte sur ce réglage.

### 4.12 « libx265 indisponible ici » sur un profil 4K

Le profil `cinema_4k_quality` encode sur **processeur**, avec libx265 : c'est
ce qui lui permet d'injecter les métadonnées HDR10 statiques qu'attendent
certains téléviseurs, et qu'aucun encodeur de carte graphique n'expose.

Avant la v0.8.4.3, l'application ne vérifiait au lancement que les trois
encodeurs de la carte, et tenait pour indisponible tout ce qu'elle n'avait pas
essayé. Sur une machine équipée d'une carte graphique — donc sur presque
toutes — le profil était refusé avant même de commencer, au nom d'une mesure
qui n'avait pas eu lieu. Il fonctionne désormais.

Si le message persiste, c'est que votre ffmpeg est réellement construit sans
libx265 : `ffmpeg -encoders | findstr x265` le confirme. Utilisez alors
`cinema_4k_hd`, qui passe par la carte.

### 4.13 « NVENC refusé : ce ffmpeg exige le pilote NVIDIA … »

Au lancement, une alerte « Carte graphique » annonce que HEVC, H264 et AV1 par
la carte sont tous indisponibles. Chaque ffmpeg est compilé pour une version de
l'interface NVENC, qui exige un pilote minimal : un ffmpeg plus récent que le
pilote refuse toute la carte. Le numéro de ffmpeg ne suffit pas à le prévoir
(8.1.2 de gyan.dev exige le pilote 610, 8.1.3 de BtbN se contente du 597).

Deux sorties : mettre à jour le pilote NVIDIA à la version indiquée, ou
installer un ffmpeg plus ancien. L'application prend le ffmpeg du `PATH` avant
celui de `bin/`. Pour tester un ffmpeg :

```
ffmpeg -v error -f lavfi -i testsrc2=d=1 -c:v hevc_nvenc -f null -
```

Aucune sortie : il fonctionne.

### 4.14 Un outil optionnel manque

`dovi_tool`, `mkvmerge` et `mpv` sont optionnels : leur absence désactive une
fonction sans bloquer le lancement. Le preflight propose de les installer à
chaque démarrage ; répondez `o`, ou placez les binaires dans `bin/`.

---

## 5. Conventions communes à tous les écrans

- `⌫` ou `Esc` reviennent en arrière, partout.
- `Ctrl+Home` **ramène à la liste des volumes** — la racine — depuis
  n'importe quel écran : aperçu, encodage, mux, assistant, profils, pistes,
  recalage, et l'accueil lui-même. C'est ce qui permet d'enchaîner plusieurs
  fichiers sans remonter la pile un écran à la fois. La sélection est vidée. Depuis les **pistes** et le **recalage**, une confirmation est demandée :
  ces deux écrans portent un travail que le retour ne conserve pas — une
  sélection, une greffe, une mesure. Depuis l'**encodage** en cours aussi :
  confirmer arrête le lot entier et efface la sortie partielle. `Home` seule garde son rôle, aller à la
  première ligne de la table.
- `F10` quitte, toujours en dernier dans le pied de page. La confirmation dit
  ce qui tourne — encodage, mux, jonction, mesure — et ce que quitter lui fait,
  ou « Aucun traitement en cours ». Un encodage, un mux ou une jonction est
  arrêté et sa sortie partielle effacée.
- `Début` `Fin` `Page ↑` `Page ↓` naviguent dans les tables.
- Le pied de page range les raccourcis par rôle, du haut vers le bas :
  **propres à l'écran**, puis **globaux** (navigation, retour), puis les
  **touches de fonction** `F1` à `F10`, toujours en dernière ligne. Chaque
  bande s'enroule sur autant de lignes que la largeur l'impose ; aucun
  raccourci n'est masqué, même sur un écran étroit.
- Les largeurs de colonnes sont mémorisées dans `config.toml`, **sauf sur
  l'écran d'accueil** : celui-ci repart des valeurs par défaut à chaque
  lancement, pour offrir la même disposition d'une session à l'autre. Le
  redimensionnement y reste actif pendant la session.
- Les erreurs de scan sont journalisées dans
  `~/.iris_encode/iris_encode.log`.
- **Le lancement interroge le réseau une fois par jour** pour comparer vos
  outils aux dernières versions publiées. Pour le couper, mettez
  `check_on_startup = false` sous `[updates]` dans `config.toml` — et non sous
  `[ffmpeg]`, qui n'est pas la bonne section. Le réglage n'a d'effet que depuis
  la **v0.8.5.2** : il était jusque-là lu au mauvais endroit, donc sans jamais
  rien changer. Hors ligne, le lancement se poursuit sans attendre.
