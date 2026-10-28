# Réglages GitHub à faire pour IRIS_Encode

Ces réglages se font sur github.com, ou avec la CLI `gh`. Ce sont des
réglages du dépôt, pas des fichiers. Compte 10 minutes en tout.

**Ordre conseillé** : 1 à 4 avant de fusionner la branche dans `main`, car le
README et les modèles d'issues pointent vers Discussions et vers le signalement
privé. Le reste quand tu veux.

> Toutes les commandes `gh` supposent `gh auth login` déjà fait. Elles tournent
> dans PowerShell comme dans un terminal Linux.

---

## 1. Description et sujets (*topics*)

### Description (350 caractères max., en anglais)

Proposition :

```text
Prepare a movie library for Jellyfin direct play: re-encode only what needs it, strip Dolby Vision without re-encoding, and see every decision before it runs. Terminal app for Windows; Linux planned for 2027.
```

Variante plus courte :

```text
Make every file play directly in Jellyfin — re-encode only what needs it, strip Dolby Vision without re-encoding.
```

### Sujets (20 max., minuscules et tirets)

```text
jellyfin ffmpeg dolby-vision hdr10 hevc video-encoding transcoding direct-play media-server home-theater webos lg-tv dovi-tool eac3 mkv mp4 tui textual python windows
```

### Sur github.com

Page d'accueil du dépôt → roue dentée ⚙️ à droite de **About** :
- *Description* : coller le texte ;
- *Topics* : taper chaque sujet, puis Entrée ;
- décocher *Packages* et *Deployments* (inutilisés) ; laisser *Releases* coché.

### Avec `gh`

```bash
gh repo edit opegon/IRIS_Encode --description "Prepare a movie library for Jellyfin direct play: re-encode only what needs it, strip Dolby Vision without re-encoding, and see every decision before it runs. Terminal app for Windows; Linux planned for 2027."
```

```bash
gh repo edit opegon/IRIS_Encode --add-topic jellyfin,ffmpeg,dolby-vision,hdr10,hevc,video-encoding,transcoding,direct-play,media-server,home-theater,webos,lg-tv,dovi-tool,eac3,mkv,mp4,tui,textual,python,windows
```

---

## 2. Activer Discussions

Le README, CONTRIBUTING et les modèles d'issues y renvoient : sans
Discussions, ces liens mènent à une page d'erreur.

- **github.com** : *Settings* → *General* → *Features* → cocher **Discussions**.
- **gh** :

```bash
gh repo edit opegon/IRIS_Encode --enable-discussions
```

Catégories conseillées, à créer dans l'onglet *Discussions* (crayon ✏️ à côté
de *Categories*) :

| Catégorie | Format | Usage |
|---|---|---|
| Announcements | Announcement | Nouvelles versions, portage Linux. Toi seul y publies. |
| Q&A | Question / Answer | « Comment faire… » — une réponse peut être marquée comme solution |
| Profiles | Open-ended discussion | Partage de profils pour un écran donné |
| Ideas | Open-ended discussion | Idées pas encore mûres pour une issue |
| Français | Open-ended discussion | Pour qui préfère échanger en français |

Supprime les catégories par défaut inutiles (*Show and tell*, *Polls*…).

---

## 3. Activer le signalement privé des vulnérabilités

SECURITY.md et les modèles d'issues pointent dessus.

- **github.com** : *Settings* → *Security* (ou *Code security*) → **Private
  vulnerability reporting** → *Enable*.
- **gh** :

```bash
gh api -X PUT repos/opegon/IRIS_Encode/private-vulnerability-reporting
```

Active aussi, au même endroit, **Dependabot alerts**. Il te préviendra si une
dépendance de `requirements.txt` a une faille connue.

---

## 4. Créer les étiquettes (*labels*)

Les modèles d'issues posent `bug`, `enhancement` et `playback`. Les deux
premières existent par défaut ; les autres sont à créer :

```bash
gh label create playback --repo opegon/IRIS_Encode --color 1D76DB --description "How an IRIS output plays on a given screen, client or server"
```

