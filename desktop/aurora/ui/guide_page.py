"""TV Guide: time-based grid of every channel that has EPG data (cable-guide style) with a live preview and details panel."""
from __future__ import annotations
import time
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QTimer
from PySide6.QtGui import QPainter, QColor, QFont, QFontMetrics, QPen, QLinearGradient, QPainterPath
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, QPushButton, QAbstractScrollArea, QFrame, QSizePolicy)
from .backdrop import Backdrop
from .preview import PreviewPane
from . import theme
from ..ratings import clean_title
from ..models import Item, Programme

ROW_H, HEAD_H, NAME_W, PX_MIN = 58, 38, 230, 5.0         # px per minute -> 30 min = 150 px
BACK_H, AHEAD_H = 1.5, 30                               # hours of guide shown before "now" / after


def _hm(t): return time.strftime("%H:%M", time.localtime(t))


class GuideView(QAbstractScrollArea):
    selected = Signal(object, object)      # Item, Programme|None
    watch = Signal(object)

    def __init__(self, programmes):
        super().__init__()
        self.programmes = programmes          # callable(Item) -> list[Programme]
        self.items: list[Item] = []; self.cache: dict[str, list[Programme]] = {}
        self.sel_row = 0; self.sel_prog: Programme | None = None; self.hover = (-1, None)
        self.t0 = self._base(); self.setMouseTracking(True); self.viewport().setMouseTracking(True); self.setFocusPolicy(Qt.StrongFocus)
        self.setFrameShape(QFrame.NoFrame); self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn); self.horizontalScrollBar().setSingleStep(60)
        self.verticalScrollBar().setSingleStep(ROW_H // 2)
        self.horizontalScrollBar().valueChanged.connect(lambda _v: self.viewport().update()); self.verticalScrollBar().valueChanged.connect(lambda _v: self.viewport().update())

    @staticmethod
    def _base():
        t = time.time() - BACK_H * 3600; return t - (t % 1800)

    def total_w(self): return int((BACK_H + AHEAD_H) * 60 * PX_MIN)

    def set_items(self, items):
        self.items = items; self.cache.clear(); self.t0 = self._base(); self.sel_row = min(self.sel_row, max(0, len(items) - 1)); self._ranges(); self.viewport().update()

    def refresh(self):
        self.cache.clear(); self.t0 = self._base(); self.viewport().update()

    def _ranges(self):
        vw, vh = self.viewport().width() - NAME_W, self.viewport().height() - HEAD_H
        self.horizontalScrollBar().setRange(0, max(0, self.total_w() - vw)); self.horizontalScrollBar().setPageStep(max(1, vw))
        self.verticalScrollBar().setRange(0, max(0, len(self.items) * ROW_H - vh)); self.verticalScrollBar().setPageStep(max(1, vh))

    def resizeEvent(self, e):
        super().resizeEvent(e); self._ranges()

    def progs(self, row):
        it = self.items[row]
        if it.key not in self.cache: self.cache[it.key] = self.programmes(it) or []
        return self.cache[it.key]

    def x_of(self, t): return NAME_W + (t - self.t0) / 60 * PX_MIN - self.horizontalScrollBar().value()

    def scroll_to_now(self, offset_min=20):
        self.horizontalScrollBar().setValue(int(max(0, (time.time() - self.t0) / 60 * PX_MIN - offset_min * PX_MIN)))

    # --- painting
    def paintEvent(self, ev):
        p = QPainter(self.viewport()); p.setRenderHint(QPainter.Antialiasing); W, H = self.viewport().width(), self.viewport().height()
        p.fillRect(self.viewport().rect(), QColor(theme.BG)); now = time.time(); vs = self.verticalScrollBar().value()
        first = max(0, vs // ROW_H); last = min(len(self.items), (vs + H - HEAD_H) // ROW_H + 2)
        f = QFont(p.font()); f.setPixelSize(13); p.setFont(f); fm = QFontMetrics(f)
        p.setClipRect(NAME_W, HEAD_H, W - NAME_W, H - HEAD_H)
        for row in range(first, last):
            y = HEAD_H + row * ROW_H - vs
            p.fillRect(QRectF(NAME_W, y, W, ROW_H - 1), QColor(255, 255, 255, 5 if row % 2 else 0))
            for pr in self.progs(row):
                x1, x2 = self.x_of(pr.start), self.x_of(pr.stop)
                if x2 < NAME_W or x1 > W: continue
                r = QRectF(x1 + 2, y + 4, max(4, x2 - x1 - 4), ROW_H - 9); airing = pr.start <= now < pr.stop
                sel = row == self.sel_row and pr is self.sel_prog; hov = self.hover == (row, pr)
                path = QPainterPath(); path.addRoundedRect(r, 9, 9)
                if sel: p.fillPath(path, QColor(*theme.ACC, 200))
                elif airing: p.fillPath(path, QColor(*theme.ACC, 70 if not hov else 110))
                else: p.fillPath(path, QColor(255, 255, 255, 30 if hov else 16))
                p.setPen(QPen(QColor(*theme.ACC) if airing and not sel else QColor(255, 255, 255, 22), 1)); p.drawPath(path)
                tx = max(r.left() + 10, NAME_W + 8) if r.left() < NAME_W + 8 < r.right() - 40 else r.left() + 10
                w = r.right() - tx - 8
                if w > 24:
                    f2 = QFont(f); f2.setBold(True); p.setFont(f2); p.setPen(QColor(theme.TEXT)); p.drawText(QRectF(tx, r.y() + 6, w, 20), Qt.AlignLeft | Qt.AlignVCenter, QFontMetrics(f2).elidedText(pr.title or "—", Qt.ElideRight, int(w)))
                    f3 = QFont(f); f3.setPixelSize(11); p.setFont(f3); p.setPen(QColor(255, 255, 255, 150)); p.drawText(QRectF(tx, r.y() + 27, w, 16), Qt.AlignLeft | Qt.AlignVCenter, f"{_hm(pr.start)} – {_hm(pr.stop)}")
                    p.setFont(f)
            if not self.progs(row):
                p.setPen(QColor(theme.MUTED)); p.drawText(QRectF(NAME_W + 16, y, 400, ROW_H), Qt.AlignVCenter | Qt.AlignLeft, "No guide data")
        # now line
        nx = self.x_of(now)
        if NAME_W <= nx <= W: p.setPen(QPen(QColor(theme.RED), 2)); p.drawLine(QPointF(nx, HEAD_H), QPointF(nx, H))
        p.setClipping(False)
        # sticky header
        p.fillRect(NAME_W, 0, W - NAME_W, HEAD_H, QColor(8, 8, 10)); p.setClipRect(NAME_W, 0, W - NAME_W, HEAD_H)
        t = self.t0; fh = QFont(f); fh.setPixelSize(12); fh.setBold(True); p.setFont(fh)
        while True:
            x = self.x_of(t)
            if x > W: break
            if x > NAME_W - 60:
                p.setPen(QColor(255, 255, 255, 40)); p.drawLine(QPointF(x, 8), QPointF(x, HEAD_H)); p.setPen(QColor(theme.MUTED if t % 3600 else theme.TEXT)); p.drawText(QRectF(x + 8, 0, 100, HEAD_H), Qt.AlignVCenter | Qt.AlignLeft, _hm(t))
            t += 1800
        p.setClipping(False); p.setFont(f)
        # sticky channel column
        p.fillRect(0, 0, NAME_W, H, QColor(8, 8, 10)); p.setClipRect(0, HEAD_H, NAME_W, H - HEAD_H)
        for row in range(first, last):
            y = HEAD_H + row * ROW_H - vs; it = self.items[row]; sel = row == self.sel_row
            if sel: p.fillRect(QRectF(0, y, NAME_W, ROW_H - 1), QColor(*theme.ACC, 55)); p.fillRect(QRectF(0, y + 8, 3, ROW_H - 17), QColor(theme.RED))
            num = (it.extra or {}).get("num") or ""
            p.setPen(QColor(theme.MUTED)); fn = QFont(f); fn.setPixelSize(11); p.setFont(fn); p.drawText(QRectF(14, y + 8, NAME_W - 24, 14), Qt.AlignLeft, str(num))
            fb = QFont(f); fb.setBold(True); fb.setPixelSize(14); p.setFont(fb); p.setPen(QColor(theme.TEXT)); p.drawText(QRectF(14, y + 22, NAME_W - 26, 24), Qt.AlignLeft | Qt.AlignVCenter, QFontMetrics(fb).elidedText(it.name, Qt.ElideRight, NAME_W - 28))
            p.setPen(QColor(255, 255, 255, 14)); p.drawLine(0, int(y + ROW_H - 1), NAME_W, int(y + ROW_H - 1))
        p.setClipping(False); p.fillRect(0, 0, NAME_W, HEAD_H, QColor(8, 8, 10))
        p.setPen(QColor(theme.MUTED)); fh2 = QFont(f); fh2.setPixelSize(11); fh2.setBold(True); p.setFont(fh2); p.drawText(QRectF(14, 0, NAME_W - 20, HEAD_H), Qt.AlignVCenter | Qt.AlignLeft, "CHANNEL")

    # --- interaction
    def hit(self, pos):
        if pos.y() < HEAD_H: return -1, None
        row = (pos.y() - HEAD_H + self.verticalScrollBar().value()) // ROW_H
        if not 0 <= row < len(self.items): return -1, None
        if pos.x() < NAME_W: return row, None
        t = self.t0 + (pos.x() - NAME_W + self.horizontalScrollBar().value()) / PX_MIN * 60
        return row, next((pr for pr in self.progs(row) if pr.start <= t < pr.stop), None)

    def mouseMoveEvent(self, e):
        h = self.hit(e.position().toPoint())
        if h != self.hover: self.hover = h; self.viewport().update()
        pr = h[1]
        self.viewport().setToolTip(f"{pr.title}\n{_hm(pr.start)} – {_hm(pr.stop)}\n\n{pr.desc[:300]}" if pr else "")
        self.viewport().setCursor(Qt.PointingHandCursor if h[0] >= 0 else Qt.ArrowCursor)

    def leaveEvent(self, e): self.hover = (-1, None); self.viewport().update()

    def mousePressEvent(self, e):
        row, pr = self.hit(e.position().toPoint())
        if row >= 0: self.select(row, pr or self.current_prog(row))

    def mouseDoubleClickEvent(self, e):
        row, _pr = self.hit(e.position().toPoint())
        if row >= 0: self.watch.emit(self.items[row])

    def current_prog(self, row, at=None):
        at = at or time.time()
        return next((p for p in self.progs(row) if p.start <= at < p.stop), None)

    def select(self, row, pr=None, ensure=True):
        row = max(0, min(len(self.items) - 1, row))
        if not self.items: return
        self.sel_row, self.sel_prog = row, pr
        if ensure: self.ensure_visible()
        self.viewport().update(); self.selected.emit(self.items[row], pr)

    def ensure_visible(self):
        vs, vh = self.verticalScrollBar().value(), self.viewport().height() - HEAD_H; y = self.sel_row * ROW_H
        if y < vs: self.verticalScrollBar().setValue(y)
        elif y + ROW_H > vs + vh: self.verticalScrollBar().setValue(y + ROW_H - vh)
        if self.sel_prog:
            hs, hw = self.horizontalScrollBar().value(), self.viewport().width() - NAME_W
            x1, x2 = (self.sel_prog.start - self.t0) / 60 * PX_MIN, (self.sel_prog.stop - self.t0) / 60 * PX_MIN
            if x1 < hs: self.horizontalScrollBar().setValue(int(x1) - 20)
            elif x2 > hs + hw: self.horizontalScrollBar().setValue(int(min(x1 - 20, x2 - hw + 20)))

    def keyPressEvent(self, e):
        k = e.key(); row = self.sel_row
        if k in (Qt.Key_Up, Qt.Key_Down):
            nr = max(0, min(len(self.items) - 1, row + (1 if k == Qt.Key_Down else -1)))
            at = (self.sel_prog.start + 1) if self.sel_prog else time.time()
            self.select(nr, self.current_prog(nr, at) or self.current_prog(nr))
        elif k in (Qt.Key_Left, Qt.Key_Right):
            ps = self.progs(row); cur = self.sel_prog or self.current_prog(row)
            if not ps: return
            i = ps.index(cur) if cur in ps else 0
            self.select(row, ps[max(0, min(len(ps) - 1, i + (1 if k == Qt.Key_Right else -1)))])
        elif k in (Qt.Key_Return, Qt.Key_Enter):
            if self.items: self.watch.emit(self.items[row])
        elif k == Qt.Key_Home: self.scroll_to_now()
        else: super().keyPressEvent(e)


class GuidePage(Backdrop):
    play = Signal(object, object)          # item, zapping context
    toggle_fav = Signal(object)

    def __init__(self, loader, epg, store, fav):
        super().__init__()
        self.epg, self.store, self.fav = epg, store, fav; self.all: list[Item] = []; self.shown: Item | None = None; self.alts = lambda it: []
        root = QVBoxLayout(self); root.setContentsMargins(32, 28, 32, 20); root.setSpacing(12)
        top = QHBoxLayout(); col = QVBoxLayout(); col.setSpacing(2)
        eb = QLabel("PROGRAM GUIDE"); eb.setObjectName("eyebrow"); title = QLabel("TV Guide"); title.setObjectName("display"); col.addWidget(eb); col.addWidget(title); top.addLayout(col); top.addStretch()
        self.cat = QComboBox(); self.cat.setMinimumWidth(210); self.search = QLineEdit(); self.search.setObjectName("search"); self.search.setPlaceholderText("Search channel or programme"); self.search.setFixedWidth(280); self.search.setClearButtonEnabled(True)
        self.b_now = QPushButton("Now"); self.b_now.setObjectName("ghostsm"); self.b_now.setCursor(Qt.PointingHandCursor); self.b_now.setToolTip("Jump to the current time (Home)")
        for w in (self.cat, self.search, self.b_now): top.addWidget(w)
        root.addLayout(top)
        self.view = GuideView(lambda it: self.epg.lookup(it.tvg_id, it.name)); root.addWidget(self.view, 1)
        self.empty = QLabel("No program guide loaded.\nAdd an EPG (XMLTV) URL in Settings, or use a playlist that provides one."); self.empty.setAlignment(Qt.AlignCenter); self.empty.setObjectName("muted"); self.empty.hide(); root.addWidget(self.empty, 1)
        box = QFrame(); box.setObjectName("glass"); bl = QHBoxLayout(box); bl.setContentsMargins(16, 14, 20, 14); bl.setSpacing(18)
        pv = QWidget(); pv.setFixedWidth(330); pl_ = QVBoxLayout(pv); pl_.setContentsMargins(0, 0, 0, 0); self.preview = PreviewPane(store); pl_.addWidget(self.preview); pl_.addStretch(); bl.addWidget(pv)
        info = QVBoxLayout(); info.setSpacing(3)
        self.chan = QLabel(""); self.chan.setObjectName("eyebrow"); self.p_title = QLabel("Select a programme"); self.p_title.setObjectName("h1"); self.p_title.setWordWrap(True)
        self.p_time = QLabel(""); self.p_time.setObjectName("muted"); self.p_desc = QLabel(""); self.p_desc.setWordWrap(True); self.p_desc.setStyleSheet("color:#b9b9c2;"); self.p_desc.setAlignment(Qt.AlignTop)
        self.p_rate = QLabel(""); self.p_rate.setStyleSheet(f"color:{theme.GOLD}; font-weight:600;")
        for w in (self.chan, self.p_title, self.p_rate, self.p_time): info.addWidget(w)
        info.addWidget(self.p_desc, 1)
        row = QHBoxLayout(); self.b_watch = QPushButton("▶  Watch full screen"); self.b_watch.setObjectName("primary"); self.b_fav = QPushButton(""); self.b_reload = QPushButton("↻"); self.b_reload.setObjectName("ghostsm")
        for b in (self.b_watch, self.b_fav, self.b_reload): b.setCursor(Qt.PointingHandCursor)
        row.addWidget(self.b_watch); row.addWidget(self.b_fav); row.addWidget(self.b_reload); row.addStretch(); info.addLayout(row); bl.addLayout(info, 1)
        box.setFixedHeight(228); root.addWidget(box)
        self.view.selected.connect(self._selected); self.view.watch.connect(self._watch)
        self.cat.activated.connect(lambda _i: self._apply()); self.search.textChanged.connect(lambda _t: self._apply()); self.b_now.clicked.connect(self.view.scroll_to_now)
        self.b_watch.clicked.connect(lambda: self.shown and self._watch(self.shown)); self.b_fav.clicked.connect(lambda: self.shown and self.toggle_fav.emit(self.shown))
        self.b_reload.clicked.connect(self.preview.reload)
        self.preview.set_message("Select a channel to preview")
        QShortcutHome = None
        self._t = QTimer(self); self._t.setInterval(60000); self._t.timeout.connect(lambda: self.isVisible() and self.view.viewport().update()); self._t.start()

    def set_items(self, live):
        self.all = live; self.reload_epg()

    def reload_epg(self):
        cur = self.cat.currentData(); self.cat.blockSignals(True); self.cat.clear(); self.cat.addItem("All channels with a guide", ""); self.cat.addItem("★  Favorites", "__fav__")
        groups = sorted({i.group for i in self.all if i.group})
        for g in groups: self.cat.addItem(g, g)
        self.cat.setCurrentIndex(max(0, self.cat.findData(cur))); self.cat.blockSignals(False); self._apply()

    def _has_epg(self, it): return bool(self.epg.by_channel) and bool(self.epg.lookup(it.tvg_id, it.name))

    def _apply(self):
        g = self.cat.currentData() or ""; q = self.search.text().strip().lower()
        base = [i for i in self.all if (not g or (g == "__fav__" and self.fav(i)) or i.group == g) and self._has_epg(i)]
        if q:
            base = [i for i in base if q in i.name.lower() or any(q in (p.title or "").lower() for p in self.epg.lookup(i.tvg_id, i.name))]
        self.items = base; self.view.set_items(base); has = bool(base)
        self.view.setVisible(has); self.empty.setVisible(not has)
        self.empty.setText("No channels match." if self.epg.by_channel else "No program guide loaded.\nAdd an EPG (XMLTV) URL in Settings, or use a playlist that provides one.")
        if has:
            self.view.scroll_to_now()
            if not self.shown or self.shown not in base: self.view.select(0, self.view.current_prog(0), ensure=False)

    rate_for = staticmethod(lambda title: "")     # set by the main window: IMDb / Rotten Tomatoes text for a programme title (cached, looked up in the background)

    def _selected(self, it, pr):
        self.shown = it; self.chan.setText((f"{(it.extra or {}).get('num') or ''}  ·  " if (it.extra or {}).get("num") else "") + it.name.upper())
        pr = pr or self.view.current_prog(self.view.sel_row)
        if pr:
            live = pr.start <= time.time() < pr.stop
            self.p_title.setText(clean_title(pr.title) or pr.title or "—"); self.p_rate.setText(self.rate_for(pr.title)); self.p_time.setText(f"{_hm(pr.start)} – {_hm(pr.stop)}" + ("   ·   ON NOW" if live else "")); self.p_desc.setText(pr.desc[:500] or "No description.")
        else:
            self.p_title.setText("No guide information"); self.p_rate.setText(""); self.p_time.setText(""); self.p_desc.setText("")
        self.b_fav.setText("♥  In My List" if self.fav(it) else "♡  Add to My List"); self.preview.request(it)

    def _watch(self, it):
        self.preview.release(); self.play.emit(it, list(self.items))

    def select_item(self, it):
        for r, i in enumerate(self.items):
            if i.key == it.key: self.view.select(r, self.view.current_prog(r)); return

    def refresh_fav(self):
        if self.shown: self.b_fav.setText("♥  In My List" if self.fav(self.shown) else "♡  Add to My List")

    def showEvent(self, e):
        super().showEvent(e); self.view.refresh(); self.view.scroll_to_now()
        if self.shown and self.shown in self.items: QTimer.singleShot(200, lambda: self.isVisible() and self.preview.request(self.shown))
        self.view.setFocus()

    def hideEvent(self, e):
        self.preview.stop(); super().hideEvent(e)
