"""M3U / M3U8 playlist parser and loader."""
from __future__ import annotations
import gzip, logging, re
from pathlib import Path
import requests
from .models import Item

log = logging.getLogger(__name__)
_ATTR = re.compile(r'([\w-]+)="([^"]*)"')
_SERIES = re.compile(r"^(.*?)[\s._-]*[Ss](\d{1,2})[\s._-]*[Ee](\d{1,3})")
UA = "VLC/3.0.20 LibVLC/3.0.20"


def classify(url: str, group: str) -> str:
    u, g = url.lower(), group.lower()
    if "/series/" in u or any(k in g for k in ("series", "tv show", "tvshow")):
        return "series"
    if "/movie/" in u or any(k in g for k in ("movie", "vod", "film", "cinema")):
        return "movie"
    if u.endswith((".mkv", ".mp4", ".avi")):
        return "movie"
    return "live"


def parse(text: str) -> list[Item]:
    items: list[Item] = []
    attrs, name = None, ""
    for raw in text.splitlines():
        line = raw.strip().lstrip("\ufeff")
        if not line:
            continue
        if line.upper().startswith("#EXTINF"):
            head, _, name = line.partition(",")
            attrs = dict(_ATTR.findall(head))
            name = name.strip()
        elif line.startswith("#EXTGRP:") and attrs is not None:
            attrs.setdefault("group-title", line[8:].strip())
        elif line.startswith("#"):
            continue
        elif attrs is not None:
            group = attrs.get("group-title", "") or "Uncategorized"
            title = name or attrs.get("tvg-name", "") or line
            items.append(Item(name=title, kind=classify(line, group), url=line, group=group,
                              logo=attrs.get("tvg-logo", ""), tvg_id=attrs.get("tvg-id", ""),
                              extra={"tvg_name": attrs.get("tvg-name", ""), "num": attrs.get("tvg-chno", "")}))
            attrs, name = None, ""
    return _fold_series(items)


def _fold_series(items: list[Item]) -> list[Item]:
    """Turn 'Show S01E02' entries of kind series into one series item with episodes."""
    out, shows = [], {}
    for it in items:
        m = _SERIES.match(it.name) if it.kind == "series" else None
        if not m:
            out.append(it); continue
        title = m.group(1).strip() or it.name
        show = shows.get(title.lower())
        if show is None:
            show = Item(name=title, kind="series", group=it.group, logo=it.logo, extra={"episodes": []})
            show.ext_id = f"m3u:{title.lower()}"
            shows[title.lower()] = show; out.append(show)
        show.extra["episodes"].append({"title": it.name, "url": it.url, "season": int(m.group(2)), "number": int(m.group(3))})
    return out


def header_epg(text: str) -> str:
    head = text[:2048].splitlines()[0] if text else ""
    m = re.search(r'(?:url-tvg|x-tvg-url)="([^",]+)', head)
    return m.group(1) if m else ""


def load(source: str, timeout: int = 30) -> list[Item]:
    return load_with_meta(source, timeout)[0]


def load_with_meta(source: str, timeout: int = 30):
    """source: http(s) URL or local file path. Returns (items, epg_url_from_header)."""
    if source.lower().startswith(("http://", "https://")):
        log.info("Downloading playlist (%s)", source.split("?")[0])
        r = requests.get(source, timeout=timeout, headers={"User-Agent": UA})
        r.raise_for_status()
        data = r.content
    else:
        data = Path(source).expanduser().read_bytes()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    text = data.decode("utf-8", errors="replace")
    if "#EXTM3U" not in text[:2048].upper() and "#EXTINF" not in text.upper():
        raise ValueError("Not a valid M3U playlist")
    items = parse(text)
    log.info("Parsed %d entries", len(items))
    return items, header_epg(text)