```bash
gh label create platform --repo opegon/IRIS_Encode --color 5319E7 --description "Linux and macOS ports"
```

```bash
gh label create needs-info --repo opegon/IRIS_Encode --color FBCA04 --description "Waiting for details from the reporter"
```

`good first issue` et `help wanted` existent par défaut. Pose-les sur
quelques issues simples : GitHub les met en avant auprès des nouveaux
contributeurs.

Sur github.com : onglet *Issues* → *Labels* → *New label*.

---

## 5. Désactiver l'onglet Wiki de GitHub

Ton wiki vit dans le dépôt (`wiki/`). L'onglet *Wiki* de GitHub est vide et
risque d'induire en erreur.

- **github.com** : *Settings* → *General* → *Features* → décocher **Wikis**.
- **gh** :

```bash
gh repo edit opegon/IRIS_Encode --enable-wiki=false
```

---

## 6. Image de partage (*social preview*)

C'est l'image qui s'affiche quand le lien du dépôt est partagé sur un forum,
Reddit ou Mastodon. Sans elle, GitHub génère une carte grise générique.

- Format : PNG ou JPG, **1280 × 640 px**, moins de 1 Mo.
- Contenu : le nom, l'accroche (« Jellyfin direct play, without re-encoding
  what doesn't need it »), et une capture de l'écran d'accueil.
- **github.com uniquement** : *Settings* → *General* → *Social preview* →
  *Edit* → *Upload an image*.

Pour la capture, `python tests/shots_tui.py --langue en` exporte chaque écran
en SVG dans `_shots/en/`, à partir de vrais fichiers placés dans
`resources_files/`. La même capture peut aller en tête du README : un
commentaire y marque l'emplacement prévu.

---

## 7. Ouvrir l'issue de suivi du portage Linux

C'est l'issue vers laquelle renvoient README et CONTRIBUTING. Épingle-la
ensuite (menu `…` de l'issue → *Pin issue*).

```bash
gh issue create --repo opegon/IRIS_Encode --label platform --label "help wanted" --title "Linux port (planned for 2027), then macOS" --body-file - <<'EOF'
IRIS ENCODE runs on Windows today. **Linux support is planned for 2027**, macOS after.

What already exists:
- platform-specific code is kept in `core/platform.py`;
- Linux download sources for ffmpeg and dovi_tool in `data/ffmpeg_releases.toml`;
- VideoToolbox (macOS) is already among the encoders.

What will be needed:
- [ ] a launcher equivalent to `launch.bat` / `bootstrap.ps1`
- [ ] tool installation: static builds or package manager (mkvmerge has no official static Linux build)
- [ ] hardware encoding: NVENC, VAAPI / Quick Sync on Linux
- [ ] DVD / Blu-ray folders and mounted volumes
- [ ] testers on common distributions (Ubuntu, Debian, Fedora, Arch) and on a NAS over SSH

**Want to help or test?** Comment here with your distribution and hardware. Please discuss before writing code, so the work is not done twice. English or French.
EOF
```

---

## 8. Autres réglages utiles (facultatifs)

- **Branche protégée** : *Settings* → *Branches* → règle sur `main` avec
  *Require a pull request before merging*. Ça évite un push direct par erreur
  une fois qu'il y a des contributeurs.
- **Notes de version en anglais** : les titres de release sont en français
  (« la pause se voit… »). Un public anglophone lira la page *Releases* : une
  ligne en anglais en tête de chaque note suffit.
- **Code de conduite** : CONTRIBUTING contient une courte section
  « Behaviour ». Si le projet grossit, *Insights* → *Community standards* →
  *Code of conduct* → *Add* propose le Contributor Covenant en un clic.

---

## Vérification finale

*Insights* → **Community standards** : GitHub y coche ce qui est en place
(description, README, licence, contributing, security policy, issue
templates). Il ne devrait rester que *Code of conduct* si tu ne l'as pas
ajouté.

Ce fichier est un aide-mémoire : une fois les réglages faits, tu peux le
supprimer du dépôt.
