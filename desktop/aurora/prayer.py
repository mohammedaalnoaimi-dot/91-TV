"""Prayer times for Bahrain (Manama) from the free Aladhan API, cached per day on disk. No Qt in here."""
from __future__ import annotations
import json, logging, threading, time
from datetime import datetime, timedelta, timezone
import requests
from .paths import cache_dir

log = logging.getLogger(__name__)
TZ = timezone(timedelta(hours=3))      # Asia/Bahrain has no daylight saving, so a fixed offset is exact (and needs no tz database on Windows)
ORDER = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]
FARD = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]       # Sunrise is shown but never "next prayer"
ARABIC = {"Fajr": "الفجر", "Sunrise": "الشروق", "Dhuhr": "الظهر", "Asr": "العصر", "Maghrib": "المغرب", "Isha": "العشاء"}
METHODS = [(8, "Gulf Region"), (4, "Umm Al-Qura (Makkah)"), (9, "Kuwait"), (10, "Qatar"), (3, "Muslim World League")]
REMIND = [0, 5, 10, 15, 30]
URL = "https://api.aladhan.com/v1/timingsByCity/{key}"


def method_name(m: int) -> str:
    return dict(METHODS).get(int(m), "Gulf Region")


def now() -> datetime:
    return datetime.now(TZ)


def day_key(d: datetime) -> str:
    return d.astimezone(TZ).strftime("%d-%m-%Y")


class Day:
    def __init__(self, key: str, times: dict, hijri: str = "", month: int = 0):
        self.key, self.times, self.hijri, self.month = key, times, hijri, month      # month = hijri month number (9 = Ramadan)

    def at(self, name: str) -> datetime:
        h, m = self.times[name].split(":")
        d = datetime.strptime(self.key, "%d-%m-%Y")
        return datetime(d.year, d.month, d.day, int(h), int(m), tzinfo=TZ)


def parse(payload: dict, key: str) -> Day:
    """Aladhan answer -> Day. Times arrive like '04:14 (+03)'; only the first 5 characters matter."""
    data = payload["data"]; t = data["timings"]
    times = {n: str(t[n]).strip()[:5] for n in ORDER}
    h = (data.get("date") or {}).get("hijri") or {}
    hijri = ""
    if h:
        hijri = f"{str(h.get('day', '')).lstrip('0')} {(h.get('month') or {}).get('en', '')} {h.get('year', '')} AH".strip()
    try: hm = int((h.get("month") or {}).get("number") or 0)
    except (TypeError, ValueError): hm = 0
    return Day(key, times, hijri, hm)


def _cache_file():
    return cache_dir() / "prayer.json"


def _load_cache() -> dict:
    try: return json.loads(_cache_file().read_text("utf-8"))
    except Exception: return {}


def fetch_day(method: int, key: str, session=None) -> Day | None:
    ck = f"v2_{method}_{key}"; cache = _load_cache()
    if ck in cache:
        try: return Day(key, cache[ck]["t"], cache[ck].get("h", ""), int(cache[ck].get("m", 0)))
        except Exception: pass
    try:
        r = (session or requests).get(URL.format(key=key), params={"city": "Manama", "country": "Bahrain", "method": method}, timeout=15)
        r.raise_for_status(); d = parse(r.json(), key)
    except Exception as e:
        log.warning("Prayer times fetch failed: %s", e); return None
    keep = {k: v for k, v in cache.items() if k.endswith(key) or k.endswith(day_key(now() + timedelta(days=1)))}
    keep[ck] = {"t": d.times, "h": d.hijri, "m": d.month}
    try: _cache_file().write_text(json.dumps(keep), "utf-8")
    except Exception: pass
    return d


class Times:
    """Holds today's and tomorrow's times; refresh() is cheap when nothing is missing."""
    def __init__(self, get_method):
        self.get_method = get_method; self.today: Day | None = None; self.tomorrow: Day | None = None
        self._busy = False; self._last = 0.0; self.on_change = lambda: None

    def refresh(self, force=False):
        n = now(); k0, k1 = day_key(n), day_key(n + timedelta(days=1))
        if not force and self.today and self.today.key == k0 and self.tomorrow and self.tomorrow.key == k1: return
        if self._busy or (time.time() - self._last < 60 and not force): return
        self._busy = True; self._last = time.time(); m = int(self.get_method() or 8)

        def work():
            try:
                d0, d1 = fetch_day(m, k0), fetch_day(m, k1)
                if d0: self.today = d0
                if d1: self.tomorrow = d1
            finally:
                self._busy = False
            self.on_change()
        threading.Thread(target=work, daemon=True).start()

    def reset(self):
        self.today = self.tomorrow = None; self._last = 0.0

    def next(self, at: datetime | None = None):
        """(name, datetime) of the next of Fajr/Dhuhr/Asr/Maghrib/Isha, or None while nothing is loaded."""
        at = at or now()
        if not self.today: return None
        for n in FARD:
            t = self.today.at(n)
            if t > at: return n, t
        if self.tomorrow: return "Fajr", self.tomorrow.at("Fajr")
        return None


def left(delta: timedelta) -> str:
    s = max(0, int(delta.total_seconds())); h, m = s // 3600, (s % 3600) // 60
    return f"{h}h {m}m" if h else f"{m}m" if m else "<1m"


def hms(delta: timedelta) -> str:
    s = max(0, int(delta.total_seconds())); return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def ramadan(day) -> bool:
    return bool(day and day.month == 9)


def fetch_month(method: int, year: int, month: int, session=None):
    """Whole Gregorian month as [(DD-MM-YYYY, hijri_day, hijri_month, {name: 'HH:MM'})]; cached on disk per month. None when offline and not cached yet."""
    ck = f"month_{method}_{year}_{month}"; cache = _load_cache()
    if ck in cache: return [tuple(r) for r in cache[ck]]
    try:
        r = (session or requests).get(f"https://api.aladhan.com/v1/calendarByCity/{year}/{month}", params={"city": "Manama", "country": "Bahrain", "method": method}, timeout=20)
        r.raise_for_status(); rows = []
        for d in r.json()["data"]:
            hj = d["date"]["hijri"]; rows.append((d["date"]["gregorian"]["date"], str(hj.get("day", "")).lstrip("0"), int((hj.get("month") or {}).get("number") or 0), {n: str(d["timings"][n]).strip()[:5] for n in ORDER}))
    except Exception as e:
        log.warning("Prayer month fetch failed: %s", e); return None
    cache[ck] = rows
    try: _cache_file().write_text(json.dumps(cache), "utf-8")
    except Exception: pass
    return rows
