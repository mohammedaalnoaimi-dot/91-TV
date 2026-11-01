"""Item models, poster/channel delegates, hero banner, carousel rows."""
from __future__ import annotations
import time, random
from PySide6.QtCore import (QObject, Qt, QAbstractListModel, QModelIndex, QSize, QRectF, QPropertyAnimation, QEasingCurve, Signal,
                            Property, QTimer, QPointF)
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QFont, QLinearGradient, QPixmap, QBrush, QFontMetrics
from PySide6.QtWidgets import (QStyledItemDelegate, QListView, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
                               QAbstractItemView, QSizePolicy, QStyle)
from ..models import Item
from . import theme

ITEM_ROLE = Qt.UserRole + 1
PROG = lambda it: 0.0         # set by the main window: fraction watched (0..1) of a title, for the progress bar under "Continue watching" posters
RATE = lambda it: ""        # set by the main window: returns "IMDb 7.1 · RT 85%" (or the provider score) for a movie / series


class ItemModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.all: list[Item] = []
        self.items: list[Item] = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.items)

    def data(self, idx, role=Qt.DisplayRole):
        if not idx.isValid():
            return None
        it = self.items[idx.row()]
        if role == ITEM_ROLE:
            return it
        if role == Qt.DisplayRole:
            return it.name
        return None

    def set_items(self, items):
        self.beginResetModel(); self.all = list(items); self.items = list(items); self.endResetModel()

    def set_loading(self, n=24):
        """Show grey skeleton cards while the real content is on its way."""
        self.set_items([Item("", kind="skeleton") for _ in range(n)])

    def filter(self, text="", group=""):
        text = text.strip().lower()
        self.beginResetModel()
        self.items = [i for i in self.all if (not group or i.group == group) and (not text or text in i.name.lower())]
        self.endResetModel()


def _initials(name):
    w = [x for x in name.replace("-", " ").split() if x[:1].isalnum()]
    return "".join(x[0] for x in w[:2]).upper() or "?"


def tile_colors(name: str):
    """Stable pleasant gradient per title so a missing poster/logo still looks designed."""
    h = (sum(ord(c) * (i + 3) for i, c in enumerate(name or "?")) * 37) % 360
    return QColor.fromHsv(h, 120, 92), QColor.fromHsv((h + 30) % 360, 150, 36)


class HoverTracker(QObject):
    """Smooth hover/focus progress (0..1) per row, plus a shared shimmer clock for skeleton placeholders."""
    hoverRow = Signal(object)          # row index or None when the pointer enters a different card

    def __init__(self, view):
        super().__init__(view)
        self.view = view; self.t: dict[int, float] = {}; self.target: int | None = None; self.skel = False
        view.setMouseTracking(True); view.viewport().installEventFilter(self); view._ht = self
        self.timer = QTimer(self); self.timer.setInterval(16); self.timer.timeout.connect(self.step)

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t == ev.Type.MouseMove:
            idx = self.view.indexAt(ev.position().toPoint()); row = idx.row() if idx.isValid() else None
            if row != self.target: self.target = row; self.hoverRow.emit(row); self.wake()
        elif t == ev.Type.Leave:
            self.target = None; self.wake()
        return False

    def wake(self):
        if not self.timer.isActive(): self.timer.start()

    def level(self, row: int) -> float:
        return self.t.get(row, 0.0)

    def need_anim(self): self.skel = True; self.wake()


    def step(self):
        rows = set(self.t) | ({self.target} if self.target is not None else set()); moving = False
        for r in rows:
            v = self.t.get(r, 0.0); goal = 1.0 if r == self.target else 0.0
            nv = v + (goal - v) * 0.28
            if abs(goal - nv) < 0.02: nv = goal
            if nv != v: moving = True
            if nv <= 0.0 and r != self.target: self.t.pop(r, None)
            else: self.t[r] = nv
        if moving or self.skel: self.view.viewport().update()
        if not moving and not self.skel: self.timer.stop()
        self.skel = False


def _tracker(widget):
    return getattr(widget, "_ht", None) or (HoverTracker(widget) if isinstance(widget, QListView) else None)


