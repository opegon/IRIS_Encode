"""
tests/test_revue_code.py — Les quatre constats de la revue du 2026-08-29.

Chaque test reproduit le défaut tel qu'il se produisait, pas une abstraction
de celui-ci. Deux d'entre eux (IE-38, IE-39) portent sur un travail long qui
se termine dans un monde qui a changé — une liste réordonnée, un fichier qu'un
autre thread écrit : la famille que cette passe ferme.
"""
from __future__ import annotations

import io
import threading
import time
import zipfile
from pathlib import Path

import pytest

from core import config as cfg_mod
from core import meta as meta_mod
from core import muxer as muxer_mod
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


# ─── IE-50 — profiles.toml : la parade d'IE-39, jamais portée ────────────────
#
# `save_all` et `_write_defaults` ouvraient en `"wb"` : tronquer, puis écrire.
# Une coupure à mi-course laisse un TOML invalide ; `load_all` avale l'erreur
# de syntaxe, avertit, et rend les seuls profils livrés. Tout ce que
# l'utilisateur a créé ou modifié est perdu, sans recours et sans qu'un
# redémarrage n'y change rien.
#
# Ces tests reprennent, à la lettre, ceux qu'IE-39 avait écrits pour
# `config.save` : le défaut est le même, et il doit se vérifier de la même
# façon aux deux endroits.

def _profils(prof_mod, ids: list[str]) -> dict:
    return {i: prof_mod.Profile(id=i, data={"bitrate_1080p_kbps": 5000},
                                user=True) for i in ids}


def test_profiles_ne_laisse_jamais_un_fichier_a_moitie_ecrit(tmp_path, monkeypatch):
    """L'écriture échoue en cours de route : l'ancien fichier doit survivre."""
    from core import profiles as prof_mod

    cible = tmp_path / "profiles.toml"
    cible.write_text('[mien]\nbitrate_1080p_kbps = 4200\n', encoding="utf-8")
    monkeypatch.setattr(prof_mod, "PROFILES_PATH", cible)

    def _dump_qui_meurt(data, f):
        f.write(b"[mien]\nbitra")          # à mi-course
        raise OSError("disque plein")

    monkeypatch.setattr(prof_mod.tomli_w, "dump", _dump_qui_meurt)
    with pytest.raises(OSError):
        prof_mod.save_all(_profils(prof_mod, ["mien", "autre"]))

    # Le fichier d'origine est intact, et toujours lisible
    assert cible.read_text(encoding="utf-8") == '[mien]\nbitrate_1080p_kbps = 4200\n'
    assert not list(tmp_path.glob("*.tmp")), "le provisoire doit être retiré"


def test_les_profils_de_l_utilisateur_survivent_a_une_ecriture_ratee(tmp_path,
                                                                     monkeypatch):
    """La conséquence réelle : ce sont ses profils, pas un réglage d'affichage."""
    from core import profiles as prof_mod

    cible = tmp_path / "profiles.toml"
    cible.write_text('[le_mien]\nbitrate_1080p_kbps = 4200\n', encoding="utf-8")
    monkeypatch.setattr(prof_mod, "PROFILES_PATH", cible)
    monkeypatch.setattr(prof_mod.tomli_w, "dump",
                        lambda d, f: (_ for _ in ()).throw(OSError("coupure")))
    with pytest.raises(OSError):
        prof_mod.save_all(_profils(prof_mod, ["le_mien"]))

    charges = prof_mod.load_all()
    assert "le_mien" in charges, "le profil personnel a disparu"
    assert charges["le_mien"].data["bitrate_1080p_kbps"] == 4200


