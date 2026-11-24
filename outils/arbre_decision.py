"""outils/arbre_decision.py — Document PDF de l'arbre de décision d'IRIS Encode.

Outil de documentation, sans dépendance Python. Produit, à la racine du
projet, `IRIS_Encode_arbre_de_decision_v<RELEVE>.pdf` : tous les tests et
décisions appliqués à un fichier vidéo, de l'entrée à la sortie, en pièces
A4 (un diagramme Mermaid par page, mis à l'échelle de la page).

    python outils/arbre_decision.py            # PDF à la racine du projet
    python outils/arbre_decision.py --html     # garde aussi le HTML à côté

Il faut un Microsoft Edge ou un Google Chrome récent (impression sans
interface ; la variable IRIS_NAVIGATEUR en impose un) et l'accès réseau :
Mermaid est chargé depuis cdn.jsdelivr.net.

**Le contenu est écrit à la main**, d'après le code de la version `RELEVE`.
Il ne se met pas à jour seul : quand la logique de décision change, revoir les
pièces contre le code (`core/decision.py`, `core/encoder.py`,
`core/scanner.py`, `core/preflight.py`, `tui/screens/run.py`), puis relever
`RELEVE`. L'outil avertit quand `RELEVE` et `version.py` diffèrent.

Déroulé : la page est servie par un serveur local éphémère. Elle porte une
image `/attendre` que le serveur ne rend qu'une fois les diagrammes dessinés
(POST `/pret`) : l'événement `load` attend donc le rendu, et le navigateur
n'imprime qu'après. Imprimée sans cette attente, la page sortait avec des
diagrammes à moitié dessinés.
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import date
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# Version du code sur laquelle le contenu des pièces a été relevé et vérifié.
RELEVE = "0.9.3.13"

# Corps minimal accepté pour le texte d'un diagramme, une fois mis à l'échelle.
CORPS_MIN_PT = 7.5

MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre")

PIECES: list[dict] = []


def piece(chap, num, orient, titre, sous_titre, mermaid, notes=(), source=""):
    PIECES.append(dict(chap=chap, num=num, orient=orient, titre=titre,
                       sous_titre=sous_titre, mermaid=mermaid.strip("\n"),
                       notes=list(notes), source=source))


CLASSES = """
  classDef test fill:#FFFFFF,stroke:#051C2C,stroke-width:1.6px,color:#051C2C
  classDef enc fill:#2251FF,stroke:#1A3FCC,color:#FFFFFF
  classDef ok fill:#D3F1FB,stroke:#00A9F4,color:#051C2C
  classDef dv fill:#051C2C,stroke:#051C2C,color:#FFFFFF
  classDef off fill:#EFEFEF,stroke:#9A9A9A,color:#4D4D4D
  classDef err fill:#FBE3E3,stroke:#C8102E,color:#7A0A1C
"""


# ── 1. Vue d'ensemble ─────────────────────────────────────────────────────────
piece("Vue d'ensemble", "1", "land",
      "Un fichier traverse trois phases : préparation, décision, exécution",
      "Trajet complet d'un fichier vidéo, du lancement de l'application au fichier suivant du lot",
      """
flowchart LR
  subgraph PREP["Préparation · chapitres 2 et 3"]
    direction TB
    A(["Lancement"]) --> B["Preflight<br/>outils"]
    B --> C["Accueil<br/>filtre des fichiers"]
    C --> D["Analyse<br/>VideoInfo"]
  end
  subgraph DEC["Décision · chapitres 4 à 7"]
    direction TB
    E["Vidéo<br/>decide_video"] --> F["Audio<br/>decide_audio"]
    F --> G["Sous-titres<br/>decide_subtitles"]
    G --> H["SKIP ⇄ REMUX<br/>ajuster_remux"]
    H --> I["Conteneur<br/>MKV ou MP4"]
    I --> J["Nom de sortie<br/>suffixe -iris"]
  end
  subgraph EXE["Exécution · chapitres 8 à 10"]
    direction TB
    L["Mise en file<br/>noms figés"] --> M["Aiguillage<br/>mux, DV, ffmpeg"]
    M --> N{"Sortie<br/>conforme ?"}
    N -->|oui| P["Source supprimée<br/>si delete_source"]
    N -->|non| Q["Sortie partielle<br/>effacée"]
  end
  PREP --> DEC
  DEC --> K{"Changement<br/>manuel ?"}
  K -->|oui| DEC
  K -->|non| EXE
  class N,K test
  class Q err
  class P ok
""",
      ["Toute modification de piste ou de réglage (écran Pistes, Assistant, Aperçu) relance toute la phase de décision.",
       "Les pièces suivantes détaillent chaque bloc dans l'ordre d'évaluation du code."],
      "core/decision.py (decide) · tui/screens/run.py (_encoder_suivant)")

# ── 2. Lancement ──────────────────────────────────────────────────────────────
piece("Lancement et outils", "2", "port",
      "Seuls ffmpeg et ffprobe sont bloquants ; chaque outil optionnel absent ferme une branche",
      "Contrôle des outils au démarrage et conséquences sur les décisions ultérieures",
      """
flowchart TD
  S(["main.py"]) --> CFG{"config.toml<br/>lisible ?"}
  CFG -->|non| CFG2["Réglages par défaut<br/>fichier non modifié"]
  CFG -->|oui| T
  CFG2 --> T{"ffmpeg et ffprobe trouvés ?<br/>PATH, puis ./bin"}
  T -->|non| DL["Installation proposée<br/>SHA256 exigé<br/>pose tous ou aucun"]
  DL --> T2{"Présents<br/>après coup ?"}
  T2 -->|non| STOP(["Arrêt :<br/>outils manquants"])
  T2 -->|oui| OPT
  T -->|oui| OPT["Outils optionnels absents :<br/>installation proposée"]
  OPT --> TUI(["Accueil"])
  OPT -.-> XS["Fonctions fermées<br/>voir la liste ci-dessous"]
  class CFG,T,T2 test
  class STOP err
  class XS off
""",
      ["Fonctions fermées par un outil absent — dovi_tool ou mkvmerge : ni STRIP_DV ni ENCODE_DV · mkvmerge : ni mux ni greffe étirée · ffmpeg à libplacebo : profil 5 en SKIP, pas d'agrandissement · seconv : pas d'OCR · ffmpeg DVD : titres de DVD non lus.",
       "Ordre de recherche : PATH système, puis le dossier ./bin de l'installation.",
       "Au lancement, les encodeurs matériels sont aussi sondés (hevc_nvenc en 10 bits, par exemple) : le résultat conditionne la chaîne tout-carte et la sortie HEVC SDR en 10 bits (chapitre 9)."],
      "core/preflight.py · main.py · decision.set_strip_dv_available")

# ── 3. Entrée et analyse ──────────────────────────────────────────────────────
piece("Entrée et analyse", "3.1", "port",
      "Six filtres écartent ce qui n'est pas une source avant toute analyse",
      "Du fichier présent dans le dossier à une source lisible par ffprobe",
      """
flowchart TD
  F(["Fichier du dossier"]) --> EXT{"Extension vidéo reconnue ?"}
  EXT -->|non| IGN["Non listé"]
  EXT -->|oui| INT{"Intermédiaire<br/>nom.iris_étape ?"}
  INT -->|oui| GR1["Grisé, hors sélection<br/>visible pour suppression"]
  INT -->|non| OUT{"Nom finit par -iris ?<br/>sauf .mux-iris, .join-iris"}
  OUT -->|oui| GR2["Sortie d'IRIS : grisée<br/>hors scan récursif<br/>recochable à la main"]
  OUT -->|non| DISC{"Disque ?<br/>ISO, BDMV, VIDEO_TS"}
  DISC -->|oui| TIT["Titres Blu-ray ou DVD :<br/>chaque titre = une source"]
  DISC -->|non| PROBE
  TIT --> PROBE{"ffprobe lit<br/>le fichier ?"}
  PROBE -->|non| ILL["Illisible<br/>cause affichée"]
  PROBE -->|oui| VS{"Flux vidéo<br/>présent ?"}
  VS -->|non| ILL2["Illisible :<br/>no video stream"]
  VS -->|oui| OKS(["Source à analyser<br/>pièce 3.2"])
  class EXT,INT,OUT,DISC,PROBE,VS test
  class ILL,ILL2 err
  class IGN,GR1,GR2 off
  class OKS ok