def draw_skeleton(p: QPainter, r: QRectF, radius: float, widget=None):
    """Grey placeholder with a soft moving highlight."""
    path = QPainterPath(); path.addRoundedRect(r, radius, radius); p.fillPath(path, QColor(255, 255, 255, 14))
    ph = (time.time() * 0.9) % 1.6 - 0.3; x = r.x() + r.width() * ph
    g = QLinearGradient(x - r.width() * 0.25, 0, x + r.width() * 0.25, 0); g.setColorAt(0, QColor(255, 255, 255, 0)); g.setColorAt(0.5, QColor(255, 255, 255, 26)); g.setColorAt(1, QColor(255, 255, 255, 0))
    p.save(); p.setClipPath(path); p.fillRect(r, g); p.restore()
    tr = _tracker(widget) if widget is not None else None
    if tr: tr.need_anim()


class PosterDelegate(QStyledItemDelegate):
    def __init__(self, loader, w=170, favorites=None, parent=None):
        super().__init__(parent)
        self.loader, self.w, self.is_fav = loader, w, favorites

    def set_width(self, w):
        self.w = w

    @property
    def ph(self):
        return int(self.w * 1.5)

    def sizeHint(self, opt, idx):
        return QSize(self.w + 16, self.ph + 56)

    def paint(self, p: QPainter, opt, idx):
        it: Item = idx.data(ITEM_ROLE)
        p.save(); p.setRenderHint(QPainter.Antialiasing); p.setRenderHint(QPainter.SmoothPixmapTransform)
        tr = _tracker(opt.widget); selected = bool(opt.state & QStyle.State_Selected)
        lvl = max(tr.level(idx.row()) if tr else (1.0 if opt.state & QStyle.State_MouseOver else 0.0), 1.0 if selected else 0.0)
        r0 = QRectF(opt.rect.x() + 8, opt.rect.y() + 6, self.w, self.ph)
        if it.kind == "skeleton":
            draw_skeleton(p, r0.adjusted(0, 4, 0, 4), 14, opt.widget)
            draw_skeleton(p, QRectF(r0.x(), r0.bottom() + 12, self.w * 0.8, 12), 6); draw_skeleton(p, QRectF(r0.x(), r0.bottom() + 32, self.w * 0.45, 10), 5); p.restore(); return
        grow = 9 * lvl; r = r0.adjusted(-grow, -grow - 2 * lvl, grow, grow - 2 * lvl)
        if lvl > 0.02:                       # soft accent glow under the lifted card
            for k in range(5, 0, -1):
                p.setPen(Qt.NoPen); p.setBrush(QColor(*theme.ACC, int(16 * lvl / k * 1.6))); gp = QPainterPath(); gp.addRoundedRect(r.adjusted(-k * 3, -k * 3 + 6, k * 3, k * 3 + 8), 14 + k * 2, 14 + k * 2); p.drawPath(gp)
        path = QPainterPath(); path.addRoundedRect(r, 14, 14)
        p.setClipPath(path)
        pm = self.loader.get(it.logo); state = self.loader.status(it.logo)
        if pm is not None and not pm.isNull():
            s = pm.scaled(int(r.width()), int(r.height()), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            p.drawPixmap(int(r.x()), int(r.y()), s, (s.width() - int(r.width())) // 2, (s.height() - int(r.height())) // 2, int(r.width()), int(r.height()))
        elif state == "loading":
            draw_skeleton(p, r, 14, opt.widget)
        else:
            c1, c2 = tile_colors(it.name); g = QLinearGradient(r.topLeft(), r.bottomRight()); g.setColorAt(0, c1); g.setColorAt(1, c2)
            p.fillRect(r, g)
            f = QFont(p.font()); f.setPixelSize(int(self.w * 0.26)); f.setBold(True); p.setFont(f); p.setPen(QColor(255, 255, 255, 120))
            p.drawText(r, Qt.AlignCenter, _initials(it.name))
        fr = PROG(it) if it.kind in ("movie", "series") else 0.0
        if fr > 0.01:
            p.fillRect(QRectF(r.x(), r.bottom() - 6, r.width(), 6), QColor(0, 0, 0, 170)); p.fillRect(QRectF(r.x(), r.bottom() - 6, r.width() * fr, 6), QColor(theme.RED))
        p.setClipping(False)
        if lvl > 0.02:
            p.setPen(QPen(QColor(*theme.ACC, int(255 * lvl)), 4 if theme.TENFOOT else 3)); p.setBrush(Qt.NoBrush); p.drawPath(path)
        if self.is_fav and self.is_fav(it):
            p.setPen(Qt.NoPen); p.setBrush(QColor(theme.RED)); p.drawEllipse(QPointF(r.right() - 16, r.top() + 16), 8, 8)
        f = QFont(p.font()); f.setPixelSize(13); f.setBold(False); p.setFont(f)
        p.setPen(QColor(theme.TEXT if lvl > 0.5 else theme.SOFT))
        fm = QFontMetrics(f)
        t = fm.elidedText(it.name, Qt.ElideRight, self.w)
        p.drawText(QRectF(opt.rect.x() + 8, r0.bottom() + 8, self.w, 20), Qt.AlignLeft | Qt.AlignVCenter, t)
        rt = RATE(it) if it.kind in ("movie", "series") else ""
        sub = " · ".join(x for x in (it.year, rt or (("★ " + it.rating[:3]) if it.rating and it.rating not in ("0", "0.0") else "")) if x)
        if sub:
            p.setPen(QColor(theme.GOLD)); f.setPixelSize(12); p.setFont(f)
            p.drawText(QRectF(opt.rect.x() + 8, r0.bottom() + 28, self.w, 18), Qt.AlignLeft | Qt.AlignVCenter, QFontMetrics(f).elidedText(sub, Qt.ElideRight, self.w))
        p.restore()


class ChannelDelegate(QStyledItemDelegate):
    """Live channel row: number, logo, name, now-playing title and progress."""
    def __init__(self, loader, epg_now, favorites, parent=None):
        super().__init__(parent)
        self.loader, self.epg_now, self.is_fav = loader, epg_now, favorites

    def sizeHint(self, opt, idx):
        return QSize(300, 76)

    def paint(self, p, opt, idx):
        it: Item = idx.data(ITEM_ROLE)
        p.save(); p.setRenderHint(QPainter.Antialiasing); p.setRenderHint(QPainter.SmoothPixmapTransform)
        r = QRectF(opt.rect).adjusted(2, 3, -2, -3)
        if it.kind == "skeleton":
            draw_skeleton(p, r, 14, opt.widget); draw_skeleton(p, QRectF(r.x() + 60, r.y() + 14, r.width() * 0.5, 14), 6); draw_skeleton(p, QRectF(r.x() + 60, r.y() + 38, r.width() * 0.3, 11), 5); p.restore(); return
        tr = _tracker(opt.widget); sel = bool(opt.state & QStyle.State_Selected); hov = tr.level(idx.row()) if tr else (1.0 if opt.state & QStyle.State_MouseOver else 0.0)
        path = QPainterPath(); path.addRoundedRect(r, 14, 14)
        if sel:
            g = QLinearGradient(r.topLeft(), r.topRight()); g.setColorAt(0, QColor(*[int(v * 0.22) for v in theme.ACC], 255)); g.setColorAt(0.45, QColor("#17171c")); g.setColorAt(1, QColor("#121216"))
            p.fillPath(path, g)
            p.setPen(QPen(QColor(*theme.ACC, 150), 1.2)); p.drawPath(path)
            p.setPen(Qt.NoPen); p.setBrush(QColor(theme.RED)); p.drawRoundedRect(QRectF(r.x(), r.y() + 14, 4, r.height() - 28), 2, 2)
        else:
            p.fillPath(path, QColor(255, 255, 255, int(10 + 12 * hov)))
        f = QFont(p.font()); f.setPixelSize(13); f.setBold(True); p.setFont(f)
        p.setPen(QColor(theme.RED if sel else "#5c5c68"))
        num = (it.extra or {}).get("num") or str(idx.row() + 1)
        p.drawText(QRectF(r.x() + 8, r.y(), 40, r.height()), Qt.AlignCenter, str(num))
        lr = QRectF(r.x() + 50, r.y() + 11, 52, 52); pm = self.loader.get(it.logo); state = self.loader.status(it.logo)
        if pm is not None and not pm.isNull():
            light = self.loader.luma(it.logo) < 0.30            # dark logos get a light tile so they stay readable
            p.setPen(Qt.NoPen); p.setBrush(QColor("#e9e9ef") if light else QColor("#0b0b0e")); p.drawRoundedRect(lr, 11, 11)
            s = pm.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            p.drawPixmap(int(lr.x() + (52 - s.width()) / 2), int(lr.y() + (52 - s.height()) / 2), s)
        elif state == "loading":
            draw_skeleton(p, lr, 11, opt.widget)
        else:
            c1, c2 = tile_colors(it.name); g = QLinearGradient(lr.topLeft(), lr.bottomRight()); g.setColorAt(0, c1); g.setColorAt(1, c2)
            p.setPen(Qt.NoPen); p.setBrush(g); p.drawRoundedRect(lr, 11, 11)
            f.setPixelSize(16); p.setFont(f); p.setPen(QColor(255, 255, 255, 190)); p.drawText(lr, Qt.AlignCenter, _initials(it.name))
        x = lr.right() + 14; w = r.right() - x - 38
        f = QFont(p.font()); f.setPixelSize(15); f.setBold(True); p.setFont(f); p.setPen(QColor(theme.TEXT))
        p.drawText(QRectF(x, r.y() + 10, w, 22), Qt.AlignLeft | Qt.AlignVCenter, QFontMetrics(f).elidedText(it.name, Qt.ElideRight, int(w)))
        now = self.epg_now(it)
        f.setPixelSize(12); f.setBold(False); p.setFont(f); p.setPen(QColor("#9a9aa6" if sel else theme.MUTED))
        txt = now.title if now else (it.group or "")
        p.drawText(QRectF(x, r.y() + 33, w, 18), Qt.AlignLeft | Qt.AlignVCenter, QFontMetrics(f).elidedText(txt, Qt.ElideRight, int(w)))
        if now and now.stop > now.start:
            frac = max(0.0, min(1.0, (time.time() - now.start) / (now.stop - now.start)))
            bar = QRectF(x, r.bottom() - 13, w, 3)
            p.setPen(Qt.NoPen); p.setBrush(QColor(255, 255, 255, 28)); p.drawRoundedRect(bar, 1.5, 1.5)
            p.setBrush(QColor(theme.RED)); p.drawRoundedRect(QRectF(bar.x(), bar.y(), max(3.0, bar.width() * frac), 3), 1.5, 1.5)
        if self.is_fav and self.is_fav(it):
            p.setPen(Qt.NoPen); p.setBrush(QColor(theme.RED)); _heart(p, QPointF(r.right() - 22, r.center().y()), 8)
        p.restore()


def _heart(p: QPainter, c: QPointF, s: float, filled=True):
    path = QPainterPath(); x, y = c.x(), c.y()
    path.moveTo(x, y + s * 0.9)
    path.cubicTo(x - s * 1.6, y - s * 0.1, x - s * 0.7, y - s * 1.2, x, y - s * 0.35)
    path.cubicTo(x + s * 0.7, y - s * 1.2, x + s * 1.6, y - s * 0.1, x, y + s * 0.9)
    p.drawPath(path)


class ProgressBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.frac = 0.0; self.setFixedHeight(6)

    def set_fraction(self, f):
        self.frac = max(0.0, min(1.0, f)); self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); r = QRectF(self.rect())
        p.setPen(Qt.NoPen); p.setBrush(QColor(255, 255, 255, 30)); p.drawRoundedRect(r, 3, 3)
        if self.frac > 0:
            g = QLinearGradient(r.topLeft(), r.topRight()); g.setColorAt(0, QColor(theme.RED_DIM)); g.setColorAt(1, QColor(theme.RED))
            p.setBrush(g); p.drawRoundedRect(QRectF(r.x(), r.y(), max(6.0, r.width() * self.frac), r.height()), 3, 3)


def draw_nav_icon(p: QPainter, kind: str, r: QRectF, color: QColor):
    """Crisp vector line icons in a 22x22 box at r."""
    p.save(); p.translate(r.x(), r.y()); pen = QPen(color, 1.8); pen.setCapStyle(Qt.RoundCap); pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen); p.setBrush(Qt.NoBrush); path = QPainterPath()
    if kind == "home":
        path.moveTo(3, 11); path.lineTo(11, 4); path.lineTo(19, 11); path.moveTo(5.5, 9.5); path.lineTo(5.5, 18.5); path.lineTo(16.5, 18.5); path.lineTo(16.5, 9.5)
        path.moveTo(9, 18.5); path.lineTo(9, 13); path.lineTo(13, 13); path.lineTo(13, 18.5)
    elif kind == "live":
        path.addRoundedRect(QRectF(2.5, 6.5, 17, 11.5), 3, 3); path.moveTo(7.5, 3); path.lineTo(11, 6.5); path.lineTo(14.5, 3); path.moveTo(8, 20.5); path.lineTo(14, 20.5)
    elif kind == "movies":
        path.addRoundedRect(QRectF(2.5, 4.5, 17, 13), 3, 3)
        p.drawPath(path); p.setBrush(color); p.setPen(Qt.NoPen)
        tri = QPainterPath(); tri.moveTo(9, 8.2); tri.lineTo(14.2, 11); tri.lineTo(9, 13.8); tri.closeSubpath(); p.drawPath(tri); p.restore(); return
    elif kind == "series":
        path.addRoundedRect(QRectF(6, 3, 13, 10), 2.5, 2.5); path.moveTo(3, 8); path.lineTo(3, 16); path.quadTo(3, 18.5, 5.5, 18.5); path.lineTo(15, 18.5)
    elif kind == "guide":
        path.addRoundedRect(QRectF(2.5, 4.5, 17, 13.5), 3, 3); path.moveTo(2.5, 9.5); path.lineTo(19.5, 9.5); path.moveTo(8, 9.5); path.lineTo(8, 18); path.moveTo(13.5, 9.5); path.lineTo(13.5, 14)
    elif kind == "list":
        _heart(p, QPointF(11, 11), 6.5); p.restore(); return
    elif kind == "settings":
        for y, kx in ((6, 14), (11, 8), (16, 13)):
            path.moveTo(3, y); path.lineTo(19, y); path.addEllipse(QPointF(kx, y), 2.2, 2.2)
        p.setBrush(QColor(0, 0, 0))
    p.drawPath(path); p.restore()


