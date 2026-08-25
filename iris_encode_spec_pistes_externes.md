# IRIS Encode — Spec : pistes externes et recalage

> **Statut :** à valider avant implémentation
> **Base :** `main` @ `dd2a376` (v0.7.1)
> **Date :** 25 août 2026
> **Version artifact :** https://claude.ai/code/artifact/789094e4-3bc2-4de2-bcb9-da832d74973d

Greffer une piste audio ou un sous-titre venu d'un autre fichier dans le fichier
courant, sans réencoder — avec mesure automatique du décalage, ajustement manuel
indépendant par piste, et mux final par `mkvmerge`.

---

## 1. Décisions actées

| Sujet | Décision | Conséquence |
|---|---|---|
| **Portée** | Un seul fichier à la fois | Pas de batch, pas de sidecar de persistance. L'état vit dans le `FileDecision` en mémoire, de l'écran de recalage jusqu'au mux. |
| **Exécution** | Opération immédiate depuis l'écran des pistes | Chemin d'exécution distinct de la file d'encodage, barre de progression propre. La queue n'est pas touchée. |
| **Multiplicité** | N pistes externes par fichier, audio et sous-titres mélangés | Chaque piste porte son propre décalage, réglé indépendamment des autres. |
| **Conteneur** | Sortie MKV obligatoire | Le MP4 ne porte ni ASS ni la plupart des pistes audio HD. `output_container` force `.mkv` dès qu'une piste externe est présente. |
| **Installation** | Archive ZIP portable officielle | `_install_from_zip()` fonctionne **sans modification**. Aucune dépendance d'extraction nouvelle. |
| **Hors périmètre** | Montages divergents (version longue, censure régionale) | Un décalage unique ne peut pas les recaler. Détecté et refusé, pas traité. |

---

## 2. Vérifications faites en amont

Tout ce qui suit a été **testé** le 25/08/2026, pas supposé.

### 2.1 L'archive portable

MKVToolNix publie bien un `.zip` pour Windows, en plus du `.7z` et de l'installeur.
Le problème d'extraction évoqué initialement **n'existe pas**.

```
https://mkvtoolnix.download/windows/releases/99.0/mkvtoolnix-64-bit-99.0.zip
sha256 = 9929554403e1ed920baa708a0f77967816f5f1c02de0b44ae320d6f8c367e876
taille = 84,6 Mo
```

Contenu — **aucune DLL**, les exécutables sont liés statiquement :

| Fichier | Taille |
|---|---|
| `mkvtoolnix/mkvmerge.exe` | 22 038 568 |
| `mkvtoolnix/mkvpropedit.exe` | 16 774 696 |
| `mkvtoolnix/mkvextract.exe` | 17 834 024 |
| `mkvtoolnix/mkvinfo.exe` | 16 012 328 |
| `mkvtoolnix/mkvtoolnix-gui.exe` | 53 669 416 |

Extraits seuls hors de leur dossier d'origine, `mkvmerge.exe` et `mkvpropedit.exe`
répondent correctement à `--version`. `_install_from_zip()` aplatit par nom de
fichier (`Path(member).name`) — c'est exactement ce qu'il faut ici.

> **Linux :** pas de tarball statique officiel. Installation par le gestionnaire de
> paquets de la distribution. `check_tools()` le trouvera dans le PATH.

### 2.2 Les options mkvmerge

Toutes vérifiées sur mkvmerge v99.0 :

```
-y, --sync <TID:d[,o[/p]]>   décalage en ms + facteur d'étirement linéaire
--language <TID:lang>
--track-name <TID:nom>
--default-track-flag <TID[:bool]>
--forced-display-flag <TID[:bool]>
--no-video / --no-subtitles / --audio-tracks
-J <fichier>                 identification JSON
--gui-mode                   protocole de progression
```

`--gui-mode` **n'apparaît pas dans `--help`** mais fonctionne. Il émet sur stdout :

```
#GUI#progress 99%
#GUI#progress 100%
#GUI#error <message>
```

C'est la sortie à parser dans le runner — plus fiable que le `Progress: x%` par défaut,
et les erreurs sont préfixées de la même façon.

### 2.3 Mux de bout en bout

Commande réellement exécutée, exit 0 :

```bash
mkvmerge --gui-mode -o sortie.mkv \
  cible.mkv \
  --sync 0:-2450,24000/25025 --language 0:fre --track-name 0:VF \
  --default-track-flag 0:1 donneur.mka \
  --sync 0:850 --language 0:fre --track-name 0:Francais subs.srt
```