""",
      ["Extensions reconnues : mp4, mkv, avi, mov, wmv, flv, webm, m4v, 3gp, ts, m2ts, mts, mpg, mpeg, vob.",
       ".mux-iris et .join-iris restent des entrées : une greffe ou un collage existent pour être encodés ensuite."],
      "core/scanner.py (SUPPORTED_EXTENSIONS, est_intermediaire, deja_produit) · core/bluray.py · core/dvd.py")

piece("Entrée et analyse", "3.2", "port",
      "Le débit retenu est celui de la vidéo seule, jamais celui du conteneur",
      "Enrichissements du VideoInfo : codec caché, débit, langues, sous-titres illisibles, HDR",
      """
flowchart TD
  S(["Source lisible"]) --> RAW{"rawvideo à<br/>fourcc nul ?"}
  RAW -->|oui| ANB["1er paquet Annex B<br/>→ HEVC ou H.264 imposé"]
  RAW -->|non| BR
  ANB --> BR["Débit de la VIDÉO seule<br/>1 · bit_rate du flux<br/>2 · tag BPS si ≤ conteneur<br/>3 · conteneur − autres pistes"]
  BR --> LG{"m2ts sans langue<br/>sur une piste ?"}
  LG -->|oui| MKJ["Langues lues par<br/>mkvmerge -J"]
  LG -->|non| WV
  MKJ --> WV{"Sous-titre<br/>codec unknown ?"}
  WV -->|en-tête WEBVTT| WV2["WebVTT brut<br/>refait en SRT"]
  WV -->|non| HDR
  WV2 --> HDR(["HDR10 lu dans les SEI<br/>profil Dolby Vision relevé<br/>→ pièce 3.3"])
  class RAW,LG,WV test
  class HDR ok
""",
      ["Le débit comparé à la cible exclut l'audio et les sous-titres : 9 611 kb/s de conteneur pour 5 364 kb/s de vidéo, mesuré sur un film avec TrueHD.",
       "Un tag BPS qui dépasse le débit du conteneur est périmé (recopié par ffmpeg sans recalcul) et écarté.",
       "Une piste dont le débit reste introuvable ne retire rien : le résultat penche vers le réencodage."],
      "core/scanner.py (_video_bitrate, _codec_annexe_b, _completer_langues, _reconnaitre_webvtt_brut, _hdr10_metadata)")

piece("Entrée et analyse", "3.3", "port",
      "Les sources SD sont mesurées : proportion d'image et entrelacement",
      "Estimation du SAR des DVD convertis, puis analyse de l'entrelacement",
      """
flowchart TD
  S(["VideoInfo<br/>pièce 3.2"]) --> SAR{"720/704 × 480/576<br/>sans SAR ou SAR 1:1<br/>hors titre de disque ?"}
  SAR -->|oui| M1{"SAR dans les<br/>métadonnées ?"}
  M1 -->|oui| MOK["Pas de doute"]
  M1 -->|non| M2["Format d'origine du film<br/>Wikidata P2061<br/>puis image utile, cropdetect"]
  M2 --> M3{"Une seule hypothèse à 5 %<br/>du format du film<br/>ou d'un format standard ?"}
  M3 -->|oui| M4["4:3 ou 16:9 probable<br/>→ sar_impose"]
  M3 -->|non| M5["Indéterminée<br/>4:3 par défaut"]
  SAR -->|non| ENT
  MOK --> ENT
  M4 --> ENT
  M5 --> ENT{"≤ 576 lignes à 25 ou 29,97 i/s<br/>ou déclaré entrelacé ?"}
  ENT -->|non| VI
  ENT -->|oui| I1{"idet : images en<br/>peigne sous 10 % ?"}
  I1 -->|oui| PR["PROGRESSIF"]
  I1 -->|non| I2{"Après fieldmatch :<br/>peigne ≤ 15 % ?"}
  I2 -->|oui| TC["TELECINE"]
  I2 -->|non| EN["ENTRELACE"]
  PR & TC & EN --> VI(["VideoInfo prêt"])
  class SAR,M1,M3,ENT,I1,I2 test
  class VI ok
""",
      ["Tant que l'utilisateur n'a pas confirmé le SAR estimé (touche P, annexe A), l'accueil signale la source par ⚠.",
       "L'analyse d'entrelacement tourne en arrière-plan, 6 passages de 10 s, et reste en cache dans data/analyses.json ; les écrans qui en ont besoin l'attendent.",
       "Une source qui se déclare progressive mais mesurée entrelacée reçoit tout de même un filtre (chapitre 9)."],
      "core/scanner.py (_estimer_sar, analyser_entrelacement) · core/sar.py · core/entrelacement.py · core/analyses.py")

# ── 4. Décision vidéo ─────────────────────────────────────────────────────────
piece("Décision vidéo", "4.1", "port",
      "La super-résolution ne s'applique qu'aux petites sources SDR, sans repli sur une interpolation",
      "Premier temps de decide_video : agrandissement demandé, palier atteint, refus",
      """
flowchart TD
  S(["decide_video"]) --> UP{"Agrandissement demandé ?<br/>clé upscale ou touche U"}
  UP -->|non| CL(["Décision classique<br/>pièce 4.2"])
  UP -->|oui| K4{"Source 4K ?<br/>côtés ≥ 3200 ou ≥ 1700"}
  K4 -->|oui| CL
  K4 -->|non| PAL{"palier_cible<br/>largeur affichée"}
  PAL -->|touche le cadre 1080p| CL
  PAL -->|facteur sous 1,2<br/>ou au-delà de 2,7| CLN(["Classique<br/>définition d'origine"])
  PAL -->|agrandir| REF{"Refus ?<br/>source HDR · pas de libplacebo<br/>shader absent · Vulkan KO"}
  REF -->|oui| CLR(["Classique + raison<br/>pas d'agrandissement"])
  REF -->|non| UPS(["HEVC, ou H.264 sous 1080p<br/>débit du palier atteint<br/>480p, 720p ou 1080p<br/>1 ou 2 passes"])
  class UP,K4,PAL,REF test
  class UPS enc
""",
      ["Aucun profil livré n'active l'agrandissement : il se demande par la clé de profil upscale ou par fichier dans l'Aperçu.",
       "Les facteurs 1,2 (zone morte) et 2,7 (plafond) se règlent dans la section [decision] de config.toml."],
      "core/decision.py:1097 decide_video · :1067 _refus_agrandissement · core/super_resolution.py")

piece("Décision vidéo", "4.2", "port",
      "Le cadre de sortie et le sort du Dolby Vision sont fixés avant d'examiner les cas",
      "Début de la décision classique : cadre, tranche de débit, action de base, Dolby Vision",
      """
flowchart TD
  S(["Décision classique"]) --> LIM{"Cadre et tranche<br/>_resolve_limits"}
  LIM -->|4K + keep_4k| L1["Natif · tranche 2160"]
  LIM -->|4K| L2["1920×1080 · tranche 1080"]
  LIM -->|presque 1080p| L3["Natif · tranche 1080"]
  LIM -->|reste| L4["1280×720 · tranche 720"]
  L1 & L2 & L3 & L4 --> DV{"Dolby Vision ?"}
  DV -->|non| DVN["dv_action NONE"]
  DV -->|oui| DVA["Profil : dv, hdr10 ou sdr<br/>défaut sdr"]
  DVN & DVA --> P5{"Profil 5 vers HDR10/SDR<br/>sans libplacebo ?"}
  P5 -->|oui| SK1(["SKIP<br/>outil DV manquant"])
  P5 -->|non| ACT["Action de base<br/>tranche sous 1080 et non HDR → H.264<br/>sinon HEVC"]
  ACT --> KDV{"dv_action DV<br/>et HEVC ?"}
  KDV -->|non| NEXT(["Cas 1 à 3<br/>pièce 4.3"])
  KDV -->|oui| RDV{"peut_reencoder_en_dv ?<br/>base HDR10 (8.1 ou 7)<br/>même définition<br/>dovi_tool + mkvmerge"}
  RDV -->|oui| EDV["ENCODE_DV<br/>RPU extrait puis réinjecté"]
  RDV -->|non| CPY["Vidéo recopiée<br/>débit et cadre sans effet"]
  EDV --> NEXT
  CPY --> NEXT
  class LIM,DV,P5,KDV,RDV test
  class ACT enc
  class EDV,CPY,DVA dv
  class SK1 off
""",
      ["Une source est 4K dès que son grand côté atteint 3 200 px ou son petit côté 1 700 px (un scope 3832×1600 compris).",
       "Une source verticale est jugée sur son grand et son petit côté ; le cadre se pose dans son orientation.",
       "Aucune sortie HDR n'est confiée à H.264 : la décision automatique garde une source HDR en HEVC."],
      "core/decision.py:1154 _decide_video_classique · :964 _resolve_limits · :1082 _decide_dv · :124 peut_reencoder_en_dv")

piece("Décision vidéo", "4.3", "port",
      "Le premier cas qui répond l'emporte ; le SKIP n'intervient qu'en dernier",
      "Fin de la décision classique : cas 1 à 3, retrait du RPU, SKIP",
      """