class NavButton(QPushButton):
    """Sidebar entry with painted icon, accent bar and compact (icon-only) mode."""
    def __init__(self, text, icon, parent=None):
        super().__init__(parent); self.label, self.icon_kind, self.compact = text, icon, False
        self.setCheckable(True); self.setCursor(Qt.PointingHandCursor); self.setFixedHeight(46); self.setFocusPolicy(Qt.NoFocus)

    def set_compact(self, on):
        self.compact = on; self.setToolTip(self.label if on else ""); self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(10, 2, -10, -2); on = self.isChecked(); hov = self.underMouse()
        if on:
            g = QLinearGradient(r.topLeft(), r.topRight()); g.setColorAt(0, QColor(*theme.ACC, 46)); g.setColorAt(1, QColor(*theme.ACC, 6))
            path = QPainterPath(); path.addRoundedRect(r, 12, 12); p.fillPath(path, g)
            p.setPen(Qt.NoPen); p.setBrush(QColor(theme.RED)); p.drawRoundedRect(QRectF(r.x() - 8, r.y() + 11, 4, r.height() - 22), 2, 2)
        elif hov:
            path = QPainterPath(); path.addRoundedRect(r, 12, 12); p.fillPath(path, QColor(255, 255, 255, 14))
        col = QColor(theme.TEXT) if on else QColor("#c4c4cc" if hov else "#7d7d88")
        ix = r.x() + (r.width() - 22) / 2 if self.compact else r.x() + 16
        draw_nav_icon(p, self.icon_kind, QRectF(ix, r.y() + (r.height() - 22) / 2, 22, 22), col)
        if not self.compact:
            f = QFont(self.font()); f.setPixelSize(15); f.setBold(on); p.setFont(f); p.setPen(col)
            p.drawText(QRectF(r.x() + 52, r.y(), r.width() - 56, r.height()), Qt.AlignLeft | Qt.AlignVCenter, self.label)


