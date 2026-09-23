---
type: synthese
maj: 2026-09-24
sources:
  - "[[source-spec]]"
  - "[[source-2026-09-24-diagnostic]]"
  - "[[source-2026-09-24-utilisateur]]"
---

# Questions ouvertes

Ce qui n'est pas vérifié. Retirer une ligne dès qu'elle est tranchée, et
reporter la réponse dans la page du sujet.

## Lecture sur la chaîne Jellyfin → LG G3

| Question | Pour trancher | Depuis |
|---|---|---|
| Les fichiers qui plantaient (son sans image) étaient-ils des MP4 issus d'un retrait DV, ou des MKV ? | refaire un fichier en v0.8.8.15, le lire, relever la méthode et la **raison de transcodage** dans le tableau de bord Jellyfin | 2026-09-24 |
| Jellyfin incruste-t-il un PGS marqué forcé quand un SRT forcé de même langue existe ? | lire un fichier comme Starship Troopers et regarder la méthode de lecture | 2026-09-24 |
| Le client webOS lit-il tous les HEVC MP4 en `hev1`, ou faut-il `hvc1` ? | comparer deux copies d'un même fichier, l'une retaguée `-tag:v hvc1` | 2026-09-24 |
| Le Dolby Vision 8.1 en **MP4** passe-t-il en lecture directe sur le client webOS, là où le MKV part en remux HLS ? | un fichier DV en MP4 contre le même en MKV | 2026-09-24 |
| Quelle limite de débit le client webOS applique-t-il ? | réglages de lecture du client | 2026-09-24 |

## Dolby Vision

| Question | Pourquoi c'est ouvert |
|---|---|
| Le filtre ffmpeg `dovi_rpu=strip=1` retire-t-il la couche d'amélioration (NAL 63) d'un profil 7 ? | aucun échantillon P7 : le profil 7 est donc forcé en MKV, par `dovi_tool remove` |
| Le retrait et le réencodage DV d'un **profil 7** fonctionnent-ils ? | éligibles par construction, jamais essayés |
| Le réencodage DV tient-il sur un film entier, avec changements de plans ? | vérifié sur 48 images de mire synthétique seulement |
| Le rendu Dolby Vision d'un réencodage DV est-il correct sur le téléviseur ? | jamais contrôlé sur le G3 |

## Divers

| Question | Pourquoi c'est ouvert |
|---|---|
| Le téléchargement OpenSubtitles fonctionne-t-il de bout en bout ? | recherche éprouvée contre l'API réelle ; téléchargement en attente d'identifiants |
| La passe audio préalable est-elle nécessaire pour toutes les familles sans perte ? | mesurée sur un codec de chaque famille seulement ; filet : contrôle de durée des pistes |

## Voir aussi

[[chaine-de-diffusion]] · [[jellyfin]] · [[lg-oled-g3]] · [[hdr-dolby-vision]] · [[opensubtitles]]
