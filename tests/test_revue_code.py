"""
tests/test_revue_code.py — Les quatre constats de la revue du 2026-08-29.

Chaque test reproduit le défaut tel qu'il se produisait, pas une abstraction
de celui-ci. Deux d'entre eux (IE-38, IE-39) portent sur un travail long qui
se termine dans un monde qui a changé — une liste réordonnée, un fichier qu'un
autre thread écrit : la famille que cette passe ferme.
"""
from __future__ import annotations

import threading
import time
import zipfile
from pathlib import Path

import pytest

from core import config as cfg_mod
from core import preflight
from core import sync as sync_mod
from core.muxer import ExternalTrack, TrackKind


# ─── IE-38 — la mesure vit sur la piste, pas sur son rang ─────────────────────

def _piste(nom: str, tid: int = 0) -> ExternalTrack:
    return ExternalTrack(source_path=Path(f"{nom}.mkv"), source_tid=tid,
                         kind=TrackKind.AUDIO, codec="ac3", language="fre")


class _EcranFactice:
    """Le strict nécessaire de SyncScreen pour exercer `_rang`.

    Instancier l'écran demanderait une application Textual ; ce qu'on vérifie
    ici est une règle d'identité, qui n'a besoin que de la liste.
    """

    def __init__(self, tracks):
        self._tracks = tracks

    def _rang(self, piste):
        # Résolu à l'appel, pas à l'import : un module de test qui explose à la
        # collecte emporte avec lui les tests des trois autres constats.
        from tui.screens.sync import SyncScreen
        return SyncScreen._rang(self, piste)


def test_le_rang_suit_la_piste_quand_la_liste_bouge():
    a, b, c = _piste("a"), _piste("b"), _piste("c")
    ecran = _EcranFactice([a, b, c])
    assert ecran._rang(b) == 1
    ecran._tracks.remove(a)              # `D` sur la première piste
    assert ecran._rang(b) == 0, "le rang doit suivre la piste, pas l'inverse"
    assert ecran._rang(c) == 1


def test_une_piste_retiree_na_plus_de_rang():
    """Le résultat d'une mesure doit alors être jeté, pas écrit ailleurs."""
    a, b = _piste("a"), _piste("b")
    ecran = _EcranFactice([a, b])
    ecran._tracks.remove(a)
    assert ecran._rang(a) is None


def test_le_rang_compare_par_identite_pas_par_egalite():
    """
    Deux pistes du même fichier sont égales au sens du dataclass.

    Sans comparaison par identité, une mesure lancée sur la seconde
    s'appliquerait à la première — le défaut d'origine, déplacé.
    """
    a, jumelle = _piste("meme"), _piste("meme")
    assert a == jumelle, "prémisse du test : le dataclass les dit égales"
    ecran = _EcranFactice([a, jumelle])
    assert ecran._rang(jumelle) == 1


def test_quitter_pendant_une_mesure_est_refuse():
    """
    `dismiss` rend la liste à l'écran des pistes, qui la tient pour validée.

    Un worker encore en vol écrirait dedans après cette validation. Les cinq
    autres actions longues refusaient déjà ; celle qui sort de l'écran non.
    """
    from tui.screens.sync import SyncScreen

    class _Faux(SyncScreen):
        def __init__(self):                    # pas d'app Textual ici
            self._measuring = True
            self._tracks = []
            self.dits: list[str] = []
            self.rendu = False

        def _set_hint(self, texte):  self.dits.append(texte)
        def dismiss(self, *a, **k):  self.rendu = True

    e = _Faux()
    e.action_go_back()
    assert not e.rendu, "l'écran ne doit pas se fermer pendant une mesure"
    assert e.dits and "Mesure en cours" in e.dits[0]

    e._measuring = False
    e.action_go_back()
    assert e.rendu, "hors mesure, le retour doit fonctionner"


# ─── IE-39 — config.toml : écriture atomique ─────────────────────────────────

def test_save_ne_laisse_jamais_un_fichier_a_moitie_ecrit(tmp_path, monkeypatch):
    """
    L'écriture directe tronquait avant d'écrire.

    On fait échouer la sérialisation à mi-course : le fichier d'origine doit
    être intact, et aucun `.tmp` ne doit rester derrière.
    """
    cible = tmp_path / "config.toml"
    cible.write_bytes(b'[app]\nlanguage = "fr"\n')
    avant = cible.read_bytes()
    monkeypatch.setattr(cfg_mod, "CONFIG_PATH", cible)

    def _explose(cfg, f):
        f.write(b"[app]\n")                 # écriture partielle, puis panne
        raise OSError("disque plein")

    monkeypatch.setattr(cfg_mod.tomli_w, "dump", _explose)
    with pytest.raises(OSError):
        cfg_mod.save({"app": {"language": "fr"}})

    assert cible.read_bytes() == avant, "la configuration a été abîmée"
    assert not list(tmp_path.glob("*.tmp")), "un fichier provisoire est resté"


