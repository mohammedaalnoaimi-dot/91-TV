"""Ready-made lists built from what the provider sends: recently added, top rated, new releases, Hollywood / English."""
from __future__ import annotations
import re, datetime

SPECIALS = [("@recent", "Recently added"), ("@top", "Top rated"), ("@new", "New releases"), ("@hollywood", "Hollywood / English")]
HOLLY = re.compile(r"hollywood|english|\bEN\b|^\s*EN\s*[|:\-\]]|\bUSA?\b|\bUK\b", re.I)
YEAR = re.compile(r"\((\d{4})\)")


def added(it) -> int:
    try: return int(float((it.extra or {}).get("added") or 0))
    except (TypeError, ValueError): return 0


def score(it) -> float:
    try: v = float(it.rating)
    except (TypeError, ValueError): return 0.0
    return v if 0 < v <= 10 else 0.0


def year(it) -> int:
    m = YEAR.search(it.name or "")
    if m: return int(m.group(1))
    try: return int(str(it.year)[:4])
    except ValueError: return 0


def build(which: str, items: list, kind: str = "movie") -> list:
    if which == "@recent": return sorted([i for i in items if added(i) > 0], key=added, reverse=True)[:300]
    if which == "@top": return sorted([i for i in items if score(i) > 0], key=score, reverse=True)[:300]
    if which == "@new":
        y = datetime.date.today().year - 1
        return sorted([i for i in items if year(i) >= y], key=added, reverse=True)[:300]
    if which == "@hollywood" and kind == "movie": return sorted([i for i in items if HOLLY.search(i.group or "")], key=score, reverse=True)[:1500]
    return []


def rank(items: list, q: str, cap: int = 300) -> list:
    """Every word must match; titles that start with the first word come first, then word-start matches, then the rest; better rated first."""
    toks = [t for t in re.split(r"[\s\-._]+", q.lower()) if t]
    if not toks: return []
    first = toks[0]; out = []
    for it in items:
        n = (it.name or "").lower()
        if all(t in n for t in toks):
            w = 0 if n.startswith(first) else 1 if (" " + first) in n else 2
            out.append((w, -score(it), it))
    out.sort(key=lambda x: (x[0], x[1]))
    return [x[2] for x in out[:cap]]


def because(recents: list, pool: list, rows: int = 3, per: int = 30) -> list:
    """'Because you watched X' rows from your own history: same category as a title you watched, not watched yet, better rated first. Returns [(title, items)]."""
    watched = {i.key for i in recents}; by_group: dict = {}
    for it in pool:
        if it.group: by_group.setdefault((it.kind, it.group), []).append(it)
    out, used = [], set()
    for r in recents:
        if r.kind not in ("movie", "series") or not r.group or (r.kind, r.group) in used: continue
        cand = [i for i in by_group.get((r.kind, r.group), []) if i.key not in watched]
        if len(cand) < 6: continue
        used.add((r.kind, r.group)); cand.sort(key=lambda i: (score(i), added(i)), reverse=True); out.append((r.name, cand[:per]))
        if len(out) >= rows: break
    return out
