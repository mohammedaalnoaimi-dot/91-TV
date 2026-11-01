"""Filesystem locations (per-user, no admin rights needed)."""
import os, sys
from pathlib import Path


def app_dir() -> Path:
    """Folder containing the running app (PyInstaller aware)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def exe_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return app_dir()


def data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or (os.path.join(Path.home(), "Library", "Application Support") if sys.platform == "darwin" else os.path.join(Path.home(), ".local", "share"))
    p = Path(os.environ.get("AURORA_DATA_DIR") or Path(base) / "91TV")
    p.mkdir(parents=True, exist_ok=True)
    return p


def log_dir() -> Path:
    p = data_dir() / "logs"; p.mkdir(parents=True, exist_ok=True); return p


def cache_dir() -> Path:
    p = data_dir() / "cache"; p.mkdir(parents=True, exist_ok=True); return p


def asset(name: str) -> Path:
    return app_dir() / "assets" / name
