---
type: concept
maj: 2026-09-29
sources:
  - "[[source-spec]]"
  - "[[source-changelog]]"
  - "[[source-2026-09-24-mise-a-jour]]"
---

# Lancer les outils externes

Règles valables pour tout appel à [[ffmpeg]], [[ffprobe]], [[mkvmerge]],
[[dovi-tool]] ou [[mpv]]. Chacune vient d'un défaut silencieux
([[pieges-et-lecons]]).

## Trouver l'outil

**Ordre de recherche : `PATH` système, puis `bin/`.** Le preflight installe
dans `bin/` **sans toucher au `PATH`** : tout appel doit passer par le chemin
résolu. Un appel par nom nu marche sur un poste qui a l'outil dans son `PATH`
et échoue sur une installation neuve : tous les fichiers y étaient déclarés
illisibles. *(mesuré, v0.8.1.19)*

L'absence d'un outil optionnel désactive la fonction qui en dépend, sans
bloquer le lancement.

## Les règles

- **`stdin=subprocess.DEVNULL`, sans exception.** ffmpeg lit `stdin` pour son
  clavier interactif et hérite sinon de celle du terminal, que l'interface
  Textual écoute : les deux se disputent les frappes. Un test refuse tout
  lancement sans `stdin=`. *(mesuré, IE-58)*
- **Lire la sortie en UTF-8** (`encoding="utf-8", errors="replace"`), jamais
  `text=True`. Sous Windows français, `text=True` décode en cp1252. Le premier
  caractère hors table (« ❤️ » dans un tag) lève une exception **dans le
  thread de lecture**, qui ne remonte pas : `stdout` vaut `None` et le
  fichier disparaît de la liste sans message. *(mesuré, v0.8.1.23)*
- **Un seul tube** (`stderr=STDOUT`) quand on lit la progression au fil de
  l'eau. Deux tubes dont un seul est lu se bloquent dès que l'autre est
  plein. *(mesuré, IE-46)*
- **Un code de retour nul ne prouve pas le succès** : relire la sortie (durée
  des pistes, nombre d'images). *(mesuré, v0.8.2.8)*
- **Vérifier le code de retour** d'un décodage : un ffmpeg tué rend une
  sortie partielle qui passe pour un film court. *(mesuré, IE-41)*
- Tuer le processus si la boucle de lecture sort en erreur : un ffmpeg oublié
  décode un film entier pour personne.
- **Quitter un écran ne tue rien.** Dépiler l'écran d'encodage laissait
  ffmpeg écrire la sortie, invisible (UX-01). Un arrêt voulu termine le
  processus **et** lève un drapeau que chaque démarrage relit *après* avoir
  lancé le sien : sans ce second verrou, un arrêt tombé entre deux étapes
  (mux préalable → encodage) laissait partir l'étape suivante. *(mesuré à
  l'essai pour UX-01 ; le drapeau est vérifié par `tests/test_arret_encodage.py`,
  v0.8.9.5)*

## Scripts .bat réécrits pendant leur exécution

cmd.exe lit un `.bat` **au fil de l'exécution, par position dans le fichier**.
Si le fichier est remplacé pendant qu'il tourne (par une mise à jour, par
exemple), la suite est lue dans le nouveau fichier à l'ancienne position : un
fragment de ligne est exécuté comme une commande. *(mesuré, Windows 11)*

Parade : placer ce qui peut remplacer le fichier **et tout ce qui suit** dans
un bloc `( … )`, qui se termine par la relance ou `exit /b`. cmd lit un bloc en
entier avant de l'exécuter. *(mesuré, voir [[2026-09-24-mise-a-jour-application]])*

## Voir aussi

[[ffmpeg]] · [[ffprobe]] · [[mkvmerge]] · [[dovi-tool]] · [[mpv]] · [[github]] · [[pieges-et-lecons]]
