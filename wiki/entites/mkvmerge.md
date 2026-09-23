---
type: entite
categorie: outil
maj: 2026-09-24
sources:
  - "[[source-spec]]"
  - "[[source-changelog]]"
  - "[[source-2026-09-24-diagnostic]]"
---

# mkvmerge

Remux Matroska (MKVToolNix). Outil **optionnel** : greffe de pistes, collage,
retrait et réencodage Dolby Vision. N'écrit **que** du Matroska.

Version en place : v102.0 (`bin/`, 2026-09-24). ZIP officiel statique, sans
DLL, 22 Mo. Licence GPL-2.0.

## Comportements à connaître

- **`--gui-mode`**, absent de `--help`, fonctionne : il émet
  `#GUI#progress N%` et `#GUI#error <message>` sur stdout.
- **ID global** des pistes (vidéo, audio, sous-titres confondus), là où
  [[ffprobe]] compte par type. Une piste audio unique est `id=1` ici, `a:0`
  chez ffprobe. Ne jamais croiser les deux sans traduction. *(mesuré)*
- `mkvmerge -J` décrit un fichier en JSON. À mettre en cache par (chemin,
  taille, date) : vingt traductions d'index lançaient vingt-six processus.
  *(mesuré, IE-55)*
- **Reconstitue les horodatages d'un flux brut** avec
  `--default-duration 0:<fps>p` : sortie aux paquets identiques à la source.
  *(mesuré, [[source-2026-09-24-diagnostic]])*
- **Pose d'office le drapeau « par défaut »** sur le premier sous-titre qu'on
  lui donne. Émettre `--default-track-flag TID:0`. *(mesuré, [[sous-titres]])*
- `--sync TID:<ms>,<num>/<den>` : décalage et étirement
  ([[synchronisation]]).
- Donneur : `--no-video --no-subtitles` si seul l'audio est voulu, sinon il
  entre en entier.
- **Réécrit tout le conteneur** : pas d'ajout en place. 30 Go veut dire une
  copie complète, une à trois minutes sur SSD, et la place pour deux fichiers.
- **`a.mkv + b.mkv`** enchaîne (collage) ; sans le `+`, les pistes se
  superposent. Refuse d'apparier des codecs ou définitions différents ;
  n'apparie que les rangs communs si le nombre de pistes diffère, **sans
  refuser** ([[conteneurs#Coller des parties]]).
- Pose les tags de statistiques `BPS`, `NUMBER_OF_BYTES`, `DURATION` :
  seule source du débit d'une piste sans perte ([[audio]]).
