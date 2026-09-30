---
type: synthese
maj: 2026-09-30
sources:
  - "[[source-spec]]"
  - "[[source-2026-09-24-diagnostic]]"
  - "[[source-2026-09-24-utilisateur]]"
  - "[[source-2026-09-26-nvenc-pilote]]"
  - "[[source-2026-09-30-hev1-hvc1]]"
  - "[[source-2026-09-30-lecture]]"
---

# Questions ouvertes

Ce qui n'est pas vérifié. Retirer une ligne dès qu'elle est tranchée, et
reporter la réponse dans la page du sujet.

## Lecture sur la chaîne Jellyfin → LG G3

| Question | Pour trancher | Depuis |
|---|---|---|
| Les fichiers qui plantaient (son sans image) étaient-ils des MP4 issus d'un retrait DV, ou des MKV ? | refaire un fichier en v0.8.8.15, le lire, relever la méthode et la **raison de transcodage** dans le tableau de bord Jellyfin | 2026-09-24 |
| Le Dolby Vision 8.1 en **MP4** passe-t-il en lecture directe sur le client webOS, là où le MKV part en remux HLS ? | un fichier DV en MP4 contre le même en MKV | 2026-09-24 |
| Quel débit le réglage « Auto » du client webOS laisse-t-il passer ? (manuel : 8 à 120 Mb/s) | lire un remux UHD (40-80 Mb/s) en « Auto », relever la méthode de lecture | 2026-09-24 |

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
| Le preflight et la mise à jour (gyan.dev *release*) installent-ils un ffmpeg sans NVENC sous un pilote < 610 ? | gyan.dev 8.1.2 refuse NVENC sous 597 ; sans ffmpeg au `PATH`, `bin/` servirait ([[ffmpeg#NVENC et version du pilote]]). Depuis la v0.8.9.2, le cas est **annoncé** au lancement ; le choix du build téléchargé reste inchangé |
| Un sous-titre WebVTT d'un MKV muxé par mkvmerge 102 est-il copié par ffmpeg ? | ffprobe 8.1.2 le voit `codec_name=unknown`, sans autre indice (mkvmerge le nomme « WebVTT ») — constaté le 2026-09-30 en UX-21. L'affichage dit désormais « ? » ; l'encodage d'un tel fichier n'a pas été essayé |
| Le pilote 610 est-il sûr sur un Shadow Power (flux, encodage côté Shadow) ? | Shadow autorise la mise à jour manuelle, ne dit rien de la 610 ; demander au support |

## Voir aussi

[[chaine-de-diffusion]] · [[jellyfin]] · [[lg-oled-g3]] · [[hdr-dolby-vision]] · [[opensubtitles]]
