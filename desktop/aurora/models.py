from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Item:
    """A live channel, a movie, or a series (episodes resolved on demand)."""
    name: str
    kind: str = "live"            # live | movie | series
    url: str = ""
    group: str = ""
    logo: str = ""
    tvg_id: str = ""
    plot: str = ""
    year: str = ""
    rating: str = ""
    ext_id: str = ""              # Xtream stream_id / series_id
    extra: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.url or self.ext_id or self.name}"


@dataclass
class Episode:
    title: str
    url: str
    season: int = 1
    number: int = 1
    plot: str = ""
    image: str = ""
    duration: str = ""


@dataclass
class Programme:
    start: float   # epoch seconds
    stop: float
    title: str
    desc: str = ""
