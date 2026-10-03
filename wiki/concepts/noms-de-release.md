---
type: concept
maj: 2026-10-01
sources:
  - "[[source-spec]]"
  - "[[source-changelog]]"
  - "[[source-2026-09-24-utilisateur]]"
---

# Noms de release

Dans une médiathèque, c'est le **nom** qui dit ce qu'est un fichier. Un nom de
release décrit la source ; le fichier produit n'a plus forcément ses
propriétés. Règles d'IRIS : spec § 8.7.

## Les marques

| Famille | Jetons rencontrés |
|---|---|
| Définition | `2160p`, `4K`, `4KLight`, `UHD`, `1080p`, `720p` |
| Codec vidéo | `x264`, `x265`, `H264`, `H.264`, `H265`, `H.265`, `HEVC`, `AV1`, `VP9`, `[hevc]` |
| Dolby Vision | `DV`, `DoVi`, `Dolby Vision` |
| HDR | `HDR`, `HDR10`, `HDR10+`, `HDR10Plus` |
| Profondeur | `10bit`, `10bits`, `10 bits` |
| Audio | `TrueHD`, `True-HD`, `MLP`, `DTS-HD MA`, `DTS-X`, `DTS`, `DD+`, `DDP`, `E-AC3`, `AC3`, `FLAC`, `LPCM`, `Opus`, `Atmos`, `5.1`, `7.1` |
| Langue | `MULTi`, `VFF`, `VF2`, `VOF`, `FRENCH` |
| Source | `BluRay`, `WEB-DL`, `WEBRip`, `Remux` |
| Groupe | dernier terme après un tiret : `x265-GROUPE`, `1080p - GROUPE` |

## Pièges d'analyse

- **Mot entier** : le `4K` de `H4K`, le `2160` de `3840x2160`, le `AV1` de
  `AV1ator`, le `DD` de `ADD` ne sont pas des marques.
- **Le plus long d'abord** : sinon `DTS` l'emporte sur `DTS-HD MA` et laisse
  un `.MA` orphelin.
- **Séparateurs interchangeables** : `DTS-HD.MA`, `DTS-HD-MA`, `DTS HD MA`.
- **`HDR10+`** ne doit pas perdre son `HDR10` en gardant son `+`.
- **Crochets et parenthèses** partent avec la marque : `Film [hevc]` ne doit
  pas laisser `Film []`.
- **Fin de nom** : retirer deux marques finales laisse un séparateur nu
  (`Film.DV.HDR10` → `Film.`).
- `HDR10Plus` et `HDR10P` sont des graphies de `HDR10+`. Avant v0.8.9.48,
  elles restaient dans une sortie SDR et le suffixe redisait `.hdr10`.
  `HDR10Plus.DV` → `HDR10Plus.HDR10` au retrait du RPU est, lui, le
  comportement voulu, comme pour `HDR10+`. *(corrigé en v0.8.9.48, IE-81)*
- Un titre peut finir comme une marque : `Film-Iris`. La marque `-iris`
  d'IRIS est donc sensible à la casse.
- **Un tiret final n'annonce pas toujours un groupe** : `Spider-Man`,
  `Titre - Sous-titre` sont des titres, `DTS-HD` et `WEB-DL` des marques. Le
  groupe n'est retiré que si le reste du nom porte une marque de release et
  que le dernier terme n'en est pas une.

## Ce que la conversion rend faux

| Traitement | Marque devenue fausse |
|---|---|
| Rabattre en 1080p | `2160p`, `4K`, `UHD` |
| Réencoder | le codec de la source (`x264`, `x265`, `AV1`…) |
| Retirer le RPU | `DV`, `DoVi` (→ `HDR10`) |
| Convertir en SDR | toute marque HDR, `HDR10+`, la profondeur 10 bits |
| Transcoder l'audio | la famille (`TrueHD` → `E-AC3`), `7.1` → `5.1`, `Atmos` |

Exemple complet : `Film.2160p.DV.HDR10.x265.TrueHD.7.1-GROUP` ressort
`Film.1080p.HDR10.E-AC3.5.1.hevc-iris`.

## Conventions d'IRIS

- Toute sortie finit par **`-iris`**, en minuscules, précédée d'une
  caractéristique **en minuscules** : `.hevc`, `.h264`, `.av1`, `.dv`,
  `.hdr10`, `.mux`, `.join`. Préférence de l'utilisateur (2026-10-01) : une
  marque sobre, détachée comme un groupe, plutôt que `.IRIS`, jugée criarde.
- **Le groupe de la source ne passe pas dans la sortie** : `-iris` en prend
  la place (préférence de l'utilisateur, 2026-10-01).
- L'ancienne marque **`.IRIS` n'est plus reconnue** (choix de l'utilisateur) :
  ces sorties redeviennent des sources, `.IRIS` restant dans le nom d'un
  réencodage.
- Une caractéristique que le nom annonce déjà n'est pas répétée.
- Collision : `Film.hevc-iris(2).mkv`. Rien n'est jamais écrasé.

## Voir aussi

[[codecs-video]] · [[hdr-dolby-vision]] · [[audio]]
