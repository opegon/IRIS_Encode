---
type: concept
maj: 2026-10-09
sources:
  - "[[source-spec]]"
  - "[[source-changelog]]"
  - "[[source-2026-09-24-diagnostic]]"
  - "[[source-2026-09-30-lecture]]"
  - "[[source-2026-10-04-mov-text]]"
---

# Sous-titres

## Texte contre image

| Format | Nature | MP4 | MKV | Jellyfin → client |
|---|---|---|---|---|
| **SubRip (SRT)** | texte | ✓ en `mov_text` | ✓ | envoyé tel quel, lecture directe |
| `mov_text` | texte | ✓ | ✗ (jamais proposé) | lecture directe |
| **ASS / SSA** | texte stylé | ✗ : le style ne survit pas à `mov_text` | ✓ | |
| **PGS** (HDMV, Blu-ray) | image | ✗ | ✓ | **incrusté**, donc transcodage vidéo complet |
| **VobSub** (DVD) | image | ✗ | ✓ | idem |

**Aucun client ne reçoit un sous-titre image tel quel** (observé, README).
Sur un serveur sans transcodage matériel, un PGS sélectionné suffit à rendre
un film 4K illisible (voir [[chaine-de-diffusion|Chaîne de diffusion]]).

Un sous-titre image n'a **pas de texte** : il ne se mesure pas pour un
recalage (voir [[synchronisation|Synchronisation]]) et ne se convertit pas
en SRT sans OCR.

## Ce que portent les releases

Les rips Blu-ray MULTi doublent souvent chaque sous-titre en SRT et en PGS.
Relevé sur Film B et Film A *(mesuré)* :

```
SRT fre  default FORCED  « FR Forced : SRT »
SRT fre                  « FR Full : SRT »
SRT eng                  « ENG Full : SRT »
PGS fre          FORCED  « FR Forced : PGS »
PGS fre                  « FR Full : PGS »
PGS eng                  « ENG Full : PGS »
```

Un rip streaming peut embarquer **43 sous-titres** : sans filtre, tous
traversent la chaîne. La clé `subtitle_languages` du profil trie (43 → 4 sur
le fichier de test). *(mesuré, v0.8.2.0)*

Film E n'a qu'un sous-titre, image : l'écarter reviendrait à perdre les
sous-titres, donc la sortie reste en MKV.

## Drapeaux par défaut et forcé

- **Forcé** : sous-titre des seuls passages en langue étrangère (« FR Forced »).
- **Par défaut** : celui que le lecteur choisit sans qu'on demande.
- **mkvmerge pose d'office le drapeau par défaut sur le premier sous-titre**
  qu'on lui donne, sans qu'on le demande : les sous-titres s'affichent chez
  l'utilisateur. Poser `--default-track-flag TID:0` explicitement.
  *(mesuré, spec § 9.5 piège 4)*
- Un PGS marqué forcé ou par défaut peut être sélectionné automatiquement par
  Jellyfin, ce qui déclenche l'incrustation. *(supposé, jamais observé)*
  **Politique retenue** (v0.8.9.40) : un PGS forcé doublé par un SRT forcé de
  même langue est écarté de la sortie ; seul forcé de sa langue, il reste.
  Forcé = drapeau du conteneur **ou** « forced » / « forcé » dans le titre.
  Une sélection manuelle n'est pas touchée.
  **Étendue** (v0.8.9.47) aux sous-titres complets : un PGS complet doublé par
  un SRT complet de même langue est écarté aussi. La nature (forcé / complet)
  doit concorder : un SRT forcé ne remplace pas un PGS complet.
- **Une greffe « par défaut » retire le drapeau de la source.** Sinon deux
  pistes du même type sont par défaut et le lecteur prend la première : le
  choix reste sans effet. Mesuré au mux (mkvmerge v82) comme à l'encodage
  (ffmpeg 6.1). *(revue IE-114, CR-23/25 ; corrigé en v0.8.9.103)*

