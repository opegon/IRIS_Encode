# 2026-10-04 — Décisions de localisation (IE-83, IE-85, IE-86, IE-111)

Réponses de l'utilisateur, en séance, aux questions posées après l'audit de
localisation (`audit_localisation_2026-10-04.md`).

**Noms de piste proposés au recalage** (L-77) :

> 1. liste selon langue.

**Messages de `main.py` avant la configuration, et `updater.py`** (L-85, L-87) :

> 2. Anglais seul

**Erreurs affichées** (L-18) :

> 3. je te laisse déterminer le plus robuste

Retenu : l'erreur porte un identifiant de message et ses paramètres, l'écran
traduit (`ErreurAffichable`).

**Revue de code d'IE-83** : choix « Clore sans revue » — revue complète reportée
après la localisation (IE-114).

**Compilation des `.mo`** (IE-111 point 4) : choix « .mo versionnés ».

**Outillage d'extraction et de compilation** : choix « Scripts maison », contre
Babel.

**Glossaire** (IE-85), choix parmi des options proposées :

- « SKIP » : « Terme invariant » — gardé tel quel dans toutes les langues ;
- nom anglais de l'écran Aperçu : « Dry run » ;
- nom anglais de l'assistant : « Guided » ;
- « lossless → copy » dans les raisons audio : « Garder l'anglais ».
