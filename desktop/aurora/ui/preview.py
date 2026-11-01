"""Embedded live preview pane: its own lightweight libmpv instance inside the Live TV page."""
from __future__ import annotations
import logging
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPainterPath, QRegion
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QStackedLayout, QSizePolicy
from .. import player as pl
from ..models import Item

log = logging.getLogger(__name__)
RADIUS = 14


class VideoSurface(QWidget):
    """Native child window that libmpv renders into; masked to rounded corners."""
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_NativeWindow); self.setAttribute(Qt.WA_OpaquePaintEvent); self.setStyleSheet("background:#000;")

    def resizeEvent(self, e):
        try:
            path = QPainterPath(); path.addRoundedRect(self.rect(), RADIUS, RADIUS)
            self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        except Exception:
            pass
        super().resizeEvent(e)


class AspectBox(QWidget):
    """Always 16:9 for the width it is given (explicit height; nested layouts do not propagate heightForWidth)."""
    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed); self.setFixedHeight(270)

    def resizeEvent(self, e):
        h = max(120, int(self.width() * 9 / 16))
        if self.height() != h:
            self.setFixedHeight(h)
        super().resizeEvent(e)


class PreviewPane(QFrame):
    state = Signal(str)       # idle | loading | playing | failed | unavailable | off

    def __init__(self, store):
        super().__init__()
        self.store = store; self.player: pl.Player | None = None; self.item: Item | None = None
        self.alternates = lambda item: []; self.muted = bool(store.get("preview_muted")); self.dead = False; self.pending: Item | None = None; self.status = "idle"; self.force = False
        self.setObjectName("previewFrame"); self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.setStyleSheet("QFrame#previewFrame { background:#000; border:1px solid #2a2a31; border-radius:%dpx; }" % (RADIUS + 3))
        lay = QVBoxLayout(self); lay.setContentsMargins(3, 3, 3, 3)
        self.box = AspectBox(); bl = QVBoxLayout(self.box); bl.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedLayout(); bl.addLayout(self.stack)
        self.video = VideoSurface()
        self.msg = QLabel(""); self.msg.setAlignment(Qt.AlignCenter); self.msg.setWordWrap(True)
        self.msg.setStyleSheet("color:#8d8d96; font-size:15px; background:#07070a; border-radius:%dpx; padding:20px;" % RADIUS)
        self.stack.addWidget(self.msg); self.stack.addWidget(self.video); lay.addWidget(self.box)
        self.set_message("Select a channel to preview")
        self.deb = QTimer(self); self.deb.setSingleShot(True); self.deb.setInterval(450); self.deb.timeout.connect(self._start)
        self.tick = QTimer(self); self.tick.setInterval(1000); self.tick.timeout.connect(self._tick)

    def _set_status(self, s):
        self.status = s; self.state.emit(s)

    def set_message(self, text):
        self.msg.setText(text); self.stack.setCurrentWidget(self.msg)

    def request(self, item: Item | None):
        """Debounced: holding an arrow key through the list only starts the channel you stop on."""
        self.pending = item
        if item is None:
            self.stop(); return
        if not self.force and not self.store.get("preview_enabled"):
            self.stop(); self.set_message("Preview is turned off (Settings → Live preview).\nDouble-click a channel to watch it.")
            self._set_status("off"); return
        if self.dead:
            return
        self.set_message(f"Connecting to {item.name}…"); self._set_status("loading"); self.deb.start()

    def _ensure(self) -> bool:
        if self.player:
            return True
        self.video.winId()
        s = {"hwdec": self.store.get("hwdec"), "hdr": "off", "volume": self.store.get("preview_volume"), "audio_device": self.store.get("audio_device"),
             "pass_ac3": False, "pass_eac3": False, "pass_dts": False, "pass_hd": False, "audio_exclusive": False,
             "max_reconnects": 3, "lite": True, "mute": self.muted}
        try:
            self.player = pl.Player(int(self.video.winId()), s); self.tick.start(); return True
        except Exception as e:
            log.exception("Preview player init failed"); self.dead = True
            self.set_message("Preview unavailable: the video engine could not be loaded.\nYou can still open channels full screen.\n\n" + str(e)[:140])
            self._set_status("unavailable"); return False

    def _start(self):
        it = self.pending
        if not it or not it.url or not self._ensure():
            return
        self.item = it; self.stack.setCurrentWidget(self.video)
        self.player.play(it.url, True, 0.0, self.alternates(it)); self.player.set_mute(self.muted); self._set_status("playing")

    def stop(self):
        self.deb.stop(); self.item = None
        if self.player:
            self.player.stop()
        if self.stack.currentWidget() is self.video:
            self.set_message("Select a channel to preview")
        if self.status != "off":
            self._set_status("idle")

    def release(self):
        """Free the decoder entirely (full-screen player takes over, or settings changed)."""
        self.stop()
        if self.player:
            self.tick.stop(); self.player.shutdown(); self.player = None

    def reset(self):
        self.release(); self.dead = False

    def reload(self):
        """Manual refresh of the previewed channel (second press within 10 s tries a backup source)."""
        if self.player and self.item:
            self.player.reload(); self.player.set_mute(self.muted); self.stack.setCurrentWidget(self.video)
        elif self.pending:
            self.request(self.pending)

    def set_muted(self, on: bool):
        self.muted = on; self.store.set("preview_muted", on)
        if self.player:
            self.player.set_mute(on)

    def _tick(self):
        if not self.player:
            return
        r = self.player.tick()
        if r == "reconnect":
            self.set_message("Stream stalled - refreshing…"); self._set_status("loading")
        elif r == "switched":
            self.set_message(f"Trying backup source {self.player.source_index + 1}/{len(self.player.sources)}…"); self._set_status("loading")
        elif r == "failed":
            self.set_message("This channel did not respond (all sources tried).\nPress Reload, or pick another channel."); self._set_status("failed")
        elif self.stack.currentWidget() is self.msg and self.status in ("playing", "loading") and self.player.position()[0] > 1:
            self.stack.setCurrentWidget(self.video); self._set_status("playing")
