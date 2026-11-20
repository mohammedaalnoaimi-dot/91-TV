#!/usr/bin/env python3
"""Mock Xtream-codes server for the visual audit: synthetic channels, movies, series, posters and a short test clip. No real content."""
import json, os, random, base64, io, time, colorsys, sys
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from PIL import Image, ImageDraw, ImageFont, ImageFilter

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
MEDIA = sys.argv[2] if len(sys.argv) > 2 else "/tmp/media"
W1 = "Midnight Silent Golden Crimson Hidden Last Final Broken Distant Winter Burning Iron Velvet Paper Hollow Savage Quiet Electric Lonely Wild".split()
W2 = "Harbor Empire Horizon Kingdom Witness Garden Protocol Frontier Echo Letter Station Meridian Orchard Verdict Signal Archive Passage Reckoning Season Mirage".split()
R = random.Random(11)
def title(i): r = random.Random(i); return f"{r.choice(W1)} {r.choice(W2)}" + (f" {r.randint(2,4)}" if i % 7 == 0 else "")
CATS = ["Action", "Drama", "Comedy", "Thriller", "Sci-Fi", "Documentary", "Family", "Arabic", "Horror", "Romance"]
NMOV, NSER, NLIVE = 420, 160, 48
BASE = ""
try: SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"; ImageFont.truetype(SERIF, 20)
except Exception: SERIF = None
def font(sz):
    try: return ImageFont.truetype(SERIF, sz)
    except Exception: return ImageFont.load_default()