def test_profiles_ecrit_bien_ce_quon_lui_donne(tmp_path, monkeypatch):
    """L'écriture atomique ne doit pas être atomique *et* fausse."""
    from core import profiles as prof_mod

    cible = tmp_path / "profiles.toml"
    monkeypatch.setattr(prof_mod, "PROFILES_PATH", cible)
    prof_mod.save_all(_profils(prof_mod, ["a", "b"]))

    relus = prof_mod.load_all()
    assert relus["a"].data["bitrate_1080p_kbps"] == 5000
    assert relus["b"].user is True


def test_profiles_est_serialise_entre_threads(tmp_path, monkeypatch):
    """Deux écrans peuvent enregistrer : le fichier ne doit jamais s'entrelacer."""
    from core import profiles as prof_mod

    cible = tmp_path / "profiles.toml"
    monkeypatch.setattr(prof_mod, "PROFILES_PATH", cible)

    dump_vrai = prof_mod.tomli_w.dump
    dedans    = []
    collisions = []

    def _dump_lent(data, f):
        dedans.append(1)
        if len(dedans) > 1:
            collisions.append(1)
        time.sleep(0.02)
        dump_vrai(data, f)
        dedans.pop()

    monkeypatch.setattr(prof_mod.tomli_w, "dump", _dump_lent)
    fils = [threading.Thread(target=prof_mod.save_all,
                             args=(_profils(prof_mod, [f"p{n}"]),))
            for n in range(6)]
    for t in fils:
        t.start()
    for t in fils:
        t.join()

    assert not collisions, "deux écritures se sont chevauchées"
    assert cible.exists()


# ─── IE-52 — une réserve sur un résultat accepté ─────────────────────────────
#
# `measure_audio` écrivait « durées écartées de N % » dans `reason` alors que
# `ok` est vrai. Or `reason` n'est lu que sur les échecs : `label()` ne le
# regarde que dans sa branche `if not self.ok`, `report()` n'y touche pas, et
# l'assistant non plus. Un donneur dont la durée s'écarte de plus de 6 % — donc
# un autre montage — était accepté sans que rien ne le signale nulle part.

def test_une_reserve_est_portee_par_un_champ_a_elle():
    """`reason` reste au refus ; une réserve sur un succès a son propre champ."""
    res = sync_mod._finish(lag=-249, ratio=(1, 1), conf=0.9, salience=90.0)
    assert res.ok
    assert hasattr(res, "warning") and res.warning == ""


def test_la_reserve_apparait_dans_le_compte_rendu():
    """C'est ce que lit l'écran de recalage — le seul endroit qui l'affichait pas."""
    res = sync_mod._finish(lag=-249, ratio=(1, 1), conf=0.9, salience=90.0)
    res.warning = "durées écartées de 12% — vérifiez qu'il s'agit bien du même montage"
    rapport = res.report()
    assert "durées écartées de 12%" in rapport
    assert rapport.startswith("⚠"), "un succès sous réserve n'est pas un ✓"


def test_un_succes_sans_reserve_reste_coche():
    res = sync_mod._finish(lag=-249, ratio=(1, 1), conf=0.9, salience=90.0)
    assert res.report().startswith("✓")
    assert "⚠" not in res.report().splitlines()[0]


def test_la_derive_de_duree_ecrit_dans_warning_pas_dans_reason(monkeypatch):
    """Le chemin réel : `measure_audio` sur deux durées trop écartées."""
    import numpy as np

    court = np.ones(4_000, dtype=np.float32)
    long_ = np.ones(12_000, dtype=np.float32)
    appels = iter([court, long_])
    monkeypatch.setattr(sync_mod, "_decode_envelope",
                        lambda *a, **k: next(appels))
    monkeypatch.setattr(sync_mod, "_finish",
                        lambda *a, **k: sync_mod.SyncResult(
                            delay_ms=0, stretch=None, confidence=0.9, ok=True))
    monkeypatch.setattr(sync_mod, "_search", lambda *a, **k: (0, (1, 1), 0.9, 90.0))
    monkeypatch.setattr(sync_mod, "_cross_validate", lambda *a, **k: (True, 0))

    res = sync_mod.measure_audio(Path("cible.mkv"), Path("donneur.mkv"))
    assert res.ok
    assert "écartées" in res.warning, res.warning
    assert res.reason == "", "une réserve dans `reason` n'atteint personne"


