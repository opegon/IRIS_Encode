# Carte des écrans — IRIS ENCODE

Relation entre les écrans de la TUI et les fichiers `.py` qui les décrivent.
Document **dérivé du code** (`tui/app.py`, `tui/screens/*.py`) : chaque flèche
correspond à un `push_screen` / `dismiss` réel, chaque touche à un `Binding`.

---

## 1. Graphe de navigation

```mermaid
flowchart TD
    MAIN["main.py<br/><i>CLI, preflight, deps</i>"]
    APP["tui/app.py<br/><b>IrisEncodeApp</b><br/><i>état global : cfg, profils, platform</i>"]

    MAIN -->|"main()"| APP

    subgraph ACCUEIL["Accueil"]
        BROWSER["browser.py<br/><b>BrowserScreen</b><br/><i>navigation fichiers</i>"]
    end

    APP -->|"on_mount()"| BROWSER

    subgraph PARCOURS["Parcours guidé (défaut)"]
        WIZ["wizard.py<br/><b>WizardScreen</b><br/><i>1 fichier, 5 étapes</i>"]
    end

    subgraph LIBRE["Parcours libre (W bascule)"]
        TRACKS["tracks.py<br/><b>TracksScreen</b><br/><i>pistes + décision vidéo</i>"]
        SYNC["sync.py<br/><b>SyncScreen</b><br/><i>recalage pistes externes</i>"]
    end

    subgraph EXEC["Exécution"]
        DRY["dryrun.py<br/><b>DryrunScreen</b><br/><i>prévisualisation</i>"]
        RUN["run.py<br/><b>RunScreen</b><br/><i>encodage ffmpeg live</i>"]
        MUX["mux_run.py<br/><b>MuxScreen</b><br/><i>mux mkvmerge</i>"]
        JOIN["join.py<br/><b>JoinScreen</b><br/><i>collage des parties</i>"]
    end

    subgraph REGLAGES["Réglages"]
        CONFIG["config.py<br/><b>ConfigScreen</b><br/><i>CRUD profils</i>"]
    end

    BROWSER -->|"↵ / T (wizard_mode)"| WIZ
    BROWSER -->|"↵ / T (mode manuel)"| TRACKS
    BROWSER -->|"F1"| DRY
    BROWSER -->|"F2"| RUN
    BROWSER -->|"F3 (récursif)"| DRY
    BROWSER -->|"F5"| CONFIG
    BROWSER -->|"F6"| JOIN

    TRACKS -->|"F9 pistes externes"| SYNC
    TRACKS -.->|"F1/F2 : dismiss(TracksSelection)<br/>le browser pousse l'écran"| BROWSER

    WIZ -->|"M"| MUX
    WIZ -->|"E"| RUN
    SYNC -->|"F3"| MUX
    SYNC -->|"F1"| DRY
    SYNC -->|"F2"| RUN
    MUX -->|"F1"| DRY
    MUX -->|"F2"| RUN
    DRY -->|"F2 / ↵"| RUN

    JOIN -.->|"BACKSPACE — n'enchaîne pas<br/>volontairement"| BROWSER

    RUN -.->|"BACKSPACE / Ctrl+Home"| BROWSER
    DRY -.->|"BACKSPACE"| BROWSER
    CONFIG -.->|"BACKSPACE"| BROWSER
```

### Modales (empilées sur l'écran courant, rendent une valeur)

```mermaid
flowchart LR
    subgraph BASE["Socle"]
        CONFIRM["confirm.py<br/><b>ConfirmModal</b><br/><i>ModalScreen bool</i>"]
    end

    QUIT["quit.py<br/><b>QuitConfirmScreen</b>"]
    DELC["delete_confirm.py<br/><b>DeleteConfirmModal</b>"]
    RECC["recursive_confirm.py<br/><b>RecursiveConfirmModal</b>"]

    CONFIRM -->|"hérite"| QUIT
    CONFIRM -->|"hérite"| DELC
    CONFIRM -->|"hérite"| RECC

    VP["value_picker.py<br/><b>ValuePickerScreen</b><br/><i>ModalScreen int ou None</i>"]
    PP["profile_picker.py<br/><b>ProfilePickerScreen</b><br/><i>ModalScreen str ou None</i>"]
    META["meta_popup.py<br/><b>MetaPopup</b>"]
    ANCR["ancrage.py<br/><b>AncrageModal</b>"]
    SEG["segments.py<br/><b>SegmentsScreen</b>"]
    DONOR["donor_picker.py<br/><b>DonorFileScreen</b> → <b>DonorTrackScreen</b><br/><i>pick_external_tracks()</i>"]
    AIDE["aide.py<br/><b>AideScreen</b><br/><i>guide dérivé des BINDINGS</i>"]

    APP2["app.py"] -->|"F10 / Ctrl+C"| QUIT
    APP2 -->|"H, depuis tout écran"| AIDE

    BR["browser.py"] -->|"Ctrl+D"| DELC
    BR -->|"F3"| RECC
    BR -->|"F4"| PP
    BR -->|"F7/F8"| META

    TR["tracks.py"] -->|"F4"| PP
    TR -->|"↵ / F6 / F7"| VP
    TR -->|"F9"| DONOR
    TR -->|"Ctrl+Home"| CONFIRM

    WZ["wizard.py"] -->|"F6 / F7"| VP
    WZ -->|"F9"| DONOR

    SY["sync.py"] -->|"↵ / C"| VP
    SY -->|"R"| ANCR
    SY -->|"S"| SEG
    SY -->|"F9"| DONOR
    SY -->|"Ctrl+Home"| CONFIRM

    DR["dryrun.py"] -->|"F6 / F7"| VP
    CF["config.py"] -->|"D"| CONFIRM
```