class Carousel(QListView):
    """Single horizontal row of posters."""
    def __init__(self, model, delegate, parent=None):
        super().__init__(parent)
        self.setModel(model); self.setItemDelegate(delegate)
        self.setFlow(QListView.LeftToRight); self.setWrapping(False); self.setUniformItemSizes(True)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setMouseTracking(True); self.setFrameShape(QListView.NoFrame)
        self.setSelectionMode(QAbstractItemView.SingleSelection); self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._anim = QPropertyAnimation(self.horizontalScrollBar(), b"value", self); self._anim.setDuration(260)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def sync_height(self):
        self.setFixedHeight(self.itemDelegate().sizeHint(None, QModelIndex()).height() + 14)

    def wheelEvent(self, e):
        d = e.angleDelta()
        if abs(d.x()) > abs(d.y()):
            self._scroll(-d.x()); e.accept()
        else:
            e.ignore()      # let the page scroll vertically

    def _scroll(self, dx):
        sb = self.horizontalScrollBar()
        self._anim.stop(); self._anim.setStartValue(sb.value()); self._anim.setEndValue(max(0, min(sb.maximum(), sb.value() + dx)))
        self._anim.start()

    def page(self, direction):
        self._scroll(direction * int(self.viewport().width() * 0.8))


class Row(QWidget):
    activated = Signal(object)
    context = Signal(object, object)

    def __init__(self, title, loader, fav, parent=None):
        super().__init__(parent)
        self.model = ItemModel(self)
        self.delegate = PosterDelegate(loader, 150, fav)
        self.view = Carousel(self.model, self.delegate)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(2)
        top = QHBoxLayout(); self.title = QLabel(title); self.title.setObjectName("h2")
        top.addWidget(self.title); top.addStretch()
        for sym, d in (("‹", -1), ("›", 1)):
            b = QPushButton(sym); b.setObjectName("icon"); b.setFixedSize(34, 30); b.clicked.connect(lambda _=False, d=d: self.view.page(d)); top.addWidget(b)
        lay.addLayout(top); lay.addWidget(self.view)
        self.view.sync_height()
        self.view.clicked.connect(lambda i: self.activated.emit(i.data(ITEM_ROLE)))
        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(lambda pos: self._ctx(pos))

    def _ctx(self, pos):
        i = self.view.indexAt(pos)
        if i.isValid():
            self.context.emit(i.data(ITEM_ROLE), self.view.viewport().mapToGlobal(pos))

    def set_items(self, items):
        self.model.set_items(items); self.setVisible(bool(items))

    def set_card_width(self, w):
        self.delegate.set_width(w); self.view.sync_height(); self.model.layoutChanged.emit()


