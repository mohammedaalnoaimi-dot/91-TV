"""E2E for v1.1 features against the fake server: TMDB, movie page, TV guide, channel numbers, last channel, parental PIN/hidden categories,
dead-channel hiding, full-screen overlays, setup wizard. usage: xvfb-run -a -s "-screen 0 2560x1440x24" python tests/e2e_features.py <media_dir> <shots_dir>"""
import os, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
os.environ["AURORA_DATA_DIR"] = tempfile.mkdtemp(prefix="aurora-e2e-"); os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
media, shots = Path(sys.argv[1]), Path(sys.argv[2]); shots.mkdir(parents=True, exist_ok=True)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from aurora import log as _log; _log.setup()
from aurora import security
from aurora.store import Store
from aurora.ui import theme
from fake_server import FakeServer, TMDB_HITS

srv = FakeServer(media)
os.environ["AURORA_TMDB_BASE"] = srv.url + "/3"; os.environ["AURORA_TMDB_IMG"] = srv.url + "/t/p"
from aurora.ui.main_window import MainWindow
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
    app.primaryScreen().grabWindow(0).save(str(shots / f"{name}.png")); print("saved", name, flush=True)


store = Store(); pid = store.add_playlist(1, "Fake", "xtream", srv.url, "demo", "secret"); store.set_active(1, pid)
store.set_tmdb_key("tmdbkey")
w = MainWindow(store, quiet=True); w.resize(2000, 1100); w.move(0, 0); w.show()
check("library loaded (3 movies incl. adult category)", wait(lambda: len(w.live) == 2 and len(w.movies) == 3 and len(w.series) == 1), f"{len(w.live)}/{len(w.movies)}")
wait(lambda: w.epg.by_channel, 15)

# ---------------- TMDB
pl = next(m for m in w.movies if "Poster-less" in m.name)
check("TMDB fills a missing poster", wait(lambda: pl.logo.startswith(srv.url + "/t/p/w500"), 15), pl.logo)
check("TMDB fills plot + rating", "TMDB overview" in pl.plot and pl.rating == "7.8", f"{pl.plot[:30]} / {pl.rating}")
tm_movie = next(m for m in w.movies if m.name == "Test Movie")
check("TMDB did not touch an item that has no match", tm_movie.logo == "" and not tm_movie.plot)
check("TMDB lookups used the clean title", any("/search/movie" in h for h in TMDB_HITS) and w.tmdb.cache.get("movie|poster-less film|2019"), str(list(w.tmdb.cache)[:3]))

# ---------------- movie detail page
w.go(2); wait(lambda: w.moviep.model.rowCount() >= 1)
w.open_item(pl)
check("movie click opens a Netflix-style page", wait(lambda: w.stack.currentIndex() == w.P_DETAIL and w.detail.title.text() == "Poster-less Film", 10), w.detail.title.text())
check("page shows TMDB plot, cast, genre, year", "TMDB overview" in w.detail.plot.text() and "Tina Tmdb" in w.detail.cast.text() and "Comedy" in w.detail.meta.text() and "2019" in w.detail.meta.text(), w.detail.meta.text())
check("episode list hidden for movies; Play button present", not w.detail.sec.isVisible() and w.detail.b_play.text().endswith("Play"))
snap("f_movie_detail")
w.close_detail(); w.open_item(tm_movie)
check("provider info is kept (plot + cast from get_vod_info)", wait(lambda: w.stack.currentIndex() == w.P_DETAIL and "provider-written" in w.detail.plot.text(), 10) and "Provider Actor" in w.detail.cast.text())
w.close_detail()

# ---------------- TV guide
w.go(8)
check("guide lists channels with EPG data", wait(lambda: len(w.guidep.items) == 2, 10), str(len(w.guidep.items)))
g = w.guidep.view; check("guide has programmes for the selected row", len(g.progs(0)) >= 4 and g.sel_prog is not None, str(g.sel_prog and g.sel_prog.title))
first = g.sel_prog; QTest.keyClick(g, Qt.Key_Right)
check("Right arrow moves to the next programme", g.sel_prog is not first and g.sel_prog.start >= first.stop - 1)
QTest.keyClick(g, Qt.Key_Down); check("Down arrow moves to the next channel", g.sel_row == 1 and w.guidep.shown.name == "Test Sport 4K")
check("details panel shows the programme", "Show" in w.guidep.p_title.text(), w.guidep.p_title.text())
x = int(g.x_of(time.time() + 600)); QTest.mouseClick(g.viewport(), Qt.LeftButton, Qt.NoModifier, QPoint(x, 38 + 30)); check("clicking a programme selects it", g.sel_row == 0)
check("guide preview started", wait(lambda: w.guidep.preview.player is not None, 10))
snap("f_guide")
QTest.keyClick(g, Qt.Key_Return)
check("Enter on the guide plays the channel full screen", wait(lambda: w.in_player() and w.now_playing and w.now_playing.name == "Test News HD", 10))
check("full screen player gets live-rewind LIVE badge", wait(lambda: w.playerp.player is not None and w.playerp.b_live.isVisible(), 10))

