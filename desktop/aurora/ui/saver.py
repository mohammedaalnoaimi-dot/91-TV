"""Clock screensaver: big time, date, next prayer. Drifts a little every minute so a screen never burns in."""
from __future__ import annotations
from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QFont
from PySide6.QtWidgets import QWidget
from .. import prayer
from . import theme


class Saver(QWidget):
    def __init__(self, parent):
        super().__init__(parent); self.setAttribute(Qt.WA_OpaquePaintEvent); self.setCursor(Qt.BlankCursor)
        self.t = ""; self.d = ""; self.p = ""; self.drift = 0

    def tick(self, times):
        n = prayer.now(); self.t = n.strftime("%H:%M"); self.d = n.strftime("%A  ·  %d %B %Y").upper(); self.drift = n.minute
        nx = times.next(n); self.p = f"NEXT PRAYER   {nx[0].upper()}  {nx[1].strftime('%H:%M')}   ·   in {prayer.left(nx[1] - n)}" if nx else ""
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.TextAntialiasing); r = self.rect(); p.fillRect(r, QColor("#050304"))
        dx = int((self.drift % 10 - 5) * r.width() * 0.012); dy = int((self.drift % 7 - 3) * r.height() * 0.015); c = r.center(); c.setX(c.x() + dx); c.setY(c.y() + dy)
        f = QFont(theme.DISPLAY); f.setPixelSize(max(80, int(r.height() * 0.30))); p.setFont(f); p.setPen(QColor(theme.TEXT))
        p.drawText(c.x() - r.width() // 2, c.y() - int(r.height() * 0.22), r.width(), int(r.height() * 0.4), Qt.AlignCenter, self.t)
        f2 = QFont(theme.BODY); f2.setPixelSize(max(16, int(r.height() * 0.028))); f2.setLetterSpacing(QFont.AbsoluteSpacing, 4); p.setFont(f2); p.setPen(QColor(theme.GOLD))
        p.drawText(c.x() - r.width() // 2, c.y() + int(r.height() * 0.2), r.width(), 40, Qt.AlignCenter, self.d)
        p.setPen(QColor(theme.MUTED)); p.drawText(c.x() - r.width() // 2, c.y() + int(r.height() * 0.2) + 50, r.width(), 40, Qt.AlignCenter, self.p)
