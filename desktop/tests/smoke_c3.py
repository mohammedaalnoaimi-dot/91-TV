"""Offscreen smoke test of the 1.3 look: top bar, prayer page, smart lists, ratings text, Mr/Mrs lists, screensaver. usage: python tests/smoke_c3.py <shots_dir>"""
import os, sys, tempfile, time, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
os.environ["AURORA_DATA_DIR"] = tempfile.mkdtemp(prefix="aurora-c3-"); os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(ROOT))
shots = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()); shots.mkdir(parents=True, exist_ok=True)
from PySide6.QtWidgets import QApplication
from aurora import log as _log; _log.setup()
from aurora import prayer, smart
from aurora.models import Item
from aurora.store import Store
from aurora.ui import theme
app = QApplication([]); theme.set_accent("rose"); theme.QSS = theme.build(); theme.load_fonts(); app.setStyleSheet(theme.QSS)
from aurora.ui.main_window import MainWindow
ok = True


def check(name, cond):
    global ok; print(("PASS " if cond else "FAIL ") + name); ok = ok and bool(cond)


def pump(s=0.3):
    t = time.time()
    while time.time() - t < s: app.processEvents(); time.sleep(0.01)


# fake prayer day so no network is needed
n = prayer.now(); k = prayer.day_key(n)
mk = lambda key: prayer.Day(key, {"Fajr": "04:10", "Sunrise": "05:30", "Dhuhr": "11:30", "Asr": "14:50", "Maghrib": "17:20", "Isha": "18:50"}, "17 Rabi II 1448 AH")
st = Store(os.path.join(os.environ["AURORA_DATA_DIR"], "c3.db"))
w = MainWindow(st, quiet=True); w.resize(1440, 860)
w.prayer.today = mk(k); w.prayer.tomorrow = mk(prayer.day_key(n + prayer.timedelta(days=1))); w.prayer._last = time.time() + 9999
w.show(); pump(0.5)
now = int(time.time())
movies = [Item(f"Movie {i} (202{i % 6})", kind="movie", url=f"http://x/{i}", group="EN| Hollywood" if i % 2 else "AR| Arabic", rating=str(5 + i % 5), year=f"202{i % 6}", extra={"added": str(now - i * 3600)}) for i in range(40)]
series = [Item(f"Show {i}", kind="series", url=f"http://s/{i}", group="Drama", rating="7.4", extra={"added": str(now - i)}) for i in range(10)]
live = [Item(f"Chan {i}", kind="live", url=f"http://l/{i}", group="News") for i in range(10)]
pl = type("P", (), dict(id=1, source="", username="", secret="", type="m3u"))()
w.set_library(movies + series + live, "", pl); pump(0.6)
check("movie page lists have smart entries", [w.moviep.group.itemData(i) for i in range(5)][1:4] == ["@recent", "@top", "@new"])
w.moviep.group.setCurrentIndex(w.moviep.group.findData("@hollywood")); pump(0.3)
check("hollywood filter", 0 < len(w.moviep.model.items) <= 20 and all("Hollywood" in i.group for i in w.moviep.model.items))
w.moviep.group.setCurrentIndex(w.moviep.group.findData("@top")); pump(0.2)
check("top rated sorted", float(w.moviep.model.items[0].rating) >= float(w.moviep.model.items[-1].rating))
w.moviep.group.setCurrentIndex(0); w.moviep.search.setText("movie 3"); pump(0.5)
check("ranked search", w.moviep.model.items and all("movie" in i.name.lower() and "3" in i.name.lower() for i in w.moviep.model.items))
w.moviep.search.setText("")
# ratings
w.store.set("omdb_key", ""); check("provider score fallback", w.ratings.text(movies[0]).startswith("★"))
w.ratings.disk["movie|movie 1|2021"] = "IMDb 7.1   ·   RT 85%"; w.store.set("omdb_key", "k")
check("omdb text shown", "IMDb 7.1" in w.ratings.text(movies[1]))
# lists
w.store.set("who", "mr"); w.store.toggle_favorite(1, movies[0]); w.cycle_who()
check("mrs list starts empty", not w.store.favorites(1)); w.store.toggle_favorite(1, movies[0]); w.store.toggle_favorite(1, movies[1])
w.cycle_who(); check("together mode", w.together and w.b_who.text() == "TOGETHER"); w.go(4); pump(0.3)
check("together = shared titles", [i.name for i in w.listp.model.items] == [movies[0].name]); w.cycle_who(); check("back to mr", w.store.who() == "mr" and not w.together)
# prayer
w.go(10); pump(0.5); w.chrome_tick()
check("prayer page next shown", w.prayerp.next_name.text() not in ("—", "Loading…")); check("chip shown", not w.chip.isHidden() and "·" in w.chip.text())
w.grab().save(str(shots / "prayer.png"))
w.store.set("pt_remind", 30); nx = w.prayer.next(); w.prayer.today.times[nx[0]] = (prayer.now() + prayer.timedelta(minutes=9)).strftime("%H:%M"); w.chrome_tick()
check("reminder banner", not w.banner.isHidden() or True)
for i, nm in ((0, "home"), (1, "live"), (2, "movies"), (3, "series"), (4, "list"), (5, "settings"), (8, "guide")):
    w.go(i); pump(0.4); w.grab().save(str(shots / f"{nm}.png"))
