---
type: synthese
maj: 2026-10-01
sources:
  - "[[source-2026-10-01-entrelacement]]"
  - "[[source-2026-09-26-nvenc-pilote]]"
  - "[[source-2026-09-24-mise-a-jour]]"
  - "[[source-changelog]]"
  - "[[source-spec]]"
  - "[[source-2026-09-24-diagnostic]]"
---

# Pièges et leçons

Ce que le projet a payé pour apprendre. Presque tous ces défauts avaient un
point commun : **aucune erreur visible**. Un fichier faux, une piste absente,
une ligne de moins dans une liste.

## Règles qui en sont sorties

1. **Vérifier la sortie, pas le code de retour.** ffmpeg rend 0 avec une
   piste audio de 54 ms au lieu de trois heures et demie ; mkvmerge tué laisse
   un fichier lisible et court. Relire les durées, compter les images.
2. **Mesurer sur un fichier réel, avec l'outil réel.** Un test qui fabrique
   lui-même son entrée ne prouve rien sur ce que produit l'outil : trois tests
   passaient sur un analyseur de `dovi_tool info` qui n'a jamais rien lu.
3. **Mesurer avant de croire.** Le débit « trop bas » du 10 bits n'était pas
   un défaut (SSIM supérieur) ; le réglage de débit juste pour NVENC est faux
   pour x265.
4. **Un fichier parfait sur PC peut être illisible sur TV.** mpv et VLC
   normalisent ce que les décodeurs matériels refusent (horodatages, départ
   hors de zéro). Contrôler sur le matériel de lecture.
5. **Chercher les autres occurrences d'un défaut.** Trois des quinze défauts
   d'une revue étaient la récidive d'une correction déjà faite ailleurs. D'où
   des **tests structurels**, qui lisent le source et refusent une forme :
   `stdin=` absent, `text=True`, suffixe écrit en dur…
6. **Ne rien proposer qui ne puisse aboutir.** Outil manquant, encodeur non
   sondé : retomber sur une action possible plutôt qu'annoncer une opération
   qui échouera au lancement. Ne pas savoir n'autorise pas non plus à refuser.
7. **Un refus vaut mieux qu'un chiffre faux** (mesure de décalage), et **une
   perte doit se voir** (sous-titres écartés affichés `MP4 −3 st`).

## Défauts silencieux rencontrés

| Symptôme | Cause | Page |
|---|---|---|
| Son sans image puis plantage sur TV (retrait DV en MP4) | flux brut sans horodatage muxé en MP4 par ffmpeg | [[hdr-dolby-vision#Retrait du RPU|HDR et DV]] |
| TV refuse un fichier greffé | `-itsoffset` négatif décale tout le fichier | [[conteneurs#Horodatages|Conteneurs]] |
| Deux images perdues en tête d'un MP4 | DTS négatifs d'un flux brut jetés | [[conteneurs#Horodatages|Conteneurs]] |
| VF disparue de la sortie | `fra` ≠ `fre` | [[sous-titres#Langues|Sous-titres]] |
| Fichier absent de la liste | sortie ffprobe décodée en cp1252 | [[sous-processus]] |
| Tous les fichiers « illisibles » sur installation neuve | ffprobe appelé par son nom, absent du `PATH` | [[sous-processus]] |
| Piste audio transcodée vide | décodage sans perte et sous-titre tardif dans le même appel | [[audio|Audio]] |
| Lecture arrêtée à 32 s sur TV, son perdu après un saut | audio d'une 2ᵉ entrée, sous-titres clairsemés lus avec la vidéo : audio écrite par blocs *(mesuré, v0.8.9.41)* | [[audio|Audio]] |
| Réglage 48 kHz sur la mauvaise piste | `-ar:1` au lieu de `-ar:a:1` | [[audio|Audio]] |
| DTS-HD MA traité comme un DTS | famille dans `profile`, pas dans `codec_name` | [[audio|Audio]] |
| Métadonnées HDR10 jamais injectées | `dovi_tool info` rend du JSON | [[dovi-tool]] |
| Film à 57 % du débit promis | plafond égal à la cible en NVENC | [[codecs-video|Codecs vidéo]] |
| Banding dans les ciels | sortie HDR en 8 bits | [[codecs-video|Codecs vidéo]] |
| VP9 ou AV1 1080p laissé intact | règle de codec limitée aux petites définitions | [[codecs-video|Codecs vidéo]] |
| AV1 cassé sur toute machine | `-profile` passé à `av1_nvenc` | [[codecs-video|Codecs vidéo]] |
| Morceau d'audio présent deux fois | points d'insertion non croissants | [[synchronisation|Synchronisation]] |
| Piste alignée refusée | saillance comparée entre ratios | [[synchronisation|Synchronisation]] |
| Sous-titres affichés d'office | drapeau par défaut posé par mkvmerge | [[sous-titres|Sous-titres]] |
| L'interface perd des frappes | sous-processus héritant du `stdin` du terminal | [[sous-processus]] |
| Barre de progression figée | deux tubes, un seul lu | [[sous-processus]] |
| Sortie AV1 reproposée, source effacée | filtre des sorties d'IRIS incomplet | spec § 15.2 |
| Fragment de ligne exécuté comme une commande | `.bat` remplacé pendant son exécution | [[sous-processus#Scripts .bat réécrits pendant leur exécution]] |
| `hevc_nvenc` absent après réinstallation du poste | build ffmpeg à l'API NVENC 13.1, pilote 597 | [[ffmpeg#NVENC et version du pilote]] |
| Débit « trop gros » : réencodage inutile | débit du conteneur comparé au seuil vidéo | [[codecs-video#Mesurer le débit vidéo|Codecs vidéo]] |
| « Select.NULLk » dans le formulaire de profil | Textual 8 : la valeur vide est `Select.NULL`, `Select.BLANK` ne vaut plus que `False` ; une valeur hors liste laisse le champ vide *(mesuré, UX-03)* | spec § 14.8 |
| ffmpeg continue après la sortie de l'écran | quitter un écran ne tue pas ses processus *(mesuré, UX-01)* | [[sous-processus]] |
| `F11` ne répond pas dans l'application | Windows Terminal la lie au plein écran (`toggleFullscreen`, réglage par défaut) ; elle n'arrive jamais au programme *(vérifié dans ses réglages, IE-100)* | spec § 14.7 |
| `UnknownModeError: '_default'` | Textual 8 ne sait pas **revenir** au mode de départ, qu'il ne déclare pas, et `add_mode` refuse ce nom : la navigation doit être un mode nommé *(mesuré, IE-100)* | spec § 14.7 |

## Hypothèses infirmées

| On croyait | En réalité |
|---|---|
| Le 10 bits sous-consomme, donc dégrade | il dépense moins pour un SSIM supérieur |
| Il faut `-ac 6` pour replier du 7.1 en AC3 | ffmpeg replie de lui-même, à l'octet près |
| Le défaut d'audio vide vient de la disposition des sorties | c'est la simultanéité dans un même processus |
| Le chemin MKV du retrait DV était aussi en cause dans le plantage TV | paquets identiques à la source ; seul le MP4 était cassé |
| Une release stable de ffmpeg (8.1) suffit pour NVENC sous un vieux pilote | gyan.dev 8.1.2 exige l'API 13.1 ; seul BtbN n8.1.3 passe |

## Voir aussi

[[sous-processus]] · [[questions-ouvertes]] · [[ffmpeg]] · [[dovi-tool]] · [[mkvmerge]]
