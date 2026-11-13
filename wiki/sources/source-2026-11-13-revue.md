---
type: source
maj: 2026-11-13
ingere: 2026-11-13
---

# Source : revue de code et d'interface du 2026-11-13

**Où** : [[2026-11-13-revue-code]] ; rapport `revue_code_2026-11-13.md`
**Nature** : reproductions sur fichiers synthétiques, ffmpeg 6.1.1 sous Linux

Trois comportements d'outil relevés en reproduisant les constats de la
revue : le muxeur Matroska refuse un `mov_text` recopié ; un `.srt` en UTF-16
déclaré cp1252 passe sans erreur et sort illisible ; `idet` voit du peigne
sur une mire progressive. Tous *mesurés* en ffmpeg 6.1.1, **pas** dans le
8.1 que l'application installe.

## Pages alimentées

[[ffmpeg]] · [[questions-ouvertes]]
