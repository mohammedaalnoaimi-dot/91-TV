"""Local persistence: profiles, playlists, favorites, recents, settings (SQLite)."""
from __future__ import annotations
import json, sqlite3, threading, time
from dataclasses import dataclass
from . import secrets
from .models import Item
from .paths import data_dir

DEFAULTS = {
    "hwdec": "auto-safe", "volume": 100, "audio_device": "auto", "hdr": "auto",
    "pass_ac3": False, "pass_eac3": False, "pass_dts": False, "pass_hd": False, "audio_exclusive": False,
    "max_reconnects": 6, "epg_url": "", "sub_lang": "", "audio_lang": "", "active_profile": 1, "upscale": "off", "preview_enabled": True, "preview_muted": True, "preview_volume": 70,
    "tmdb_key": "", "quality": "balanced", "denoise": "off", "deinterlace": "auto", "hdr_enhance": False, "accent": "rose", "animations": True, "ui_scale": 100, "tenfoot": False, "scrub_thumbs": False, "tmdb_replace": False, "motion": "off", "display_peak": 0, "tone_mapping": "auto", "timeshift": 5, "auto_hide_dead": True, "wizard_done": False, "gamepad": True,
    "pt_method": 8, "pt_header": True, "pt_remind": 0, "omdb_key": "", "ss_on": True, "ss_minutes": 2, "who": "mr", "theme_v": 0,
}


@dataclass
class Playlist:
    id: int
    profile_id: int
    name: str
    type: str          # m3u | xtream
    source: str        # url/path or server
    username: str = ""
    secret: str = ""   # password (xtream) or full URL (m3u url) - from keyring when possible
    epg_url: str = ""


