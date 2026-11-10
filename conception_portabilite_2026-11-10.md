# IRIS ENCODE sur Linux puis macOS — note de conception

*Rédigée le 2026-11-10, sur la base de v0.9.2.6. Note datée : elle n'est pas
tenue à jour, la spec (§ 17) le sera au fil des livraisons.*

Deux plans, dans cet ordre : **Linux d'abord** (IE-183), **macOS ensuite**
(IE-184). macOS réutilise tout ce que Linux aura rendu POSIX : lanceur `sh`,
signaux, chemins montés, outils hors `.exe`. Faire macOS d'abord obligerait à
tout faire deux fois.

---

## 0. État des lieux (relevé dans le code)

### Ce qui est déjà portable

| Domaine | Où | État |
|---|---|---|
| Chemins | partout | `pathlib`, pas de registre ni `%APPDATA%` (spec § 17.1) |
| Pause / reprise d'encodage | `core/encoder.py:44-76` | `SIGSTOP` / `SIGCONT` hors Windows |
| Octets écrits par ffmpeg | `core/encoder.py:79-112` | `/proc/<pid>/io` sous Linux ; `None` sous macOS |
| Langue du système | `core/i18n.py:91-113` | `LC_ALL` / `LC_MESSAGES` / `LANG` hors Windows |
| Ouvrir un fichier | `tui/screens/sar.py:60-63` | `xdg-open` / `open` |
| Détection d'OS | `core/platform.py:183-191` | Windows / macOS / Linux distingués |
| Nom des exécutables | `core/preflight.py:58-63`, `core/ocr.py`, `core/dovi.py` | `.exe` seulement sous Windows |
| dovi_tool Linux | `core/preflight.py:366`, `data/ffmpeg_releases.toml` | URL `x86_64-unknown-linux-musl`, archive `.tar.gz` gérée (CHANGELOG) |
| Extensions | `core/scanner.py` & co | `.suffix.lower()` presque partout |

### Ce qui est propre à Windows

| Domaine | Où | Nature |
|---|---|---|
| Lancement | `launch.bat`, `bootstrap.ps1`, `launcher/` (`IRIS_Encode.exe`) | cmd + PowerShell + C# |
| Mise à jour | `updater.py:57` | `REQUIS` exige `launch.bat` ; l'extraction ZIP perd le bit exécutable |
| Téléchargement des outils | `core/preflight.py:419-470, 710-770` | mpv, mkvmerge, seconv, yt-dlp, Deno : Windows seulement |
| Suivi des versions | `core/updates.py:130-215` | motifs `win64`, `windows-msvc`, `yt-dlp.exe`, `/windows/releases/` |
| ffmpeg | `data/ffmpeg_releases.toml` | gyan.dev (Windows) ; Linux pointe johnvansickle (7.1.1, ni NVENC ni VAAPI ni libplacebo) |
| Encodage matériel | `core/platform.py:265-310` | Linux = processeur seul, même avec une NVIDIA ; QSV/AMF gardés par `OS.WINDOWS` |
| Veille / arrêt | `core/veille.py` | `kernel32`, `powrprof`, `shutdown.exe` ; `disponible()` faux ailleurs |
| Emplacements réseau | `core/emplacements.py:192-475` | UNC `\\serveur\partage`, `mpr.dll`, Credential Manager |
| Volumes | `tui/widgets/file_tree.py:21-37` | lettres A–Z ; ailleurs `[Path("/")]` seulement |
| Nom d'un Blu-ray | `core/bluray.py:190` | `GetVolumeInformationW` |
| Tests | `tests/*` | ~15 fichiers visent `bin/ffmpeg.exe` : sautés en silence ailleurs |
| Fins de ligne | `.gitattributes` | CRLF imposé aux `.bat/.ps1`, rien pour `.sh` |

### Sources des outils (vérifiées le 2026-11-10 sur les releases)

| Outil | Linux x64 | macOS |
|---|---|---|
| ffmpeg | **BtbN** `ffmpeg-n9.0-latest-linux64-gpl-9.0.tar.xz` (+ arm64) | **aucun BtbN** — Homebrew, evermeet.cx (Intel), osxexperts (arm64) |
| dovi_tool | `x86_64-unknown-linux-musl.tar.gz` | `universal-macOS.zip` |
| seconv | `SeConv-Linux-x64.tar.gz` | `SeConv-macOS-ARM64.zip`, `-x64.zip` |
| yt-dlp | `yt-dlp_linux` | `yt-dlp_macos` |
| Deno | `x86_64-unknown-linux-gnu.zip` | `aarch64-apple-darwin.zip`, `x86_64-…` |
| mkvmerge | AppImage officielle, ou paquet | DMG seulement → Homebrew |
| mpv | paquet de la distribution | Homebrew |

