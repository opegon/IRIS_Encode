"""
tests/test_assistant_recalage.py — Vérifier une mesure depuis l'assistant (IE-142).

Une mesure refusée laissait la piste à 0 avec « vérifiez avant de lancer »,
et l'assistant n'offrait aucun moyen de le faire ; une mesure acceptée mais
non sûre passait sans un mot. `R` ouvre désormais le recalage, pré-chargé du
dernier résultat.
"""
from __future__ import annotations

from types import SimpleNamespace

from core.i18n import _
from core.muxer import ExternalTrack, SyncOrigin, TrackKind
from core.sync import SyncResult
from tui.common import touche
from tui.screens import wizard as wizard_mod
from tui.screens.sync import SyncScreen
from tui.screens.wizard import Etape, WizardScreen, _ORDRE


def _refus(candidat: int = 260) -> SyncResult:
    return SyncResult(0, None, 0.12, False, "no common alignment",
                      best_delay_ms=candidat, floor=0.25, n_events=500,
                      speech_ratio=0.4)


def _a_verifier() -> SyncResult:
    """Acceptée, mais ni recoupée ni assez corrélée : `sure` est faux."""
    return SyncResult(300, None, 0.30, True, floor=0.25, n_events=500)


def _sure() -> SyncResult:
    return SyncResult(260, None, 0.86, True, floor=0.25, n_events=500,
                      cross_checked=True)


def _pistes(tmp_path) -> list[ExternalTrack]:
    return [
        ExternalTrack(source_path=tmp_path / "en.mp4", source_tid=1,
                      kind=TrackKind.AUDIO, language="eng"),
        ExternalTrack(source_path=tmp_path / "vf.mkv", source_tid=1,
                      kind=TrackKind.AUDIO, language="fre"),
    ]


# ─── Le recalage reprend la mesure de l'assistant ────────────────────────────

class _Table:
    def __init__(self):
        self.ligne = None

    def move_cursor(self, row):
        self.ligne = row


def _recalage(pistes, mesures, *, assistant=True):
    class _Faux(SyncScreen):
        app = SimpleNamespace(bell=lambda: None)

        def __init__(self):
            self._assistant = assistant
            self._mesures_initiales = mesures
            self._tracks = pistes
            self._candidate = None
            self._segments = None
            self.table = _Table()
            self.dits: list[str] = []

        def query_one(self, *_a, **_k):        return self.table
        def _set_hint(self, texte):            self.dits.append(texte)
        def _set_origin_cell(self, *a):        pass

    return _Faux()


def test_un_refus_rend_son_candidat_applicable_sans_remesurer(tmp_path):
    pistes = _pistes(tmp_path)
    e = _recalage(pistes, [(pistes[1], _refus(260))])
    e._reprendre_mesure()
    assert e._candidate == (pistes[1], 260)
    assert e.table.ligne == 1
    assert "+260" in e.dits[-1]


def test_le_refus_passe_avant_la_mesure_a_verifier(tmp_path):
    pistes = _pistes(tmp_path)
    e = _recalage(pistes, [(pistes[0], _a_verifier()), (pistes[1], _refus())])
    e._reprendre_mesure()
    assert e.table.ligne == 1 and e._candidate[0] is pistes[1]


def test_une_mesure_a_verifier_montre_son_compte_rendu(tmp_path):
    pistes = _pistes(tmp_path)
    e = _recalage(pistes, [(pistes[0], _a_verifier())])
    e._reprendre_mesure()
    assert e.table.ligne == 0 and e._candidate is None
    assert e.dits == [_a_verifier().report()]


def test_une_mesure_sure_ne_demande_rien(tmp_path):
    pistes = _pistes(tmp_path)
    e = _recalage(pistes, [(pistes[0], _sure())])
    e._reprendre_mesure()
    assert e.dits == [] and e.table.ligne is None


def test_une_piste_retiree_depuis_est_ignoree(tmp_path):
    pistes = _pistes(tmp_path)
    retiree = pistes.pop(1)
    e = _recalage(pistes, [(retiree, _refus())])
    e._reprendre_mesure()
    assert e._candidate is None and e.dits == []


