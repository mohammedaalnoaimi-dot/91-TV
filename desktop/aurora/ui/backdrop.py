from PySide6.QtCore import QPointF, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QRadialGradient
from PySide6.QtWidgets import QWidget
from . import theme


def normalise_tint(c: QColor | None) -> QColor:
    """Make a poster colour usable as a background glow: keep the hue, force a lively but not blinding saturation/brightness."""
    if c is None or not c.isValid(): return QColor(*theme.ACC)
    h, s, v, _ = c.getHsv()
    return QColor.fromHsv(max(0, h), max(110, min(235, s + 40)), max(150, min(235, v + 40)))


class Backdrop(QWidget):
    """Page base: OLED black with a soft cinematic glow. The glow colour follows the poster you're looking at (Apple-TV style) and eases between colours."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._tint = QColor(*theme.ACC); self._custom = False
        self._anim = QVariantAnimation(self); self._anim.setDuration(520); self._anim.setEasingCurve(QEasingCurve.InOutCubic)
        self._anim.valueChanged.connect(self._tick)

    def _tick(self, v):
        self._tint = QColor(v); self.update()

    def set_tint(self, color: QColor | None):
        """None = back to the accent colour."""
        target = normalise_tint(color) if color is not None else QColor(*theme.ACC); self._custom = color is not None
        if target.rgb() == self._tint.rgb(): return
        self._anim.stop(); self._anim.setStartValue(QColor(self._tint)); self._anim.setEndValue(target); self._anim.start()

    def paintEvent(self, e):
        p = QPainter(self); r = self.rect(); p.fillRect(r, QColor("#000000")); t = self._tint
        a1, a2 = (92, 36) if self._custom else (62, 22)
        g = QRadialGradient(QPointF(r.width() * 0.88, -r.height() * 0.12), r.width() * 0.85)
        g.setColorAt(0.0, QColor(int(t.red() * .75), int(t.green() * .75), int(t.blue() * .75), a1)); g.setColorAt(0.55, QColor(int(t.red() * .3), int(t.green() * .3), int(t.blue() * .3), a2)); g.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(r, g)
        h, s, v, _ = t.getHsv(); c2 = QColor.fromHsv((h + 40) % 360, max(60, s // 2), 120)
        g2 = QRadialGradient(QPointF(0, r.height() * 1.1), r.width() * 0.6)
        g2.setColorAt(0.0, QColor(c2.red(), c2.green(), c2.blue(), 44 if self._custom else 30)); g2.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(r, g2)
