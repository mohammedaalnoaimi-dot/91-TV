"""A tiny fake Xtream Codes server for tests (serves JSON, XMLTV and generated media files)."""
import json, threading, time, http.server, socketserver, urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path


def xmltv():
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    fmt = lambda d: d.strftime("%Y%m%d%H%M%S +0000")
    out = ['<?xml version="1.0"?><tv>']
    for ch in ("news.test", "sport.test"):
        out.append(f'<channel id="{ch}"><display-name>{ch}</display-name></channel>')
        for i in range(8):
            s = now + timedelta(minutes=45 * i)
            out.append(f'<programme start="{fmt(s)}" stop="{fmt(s + timedelta(minutes=45))}" channel="{ch}"><title>{ch.split(".")[0].title()} Show {i}</title><desc>Test programme {i}</desc></programme>')
    out.append("</tv>")
    return "\n".join(out).encode()


TMDB_HITS: list = []


def make_handler(media: Path, port_holder):
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def _json_status(self, code):
            self.send_response(code); self.send_header("Content-Length", "0"); self.end_headers()

        def _json(self, obj):
            b = json.dumps(obj).encode(); self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

        def do_GET(self):
            u = urllib.parse.urlsplit(self.path); q = dict(urllib.parse.parse_qsl(u.query))
            if u.path == "/player_api.php":
                if q.get("username") != "demo" or q.get("password") != "secret":
                    return self._json({"user_info": {"auth": 0}})
                a = q.get("action", "")
                if not a: return self._json({"user_info": {"auth": 1, "status": "Active"}, "server_info": {}})
                if a == "get_live_categories": return self._json([{"category_id": "1", "category_name": "News"}, {"category_id": "2", "category_name": "Sport"}])
                if a == "get_live_streams":
                    return self._json([{"stream_id": 1, "name": "Test News HD", "category_id": "1", "epg_channel_id": "news.test"},
                                       {"stream_id": 2, "name": "Test Sport 4K", "category_id": "2", "epg_channel_id": "sport.test"}])
                if a == "get_vod_categories": return self._json([{"category_id": "10", "category_name": "Action"}, {"category_id": "30", "category_name": "Adults 18+"}])
                if a == "get_vod_streams":
                    return self._json([{"stream_id": 100, "name": "Test Movie", "category_id": "10", "container_extension": "mkv", "rating": "7.5"},
                                       {"stream_id": 101, "name": "4K-AR-DO - Poster-less Film (2019) FHD", "category_id": "10", "container_extension": "mkv", "stream_icon": ""},
                                       {"stream_id": 102, "name": "Adult Night", "category_id": "30", "container_extension": "mkv", "stream_icon": ""}])
                if a == "get_vod_info":
                    return self._json({"info": {"plot": "A provider-written plot for the test movie.", "actors": "Provider Actor", "genre": "Action", "duration": "01:45:00", "backdrop_path": [f"http://{self.headers.get('Host')}/backdrop.jpg"]}} if q.get("vod_id") == "100" else {"info": []})
                if a == "get_series_categories": return self._json([{"category_id": "20", "category_name": "Drama"}])
                if a == "get_series": return self._json([{"series_id": 7, "name": "Test Series", "category_id": "20", "plot": "A test series.", "rating": "8", "releaseDate": "2020-01-01"}])
                if a == "get_series_info":
                    return self._json({"info": {"name": "Test Series", "plot": "A gripping test drama about a fake IPTV server that never sleeps.", "cast": "Ada Tester, Bob Mock", "genre": "Drama, Thriller", "rating": "8.1", "releaseDate": "2020-01-01", "backdrop_path": [f"http://{self.headers.get('Host')}/backdrop.jpg"], "cover": f"http://{self.headers.get('Host')}/thumb.jpg"},
                                       "episodes": {"1": [{"id": "700", "episode_num": 1, "title": "4K-AR-DO - Test Series - S01E01 - Episode 1", "season": 1, "container_extension": "mkv", "info": {"plot": "The pilot episode.", "duration": "00:45:10", "movie_image": f"http://{self.headers.get('Host')}/thumb.jpg"}},
                                                          {"id": "701", "episode_num": 2, "title": "4K-AR-DO - Test Series - S01E02 - The Second One", "season": 1, "container_extension": "mkv", "info": {"plot": "Things escalate.", "duration": "00:44:02"}}],
                                                    "2": [{"id": "702", "episode_num": 1, "title": "4K-AR-DO - Test Series - S02E01 - Return", "season": 2, "container_extension": "mkv", "info": {"duration": "00:50:00"}}]}})
                return self._json([])
            if u.path.startswith("/3/"):
                if u.path == "/3/configuration": return self._json({"images": {}}) if q.get("api_key") == "tmdbkey" else self._json_status(401)
                if q.get("api_key") != "tmdbkey": return self._json_status(401)
                host = self.headers.get("Host"); TMDB_HITS.append(u.path)
                if u.path in ("/3/search/movie", "/3/search/tv"):
                    return self._json({"results": [{"id": 555}]} if "poster" in q.get("query", "").lower() else {"results": []})
                if u.path in ("/3/movie/555", "/3/tv/555"):
                    return self._json({"id": 555, "poster_path": "/thumb.jpg", "backdrop_path": "/backdrop.jpg", "overview": "TMDB overview for the poster-less film.", "vote_average": 7.84,
                                       "release_date": "2019-05-01", "genres": [{"name": "Comedy"}, {"name": "Drama"}], "credits": {"cast": [{"name": "Tina Tmdb"}, {"name": "Tom Test"}]}})
            if u.path.startswith("/t/p/"):
                f = media / "thumb.jpg"
                if f.exists():
                    b = f.read_bytes(); self.send_response(200); self.send_header("Content-Type", "image/jpeg"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
            if u.path in ("/backdrop.jpg", "/thumb.jpg") and (media / u.path[1:]).exists():
                b = (media / u.path[1:]).read_bytes(); self.send_response(200); self.send_header("Content-Type", "image/jpeg"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
            if u.path == "/xmltv.php":
                b = xmltv(); self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
            f = media / "test.mkv"            # any /live /movie /series path serves the test clip
            if u.path.split("/")[1] in ("live", "movie", "series") and f.exists():
                data = f.read_bytes(); self.send_response(200); self.send_header("Content-Type", "video/x-matroska")
                self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data); return
            self.send_response(404); self.end_headers()
    return H


class FakeServer:
    def __init__(self, media: Path):
        class S(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads = True
        self.httpd = S(("127.0.0.1", 0), make_handler(media, None))
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def url(self): return f"http://127.0.0.1:{self.port}"
    def close(self): self.httpd.shutdown()
