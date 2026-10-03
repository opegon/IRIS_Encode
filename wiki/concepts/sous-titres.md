---
type: concept
maj: 2026-09-30
sources:
  - "[[source-spec]]"
  - "[[source-changelog]]"
  - "[[source-2026-09-24-diagnostic]]"
  - "[[source-2026-09-30-lecture]]"
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
Relevé sur Starship Troopers et Watchmen *(mesuré)* :

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

Colossus n'a qu'un sous-titre, image : l'écarter reviendrait à perdre les
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
(`film.fre.srt`, `film.VF.srt`).

## Chapitres en MP4

Voir [[conteneurs#Chapitres|Conteneurs]] : la piste `bin_data` d'un MP4
n'est pas un sous-titre parasite.

## Trouver un sous-titre en ligne

Voir [[opensubtitles]] : recherche par empreinte (release exacte, déjà
synchronisée) ou par nom, quotas, pièges de l'API.

## Voir aussi

[[chaine-de-diffusion]] · [[jellyfin]] · [[conteneurs]] · [[synchronisation]] · [[mkvmerge]] · [[opensubtitles]]
