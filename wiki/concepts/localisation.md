---
type: concept
maj: 2026-10-07
sources:
  - "[[source-2026-10-04-localisation]]"
  - "[[source-spec]]"
  - "[[2026-10-07-decisions-formats]]"
  - "[[2026-10-07-decisions-console]]"
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

## Voir aussi

- [[noms-de-release]] — les marques, qui ne se traduisent pas
- [[sous-titres]] — drapeaux forcé et par défaut, codes de langue
- [[source-2026-10-04-localisation]]
