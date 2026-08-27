# IRIS ENCODE — Guide d'utilisation

**Version** : 0.8.1.5
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

## 2. Écran par écran

### 2.1 Browser — navigation et sélection

Le point d'entrée. Une ligne par fichier, avec sa décision d'encodage calculée
d'après le profil actif.

| Touche | Action |
|---|---|
| `↵` | Ouvrir le dossier |
| `⌫` | Remonter |
| `Espace` | Cocher / décocher le fichier |
| `A` / `N` | Tout cocher / tout décocher |
| `T` | Écran des pistes du fichier sous le curseur |
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

Écarter tous les sous-titres image (PGS, VobSub) libère le conteneur MP4 ;
en garder un impose le MKV.

### 2.3 Choix du donneur

Après `F9`. On choisit d'abord le fichier qui porte la piste à greffer, puis
ses pistes dans ce fichier. Le fichier de travail est exclu de la liste.

`↵` choisit, `Esc` annule. Plusieurs donneurs s'enchaînent sans quitter
l'écran suivant.

### 2.4 Recalage — l'écran qui demande le plus d'attention

Une ligne par piste greffée. Les champs se parcourent avec `←/→`, les valeurs
se changent avec `+/-`.

| Touche | Action |
|---|---|
| `←/→` | Champ précédent / suivant |
| `+/-` | ±100 ms sur le décalage, valeur suivante sur les autres champs |
| `Maj+↑/↓` | ±1 s sur le décalage |
| `↵` | Liste de valeurs du champ courant |
| `M` | **Mesurer** le décalage automatiquement |
| `A` | Forcer le candidat d'une mesure refusée |
| `S` | Détail des **plages** détectées |
| `P` | **Appliquer les plages** à la piste sous le curseur |
| `C` | Reprendre le décalage d'une autre piste |
| `V` | Contrôler dans mpv |
| `K` | Extrait de contrôle réellement muxé |
| `D` | Retirer la piste |
| `F9` | Ajouter une autre piste |
| `F1` `F2` `F3` | Dry-run / Encoder / Muxer |

**La langue est obligatoire.** Sans elle, la piste sortirait en « und » dans
tous les lecteurs, et le mux est refusé. L'écran ouvre directement sur ce champ
quand une piste en manque.

**`C` plutôt qu'une seconde mesure.** Des sous-titres livrés avec une VF sont
presque toujours écrits sur le timing de cette VF : leur bon décalage *est*
celui de la piste audio. Le recopier est plus fiable qu'une mesure indépendante.

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

## 3. Recette : ajouter une VF et ses sous-titres

1. Browser : curseur sur le film, `T`.
2. `F9`, choisir le fichier qui porte la VF, puis ses pistes.
3. Sur l'écran de recalage, curseur sur la piste audio, `M`.
4. Selon le résultat, voir § 4.
5. Renseigner la **langue** de chaque piste si elle manque.
6. `V` ou `K` pour contrôler.
7. `F3` pour muxer sans réencoder, ou `F2` pour réencoder aussi la vidéo.

---

## 4. Les cas rencontrés

### 4.1 « ✓ +2450 ms (confiance 0.87) »

Le cas nominal. Le décalage est posé. Un contrôle `V` reste une bonne habitude
mais n'est pas indispensable.

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
une seule détection, sur l'audio, sert aux trois pistes. C'est voulu — le
signal d'un sous-titre est trop creux pour retrouver les plages seul.

Si le compte rendu signale « aucun silence trouvé » sur une frontière,
l'insertion a été posée sur la position estimée. Rien n'est perdu, mais cette
zone mérite une écoute.

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

### 4.9 Un outil optionnel manque

`dovi_tool`, `mkvmerge` et `mpv` sont optionnels : leur absence désactive une
fonction sans bloquer le lancement. Le preflight propose de les installer à
chaque démarrage ; répondez `o`, ou placez les binaires dans `bin/`.

---

## 5. Conventions communes à tous les écrans

- `⌫` ou `Esc` reviennent en arrière, partout.
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