---

## Plan A — Linux (IE-183)

**Hypothèses** (à confirmer, § A.8) : cible x86_64 ; Debian 13 et Ubuntu 24.04 ;
terminal local ou SSH ; même ZIP de release pour tous les systèmes.

### A.1 Banc d'essai — *avant tout code*

1. VM Proxmox Debian 13 (et Ubuntu 24.04 si possible), Python 3.11+ ;
   idéalement une carte NVIDIA en passthrough pour NVENC.
2. `pytest` complet sur Linux : **inventaire des échecs** = la vraie liste de travail.
3. Helper commun dans `tests/conftest.py` pour le chemin de `bin/ffmpeg[.exe]` :
   les tests aujourd'hui sautés hors Windows doivent s'exécuter.
4. Télécharger le BtbN linux64-gpl et relever ses filtres et encodeurs :
   `libplacebo`, `libdvdnav`, `nvenc`, `vaapi`, `vulkan` présents ?

→ *vérif* : liste des échecs datée dans `wiki/raw/`, et les tests marqués Windows à tort sont corrigés.

### A.2 Lancement et mise à jour

- `launch.sh` (POSIX `sh`, pas de bashismes, déjà prêt pour macOS) : même
  ordre que `launch.bat` — `.venv` local, puis `python3` ≥ 3.11 validé par
  `dependances.py`, puis `bootstrap.sh`.
- `bootstrap.sh` : uv via son script d'installation dans le dossier de
  l'application (pas de `~/.local`), CPython, `.venv`. Même contrat que `bootstrap.ps1`.
- Code de sortie 10 de `updater.py` → relance, comme sous Windows.
- `updater.py` : `REQUIS` selon le système (`launch.sh` sous Linux) ; rétablir
  `chmod +x` sur `*.sh` après extraction (le ZIP ne restaure pas les modes).
- `.gitattributes` : `*.sh text eol=lf`.
- `IRIS_Encode.exe` / `launcher/` : Windows seulement, rien à porter.

→ *vérif* : sur une VM vierge, `sh launch.sh` aboutit à l'accueil ; mise à jour N → N+1 simulée.

### A.3 Outils externes (`core/preflight.py`, `core/updates.py`, `data/ffmpeg_releases.toml`)

- **ffmpeg principal = BtbN linux64-gpl** (remplace johnvansickle). S'il a
  `libplacebo` et `libdvdnav`, les outils DVD et Dolby Vision (`bin/dvd`,
  `bin/dv`) deviennent inutiles : le mécanisme `couverts` les marque déjà.
- dovi_tool : existant. seconv, yt-dlp, Deno : ajouter les sections `.linux`
  et retirer les gardes `_is_windows()` correspondantes.
- mkvmerge : AppImage officielle (exécutable unique) **ou** paquet — à trancher.
  mpv : paquet de la distribution (message actuel conservé).
- `core/updates.py` : le motif de chaque asset dépend du système
  (`win64` ↔ `linux64`, `windows-msvc` ↔ `unknown-linux-*`, `yt-dlp.exe` ↔ `yt-dlp_linux`).
- Bit exécutable posé à l'installation (`_poser_tous`).
- Un ffmpeg du PATH (paquet Debian) reste accepté : il prime déjà sur `bin/`.

→ *vérif* : `tests/test_outils_installation.py` étendu par système ; installation réelle de chaque outil sur la VM.

### A.4 Encodage matériel (`core/platform.py`, `core/encoder.py`)

- **A.4a NVIDIA** : la branche Linux reprend celle de Windows (`nvidia-smi`
  → `hevc_nvenc`, `-hwaccel cuda`). Chaîne tout-puce `scale_cuda` à remesurer.
- **A.4b Intel / AMD → VAAPI** (`hevc_vaapi`, `/dev/dri/renderD128`), nouvel
  encodeur **expérimental**, sondé comme `avec_amf` / `avec_qsv`. À mesurer :
  tenue du débit, 10 bits (`p010`), conservation des métadonnées HDR10.
  QSV sous Linux passe aussi par VAAPI/oneVPL : ne pas le dupliquer.
