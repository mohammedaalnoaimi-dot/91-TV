"""Netflix-style series page: big backdrop banner, Play/Resume, My List, season selector, episode list."""
from __future__ import annotations
import re
from PySide6.QtCore import Qt, Signal, QAbstractListModel, QModelIndex, QSize, QRectF, QPointF, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QPainterPath, QFont, QFontMetrics, QPen
from PySide6.QtWidgets import (QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QListView, QStyledItemDelegate,
                               QStyle, QFrame, QAbstractItemView, QSizePolicy)
from .backdrop import Backdrop
from . import theme, widgets
from ..models import Item, Episode

EP_ROLE = Qt.UserRole + 2
_TAG = re.compile(r"^\s*[A-Z0-9+]{1,10}(?:-[A-Z0-9+]{1,10})*\s+-\s+")
_SXXEXX = re.compile(r"^.*?\bS\d{1,3}\s?E\d{1,4}\b[\s._:\-–]*", re.I)


def clean_title(name: str) -> str:
    """'4K-AR-DO - Show' -> 'Show' (provider tag prefixes are noise on a detail page)."""
    c = _TAG.sub("", name or "", count=1).strip()
    return c or (name or "")


def clean_episode_title(title: str, number: int) -> str:
    """'4K-AR-DO - Show - S01E07 - A Child' -> 'A Child'; falls back to 'Episode N'."""
    t = title or ""
    if _SXXEXX.match(t):
        t = _SXXEXX.sub("", t, count=1)
    t = t.strip(" -–:._")
    if not t or re.fullmatch(r"(?i)episode\s*\d+", t):
        return f"Episode {number}" if number else (title or "Episode")
    return t


def _okr(r):
    try: return 0 < float(r) <= 10
    except (TypeError, ValueError): return False


class EpisodeModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent); self.eps: list[Episode] = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.eps)

    def data(self, idx, role=Qt.DisplayRole):
        if not idx.isValid(): return None
        e = self.eps[idx.row()]
        if role == EP_ROLE: return e
        if role == Qt.DisplayRole: return e.title
        return None

    def set_episodes(self, eps):
        self.beginResetModel(); self.eps = list(eps); self.endResetModel()


