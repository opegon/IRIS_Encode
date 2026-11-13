"""
tests/test_apercu_estimation.py — Aperçu et estimation (IE-193 : CR-126, CR-137).

- **CR-126** — la vitesse mesurée se range sous l'encodeur effectif, et une
  copie de la vidéo n'en enregistre aucune : une copie Dolby Vision (> 100×)
  entrait dans la moyenne « hevc » d'un libx265 ;
- **CR-137** — l'aperçu compte les lignes retenues, estime et teinte comme
  l'accueil, coupe avec une ellipse, lit le préréglage de la décision et ne
  relit pas la taille des sources à chaque touche.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from textual.widgets import DataTable, Static

from core import config as cfg_mod
from core.decision import FileDecision, VideoAction
from core.i18n import ngettext
from core.profiles import Profile
from core.scanner import VideoInfo
from tests.test_arret_encodage import _App, _dec, _FauxFfmpeg, faux  # noqa: F401
from tui.common import estimate_encoding_duration, fmt_duration
from tui.screens import run as run_mod
from tui.screens.browser import _teinte_estimation
from tui.screens.dryrun import DryrunScreen


# ─── CR-126 : une vitesse par encodeur, aucune pour une copie ─────────────────

class _FfmpegReussi(_FauxFfmpeg):
    """Une passe qui aboutit, à la vitesse que dit son encodeur."""

    def __init__(self, cmd, duration=0.0):
        super().__init__(cmd, duration)
        self.vitesse = 120.0 if "copy" in cmd else 1.5

    def iter_progress(self):
        p = SimpleNamespace(percent=100.0, speed=self.vitesse, frame=1, fps=24.0,
                            bitrate=3000.0, format_elapsed=lambda: "0:01",
                            format_remaining=lambda: "0:00")
        yield "frame=1", p

    def wait(self):
        return 0


def _sans_defaut(*_args):
    return None


def test_une_copie_n_entre_pas_dans_la_vitesse_mesuree(faux, tmp_path, monkeypatch):
    def _build(d, plateforme, **options):
        codec = "copy" if d.info.path.name == "a.mkv" else "libx265"
        return ["ffmpeg", "-i", str(d.info.path), "-c:v", codec, str(d.output_path)]

    monkeypatch.setattr(run_mod, "EncoderProcess", _FfmpegReussi)
    monkeypatch.setattr(run_mod, "build_command", _build)
    monkeypatch.setattr(run_mod, "chaine_prevue", lambda d, p: (None, None, None))
    monkeypatch.setattr(run_mod, "defaut_sortie", _sans_defaut)
    monkeypatch.setattr(run_mod.RunScreen, "_audio_vide", staticmethod(_sans_defaut))
    monkeypatch.setattr(cfg_mod, "enregistrer", _sans_defaut)

    async def _run():
        app = _App([_dec(tmp_path / "a.mkv"), _dec(tmp_path / "b.mkv")])
        async with app.run_test() as pilot:
            for _i in range(20):
                await pilot.pause(0.1)
                if all(st.state == run_mod.FileState.SUCCESS for st in app.lot.statuts):
                    break
            await pilot.pause(0.2)
            return [st.state for st in app.lot.statuts], dict(
                app.cfg.get("stats", {}).get("encode_speed", {}))

    etats, vitesses = asyncio.run(_run())
    assert etats == [run_mod.FileState.SUCCESS] * 2
    assert vitesses == {"libx265": 1.5}


# ─── L'aperçu ────────────────────────────────────────────────────────────────

def _decision(tmp_path: Path, nom: str, octets: int = 10_000_000,
              duree: float = 60.0, preset: str = "medium") -> FileDecision:
    d = _dec(tmp_path / nom)
    d.info.path.write_bytes(b"\0" * octets)
    d.info.duration = duree
    d.profile = Profile("test", {"preset_encoder": preset})
    return d


def _ouvrir(decisions, cfg=None, profils=None, actions=()):
    async def _run():
        ecran = DryrunScreen(decisions)
        app = _App(ecran)
        app.cfg = cfg or {}
        app.profiles = profils or {}
        async with app.run_test(size=(200, 50)) as pilot:
            await pilot.pause(0.3)
            for action in actions:
                action(ecran)
                await pilot.pause(0.1)
            table = ecran.query_one(DataTable)
            lignes = [table.get_row_at(i) for i in range(table.row_count)]
            return (str(ecran.query_one("#status-bar", Static).render()),
                    str(ecran.query_one("#dryrun-summary", Static).render()),
                    lignes, list(table.columns.keys()),
                    ngettext("{count} file selected", "{count} files selected",
                             1).format(count=1))
    return asyncio.run(_run())


def _colonne(cles, nom: str) -> int:
    return [c.value for c in cles].index(nom)


def test_decocher_une_ligne_change_le_compte(tmp_path):
    decisions = [_decision(tmp_path, "a.mkv"), _decision(tmp_path, "b.mkv")]
    statut, resume, _l, _c, un = _ouvrir(
        decisions, actions=[DryrunScreen.action_toggle_select])
    assert un in statut
    assert "HEVC 1 " in resume + " "


def test_l_estimation_suit_la_regle_de_l_accueil(tmp_path):
    # 3 Mb/s pendant 60 s : 22,5 Mo estimés pour 10 Mo de source, +125 %.
    _st, _r, lignes, cles, _u = _ouvrir([_decision(tmp_path, "a.mkv")])
    cellule = lignes[0][_colonne(cles, "estim")]
    assert cellule.overflow == "ellipsis"
    assert str(cellule.style) == _teinte_estimation(125.0)


def test_la_resolution_desentrelacee_tient_sa_colonne(tmp_path, monkeypatch):
    monkeypatch.setattr(FileDecision, "desentrelace", property(lambda soi: True))
    _st, _r, lignes, cles, _u = _ouvrir([_decision(tmp_path, "a.mkv")])
    texte = lignes[0][_colonne(cles, "res")].plain
    assert texte.startswith("1920x1080")
    assert len(texte) <= cfg_mod.get_dryrun_column_widths({})["res"], texte


def test_l_eta_lit_le_preset_et_l_encodeur_de_la_decision(tmp_path):
    dec = _decision(tmp_path, "a.mkv", duree=6000.0, preset="fast")
    actif = {"test": Profile("test", {"preset_encoder": "slow"})}
    _st, _r, lignes, cles, _u = _ouvrir([dec], profils=actif)
    attendu = estimate_encoding_duration(6000.0, 8_000_000, 3_000_000,
                                         VideoAction.ENCODE_HEVC, "fast", None)
    assert lignes[0][_colonne(cles, "temps_estim")].plain == fmt_duration(attendu)

    # Une vitesse mesurée pour l'encodeur de la plateforme (libx265), et une
    # ancienne moyenne « hevc » faussée par des copies : seule la première vaut.
    vitesses = {"stats": {"encode_speed": {"hevc": 100.0, "libx265": 0.5}}}
    _st, _r, lignes, cles, _u = _ouvrir([dec], cfg=vitesses, profils=actif)
    assert lignes[0][_colonne(cles, "temps_estim")].plain == fmt_duration(12000)


def test_la_taille_des_sources_se_lit_une_fois(tmp_path, monkeypatch):
    lectures: list[Path] = []
    taille = VideoInfo.taille

    def _compter(info):
        lectures.append(info.path)
        return taille.fget(info)
    monkeypatch.setattr(VideoInfo, "taille", property(_compter))

    decisions = [_decision(tmp_path, "a.mkv"), _decision(tmp_path, "b.mkv")]
    _ouvrir(decisions, actions=[DryrunScreen.action_toggle_select] * 3)
    assert sorted(p.name for p in lectures) == ["a.mkv", "b.mkv"]
