"""Channel pre-warm: when you are watching a channel, the next and previous ones are contacted in the background (DNS, TLS, provider redirect / token),
so the real switch has less to do. This does NOT decode video in advance."""
from __future__ import annotations
import logging, threading
import requests

log = logging.getLogger(__name__)
_session = requests.Session(); _session.headers["User-Agent"] = "VLC/3.0.20 LibVLC/3.0.20"
_done: dict[str, float] = {}
_lock = threading.Lock()


def warm(urls, now: float):
    todo = []
    with _lock:
        for u in urls:
            if u and u.startswith("http") and now - _done.get(u, 0) > 120: _done[u] = now; todo.append(u)
        if len(_done) > 400: _done.clear()
    if not todo: return
    def work():
        for u in todo:
            try:
                r = _session.get(u, headers={"Range": "bytes=0-2047"}, stream=True, timeout=4, allow_redirects=True); r.close()
            except Exception as e:
                log.debug("warm %s failed: %s", u[:60], e)
    threading.Thread(target=work, daemon=True).start()
