"""Ecart d'entrelacement video/audio, mesure par sondages le long du fichier."""
import json, subprocess, sys
from core.config import load, get_bin_dir
from core.preflight import get_tool_path

FP = get_tool_path("ffprobe", get_bin_dir(load()))

def mesure(chemin, points):
    pires = []
    for t in points:
        r = subprocess.run(
            [FP, "-v", "error", "-print_format", "json",
             "-read_intervals", f"{t}%+3", "-show_packets",
             "-show_entries", "packet=codec_type,pos", chemin],
            capture_output=True, encoding="utf-8", errors="replace")
        pk = [x for x in json.loads(r.stdout)["packets"] if "pos" in x]
        v = [int(x["pos"]) for x in pk if x["codec_type"] == "video"]
        a = [int(x["pos"]) for x in pk if x["codec_type"] == "audio"]
        if not v or not a:
            print(f"  t={t:5}s   pas de paquet des deux types ({len(v)} v, {len(a)} a)")
            continue
        ecart = max(abs(min(v) - min(a)), abs(max(v) - max(a)))
        pires.append(ecart)
        print(f"  t={t:5}s   ecart {ecart/1e6:8.1f} Mo   ({len(v)} v, {len(a)} a)")
    if pires:
        print(f"  --> pire ecart : {max(pires)/1e6:.1f} Mo")
    return max(pires) if pires else None

if __name__ == "__main__":
    chemin = sys.argv[1]
    duree = float(json.loads(subprocess.run(
        [FP, "-v", "error", "-print_format", "json", "-show_format", chemin],
        capture_output=True, encoding="utf-8", errors="replace").stdout)["format"]["duration"])
    pts = [int(duree * f) for f in (0.01, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.98)]
    print(f"  {chemin.split(chr(92))[-1][:60]}  ({duree/60:.1f} min)")
    mesure(chemin, pts)