flowchart TD
  S(["Action et cadre<br/>pièce 4.2"]) --> C1B{"CAS 1 bis<br/>débit inconnu ?"}
  C1B -->|oui| R1B(["Réencodage<br/>au débit cible"])
  C1B -->|non| C1{"CAS 1<br/>débit au-dessus de<br/>la cible + 10 % ?"}
  C1 -->|oui| R1(["Réencodage<br/>au débit cible"])
  C1 -->|non| C1T{"CAS 1 ter<br/>profil convert_h264<br/>H.264 ≥ h264_min_kbps<br/>sortie HEVC ?"}
  C1T -->|oui| R1T(["HEVC à 70 % du débit<br/>source, plafonné à la cible"])
  C1T -->|non| C2{"CAS 2<br/>au-delà du cadre ?"}
  C2 -->|oui| R2(["Réduction<br/>débit source gardé"])
  C2 -->|non| C3{"CAS 3<br/>codec ni h264 ni hevc ?"}
  C3 -->|oui| R3(["Réencodage<br/>débit source gardé"])
  C3 -->|non| ST{"dv_action HDR10<br/>RPU retirable (8.1 ou 7)<br/>dovi_tool + mkvmerge ?"}
  ST -->|oui| RST(["STRIP_DV<br/>RPU retiré, image intacte"])
  ST -->|non| SKIP(["SKIP<br/>débit, définition<br/>et codec conviennent"])
  class C1B,C1,C1T,C2,C3,ST test
  class R1B,R1,R1T,R2,R3 enc
  class RST dv
  class SKIP off
""",
      ["La tolérance de 10 % ne joue que vers le haut : une source sous la cible n'est jamais réencodée pour son débit.",
       "Le cas 3 vaut quelle que soit la définition : VP9, AV1, VC-1, MPEG-2 ou DivX sont réencodés.",
       "Les cas 1 à 3 l'emportent sur le retrait du RPU : un réencodage le supprime déjà.",
       "Un SKIP peut encore devenir REMUX au chapitre 6."],
      "core/decision.py:1221-1321 · TOLERANCE_DEBIT_PCT · cible_conversion_h264 · CODECS_LISIBLES")

# ── 5. Audio ──────────────────────────────────────────────────────────────────
piece("Décision audio", "5.1", "port",
      "Une piste audio est gardée si elle est l'originale, de langue voulue ou de langue inconnue",
      "Sélection des pistes audio de la source, dans l'ordre d'évaluation",
      """
flowchart TD
  P(["Piste audio"]) --> U{"Codec unknown ?<br/>sans décodeur"}
  U -->|oui| EX1(["Exclue,<br/>même cochée"])
  U -->|non| MAN{"Sélection<br/>manuelle ?"}
  MAN -->|oui| M2{"Cochée ?"}
  M2 -->|oui| KEEP
  M2 -->|non| EX2(["Exclue"])
  MAN -->|non| PAIR{"Paire HD + cœur<br/>même PID ?"}
  PAIR -->|HD sans<br/>preserve_hd_audio| EX3(["Exclue<br/>au profit du cœur"])
  PAIR -->|cœur avec<br/>preserve_hd_audio| EX4(["Exclue<br/>la HD la porte"])
  PAIR -->|sinon| ORI{"Piste originale ?<br/>index 0 ou son cœur"}
  ORI -->|oui| KEEP
  ORI -->|non| LNG{"Langue<br/>déclarée ?"}
  LNG -->|non| KEEP
  LNG -->|oui| LW{"Dans<br/>audio_languages ?"}
  LW -->|oui| KEEP(["Retenue<br/>pièce 5.2"])
  LW -->|non| EX5(["Exclue<br/>langue non voulue"])
  class U,MAN,M2,PAIR,ORI,LNG,LW test
  class KEEP ok
  class EX1,EX2,EX3,EX4,EX5 off
""",
      ["Une TrueHD et son cœur AC-3 de Blu-ray apparaissent en deux pistes de même PID ; la règle automatique n'en garde qu'une.",
       "Les codes « fre » et « fra » désignent la même langue (normalize_language).",
       "Si la piste 0 est illisible, le rôle de piste originale passe à la première piste lisible."],
      "core/decision.py:1460 decide_audio · :1672 _paires_coeur")

piece("Décision audio", "5.2", "port",
      "Les pistes compatibles sont recopiées ; les autres sont transcodées selon leurs canaux",
      "Recopie ou transcodage d'une piste retenue — même règle pour une piste greffée",
      """
flowchart TD
  K(["Piste retenue"]) --> LL{"Sans perte ?<br/>TrueHD, MLP, DTS-HD MA,<br/>FLAC, PCM"}
  LL -->|oui| PH{"preserve_hd_audio ?"}
  PH -->|oui| CP1(["COPY"])
  PH -->|non| TR
  LL -->|non| CC{"AAC, AC3 ou E-AC3<br/>et audio_copy_compatible ?"}
  CC -->|oui| CP2(["COPY"])
  CC -->|non| TR{"audio_hd_codec ac3/eac3<br/>source TrueHD ou DTS<br/>débit lisible ?"}
  TR -->|oui| HD(["Au débit source<br/>plafond AC3 640k<br/>E-AC3 1 024k"])
  TR -->|non| CH{"Canaux ?"}
  CH -->|1| A1(["AAC 64k"])
  CH -->|2| A2(["AAC<br/>audio_stereo_kbps"])
  CH -->|3 à 6| A6(["AC3 ou E-AC3<br/>audio_surround_kbps"])
  CH -->|7 et +| A8(["AC3 ou E-AC3<br/>surround_7_1_kbps<br/>replié en 5.1"])
  class LL,PH,CC,TR,CH test
  class HD,A1,A2,A6,A8 enc
  class CP1,CP2 ok
""",
      ["Le multicanal sort en E-AC3 quand le profil fixe audio_hd_codec = eac3, en AC3 sinon.",
       "Une piste transcodée voit son titre corrigé (codec, disposition, mention Atmos retirée) ; une piste recopiée n'est jamais retitrée."],
      "core/decision.py:1594 decide_codec_audio · :1432 _transcode_spec · :1643 audio_greffee")

piece("Décision audio", "5.3", "port",
      "Une piste qui ne sort pas en AAC est précédée d'un AAC stéréo, lu par défaut",
      "Piste AAC de secours (audio_aac_fallback), posée sur les pistes retenues après 5.2",
      """
flowchart TD
  G(["Piste retenue<br/>et sa décision 5.2"]) --> K{"audio_aac_fallback ?"}
  K -->|non| N1(["Pas de secours<br/>drapeaux de la source"])
  K -->|oui| C{"Sort en AAC ?<br/>recopiée ou transcodée"}
  C -->|oui| N2(["Pas de secours"])
  C -->|non| L{"Une piste retenue<br/>de même langue<br/>sort en AAC ?"}
  L -->|oui| N2
  L -->|non| S(["AAC stéréo écrit<br/>avant la piste<br/>audio_stereo_kbps<br/>64k si mono"])
  S --> D(["Drapeau par défaut<br/>sur la première<br/>piste écrite seule"])
  class K,C,L test
  class S enc
  class D ok
  class N1,N2 off
""",
      ["Ordre écrit, exemple : AAC fre (par défaut), E-AC3 fre, AAC eng, E-AC3 eng. Le client web de Jellyfin sous Chrome ne lit pas l'E-AC3 et ne choisit pas seul une autre piste.",
       "Le secours lit la même piste source ; son titre est corrigé (« FR E-AC3 5.1 Atmos » → « FR AAC 2.0 »).",
       "Une piste audio externe marquée par défaut garde la priorité. Les pistes greffées ne reçoivent pas de secours.",
       "Clé absente d'un profil : pas de secours. Les profils livrés l'activent."],
      "core/decision.py:1559 _poser_secours_aac · :1537 sorties_audio · core/encoder.py:713 drapeaux_secours")

# ── 6. Sous-titres, remux, conteneur ──────────────────────────────────────────
piece("Sous-titres, remux et conteneur", "6.1", "port",
      "Les sous-titres image doublés sont écartés, les autres convertis en texte quand c'est possible",
      "Sélection des sous-titres, puis conversion par OCR ou depuis l'ASS",
      """
