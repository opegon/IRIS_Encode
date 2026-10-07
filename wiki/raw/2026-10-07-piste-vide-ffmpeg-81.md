# 2026-10-07 — Piste sans perte vidée : plus reproduite en ffmpeg 8.1.x (IE-80)

Mesures de la session, pour décider si la passe audio préalable
(`encoder.audio_prepass_needed`) couvre toutes les familles sans perte.

Défaut visé, mesuré le 2026-08-28 (CHANGELOG v0.8.2.6, v0.8.2.7) : un même appel
ffmpeg qui décode une piste sans perte et mappe un sous-titre dont la première
réplique arrive tard écrit 2 paquets audio au lieu de 1 875 sur 60 s. Version de
ffmpeg de l'époque : non relevée.

Outils : ffmpeg 8.1.2 essentials de gyan.dev (`bin/`) et n8.1.3-20260925 de BtbN
(PATH). Toutes les mesures : encodage de 60 s, audio transcodée en E-AC3,
paquets audio comptés par `ffprobe -count_packets` (attendu 1 875, 1 876 pour
une source DTS).

| Essai | 8.1.2 | 8.1.3 |
|---|---|---|
| Sinusoïde 480 s encodée en TrueHD, MLP, FLAC, PCM 24 bits, AC3 ; vidéo de mire ; SRT dont la 1re réplique est à 400 s ; sous-titre mappé / non mappé | 1 875 partout | 1 875 partout |
| Flux réels recopiés sur 480 s : TrueHD 5.1 et AC3 5.1 (*Watchmen*), DTS-HD MA 2.0 (*Colossus*), 7.1 et 5.1 (*Premier Contact*) ; même SRT | 1 875 / 1 876 partout | idem |
| Deux pistes, une recopiée et une transcodée (AC3 + TrueHD, TrueHD + AC3, DTS-HD MA + DTS-HD MA) | transcodée complète | idem |
| *Watchmen* lui-même : TrueHD transcodé, piste « FR Forced » (1re réplique à **380,255 s**, les « 6 min 20 » du signalement) seule mappée | 1 875 | 1 875 |
| *Watchmen*, commande complète de `build_command` (NVENC, MP4, `mov_text`, AC3 recopié, TrueHD → E-AC3, trois sous-titres), passe préalable ôtée, `-t 60` | AC3 1 875, E-AC3 1 875 | idem |

Constat : le défaut ne se reproduit plus, ni sur flux synthétiques ni sur le
fichier qui le déclenchait (très probablement celui du signalement). Hypothèse
la plus probable : défaut d'une version antérieure de ffmpeg, corrigé depuis —
non vérifiable, la version d'août n'ayant pas été notée.

Décision de l'utilisateur, en séance :

> on garde la passe

Scripts de l'essai : scratchpad de session (`ie80/essai.py`, `essai_reel.py`,
`essai_mixte.py`, `commande_iris.py`), non versionnés.
