"""E2E: single-click a series -> Netflix-style detail page -> seasons -> play episode -> back. Needs a display (xvfb-run).
usage: xvfb-run -a -s "-screen 0 2560x1440x24" python tests/e2e_series.py <media_dir_with_test.mkv> <screenshot_dir>"""
import os, subprocess, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
os.environ["AURORA_DATA_DIR"] = tempfile.mkdtemp(prefix="aurora-e2e-"); os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
media, shots = Path(sys.argv[1]), Path(sys.argv[2]); shots.mkdir(parents=True, exist_ok=True)
from PySide6.QtWidgets import QApplication
from aurora import log as _log; _log.setup()
from aurora.store import Store
from aurora.ui import theme
from aurora.ui.main_window import MainWindow
from aurora.ui.widgets import ITEM_ROLE
from fake_server import FakeServer

app = QApplication([]); app.setStyleSheet(theme.QSS); results = []


def wait(cond, timeout=15.0):
    t = time.time()
    while time.time() - t < timeout:
        app.processEvents()
        try:
            if cond(): return True
        except Exception: pass
        time.sleep(0.02)
    return False


def check(name, ok, detail=""):
    results.append(bool(ok)); print(("PASS  " if ok else "FAIL  ") + name + (f"  [{detail}]" if detail else ""), flush=True)


def snap(name):
    for _ in range(10): app.processEvents(); time.sleep(0.05)
    out = shots / f"{name}.png"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "x11grab", "-video_size", "2560x1440", "-i", os.environ["DISPLAY"], "-frames:v", "1", str(out)], timeout=30)
    print("saved", out, flush=True)


srv = FakeServer(media); store = Store(); pid = store.add_playlist(1, "Fake", "xtream", srv.url, "demo", "secret"); store.set_active(1, pid)
w = MainWindow(store, quiet=True); w.resize(2000, 1100); w.move(0, 0); w.show()
check("library loaded", wait(lambda: len(w.series) == 1))
w.go(3); sp = w.seriesp; wait(lambda: sp.model.rowCount() == 1)
sp.view.clicked.emit(sp.model.index(0, 0))          # ONE click
check("single click opens the series page (not a dialog)", wait(lambda: w.stack.currentIndex() == w.P_DETAIL, 10))
d = w.detail
check("title cleaned", d.title.text() == "Test Series", d.title.text())
check("meta shows year, rating, seasons, genre", all(x in d.meta.text() for x in ("2020", "8.1", "2 seasons", "Drama")), d.meta.text())
check("plot + cast shown", "gripping" in d.plot.text() and "Ada Tester" in d.cast.text())
check("episodes listed for season 1 with cleaned titles", [e.title for e in d.model.eps] == ["Episode 1", "The Second One"], str([e.title for e in d.model.eps]))
check("season selector present", not d.season.isHidden() and d.season.count() == 2)
check("play button targets S1 E1", "Play S1 E1" in d.b_play.text(), d.b_play.text())
snap("series_page")
d.season.setCurrentIndex(1); app.processEvents()
check("switching season shows season 2", [e.title for e in d.model.eps] == ["Return"], str([e.title for e in d.model.eps]))
d.season.setCurrentIndex(0); app.processEvents()
d.b_fav.click(); app.processEvents()
check("My List button toggles", store.is_favorite(1, d.item) and "In My List" in d.b_fav.text(), d.b_fav.text())
d.view.clicked.emit(d.model.index(1, 0)); d.view.clicked.emit(d.model.index(1, 0))     # double click -> must start only once
check("clicking an episode plays it full screen", wait(lambda: w.in_player() and w.playerp.player is not None and w.playerp.player.position()[0] > 1.0, 20))
check("player title is clean", "Test Series - S01E02" in w.playerp.title.text() and "4K-AR-DO" not in w.playerp.title.text(), w.playerp.title.text())
snap("series_playing")
w.leave_player()
check("Back from player returns to the series page", wait(lambda: w.stack.currentIndex() == w.P_DETAIL, 5))
w.close_detail()
check("Back from series page returns to TV Series grid", w.stack.currentIndex() == 3)
w.open_series(sp.model.items[0])
check("re-open shows Resume button for last watched episode", wait(lambda: w.stack.currentIndex() == w.P_DETAIL and "Resume S1 E2" in d.b_play.text(), 10), d.b_play.text())
w.close(); srv.close()
print(f"\n{sum(results)}/{len(results)} checks passed"); sys.exit(0 if all(results) else 1)