Résultat vérifié par `mkvmerge -J` :

```
id=0  type=video      codec=AVC/H.264   lang=und  nom=          default=False
id=1  type=audio      codec=AC-3        lang=und  nom=          default=False
id=2  type=audio      codec=AC-3        lang=fre  nom=VF        default=True
id=3  type=subtitles  codec=SubRip/SRT  lang=fre  nom=Francais  default=True
```

Deux enseignements :

- Poser `--default-track-flag` sur la nouvelle piste **retire** automatiquement le
  drapeau de l'ancienne. Pas besoin de le gérer nous-mêmes.
- Le sous-titre est passé `default=True` **sans qu'on le demande** — voir piège 6.4.

---

## 3. Modèle de données

```python
# core/muxer.py

class TrackKind(Enum):
    AUDIO    = auto()
    SUBTITLE = auto()

class SyncOrigin(Enum):
    NONE     = auto()   # pas encore recalé
    MEASURED = auto()   # corrélation automatique
    MANUAL   = auto()   # ajusté à la main
    COPIED   = auto()   # repris d'une autre piste externe

@dataclass
class ExternalTrack:
    source_path:  Path                  # .mkv, .ac3, .srt, .ass…
    source_tid:   int                   # ID mkvmerge DANS ce fichier
    kind:         TrackKind
    codec:        str                   # affichage seulement
    language:     str                   # obligatoire — sinon « und »
    track_name:   str   = ""            # « VF », « Forcés »…
    delay_ms:     int   = 0
    stretch:      tuple[int, int] | None = None   # (24000, 25025)
    is_default:   bool  = False
    is_forced:    bool  = False
    sync_origin:  SyncOrigin = SyncOrigin.NONE
    copied_from:  int | None = None     # index dans external_tracks
```

```python
# core/decision.py — ajout à FileDecision

external_tracks: list[ExternalTrack] = field(default_factory=list)

@property
def output_container(self) -> str:
    if self.external_tracks:
        return ".mkv"          # ASS + audio HD → MKV imposé
    return ".mkv" if self.info.has_image_subs else ".mp4"
```

---

## 4. Le recalage, en trois temps

Chaque étape est facultative — on peut saisir un décalage à la main et muxer directement.

### Temps A — mesurer (corrélation multi-points)

Quatre sondes à 10 / 40 / 70 / 90 % du fichier. À chaque point, ~30 s d'audio cible et
donneur décodés en mono 8 kHz via ffmpeg, corrélation croisée par FFT. Python pur,
ffmpeg est déjà présent.

Le diagnostic se lit dans la colonne des décalages :

| Sonde | Cas constant | Conf. | Cas dérive PAL | Conf. |
|---|---|---|---|---|
| 00:12:00 | −2 450 ms | 0.94 | −2 450 ms | 0.92 |
| 00:48:00 | −2 451 ms | 0.91 | −1 021 ms | 0.90 |
| 01:24:00 | −2 449 ms | 0.93 | +410 ms | 0.88 |
| 01:48:00 | −2 452 ms | 0.89 | +1 180 ms | 0.87 |
| **Verdict** | **offset −2450 ms** | | **−2450 ms + 24000/25025** | |

Décalage stable → offset constant. Décalage qui dérive → facteur d'étirement, calculé
par régression linéaire sur les quatre points.

**Garde-fou :** la colonne *confiance* porte le pic de corrélation normalisé. Sous un
seuil (~0.6 en première approche, à caler empiriquement), ou si les sondes se
contredisent sans dériver linéairement, le résultat est **refusé** plutôt que proposé.
Un chiffre faux est pire que pas de chiffre.

### Temps B — ajuster (prévisualisation mpv)

mpv joue la cible avec la piste externe attachée. La TUI garde les commandes `+` / `−` ;
la valeur est déjà dans l'état au moment de valider, aucune recopie manuelle.

- v1 : lancement nu, l'utilisateur ajuste avec `Ctrl +` / `Ctrl −`, mpv affiche le délai
  en OSD, la valeur est retapée dans la TUI.
- v2 : IPC sur named pipe `\\.\pipe\iris_sync`, commandes JSON
  `{"command": ["set_property", "audio-delay", -2.45]}`. Confort, pas prérequis.

### Temps C — valider (extrait muxé)

60 s d'une scène dialoguée réellement passées par mkvmerge. Seule façon honnête de
vérifier un facteur d'étirement, que mpv ne prévisualise pas (`audio-delay` ne fait
qu'un décalage constant).

---

## 5. Parcours dans la TUI