# ─── IE-51 — un réglage lu dans la mauvaise section ──────────────────────────
#
# `check_for_updates` lisait `check_on_startup` sous `[ffmpeg]`, alors que la
# clé vit sous `[updates]` — c'est là que `config._DEFAULTS` la pose, là que
# `config.toml` l'écrit, et là que la spec la documente. Le `.get(..., True)`
# retombait donc toujours sur le défaut : le réglage était mort, et
# l'utilisateur qui coupait la vérification pour éviter l'aller-retour réseau
# au lancement continuait de le payer.

def _cfg_sans_verification() -> dict:
    """La configuration telle que `config.load()` la rend, réglage coupé."""
    cfg = cfg_mod._deep_merge({}, cfg_mod._DEFAULTS)
    cfg["updates"]["check_on_startup"] = False
    return cfg


def test_couper_la_verification_la_coupe_vraiment(monkeypatch):
    touche_au_reseau = []
    monkeypatch.setattr(preflight, "_load_releases",
                        lambda: touche_au_reseau.append(1) or {})
    import core.updates as up_mod
    monkeypatch.setattr(up_mod, "load_cache",
                        lambda *a: touche_au_reseau.append(1) or None)
    monkeypatch.setattr(up_mod, "fetch_latest",
                        lambda *a, **k: touche_au_reseau.append(1) or {})

    preflight.check_for_updates(_cfg_sans_verification(), [], Path("bin"))
    assert not touche_au_reseau, "la vérification a tourné malgré le réglage"


def test_la_cle_vit_bien_dans_updates():
    """Le défaut venait de deux sections en désaccord : elles doivent l'être une."""
    assert "check_on_startup" in cfg_mod._DEFAULTS["updates"]
    assert "check_on_startup" not in cfg_mod._DEFAULTS["ffmpeg"]


def test_le_reglage_actif_laisse_passer(monkeypatch):
    """Le défaut reste `True` : ne rien écrire, c'est vérifier."""
    passages = []
    import core.updates as up_mod
    monkeypatch.setattr(up_mod, "load_cache", lambda *a: passages.append(1) or {})
    monkeypatch.setattr(up_mod, "pending", lambda *a: [])

    preflight.check_for_updates(cfg_mod._deep_merge({}, cfg_mod._DEFAULTS),
                                [], Path("bin"))
    assert passages, "avec le réglage à True, la vérification doit tourner"


# ─── IE-54 — la mise à jour doit ranger comme l'installation ─────────────────
#
# `_installer_for` appelait `_install_from_zip` en direct, sautant
# `install_dovi_tool` et son `zipfile.is_zipfile` — le garde-fou posé par
# IE-40 précisément parce que « certaines releases publient un ZIP, d'autres
# l'exécutable nu ». Sur une release en binaire nu, la mise à jour échouait à
# chaque lancement pendant qu'une installation neuve de la même release
# réussissait.

_BINAIRE_NU = b"MZ\x90\x00" + b"\x00" * 64          # pas un ZIP


def _zip_avec(nom: str) -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as z:
        z.writestr(f"dossier/{nom}", b"binaire")
    return tampon.getvalue()


def test_la_mise_a_jour_de_dovi_tool_accepte_un_binaire_nu(tmp_path, monkeypatch):
    """Le cas exact du défaut."""
    monkeypatch.setattr(preflight, "_download", lambda url, sha="": _BINAIRE_NU)
    installer = preflight._installer_for("dovi_tool")
    assert installer(tmp_path, "https://exemple/dovi_tool") is True
    pose = tmp_path / preflight._exe("dovi_tool")
    assert pose.exists() and pose.read_bytes() == _BINAIRE_NU


