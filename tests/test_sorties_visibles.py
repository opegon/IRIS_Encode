"""
tests/test_sorties_visibles.py — IE-62 : les sorties restent visibles, le nom se
remplace, et l'estimation prend une échelle.

Trois changements liés par l'écran d'accueil.

**La vue montre ce que le dossier contient.** Depuis IE-49, `deja_produit()`
écartait du scan tout fichier portant un suffixe d'encodage. Le dossier de
travail mentait donc sur son contenu : un film encodé la veille n'y figurait
plus, et rien ne distinguait « déjà produit » de « jamais existé ». Le filtre
quitte la vue et reste dans le scanner, qui alimente le scan récursif et les
lots automatiques — c'est là qu'il protège vraiment.

**Le suffixe se remplace.** `Film_[av1]` réencodé en HEVC donnait
`Film_[av1]_[hevc]`, puis `Film_[av1]_[hevc]_[hevc]`. Remplacer fait apparaître
deux collisions que l'empilement masquait — la cible peut être la source, ou un
fichier existant — et toutes deux se numérotent.

**L'estimation prend une échelle continue.** Elle n'avait que deux états :
orange au-dessus de zéro, rien en dessous.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from rich.text import Text

from core.decision import (DVAction, FileDecision, VideoAction, VideoDecision,
                           resoudre_sorties)
from core.scanner import (SubtitleTrack, VideoInfo,
                          stem_sans_suffixe_produit, suffixes_produits)
from tui.screens.browser import (_DEGRADE_GAIN, _DEGRADE_PERTE,
                                 _teinte_estimation)
from tui.widgets.file_tree import FileNavigator


# ─── Fabriques ────────────────────────────────────────────────────────────────

def _info(path: Path) -> VideoInfo:
    """Un 4K avec sous-titres image — donc une sortie Matroska.

    Le conteneur compte ici : une collision de noms n'existe qu'à extension
    égale. Un `Film_[hevc].mkv` dont la sortie tomberait en `.mp4` ne se
    heurterait pas à lui-même.
    """
    return VideoInfo(path=path, width=3840, height=2160, bitrate=8_000_000,
                     codec="hevc", duration=7200.0, frame_count=0,
                     dv_profile=None,
                     subtitle_tracks=[SubtitleTrack(index=0,
                                                    codec="hdmv_pgs_subtitle",
                                                    language="fre")])


def _dec(path: Path, *, suffixe: str = "_[hevc]",
         action: VideoAction = VideoAction.ENCODE_HEVC) -> FileDecision:
    return FileDecision(
        info=_info(path), profile={},
        video=VideoDecision(action=action, reason="", target_bitrate=3_000_000,
                            target_width=3840, target_height=2160,
                            dv_action=DVAction.NONE, output_suffix=suffixe))


# ─── La vue montre les sorties, le scanner continue de les écarter ────────────

def test_la_vue_liste_les_sorties_de_l_application(tmp_path):
    for nom in ("Film.mkv", "Film_[hevc].mkv", "Serie_[av1].mkv"):
        (tmp_path / nom).touch()
    noms = {p.name for p in FileNavigator(tmp_path).list_videos()}
    assert noms == {"Film.mkv", "Film_[hevc].mkv", "Serie_[av1].mkv"}


def test_le_scan_automatique_les_ecarte_toujours(tmp_path, monkeypatch):
    """Le garde-fou d'IE-49 vit dans le scanner, pas dans la vue : c'est lui
    qui alimente le scan récursif et les lots que l'utilisateur ne compose pas
    lui-même."""
    from core import scanner
    for nom in ("Film.mkv", "Film_[av1].mkv"):
        (tmp_path / nom).touch()
    monkeypatch.setattr(scanner, "scan", _info)
    vus = {i.path.name for i in scanner.scan_directory(tmp_path)}
    assert vus == {"Film.mkv"}
    vus_rec = {i.path.name for i in scanner.scan_directory_recursive(tmp_path)}
    assert vus_rec == {"Film.mkv"}


# ─── Ctrl+A les ignore, l'espace les atteint ──────────────────────────────────

class _FauxEcran:
    """Juste ce qu'il faut pour appeler les deux actions sans monter l'écran."""
    from tui.screens.browser import BrowserScreen as _B
    action_select_all    = _B.action_select_all
    action_toggle_select = _B.action_toggle_select

    def __init__(self, rows, produits, curseur=None):
        self._rows     = rows
        self._produits = produits
        self._selected = set()
        self._curseur  = curseur

    def _current_row_info(self):
        return ("file", self._curseur)

    def _update_row_check(self, path):
        pass

    def _update_status(self):
        pass


def test_ctrl_a_ne_prend_pas_nos_propres_sorties(tmp_path):
    source  = tmp_path / "Film.mkv"
    produit = tmp_path / "Film_[hevc].mkv"
    ecran = _FauxEcran([("file", source), ("file", produit)], {produit})
    ecran.action_select_all()
    assert ecran._selected == {source}, \
        "Ctrl+A coche « tout ce qu'il y a à faire ici » — une sortie n'en est pas"


def test_l_espace_coche_une_sortie(tmp_path):
    produit = tmp_path / "Film_[hevc].mkv"
    ecran = _FauxEcran([("file", produit)], {produit}, curseur=produit)
    ecran.action_toggle_select()
    assert ecran._selected == {produit}, \
        "Réencoder une sortie se demande, il ne se refuse pas"


# ─── La ligne d'une sortie s'efface, sauf sa case ─────────────────────────────

class _FauxEcranCellules:
    """`_row_cells` ne lit du reste de l'écran que le profil et la config."""
    from tui.screens.browser import BrowserScreen as _B
    _row_cells = _B._row_cells

    def _active_profile(self):
        return SimpleNamespace(data={"preset_encoder": "medium"})

    @property
    def _app(self):
        return SimpleNamespace(cfg={})


