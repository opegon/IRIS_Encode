---
type: concept
maj: 2026-09-24
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
- `HDR10Plus` n'est **pas** reconnu comme `HDR10+` : `HDR10Plus.DV` devient
  `HDR10Plus.HDR10` au retrait du RPU. *(constaté le 2026-09-24, non corrigé)*
- Un titre peut finir comme une marque : `Hotel.Iris`. La marque `.IRIS`
  d'IRIS est donc sensible à la casse.

## Ce que la conversion rend faux

| Traitement | Marque devenue fausse |
|---|---|
| Rabattre en 1080p | `2160p`, `4K`, `UHD` |
| Réencoder | le codec de la source (`x264`, `x265`, `AV1`…) |
| Retirer le RPU | `DV`, `DoVi` (→ `HDR10`) |
| Convertir en SDR | toute marque HDR, `HDR10+`, la profondeur 10 bits |
| Transcoder l'audio | la famille (`TrueHD` → `E-AC3`), `7.1` → `5.1`, `Atmos` |

Exemple complet : `Film.2160p.DV.HDR10.x265.TrueHD.7.1-GROUP` ressort
`Film.1080p.HDR10.E-AC3.5.1-GROUP.hevc.IRIS`.

## Conventions d'IRIS

- Toute sortie finit par **`.IRIS`**, en capitales, précédée d'une
  caractéristique **en minuscules** : `.hevc`, `.h264`, `.av1`, `.dv`,
  `.hdr10`, `.mux`, `.join`. Préférence de l'utilisateur : les suffixes en
  minuscules, sauf la marque `IRIS`.
- Une caractéristique que le nom annonce déjà n'est pas répétée.
- Collision : `Film.hevc.IRIS(2).mkv`. Rien n'est jamais écrasé.

## Voir aussi

[[codecs-video]] · [[hdr-dolby-vision]] · [[audio]]
