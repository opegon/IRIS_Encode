---
type: schema
maj: 2026-09-24
---

# Schéma du wiki

Wiki tenu par Claude sur le modèle « LLM Wiki » de Karpathy : le savoir est compilé
une fois dans des pages reliées, pas redécouvert à chaque question.
**À consulter pour chaque question**, avant de répondre, de diagnostiquer ou de
modifier le code : lire `wiki/index.md`, puis les pages concernées.
**À enrichir dès qu'on apprend quelque chose** : une mesure, un comportement
d'outil, un symptôme sur le téléviseur, une hypothèse infirmée.

Le wiki dit comment le monde se comporte (formats, outils, matériel) ; la spec dit
ce que fait le code. Il n'est pas versionné comme l'application : ses pages sont datées.

Ce fichier est le **schéma** du wiki. Le `CLAUDE.md` du projet, local et hors
dépôt, y renvoie. Une convention qui change se change ici, et le changement est
noté au journal.

## Couches

- `wiki/raw/` : relevés bruts et citations de l'utilisateur, **immuables** : on
ajoute un fichier daté (`AAAA-MM-JJ-sujet.md`), on n'en modifie jamais un. Pas de frontmatter.
- `wiki/sources/` : une page `source-…` par source ingérée (docs du dépôt ou fichier
de `raw/`) : ce qu'elle apporte, vers quelles pages ses faits sont partis.
- `wiki/entites/` (outils, matériel, services), `wiki/concepts/` (sujets),
`wiki/syntheses/` (vues transverses : chaîne de diffusion, leçons, questions ouvertes).
- `wiki/index.md` : catalogue, une ligne par page. `wiki/log.md` : journal en ajout seul.

## Conventions

- Noms de fichiers uniques, en minuscules avec tirets ; liens `[[nom]]`,
`[[nom#Titre exact]]`, `[[nom|libellé]]` (syntaxe Obsidian, résolue par le nom seul).
- Frontmatter YAML : `type` (entite, concept, synthese, source, index, log, schema), `maj`
(date), `sources` (liste de `"[[source-…]]"`, obligatoire hors sources).
- Chaque fait porte son niveau de preuve : *mesuré* (vérifié ici, outil et version
cités), *observé* (sur le matériel, rapporté par l'utilisateur), *documenté* (dit par
l'outil), *supposé* (à vérifier avant de s'appuyer dessus).
- Un fait vit dans une seule page ; les autres y renvoient. Chaque page finit par
« Voir aussi ».

## Opérations

Chacune ajoute une entrée `## [AAAA-MM-JJ] ingest|query|lint | titre` à `log.md`.

- **ingest** : déposer le relevé dans `raw/` s'il vient de la session, écrire sa page
`source-…`, puis mettre à jour *toutes* les pages touchées (entités, concepts,
synthèses) : remplacer ce qui est contredit, ne pas empiler. Retirer de
`questions-ouvertes` ce qui est tranché. Mettre à jour `index.md` et les dates `maj`.
- **query** : répondre depuis le wiki en citant les pages ; une réponse qui apprend
quelque chose est versée dans la page concernée.
- **lint** : `python -m pytest tests/test_wiki.py` vérifie liens, orphelins, index,
frontmatter et journal. La relecture cherche le reste : contradictions, affirmations
périmées, faits *supposés* devenus vérifiables, sujets sans page.