def test_depuis_lassistant_ajouter_et_lancer_restent_a_lassistant(tmp_path):
    e = _recalage(_pistes(tmp_path), [])
    for action in ("run", "run_mux", "dryrun", "add_track"):
        assert e.check_action(action, ()) is False, action
    assert e.check_action("apply_candidate", ()) is True
    pied = {k for k, _l in e._actions_pied()}
    assert not pied & {"f1", "f2", "f3", "f9"}, pied
    assert {"f", "g", "r", "m"} <= pied


def test_hors_assistant_le_recalage_garde_toutes_ses_touches(tmp_path):
    e = _recalage(_pistes(tmp_path), [], assistant=False)
    assert e.check_action("run_mux", ()) is True
    assert {"f1", "f2", "f3", "f9"} <= {k for k, _l in e._actions_pied()}


# ─── L'assistant dit où vérifier, et garde les résultats ─────────────────────

def _assistant(pistes, app=None):
    class _Faux(WizardScreen):
        def __init__(self):
            self._dec = SimpleNamespace(
                external_tracks=pistes,
                info=SimpleNamespace(lecture="film.mkv", duration=6000.0))
            self._i = _ORDRE.index(Etape.PISTES)
            self._mesure = False
            self._resultats = []
            self.dit: list[str] = []
            self.affiche = 0

        def query_one(self, *_a, **_k):
            return SimpleNamespace(update=self.dit.append)

        def _jauge(self, *a, **k):
            pass

        def _afficher(self):
            self.affiche += 1

    _Faux.app = app or SimpleNamespace(call_from_thread=lambda f, *a: f(*a))
    return _Faux()


def _mesurer(monkeypatch, ecran, resultats):
    par_piste = dict(zip(map(id, ecran._dec.external_tracks), resultats))
    monkeypatch.setattr(wizard_mod, "measure_external_track",
                        lambda cible, t, **k: par_piste[id(t)])
    WizardScreen._travail_mesure.__wrapped__(
        ecran, list(range(len(ecran._dec.external_tracks))))


def test_un_refus_dit_quelle_touche_ouvre_le_recalage(tmp_path, monkeypatch):
    pistes = _pistes(tmp_path)[:1]
    e = _assistant(pistes)
    _mesurer(monkeypatch, e, [_refus()])
    renvoi = _("{key} to check").format(key=touche("r"))
    assert renvoi in e.dit[-1]
    assert pistes[0].delay_ms == 0
    assert e._resultats[0][0] is pistes[0]


def test_une_mesure_a_verifier_nest_plus_appliquee_en_silence(tmp_path, monkeypatch):
    pistes = _pistes(tmp_path)[:1]
    e = _assistant(pistes)
    _mesurer(monkeypatch, e, [_a_verifier()])
    assert pistes[0].delay_ms == 300
    assert _("{key} to check").format(key=touche("r")) in e.dit[-1]


def test_une_mesure_sure_ne_renvoie_nulle_part(tmp_path, monkeypatch):
    pistes = _pistes(tmp_path)[:1]
    e = _assistant(pistes)
    _mesurer(monkeypatch, e, [_sure()])
    assert _("{key} to check").format(key=touche("r")) not in e.dit[-1]


def test_r_ouvre_le_recalage_preCharge_et_oublie_ce_qui_a_ete_corrige(tmp_path):
    pistes = _pistes(tmp_path)
    ouverts = []
    app = SimpleNamespace(push_screen=lambda ecran, cb: ouverts.append((ecran, cb)))
    e = _assistant(pistes, app)
    refus, verif = _refus(), _a_verifier()
    pistes[1].sync_origin = SyncOrigin.MEASURED
    e._resultats = [(pistes[0], refus), (pistes[1], verif)]

    e.action_recaler()
    ecran, retour = ouverts[0]
    assert isinstance(ecran, SyncScreen)
    assert ecran._assistant is True
    assert ecran._mesures_initiales == e._resultats

    # Dans le recalage : candidat forcé sur la première, la seconde intacte
    pistes[0].sync_origin = SyncOrigin.MANUAL
    retour(pistes)
    assert e._resultats == [(pistes[1], verif)]
    assert e.affiche == 1


def test_r_sans_piste_ajoutee_renvoie_vers_f9(tmp_path):
    ouverts = []
    app = SimpleNamespace(push_screen=lambda *a: ouverts.append(a))
    e = _assistant([], app)
    e.action_recaler()
    assert not ouverts
    assert e.dit == [_("No track added yet — {key} to present a file.").format(
        key=touche("f9"))]
