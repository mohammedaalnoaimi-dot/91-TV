from __future__ import annotations
import json, logging, os, sys, time
from PySide6.QtCore import Qt, QObject, QRunnable, QThreadPool, Signal, QTimer, QUrl
from PySide6.QtGui import QShortcut, QKeySequence, QDesktopServices, QIcon
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFrame, QLabel, QPushButton, QStackedWidget, QMessageBox,
                               QMenu, QButtonGroup, QInputDialog)
from .. import __version__, m3u, secrets
from ..sources import SourceIndex
from ..epg import Epg
from ..models import Item, Episode
from ..paths import cache_dir, log_dir, asset
from ..store import Store
from ..xtream import XtreamClient
import threading
from PySide6.QtWidgets import QApplication, QLineEdit, QAbstractSpinBox, QComboBox, QAbstractButton
from PySide6.QtCore import QEvent
from .. import security, gamepad
from ..tmdb import Tmdb
from .dialogs import PlaylistDialog, CategoriesDialog, DeadDialog, HideDialog
from .guide_page import GuidePage
from .search_page import SearchPage
from .fade import FadeStack
from . import theme
from .wizard import SetupWizard
from .detail_page import DetailPage
from .images import ImageLoader
from .pages import HomePage, BrowsePage, SettingsPage
from .live_page import LivePage
from .widgets import NavButton
from . import widgets
from .prayer_page import PrayerPage
from .multi_page import MultiPage
from .. import warm
from .. import prayer as pt, smart
from ..ratings import Ratings
from .player_page import PlayerPage
from . import player_page
from .. import player as pl

log = logging.getLogger(__name__)


class TopNav(QPushButton):
    def __init__(self, text):
        super().__init__(text.upper()); self.setObjectName("topnav"); self.setCheckable(True); self.setCursor(Qt.PointingHandCursor); self.setFocusPolicy(Qt.NoFocus)

    def set_compact(self, on): pass


class _Sig(QObject):
    done = Signal(object)
    error = Signal(str)


class Worker(QRunnable):
    def __init__(self, fn):
        super().__init__(); self.fn = fn; self.sig = _Sig()

    def run(self):
        try:
            self.sig.done.emit(self.fn())
        except Exception as e:
            log.exception("Background task failed")
            self.sig.error.emit(f"{type(e).__name__}: {e}")


def run_async(fn, ok, err=None):
    w = Worker(fn); w.setAutoDelete(False); w.sig.done.connect(ok)
    if err: w.sig.error.connect(err)
    _keep.append(w); QThreadPool.globalInstance().start(w)
_keep: list = []


def _item_to_json(i: Item):
    return dict(name=i.name, kind=i.kind, url=i.url, group=i.group, logo=i.logo, tvg_id=i.tvg_id, plot=i.plot, year=i.year, rating=i.rating, ext_id=i.ext_id, extra=i.extra)


