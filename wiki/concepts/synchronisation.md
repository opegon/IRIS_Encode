---
type: concept
maj: 2026-09-24
sources:
  - "[[source-spec]]"
  - "[[source-changelog]]"
---

# Synchronisation de pistes

Greffer une VF ou un sous-titre venu d'une autre release suppose de savoir de
combien il est décalé. Implémentation : spec § 10.

## Trois situations

| Situation | Signature | Correction |
|---|---|---|
| **Décalage constant** | même écart partout (−2 450 ms à toutes les sondes) | `--sync TID:-2450` ou `-ss` / `-itsoffset` |
| **Dérive linéaire (PAL)** | écart qui croît régulièrement | décalage **et** facteur d'étirement, `24000/25025` |
| **Montages différents** | paliers : l'écart saute par endroits et reste stable entre deux sauts | recalage par plages : insertion de silence (audio), réécriture des horodatages (SRT) |

### La dérive PAL

Une source PAL passe le film à 25 i/s au lieu de 23,976 : tout dure 4 % de
moins. Ratio `24000/25025`. Ses voisins sur la grille (24/25 contre
24000/25025) ne diffèrent que de 0,1 %.

### Les montages différents

Cas typique : rip broadcast contre rip streaming. Les coupures publicitaires
du broadcast décalent tout ce qui suit. Mesuré sur un épisode : 6 plages,
cinq paliers de **+2 000 ms** (les noirs de coupure), confiances 0,64 à 0,87.
*(mesuré)*

`--sync` de mkvmerge et `-itsoffset` de ffmpeg n'expriment qu'une
transformation **linéaire**. Un décalage par plages oblige à **fabriquer une
piste corrigée**, greffée ensuite sans décalage.

## Mesurer

- Corrélation croisée par FFT, sur l'**enveloppe d'énergie** (audio contre
  audio), ou sur la **parole détectée** du film contre les **répliques** du
  sous-titre.
- Plusieurs sondes de ~30 s réparties dans le film, décodées en mono 8 kHz.
- Le résultat est **recoupé sur trois tiers** du film : un vrai alignement
  tient sur chacun, le bruit se disperse.
- *Un chiffre faux est pire que pas de chiffre* : sous le seuil de confiance,
  ou si les sondes se contredisent sans dériver linéairement, le résultat est
  refusé.

### Leçon : la saillance ne se compare pas d'un ratio à l'autre

Sur *Nom Série* S02E06, deux pistes alignées à 10 ms près étaient refusées :

| Ratio | Décalage | Corrélation | Saillance |
|---|---|---|---|
| 1/1 | −10 ms | **0,83** | 546 |
| 24000/25025 | +160 280 ms | 0,26 | **1 008** |

Le ratio PAL l'emportait sur de la saillance, alors que sa corrélation était du
bruit. Rééchantillonner change la longueur du signal, donc l'échelle de la
médiane et du MAD qui normalisent la saillance : comparer ces nombres revient
à comparer des degrés et des kelvins. **La corrélation choisit le ratio ; la
saillance départage seulement à corrélation comparable** (0,10 d'écart).
*(mesuré, v0.8.3.8)*

### Les sous-titres

- Le signal d'un sous-titre est **creux**. Les plages d'un montage se
  trouvent sur l'**audio du donneur**, puis s'appliquent aux sous-titres du
  même donneur, qui portent le même montage.
- Un sous-titre corrigé ressort à +0 ms résiduel, trois tiers concordants,
  alors que sa corrélation brute (0,17) reste sous le seuil. Le recoupement
  par tiers est le vrai juge. *(mesuré)*
- Un sous-titre embarqué s'extrait d'abord en `.srt`
  (`ffmpeg -map 0:s:N -c:s srt`). Un sous-titre image ne s'extrait pas : le
  refus doit le dire.
- Un `.srt` d'une autre source que la VF (DVDRip Netflix contre VF 720p) peut
  avoir son propre décalage (−13 170 ms contre −10 ms pour l'audio) : ce n'est
  pas une erreur.

## Corriger une piste audio par plages

- L'opération est une **insertion de silence**, jamais une coupe : le
  décalage croissant veut dire que la cible porte du contenu que le donneur
  n'a pas. Un donneur peut être plus long au total et manquer quand même de
  contenu dans le corps du film, ses minutes en trop étant dans le générique.
- La frontière de corrélation n'est juste qu'à une ou deux secondes près :
  s'ancrer sur le **silence le plus proche** (fenêtre de 15 s). Allonger une
  pause ne s'entend pas.
- Faute de silence, poser l'insertion quand même : allonger n'efface rien.
- Les points d'insertion doivent être **strictement croissants**. Un point en
  retrait donnait un segment `atrim` à l'envers et un morceau **présent deux
  fois** dans la piste, qui passait pourtant code retour et contrôle de
  taille. *(mesuré, IE-47)*
- Le silence est un extrait du donneur passé à `volume=0`, pas un `anullsrc` :
  il a d'office la fréquence et la disposition que `concat` exige.
- Un saut négatif (donneur plus long à cet endroit) supposerait de supprimer
  du contenu : ignoré et signalé.

Résultat sur un épisode réel : piste produite à **+0 ms, confiance 0,72,
trois tiers concordants**. *(mesuré)*

## Contrôler à l'oreille

- Un extrait de contrôle découpé en `-c copy` se cale sur les images clés de
  **chaque** fichier, ce qui change le décalage relatif et fausse le test :
  réencoder l'audio de l'extrait.
- Avec étirement, contrôler **tôt et tard** : la dérive s'accumule.

## Voir aussi

[[mkvmerge]] · [[ffmpeg]] · [[mpv]] · [[sous-titres]] · [[audio]]
