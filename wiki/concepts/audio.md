---
type: concept
maj: 2026-10-07
sources:
  - "[[2026-10-07-piste-vide-ffmpeg-81]]"
  - "[[source-2026-10-01-entrelacement]]"
  - "[[source-spec]]"
  - "[[source-changelog]]"
  - "[[source-guide]]"
  - "[[source-readme]]"
---

# Audio

## Ce que la chaîne accepte

| Format | Téléviseur LG G3 | Barre de son eARC | Remarque |
|---|---|---|---|
| **E-AC3** (DD+), Atmos compris | ✓ natif | ✓ | **cible par défaut** |
| AC3 | ✓ | ✓ | repli universel, plafonné à 640 kbps |
| AAC | ✓ | ✓ | stéréo |
| TrueHD, DTS-HD MA | ✗ | ✓ seulement si la TV ne mixe pas | provoquent un transcodage dans Jellyfin |
| DTS | gel au saut (modèles 2023) | ✓ | *observé (README)* |
| Opus (WebM, MKV) | — | — | transcodé en AAC ou AC3 |

*Niveau : observé (README), sauf mention.*

## Les familles sans perte

TrueHD, MLP, DTS-HD MA. **ffprobe nomme `dts` toutes les variantes DTS** et
met la famille dans `profile` : « DTS », « DTS-ES », « DTS-HD HR »,
« DTS-HD MA », « DTS-HD MA + DTS:X ». Sans lire `profile`, un DTS-HD MA passe
pour un DTS ordinaire. *(mesuré)*

## Transcoder au débit de la source

Le forfait par canaux (448 kbps en AC3 5.1) convient à une source déjà
compressée. Sur un TrueHD à 3,5 Mbps, il jette bien plus que nécessaire. D'où
`audio_hd_codec` : transcoder TrueHD et DTS **au débit présent dans la piste**.

| Encodeur | Plafond réel | Au-delà |
|---|---|---|
| `ac3` | **640 000 bps** | ramené **en silence** par l'encodeur |
| `eac3` | **6 144 000 bps** | commande **refusée** par ffmpeg |

*(mesuré)* Un TrueHD à 3 501 kbps ressort en E-AC3 à 3 501 kbps.

### Trouver le débit d'une piste

Un flux TrueHD ou DTS-HD MA **n'annonce jamais** de `bit_rate`. Ordre de
lecture :

1. `bit_rate` du flux ;
2. tag Matroska `BPS`, posé par mkvmerge, exact ;
3. `NUMBER_OF_BYTES ÷ DURATION` (tags de statistiques mkvmerge).

Sans ces tags, la piste retombe sur le forfait plutôt que sur une valeur inventée.

## Canaux

- **Les encodeurs `ac3` et `eac3` s'arrêtent au 5.1.** ffmpeg replie une source
  7.1 de lui-même, avec une sortie identique à l'octet près avec ou sans `-ac`.
  *(mesuré)* IRIS pose quand même `-ac 6`, pour que la commande affichée dise
  ce qui sort.
- Mono : AAC 64k. Stéréo : AAC. 5.1 : AC3. 7.1 : AC3, replié en 5.1.

## Atmos

Les objets Atmos **ne survivent pas** à une conversion vers AC3 ou E-AC3. La
mention `Atmos` disparaît du titre de piste et du nom de fichier.

## Titres de pistes

Un titre survit au transcodage et annonce alors un codec absent du fichier.
« ENG VO : TrueHD 5.1 » devient « ENG VO : E-AC3 5.1 ». Un titre muet sur le
format (« English ») n'a jamais menti : il reste tel quel. Une piste copiée
n'est jamais retitrée.

## Langues

Voir [[sous-titres#Langues|Sous-titres]] : l'audio a le même piège
`fra`/`fre`. La piste d'index 0 (langue originale) est toujours conservée.

## Pièges ffmpeg côté audio

- **`-ar:1` n'est pas la deuxième piste audio.** Un spécificateur nu désigne
  le n-ième flux de sortie **tous types confondus**. Si la vidéo est mappée en
  premier, `-ar:0` tombe sur la vidéo (ignoré) et `-ar:1` sur la première
  piste audio. Écrire `-ar:a:1`. *(mesuré, IE-48)*
- **Une piste sans perte transcodée pouvait disparaître.** Quand un même appel
  ffmpeg décode une piste sans perte **et** mappe un sous-titre dont la
  première réplique arrive tard, la piste transcodée s'arrête après deux
  trames, sans erreur ni code de retour non nul. *(mesuré, reproductible)*

  | Disposition | Paquets audio sur 60 s |
  |---|---|
  | une seule sortie | 2 |
  | deux sorties, audio seule dans la sienne | 2 |
  | sous-titre présent mais non mappé | 1 875 |
  | **appel ffmpeg distinct** | 1 875 |

  Seul un processus séparé sauve la piste : IRIS fait alors une passe audio
  préalable, puis **recopie** la piste. Transcoder un AC3 du même fichier sort
  indemne. Facteurs écartés par mesure : codec de sortie, durée, encodage
  matériel, drapeaux, `max_muxing_queue_size`, `max_interleave_delta`,
  `avoid_negative_ts`, `copyts`, `muxdelay`, ordre des `-map`.

  **Plus reproduit en ffmpeg 8.1.2 et 8.1.3** *(mesuré, 2026-10-07)* : ni sur
  *Watchmen* (piste forcée à 380 s, très probablement le fichier d'origine),
  ni sur de vrais TrueHD et DTS-HD MA, ni sur MLP, FLAC, PCM synthétiques,
  même avec la commande complète d'IRIS sans passe. Version de ffmpeg d'août
  non notée : *supposé* corrigé entre-temps. La passe reste, par choix
  ([[2026-10-07-piste-vide-ffmpeg-81]]).
- **Une audio venue d'une autre entrée que la vidéo sortait mal entrelacée.**
  Avec la vidéo encodée depuis l'entrée 0, l'audio recopiée depuis une entrée 1
  (passe préalable ou greffe) et des sous-titres clairsemés mappés depuis
  l'entrée 0, le muxeur écrit des centaines de secondes de vidéo seule, puis
  l'audio en bloc. ffmpeg et mpv relisent le fichier sans erreur. Un lecteur de
  salon s'arrête quand l'audio manque (*observé* : arrêt à 32 s, son perdu
  après un saut). *(mesuré, ffmpeg 8.1, [[2026-10-01-entrelacement-audio]])*

  | Disposition | Retard max de l'audio dans le fichier |
  |---|---|
  | sous-titres lus avec la vidéo (film entier) | ~1 150 s |
  | idem, extrait de 300 s | 162 s |
  | sans sous-titres | 0,2 s |
  | `-max_interleave_delta 0` | 0,2 s, mais mémoire ∝ silence de la piste la plus creuse |
  | **sous-titres par une entrée dédiée** | 0,2 s |

  IRIS rouvre la source pour les sous-titres dans ce cas (v0.8.9.41).
  *Supposé* : c'est l'ordonnanceur de ffmpeg 7+ qui bride l'entrée audio, et
  le défaut des pistes sans perte vides ci-dessus pourrait avoir la même
  cause. Non vérifié.
- **L'AAC est forcé à 48 kHz** (`-ar:a:N 48000`).

## Voir aussi

[[ffmpeg]] · [[ffprobe]] · [[mkvmerge]] · [[lg-oled-g3]] · [[jellyfin]] · [[conteneurs]] · [[noms-de-release]]
