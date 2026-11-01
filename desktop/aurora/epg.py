"""XMLTV electronic program guide."""
from __future__ import annotations
import gzip, io, logging, time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import requests
from .models import Programme

log = logging.getLogger(__name__)


def _ts(s: str) -> float:
    s = s.strip()
    base, _, tz = s.partition(" ")
    dt = datetime.strptime(base[:14], "%Y%m%d%H%M%S")
    off = 0
    if tz and len(tz) >= 5 and tz[0] in "+-":
        off = (int(tz[1:3]) * 3600 + int(tz[3:5]) * 60) * (1 if tz[0] == "+" else -1)
    return dt.replace(tzinfo=timezone.utc).timestamp() - off


class Epg:
    def __init__(self):
        self.by_channel: dict[str, list[Programme]] = {}
        self.names: dict[str, str] = {}   # lower display-name -> channel id

    def load(self, source: str, timeout: int = 60):
        if source.lower().startswith("http"):
            r = requests.get(source, timeout=timeout, headers={"User-Agent": "VLC/3.0.20 LibVLC/3.0.20"}); r.raise_for_status(); data = r.content
        else:
            data = open(source, "rb").read()
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        self.parse(data)

    def parse(self, data: bytes):
        by, names = {}, {}
        cutoff = time.time() - 6 * 3600
        for _, el in ET.iterparse(io.BytesIO(data), events=("end",)):
            if el.tag == "channel":
                cid = el.get("id", "")
                for dn in el.findall("display-name"):
                    if dn.text:
                        names[dn.text.strip().lower()] = cid
                el.clear()
            elif el.tag == "programme":
                try:
                    stop = _ts(el.get("stop", ""))
                    if stop >= cutoff:
                        by.setdefault(el.get("channel", ""), []).append(
                            Programme(_ts(el.get("start", "")), stop, (el.findtext("title") or "").strip(),
                                      (el.findtext("desc") or "").strip()))
                except (ValueError, TypeError):
                    pass
                el.clear()
        for v in by.values():
            v.sort(key=lambda p: p.start)
        self.by_channel, self.names = by, names
        log.info("EPG loaded: %d channels, %d programmes", len(by), sum(map(len, by.values())))

    def lookup(self, tvg_id: str, name: str = "") -> list[Programme]:
        if tvg_id and tvg_id in self.by_channel:
            return self.by_channel[tvg_id]
        cid = self.names.get(name.strip().lower())
        return self.by_channel.get(cid, []) if cid else []

    def now_next(self, tvg_id: str, name: str = "", at: float | None = None):
        at = at or time.time()
        now = nxt = None
        for p in self.lookup(tvg_id, name):
            if p.start <= at < p.stop:
                now = p
            elif p.start >= at and nxt is None:
                nxt = p
                break
        return now, nxt

    def upcoming(self, tvg_id: str, name: str = "", count: int = 8, at: float | None = None):
        at = at or time.time()
        return [p for p in self.lookup(tvg_id, name) if p.stop > at][:count]