---

## 2. Écran ↔ fichier ↔ rôle

| Écran (classe) | Fichier | Type | Lignes | Rôle |
|---|---|---|---|---|
| `IrisEncodeApp` | `tui/app.py` | `App` | 175 | État global (cfg, profils, platform), câblage des binaires, `F10`/`H` |
| `BrowserScreen` | `tui/screens/browser.py` | `Screen` | 1073 | Accueil : navigation fichiers, sélection, scan, lancement de tout le reste |
| `WizardScreen` | `tui/screens/wizard.py` | `Screen` | 596 | Assistant autonome : un fichier, cinq étapes, `↵` pour avancer |
| `TracksScreen` | `tui/screens/tracks.py` | `Screen[TracksSelection\|None]` | 767 | Sélection pistes + édition de la décision vidéo (3 sections dans un `DataTable`) |
| `SyncScreen` | `tui/screens/sync.py` | `Screen[list[ExternalTrack]\|None]` | 1199 | Recalage manuel des pistes externes avant mux (mesure, ancrage, segments) |
| `DryrunScreen` | `tui/screens/dryrun.py` | `Screen` | 427 | Prévisualisation des décisions pour tous les fichiers sélectionnés |
| `RunScreen` | `tui/screens/run.py` | `Screen` | 1022 | File d'encodage ffmpeg avec progression live, pause, skip |
| `MuxScreen` | `tui/screens/mux_run.py` | `Screen[bool]` | 226 | Exécution du mux mkvmerge (chemin distinct de la file d'encodage) |
| `JoinScreen` | `tui/screens/join.py` | `Screen[bool]` | 343 | Collage bout à bout des parties d'un film ; s'arrête au fichier produit |
| `ConfigScreen` | `tui/screens/config.py` | `Screen[bool]` | 329 | Gestion des profils (`profiles.toml`), intègre `ProfileForm` |
| `AideScreen` | `tui/screens/aide.py` | `Screen` | 407 | Guide dérivé des `BINDINGS` de chaque écran — pas de liste écrite à la main |
| `ConfirmModal` | `tui/screens/confirm.py` | `ModalScreen[bool]` | 140 | Socle de toutes les confirmations |
| `QuitConfirmScreen` | `tui/screens/quit.py` | ← `ConfirmModal` | 23 | Sortie (focus initial sur Annuler) |
| `DeleteConfirmModal` | `tui/screens/delete_confirm.py` | ← `ConfirmModal` | 30 | Suppression d'un fichier |
| `RecursiveConfirmModal` | `tui/screens/recursive_confirm.py` | ← `ConfirmModal` | 30 | Scan/encodage récursif |
| `ValuePickerScreen` | `tui/screens/value_picker.py` | `ModalScreen[int\|None]` | 96 | Liste de valeurs générique (codec, débit, langue…) |
| `ProfilePickerScreen` | `tui/screens/profile_picker.py` | `ModalScreen[str\|None]` | 142 | Choix de profil en table (remplace un `ValuePicker` paddé à la main) |
| `MetaPopup` | `tui/screens/meta_popup.py` | `ModalScreen` | 159 | Fiche IMDB / AlloCiné |
| `AncrageModal` | `tui/screens/ancrage.py` | `ModalScreen[tuple[float,float]\|None]` | 154 | Point de repère quand la corrélation ne peut pas mesurer seule |
| `SegmentsScreen` | `tui/screens/segments.py` | `ModalScreen[None]` | 134 | Détail lecture seule des plages de décalage détectées |
| `DonorFileScreen` / `DonorTrackScreen` | `tui/screens/donor_picker.py` | `ModalScreen` ×2 | 264 | Fichier donneur puis ses pistes (tid mkvmerge, jamais index ffprobe) |

### Support transverse (pas des écrans)

| Fichier | Lignes | Rôle |
|---|---|---|
| `tui/common.py` | 446 | Formatage, styles DV, options des pickers, groupes de raccourcis |
| `tui/mixins.py` | 247 | `TableNavMixin` (Home/End/PgUp/PgDn), `ColumnResizeMixin` (Tab, `<`/`>`, persistance) |
| `tui/widgets/entete.py` | 66 | `Entete` — header + rappel de la touche d'aide, en un seul widget |
| `tui/widgets/footer.py` | 188 | `KeyFooter` — raccourcis en trois bandes (écran / globaux / F1-F10) |
| `tui/widgets/file_tree.py` | 123 | `FileNavigator` — accès système de fichiers pour le browser |
| `tui/widgets/profile_form.py` | 617 | Formulaire CRUD profil, utilisé par `ConfigScreen` |

---

## 3. Écrans → modules `core`

```mermaid
flowchart LR
    BROWSER["browser.py"]
    WIZARD["wizard.py"]
    TRACKS["tracks.py"]
    SYNC["sync.py"]
    DRYRUN["dryrun.py"]
    RUN["run.py"]
    MUXRUN["mux_run.py"]
    JOIN["join.py"]
    CONFIG["config.py"]
    META["meta_popup.py"]
    DONOR["donor_picker.py"]
    ANCRAGE["ancrage.py"]
    SEGMENTS["segments.py"]
    APP["app.py"]

    C_DEC["core/decision.py"]
    C_SCAN["core/scanner.py"]
    C_MUX["core/muxer.py"]
    C_SYNC["core/sync.py"]
    C_ENC["core/encoder.py"]
    C_CFG["core/config.py"]
    C_PROF["core/profiles.py"]
    C_JOIN["core/joiner.py"]
    C_META["core/meta.py"]
    C_PREV["core/preview.py"]
    C_PLAT["core/platform.py"]
    C_DOVI["core/dovi.py"]
    C_PRE["core/preflight.py"]

    BROWSER --> C_DEC & C_SCAN & C_CFG & C_PREV & C_JOIN
    WIZARD --> C_DEC & C_MUX & C_SYNC
    TRACKS --> C_DEC & C_MUX & C_CFG & C_DOVI
    SYNC --> C_DEC & C_MUX & C_SYNC & C_PREV
    DRYRUN --> C_DEC & C_CFG
    RUN --> C_DEC & C_ENC & C_MUX & C_PLAT
    MUXRUN --> C_DEC & C_MUX
    JOIN --> C_JOIN & C_MUX & C_SCAN & C_CFG
    CONFIG --> C_PROF
    META --> C_META
    DONOR --> C_MUX
    ANCRAGE --> C_SYNC
    SEGMENTS --> C_SYNC
    APP --> C_CFG & C_PROF & C_PLAT & C_DOVI & C_PRE & C_SCAN & C_ENC & C_SYNC & C_MUX & C_DEC & C_PREV
```

---

## 4. Lectures utiles du graphe

- **`BrowserScreen` est le seul hub.** Tous les retours (`BACKSPACE`, `Ctrl+Home`)
  y reviennent, et c'est lui qui pousse `DryrunScreen`/`RunScreen` même quand la
  demande vient de `TracksScreen` — celui-ci se contente de `dismiss()` une
  `TracksSelection` portant un `launch_mode`. L'écran des pistes n'a donc pas
  besoin de connaître les écrans d'exécution.
- **Deux parcours concurrents vers le même point.** `WizardScreen` (défaut) et
  la chaîne `TracksScreen → SyncScreen` (mode manuel, bascule `W`) aboutissent
  tous deux à `MuxScreen` ou `RunScreen`. Le wizard est **autonome**, pas un
  enchaînement des écrans existants.
- **`ConfirmModal` est le seul socle de confirmation**, décliné trois fois par
  héritage. Toute nouvelle confirmation devrait en hériter plutôt que
  reconstruire une modale.
- **`ValuePickerScreen` est le point d'entrée d'édition partagé** de `tracks`,
  `sync`, `dryrun` et `wizard` — modifier ses options touche quatre écrans.
- **`AideScreen` est dérivé, pas rédigé** : il importe les `BINDINGS` de neuf
  écrans et échoue en test (`tests/test_aide.py`) si une touche est ajoutée sans
  explication. C'est la seule dépendance « inverse » du graphe : l'aide dépend
  de tous les écrans, aucun écran ne dépend d'elle.
- **`JoinScreen` s'arrête volontairement** au fichier produit là où `MuxScreen`
  enchaîne sur dry-run/encodage : le fichier recousu redevient une entrée
  ordinaire du browser.
