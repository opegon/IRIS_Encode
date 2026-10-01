# 2026-10-01 — Audio mal entrelacée : *L'Ombre d'un doute*

Fichiers, dans `resources_files/` :

- source `L.Ombre.D.Un.Doute.(Shadow.of.a.Doubt).1943.BD.Remux.1080p.MULTi.VFF.VC-1.DTS-HD.DTS.2.0-DiY.mkv`
  (VC-1, DTS 2.0 fre, DTS-HD MA 2.0 eng, 3 PGS, 3 SRT dont un forcé par défaut) ;
- sortie IRIS `….VC-1.AAC.2.0-DiY.hevc.IRIS.mkv` (HEVC Main, 2 AAC 2.0, mêmes
  sous-titres recopiés), muxée par Lavf62.12.103.

Citation de l'utilisateur :

> le fichier transcodé n'est pas conforme. la lecture s'arrête à 32 sec. et si on se déplace dans le fichier, la synchronisation est perdu, la lecture impossible et plus de son

## Relevés sur la sortie (ffprobe 8.1.3)

- Structure saine : SeekHead, Info, Tracks, Chapters, Tags, 3 179 clusters,
  Cues en fin. `mkvmerge -J` : aucune erreur.
- Horodatages continus sur chaque piste : vidéo 0,042 → 6 468,46 s, 155 088
  images ; audio −0,021 → 6 469,46 s, 303 258 paquets. Images-clés IDR_W_RADL
  toutes les 10,4 s.
- `ffmpeg -f null` sur 0–60 s et sur 1 200–1 220 s : aucune erreur.
  `mpv --vo=null --ao=null` sur 25–40 s et 1 500–1 510 s : aucun message.
- **Entrelacement, dans l'ordre du fichier** : dernier paquet audio à 31,91 s,
  puis 26 Mo de vidéo seule, reprise à 122,6 s. Autres trous d'audio dans le
  fichier : 126,8 → 564,8 s (163 Mo), 564,8 → 1 714,4 s (463 Mo),
  1 816,9 → 3 542,5 s (696 Mo), 4 302,1 s (863 Mo). Exemple : l'audio à
  4 302 s est écrite à côté de la vidéo à 6 455 s.
- Plus long silence par piste de sous-titres : 2 165 s (PGS forced), 2 168 s
  (SRT forced), 88 à 119 s pour les autres.

## Reproduction (ffmpeg 8.1.3, hevc_nvenc, RTX A4500)

Extrait de 300 s de la source (`-c copy`), pistes audio produites à part
comme le fait la passe préalable d'IRIS (`aac`, 192k, 48 kHz), puis :
`-i ex.mkv -i audio.mka … -map 0:v:0 -map 1:a:0 -map 1:a:1 -map 0:s? -c:a copy -c:s copy`.

| Variante | Retard max de l'audio sur la vidéo, ordre du fichier |
|---|---|
| comme IRIS v0.8.9.40 | 162,0 s |
| sans `-map 0:s?` | 0,23 s |
| `-max_interleave_delta 0` | 0,23 s |
| sous-titres depuis une 3ᵉ entrée (`-i ex.mkv` rouverte, `-map 2:s?`) | 0,23 s |

Mémoire de pointe sur l'extrait : 333 Mo avec le réglage par défaut (10 s),
400 Mo avec `-max_interleave_delta 0`.
