"""Xtream Codes API client."""
from __future__ import annotations
import base64, logging
import time, threading
import requests
from .models import Item, Episode

log = logging.getLogger(__name__)
UA = "VLC/3.0.20 LibVLC/3.0.20"


def normalise_server(server: str) -> str:
    s = server.strip().rstrip("/")
    if not s.lower().startswith(("http://", "https://")):
        s = "http://" + s
    for tail in ("/player_api.php", "/get.php"):
        if s.endswith(tail):
            s = s[: -len(tail)]
    return s

_API_LOCK = threading.Lock(); _LAST = [0.0]; _GAP = 0.15; _INFO: dict = {}


class XtreamError(Exception):
    pass


class XtreamClient:
    def __init__(self, server: str, user: str, password: str, timeout: int = 30):
        self.server, self.user, self.password, self.timeout = normalise_server(server), user, password, timeout
        self.s = requests.Session(); self.s.headers["User-Agent"] = UA; self.s.headers["Connection"] = "close"   # fresh connection per call: providers drop reused ones (RemoteDisconnected)

    def _api(self, action: str | None = None, **params):
        q = {"username": self.user, "password": self.password}
        if action: q["action"] = action          # same parameter order as the TV app (action before the extras); some providers are strict about it
        q.update(params)
        ck = (action, tuple(sorted(params.items()))) if action in ("get_vod_info", "get_series_info") else None
        if ck and ck in _INFO: return _INFO[ck]
        with _API_LOCK:                                   # one request at a time, spaced out: providers answer 5xx when hit in parallel
            for attempt in range(4):
                wait = _GAP - (time.time() - _LAST[0])
                if wait > 0: time.sleep(wait)
                try: r = self.s.get(f"{self.server}/player_api.php", params=q, timeout=self.timeout)
                except (requests.ConnectionError, requests.Timeout) as e:   # provider hung up / dropped the line: wait and retry, then say so plainly
                    _LAST[0] = time.time()
                    if attempt == 3:
                        raise XtreamError("Your provider closed the connection. This usually means it allows only a few connections at once: close 91 TV on other devices (TV, phone), wait a minute and try again.") from e
                    time.sleep((2, 4, 8)[attempt]); continue
                finally: _LAST[0] = time.time()
                if r.status_code < 500 and r.status_code != 429 or attempt == 3: break
                time.sleep((2, 5, 10)[attempt])                # busy provider (513 / 429): give it time to free a slot
        if r.status_code >= 500 or r.status_code == 429:
            raise XtreamError("Your provider is busy or limiting connections (error %d). Wait a minute and try again; close 91 TV on other devices if it keeps happening." % r.status_code)
        r.raise_for_status()
        try:
            data = r.json()
            if ck: _INFO[ck] = data
            return data
        except ValueError as e:
            raise XtreamError("Server did not return JSON (wrong server URL?)") from e

    def authenticate(self) -> dict:
        d = self._api()
        info = d.get("user_info") if isinstance(d, dict) else None
        if not info or str(info.get("auth", 0)) != "1":
            raise XtreamError("Login failed: check username/password")
        if str(info.get("status", "Active")).lower() not in ("active", ""):
            raise XtreamError(f"Account status: {info.get('status')}")
        return d

    def _cats(self, action):
        return {str(c.get("category_id")): c.get("category_name", "") for c in (self._api(action) or [])}

    def live(self) -> list[Item]:
        cats = self._cats("get_live_categories")
        out = []
        for s in self._api("get_live_streams") or []:
            sid = str(s["stream_id"])
            out.append(Item(name=s.get("name", sid), kind="live", url=f"{self.server}/live/{self.user}/{self.password}/{sid}.m3u8",
                            group=cats.get(str(s.get("category_id")), "Live"), logo=s.get("stream_icon") or "",
                            tvg_id=s.get("epg_channel_id") or "", ext_id=sid, extra={"num": str(s.get("num") or "")}))
        return out

    def movies(self) -> list[Item]:
        cats = self._cats("get_vod_categories")
        out = []
        for s in self._api("get_vod_streams") or []:
            sid, ext = str(s["stream_id"]), s.get("container_extension") or "mp4"
            out.append(Item(name=s.get("name", sid), kind="movie", url=f"{self.server}/movie/{self.user}/{self.password}/{sid}.{ext}",
                            group=cats.get(str(s.get("category_id")), "Movies"), logo=s.get("stream_icon") or "",
                            rating=str(s.get("rating") or ""), year=str(s.get("year") or ""), ext_id=sid, extra={"added": str(s.get("added") or "")}))
        return out

    def series(self) -> list[Item]:
        cats = self._cats("get_series_categories")
        out = []
        try:
            rows = self._api("get_series") or []
        except (XtreamError, requests.RequestException) as first:
            # Some providers refuse (513) or hang up on the one huge request: ask for one category at a time instead.
            rows, ok = [], 0
            for cid in cats:
                try: rows += self._api("get_series", category_id=cid) or []; ok += 1
                except (XtreamError, requests.RequestException): log.warning("series category %s failed", cid)
            if not ok: raise first
        for s in rows:
            sid = str(s["series_id"])
            out.append(Item(name=s.get("name", sid), kind="series", group=cats.get(str(s.get("category_id")), "Series"),
                            logo=s.get("cover") or "", plot=s.get("plot") or "", rating=str(s.get("rating") or ""),
                            year=str(s.get("year") or s.get("releaseDate") or "")[:4], ext_id=sid, extra={"added": str(s.get("last_modified") or "")}))
        return out

    def vod_info(self, vod_id: str) -> dict:
        """Movie details (plot, cast, genre, backdrop...) from get_vod_info; {} when the provider has none."""
        d = self._api("get_vod_info", vod_id=vod_id) or {}
        info = d.get("info") if isinstance(d, dict) and isinstance(d.get("info"), dict) else {}
        out = dict(info)
        if info.get("plot") is None and info.get("description"): out["plot"] = info["description"]
        if info.get("cast") is None and info.get("actors"): out["cast"] = info["actors"]
        if info.get("cover") is None and info.get("movie_image"): out["cover"] = info["movie_image"]
        return out

    def series_info(self, series_id: str):
        """Returns (info dict with plot/cast/genre/backdrop..., sorted list of Episode)."""
        d = self._api("get_series_info", series_id=series_id) or {}
        info = d.get("info") if isinstance(d.get("info"), dict) else {}
        raw = d.get("episodes") or {}
        groups = raw.items() if isinstance(raw, dict) else enumerate(raw, start=1)
        eps = []
        for season, lst in groups:
            for e in lst or []:
                ext = e.get("container_extension") or "mp4"; ei = e.get("info") if isinstance(e.get("info"), dict) else {}
                try:
                    sn = int(e.get("season") or season)
                except (TypeError, ValueError):
                    sn = 1
                try:
                    num = int(e.get("episode_num") or 0)
                except (TypeError, ValueError):
                    num = 0
                eps.append(Episode(title=e.get("title") or f"Episode {num}",
                                   url=f"{self.server}/series/{self.user}/{self.password}/{e['id']}.{ext}",
                                   season=sn, number=num, plot=ei.get("plot", "") or "", image=ei.get("movie_image", "") or "",
                                   duration=str(ei.get("duration", "") or "")))
        return info, sorted(eps, key=lambda e: (e.season, e.number))

    def episodes(self, series_id: str) -> list[Episode]:
        return self.series_info(series_id)[1]

    def short_epg(self, stream_id: str, limit: int = 8):
        from .models import Programme
        d = self._api("get_short_epg", stream_id=stream_id, limit=limit)
        out = []
        for e in (d or {}).get("epg_listings", []):
            try:
                out.append(Programme(float(e["start_timestamp"]), float(e["stop_timestamp"]),
                                     _b64(e.get("title", "")), _b64(e.get("description", ""))))
            except (KeyError, ValueError):
                continue
        return out

    @property
    def xmltv_url(self) -> str:
        return f"{self.server}/xmltv.php?username={self.user}&password={self.password}"


def _b64(s: str) -> str:
    try:
        return base64.b64decode(s).decode("utf-8", "replace")
    except Exception:
        return s
