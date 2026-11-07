# 2026-11-07 — SAR manquant : The Kid, indices et mesures

## Déclarations de l'utilisateur

Sur l'aperçu avant de choisir 4:3 ou 16:9 : « ce n'est une réponse que l'on ne
peut faire sans voir le résultat. est-il possible de le déterminer autrement ? »

Accord pour un appel réseau (Wikidata) limité aux fichiers sans SAR, résultat
gardé en mémoire.

## Fichier

`resources_files/The Kid (and A Dog's Life) - 1921.avi` : `msmpeg4v3`
(fourcc `DIV3`), 720×480, 29,97 i/s, 6 237 s. ffprobe : `sample_aspect_ratio`
et `display_aspect_ratio` à `N/A` (absents du JSON).

## Métadonnées (lecture des blocs RIFF de l'en-tête `hdrl`)

`avih`, deux `strl` (`strh`, `strf`, `JUNK`), `odml/dmlh`, pas de `vprp`.
Même chose pour `Le Monde Du Silence (1955)….avi` (DX50, 704×528, SAR 1:1 :
déjà redimensionné, hors sujet). DivX 3 n'a pas de champ de proportion dans
son flux.

## Zone utile (`cropdetect=limit=24:round=2:reset=0`, ffmpeg 8.1.3)

12 points, 4 s chacun, toutes images : `crop=` entre 682 et 696 de large,
454 à 476 de haut (696:470, 682:468, 692:468, 688:468, 688:460, 686:454,
686:470, 690:468, 692:468, 688:466, 686:476, 688:468).

8 points, `-skip_frame nokey`, 20 s chacun : 1,8 s en tout. Valeurs
584:420, 520:414 (scènes sombres), 684:450, 682:468, 680:468, 636:452,
684:456, 684:454 → maximum par dimension 684×468. Au scan complet : 690×468.

Format de 688×468 : 1,307 en SAR 8:9 (4:3), 1,742 en 32:27 (16:9). Avec les
SAR ITU (10:11, 40:33) : 1,336 et 1,782. Les deux hypothèses tombent sur un
format standard.

## Wikidata

SPARQL `rdfs:label` + `wdt:P31 wd:Q11424` : 7 films « The Kid » ; Q374172
(« Le Kid », 1921) → P2061 « format 4/3 ». 300 et Blade Runner → 2,35/1 ;
« Le Monde du silence » sans P2061.

API de recherche `srsearch=The Kid haswbstatement:P2061` : Q374172 en tête
(8 résultats). `The Kid (and A Dog's Life)` : aucun résultat. `Le Monde Du
Silence`, `Cactus Jack` : aucun.

Valeurs de P2061 les plus courantes (libellé anglais, nombre de films) :
4:3 24 758 · 16:9 6 146 · 2.35:1 4 005 · 3:2 1 477 · 1.85:1 1 258 ·
2.39:1 857 · Academy ratio 670 · 2:1 372 · 1.66:1 317.

## `-aspect` en copie de flux (ffmpeg 8.1.3)

Extrait H.264 720×480 sans SAR (`N/A`), `-c copy -aspect 4:3` :
MKV → `sample_aspect_ratio=8:9`, `display_aspect_ratio=4:3` ; MP4 → idem.

## Encodage

Filtre `setsar=8/9,scale=trunc(iw*sar/2)*2:trunc(ih/2)*2,setsar=1`, libx264,
5 s à 900 s : 640×480, SAR 1:1, DAR 4:3. Comparaison d'image à l'œil : la
silhouette et les colonnes reprennent leurs proportions.
