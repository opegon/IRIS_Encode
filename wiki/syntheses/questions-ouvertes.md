---
type: synthese
maj: 2026-11-05
sources:
  - "[[source-spec]]"
  - "[[source-2026-09-24-diagnostic]]"
  - "[[source-2026-09-24-utilisateur]]"
  - "[[source-2026-09-26-nvenc-pilote]]"
  - "[[source-2026-09-30-hev1-hvc1]]"
  - "[[source-2026-10-03-dv81-mp4]]"
  - "[[source-2026-09-30-lecture]]"
  - "[[source-conception-upscaling]]"
---

# Questions ouvertes

Ce qui n'est pas vérifié. Retirer une ligne dès qu'elle est tranchée, et
reporter la réponse dans la page du sujet.

**Reporté après la v0.9.0** (décision de l'utilisateur du 2026-10-09) : tout ce
qui suit attend un essai sur le téléviseur ou un échantillon, pas du code. La
release est sortie quand la revue de code a été entièrement traitée.

## Lecture sur la chaîne Jellyfin → LG G3

| Question | Pour trancher | Depuis |
|---|---|---|
| Quel débit le réglage « Auto » du client webOS laisse-t-il passer ? (manuel : 8 à 120 Mb/s) | lire un remux UHD (40-80 Mb/s) en « Auto », relever la méthode de lecture | 2026-09-24 |
| Un DVD converti (pixels carrés, `setsar=1`) passe-t-il en lecture directe ? | lire sur le G3 une sortie de DVD anamorphique (CR-14, v0.8.9.113) | 2026-10-09 |

## Dolby Vision

| Question | Pourquoi c'est ouvert |
|---|---|
| Le filtre ffmpeg `dovi_rpu=strip=1` retire-t-il la couche d'amélioration (NAL 63) d'un profil 7 ? | aucun échantillon P7 : le profil 7 est donc forcé en MKV, par `dovi_tool remove` |
| Le retrait et le réencodage DV d'un **profil 7** fonctionnent-ils ? | éligibles par construction, jamais essayés |
| Le réencodage DV tient-il sur un film entier, avec changements de plans ? | vérifié sur 48 images de mire synthétique seulement |
| Le rendu Dolby Vision d'un réencodage DV est-il correct sur le téléviseur ? | jamais contrôlé sur le G3 |
| Une copie DV **profil 5** en MP4 `hvc1` + `dvcC` s'affiche-t-elle juste sur le G3 ? | seul le 8.1 a été essayé ; un P5 n'a pas de couche de base lisible (question de la revue IE-114) |
| Le MKV Dolby Vision produit par le mux (SKIP + greffes) se lit-il sur le G3 ? | CR-85 corrigé sans essai sur le téléviseur |

## Super-résolution

| Question | Pourquoi c'est ouvert |
|---|---|
| Quelle vitesse sur une carte AMD (Vulkan, `hevc_amf`) ? | aucune carte AMD sous la main : l'estimation de durée prend les chiffres de l'iGPU Intel |
| Une passe vers 1080p de bout en bout sur l'iGPU Intel, avec `hevc_qsv` ? | seul le filtre (38,2 i/s) est mesuré ; le bout en bout ne l'est qu'en deux passes et vers 720p |
| Real-ESRGAN vaut-il mieux qu'ArtCNN sur l'animation dessinée ? | écarté sur la prise de vue réelle ; l'animation dessinée n'a pas été essayée (IE-171) |

## Divers

| Question | Pourquoi c'est ouvert |
|---|---|
| Le preflight et la mise à jour (gyan.dev *release*) installent-ils un ffmpeg sans NVENC sous un pilote < 610 ? | gyan.dev 8.1.2 refuse NVENC sous 597 ; sans ffmpeg au `PATH`, `bin/` servirait ([[ffmpeg#NVENC et version du pilote]]). Depuis la v0.8.9.2, le cas est **annoncé** au lancement ; le choix du build téléchargé reste inchangé |
| AMD AMF (v0.9.1.9) encode-t-il juste sur une vraie carte Radeon ? | écrit sans matériel AMD : seules les options ont été validées par ffmpeg. À mesurer : débit tenu avec `-rc vbr_peak` et 1,5 × de marge, HDR10 conservé (BT.2020, PQ, écran de mastering, MaxCLL) à travers `hevc_amf`, 10 bits sur Polaris et après, AV1 sur RX 7000. Tant que ce n'est pas fait, le support reste « expérimental » |
| Le pilote 610 est-il sûr sur un Shadow Power (flux, encodage côté Shadow) ? | Shadow autorise la mise à jour manuelle, ne dit rien de la 610 ; demander au support |

## Voir aussi

[[chaine-de-diffusion]] · [[jellyfin]] · [[lg-oled-g3]] · [[hdr-dolby-vision]] · [[opensubtitles]]