def _styles(tmp_path, *, produit: bool):
    fichier = tmp_path / "Film_[hevc].mkv"
    fichier.write_bytes(b"x" * 1024)
    return [c.style for c in _FauxEcranCellules()._row_cells(
        _dec(fichier), Text("[ ]"), produit)]


def test_la_ligne_d_une_sortie_est_grisee(tmp_path):
    styles = _styles(tmp_path, produit=True)
    assert styles[0] == "",         "la case à cocher garde sa teinte : grisée, on ne verrait plus la sélection"
    assert all(s == "dim" for s in styles[1:]), styles


def test_une_ligne_ordinaire_garde_ses_couleurs(tmp_path):
    styles = _styles(tmp_path, produit=False)
    assert not all(s == "dim" for s in styles[1:]), styles


# ─── Le suffixe se remplace ───────────────────────────────────────────────────

@pytest.mark.parametrize("stem, attendu", [
    ("Film",                "Film"),
    ("Film_[hevc]",         "Film"),
    ("Film_[av1]",          "Film"),
    # Le compteur de collision part avec le suffixe : sans cela, un
    # `Film_[hevc](2)` réencodé redonnerait `Film_[hevc](2)_[hevc]` et
    # l'empilement reviendrait par la porte que la numérotation vient d'ouvrir.
    ("Film_[hevc](2)",      "Film"),
    ("Film_[hevc](12)",     "Film"),
    # `_[mux]` et `_[join]` disent d'où vient le fichier, pas comment il a été
    # encodé : l'encodage ne les efface pas.
    ("Film_[mux]",          "Film_[mux]"),
    ("Film_[join]",         "Film_[join]"),
    # La copie que fait Windows n'a pas de suffixe produit devant son compteur.
    ("Film (2)",            "Film (2)"),
    # Le suffixe se cherche en fin de nom : au milieu, ce n'est pas une sortie
    # que nous venons d'écrire, et la retirer fabriquerait un nom inédit.
    ("Film_[hevc] (copie)", "Film_[hevc] (copie)"),
])
def test_retrait_du_suffixe_produit(stem, attendu):
    assert stem_sans_suffixe_produit(stem) == attendu


def test_le_retrait_derive_de_la_table_des_suffixes():
    """IE-49 : aucun littéral en dur. Tout suffixe produit doit se retirer."""
    for suffixe in suffixes_produits():
        assert stem_sans_suffixe_produit(f"Film{suffixe}") == "Film"


