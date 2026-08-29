"""
core/joiner.py — Collage bout à bout de plusieurs parties en un fichier unique.

Un film livré en `part1` / `part2` n'est encodable qu'une fois recousu : chaque
partie prise seule donnerait sa propre sortie, et le profil déciderait deux fois
au lieu d'une. Le collage produit un `_[join].mkv` que le navigateur reproposera
comme n'importe quel autre fichier — c'est tout l'objet du suffixe (voir
`scanner.suffixes_produits`, qui l'écarte de la liste des sorties d'encodage).

mkvmerge en mode `append` (`fichier1 + fichier2`) fait le travail sans réencoder :
il recale les horodatages de chaque partie sur la fin de la précédente. Le prix à
payer est sa règle d'appariement — il refuse de coller deux parties dont les
pistes ne se correspondent pas. `controler()` le dit *avant* de lancer, plutôt
que de laisser mkvmerge échouer à la moitié d'une copie de 30 Go.

⚠ Le démultiplexeur `concat` de ffmpeg n'est pas une alternative ici : il exige
des paramètres de flux strictement identiques et gère mal les pistes multiples.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .scanner import VideoInfo

# Suffixe du fichier recousu. Absent de `SUFFIX_BY_ACTION` à dessein : ce n'est
# pas une sortie d'encodage mais une entrée de travail, et le scan doit la voir.
JOIN_SUFFIX = "_[join]"

# Il faut au moins deux parties pour qu'il y ait quelque chose à coller.
MIN_PARTIES = 2


# ─── Ordre des parties ────────────────────────────────────────────────────────

def _cle_naturelle(nom: str) -> list[tuple]:
    """Clé de tri où les nombres comptent comme des nombres.

    Un tri alphabétique place `part10` avant `part2`. Chaque élément est un
    tuple homogène — `(0, n, "")` pour un nombre, `(1, 0, texte)` pour du
    texte — pour qu'aucune comparaison ne mette jamais un int face à une str.
    """
    return [
        (0, int(morceau), "") if morceau.isdigit() else (1, 0, morceau.lower())
        for morceau in re.split(r"(\d+)", nom)
    ]


def ordre_naturel(parts: list[Path]) -> list[Path]:
    """Les parties dans l'ordre déduit de leurs noms (part1 < part2 < part10)."""
    return sorted(parts, key=lambda p: _cle_naturelle(p.name))


# ─── Nom du fichier produit ───────────────────────────────────────────────────

# Les mots qui ne servaient qu'à numéroter les parties : une fois recousues,
# ils n'ont plus de sens dans le nom du tout.
_MARQUEURS: tuple[str, ...] = (
    "part", "partie", "pt", "cd", "disc", "disk", "disque", "vol", "tome",
)
_SEPARATEURS = " ._-([{#"


def nom_commun(parts: list[Path]) -> str:
    """Le nom du tout, déduit du préfixe commun aux parties.

    `Film part1` + `Film part2` → `Film`. Le préfixe commun s'arrête sur
    `Film part`, dont il reste à retirer le marqueur de numérotation et les
    séparateurs qui le portaient. Si les noms n'ont rien en commun, le nom de
    la première partie fait foi — mieux vaut un nom imparfait qu'un nom vide.
    """
    stems = [p.stem for p in parts]
    if not stems:
        return ""

    nom = os.path.commonprefix(stems)
    while True:
        avant = nom
        nom = nom.rstrip(_SEPARATEURS)
        bas  = nom.lower()
        for marqueur in _MARQUEURS:
            if bas.endswith(marqueur):
                nom = nom[: -len(marqueur)]
                break
        if nom == avant:
            break

    return nom.strip() or stems[0]


def join_output_path(parts: list[Path]) -> Path:
    """Chemin du fichier recousu, à côté des parties et jamais sur l'une d'elles."""
    return parts[0].parent / f"{nom_commun(parts)}{JOIN_SUFFIX}.mkv"


# ─── Contrôle de compatibilité ────────────────────────────────────────────────

@dataclass
class Controle:
    """Ce que l'appariement des pistes autorise, et ce qu'il coûte.

    Deux niveaux, parce que mkvmerge lui-même en a deux : un codec vidéo qui
    change interdit le collage, une piste de sous-titres en trop se contente de
    disparaître. Confondre les deux, c'est soit refuser un collage possible,
    soit laisser produire un fichier amputé sans le dire (voir IE-52).
    """
    blocages:        list[str] = field(default_factory=list)
    avertissements:  list[str] = field(default_factory=list)

    @property
    def collable(self) -> bool:
        return not self.blocages


