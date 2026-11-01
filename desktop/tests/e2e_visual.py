"""E2E for the v1.2 visual/picture features + search + hiding. usage: xvfb-run -a -s "-screen 0 2560x1440x24" python tests/e2e_visual.py <media_dir> <shots_dir>"""
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
from aurora.store import Store
from aurora.ui import theme
from fake_server import FakeServer
srv = FakeServer(media); os.environ["AURORA_TMDB_BASE"] = srv.url + "/3"; os.environ["AURORA_TMDB_IMG"] = srv.url + "/t/p"
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
    for _ in range(12): app.processEvents(); time.sleep(0.05)
    app.primaryScreen().grabWindow(0).save(str(shots / f"{name}.png")); print("saved", name, flush=True)


store = Store(); pid = store.add_playlist(1, "Fake", "xtream", srv.url, "demo", "secret"); store.set_active(1, pid); store.set_tmdb_key("tmdbkey"); store.set("scrub_thumbs", True)
w = MainWindow(store, quiet=True); w.resize(2000, 1100); w.move(0, 0); w.show()
check("library loaded", wait(lambda: len(w.live) == 2 and len(w.movies) == 3), f"{len(w.live)}/{len(w.movies)}")
wait(lambda: w.epg.by_channel, 15)
pl = next(m for m in w.movies if "Poster-less" in m.name); wait(lambda: pl.logo.startswith("http"), 15)

# ---- skeleton loading
w.go(2); w.moviep.set_loading(); snap("v_skeleton")
check("skeleton placeholders shown while loading", w.moviep.model.rowCount() == 24 and w.moviep.model.items[0].kind == "skeleton")
w.open_item(w.moviep.model.items[0]); check("skeleton cards are not clickable", w.stack.currentIndex() == 2)
w.moviep.set_items(w.movies); w.moviep.model.set_items(w.movies)

# ---- colour glow follows the poster
for _ in range(60):
    app.processEvents(); time.sleep(0.05)
    if w.loader.color(pl.logo) is not None: break
check("poster dominant colour computed", w.loader.color(pl.logo) is not None, str(w.loader.color(pl.logo) and w.loader.color(pl.logo).name()))
row = next(i for i, m in enumerate(w.moviep.model.items) if m.key == pl.key)
before = w.moviep._anim.endValue(); w.moviep._ht.hoverRow.emit(row)
check("hovering a poster retints the page background", wait(lambda: w.moviep._custom and w.moviep._anim.endValue() is not None, 3))
wait(lambda: not w.moviep._anim.state(), 2); snap("v_tint_movies")
idx = w.moviep.model.index(row, 0); r = w.moviep.view.visualRect(idx); QTest.mouseMove(w.moviep.view.viewport(), r.center()); wait(lambda: w.moviep._ht.level(row) > 0.8, 2)
check("hover lift animates (progress approaches 1)", w.moviep._ht.level(row) > 0.8, f"{w.moviep._ht.level(row):.2f}"); snap("v_hover_lift")

# ---- page fade
w.go(0); check("page fade veil animates then disappears", w.stack.veil.isVisible() and wait(lambda: not w.stack.veil.isVisible(), 3))
store.set("animations", False); w.settings_changed(); w.go(2); check("animations can be turned off", not w.stack.veil.isVisible())
store.set("animations", True); w.settings_changed()

# ---- detail zoom
w.open_item(pl); wait(lambda: w.stack.currentIndex() == w.P_DETAIL, 8)
check("detail hero zooms in then settles", w.detail.hero.zoom_anim.state() != 0 or w.detail.hero._z < 1.0)
wait(lambda: w.detail.hero._z == 0.0, 3); check("zoom ends at rest", w.detail.hero._z == 0.0)
wait(lambda: w.detail.body._custom, 5); check("series/movie page glow takes the backdrop colour", w.detail.body._custom)
snap("v_detail"); w.close_detail()

# ---- theme accent
theme.set_accent("blue"); check("accent switch changes theme colours", theme.RED == "#2e7dff" and "2e7dff" in theme.build() and theme.acc("color:#e0262d").endswith("#2e7dff"), theme.RED)
app.setStyleSheet(theme.build()); w.go(1); snap("v_blue_live"); theme.set_accent("red"); app.setStyleSheet(theme.build())

# ---- hide by category / language / alphabet
w.go(1); check("category list has News + Sport", any(w.livep.cats.item(i).text() == "Sport" for i in range(w.livep.cats.count())))
w.livep.hide_group.emit("Sport", False); check("hiding a category removes it and its channels", wait(lambda: len(w.live) == 1 and all(w.livep.cats.item(i).text() != "Sport" for i in range(w.livep.cats.count())), 5))
w.seriesp.hide_group.emit("Drama", False); check("hide-category button on Series works", wait(lambda: len(w.series) == 0, 3))
w.par.set_hidden([]); w.apply_visibility(); check("restored by clearing hidden categories", len(w.live) == 2 and len(w.series) == 1)
w.go(2); w.moviep.group.setCurrentIndex(1); app.processEvents(); check("movies page shows Hide category button for a selected category", not w.moviep.b_hide.isHidden())
w.moviep.group.setCurrentIndex(0)

