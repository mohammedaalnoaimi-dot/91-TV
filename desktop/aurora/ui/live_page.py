from __future__ import annotations
import time
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem, QPushButton,
                               QFrame, QAbstractItemView, QSizePolicy)
from .backdrop import Backdrop
from . import theme
from .preview import PreviewPane
from .widgets import ItemModel, ChannelDelegate, ProgressBar, ITEM_ROLE
from ..models import Item

CHIPS = {  # state -> (text, colour)
    "idle": ("READY", "#8d8d96"), "loading": ("CONNECTING", "#d9a441"), "playing": ("● LIVE", None),
    "failed": ("NO SIGNAL", "#8d8d96"), "unavailable": ("PREVIEW OFF", "#8d8d96"), "off": ("PREVIEW OFF", "#8d8d96"),
}


def _hm(t): return time.strftime("%H:%M", time.localtime(t))


class LivePage(Backdrop):
    play = Signal(object, object)          # item, zapping context
    context = Signal(object, object)       # item, global pos
    toggle_fav = Signal(object)
    hide_group = Signal(str, bool)         # category name, hide every category with the same language prefix

    def __init__(self, loader, fav, epg_now, epg_upcoming, store):
        super().__init__()
        self.store, self.fav, self.epg_upcoming, self.loader = store, fav, epg_upcoming, loader
        self.items: list[Item] = []; self.get_recents = lambda: []; self.get_favs = lambda: []; self.shown: Item | None = None
        root = QHBoxLayout(self); root.setContentsMargins(32, 28, 32, 20); root.setSpacing(24)
        # --- categories
        left = QVBoxLayout(); left.setSpacing(6)
        eb = QLabel("LIVE TV"); eb.setObjectName("eyebrow"); title = QLabel("Channels"); title.setObjectName("display")
        self.count = QLabel(""); self.count.setObjectName("muted")
        left.addWidget(eb); left.addWidget(title); left.addWidget(self.count); left.addSpacing(10)
        self.cats = QListWidget(); self.cats.setObjectName("cats"); self.cats.setFixedWidth(230); left.addWidget(self.cats, 1); root.addLayout(left)
        # --- channel list
        mid = QVBoxLayout(); mid.setSpacing(12)
        self.search = QLineEdit(); self.search.setObjectName("search"); self.search.setPlaceholderText("Search channels   (Ctrl+F)"); self.search.setClearButtonEnabled(True)
        mid.addWidget(self.search)
        self.model = ItemModel(self); self.view = QListView(); self.view.setModel(self.model)
        self.view.setItemDelegate(ChannelDelegate(loader, epg_now, fav)); self.view.setMouseTracking(True)
        self.view.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel); self.view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.view.setSelectionMode(QAbstractItemView.SingleSelection); self.view.setFrameShape(QFrame.NoFrame)
        self.view.verticalScrollBar().setSingleStep(30)
        mid.addWidget(self.view, 1); root.addLayout(mid, 5)
        # --- preview column
        self.side = QFrame(); self.side.setObjectName("glass"); self.side.setMinimumWidth(440); self.side.setMaximumWidth(820)
        self.side.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sl = QVBoxLayout(self.side); sl.setContentsMargins(20, 20, 20, 20); sl.setSpacing(10)
        self.preview = PreviewPane(store); sl.addWidget(self.preview)
        row = QHBoxLayout(); self.chip = QLabel(""); self.chip.setObjectName("chip"); row.addWidget(self.chip); row.addStretch()
        self.b_reload = QPushButton("↻  Reload"); self.b_reload.setObjectName("ghostsm"); self.b_reload.setCursor(Qt.PointingHandCursor); self.b_reload.setToolTip("Reload this channel. Press twice to try a backup source.")
        self.b_mute = QPushButton(""); self.b_mute.setObjectName("ghostsm"); self.b_mute.setCursor(Qt.PointingHandCursor); row.addWidget(self.b_reload); row.addWidget(self.b_mute); sl.addLayout(row)
        self.s_title = QLabel("Select a channel"); self.s_title.setObjectName("h1"); self.s_title.setWordWrap(True)
        self.s_group = QLabel(""); self.s_group.setObjectName("muted")
        sl.addWidget(self.s_title); sl.addWidget(self.s_group); sl.addSpacing(6)
        self.n_label = QLabel(""); self.n_label.setObjectName("eyebrow"); self.n_title = QLabel(""); self.n_title.setObjectName("h2"); self.n_title.setWordWrap(True)
        self.n_time = QLabel(""); self.n_time.setObjectName("muted"); self.bar = ProgressBar()
        self.n_desc = QLabel(""); self.n_desc.setWordWrap(True); self.n_desc.setStyleSheet("color:#b9b9c2;"); self.n_desc.setAlignment(Qt.AlignTop)
        for w in (self.n_label, self.n_title, self.n_time, self.bar, self.n_desc): sl.addWidget(w)
        self.upnext = QLabel(""); self.upnext.setObjectName("muted"); self.upnext.setWordWrap(True); self.upnext.setTextFormat(Qt.RichText); self.upnext.setAlignment(Qt.AlignTop)
        sl.addWidget(self.upnext, 1)
        btns = QHBoxLayout(); self.b_play = QPushButton("▶  Watch full screen"); self.b_play.setObjectName("primary"); self.b_fav = QPushButton("")
        self.b_play.setCursor(Qt.PointingHandCursor); self.b_fav.setCursor(Qt.PointingHandCursor)
        btns.addWidget(self.b_play, 1); btns.addWidget(self.b_fav); sl.addLayout(btns); root.addWidget(self.side, 4)
        # --- wiring
        self.cats.setContextMenuPolicy(Qt.CustomContextMenu); self.cats.customContextMenuRequested.connect(self._cat_menu)
        self.cats.currentRowChanged.connect(lambda _r: self._apply()); self.search.textChanged.connect(lambda _t: self._apply())
        self.view.activated.connect(lambda i: self._play(i.data(ITEM_ROLE)))
        self.view.selectionModel().currentChanged.connect(lambda cur, _p: self._select(cur.data(ITEM_ROLE) if cur.isValid() else None))
        self.b_play.clicked.connect(lambda: self.shown and self._play(self.shown))
        self.b_fav.clicked.connect(lambda: self.shown and self.toggle_fav.emit(self.shown))
        self.b_mute.clicked.connect(self._toggle_mute); self.b_reload.clicked.connect(self.preview.reload); self.preview.state.connect(self._state)
        self.view.setContextMenuPolicy(Qt.CustomContextMenu); self.view.customContextMenuRequested.connect(self._ctx)
        self._t = QTimer(self); self._t.setInterval(30000); self._t.timeout.connect(self._tick); self._t.start()
        self._state("idle"); self._mute_label(); self._fav_label()

    # ---- helpers
    def current(self):
        i = self.view.currentIndex(); return i.data(ITEM_ROLE) if i.isValid() else None

    def _cat_menu(self, pos):
        from PySide6.QtWidgets import QMenu
        from .. import security
        it = self.cats.itemAt(pos)
        if not it or self.cats.row(it) < 3: return
        g = it.text(); m = QMenu(self); a1 = m.addAction(f"Hide category “{g}”"); pf = security.group_prefix(g); a2 = m.addAction(f"Hide every “{pf}” category") if pf else None
        act = m.exec(self.cats.viewport().mapToGlobal(pos))
        if act == a1: self.hide_group.emit(g, False)
        elif a2 is not None and act == a2: self.hide_group.emit(g, True)

    def _ctx(self, pos):
        i = self.view.indexAt(pos)
        if i.isValid():
            self.context.emit(i.data(ITEM_ROLE), self.view.viewport().mapToGlobal(pos))

    def _play(self, it):
        if it:
            self.preview.release(); self.play.emit(it, list(self.model.items))

    def _toggle_mute(self):
        self.preview.set_muted(not self.preview.muted); self._mute_label()

    def _mute_label(self):
        self.b_mute.setText("Sound off" if self.preview.muted else "Sound on")

    def _fav_label(self):
        on = bool(self.shown and self.fav(self.shown)); self.b_fav.setText("♥  In My List" if on else "♡  Add to My List")

    def _state(self, s):
        text, col = CHIPS.get(s, CHIPS["idle"]); col = col or theme.RED
        self.chip.setText(text); self.chip.setStyleSheet(f"color:{col}; background:rgba(255,255,255,0.06); border-radius:11px; padding:4px 12px; font-weight:800; font-size:11px; letter-spacing:2px;")

    def _select(self, it):
        self.shown = it
        if not it:
            self.preview.request(None); return
        self.s_title.setText(it.name); self.s_group.setText(it.group or "Live channel"); self._fav_label(); self.set_tint(self.loader.color(it.logo))
        self._info(it)
        self.preview.request(it)

    def _info(self, it):
        ups = self.epg_upcoming(it) if it else []
        if ups:
            n = ups[0]; live = n.start <= time.time() < n.stop
            self.n_label.setText("NOW PLAYING" if live else "UP NEXT"); self.n_title.setText(n.title or "—")
            self.n_time.setText(f"{_hm(n.start)} – {_hm(n.stop)}"); self.n_desc.setText(n.desc[:320])
            self.bar.set_fraction((time.time() - n.start) / (n.stop - n.start) if live and n.stop > n.start else 0.0); self.bar.show()
            more = ups[1:6]
            self.upnext.setText("<br>".join(f"<span style='color:{theme.RED}'>{_hm(p.start)}</span> &nbsp; <span style='color:#cfcfd6'>{p.title}</span>" for p in more) if more else "")
        else:
            self.n_label.setText(""); self.n_title.setText("No program guide for this channel"); self.n_time.setText(""); self.n_desc.setText(""); self.bar.hide(); self.upnext.setText("")

    def _tick(self):
        if self.isVisible():
            self.view.viewport().update()
            if self.shown: self._info(self.shown)

    def refresh_info(self):
        if self.shown: self._info(self.shown)

    # ---- data
    def set_items(self, items):
        self.items = items; self.count.setText(f"{len(items):,} channels")
        groups = sorted({i.group for i in items if i.group})
        cur = self.cats.currentItem().text() if self.cats.currentItem() else None
        self.cats.blockSignals(True); self.cats.clear()
        for name in ["All channels", "★  Favorites", "Recently watched"] + groups:
            self.cats.addItem(QListWidgetItem(name))
        row = next((r for r in range(self.cats.count()) if self.cats.item(r).text() == cur), 0)
        self.cats.setCurrentRow(row); self.cats.blockSignals(False); self._apply()

    def _apply(self):
        r = self.cats.currentRow(); text = self.search.text().strip().lower()
        if r == 1:
            keys = {i.key for i in self.get_favs()}; base = [i for i in self.items if i.key in keys]
        elif r == 2:
            order = {k: n for n, k in enumerate(i.key for i in self.get_recents())}
            base = sorted([i for i in self.items if i.key in order], key=lambda i: order[i.key])
        elif r <= 0:
            base = self.items
        else:
            g = self.cats.item(r).text(); base = [i for i in self.items if i.group == g]
        self.model.set_items([i for i in base if not text or text in i.name.lower()])

    def set_loading(self):
        self.model.set_loading(14); self.count.setText("Loading channels…")

    def refresh(self):
        self._apply(); self._fav_label()

    def select_item(self, it):
        """Jump to a channel (e.g. typed channel number): show all channels, clear the search and select it."""
        self.search.blockSignals(True); self.search.clear(); self.search.blockSignals(False); self.cats.setCurrentRow(0); self._apply()
        for r, i in enumerate(self.model.items):
            if i.key == it.key:
                idx = self.model.index(r, 0); self.view.setCurrentIndex(idx); self.view.scrollTo(idx, QAbstractItemView.PositionAtCenter); return

    # ---- lifecycle: only decode while the page is visible
    def showEvent(self, e):
        super().showEvent(e)
        if self.shown and self.shown in self.model.items:
            QTimer.singleShot(150, lambda: self.isVisible() and self.shown and self.preview.request(self.shown))

    def hideEvent(self, e):
        self.preview.stop(); super().hideEvent(e)
