"""Backup sources for live channels: alternate URL forms and same-named channels in the playlist."""
from __future__ import annotations
import re
from .models import Item

_BRACKETS = re.compile(r"[\[\(\{].*?[\]\)\}]")
_PREFIX = re.compile(r"^\s*[a-z0-9+]{2,6}\s*[:|]\s*")
_QUALITY = re.compile(r"\b(hd|fhd|uhd|4k|8k|sd|hevc|h265|h264|raw|backup|vip|multi|50fps|60fps|2160p|1080p|720p|576p)\b")


def norm_name(name: str) -> str:
    """'UK| BBC One FHD [backup]' -> 'bbcone' (works for any script: \\w is Unicode-aware)."""
    n = _BRACKETS.sub(" ", (name or "").lower())
    n = _PREFIX.sub("", n)
    n = _QUALITY.sub(" ", n)
    return re.sub(r"[\W_]+", "", n, flags=re.UNICODE)


def url_variants(url: str) -> list[str]:
    """Xtream live streams are served as .m3u8 (HLS) and .ts; if one form hangs the other often works."""
    base = url.split("?")[0]
    if "/live/" not in base:
        return []
    if base.endswith(".m3u8"):
        return [url[: len(base) - 5] + ".ts" + url[len(base):]]
    if base.endswith(".ts"):
        return [url[: len(base) - 3] + ".m3u8" + url[len(base):]]
    return []


class SourceIndex:
    def __init__(self):
        self.by_name: dict[str, list[Item]] = {}

    def build(self, live: list[Item]):
        idx: dict[str, list[Item]] = {}
        for it in live:
            k = norm_name(it.name)
            if len(k) >= 3:
                idx.setdefault(k, []).append(it)
        self.by_name = {k: v for k, v in idx.items() if len(v) > 1}

    def alternates(self, it: Item, limit: int = 4) -> list[str]:
        if it.kind != "live" or not it.url:
            return []
        out = list(url_variants(it.url))
        for other in self.by_name.get(norm_name(it.name), []):
            if other.url and other.url != it.url and other.url not in out:
                out.append(other.url)
        return out[:limit]