class EpisodeDelegate(QStyledItemDelegate):
    H = 112

    def __init__(self, loader, fallback_logo, resume_url, parent=None):
        super().__init__(parent); self.loader, self.fallback_logo, self.resume_url = loader, fallback_logo, resume_url

    def sizeHint(self, opt, idx):
        return QSize(900, self.H)

    def paint(self, p: QPainter, opt, idx):
        e: Episode = idx.data(EP_ROLE)
        p.save(); p.setRenderHint(QPainter.Antialiasing); p.setRenderHint(QPainter.SmoothPixmapTransform)
        r = QRectF(opt.rect).adjusted(0, 4, 0, -4); hov = bool(opt.state & (QStyle.State_MouseOver | QStyle.State_Selected))
        path = QPainterPath(); path.addRoundedRect(r, 16, 16)
        p.fillPath(path, QColor(255, 255, 255, 22) if hov else QColor(255, 255, 255, 8))
        f = QFont(p.font()); f.setPixelSize(24); f.setBold(True); p.setFont(f); p.setPen(QColor(theme.TEXT if hov else "#6a6a76"))
        p.drawText(QRectF(r.x() + 8, r.y(), 52, r.height()), Qt.AlignCenter, str(e.number))
        tr = QRectF(r.x() + 66, r.y() + 10, 148, r.height() - 20)
        tp = QPainterPath(); tp.addRoundedRect(tr, 10, 10); p.setClipPath(tp)
        pm = self.loader.get(e.image) or self.loader.get(self.fallback_logo)
        if pm is not None and not pm.isNull():
            s = pm.scaled(int(tr.width()), int(tr.height()), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            p.drawPixmap(int(tr.x()), int(tr.y()), s, (s.width() - int(tr.width())) // 2, (s.height() - int(tr.height())) // 2, int(tr.width()), int(tr.height()))
            p.fillRect(tr, QColor(0, 0, 0, 70 if hov else 110))
        else:
            g = QLinearGradient(tr.topLeft(), tr.bottomRight()); g.setColorAt(0, QColor("#22222a")); g.setColorAt(1, QColor("#0e0e12")); p.fillRect(tr, g)
        p.setClipping(False)
        c = tr.center(); p.setPen(Qt.NoPen); p.setBrush(QColor(0, 0, 0, 150 if hov else 90)); p.drawEllipse(c, 19, 19)
        p.setBrush(QColor(theme.TEXT)); tri = QPainterPath(); tri.moveTo(c.x() - 5, c.y() - 8); tri.lineTo(c.x() + 9, c.y()); tri.lineTo(c.x() - 5, c.y() + 8); tri.closeSubpath(); p.drawPath(tri)
        x = tr.right() + 20; w = r.right() - x - 16
        f = QFont(p.font()); f.setPixelSize(17); f.setBold(True); p.setFont(f); p.setPen(QColor(theme.TEXT))
        dur = e.duration if e.duration and e.duration not in ("0", "00:00:00") else ""
        dw = QFontMetrics(f).horizontalAdvance(dur) + 6 if dur else 0
        p.drawText(QRectF(x, r.y() + 12, w - dw, 24), Qt.AlignLeft | Qt.AlignVCenter, QFontMetrics(f).elidedText(e.title, Qt.ElideRight, int(w - dw)))
        f.setBold(False); f.setPixelSize(13); p.setFont(f); p.setPen(QColor(theme.MUTED))
        if dur: p.drawText(QRectF(r.right() - 16 - dw, r.y() + 12, dw, 24), Qt.AlignRight | Qt.AlignVCenter, dur)
        if self.resume_url() and e.url == self.resume_url():
            f.setBold(True); f.setPixelSize(11); p.setFont(f); p.setPen(QColor(theme.RED)); p.drawText(QRectF(x, r.y() + 38, w, 16), Qt.AlignLeft | Qt.AlignVCenter, "CONTINUE WATCHING")
            f.setBold(False); f.setPixelSize(13); p.setFont(f); p.setPen(QColor(theme.MUTED)); top = 56
        else:
            top = 40
        p.drawText(QRectF(x, r.y() + top, w, r.height() - top - 8), Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, (e.plot or "")[:240])
        p.restore()


class DetailHero(QWidget):
    def __init__(self, loader):
        super().__init__(); self.loader = loader; self.image_url = ""; self._z = 0.0
        self.zoom_anim = QVariantAnimation(self); self.zoom_anim.setDuration(1100); self.zoom_anim.setEasingCurve(QEasingCurve.OutCubic); self.zoom_anim.valueChanged.connect(self._set_zoom)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        loader.loaded.connect(lambda u: self.isVisible() and u == self.image_url and self.update())

    def _set_zoom(self, v): self._z = float(v); self.update()

    def kick(self):
        """Netflix-style 'push in': the backdrop starts slightly zoomed and settles."""
        self.zoom_anim.stop(); self.zoom_anim.setStartValue(1.0); self.zoom_anim.setEndValue(0.0); self.zoom_anim.start()

    def set_image(self, url): self.image_url = url; self.loader.get(url, wide=True); self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.SmoothPixmapTransform); r = self.rect()
        g = QLinearGradient(0, 0, r.width(), r.height()); g.setColorAt(0, QColor("#2a0a0d")); g.setColorAt(0.5, QColor("#0a0a0d")); g.setColorAt(1, QColor("#000")); p.fillRect(r, g)
        pm = self.loader.get(self.image_url, wide=True)
        if pm is not None and not pm.isNull():
            f = 1.0 + 0.12 * self._z
            s = pm.scaled(int(r.width() * f), int(r.height() * f), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            p.drawPixmap(0, 0, s, (s.width() - r.width()) // 2, int((s.height() - r.height()) * 0.2), r.width(), r.height())
        lg = QLinearGradient(0, 0, r.width() * 0.8, 0); lg.setColorAt(0, QColor(0, 0, 0, 240)); lg.setColorAt(0.6, QColor(0, 0, 0, 150)); lg.setColorAt(1, QColor(0, 0, 0, 0)); p.fillRect(r, lg)
        bg = QLinearGradient(0, r.height() * 0.45, 0, r.height()); bg.setColorAt(0, QColor(0, 0, 0, 0)); bg.setColorAt(1, QColor(0, 0, 0, 255)); p.fillRect(r, bg)


class DetailPage(QScrollArea):
    back = Signal()
    play_episode = Signal(object, object)       # Episode, series Item
    toggle_fav = Signal(object)
    play_movie = Signal(object)

    def __init__(self, loader):
        super().__init__()
        self._movie = False
        self.loader = loader; self.item: Item | None = None; self.eps: list[Episode] = []; self._resume = ""; self._first: Episode | None = None
        self.setWidgetResizable(True); self.setFrameShape(QFrame.NoFrame)
        body = Backdrop(); self.setWidget(body); root = QVBoxLayout(body); root.setContentsMargins(0, 0, 0, 40); root.setSpacing(0)
        self.body = body; self.hero = DetailHero(loader); self.hero.setFixedHeight(520); root.addWidget(self.hero)
        loader.loaded.connect(lambda u: self.isVisible() and u == self.hero.image_url and self.body.set_tint(loader.color(u)))
        hl = QVBoxLayout(self.hero); hl.setContentsMargins(56, 22, 56, 44); hl.setSpacing(8)
        self.b_back = QPushButton("←  Back"); self.b_back.setObjectName("ghostsm"); self.b_back.setCursor(Qt.PointingHandCursor); self.b_back.setFixedWidth(110)
        hl.addWidget(self.b_back, 0, Qt.AlignLeft); hl.addStretch()
        self.kicker = QLabel("SERIES"); self.kicker.setObjectName("eyebrow")
        self.title = QLabel(""); self.title.setWordWrap(True); self.title.setStyleSheet("font-size:50px; font-weight:800; background:transparent;"); self.title.setMaximumWidth(900)
        self.rate = QLabel(""); self.rate.setStyleSheet(f"color:{theme.GOLD}; font-size:16px; font-weight:600; background:transparent;")
        self.meta = QLabel(""); self.meta.setStyleSheet("color:#d4d4da; font-size:15px; font-weight:600; background:transparent;")
        self.plot = QLabel(""); self.plot.setWordWrap(True); self.plot.setMaximumWidth(700); self.plot.setStyleSheet("color:#cfcfd6; font-size:15px; background:transparent;")
        self.cast = QLabel(""); self.cast.setWordWrap(True); self.cast.setMaximumWidth(700); self.cast.setStyleSheet("color:#8d8d96; font-size:13px; background:transparent;")
        for w in (self.kicker, self.title, self.rate, self.meta, self.plot, self.cast): hl.addWidget(w)
        hl.addSpacing(8); row = QHBoxLayout(); row.setSpacing(12)
        self.b_play = QPushButton("▶  Play"); self.b_play.setObjectName("primary"); self.b_fav = QPushButton("♡  My List"); self.b_fav.setObjectName("ghost")
        for b in (self.b_play, self.b_fav): b.setCursor(Qt.PointingHandCursor); row.addWidget(b)
        row.addStretch(); hl.addLayout(row)
        sec = QWidget(); sl = QVBoxLayout(sec); sl.setContentsMargins(56, 18, 56, 0); sl.setSpacing(10)
        top = QHBoxLayout(); h = QLabel("Episodes"); h.setObjectName("h1"); top.addWidget(h); top.addStretch()
        self.season = QComboBox(); self.season.setMinimumWidth(190); top.addWidget(self.season); sl.addLayout(top)
        self.model = EpisodeModel(self); self.view = QListView(); self.view.setModel(self.model)
        self.view.setItemDelegate(EpisodeDelegate(loader, "", lambda: self._resume)); self.view.setMouseTracking(True); self.view.setFrameShape(QFrame.NoFrame)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.view.setEditTriggers(QAbstractItemView.NoEditTriggers); self.view.setCursor(Qt.PointingHandCursor)
        sl.addWidget(self.view); self.empty = QLabel("No episodes found for this series."); self.empty.setObjectName("muted"); self.empty.hide(); sl.addWidget(self.empty)
        self.sec = sec; root.addWidget(sec); root.addStretch()
        self.b_back.clicked.connect(self.back); self.season.currentIndexChanged.connect(lambda _i: self._fill())
        self.view.clicked.connect(lambda i: self._play(i.data(EP_ROLE))); self.view.activated.connect(lambda i: self._play(i.data(EP_ROLE)))
        self.b_play.clicked.connect(self._on_play); self.b_fav.clicked.connect(lambda: self.item and self.toggle_fav.emit(self.item))

    def resizeEvent(self, e):
        h = max(430, min(720, int(self.viewport().width() * 0.40)))
        if self.hero.height() != h:
            self.hero.setFixedHeight(h)
        super().resizeEvent(e)

    # ---- data
    def _on_play(self):
        if self._movie and self.item: self.play_movie.emit(self.item)
        else: self._play(self._target())

    def show_movie(self, item: Item, info: dict, resume_pos: float, is_fav: bool):
        """Movie variant of the page: same hero, no episode list."""
        from ..tmdb import clean_query
        self._movie = True; self.item, self.eps, self._resume = item, [], ""; self.kicker.setText("MOVIE"); self.sec.hide()
        self.title.setText(clean_query(item.name)[0] or clean_title(item.name)); self.rate.setText(widgets.RATE(item))
        rating = str(info.get("rating") or item.rating or "").strip(); year = (str(info.get("releaseDate") or info.get("release_date") or "") or item.year or "")[:4]
        dur = str(info.get("duration") or "").strip(); dur = "" if dur in ("0", "00:00:00") else dur
        parts = [year, ("★ " + rating[:3]) if _okr(rating) else "", dur, (info.get("genre") or "").strip()[:60]]
        self.meta.setText("   ·   ".join(x for x in parts if x))
        plot = (info.get("plot") or info.get("description") or item.plot or "").strip(); self.plot.setText(plot[:520] + ("…" if len(plot) > 520 else "")); self.plot.setVisible(bool(plot))
        cast = (info.get("cast") or info.get("actors") or "").strip(); self.cast.setText(("Starring: " + cast[:160]) if cast else ""); self.cast.setVisible(bool(cast))
        bd = info.get("backdrop_path"); bd = bd[0] if isinstance(bd, list) and bd else (bd if isinstance(bd, str) else "")
        self.hero.set_image(bd or info.get("cover") or item.logo); self.hero.kick(); self.body.set_tint(self.loader.color(self.hero.image_url))
        self.b_play.setText("▶  Resume" if resume_pos > 30 else "▶  Play"); self.b_play.setEnabled(bool(item.url)); self.set_fav(is_fav); self.verticalScrollBar().setValue(0)

    def show_series(self, item: Item, info: dict, eps: list[Episode], resume_url: str | None, is_fav: bool):
        self._movie = False; self.kicker.setText("SERIES"); self.sec.show()
        self.item, self.eps, self._resume = item, eps, resume_url or ""
        self.view.itemDelegate().fallback_logo = item.logo
        for e in eps: e.title = clean_episode_title(e.title, e.number)
        self.title.setText(clean_title(item.name)); self.rate.setText(widgets.RATE(item))
        seasons = sorted({e.season for e in eps})
        genre = (info.get("genre") or "").strip(); rating = str(info.get("rating") or item.rating or "").strip()
        year = (str(info.get("releaseDate") or info.get("release_date") or "") or item.year or "")[:4]
        parts = [year, ("★ " + rating[:3]) if _okr(rating) else "", f"{len(seasons)} season{'s' if len(seasons) != 1 else ''}" if seasons else "", genre[:60]]
        self.meta.setText("   ·   ".join(x for x in parts if x))
        plot = (info.get("plot") or item.plot or "").strip(); self.plot.setText(plot[:520] + ("…" if len(plot) > 520 else "")); self.plot.setVisible(bool(plot))
        cast = (info.get("cast") or "").strip(); self.cast.setText(("Starring: " + cast[:160]) if cast else ""); self.cast.setVisible(bool(cast))
        bd = info.get("backdrop_path"); bd = bd[0] if isinstance(bd, list) and bd else (bd if isinstance(bd, str) else "")
        self.hero.set_image(bd or info.get("cover") or item.logo); self.hero.kick(); self.body.set_tint(self.loader.color(self.hero.image_url))
        self.season.blockSignals(True); self.season.clear()
        for s in seasons: self.season.addItem(f"Season {s}", s)
        target = next((e for e in eps if e.url == self._resume), None)
        if target: self.season.setCurrentIndex(max(0, self.season.findData(target.season)))
        self.season.blockSignals(False); self.season.setVisible(len(seasons) > 1)
        self._first = eps[0] if eps else None
        t = target or self._first
        self.b_play.setText((f"▶  Resume S{t.season} E{t.number}" if target else f"▶  Play S{t.season} E{t.number}") if t else "▶  Play"); self.b_play.setEnabled(bool(t))
        self.set_fav(is_fav); self._fill(); self.verticalScrollBar().setValue(0)

    def set_fav(self, on: bool): self.b_fav.setText("♥  In My List" if on else "♡  My List")

    def _fill(self):
        s = self.season.currentData(); lst = [e for e in self.eps if s is None or e.season == s]
        self.model.set_episodes(lst); self.view.setFixedHeight(max(1, len(lst)) * EpisodeDelegate.H + 8); self.empty.setVisible(not self.eps)

    def _target(self):
        return next((e for e in self.eps if e.url == self._resume), None) or self._first

    def _play(self, ep):
        if ep and self.item: self.play_episode.emit(ep, self.item)