def test_save_ecrit_bien_ce_quon_lui_donne(tmp_path, monkeypatch):
    """L'atomicité ne doit pas se payer d'un contenu faux."""
    cible = tmp_path / "config.toml"
    monkeypatch.setattr(cfg_mod, "CONFIG_PATH", cible)
    cfg_mod.save({"app": {"language": "fr"}, "stats": {"encode_speed": {}}})
    assert cfg_mod.tomllib.loads(cible.read_text(encoding="utf-8")) == {
        "app": {"language": "fr"}, "stats": {"encode_speed": {}}}


def test_save_est_serialise_entre_threads(tmp_path, monkeypatch):
    """
    Le worker d'encodage et le thread d'interface écrivent tous deux.

    Sans verrou, deux `dump` s'entrelacent dans le même fichier. On compte les
    recouvrements plutôt que d'espérer les voir — mais un `dump` réel dure
    quelques microsecondes, et huit threads peuvent se croiser sans jamais se
    superposer. La pause rend le chevauchement **certain** en l'absence de
    verrou : sans elle, le test passait aussi sur le code défectueux, et ne
    prouvait donc rien.
    """
    cible = tmp_path / "config.toml"
    monkeypatch.setattr(cfg_mod, "CONFIG_PATH", cible)
    dedans = 0
    chevauchements = 0
    garde = threading.Lock()
    vrai_dump = cfg_mod.tomli_w.dump

    def _lent(cfg, f):
        nonlocal dedans, chevauchements
        with garde:
            dedans += 1
            if dedans > 1:
                chevauchements += 1
        time.sleep(0.02)
        vrai_dump(cfg, f)
        time.sleep(0.02)
        with garde:
            dedans -= 1

    monkeypatch.setattr(cfg_mod.tomli_w, "dump", _lent)
    fils = [threading.Thread(target=cfg_mod.save,
                             args=({"app": {"language": f"l{n}"}},))
            for n in range(8)]
    for t in fils:
        t.start()
    for t in fils:
        t.join()
    assert chevauchements == 0
    assert cible.exists()


# ─── IE-40 — le repli d'installation ─────────────────────────────────────────

def test_un_zip_illisible_nest_pas_ecrit_sous_le_nom_dun_executable(tmp_path,
                                                                    monkeypatch):
    """
    Le défaut : `except Exception: pass` autour de l'extraction, puis repli.

    Une erreur pendant l'extraction — disque plein, antivirus — faisait écrire
    les octets du ZIP dans `dovi_tool.exe`, en annonçant « ✓ Installé ». Ici
    l'extraction échoue ; le repli ne doit pas se déclencher.
    """
    tampon = tmp_path / "z.zip"
    with zipfile.ZipFile(tampon, "w") as z:
        z.writestr("dovi_tool.exe", b"MZ vrai binaire")
    octets = tampon.read_bytes()

    monkeypatch.setattr(preflight, "_download", lambda url: octets)
    monkeypatch.setattr(preflight, "_install_from_zip",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("disque plein")))
    bin_dir = tmp_path / "bin"
    releases = {"dovi_tool": {"windows": {"url": "http://x/z.zip"},
                              "linux":   {"url": "http://x/z.zip"}}}
    with pytest.raises(OSError):
        preflight.install_dovi_tool(bin_dir, releases)
    ecrit = list(bin_dir.glob("dovi_tool*")) if bin_dir.exists() else []
    assert not ecrit, f"un fichier a été écrit malgré l'échec : {ecrit}"


def test_un_binaire_nu_reste_installe_directement(tmp_path, monkeypatch):
    """Le repli garde sa raison d'être : certaines releases ne sont pas zippées."""
    octets = b"MZ\x90\x00 binaire nu"
    monkeypatch.setattr(preflight, "_download", lambda url: octets)
    bin_dir = tmp_path / "bin"
    releases = {"dovi_tool": {"windows": {"url": "http://x/dovi_tool.exe"},
                              "linux":   {"url": "http://x/dovi_tool"}}}
    assert preflight.install_dovi_tool(bin_dir, releases)
    produit = next(bin_dir.glob("dovi_tool*"))
    assert produit.read_bytes() == octets


# ─── IE-41 — un ffmpeg mort ne passe plus pour un film court ─────────────────