class Hero(QWidget):
    """Large cinematic banner with cross-fade between featured titles."""
    play = Signal(object)
    info = Signal(object)

    def __init__(self, loader, parent=None):
        super().__init__(parent)
        self.loader = loader; self.items: list[Item] = []; self.cur: Item | None = None; self.prev: Item | None = None
        self._blend = 1.0
        self.setMinimumHeight(380); self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.anim = QPropertyAnimation(self, b"blend", self); self.anim.setDuration(900); self.anim.setStartValue(0.0); self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.timer = QTimer(self); self.timer.setInterval(9000); self.timer.timeout.connect(self.advance)
        lay = QVBoxLayout(self); lay.setContentsMargins(48, 0, 48, 40); lay.addStretch()
        self.kicker = QLabel(""); self.kicker.setStyleSheet(f"color:{theme.RED}; font-weight:800; letter-spacing:3px; font-size:12px; background:transparent;")
        self.title = QLabel(""); self.title.setObjectName("h1"); self.title.setStyleSheet("font-size:42px; font-weight:600; background:transparent;"); self.title.setWordWrap(True)
        self.rate = QLabel(""); self.rate.setStyleSheet(f"color:{theme.GOLD}; font-size:15px; font-weight:600; background:transparent;")
        self.desc = QLabel(""); self.desc.setWordWrap(True); self.desc.setMaximumWidth(620); self.desc.setStyleSheet("color:#cfcfd6; font-size:15px; background:transparent;")
        btns = QHBoxLayout(); self.bplay = QPushButton("▶  Play"); self.bplay.setObjectName("primary")
        self.binfo = QPushButton("More info"); self.binfo.setObjectName("ghost")
        btns.addWidget(self.bplay); btns.addWidget(self.binfo); btns.addStretch()
        for w in (self.kicker, self.title, self.rate, self.desc):
            lay.addWidget(w)
        lay.addSpacing(8); lay.addLayout(btns)
        self.bplay.clicked.connect(lambda: self.cur and self.play.emit(self.cur))
        self.binfo.clicked.connect(lambda: self.cur and self.info.emit(self.cur))
        loader.loaded.connect(lambda _u: self.update())

    def get_blend(self): return self._blend
    def set_blend(self, v): self._blend = v; self.update()
    def refresh_rate(self):
        if self.cur and self.cur.kind in ("movie", "series"): self.rate.setText(RATE(self.cur))
    blend = Property(float, get_blend, set_blend)

    def set_items(self, items):
        self.items = items
        self.timer.stop()
        if items:
            self.cur = None; self.show_item(items[0], animate=False); self.timer.start() if len(items) > 1 else None
        else:
            self.cur = self.prev = None; self.kicker.setText(""); self.title.setText("Welcome to 91 TV")
            self.desc.setText("Add a playlist in Settings to get started. M3U / M3U8 files and URLs, or Xtream Codes login."); self.bplay.hide(); self.binfo.hide(); self.update()

    def advance(self):
        if self.items and self.isVisible():
            i = (self.items.index(self.cur) + 1) % len(self.items) if self.cur in self.items else 0
            self.show_item(self.items[i])

    def show_item(self, it, animate=True):
        self.prev, self.cur = self.cur, it
        self.kicker.setText({"movie": "MOVIE", "series": "SERIES", "live": "LIVE NOW"}.get(it.kind, ""))
        self.title.setText(it.name); self.rate.setText(RATE(it) if it.kind in ("movie", "series") else "")
        self.desc.setText(it.plot or it.group); self.bplay.show(); self.binfo.setVisible(it.kind == "series")
        self.bplay.setText("▶  Watch live" if it.kind == "live" else "▶  Play" if it.kind == "movie" else "▶  Episodes")
        self.loader.get(it.logo)
        if animate:
            self.anim.stop(); self.anim.start()
        else:
            self._blend = 1.0
        self.update()

    def _draw(self, p, it, opacity):
        pm = self.loader.get(it.logo) if it else None
        r = self.rect()
        if pm is not None and not pm.isNull():
            s = pm.scaled(r.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            p.setOpacity(opacity)
            p.drawPixmap(0, 0, s, (s.width() - r.width()) // 2, int((s.height() - r.height()) * 0.25), r.width(), r.height())
            p.setOpacity(1.0)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.SmoothPixmapTransform)
        r = self.rect(); p.fillRect(r, QColor(theme.BG))
        g = QLinearGradient(0, 0, r.width(), r.height()); g.setColorAt(0, QColor("#2a0d12")); g.setColorAt(0.5, QColor("#0e080a")); g.setColorAt(1, QColor("#070506"))
        p.fillRect(r, g)
        self._draw(p, self.prev, 1.0 - self._blend); self._draw(p, self.cur, self._blend)
        lg = QLinearGradient(0, 0, r.width() * 0.75, 0); lg.setColorAt(0, QColor(0, 0, 0, 235)); lg.setColorAt(1, QColor(0, 0, 0, 0)); p.fillRect(r, lg)
        bg = QLinearGradient(0, r.height() * 0.4, 0, r.height()); bg.setColorAt(0, QColor(0, 0, 0, 0)); bg.setColorAt(1, QColor(0, 0, 0, 255)); p.fillRect(r, bg)

    def resizeEvent(self, e):
        self.setFixedHeight(max(360, min(640, int(self.width() * 0.34))))
        super().resizeEvent(e)
