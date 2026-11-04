---
type: source
maj: 2026-11-05
ingere: 2026-11-05
---

# Source : Note de conception de la super-résolution

**Où** : `conception_upscaling_2026-11-03.md` (dans le dépôt)
**Nature** : note de conception datée, avec les essais et mesures des
2026-11-03 et 2026-11-04 (§ 10) et les décisions de l'utilisateur (D1 à D26)

Ce que la note apporte au wiki : le comportement de `libplacebo` et des
shaders mpv, les gains mesurés (VMAF, PSNR) selon le facteur, la vitesse sur
RTX A4500 et sur iGPU Intel, le jugement à l'œil de l'utilisateur. Ce que
fait le code est dans la spec (§ 8.1, § 12, § 14.6).

## Ce qui en a été tiré

| Section | Pages alimentées |
|---|---|
| § 10.2, § 10.3 pièges de `libplacebo` et des shaders | [[codecs-video#Agrandissement par super-résolution]] |
| § 10.4, § 10.13, § 10.14 mesures VMAF / PSNR | [[codecs-video#Agrandissement par super-résolution]] |
| § 10.5, § 10.15 vitesse | [[codecs-video#Agrandissement par super-résolution]] |
| D21 marque `upscaled` | [[noms-de-release]] |
| points non mesurés | [[questions-ouvertes]] |

## Voir aussi

[[source-2026-11-04-libplacebo-shader-chemin]] · [[ffmpeg]]
