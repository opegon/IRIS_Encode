# libplacebo : chemin du shader, sonde Vulkan (2026-11-04)

ffmpeg BtbN n8.1.3-20260925, RTX A4500 (PC Shadow), IE-168.
Commande : `ffmpeg -init_hw_device vulkan -f lavfi -i color=c=gray:s=128x96:d=0.1
-vf libplacebo=w=160:h=120:custom_shader_path=<valeur> -f null -`
(arguments passés en liste, sans shell).

| Valeur de `custom_shader_path` | Résultat |
|---|---|
| `'C\:/…/sh dir/ArtCNN_C4F16.glsl'` | 0, 3,55 s |
| `C\:/…` (sans apostrophes) | « No option name near '/Users/…' » |
| `'C:/…'` | « No option name near '/Users/…' » |
| Chemin `…/d'Oli, [x];y/…`, échappé deux fois : `C\:/…/d\\'Oli\, \[x\]\;y/…` | 0 |

Échappement retenu : `\` → `/`, puis `\ ' :` précédés d'une barre (options),
puis `\ ' [ ] , ;` précédés d'une barre (graphe).

Sonde avec shader ArtCNN C4F16 : 2,21 s au premier appel. Shader absent :
« Cannot read file '…absent.glsl': No such file or directory ».

`ffmpeg -h filter=setparams` : `color_trc` accepte bt709, bt470m, bt470bg,
smpte170m, smpte240m, linear, iec61966-2-4, bt1361e, iec61966-2-1,
bt2020-10, bt2020-12, smpte2084, smpte428… ; `colorspace` : bt709, fcc,
bt470bg, smpte170m, smpte240m, bt2020nc, bt2020c, smpte2085…

Bout en bout (Cactus Jack 720×400, 10 s, `hevc_nvenc`) : une passe vers
1920×1066 en 5,8 s, deux passes en 13,6 s ; sortie SAR 1:1, bt709/bt709/bt709.
