"""Game-controller input for living-room use. Windows XInput (Xbox/most modern pads) via ctypes, polled from a Qt timer.
Buttons are translated into the same key presses a keyboard/remote would send, so every screen works with a pad."""
from __future__ import annotations
import ctypes, logging, sys, time
from PySide6.QtCore import Qt, QTimer, QObject, QEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

log = logging.getLogger(__name__)

# XInput button bit masks
DPAD_UP, DPAD_DOWN, DPAD_LEFT, DPAD_RIGHT = 0x1, 0x2, 0x4, 0x8
START, BACK, LB, RB, A, B, X, Y = 0x10, 0x20, 0x100, 0x200, 0x1000, 0x2000, 0x4000, 0x8000
MAP = {DPAD_UP: Qt.Key_Up, DPAD_DOWN: Qt.Key_Down, DPAD_LEFT: Qt.Key_Left, DPAD_RIGHT: Qt.Key_Right,
       A: Qt.Key_Return, B: Qt.Key_Escape, X: Qt.Key_R, Y: Qt.Key_F, START: Qt.Key_Space, BACK: Qt.Key_Backspace,
       LB: Qt.Key_PageUp, RB: Qt.Key_PageDown}
REPEAT = {DPAD_UP, DPAD_DOWN, DPAD_LEFT, DPAD_RIGHT, LB, RB}
STICK_DEAD = 14000


class _State(ctypes.Structure):
    _fields_ = [("packet", ctypes.c_uint32), ("buttons", ctypes.c_uint16), ("lt", ctypes.c_ubyte), ("rt", ctypes.c_ubyte),
                ("lx", ctypes.c_short), ("ly", ctypes.c_short), ("rx", ctypes.c_short), ("ry", ctypes.c_short)]


def stick_to_buttons(lx: int, ly: int) -> int:
    m = 0
    if lx < -STICK_DEAD: m |= DPAD_LEFT
    if lx > STICK_DEAD: m |= DPAD_RIGHT
    if ly > STICK_DEAD: m |= DPAD_UP
    if ly < -STICK_DEAD: m |= DPAD_DOWN
    return m


class Gamepad(QObject):
    """poll() is separated from reading hardware so the mapping/repeat logic is unit-testable (pass `reader`)."""
    def __init__(self, parent=None, reader=None, send=None):
        super().__init__(parent); self.reader = reader or self._xinput_reader(); self.send = send or self._post
        self.down = 0; self.next_repeat: dict[int, float] = {}; self.connected = False
        self.timer = QTimer(self); self.timer.setInterval(33); self.timer.timeout.connect(self.poll)

    @staticmethod
    def _xinput_reader():
        if sys.platform != "win32": return None
        for dll in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
            try:
                lib = getattr(ctypes, "windll")[dll]
                def read(lib=lib):
                    for idx in range(4):
                        st = _State()
                        if lib.XInputGetState(idx, ctypes.byref(st)) == 0:
                            return st.buttons | stick_to_buttons(st.lx, st.ly)
                    return None
                return read
            except Exception:
                continue
        return None

    @property
    def available(self) -> bool: return self.reader is not None

    def start(self):
        if self.available: self.timer.start(); log.info("Gamepad polling started")

    def stop(self): self.timer.stop()

    def poll(self, now: float | None = None):
        now = time.time() if now is None else now
        cur = self.reader() if self.reader else None
        self.connected = cur is not None; cur = cur or 0
        for bit, key in MAP.items():
            on = bool(cur & bit); was = bool(self.down & bit)
            if on and not was:
                self.send(key); self.next_repeat[bit] = now + 0.45
            elif on and was and bit in REPEAT and now >= self.next_repeat.get(bit, 1e18):
                self.send(key); self.next_repeat[bit] = now + 0.12
        self.down = cur

    @staticmethod
    def _post(key):
        w = QApplication.focusWidget() or QApplication.activeWindow()
        if w is None: return
        for t in (QEvent.KeyPress, QEvent.KeyRelease):
            QApplication.postEvent(w, QKeyEvent(t, int(key), Qt.NoModifier))
