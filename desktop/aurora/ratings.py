"""IMDb + Rotten Tomatoes scores from OMDb (free key from omdbapi.com), cached on disk. No Qt in here."""
from __future__ import annotations
import json, logging, re, threading
from concurrent.futures import ThreadPoolExecutor
import requests
from .paths import cache_dir

log = logging.getLogger(__name__)
_YEAR = re.compile(r"\((\d{4})\)")
_BRACKETS = re.compile(r"[\[\(][^\]\)]*[\]\)]")
URL = "https://www.omdbapi.com/"


def clean_title(raw: str) -> str:
    """'4K-A+ - Tenzing (2026)' -> 'Tenzing'. Provider prefixes are short tags before ' - '."""
    n = raw or ""; i = n.find(" - ")
    if 1 <= i <= 14 and not any(c.islower() for c in n[:i]): n = n[i + 3:]
    n = _BRACKETS.sub(" ", n)
    return re.sub(r"\s+", " ", n).strip()


def year_of(raw: str, hint: str = "") -> str:
    m = _YEAR.search(raw or "")
    return m.group(1) if m else (hint or "")[:4]


def provider_score(rating: str) -> str:
    try: v = float(rating)
    except (TypeError, ValueError): return ""
    return f"★ {v:.1f}" if 0 < v <= 10 else ""


class Ratings:
    def __init__(self, get_key, on_update=lambda: None, session=None):
        self.get_key, self.on_update, self.session = get_key, on_update, session or requests
        self.mem: dict[str, str] = {}; self.pending: set[str] = set(); self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=2); self.file = cache_dir() / "ratings2.json"
        try: self.disk = json.loads(self.file.read_text("utf-8"))
        except Exception: self.disk = {}

    @staticmethod
    def cache_key(it) -> str:
        return f"{it.kind}|{clean_title(it.name).lower()}|{year_of(it.name, it.year)}"

    def lookup(self, kind: str, raw_name: str, year_hint: str = "") -> str:
        """Blocking network lookup (cached). '' when not found / no key."""
        key = (self.get_key() or "").strip()
        if not key or kind not in ("movie", "series"): return ""
        title = clean_title(raw_name)
        if len(title) < 2: return ""
        year = year_of(raw_name, year_hint); ck = f"{kind}|{title.lower()}|{year}"
        if ck in self.disk: return self.disk[ck]
        try:
            params = {"apikey": key, "t": title, "type": "series" if kind == "series" else "movie"}
            if year and kind != "series": params["y"] = year
            r = self.session.get(URL, params=params, timeout=12); r.raise_for_status(); o = r.json()
        except Exception as e:
            log.warning("OMDb lookup failed for %r: %s", title, e); return ""
        if str(o.get("Response")) != "True":
            self._store(ck, ""); return ""
        nz = lambda t: "".join(c for c in (t or "").lower() if c.isalnum())
        a, b = nz(title), nz(o.get("Title"))
        if not a or not b or not (a == b or a in b or b in a): self._store(ck, ""); return ""
        try:
            if kind != "series" and year and abs(int(str(o.get("Year"))[:4]) - int(year)) > 1: self._store(ck, ""); return ""
        except ValueError: pass
        parts = []
        imdb = o.get("imdbRating")
        if imdb and imdb != "N/A": parts.append(f"IMDb {imdb}")
        for rt in o.get("Ratings") or []:
            if "Rotten" in str(rt.get("Source", "")): parts.append(f"RT {rt.get('Value')}")
        text = "   ·   ".join(parts); self._store(ck, text); return text

    def _store(self, ck, text):
        with self.lock:
            self.disk[ck] = text
            try: self.file.write_text(json.dumps(self.disk), "utf-8")
            except Exception: pass

    def text(self, it) -> str:
        """What to print next to a title: OMDb text when known, else the provider's score. Starts a lookup in the background."""
        base = provider_score(it.rating)
        if it.kind not in ("movie", "series") or not (self.get_key() or "").strip(): return base
        ck = self.cache_key(it)
        if ck in self.disk: return self.disk[ck] or base
        if ck in self.mem: return self.mem[ck] or base
        if ck not in self.pending and len(self.pending) < 40:
            self.pending.add(ck)
            def work():
                try: t = self.lookup(it.kind, it.name, it.year); self.mem[ck] = t
                finally: self.pending.discard(ck)
                if t: self.on_update()
            self.pool.submit(work)
        return base
