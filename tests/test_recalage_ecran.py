"""
tests/test_recalage_ecran.py — Écran de recalage et lecture des sous-titres (IE-125, 3/3).

Constats CR-35, CR-36, CR-37, CR-52 et CR-92 de `revue_code_2026-10-08.md`
(CR-35 : voir aussi `tests/test_sync.py`).
"""
from __future__ import annotations

from pathlib import Path

from core import preview, sync
from core.muxer import ExternalTrack, TrackKind
from tui.screens.sync import SyncScreen


# ─── CR-36 : jamais quatre chiffres de millisecondes ─────────────────────────

def test_l_horodatage_arrondit_avant_de_decouper():
    assert sync._srt_stamp(8.450 - 2.450) == "00:00:06,000"


def test_aucun_horodatage_decale_n_a_quatre_chiffres():
    """Toutes les millisecondes de la première minute × décalages usuels."""
    for ms in range(60_000):
        for d in (-2.450, -0.85, 0.04, 1.001, 2.450):
            texte = sync._srt_stamp(ms / 1000 + d)
            assert len(texte.rsplit(",", 1)[1]) == 3, (ms, d, texte)


# ─── CR-37 : WebVTT, fractions courtes, `.sub` ───────────────────────────────

def test_un_vtt_sans_heures_rend_ses_repliques(tmp_path):
    vtt = tmp_path / "vf.vtt"
    vtt.write_text("WEBVTT\n\n00:01.000 --> 00:02.500\nBonjour\n\n"
                   "01:02:03.250 --> 01:02:04.000\nSalut\n", encoding="utf-8")
    assert sync.read_cues(vtt) == [(1.0, 2.5), (3723.25, 3724.0)]


def test_une_fraction_courte_se_complete_a_droite(tmp_path):
    srt = tmp_path / "vf.srt"
    srt.write_text("1\n00:00:01,5 --> 00:00:02,25\nX\n", encoding="utf-8")
    assert sync.read_cues(srt) == [(1.5, 2.25)]


def test_un_sub_n_est_pas_lu_comme_du_texte():
    """VobSub binaire ou MicroDVD : ni l'un ni l'autre ne se lit comme un SRT.
    Il passe par l'extraction, qui dit pourquoi elle échoue."""
    assert ".sub" not in sync._TEXT_SUB_EXT
    assert ".vtt" in sync._TEXT_SUB_EXT


def test_le_recalage_par_plages_relit_un_vtt(tmp_path):
    vtt = tmp_path / "vf.vtt"
    vtt.write_text("WEBVTT\n\n00:01.000 --> 00:02.500\nBonjour\n", encoding="utf-8")
    out = sync.shift_srt(vtt, [sync.Segment(0.0, 10.0, 500, 1.0)], tmp_path / "out.srt")
    assert sync.read_cues(out) == [(1.5, 3.0)]


# ─── CR-52 : mpv montre la piste choisie ─────────────────────────────────────

def test_mpv_recoit_la_piste_extraite_et_non_le_conteneur(tmp_path, monkeypatch):
    monkeypatch.setattr(preview, "_mpv_path", "mpv")
    t = ExternalTrack(source_path=tmp_path / "donneur.mkv", source_tid=5,
                      kind=TrackKind.SUBTITLE, language="fre")
    extrait = tmp_path / "donneur_4_[sync].srt"
    cmd = preview.build_command(tmp_path / "film.mkv", t, sub_file=extrait)
    assert f"--sub-file={extrait}" in cmd
    assert f"--sub-file={t.source_path}" not in cmd


def test_sans_extraction_mpv_recoit_le_fichier_texte(tmp_path, monkeypatch):
    monkeypatch.setattr(preview, "_mpv_path", "mpv")
    t = ExternalTrack(source_path=tmp_path / "vf.ass", source_tid=0,
                      kind=TrackKind.SUBTITLE, language="fre")
    assert f"--sub-file={t.source_path}" in preview.build_command(
        tmp_path / "film.mkv", t)


# ─── CR-92 : le recalage audio vise sa piste, pas un rang ────────────────────

class _FauxApp:
    def bell(self) -> None:
        pass


def _ecran(pistes: list[ExternalTrack], curseur: int):
    class _Faux(SyncScreen):
        app = _FauxApp()                       # pas d'application Textual

        def __init__(self):
            self._tracks = pistes
            self._measuring = False
            self.dits: list[str] = []

        def _current(self):                    return curseur
        def _set_hint(self, texte):            self.dits.append(texte)
        def _show_bar(self, *a, **k):          pass
        def _refresh_row(self, i):             pass
        def _update_status(self):              pass
        def _build_table(self, **k):           pass
        def _set_origin_cell(self, *a):        pass

    return _Faux()


def _pistes(tmp_path) -> list[ExternalTrack]:
    return [
        ExternalTrack(source_path=tmp_path / "en.srt", source_tid=0,
                      kind=TrackKind.SUBTITLE, language="eng"),
        ExternalTrack(source_path=tmp_path / "vf.mkv", source_tid=1,
                      kind=TrackKind.AUDIO, language="fre", delay_ms=-2000),
        ExternalTrack(source_path=tmp_path / "fr.srt", source_tid=0,
                      kind=TrackKind.SUBTITLE, language="fre"),
    ]


def test_d_est_refuse_pendant_un_recalage(tmp_path):
    pistes = _pistes(tmp_path)
    e = _ecran(pistes, curseur=0)
    e._measuring = True
    e.action_remove_track()
    assert len(pistes) == 3
    assert e.dits


def test_le_resultat_va_a_la_piste_recalee_meme_si_les_rangs_ont_bouge(tmp_path):
    """Le scénario de la revue : la VF recalée, une piste retirée avant
    elle entre-temps. Le fichier va à la VF, les sous-titres FR gardent le leur."""
    pistes = _pistes(tmp_path)
    vf, st_fr = pistes[1], pistes[2]
    e = _ecran(pistes, curseur=1)
    pistes.pop(0)                             # les rangs glissent d'un cran
    recale = tmp_path / "Film_fre.iris_recale.mka"
    e._retime_done(vf, recale, [])
    assert vf.source_path == recale and vf.delay_ms == 0
    assert st_fr.source_path == tmp_path / "fr.srt"


def test_un_resultat_pour_une_piste_retiree_est_ignore(tmp_path):
    pistes = _pistes(tmp_path)
    vf = pistes.pop(1)
    e = _ecran(pistes, curseur=0)
    e._retime_done(vf, tmp_path / "x.mka", [])
    assert all(t.source_path.name != "x.mka" for t in pistes)