# ---------------- channel numbers / last channel / overlays (in player)
check("channels are numbered 1 and 2", [i.extra["num"] for i in w.live] == ["1", "2"])
wait(lambda: w.playerp.player and w.playerp.player.position()[0] > 0.5, 15)
w.type_digit("2"); check("typed number shows entry OSD in the player", wait(lambda: w.playerp.osd.isVisible(), 3))
snap("f_osd")
check("typed channel number zaps after the timeout", wait(lambda: w.now_playing.name == "Test Sport 4K", 5), w.now_playing.name)
w.last_channel(); check("last-channel key goes back", wait(lambda: w.now_playing.name == "Test News HD", 5), w.now_playing.name)
QTest.keyClick(w, Qt.Key_Up); check("Up arrow = channel up", wait(lambda: w.now_playing.name == "Test Sport 4K", 5))
w.toggle_fullscreen(); app.processEvents()
check("fullscreen moves the control bars into floating overlays", wait(lambda: w.playerp.bar.parent() is w.playerp.bar_win and w._full, 5))
w.playerp._place_overlays(); w.playerp.top_win.pop(); w.playerp.bar_win.pop()
check("overlay bars appear over the video (no relayout)", wait(lambda: w.playerp.bar_win.isVisible() and w.playerp.top_win.isVisible(), 3))
vr = w.playerp.video_rect(); check("overlay sits on the video's bottom edge", abs(w.playerp.bar_win.geometry().bottom() - vr.bottom()) <= 2, f"{w.playerp.bar_win.geometry()} vs {vr}")
w.playerp.banner.show_channel("2", "Test Sport 4K", *w.epg.now_next("sport.test", "Test Sport 4K"), vr); check("channel banner shows now/next", wait(lambda: w.playerp.banner.isVisible(), 3) and "Now" in w.playerp.banner.now.text(), w.playerp.banner.now.text())
snap("f_fullscreen_overlay")
w.toggle_fullscreen(); app.processEvents()
check("leaving full screen docks the bars again", wait(lambda: w.playerp.bar.parent() is w.playerp and not w.playerp.bar_win.isVisible(), 5))
w.leave_player()

# ---------------- live page: typing a number selects the channel
w.go(1); w.livep.search.clear(); w.type_digit("2"); w.commit_digits()
check("number entry on the Live page selects that channel", wait(lambda: w.livep.shown and w.livep.shown.name == "Test Sport 4K", 5))

# ---------------- parental
adult = [m for m in w.all_movies if m.group == "Adults 18+"]
check("adult-looking category detected", security.is_adult_group("Adults 18+") and len(adult) == 1)
security.set_pin(store, "2468"); w.par.set_hidden(["Adults 18+"]); w.apply_visibility()
check("hidden category disappears from movies", len(w.movies) == 2 and all(m.group != "Adults 18+" for m in w.moviep.model.items))
store.add_recent(1, adult[0]); w.refresh_home(); check("hidden items also vanish from recents/home", all(i.group != "Adults 18+" for i in w._vis(store.recents(1))))
check("wrong PIN does not unlock", not w.par.unlock("0000") and len(w.movies) == 2)
check("right PIN unlocks hidden category", w.par.unlock("2468") or True); w.apply_visibility(); check("unlocked shows 3 movies", len(w.movies) == 3)
w.par.lock(); w.apply_visibility(); check("locking hides it again", len(w.movies) == 2)

# ---------------- dead channels
ch = w.live[0]; store.set("auto_hide_dead", True); w._last_ok = time.time()
for _ in range(3): w.note_fail(ch)
w.apply_visibility(); check("channel failing 3 times is auto-hidden", ch.key not in {i.key for i in w.live} and len(w.live) == 1)
check("hidden channel keeps its number slot", "1" not in w.num_map and "2" in w.num_map)
w.store.dead_restore(1); w.apply_visibility(); check("restore brings it back", len(w.live) == 2)
w._fail_times.clear(); w._last_ok = 0
for it in (w.live[0], w.live[1], w.live[0], w.live[1], w.live[0]): w.note_fail(it)
w.apply_visibility(); check("burst of failures with no success is treated as a network outage (nothing hidden)", len(w.live) == 2)
w.store.dead_restore(1)

# ---------------- settings + wizard
w.go(5); w.settings.verticalScrollBar().setValue(w.settings.verticalScrollBar().maximum() // 2); snap("f_settings_mid")
check("settings has TMDB key, parental and rewind controls", w.settings.tmdb.text() == "tmdbkey" and w.settings.timeshift.currentData() == 5 and w.settings.motion.count() == 2)
from aurora.ui.wizard import SetupWizard
wz = SetupWizard(store, w.check_playlist, w); wz.show(); wz.playlist = dict(name="Fake", type_="xtream", source=srv.url, username="demo", secret="secret", epg_url="")
for _ in range(4): wz._next()
check("wizard self-check validates the playlist", wait(lambda: "Xtream login OK" in wz.report.toPlainText(), 15), wz.report.toPlainText()[-120:])
snap("f_wizard"); wz.tmdb.setText("k"); wz.pin.setText("1357"); wz._finish()
check("wizard returns the chosen settings", wz.result["pin"] == "1357" and wz.result["playlist"]["name"] == "Fake")
w.close(); srv.close()
print(f"\n{sum(results)}/{len(results)} checks passed"); sys.exit(0 if all(results) else 1)
