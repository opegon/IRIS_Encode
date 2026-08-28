# CHANGELOG — IRIS ENCODE

## [v0.8.2.13] — 2026-08-28

### L'assistant rappelle sur quel fichier il travaille

Seule la première étape nommait le fichier. Les quatre suivantes parlaient d'un
codec, de pistes, d'un lancement — sans jamais redire de quoi. Le bandeau porte
désormais le nom du fichier traité à chaque étape.

Le nom seul, jamais le chemin : c'est lui qui identifie. Il est tronqué au
milieu selon la largeur disponible, pour que sa fin survive — c'est là que
vivent la résolution, le codec et le groupe qui distinguent deux versions d'un
même film.

## [v0.8.2.12] — 2026-08-28

### Le mode se lit dans le footer, et dans sa couleur

La barre de profil annonçait déjà le mode, mais le footer disait seulement
« W Mode » — ce qui n'apprend rien sur celui qui est actif. Il nomme désormais
le mode courant : `W Assistant` ou `W Manuel`.

Et le fond du footer change : le **manuel garde le code couleur par défaut**,
l'assistant prend l'accent du thème. Sur l'accueil comme sur les écrans de
l'assistant lui-même.

Une couleur se remarque sans être lue. Le mode commande ce que fait une touche
aussi banale que `↵` sur un fichier : il ne devait pas demander qu'on aille le
chercher.

## [v0.8.2.11] — 2026-08-28

### L'assistant devient un écran à lui seul

La première version enchaînait les écrans existants — pistes, donneur,
recalage — en leur donnant seulement un ordre. C'était un mélange, pas un
parcours : chaque écran gardait ses propres touches, ses propres colonnes et
ses propres détours.

L'assistant est désormais **autonome**, cinq étapes, `↵` pour avancer :

| Étape | Ce qu'on y fait |
|---|---|
| 1 — Fichier | Le nom du fichier et le profil actif |
| 2 — Décision | Codec, débit et pistes conservées, **sur un seul écran** |
| 3 — Pistes externes | Présenter un donneur ; la mesure suit aussitôt |
| 4 — Lancer | Muxer ou encoder, les deux toujours offerts |
| 5 — Terminé | Le résultat, puis retour à l'accueil |

**L'accueil ne change pas.** `W` y bascule entre assistant et parcours libre, et
la barre de profil affiche lequel est actif : le mode change ce que fait `↵` sur
un fichier, cela devait se lire sans l'essayer. En mode assistant, `↵` ouvre le
parcours — un fichier à la fois.

**La mesure ne se demande plus.** Une piste greffée sans recalage est une piste
décalée : il n'y a rien à arbitrer. L'audio est mesurée dès l'ajout et son
décalage reporté sur les sous-titres du même donneur. Une mesure refusée laisse
le décalage à zéro et le dit, plutôt que d'appliquer un candidat non confirmé.

**Les deux lancements restent offerts.** `↵` prend le recommandé, `M` et `E`
forcent l'autre. Un mux sans piste externe est refusé avec sa raison au lieu
d'être exécuté à vide.

`muxer.propager_recalage()` sort de l'écran de recalage pour que la règle
n'existe qu'une fois : l'assistant s'en sert aussi.

## [v0.8.2.10] — 2026-08-28

### `Ctrl+Home` — revenir à l'accueil d'une touche

Enchaîner plusieurs fichiers demandait de remonter les écrans un par un.
`Ctrl+Home` dépile jusqu'au browser depuis les sept écrans non modaux :
dry-run, run, mux, assistant, config, pistes et recalage.

`Home` n'était pas disponible : elle appartient à la navigation dans les tables,
et `TableNavMixin` l'intercepte avant même que les bindings soient consultés.
Lui donner un second sens aurait cassé le premier.

**Deux écrans demandent confirmation.** Le dépilage ne rend aucun résultat, donc
les rappels des écrans traversés ne sont pas appelés. Sans conséquence pour ceux
qui n'ont rien à rendre — mais les pistes et le recalage portent une sélection,
une greffe, une mesure de plusieurs minutes. Perdre cela sur deux touches n'était
pas acceptable : ils passent par la modale de confirmation.

Les bindings sont tous `priority=True` : un `DataTable` étouffe la touche avant
le système de bindings, et sans cela le raccourci ne faisait rien sur les écrans
qui affichent une table — presque tous. C'est le smoke test qui l'a montré.

Quatre cas verrouillés par le scénario 17 : retour direct depuis un écran sans
état, confirmation demandée depuis les pistes, refus respecté, et la touche sans
effet quand on est déjà à l'accueil.

## [v0.8.2.9] — 2026-08-28

### Le flux `bin_data` des sorties MP4 : c'est la piste de chapitres

Relevé en vérifiant la passe audio, sur une sortie MP4 qui portait un flux de
plus que ceux demandés. Identifié plutôt que soupçonné :
`codec_tag_string=text`, `handler_name=SubtitleHandler`, une trame par
chapitre — et `-map_chapters -1` le fait disparaître, emportant les chapitres
avec lui.

Le MP4 ne sait porter les chapitres que sous la forme d'une piste texte
QuickTime ; c'est ainsi que les lecteurs les retrouvent. Rien à corriger. C'est
noté dans la spec (§ 8.6) pour que personne ne réenquête, la mention `bin_data`
d'ffprobe ayant tout d'une piste parasite.

## [v0.8.2.8] — 2026-08-28

### La passe audio ne se paie plus que là où elle sert

Elle se déclenchait sur « transcodage + sous-titres conservés », soit la
plupart des encodages. La mesure exige davantage : la source décodée doit être
**sans perte**. Transcoder l'AC3 du même fichier, au lieu de son TrueHD, sort
indemne. Le déclencheur est donc restreint à TrueHD, MLP et DTS-HD MA.

### Un code de retour nul ne vaut plus succès

La restriction ci-dessus repose sur deux mesures — un codec sans perte qui
échoue, un codec avec perte qui passe. C'est une inférence, pas une loi. Et le
défaut qu'elle contourne est silencieux : ffmpeg rend un code nul et un fichier
amputé d'une piste.

La sortie est donc relue après chaque encodage. La durée de chaque piste audio
est comparée à celle attendue ; en dessous du dixième, le fichier est déclaré en
erreur au lieu d'être compté comme réussi, avec le nom des pistes en cause. Le
seuil est grossier à dessein : il sépare « 54 millisecondes au lieu de trois
heures et demie » de tout ce qui est légitime, une piste de commentaires
écourtée comprise.

Vérifié sur un fichier délibérément cassé : `ENG VO (eac3, 0.06 s)` signalée,
le même encodage sans le sous-titre déclaré sain. Le filet ne peut pas devenir
lui-même une cause d'échec — une sortie illisible le laisse muet.

## [v0.8.2.7] — 2026-08-28

### Le défaut d'audio tient à la simultanéité, pas à la sortie

La v0.8.2.6 décrivait le défaut comme « transcoder une piste audio **et
recopier** un sous-titre » — ce qui laissait croire que le partage d'un même
fichier de sortie était en cause. La mesure dit autre chose :

| Disposition | Paquets audio sur 60 s |
|---|---|
| une seule sortie, tout ensemble | 2 |
| deux sorties, l'audio seule dans la sienne | 2 |
| deux sorties, le sous-titre seul dans la sienne | 2 |
| sous-titre présent dans l'entrée, **non mappé** | 1 875 |
| **appel ffmpeg distinct** | 1 875 |

Il suffit que le sous-titre soit **mappé** quelque part dans l'invocation. Le
muxeur est hors de cause : aucune disposition des sorties ne sauve la piste,
seul un processus séparé le fait — ce que la parade fait déjà.

Deux facteurs de plus éliminés au passage : transcoder l'AC3 de la même source
au lieu du TrueHD sort indemne, et un sous-titre laissé dans l'entrée sans être
mappé est sans effet.

Aucun changement de comportement : la parade était juste, et pour la bonne
raison. Seule sa description l'était à moitié.

## [v0.8.2.6] — 2026-08-28

### Une piste audio transcodée pouvait disparaître sans un mot

Signalé sur une conversion refaite : la piste anglaise du fichier produit était
vide. C'est le **second** exemplaire du défaut qui avait fait ouvrir IE-12 puis
IE-16, et qui avait été classé « cause non identifiée, non reproductible ».

Elle l'est désormais. Quand une même commande ffmpeg transcode une piste audio
**et** recopie un flux de sous-titres dont le premier repère arrive tardivement,
la piste transcodée n'est pas écrite. Deux trames sortent, puis plus rien — sans
erreur, sans code de retour non nul, et le bilan de ffmpeg ne compte que l'audio
recopiée. Sur un film dont les sous-titres « forced » n'ouvrent qu'à 6 min 20,
mesuré sur soixante secondes :

| Sous-titres mappés | Paquets audio produits |
|---|---|
| aucun | 1 875 — correct |
| les denses seules (premier repère à 23 s) | 1 875 — correct |
| la seule piste « forced » (premier repère à 380 s) | **2** |

Le défaut ne dépend ni du codec — l'AC3 meurt comme l'E-AC3 — ni de la durée, et
aucun réglage n'y change rien : ni `max_muxing_queue_size`, ni
`max_interleave_delta`, ni `avoid_negative_ts`, ni `copyts`, ni l'ordre des
`-map`. Les pistes simplement recopiées survivent, et la vidéo aussi.

D'où la parade : produire les pistes finales dans une passe à part, puis les
**recopier** dans la passe d'encodage. Elle n'est payée que lorsque les deux
conditions sont réunies, et coûte un transcodage audio là où la passe vidéo se
compte en heures. Vérifié sur le fichier du signalement : la piste anglaise
passe de 2 à 1 876 paquets, avec sa langue, son titre et les six sous-titres.

### Ce que cela clôt

IE-12 et IE-16 avaient diagnostiqué un « mauvais entrelacement » et cherché la
cause dans la durée du film et le nombre de pistes. Le fichier n'était pas mal
entrelacé : **il n'avait pas de piste anglaise**, et les sondages ne trouvaient
donc aucun paquet audio. Mars Express, réencodé avec huit sous-titres, sortait
propre parce que tous ses sous-titres ouvrent tôt.

## [v0.8.2.5] — 2026-08-28

### Le mode « HDR10 quality » gardera son plafond serré — c'est mesuré

Le mode standard (NVENC) a reçu en v0.8.1.24 un plafond à 1,5 × la cible : son
CBR traitait le débit demandé comme un plafond qu'il n'avait pas à atteindre.
Le mode « HDR10 quality », qui passe par libx265, portait le même `-maxrate`
égal à la cible et avait été laissé en l'état faute de mesure.

La mesure dit l'inverse de l'intuition. L'ABR de x265 distribue un budget selon
son modèle de qualité ; c'est un **VBV serré qui le force à le dépenser**, là où
le CBR de NVENC n'y voyait qu'un plafond. Desserrer le plafond fait donc
sous-consommer. Sur un film 1080p 10 bits, extraits de 120 s, cible 5 000k :

| Réglage | t=1800 | t=4200 |
|---|---|---|
| `maxrate` = cible — **celui en place** | 99,9 % | 100,0 % |
| `maxrate` = 1,5 × la cible | 93,6 % | 99,9 % |
| ABR seul, sans VBV | 93,7 % | — |

Au preset `slow`, celui de `cinema_4k_basic` : 99,6 %.

Aucun changement de comportement, donc : appliquer la correction NVENC ici
aurait coûté six points. Les deux branches de `build_command` se ressemblent et
doivent différer — `tests/test_x265_debit.py` le verrouille, pour qu'une passe
d'harmonisation échoue bruyamment plutôt que de casser ce mode en silence.

## [v0.8.2.4] — 2026-08-28

### Savoir quelle piste de sous-titres est laquelle

