"""End-to-end check of the Live TV page + embedded preview against a fake Xtream server (needs a display: run under xvfb-run).
usage: xvfb-run -a -s "-screen 0 2560x1440x24" python tests/e2e_live.py <media_dir_with_test.mkv> <screenshot_dir>"""
import os, subprocess, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
os.environ["AURORA_DATA_DIR"] = tempfile.mkdtemp(prefix="aurora-e2e-"); os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
media, shots = Path(sys.argv[1]), Path(sys.argv[2]); shots.mkdir(parents=True, exist_ok=True)
from PySide6.QtWidgets import QApplication
from aurora import log as _log; _log.setup()
from aurora import player as pl
from aurora.store import Store
from aurora.ui import theme
from aurora.ui.main_window import MainWindow
from fake_server import FakeServer

app = QApplication([]); app.setStyleSheet(theme.QSS)
results = []


def wait(cond, timeout=15.0):
    t = time.time()
    while time.time() - t < timeout:
        app.processEvents()
        try:
            if cond(): return True
        except Exception:
            pass
        time.sleep(0.02)
    return False


def check(name, ok, detail=""):
    results.append(ok); print(("PASS  " if ok else "FAIL  ") + name + (f"  [{detail}]" if detail else ""), flush=True)


def snap(name):
    for _ in range(10): app.processEvents(); time.sleep(0.05)
    out = shots / f"{name}.png"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "x11grab", "-video_size", "2560x1440", "-i", os.environ["DISPLAY"], "-frames:v", "1", str(out)], timeout=30)
    print("saved", out, flush=True)


srv = FakeServer(media)
store = Store(); pid = store.add_playlist(1, "Fake", "xtream", srv.url, "demo", "secret"); store.set_active(1, pid)
w = MainWindow(store, quiet=True); w.resize(2000, 1100); w.move(0, 0); w.show()
check("library loaded from Xtream", wait(lambda: len(w.live) == 2 and len(w.movies) == 3 and len(w.series) == 1), f"{len(w.live)} live")
check("EPG loaded", wait(lambda: bool(w.epg.by_channel)))
w.go(1); lp = w.livep; pv = lp.preview
wait(lambda: lp.model.rowCount() == 2)
lp.view.setCurrentIndex(lp.model.index(0, 0))
check("preview starts playing", wait(lambda: pv.status == "playing" and pv.player and pv.player.position()[0] > 1.0, 20), pv.status)
check("preview muted by default", bool(pv.player and pv.player.m.mute))
check("guide panel shows now-playing", wait(lambda: lp.n_title.text().startswith("News Show")), lp.n_title.text())
check("chip shows LIVE", "LIVE" in lp.chip.text(), lp.chip.text())
if pv.player: print(pl.format_info(pv.player.info()))
snap("live_preview")
# rapid selection -> only the last channel is started (debounce)
n0 = pv.player.current_url if pv.player else ""
for r in (1, 0, 1):
    lp.view.setCurrentIndex(lp.model.index(r, 0)); app.processEvents(); time.sleep(0.05)
want = lp.model.items[1]
check("debounce: last selection wins", wait(lambda: pv.item is not None and pv.item.key == want.key and pv.player.current_url == want.url, 10), pv.item.name if pv.item else "none")
check("second channel plays", wait(lambda: pv.player.position()[0] > 1.0, 15))
lp.b_mute.click(); app.processEvents()
check("unmute toggles audio + saves preference", pv.player.m.mute is False and store.get("preview_muted") is False)
lp.b_mute.click(); app.processEvents()
lp.b_fav.click(); app.processEvents()
check("favorite button toggles My List", store.is_favorite(1, lp.shown) and "In My List" in lp.b_fav.text(), lp.b_fav.text())
# full screen hand-off
it = lp.model.items[0]; lp.view.setCurrentIndex(lp.model.index(0, 0))
lp._play(it)
check("full player opens and preview decoder released", wait(lambda: w.in_player() and pv.player is None and w.playerp.player is not None and w.playerp.player.position()[0] > 1.0, 20))
snap("full_player")
w.leave_player()
check("returns to Live TV and preview resumes", wait(lambda: w.stack.currentIndex() == 1 and pv.status == "playing" and pv.player and pv.player.position()[0] > 0.5, 20))
w.go(0)
check("leaving Live TV stops preview", wait(lambda: pv.item is None and pv.status == "idle"))
w.go(1); wait(lambda: pv.status == "playing", 15)
store.set("preview_enabled", False); w.settings_changed()
lp.view.setCurrentIndex(lp.model.index(1, 0)); wait(lambda: pv.status == "off", 5)
check("preview can be disabled in settings", pv.status == "off" and pv.player is None, pv.status)
store.set("preview_enabled", True)
w.close(); srv.close()
print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