class MainWindow(QMainWindow):
    enriched = Signal(int, int)
    rated = Signal()

    def __init__(self, store: Store, quiet: bool = False):
        super().__init__(); self.quiet = quiet
        self.store = store; self.epg = Epg(); self.loader = ImageLoader(self)
        self.profile_id = int(store.get("active_profile") or 1)
        if self.profile_id not in [p for p, _ in store.profiles()]:
            self.profile_id = 1
        self.par = security.Parental(store, self.profile_id); self.tmdb = Tmdb(store.tmdb_key()); self._enrich_gen = 0
        self._digits = ""; self._digit_timer = QTimer(self); self._digit_timer.setSingleShot(True); self._digit_timer.timeout.connect(self.commit_digits)
        self.last_live: Item | None = None; self._fail_times: list[float] = []; self._last_ok = 0.0; self.pad = None
        self.playlist = None; self.xt: XtreamClient | None = None
        self.all_live: list[Item] = []; self.all_movies: list[Item] = []; self.all_series: list[Item] = []; self.num_map: dict[str, Item] = {}
        self.live: list[Item] = []; self.movies: list[Item] = []; self.series: list[Item] = []
        self.context_items: list[Item] = []; self.now_playing: Item | None = None; self.return_page = 0; self._full = False
        self.setWindowTitle("91 TV"); self.resize(1440, 860); self.setMinimumSize(960, 600)
        ic = asset("aurora.ico")
        if ic.exists(): self.setWindowIcon(QIcon(str(ic)))
        root = QWidget(); root.setObjectName("root"); self.setCentralWidget(root); h = QVBoxLayout(root); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(0)
        # top bar: brand, menu, prayer chip, clock, list owner, profile
        self.sidebar = QFrame(); self.sidebar.setObjectName("chrome"); sl = QHBoxLayout(self.sidebar); sl.setContentsMargins(26, 6, 22, 0); sl.setSpacing(2)
        self.brand = QLabel(); self.brand.setObjectName("brand"); self.brand.setStyleSheet("padding-right:26px; background:transparent;")
        from PySide6.QtGui import QPixmap
        _wm = QPixmap(str(asset("wordmark.png")))
        if _wm.isNull(): self.brand.setText(f"<span style='color:{theme.RED}'>91</span> TV")
        else: self.brand.setPixmap(_wm.scaledToHeight(26, Qt.SmoothTransformation))
        sl.addWidget(self.brand)
        self.navs = QButtonGroup(self); self.navs.setExclusive(True)
        for name, idx in (("Home", 0), ("Live TV", 1), ("TV Guide", 8), ("Multi", 11), ("Movies", 2), ("TV Series", 3), ("My List", 4), ("Prayer", 10), ("Settings", 5)):
            b = TopNav(name); b.clicked.connect(lambda _c=False, i=idx: self.go(i)); self.navs.addButton(b, idx); sl.addWidget(b)
        sl.addStretch()
        self.status = QLabel(""); self.status.setObjectName("muted"); self.status.setStyleSheet("font-size:11px; padding-right:10px; background:transparent;"); sl.addWidget(self.status)
        self.chip = QPushButton(""); self.chip.setObjectName("who"); self.chip.setCursor(Qt.PointingHandCursor); self.chip.clicked.connect(lambda: self.go(10)); sl.addWidget(self.chip)
        self.clock = QLabel(""); self.clock.setObjectName("clock"); self.clock.setStyleSheet("font-size:18px; padding:0 12px; background:transparent;"); sl.addWidget(self.clock)
        self.b_who = QPushButton("MR"); self.b_who.setObjectName("who"); self.b_who.setCursor(Qt.PointingHandCursor); self.b_who.setToolTip("Whose list the heart / My List button saves to. Click to switch Mr / Mrs / Together."); self.b_who.clicked.connect(self.cycle_who); sl.addWidget(self.b_who)
        self.b_search = QPushButton("Search"); self.b_search.setObjectName("who"); self.b_search.setCursor(Qt.PointingHandCursor); self.b_search.setToolTip("Ctrl+K"); self.b_search.clicked.connect(lambda: self.open_search()); sl.addWidget(self.b_search)
        self.pname = QPushButton(""); self.pname.setObjectName("who"); self.pname.setCursor(Qt.PointingHandCursor); self.pname.clicked.connect(self.cycle_profile); sl.addWidget(self.pname)
        h.addWidget(self.sidebar)
        self.banner = QPushButton(""); self.banner.setObjectName("who"); self.banner.setStyleSheet(f"QPushButton{{background:{theme.RED}; color:white; border:none; padding:7px; font-size:14px;}}"); self.banner.hide(); self.banner.clicked.connect(self._dismiss_banner); h.addWidget(self.banner)
        self._dismissed = ""; self.together = False
        # pages
        fav = lambda it: store.is_favorite(self.profile_id, it)
        self.stack = FadeStack(); self.stack.enabled = bool(store.get("animations")); h.addWidget(self.stack, 1)
        self.home = HomePage(self.loader, fav); self.livep = LivePage(self.loader, fav, self.epg_now, self.epg_upcoming, store)
        self.moviep = BrowsePage("Movies", self.loader, fav, "movie"); self.seriesp = BrowsePage("TV Series", self.loader, fav, "series")
        self.listp = BrowsePage("My List", self.loader, fav); self.settings = SettingsPage(store)
        self.playerp = PlayerPage(store.get)
        self.detail = DetailPage(self.loader)
        self.guidep = GuidePage(self.loader, self.epg, store, fav)
        self.searchp = SearchPage(self.loader, lambda: (self.live, self.movies, self.series), self.epg)
        self.prayer = pt.Times(lambda: store.get("pt_method")); self.prayerp = PrayerPage(self.prayer, store)
        self.multip = MultiPage(store, lambda: self._vis(self.live), lambda it: self.sources.alternates(it)); self.multip.open_full.connect(lambda it: self.open_item(it, self.live))
        self.ratings = Ratings(lambda: store.get("omdb_key"), on_update=self.rated.emit); widgets.RATE = self.ratings.text; self.guidep.rate_for = self.guide_rating; self._prog = {}; widgets.PROG = lambda it: self._prog.get(it.key, 0.0); self._smart = {}; self._smart_sig = None; self.rated.connect(self.on_rated)
        for w in (self.home, self.livep, self.moviep, self.seriesp, self.listp, self.settings, self.playerp, self.detail, self.guidep, self.searchp, self.prayerp, self.multip):
            self.stack.addWidget(w)
        self.P_PLAYER = 6; self.P_DETAIL = 7; self.detail_return = 3; self._opening = None; self._last_start = (None, 0.0)
        self.detail.back.connect(self.close_detail); self.detail.play_episode.connect(self.play_episode); self.detail.play_movie.connect(lambda it: self.open_item(it, direct=True)); self.detail.toggle_fav.connect(self.detail_fav)
        self.sources = SourceIndex(); self.livep.preview.alternates = lambda it: self.sources.alternates(it); self.guidep.preview.alternates = lambda it: self.sources.alternates(it)
        self.livep.get_recents = lambda: self._vis(store.recents(self.profile_id, "live")); self.livep.get_favs = lambda: self._vis(store.favorites(self.profile_id, "live"))
        self.livep.hide_group.connect(self.hide_groups); self.moviep.hide_group.connect(self.hide_groups); self.seriesp.hide_group.connect(self.hide_groups)
        self.searchp.open_item.connect(self.search_open); self.searchp.open_programme.connect(self.search_programme); self.search_return = 0
        self.guidep.play.connect(lambda it, ctx: self.open_item(it, ctx)); self.guidep.toggle_fav.connect(self.toggle_favorite)
        self.livep.preview.state.connect(lambda st: self.preview_state(self.livep.shown, st)); self.guidep.preview.state.connect(lambda st: self.preview_state(self.guidep.shown, st))
        # wiring
        self.home.play.connect(self.play_item); self.home.info.connect(self.open_item); self.home.context.connect(self.item_menu)
        self.livep.play.connect(lambda it, ctx: self.open_item(it, ctx)); self.livep.context.connect(self.item_menu); self.livep.toggle_fav.connect(self.toggle_favorite)
        for p in (self.moviep, self.seriesp, self.listp):
            p.activated.connect(self.open_item); p.context.connect(self.item_menu)
        self.playerp.profile_changed.connect(lambda d: self.now_playing and self.store.set_picture_profile(self.now_playing.key, d)); self.playerp.back.connect(self.leave_player); self.playerp.fullscreen.connect(self.toggle_fullscreen); self.playerp.prev_next.connect(self.zap)
        self.playerp.failed.connect(self.player_failed); self.playerp.position_changed.connect(lambda p: self.now_playing and store.save_position(self.profile_id, self.now_playing, p, getattr(self.playerp, "last_dur", 0.0)))
        s = self.settings
        s.b_add.clicked.connect(self.add_playlist); s.b_del.clicked.connect(self.remove_playlist); s.b_use.clicked.connect(self.use_playlist); s.b_ref.clicked.connect(lambda: self.load_library(force=True))
        s.b_newp.clicked.connect(self.new_profile); s.b_delp.clicked.connect(self.delete_profile); s.profile.activated.connect(lambda _i: self.switch_profile(s.profile.currentData()))
        s.b_pin.clicked.connect(self.set_pin); s.b_pin_clear.clicked.connect(self.clear_pin); s.b_cats.clicked.connect(self.edit_hidden); s.b_unlock.clicked.connect(self.toggle_unlock)
        s.b_restart.clicked.connect(self.restart_app); s.b_dead.clicked.connect(self.show_dead); s.b_tmdb.clicked.connect(self.test_tmdb); s.b_wizard.clicked.connect(self.run_wizard); self.update_unlock_button()
        s.b_log.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_dir())))); s.b_diag.clicked.connect(self.run_diag); s.changed.connect(self.settings_changed)
        for key, fn in (("Esc", self.escape), ("F", lambda: self.in_player() and self.toggle_fullscreen()), ("F11", self.toggle_fullscreen), ("Space", self.space),
                        ("R", self.reload_stream), ("PgUp", lambda: self.zap(-1)), ("PgDown", lambda: self.zap(1)), ("Ctrl+F", self.focus_search), ("Ctrl+K", self.open_search),
                        ("Backspace", self.last_channel), ("Q", self.last_channel), ("L", self.go_live)):
            QShortcut(QKeySequence(key), self, activated=fn)
        for k, fn in ((Qt.Key_MediaTogglePlayPause, self.space), (Qt.Key_MediaPlay, self.space), (Qt.Key_MediaPause, self.space), (Qt.Key_MediaStop, self.leave_player_if), (Qt.Key_MediaNext, lambda: self.zap(1)),
                      (Qt.Key_MediaPrevious, lambda: self.zap(-1)), (Qt.Key_ChannelUp, lambda: self.zap(1)), (Qt.Key_ChannelDown, lambda: self.zap(-1)), (Qt.Key_Back, self.escape)):
            QShortcut(QKeySequence(k), self, activated=fn)
        QApplication.instance().installEventFilter(self); self.enriched.connect(self.on_enriched)
        self.pad = gamepad.Gamepad(self)
        if store.get("gamepad"): self.pad.start()
        self._last_input = time.time(); self.saver = None; self._pt_method = store.get("pt_method")
        self.tick_t = QTimer(self); self.tick_t.setInterval(1000); self.tick_t.timeout.connect(self.chrome_tick); self.tick_t.start(); self.update_who()
        QTimer.singleShot(0, self.after_show)

    # ---------- navigation
    def go(self, i):
        self.stack.setCurrentIndex(i)
        if self.navs.button(i): self.navs.button(i).setChecked(True)
        if i == 4: self.refresh_list()
        if i == 0: self.refresh_home()
        self.sidebar.setVisible(i != self.P_PLAYER or not self._full)

    def in_player(self): return self.stack.currentIndex() == self.P_PLAYER

    def escape(self):
        if self.stack.currentIndex() == 9: self.go(self.search_return if self.search_return != 9 else 0); return
        if self.in_player():
            self.toggle_fullscreen() if self._full else self.leave_player()
        elif self.stack.currentIndex() == self.P_DETAIL:
            self.close_detail()
        elif getattr(self, "_appfull", False):
            self.toggle_fullscreen()

    def reload_stream(self):
        if self.in_player(): self.playerp.reload()
        elif self.stack.currentIndex() == 1 and not self.livep.search.hasFocus(): self.livep.preview.reload()

    def space(self):
        if self.in_player(): self.playerp.toggle_pause()

    def seek_rel(self, s):
        if self.in_player(): self.playerp.skip(s)

    def open_search(self):
        if self.in_player(): return
        if self.stack.currentIndex() != 9: self.search_return = self.stack.currentIndex()
        self.go(9); self.searchp.focus()

    def search_open(self, it: Item):
        if it.kind == "live": self.open_item(it, self.live)
        else: self.open_item(it)

    def search_programme(self, ch: Item, pr):
        self.go(8); self.guidep.select_item(ch)

    def focus_search(self):
        w = self.stack.currentWidget(); getattr(w, "search", None) and w.search.setFocus()

    def toggle_fullscreen(self):
        if not self.in_player():
            self._appfull = not getattr(self, "_appfull", False)
            self.showFullScreen() if self._appfull else self.showNormal()
            return
        self._full = not self._full
        self.sidebar.setVisible(not self._full); self.banner.setVisible(False) if self._full else None
        self.showFullScreen() if (self._full or getattr(self, '_appfull', False)) else self.showNormal()
        self.playerp.set_fullscreen(self._full); QTimer.singleShot(300, self.playerp._place_overlays) if self._full else None

    def after_show(self):
        self.go(0); self.reload_settings_lists(); self.apply_dark_titlebar()
        self.load_library()
        if self.playlist is None and not self.quiet:
            self.go(5)
            if not self.store.get("wizard_done"): QTimer.singleShot(400, self.run_wizard)

    def apply_dark_titlebar(self):
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.dwmapi.DwmSetWindowAttribute(int(self.winId()), 20, ctypes.byref(ctypes.c_int(1)), 4)
            except Exception:
                pass

    # ---------- profiles & playlists
    def reload_settings_lists(self):
        self.playlist = self.store.active_playlist(self.profile_id)
        self.settings.reload_profiles(self.profile_id); self.settings.reload_playlists(self.profile_id, self.playlist.id if self.playlist else None)
        self.pname.setText(dict(self.store.profiles()).get(self.profile_id, "?").upper())

    def cycle_profile(self):
        ps = [p for p, _ in self.store.profiles()]; self.switch_profile(ps[(ps.index(self.profile_id) + 1) % len(ps)])

    def switch_profile(self, pid):
        self.profile_id = int(pid); self.store.set("active_profile", self.profile_id); self.par = security.Parental(self.store, self.profile_id)
        self.update_unlock_button(); self.reload_settings_lists(); self.load_library()

    def new_profile(self):
        n, ok = QInputDialog.getText(self, "New profile", "Profile name:")
        if ok and n.strip():
            try: self.switch_profile(self.store.add_profile(n))
            except Exception: QMessageBox.warning(self, "Profile", "A profile with that name already exists.")

    def delete_profile(self):
        if self.profile_id == 1: QMessageBox.information(self, "Profile", "The default profile cannot be deleted."); return
        if QMessageBox.question(self, "Delete profile", "Delete this profile with its playlists, favorites and history?") == QMessageBox.Yes:
            self.store.delete_profile(self.profile_id); self.switch_profile(1)

    def add_playlist(self):
        d = PlaylistDialog(self)
        if d.exec() and d.result_data:
            pid = self.store.add_playlist(self.profile_id, **d.result_data); self.store.set_active(self.profile_id, pid)
            self.reload_settings_lists(); self.load_library(force=True)

    def _selected_pl(self):
        it = self.settings.pl_list.currentItem(); return it.data(Qt.UserRole) if it else None

    def use_playlist(self):
        pid = self._selected_pl()
        if pid: self.store.set_active(self.profile_id, pid); self.reload_settings_lists(); self.load_library()

    def remove_playlist(self):
        pid = self._selected_pl()
        if pid and QMessageBox.question(self, "Remove", "Remove this playlist and its saved credentials?") == QMessageBox.Yes:
            self.store.delete_playlist(pid); (cache_dir() / f"playlist-{pid}.json").unlink(missing_ok=True); self.reload_settings_lists(); self.load_library()

    # ---------- library
    def _cache(self): return cache_dir() / f"playlist-{self.playlist.id}.json"

    def load_library(self, force=False):
        self.live, self.movies, self.series = [], [], []; self.all_live, self.all_movies, self.all_series = [], [], []; self.xt = None
        if not self.playlist:
            self.distribute(); return
        pl_ = self.playlist; cf = self._cache()

        def work():
            epg = pl_.epg_url
            if pl_.type == "xtream":
                c = XtreamClient(pl_.source, pl_.username, pl_.secret); c.authenticate()
                items = c.live() + c.movies() + c.series(); epg = epg or c.xmltv_url
            else:
                items, hdr = m3u.load_with_meta(pl_.source); epg = epg or hdr
            cf.write_text(json.dumps({"ts": time.time(), "epg": epg, "items": [_item_to_json(i) for i in items]}), "utf-8")
            return items, epg

        def fetch(): run_async(work, lambda r: self._loaded(r, pl_), self._load_err)
        if not force and cf.exists():
            # faster start: the saved library (can be 100k+ titles) is read and parsed off the UI thread, so the window opens straight away
            for pg in (self.moviep, self.seriesp, self.livep, self.home): pg.set_loading()
            def rd():
                data = json.loads(cf.read_text("utf-8")); return data, [Item(**d) for d in data["items"]]
            def done(r):
                data, items = r
                if not (self.playlist and pl_.id == self.playlist.id): return
                self.set_library(items, data.get("epg", ""), pl_)
                if time.time() - data["ts"] >= 12 * 3600: self.status.setText("Refreshing…"); fetch()
            def bad(_m): log.warning("Bad cache, reloading"); self.status.setText("Loading playlist…"); fetch()
            run_async(rd, done, bad); return
        self.status.setText("Loading playlist…")
        for pg in (self.moviep, self.seriesp, self.livep, self.home): pg.set_loading()
        fetch()

    def _loaded(self, r, pl_):
        if self.playlist and pl_.id == self.playlist.id:
            self.set_library(*r, pl_)

    def _load_err(self, msg):
        self.status.setText("Load failed"); self.distribute()
        if self.quiet: return
        if self.all_live or self.all_movies:
            self.status.setText("Could not refresh - showing saved list"); log.warning("Refresh failed: %s", msg); return
        QMessageBox.warning(self, "Playlist error", f"Could not load the playlist:\n{msg}\n\nCheck the URL/credentials and your connection. Details are in the log.")

    def set_library(self, items, epg_url, pl_):
        self.all_live = [i for i in items if i.kind == "live"]; self.all_movies = [i for i in items if i.kind == "movie"]; self.all_series = [i for i in items if i.kind == "series"]
        self.xt = XtreamClient(pl_.source, pl_.username, pl_.secret) if pl_.type == "xtream" else None
        self.apply_visibility(); self.start_enrichment()
        epg_url = epg_url or self.store.get("epg_url")
        if epg_url:
            run_async(lambda: self._load_epg(epg_url), lambda _r: (self.livep.refresh(), self.livep.refresh_info(), self.livep.view.viewport().update(), self.guidep.reload_epg()), lambda m: log.warning("EPG load failed: %s", m))

    def _load_epg(self, url):
        e = Epg(); e.load(url); self.epg.by_channel, self.epg.names = e.by_channel, e.names

    def distribute(self):
        self.livep.set_items(self.live); self.moviep.set_items(self.movies); self.seriesp.set_items(self.series); self.guidep.set_items(self.live); self.refresh_home()

    def refresh_home(self):
        self._prog = self.store.progress(self.profile_id)
        rec = self._vis(self.store.recents(self.profile_id))
        keep = [i for i in rec if i.kind != "live" and self._prog.get(i.key, 0) < 0.95]         # unfinished movies / episodes first, finished ones drop out
        self.home.populate(self.live, self.movies, self.series, keep or rec, self._vis(self.store.favorites(self.profile_id)), self._smart)
        self.build_smart()

    def guide_rating(self, title):
        """IMDb / RT line for a programme shown in the guide (only when it is a known film or series and an OMDb key exists)."""
        key = (self.store.get("omdb_key") or "").strip()
        if not key or not title: return ""
        from ..ratings import clean_title as ct, year_of
        ck = f"movie|{ct(title).lower()}|{year_of(title)}"; hit = self.ratings.disk.get(ck)
        if hit is not None: return hit
        if ck not in self.ratings.pending and len(self.ratings.pending) < 20:
            self.ratings.pending.add(ck)
            def work():
                try: t = self.ratings.lookup("movie", title, "")
                finally: self.ratings.pending.discard(ck)
                if t: self.rated.emit()
            self.ratings.pool.submit(work)
        return ""

    def build_smart(self):
        """Recently added / Top rated / New releases are sorted on a worker thread (89k titles), then the home screen is filled again."""
        rec = self._vis(self.store.recents(self.profile_id)); head = tuple(i.key for i in rec[:6])
        sig = (self.profile_id, len(self.movies), len(self.series), self.playlist.id if self.playlist else 0, head)
        if sig == self._smart_sig or not (self.movies or self.series): return
        self._smart_sig = sig; both = self.movies + self.series
        def ok(r):
            if sig == self._smart_sig: self._smart = r; self.refresh_home()
        def work():
            d = {k: smart.build(k, both, "movie") for k in ("@recent", "@top", "@new")}; d["because"] = smart.because(rec, both); return d
        run_async(work, ok)

    def refresh_list(self):
        self.listp.set_items(self._vis(self.store.wl_together(self.profile_id) if self.together else self.store.favorites(self.profile_id)))

    # ---------- top bar: clock, prayer chip + reminder, Mr / Mrs / Together, screensaver
    def update_who(self):
        self.b_who.setText("TOGETHER" if self.together else self.store.who().upper())

    def cycle_who(self):
        w = self.store.who()
        if not self.together and w == "mr": self.store.set("who", "mrs")
        elif not self.together and w == "mrs": self.together = True
        else: self.together = False; self.store.set("who", "mr")
        self.update_who(); self.refresh_home(); self.livep.refresh(); self.livep.view.viewport().update()
        if self.stack.currentIndex() == 4: self.refresh_list()

    def on_rated(self):
        self.home.hero.refresh_rate()
        for p in (self.home, self.moviep, self.seriesp, self.listp, self.searchp): p.update()
        for p in (self.moviep, self.seriesp, self.listp): p.view.viewport().update()
        for r in self.home.rows.values(): r.view.viewport().update()

    def _dismiss_banner(self):
        self._dismissed = self.banner.property("key") or ""; self.banner.hide()

    def chrome_tick(self):
        n = pt.now(); self.clock.setText(n.strftime("%H:%M"))
        self.prayer.refresh(); nx = self.prayer.next(n)
        show = bool(self.store.get("pt_header")) and nx is not None
        self.chip.setVisible(show)
        if show:
            nm = nx[0].upper()
            if pt.ramadan(self.prayer.today): nm = "IFTAR" if nx[0] == "Maghrib" else "SUHOOR ENDS" if nx[0] == "Fajr" else nm
            self.chip.setText(f"{nm}  {nx[1].strftime('%H:%M')}  ·  {pt.left(nx[1] - n)}")
        rem = int(self.store.get("pt_remind") or 0)
        if nx and rem and 0 < (nx[1] - n).total_seconds() <= rem * 60 and not self.in_player():
            key = nx[1].isoformat()
            if key != self._dismissed:
                self.banner.setProperty("key", key); self.banner.setText(f"{nx[0]} prayer in {pt.left(nx[1] - n)}   ({nx[1].strftime('%H:%M')})      — click to dismiss"); self.banner.show()
        else: self.banner.hide()
        # screensaver
        idle = time.time() - self._last_input
        if self.saver is None and self.store.get("ss_on") and idle >= int(self.store.get("ss_minutes") or 2) * 60 and self.stack.currentIndex() != self.P_PLAYER and not self.quiet:
            self.show_saver()
        elif self.saver is not None: self.saver.tick(self.prayer)

    def show_saver(self):
        from .saver import Saver
        self.saver = Saver(self.centralWidget()); self.saver.setGeometry(self.centralWidget().rect()); self.saver.show(); self.saver.raise_(); self.saver.tick(self.prayer)

    def hide_saver(self):
        if self.saver is not None: self.saver.hide(); self.saver.deleteLater(); self.saver = None

    # ---------- EPG helpers
    def epg_now(self, it: Item):
        return self.epg.now_next(it.tvg_id, it.name)[0] if self.epg.by_channel else None

    def epg_upcoming(self, it: Item):
        ups = self.epg.upcoming(it.tvg_id, it.name)
        if not ups and self.xt and it.ext_id:
            key = "x:" + it.ext_id
            if key not in self.epg.by_channel:
                self.epg.by_channel[key] = []
                def ok(r): self.epg.by_channel[key] = r; self.livep.refresh_info()
                run_async(lambda: self.xt.short_epg(it.ext_id), ok)
            return self.epg.by_channel.get(key, [])
        return ups

    # ---------- playback
    def item_menu(self, it: Item, pos):
        m = QMenu(self); fav = self.store.is_favorite(self.profile_id, it)
        a1 = m.addAction("Remove from My List" if fav else "Add to My List"); a2 = m.addAction("Play" if it.kind != "series" else "Episodes…"); m.addSeparator()
        a_mv = m.addAction("Add to Multi-view") if it.kind == "live" else None
        a3 = m.addAction("Hide this channel" if it.kind == "live" else "Hide this title")
        a4 = m.addAction(f"Hide category “{it.group}”") if it.group else None
        sc = security.name_script(it.name); a5 = m.addAction(f"Hide all {sc}-script names") if sc else None
        act = m.exec(pos or self.cursor().pos())
        if act == a1:
            self.toggle_favorite(it); self.stack.currentWidget().update()
        elif act == a2:
            self.open_item(it)
        elif a_mv is not None and act == a_mv:
            self.multip.add_channel(it); self.go(11)
        elif act == a3:
            self.par.hide_channel(it); self.apply_visibility(); self.status.setText(f"Hidden: {it.name}\n(restore in Settings → Hide channels)")
        elif a4 is not None and act == a4:
            self.par.set_hidden(self.par.hidden() | {it.group}); self.apply_visibility(); self.status.setText(f"Hidden category: {it.group}")
        elif a5 is not None and act == a5:
            self.par.set_scripts(self.par.hidden_scripts() | {sc}); self.apply_visibility(); self.status.setText(f"Hidden all {sc}-script names")

    def play_item(self, it: Item):
        """Play now (hero Play / continue watching): series open their page, everything else starts."""
        if it.kind == "series": self.open_series(it)
        else: self.open_item(it, direct=True)

    def open_item(self, it: Item, ctx=None, direct=False):
        if it.kind == "skeleton": return
        if it.kind == "series":
            self.open_series(it); return
        if it.kind == "movie" and not direct and not self.quiet_movies:
            self.open_movie(it); return
        self.context_items = ctx or ([it] if it.kind != "live" else self.live)
        self.start(it)

    quiet_movies = False

    def open_movie(self, it: Item):
        """Netflix-style movie page with plot, rating and cast (TMDB / provider info when available)."""
        if self._opening == it.key or (self.stack.currentIndex() == self.P_DETAIL and self.detail.item and self.detail.item.key == it.key): return
        self._opening = it.key; xt = self.xt; tm = self.tmdb

        def work():
            info = {}
            if xt and it.ext_id and not it.ext_id.startswith("m3u:"):
                try: info = xt.vod_info(it.ext_id)
                except Exception as e: log.info("vod info unavailable: %s", e)
            return self.merge_tmdb(it, info)

        # open the page at once with what we already know; plot / cast / backdrop fill in when the provider answers
        if self.stack.currentIndex() != self.P_DETAIL: self.detail_return = self.stack.currentIndex()
        pos0 = self.store.position(self.profile_id, it)
        self.detail.show_movie(it, {}, pos0, self.store.is_favorite(self.profile_id, it)); self.stack.setCurrentIndex(self.P_DETAIL)

        def ok(info):
            self._opening = None
            if self.stack.currentIndex() == self.P_DETAIL and self.detail.item and self.detail.item.key == it.key and info:
                self.detail.show_movie(it, info, self.store.position(self.profile_id, it), self.store.is_favorite(self.profile_id, it))

        def fail(m):
            self._opening = None
        run_async(work, ok, fail)

    def merge_tmdb(self, it: Item, info: dict) -> dict:
        """Fill gaps in the provider's info with TMDB data (never overwrites what the provider supplied, except artwork when 'prefer TMDB' is on)."""
        info = dict(info or {})
        if self.tmdb.enabled:
            r = self.tmdb.lookup(it.kind, it.name, it.year)
            if r:
                for k_info, k_r in (("plot", "overview"), ("cast", "cast"), ("genre", "genres"), ("rating", "rating"), ("releaseDate", "year")):
                    if not str(info.get(k_info) or "").strip(): info[k_info] = r.get(k_r) or ""
                bd = info.get("backdrop_path"); has_bd = bool(bd[0] if isinstance(bd, list) and bd else (bd if isinstance(bd, str) else ""))
                if r.get("backdrop") and (not has_bd or self.store.get("tmdb_replace")): info["backdrop_path"] = [r["backdrop"]]
                if r.get("poster") and not info.get("cover"): info["cover"] = r["poster"]
        return info

    def open_series(self, it: Item):
        """Netflix-style: open the full series page (banner, seasons, episodes)."""
        if self._opening == it.key or (self.stack.currentIndex() == self.P_DETAIL and self.detail.item and self.detail.item.key == it.key):
            return
        self._opening = it.key; xt = self.xt; self.status.setText("Loading series…")

        def work():
            if xt and it.ext_id and not it.ext_id.startswith("m3u:"):
                info, eps = xt.series_info(it.ext_id); return self.merge_tmdb(it, info), eps
            return self.merge_tmdb(it, {}), [Episode(e["title"], e["url"], e["season"], e["number"]) for e in sorted(it.extra.get("episodes", []), key=lambda e: (e["season"], e["number"]))]

        def done():
            self._opening = None; self.status.setText("")

        def ok(res):
            done(); info, eps = res
            if not eps and not self.quiet:
                QMessageBox.information(self, it.name, "No episodes found for this series."); return
            urls = {e.url for e in eps}
            resume = next((r.url for r in self.store.recents(self.profile_id, "movie", limit=200) if r.url in urls), None)
            if self.stack.currentIndex() != self.P_DETAIL:
                self.detail_return = self.stack.currentIndex()
            self.detail.show_series(it, info, eps, resume, self.store.is_favorite(self.profile_id, it)); self.stack.setCurrentIndex(self.P_DETAIL)

        def fail(m):
            done()
            if not self.quiet: QMessageBox.warning(self, "Series", m)
        run_async(work, ok, fail)

    def close_detail(self):
        self.go(self.detail_return if self.detail_return != self.P_DETAIL else 3)

    def play_episode(self, ep, series: Item):
        from .detail_page import clean_title
        self.start(Item(f"{clean_title(series.name)} - S{ep.season:02d}E{ep.number:02d}  {ep.title}", "movie", ep.url, series.group, series.logo))

    def detail_fav(self, it: Item):
        self.toggle_favorite(it); self.detail.set_fav(self.store.is_favorite(self.profile_id, it))

    def start(self, it: Item):
        if not it.url or it.kind == "skeleton": return
        if self._last_start[0] == it.key and time.time() - self._last_start[1] < 1.5: return     # ignore double-click double-start
        self._last_start = (it.key, time.time())
        self.livep.preview.release(); self.guidep.preview.release()      # free the preview decoders before the full player opens
        self.return_page = self.stack.currentIndex() if not self.in_player() else self.return_page
        self.stack.setCurrentIndex(self.P_PLAYER); QTimer.singleShot(30, lambda: self._begin(it))

    def _begin(self, it: Item):
        if self.now_playing and self.now_playing.kind == "live" and it.kind == "live" and self.now_playing.key != it.key: self.last_live = self.now_playing
        self.now_playing = it; self.store.add_recent(self.profile_id, it)
        start = self.store.position(self.profile_id, it) if it.kind != "live" else 0.0
        self.playerp.open(it.name, it.url, it.kind == "live", start, self.sources.alternates(it) if it.kind == "live" else None, self.store.picture_profile(it.key))
        if it.kind == "live":
            now, nxt = self.epg.now_next(it.tvg_id, it.name) if self.epg.by_channel else (None, None)
            self.playerp.show_banner(self.channel_number(it), it.name, now, nxt)
            QTimer.singleShot(9000, lambda k=it.key: self.check_playing(k))
            ctx = self.context_items or self.live
            if ctx and it in ctx:
                i = ctx.index(it); warm.warm([ctx[(i + 1) % len(ctx)].url, ctx[(i - 1) % len(ctx)].url], time.time())     # pre-warm next / previous channel

    def zap(self, d):
        if not self.in_player() or not self.now_playing or self.now_playing.kind != "live": return
        items = self.context_items or self.live
        if not items: return
        keys = [i.key for i in items]
        if self.now_playing.key in keys:
            self.start_in_place(items[(keys.index(self.now_playing.key) + d) % len(items)])

    def start_in_place(self, it): self._begin(it)

    def leave_player_if(self):
        if self.in_player(): self.leave_player()

    def leave_player(self):
        if self._full: self.toggle_fullscreen()
        self.playerp.stop(); self.go(self.return_page)

    def player_failed(self, msg):
        if self.now_playing and self.now_playing.kind == "live": self.note_fail(self.now_playing)
        if "libmpv" in msg:
            QMessageBox.critical(self, "Video engine missing", "The video engine (libmpv-2.dll) could not be loaded.\n\nReinstall 91 TV or see TROUBLESHOOTING.md.\n\n" + msg)
            self.leave_player()
        else:
            QMessageBox.warning(self, "Playback", msg)

    def toggle_favorite(self, it: Item):
        self.store.toggle_favorite(self.profile_id, it); self.livep.refresh(); self.refresh_home(); self.livep.view.viewport().update()

    def restart_app(self):
        from PySide6.QtCore import QProcess
        QProcess.startDetached(sys.executable, sys.argv); QApplication.quit()

    def settings_changed(self):
        self.stack.enabled = bool(self.store.get("animations"))
        key = self.store.tmdb_key()
        if key != self.tmdb.key:
            self.tmdb = Tmdb(key); self.start_enrichment()
        if self.store.get("gamepad"): self.pad.start()
        else: self.pad.stop()
        if self.store.get("pt_method") != self._pt_method: self._pt_method = self.store.get("pt_method"); self.prayer.reset(); self.prayer.refresh(True)
        self.on_rated(); self.livep.preview.reset(); self.guidep.preview.reset()
        self.playerp.reset_player() if not self.in_player() else None   # apply new engine options on next play


    # ---------- visibility (parental, hidden categories, dead channels)
    def _vis(self, items):
        return self.par.filter(items)

    def apply_visibility(self):
        dead = self.store.dead_hidden(self.profile_id, security.DEAD_RETRY_DAYS) if self.store.get("auto_hide_dead") else {}
        self.dead_keys = set(dead)
        self.live = [i for i in self.par.filter(self.all_live) if i.key not in self.dead_keys]
        self.movies = self._vis(self.all_movies); self.series = self._vis(self.all_series)
        self.sources.build(self.live); self.build_numbers()
        hid = len(self.all_live) - len(self.live) + len(self.all_movies) - len(self.movies) + len(self.all_series) - len(self.series)
        self.status.setText(f"{len(self.live)} channels · {len(self.movies)} movies · {len(self.series)} series" + (f"\n{hid} hidden" if hid else ""))
        self.distribute()

    def build_numbers(self):
        """Channel numbers: provider numbers when they are unique digits, otherwise list position."""
        allc = self.all_live; nums = [(i.extra or {}).get("num", "") for i in allc]
        use = len(allc) > 0 and all(n.isdigit() for n in nums) and len(set(nums)) == len(nums)
        vis = {i.key for i in self.live}; self.num_map = {}
        for pos, it in enumerate(allc, 1):      # numbering covers hidden channels too, so numbers never shift when something is hidden/unhidden
            n = nums[pos - 1] if use else str(pos); it.extra = dict(it.extra or {}); it.extra["num"] = n
            if it.key in vis: self.num_map[n] = it

    def channel_number(self, it: Item) -> str:
        return (it.extra or {}).get("num", "") or ""

    # ---------- channel entry / zapping
    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.MouseButtonDblClick and isinstance(obj, QWidget) and not isinstance(obj, QAbstractButton) and not self.in_player() \
                and (obj is self.sidebar or self.sidebar.isAncestorOf(obj)):
            self.toggle_fullscreen(); return True
        if ev.type() in (QEvent.KeyPress, QEvent.MouseButtonPress, QEvent.MouseMove, QEvent.Wheel):
            self._last_input = time.time()
            if self.saver is not None:
                if ev.type() != QEvent.MouseMove: self.hide_saver(); return True
                return False
        if ev.type() == QEvent.KeyPress and (self.isActiveWindow() or QApplication.activeWindow() is None) and QApplication.activeModalWidget() is None and not ev.modifiers() & (Qt.ControlModifier | Qt.AltModifier):
            fw = QApplication.focusWidget()
            if isinstance(fw, (QLineEdit, QAbstractSpinBox, QComboBox)) or (fw is not None and fw.metaObject().className() in ("QPlainTextEdit", "QTextEdit")): return False
            k = ev.key(); idx = self.stack.currentIndex()
            if Qt.Key_0 <= k <= Qt.Key_9 and idx in (1, 8, self.P_PLAYER):
                self.type_digit(chr(k)); return True
            if k in (Qt.Key_Return, Qt.Key_Enter) and self._digits:
                self.commit_digits(); return True
            if idx == self.P_PLAYER:
                if k == Qt.Key_Up: self.zap(1); return True
                if k == Qt.Key_Down: self.zap(-1); return True
                if k == Qt.Key_Left: self.seek_rel(-10); return True
                if k == Qt.Key_Right: self.seek_rel(10); return True
        return super().eventFilter(obj, ev)

    def type_digit(self, d):
        self._digits = (self._digits + d)[-5:]; it = self.num_map.get(self._digits)
        hint = it.name if it else "Enter channel number"
        if self.in_player(): self.playerp.show_entry(self._digits, hint)
        else: self.status.setText(f"Channel {self._digits}: {hint}")
        self._digit_timer.start(1600 if not it else 1100)

    def commit_digits(self):
        self._digit_timer.stop(); d, self._digits = self._digits, ""
        self.playerp.hide_entry()
        it = self.num_map.get(d)
        if not it: self.status.setText(f"No channel {d}") if d else None; return
        self.jump_to(it)

    def jump_to(self, it: Item):
        idx = self.stack.currentIndex()
        if self.in_player():
            self.context_items = self.context_items or self.live; self.start_in_place(it)
        elif idx == 1: self.livep.select_item(it)
        elif idx == 8: self.guidep.select_item(it)

    def last_channel(self):
        if self.last_live and self.stack.currentIndex() in (1, 8, self.P_PLAYER):
            fw = QApplication.focusWidget()
            if isinstance(fw, (QLineEdit, QAbstractSpinBox)): return
            self.jump_to(self.last_live)

    def go_live(self):
        if self.in_player(): self.playerp.go_live()

    # ---------- dead channels
    def note_fail(self, it: Item):
        if not it or it.kind != "live" or not self.store.get("auto_hide_dead"): return
        now = time.time(); self._fail_times = [t for t in self._fail_times if now - t < 120] + [now]
        if len(self._fail_times) >= 4 and self._last_ok < self._fail_times[0]:
            log.info("Several failures in a row without any success - looks like a network outage, not counting them against channels"); return
        if self.store.dead_fail(self.profile_id, it, security.DEAD_AFTER):
            self.status.setText(f"Hidden dead channel: {it.name}\n(restore in Settings)"); log.warning("Auto-hid dead channel %s", it.name)
            QTimer.singleShot(1500, self.apply_visibility_soon)

    def apply_visibility_soon(self):
        if not self.in_player(): self.apply_visibility()
        else: QTimer.singleShot(5000, self.apply_visibility_soon)

    def note_ok(self, it: Item):
        if not it or it.kind != "live": return
        self._last_ok = time.time(); self.store.dead_ok(self.profile_id, it)

    def check_playing(self, key):
        p = self.playerp.player
        if self.now_playing and self.now_playing.key == key and p and p.position()[0] > 3: self.note_ok(self.now_playing)

    def preview_state(self, it: Item, st: str):
        if not it: return
        if st == "failed": self.note_fail(it)
        elif st == "playing": QTimer.singleShot(4000, lambda k=it.key: self.note_ok(it) if (self.livep.shown and self.livep.shown.key == k) or (self.guidep.shown and self.guidep.shown.key == k) else None)

    def show_dead(self):
        d = DeadDialog(self.store.dead_hidden(self.profile_id, security.DEAD_RETRY_DAYS), self)
        if d.exec():
            if d.restore_all: self.store.dead_restore(self.profile_id)
            for k in d.restore_keys: self.store.dead_restore(self.profile_id, k)
            self.apply_visibility()

    # ---------- parental PIN / hidden categories
    def _ask_pin(self, title="Enter PIN") -> str | None:
        t, ok = QInputDialog.getText(self, "Parental PIN", title, QLineEdit.Password); return t if ok else None

    def verify_pin(self) -> bool:
        if not security.has_pin(self.store) or self.par.unlocked: return True
        p = self._ask_pin("Enter your PIN")
        if p is None: return False
        if security.check_pin(self.store, p): return True
        QMessageBox.warning(self, "Parental PIN", "Wrong PIN."); return False

    def set_pin(self):
        if not self.verify_pin(): return
        a = self._ask_pin("New PIN (4 to 12 digits)")
        if a is None: return
        if not (a.isdigit() and 4 <= len(a) <= 12): QMessageBox.warning(self, "Parental PIN", "Use 4 to 12 digits."); return
        if self._ask_pin("Repeat the new PIN") != a: QMessageBox.warning(self, "Parental PIN", "The PINs did not match."); return
        security.set_pin(self.store, a); self.update_unlock_button(); QMessageBox.information(self, "Parental PIN", "PIN saved.")

    def clear_pin(self):
        if not security.has_pin(self.store): return
        if self.verify_pin(): security.clear_pin(self.store); self.par.lock(); self.update_unlock_button(); self.apply_visibility()

    def hide_groups(self, group: str, whole_prefix: bool):
        """Hide a category (or every category sharing its language prefix, e.g. all 'FR|')."""
        names = {group}
        if whole_prefix:
            pf = security.group_prefix(group); names = {i.group for i in self.all_live + self.all_movies + self.all_series if i.group and security.group_prefix(i.group) == pf}
        self.par.set_hidden(self.par.hidden() | names); self.apply_visibility()
        self.status.setText(f"Hidden {len(names)} categor{'ies' if len(names) != 1 else 'y'}\n(restore in Settings → Hide channels)")

    def edit_hidden(self):
        if not self.verify_pin(): return
        groups: dict[str, int] = {}; scripts: dict[str, int] = {}
        for i in self.all_live + self.all_movies + self.all_series:
            if i.group: groups[i.group] = groups.get(i.group, 0) + 1
            sc = security.name_script(i.name)
            if sc: scripts[sc] = scripts.get(sc, 0) + 1
        d = HideDialog(groups, self.par.hidden(), scripts, self.par.hidden_scripts(), self.par.hidden_channels(), security.is_adult_group, self)
        if d.exec():
            self.par.set_hidden(d.result_groups()); self.par.set_scripts(d.result_scripts()); self.par.unhide_channels(d.restore_keys); self.apply_visibility()

    def toggle_unlock(self):
        if not security.has_pin(self.store):
            QMessageBox.information(self, "Parental PIN", "Set a PIN first. Without a PIN, hidden categories simply stay hidden."); return
        if self.par.unlocked: self.par.lock()
        elif self.verify_pin(): self.par.unlocked = True
        self.update_unlock_button(); self.apply_visibility()

    def update_unlock_button(self):
        self.settings.b_unlock.setText("Lock hidden content" if self.par.unlocked else "Unlock hidden content")

    # ---------- TMDB
    def start_enrichment(self):
        self._enrich_gen += 1; gen = self._enrich_gen
        if not self.tmdb.enabled: return
        replace = bool(self.store.get("tmdb_replace")); tm = self.tmdb
        todo = [i for i in self.all_movies + self.all_series if replace or not i.logo]
        if not todo: return

        def work():
            done = 0
            for it in todo:
                if gen != self._enrich_gen: return
                t0 = time.time(); r = tm.lookup(it.kind, it.name, it.year)
                if r:
                    if r.get("poster") and (replace or not it.logo): it.logo = r["poster"]
                    if r.get("overview") and not it.plot: it.plot = r["overview"]
                    if r.get("rating") and (not it.rating or it.rating in ("0", "0.0")): it.rating = r["rating"]
                    if r.get("year") and not it.year: it.year = r["year"]
                if time.time() - t0 > 0.02: time.sleep(0.05)      # network lookup happened: stay polite to the API
                done += 1
                if done % 25 == 0: self.enriched.emit(done, len(todo))
                if tm.errors > 25 and tm.errors * 2 > done: log.warning("TMDB: too many errors, stopping (%s)", tm.last_error); break
            tm.flush(); self.enriched.emit(done, len(todo))
        threading.Thread(target=work, daemon=True).start()

    def on_enriched(self, done, total):
        self.status.setText(f"Artwork {done}/{total}" if done < total else f"{len(self.live)} channels · {len(self.movies)} movies · {len(self.series)} series")
        for p in (self.moviep, self.seriesp): p.view.viewport().update()
        if done >= total: self.refresh_home()

    def test_tmdb(self):
        key = self.settings.tmdb.text().strip(); self.settings.tmdb_state.setText("Testing…")
        if not key: self.settings.tmdb_state.setText("Paste a key first."); return
        run_async(lambda: Tmdb(key).test(), lambda err: self.settings.tmdb_state.setText("Key works ✔" if not err else f"Key rejected: {err}"), lambda m: self.settings.tmdb_state.setText(m))

    # ---------- setup wizard
    def check_playlist(self, data, cb):
        def work():
            if data["type_"] == "xtream":
                c = XtreamClient(data["source"], data["username"], data["secret"]); c.authenticate(); n = len(c.live())
                return f"Xtream login OK - {n} live channels found"
            items, _ = m3u.load_with_meta(data["source"]); return f"Playlist loaded - {len(items)} entries found"
        run_async(work, lambda t: cb(True, t), lambda m: cb(False, f"Could not load the playlist: {m}"))

    def run_wizard(self):
        w = SetupWizard(self.store, self.check_playlist, self)
        accepted = w.exec()
        self.store.set("wizard_done", True)
        if not accepted: return
        r = w.result
        self.store.set("audio_device", r["audio_device"]); self.store.set("hwdec", r["hwdec"]); self.store.set("hdr", r["hdr"])
        if r["tmdb"]: self.store.set_tmdb_key(r["tmdb"])
        if r["pin"].isdigit() and len(r["pin"]) >= 4:
            security.set_pin(self.store, r["pin"])
            if r["hide_adult"]:
                groups = {i.group for i in self.all_live + self.all_movies + self.all_series if security.is_adult_group(i.group)}
                self.par.set_hidden(self.par.hidden() | groups)
        self.settings._load(); self.update_unlock_button()
        if r["playlist"]:
            pid = self.store.add_playlist(self.profile_id, **r["playlist"]); self.store.set_active(self.profile_id, pid)
            self.reload_settings_lists(); self.load_library(force=True)
        self.settings_changed()

    # ---------- diagnostics
    def run_diag(self):
        lines = [f"91 TV {__version__} | Python {sys.version.split()[0]}", f"Credential store: {secrets.backend() if secrets.available() else 'none (local fallback)'}"]
        m = pl.load_mpv(); lines.append("libmpv: OK" if m else f"libmpv: MISSING - {pl.mpv_error()}")
        if self.playerp.ensure_player():
            self.settings.set_devices(self.playerp.player.audio_devices()); lines.append(f"Audio devices found: {self.settings.dev.count() - 1}")
        lines.append(f"Logs: {log_dir()}"); self.settings.diag.setText("\n".join(lines))

    def resizeEvent(self, e):
        compact = self.width() < 1180
        if compact != getattr(self, '_compact', None):
            self._compact = compact; self.b_search.setText("⌕" if compact else "Search"); self.pname.setVisible(not compact); self.clock.setVisible(not compact)
        self.status.setVisible(self.width() >= 1700)
        if self.saver is not None: self.saver.setGeometry(self.centralWidget().rect())
        super().resizeEvent(e)

    def closeEvent(self, e):
        self._enrich_gen += 1; self.tmdb.flush(); self.pad.stop(); self.playerp.banner.hide_now(); self.playerp.osd.hide_now(); self.playerp.top_win.hide_now(); self.playerp.bar_win.hide_now()
        self.guidep.preview.release(); self.livep.preview.release(); self.playerp.stop(); self.playerp.reset_player(); super().closeEvent(e)