Deux défauts se cumulaient pour rendre six pistes indiscernables.

**Le nom n'était pas lu.** `SubtitleTrack` portait l'index, le codec et la
langue ; le scanner lisait les tags du flux et jetait le titre. Or « Français
(France) », « Français (France) (forced) » et « Français (Canada) (SDH) » ont
le même codec et la même langue : **seul le titre les sépare**. L'assistant
affichait « — » sur chacune, et l'écran des pistes n'en disait rien.

**Les colonnes tronquaient par la droite**, c'est-à-dire exactement là où se
trouve ce qui distingue ces noms. La colonne `Nom` du recalage faisait quatorze
caractères : les trois variantes d'une même région s'y écrivaient toutes
« Français (Fran… ».

Le titre est désormais lu et affiché — dans l'assistant, sur l'écran des pistes,
dans le sélecteur du donneur et sur celui du recalage. Les colonnes qui le
portent ont la largeur d'un nom entier, et `tronquer_milieu` coupe au milieu
quand la place manque quand même : « França…(forced) » plutôt que
« Français (Fran… ». La fin l'emporte, parce que c'est elle qui porte le sens.

Le sélecteur du donneur passe de 84 à 104 colonnes ; son champ Codec, qui
réservait 22 caractères pour écrire « SubRip », les rend au nom.

C'est le défaut de fond derrière le signalement précédent : une piste « forced »
de vingt-trois répliques greffée à la place de la piste complète de 949.

## [v0.8.2.3] — 2026-08-28

### Le recalage mesuré se reporte seul sur les sous-titres

La piste audio est la base du recalage : c'est sur elle que la mesure tourne.
Il fallait ensuite recopier son décalage sur chaque sous-titre, avec `c`. Or le
guide affirmait déjà que ce décalage **est** le bon pour eux — des sous-titres
livrés avec une VF sont écrits sur le timing de cette VF. Une copie qui
n'apporte aucune information n'est qu'une occasion de l'oublier, et une piste
oubliée sort décalée sans que rien ne le signale.

Une mesure réussie s'applique désormais d'elle-même aux sous-titres du même
fichier donneur. Le bandeau annonce combien de pistes ont suivi ; leur colonne
d'origine affiche « repris de #N », exactement comme après un `c` manuel.

Trois garde-fous, parce qu'un report automatique doit rester un service et
jamais une surprise : il ne quitte pas le **fichier donneur** de l'audio ; il
n'écrase jamais une piste **déjà mesurée ou réglée à la main** ; et il ne part
que d'une piste **audio**. `c` reste pour tout le reste — un sous-titre venu
d'ailleurs, ou une référence choisie exprès.

Un candidat forcé (`a`) se reporte comme une mesure : c'est aussi une décision.

## [v0.8.2.2] — 2026-08-28

### La piste greffée n'était pas celle qu'on avait choisie

Signalé à l'usage : des sous-titres ajoutés apparaissaient dans le lecteur, au
bon nom, et n'affichaient rien.

Le fichier donneur entre dans ffmpeg **en entier**, et la commande mappait son
flux `:0` — ce qui suppose qu'il n'en porte qu'un. Vrai d'un `.srt` nu, faux
d'un conteneur. Un rip qui embarque six pistes françaises rendait donc toujours
la première, quelle que soit celle demandée ; et la première d'un rip est en
général la piste « **forced** », vingt-trois répliques sur un épisode entier.

Le défaut résistait à la relecture de la commande, parce que la langue, le titre
et les drapeaux venaient bien de la piste choisie : le lecteur affichait
« Français (France) » sur le contenu de « Français (France) (forced) ».

`muxer.ffmpeg_stream_index` traduit désormais le tid choisi en index ffmpeg —
c'est déjà le seul endroit du code où les deux numérotations se croisent. Un
donneur illisible retombe sur le premier flux, comme avant.

Vérifié sur les fichiers du signalement : la piste tid 3 se mappe `1:s:1` et
rend 949 repères, là où l'ancienne commande en rendait 23.

**Le chemin mkvmerge n'était pas touché** — il raisonne en tid de bout en bout.
Le défaut ne frappait que les fichiers réencodés.

## [v0.8.2.1] — 2026-08-28

### Trois défauts de l'assistant, dont deux silencieux

Signalés par un `IndexError` à l'usage. Le plantage était le moins grave des trois.

**Revenir sur l'étape des langues plantait.** En validant la dernière ambiguïté,
le compteur dépassait la fin ; `action_retour` ne le recadrait pas, parce qu'au
moment du test l'étape courante était déjà la suivante.

**Un choix révisé ne pouvait que retirer.** Les arbitrages se retranchaient de
la sélection *courante* : une piste écartée avait déjà quitté la liste, et la
recocher ne la ramenait pas — l'écran affichait pourtant sa case cochée. Les
choix repartent désormais d'une base figée avant tout arbitrage.

**Les flèches ne répondaient plus.** Masquer la table lui retire le focus :
en revenant sur l'étape, le curseur restait bloqué sur la première ligne.

Au passage, les cases partent cochées sur ce que la décision garde déjà :
valider sans rien toucher ne retire plus rien.

Scénario 16 du smoke TUI : il rejoue les trois, sur un clip fabriqué avec deux
pistes « fre » — et c'est lui qui a trouvé le troisième.

## [v0.8.2.0] — 2026-08-28

### L'assistant

L'application s'ouvre désormais sur un assistant : **un fichier, quatre étapes,
une touche pour avancer**. `F12` bascule vers le parcours libre, et le choix
tient pour la session.

Il ne calcule rien de neuf. `decide()` arbitrait déjà le codec, le débit, le
conteneur, le sort du Dolby Vision et chaque piste ; l'assistant parcourt cette
décision et rend la main aux écrans existants — sélection des pistes, choix du
donneur, recalage — pour ce qu'ils font déjà.

Deux étapes seulement sont conditionnelles :

- **les langues ambiguës**, quand plusieurs pistes revendiquent la même langue
  voulue. Le doute se définit par un **compte**, pas par une heuristique : une
  seule candidate, on la prend ; plusieurs, seul leur titre les sépare
  (« Français » contre « Français canadien »), et un titre ne se devine pas ;
- **les pistes additionnelles**. Aucun fichier donneur n'est cherché
  automatiquement : les conventions de nommage des releases sont sans limite et
  un mauvais appariement est *silencieux*. C'est l'utilisateur qui le présente,
  quand il y en a un — il peut n'y en avoir aucun.

Ce qui est retiré, c'est la navigation, jamais l'information : chaque étape
montre ce qu'elle a décidé, et l'étape 1 nomme le fichier produit. Un assistant
qui déciderait en silence remplacerait un doute de manipulation par un doute de
contenu, qui ne se voit qu'après l'encodage.

### « fra » n'était pas « fre », et une VF disparaissait sans un mot

ISO 639-2 a deux jeux de codes pour vingt langues — un bibliographique (`fre`,
`ger`, `dut`), un terminologique (`fra`, `deu`, `nld`) — et les conteneurs
emploient l'un ou l'autre sans règle. La comparaison portait sur les chaînes
brutes : `audio_languages = ["fre"]` **excluait une piste étiquetée « fra »**,
qui n'atteignait jamais le fichier produit.

Mesuré sur un épisode réel : ses sous-titres portent `fra`, `ces`, `nld`, `deu`,
`ell`, `ron`, `slk`, `zho` — huit codes terminologiques dans un seul fichier.
`scanner.normalize_language` les réconcilie ; l'affichage garde ce que le
fichier déclare.

### Les sous-titres n'étaient filtrés par rien

Le profil filtrait l'audio par langue, jamais les sous-titres :
`subtitle_indices = None` vaut « toutes », et aucune règle ne s'y appliquait.
Un épisode de rip streaming en embarque quarante-trois ; les quarante-trois
traversaient la chaîne. La clé `subtitle_languages` pose la règle, et les dix
profils intégrés la portent désormais aux mêmes langues que leur audio. Sur le
fichier de test : 43 pistes en entrée, 4 retenues.

Une clé absente ne change rien — les profils personnels gardent leur
comportement.

## [v0.8.1.27] — 2026-08-28

### La recette de greffe s'arrêtait avant les sous-titres

`GUIDE.md` § 3 menait jusqu'à la mesure de la piste audio, puis renvoyait à
« § 4 selon le résultat » — et § 4.1, le cas nominal, ne dit rien des
sous-titres. La réponse existait bien, mais éclatée : § 2.4 conseille `C`,
§ 4.3 et § 4.4 le rappellent pour les cas mesurables, § 4.5 décrit `P` pour un
montage différent. Personne ne suit une recette en la recomposant à partir de
trois sections.

L'étape 4 porte désormais une table des quatre suites possibles selon ce que la
mesure a rendu, et dit ce qui n'allait pas de soi : la mesure ne vaut que pour
la ligne sur laquelle elle a tourné. § 4.1 le répète sur place.

La recette s'ouvre aussi sur un rappel : regarder ce que la cible contient déjà.
Un rip streaming embarque trente sous-titres, français compris — il n'y a alors
qu'une piste audio à greffer.

## [v0.8.1.26] — 2026-08-28

### Le transcodage des pistes sans perte ne suit plus le débit de la source

`CODEC_MAX_BPS["eac3"]` valait 6 144k — la limite de l'encodeur ffmpeg, pas un
choix. Une piste sans perte étant transcodée **au débit présent dans la piste**,
un TrueHD 5.1 à 3 501k donnait un E-AC3 à 3 501k : 5,66 Go pour un film de
3 h 35, quand aucun décodeur ne tire quoi que ce soit d'un Dolby Digital Plus
5.1 au-delà du palier haut usuel. Le plafond passe à 1 024k, et la même piste y
pèse 1,65 Go.

Le plafond AC3 ne bouge pas : ses 640k sont ceux de l'encodeur, qui ramène
silencieusement toute demande supérieure. Les sources déjà sous le nouveau
plafond gardent leur débit — un DTS à 768k reste à 768k.

## [v0.8.1.25] — 2026-08-28

### La décision audio survit au retrait du Dolby Vision

L'écran annonçait `→ eac3 3501k` et le titre corrigé `ENG VO : E-AC3 5.1` ; la
sortie contenait un TrueHD inchangé, sous son ancien titre. Le retrait du DV
remuxait par `mkvmerge -o <sortie> <video_nodv> --no-video <source>` : aucune
décision audio ne lui était transmise. Transcodage, exclusion d'une piste par
langue et retitrage étaient perdus, en MKV comme en MP4.

Les quatre opérations n'ont pas le même prix, et le chemin le reflète
désormais. Exclure une piste audio ou un sous-titre passe par des options de la
commande mkvmerge existante — aucune étape, aucun octet recopié. Seul le
transcodage coûte une passe : une étape 3 produit les pistes finales dans un
Matroska audio, que le remux prend comme seconde entrée. Elle n'existe que
lorsqu'une piste est réellement à transcoder. En MP4, il n'y a jamais d'étape
supplémentaire : ffmpeg recompose déjà le fichier et transcode au passage.

Vérifié sur un extrait de 60 s de `Watchmen` 2160p DV P8.1, profil
`cinema_4k_basic` : ce que l'écran annonce et ce que `ffprobe` lit dans la
sortie coïncident piste par piste, titres compris — `ac3 6ch fre « FR VFF :
AC3 5.1 »` recopié, `eac3 6ch eng 3501k « ENG VO : E-AC3 5.1 »` transcodé, six
sous-titres conservés, RPU Dolby Vision absent, transfert `smpte2084` intact.

## [v0.8.1.24] — 2026-08-28

### Le débit demandé redevient une cible, et non un plafond

Un film pouvait sortir à 57 % du débit que le profil promet et que l'écran
affiche. La commande passait `-b:v <cible> -maxrate <cible> -rc cbr` : le débit
demandé servait à la fois de cible et de plafond. Chaque scène facile tire alors
la moyenne vers le bas, et aucune scène difficile ne peut la remonter — la
moyenne ne peut, par construction, que tomber sous la cible.

La commande passe désormais en VBR avec 50 % de marge au-dessus de la cible et
un tampon qui couvre ce plafond. Mesuré sur un extrait de 180 s d'un film en
prises de vues réelles 2160p 10 bits, cible 6 035k : **92 % du débit demandé
avant, 99 % après**.

### Ce qui n'était pas un défaut, et qui est maintenant écrit

Le même retrait, mesuré sur une animation au dessin plat, ne se comble pas : le
même extrait rend 41 % avant, 54 % après. Ce n'est pas l'encodeur qui échoue,
c'est le contenu qui n'a pas besoin de ces bits — un encodage piloté par la
qualité (`-cq 16`, quasi transparent) en dépense encore moins.

La suspicion portait sur le 10 bits, qui creuse effectivement l'écart (41 %
contre 72 % en 8 bits sur le même extrait). La mesure de fidélité renverse la
conclusion : contre la source, le 10 bits à 2 911k obtient un SSIM de **0,9991**,
le 8 bits à 4 727k un SSIM de **0,9970**. Le 8 bits consomme 62 % de bits en plus
pour un résultat nettement moins fidèle. Le retrait de débit en 10 bits ne coûte
donc pas de qualité, et la spécification le dit désormais (§ 12.1).

## [v0.8.1.23] — 2026-08-28

### Un fichier pouvait disparaître de la liste sans un mot

Un WebM déposé dans le dossier n'apparaissait pas. Ni l'extension ni le codec
n'étaient en cause : le fichier portait un tag `DESCRIPTION` contenant « ❤️ ».

ffprobe écrit sa sortie en UTF-8. La lire avec `text=True` laisse Python choisir
l'encodage de la machine — cp1252 sur un Windows français — et le premier
caractère hors de cette table lève `UnicodeDecodeError` **dans le thread de
lecture de subprocess**. L'exception n'y remonte pas jusqu'à l'appelant :
`stdout` vaut simplement `None`, `json.loads(None)` échoue, et le fichier est
écarté comme illisible. `scan_directory` avalant les erreurs par fichier, il n'en
restait rien à l'écran — une ligne de moins, sans message.

Six appels lisaient ainsi la sortie de ffprobe, ffmpeg et mkvmerge, dont les
lignes de progression citent les noms de fichiers : `scanner`, `encoder`,
`muxer` (deux), `preflight` et `sync`. Tous lisent désormais en UTF-8, les
octets invalides étant remplacés plutôt que fatals. Un test interdit le motif
`text=True` dans `core/`, et deux autres vérifient sur un fichier réel qu'un
titre hors cp1252 ne fait plus perdre le fichier.

Vu de l'utilisateur : les WebM VP9/Opus et les MKV AV1/Opus sont listés,
décidés et encodés comme le reste — VP9 et AV1 vers HEVC, Opus vers AAC ou AC3,
le HDR10 conservé en 10 bits.

## [v0.8.1.22] — 2026-08-28

### L'AV1 était cassé sur toute machine

Découvert en cherchant pourquoi il échouait sur une RTX A4500 : la commande
passait `-profile:v main` à `av1_nvenc`, **qui n'a pas d'option `profile`**.
ffmpeg refusait donc la commande avant même d'interroger la carte —
« Unable to parse "profile" option value "main" ». Le défaut ne dépendait pas
du matériel : l'AV1 n'aurait pas davantage fonctionné sur une RTX 40.

### Les capacités d'encodage sont mesurées, plus supposées

`detect()` déduisait les encodeurs du modèle de carte. Or NVENC n'encode l'AV1
qu'à partir d'Ada (RTX 40), et une carte antérieure ne le dit qu'au moment
d'échouer. Les trois encodeurs sont désormais **sondés au lancement** — ouverts
sur une image, en parallèle, ~0,7 s — et le résultat suit l'application.

Relevé sur la machine de développement : `hevc_nvenc` ✓, `h264_nvenc` ✓,
`av1_nvenc` ✗ (« No capable devices found »).

**Le choix AV1 n'est pas retiré du picker.** Une carte se remplace, un pilote se
met à jour, et masquer l'option laisserait croire qu'elle n'existe pas. Elle
s'affiche « ✗ indisponible ici », et le lancement **refuse avant d'appeler
ffmpeg**, en nommant la cause :

```
✗ ERREUR : av1_nvenc indisponible ici
Cette machine ne sait pas encoder avec « av1_nvenc » — sondé au lancement.
L'AV1 par NVENC demande une RTX 40 ou plus récente ; le HEVC et le H264
restent disponibles.
```

`peut_encoder()` rend `None` tant que rien n'a été sondé : ne rien savoir
n'autorise pas à refuser.

### Un échec d'encodage nomme sa cause

ffmpeg annonce la cause puis constate l'échec. L'écran ne gardait que la
**dernière** ligne — « Error opening output files: Invalid argument » —
c'est-à-dire la seule qui n'apprend rien.

`diagnostiquer()` cherche des signatures connues dans les quarante dernières
lignes : encodeur indisponible, pilote absent, débit hors plage, disposition de
canaux refusée, disque plein, écriture refusée. Chacune a été reproduite avant
d'être ajoutée. Sans cause reconnue, la ligne brute reste affichée : mieux vaut
un message opaque qu'un message inventé.

Correspond à l'entrée **IE-13** de `TODO.md`.

## [v0.8.1.21] — 2026-08-28

### Les sources WebM, VP9, AV1 et Opus traversent la chaîne

`.webm` était déjà une extension reconnue, et l'Opus déjà transcodé. Mais la
règle du codec non standard **ne se déclenchait qu'en dessous de 1080p** : un
VP9 ou un AV1 en 1080p ou en 4K, dont le débit et la résolution tenaient dans
les seuils du profil, ressortait en `← SKIP`. Il restait donc illisible chez le
destinataire — un fichier ne devient pas lisible parce que son débit est
raisonnable.

Le critère porte désormais sur le codec seul. `CODECS_LISIBLES` — `h264` et
`hevc` — nomme ce qu'une chaîne grand public prend sans transcodage ; tout le
reste est réencodé, à toute résolution : VP9, AV1, VC-1, MPEG-2, DivX, et un
codec que ffprobe ne reconnaît pas.

La cible suit le bucket de résolution, comme les autres cas : H264 sous 1080p
où il compresse mieux, HEVC au-dessus.

Vérifié de bout en bout sur des fichiers réels :

| Source | Sortie |
|---|---|
| WebM VP9 1080p + Opus 2.0 | **HEVC Main + AAC LC 192k**, MP4 |
| WebM AV1 720p + Opus 5.1 | **H264 High + AC3 5.1 448k**, MP4 |

Les deux se lisent en direct sur un téléviseur récent comme sur un client
mobile, sans que le serveur ait à transcoder.

Le débit et la résolution gardent la priorité : un VP9 trop gros reste traité
par le cas du débit, et le motif affiché dit lequel a tranché.

## [v0.8.1.20] — 2026-08-28

### Le conteneur de sortie se règle par profil

Il se déduisait du seul contenu. Or le choix ne s'en déduit pas : certains
lecteurs digèrent mal le Matroska, et c'est une politique, pas une propriété du
fichier. Nouvelle clé **`container`**, réglable dans l'écran des profils :

| Valeur | Effet |
|---|---|
| `auto` | Le contenu décide — comportement inchangé |
| `mkv` | Toujours du Matroska, rien n'est écarté |
| `mp4` | Les sous-titres image sont écartés, et la décision les compte |

**Deux garde-fous, parce qu'une politique ne vaut pas une perte silencieuse :**

- Si les sous-titres image sont les **seuls** du fichier, c'est le conteneur
  qui cède. Mieux vaut un MKV qu'une sortie sans sous-titres.
- Une piste audio sans perte **conservée** ramène toujours au MKV. On écarte un
  sous-titre doublé par un SubRip ; on n'échange pas contre un format une piste
  que l'utilisateur a demandé de garder.

Et l'exclusion **se voit avant le lancement** : le dry-run affiche `MP4 −3 st`
dans la colonne Conteneur, en style « modifié ». L'encodeur mappe la liste
finale au lieu de `0:s?`, sans quoi l'exclusion aurait été purement décorative.

Relevé sur le dossier de travail en mode `mp4` :

| Fichier | Sortie | Écartés |
|---|---|---|
| Watchmen | MP4 | 3 PGS, doublés par 3 SubRip de mêmes langues |
| Starship Troopers | MP4 | 3 PGS, doublés |
| The Zookeeper's Wife | MP4 | 1 VobSub anglais ; le SubRip néerlandais reste |
| **Colossus** | **MKV** | aucun — son unique sous-titre est une piste image |

### Le retrait de Dolby Vision sait sortir en MP4

Il passait par mkvmerge, qui ne sait écrire que du Matroska : la décision
imposait donc le MKV, ce qui contredisait une politique `mp4`. Quand le
conteneur demandé est le MP4, le remux passe désormais par ffmpeg.

**Deux images étaient perdues.** Un flux HEVC brut n'a pas d'horodatage — d'où
la cadence donnée avant l'entrée — et ses premières images portent des DTS
négatifs que le muxeur MP4 refuse : il les jetait. Mesuré sur un extrait de
2 270 images, la sortie n'en avait que 2 268, et la première manquait.
`-avoid_negative_ts make_zero` décale la base au lieu de rogner.

Vérifié après correction : **2 270 images des deux côtés, et les empreintes de
200 images décodées sont identiques**.

## [v0.8.1.19] — 2026-08-28

### Le mode « HDR10 quality » n'a jamais injecté ses métadonnées

Ce mode existe pour produire un HDR10 aux métadonnées statiques correctes —
master display et MaxCLL — que certains téléviseurs exigent pour appliquer leur
tone mapping. Il ne les a **jamais** écrites.

`dovi.rpu_info()` analysait la sortie de `dovi_tool info` avec des expressions
régulières attendant du texte — `Dolby Vision Profile: 8.1`, `MaxCLL: 1000` —
alors que l'outil livré rend du **JSON**. `master_display` et `max_cll` valaient
donc toujours `None`, et les `-x265-params` sortaient sans elles.

**Trois tests passaient pourtant**, parce qu'ils fabriquaient eux-mêmes le
format attendu. C'est exactement ainsi qu'un défaut survit à une suite verte :
un test qui invente son entrée ne prouve rien sur ce que produit l'outil réel.

Les métadonnées sont désormais lues **dans les SEI du flux, par ffprobe** :

```
master-display=G(8500,39850)B(6550,2300)R(35400,14600)WP(15635,16450)L(10000000,50)
max-cll=988,382
```

Trois conséquences, toutes des améliorations :

- **Cela vaut pour toute source HDR**, avec ou sans Dolby Vision. L'ancienne
  voie ne s'activait que sur un fichier DV.
- **`dovi_tool` n'est plus requis** pour ce mode.
- **Le scan est trois fois moins cher** sur un fichier DV : l'ancienne voie
  extrayait 30 s de flux HEVC, en tirait le RPU puis l'interrogeait — 1,86 s
  par fichier, contre 0,62 s pour une lecture d'image.

Un `max_content`/`max_average` à `0,0` signifie « non mesuré » : rien n'est
injecté plutôt que d'affirmer un pic lumineux nul. `probe_file()` et
`rpu_info()`, sans appelant, sont retirés.

⚠ **Le coût du mode reste ce qu'il est** : `libx265` mesuré à 0,78 image/s en
4K, soit de l'ordre de 70 heures pour un long métrage. Il est réparé, pas rendu
praticable en 4K — l'écran des profils l'annonce.

### Ni ffprobe ni ffmpeg n'étaient trouvés sur une installation neuve

Découvert en réparant ce qui précède. Le preflight installe les binaires dans
`./bin/` **sans toucher au `PATH`**, or `scanner._ffprobe_json` et
`encoder.build_command` les appelaient par leur nom nu.

Vérifié en retirant ffprobe du `PATH` : `scan()` lève `FileNotFoundError`, et
le browser écarte alors **tous les fichiers comme illisibles**. L'encodage
aurait échoué de la même façon.

`scanner.set_ffprobe_path()` et `encoder.set_ffmpeg_path()` sont posés au
démarrage, comme `muxer.set_mkvmerge_path()` et `sync.set_ffmpeg_path()` le
faisaient déjà. Le défaut ne se voyait pas ici parce que cette machine a
ffmpeg dans son `PATH` — c'est précisément ce que le test en dossier vierge ne
pouvait pas attraper.

## [v0.8.1.18] — 2026-08-28

### Le chemin du dossier était écrit deux fois

La barre d'état donne le dossier courant ; quatre lignes plus bas, la notice
donnait le chemin **complet** du fichier survolé, qui recommence par ce même
dossier. Une quarantaine de colonnes payées deux fois — et sur un partage
réseau, il ne restait plus la place d'afficher le nom du fichier.

La notice ne montre désormais que ce que la barre d'état n'a pas déjà dit :

| Dossier courant | Fichier survolé | Notice |
|---|---|---|
| `D:\films` | `D:\films\Watchmen.mkv` | `Watchmen.mkv` |
| `D:\films` | `D:\films\2009\Watchmen.mkv` | `2009\Watchmen.mkv` |
| `D:\films` | `C:\ailleurs\Autre.mkv` | chemin complet |
| `D:
ilms` | `D:
ilms9\Watchmen.mkv` | `2009\Watchmen.mkv` |
| `D:
ilms` | `C:illeurs\Autre.mkv` | chemin complet |

Le deuxième cas compte : un scan récursif remonte des fichiers de sous-dossiers,
et là le chemin relatif dit quelque chose que la barre d'état ignore.

### Le footer passait à la ligne avant d'être plein

Les raccourcis étaient répartis en trois bandes — propres à l'écran, globaux,
touches de fonction — et **chaque bande était enroulée séparément**. Chacune
démarrait donc sa ligne, même pour une seule entrée : `⌫ Retour` au dry-run et
au mux, `F10 Quitter` à l'encodage et à la configuration.

Les bandes fixent toujours l'ordre, mais plus le découpage : elles sont
enchaînées puis enroulées ensemble, et la ligne ne se coupe qu'au débordement.

| Écran | Avant | Après |
|---|---|---|
| Encodage | 2 lignes | **1** |
| Configuration (150 col.) | 3 lignes | **1** |
| Dry-run | 3 à 4 lignes | **2** |
| Browser | 3 à 4 lignes | **3** |

**Contrepartie assumée** : la v0.8.1.2 avait rangé les raccourcis par rôle pour
qu'« une place fixe par rôle vaille mieux qu'un ordre de déclaration ». Les
touches de fonction restent en fin de séquence, mais ne démarrent plus
forcément leur propre ligne. C'est de la place rendue au contenu au prix d'un
repère un peu moins strict — arbitrage de la revue, inscrit ici pour qu'il ne
se perde pas.

Correspond aux entrées **IE-08** et **IE-09** de `TODO.md`.

## [v0.8.1.17] — 2026-08-28

### L'écran d'accueil promettait dix colonnes vides

Premier écran de l'application, il listait les volumes sous l'en-tête complet du
tableau de fichiers — Taille, Résolution, Durée, Débit, Codec, Dolby V.,
Décision, Estim., ETA, Audio — **dont aucune ne peut avoir de valeur pour un
volume**. S'y ajoutaient « 0/0 sélectionné(s) » alors que rien n'y est
sélectionnable, le bandeau détaillé du profil d'encodage alors qu'aucun fichier
n'est en vue, et un pied proposant `F1 Dry-run`, `F2 Run`, `F7 AlloCiné`.

L'écran des volumes porte désormais **ses propres colonnes** :

| Volume | Espace libre | Total | Occupé |
|---|---|---|---|
| 💾 `C:\` | 407.3 Go | 510.5 Go | 20 % |
| 💾 `D:\` | 305.0 Go | 2.0 To | 85 % |

- La barre d'état compte des volumes au lieu d'annoncer une sélection
  impossible, et ne parle plus de redimensionner des colonnes qui ne le sont
  pas.
- Le bandeau de profil attend qu'un fichier soit en vue : le profil décide de
  ce qu'on fera des fichiers, il n'a rien à dire avant.
- Le footer ne propose que **`↵ Ouvrir le volume`**. Sélectionner, encoder ou
  interroger AlloCiné n'a pas de sens ici — c'est le même défaut que le footer
  de l'écran Config corrigé en v0.8.1.15, au même endroit du raisonnement.
- **Un taux d'occupation d'au moins 90 % passe en alerte** : c'est là qu'un
  encodage échouera faute de place.
- Un volume injoignable — lecteur vide, partage réseau coupé — rend des tirets
  plutôt que de faire disparaître sa ligne : le volume existe, c'est sa mesure
  qui manque.

Le jeu de colonnes et les raccourcis basculent au changement de mode, dans les
deux sens.

### `fmt_bytes` connaît le téraoctet

Un partage réseau s'affichait `35726.4 Go`, ce qui ne se lit pas. Il rend
maintenant `34.9 To`.

Correspond à l'entrée **IE-07** de `TODO.md`.

## [v0.8.1.16] — 2026-08-28

### Une modale laisse voir l'écran sur lequel elle porte

Les modales effaçaient tout — titre, barre d'état, liste des fichiers, footer.
Il ne restait qu'une boîte au milieu du vide, au moment précis où l'on voudrait
voir sur quoi le choix va s'appliquer.

**La cause n'était pas Textual**, qui rend ses modales translucides par défaut,
mais une règle de confort de l'application : `Screen { background: $surface; }`.
`ModalScreen` héritant de `Screen`, la règle s'appliquait à elle aussi et
écrasait la transparence. Une ligne posée après elle rétablit le filigrane :

```css
ModalScreen { background: $background 40%; }
```

La boîte, elle, garde son fond opaque : **son texte ne perd rien en
lisibilité**, seul son pourtour laisse voir l'écran d'origine. Mesuré sur le
rendu : 137 fragments de texte visibles contre 9 auparavant.

### Un seul cadre

Deux familles graphiques coexistaient sans rapport avec le rôle : demi-blocs
`█ ▀ ▄` pour les listes de choix — profil, valeur, donneur, plages — et traits
`┌ ─ │` pour les confirmations et la fiche AlloCiné. Les cinq cadres en
demi-blocs passent au trait fin.

Les couleurs, elles, restent : elles portent le rôle et non la famille — le
`$warning` de l'écran des plages continue d'alerter.

Rendu vérifié sur quatre modales — confirmation, quitter, liste de valeurs,
choix de profil : parent visible, trait fin, plus aucun demi-bloc.

Correspond à l'entrée **IE-06** de `TODO.md`, dont les deux arbitrages ont été
tranchés par le propriétaire du projet.

## [v0.8.1.15] — 2026-08-28

### Le footer suivait l'écran, pas le focus

Pendant l'édition d'un profil, le footer annonçait encore les touches de
l'écran Config — `N Nouveau`, `E Éditer`, `D Supprimer`, `↵ Activer profil` —
alors que le formulaire tenait le focus et que **taper « n » écrivait un « n »
dans le champ courant**. Les vraies touches n'étaient annoncées que par un
bandeau propre au formulaire.

Le comportement était juste : `check_action` neutralisait déjà ces touches.
C'est l'affichage seul qui mentait — et un footer faux vaut moins qu'un footer
vide, puisqu'il invite à des gestes sans effet.

- Le formulaire publie ses raccourcis dans `ProfileForm.RACCOURCIS` ; l'écran
  bascule le footer dessus à l'ouverture et restaure les siens à la fermeture.
- **`F10 Quitter` reste dans les deux états**, comme la convention du projet
  l'exige — la première version le faisait disparaître avec la ligne de
  navigation, ce que le rendu à l'écran a montré.
- **Le formulaire perd son bandeau propre.** Il disait vrai pendant que le
  footer mentait ; maintenant que le footer dit vrai, deux bandeaux répétant la
  même chose, c'en est un de trop.
- La liste des raccourcis de l'écran n'est plus écrite deux fois — elle l'était
  dans les `BINDINGS` et dans la construction du footer.

Rendu vérifié à l'écran, dans les trois états :

```
liste       ↵ Activer profil   N Nouveau   E Éditer   D Supprimer   ⌫ Retour
formulaire  Tab Champ suivant   ⇧Tab Champ précédent   ↵ Ouvrir une liste …
retour      ↵ Activer profil   N Nouveau   E Éditer   D Supprimer   ⌫ Retour
```

### Les tests ne se contaminent plus entre eux

Écrire ce test a révélé un piège : construire l'application pose les chemins
d'outils en **variables de module**, qui survivaient au test et faussaient les
suivants. `test_muxer` attendait `"mkvmerge"` et recevait le chemin absolu du
binaire — selon l'ordre d'exécution, ce qui est la pire forme d'échec.

`tests/conftest.py` sauvegarde et restaure ces variables autour de chaque test.
Un test peut désormais construire l'application sans y penser.

Correspond à l'entrée **IE-05** de `TODO.md`.

## [v0.8.1.14] — 2026-08-27

### Un seul rendu pour les noms de touches

Trois notations coexistaient pour la même information :

| Endroit | Ce qui s'affichait |
|---|---|
| Footer permanent | `Space Sélect` · `Enter Ouvrir` · `Back Retour` |
| Modales et bandeaux | `Espace  Sélectionner` · `↵  Valider` · `Esc  Annuler` |
| Formulaire de profil | `Tab / Shift+Tab : champ suiv./préc.` |

Le nom anglais côtoyait le mot français, le glyphe côtoyait le mot, et
l'espacement changeait d'un écran à l'autre. **Douze bandeaux réécrivaient les
touches à la main.**

- `tui.common` porte désormais la table `TOUCHES` et les fonctions `touche()`,
  `raccourci()` et `raccourcis()` ; `SEP_TOUCHE` et `SEP_ENTREE` fixent
  l'espacement. Le footer lit la même table — son `_fmt_key` n'en est plus
  qu'un alias.
- **Les glyphes sont préférés là où ils existent** : `↵`, `⌫`, `␣`, `←`, `→`,
  `↑`, `↓`. Ils tiennent en une colonne, ce qui compte sur un footer de trois
  lignes — `Space` occupait cinq colonnes pour la même information.
- Une notation composée — `+/-`, `Shift+↑/↓` — traverse intacte : elle ne
  correspond à aucun nom de touche et n'avait pas à être défigurée.

Rendu vérifié à l'écran :

```
␣  Sélect   A  Tout   N  Aucun   ↵  Ouvrir   V  Visualiser   ⌫  Remonter
```

Un test interdit qu'une quatrième notation réapparaisse : il parcourt les
écrans à la recherche des anciennes graphies et échoue si l'une revient.

Le `␣` est le seul glyphe que le projet n'employait pas encore. S'il rend mal
dans un terminal, il se change en une ligne — c'est tout l'intérêt d'une source
unique.

Correspond à l'entrée **IE-04** de `TODO.md`.

## [v0.8.1.13] — 2026-08-27

### Une seule table de couleurs, exprimée en rôles

La même décision portait deux teintes selon l'écran : `→ HEVC` était magenta au
browser et `dark_orange` sur l'écran des pistes. Trois tables indépendantes
coloraient les mêmes notions — celle de `core/decision.py`, celle de
`tracks.py`, et `DV_VALUE_STYLES` dans `tui/common.py` — et le vert signifiait
« gain de taille » ici, « décision de piste » là.

Les couleurs se décident désormais **une fois**, en nommant leur rôle plutôt
qu'en choisissant une teinte :

| Rôle | Ce qu'il signale | Teinte |
|---|---|---|
| `INACTION` | rien ne sera fait | `dim` |
| `SANS_PERTE` | traité sans réencodage, image intacte | `green` |
| `ORDINAIRE` | le cas courant | **aucune** |
| `MODIFIEE` | l'utilisateur a écarté la décision automatique | `bold yellow` |
| `ALERTE` | coûteux, lent, ou destructeur | `bold dark_orange` |

Deux arbitrages, qui étaient les points d'attention du rapport :

- **Le cas ordinaire ne porte plus aucune couleur.** `→ HEVC` occupe presque
  chaque ligne de l'écran le plus dense et portait le magenta, la teinte la plus
  criarde. Ce qui se répète partout n'a pas à attirer l'œil.
- **`dark_orange` n'appartient plus qu'aux alertes** — le tone mapping SDR, qui
  détruit la plage dynamique, et l'AV1, qui coûte des heures. L'écran des pistes
  l'employait pour un encodage HEVC ordinaire, ce qui vidait la réserve de son
  sens.

Le vert, du coup, ne dit plus qu'une chose. La colonne d'estimation de taille
l'utilisait pour « plus petit que la source » : une réduction étant le résultat
attendu, elle ne porte plus de couleur, et seule une sortie **plus grosse** —
une anomalie — passe en alerte.

### Une décision « → HDR10 » s'affichait « ? »

`_ACTION_SHORT` n'avait pas reçu d'entrée pour `VideoAction.STRIP_DV`, introduit
en v0.8.1.6 : l'écran des pistes affichait un point d'interrogation sans couleur
sur tout fichier promis au retrait de Dolby Vision. Un test parcourt désormais
tous les membres de l'énumération.

**Vérification** — sur les huit films du dossier de travail, la décision porte
la même couleur au browser, au dry-run, à l'écran d'encodage et à l'écran des
pistes.

Hors périmètre, à traiter avec le constat 10 : les marqueurs de curseur `◄►`
restent en jaune, qui relève de la navigation et non de la décision.

Correspond à l'entrée **IE-03** de `TODO.md`.

## [v0.8.1.12] — 2026-08-27

### Toute durée d'au moins une heure perdait son dernier chiffre

`fmt_duration` rend sept caractères dès qu'il y a des heures — `3:17:24`. La
colonne en réservait six. Le résultat, `3:17:2`, s'affichait **sans ellipse** :
non pas une valeur visiblement coupée, mais une durée valide et fausse. Tous les
films étaient concernés.

Trois protections, parce que la première seule ne suffisait pas :

- **Le défaut de la colonne passe de 6 à 7.** Mesuré sur le dossier de travail,
  c'était la seule colonne dont le contenu réel dépassait sa largeur — mais
  `debit` et `estim` y tiennent tout juste, à un caractère près.
- **Les planchers remontent dans `core.config.COLUMN_MIN_WIDTHS`**, et
  s'appliquent **à la lecture** autant qu'au redimensionnement. C'est ce qui
  répare les installations existantes : un `config.toml` portant déjà
  `duree = 6`, écrit avant que le plancher existe, l'emportait sur le défaut
  corrigé. Les écrans reprennent cette table plutôt que d'en tenir une seconde.
- **Les cellules numériques portent une ellipse.** Rendu vérifié dans une vraie
  `DataTable` : `3:17:…` avec, `3:17:2` sans. Une coupe qui se voit fait perdre
  une information ; une coupe invisible en invente une.

**Vérification** — sur `resources_files/`, les neuf durées s'affichent entières,
dont le `3:35:23` du plus long film. Et la lecture du `config.toml` réel, qui
portait `duree = 6` au dry-run, rend désormais 7.

Correspond à l'entrée **IE-02** de `TODO.md`.

## [v0.8.1.11] — 2026-08-27

### Le markup Rich mangeait les noms de fichiers et de profils

`Static.update()` interprète par défaut ce qui ressemble à une balise entre
crochets. Or **la convention de nommage du projet est faite de cette syntaxe**.
Mesuré sur le rendu réel :

| Écrit | Affiché |
|---|---|
| `film_[mux].mkv` | `film_.mkv` |
| `film_[hevc].mkv` | `film_.mkv` |
| `film_[av1].mkv` · `film_[hdr10].mkv` | `film_.mkv` |
| `Profil : [serie_basic]` | `Profil :` |
| `film_[H264].mkv` | `film_[H264].mkv` — intact |

L'irrégularité aggravait le piège : `_[H264]` survivait, les autres non, Rich ne
consommant que ce qui ressemble à un nom de style valide. Deux conséquences
visibles à l'écran : **le nom du profil actif était invisible** sur l'écran des
pistes, quel que soit le profil ; et **l'écran de mux annonçait `film_.mkv`**
alors que le fichier produit s'appelait `film_[mux].mkv`.

- **Quatorze afficheurs passent en `markup=False`** — barres d'état des cinq
  écrans, sortie et état du mux, lignes de commande ffmpeg et de progression,
  notice de scan, chemin du donneur, bandeau de recalage, en-tête de
  configuration, titre des modales. Aucun n'utilisait de balise volontaire.
- **Les modales de confirmation gardent leur markup** : elles s'en servent
  réellement, et échappaient déjà les noms interpolés.
- L'audit a porté sur les 32 appels d'affichage des huit écrans concernés ;
  les sites recensés sont ceux qui interpolent un nom, un chemin ou un
  identifiant, pas l'ensemble.

**Vérifications** — le smoke TUI lit désormais ce qui est *rendu*, pas ce qui a
été demandé : le suffixe `_[mux]` doit survivre sur l'écran de mux, et le nom du
profil apparaître dans la barre d'état des pistes. Les deux contrôles ont été
falsifiés — correctif retiré, ils échouent en affichant `Profil :   ·` ; remis,
ils passent. `tests/test_markup.py` verrouille les douze autres afficheurs.

Correspond à l'entrée **IE-01** de `TODO.md`.

## [v0.8.1.10] — 2026-08-27

### L'écran des profils dit ce que chaque réglage entraîne

Un profil se réglait à l'aveugle : les champs portaient le nom de la clé TOML,
et rien ne disait ce qu'un choix impliquait. Le formulaire est réorganisé en
**six sections**, chacune suivie d'une ligne qui énonce la conséquence des
valeurs choisies — recalculée à chaque changement, pas un texte d'aide figé.

| Section | Ce que la conséquence annonce |
|---|---|
| **Quand réencoder** | les seuils en clair, et le sort réservé à une source 4K |
| **Comment encoder** | que le preset ne concerne que les fichiers réellement réencodés |
| **Dolby Vision** | retrait par remux, conservation, ou tone mapping — et l'ordre de grandeur du mode `quality` |
| **Audio sans perte** | ce que devient une piste TrueHD, et le conteneur que le choix impose |
| **Autres pistes audio** | si les pistes déjà compatibles sont recopiées ou retranscodées |
| **Fichier source** | l'irréversibilité de la suppression, en style d'alerte |

### Deux réglages audio qui se contredisaient en silence

`preserve_hd_audio` et `audio_hd_codec` étaient indépendants. Un profil pouvait
donc porter « copier sans perte » **et** « transcoder en E-AC3 », l'un
l'emportant sans que rien ne l'indique — c'est précisément ce qui a produit un
fichier gardant son TrueHD alors que l'E-AC3 était attendu.

L'écran n'expose plus qu'un **choix à quatre branches** : copier telles quelles,
transcoder en E-AC3 au débit de la source, en AC3, ou au forfait. Les deux clés
restent dans `profiles.toml` — le moteur est inchangé et les profils existants
restent lisibles — mais l'écran les écrit toujours cohérentes.

Un profil hérité portant une combinaison contradictoire s'affiche sur la branche
**qui décrit ce qui se passe réellement**, la copie, et non sur l'intention
qu'exprimait le codec.

### Documentation

- Spec § 14.8 réécrite : les six sections et la table de correspondance du choix
  audio vers le couple de clés.
- **L'historique des versions de la spec était en désordre.** Mes quatre
  dernières entrées s'étaient insérées en ordre décroissant, chacune s'ancrant
  sur la précédente, alors que le tableau se lit du plus ancien au plus récent.
  Remis en ordre.

## [v0.8.1.10] — 2026-08-27

### L'interface peut enfin être regardée sans être lancée

Travailler l'UI supposait jusqu'ici de lancer l'application et de naviguer
jusqu'à l'écran en question — ce qui rend toute comparaison impossible : on ne
voit jamais deux écrans côte à côte, et on juge de mémoire.

`tests/shots_tui.py` pilote la TUI en headless, presse les mêmes touches qu'un
utilisateur et exporte chaque écran en SVG dans `_shots/`. **Vingt prises,
couvrant les dix-sept classes d'écran** de `tui/screens/`, à grille fixe
(160 × 45) pour qu'elles soient comparables entre elles.

Le point qui compte : ce sont des rendus, pas des maquettes. Le contexte
principal tourne sur `resources_files/`, c'est-à-dire sur de vrais films — noms
de fichiers à rallonge, 4K, HDR, Dolby Vision, pistes multiples. Ce qui déborde
sur ces captures déborde réellement chez l'utilisateur. Les écrans qui écrivent
(suppression, mux, encodage) sont joués à part, dans un dossier temporaire :
aucune touche destructrice n'est pressée sur le matériel réel.

Deux écrans n'étaient pas atteignables sans matériel taillé pour eux, et le
harnais le fabrique : `RecursiveConfirmModal` exige un dossier sous le curseur,
`SegmentsScreen` n'existe qu'après une mesure ayant constaté deux montages
différents — un SRT à décalage volontairement rompu en son milieu la provoque.

Le matériel mesurable est repris de `smoke_tui.py` plutôt que redéfini.
Aucun changement dans l'application elle-même.

## [v0.8.1.9] — 2026-08-27

### Le README dit enfin à quel problème l'outil répond

Il s'ouvrait sur ses prérequis, c'est-à-dire sur le « comment » d'un « pourquoi »
que rien n'exposait. Une section d'introduction décrit désormais la chaîne de
diffusion — serveur Jellyfin, téléviseur webOS, barre en eARC, clients iOS,
sous-titres image — et **ce que chaque maillon impose**.

L'intersection de ces contraintes est étroite : HEVC en HDR10, audio E-AC3,
sous-titres texte. C'est de là que découlent les partis pris de l'outil, et la
section les énonce comme des conséquences plutôt que comme des préférences : ne
pas réencoder par défaut, retirer le Dolby Vision plutôt que le convertir,
transcoder l'audio au débit de la source, laisser le conteneur suivre le
contenu, et régler tout cela par profil parce qu'un salon et un téléphone ne
demandent pas le même fichier.

Aucun changement de code.

## [v0.8.1.8] — 2026-08-27

### Le débit comparé au seuil est celui de la vidéo, pas celui du fichier

Un profil fixe un débit **vidéo** cible, et c'est un débit vidéo que reçoit
l'encodeur (`-b:v`). Le scanner, lui, comparait le débit du **conteneur** :
vidéo, audio et sous-titres confondus. Les deux termes ne portaient pas sur la
même chose, et l'écart part directement en réencodages injustifiés — d'autant
plus grands que les pistes audio sont grosses.

Relevé sur le dossier de travail :

| Fichier | Conteneur | Vidéo réelle | Écart |
|---|---|---|---|
| Watchmen (TrueHD + AC3) | 9 611k | **5 364k** | **−44 %** |
| Kingdom of the Planet of the Apes | 5 658k | **4 248k** | −25 % |
| Colossus (DTS-HD MA) | 12 241k | **10 209k** | −17 % |
| The Zookeeper's Wife | 11 528k | **9 608k** | −17 % |
| Starship Troopers | 8 148k | **6 784k** | −17 % |

Conséquence concrète, avec le profil `cinema_4k_basic` inchangé (seuil 4K à
8 000k) : **Watchmen et Starship Troopers ne partent plus en réencodage** —
leur vidéo est sous le seuil. Ils basculent sur le retrait de Dolby Vision,
soit quelques minutes et une image intacte au lieu d'heures de GPU et d'une
image dégradée.

- `_video_bitrate()` résout le débit dans l'ordre : `bit_rate` du flux vidéo
  (presque toujours absent en Matroska), puis le tag `BPS` posé par mkvmerge,
  puis le débit du conteneur **moins celui des autres pistes**.
- **Une piste dont le débit reste introuvable ne retire rien** : le résultat
  penche alors du côté prudent, celui du réencodage. Une soustraction qui
  donnerait un résultat nul ou négatif est écartée au profit du total.
- Un second flux vidéo — une pochette embarquée — n'est jamais soustrait.
- La colonne « Débit » de l'accueil affiche désormais le débit vidéo. Elle ne
  correspondra plus à ce qu'annonce un explorateur de fichiers, qui montre le
  débit du conteneur ; c'est en revanche la valeur que le seuil compare.

Le défaut existait depuis l'origine et se voyait d'autant moins que les
fichiers testés portaient de l'audio léger.

## [v0.8.1.7] — 2026-08-27

### Transcoder les pistes HD au débit de la source — `audio_hd_codec`

Le forfait par canaux (`audio_surround_kbps`, 448 kbps par défaut) convient à
une piste déjà compressée. Appliqué à un TrueHD à 3,5 Mbps, il jette beaucoup
plus que nécessaire — surtout quand la destination accepte mieux.

- **Nouvelle clé de profil `audio_hd_codec`** : `none` (défaut, comportement
  inchangé), `ac3` ou `eac3`. Les pistes **TrueHD et DTS, toutes variantes**,
  sont alors transcodées **au débit présent dans la piste**.
- **Plafonds mesurés, pas déduits de la norme.** L'encodeur AC3 de ffmpeg
  ramène en silence toute demande au-dessus de **640 kbps** — demander 6144 en
  produit 640 sans le moindre avertissement. L'E-AC3 honore jusqu'à
  **6 144 kbps** puis refuse la commande. La décision annonce donc le débit
  réellement obtenu, pas celui demandé.
- **Le débit de la source est lu même quand le flux n'en déclare pas.** Un
  TrueHD ou un DTS-HD MA rend `bit_rate=N/A` sous ffprobe : le débit est repris
  du tag Matroska `BPS`, sinon calculé par `NUMBER_OF_BYTES ÷ DURATION`. Sans
  aucune de ces sources, la piste retombe sur le forfait du profil — mieux vaut
  ça qu'une valeur inventée.
- **Réglable depuis l'écran Profils** (`F5` → éditer), à côté du débit 7.1.
- `preserve_hd_audio` garde la priorité : copier sans perte prime sur
  transcoder au débit source.

Mesuré sur les fichiers du dossier de travail :

| Source | `none` | `eac3` |
|---|---|---|
| Watchmen — TrueHD 5.1 @ 3 501 887 | ac3 448k | **eac3 3501k** |
| Colossus — DTS-HD MA 2.0 @ 2 008 937 | aac 192k | **eac3 2008k** |
| The Zookeeper's Wife — DTS 5.1 @ 1 536 000 | ac3 448k | **eac3 1536k** |
| Pilgrimage — DTS 5.1 @ 768 000 | ac3 448k | **eac3 768k** |

### DTS-HD MA reconnu comme sans perte

ffprobe nomme `dts` toutes les déclinaisons et met la famille dans `profile` :
« DTS », « DTS-ES », « DTS-HD HR », « DTS-HD MA ». `is_lossless` ne comparait
que le nom du codec — un **DTS-HD MA passait donc pour un DTS ordinaire**, et
échappait à `preserve_hd_audio` comme à la contrainte de conteneur MKV.
`AudioTrack` porte désormais le champ `profile`, lu au scan.

### Repli 7.1 → 5.1 rendu visible

Les encodeurs `ac3` et `eac3` s'arrêtent au 5.1. ffmpeg replie une source 7.1
de lui-même — vérifié, la sortie est identique à l'octet près avec ou sans
`-ac` — mais rien ne le disait : la décision annonçait « → ac3 640k » sur une
piste 7.1 sans mentionner la perte de deux canaux. La commande pose désormais
`-ac:a:N` explicitement et la décision affiche « → ac3 5.1 640k ».

### Titres de pistes corrigés au transcodage

Le titre d'une piste survivait tel quel à sa conversion : un « ENG VO :
TrueHD 5.1 » devenu E-AC3 continuait d'annoncer un codec absent du fichier —
et c'est précisément ce que lisent les lecteurs, la seule chose que voit
l'utilisateur au moment de choisir sa piste.

- Le jeton de codec est remplacé (`TrueHD`, `DTS-HD MA`, `DDP`, `AC3`…), la
  disposition suit quand elle change, et la mention **Atmos est retirée** :
  les objets sonores ne survivent pas à une conversion vers AC3 ou E-AC3.
- **Un titre qui ne dit rien du format est laissé intact.** « English »,
  « Commentaire du réalisateur » n'ont jamais menti : les réécrire serait une
  modification gratuite. Seul ce qui devient faux est corrigé.
- Une piste **copiée** n'est jamais retitrée : rien n'a changé.

| Titre source | Après transcodage en E-AC3 |
|---|---|
| `ENG VO : TrueHD 5.1` | `ENG VO : E-AC3 5.1` |
| `VO DDP Atmos 5.1` | `VO E-AC3 5.1` |
| `VFF DDP 7.1` (→ AC3 5.1) | `VFF AC3 5.1` |
| `DTS-HD MA 7.1` | `E-AC3 5.1` |
| `English` | inchangé |

Vérifié sur un extrait réel de Watchmen : le fichier produit porte bien
`ENG VO : E-AC3 5.1`, et la piste AC3 recopiée garde son titre d'origine.

## [v0.8.1.6] — 2026-08-27

### Retrait du Dolby Vision sans réencodage

Un fichier Dolby Vision **profil 8.1** porte une couche de base qui *est* du
HDR10 : le RPU n'est qu'un jeu de NAL en plus. Jusqu'ici, demander « DV → HDR10 »
passait forcément par un réencodage — qui dégrade l'image, coûte des heures, et
détruit le HDR10+ au passage. Mesuré sur *La Planète des singes* (4K, 2 h 24) :
1 h 40 en NVENC, **74 h** en libx265.

- **`VideoAction.STRIP_DV`.** Quand le profil demande du HDR10 et que le fichier
  n'a par ailleurs aucune raison d'être réencodé — débit sous le seuil,
  résolution dans les clous, codec standard — la décision devient un retrait de
  RPU : ffmpeg recopie le flux HEVC, `dovi_tool remove` en retire le RPU,
  mkvmerge remuxe avec les pistes de la source. Sortie `<nom>_[hdr10].mkv`.
- **Le profil garde la main.** Dès qu'un des trois cas d'encodage s'applique,
  c'est l'encodage qui l'emporte : il supprime le RPU de lui-même, et stripper
  d'abord réécrirait le film pour rien.
- **Mesuré sur le fichier réel**, pas seulement en test unitaire : 5,7 Go
  traités en **2 min 16 s**, durée du conteneur inchangée à la milliseconde,
  image **bit à bit identique** à la source (`framemd5` concordant à 30 min et à
  1 h 10), **HDR10+ conservé**, master display et MaxCLL conservés, les deux
  pistes audio et les six sous-titres avec leurs titres et leurs drapeaux.
- **Sous-profil détecté pour de bon.** `dv_bl_signal_compatibility_id` distingue
  le 8.1 (couche de base HDR10) du 8.4 (HLG) et du 8.2 (SDR). Le browser affiche
  `DV:P8.1` au lieu de `DV:P8`. Seuls les profils **8.1 et 7** sont éligibles :
  retirer le RPU d'un profil 5 laisse une image aux couleurs fausses.
- **Rien n'est proposé qui ne puisse aboutir.** Sans `dovi_tool` *et* mkvmerge,
  la décision retombe sur `SKIP` plutôt que d'afficher une action qui échouera au
  lancement.
- **Dans les pickers de codec, le retrait de DV se range avec `SKIP`.** Ce n'est
  pas un choix de codec : `ACTION_CYCLE` ne le contient pas, et `cycle_index()`
  lui donne la position de `SKIP` — les deux voulant dire « ne pas réencoder ».
  Choisir `SKIP` sur un tel fichier lève la surcharge au lieu d'imposer un SKIP
  sec, qui laisserait le Dolby Vision en place sans que rien ne l'explique.
- Les intermédiaires sont écrits à côté de la source, pas dans le temp du
  système : ils pèsent le poids du film. Ils sont supprimés dans tous les cas.

### Sortie HDR10 en 10 bits

Le mode d'encodage standard posait `-pix_fmt yuv420p` — 8 bits — quelle que soit
la source. Sur une courbe PQ, cela étale 10 bits de dégradés sur 256 niveaux :
banding garanti dans les ciels et les fondus. Toute source HDR réencodée depuis
la v0.6 en sortait abîmée, y compris sans Dolby Vision.

- Sortie en `yuv420p10le` + `-profile:v main10` dès que le résultat est HDR
  (source PQ/HLG, ou `dv_action == HDR10`) et que l'encodeur sait le porter :
  HEVC et AV1. H264 n'a pas de profil 10 bits chez NVENC — une source HDR
  ramenée en H264 reste en 8 bits, ce qui ne concerne que les cibles < 1080p.

### Documentation

- `iris_encode_spec.md` : nouvelle section 7.3, tables de décision et d'encodage
  mises à jour, et **historique des versions complété** — il s'était arrêté à la
  0.8.0.1 alors que le CHANGELOG suivait.

## [v0.8.1.5] — 2026-08-27

- **Crash au lancement sur toute installation neuve** (v0.8.1.4 uniquement).
  `_deep_merge` ne copiait que le premier niveau : les sous-dictionnaires
  absents du fichier utilisateur étaient assignés *par référence*. Sans
  `config.toml` — donc sur toute machine qui vient de télécharger l'archive —
  `cfg["tui"]["browser"]` **était** `_DEFAULTS["tui"]["browser"]`, et la
  réinitialisation des colonnes introduite en v0.8.1.4 vidait les valeurs par
  défaut du module. Tout accès ultérieur levait `KeyError: 'columns'`.
- La fusion recurse désormais sur toute valeur de type dict, y compris absente
  du fichier utilisateur : aucune branche n'est plus partagée. Le piège
  préexistait et attendait la première écriture en configuration.
- `tests/test_config.py` verrouille l'isolation : une écriture dans la
  configuration ne doit jamais atteindre les défauts du module.

## [v0.8.1.4] — 2026-08-27

- **Largeurs de colonnes de l'accueil revues** : les colonnes numériques n'ont
  besoin que de leur contenu, et la place gagnée revient au nom de fichier et
  aux pistes audio — les deux seules qui débordent vraiment. Résolution 12→10,
  durée 12→6, débit 10→6, codec 8→6, Dolby Vision 12→8, décision 12→8,
  Estim. 16→14.
- **L'écran d'accueil repart des largeurs par défaut à chaque lancement.** La
  section `[tui.browser.columns]` de `config.toml` n'est plus lue au
  démarrage : une disposition stable, identique d'une session à l'autre, vaut
  mieux qu'un réglage qui dérive au fil des redimensionnements ponctuels. Le
  redimensionnement reste actif pendant la session, et les autres écrans
  gardent leurs largeurs mémorisées.

## [v0.8.1.3] — 2026-08-27

- La colonne **« Temps estim. »** devient **« ETA »** au browser et au dry-run,
  et sa largeur par défaut passe de 14 à 9 colonnes. Douze caractères d'en-tête
  pour une valeur qui en fait cinq, c'était de la place prise aux noms de
  fichiers. La clé `temps_estim` est inchangée : les largeurs déjà mémorisées
  dans `config.toml` restent valides.

## [v0.8.1.2] — 2026-08-27

- **Le footer ne se calait plus en bas de la fenêtre.** En passant le footer à
  hauteur variable en v0.8.1.0, son ancrage avait été retiré du browser au
  profit du `1fr` de la table — mais ce `1fr` ne s'appliquait pas : le
  sélecteur de type `DataTable` perd contre le style par défaut du widget, là
  où les autres écrans utilisent un sélecteur d'id. L'ancrage masquait le
  défaut depuis toujours. Corrigé sur le browser et le dry-run.
- La hauteur du footer est désormais posée explicitement plutôt que calculée
  en `auto` : une hauteur `auto` dépend de la largeur, qui dépend de la mise
  en page, qui dépend du `1fr` du contenu — la boucle laissait la table à
  trois lignes.
- Le footer reste dans le flux vertical, jamais ancré : ancré, il recouvrirait
  les dernières lignes de la table au lieu de lui laisser la place.
- **Les raccourcis sont rangés par rôle**, du haut vers le bas : propres à
  l'écran, globaux, puis touches de fonction `F1` à `F10` toujours en dernière
  ligne et triées par numéro. Une place fixe par rôle vaut mieux qu'un ordre
  de déclaration : l'œil apprend où regarder, et les touches qui lancent un
  encodage sont toujours au même endroit.

## [v0.8.1.1] — 2026-08-27

- **`GUIDE.md`** — guide d'utilisation : le parcours en trois temps, les
  raccourcis de chaque écran, une recette pour greffer une VF, et une section
  par cas rencontré (mesure refusée, montage différent, sous-titre image,
  étirement PAL, fichier illisible sur téléviseur…). Les raccourcis sont
  relevés depuis les `BINDINGS` du code, pas rédigés de mémoire.
- Le README précise qu'il couvre l'installation et renvoie au guide pour
  l'utilisation.

## [v0.8.1.0] — 2026-08-27

### Greffe d'une piste venue d'un autre montage

Ajouter une VF et ses sous-titres échouait dès que le donneur n'était pas le
même montage que la cible — le cas courant d'un rip broadcast face à un rip
streaming, dont les coupures publicitaires décalent tout ce qui suit.

- **Détection des plages** (`s`). Quand le recoupement par tiers constate que
  le décalage ne tient pas sur tout le film, la mesure cherche désormais s'il
  tient *par morceaux* : fenêtres de 2 min, fusion des voisines concordantes,
  affinage de chaque frontière à la seconde, puis remesure sur l'étendue
  définitive. Deux garde-fous écartent un découpage qui ne serait que du bruit
  de corrélation. Le refus nomme ce qu'il a vu au lieu d'une hypothèse
  générique.
- **Recalage des sous-titres** (`p`). Exact : il n'y a que des horodatages à
  décaler. `shift_srt()` réécrit chaque réplique avec le décalage de sa plage
  et produit un `.srt` recalé qui devient la source de la piste.
- **Recalage de l'audio** (`p`). L'opération est une **insertion**, pas une
  coupe : le décalage croissant signifie que la cible porte du contenu que le
  donneur n'a pas — celui-ci peut être plus long au total, ses minutes
  excédentaires étant dans le générique. Les insertions s'ancrent sur le
  silence le plus proche, la frontière de corrélation étant juste à une ou
  deux secondes près. Faute de silence, l'insertion est posée quand même et
  signalée : contrairement à une coupe, allonger n'efface rien.
- Les plages viennent toujours de l'audio du donneur : le signal d'un
  sous-titre est trop creux pour les retrouver seul, et les pistes d'un même
  donneur portent le même montage.
- **Sous-titres embarqués mesurables.** Une piste `mov_text` ou SRT logée dans
  un conteneur n'avait aucune réplique lisible et la mesure refusait pour
  « format inconnu ». Elle est désormais extraite vers un `.srt` temporaire.
  Un sous-titre image (PGS, VobSub) est refusé pour ce motif propre.

Vérifié sur un épisode réel : 6 plages, cinq paliers de +2 000 ms, et les
pistes produites mesurent **+0 ms de décalage résiduel** — l'audio avec une
confiance de 0,72 et trois tiers concordants à 0 ms.

### Corrections

- **Fichiers illisibles sur téléviseur après un encodage `F2` avec piste
  greffée en décalage négatif.** Un `-itsoffset` négatif rend négatifs les
  horodatages du donneur ; ffmpeg refuse de les écrire et décale *tout le
  fichier* vers l'avant. Mesuré pour −2 500 ms : la vidéo sortait avec
  `start_time = 2.5 s`. mpv et VLC normalisent sans broncher, un décodeur
  matériel de TV non. Le décalage négatif passe désormais par `-ss` sur
  l'entrée du donneur.
- **Une piste étirée n'interdit plus l'encodage.** `F2` refusait et renvoyait
  l'utilisateur muxer lui-même avant de revenir encoder — un travail que
  l'outil sait faire. mkvmerge greffe vers un intermédiaire temporaire juste
  avant l'encodage. Le surcoût n'est payé que dans ce cas ; sans mkvmerge, le
  refus a lieu en amont plutôt qu'au milieu d'un encodage.
- `tests/smoke_tui.py` mourait sur le même `UnicodeEncodeError` que `main.py`
  corrigeait en v0.8.0.2, ce point d'entrée ne passant pas par `main()`.

### Interface

- **Footer réparti sur plusieurs lignes.** Il tenait sur deux lignes fixes et
  tronquait l'excédent en silence : au-delà de ~147 colonnes, soit dès un
  1920×1080, `F1`, `F2`, `F3` et `Back` disparaissaient sans que rien ne
  signale leur existence. `KeyFooter` répartit les raccourcis sur autant de
  lignes qu'il en faut ; aucun n'est jamais coupé ni omis. Libellés raccourcis
  en complément — l'écran de recalage passe de 245 à 166 colonnes.
- **Troisième ligne du bandeau de recalage invisible.** `height: 3` avec une
  bordure haute ne laissait que deux lignes de texte, la perdue étant toujours
  celle qui renvoie vers `a` ou `s`. Défaut présent depuis la v0.8.0.
- **Le recalage audio ne donnait aucun signe d'activité** : la barre atteignait
  85 % puis restait figée pendant tout le réencodage — 65 des 82 secondes de
  l'opération. ffmpeg rapporte désormais sa progression. Le libellé annonçait
  par ailleurs « Mesure en cours » pendant un recalage.

## [v0.8.0.2] — 2026-08-26

- **Démarrage hors console corrigé.** `main.py` mourait sur un
  `UnicodeEncodeError` avant d'afficher quoi que ce soit dès que sa sortie
  n'était pas une vraie console Windows — redirection vers un fichier, pipe,
  lancement depuis Git Bash, WSL ou une tâche planifiée. Python retombe alors
  sur l'encodage local (cp1252 en français), où le cadre de la bannière et les
  coches `✓`/`✗` n'existent pas. `stdout` et `stderr` sont désormais forcés en
  UTF-8 avant le premier `print`. Le double-clic sur `launch.bat` n'était pas
  affecté, ce qui explique que le défaut ait survécu depuis la v0.7.0.

## [v0.8.0.1] — 2026-08-26

- **`Ctrl+D` — supprimer le fichier sous le curseur** depuis le browser, avec
  confirmation (`tui/screens/delete_confirm.py`, bâtie sur `ConfirmModal`, focus
  initial sur *Annuler*). Pendant de `v` : juger une source amène parfois à
  constater qu'elle ne vaut rien. Suppression définitive, sans corbeille ; la
  ligne disparaît sans re-scanner le dossier. Un fichier encore ouvert dans mpv
  fait échouer la suppression sous Windows — le message le dit.
- **Documentation** : consolidation des trois specs concurrentes en un document
  unique à nom fixe (`iris_encode_spec.md`) suivant la version.

## [v0.8.0] — 2026-08-26

### Greffe de pistes externes

Ajouter à un fichier une piste audio ou des sous-titres venus d'un autre
fichier, sans réencoder la vidéo, chaque piste portant son propre décalage.

- **`F9` — piste externe** depuis l'écran des pistes ou celui du recalage :
  choix du fichier donneur, puis de ses pistes via `mkvmerge -J`. Plusieurs
  donneurs s'enchaînent sans quitter l'écran.
- **Écran de recalage** : décalage réglable au clavier (`+/-` par 100 ms,
  `Shift+↑/↓` par seconde), facteur d'étirement PAL↔film, langue, nom,
  drapeaux défaut et forcé. `c` reprend le décalage d'une autre piste — le cas
  d'une VF et de ses sous-titres écrits sur le même timing.
- **`m` — mesure automatique du décalage** par corrélation croisée. Pour une
  piste audio, les deux enveloppes d'énergie ; pour un sous-titre, les
  répliques contre un VAD appliqué à la parole du film. Le facteur d'étirement
  est cherché sur une grille de ratios. Le résultat est recoupé sur trois
  tiers du film : un vrai alignement tient sur chacun, du bruit se disperse.
- **`v` — visualiser dans mpv** avec la piste greffée et le décalage appliqué,
  positionné sur un passage dialogué.
- **`k` — extrait de contrôle** réellement muxé, découpé par mkvmerge sur le
  flux de sortie. Deux fenêtres quand un étirement est en jeu, la dérive
  s'accumulant.
- **`F3` — mux** par mkvmerge, ou **`F2` — encodage** : ffmpeg absorbe alors
  les pistes dans la même passe, sans fichier intermédiaire.
- Après un mux, le fichier produit devient le fichier de travail.

### Outils

- **mkvmerge et mpv** rejoignent les outils optionnels, installés depuis leur
  archive portable. mpv n'étant publié qu'en `.7z`, l'extraction passe par le
  tar/libarchive livré avec Windows plutôt que par une dépendance nouvelle.
- **Vérification des mises à jour au démarrage**, au plus une fois par jour et
  sans bloquer hors ligne. `check_on_startup`, le cache des versions et la
  vérification SHA256 étaient déclarés mais inertes.

### Estimation

- Colonne **Temps estim.** au dry-run, appuyée sur une moyenne mobile de vitesse
  d'encodage relevée à chaque passe. (`Estim. (Δ%)` avait été ajoutée en v0.6.5,
  `Durée` en v0.7.1.)

### Corrections

- Le conteneur de sortie suit les pistes réellement conservées : écarter les
  sous-titres image libère le MP4. `mov_text` n'est plus proposé en Matroska.
- Les listes de dépendances de `main.py` et `launch.bat` couvrent
  `requirements.txt` ; un test les compare.
- Le preflight ne dépend plus d'un terminal interactif.
- `.gitattributes` impose le CRLF aux scripts Windows.

## [v0.7.1] — 2026-08-06

- **Dry-run : colonne « Durée »** entre Taille et Estim. (Δ%) — durée de chaque
  fichier au format h:mm:ss, redimensionnable comme les autres colonnes
  (largeur persistée dans `config.toml`).
- **Sélecteur de profils (F4) en vraie table** (`tui/screens/profile_picker.py`) :
  colonnes alignées (Profil, 1080p, 4K, DV, Preset, HD audio, Source), profil
  actif marqué ✓, valeurs DV colorées, alerte `⚠ suppr.` sur les profils qui
  suppriment la source. Remplace les chaînes paddées à la main ; le callback
  reçoit l'id du profil (plus robuste qu'un index). Utilisé par Browser et
  TracksScreen.
- Correction du crash `NoMatches` sur `Backspace` pendant un encodage.
- Gestion des événements clavier dans les modales de saisie.

---

## [v0.7.0] — 2026-06-10

### Normalisation UIX

- **Touches « Retour » unifiées** : `Backspace` / `Esc` sur tous les écrans. ConfigScreen
  utilisait `←` (et son footer affichait à tort `Backspace`) — corrigé.
- **Modale de confirmation générique** (`tui/screens/confirm.py`) : quitter, run récursif
  et suppression de profil partagent désormais le même style (bordure `$warning` si
  destructif), les mêmes touches (`←/→` focus, `↵` valide le bouton focalisé,
  `Esc`/`⌫` annule) et un rappel des touches intégré.
- **Modale Quitter sécurisée** : `Enter` validait la sortie même avec le focus sur
  *Annuler* (binding priority) — désormais `Enter` active le bouton focalisé.
- **Suppression de profil enfin câblée** : la colonne Actions de ConfigScreen affichait
  « ✕ suppr. » sans qu'aucune touche n'y mène. `D`/`Suppr` supprime le profil user
  sous le curseur (confirmation, builtins protégés avec message).
- **Footers normalisés** (`tui/common.py`) : libellés identiques pour les mêmes touches
  (Début/Fin/Page ↑/Page ↓), groupes navigation + resize partagés, `F10 Quitter`
  toujours en dernier, doublon `↵`/`F2` du dry-run supprimé.
- **Hints contextuels** : TracksScreen affiche les contrôles selon la ligne (champs
  ←/→ et +/- sur la ligne vidéo, Espace/↵ sur les pistes) — ils étaient documentés
  mais invisibles. ValuePicker affiche `↵ Choisir · Esc Annuler`.
- **Version unique** (`version.py`) : le header TUI affichait `v0.6` et la bannière
  console `v0.6.5` — les deux lisent la même constante.
- **Barre de statut commune** : classe CSS `.status-bar` au niveau App (le même bloc
  était dupliqué dans 5 écrans), couleurs DV des profils centralisées.
- ConfigScreen : compteur AV1 ajouté au résumé dry-run ; la barre profil du browser
  se rafraîchit après activation d'un profil dans ConfigScreen (elle restait sur
  l'ancien profil).

### Corrections

- **Home/End/PgUp/PgDn restaurés sur Tracks et Config** : leurs `on_key` locaux
  écrasaient celui de `TableNavMixin` (les touches scrollaient sans déplacer le
  curseur). Les écrans délèguent désormais à `super().on_key()`.
- Les erreurs de scan du browser sont logguées (`~/.iris_encode/iris_encode.log`)
  au lieu d'être avalées silencieusement.

### Optimisations

- **Scan parallèle** : le browser analyse les fichiers avec 4 workers ffprobe
  simultanés (ordre des résultats préservé) au lieu d'un scan séquentiel ; la
  navigation pendant un scan abandonne les analyses restantes au lieu de les
  terminer pour rien.
- Dry-run : un seul `stat()` par fichier (taille réutilisée entre la ligne et le
  résumé, soit 2-3× moins d'appels disque).
- **Dé-duplication** (~150 lignes) : sélecteur de profils (browser/tracks), resize
  de colonnes (`ColumnResizeMixin` — browser/tracks/dryrun), formatage
  tailles/durées, options des pickers codec/débit (`tui/common.py`).
- Code mort retiré : messages Textual jamais postés et `_update_progress` (run),
  styles `_STYLE_*` et imports inutilisés (browser), `_force_nav` (mixins),
  constante `_ROW_VALIDATE` (tracks).

### Tests

- `tests/smoke_tui.py` : smoke test headless (Textual `run_test`) — navigation,
  modales, resize, scan parallèle. Lancement manuel : `python tests/smoke_tui.py`.

---

## [v0.6.5] — 2026-06-09

### Décision d'encodage
- **Seuils `near_1080p` paramétrables** (`config.toml`, section `[decision]`, 1600×850 par défaut) : les sources rognées (typ. 1918×1040, 1920×800 HDLight) sont désormais traitées comme du 1080p — résolution d'origine conservée, codec HEVC. Auparavant rabattues en 720p H264.
- `_resolve_limits` dissocie `limit_h` (cap résolution) et `bucket_h` (référence bitrate) pour éviter les rabats incohérents quand la source est entre 720p et 1080p strict.

### Dry-run — édition par fichier
- **F6 / F7** sur l'écran dry-run : picker `Codec` (HEVC / H264 / AV1 / SKIP) et `Débit cible` (échelle dédiée si AV1), appliqués à la ligne sous le curseur.
- Cohérence garantie à la modif : `output_suffix` aligné sur le codec, `DV → HDR10` forcé si passage en H264 (RPU incompatible), débit source pré-rempli sur `SKIP → encodage`, snap d'échelle si passage à AV1, recalcul auto de l'estimation et du résumé.

### Profils
- `bitrate_4k_kbps` réduit sur `film_basic` (5000→3000), `film_hd` (8000→5000), `basic_delete` (3500→2000).

### Interne
- Constantes vidéo mutualisées dans `core/decision.py` : `ACTION_CYCLE`, `BITRATE_OPTS_KBPS`, `AV1_BITRATE_OPTS_KBPS`, `SUFFIX_BY_ACTION` (fin de duplication entre `tracks.py`, `browser.py`, `dryrun.py`).
- Spec `iris_encode_spec_v0_5.md` retirée (remplacée par v0.6 depuis `58a3923`).

---

## [v0.6] — 2026-05-14

### Intégration Dolby Vision via dovi_tool

Trois PRs internes pour intégrer pleinement `dovi_tool` dans le pipeline d'encodage.

#### PR1 — Module `core/dovi.py`
- Wrapper standalone autour de `dovi_tool` :
  - `get_path()` / `is_available()` : détection (PATH + `./bin/`)
  - `probe_file()` : extrait sous-profil DV + master display + MaxCLL en un appel (50-150ms)
  - `extract_hevc_stream()` / `extract_rpu()` / `convert_p7_to_p8()`
  - `rpu_info()` : parsing structuré de la sortie `dovi_tool info`
  - `make_x265_hdr_params()` : construction des tokens `-x265-params` HDR10
- 15 tests unitaires (mock subprocess)
- URL Linux ajoutée dans `data/ffmpeg_releases.toml` (l'install auto Windows était déjà gérée par `preflight.py`)

#### PR2 — Scanner enrichi
- `VideoInfo` gagne 3 champs optionnels : `dv_subprofile`, `hdr10_master_display`, `hdr10_max_cll`
- `scanner.scan()` appelle `dovi.probe_file()` si DV détecté et `dovi_tool` disponible — pas de surcoût sur les fichiers non-DV
- `TracksScreen` affiche désormais le sous-profil exact (`DV:P8.1`, `DV:P5`…) en colonne Source
- Avertissement inline `⚠ dovi_tool absent` si HDR10 demandé sans dovi_tool

#### PR3 — Pipeline HDR10 quality
- Nouveau champ profil `hdr10_quality` : `"compat"` (NVENC, défaut) | `"quality"` (libx265 CPU)
- Nouveau profil builtin **`cinema_4k_quality`** : `hdr10_quality = "quality"`, encodage CPU avec :
  - `libx265` + `yuv420p10le` + `profile main10`
  - `-x265-params` injecté avec `master-display`, `max-cll`, `hdr10-opt=1`, `colorprim=bt2020`, etc.
  - hwaccel désactivé automatiquement (CPU obligatoire pour metadata HDR10 fines)
- `ProfileForm` expose le champ HDR10 mode

### Reporté en v0.7
- **Conversion P7→P8 pour DV preserve** : pertinent uniquement quand `dv_action == DV` (LG préfère P8). Pour `dv_action == HDR10`, le RPU est de toute façon supprimé et la conversion P7→P8 du RPU n'apporte rien — donc non implémenté ici.

---

## [v0.5] — 2026-05-14

### Correctifs critiques
- **Garde-fou anti-écrasement source** dans `build_command` : refuse l'encodage si `output_path == input_path` (évite la corruption irréversible)
- **Fallback DV obsolète** : `profiles.py` retournait `"hdr"` (ancien nom) à la place de `"hdr10"` pour les profils sans champ explicite — styling cassé corrigé
- **Forçage SKIP : `dv_action` désormais cohérent** avec l'action forcée (H264 + source DV → HDR10 obligatoire, le RPU étant incompatible)

### Correctifs importants
- **`_eff_*` falsy bug** (`tracks.py`) : `or` retournait la valeur source quand l'override valait `0` ou `VideoAction.SKIP` (truthy). Remplacé par `is not None`.
- **Override `action` recalcule `output_suffix`** dans BrowserScreen : un passage HEVC→H264 via TracksScreen ne laisse plus un nom `_[hevc]` incorrect
- **Override SKIP→encode** : si la décision originale était SKIP (bitrate=0) et qu'on passe à une action d'encodage, le débit source est appliqué par défaut
- **Code mort retiré** : `_extract_dv_to_hdr10_json` jamais appelée — supprimée (dette technique). Réintégration prévue avec dovi_tool complet en v0.6.
- **Run récursif filtrait SKIP par `.name`** (string) au lieu d'enum — uniformisé
- **DryrunScreen footer** : `ctrl+x` (binding inexistant) → `f10`
- **Helper `_force_skip_to_encode`** : extraction de la duplication entre `action_open_dryrun` et `action_open_run`

### Nouveautés
- **DryrunScreen** : nouvelle colonne **Estim. (Δ%)** avec la taille de sortie estimée par fichier (`bitrate × durée / 8`) et le ratio de compression vs source. Summary global avec total source → estimé.
- **RunScreen** :
  - Nouveau raccourci `s` pour **passer le fichier en cours** sans annuler tout le batch
  - Le binding `enter` "Démarrer" (devenu menteur depuis le démarrage auto) a été retiré
  - Gestion propre des erreurs `build_command` (fichier en erreur, on enchaîne sur le suivant)
- **TracksScreen** : le **profil actif** est désormais affiché dans la status bar
- **Logging** : les erreurs de scan ne sont plus avalées silencieusement — fichier de log dans `~/.iris_encode/iris_encode.log` (niveau WARNING)

---

## [v0.2] — 2026-05-14

### Correctifs
- **DryrunScreen** : passage d'un `dict` au lieu d'une liste lors du lancement F1 depuis TracksScreen — corrigé avec `[dec]` (fichier courant uniquement)
- **TracksScreen** : `_make_selection()` appelée avec un argument superflu — TypeError corrigé
- **BrowserScreen** : `action_open_run()` filtrait les fichiers SKIP même s'ils étaient cochés manuellement

### Nouveautés
- **TracksScreen** : la colonne Décision affiche désormais systématiquement l'info Dolby Vision : `DV - N/A` si la source n'en a pas, `DV → HDR10 / DV → DV / DV → SDR` selon le traitement actif
- **Fichiers SKIP forcés** : sélectionner manuellement un fichier SKIP dans le navigateur l'inclut dans le dry-run/run en le forçant en HEVC (ou H264 si < 1080p) au débit source — sans jamais augmenter le débit existant
- **DryrunScreen** : raccourci `R` remplacé par `F2` pour cohérence avec les autres écrans
- **RunScreen** : l'encodage démarre automatiquement à l'ouverture — confirmation Enter supprimée

---

## [v0.1] — 2026-05-13

- Version initiale : navigateur de fichiers, décisions vidéo/audio, profils, encodage HEVC/H264, support Dolby Vision (HDR10/DV/SDR), dry-run, run, récursif, métadonnées IMDB/OMDb