def test_le_suffixe_ne_s_empile_plus(tmp_path):
    dec = _dec(tmp_path / "Film_[av1].mkv")
    assert dec.output_path.stem == "Film_[hevc]"


# ─── La numérotation des collisions ───────────────────────────────────────────

def test_la_cible_est_la_source(tmp_path):
    """Le geste le plus courant : rebaisser le débit d'une sortie HEVC."""
    src = tmp_path / "Film_[hevc].mkv"
    src.touch()
    dec = _dec(src)
    resoudre_sorties([dec])
    assert dec.output_path.stem == "Film_[hevc](2)"
    assert dec.output_path != src


def test_la_cible_existe_deja(tmp_path):
    """Ce fichier-là n'est la source de personne : rien ne l'aurait protégé."""
    (tmp_path / "Film_[hevc].mkv").touch()
    dec = _dec(tmp_path / "Film_[av1].mkv")
    resoudre_sorties([dec])
    assert dec.output_path.stem == "Film_[hevc](2)"


def test_deux_decisions_d_un_lot_ne_visent_pas_le_meme_nom(tmp_path):
    a = _dec(tmp_path / "Film_[av1].mkv")
    b = _dec(tmp_path / "Film_[H264].mkv")
    resoudre_sorties([a, b])
    assert a.output_path != b.output_path


def test_le_nom_ne_derive_pas_une_fois_le_fichier_ecrit(tmp_path):
    """Le piège de fond : `output_path` est relu *après* l'encodage — pour
    vérifier la sortie, et pour effacer un fichier partiel après un abandon.
    Une résolution qui interrogerait le disque à chaque lecture rendrait `(3)`
    une fois `(2)` écrit, et le nettoyage effacerait un fichier étranger."""
    src = tmp_path / "Film_[hevc].mkv"
    src.touch()
    dec = _dec(src)
    resoudre_sorties([dec])
    fige = dec.output_path
    fige.touch()                       # l'encodage a eu lieu
    assert dec.output_path == fige
    resoudre_sorties([dec])            # idempotent, même sur un lot qui repasse
    assert dec.output_path == fige


def test_un_skip_qui_n_ecrit_rien_n_est_pas_numerote(tmp_path):
    """Sa sortie nominale est sa propre source : la numéroter fabriquerait un
    nom qui ne servira jamais."""
    src = tmp_path / "Film.mkv"
    src.touch()
    dec = _dec(src, suffixe="", action=VideoAction.SKIP)
    resoudre_sorties([dec])
    assert dec.output_override is None
    assert dec.output_path.stem == "Film"


# ─── Le dégradé de la colonne Estim ───────────────────────────────────────────

def _canaux(style: str) -> tuple[int, int, int]:
    nombres = style[style.index("(") + 1:style.index(")")].split(",")
    return tuple(int(n) for n in nombres)   # type: ignore[return-value]


def test_un_gain_est_vert_une_perte_est_orange():
    rouge_gain,  vert_gain,  _ = _canaux(_teinte_estimation(-60))
    rouge_perte, vert_perte, _ = _canaux(_teinte_estimation(60))
    assert vert_gain > rouge_gain,   "un gain de taille tire vers le vert"
    assert rouge_perte > vert_perte, "une sortie plus grosse tire vers l'orange"


def test_l_echelle_est_monotone():
    """L'intensité doit dire l'ampleur, pas seulement le signe."""
    rouges = [_canaux(_teinte_estimation(d))[0]
              for d in (-60, -50, -30, -10, 0, 10, 25, 60)]
    assert rouges == sorted(rouges)


def test_l_echelle_est_bornee():
    """Au-delà, l'œil ne distingue plus rien, et le corpus courant — entre
    −20 % et −50 % — deviendrait indiscernable."""
    assert _teinte_estimation(_DEGRADE_GAIN) == _teinte_estimation(-200)
    assert _teinte_estimation(_DEGRADE_PERTE) == _teinte_estimation(500)


def test_une_sortie_plus_grosse_garde_le_gras_des_alertes():
    assert _teinte_estimation(10).startswith("bold ")
    assert not _teinte_estimation(-10).startswith("bold ")
