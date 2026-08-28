import json, pathlib, sys
from core import decision as dm, dovi, muxer, profiles, scanner
from core.config import get_bin_dir, load
from core.decision import decide
from core.encoder import build_command
from core.platform import detect
from core.preflight import get_tool_path
from core import encoder

cfg = load(); bd = get_bin_dir(cfg)
scanner.set_dovi_path(dovi.get_path(bd))
scanner.set_ffprobe_path(get_tool_path("ffprobe", bd))
muxer.set_mkvmerge_path(get_tool_path("mkvmerge", bd))
encoder.set_ffmpeg_path(get_tool_path("ffmpeg", bd))
dm.set_strip_dv_available(True)

info = scanner.scan(pathlib.Path("resources_files") / sys.argv[1])
dec  = decide(info, profiles.load_all()["cinema_4k_basic"])
print(f"  source    : {info.codec} {info.width}x{info.height} {info.kbps}k {info.dv_label} {info.color_transfer}")
print(f"  video     : {dec.video.label()}  ->  {dec.video.target_bitrate//1000}k   ({dec.video.reason})")
for a in dec.audio:
    print(f"  audio     : {a.action.name:9} {a.track.codec}/{a.track.channels}ch {a.track.language} {a.display():16} titre={a.output_title}")
print(f"  st ecartes: {dec.sous_titres_ecartes}")
print(f"  sortie    : {dec.output_path.name}")
cmd = build_command(dec, detect())
json.dump(cmd, open(sys.argv[2], "w", encoding="utf-8"))
print("\n  " + " ".join(cmd))
