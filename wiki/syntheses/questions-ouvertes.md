---
type: synthese
maj: 2026-11-13
sources:
  - "[[source-spec]]"
  - "[[source-2026-09-24-diagnostic]]"
  - "[[source-2026-09-24-utilisateur]]"
  - "[[source-2026-09-26-nvenc-pilote]]"
  - "[[source-2026-09-30-hev1-hvc1]]"
  - "[[source-2026-10-03-dv81-mp4]]"
  - "[[source-2026-09-30-lecture]]"
  - "[[source-conception-upscaling]]"
  - "[[source-2026-11-08-yt-dlp-ejs]]"
  - "[[source-2026-11-13-revue]]"
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
| Le téléchargement YouTube (v0.9.1.31) fonctionne-t-il sur de vraies pages ? | écrit et testé sur des pages fabriquées seulement. À vérifier : paliers lus dans `format_note` (film en 2,39:1), clés `-orig` des sous-titres automatiques, SRT intégrés au MKV, nettoyage après `Échap` ([[yt-dlp]]) |
| La liste d'une chaîne (v0.9.2.5, IE-181) fonctionne-t-elle sur une vraie chaîne ? | testée sur des listes fabriquées seulement. À vérifier : `/@nom/videos` donne bien les vidéos (et non les onglets), dates approchées présentes, `--playlist-items` n'arrête pas trop tôt ni ne lit toute la chaîne, vidéos réservées aux membres bien écartées ([[yt-dlp]]) |
| ffmpeg 8.1 refuse-t-il aussi un `mov_text` recopié vers Matroska, et convertit-il aussi sans erreur un `.srt` UTF-16 annoncé cp1252 ? | mesuré en 6.1.1 seulement, lors de la revue du 2026-11-13 (CR-117, CR-123) ; à rejouer avec le ffmpeg de `bin/` ([[ffmpeg#Comportements à connaître]]) |
| L'analyse d'entrelacement prend-elle du contenu progressif réel pour de l'entrelacé ? | une mire `testsrc2` 720×480 progressive est classée entrelacée (peigne 0,70). Une seule mire : à essayer sur une animation ou une image de synthèse progressive avant de conclure |

## Linux et macOS (IE-183, IE-184)

Décisions de l'utilisateur attendues avant de commencer, posées le 2026-11-10
par la note `conception_portabilite_2026-11-10.md` (§ A.8, § B.7).

| Question | Ce qui en dépend |
|---|---|
| Une VM Proxmox est-elle disponible pour Linux, avec une carte NVIDIA en passthrough ? | banc d'essai (A1) ; NVENC sous Linux mesurable ou non (A4a) |
| Quelles distributions viser (Debian 13, Ubuntu 24.04, autre) ? arm64 ou x86_64 seulement ? | choix des assets téléchargés, tests |
| Un Mac est-il accessible (Apple Silicon, Intel) ? Sinon, macOS annoncé « best effort » ? | tout le plan B ; VideoToolbox jamais lancé |
| CI GitHub Actions (Ubuntu, puis macOS) pour `pytest` à chaque push ? | vérification hors Windows sans machine dédiée |
| mkvmerge sous Linux : AppImage officielle téléchargée par IRIS, ou gestionnaire de paquets ? | A3 |
| Partages réseau sous Linux et macOS : « déjà montés seulement » convient-il ? | A5 ; masquer connexion et identifiants |
| Homebrew obligatoire sur Mac pour ffmpeg, mkvmerge et mpv : acceptable ? | B3 |
| Numéro de version de la livraison Linux (MINOR ?) | règle 5.1 : décision de l'utilisateur |

## Voir aussi

[[chaine-de-diffusion]] · [[jellyfin]] · [[lg-oled-g3]] · [[hdr-dolby-vision]] · [[opensubtitles]]
