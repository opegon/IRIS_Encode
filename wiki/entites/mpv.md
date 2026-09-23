---
type: entite
categorie: outil
maj: 2026-09-24
sources:
  - "[[source-spec]]"
  - "[[source-guide]]"
---

# mpv

Lecteur pour visualiser un fichier ou contrôler un recalage. Outil
**optionnel**. Publié en `.7z` (sourceforge), extrait par le `tar` de
Windows 10/11. Licence GPL-2.0+.

- `audio-delay` et `sub-delay` sont distincts : un audio et un sous-titre se
  calibrent ensemble, deux pistes audio demandent deux passes
  ([[synchronisation]]).
- Normalise en silence des horodatages que les décodeurs de téléviseur
  refusent : **un fichier qui passe dans mpv n'est pas prouvé lisible sur le
  [[lg-oled-g3]]** ([[pieges-et-lecons]]).
- Windows verrouille un fichier ouvert dans mpv : le supprimer échoue tant que
  le lecteur est ouvert.
