from __future__ import annotations
import logging, os, sys, tempfile, time, traceback


def selftest() -> int:
    """Headless-capable self check. Writes <logs>/selftest.txt. Returns 0 if everything essential passed."""
    os.environ.setdefault("AURORA_DATA_DIR", tempfile.mkdtemp(prefix="aurora-selftest-"))
    from . import secrets as _sec
    _sec._ok = False        # the self-test must never write to the real Windows Credential Manager (it once overwrote a playlist password with "p")
    from . import log as _log, __version__, m3u, secrets, player
    from .paths import log_dir
    _log.setup()
    res, ok = [], True

    def check(name, fn, essential=True):
        nonlocal ok
        try:
            r = fn(); res.append(f"PASS  {name}" + (f" - {r}" if r else ""))
        except Exception as e:
            res.append(f"{'FAIL' if essential else 'WARN'}  {name} - {type(e).__name__}: {e}")
            logging.getLogger("selftest").exception(name)
            if essential: ok = False
    sample = "#EXTM3U\n#EXTINF:-1 group-title=\"News\",Test Channel\nhttp://example.invalid/1.m3u8\n"
    check("M3U parser", lambda: len(m3u.parse(sample)) == 1 or (_ for _ in ()).throw(AssertionError("parse")))
    from .store import Store
    from .models import Item
    def st():
        s = Store(os.path.join(os.environ["AURORA_DATA_DIR"], "t.db")); s.add_playlist(1, "t", "xtream", "http://h", "u", "p"); it = Item("x", url="http://a")
        s.toggle_favorite(1, it); assert s.is_favorite(1, it); return "ok"
    check("Database", st)
    check("Credential store", lambda: secrets.backend() if secrets.available() else (_ for _ in ()).throw(RuntimeError("no keyring backend; local fallback in use")), essential=False)
    def eng():
        m = player.load_mpv()
        if not m: raise RuntimeError(player.mpv_error())
        return "libmpv loaded"
    check("libmpv (video engine)", eng, essential=False)
    def ui():
        from PySide6.QtWidgets import QApplication
        from .ui.main_window import MainWindow
        from .ui import theme
        app = QApplication.instance() or QApplication([]); theme.load_fonts(); app.setStyleSheet(theme.QSS)
        w = MainWindow(Store(os.path.join(os.environ["AURORA_DATA_DIR"], "ui.db")), quiet=True); w.show()
        t = time.time()
        while time.time() - t < 1.0: app.processEvents()
        w.close(); return "main window created and closed"
    check("User interface", ui)
    res.append(f"91 TV {__version__} | Python {sys.version.split()[0]} | {sys.platform}")
    out = "\n".join(res); (log_dir() / "selftest.txt").write_text(out + "\n", "utf-8")
    print(out)
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    from . import log as _log
    _log.setup()
    log = logging.getLogger("aurora")
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication
        from .paths import asset
        from .store import Store
        from .ui import theme
        from .ui.main_window import MainWindow
        if sys.platform == "win32":
            try:
                import ctypes; ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AURORA.IPTV.1")
            except Exception:
                pass
        store = Store()
        scale = max(int(store.get("ui_scale") or 100), 140 if store.get("tenfoot") else 0) / 100.0      # text/UI size (restart to change); 10-foot mode implies >= 140 %
        if scale != 1.0: os.environ.setdefault("QT_SCALE_FACTOR", f"{scale:.2f}")
        if int(store.get("theme_v") or 0) < 1: store.set("accent", "rose"); store.set("theme_v", 1)      # one-time switch to the new look's rose accent
        theme.set_accent(store.get("accent") or "rose"); theme.TENFOOT = bool(store.get("tenfoot")); theme.QSS = theme.build()
        app = QApplication(sys.argv); app.setApplicationName("91 TV"); theme.load_fonts(); app.setStyleSheet(theme.QSS)
        if asset("aurora.ico").exists(): app.setWindowIcon(QIcon(str(asset("aurora.ico"))))
        from . import lic as _lic
        from .ui.dialogs import ActivationDialog
        lic = _lic.Lic(store)
        if _lic.REQUIRED and lic.needs_screen():
            if ActivationDialog(lic).exec() != ActivationDialog.Accepted and not lic.ok():
                return 0
        if not lic.ok():
            return 0
        if lic.recheck_due():
            import threading; threading.Thread(target=lic.refresh, daemon=True).start()
        w = MainWindow(store); w.show()
        if theme.TENFOOT: w.showMaximized()
        log.info("UI ready")
        return app.exec()
    except Exception:
        log.critical("Fatal startup error", exc_info=True)
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            QApplication.instance() or QApplication([])
            QMessageBox.critical(None, "91 TV", "91 TV failed to start.\n\n" + traceback.format_exc()[-900:] + "\n\nSee the log folder: %LOCALAPPDATA%\\91TV\\logs")
        except Exception:
            pass
        return 2
