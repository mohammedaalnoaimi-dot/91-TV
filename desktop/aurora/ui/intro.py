"""Start-up intro: plays the clip full screen on black, skippable with any key / click. Any failure just skips it."""
from __future__ import annotations
import logging
from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout

log = logging.getLogger(__name__)


class IntroWindow(QWidget):
    finished = Signal()

    def __init__(self, path: str):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
        from PySide6.QtMultimediaWidgets import QVideoWidget
        self._done = False
        self.setStyleSheet("background:#000;"); self.setCursor(Qt.BlankCursor)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        self.video = QVideoWidget(); self.video.setStyleSheet("background:#000;"); lay.addWidget(self.video)
        self.out = QAudioOutput(self); self.out.setVolume(0.9)
        self.mp = QMediaPlayer(self); self.mp.setAudioOutput(self.out); self.mp.setVideoOutput(self.video)
        self.mp.mediaStatusChanged.connect(lambda st: st == QMediaPlayer.EndOfMedia and self.finish())
        self.mp.errorOccurred.connect(lambda *_a: (log.warning("intro playback error: %s", self.mp.errorString()), self.finish()))
        self.mp.setSource(QUrl.fromLocalFile(path))
        QTimer.singleShot(13000, self.finish)          # safety net: never hold up start-up

    def play(self):
        self.showFullScreen(); self.activateWindow(); self.raise_(); self.mp.play()

    def finish(self):
        if self._done: return
        self._done = True
        try: self.mp.stop()
        except Exception: pass
        self.hide(); self.finished.emit()

    def keyPressEvent(self, e): self.finish()
    def mousePressEvent(self, e): self.finish()
