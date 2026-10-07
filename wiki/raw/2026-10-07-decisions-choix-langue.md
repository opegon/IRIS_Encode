# 2026-10-07 — Décisions : choix de la langue (IE-92)

Questions posées en séance par IRIS, options retenues par l'utilisateur :

| Question | Options proposées | Choix |
|---|---|---|
| Langues proposées par l'écran Options, et sous quel nom | catalogues présents, chacun nommé dans sa langue · liste fixe en/fr | **catalogues présents** |
| Windows dans une langue non traduite au premier lancement | écrire « en » · écrire le code détecté | **« en »** |
| Après l'enregistrement d'une autre langue | message seulement · proposer de quitter · relancer seul | **message seulement** |

Annoncé et non contesté : section dans l'écran Options (`F5`, `U`) ; valeur par
défaut de `[app] language` vidée (les installations existantes ont déjà « fr »
écrit) ; détection sur la langue d'affichage de Windows, pas le format régional ;
hors Windows, `LANG`, sinon l'anglais.
