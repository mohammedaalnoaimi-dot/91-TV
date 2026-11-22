"""Automatic updates (Windows portable / per-user install): checks the published version, downloads the new build in the background,
and swaps it in when 91 TV is closed. Nothing here touches your library, playlists or settings (they live in %LOCALAPPDATA%\\91TV)."""
from __future__ import annotations
import logging, os, re, subprocess, sys, tempfile, zipfile
from pathlib import Path
from . import __version__
from .paths import exe_dir

log = logging.getLogger(__name__)
VERSION_URL = "https://raw.githubusercontent.com/mohammedaalnoaimi-dot/91-TV/main/desktop/aurora/__init__.py"
ZIP_URL = "https://github.com/mohammedaalnoaimi-dot/91-TV/releases/download/windows-latest/91TV-Windows.zip"
_ready: Path | None = None


def parse_version(text: str):
    m = re.search(r'__version__\s*=\s*"(\d+(?:\.\d+)*)"', text or "")
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


def newer(remote, local=None) -> bool:
    local = local or parse_version(f'__version__ = "{__version__}"')
    return bool(remote and local and remote > local)


def can_update() -> bool:
    """Only for the packaged Windows app, and only where we are allowed to write (portable zip / per-user install)."""
    return sys.platform == "win32" and getattr(sys, "frozen", False) and os.access(exe_dir(), os.W_OK) and (exe_dir() / "91TV.exe").exists()


def check_and_download() -> bool:
    """Blocking; call from a worker thread. True when a newer build has been downloaded and is waiting to be applied."""
    global _ready
    import requests
    if not can_update(): return False
    try:
        remote = parse_version(requests.get(VERSION_URL, timeout=15).text)
        if not newer(remote): return False
        tmp = Path(tempfile.mkdtemp(prefix="91tv-update-")); zp = tmp / "u.zip"
        with requests.get(ZIP_URL, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(zp, "wb") as f:
                for chunk in r.iter_content(1 << 20): f.write(chunk)
        with zipfile.ZipFile(zp) as z:
            if zp.stat().st_size < 20_000_000 or z.testzip() is not None or not any(n.endswith("91TV/91TV.exe") or n == "91TV.exe" for n in z.namelist()):
                raise RuntimeError("downloaded update is not a valid 91 TV package")
            z.extractall(tmp / "x")
        src = tmp / "x" / "91TV" if (tmp / "x" / "91TV" / "91TV.exe").exists() else tmp / "x"
        if not (src / "91TV.exe").exists(): raise RuntimeError("update package has no 91TV.exe")
        _ready = src; log.info("update %s downloaded and waiting for exit", ".".join(map(str, remote))); return True
    except Exception:
        log.exception("auto-update check failed"); return False


def apply_on_exit():
    """Call as the app quits: starts a tiny detached script that waits for us to exit, copies the new files over, and relaunches."""
    if not _ready or not can_update(): return
    try:
        dst = exe_dir(); bat = _ready.parent / "apply.bat"
        bat.write_text("@echo off\r\nping 127.0.0.1 -n 3 >nul\r\n:w\r\ntasklist /FI \"PID eq %d\" 2>nul | find \"%d\" >nul && (ping 127.0.0.1 -n 2 >nul & goto w)\r\n"
                       "robocopy \"%s\" \"%s\" /E /NFL /NDL /NJH /NJS /R:5 /W:1 >nul\r\nstart \"\" \"%s\"\r\n" % (os.getpid(), os.getpid(), _ready, dst, dst / "91TV.exe"), "utf-8")
        subprocess.Popen(["cmd", "/c", str(bat)], creationflags=0x08000000 | 0x00000008, close_fds=True)      # CREATE_NO_WINDOW | DETACHED_PROCESS
    except Exception:
        log.exception("could not start the update script")
