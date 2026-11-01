"""Real-libmpv test of the stuck-stream recovery ladder (vo=null, no window)."""
import os, sys, time, threading, http.server
os.environ["AURORA_VO"] = "null"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MEDIA = os.environ.get("AURORA_TEST_MEDIA", "media/test.mkv")
data = open(MEDIA, "rb").read()
hits = {"dead": 0, "stall": 0, "good": 0}

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        k = self.path.strip("/").split(".")[0]
        hits[k] = hits.get(k, 0) + 1
        if k == "dead":
            self.send_error(404); return
        self.send_response(200); self.send_header("Content-Type", "video/x-matroska")
        self.send_header("Content-Length", str(len(data) * 50)); self.end_headers()
        try:
            if k == "stall":
                self.wfile.write(data[:20000]); self.wfile.flush(); time.sleep(120); return
            for _ in range(50): self.wfile.write(data)
        except Exception: pass

srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
from aurora.player import Player
def run(primary, alts, want, limit=40):
    p = Player(0, {"hwdec": "no"}); t0 = time.time(); events = []
    p.play(f"http://127.0.0.1:{port}/{primary}", True, alternates=[f"http://127.0.0.1:{port}/{a}" for a in alts])
    while time.time() - t0 < limit:
        r = p.tick()
        if r: events.append((round(time.time() - t0, 1), r))
        if p.sources[p.source_index].endswith(want) and (p.info() or {}).get("time", 0) > 0 and want == "good":
            pass
        pos = p.m.time_pos or 0
        if p.sources[p.source_index].endswith(want) and pos > 1.0: break
        time.sleep(0.25)
    ok = p.sources[p.source_index].endswith(want) and (p.m.time_pos or 0) > 1.0
    p.shutdown(); return ok, events, time.time() - t0
fails = 0
for name, prim, alts in [("dead link -> backup", "dead", ["good"]), ("stalled stream -> backup", "stall", ["good"])]:
    ok, ev, dt = run(prim, alts, "good")
    print(("PASS" if ok else "FAIL"), name, f"{dt:.1f}s", ev, flush=True); fails += not ok
print(hits); os._exit(1 if fails else 0)