def test_la_mise_a_jour_de_dovi_tool_accepte_toujours_un_zip(tmp_path, monkeypatch):
    """L'autre forme ne doit pas régresser en réparant la première."""
    cible = preflight._exe("dovi_tool")
    monkeypatch.setattr(preflight, "_download", lambda url, sha="": _zip_avec(cible))
    installer = preflight._installer_for("dovi_tool")
    assert installer(tmp_path, "https://exemple/dovi_tool.zip") is True
    assert (tmp_path / cible).exists()


def test_installation_et_mise_a_jour_rangent_pareil(tmp_path, monkeypatch):
    """L'invariant, pas le symptôme : un même contenu, un même résultat."""
    monkeypatch.setattr(preflight, "_download", lambda url, sha="": _BINAIRE_NU)

    par_installation = tmp_path / "neuf"
    par_mise_a_jour  = tmp_path / "maj"
    preflight.install_dovi_tool(
        par_installation, {"dovi_tool": {"windows": {"url": "u"},
                                         "linux":   {"url": "u"}}})
    preflight._installer_for("dovi_tool")(par_mise_a_jour, "u")

    exe = preflight._exe("dovi_tool")
    assert (par_installation / exe).read_bytes() == (par_mise_a_jour / exe).read_bytes()


def test_un_telechargement_rate_ne_devient_pas_une_archive_vide(tmp_path,
                                                                monkeypatch):
    """`_download(url) or b""` remettait des octets vides à l'extracteur."""
    monkeypatch.setattr(preflight, "_download", lambda url, sha="": None)
    for outil in sorted(preflight.OUTILS_INSTALLABLES):
        assert preflight._installer_for(outil)(tmp_path, "u") is False, outil


@pytest.mark.parametrize("outil", sorted({"ffmpeg", "mkvmerge", "dovi_tool", "mpv"}))
def test_tout_outil_installable_a_sa_mise_a_jour(outil):
    assert preflight._installer_for(outil) is not None


def test_un_outil_inconnu_n_a_pas_d_installateur():
    """ffprobe suit ffmpeg : il n'a pas de mise à jour propre."""
    assert preflight._installer_for("ffprobe") is None


# ─── IE-56 — les versions se relèvent en parallèle ───────────────────────────
#
# `_get_version` essaie `-version` puis `--version`, 5 s de délai chacun ;
# mkvmerge et dovi_tool échouent sur le premier. En série, un démarrage payait
# jusqu'à dix lancements de sous-processus l'un après l'autre — et
# `check_tools` repasse une seconde fois après une installation de ffmpeg.

def test_les_versions_sont_relevees_en_parallele(tmp_path, monkeypatch):
    """Cinq relevés à 100 ms doivent tenir bien en deçà de leur somme."""
    for nom in preflight.ALL_TOOLS:
        (tmp_path / preflight._exe(nom)).write_bytes(b"")
    monkeypatch.setattr(preflight.shutil, "which", lambda _n: None)

    def _lent(_chemin):
        time.sleep(0.1)
        return "1.0"

    monkeypatch.setattr(preflight, "_get_version", _lent)
    debut = time.monotonic()
    statuses = preflight.check_tools(tmp_path)
    ecoule = time.monotonic() - debut

    assert all(s.version == "1.0" for s in statuses)
    assert ecoule < 0.3, (
        f"{ecoule:.2f} s pour cinq relevés de 100 ms — ils sont encore en série")