def controler(infos: list[VideoInfo]) -> Controle:
    """Ces parties peuvent-elles être collées, et à quel prix ?

    mkvmerge apparie les pistes par type et par rang. La première partie sert
    de référence : c'est elle qui donne au fichier produit ses codecs, sa
    définition et son jeu de pistes.
    """
    ctrl = Controle()
    if len(infos) < MIN_PARTIES:
        ctrl.blocages.append(
            f"Il faut au moins {MIN_PARTIES} parties à coller "
            f"({len(infos)} sélectionnée(s))."
        )
        return ctrl

    ref = infos[0]
    for info in infos[1:]:
        nom = info.path.name

        if info.codec != ref.codec:
            ctrl.blocages.append(
                f"{nom} — vidéo en {info.codec}, "
                f"{ref.path.name} en {ref.codec}."
            )
        if (info.width, info.height) != (ref.width, ref.height):
            ctrl.blocages.append(
                f"{nom} — {info.width}×{info.height}, "
                f"{ref.path.name} en {ref.width}×{ref.height}."
            )

        # Pistes audio appariées rang par rang : seules celles que mkvmerge
        # mettra effectivement bout à bout sont comparées.
        for rang, (a, b) in enumerate(zip(ref.audio_tracks, info.audio_tracks)):
            if a.codec != b.codec:
                ctrl.blocages.append(
                    f"{nom} — piste audio {rang + 1} en {b.codec}, "
                    f"{a.codec} dans {ref.path.name}."
                )
            elif a.channels != b.channels:
                ctrl.blocages.append(
                    f"{nom} — piste audio {rang + 1} en {b.channel_layout}, "
                    f"{a.channel_layout} dans {ref.path.name}."
                )

        if len(info.audio_tracks) != len(ref.audio_tracks):
            ctrl.avertissements.append(
                f"{nom} — {len(info.audio_tracks)} piste(s) audio contre "
                f"{len(ref.audio_tracks)} : le fichier collé n'en gardera que "
                f"{min(len(info.audio_tracks), len(ref.audio_tracks))}."
            )
        if len(info.subtitle_tracks) != len(ref.subtitle_tracks):
            ctrl.avertissements.append(
                f"{nom} — {len(info.subtitle_tracks)} piste(s) de sous-titres "
                f"contre {len(ref.subtitle_tracks)} : le fichier collé n'en "
                f"gardera que "
                f"{min(len(info.subtitle_tracks), len(ref.subtitle_tracks))}."
            )

    return ctrl


# ─── Commande ─────────────────────────────────────────────────────────────────

def build_join_command(parts: list[Path], output: Path) -> list[str]:
    """
    Retourne la commande mkvmerge collant `parts` bout à bout vers `output`.

    Le `+` entre deux fichiers est ce qui distingue un collage d'un mux : sans
    lui, mkvmerge superposerait les pistes au lieu de les enchaîner.

    Lève ValueError si les parties sont trop peu nombreuses, si l'une revient
    deux fois, ou si la sortie écrase l'une d'elles.
    """
    if len(parts) < MIN_PARTIES:
        raise ValueError(
            f"Collage : {MIN_PARTIES} parties au minimum ({len(parts)} donnée(s))."
        )

    resolus = [p.resolve() for p in parts]
    if len(set(resolus)) != len(resolus):
        raise ValueError("Collage : la même partie est présente deux fois.")

    if output.resolve() in resolus:
        raise ValueError(
            f"Chemin de sortie identique à une partie ({output.name}). "
            f"Collage refusé pour éviter la corruption du fichier source."
        )

    # Relu ici et non importé une fois pour toutes : `set_mkvmerge_path` peut
    # l'avoir changé après l'import du module.
    from . import muxer

    cmd = [muxer._mkvmerge_path, "--gui-mode", "-o", str(output), str(parts[0])]
    for suivante in parts[1:]:
        cmd += ["+", str(suivante)]
    return cmd


# ─── Vérification du résultat ─────────────────────────────────────────────────

def duree_attendue(infos: list[VideoInfo]) -> float:
    """Durée du fichier collé, en secondes : la somme de celles des parties."""
    return sum(i.duration for i in infos)


def derive_duree(attendue: float, obtenue: float) -> float | None:
    """Écart entre durée attendue et durée obtenue, s'il dépasse le bruit.

    Un mkvmerge tué en cours de route laisse un fichier lisible et court : sans
    ce contrôle, il passerait pour un collage réussi (même piège qu'IE-41). La
    tolérance couvre l'arrondi du dernier bloc de chaque partie.
    """
    if attendue <= 0:
        return None
    ecart = obtenue - attendue
    return ecart if abs(ecart) > max(2.0, 0.01 * attendue) else None
