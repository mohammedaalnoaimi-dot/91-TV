import os, sys, time, threading, subprocess, http.server
os.environ["AURORA_VO"]="null"; sys.path.insert(0,""+os.path.dirname(os.path.dirname(os.path.abspath(__file__)))+"")
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type","video/mp2t"); self.end_headers()
        p=subprocess.Popen(["ffmpeg","-v","quiet","-re","-f","lavfi","-i","testsrc=size=320x240:rate=25","-f","lavfi","-i","sine=frequency=440","-c:v","libx264","-preset","ultrafast","-g","25","-c:a","aac","-f","mpegts","pipe:1"],stdout=subprocess.PIPE)
        try:
            while True:
                b=p.stdout.read(4096)
                if not b: break
                self.wfile.write(b)
        except Exception: pass
        finally: p.kill()
srv=http.server.ThreadingHTTPServer(("127.0.0.1",0),H); port=srv.server_address[1]
threading.Thread(target=srv.serve_forever,daemon=True).start()
from aurora.player import Player
pl=Player(0,{"hwdec":"no","timeshift":5,"motion":"off","tone_mapping":"hable","display_peak":600})
pl.play(f"http://127.0.0.1:{port}/live",True)
t0=time.time()
while time.time()-t0<40 and (pl.m.time_pos or 0)<20: time.sleep(0.5)
pos0=pl.m.time_pos; print("pos before",pos0)
pl.seek(-10); time.sleep(2)
b=pl.behind_live(); print("pos after seek-back",pl.m.time_pos,"behind",b, "tick",pl.tick())
ok1 = 6<b<14
pl.go_live(); time.sleep(2); b2=pl.behind_live(); print("behind after go_live",b2)
ok2 = b2<3
print("PASS" if ok1 and ok2 else "FAIL"); os._exit(0 if ok1 and ok2 else 1)
