---
type: concept
maj: 2026-10-07
sources:
  - "[[source-2026-10-04-localisation]]"
  - "[[source-spec]]"
  - "[[2026-10-07-decisions-formats]]"
  - "[[2026-10-07-decisions-console]]"
  - "[[2026-10-07-decisions-choix-langue]]"
---

# Localisation

Rendre l'interface traduisible : anglais US et français pour la v0.9.0, puis des
langues apportées par des bénévoles sur Weblate. Le mécanisme (gettext, anglais
source, `.mo` versionnés) est décrit par la spec, § 2.1 ; les règles d'écriture
des messages, en tête de `core/i18n.py`. Cette page dit **quoi** traduire et
**comment** nommer les choses.

## Ce qui ne se traduit jamais

Principe : on traduit ce qui **s'affiche**, jamais ce qui **s'écrit** sur le
disque ou part vers un autre programme. Un même fichier source doit donner le
même fichier de sortie quelle que soit la langue de l'interface.

- **Écrit dans les fichiers produits** : suffixes et marques (`.hevc-iris`), titres
  de pistes réécrits (« E-AC3 5.1 »), codes de langue (`fre`, `eng`), noms des
  `.srt` produits, **noms de piste proposés au recalage** (voir plus bas).
- **Réglages** : clés et valeurs de `config.toml` et `profiles.toml`, noms des
  profils (`series_basic`…). L'écran traduit le libellé d'une option, jamais sa
  valeur ; aucune logique ne compare un texte affiché.
- **Envoyé à un programme** : arguments de ffmpeg, mkvmerge, dovi_tool ; requêtes
  aux services. Les sorties de ffmpeg sont lues **en anglais** ([[ffmpeg]]) :
  ne jamais le lancer sous une langue traduite.
- **Lu dans les noms de fichiers** : jetons de release ([[noms-de-release]]).
- **Journaux** : dans une langue stable, l'anglais du message source.
- **Avant la configuration** : lanceurs (`launch.bat`, `bootstrap.ps1`,
  `launcher/`), `updater.py`, et dans `main.py` la version de Python, les
  dépendances manquantes, `--help`, le chemin introuvable — anglais seul
  (décidé le 2026-10-04, livré en v0.8.9.83). La **bannière** et « Vérification
  des outils : », elles, suivent la langue : `main.py` la charge juste avant
  ([[2026-10-07-decisions-console]]). Les `.bat` n'affichent que de l'ASCII.
- **Termes techniques et noms propres** : la liste « Do not translate » du
  glossaire.

## Noms de piste proposés

Le champ Nom du recalage propose des noms **selon la langue de la piste**, pas
de l'interface (décidé le 2026-10-04) : `fre` → VF, VFF, VFQ, VOSTFR, Forcés,
Commentaires, SDH ; `eng` → English, Forced, Commentary, SDH ; autre langue →
Forced, SDH. Ce sont des données écrites dans le fichier ([[sous-titres]]).

## Formats

Arbitrés par l'utilisateur le 2026-10-07 ([[2026-10-07-decisions-formats]]) :
les formats suivent `[app] language`, jamais les paramètres régionaux de Windows,
et une seule chose varie d'une langue à l'autre : **l'unité d'octets**
(TB/GB/MB/KB en anglais, comme l'Explorateur, qui compte pourtant en 1024 ;
To/Go/Mo/Ko en français), au catalogue sous le contexte `bytes`. Le reste est
identique partout, hors catalogue : **point décimal** (`1.5 Go`), **pourcentage
collé** au nombre (`12%`, aussi en français), durées `H:MM:SS`, symboles `ms`,
`s`, `k`, `kbps`. Le texte de remise du quota OpenSubtitles est montré tel que
l'API l'envoie, en anglais. `tests/test_formats.py` garde ces règles.

## Choix de la langue

Arbitré par l'utilisateur le 2026-10-07 ([[2026-10-07-decisions-choix-langue]]).
L'écran Options propose l'anglais et chaque catalogue livré, chacun nommé **dans
sa propre langue** : un nouveau catalogue Weblate s'y ajoute sans code, et son
traducteur fournit ce nom (message `language name`). Au premier lancement, la
langue d'affichage de Windows si elle est traduite, sinon l'anglais — jamais un
code sans catalogue, que l'écran ne saurait montrer coché. Un changement prend
effet au redémarrage, annoncé par un message ; rien ne relance l'application.

## Glossaire

