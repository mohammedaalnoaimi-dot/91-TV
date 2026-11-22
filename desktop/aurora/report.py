"""Crash reports: notice that 91 TV closed unexpectedly last time and let the person send the details to support
together with their activation code, so we know who it was. Nothing is ever sent without the person pressing the button."""
from __future__ import annotations
import logging, time
from . import __version__
from .paths import data_dir, log_dir

log = logging.getLogger(__name__)
_RUN = lambda: data_dir() / "running.flag"
_CRASH = lambda: log_dir() / "crash.txt"


def mark_running():
    try: _RUN().write_text(str(time.time()), "utf-8")
    except Exception: pass


def mark_clean_exit():
    for f in (_RUN(), _CRASH()):
        try: f.unlink()
        except Exception: pass


def note_exception(text: str):
    try: _CRASH().write_text(text, "utf-8")
    except Exception: pass


def previous_crash() -> str | None:
    """Text describing the last unexpected close, or None if the last run ended normally. Clears the flag."""
    if not _RUN().exists(): return None
    txt = ""
    try:
        if _CRASH().exists(): txt = _CRASH().read_text("utf-8", "replace")
        else:
            lg = (log_dir() / "aurora.log").read_text("utf-8", "replace").splitlines()
            txt = "No error was recorded (the app was closed or killed). Last log lines:\n" + "\n".join(lg[-40:])
    except Exception: pass
    try: _RUN().unlink()
    except Exception: pass
    try: _CRASH().unlink()
    except Exception: pass
    return txt or "No details available."


def send(trace: str, key: str, plan: str = "") -> bool:
    try:
        import platform, requests
        from .lic import PAIR_API
        r = requests.post(PAIR_API + "/report", json={"key": key or "", "plan": plan or "", "app": "windows " + __version__,
                          "device": platform.node()[:40] + " " + platform.platform()[:40], "android": platform.release(), "trace": trace[-4000:]}, timeout=15)
        return r.ok
    except Exception:
        log.exception("crash report send failed"); return False
