---
type: entite
categorie: outil
maj: 2026-10-06
sources:
  - "[[source-2026-10-06-sar-scale]]"
  - "[[source-spec]]"
  - "[[source-changelog]]"
  - "[[source-2026-09-24-diagnostic]]"
  - "[[source-2026-09-26-nvenc-pilote]]"
  - "[[source-2026-10-04-mov-text]]"
---

# ffmpeg

Moteur d'encodage, de remux, d'extraction et de décodage (pour la mesure de
décalage). Outil **essentiel**. Voir aussi [[ffprobe]] et [[sous-processus]].

## Versions

| Version | Où | Relevé |
|---|---|---|
| 8.1.2 essentials (gyan.dev) | `bin/` | 2026-09-24 |
| build git N-125365 (winget) | `PATH` du poste | 2026-09-24 |
| n8.1.3 BtbN gpl | `PATH` du poste (`C:\Program Files\ffmpeg\bin`) | 2026-09-26 |

`get_tool_path` prend le `PATH` **avant** `bin/`.

## NVENC et version du pilote

Chaque build embarque une version de l'API NVENC, qui fixe un pilote minimal.
Un pilote trop ancien fait refuser **tous** les encodeurs NVENC. *(mesuré,
pilote 597.16 = API 13.0, [[source-2026-09-26-nvenc-pilote]])*

| Build | API exigée | Sous le pilote 597 |
|---|---|---|
| git master N-126856 (2026-09-25) | 13.1 (pilote ≥ 610) | refusé |
| gyan.dev 8.1.2 essentials | 13.1 | refusé |
| BtbN n9.0 | 13.1 | refusé |
| BtbN n8.1.3 | ≤ 13.0 | accepté |

Le numéro de ffmpeg ne dit donc rien : deux builds 8.1 divergent. La cause
n'apparaît qu'en `-loglevel verbose` (« Driver does not support the required
nvenc API version ») ; sans, seulement « Function not implemented ». Test :
`ffmpeg -loglevel verbose -f lavfi -i testsrc2=d=1 -c:v hevc_nvenc -f null -`.

Build installé par le preflight : *essentials* (~30 Mo), gyan.dev ou BtbN,
SHA256 vérifié. Licence GPL (libx265 inclus). Un ffmpeg peut être construit
sans libx265 : `ffmpeg -encoders | findstr x265`.

## Filtres de flux (`-bsf:v`)

- `hevc_mp4toannexb` : de la forme conteneur (hvcC) au flux brut Annex-B,
  celui qu'attend [[dovi-tool]].
- `dovi_rpu=strip=1` (**7.1+**, HEVC et AV1) : retire le RPU Dolby Vision et
  l'enregistrement de configuration DV, **horodatages de la source
  conservés**. Présence : `ffmpeg -h bsf=dovi_rpu`. *(mesuré, voir
  [[hdr-dolby-vision#Retrait du RPU]])* Retrait de la couche d'amélioration
  d'un profil 7 : non vérifié ([[questions-ouvertes]]).

## Comportements à connaître

- **Muxer un flux brut en MP4 perd les horodatages** : PTS = DTS sur chaque
  image (« pts has no value »), même avec `-r`. Partir d'un fichier
  conteneurisé. *(mesuré, [[conteneurs#Horodatages]])*
- **`-itsoffset` négatif** : ffmpeg refuse des horodatages négatifs et décale
  **tout le fichier** (`start_time = 2.5 s` pour −2 500 ms). Traduire en `-ss`
  sur l'entrée du donneur. Un positif est sans risque. *(mesuré)*
- **Spécificateurs de flux** : `-c:a:1`, `-b:a:1`, `-ar:a:1` visent la
  deuxième piste audio ; `-ar:1` vise le deuxième flux **tous types
  confondus**. *(mesuré, [[audio]])*
- `-c copy` suivi de `-c:s mov_text` : avertissement « Multiple -codec
  options specified », sans conséquence. L'option la plus précise l'emporte.
- **Replie seul du 7.1 en 5.1** pour `ac3`/`eac3`, à l'octet près avec ou sans
  `-ac`. *(mesuré)*
- **Piste audio vidée** quand un même appel décode du sans perte et mappe un
  sous-titre tardif, avec un code retour 0. *(mesuré, [[audio]])*
- `atrim` découpe à l'échantillon près ; `-c copy` se cale sur la trame la plus
  proche. `concat` exige fréquence et disposition identiques.
- **`mov_text` après un silence de plus de 2³¹ µs** (35 min 47 s) : temps
  écrasés à l'écriture en MP4/MOV, en 8.1.2 comme en 8.1.3. Le MKV n'a pas
  le défaut. *(mesuré, [[sous-titres#Long silence en MP4]])*
- **`scale` avec `force_original_aspect_ratio` rattrape l'arrondi par un SAR** :
  3832×1600 → 1920×802 en 192079:192000, 1918×802 → 1920×802 en 959:960.
  Ajouter `setsar=1` pour des pixels carrés. *(mesuré, [[jellyfin]])*
- Chapitres d'un MP4 : piste `bin_data` (voir [[conteneurs#Chapitres]]).
- Écrit **`hev1`** par défaut pour du HEVC en MP4 ; `-tag:v hvc1` le change sans toucher au flux, et IRIS le passe depuis la v0.8.9.39 ([[conteneurs]]).
- Lit `stdin` pour son clavier interactif (`q` l'arrête) : voir [[sous-processus]].

## Encodeurs

Voir [[codecs-video#Encodeurs]] : NVENC, libx265, libx264, `av1_nvenc`
(RTX 40 et plus, sans option `-profile`).

## Diagnostic d'un échec

ffmpeg annonce la cause **avant** de constater l'échec : la dernière ligne
(« Error opening output files: Invalid argument ») est la seule qui n'apprend
rien. Chercher dans les ~40 lignes précédentes. Exemple réel : « Subtitle
encoding currently only possible from text to text or bitmap to bitmap » pour
un PGS forcé en `mov_text`. *(mesuré)*
