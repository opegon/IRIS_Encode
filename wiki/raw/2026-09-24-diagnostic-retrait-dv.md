# Diagnostic du retrait Dolby Vision — relevés bruts

Session du 2026-09-24. Relevés tels qu'obtenus, sans interprétation.
**Fichier immuable** : ne pas modifier, ajouter un nouveau relevé à côté.

Outils : ffmpeg/ffprobe 8.1.2 essentials (`bin/`), mkvmerge v102.0, dovi_tool 5717cab.

## Sortie MKV existante (produite le 2026-08-27, mkvmerge v101)

Source : `Kingdom.of.the.Planet.of.the.Apes.2024.MULTi.VFF.4K.2160p.HDR10Plus.DV.WEBRip.DDP.Atmos.7.1.x265.mkv`
Sortie : même nom `_[hdr10].mkv`

- ffprobe, source : hevc Main 10, level 150, `yuv420p10le`, bt2020nc / smpte2084 / bt2020,
  24/1, `has_b_frames=2`, `DOVI configuration record` profile 8, level 6, rpu 1, el 0, bl 1, compat 1.
- ffprobe, sortie : identique, sans `DOVI configuration record`.
- `codec_private_data` (hvcC, 130 octets) identique entre source et sortie.
- NAL sur les 20 premières secondes (comptage des codes de début `00 00 01`) :
  - source : `{0:242, 1:234, 8:2, 9:1, 20:1, 21:2, 32:6, 33:6, 34:6, 35:482, 39:497, 62:482}`
  - sortie : `{0:242, 1:234, 8:2, 9:1, 20:1, 21:2, 32:9, 33:9, 34:9, 35:482, 39:497}`
- 14 premiers paquets vidéo (pts,dts) identiques entre source et sortie :
  `0.000,N/A K | 0.208,N/A | 0.125,0.000 | 0.042,0.042 | 0.083,0.083 | 0.167,0.125 | 0.417,0.167 | …`

## Chemin MP4 d'alors (flux brut → ffmpeg), rejoué sur 60 s d'Avatar

Source : `Avatar.Fire.and.Ash.2025.MULTi.VF2.2160p.HDR.DV.WEB-DL.Dolby.Atmos.7.1.H265-Slay3R.mp4`
(`hev1`, `has_b_frames=4`, level 150, 24/1).

```
ffmpeg -y -r 24/1 -i a_nodv.hevc -i <source> -map 0:v:0 -map 1:a? -c copy
       -avoid_negative_ts make_zero -movflags +faststart -t 60 a_out.mp4
```

- ffmpeg : `Timestamps are unset in a packet for stream 0` puis
  `pts has no value`, répété 1 443 fois de plus (1 444 images).
- Paquets de la source : `0.000,-0.167 K | 0.083,-0.126 | 0.042,-0.085 | 0.167,-0.044 | 0.125,0.000 | …`
- Paquets de la sortie : `0.000,0.000 K | 0.034993,0.034993 | 0.076660,0.076660 | 0.118327,0.118327 | …`
  (PTS = DTS, pas de 0,0417 s).

## Filtre `dovi_rpu=strip=1`, 60 s d'Avatar

```
ffmpeg -i <source> -t 60 -map 0:v:0 -map 0:a -c copy -bsf:v dovi_rpu=strip=1 -movflags +faststart a_bsf.mp4
```

- Paquets identiques à la source (`0.000,-0.167 K | 0.083,-0.126 | …`), tag `hev1`, aucune side data DV.
- NAL 62 et 63 restants : 0 et 0.
- `ffmpeg -h bsf=dovi_rpu` : options `strip` (booléen), `compression` ; codecs pris en charge : hevc, av1.

## Nouveau chemin MP4 (v0.8.8.15), 90 s de Kingdom

Décision réelle, profil `cinema_4k_hdr_basic` : `STRIP_DV`, conteneur `.mp4`, `DV:P8.1`.

- Code retour 0. Avertissements : « Multiple -codec/-c… options specified » (sous-titres),
  « track 1: codec frame size is not set ».
- Paquets (pts,dts) — source : `0.000,N/A | 0.208,N/A | 0.125,0.000 | 0.042,0.042 | …` ;
  sortie : `0.000,-0.083 | 0.208,-0.042 | 0.125,0.000 | 0.042,0.042 | …` (PTS identiques).
- Images sur 90 s : 2 157 (source) et 2 157 (sortie). Tag sortie `hev1`, transfert smpte2084.
- NAL 62/63 : 0/0. SEI préfixe (type 39) : 2 212.
- `ffmpeg -i sortie -map 0:v:0 -f null -` : aucune erreur.

## Profils DV relevés dans `resources_files`

| Fichier | Profil | compat |
|---|---|---|
| Kingdom of the Planet of the Apes | 8 | 1 |
| Starship Troopers (4KLight) | 8 | 1 |
| Watchmen | 8 | 1 |
| Good Luck Have Fun Don't Die | 5 | 0 |
| Avatar Fire and Ash | DV (MP4, hev1) | — |

## Pistes de sous-titres relevées (mkvmerge -J)

Starship Troopers et Watchmen, identiques :
`SRT fre default+forced « FR Forced : SRT »`, `SRT fre « FR Full : SRT »`, `SRT eng « ENG Full : SRT »`,
`PGS fre forced « FR Forced : PGS »`, `PGS fre « FR Full : PGS »`, `PGS eng « ENG Full : PGS »`.
Watchmen porte en plus un TrueHD 5.1 anglais.

## Aide de dovi_tool

`dovi_tool remove --help` : « Removes the enhancement layer and RPU data from the video ».
