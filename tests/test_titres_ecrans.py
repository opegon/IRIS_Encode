"""
tests/test_titres_ecrans.py — Les titres de disque dans les écrans annexes (IE-134).

Constats de la revue IE-114 :

- **CR-86**, **CR-94** — sur un titre de Blu-ray de plusieurs clips, la mesure
  d'une greffe lisait le seul premier clip, avec la durée du titre entier :
  la greffe est refusée tant que le titre n'est pas assemblé, comme pour un DVD ;
- **CR-96** — OpenSubtitles cherchait « 00800 », sans empreinte ;
- **CR-100** — la fiche (`I`) cherchait « 00800 » ou « TITLE 01 ».
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from core.bluray import TitreDisque

RACINE = Path(__file__).resolve().parent.parent


def _titre(tmp_path, clips: int, numero: int = 0) -> TitreDisque:
    racine = tmp_path / "Film (2020)"
    return TitreDisque(chemin=racine / "BDMV" / "PLAYLIST" / "00800.mpls", racine=racine,
                       clips=[racine / "BDMV" / "STREAM" / f"0000{i}.m2ts"
                              for i in range(clips)],
                       duree=6000.0, nom="Film (2020)", principal=True, numero=numero)


class _Ecran:
    def __init__(self):
        self.notes, self.empile = [], []
        self.app = SimpleNamespace(bell=lambda: None,
                                   push_screen=lambda *a: self.empile.append(a))

    def notify(self, texte, **_k):
        self.notes.append(texte)


def _decision(titre):
    info = SimpleNamespace(titre=titre, path=titre.chemin, lecture=titre.clips[0],
                           dossier=titre.racine, stem_sortie=titre.nom_sortie)
    return SimpleNamespace(info=info, external_tracks=[],
                           profile={"subtitle_languages": ["fre"]})


@pytest.mark.parametrize("clips,numero", [(2, 0), (1, 1)])
def test_pas_de_greffe_sur_un_titre_non_assemblé(tmp_path, clips, numero):
    """Blu-ray de plusieurs clips (CR-86, CR-94), DVD (IE-121)."""
    from tui.screens.donor_picker import pick_external_tracks
    ecran = _Ecran()
    pick_external_tracks(ecran, _decision(_titre(tmp_path, clips, numero)), lambda: None)
    assert ecran.empile == [] and len(ecran.notes) == 1


def test_un_titre_d_un_clip_se_greffe_et_cherche_par_le_disque(tmp_path):
    """CR-96 : la vidéo donnée est le clip (empreinte), le nom celui du disque."""
    from tui.screens.donor_picker import DonorFileScreen, pick_external_tracks
    ecran = _Ecran()
    titre = _titre(tmp_path, 1)
    pick_external_tracks(ecran, _decision(titre), lambda: None)
    (donneur, _rappel), = ecran.empile
    assert isinstance(donneur, DonorFileScreen)
    assert donneur._video == titre.clips[0]
    assert donneur._nom == "Film (2020)"


def test_opensubtitles_cherche_le_nom_donné(monkeypatch, tmp_path):
    from core import opensubtitles
    vus = []
    monkeypatch.setattr(opensubtitles, "empreinte", lambda v: "")
    monkeypatch.setattr(opensubtitles, "_parametres_nom",
                        lambda v: vus.append(v.name) or {"query": v.stem})
    client = opensubtitles.Client("cle", "", "", "iris")
    monkeypatch.setattr(client, "_appel", lambda *a, **k: {"data": []})
    client.chercher(tmp_path / "00800.mpls", ["fre"], nom="Film.2020")
    assert vus == ["Film.2020.mkv"], "le nom à points garde sa fin"


def test_la_fiche_d_un_titre_cherche_le_nom_du_disque():
    """CR-100."""
    texte = (RACINE / "tui" / "screens" / "browser.py").read_text(encoding="utf-8")
    corps = texte[texte.index("def _open_meta"):]
    corps = corps[:corps.index("self.app.push_screen(MetaPopup(path, source))")]
    assert "stem_sortie" in corps
