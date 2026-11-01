import logging, platform, sys
from logging.handlers import RotatingFileHandler
from . import __version__
from .paths import log_dir

_done = False


def setup() -> logging.Logger:
    global _done
    root = logging.getLogger()
    if _done:
        return root
    root.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    fh = RotatingFileHandler(log_dir() / "aurora.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt); root.addHandler(fh)
    if sys.stderr:
        sh = logging.StreamHandler(); sh.setLevel(logging.INFO); sh.setFormatter(fmt); root.addHandler(sh)
    _done = True
    log = logging.getLogger("aurora.startup")
    log.info("91 TV %s starting", __version__)
    log.info("Python %s | %s | frozen=%s", sys.version.split()[0], platform.platform(), getattr(sys, "frozen", False))
    sys.excepthook = lambda t, v, tb: logging.getLogger("aurora.crash").critical("Unhandled exception", exc_info=(t, v, tb))
    return root
