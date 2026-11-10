---
type: entite
categorie: outil
maj: 2026-11-10
sources:
  - "[[source-2026-11-08-yt-dlp-ejs]]"
  - "[[source-spec]]"
---

# yt-dlp (et Deno)

Téléchargeur de vidéos en ligne. Usage dans IRIS : télécharger une vidéo
YouTube pour l'encoder (v0.9.1.31, IE-180). Posé avec Deno dans `bin/yt-dlp/`
([[sous-processus]] pour les règles d'appel).

## Moteur JavaScript

- YouTube impose des défis JavaScript ; yt-dlp les résout par un moteur
  externe. **Deno** est celui par défaut (2.3.0 au moins), désignable par son
  chemin : `--js-runtimes deno:<chemin>`. *(documenté)*
- `yt-dlp.exe` sous Windows **embarque** ses scripts de résolution
  (`yt-dlp-ejs`) : seul Deno est à ajouter. *(documenté)*
- YouTube change souvent ce que yt-dlp doit contourner : une version ancienne
  cesse de fonctionner. D'où la mise à jour suivie plutôt qu'épinglée.
  *(supposé, d'après le rythme des releases)*

## Formats de YouTube

- La 1440p et la 2160p ne sont servies qu'en VP9 ou AV1 ; H.264 s'arrête à
  1080p. L'AAC natif est le format 140 (128 kb/s). *(supposé, noté avant
  IE-180 ; non revérifié)*
- Un film en 2,39:1 publié en « 2160p » a une image de 3840 × 1608 : le palier
  se lit dans la note du format (`format_note`, « 2160p60 HDR »), pas dans la
  hauteur. *(supposé ; IRIS s'appuie dessus, à confirmer sur une vraie page)*
- Les sous-titres automatiques sont proposés traduits dans une centaine de
  langues ; la transcription d'origine porte la clé `<langue>-orig`.
  *(supposé ; même remarque)*

## Options utiles

- `-J` : la description complète de la page, en JSON ; formats listés du
  moins bon au meilleur.
- `--print after_move:<gabarit>` rend yt-dlp silencieux : `--progress` garde
  la progression. *(documenté)*
- `--no-config` : ignorer une configuration personnelle.

## Liste d'une chaîne (IE-181, v0.9.2.5)

- `--flat-playlist -J` liste les vidéos sans lire leur page : titre,
  identifiant, durée, mais **ni formats ni date exacte**. *(documenté)*
- `--extractor-args youtubetab:approximate_date` ajoute à chaque entrée une
  date approchée, déduite de « il y a 3 semaines ». *(documenté)*
- `--playlist-items 101:200` lit une tranche de la liste ; on suppose que
  yt-dlp s'arrête de paginer une fois la tranche lue. *(supposé)*
- L'adresse nue d'une chaîne (`/@nom`) liste ses **onglets** (Vidéos, Shorts,
  Directs) plutôt que ses vidéos : IRIS vise `/@nom/videos`. *(supposé, d'après
  le comportement annoncé de yt-dlp depuis 2023 ; non revérifié)*
- Les entrées portent `availability` (`subscriber_only`, `needs_auth`…) et
  `live_status` (`is_upcoming`…), qui servent à écarter ce qui ne se télécharge
  pas sans compte. *(supposé ; à confirmer sur une vraie chaîne)*

## Voir aussi

[[sous-titres]] · [[codecs-video]] · [[conteneurs]] · [[github]]