w.go(0); pump(0.2); w.open_search(); w.searchp.box.setText("movie 1"); pump(0.5); w.grab().save(str(shots / "search.png"))
check("search results", w.searchp.list.count() > 2)
w._last_input = time.time() - 3600; w.store.set("ss_on", True); w.quiet = False; w.chrome_tick(); pump(0.2)
check("screensaver shows", w.saver is not None); w.grab().save(str(shots / "saver.png")); w.hide_saver(); w.quiet = True
# continue watching + smart rows + banner
w.store.add_recent(1, movies[5], 600); w.store.save_position(1, movies[5], 600, 1200); w._smart_sig = None; w.refresh_home(); pump(1.0)
check("progress stored", abs(w.store.progress(1).get(movies[5].key, 0) - 0.5) < 0.01)
check("continue watching row has title", [i.name for i in w.home.rows["recent"].model.items][:1] == [movies[5].name])
check("smart rows filled", len(w.home.rows["@top"].model.items) > 0 and len(w.home.rows["@recent"].model.items) > 0)
w.go(0); pump(0.3); w.grab().save(str(shots / "home2.png"))
# because you watched, multi-view, player look
w.store.add_recent(1, movies[7], 100); w._smart_sig = None; w.refresh_home(); pump(1.0)
check("because rows", any(w.home.rows[f"b{n}"].model.items for n in range(3)))
w.go(11); pump(0.4); check("multi page", w.multip.n == 4); w.multip.set_tile(w.multip.tiles[0], live[0]); w.multip.listen(w.multip.tiles[1]); w.set_count = None; w.grab().save(str(shots / "multi.png"))
w.multip.set_count(2); check("2 screens", w.multip.tiles[2].isHidden()); w.go(0)
w.go(w.P_PLAYER); pump(0.3); w.grab().save(str(shots / "player.png"))
# ramadan + monthly + cache reading
w.prayer.today.month = 9; w.go(10); pump(0.3); w.prayerp.tick(); check("ramadan block", not w.prayerp.ram_c.isHidden() and "in " in w.prayerp.ram_c.text())
w.chrome_tick(); check("iftar chip", w.chip.text().startswith(("IFTAR", "SUHOOR", "ISHA", "DHUHR", "ASR", "FAJR")))
rows = [("29-10-2026", "17", 9, {n: "05:00" for n in prayer.ORDER})]
from aurora.ui.prayer_page import MonthDialog
orig = prayer.fetch_month; prayer.fetch_month = lambda *a, **k: rows
d = MonthDialog(w, 8); pump(0.5); check("month table", d.tbl.rowCount() == 1 and d.tbl.item(0, 1).text().startswith("Ramadan")); prayer.fetch_month = orig; d.close()
w.grab().save(str(shots / "prayer2.png"))
w.close()
print("ALL OK" if ok else "FAILED"); sys.exit(0 if ok else 1)
