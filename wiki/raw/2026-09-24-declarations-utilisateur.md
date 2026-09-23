# Déclarations de l'utilisateur

Ce que l'utilisateur a dit de son installation et de ses constats, cité tel quel.
**Fichier immuable** : ajouter une nouvelle déclaration en fin de fichier, datée.

## 2026-09-23

> en dehors d'IRIS, je préfère que les suffixe soient marqués en minuscule

## 2026-09-24

> je souhaite revenir sur la conversion des fichiers DV en HDR, j'ai utilisé la
> fonction sur quelques fichiers et il y a toujours des problèmes de lecture sur
> la tv avec une lecture qui commence mais sans image et que le son et un
> plantage complet quelques dizaines de scondes plus tard.

> ma tv est une LG OLED G3

> ma chaine de diffusion est un serveur Jellyfin sans possibilité de transcodage
> matériel

## Antérieures (README du projet, rédigé avec l'utilisateur)

Contraintes de la chaîne telles que décrites dans `README.md` § « La chaîne de
diffusion et ses contraintes » : Jellyfin transcode tout format non reconnu ;
le LG OLED (webOS) ne lit aucun audio sans perte, le MKV y est capricieux, le
DV profil 8 déclenche un remux HLS avec coupures audio, le DTS gèle au saut sur
les modèles 2023 ; la barre de son eARC ne reçoit pas de sans perte quand le
téléviseur mixe ; Swiftfin (VLCKit) est permissif, le lecteur natif Apple ne
change pas de piste audio ; les sous-titres image forcent l'incrustation.
