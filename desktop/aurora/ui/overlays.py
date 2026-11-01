"""Floating overlays that sit above the native video surface: fading controls host, channel banner, number-entry OSD.
They are tiny frameless tool windows (a child widget can't be drawn over a native video window), never take focus, and fade in/out."""
from __future__ import annotations
import time
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QRect, QRectF
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from .widgets import ProgressBar
from .glyphs import draw_glyph
from PySide6.QtGui import QPainter, QColor
from . import theme

FLAGS = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus


class OverlayWindow(QWidget):
    def __init__(self, parent):
        super().__init__(parent, FLAGS)
        self.setAttribute(Qt.WA_ShowWithoutActivating); self.setFocusPolicy(Qt.NoFocus)
        self.anim = QPropertyAnimation(self, b"windowOpacity", self); self.anim.setDuration(180)
        self.anim.finished.connect(self._after_fade); self._hiding = False
        self.auto = QTimer(self); self.auto.setSingleShot(True); self.auto.timeout.connect(self.fade_out)

    def pop(self, seconds: float = 0.0):
        """Show (fading in); if seconds>0 fade out again automatically."""
        self.auto.stop(); self._hiding = False
        if not self.isVisible():
            self.setWindowOpacity(0.0); self.show()
        self.anim.stop(); self.anim.setStartValue(self.windowOpacity()); self.anim.setEndValue(1.0); self.anim.start()
        if seconds > 0: self.auto.start(int(seconds * 1000))

    def fade_out(self):
        if not self.isVisible() or self._hiding: return
        self._hiding = True; self.anim.stop(); self.anim.setStartValue(self.windowOpacity()); self.anim.setEndValue(0.0); self.anim.start()

    def _after_fade(self):
        if self._hiding:
            self.hide(); self._hiding = False

    def hide_now(self):
        self.auto.stop(); self.anim.stop(); self._hiding = False; self.hide(); self.setWindowOpacity(1.0)


class ControlsHost(OverlayWindow):
    """Hosts an existing widget (the player's top/bottom control bar) while in full screen."""
    def __init__(self, parent, edge: str):
        super().__init__(parent); self.edge = edge
        self.lay = QVBoxLayout(self); self.lay.setContentsMargins(0, 0, 0, 0); self.lay.setSpacing(0)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def host(self, w: QWidget): self.lay.addWidget(w)

    def place(self, video: QRect):
        h = self.sizeHint().height()
        y = video.top() if self.edge == "top" else video.bottom() - h + 1
        self.setGeometry(video.left(), y, video.width(), h)


class Banner(OverlayWindow):
    def __init__(self, parent):
        super().__init__(parent); self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QWidget#bn { background: rgba(10,10,13,235); border: 1px solid rgba(255,255,255,0.10); border-radius: 18px; } QLabel { background: transparent; }")
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); f = QFrame(); f.setObjectName("bn"); outer.addWidget(f)
        l = QHBoxLayout(f); l.setContentsMargins(22, 16, 26, 16); l.setSpacing(18)
        self.num = QLabel(""); self.num.setStyleSheet(theme.acc("font-size:44px; font-weight:800; color:#e0262d;")); self.num.setMinimumWidth(78); l.addWidget(self.num)
        col = QVBoxLayout(); col.setSpacing(4)
        self.name = QLabel(""); self.name.setStyleSheet("font-size:22px; font-weight:700;")
        self.now = QLabel(""); self.now.setStyleSheet("font-size:15px; font-weight:600; color:#e8e8ec;")
        self.bar = ProgressBar(); self.times = QLabel(""); self.times.setStyleSheet("font-size:12px; color:#8d8d96;")
        self.nxt = QLabel(""); self.nxt.setStyleSheet("font-size:13px; color:#9a9aa3;")
        for w in (self.name, self.now, self.bar, self.times, self.nxt): col.addWidget(w)
        l.addLayout(col, 1); self.setFixedWidth(620)

    def show_channel(self, number, name, now, nxt, video: QRect):
        """now/nxt: Programme or None."""
        self.num.setText(str(number) if number else ""); self.name.setText(name)
        t = time.time()
        if now:
            self.now.setText("Now · " + now.title); self.bar.setVisible(True); self.bar.set_fraction((t - now.start) / max(1, now.stop - now.start))
            fm = lambda x: time.strftime("%H:%M", time.localtime(x)); self.times.setText(f"{fm(now.start)} – {fm(now.stop)}"); self.times.show()
        else:
            self.now.setText("No guide information"); self.bar.setVisible(False); self.times.hide()
        self.nxt.setText(("Next · " + nxt.title) if nxt else ""); self.nxt.setVisible(bool(nxt))
        self.adjustSize(); self.move(video.left() + 36, video.bottom() - self.height() - 36 - 0); self.pop(4.5)


class NumberOSD(OverlayWindow):
    def __init__(self, parent):
        super().__init__(parent); self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(theme.acc("QWidget#no { background: rgba(10,10,13,240); border: 1px solid rgba(224,38,45,0.6); border-radius: 16px; } QLabel { background: transparent; }"))
        o = QVBoxLayout(self); o.setContentsMargins(0, 0, 0, 0); f = QFrame(); f.setObjectName("no"); o.addWidget(f)
        l = QVBoxLayout(f); l.setContentsMargins(26, 12, 26, 12); l.setSpacing(0)
        self.val = QLabel(""); self.val.setStyleSheet("font-size:52px; font-weight:800; letter-spacing:4px;"); self.val.setAlignment(Qt.AlignCenter)
        self.sub = QLabel(""); self.sub.setStyleSheet("font-size:14px; color:#9a9aa3;"); self.sub.setAlignment(Qt.AlignCenter)
        l.addWidget(self.val); l.addWidget(self.sub); self.setMinimumWidth(240)

    def show_entry(self, digits: str, hint: str, video: QRect):
        self.val.setText(digits + "_"); self.sub.setText(hint); self.adjustSize()
        self.move(video.right() - self.width() - 36, video.top() + 36); self.pop(0)


class CenterOSD(OverlayWindow):
    """Big round play / pause symbol that pops in the middle of the picture when you pause or resume (like Netflix)."""
    def __init__(self, parent):
        super().__init__(parent); self.setAttribute(Qt.WA_TranslucentBackground); self.setFixedSize(132, 132); self.kind = "play"

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); r = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        p.setPen(Qt.NoPen); p.setBrush(QColor(0, 0, 0, 150)); p.drawEllipse(r); draw_glyph(p, self.kind, r.adjusted(26, 26, -26, -26), QColor(255, 255, 255, 245))

    def flash(self, kind: str, video: QRect):
        self.kind = kind; self.update(); self.move(video.center().x() - 66, video.center().y() - 66); self.pop(0.8)