Tout part de `TracksScreen`, qui liste déjà audio et sous-titres. Les pistes externes
s'ajoutent comme une quatrième section, visuellement distincte.

| Touche | Écran | Action |
|---|---|---|
| `F9` | `TracksScreen` | Ouvre le sélecteur de fichier donneur. F9 est libre : F1–F8 pris, F10 reste Quitter. |
| `↵` | `DonorPicker` | Liste les pistes du donneur via `mkvmerge -J`. Sélection multiple dans le même fichier. |
| `↵` | `SyncScreen` | Une piste externe = une ligne. Champs : décalage, étirement, langue, nom, défaut, forcé. |
| `+` / `−` | `SyncScreen` | ±100 ms sur la ligne courante. Avec Shift : ±1 s. Reprend l'idiome `action_val_up` / `val_down` existant. |
| `m` | `SyncScreen` | Mesure automatique de la ligne courante (temps A). |
| `p` | `SyncScreen` | Prévisualise dans mpv (temps B). |
| `c` | `SyncScreen` | Reprend le décalage d'une autre piste externe → `sync_origin = COPIED`. |
| `F2` | `SyncScreen` | Mux immédiat, barre de progression propre, retour aux pistes. |
| `⌫` / `Esc` | `SyncScreen` | Retour sans muxer. L'état reste dans le `FileDecision`. |

> **Pourquoi `c` compte.** Quand on ajoute une VF *et* ses sous-titres français, les
> sous-titres ont presque toujours été écrits sur le timing du donneur : leur bon
> décalage *est* celui de la piste audio. Une mesure indépendante contre la vidéo cible
> serait du travail perdu, et souvent moins fiable.

---

## 6. Pièges identifiés

Chacun produit un résultat faux **sans erreur visible**. C'est ce qui les rend coûteux.

### 6.1 Deux numérotations de pistes incompatibles — *critique*

`core/scanner.py:222` numérote par `enumerate` sur les flux audio seuls :
`AudioTrack.index` est un compteur **par type**, issu de ffprobe. mkvmerge utilise un ID
**global**, toutes catégories confondues.

Démontré sur le fichier de test : une piste audio unique après une vidéo est
`id=1` chez mkvmerge, `index=0` chez ffprobe.

Tout fichier donneur doit être identifié par `mkvmerge -J`, et les deux numérotations ne
doivent **jamais** se croiser dans le code.

### 6.2 Découper l'extrait de test en copie de flux — *critique*

Avec `-c copy`, chaque fichier se cale sur son propre keyframe le plus proche. Découper
cible et donneur séparément **modifie leur décalage relatif** et invalide le test — on
valide un décalage qui n'existe que dans l'extrait.

→ Réencoder l'audio de l'extrait (60 s, instantané) ou passer `-copyts`.

### 6.3 Oublier `--no-video --no-subtitles` sur le donneur

Sans ces options, mkvmerge embarque **tout** le fichier donneur, pas seulement la piste
voulue.

### 6.4 Le premier sous-titre devient `default` tout seul

Vérifié : mkvmerge pose `default=True` sur la première piste de sous-titres sans qu'on
le demande. Résultat : les sous-titres s'affichent d'office chez l'utilisateur.

→ Émettre explicitement `--default-track-flag TID:0` quand `is_default` est faux.

### 6.5 Une seule piste audio externe à la fois dans mpv

`audio-delay` et `sub-delay` sont des propriétés distinctes : une piste audio et un
sous-titre se calibrent dans la même session mpv. Mais deux pistes audio demandent deux
passes — l'écran doit le dire au lieu de laisser croire à un réglage simultané.

### 6.6 Métadonnées absentes des fichiers externes

Un `.srt` n'a aucune langue. Sans `--language`, la piste apparaît en « und » dans tous
les lecteurs. Ces champs sont saisis dans l'écran, jamais déduits.

### 6.7 mkvmerge réécrit le conteneur entier

Il n'y a pas d'ajout de piste in-place en MKV. Pour un fichier de 30 Go, c'est une copie
disque complète — une à trois minutes sur SSD. Énorme gain face à un réencodage, mais il
faut une barre de progression, pas un flash. Prévoir aussi l'espace disque : le temps du
mux, les deux fichiers coexistent.

### 6.8 Dolby Vision et remux — *non vérifié*

mkvmerge sait porter le RPU HEVC (bloc `dvcC` / `dvvC`), mais le comportement face au
pipeline `core/dovi.py` actuel n'est pas testé. À valider sur un fichier DV réel **avant**
d'autoriser le mux sur ces sources — sinon, bloquer explicitement.

---

