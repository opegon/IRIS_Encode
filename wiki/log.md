---
type: log
---

# Journal du wiki

Registre chronologique, **en ajout seul** : une entrée par opération, la plus
récente en bas. Format fixe, lisible par `grep "^## \[" wiki/log.md` :

```
## [AAAA-MM-JJ] ingest|query|lint | titre
```

## [2026-09-24] ingest | Spécification, CHANGELOG, GUIDE, README

Première compilation du wiki à partir des quatre documents du dépôt
(spec v0.8.8.15, CHANGELOG jusqu'à v0.8.8.15). Pages créées : concepts
(codecs vidéo, HDR et DV, audio, sous-titres, conteneurs, synchronisation,
noms de release), synthèses (chaîne de diffusion, pièges et leçons, questions
ouvertes). Sources : [[source-spec]], [[source-changelog]], [[source-guide]],
[[source-readme]].

## [2026-09-24] ingest | Diagnostic du retrait Dolby Vision

Relevés de la session « son sans image puis plantage » : MKV sain, MP4 aux
horodatages perdus, filtre `dovi_rpu` vérifié, profils DV et sous-titres des
fichiers de test. Source : [[source-2026-09-24-diagnostic]]. Pages touchées :
[[hdr-dolby-vision]], [[conteneurs]], [[ffmpeg]], [[ffprobe]], [[mkvmerge]],
[[dovi-tool]], [[sous-titres]], [[lg-oled-g3]], [[pieges-et-lecons]],
[[questions-ouvertes]].

## [2026-09-24] ingest | Déclarations de l'utilisateur

LG OLED G3 ; Jellyfin sans transcodage matériel ; préférence des suffixes en
minuscules. Source : [[source-2026-09-24-utilisateur]]. Pages touchées :
[[chaine-de-diffusion]], [[jellyfin]], [[lg-oled-g3]], [[noms-de-release]].

## [2026-09-24] query | Pourquoi le téléviseur joue le son sans l'image

Réponse versée au wiki : la lecture directe est le seul critère sur un serveur
sans transcodage matériel ; les causes qui en font sortir ; la méthode de
diagnostic par le tableau de bord Jellyfin. Pages : [[chaine-de-diffusion]],
[[jellyfin]]. Réponse de l'utilisateur en attente ([[questions-ouvertes]]).

## [2026-09-24] lint | Alignement sur le modèle « LLM Wiki » de Karpathy

Réorganisation en couches : `raw/` immuable, pages de sources, entités,
concepts, synthèses ; [[index]] et journal ; frontmatter YAML ; liens
`[[…]]`. La page « Outils » est éclatée en entités ([[ffmpeg]], [[ffprobe]],
[[mkvmerge]], [[dovi-tool]], [[mpv]]) et en un concept ([[sous-processus]]) ;
[[jellyfin]], [[lg-oled-g3]] et [[opensubtitles]] reçoivent leur page. Les
conventions passent dans le schéma (`CLAUDE.md`). Contrôle automatique :
`tests/test_wiki.py` (liens, orphelins, index, frontmatter, journal).

## [2026-09-24] lint | Le schéma rejoint le wiki

Les conventions et les opérations quittent le `CLAUDE.md` du projet, exclu du
dépôt, pour [[SCHEMA]] : un clone du dépôt a désormais le wiki et son mode
d'emploi. `CLAUDE.md` n'en garde qu'un renvoi.

## [2026-09-24] ingest | Mise à jour de l'application

Relevés d'`updater.py` (v0.8.9.1) : cmd.exe reprend un `.bat` remplacé à
l'ancienne position, un bloc `( … )` protège la relance ; essai réel contre
l'API des releases GitHub, empreinte `digest` conforme. Source :
[[source-2026-09-24-mise-a-jour]]. Pages touchées : [[github]] (créée),
[[sous-processus]], [[pieges-et-lecons]].


## [2026-09-26] ingest | NVENC refusé après réinstallation du poste

Poste Shadow réinstallé, pilote 597.16 (API NVENC 13.0) : le ffmpeg git master,
gyan.dev 8.1.2 et BtbN n9.0 exigent l'API 13.1 (pilote ≥ 610) et refusent tout
NVENC ; BtbN n8.1.3 passe, 8 et 10 bits. Hypothèse « une release 8.1 suffit »
infirmée. Source : [[source-2026-09-26-nvenc-pilote]]. Pages touchées :
[[ffmpeg]], [[codecs-video]], [[pieges-et-lecons]], [[questions-ouvertes]].


## [2026-09-29] ingest | Arrêter un encodage en cours

UX-01/UX-02 (v0.8.9.5) : quitter l'écran d'encodage ne tuait pas ffmpeg,
et rien n'empêchait l'étape suivante de démarrer après un arrêt. Règle
ajoutée à [[sous-processus]]. Constat annexe, non généralisé : un worker
Textual relancé depuis un écran déjà dépilé ne démarre pas toujours (test
intermittent) — ne pas y placer un nettoyage.


## [2026-09-29] ingest | Formulaire de profil sous Textual 8

UX-03 (v0.8.9.7) : `Select.BLANK` ne vaut plus que `False`, la valeur vide
est `Select.NULL` ; un débit hors liste (3500k de `serie_basic`) laissait le
champ vide, et `tomli_w` refusait d'écrire la sentinelle. Pages touchées :
[[pieges-et-lecons]].


## [2026-09-30] ingest | WebVTT illisible par ffprobe dans un MKV

UX-21 (v0.8.9.28) : un `.vtt` muxé par mkvmerge 102 dans un MKV sort
`codec_name=unknown` sous ffprobe 8.1.2 ; mkvmerge le nomme « WebVTT ». Le nom
affiché passe par `nom_codec()` (« ? »). La copie par ffmpeg reste à
vérifier. Pages touchées : [[questions-ouvertes]].


## [2026-09-30] ingest | File d'encodage et modes Textual

IE-100 (v0.8.9.34 à v0.8.9.36) : le lot d'encodage vit dans son propre mode
Textual, la navigation dans un autre ; basculer suspend sans démonter, ffmpeg
continue. Deux pièges : Textual ne revient pas au mode `_default`, et `F11`
est captée par Windows Terminal — la bascule prend `F12`. Pages touchées :
[[pieges-et-lecons]].


## [2026-09-30] ingest | `hev1` contre `hvc1` sur le G3

IE-74 : deux paires (Clip musical SDR, Film L HDR10 8 bits),
original `hev1` et copie `hvc1` ; les quatre en lecture directe via Jellyfin,
sauts quasi instantanés. Question retirée. Pages touchées : [[conteneurs]],
[[lg-oled-g3]], [[questions-ouvertes]].


## [2026-09-30] ingest | IRIS écrit `hvc1` (v0.8.9.39)

v0.8.9.39 : `-tag:v hvc1` sur toutes les sorties HEVC en MP4, suite d'IE-74.
Pages touchées : [[conteneurs]], [[ffmpeg]].


## [2026-09-30] ingest | PGS forcé écarté, débit du client webOS

IE-73 tranché en politique : un PGS forcé doublé par un SRT forcé de même
langue est écarté (v0.8.9.40) ; seul forcé de sa langue, il reste. IE-76 :
client en « Auto », manuel de 8 à 120 Mb/s ; la question se resserre sur ce
qu'« Auto » laisse passer. Pages touchées : [[sous-titres]], [[jellyfin]],
[[questions-ouvertes]].


## [2026-10-01] ingest | Audio mal entrelacée (v0.8.9.41)

*Film K* : lecture arrêtée à 32 s, son perdu après un saut. Fichier
complet et décodable, mais audio écrite par blocs, jusqu'à ~1 150 s de la vidéo
correspondante. Cause reproduite : audio d'une seconde entrée, sous-titres
clairsemés lus avec la vidéo. Parade : entrée dédiée aux sous-titres.
Validée sur le film entier : 0,23 s de retard audio au plus.
Pages touchées : [[audio]], [[pieges-et-lecons]].


## [2026-10-01] ingest | Marque `-iris`, groupe de release retiré (v0.8.9.44)

Demande de l'utilisateur : la sortie ne garde plus le groupe de la source
(`-GROUPE`, ` - GROUPE`), et la marque `.IRIS`, jugée criarde, devient `-iris`.
Tranché : caractéristique conservée (`.hevc-iris`), ancienne marque plus
reconnue, groupe retiré seulement d'un nom qui porte une marque de release.
Pages touchées : [[noms-de-release]].


## [2026-10-02] ingest | PGS complet doublé écarté (v0.8.9.47)

Demande de l'utilisateur : comme le PGS forcé, un PGS doublé par un sous-titre
texte de même langue arrive décoché. La nature (forcé / complet) doit
concorder. Pages touchées : [[sous-titres]].


## [2026-10-03] ingest | `HDR10Plus` reconnu comme `HDR10+` (v0.8.9.48)

IE-81 corrigé. Le constat du 2026-09-24 visait le mauvais cas : garder
`HDR10Plus` au passage en HDR10 est voulu ; les vrais défauts étaient la
sortie SDR et le suffixe redondant. Pages touchées : [[noms-de-release]].


## [2026-10-03] ingest | DV 8.1 en MP4 `hvc1` lu en direct sur le G3 (IE-75)

MP4 `hvc1` : lecture directe, logo Dolby Vision. `dvh1` ne se lance pas, le
MKV témoin plante l'application. Nouvelle question : son instable avec deux
pistes E-AC3. Pages touchées : [[lg-oled-g3]], [[questions-ouvertes]],
[[source-2026-10-03-dv81-mp4]].


## [2026-10-03] ingest | Son à deux pistes : non reproduit (IE-107)

Relecture du MP4 DV à deux pistes E-AC3 : lecture directe, son propre. Le
« wobble » du premier essai ne revient pas. Pages touchées : [[lg-oled-g3]],
[[questions-ouvertes]], [[source-2026-10-03-dv81-mp4]].


## [2026-10-03] ingest | `dvcC` en MP4 : `-strict unofficial` (v0.8.9.49)

Mesuré : sans l'option, ffmpeg n'écrit pas la configuration DV en MP4 ;
depuis un flux brut, jamais. Copie DV d'IRIS corrigée (IE-109). Décisions
d'IE-108 consignées. Pages touchées : [[hdr-dolby-vision]],
[[source-2026-10-03-dv81-mp4]].


## [2026-10-03] ingest | Réencodage DV en MP4 (IE-108, v0.8.9.57)

Le réencodage DV ne force plus le MKV : mkvmerge puis remux MP4 par ffmpeg.
Mesuré sur l'extrait Apes : `hvc1`, `dvcC` P8 compat. 1, RPU intact
(2 270 images). Pages touchées : [[conteneurs]], [[hdr-dolby-vision]].

## [2026-10-04] ingest | `mov_text` désynchronisé après un long silence (v0.8.9.62)

VF forcée de *Film J* affichée dès les premières images : le muxeur
MP4 de ffmpeg écrase les temps d'un `mov_text` après plus de 2³¹ µs de
silence. Seuil mesuré, MKV indemne, contournement par répliques invisibles.
Source : [[source-2026-10-04-mov-text]]. Pages touchées : [[sous-titres]],
[[ffmpeg]], [[pieges-et-lecons]].

## [2026-10-04] ingest | Localisation : politique de traduction et glossaire (v0.8.9.73)

Audit de localisation (82 constats) et décisions de l'utilisateur : ce qui ne se
traduit jamais, noms de piste selon la langue de la piste, console de démarrage
en anglais seul, arbitrages du glossaire (SKIP invariant, Dry run, Guided,
« lossless » gardé). Glossaire dans `locales/glossaire.fr.csv`.
Source : [[source-2026-10-04-localisation]]. Pages touchées : [[localisation]].

## [2026-10-06] ingest | SAR non carré après `scale` (v0.8.9.79)

*Titre-Film* 3832×1600 ramené en 1080p, puis un 1918×802 H264 réencodé en HEVC :
Jellyfin transcode, vidéo jugée anamorphique. `scale` compensait l'arrondi par un
SAR de 192079:192000 et 959:960 ; `setsar=1` ajouté. Source :
[[source-2026-10-06-sar-scale]]. Pages touchées : [[ffmpeg]], [[jellyfin]],
[[pieges-et-lecons]].

## [2026-10-06] ingest | Retrait DV en MP4 confirmé sur le G3 (IE-72)

L'utilisateur confirme que la correction d'IE-69 tient sur le téléviseur. Question
retirée de [[questions-ouvertes]]. Source : [[2026-10-06-declaration-ie72]].
Pages touchées : [[lg-oled-g3]].

## [2026-10-07] ingest | Formats localisés arbitrés (IE-90)

Quatre choix de l'utilisateur : point décimal fixe, octets TB/GB/MB/KB en
anglais, « 12% » sans espace dans toutes les langues, quota OpenSubtitles laissé
brut. Source : [[2026-10-07-decisions-formats]]. Pages touchées : [[localisation]].

## [2026-10-07] ingest | Lanceurs et console arbitrés (IE-91)

Deux choix de l'utilisateur : la langue se charge avant la bannière, qui suit
donc `[app] language` ; `launcher/build.bat` passe en anglais avec les autres
lanceurs. Source : [[2026-10-07-decisions-console]]. Pages touchées :
[[localisation]].

## [2026-10-07] ingest | Choix de la langue arbitré (IE-92)

Trois choix de l'utilisateur : langues proposées = catalogues livrés, nommés
dans leur langue ; anglais si Windows est dans une langue non traduite ; message
seulement après un changement. Source : [[2026-10-07-decisions-choix-langue]].
Pages touchées : [[localisation]].

## [2026-10-07] ingest | Anglais source relu (IE-93)

Relecture des 883 messages contre le glossaire et captures de tous les écrans en
anglais : conventions US et noms d'écrans fixés, deux troncatures propres à
l'anglais corrigées. Pas de source brute : décisions prises pendant la
relecture, consignées dans la page. Pages touchées : [[localisation]].

## [2026-10-07] ingest | Annexes Jellyfin d'une vidéo (IE-116)

Format des `.nfo` et images que Jellyfin dépose à côté d'une vidéo, relevé sur
deux dossiers de la bibliothèque. Choix de l'utilisateur : ils partent avec la
source (après encodage et `Ctrl+D`), sans option séparée ; les `.srt` restent.
Pages touchées : [[jellyfin]].

## [2026-10-07] ingest | Tests de la localisation (IE-94)

Smoke, captures, guide et planchers de colonnes dans les deux langues ;
garde-fous structurels. Trois textes français en dur trouvés et corrigés.
Pages touchées : [[localisation]].

## [2026-10-07] ingest | Documentation en deux langues (IE-95)

README et GUIDE en anglais, versions françaises en `.fr.md`. Dérives du guide
français corrigées au passage. Pages touchées : [[localisation]].

## [2026-10-07] query | Hors scope de la spec arbitré (IE-82)

Six lignes gardées hors scope avec leur raison, cinq retirées parce que faites,
l'analyse récursive en parallèle placée en v0.9.0 (IE-117). Fait relevé : pas
de corbeille Windows sur un partage réseau, d'où le refus d'une corbeille pour
`Ctrl+D`. Spec § 19. Pages touchées : aucune.

## [2026-10-07] ingest | Téléchargement OpenSubtitles vérifié (IE-79)

L'utilisateur déclare le téléchargement fonctionnel, sans relevé du parcours.
Question retirée de [[questions-ouvertes]] ; les refus 401/406/429 restent
éprouvés en simulation seulement. Source : [[2026-10-07-declaration-ie79]].
Pages touchées : [[opensubtitles]].

## [2026-10-07] ingest | Piste sans perte vidée : plus reproduite (IE-80)

Défaut du 2026-08-28 rejoué sous ffmpeg 8.1.2 et 8.1.3 : flux synthétiques et
réels, fichier du signalement, commande complète d'IRIS sans passe — aucune
piste vidée. Passe préalable gardée par choix de l'utilisateur. Question
retirée de [[questions-ouvertes]]. Source : [[2026-10-07-piste-vide-ffmpeg-81]].
Pages touchées : [[audio]], [[pieges-et-lecons]].

## [2026-10-08] ingest | Sources disque et `.ts` (IE-118)

Sondage des deux ISO et des deux `.ts` d'essai : capacités des builds ffmpeg,
langues absentes hors mkvmerge, lecteur monté en lecture seule, encodages
courts réussis. Nouvelle page [[disques-optiques]]. Source :
[[2026-10-08-sondage-disques]]. Pages touchées : [[ffmpeg]], [[mkvmerge]].

## [2026-10-08] ingest | Langues des `.m2ts`, cœur AC-3, sous-titres TNT (IE-119)

Une langue complétée par mkvmerge doit être écrite par `-metadata`, ffmpeg ne
la voyant pas ; la TrueHD et son cœur AC-3 partagent un PID ; libzvbi présent
dans le BtbN seulement. Pages touchées : [[disques-optiques]].

## [2026-10-08] ingest | Titres de Blu-ray (IE-120)

Playlists `.mpls` du disque d'essai lues sans outil, validées contre mkvmerge ;
doublons à chapitres différents ; assemblage mkvmerge d'une playlist de deux
clips ; chapitres posés par FFMETADATA ; signature AACS des clips. Pages
touchées : [[disques-optiques]].

## [2026-10-08] ingest | Titres de DVD et outil DVD (IE-121)

IFO du DVD d'essai lus sans outil, validés contre ffprobe `dvdvideo` ; chemin
`VIDEO_TS` exigé par libdvdread à la racine d'un lecteur ; extraction MKV
mesurée ; BtbN n9.0 installé et éprouvé. Pages touchées : [[disques-optiques]].

## [2026-10-08] ingest | Entrelacement des sources disque et TNT (IE-122)

`field_order` et `idet` sur le DVD et les deux `.ts` : un `.ts` déclaré
progressif est entrelacé par passages ; bwdif mesuré sur le DVD, et un artefact
de la détection « multi » d'`idet` sur les scènes sombres. Pages touchées :
[[disques-optiques]].

## [2026-10-08] lint | Conteneur d'une greffe (IE-123, CR-15)

La page disait qu'une piste externe impose le MKV ; le code ne l'impose que pour
un codec qui l'exige, et un mux seul sort toujours en MKV. Corrigé avec la spec.
Pages touchées : [[conteneurs]].

## [2026-10-09] ingest | Greffes : jeu de caractères, drapeaux, polices (IE-125)

Constats CR-20, 23, 25, 50 de la revue, reproduits en tests de bout en bout
(ffmpeg et mkvmerge de `bin/`). Pages touchées : [[sous-titres]].

## [2026-10-09] ingest | Greffes : langue dans le nom, long silence (IE-125 2/3)

Mots de titre pris pour des langues (CR-26) ; sous-titre greffé tardif en MP4
reproduit de bout en bout, décalage négatif par `-ss` vérifié sur un `.srt`.
Pages touchées : [[sous-titres]].

## [2026-10-09] ingest | Formats texte et extraction (IE-125 3/3)

MicroDVD refusé par mkvmerge et ffmpeg, WebVTT sans heures, horodatage à
quatre chiffres, extraction d'un sous-titre embarqué sans délai fixe.
Pages touchées : [[sous-titres]].
