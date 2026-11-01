"""First-run setup wizard: playlist -> audio/video -> optional extras -> self-check. Applies nothing itself; MainWindow reads `.result`."""
from __future__ import annotations
import logging
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton, QStackedWidget, QComboBox, QLineEdit, QWidget, QPlainTextEdit, QCheckBox)
from .dialogs import PlaylistDialog
from .. import player as pl, secrets

log = logging.getLogger(__name__)


def play_test_tone(device: str):
    """Plays a 2-second 440 Hz tone on `device` through libmpv. Returns '' on success or an error text."""
    mpv = pl.load_mpv()
    if mpv is None: return f"libmpv not available: {pl.mpv_error()}"
    try:
        m = mpv.MPV(vo="null", video="no", audio_device=device or "auto", volume="60", ytdl="no", idle="yes")
        m.play("av://lavfi:sine=frequency=440:duration=2")
        QTimer.singleShot(3500, lambda: (m.terminate() if m else None))
        return ""
    except Exception as e:
        return str(e)


def audio_devices() -> list[tuple[str, str]]:
    mpv = pl.load_mpv()
    if mpv is None: return [("auto", "System default")]
    try:
        m = mpv.MPV(vo="null", video="no", ytdl="no"); devs = [(d["name"], d.get("description", d["name"])) for d in m.audio_device_list]; m.terminate(); return devs
    except Exception:
        return [("auto", "System default")]