flowchart TD
  S(["Sous-titres"]) --> MAN{"Sélection<br/>manuelle ?"}
  MAN -->|oui| KEEP
  MAN -->|non| TT{"Télétexte ?"}
  TT -->|oui| X1(["Écarté<br/>non transportable"])
  TT -->|non| LG{"subtitle_languages<br/>défini ?"}
  LG -->|oui| LG2{"Langue inconnue<br/>ou voulue ?"}
  LG2 -->|non| X2(["Écarté"])
  LG2 -->|oui| DBL
  LG -->|non| DBL{"Image doublée par un texte<br/>même langue, même nature ?"}
  DBL -->|oui| X3(["PGS écarté"])
  DBL -->|non| KEEP["Retenu"]
  KEEP --> OCR{"PGS ou VobSub fr/en<br/>seconv présent<br/>hors disque et DV ?"}
  OCR -->|oui| OCR2(["SRT par OCR<br/>repli : PGS gardé"])
  OCR -->|non| ASS{"ASS/SSA et ass_to_srt<br/>hors panneaux, chansons<br/>hors disque et DV ?"}
  ASS -->|oui| ASS2(["SRT converti<br/>repli : ASS gardé"])
  ASS -->|non| KEEP2(["Gardé tel quel"])
  class MAN,TT,LG,LG2,DBL,OCR,ASS test
  class OCR2,ASS2,KEEP2 ok
  class X1,X2,X3 off
""",
      ["Nature : un SRT forcé ne double qu'un PGS forcé, un SRT complet qu'un PGS complet. Sans langue déclarée, un PGS n'est jamais dit doublé.",
       "« Hors DV » : ni STRIP_DV ni ENCODE_DV, chemins qui écrivent la sortie sans build_command."],
      "core/decision.py:1974 decide_subtitles · :2027 _pgs_doubles · :2003 ocr_prevu · :2015 ass_converti · core/ocr.py · core/ass.py")

piece("Sous-titres, remux et conteneur", "6.2", "port",
      "Un SKIP devient REMUX dès qu'une piste ferait transcoder la chaîne de lecture",
      "Ajustement SKIP ⇄ REMUX après les décisions audio et sous-titres",
      """
flowchart TD
  V(["Action vidéo"]) --> SR{"SKIP ou<br/>REMUX ?"}
  SR -->|non| END(["Inchangée"])
  SR -->|oui| TD{"Titre de disque<br/>Dolby Vision ?"}
  TD -->|oui| NOM["Aucun motif"]
  TD -->|non| MOT["Motifs de remux :<br/>audio retenu à transcoder<br/>secours AAC à ajouter<br/>PGS doublé laissé de côté<br/>PGS ou VobSub à l'OCR<br/>ASS converti · SAR imposé"]
  MOT --> M1{"Au moins<br/>un motif ?"}
  NOM --> M1
  M1 -->|oui, SKIP| RX(["REMUX<br/>vidéo recopiée<br/>suffixe .remux-iris"])
  M1 -->|non, REMUX| RD(["Décision vidéo<br/>refaite"])
  M1 -->|sinon| END
  class SR,TD,M1 test
  class RX ok
  class END off
""",
      ["Une piste écartée pour sa langue ne déclenche rien : le lecteur ne la choisit pas.",
       "Rappelé par chaque écran qui change les pistes (Pistes, Assistant, Aperçu)."],
      "core/decision.py:2071 motifs_remux · :2100 ajuster_remux")

piece("Sous-titres, remux et conteneur", "6.3", "port",
      "Le MP4 est retenu quand tout y tient ; il cède au MKV plutôt que de perdre une piste",
      "Choix du conteneur de sortie (needs_mkv)",
      """
flowchart TD
  S(["Pistes finales"]) --> CT{"container = mkv ?"}
  CT -->|oui| MKV(["MKV"])
  CT -->|non| D7{"STRIP_DV<br/>d'un profil 7 ?"}
  D7 -->|oui| MKV
  D7 -->|non| AU{"Audio sans perte recopié<br/>ou greffe MKV seulement ?"}
  AU -->|oui| MKV
  AU -->|non| M4{"container = mp4 ?"}
  M4 -->|oui| M4B{"Sous-titres hors MP4<br/>tous doublés<br/>par un texte ?"}
  M4B -->|oui| M4C["Ils sont écartés"]
  M4B -->|non| IMG
  M4C --> IMG
  M4 -->|non, auto| IMG{"Reste un sous-titre<br/>image ou ASS/SSA ?"}
  IMG -->|oui| MKV
  IMG -->|non| MP4(["MP4<br/>HEVC en hvc1<br/>SRT en mov_text"])
  class CT,D7,AU,M4,M4B,IMG test
  class MKV,MP4 ok
""",
      ["Un mux sans réencodage (SKIP + pistes greffées) sort toujours en .mux-iris.mkv, seul format de mkvmerge.",
       "En sortie MKV, un mov_text de la source est converti en SRT : le muxeur Matroska de ffmpeg le refuse."],
      "core/decision.py:628 needs_mkv · :598 sous_titres_ecartes · :580 _mkv_impose_par_l_audio")

# ── 7. Nommage ────────────────────────────────────────────────────────────────
piece("Nom de sortie", "7.1", "port",
      "Le nom de sortie retire d'abord ce que la source annonçait et que la sortie n'aura plus",
      "Premières réécritures du nom : marque précédente, groupe de release, définition, codec",
      """
flowchart TD
  N(["Nom de la source"]) --> A["Ancienne marque -iris<br/>et compteur (n) retirés"]
  A --> B{"Dernier terme après tiret<br/>= groupe de release ?"}
  B -->|oui| B2["Groupe retiré"]
  B -->|non| C
  B2 --> C{"Définition<br/>abaissée ?"}
  C -->|oui| C2["2160p, 4K, UHD → 1080p"]
  C -->|non| D
  C2 --> D{"Réencodage HEVC, H264, AV1<br/>sans vidéo recopiée ?"}
  D -->|oui| D2["Marques x264, x265,<br/>HEVC, AV1 retirées"]
  D -->|non| NX
  D2 --> NX(["Suite<br/>pièce 7.2"])
  class B,C,D test
  class NX ok
""",
      ["Groupe de release : un mot seul, qui n'est pas une marque, derrière un nom qui porte au moins une marque de release (définition, codec, HDR, audio, source).",
       "Les marques sont prises comme mots entiers : le 4K de H4K et le 2160 de 3840x2160 ne sont pas touchés.",
       "keep_4k et la vidéo recopiée laissent la marque de définition en place : la définition ne baisse pas."],
      "core/scanner.py (stem_sans_suffixe_produit, stem_sans_groupe, stem_resolution_ramenee, stem_sans_marque_codec)")

piece("Nom de sortie", "7.2", "port",
      "Le nom de sortie dit ce que contient le fichier produit, jamais ce qu'annonçait la source",
      "Dernières réécritures : HDR, audio, agrandissement, puis suffixe et numérotation",
      """
flowchart TD
  S(["Nom réécrit<br/>pièce 7.1"]) --> E{"dv_action ?"}
  E -->|HDR10| E1["DV, DoVi, HDR → HDR10"]
  E -->|SDR| E2["Marques HDR retirées<br/>10bit si sortie 8 bits"]
  E -->|DV ou aucun| F
  E1 --> F
  E2 --> F{"Audio<br/>transcodé ?"}
  F -->|oui| F2["TrueHD, DTS → AC3, E-AC3<br/>7.1 → 5.1, Atmos retiré"]
  F -->|non| G
  F2 --> G{"Super-<br/>résolution ?"}
  G -->|oui| G2["720p → 1080p.upscaled"]
  G -->|non| H
  G2 --> H["Suffixe sans redite :<br/>.hevc-iris .h264-iris .av1-iris<br/>.dv-iris .hdr10-iris .remux-iris"]
  H --> J{"Collision ?<br/>source, disque ou lot"}
  J -->|oui| J2["Numérotation<br/>nom.hevc-iris(2)"]
  J -->|non| K(["Nom figé<br/>à la mise en file"])
  J2 --> K
  class E,F,G,J test
  class K ok
""",
      ["Exemple : Film.2160p.DV.HDR10.x265.TrueHD.7.1-GROUP devient Film.1080p.HDR10.E-AC3.5.1.hevc-iris.",
       "Le nom n'est jamais relu sur le disque après coup : figé une fois, il sert aussi à effacer une sortie partielle sans risque."],
      "core/decision.py:705 _stem_a_jour · :418 suffixe_sans_redite · :1695 resoudre_sorties · core/scanner.py (stem_*)")

# ── 8. Exécution ──────────────────────────────────────────────────────────────
piece("Exécution", "8.1", "port",
      "L'exécution aiguille chaque fichier vers mkvmerge, les chemins Dolby Vision ou ffmpeg",
      "Premier temps de _encoder_suivant : aiguillage selon l'action et la nature de la source",
      """