def grad_img(w, h, hue, dark=False, seed=0):
    """Smooth float-computed gradient with a soft glow and light dither, so any banding seen in the app is the app's, not the sample image's."""
    import numpy as np
    r = random.Random(seed)
    top = np.array(colorsys.hsv_to_rgb(hue, 0.55 if not dark else 0.25, 0.55 if not dark else 0.12))
    bot = np.array(colorsys.hsv_to_rgb((hue + 0.08) % 1, 0.7 if not dark else 0.3, 0.12 if not dark else 0.03))
    t = np.linspace(0, 1, h)[:, None, None]
    img = (top * (1 - t) + bot * t) * np.ones((h, w, 1))
    cx, cy = r.randint(w // 4, 3 * w // 4), r.randint(h // 5, h // 2)
    yy, xx = np.mgrid[0:h, 0:w]
    g = np.exp(-(((xx - cx) / (0.55 * w)) ** 2 + ((yy - cy) / (0.4 * h)) ** 2))[..., None]
    img = img + g * np.array([1.0, 0.86, 0.74]) * (0.09 if not dark else 0.03)
    img = img * 255 + np.random.default_rng(seed).normal(0, 0.7, (h, w, 1))
    return Image.fromarray(np.clip(img, 0, 255).astype("uint8"))

def poster(i, w=400, h=600):
    hue = (i * 0.618) % 1; dark = (i % 9 == 0)
    im = grad_img(w, h, hue, dark, i)
    d = ImageDraw.Draw(im)
    t = title(i).upper().split()
    f = font(34); y = int(h * 0.62)
    for wd in t:
        tw = d.textlength(wd, font=f); d.text(((w - tw) / 2, y), wd, font=f, fill=(235, 221, 196)); y += 44
    return im

def backdrop(i): return grad_img(1280, 720, (i * 0.618) % 1, i % 3 == 0, i + 99)
def logo(i):
    im = Image.new("RGB", (256, 256), (24, 17, 15)); d = ImageDraw.Draw(im)
    col = tuple(int(255 * v) for v in colorsys.hsv_to_rgb((i * 0.13) % 1, 0.5, 0.85))
    d.ellipse([40, 40, 216, 216], outline=col, width=12)
    f = font(56); s = f"{i % 100:02d}"; d.text((128 - d.textlength(s, font=f) / 2, 100), s, font=f, fill=col); return im

def jpg(im, q=88): b = io.BytesIO(); im.save(b, "JPEG", quality=q); return b.getvalue(), "image/jpeg"
def png(im): b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue(), "image/png"

def cat_list(): return [{"category_id": str(i + 1), "category_name": n, "parent_id": 0} for i, n in enumerate(CATS)]
def host(h): return f"http://{h}"
def movies(h):
    now = int(time.time()); out = []
    for i in range(1, NMOV + 1):
        out.append({"num": i, "name": title(i) + f" ({2005 + i % 20})", "stream_type": "movie", "stream_id": i, "stream_icon": f"{host(h)}/img/p_{i}.jpg",
                    "rating": f"{5 + (i % 40) / 10:.1f}", "added": str(now - i * 86400), "category_id": str(1 + i % len(CATS)), "container_extension": "mp4"})
    return out
def series(h):
    now = int(time.time())
    return [{"num": i, "name": title(1000 + i), "series_id": i, "cover": f"{host(h)}/img/p_{500 + i}.jpg", "rating": f"{6 + (i % 30) / 10:.1f}",
             "last_modified": str(now - i * 3600), "category_id": str(1 + i % len(CATS))} for i in range(1, NSER + 1)]
def live(h):
    return [{"num": i, "name": f"Channel {i:02d} {['News','Sports','Movies','Kids','Music','Docs'][i % 6]}", "stream_type": "live", "stream_id": i,
             "stream_icon": f"{host(h)}/img/l_{i}.png", "category_id": str(1 + i % 6)} for i in range(1, NLIVE + 1)]
def info(i, h):
    return {"plot": "A quiet town hides a long-buried secret. When an old letter resurfaces, three strangers are drawn into a race against time that will change how they see the world and each other.",
            "cast": "A. Rahman, L. Moreau, J. Whitfield", "genre": "Drama, Thriller", "releasedate": f"{2005 + i % 20}-05-01", "rating": f"{5 + (i % 40) / 10:.1f}",
            "backdrop_path": [f"{host(h)}/img/b_{i}.jpg"], "movie_image": f"{host(h)}/img/p_{i}.jpg", "youtube_trailer": ""}
def series_info(sid, h):
    eps = {}
    for s in (1, 2):
        eps[str(s)] = [{"id": str(sid * 100 + s * 10 + e), "episode_num": e, "title": f"Chapter {e}", "container_extension": "mp4",
                        "info": {"movie_image": f"{host(h)}/img/b_{sid + e}.jpg", "duration_secs": 25}} for e in range(1, 9)]
    return {"info": info(500 + sid, h), "episodes": eps}
def epg(sid):
    now = int(time.time()); out = []
    t0 = now - (now % 3600)
    for k in range(4):
        out.append({"title": base64.b64encode(f"Program {sid}-{k}".encode()).decode(), "description": base64.b64encode(b"Sample programme").decode(),
                    "start_timestamp": str(t0 + k * 3600), "stop_timestamp": str(t0 + (k + 1) * 3600)})
    return {"epg_listings": out}

class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def send(self, body, ctype, code=200, extra=None):
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items(): self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD": self.wfile.write(body)
    def file(self, path, ctype):
        data = open(path, "rb").read(); n = len(data); rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            a, _, b = rng[6:].partition("-"); a = int(a or 0); b = int(b) if b else n - 1
            return self.send(data[a:b + 1], ctype, 206, {"Content-Range": f"bytes {a}-{b}/{n}", "Accept-Ranges": "bytes"})
        self.send(data, ctype, 200, {"Accept-Ranges": "bytes"})
    do_HEAD = lambda self: self.do_GET()
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query); h = self.headers.get("Host", f"10.0.2.2:{PORT}")
        p = u.path
        try:
            if p == "/player_api.php":
                a = (q.get("action") or [""])[0]
                if not a: return self.send(json.dumps({"user_info": {"auth": 1, "status": "Active", "username": "demo"}, "server_info": {}}).encode(), "application/json")
                m = {"get_live_categories": lambda: [{"category_id": str(i + 1), "category_name": n, "parent_id": 0} for i, n in enumerate(["News", "Sports", "Movies", "Kids", "Music", "Docs"])],
                     "get_vod_categories": cat_list, "get_series_categories": cat_list,
                     "get_live_streams": lambda: live(h), "get_vod_streams": lambda: movies(h), "get_series": lambda: series(h),
                     "get_vod_info": lambda: {"info": info(int((q.get("vod_id") or ["1"])[0]), h)},
                     "get_series_info": lambda: series_info(int((q.get("series_id") or ["1"])[0]), h),
                     "get_short_epg": lambda: epg((q.get("stream_id") or ["1"])[0])}.get(a)
                return self.send(json.dumps(m() if m else []).encode(), "application/json")
            if p.startswith("/img/"):
                k = p[5:].split(".")[0]; kind, _, n = k.partition("_"); n = int(n)
                if kind == "p": return self.send(*jpg(poster(n)))
                if kind == "b": return self.send(*jpg(backdrop(n)))
                if kind == "l": return self.send(*png(logo(n)))
            if p.startswith("/live/"): return self.file(os.path.join(MEDIA, "test.ts"), "video/mp2t")
            if p.startswith(("/movie/", "/series/")): return self.file(os.path.join(MEDIA, "test.mp4"), "video/mp4")
            self.send(b"not found", "text/plain", 404)
        except (BrokenPipeError, ConnectionResetError): pass
        except Exception as e: self.send(str(e).encode(), "text/plain", 500)

if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