- AMF sous Linux : écarté.
- Super-résolution et DV profil 5 : Vulkan (pilote Mesa ou NVIDIA) ; l'essai
  existant (`core/super_resolution.py:117`) détecte déjà l'absence.

→ *vérif* : encodage SDR et HDR10 par encodeur, débit et métadonnées relevés dans le wiki (modèle des essais QSV du 2026-10-28).

### A.5 Intégrations système

| Sujet | Proposition Linux |
|---|---|
| Volumes (`file_tree.list_volumes`) | `/`, `$HOME`, `/media/$USER/*`, `/run/media/$USER/*`, `/mnt/*` |
| Emplacements réseau | **chemins déjà montés seulement** (fstab, gvfs, autofs) : libellé et test d'accès gardés ; connexion et coffre d'identifiants masqués. Monter du CIFS demande root. |
| Nom d'un Blu-ray | `findmnt` + `lsblk -no LABEL`, à défaut le nom du dossier |
| Veille | `systemd-inhibit --what=sleep` tenu pendant l'encodage ; fin : `systemctl suspend / hibernate / poweroff` (polkit, session locale active). Hors systemd : `disponible()` reste faux. |
| Casse des noms | Linux distingue `VIDEO_TS` / `video_ts` : recherche insensible à la casse dans `dvd.py` / `bluray.py` ; `core/annexes.py:43` compare un suffixe sans `.lower()` |
| Touche Quitter | **GNOME Terminal capture F10** (menu) par défaut : prévoir un second raccourci (`Ctrl+Q`) dans les footers |
| Console | `encoding="oem"` (`core/veille.py`) reste dans la branche Windows |

→ *vérif* : tests unitaires par fonction, avec les appels système remplacés comme dans `tests/test_veille.py` ; `smoke_tui.py` en/fr sur la VM.

### A.6 Documentation

README / GUIDE (en + fr) : installation Linux, paquets conseillés (`mpv`,
`mkvtoolnix`), limites (réseau monté, VAAPI expérimental). Spec § 17 réécrite
(tableau des outils par système). `install.txt` : une ligne Linux.

### A.7 Critères de fin

- `pytest` vert sur Linux **et** Windows ; `smoke_tui.py` vert sur Linux en en/fr.
- Encodages réels : SDR et HDR10 au processeur, NVENC si passthrough,
  un DVD, un Blu-ray, une piste DV.
- Mise à jour automatique éprouvée sur Linux.

### A.8 Questions à trancher

1. Banc d'essai : VM Proxmox ? Carte NVIDIA disponible en passthrough ?
2. Distributions visées (Debian 13, Ubuntu 24.04, autre) et arm64 ou non.
3. CI GitHub Actions (`ubuntu-latest`) pour `pytest` à chaque push ?
4. mkvmerge : AppImage téléchargée par IRIS, ou gestionnaire de paquets ?
5. Réseau : « montés seulement » convient-il ?
6. Numéro de version de la livraison Linux (MINOR ?) — décision de l'utilisateur (règle 5.1).

---

## Plan B — macOS (IE-184), après Linux

**Prérequis** : plan A livré (lanceur `sh`, intégrations POSIX). **Bloquant** :
un Mac pour essayer — de préférence Apple Silicon. Sans Mac, la cible se limite
à « démarre et passe les tests en CI », sans aucune garantie sur l'encodage.

### B.1 Banc d'essai

- Mac Apple Silicon (prêt, location type cloud Mac, ou runner GitHub `macos-14` pour les tests seulement).
- `pytest` + `smoke_tui.py`, inventaire des échecs, comme A.1.

### B.2 Lancement

- `launch.sh` de Linux, vérifié avec le `sh` et le bash 3.2 de macOS ; pas de
  `readlink -f`, `sed -i`, `grep -P`.
- `IRIS_Encode.command` : double-clic depuis le Finder.
- **Quarantaine Gatekeeper** : un ZIP téléchargé par navigateur marque tout
  son contenu → `xattr -dr com.apple.quarantine` documenté. Les fichiers que
  Python télécharge ne sont pas marqués.
- Le Python système (3.9 des outils Xcode) est trop ancien → bootstrap uv, déjà prévu.

### B.3 Outils

- **ffmpeg : Homebrew comme voie supportée** (`brew install ffmpeg`), trouvé
  dans le PATH ; le preflight affiche la commande au lieu de télécharger. Les
  builds tiers (evermeet.cx : Intel seulement ; osxexperts : arm64) ne sont pas
  vérifiables par empreinte publiée → écartés au départ. À vérifier : le
  ffmpeg de Homebrew a-t-il `libplacebo` (SR, DV P5) et `libdvdnav` ?
