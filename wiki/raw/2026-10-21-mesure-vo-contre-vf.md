# 2026-10-21 — Mesure d'une piste anglaise contre une VF (assistant, IE-142)

Contexte : l'utilisateur, en mode assistant (v0.9.0.5 installée), greffe sur une
VFF la piste anglaise d'une autre release du même film. Il s'attendait à un
refus (« absence de mesure, conseil de vérifier »), vu lors d'un essai
précédent dont le fichier n'a pas été retrouvé.

Cible : `The.Thirteenth.Floor.(1999).VFF.1080p..AC3.5.1.x264-Serpico.mkv`
— h264, AC-3 5.1 fre (VFF), AC-3 5.1 fre (VFQ), aucun sous-titre ; 6030,106 s.

Donneur : `The.Thirteenth.Floor.1999.1080p.DDP5.1.hevc-iris.mp4`
— hevc, E-AC-3 5.1 eng (a:0), mov_text eng ×2 et fre, AC-3 5.1 fre (a:1),
données ; 6029,847 s.

Mesure refaite hors de l'interface avec `core.sync.measure_audio` de la copie
installée (v0.9.0.5), ffmpeg `C:\Program Files\ffmpeg\bin\ffmpeg.exe` :

```
=== AUDIO donneur a:0
✓ +260 ms (confidence excellent)
confidence excellent (0.86 for 0.25 required) · thirds agree within 10 ms · 24264 lines · speech 58%
=== AUDIO donneur a:1
✓ +260 ms (confidence excellent)
confidence excellent (1.00 for 0.25 required) · thirds agree within 0 ms · 24264 lines · speech 58%
(848 s, les deux mesures en parallèle, fichiers sur le NAS)
```

L'instance de l'utilisateur a rendu la mesure avec succès elle aussi (déclaration
de l'utilisateur : « la mesure a été faite avec succès »).
