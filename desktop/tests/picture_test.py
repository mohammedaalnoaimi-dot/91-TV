"""Real-libmpv test of per-channel picture profiles: denoise filter (<=1080p), deinterlace, motion, deband (vo=null)."""
import os, sys, time
os.environ["AURORA_VO"] = "null"; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aurora.player import Player
media = sys.argv[1]; res = []
def check(n, ok, d=""): res.append(bool(ok)); print(("PASS " if ok else "FAIL ") + n + (f" [{d}]" if d else ""), flush=True)
p = Player(0, {"hwdec": "no", "denoise": "off", "motion": "off", "deinterlace": "auto", "quality": "balanced"})
p.play(media, False); t = time.time()
while time.time() - t < 10 and not (p.m.video_params or {}).get("h"): time.sleep(0.2)
p.tick(); check("no filter by default", p._vf is None and p.m.vf == [])
p.apply_picture({"denoise": "light"}); time.sleep(0.2); p.tick()
check("per-channel denoise applies hqdn3d (video <=1080p)", p._vf and any("hqdn3d" in str(f) for f in p.m.vf), str(p.m.vf))
p.apply_picture({"denoise": "off", "deinterlace": "on", "motion": "smooth", "deband": "on"}); time.sleep(0.2); p.tick()
check("profile switch removes filter", p.m.vf == [], str(p.m.vf))
check("deinterlace forced on", p.m.deinterlace is True or p.m.deinterlace == "yes", str(p.m.deinterlace))
check("motion smoothing + deband applied", p.m.interpolation is True and p.m.deband is True, f"{p.m.interpolation}/{p.m.deband}")
p.apply_picture({}); p.tick(); check("empty profile falls back to global settings", p.pic["motion"] == "off" and p.pic["deinterlace"] == "auto")
p.shutdown(); print(f"{sum(res)}/{len(res)}"); os._exit(0 if all(res) else 1)