flowchart TD
  Q(["Fichier suivant"]) --> SK{"SKIP sans<br/>piste greffée ?"}
  SK -->|oui| SKD(["Ignoré"])
  SK -->|non| MX{"SKIP + greffes<br/>hors titre de disque ?"}
  MX -->|oui| MUX(["Mux mkvmerge<br/>.mux-iris.mkv"])
  MX -->|non| TI{"Titre de disque<br/>à extraire ?"}
  TI -->|oui| TDV{"STRIP_DV ou<br/>ENCODE_DV ?"}
  TDV -->|oui| TERR(["Erreur<br/>DV d'un clip seul"])
  TDV -->|non| TEX{"Extraction MKV<br/>réussie ?"}
  TEX -->|non| FAIL1(["Échec"])
  TEX -->|oui| SDV
  TI -->|non| SDV{"STRIP_DV ?"}
  SDV -->|oui| STRIP(["Retrait du RPU<br/>pièce 8.4"])
  SDV -->|non| EDV{"ENCODE_DV ?"}
  EDV -->|oui| EDV2(["Réencodage DV<br/>pièce 8.4"])
  EDV -->|non| FF(["Chemin ffmpeg<br/>pièce 8.2"])
  class SK,MX,TI,TDV,TEX,SDV,EDV test
  class MUX ok
  class STRIP,EDV2 dv
  class TERR,FAIL1 err
  class SKD off
  class FF enc
""",
      ["Avant le lot, les sorties qui iraient dans un dossier en lecture seule sont signalées (sorties_bloquees), et les noms figés (resoudre_sorties).",
       "Une exception imprévue met le fichier en échec, libère ses intermédiaires et laisse le lot continuer."],
      "tui/screens/run.py:640 _encoder_suivant · :66 _a_muxer · :2054 _remux_titre · :2125 _extraire_dvd")

piece("Exécution", "8.2", "port",
      "Avant ffmpeg, quatre préparations contournent des défauts mesurés des outils",
      "Chemin ffmpeg, premier temps : mux préalable, passe audio, porteur, sous-titres refaits",
      """
flowchart TD
  S(["Chemin ffmpeg"]) --> PM{"Greffe<br/>étirée ?"}
  PM -->|oui| PM2{"Mux préalable<br/>mkvmerge réussi ?"}
  PM2 -->|non| F1(["Échec"])
  PM2 -->|oui| AP
  PM -->|non| AP{"Audio sans perte transcodé<br/>+ sous-titre tardif ?"}
  AP -->|oui| AP2["Passe audio séparée"]
  AP -->|non| PO
  AP2 --> PO{"MP4 et texte à silence<br/>de plus de 1 800 s<br/>ou WebVTT brut ?"}
  PO -->|oui| PO2["Porteur Matroska"]
  PO -->|non| RF
  PO2 --> RF["Sous-titres refaits<br/>WebVTT → SRT, OCR, ASS → SRT"]
  RF --> SS{"S ou X<br/>pendant l'OCR ?"}
  SS -->|oui| SK(["Arrêté"])
  SS -->|non| BC(["Commande<br/>pièce 8.3"])
  class PM,PM2,AP,PO,SS test
  class AP2,PO2,RF ok
  class BC enc
  class F1 err
  class SK off
""",
      ["Mux préalable : ffmpeg ne sait pas étirer une piste greffée ; mkvmerge la greffe dans un intermédiaire, que ffmpeg encode ensuite.",
       "Passe audio séparée : une même invocation qui décode un audio sans perte et mappe un sous-titre au premier repère tardif perdait la piste, code de retour nul.",
       "Porteur Matroska : le muxeur MP4 de ffmpeg écrase les temps d'un sous-titre texte après un silence de plus de 2³¹ µs."],
      "tui/screens/run.py:718-749 · :2177 _premux · :963 _audio_prepass · :1054 _porter_sous_titres · :1205 _sous_titres_refaits")

piece("Exécution", "8.3", "port",
      "Une chaîne tout-carte qui bute en cours de fichier est relancée une fois au processeur",
      "Chemin ffmpeg, second temps : commande, lancement, relance hors puce",
      """
flowchart TD
  S(["Préparations faites<br/>pièce 8.2"]) --> BC["Chapitres écrits<br/>build_command · chapitre 9"]
  BC --> VE{"Commande<br/>refusée ?"}
  VE -->|oui| F2(["Erreur"])
  VE -->|non| RUN["ffmpeg lancé"]
  RUN --> RC{"Code 0 ?"}
  RC -->|non| HP{"Tout-carte en échec<br/>au raccord, 1re fois ?"}
  HP -->|oui| RUN2["Relance avec filtres<br/>au processeur"]
  RUN2 --> RC
  HP -->|non| CTL(["Contrôle<br/>chapitre 10"])
  RC -->|oui| CTL
  class VE,RC,HP test
  class RUN,RUN2,BC enc
  class F2 err
""",
      ["« Commande refusée » : sortie identique à la source, ou encodeur que le sondage du lancement a déjà refusé (la cause du sondage est affichée au lieu de l'erreur ffmpeg).",
       "Relance hors puce : un fichier fait de deux encodages collés change de paramètres en route ; les filtres sur la carte ne savent pas se reconstruire (« Error reinitializing filters »).",
       "Pas de relance si le fichier a été passé (S) ou le lot arrêté."],
      "tui/screens/run.py:751-833 · core/encoder.py relancer_hors_puce")

piece("Exécution", "8.4", "land",
      "Les chemins Dolby Vision passent par dovi_tool et mkvmerge plutôt que par build_command",
      "Étapes du retrait du RPU (STRIP_DV) et du réencodage préservant le Dolby Vision (ENCODE_DV)",
      """
flowchart TB
  subgraph STR["STRIP_DV · retrait du RPU sans réencodage"]
    direction LR
    S0{"Sortie ?"} -->|MKV| S1["ffmpeg<br/>flux HEVC brut"]
    S1 --> S2["dovi_tool<br/>remove"]
    S2 --> S3["ffmpeg<br/>pistes audio<br/>si transcodé ou secours"]
    S3 --> S4(["mkvmerge<br/>.hdr10-iris.mkv"])
    S0 -->|MP4 sans greffe| S5(["ffmpeg -bsf dovi_rpu strip<br/>.hdr10-iris.mp4"])
    S0 -->|MP4 avec greffes| S6["Chemin MKV"] --> S7(["Remux MP4<br/>build_dv_mp4_remux"])
  end
  subgraph ENC["ENCODE_DV · réencodage, RPU réinjecté"]
    direction LR
    E1["1 · RPU<br/>extrait"] --> E2["2 · profil 7<br/>→ 8.1"]
    E2 --> E3["3 · vidéo<br/>encodée Annex B"]
    E3 --> E4["4 · RPU<br/>réinjecté"]
    E4 --> E5["5 · audio à part<br/>si transcodé ou secours"]
    E5 --> E6["6 · mkvmerge<br/>.dv-iris.mkv"]
    E6 --> E7(["7 · remux MP4<br/>si sortie MP4"])
  end
  STR ~~~ ENC
  class S0 test
  class S4,S5,S7,E7 dv
""",
      ["Le retrait du RPU laisse l'image intacte bit à bit et conserve un éventuel HDR10+.",
       "Un profil 7 en STRIP_DV sort toujours en MKV : seul dovi_tool remove retire sa couche d'amélioration.",
       "ENCODE_DV exige une base HDR10 et une définition inchangée : le RPU décrit un cadrage image par image."],
      "tui/screens/run.py:1421 _strip_dv · :1702 _encode_dv · core/dovi.py")

# ── 9. Commande ffmpeg ────────────────────────────────────────────────────────
piece("Commande ffmpeg", "9", "port",
      "La commande garde les images sur la carte graphique quand la source s'y prête",
      "Construction de build_command : exécutable, décodage, mode vidéo, filtres, réglage du débit",
      """
