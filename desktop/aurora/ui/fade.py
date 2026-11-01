"""Page stack with a quick cross-fade (new page fades in from black). Disabled when animations are off."""
from PySide6.QtCore import Qt, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QStackedWidget, QWidget


class _Veil(QWidget):
    def __init__(self, parent):
        super().__init__(parent); self.alpha = 0; self.setAttribute(Qt.WA_TransparentForMouseEvents); self.hide()

    def paintEvent(self, e):
        p = QPainter(self); p.fillRect(self.rect(), QColor(0, 0, 0, self.alpha))


class FadeStack(QStackedWidget):
    enabled = True

    def __init__(self, parent=None):
        super().__init__(parent)
        self.veil = _Veil(self); self.anim = QVariantAnimation(self); self.anim.setDuration(230); self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.valueChanged.connect(self._tick); self.anim.finished.connect(self.veil.hide)

    def _tick(self, v):
        self.veil.alpha = int(v); self.veil.update()

    def setCurrentIndex(self, i):
        if i == self.currentIndex():
            return
        super().setCurrentIndex(i)
        if self.enabled and self.isVisible():
            self.veil.setGeometry(self.rect()); self.veil.alpha = 235; self.veil.show(); self.veil.raise_()
            self.anim.stop(); self.anim.setStartValue(235); self.anim.setEndValue(0); self.anim.start()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.veil.isVisible(): self.veil.setGeometry(self.rect())
