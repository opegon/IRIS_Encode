"""
tests/test_encodage_sortie_outils.py — Lire les outils en UTF-8, pas en cp1252.

Un WebM déposé dans `resources_files` n'apparaissait pas dans la liste. Ni
l'extension ni le codec n'étaient en cause : le fichier portait un tag
`DESCRIPTION` contenant « ❤️ ». ffprobe écrit sa sortie en UTF-8 ; la lire avec
`text=True`, c'est-à-dire dans l'encodage local — cp1252 sur un Windows
français — fait lever `UnicodeDecodeError` **dans le thread de lecture** de
subprocess. L'exception n'y remonte pas jusqu'à l'appelant : `stdout` vaut
simplement `None`, `json.loads(None)` échoue, et `scan_directory` écarte le
fichier comme illisible. Aucun message, une ligne de moins dans le tableau.

Le même piège vise ffmpeg et mkvmerge, dont les sorties citent les noms de
fichiers : six sites étaient concernés.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
CŒUR = "❤️"   # hors cp1252 : c'est le caractère exact qui écartait le fichier


# ─── La garde statique ────────────────────────────────────────────────────────

def test_aucun_appel_ne_lit_dans_l_encodage_local():
    """`text=True` seul laisse Python choisir l'encodage de la machine.

    La garde est volontairement bête : elle interdit le motif plutôt que de
    juger au cas par cas. Un nouveau site qui lit du texte doit dire dans quel
    encodage, et `encoding=` l'impose sans qu'on ait à y penser.
    """
    fautifs = [
        f"{p.relative_to(RACINE)}:{n}"
        for p in (RACINE / "core").glob("*.py")
        for n, ligne in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(r"\btext\s*=\s*True", ligne)
    ]
    assert not fautifs, "lecture dans l'encodage local : " + ", ".join(fautifs)


def test_chaque_lecture_de_texte_nomme_son_encodage():
    """Tout appel qui décode nomme explicitement son encodage."""
    for rel in ("core/scanner.py", "core/muxer.py", "core/encoder.py",
                "core/preflight.py", "core/sync.py"):
        src = (RACINE / rel).read_text(encoding="utf-8")
        assert 'encoding="utf-8"' in src, rel


# ─── Le comportement, sur un vrai fichier ─────────────────────────────────────

@pytest.fixture(scope="module")
def ffmpeg() -> str:
    from core.config import get_bin_dir, load
    from core.preflight import get_tool_path
    chemin = get_tool_path("ffmpeg", get_bin_dir(load()))
    if not chemin:
        pytest.skip("ffmpeg introuvable")
    return chemin


def test_un_fichier_au_titre_hors_cp1252_est_bien_lu(tmp_path, ffmpeg):
    """Le cas réel, reproduit : sans le correctif, `scan` renvoie None."""
    from core import scanner
    from core.config import get_bin_dir, load
    from core.preflight import get_tool_path

    film = tmp_path / "clip.mkv"
    subprocess.run(
        [ffmpeg, "-v", "error", "-y",
         "-f", "lavfi", "-i", "testsrc=s=320x180:d=1:r=25",
         "-f", "lavfi", "-i", "sine=d=1",
         "-c:v", "libx264", "-c:a", "aac",
         "-metadata", f"DESCRIPTION=merci {CŒUR}",
         str(film)],
        capture_output=True, timeout=120, check=True)

    # Le tag doit vraiment être dans le fichier, sinon le test ne prouve rien.
    brut = subprocess.run([get_tool_path("ffprobe", get_bin_dir(load())),
                           "-v", "error", "-show_format", str(film)],
                          capture_output=True, timeout=30).stdout
    assert CŒUR.encode("utf-8") in brut, "le tag n'a pas survécu au muxage"

    scanner.set_ffprobe_path(get_tool_path("ffprobe", get_bin_dir(load())))
    info = scanner.scan(film)
    assert info is not None, "fichier écarté : sortie ffprobe mal décodée"
    assert info.width == 320 and info.audio_tracks


def test_le_repertoire_entier_ne_perd_pas_ce_fichier(tmp_path, ffmpeg):
    """`scan_directory` avale les erreurs par fichier : c'est précisément ce
    qui rendait la perte invisible. On vérifie donc le compte, pas le log."""
    from core import scanner
    from core.config import get_bin_dir, load
    from core.preflight import get_tool_path

    for nom, titre in (("sobre.mkv", "sans accent"), ("orne.mkv", f"na {CŒUR}")):
        subprocess.run(
            [ffmpeg, "-v", "error", "-y",
             "-f", "lavfi", "-i", "testsrc=s=320x180:d=1:r=25",
             "-c:v", "libx264", "-metadata", f"DESCRIPTION={titre}",
             str(tmp_path / nom)],
            capture_output=True, timeout=120, check=True)

    scanner.set_ffprobe_path(get_tool_path("ffprobe", get_bin_dir(load())))
    noms = {v.path.name for v in scanner.scan_directory(tmp_path)}
    assert noms == {"sobre.mkv", "orne.mkv"}