def test_l_ordre_et_le_contenu_ne_changent_pas(tmp_path, monkeypatch):
    """La parallélisation ne doit rien réordonner : l'appelant lit par rang."""
    for nom in ("ffmpeg", "mkvmerge"):
        (tmp_path / preflight._exe(nom)).write_bytes(b"")
    monkeypatch.setattr(preflight.shutil, "which", lambda _n: None)
    monkeypatch.setattr(preflight, "_get_version", lambda c: "9.9")

    statuses = preflight.check_tools(tmp_path)
    assert [s.name for s in statuses] == list(preflight.ALL_TOOLS)
    par_nom = {s.name: s for s in statuses}
    assert par_nom["ffmpeg"].found and par_nom["ffmpeg"].version == "9.9"
    assert par_nom["mkvmerge"].found
    assert not par_nom["mpv"].found
    assert par_nom["mpv"].version == "" and par_nom["mpv"].path is None


def test_aucun_outil_trouve_ne_fait_pas_planter_le_pool(tmp_path, monkeypatch):
    """`ThreadPoolExecutor(max_workers=0)` lève : le cas doit être écarté."""
    monkeypatch.setattr(preflight.shutil, "which", lambda _n: None)
    statuses = preflight.check_tools(tmp_path / "vide")
    assert len(statuses) == len(preflight.ALL_TOOLS)
    assert not any(s.found for s in statuses)


# ─── IE-53 — le genre tronqué à cinq caractères ──────────────────────────────
#
# `data.get("genre", [])[:5]` s'appliquait **avant** l'`isinstance(genres, str)`
# qui suit. AlloCiné rend une chaîne nue quand le film n'a qu'un genre :
# « Science fiction »[:5] vaut « Scien », que la normalisation emballe ensuite
# consciencieusement en `["Scien"]`.
#
# Le casting, dix lignes plus haut dans la même fonction, faisait déjà les deux
# dans le bon ordre — c'est ce voisinage qui rend le défaut lisible.

_AUTOCOMPLETE = {"results": [{"entity_id": 1, "entity_type": "movie",
                              "label": "Le Film (2017)"}]}


def _fiche(genre) -> str:
    import json as _json
    ld = {"name": "Le Film", "genre": genre,
          "director": {"name": "Untel"}, "actor": [{"name": "Machin"}]}
    return ('<html><script type="application/ld+json">'
            + _json.dumps(ld) + "</script></html>")


class _Reponse:
    def __init__(self, charge):
        self._charge = charge
        self.text = charge if isinstance(charge, str) else ""

    def raise_for_status(self):
        pass

    def json(self):
        return self._charge


def _meta_avec_genre(monkeypatch, genre):
    import requests

    reponses = iter([_Reponse(_AUTOCOMPLETE), _Reponse(_fiche(genre))])
    monkeypatch.setattr(requests, "get", lambda *a, **k: next(reponses))
    return meta_mod.fetch_allocine("Le Film")


def test_un_genre_en_chaine_nue_nest_pas_tronque(monkeypatch):
    """Le cas signalé : AlloCiné rend une chaîne pour un genre unique."""
    m = _meta_avec_genre(monkeypatch, "Science fiction")
    assert m.genres == ["Science fiction"], m.genres


def test_un_genre_court_passait_deja(monkeypatch):
    """« Drame » fait cinq caractères : le défaut y était invisible."""
    m = _meta_avec_genre(monkeypatch, "Drame")
    assert m.genres == ["Drame"]


def test_une_liste_de_genres_reste_coupee_a_cinq(monkeypatch):
    """La limite existe pour l'affichage : la réparer ne doit pas la lever."""
    m = _meta_avec_genre(monkeypatch, [f"g{n}" for n in range(9)])
    assert m.genres == [f"g{n}" for n in range(5)]


def test_pas_de_genre_du_tout(monkeypatch):
    m = _meta_avec_genre(monkeypatch, [])
    assert m.genres == []


# ─── IE-55 — un mkvmerge par index de piste à traduire ───────────────────────
#
# `build_strip_command` traduit un index par piste retenue, et chaque
# traduction relançait `mkvmerge -J` : six pistes audio et vingt sous-titres
# coûtaient 26 processus, timeout de 30 s chacun, sur le même fichier — qui ne
# change pas entre deux.

