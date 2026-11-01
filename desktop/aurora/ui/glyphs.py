"""Vector control icons (play, pause, skip, volume, full screen...) drawn with QPainter, so they look the same on every PC and never depend on font glyphs."""
from __future__ import annotations
from PySide6.QtCore import Qt, QRectF, QPointF, QSize
from PySide6.QtGui import QPainter, QPainterPath, QColor, QPen, QFont
from PySide6.QtWidgets import QPushButton


def draw_glyph(p: QPainter, kind: str, r: QRectF, color: QColor):
    """Draw glyph `kind` inside rect r."""
    p.save(); p.setRenderHint(QPainter.Antialiasing); c = r.center(); s = min(r.width(), r.height())
    p.setPen(Qt.NoPen); p.setBrush(color)
    if kind == "play":
        a = s * 0.42; path = QPainterPath(); path.moveTo(c.x() - a * 0.7, c.y() - a); path.lineTo(c.x() + a * 1.05, c.y()); path.lineTo(c.x() - a * 0.7, c.y() + a); path.closeSubpath(); p.drawPath(path)
    elif kind == "pause":
        w, h = s * 0.15, s * 0.78; g = s * 0.12
        p.drawRoundedRect(QRectF(c.x() - g - w, c.y() - h / 2, w, h), 1.5, 1.5); p.drawRoundedRect(QRectF(c.x() + g, c.y() - h / 2, w, h), 1.5, 1.5)
    elif kind in ("prev", "next"):
        d = 1 if kind == "next" else -1; a = s * 0.3
        path = QPainterPath(); x0 = c.x() - d * a * 0.9
        path.moveTo(x0, c.y() - a); path.lineTo(x0 + d * a * 1.5, c.y()); path.lineTo(x0, c.y() + a); path.closeSubpath(); p.drawPath(path)
        p.drawRoundedRect(QRectF(c.x() + d * a * 0.85 - (1.5 if d > 0 else 1.5), c.y() - a, 3, a * 2), 1, 1)
    elif kind in ("back10", "fwd10"):
        d = -1 if kind == "back10" else 1; rad = s * 0.34
        pen = QPen(color, max(1.8, s * 0.07), Qt.SolidLine, Qt.RoundCap); p.setPen(pen); p.setBrush(Qt.NoBrush)
        # open ring with a gap at the top; arrow head on the end that points the way you are skipping
        gap = 50; span = 360 - 2 * gap
        p.drawArc(QRectF(c.x() - rad, c.y() - rad, rad * 2, rad * 2), int((90 + (gap if d < 0 else -gap)) * 16) if d < 0 else int((90 - gap) * 16), int((span if d < 0 else -span) * 16))
        import math
        ang = math.radians(90 + gap if d < 0 else 90 - gap); tip = QPointF(c.x() + rad * math.cos(ang), c.y() - rad * math.sin(ang)); ah = s * 0.15
        p.setPen(Qt.NoPen); p.setBrush(color); path = QPainterPath()
        path.moveTo(tip.x() + d * ah * 0.2, tip.y() - ah * 0.9); path.lineTo(tip.x() + d * ah * 0.2, tip.y() + ah * 0.9); path.lineTo(tip.x() - d * ah * 1.1, tip.y()); path.closeSubpath(); p.drawPath(path)
        f = QFont(p.font()); f.setPixelSize(int(s * 0.27)); f.setBold(True); p.setFont(f); p.setPen(color); p.drawText(QRectF(c.x() - rad, c.y() - rad, rad * 2, rad * 2), Qt.AlignCenter, "10")
    elif kind == "vol":
        a = s * 0.2; path = QPainterPath(); path.moveTo(c.x() - a * 1.6, c.y() - a * 0.55); path.lineTo(c.x() - a * 0.7, c.y() - a * 0.55); path.lineTo(c.x() + a * 0.3, c.y() - a * 1.3)
        path.lineTo(c.x() + a * 0.3, c.y() + a * 1.3); path.lineTo(c.x() - a * 0.7, c.y() + a * 0.55); path.lineTo(c.x() - a * 1.6, c.y() + a * 0.55); path.closeSubpath(); p.drawPath(path)
        p.setBrush(Qt.NoBrush); p.setPen(QPen(color, max(1.6, s * 0.06), Qt.SolidLine, Qt.RoundCap))
        for k in (1, 2): rr = a * (0.9 + k * 0.75); p.drawArc(QRectF(c.x() + a * 0.3 - rr, c.y() - rr, rr * 2, rr * 2), -45 * 16, 90 * 16)
    elif kind == "full":
        a = s * 0.3; l = s * 0.14; p.setBrush(Qt.NoBrush); p.setPen(QPen(color, max(1.8, s * 0.07), Qt.SolidLine, Qt.FlatCap, Qt.MiterJoin))
        for sx in (-1, 1):
            for sy in (-1, 1):
                x, y = c.x() + sx * a, c.y() + sy * a; p.drawLine(QPointF(x, y), QPointF(x - sx * l * 1.4, y)); p.drawLine(QPointF(x, y), QPointF(x, y - sy * l * 1.4))
    elif kind == "back":
        a = s * 0.3; p.setBrush(Qt.NoBrush); p.setPen(QPen(color, max(2.0, s * 0.075), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(QPointF(c.x() + a, c.y()), QPointF(c.x() - a, c.y())); p.drawLine(QPointF(c.x() - a, c.y()), QPointF(c.x() - a * 0.15, c.y() - a * 0.85)); p.drawLine(QPointF(c.x() - a, c.y()), QPointF(c.x() - a * 0.15, c.y() + a * 0.85))
    p.restore()


class GlyphButton(QPushButton):
    """Round, flat icon button. setText("⏸" / "▶") still works so older code can flip play / pause."""
    def __init__(self, kind: str, size: int = 44, parent=None):
        super().__init__("", parent); self.kind = kind; self._size = size; self.setObjectName("glyph"); self.setCursor(Qt.PointingHandCursor); self.setFixedSize(size, size)
        self.setStyleSheet("QPushButton#glyph { background: transparent; border: none; padding: 0; }"); self._hover = False

    def setText(self, t: str):
        if self.kind in ("play", "pause"): self.kind = "pause" if "⏸" in t else "play"; self.update()

    def set_size(self, n: int): self._size = n; self.setFixedSize(n, n)

    def enterEvent(self, e): self._hover = True; self.update(); super().enterEvent(e)
    def leaveEvent(self, e): self._hover = False; self.update(); super().leaveEvent(e)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); r = QRectF(self.rect())
        if self._hover: p.setPen(Qt.NoPen); p.setBrush(QColor(255, 255, 255, 34)); p.drawEllipse(r.adjusted(2, 2, -2, -2))
        if self.hasFocus(): p.setPen(QPen(QColor("#ffffff"), 2)); p.setBrush(Qt.NoBrush); p.drawEllipse(r.adjusted(2, 2, -2, -2))
        draw_glyph(p, self.kind, r.adjusted(self._size * 0.1, self._size * 0.1, -self._size * 0.1, -self._size * 0.1), QColor(255, 255, 255, 255 if self._hover else 235))