class Store:
    def __init__(self, path=None):
        self.db = sqlite3.connect(str(path or data_dir() / "aurora.db"), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.db.executescript("""
            CREATE TABLE IF NOT EXISTS profiles(id INTEGER PRIMARY KEY, name TEXT UNIQUE);
            CREATE TABLE IF NOT EXISTS playlists(id INTEGER PRIMARY KEY, profile_id INT, name TEXT, type TEXT, source TEXT,
                username TEXT DEFAULT '', fallback_secret TEXT DEFAULT '', epg_url TEXT DEFAULT '', active INT DEFAULT 0);
            CREATE TABLE IF NOT EXISTS favorites(profile_id INT, key TEXT, data TEXT, PRIMARY KEY(profile_id,key));
            CREATE TABLE IF NOT EXISTS recents(profile_id INT, key TEXT, data TEXT, played_at REAL, position REAL DEFAULT 0, PRIMARY KEY(profile_id,key));
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS dead(profile_id INT, key TEXT, name TEXT, fails INT DEFAULT 0, hidden_at REAL DEFAULT 0, PRIMARY KEY(profile_id,key));
            """)
            self.db.execute("CREATE TABLE IF NOT EXISTS picture(key TEXT PRIMARY KEY, data TEXT)")
            try: self.db.execute("ALTER TABLE recents ADD COLUMN dur REAL DEFAULT 0")
            except sqlite3.OperationalError: pass
            fresh = self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='wl'").fetchone() is None
            self.db.execute("CREATE TABLE IF NOT EXISTS wl(profile_id INT, owner TEXT, key TEXT, data TEXT, PRIMARY KEY(profile_id,owner,key))")
            if fresh:      # first run of the Mr / Mrs lists: everything already saved becomes Mr's list
                self.db.execute("INSERT OR IGNORE INTO wl SELECT profile_id,'mr',key,data FROM favorites")
            if not self.db.execute("SELECT 1 FROM profiles").fetchone():
                self.db.execute("INSERT INTO profiles(id,name) VALUES(1,'Default')")
            self.db.commit()
        if self.get("upscale") == "high" and self._raw("quality") is None: self.set("quality", "max")

    def _raw(self, key):
        with self.lock:
            r = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(r[0]) if r else None

    # settings
    def get(self, key):
        with self.lock:
            r = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(r[0]) if r else DEFAULTS.get(key)

    def set(self, key, value):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (key, json.dumps(value))); self.db.commit()

    # TMDB key lives in the credential store when possible
    def tmdb_key(self) -> str:
        return secrets.get_secret("tmdb-key") or self.get("tmdb_key") or ""

    def set_tmdb_key(self, key: str):
        key = key.strip()
        if key and secrets.set_secret("tmdb-key", key): self.set("tmdb_key", "")
        else:
            if not key: secrets.delete_secret("tmdb-key")
            self.set("tmdb_key", key)

    # profiles
    def profiles(self):
        with self.lock:
            return [(r["id"], r["name"]) for r in self.db.execute("SELECT id,name FROM profiles ORDER BY id")]

    def add_profile(self, name: str) -> int:
        with self.lock:
            cur = self.db.execute("INSERT INTO profiles(name) VALUES(?)", (name.strip(),)); self.db.commit(); return cur.lastrowid

    def delete_profile(self, pid: int):
        if pid == 1:
            return
        for pl in self.playlists(pid):
            self.delete_playlist(pl.id)
        with self.lock:
            for t in ("favorites", "recents", "wl"):
                self.db.execute(f"DELETE FROM {t} WHERE profile_id=?", (pid,))
            self.db.execute("DELETE FROM profiles WHERE id=?", (pid,)); self.db.commit()

    # playlists
    def add_playlist(self, profile_id, name, type_, source, username="", secret="", epg_url="") -> int:
        with self.lock:
            cur = self.db.execute("INSERT INTO playlists(profile_id,name,type,source,username,epg_url) VALUES(?,?,?,?,?,?)",
                                  (profile_id, name, type_, source if type_ == "xtream" or not source.lower().startswith("http") else "(stored securely)", username, epg_url))
            pid = cur.lastrowid
            sec = secret if type_ == "xtream" else (source if source.lower().startswith("http") else "")
            if sec:
                if not secrets.set_secret(f"playlist-{pid}", sec):
                    self.db.execute("UPDATE playlists SET fallback_secret=? WHERE id=?", (sec, pid))
            self.db.commit(); return pid

    def _pl(self, r) -> Playlist:
        sec = secrets.get_secret(f"playlist-{r['id']}") or r["fallback_secret"] or ""
        source = r["source"]
        if r["type"] == "m3u" and source == "(stored securely)":
            source = sec; sec = ""
        return Playlist(r["id"], r["profile_id"], r["name"], r["type"], source, r["username"], sec, r["epg_url"])

    def playlists(self, profile_id) -> list[Playlist]:
        with self.lock:
            return [self._pl(r) for r in self.db.execute("SELECT * FROM playlists WHERE profile_id=? ORDER BY id", (profile_id,))]

    def get_playlist(self, pid):
        with self.lock:
            r = self.db.execute("SELECT * FROM playlists WHERE id=?", (pid,)).fetchone()
        return self._pl(r) if r else None

    def active_playlist(self, profile_id):
        with self.lock:
            r = self.db.execute("SELECT * FROM playlists WHERE profile_id=? AND active=1", (profile_id,)).fetchone()
        if r:
            return self._pl(r)
        pls = self.playlists(profile_id)
        return pls[0] if pls else None

    def set_active(self, profile_id, pid):
        with self.lock:
            self.db.execute("UPDATE playlists SET active=0 WHERE profile_id=?", (profile_id,))
            self.db.execute("UPDATE playlists SET active=1 WHERE id=?", (pid,)); self.db.commit()

    def delete_playlist(self, pid):
        secrets.delete_secret(f"playlist-{pid}")
        with self.lock:
            self.db.execute("DELETE FROM playlists WHERE id=?", (pid,)); self.db.commit()

    # favorites / recents
    @staticmethod
    def _dump(it: Item):
        return json.dumps({"name": it.name, "kind": it.kind, "url": it.url, "group": it.group, "logo": it.logo,
                           "tvg_id": it.tvg_id, "ext_id": it.ext_id, "plot": it.plot, "year": it.year, "rating": it.rating})

    @staticmethod
    def _load(s) -> Item:
        return Item(**json.loads(s))

    # "My List" is two lists now: Mr's and Mrs's (plus Together = titles on both). The heart / "My List" actions use whoever is selected (setting "who").
    def who(self) -> str:
        return "mrs" if self.get("who") == "mrs" else "mr"

    def wl_has(self, pid, owner, it: Item) -> bool:
        with self.lock:
            return self.db.execute("SELECT 1 FROM wl WHERE profile_id=? AND owner=? AND key=?", (pid, owner, it.key)).fetchone() is not None

    def wl_add(self, pid, owner, it: Item):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO wl VALUES(?,?,?,?)", (pid, owner, it.key, self._dump(it))); self.db.commit()

    def wl_remove(self, pid, owner, it: Item):
        with self.lock:
            self.db.execute("DELETE FROM wl WHERE profile_id=? AND owner=? AND key=?", (pid, owner, it.key)); self.db.commit()

    def wl_items(self, pid, owner, kind=None) -> list[Item]:
        with self.lock:
            rows = self.db.execute("SELECT data FROM wl WHERE profile_id=? AND owner=?", (pid, owner)).fetchall()
        its = [self._load(r[0]) for r in rows]
        return [i for i in its if not kind or i.kind == kind]

    def wl_together(self, pid) -> list[Item]:
        both = {i.key for i in self.wl_items(pid, "mrs")}
        return [i for i in self.wl_items(pid, "mr") if i.key in both]

    def is_favorite(self, pid, it: Item) -> bool:
        return self.wl_has(pid, self.who(), it)

    def toggle_favorite(self, pid, it: Item) -> bool:
        o = self.who()
        if self.wl_has(pid, o, it): self.wl_remove(pid, o, it); return False
        self.wl_add(pid, o, it); return True

    def favorites(self, pid, kind=None) -> list[Item]:
        return self.wl_items(pid, self.who(), kind)

    def add_recent(self, pid, it: Item, position=0.0):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO recents(profile_id,key,data,played_at,position) VALUES(?,?,?,?,?)", (pid, it.key, self._dump(it), time.time(), position))
            self.db.execute("DELETE FROM recents WHERE profile_id=? AND key NOT IN (SELECT key FROM recents WHERE profile_id=? ORDER BY played_at DESC LIMIT 100)", (pid, pid))
            self.db.commit()

    def recents(self, pid, kind=None, limit=40) -> list[Item]:
        with self.lock:
            rows = self.db.execute("SELECT data FROM recents WHERE profile_id=? ORDER BY played_at DESC", (pid,)).fetchall()
        its = [self._load(r[0]) for r in rows]
        return [i for i in its if not kind or i.kind == kind][:limit]

    def position(self, pid, it: Item) -> float:
        with self.lock:
            r = self.db.execute("SELECT position FROM recents WHERE profile_id=? AND key=?", (pid, it.key)).fetchone()
        return r[0] if r else 0.0

    def save_position(self, pid, it: Item, pos: float, dur: float = 0.0):
        with self.lock:
            self.db.execute("UPDATE recents SET position=?, dur=CASE WHEN ?>0 THEN ? ELSE dur END WHERE profile_id=? AND key=?", (pos, dur, dur, pid, it.key)); self.db.commit()

    def progress(self, pid) -> dict:
        """key -> fraction watched (0..1) for titles with a known length; used for the bars on 'Continue watching'."""
        with self.lock:
            rows = self.db.execute("SELECT key, position, dur FROM recents WHERE profile_id=? AND dur>0 AND position>0", (pid,)).fetchall()
        return {k: min(1.0, p / d) for k, p, d in rows}

    # per-channel picture profiles
    def picture_profile(self, key: str) -> dict:
        with self.lock:
            r = self.db.execute("SELECT data FROM picture WHERE key=?", (key,)).fetchone()
        return json.loads(r[0]) if r else {}

    def set_picture_profile(self, key: str, data: dict):
        with self.lock:
            if data: self.db.execute("INSERT OR REPLACE INTO picture VALUES(?,?)", (key, json.dumps(data)))
            else: self.db.execute("DELETE FROM picture WHERE key=?", (key,))
            self.db.commit()

    # dead-channel bookkeeping
    def dead_fail(self, pid, it: Item, threshold: int) -> bool:
        """Record a failed playback; returns True when the channel just crossed the hide threshold."""
        with self.lock:
            r = self.db.execute("SELECT fails, hidden_at FROM dead WHERE profile_id=? AND key=?", (pid, it.key)).fetchone()
            fails = (r[0] if r else 0) + 1; was_hidden = bool(r and r[1])
            hide = fails >= threshold
            self.db.execute("INSERT OR REPLACE INTO dead VALUES(?,?,?,?,?)", (pid, it.key, it.name, fails, (r[1] if was_hidden else (time.time() if hide else 0))))
            self.db.commit(); return hide and not was_hidden

    def dead_ok(self, pid, it: Item):
        with self.lock:
            self.db.execute("DELETE FROM dead WHERE profile_id=? AND key=?", (pid, it.key)); self.db.commit()

    def dead_hidden(self, pid, retry_after_days=7) -> dict:
        """key -> name of channels currently auto-hidden (entries older than retry_after_days are released for a retest)."""
        cut = time.time() - retry_after_days * 86400
        with self.lock:
            self.db.execute("DELETE FROM dead WHERE profile_id=? AND hidden_at>0 AND hidden_at<?", (pid, cut)); self.db.commit()
            return {r[0]: r[1] for r in self.db.execute("SELECT key,name FROM dead WHERE profile_id=? AND hidden_at>0", (pid,))}

    def dead_restore(self, pid, key=None):
        with self.lock:
            if key: self.db.execute("DELETE FROM dead WHERE profile_id=? AND key=?", (pid, key))
            else: self.db.execute("DELETE FROM dead WHERE profile_id=?", (pid,))
            self.db.commit()