# ---- global search
w.open_search(); check("Ctrl+K opens search", w.stack.currentIndex() == 9)
w.searchp.box.setText("news"); w.searchp.run()
secs = [(w.searchp.list.item(i).text()) for i in range(w.searchp.list.count())]
check("search finds channels and programmes", any("Test News HD" in s for s in secs) and any(s.startswith("News Show") for s in secs), str(secs[:6]))
w.searchp.box.setText("poster"); w.searchp.run(); check("search finds movies", any("Poster-less" in w.searchp.list.item(i).text() for i in range(w.searchp.list.count())))
snap("v_search")
w.searchp.box.setText("test series"); w.searchp.run(); w.searchp.open_current()
check("opening a series result opens its page", wait(lambda: w.stack.currentIndex() == w.P_DETAIL, 8)); w.close_detail()
w.open_search(); w.searchp.box.setText("sport show"); w.searchp.run(); w.searchp.open_current()
check("opening a programme result jumps to the guide", wait(lambda: w.stack.currentIndex() == 8 and w.guidep.shown and w.guidep.shown.name == "Test Sport 4K", 5))
w.open_search(); w.escape(); check("Esc leaves search", w.stack.currentIndex() != 9)

# ---- picture profile + scrub thumbnails in the player
mv = tm = next(m for m in w.movies if m.name == "Test Movie"); w.open_item(mv, direct=True)
check("movie plays", wait(lambda: w.in_player() and w.playerp.player and w.playerp.player.position()[0] > 0.5, 20))
w.playerp.profile = {}; w.playerp.profile_changed.emit({"denoise": "light", "motion": "smooth"}); w.playerp.player.apply_picture({"denoise": "light", "motion": "smooth"})
check("per-channel profile is stored", store.picture_profile(mv.key) == {"denoise": "light", "motion": "smooth"})
w.leave_player(); time.sleep(1.7); w.open_item(mv, direct=True); wait(lambda: w.in_player() and w.playerp.player and w.playerp.player.pic.get("denoise") == "light", 10)
check("profile is re-applied next time the item plays", w.playerp.player.pic.get("denoise") == "light" and w.playerp.player.pic.get("motion") == "smooth", str(w.playerp.player.pic))
print("P1", w.stack.currentIndex(), w.now_playing and w.now_playing.name, flush=True); check("scrub thumbnail worker started (VOD only)", w.playerp.thumbs is not None)
wait(lambda: w.playerp.player.position()[1] > 0, 10); w.playerp.player.m.pause = True; time.sleep(1.0)
print("P2", w.in_player(), flush=True); w.playerp.thumbs.request(1.0); check("thumbnail frame captured", wait(lambda: len(w.playerp.thumbs.cache) > 0, 12), str({k: (v.width(), v.height()) for k, v in w.playerp.thumbs.cache.items()}))
w.playerp.player.position = lambda: (1.0, 10.0)  # fake server stream reports no duration; stub it for the tooltip
w.playerp._scrub_hover(0.5, QPoint(900, 900)); w.playerp.thumbs.request(1.0); w.playerp._scrub_hover(0.0, QPoint(900, 900)); wait(lambda: w.playerp.tip.isVisible(), 3)
check("scrub tooltip shows time/preview", w.playerp.tip.isVisible(), f"dur={w.playerp.player.position()} live={w.playerp.player.is_live} thumbs={w.playerp.thumbs}"); snap("v_scrub")
print("in_player", w.in_player(), flush=True); w.toggle_fullscreen(); app.processEvents(); check("fullscreen bars use the bigger style", w.playerp.bar.property("fs") is True, f"in_player={w.in_player()} full={w._full} fs={w.playerp.bar.property('fs')!r}"); snap("v_fullscreen_big"); w.toggle_fullscreen(); w.leave_player()

# ---- settings screenshot
w.go(5); sb = w.settings.verticalScrollBar(); sb.setValue(int(sb.maximum() * 0.42)); snap("v_settings_a"); sb.setValue(int(sb.maximum() * 0.62)); snap("v_settings_b")
check("settings expose quality / denoise / accent / size / 10-foot", w.settings.quality.count() == 3 and w.settings.accent.count() == 5 and w.settings.uiscale.count() == 5 and w.settings.tenfoot.text().startswith("10-foot"))
w.close(); srv.close(); print(f"\n{sum(results)}/{len(results)} checks passed"); sys.exit(0 if all(results) else 1)
