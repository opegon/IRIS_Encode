"""
core/profiles.py — Lecture/écriture profiles.toml.

`profiles.toml` fait foi : les profils, et leur ordre, viennent de lui seul.
Le code n'en garde qu'un en dur, `_default_`, qui sert de plancher — il sème
le fichier au premier lancement et tient lieu de secours si le TOML devient
illisible. Tous les profils sont modifiables et supprimables, à ceci près
qu'on refuse de vider la liste entièrement.
"""
from __future__ import annotations

import os
import re
import threading
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomli_w

APP_DIR       = Path(__file__).resolve().parent.parent
PROFILES_PATH = APP_DIR / "profiles.toml"

# Le profil plancher. Ses réglages recopient l'ancien `serie_basic`, qui était
# déjà le point de départ d'un nouveau profil et le profil actif au démarrage —
# à une exception près, `dolby_vision`, qui vaut "sdr" et non "hdr10".
PROFIL_DEFAUT_ID = "_default_"

ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")

# ─── Profil par défaut embarqué ────────────────────────────────────────────

_BASE_AUDIO = {
    "audio_languages":         ["fre", "eng"],
    # Les sous-titres n'étaient filtrés par rien : un rip streaming en embarque
    # quarante, et les quarante traversaient la chaîne. Clé absente d'un profil
    # personnel = comportement historique, tout est gardé.
    "subtitle_languages":      ["fre", "eng"],
    "audio_stereo_kbps":       192,
    "audio_surround_kbps":     448,
    "audio_surround_7_1_kbps": 640,
    "audio_copy_compatible":   True,
    # "none" | "ac3" | "eac3" — transcode les pistes TrueHD et DTS au débit
    # présent dans la piste, plafonné à ce que l'encodeur sait produire.
    "audio_hd_codec":          "none",
    # "auto" | "mp4" | "mkv" — conteneur de sortie. "auto" laisse le contenu
    # décider ; "mp4" écarte les sous-titres image, sauf s'ils sont les seuls.
    "container":               "auto",
}

_PROFIL_DEFAUT: dict[str, Any] = {
    "bitrate_720p_kbps":  1500,
    "bitrate_1080p_kbps": 2200,
    "bitrate_4k_kbps":    5000,
    "keep_4k":            False,
    "delete_source":      False,
    "preset_encoder":     "medium",
    # "sdr" : le Dolby Vision est ramené en SDR, comme sur `film_basic`. Le
    # plancher est ce que reçoit une installation neuve, et ce sur quoi retombe
    # une session dont le TOML est illisible — il doit produire un fichier qui
    # se lit partout, pas un HDR10 que le téléviseur rendra délavé s'il ne le
    # gère pas.
    "dolby_vision":       "sdr",
    "preserve_hd_audio":  False,
    **_BASE_AUDIO,
}


# ─── Modèle ───────────────────────────────────────────────────────────────────

@dataclass
class Profile:
    id:   str
    data: dict[str, Any]

    # --- Accesseurs pratiques -----------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def bitrate_for_height(self, height: int) -> int:
        """Bitrate cible (bps) selon la hauteur de la source."""
        if height >= 2160:
            return self.data.get("bitrate_4k_kbps", 5000) * 1000
        if height >= 1080:
            return self.data.get("bitrate_1080p_kbps", 2500) * 1000
        return self.data.get("bitrate_720p_kbps", 1500) * 1000

    def summary_line(self) -> str:
        """Une ligne résumant les paramètres clés (pour l'écran Config)."""
        dv   = self.data.get("dolby_vision", "hdr10")
        p1   = self.data.get("bitrate_1080p_kbps", "?")
        pre  = self.data.get("preset_encoder", "?")
        hd   = "oui" if self.data.get("preserve_hd_audio") else "non"
        return f"dv: {dv}  · 1080p: {p1}k  · preset: {pre}  · hd-audio: {hd}"

    def summary_fields(self) -> dict[str, str]:
        """Valeurs individuelles pour affichage en colonnes séparées."""
        k4   = self.data.get("keep_4k", False)
        del_ = self.data.get("delete_source", False)
        return {
            "dv":       self.data.get("dolby_vision", "hdr10"),
            "1080p":    f'{self.data.get("bitrate_1080p_kbps", "?")}k',
            "4k":       f'{self.data.get("bitrate_4k_kbps", "?")}k' + (" ✓" if k4 else ""),
            "preset":   self.data.get("preset_encoder", "?"),
            "hd_audio": "oui" if self.data.get("preserve_hd_audio") else "non",
            "del_src":  "⚠ oui" if del_ else "non",
        }

    def as_toml_dict(self) -> dict[str, Any]:
        return dict(self.data)


