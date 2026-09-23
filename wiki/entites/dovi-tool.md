---
type: entite
categorie: outil
maj: 2026-09-24
sources:
  - "[[source-spec]]"
  - "[[source-changelog]]"
  - "[[source-2026-09-24-diagnostic]]"
---

# dovi_tool

Traitement du Dolby Vision (quietvoid, GitHub). Outil **optionnel**. Licence
MIT, binaire Windows unique. Version en place : 5717cab (`bin/`, 2026-09-24).

Travaille sur du **flux brut Annex-B**, pas sur un conteneur : il faut
l'extraire avec [[ffmpeg]] (`hevc_mp4toannexb`). Concepts :
[[hdr-dolby-vision]].

## Commandes

| Commande | Rôle | Remarque |
|---|---|---|
| `extract-rpu <in> -o rpu.bin` | sort le RPU | accepte `-` en entrée : branché en tuyau sur ffmpeg, aucune recopie du film |
| `remove -i <in> -o <out>` | retire **RPU et couche d'amélioration** | *documenté par l'aide* |
| `inject-rpu -i <hevc> --rpu-in <rpu> -o <out>` | remet le RPU entre les tranches | **exige un vrai fichier** : relit son entrée pour reconstituer l'ordre des images |
| `convert -m 2` | RPU profil 7 → 8.1 | modes 0 à 5 dans l'aide |
| `info` | description d'une image | rend du **JSON** |
| `demux` | sépare BL et EL d'un profil 7 mono-piste | non utilisé |

## Pièges

- `info` rend du JSON. Un analyseur écrit pour du texte n'a **jamais** rien lu,
  et trois tests passaient parce qu'ils fabriquaient eux-mêmes le format
  attendu. *(mesuré, v0.8.1.19, [[pieges-et-lecons]])*
- Un RPU vide est un succès pour dovi_tool (la source n'en avait pas), mais un
  échec pour un réencodage DV.
- La sortie de `remove` est un flux brut **sans horodatage** : la muxer en MP4
  avec ffmpeg casse l'ordre d'affichage. Seul [[mkvmerge]] le remuxe
  correctement. *(mesuré, [[source-2026-09-24-diagnostic]])*
- Les intermédiaires pèsent le poids du film : à écrire à côté de la source.

## Alternative

Pour le seul retrait du RPU, le filtre `dovi_rpu=strip=1` de [[ffmpeg]] (7.1+)
évite le flux brut. Il ne garantit pas le retrait de la couche d'amélioration
(profil 7).
