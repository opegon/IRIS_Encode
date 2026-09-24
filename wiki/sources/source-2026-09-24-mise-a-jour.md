---
type: source
maj: 2026-09-24
ingere: 2026-09-24
---

# Source : Mise à jour de l'application (2026-09-24)

**Où** : [[2026-09-24-mise-a-jour-application]]
**Nature** : relevés bruts d'une session, immuables

Relevés faits en écrivant `updater.py` (v0.8.9.1) : comportement de cmd.exe
face à un `.bat` réécrit pendant son exécution, et premier essai réel de mise à
jour contre l'API des releases GitHub.

## Conclusions

- cmd.exe reprend un `.bat` remplacé à l'ancienne position ; un bloc `( … )`
  est lu en entier et protège la relance.
- L'API `releases/latest` et l'empreinte `digest` des assets fonctionnent comme
  prévu ; la v0.8.9.0 est refusée, faute d'`updater.py`.

## Pages alimentées

[[github]] · [[sous-processus]] · [[pieges-et-lecons]]
