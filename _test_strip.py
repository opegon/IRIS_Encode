"""Rejoue le chemin STRIP_DV de tui/screens/run.py, hors interface."""
import pathlib, subprocess, sys, time
from core import decision as dm, dovi, muxer, profiles, scanner, encoder
from core.config import get_bin_dir, load
from core.decision import decide
from core.encoder import audio_pass_needed, build_audio_command
from core.muxer import build_strip_command
from core.preflight import get_tool_path

cfg = load(); bd = get_bin_dir(cfg)
ffmpeg = get_tool_path("ffmpeg", bd)
scanner.set_dovi_path(dovi.get_path(bd))
scanner.set_ffprobe_path(get_tool_path("ffprobe", bd))
muxer.set_mkvmerge_path(get_tool_path("mkvmerge", bd))
encoder.set_ffmpeg_path(ffmpeg)
dm.set_strip_dv_available(True)

info = scanner.scan(pathlib.Path("resources_files") / sys.argv[1])
dec  = decide(info, profiles.load_all()["cinema_4k_basic"])
src, out = info.path, dec.output_path
brut = src.with_name(f"{src.stem}.iris_bl.hevc")
nodv = src.with_name(f"{src.stem}.iris_nodv.hevc")
mka  = src.with_name(f"{src.stem}.iris_audio.mka")
passe = dec.output_container != ".mp4" and audio_pass_needed(dec.audio)
n = 4 if passe else 3

def etape(n, titre, cmd):
    print(f"\n== {n} {titre}\n   {' '.join(str(c) for c in cmd)[:200]}", flush=True)
    t = time.time()
    r = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
    print(f"   rc={r.returncode}  {time.time()-t:.0f}s", flush=True)
    if r.returncode != 0:
        print("\n".join((r.stderr or r.stdout or "").splitlines()[-8:]), flush=True)
        sys.exit(1)

try:
    etape(f"1/{n}", "extraction du flux HEVC",
          dovi.build_extract_hevc_command(src, brut, ffmpeg, quiet=False))
    print(f"   -> {brut.stat().st_size/1e9:.2f} Go", flush=True)

    etape(f"2/{n}", "retrait du RPU",
          [dovi.get_path(bd), "remove", "-i", str(brut), "-o", str(nodv)])
    print(f"   -> {nodv.stat().st_size/1e9:.2f} Go", flush=True)

    if passe:
        etape("3/4", "transcodage audio",
              build_audio_command(src, mka, dec.audio, ffmpeg))
        print(f"   -> {mka.stat().st_size/1e9:.2f} Go", flush=True)

    exclues = [a for a in dec.audio if a.action == dm.AudioAction.EXCLUDE]
    etape(f"{n}/{n}", "remux mkvmerge",
          build_strip_command(
              nodv, src, out, fps=info.frame_rate, tracks=dec.external_tracks,
              audio_source=mka if passe else None,
              audio_indices=([a.track.index for a in dec.audio
                              if a.action != dm.AudioAction.EXCLUDE]
                             if exclues and not passe else None),
              sous_titres=[st.index for st in dec.subtitles_finales]))
    print(f"\n   SORTIE {out.name}  {out.stat().st_size/1e9:.2f} Go", flush=True)
finally:
    for p in (brut, nodv, mka):
        if p.exists():
            p.unlink()
            print(f"   nettoye {p.name}", flush=True)