- dovi_tool (`universal-macOS.zip`), seconv (`SeConv-macOS-*`), yt-dlp
  (`yt-dlp_macos`), Deno (`*-apple-darwin`) : téléchargement automatique,
  choix de l'asset selon `platform.machine()` (`arm64` / `x86_64`).
- mkvmerge, mpv : Homebrew.

### B.4 Encodage VideoToolbox

Le profil existe (`core/platform.py`) mais **n'a jamais tourné** :
- Débit : `hevc_videotoolbox` vise un débit moyen ; `-q:v` (qualité
  constante) n'existe que sur Apple Silicon. Le contrôle de débit d'IRIS est à
  adapter, comme pour AMF.
- 10 bits : `-profile:v main10`, `p010le` ; métadonnées HDR10 à mesurer.
- `-allow_sw 0` pour refuser un repli logiciel silencieux.
- Lecture : `-hwaccel videotoolbox`.
- AV1 : aucun encodeur matériel → `libaom-av1` actuel très lent ; envisager
  `libsvtav1` (vaut aussi pour Linux et Windows sans carte récente).
- Vulkan (SR, DV P5) passe par MoltenVK : **risque élevé**, fonctionnalités
  annoncées indisponibles si l'essai échoue (le mécanisme existe).

### B.5 Intégrations

| Sujet | Proposition macOS |
|---|---|
| Volumes | `/`, `$HOME`, `/Volumes/*` |
| Réseau | partages montés par le Finder sous `/Volumes` (même modèle que Linux) |
| Nom d'un Blu-ray | `diskutil info -plist` |
| Veille | `caffeinate -i -w <pid>` tenu pendant l'encodage ; fin : `pmset sleepnow` ; arrêt via `osascript` (autorisation « Automatisation » demandée) ; hibernation masquée |
| Octets écrits | pas de `/proc` → `None` aujourd'hui ; `proc_pid_rusage` (libproc) en option |
| Langue | `LANG` peut manquer → repli `defaults read -g AppleLanguages` |
| Noms de fichiers | **Unicode NFD** (HFS+, SMB) : normaliser en NFC avant toute comparaison de noms (annexes, sous-titres voisins, sync) |
| Terminal | Terminal.app : 256 couleurs (pas de truecolor) → vérifier la lisibilité des styles DV ; F1–F12 demandent Fn (F10 Quitter) → le `Ctrl+Q` de A.5 sert ici aussi ; conseiller iTerm2 / Ghostty |

### B.6 Critères de fin

- `pytest` vert sur macOS (CI au minimum) ; `smoke_tui.py` en/fr sur un vrai Mac.
- Encodage VideoToolbox SDR et HDR10 mesuré ; repli processeur vérifié.
- Mise à jour automatique éprouvée.

### B.7 Questions à trancher

1. Un Mac est-il disponible (Apple Silicon / Intel) ? Sinon : support « best effort » affiché comme tel ?
2. Homebrew obligatoire pour ffmpeg, mkvmerge et mpv : acceptable ?
3. Intel Mac pris en charge, ou Apple Silicon seulement ?

---

## Ordre de livraison proposé

Chaque ligne est un incrément livrable (BUILD +1, entrée CHANGELOG).

| # | Livraison | Taille |
|---|---|---|
| A1 | Banc Linux, tests exécutables hors Windows | M |
| A2 | `launch.sh` / `bootstrap.sh` / updater | M |
| A3 | Outils Linux (BtbN, seconv, yt-dlp, Deno, mkvmerge) | M |
| A5 | Volumes, casse, F10/Ctrl+Q, Blu-ray | S |
| A5b | Veille systemd | S |
| A5c | Emplacements « montés seulement » | S |
| A4a | NVENC Linux | S (si passthrough) |
| A4b | VAAPI expérimental | L |
| A6 | Docs + spec § 17 → **release Linux** | S |
| B1-B3 | Banc Mac, lanceur, outils | M |
| B5 | Intégrations macOS | M |
| B4 | VideoToolbox | L |
| B6 | Docs → **release macOS** | S |

Linux sans VAAPI (A1-A3, A5, A6) est déjà une version utilisable, au
processeur ou avec NVENC : on peut la publier avant A4b.