def _mkvmerge_factice(monkeypatch, compteur: list):
    """Remplace le sous-processus par un JSON constant, et compte les appels."""
    import json as _json

    charge = _json.dumps({"tracks": [
        {"id": 0, "type": "video",     "codec": "HEVC", "properties": {}},
        {"id": 1, "type": "audio",     "codec": "AC3",
         "properties": {"language": "fre"}},
        {"id": 2, "type": "audio",     "codec": "AC3",
         "properties": {"language": "eng"}},
        {"id": 3, "type": "subtitles", "codec": "SubRip",
         "properties": {"language": "fre"}},
    ]})

    class _R:
        returncode = 0
        stdout = charge

    def _run(*a, **k):
        compteur.append(1)
        return _R()

    monkeypatch.setattr(muxer_mod.subprocess, "run", _run)


def test_identify_ne_relit_pas_un_fichier_inchange(tmp_path, monkeypatch):
    appels: list = []
    _mkvmerge_factice(monkeypatch, appels)
    muxer_mod._CACHE_IDENTIFY.clear()

    f = tmp_path / "donneur.mkv"
    f.write_bytes(b"contenu")
    for _ in range(10):
        assert len(muxer_mod.identify(f)) == 3
    assert len(appels) == 1, f"{len(appels)} lancements de mkvmerge pour un fichier"


def test_traduire_vingt_index_ne_coute_quun_processus(tmp_path, monkeypatch):
    """Le cas réel : une commande de remux traduit index après index."""
    appels: list = []
    _mkvmerge_factice(monkeypatch, appels)
    muxer_mod._CACHE_IDENTIFY.clear()

    f = tmp_path / "source.mkv"
    f.write_bytes(b"contenu")
    for i in range(20):
        muxer_mod.mkvmerge_tid(f, i % 2, muxer_mod.TrackKind.AUDIO)
        muxer_mod.ffmpeg_stream_index(f, 1, muxer_mod.TrackKind.AUDIO)
    assert len(appels) == 1, f"{len(appels)} lancements pour 40 traductions"


def test_un_fichier_modifie_est_relu(tmp_path, monkeypatch):
    """La clé porte taille et date : un donneur remplacé ne doit pas coller."""
    appels: list = []
    _mkvmerge_factice(monkeypatch, appels)
    muxer_mod._CACHE_IDENTIFY.clear()

    f = tmp_path / "donneur.mkv"
    f.write_bytes(b"court")
    muxer_mod.identify(f)
    f.write_bytes(b"un contenu nettement plus long")
    muxer_mod.identify(f)
    assert len(appels) == 2, "le fichier a changé, il devait être relu"


def test_deux_fichiers_ne_se_melangent_pas(tmp_path, monkeypatch):
    appels: list = []
    _mkvmerge_factice(monkeypatch, appels)
    muxer_mod._CACHE_IDENTIFY.clear()

    for nom in ("a.mkv", "b.mkv"):
        (tmp_path / nom).write_bytes(b"contenu")
        muxer_mod.identify(tmp_path / nom)
    assert len(appels) == 2


def test_un_resultat_vide_nest_pas_memorise(tmp_path, monkeypatch):
    """C'est aussi ce que rend un mkvmerge absent : l'installer doit suffire."""
    muxer_mod._CACHE_IDENTIFY.clear()
    f = tmp_path / "muet.mkv"
    f.write_bytes(b"contenu")

    monkeypatch.setattr(muxer_mod.subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("absent")))
    assert muxer_mod.identify(f) == []

    appels: list = []
    _mkvmerge_factice(monkeypatch, appels)
    assert len(muxer_mod.identify(f)) == 3, "l'échec a été mémorisé"


