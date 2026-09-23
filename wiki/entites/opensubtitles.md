---
type: entite
categorie: service
maj: 2026-09-24
sources:
  - "[[source-spec]]"
  - "[[source-changelog]]"
---

# OpenSubtitles.com

Service de sous-titres, interrogé par son API REST. Usage dans IRIS : trouver
un `.srt` à greffer ([[sous-titres]]).

## Recherche

- **Par empreinte** (`moviehash`) : sous-titres déposés pour cette release
  exacte, donc déjà synchronisés.
- **Par nom** : titre, plus saison et épisode pour une série. Rattrape un
  fichier réencodé, dont l'empreinte n'est plus celle de la release.
- **Empreinte** : taille du fichier + somme des mots 64 bits little-endian des
  64 premiers et 64 derniers Kio, modulo 2⁶⁴, sur 16 chiffres hexadécimaux.
  Aucune sous 128 Kio. Même algorithme que l'extension Kodi officielle.
- **50 résultats par page.** La première page seule cachait des sous-titres
  français derrière des anglais plus téléchargés (Inception : 44 résultats
  lus sur 72, contre 64 sur 5 pages). *(mesuré)*
- Paramètres de requête **triés**, sinon l'API redirige. *(mesuré)*
- Codes de langue propres à l'API, à traduire depuis l'ISO 639-2.

## Compte et quotas

- Clé d'application (opensubtitles.com/consumers) exigée à **chaque** appel.
- Identifiant et mot de passe exigés au **téléchargement** seulement ;
  **20 téléchargements par jour** en compte gratuit. *(documenté)*
- Un compte VIP est servi par l'hôte que `login` annonce (`base_url`).
- Refus : 401 identifiants, 406 quota du jour (avec heure de remise), 429 trop
  de requêtes (`Retry-After`).

Recherche éprouvée contre l'API réelle ; **téléchargement non éprouvé**
([[questions-ouvertes]]).