flowchart TD
  B(["build_command"]) --> N0{"SKIP ou<br/>STRIP_DV ?"}
  N0 -->|oui| E0(["Aucune commande"])
  N0 -->|non| N1{"Sortie identique<br/>à la source ?"}
  N1 -->|oui| E1(["Refus"])
  N1 -->|non| N2{"Exécutable"}
  N2 -->|agrandissement| F1["ffmpeg à libplacebo<br/>+ Vulkan"]
  N2 -->|profil 5 converti| F1
  N2 -->|autres cas| F3["ffmpeg principal"]
  F1 --> HW
  F3 --> HW{"Décodage"}
  HW -->|tout-carte possible| TP["Intel vpp_qsv<br/>NVIDIA scale_cuda"]
  HW -->|hwaccel admis| HA["-hwaccel"]
  HW -->|sinon| HC["Processeur"]
  TP & HA & HC --> VM{"Mode vidéo"}
  VM -->|DV gardé ou REMUX| VC(["-c:v copy"])
  VM -->|hdr10_quality| VQ(["libx265 + métadonnées<br/>maxrate = cible"])
  VM -->|standard| FL["Filtres dans l'ordre :<br/>1 · télécinéma ou bwdif<br/>2 · setsar SAR imposé<br/>3 · pixels carrés<br/>4 · scale au cadre<br/>5 · tone mapping si SDR"]
  FL --> VS(["Encodeur :<br/>NVENC vbr, maxrate 1,5 × cible<br/>libx265 maxrate = cible<br/>10 bits si HDR"])
  class N0,N1,N2,HW,VM test
  class VQ,VS,FL enc
  class VC ok
  class E1 err
  class E0 off
""",
      ["Tout-carte exclu pour : SDR, Dolby Vision, hdr10_quality, désentrelacement, pixels non carrés, dimension impaire, source non décodable par la puce.",
       "-hwaccel exclu pour : SDR (zscale), profil 5, agrandissement, vidéo recopiée, hdr10_quality.",
       "HEVC NVENC sort aussi en 10 bits en SDR si le sondage l'a ouvert ainsi (+0,1 à +0,4 point VMAF mesuré)."],
      "core/encoder.py:1111 build_command · filtre_tout_puce · regle_debit · _hdr10_quality")

# ── 10. Contrôle ──────────────────────────────────────────────────────────────
piece("Contrôle et fin", "10", "port",
      "Le succès se vérifie sur le fichier produit avant toute suppression de la source",
      "Contrôle de la sortie, suppression de la source, nettoyage",
      """
flowchart TD
  R(["Fin du processus"]) --> C0{"Code 0 ?"}
  C0 -->|non| KO
  C0 -->|oui| C1{"Sortie présente,<br/>non vide, de la<br/>durée attendue ?"}
  C1 -->|non| KO
  C1 -->|oui| C2{"Chaque piste audio<br/>≥ 1/10 de la durée ?"}
  C2 -->|non| KO["Échec · sortie partielle<br/>effacée · cause diagnostiquée"]
  C2 -->|oui| OK["Succès · vitesse<br/>mesurée enregistrée"]
  OK --> SKP{"Passé par S<br/>entre-temps ?"}
  SKP -->|oui| KEEPS(["Source gardée"])
  SKP -->|non| DEL{"delete_source ?"}
  DEL -->|non| KEEPS
  DEL -->|oui| DISC{"Titre de<br/>disque ?"}
  DISC -->|oui| KEEPS
  DISC -->|non| RM(["Source supprimée<br/>+ .nfo et images"])
  KO --> LIB
  KEEPS --> LIB
  RM --> LIB["Intermédiaires effacés"]
  LIB --> NX(["Fichier suivant"])
  class C0,C1,C2,SKP,DEL,DISC test
  class OK,RM ok
  class KO err
""",
      ["ffmpeg peut rendre un code nul avec une piste audio amputée : le contrôle relit la sortie.",
       "Les intermédiaires (audio à part, porteur, chapitres, SRT refaits, mux préalable) sont effacés dans tous les cas ; les pistes recalées seulement après un succès."],
      "tui/screens/run.py:833-893 · :915 _supprimer_source · :896 _audio_vide · core/encoder.py:605 defaut_sortie")


# ─── Rendu HTML ───────────────────────────────────────────────────────────────

def e(t):
    return html.escape(t, quote=False)


SYNTHESE = [
    ("Deux outils bloquants",
     "Sans ffmpeg ni ffprobe, l'application s'arrête. Chaque outil optionnel absent (dovi_tool, mkvmerge, ffmpeg à libplacebo, seconv) ferme une branche précise de la décision, avec un message."),
    ("Un débit mesuré sur la vidéo seule",
     "Le débit comparé à la cible exclut l'audio et les sous-titres. Une tolérance de 10 % ne joue que vers le haut : une source sous la cible n'est jamais réencodée pour son débit."),
    ("Un ordre strict des cas vidéo",
     "Débit inconnu, débit trop élevé, H.264 à convertir, définition trop grande, codec non lisible, puis retrait du RPU : le premier cas qui répond l'emporte. Le SKIP vient en dernier."),
    ("Un SKIP n'est pas définitif",
     "Il devient REMUX dès qu'une piste ferait transcoder la chaîne de lecture : audio à convertir, secours AAC à ajouter, sous-titre image doublé ou à l'OCR, ASS converti, SAR à déclarer."),
    ("Aucune piste perdue en silence",
     "Le MP4 est préféré quand tout y tient. Il cède au MKV dès qu'une piste retenue ne pourrait pas y figurer sans être écartée."),
    ("Un succès vérifié, pas supposé",
     "La sortie est relue (présence, durée, pistes audio) avant d'être déclarée réussie et avant toute suppression de la source."),
]

LEGENDE = [
    ("#FFFFFF", "#051C2C", "Test : la question posée par le code"),
    ("#2251FF", "#1A3FCC", "Réencodage de l'image"),
    ("#D3F1FB", "#00A9F4", "Copie, remux ou issue favorable"),
    ("#051C2C", "#051C2C", "Traitement Dolby Vision"),
    ("#EFEFEF", "#9A9A9A", "Rien à faire, écarté ou ignoré"),
    ("#FBE3E3", "#C8102E", "Erreur ou refus"),
    ("#F4F6F9", "#8DA0B3", "Étape de traitement"),
]


def page_piece(p):
    notes = "".join(f"<li>{e(n)}</li>" for n in p["notes"])
    # Tests en hexagone : un losange multiligne prend deux fois la hauteur.
    source_m = re.sub(r'(\b\w+)\{"(.*?)"\}', r'\1{{"\2"}}', p["mermaid"])
    code = e(source_m + "\n" + CLASSES)
    return f"""
<section class="page {p['orient']}">
  <div class="run"><span>IRIS Encode · Arbre de décision</span><span>{e(p['chap'])}</span></div>
  <div class="exhibit">Pièce {e(p['num'])}</div>
  <h2 class="action">{e(p['titre'])}</h2>
  <p class="sub">{e(p['sous_titre'])}</p>
  <div class="fig"><pre class="mermaid">{code}</pre></div>
  {'<ul class="notes">' + notes + '</ul>' if notes else ''}
  <p class="source"><b>Source :</b> code IRIS Encode v{RELEVE} — {e(p['source'])}</p>