# ─── Chargement ───────────────────────────────────────────────────────────────

def _plancher() -> dict[str, "Profile"]:
    """Le profil livré, seul — semence du premier lancement, secours d'un TOML cassé."""
    return {PROFIL_DEFAUT_ID: Profile(id=PROFIL_DEFAUT_ID, data=dict(_PROFIL_DEFAUT))}


def load_all() -> dict[str, "Profile"]:
    """Charge les profils dans l'ordre où profiles.toml les écrit.

    Le fichier fait foi : ce qu'il contient, dans son ordre, et rien d'autre.
    La version précédente posait d'abord neuf profils codés en dur puis
    superposait le fichier — l'ordre lu était donc celui du code, jamais celui
    du fichier, et un profil livré retiré du fichier réapparaissait à chaque
    lancement sans pouvoir être supprimé. Un utilisateur ayant renommé les
    profils livrés en voyait seize là où son fichier en décrivait dix.
    """
    if not PROFILES_PATH.exists():
        _write_defaults()
        return _plancher()

    try:
        with PROFILES_PATH.open("rb") as f:
            raw: dict[str, Any] = tomllib.load(f)
    except Exception as e:
        # Syntaxe invalide — on ne réécrit rien, le fichier reste réparable à
        # la main, et on tient la session sur le seul profil plancher.
        print(
            f"⚠  profiles.toml illisible ({e}). "
            f"Chargement du profil [{PROFIL_DEFAUT_ID}] intégré."
        )
        return _plancher()

    profiles = {
        name: Profile(id=name, data=dict(data))
        for name, data in raw.items()
        if isinstance(data, dict)
    }

    # Un fichier vide, ou qui ne décrit pas une seule table nommée, ne laisse
    # aucun profil sélectionnable : le plancher reprend la main.
    return profiles or _plancher()


# Deux écrans peuvent enregistrer, et `load_all` réécrit les défauts au premier
# lancement : le verrou coûte le temps d'une écriture de quelques kilo-octets.
_VERROU_ECRITURE = threading.Lock()


def _ecrire(raw: dict[str, Any]) -> None:
    """Écrit profiles.toml — entièrement, ou pas du tout.

    L'écriture directe ouvrait le fichier en `"wb"`, ce qui **tronque avant
    d'écrire** : une coupure à mi-course laisse un TOML invalide. `load_all`
    avale alors l'erreur de syntaxe, avertit, et rend les seuls profils
    livrés — tout ce que l'utilisateur a créé ou modifié est perdu, sans
    recours. On écrit donc à côté, puis on remplace d'un seul geste.

    C'est exactement la parade de `config.save`, posée en v0.8.3.12 pour
    `config.toml` et jamais portée ici. Ce fichier-là pèse plus lourd : une
    configuration se refait en trois réglages, une bibliothèque de profils
    non.
    """
    with _VERROU_ECRITURE:
        provisoire = PROFILES_PATH.with_name(PROFILES_PATH.name + ".tmp")
        try:
            with provisoire.open("wb") as f:
                tomli_w.dump(raw, f)
                f.flush()
                # Sans fsync, `os.replace` peut publier un fichier dont le
                # contenu n'a pas encore atteint le disque : sur coupure
                # secteur, on remplace un bon fichier par un vide.
                os.fsync(f.fileno())
            os.replace(provisoire, PROFILES_PATH)
        except BaseException:
            provisoire.unlink(missing_ok=True)
            raise


def save_all(profiles: dict[str, "Profile"]) -> None:
    """Écrit tous les profils dans profiles.toml, dans l'ordre du dictionnaire."""
    _ecrire({name: p.as_toml_dict() for name, p in profiles.items()})


def _write_defaults() -> None:
    _ecrire({PROFIL_DEFAUT_ID: dict(_PROFIL_DEFAUT)})


# ─── Validation ───────────────────────────────────────────────────────────────

def validate_id(name: str) -> bool:
    return bool(ID_PATTERN.match(name))


def parse_languages(raw: str) -> list[str]:
    """Parse une chaîne de codes langue séparés par , ; ou espace."""
    parts = re.split(r"[,;\s]+", raw.strip())
    return [p.strip().lower() for p in parts if p.strip()]
