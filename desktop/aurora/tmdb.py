"""Optional TMDB lookups (posters, backdrops, plot, rating, cast) for items that have poor or missing artwork.
The user pastes their own free TMDB key (v3 API key or v4 read-access token). Results are cached on disk."""
from __future__ import annotations
import json, logging, os, re, threading
import requests
from .paths import cache_dir

log = logging.getLogger(__name__)
IMG = os.environ.get("AURORA_TMDB_IMG", "https://image.tmdb.org/t/p")
_TAGS = re.compile(r"^\s*(?:[A-Z0-9+]{1,10}(?:-[A-Z0-9+]{1,10})*\s*[-|:]\s+|\[[^\]]{1,12}\]\s*|\([A-Z]{2,6}\)\s*)", re.I)
_NOISE = re.compile(r"\b(?:4k|uhd|fhd|hd|sd|hdr|hevc|x26[45]|h26[45]|1080p|720p|2160p|multi|dubbed|dual|vostfr|web-?dl|blu-?ray|bdrip|hdrip|remux|ar|en|fr)\b", re.I)
_YEAR = re.compile(r"[\(\[]?\b(19[2-9]\d|20[0-4]\d)\b[\)\]]?")


def clean_query(name: str) -> tuple[str, str]:
    """'4K-AR-DO - The Matrix (1999) FHD' -> ('The Matrix', '1999')."""
    s = name or ""
    for _ in range(3):
        n = _TAGS.sub("", s, count=1)
        if n == s: break
        s = n
    m = _YEAR.search(s); year = m.group(1) if m else ""
    if m: s = s[:m.start()] + " " + s[m.end():]
    s = _NOISE.sub(" ", s)
    s = re.sub(r"[\._]+", " ", s); s = re.sub(r"\s*[-|:]\s*$", "", s); s = re.sub(r"\s+", " ", s).strip(" -|:")
    return s, year


class Tmdb:
    def __init__(self, key: str, base: str | None = None):
        self.key = (key or "").strip(); self.base = (base or os.environ.get("AURORA_TMDB_BASE") or "https://api.themoviedb.org/3").rstrip("/")
        self.lock = threading.Lock(); self._path = cache_dir() / "tmdb.json"; self.s = requests.Session(); self.s.headers["User-Agent"] = "VLC/3.0.20 LibVLC/3.0.20"
        self.errors = 0; self.last_error = ""
        try: self.cache = json.loads(self._path.read_text("utf-8"))
        except Exception: self.cache = {}
        self._dirty = 0

    @property
    def enabled(self) -> bool: return bool(self.key)

    def _get(self, path, **params):
        headers = {}
        if len(self.key) > 40:                         # v4 read-access token (JWT)
            headers["Authorization"] = f"Bearer {self.key}"
        else:
            params["api_key"] = self.key
        r = self.s.get(f"{self.base}{path}", params=params, headers=headers, timeout=12); r.raise_for_status(); return r.json()

    def lookup(self, kind: str, title: str, year: str = "") -> dict | None:
        """kind: 'movie' | 'series'. Returns {poster, backdrop, overview, rating, year, genres, cast} or None."""
        if not self.enabled: return None
        q, y2 = clean_query(title); year = year or y2
        if not q: return None
        ck = f"{kind}|{q.lower()}|{year}"
        with self.lock:
            if ck in self.cache: return self.cache[ck] or None
        kind_t = "movie" if kind == "movie" else "tv"
        try:
            sp = {"query": q, "include_adult": "false"}
            if year: sp["year" if kind_t == "movie" else "first_air_date_year"] = year
            res = (self._get(f"/search/{kind_t}", **sp).get("results") or [])
            if not res and year:
                sp.pop("year", None); sp.pop("first_air_date_year", None); res = self._get(f"/search/{kind_t}", **sp).get("results") or []
            out = None
            if res:
                best = res[0]
                det = self._get(f"/{kind_t}/{best['id']}", append_to_response="credits")
                cast = [c.get("name") for c in (det.get("credits") or {}).get("cast", [])[:6] if c.get("name")]
                date = det.get("release_date") or det.get("first_air_date") or ""
                out = {"poster": f"{IMG}/w500{det['poster_path']}" if det.get("poster_path") else "",
                       "backdrop": f"{IMG}/w1280{det['backdrop_path']}" if det.get("backdrop_path") else "",
                       "overview": det.get("overview") or "", "rating": f"{det.get('vote_average', 0):.1f}" if det.get("vote_average") else "",
                       "year": date[:4], "genres": ", ".join(g.get("name", "") for g in det.get("genres", [])[:3]), "cast": ", ".join(cast)}
            with self.lock:
                self.cache[ck] = out or {}; self._dirty += 1
                if self._dirty >= 20: self._save()
            return out
        except Exception as e:
            self.errors += 1; self.last_error = f"{type(e).__name__}: {e}"; log.warning("TMDB lookup failed for %r: %s", title, e)
            return None

    def _save(self):
        try: self._path.write_text(json.dumps(self.cache), "utf-8"); self._dirty = 0
        except Exception: pass

    def flush(self):
        with self.lock: self._save()

    def test(self) -> str:
        """Returns '' if the key works, else an error message."""
        try: self._get("/configuration"); return ""
        except requests.HTTPError as e: return "Invalid key" if e.response is not None and e.response.status_code == 401 else str(e)
        except Exception as e: return str(e)