def test_changer_d_executable_vide_le_cache(tmp_path, monkeypatch):
    appels: list = []
    _mkvmerge_factice(monkeypatch, appels)
    muxer_mod._CACHE_IDENTIFY.clear()

    f = tmp_path / "donneur.mkv"
    f.write_bytes(b"contenu")
    muxer_mod.identify(f)
    muxer_mod.set_mkvmerge_path("/autre/mkvmerge")
    muxer_mod.identify(f)
    assert len(appels) == 2, "le cache venait de l'exécutable précédent"


def test_le_cache_ne_se_laisse_pas_muter_par_l_appelant(tmp_path, monkeypatch):
    appels: list = []
    _mkvmerge_factice(monkeypatch, appels)
    muxer_mod._CACHE_IDENTIFY.clear()

    f = tmp_path / "donneur.mkv"
    f.write_bytes(b"contenu")
    pistes = muxer_mod.identify(f)
    pistes.clear()
    assert len(muxer_mod.identify(f)) == 3


# ─── IE-57 — un prédicat, un nom ─────────────────────────────────────────────
#
# `hdr10_quality_check` et `hdr10_quality` étaient la même expression à trois
# termes, mot pour mot, dans la même fonction. Deux noms pour un prédicat,
# c'est une modification future à faire aux deux endroits : en manquer un
# désynchronise la décision `hwaccel` du choix de l'encodeur.

def test_le_predicat_hdr10_nest_ecrit_quune_fois():
    """Structurel : c'est la duplication qui est le défaut, pas sa valeur."""
    source = (Path(__file__).resolve().parent.parent / "core" / "encoder.py"
              ).read_text(encoding="utf-8")
    assert source.count('profile.get("hdr10_quality") == "quality"') == 1, (
        "l'expression est écrite plusieurs fois — c'est ce qui permet de n'en "
        "modifier qu'une")


def test_le_mode_quality_choisit_libx265_et_refuse_le_hwaccel(tmp_path):
    """Le comportement que la désynchronisation aurait cassé."""
    cmd = _commande_hdr10(tmp_path, "quality")
    assert cmd[cmd.index("-c:v") + 1] == "libx265"
    assert "-hwaccel" not in cmd, "hwaccel passé à un encodage processeur"


def test_le_mode_compat_garde_le_hwaccel_et_nvenc(tmp_path):
    """L'autre branche : les deux décisions doivent basculer ensemble."""
    cmd = _commande_hdr10(tmp_path, "compat")
    assert cmd[cmd.index("-c:v") + 1] == "hevc_nvenc"
    assert "-hwaccel" in cmd, "hwaccel retiré à un encodage matériel"


def _commande_hdr10(tmp_path, mode: str) -> list[str]:
    from core.decision import decide
    from core.encoder import build_command
    from core.platform import GPU, OS, PlatformProfile
    from core.profiles import Profile
    from core.scanner import AudioTrack, VideoInfo

    p = tmp_path / "film.mkv"
    p.write_bytes(b"")
    info = VideoInfo(
        path=p, width=3840, height=2160, bitrate=12_000_000, codec="hevc",
        duration=8000.0, frame_count=0, dv_profile=8, dv_bl_compat=1,
        color_transfer="smpte2084", frame_rate="24/1",
        audio_tracks=[AudioTrack(index=0, codec="eac3", channels=6,
                                 language="fre", title="", bitrate=640_000)],
        subtitle_tracks=[])
    profil = Profile(id="test", data={
        "bitrate_720p_kbps": 2000, "bitrate_1080p_kbps": 5000,
        "bitrate_4k_kbps": 8000, "audio_languages": ["fre"], "keep_4k": True,
        "audio_copy_compatible": True, "preserve_hd_audio": False,
        "hdr10_quality": mode})
    plat = PlatformProfile(os=OS.WINDOWS, gpu=GPU.NVIDIA, hwaccel="cuda",
                           encoder_hevc="hevc_nvenc", encoder_h264="h264_nvenc",
                           encoder_av1="av1_nvenc")
    return build_command(decide(info, profil), plat)
