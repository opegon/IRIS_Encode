# 2026-10-04 — `mov_text` : un long silence efface les temps en MP4

Fichier : *Premier Contact* (`resources_files/`, MKV, 4 SRT + 4 PGS). Sortie
d'IRIS v0.8.9.60 en MP4, vidéo recopiée, 4 SRT convertis en `mov_text`.

Déclaration de l'utilisateur, telle quelle :

> il y a un souci avec le srt fr forcé qui est totalement désynchronisé
> puisqu'il affiche des choses dès les premières images

## Source contre sortie

Piste FR forcée de la source (`ffprobe -show_entries packet=pts_time,duration_time`) :

```
3231.562000,2.294000
3438.769000,1.544000
5334.580000,3.003000
```

La même dans la sortie MP4 (paquets de 2 octets = silences insérés par le muxeur) :

```
0.000000,0.000001,2
0.000001,2.294000,34
2.294001,0.000001,2
2.294002,1.544000,46
```

La piste FR complète (première réplique à 72 s, silences courts) est intacte.

## Mesures sur des SRT synthétiques (ffmpeg 8.1.2 gyan, `-c:s mov_text`)

| Répliques (s) | Résultat |
|---|---|
| 10, 20, 30 · 72, 100, 130 · 500, 600 · 2000, 2100 | temps justes |
| première à 2147 | temps justes |
| première à 2148, 3000, 3231 | temps écrasés |
| 10, puis 3300, 3360 | 10 juste ; tout ce qui suit le silence est écrasé |

Seuil : 2³¹ µs = 2 147,48 s. Même résultat avec ffmpeg 8.1.3 (BtbN), en MOV
et en MP4 fragmenté. En MKV (`-c:s srt`), temps justes. mkvmerge, relisant le
MP4 faux, rend les mêmes temps faux : l'écriture est en cause, pas la lecture.

## Contournement mesuré

Une réplique par tranche de 1 800 s de silence, une espace insécable pendant
1 ms : temps justes. Une espace simple est retirée par le décodeur SRT et ne
sert à rien. Sur le film entier (4 pistes passées par un MKV porteur puis
`mov_text`) : FR forcée à 3 231,562 s, 16 répliques sur 16 ; FR complète
980/980 ; ENG forcée 8/8 ; ENG complète 1 234/1 234.