**Un terme anglais, une traduction, partout.** Le glossaire vit dans
`locales/glossaire.fr.csv` (colonnes `source`, `target`, `explanation`), seule
source des termes ; `tests/test_i18n.py` vérifie qu'un terme n'y figure qu'une
fois et qu'un terme marqué « Do not translate » reste identique. Le format CSV
est importable comme glossaire Weblate *(supposé : à vérifier au branchement,
IE-111 point 7)*.

Arbitrages de l'utilisateur, le 2026-10-04 :

| Question | Choix |
|---|---|
| « SKIP » | invariant dans toutes les langues |
| Nom anglais de l'Aperçu | **Dry run** (« Preview » se confondrait avec la lecture, « Play ») |
| Nom anglais de l'assistant | **Guided** (pied de page « W Guided » / « W Manual ») |
| « lossless → copy » dans les raisons audio | gardé en anglais ; dans une phrase, le français écrit « sans perte » ; le libellé de colonne « → copie » reste traduit |

Proposés par IRIS et non contestés : « release » invariant ; SME (sourds et
malentendants) ↔ **SDH** ; la fiche AlloCiné/IMDB ↔ **Info** ; la greffe d'une
piste ↔ **add**, piste greffée ↔ **added track** ; plage ↔ **segment** ;
marque ↔ **tag**.

## Anglais source

Relu en entier le 2026-10-07 (IE-93, v0.8.9.85). Conventions retenues, à tenir
pour tout nouveau texte :

- **anglais américain** : *movie* (jamais *film*, sauf la marque d'un nom de
  release), *canceled*, *-ize* (*Analyzing*, *initializing*), *anymore* ;
- un **nom d'écran** prend sa majuscule quand une phrase le cite : « the Tracks
  screen », « the Home screen », « Resizable columns — Home, Tracks, Dry run » ;
  l'activité garde la minuscule (« go to dry run ») ;
- le **terme du glossaire, pas un synonyme** : *segment* (pas *range*), *anchor
  point* (pas *reference point*), *added track* (pas *graft*), *subtitle line*
  (pas *cue*), *check sample* ;
- un texte anglais plus long que le français peut tronquer une colonne dont la
  largeur suivait l'en-tête français : les captures anglaises
  (`tests/shots_tui.py` avec la langue forcée à `en`) l'ont montré deux fois.

Un `msgid` modifié perd sa traduction : il faut reporter le `msgstr` français
sur le nouveau texte, et retirer l'ancienne entrée devenue obsolète (`#~`).

## Tests

Livrés le 2026-10-07 (IE-94, v0.8.9.87). Ce qui tient la localisation :

- `tests/smoke_tui.py` tourne **en anglais puis en français**, un processus par
  langue (`smoke_tui.py fr` pour une seule) ; ses attentes passent par `_()` ;
- `tests/shots_tui.py --langue en` : captures dans `_shots/en/` ;
- le guide des touches (`test_aide.py`) et les planchers de colonnes
  (`test_troncature.py`) sont vérifiés dans chaque langue — fixture `langue` de
  `tests/conftest.py`, à demander par tout test qui rend du texte ;
- `test_i18n.py`, règles structurelles : aucun littéral à mots passé en dur à
  un point d'affichage (`notify`, `Static`, `Label`, `Button`, `Text`,
  `add_column`, `colonne_fixe`, `Binding`, `ErreurAffichable`) sauf les termes
  « Do not translate » du glossaire et les unités ; aucun littéral accentué
  hors `_()` dans `core/` comme dans `tui/` ; aucune comparaison à un texte
  traduit.

Le test des accents ne voyait que le français : le contrôle des points
d'affichage a trouvé « Jonction », « Choisir » et « Annuler », sans accent,
affichés tels quels dans l'interface anglaise.

## Documentation

Livrée le 2026-10-07 (IE-95, v0.8.9.88). `README.md` et `GUIDE.md` en anglais,
`README.fr.md` et `GUIDE.fr.md` en français (renommés par `git mv`, l'historique
suit), lien croisé en tête de chacun. La version anglaise cite les libellés de
l'interface anglaise, pas une retraduction du français : « confidence
excellent », « different cut — N segments », « Dry run ». La spec (§ 2.1), le
wiki et le `CHANGELOG.md` restent en français : documentation de développement.
`install.txt`, livré avec les lanceurs, est en anglais.

La relecture a montré que le guide français avait dérivé en plusieurs points
(touches `F7`/`F8` de la fiche, colonne « Raison » disparue, profils renommés) :
la traduction est aussi un audit de la documentation.

## Voir aussi

- [[noms-de-release]] — les marques, qui ne se traduisent pas
- [[sous-titres]] — drapeaux forcé et par défaut, codes de langue
- [[source-2026-10-04-localisation]]