## 7. Cas particulier : fichier déjà en réencodage

Si le fichier part de toute façon en encodage, mkvmerge ne sert à rien : ffmpeg absorbe
les pistes externes dans la même passe, à coût nul. `build_command()` doit lire
`external_tracks` et émettre les entrées supplémentaires.

```python
# core/encoder.py — build_command, après le -i source
for n, ext in enumerate(decision.external_tracks, start=1):
    cmd += ["-itsoffset", f"{ext.delay_ms / 1000:.3f}", "-i", str(ext.source_path)]
    # puis, dans la section mapping :
    #   -map n:a:0  /  -map n:s:0   selon ext.kind
    #   -metadata:s:a:N language=<ext.language>
```

**Limite à respecter :** `-itsoffset` ne fait qu'un décalage constant. Une piste
demandant un facteur d'étirement ne peut pas passer par ce chemin.

→ En v1 : si `stretch is not None`, forcer le passage par mkvmerge en seconde étape.

---

## 8. Découpage d'implémentation

Chaque phase est utilisable seule et livre quelque chose de testable. On peut s'arrêter
après la 3 et avoir déjà un outil qui sert.

### Phase 1 — Outillage

Ajouter `mkvmerge` aux `OPTIONAL_TOOLS`, sur le modèle exact de `dovi_tool`.
Aucune difficulté : le ZIP officiel et `_install_from_zip()` suffisent.

*Fichiers :* `core/preflight.py`, `data/ffmpeg_releases.toml`

```toml
[mkvtoolnix.windows]
url     = "https://mkvtoolnix.download/windows/releases/99.0/mkvtoolnix-64-bit-99.0.zip"
sha256  = "9929554403e1ed920baa708a0f77967816f5f1c02de0b44ae320d6f8c367e876"
version = "99.0"
```

> `_get_version()` essaie `-version` puis `--version`. mkvmerge rejette `-version` avec
> le code 2, la fonction bascule donc sur `--version` — le comportement actuel convient.

### Phase 2 — Modèle et génération de commande

`ExternalTrack`, le champ sur `FileDecision`, `output_container` forcé en MKV, et le
générateur d'arguments mkvmerge. Testable sans TUI : liste d'objets en entrée, liste
d'arguments en sortie. Point d'attaque naturel pour des tests unitaires.

*Fichiers :* `core/muxer.py`, `core/decision.py`, `tests/`

### Phase 3 — Écrans et mux avec décalage manuel

F9, le sélecteur de donneur, `SyncScreen` avec saisie `+`/`−`, et l'exécution mkvmerge
avec progression (`--gui-mode`). À ce stade l'outil est complet et utilisable, la valeur
de décalage étant juste saisie à la main.

Smoke test TUI obligatoire : `python tests/smoke_tui.py`

*Fichiers :* `tui/screens/tracks.py`, `tui/screens/donor_picker.py`, `tui/screens/sync.py`

### Phase 4 — Mesure automatique

Corrélation croisée multi-points, régression pour le facteur d'étirement, seuil de
confiance et refus. Le morceau le plus intéressant, et totalement indépendant de
mkvtoolnix : il se teste hors TUI, sur des paires de fichiers connues.

*Fichiers :* `core/sync.py`, `requirements.txt` (ajoute `numpy`)

### Phase 5 — Prévisualisation mpv

D'abord en lancement nu, l'IPC ensuite.

*Fichiers :* `core/preview.py`, `core/preflight.py`

### Phase 6 — Extrait de validation

Découpe de 60 s sur une scène dialoguée, mux réel, lecture. Nécessaire dès qu'un facteur
d'étirement est en jeu. Attention au piège 6.2.

*Fichiers :* `core/muxer.py`

---

## 9. Dépendances ajoutées

| Élément | Nature | Nécessaire à | Remarque |
|---|---|---|---|
| `mkvmerge` | binaire, optionnel | Phases 1–3 | GPL-2.0. ZIP officiel, statique, sans DLL. 22 Mo pour le seul `mkvmerge.exe`. |
| `numpy` | pip | Phase 4 | Corrélation FFT. Seule vraie dépendance Python nouvelle. |
| `mpv` | binaire, optionnel | Phase 5 | Binaire portable unique sous Windows. Absent = ajustement à l'aveugle, pas de blocage. |

**Licence.** MKVToolNix est en GPL-2.0. Redistribuer son binaire dans les ZIP de release
entraîne les obligations correspondantes. Ce n'est pas une situation nouvelle — le
ffmpeg embarqué avec libx265 est déjà GPL — mais autant le décider sciemment.