def test_un_decodage_interrompu_ne_rend_pas_une_enveloppe_partielle(monkeypatch):
    """
    `proc.wait()` était appelé sans regarder le code retour.

    La corrélation prenait alors le fragment décodé pour le film entier, et le
    recoupement par tiers ne rattrape pas une amputation de quelques minutes.
    """
    class _Flux:
        def __init__(self):
            self._reste = [b"\x01\x00" * sync_mod._BIN_SAMPLES * 8, b""]

        def read(self, _n):
            return self._reste.pop(0) if self._reste else b""

    class _Proc:
        def __init__(self, code):
            self.stdout = _Flux()
            self._code  = code
            self.tue    = False

        def wait(self):      return self._code
        def kill(self):      self.tue = True

    for code, attendu in ((0, True), (1, False)):
        monkeypatch.setattr(sync_mod.subprocess, "Popen",
                            lambda *a, **k: _Proc(code))
        env = sync_mod._decode_envelope(Path("film.mkv"), 0, None, 0)
        assert (env.size > 0) is attendu, f"code {code} : taille {env.size}"


def test_une_exception_dans_la_boucle_ne_laisse_pas_ffmpeg_orphelin(monkeypatch):
    """Un ffmpeg oublié décode un film entier pour personne."""
    temoin = {}

    class _FluxCasse:
        def read(self, _n):
            raise KeyboardInterrupt("l'utilisateur coupe")

    class _Proc:
        stdout = _FluxCasse()

        def wait(self):  return 0

        def kill(self):  temoin["tue"] = True

    monkeypatch.setattr(sync_mod.subprocess, "Popen", lambda *a, **k: _Proc())
    with pytest.raises(KeyboardInterrupt):
        sync_mod._decode_envelope(Path("film.mkv"), 0, None, 0)
    assert temoin.get("tue"), "le processus ffmpeg n'a pas été tué"


def test_le_decodage_ne_repose_plus_sur_un_assert():
    """`python -O` retire les `assert` : le déréférencement suivrait."""
    import inspect
    src = inspect.getsource(sync_mod._decode_envelope)
    assert "assert proc.stdout" not in src
    assert "if proc.stdout is None" in src


# ─── IE-58 — aucun sous-processus n'hérite de l'entrée du terminal ───────────
#
# ffmpeg lit l'entrée standard pour son clavier interactif : `q` l'arrête,
# `+`/`-` changent son niveau de verbosité. Sans redirection il hérite de celle
# du terminal — que l'interface Textual est en train d'écouter. Les deux se
# disputent alors les frappes : celles que ffmpeg attrape ne parviennent jamais
# à l'écran, et un `q` de passage tue l'encodage en cours.
#
# `EncoderProcess`, `MuxProcess` et `preview.launch` fermaient `stdin` ; les
# treize autres lancements du projet, non. La règle vaut pour tous, y compris
# ceux dont l'outil ne lit pas l'entrée aujourd'hui : aucun ne s'en sert, et
# c'est ce qui rend la règle vérifiable — donc tenable.
#
# Ce test est structurel à dessein. Le défaut n'est pas dans un chemin
# d'exécution, il est dans ce qu'un appel **omet** ; seule une lecture du source
# le voit, et c'est ce qui empêche le prochain lancement de repartir sans.

import ast

_LANCEURS = ("subprocess.run", "subprocess.Popen")


def _appels_sans_stdin(fichier: Path) -> list[int]:
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    return [n.lineno for n in ast.walk(arbre)
            if isinstance(n, ast.Call)
            and ast.unparse(n.func) in _LANCEURS
            and "stdin" not in {k.arg for k in n.keywords}]


def _sources() -> list[Path]:
    racine = Path(__file__).resolve().parent.parent
    return sorted(racine.glob("core/*.py")) + sorted(racine.glob("tui/**/*.py"))


def test_tout_lancement_ferme_son_entree_standard():
    fautifs = {f.name: lignes for f in _sources()
               if (lignes := _appels_sans_stdin(f))}
    assert not fautifs, (
        f"lancements sans `stdin=` : {fautifs}. Un sous-processus qui hérite de "
        f"l'entrée du terminal dispute ses frappes à l'interface.")


def test_le_test_verrait_un_lancement_nu():
    """Le garde-fou du garde-fou : vérifier qu'il ne passe pas sur du vide."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "faux.py"
        f.write_text("import subprocess\n"
                     "subprocess.run(['ffmpeg'], capture_output=True)\n",
                     encoding="utf-8")
        assert _appels_sans_stdin(f) == [2]


def test_les_lancements_sont_bien_trouves():
    """Et qu'il regarde bien là où les lancements sont."""
    total = sum(
        sum(1 for n in ast.walk(ast.parse(f.read_text(encoding="utf-8")))
            if isinstance(n, ast.Call) and ast.unparse(n.func) in _LANCEURS)
        for f in _sources())
    assert total >= 16, f"seulement {total} lancements vus — le balayage a dérivé"
