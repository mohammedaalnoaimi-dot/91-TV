"""Parental PIN (PBKDF2-hashed, stored in settings), hidden categories and dead-channel bookkeeping helpers."""
from __future__ import annotations
import functools, hashlib, hmac, os, re, time

ADULT_WORDS = ("adult", "xxx", "porn", "18+", "erotic", "sex", "nsfw")


def _hash(pin: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 120_000).hex()


def set_pin(store, pin: str):
    salt = os.urandom(16); store.set("pin_salt", salt.hex()); store.set("pin_hash", _hash(pin, salt))


def clear_pin(store):
    store.set("pin_salt", ""); store.set("pin_hash", "")


def has_pin(store) -> bool: return bool(store.get("pin_hash"))


def check_pin(store, pin: str) -> bool:
    h, s = store.get("pin_hash"), store.get("pin_salt")
    return bool(h and s) and hmac.compare_digest(h, _hash(pin, bytes.fromhex(s)))


def is_adult_group(name: str) -> bool:
    n = (name or "").lower(); return any(w in n for w in ADULT_WORDS)


_PREFIX = re.compile(r"^\s*(?:[\[(]([A-Za-z]{2,3})[\])]\s*\S|([A-Za-z]{2,3})\s*[|:/»>\-]\s*\S)")
SCRIPTS = {"Arabic": [(0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)], "Cyrillic": [(0x0400, 0x052F)], "Hebrew": [(0x0590, 0x05FF)],
           "Greek": [(0x0370, 0x03FF)], "Indic": [(0x0900, 0x0DFF)], "Thai": [(0x0E00, 0x0E7F)], "Chinese/Japanese/Korean": [(0x3040, 0x30FF), (0x4E00, 0x9FFF), (0xAC00, 0xD7AF)]}


def group_prefix(name: str) -> str:
    """'FR| Cinema' -> 'FR', '[AR] News' -> 'AR' (providers prefix categories with a language/country code)."""
    m = _PREFIX.match(name or ""); return (m.group(1) or m.group(2)).upper() if m else ""


@functools.lru_cache(maxsize=300000)
def name_script(text: str) -> str:
    """Dominant non-Latin script of a name ('Arabic', 'Cyrillic'...), or '' when the name is mostly Latin."""
    counts: dict[str, int] = {}; letters = 0
    for ch in text or "":
        if not ch.isalpha(): continue
        letters += 1; o = ord(ch)
        if o < 0x250: continue
        for sc, ranges in SCRIPTS.items():
            if any(a <= o <= b for a, b in ranges): counts[sc] = counts.get(sc, 0) + 1; break
    if not counts: return ""
    sc, n = max(counts.items(), key=lambda kv: kv[1]); return sc if n * 3 >= letters else ""


class Parental:
    """Per-profile hidden categories + session unlock. Hidden means: not shown anywhere until unlocked with the PIN (or always, if no PIN)."""
    def __init__(self, store, profile_id: int):
        self.store, self.pid, self.unlocked = store, profile_id, False

    def hidden(self) -> set[str]:
        return set(self.store.get(f"hidden_cats_{self.pid}") or [])

    def set_hidden(self, groups):
        self.store.set(f"hidden_cats_{self.pid}", sorted(set(groups)))

    # ---- user-chosen hiding (not parental): single channels and whole writing systems
    def hidden_channels(self) -> dict:
        return dict(self.store.get(f"hidden_chans_{self.pid}") or {})

    def hide_channel(self, it):
        d = self.hidden_channels(); d[it.key] = it.name; self.store.set(f"hidden_chans_{self.pid}", d)

    def unhide_channels(self, keys):
        d = self.hidden_channels(); [d.pop(k, None) for k in keys]; self.store.set(f"hidden_chans_{self.pid}", d)

    def hidden_scripts(self) -> set[str]:
        return set(self.store.get(f"hidden_scripts_{self.pid}") or [])

    def set_scripts(self, scripts): self.store.set(f"hidden_scripts_{self.pid}", sorted(set(scripts)))

    def filter(self, items):
        chans, scripts, hid = set(self.hidden_channels()), self.hidden_scripts(), self.hidden()
        show_hid = self.unlocked and has_pin(self.store)
        return [i for i in items if i.key not in chans and not (scripts and name_script(i.name) in scripts) and (show_hid or i.group not in hid)]

    def visible(self, group: str) -> bool:
        if self.unlocked and has_pin(self.store): return True
        return group not in self.hidden()

    def unlock(self, pin: str) -> bool:
        if check_pin(self.store, pin): self.unlocked = True; return True
        return False

    def lock(self): self.unlocked = False


DEAD_AFTER = 3            # consecutive failed recoveries before a channel is auto-hidden
DEAD_RETRY_DAYS = 7       # hidden dead channels get another chance after this long


def now() -> float: return time.time()
