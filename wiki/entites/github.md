---
type: entite
categorie: service
maj: 2026-09-24
sources:
  - "[[source-2026-09-24-mise-a-jour]]"
  - "[[source-spec]]"
---

# GitHub (releases)

Hébergement du dépôt `opegon/IRIS_Encode` et de ses releases. Source des mises
à jour de l'application (`updater.py`) et des outils externes
(`core/updates.py` : [[dovi-tool]] chez quietvoid, [[ffmpeg]] chez BtbN).

## API des releases

- `GET https://api.github.com/repos/<depot>/releases/latest` rend la release
  marquée **« Latest »** : ni brouillon, ni pré-version. *(mesuré)*
- Sans jeton : **60 appels par heure** par adresse IP. D'où un cache d'une
  journée côté IRIS. *(documenté)*
- Chaque asset porte `name`, `browser_download_url`, et un champ **`digest`**
  de la forme `sha256:<hex>`, l'empreinte calculée par GitHub à l'envoi.
  *(mesuré : `sha256:8c96cd55…` pour `iris_encode_v0.8.9.0.zip`, conforme au
  fichier téléchargé)*
- `browser_download_url` redirige vers le stockage de GitHub ; `urllib` suit la
  redirection sans réglage. *(mesuré)*
- Un en-tête `User-Agent` est exigé par l'API. *(documenté)*

## Les archives d'IRIS

L'archive jointe à chaque release, `iris_encode_vX.zip`, est exactement le
`git archive` du tag : mêmes fichiers, sans `config.toml`, `profiles.toml`,
`CLAUDE.md`, `bin/` ni `.venv/`. *(mesuré sur la v0.8.8.10 : 130 fichiers
identiques)* C'est ce qui permet de l'extraire par-dessus une installation sans
toucher aux fichiers personnels.

## Voir aussi

[[sous-processus]] · [[ffmpeg]] · [[dovi-tool]] · [[mkvmerge]]
