---
type: source
maj: 2026-10-04
ingere: 2026-10-04
---

# Source : sous-titre `mov_text` désynchronisé après un long silence

**Où** : [[2026-10-04-mov-text-silence]]
**Nature** : constat de l'utilisateur sur une sortie MP4, mesures ffmpeg faites ici

- **Défaut de ffmpeg** (8.1.2 et 8.1.3) : le muxeur MP4/MOV perd les temps
  d'une piste `mov_text` après un silence de plus de 2 147,48 s (2³¹ µs),
  avant la première réplique ou entre deux. Toutes les répliques suivantes se
  collent au début. Code retour nul, aucun message.
- Touche surtout les pistes **forcées** : *Film J* ouvre la sienne à
  53 min 51 s, et elle s'affichait dès les premières images.
- Le Matroska garde les temps. Une réplique invisible (espace insécable, 1 ms)
  toutes les 1 800 s de silence suffit.
- Contourné en v0.8.9.62 : `core/sous_titres.py`, un MKV porteur lu par les
  trois chemins qui écrivent du MP4.

Pages touchées : [[sous-titres]], [[ffmpeg]], [[pieges-et-lecons]].