## Jeu de caractères d'un `.srt`

Beaucoup de `.srt` circulent en **cp1252**, pas en UTF-8. ffmpeg lit un
sous-titre texte en UTF-8 : un `.srt` cp1252 perd **toutes ses répliques
accentuées** (« Invalid UTF-8 in decoded subtitles text »), avec un code de
retour nul. *(mesuré, revue IE-114, CR-50)* mkvmerge sans BOM suit le jeu du
système : sous Linux (UTF-8) il tronque un cp1252 à la première lettre
accentuée ; sous Windows en français (cp1252), il lit juste le cp1252 comme
l'UTF-8 — mesuré le 2026-10-09, mkvmerge de `bin/`. Toujours dire le
jeu : `-sub_charenc` avant l'entrée ffmpeg, `--sub-charset TID:<jeu>` pour
mkvmerge. Un `.sub` peut être du MicroDVD (texte) ou du VobSub (binaire, début
`00 00 01 BA`).

## Polices jointes

Les sous-titres ASS d'un animé s'appuient sur des polices **jointes** au MKV.
ffmpeg ne les recopie pas sans `-map 0:t? -c:t copy` : la sortie s'affiche
dans une police de repli, panneaux et karaokés faux. mkvmerge les garde.
*(reproduit, revue IE-114, CR-20)*

## Long silence en MP4

**Un silence de plus de 2 147,48 s efface les temps d'un `mov_text`.** Le
muxeur MP4 de ffmpeg (8.1.2, 8.1.3) colle alors au début du film la réplique
suivante et toutes celles d'après, sans message. Cas typique : la piste forcée,
dont la première réplique arrive tard. *(mesuré, [[source-2026-10-04-mov-text]])*
IRIS passe ces pistes par un Matroska porteur où une réplique invisible
(espace insécable, 1 ms) coupe chaque tranche de 1 800 s (v0.8.9.62,
`core/sous_titres.py`).

## Langues

ISO 639-2 a **deux jeux de codes** pour vingt langues :

| Bibliographique | Terminologique |
|---|---|
| `fre` | `fra` |
| `ger` | `deu` |
| `dut` | `nld` |
| `chi` | `zho` |
| `gre` | `ell` |
| `rum` | `ron` |
| `slo` | `slk` |
| `cze` | `ces` |

Les conteneurs emploient l'un ou l'autre **sans règle**, jusqu'à mêler les
deux dans un même fichier : huit codes terminologiques relevés dans un seul
épisode. Comparer les chaînes brutes faisait **disparaître une VF étiquetée
`fra`** d'un profil qui demande `fre`. *(mesuré, v0.8.2.0)* Comparer après
normalisation, afficher ce que le fichier déclare.

Un `.srt` nu ne porte **aucune** langue : sans saisie, il devient « und »
dans tous les lecteurs. La langue peut se lire dans le nom
(`film.fre.srt`, `film.VF.srt`) — **mais les codes courts sont aussi des mots
de titre** : « La Cité **de** la peur » donnait l'allemand, « **It** »
l'italien, « Paris **en** fête » l'anglais. Un code court ne vaut qu'en
dernière position ; « VO » ne dit pas quelle langue. *(revue IE-114, CR-26)*

**En MP4, un sous-titre greffé a le même défaut de long silence** que ceux de
la source (section suivante) : il passe par le même porteur depuis la
v0.8.9.104. *(reproduit, CR-34)*

## Chapitres en MP4

Voir [[conteneurs#Chapitres|Conteneurs]] : la piste `bin_data` d'un MP4
n'est pas un sous-titre parasite.

## Trouver un sous-titre en ligne

Voir [[opensubtitles]] : recherche par empreinte (release exacte, déjà
synchronisée) ou par nom, quotas, pièges de l'API.

## Voir aussi

[[chaine-de-diffusion]] · [[jellyfin]] · [[conteneurs]] · [[synchronisation]] · [[mkvmerge]] · [[opensubtitles]]