</section>"""


def sommaire():
    lignes, vus = [], set()
    for p in PIECES:
        chap = e(p["chap"]) if p["chap"] not in vus else ""
        lignes.append(f"<tr><td class='num'>{e(p['num'])}</td><td>{chap}</td><td>{e(p['titre'])}</td></tr>")
        vus.add(p["chap"])
    return "\n".join(lignes)


def legende():
    return "".join(
        f"<div class='lg'><span class='sw' style='background:{f};border-color:{c}'></span>{e(t)}</div>"
        for f, c, t in LEGENDE)


CSS = """
@page { size: A4 portrait; margin: 14mm 16mm 16mm 16mm;
  @bottom-left { content: "IRIS Encode · Arbre de décision · v__RELEVE__"; font-family: Arial, sans-serif; font-size: 7.5pt; color: #757575; }
  @bottom-right { content: counter(page) " / " counter(pages); font-family: Arial, sans-serif; font-size: 7.5pt; color: #757575; } }
@page land { size: A4 landscape; margin: 12mm 16mm 14mm 16mm; }
@page cover { margin: 0;
  @bottom-left { content: none; } @bottom-right { content: none; } }
:root { --navy:#051C2C; --blue:#2251FF; --cyan:#00A9F4; --grey:#757575; --rule:#D0D0D0; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: #fff; color: var(--navy); font-family: Arial, Helvetica, sans-serif; font-size: 9.5pt; line-height: 1.4; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.page { width: 178mm; height: 266mm; display: flex; flex-direction: column; break-after: page; overflow: hidden; }
.page.land { page: land; width: 265mm; height: 183mm; }
section:last-of-type { break-after: auto; }
.run { display: flex; justify-content: space-between; font-size: 7.5pt; color: var(--grey); text-transform: uppercase; letter-spacing: .06em; border-bottom: 0.5pt solid var(--rule); padding-bottom: 2mm; margin-bottom: 5mm; }
.exhibit { font-size: 8.5pt; font-weight: bold; color: var(--blue); text-transform: uppercase; letter-spacing: .08em; margin-bottom: 1.5mm; }
h1, h2, .action { font-family: Georgia, "Times New Roman", serif; font-weight: normal; color: var(--navy); margin: 0; }
.action { font-size: 17pt; line-height: 1.2; margin-bottom: 1.5mm; }
.sub { margin: 0 0 3mm; color: var(--grey); font-size: 9.5pt; }
.fig { flex: 1 1 auto; min-height: 0; display: flex; align-items: center; justify-content: center; border-top: 1.5pt solid var(--navy); padding-top: 3mm; overflow: hidden; }
.fig pre.mermaid { margin: 0; font-family: Arial, sans-serif; }
.fig svg { display: block; }
.notes { margin: 3mm 0 0; padding: 2.5mm 0 0 4.5mm; border-top: 0.5pt solid var(--rule); font-size: 8.5pt; display: grid; gap: 1mm; }
.notes li::marker { color: var(--blue); }
.source { margin: 2mm 0 0; font-size: 7.5pt; color: var(--grey); }
.source b { color: var(--navy); }
.cover { page: cover; height: 297mm; break-after: page; background: var(--navy); color: #fff; display: flex; flex-direction: column; justify-content: space-between; padding: 26mm 22mm 22mm; position: relative; overflow: hidden; }
.cover .band { position: absolute; right: -40mm; top: 0; width: 110mm; height: 297mm; background: linear-gradient(160deg, #2251FF 0%, #00A9F4 100%); transform: skewX(-14deg); }
.cover .top { position: relative; font-size: 9pt; letter-spacing: .14em; text-transform: uppercase; color: #B9C6D2; }
.cover .mid { position: relative; max-width: 125mm; }
.cover h1 { color: #fff; font-size: 34pt; line-height: 1.08; margin-bottom: 8mm; }
.cover .lead { font-size: 12pt; line-height: 1.45; color: #DCE4EC; }
.cover .bot { position: relative; font-size: 9pt; color: #B9C6D2; display: grid; gap: 1.5mm; max-width: 125mm; }
.cover .bot b { color: #fff; font-weight: normal; }
.text h2.t { font-size: 22pt; margin-bottom: 6mm; }
.text p.lead { font-size: 11pt; max-width: 165mm; margin: 0 0 6mm; }
table.toc { width: 100%; border-collapse: collapse; font-size: 8.8pt; line-height: 1.3; }
table.toc td { padding: 1.2mm 2mm; border-bottom: 0.5pt solid var(--rule); vertical-align: top; }
table.toc td.num { color: var(--blue); font-weight: bold; width: 12mm; }
table.toc td:nth-child(2) { width: 42mm; color: var(--grey); }
.legend { display: grid; grid-template-columns: 1fr 1fr; gap: 2.5mm 8mm; margin: 2mm 0 7mm; font-size: 9pt; }
.lg { display: flex; align-items: center; gap: 3mm; }
.sw { width: 9mm; height: 5.5mm; border: 1.4pt solid; border-radius: 1mm; flex: none; }
.how { display: grid; gap: 2mm; font-size: 9.5pt; max-width: 170mm; margin: 0; padding-left: 4.5mm; }
.keys { display: grid; grid-template-columns: 1fr 1fr; gap: 7mm 10mm; margin-top: 4mm; }
.key { border-top: 2pt solid var(--blue); padding-top: 3mm; }
.key .k { font-size: 8pt; color: var(--blue); font-weight: bold; letter-spacing: .08em; }
.key h3 { font-family: Georgia, serif; font-weight: normal; font-size: 13pt; margin: 1.5mm 0 2mm; }
.key p { margin: 0; font-size: 9.5pt; color: #2B3A47; }
table.man { width: 100%; border-collapse: collapse; font-size: 9pt; margin-top: 2mm; }
table.man th { text-align: left; font-size: 8pt; text-transform: uppercase; letter-spacing: .06em; color: var(--grey); border-bottom: 1.5pt solid var(--navy); padding: 2mm; }
table.man td { padding: 2.2mm 2mm; border-bottom: 0.5pt solid var(--rule); vertical-align: top; }
table.man td:first-child { color: var(--blue); font-weight: bold; white-space: nowrap; }
code { font-family: Consolas, "Courier New", monospace; font-size: .92em; }
"""

JS = r"""
mermaid.initialize({
  startOnLoad: false, securityLevel: 'loose', theme: 'base',
  themeVariables: { fontFamily: 'Arial, Helvetica, sans-serif', fontSize: '15px',
    primaryColor: '#F4F6F9', primaryBorderColor: '#8DA0B3', primaryTextColor: '#051C2C',
    lineColor: '#051C2C', edgeLabelBackground: '#FFFFFF', tertiaryColor: '#FFFFFF',
    clusterBkg: '#F6F8FB', clusterBorder: '#B7C3CF', titleColor: '#051C2C' },
  flowchart: { htmlLabels: true, curve: 'basis', nodeSpacing: 22, rankSpacing: 26,
               padding: 10, useMaxWidth: false, diagramPadding: 4 }
});
window.__fit = [];
(async () => {
  // Pas d'attente de document.fonts.ready : elle attend la fin du chargement,
  // que l'image /attendre retient jusqu'ici. Polices système seulement.
  await mermaid.run({ querySelector: 'pre.mermaid' });
  document.querySelectorAll('.fig').forEach((fig) => {
    const svg = fig.querySelector('svg');
    const vb = svg.viewBox.baseVal;
    const aw = fig.clientWidth, ah = fig.clientHeight - 12;
    const echelle = Math.min(aw / vb.width, ah / vb.height, 1.0);
    svg.style.maxWidth = 'none';
    svg.setAttribute('width', (vb.width * echelle).toFixed(1));
    svg.setAttribute('height', (vb.height * echelle).toFixed(1));
    const num = fig.closest('.page').querySelector('.exhibit').textContent;
    window.__fit.push({ num, echelle: +echelle.toFixed(3), corps_pt: +(15 * echelle * 0.75).toFixed(2), w: Math.round(vb.width), h: Math.round(vb.height) });
  });
  document.body.setAttribute('data-ready', '1');
})().catch((err) => { window.__fit = { erreur: String(err && err.message || err) }; })
  .finally(() => fetch('/pret', { method: 'POST', body: JSON.stringify(window.__fit) }));
"""



def construire_html(date_doc: str) -> str:
    """Le document complet ; l'image /attendre retient le chargement jusqu'au rendu."""
    pieces = "\n".join(page_piece(p) for p in PIECES)
    keys = "".join(f"<div class='key'><div class='k'>{i:02d}</div><h3>{e(t)}</h3><p>{e(x)}</p></div>"
                   for i, (t, x) in enumerate(SYNTHESE, 1))
    doc = f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<title>IRIS Encode — Arbre de décision du traitement d'un fichier vidéo</title>
<style>{CSS.replace("__RELEVE__", RELEVE)}</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
</head><body>
<img src="/attendre" alt="" style="display:none">

<section class="cover">
  <div class="band"></div>
  <div class="top">Document de référence technique · {date_doc}</div>
  <div class="mid">
    <h1>IRIS Encode<br/>Arbre de décision du traitement d'un fichier vidéo</h1>
    <p class="lead">Tous les tests et décisions appliqués à un fichier vidéo quelconque, de son entrée dans l'application jusqu'au fichier produit, relevés dans le code source.</p>
  </div>
  <div class="bot">
    <div><b>Version analysée :</b> IRIS Encode {RELEVE}</div>
    <div><b>Périmètre :</b> lancement, analyse, décisions vidéo, audio, sous-titres, conteneur, nommage, exécution et contrôle</div>
  </div>
</section>

<section class="page text">
  <div class="run"><span>IRIS Encode · Arbre de décision</span><span>Sommaire</span></div>
  <h2 class="t">Sommaire</h2>
  <table class="toc">
    <tr><td class="num">—</td><td>Lecture</td><td>Comment lire les pièces · Synthèse</td></tr>
    {sommaire()}
    <tr><td class="num">A</td><td>Annexe</td><td>Interventions manuelles · Périmètre et méthode</td></tr>
  </table>
</section>

<section class="page text">
  <div class="run"><span>IRIS Encode · Arbre de décision</span><span>Lecture</span></div>
  <h2 class="t">Comment lire les pièces</h2>
  <p class="lead">Chaque pièce représente un fragment de l'arbre de décision, dans l'ordre où le code l'évalue. Son titre énonce ce qu'il faut en retenir ; la ligne de source renvoie aux fonctions concernées.</p>
  <div class="legend">{legende()}</div>
  <ul class="how">
    <li>Les hexagones sont des tests ; l'étiquette d'une flèche donne la réponse qui mène à sa branche.</li>
    <li>Les formes arrondies marquent une issue : une action décidée, un renvoi vers une autre pièce ou un arrêt.</li>
    <li>Les flèches en pointillé (pièce 2) relient un outil absent à la fonction qu'il désactive.</li>
    <li>Les noms en police technique (<code>decide_video</code>, <code>preserve_hd_audio</code>…) sont ceux du code et des clés de profil.</li>
  </ul>
  <h2 class="t" style="margin-top:9mm">Synthèse</h2>
  <div class="keys">{keys}</div>
</section>

{pieces}

<section class="page text">
  <div class="run"><span>IRIS Encode · Arbre de décision</span><span>Annexe</span></div>
  <div class="exhibit">Annexe A</div>
  <h2 class="action">Six gestes manuels modifient l'arbre ; chacun relance la décision</h2>
  <p class="sub">Les réglages explicites sont reposés avant chaque réanalyse (appliquer_reglages)</p>
  <table class="man">
    <tr><th>Écran</th><th>Geste</th><th>Effet sur l'arbre</th></tr>
    <tr><td>Accueil</td><td>Cocher une ligne SKIP</td><td>Forcée en HEVC, ou en H.264 sous la tranche 1080p hors HDR, au débit source (<code>force_skip_to_encode</code>). Une ligne REMUX cochée part en remux.</td></tr>
    <tr><td>Pistes, Assistant</td><td>Cocher ou décocher des pistes</td><td>La sélection manuelle fait foi, sauf codec audio inconnu et télétexte ; l'ajustement SKIP ⇄ REMUX est refait.</td></tr>
    <tr><td>Pistes, Assistant</td><td>Changer le codec ou le débit</td><td><code>choisir_codec</code> ; H.264 sur une source HDR la fait passer en SDR.</td></tr>
    <tr><td>Pistes, Assistant</td><td>P · Proportion</td><td>SAR douteux : 4:3, 16:9 ou tel quel (<code>choisir_sar</code>) ; décision vidéo et nom recalculés.</td></tr>
    <tr><td>Aperçu</td><td>U · Agrandir</td><td>Active ou retire la super-résolution pour ce fichier, en une ou deux passes.</td></tr>
    <tr><td>Pistes</td><td>F9 · Piste externe</td><td>Ajoute une greffe : sur un SKIP, elle donne un mux ; étirée, elle impose un mux préalable.</td></tr>
  </table>
  <h2 class="action" style="margin-top:10mm">Périmètre et méthode</h2>
  <ul class="how" style="margin-top:3mm">
    <li>Relevé sur le code d'IRIS Encode {RELEVE} : <code>core/decision.py</code>, <code>core/encoder.py</code>, <code>core/scanner.py</code>, <code>core/preflight.py</code>, <code>tui/screens/run.py</code>, recoupés avec la spécification <code>iris_encode_spec.md</code>.</li>
    <li>Hors périmètre : la jonction de parties, le téléchargement YouTube, la recherche OpenSubtitles et le recalage d'une piste. Ce sont des préparations de sources, pas des décisions sur le fichier traité.</li>
    <li>Les seuils cités (10 %, 1 800 s, 640k, 1 024k…) sont les valeurs par défaut du code au moment du relevé ; plusieurs se règlent dans le profil ou dans <code>config.toml</code>.</li>
  </ul>
</section>

<script>{JS}</script>
</body></html>"""
    return doc




# ─── Impression ───────────────────────────────────────────────────────────────

def version_du_code() -> str:
    texte = (RACINE / "version.py").read_text(encoding="utf-8")
    trouve = re.search(r'__version__\s*=\s*"([^"]+)"', texte)
    return trouve.group(1) if trouve else "?"


def navigateur() -> str | None:
    """Edge ou Chrome : IRIS_NAVIGATEUR, puis les emplacements usuels, puis le PATH."""
    impose = os.environ.get("IRIS_NAVIGATEUR")
    if impose:
        return impose if Path(impose).is_file() else None
    candidats = [
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    for c in candidats:
        if c.is_file():
            return str(c)
    for nom in ("msedge", "microsoft-edge", "google-chrome", "chromium", "chromium-browser"):
        if shutil.which(nom):
            return shutil.which(nom)
    return None


def imprimer(doc: str, sortie: Path, exe: str, delai_s: int = 180) -> list | dict | None:
    """Sert `doc`, l'imprime en PDF dans `sortie`, rend ce que la page a mesuré."""
    pret = threading.Event()
    rapport: list = []

    with tempfile.TemporaryDirectory(prefix="iris_arbre_") as tmp:
        dossier = Path(tmp)
        (dossier / "doc.html").write_text(doc, encoding="utf-8")

        class Gestionnaire(SimpleHTTPRequestHandler):
            def __init__(self, *a, **k):
                super().__init__(*a, directory=str(dossier), **k)

            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path != "/attendre":
                    return super().do_GET()
                pret.wait(delai_s)
                # GIF transparent de 1×1.
                gif = bytes.fromhex("47494638396101000100800000000000ffffff21f9040100"
                                    "0000002c00000000010001000002024401003b")
                self.send_response(200)
                self.send_header("Content-Type", "image/gif")
                self.send_header("Content-Length", str(len(gif)))
                self.end_headers()
                self.wfile.write(gif)

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                corps = self.rfile.read(n)
                if self.path == "/pret":
                    try:
                        rapport.append(json.loads(corps or b"null"))
                    except ValueError:
                        rapport.append({"erreur": "rapport illisible"})
                    pret.set()
                self.send_response(204)
                self.end_headers()

        serveur = ThreadingHTTPServer(("127.0.0.1", 0), Gestionnaire)
        fil = threading.Thread(target=serveur.serve_forever, daemon=True)
        fil.start()
        try:
            url = f"http://127.0.0.1:{serveur.server_address[1]}/doc.html"
            pdf_tmp = dossier / "doc.pdf"
            # Profil propre à l'outil, réutilisé : le navigateur le garde
            # ouvert un moment après l'impression, il ne peut pas être effacé.
            profil = Path(tempfile.gettempdir()) / "iris_arbre_profil"
            subprocess.run(
                [exe, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                 f"--user-data-dir={profil}", f"--print-to-pdf={pdf_tmp}", url],
                check=False, timeout=delai_s + 60,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # msedge.exe peut rendre la main à un processus enfant qui imprime
            # ensuite : on attend un PDF dont la taille ne bouge plus.
            limite, taille = time.monotonic() + delai_s + 60, -1
            while time.monotonic() < limite:
                actuelle = pdf_tmp.stat().st_size if pdf_tmp.is_file() else -1
                if actuelle > 0 and actuelle == taille:
                    break
                taille = actuelle
                time.sleep(1)
            else:
                raise RuntimeError("le navigateur n'a pas écrit de PDF")
            shutil.copyfile(pdf_tmp, sortie)
        finally:
            serveur.shutdown()
            serveur.server_close()
    return rapport[0] if rapport else None


def main(argv: list[str]) -> int:
    # Console cp1252 : ✓ ⚠ ✗ y deviendraient « ? » au lieu de faire planter.
    sys.stdout.reconfigure(errors="replace")
    garder_html = "--html" in argv
    exe = navigateur()
    if exe is None:
        print("Ni Edge ni Chrome trouvé : définir IRIS_NAVIGATEUR (chemin de l'exécutable).")
        return 1
    code = version_du_code()
    if code != RELEVE:
        print(f"⚠ Contenu relevé sur la version {RELEVE}, code en {code} : "
              "vérifier les pièces contre le code, puis relever RELEVE.")

    aujourd_hui = date.today()
    doc = construire_html(f"{MOIS[aujourd_hui.month - 1].capitalize()} {aujourd_hui.year}")
    sortie = RACINE / f"IRIS_Encode_arbre_de_decision_v{RELEVE}.pdf"
    if garder_html:
        sortie.with_suffix(".html").write_text(doc, encoding="utf-8")

    rapport = imprimer(doc, sortie, exe)
    if rapport is None:
        print("✗ La page n'a rien signalé : diagrammes peut-être non dessinés (réseau ?).")
        return 1
    if isinstance(rapport, dict) and "erreur" in rapport:
        print(f"✗ Rendu Mermaid en échec : {rapport['erreur']}")
        return 1
    petits = [r for r in rapport if r["corps_pt"] < CORPS_MIN_PT]
    print(f"✓ {sortie.name} : {len(PIECES)} pièces, corps des diagrammes "
          f"{min(r['corps_pt'] for r in rapport)} à {max(r['corps_pt'] for r in rapport)} pt")
    for r in petits:
        print(f"⚠ {r['num']} : {r['corps_pt']} pt, sous {CORPS_MIN_PT} — découper la pièce")
    return 0 if not petits else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