class SetupWizard(QDialog):
    def __init__(self, store, check_playlist, parent=None):
        super().__init__(parent); self.store, self.check_playlist = store, check_playlist
        self.setWindowTitle("91 TV setup"); self.resize(680, 560); self.result: dict = {}; self.playlist = None
        lay = QVBoxLayout(self); lay.setContentsMargins(28, 24, 28, 20); self.step_lbl = QLabel(""); self.step_lbl.setObjectName("eyebrow"); lay.addWidget(self.step_lbl)
        self.stack = QStackedWidget(); lay.addWidget(self.stack, 1)
        # 1 welcome
        w = QWidget(); l = QVBoxLayout(w); h = QLabel("Welcome to 91 TV"); h.setObjectName("display"); l.addWidget(h)
        t = QLabel("This takes about a minute: add your playlist, choose your sound output, and run a quick self-check.\n\n91 TV does not include any channels or content - you bring your own playlist from a provider you are subscribed to.")
        t.setWordWrap(True); t.setObjectName("muted"); l.addWidget(t); l.addStretch(); self.stack.addWidget(w)
        # 2 playlist
        w = QWidget(); l = QVBoxLayout(w); h = QLabel("Your playlist"); h.setObjectName("h1"); l.addWidget(h)
        t = QLabel("Add an M3U/M3U8 link or file, or your Xtream Codes login. Credentials are kept in Windows Credential Manager."); t.setWordWrap(True); t.setObjectName("muted"); l.addWidget(t)
        row = QHBoxLayout(); self.b_pl = QPushButton("Add playlist…"); self.b_pl.setObjectName("primary"); row.addWidget(self.b_pl); row.addStretch(); l.addLayout(row)
        self.pl_state = QLabel("No playlist added yet (you can skip this and add one later in Settings)."); self.pl_state.setObjectName("muted"); self.pl_state.setWordWrap(True); l.addWidget(self.pl_state); l.addStretch(); self.stack.addWidget(w)
        # 3 audio / video
        w = QWidget(); l = QVBoxLayout(w); h = QLabel("Sound & picture"); h.setObjectName("h1"); l.addWidget(h)
        f = QFormLayout(); self.dev = QComboBox(); self.dev.addItem("System default", "auto")
        for n, d in audio_devices():
            if n != "auto": self.dev.addItem(d, n)
        self.b_tone = QPushButton("Play test tone"); r = QHBoxLayout(); r.addWidget(self.dev, 1); r.addWidget(self.b_tone); f.addRow("Audio output", r)
        self.hwdec = QComboBox()
        for label, v in (("Automatic (recommended)", "auto-safe"), ("NVIDIA NVDEC (direct)", "nvdec"), ("Direct3D 11", "d3d11va"), ("Software only", "no")): self.hwdec.addItem(label, v)
        self.hdr = QComboBox(); self.hdr.addItem("Auto - signal HDR10 when content is HDR", "auto"); self.hdr.addItem("Off - always SDR", "off")
        f.addRow("Hardware decoding", self.hwdec); f.addRow("HDR", self.hdr); l.addLayout(f)
        self.tone_state = QLabel(""); self.tone_state.setObjectName("muted"); self.tone_state.setWordWrap(True); l.addWidget(self.tone_state)
        n = QLabel("Surround passthrough (Dolby/DTS bitstream) stays OFF by default: only turn it on in Settings if your receiver/HDMI device supports it. USB DACs and stereo speakers need it off."); n.setWordWrap(True); n.setObjectName("muted"); l.addWidget(n)
        l.addStretch(); self.stack.addWidget(w)
        # 4 extras
        w = QWidget(); l = QVBoxLayout(w); h = QLabel("Optional extras"); h.setObjectName("h1"); l.addWidget(h)
        f = QFormLayout(); self.tmdb = QLineEdit(); self.tmdb.setEchoMode(QLineEdit.Password); self.tmdb.setPlaceholderText("Free TMDB key for posters, plots & cast (optional)")
        self.pin = QLineEdit(); self.pin.setEchoMode(QLineEdit.Password); self.pin.setPlaceholderText("4+ digit parental PIN (optional)"); self.pin.setMaxLength(12)
        self.adult = QCheckBox("Hide categories that look adult (needs PIN to reveal)"); f.addRow("TMDB key", self.tmdb); f.addRow("Parental PIN", self.pin); l.addLayout(f); l.addWidget(self.adult)
        l.addStretch(); self.stack.addWidget(w)
        # 5 check
        w = QWidget(); l = QVBoxLayout(w); h = QLabel("Self-check"); h.setObjectName("h1"); l.addWidget(h)
        self.report = QPlainTextEdit(); self.report.setReadOnly(True); l.addWidget(self.report, 1); self.stack.addWidget(w)
        # nav
        nav = QHBoxLayout(); self.b_back = QPushButton("Back"); self.b_next = QPushButton("Next"); self.b_next.setObjectName("primary"); self.b_skip = QPushButton("Skip setup")
        nav.addWidget(self.b_skip); nav.addStretch(); nav.addWidget(self.b_back); nav.addWidget(self.b_next); lay.addLayout(nav)
        self.b_back.clicked.connect(lambda: self._go(self.stack.currentIndex() - 1)); self.b_next.clicked.connect(self._next); self.b_skip.clicked.connect(self.reject)
        self.b_pl.clicked.connect(self._add_pl); self.b_tone.clicked.connect(self._tone)
        self.dev.setCurrentIndex(max(0, self.dev.findData(store.get("audio_device")))); self.hwdec.setCurrentIndex(max(0, self.hwdec.findData(store.get("hwdec")))); self._go(0)

    def _go(self, i):
        i = max(0, min(self.stack.count() - 1, i)); self.stack.setCurrentIndex(i); n = self.stack.count()
        self.step_lbl.setText(f"STEP {i + 1} OF {n}"); self.b_back.setEnabled(i > 0); self.b_next.setText("Finish" if i == n - 1 else "Next")
        if i == n - 1: self._run_checks()

    def _next(self):
        if self.stack.currentIndex() == self.stack.count() - 1: self._finish()
        else: self._go(self.stack.currentIndex() + 1)

    def _add_pl(self):
        d = PlaylistDialog(self)
        if d.exec() and d.result_data:
            self.playlist = d.result_data; self.pl_state.setText(f"Added: {self.playlist['name']} ({self.playlist['type'].upper()}). It will be checked on the last step.")

    def _tone(self):
        err = play_test_tone(self.dev.currentData() or "auto")
        self.tone_state.setText("Playing a 2-second tone… if you hear nothing, pick another output device." if not err else f"Could not play the tone: {err}")

    def _run_checks(self):
        lines = []
        m = pl.load_mpv(); lines.append(("OK" if m else "FAIL") + "  Video engine (libmpv): " + ("loaded" if m else str(pl.mpv_error())))
        lines.append(("OK" if secrets.available() else "WARN") + "  Credential store: " + (secrets.backend() if secrets.available() else "unavailable - secrets are kept in the local database instead"))
        lines.append(f"OK  Audio output: {self.dev.currentText()}")
        lines.append(f"OK  Hardware decoding setting: {self.hwdec.currentText()} (actual decoder is shown in the player's Info panel during playback)")
        self.report.setPlainText("\n".join(lines)); self.b_next.setEnabled(False)
        if self.playlist:
            self.report.appendPlainText("…  Checking your playlist (this can take a moment)")
            self.check_playlist(self.playlist, self._checked)
        else:
            self.report.appendPlainText("--  No playlist added (skipped)"); self.b_next.setEnabled(True)

    def _checked(self, ok: bool, text: str):
        self.report.appendPlainText(("OK  " if ok else "FAIL  ") + text); self.b_next.setEnabled(True)

    def _finish(self):
        self.result = dict(playlist=self.playlist, audio_device=self.dev.currentData() or "auto", hwdec=self.hwdec.currentData(), hdr=self.hdr.currentData(),
                           tmdb=self.tmdb.text().strip(), pin=self.pin.text().strip(), hide_adult=self.adult.isChecked())
        self.accept()
