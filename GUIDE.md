# IRIS ENCODE — Guide d'utilisation

**Version** : 0.8.1.23
**Date** : 2026-08-27

Installation : voir `README.md`. Fonctionnement interne : voir `iris_encode_spec.md`.

---

## 1. Le parcours en trois temps

```
Browser  ──F1──>  Dry-run  ──F2──>  Run
   │                                  
   └──T──>  Pistes  ──F9──>  Recalage  ──F3──>  Mux
```

**Toujours passer par le dry-run.** Il montre ce qui *va* se produire — codec,
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
| 4 — Lancer | `↵` prend le choix recommandé ; `M` force le mux, `E` force l'encodage |
| 5 — Terminé | Le résultat, `↵` ramène à la liste |

**La mesure du décalage est automatique.** Dès qu'une piste est ajoutée, elle
est mesurée, et le décalage trouvé sur l'audio est reporté sur les sous-titres
venus du même fichier. Vous n'avez rien à lancer.

Si la mesure échoue — montage différent, piste trop courte — le décalage reste à
zéro et l'assistant le dit. Passez alors par le parcours libre (`W`), où l'écran
de recalage offre `S`, `P`, `C` (§ 4.5) et le point de repère `R` (§ 4.5bis).

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
| `F1` / `F2` | Dry-run / Encoder la sélection |
| `F3` | Encoder récursivement le dossier sous le curseur |
| `F4` / `F5` | Choisir un profil / gérer les profils |
| `F7` / `F8` | Fiche AlloCiné / IMDB |
| `Tab` `<` `>` | Choisir une colonne, l'élargir, la rétrécir (largeurs mémorisées) |

La colonne **Décision** dit ce qui sera fait : `HEVC`, `H264`, `AV1` ou `SKIP`.
Un fichier `SKIP` est déjà assez compressé — le cocher quand même le force à
l'encodage au débit de la source.

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
| `F1` / `F2` | Dry-run / Encoder ce seul fichier, sans repasser par la liste |

Écarter tous les sous-titres image (PGS, VobSub) libère le conteneur MP4 ;
en garder un impose le MKV.

### 2.3 Choix du donneur

Après `F9`. On choisit d'abord le fichier qui porte la piste à greffer, puis
ses pistes dans ce fichier. Le fichier de travail est exclu de la liste.

`↵` choisit le fichier, puis `Espace` coche les pistes à greffer et `↵` valide.
`Esc` annule. Une piste seule est présélectionnée. Plusieurs donneurs
s'enchaînent sans quitter l'écran suivant.

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
| `A` | Forcer le candidat d'une mesure refusée |
| `S` | Détail des **plages** détectées |
| `P` | **Appliquer les plages** à la piste sous le curseur |
| `C` | Reprendre le décalage d'une autre piste |
| `R` | **Point de repère** — quand la mesure ne conclut pas (§ 4.5bis) |
| `V` | Contrôler dans mpv |
| `K` | Extrait de contrôle réellement muxé |
| `D` | Retirer la piste |
| `F9` | Ajouter une autre piste |
| `F1` `F2` `F3` | Dry-run / Encoder / Muxer |

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

### 2.5 Dry-run — la prévisualisation

| Touche | Action |
|---|---|
| `Espace` | Inclure / exclure la ligne |
| `F6` / `F7` | Changer codec / débit **de cette ligne seulement** |
| `F2` ou `↵` | Lancer l'encodage |

Les colonnes **Estim. (Δ%)** et **ETA** — la durée d'encodage prévue —
reposent sur une moyenne
mobile de vitesse relevée à chaque encodage : elles s'affinent à l'usage et
sont approximatives aux premières passes.

### 2.6 Run — l'encodage

| Touche | Action |
|---|---|
| `P` | Pause / reprendre |
| `S` | Passer le fichier en cours, sans annuler le reste |
| `⌫` | Retour (l'encodage continue) |

### 2.7 Profils (`F5`)

`N` crée, `E` édite, `D` supprime, `↵` active. Les profils intégrés sont
protégés en suppression. Un profil marqué `⚠ suppr.` efface le fichier source
après un encodage réussi — à vérifier avant de lancer un lot.

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

1. Placez le curseur **sur un dossier** — `F3` ne fait rien sur un fichier.
2. `F3`, puis confirmez. Tous les fichiers vidéo du dossier **et de ses
   sous-dossiers**, sans limite de profondeur, sont analysés avec le profil
   actif.
3. Le dry-run s'ouvre sur le résultat. `Espace` retire une ligne, `F6` et `F7`
   changent le codec ou le débit **de cette ligne seulement**.
4. `F2` lance.

Deux choses à savoir avant de lancer :

- **Les fichiers déjà assez compressés sont écartés** de la liste. Le dry-run ne
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
DV que le profil n'a aucune raison de réencoder sort en `_[hdr10].mkv` :

- le RPU est retiré, **aucune image n'est recalculée** ;
- le HDR10+ éventuel survit, ce qu'aucun réencodage ne permet ;
- comptez deux à trois minutes pour un film de 15 Go, contre plusieurs heures.

La colonne **Décision** affiche `→ HDR10` sur ces fichiers. C'est le cas le plus
rentable de l'application : beaucoup gagné, presque rien dépensé.

### 3.4 Ne garder que certaines langues

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

### 3.5 Recaler un sous-titre trouvé sur internet

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

1. `S` pour voir les plages. Des paliers réguliers (par exemple cinq fois
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
perdrait le HDR10+. La sortie est un `<nom>_[hdr10].mkv` portant toutes les
pistes de la source.

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

### 4.12 Un outil optionnel manque

`dovi_tool`, `mkvmerge` et `mpv` sont optionnels : leur absence désactive une
fonction sans bloquer le lancement. Le preflight propose de les installer à
chaque démarrage ; répondez `o`, ou placez les binaires dans `bin/`.

---

## 5. Conventions communes à tous les écrans

- `⌫` ou `Esc` reviennent en arrière, partout.
- `Ctrl+Home` **ramène à la liste des fichiers** depuis n'importe quel écran —
  dry-run, encodage, mux, assistant, profils, pistes, recalage. C'est ce qui
  permet d'enchaîner plusieurs fichiers sans remonter la pile un écran à la
  fois. Depuis les **pistes** et le **recalage**, une confirmation est demandée :
  ces deux écrans portent un travail que le retour ne conserve pas — une
  sélection, une greffe, une mesure. `Home` seule garde son rôle, aller à la
  première ligne de la table.
- `F10` quitte, toujours en dernier dans le pied de page.
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
