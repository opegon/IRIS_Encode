# Mise à jour de l'application — relevés bruts

Session du 2026-09-24, développement d'`updater.py` (v0.8.9.1).
**Fichier immuable** : ne pas modifier, ajouter un nouveau relevé à côté.

## cmd.exe et un .bat réécrit pendant son exécution

Windows 11 Home 10.0.26200, cmd.exe.

`naif.bat` (sans bloc) :

```
@echo off
echo avant
python rewrite.py naif.bat new.txt
echo APRES-ANCIEN-1
echo APRES-ANCIEN-2
```

`rewrite.py` remplace `naif.bat` par une version plus longue
(`@echo off`, `REM xxx…` sur 120 caractères, `echo NOUVEAU-debut`, `echo NOUVEAU-fin`).
Sortie :

```
avant
'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' n'est pas reconnu en tant que commande interne
ou externe, un programme exécutable ou un fichier de commandes.
NOUVEAU-debut
NOUVEAU-fin
```

`bloc.bat` (appel et suite dans un bloc `( … )` terminé par `exit /b 0`), même
réécriture. Sortie :

```
avant
DANS-LE-BLOC
```

`launch.bat` réel du projet, dans une installation temporaire, avec un faux
`updater.py` qui remplace `launch.bat` par une version de 300+ octets puis rend
10. Sortie :

```
FAUX-UPDATER: launch.bat remplace, code 10
RELANCE-SUR-LE-NOUVEAU-LAUNCH
```

Le `main.py` d'origine (qui imprimait `MAIN-ANCIEN-LANCE`) n'a pas été lancé.

## Mise à jour réelle contre GitHub

Installation temporaire construite depuis le dépôt, `version.py` forcé à
`0.8.8.0`, `[updates] app = "auto"`, `config.toml` et `profiles.toml` personnels,
`bin/ffmpeg.exe` factice, `core/fichier_perso.py` ajouté.

```
  Téléchargement de iris_encode_v0.8.9.0.zip…

  [AVERTISSEMENT] Mise à jour impossible : archive incomplète, il manque : updater.py
  IRIS ENCODE démarre dans sa version actuelle.
```

- code retour 0 ; `version.py` resté à 0.8.8.0 ; `config.toml`, `profiles.toml`,
  `bin/`, `core/fichier_perso.py` intacts ;
- `.iris_update/release.json` : tag `v0.8.9.0`, asset
  `iris_encode_v0.8.9.0.zip`, URL
  `https://github.com/opegon/IRIS_Encode/releases/download/v0.8.9.0/iris_encode_v0.8.9.0.zip`,
  digest `sha256:8c96cd55363150df9f93b05687412e7970e24abe7c74fd02c6041cdf18b49c65` ;
- l'archive téléchargée était restée dans `.iris_update/` (corrigé ensuite).

L'API `releases/latest` répond sans jeton ; l'asset porte un champ `digest`
`sha256:…` ; `browser_download_url` redirige et `urllib` suit la redirection ;
l'empreinte calculée sur le téléchargement correspond au `digest` (le contrôle
d'empreinte a été franchi avant le refus pour contenu).
