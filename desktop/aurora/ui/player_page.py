from __future__ import annotations
import logging, time
from PySide6.QtCore import Qt, Signal, QTimer, QPoint
from PySide6.QtGui import QCursor, QPixmap
from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QActionGroup
from ..thumbs import ThumbWorker, BUCKET
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QComboBox, QFrame, QPlainTextEdit)
from .. import player as pl
from .overlays import ControlsHost, Banner, NumberOSD, CenterOSD
from .glyphs import GlyphButton
from . import theme

log = logging.getLogger(__name__)


def _fmt(s):
    s = int(max(0, s)); h, r = divmod(s, 3600); m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class ScrubSlider(QSlider):
    """Seek bar that reports hover position (for time/thumbnail preview) and jumps where you click."""
    hovered = Signal(float, QPoint)      # fraction 0..1, global pos
    left = Signal()

    def __init__(self):
        super().__init__(Qt.Horizontal); self.setMouseTracking(True)

    def _frac(self, x): return max(0.0, min(1.0, x / max(1, self.width())))

    def mouseMoveEvent(self, e):
        self.hovered.emit(self._frac(e.position().x()), e.globalPosition().toPoint()); super().mouseMoveEvent(e)

    def leaveEvent(self, e): self.left.emit(); super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.setValue(int(self._frac(e.position().x()) * self.maximum())); self.sliderPressed.emit()
        super().mousePressEvent(e)


class PlayerPage(QWidget):
    profile_changed = Signal(dict)
    back = Signal()
    fullscreen = Signal()
    prev_next = Signal(int)
    failed = Signal(str)
    position_changed = Signal(float)

    def __init__(self, get_settings):
        super().__init__()
        self.get_settings = get_settings; self.player: pl.Player | None = None; self._tracks_sig = None; self._seeking = False
        self._full = False; self._last_mouse = (0, 0); self._last_move = time.time()
        self.setObjectName("playerpage"); self.setAttribute(Qt.WA_StyledBackground); self.setStyleSheet("QWidget#playerpage { background: #000; }")
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)
        self.top = QFrame(); self.top.setObjectName("controls"); self.top.setProperty("edge", "top"); t = QHBoxLayout(self.top); t.setContentsMargins(22, 14, 22, 26); t.setSpacing(12)
        self.b_back = GlyphButton("back", 46); self.b_back.setToolTip("Back (Esc)"); self.title = QLabel(""); self.title.setObjectName("ptitle"); self.status = QLabel(""); self.status.setStyleSheet(theme.acc("color:#e0262d; font-weight:700;"))
        self.b_pic = QPushButton("Picture"); self.b_pic.setToolTip("Picture options for this channel (remembered): motion, denoise, deband, deinterlace")
        self.b_info = QPushButton("Info"); self.b_info.setCheckable(True); self.b_reload = QPushButton("↻  Reload"); self.b_reload.setToolTip("Reload the stream (R). Press twice to try a backup source.")
        for _b in (self.b_pic, self.b_info, self.b_reload): _b.setObjectName("ptext")
        t.addWidget(self.b_back); t.addWidget(self.title, 1); t.addWidget(self.status); t.addWidget(self.b_reload); t.addWidget(self.b_pic); t.addWidget(self.b_info); lay.addWidget(self.top)
        self.b_pic.clicked.connect(self.picture_menu); self.profile: dict = {}; self.thumbs: ThumbWorker | None = None; self._thumb_url = ""
        self.b_reload.clicked.connect(self.reload)
        mid = QHBoxLayout(); mid.setSpacing(0)
        self.video = QWidget(); self.video.setAttribute(Qt.WA_NativeWindow); self.video.setAttribute(Qt.WA_OpaquePaintEvent)
        self.video.setStyleSheet("background:#000;"); mid.addWidget(self.video, 1)
        self.info = QPlainTextEdit(); self.info.setReadOnly(True); self.info.setFixedWidth(360); self.info.hide()
        self.info.setStyleSheet("background:#0b0b0d; border:none; border-left:1px solid #1b1b20; padding:14px; font-family:Consolas,monospace; font-size:13px;")
        mid.addWidget(self.info); lay.addLayout(mid, 1)
        self.bar = QFrame(); self.bar.setObjectName("controls"); self.bar.setProperty("edge", "bottom"); bv = QVBoxLayout(self.bar); bv.setContentsMargins(28, 34, 28, 14); bv.setSpacing(4)
        srow = QHBoxLayout(); srow.setSpacing(14); c = QHBoxLayout(); c.setSpacing(6)
        self.b_prev = GlyphButton("prev", 42); self.b_play = GlyphButton("pause", 58); self.b_next = GlyphButton("next", 42)
        self.b_b10 = GlyphButton("back10", 48); self.b_f10 = GlyphButton("fwd10", 48); self.b_live = QPushButton("● LIVE")
        self.b_b10.setToolTip("Back 10 seconds (Left)"); self.b_f10.setToolTip("Forward 10 seconds (Right)"); self.b_live.setToolTip("Behind live - click to jump back to the live edge")
        self.b_live.setObjectName("icon")
        self.b_live.setStyleSheet(theme.acc("color:#e0262d; font-weight:800; font-size:12px; min-width:70px;")); self.b_live.hide()
        self.seek = ScrubSlider(); self.seek.setRange(0, 1000); self.time = QLabel("0:00")
        self.audio = QComboBox(); self.audio.setMinimumWidth(190); self.audio.setToolTip("Audio track")
        self.subs = QComboBox(); self.subs.setMinimumWidth(170); self.subs.setToolTip("Subtitles")
        self.vol = QSlider(Qt.Horizontal); self.vol.setRange(0, 150); self.vol.setValue(100); self.vol.setFixedWidth(100)
        self.b_full = GlyphButton("full", 46); self.b_full.setToolTip("Full screen (F)")
        self.seek.setFixedHeight(22); self.time.setObjectName("ptime"); srow.addWidget(self.seek, 1); srow.addWidget(self.time); bv.addLayout(srow)
        self.b_vol = GlyphButton("vol", 40); self.b_vol.clicked.connect(lambda: self.vol.setValue(0 if self.vol.value() else 100))
        for w in (self.b_play, self.b_b10, self.b_f10, self.b_vol, self.vol): c.addWidget(w)
        c.addSpacing(14); c.addWidget(self.b_live); c.addStretch(1)
        for w in (self.b_prev, self.b_next, self.audio, self.subs, self.b_full): c.addWidget(w)
        bv.addLayout(c); lay.addWidget(self.bar)
        self.b_back.clicked.connect(self.back); self.b_full.clicked.connect(self.fullscreen)
        self.b_prev.clicked.connect(lambda: self.prev_next.emit(-1)); self.b_next.clicked.connect(lambda: self.prev_next.emit(1))
        self.b_play.clicked.connect(self.toggle_pause); self.b_b10.clicked.connect(lambda: self.skip(-10)); self.b_f10.clicked.connect(lambda: self.skip(10)); self.b_live.clicked.connect(self.go_live)
        self.lay = lay
        self.top_win = ControlsHost(self, "top"); self.bar_win = ControlsHost(self, "bottom"); self.banner = Banner(self); self.osd = NumberOSD(self); self.center = CenterOSD(self)
        self.top_win.hide(); self.bar_win.hide()
        self.tip = QLabel(); self.tip.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus); self.tip.setAttribute(Qt.WA_ShowWithoutActivating)
        self.tip.setAlignment(Qt.AlignCenter); self.tip.setStyleSheet("background:#0a0a0d; color:#f2f2f4; border:1px solid #2a2a31; border-radius:10px; padding:6px; font-weight:700;")
        self.seek.hovered.connect(self._scrub_hover); self.seek.left.connect(self.tip.hide)
        self.b_info.toggled.connect(self.info.setVisible)
        self.seek.sliderPressed.connect(lambda: setattr(self, "_seeking", True)); self.seek.sliderReleased.connect(self._seek_release)
        self.vol.valueChanged.connect(lambda v: self.player and self.player.set_volume(v))
        self.audio.activated.connect(lambda _i: self.player and self.player.set_track("audio", self.audio.currentData()))
        self.subs.activated.connect(lambda _i: self.player and self.player.set_track("sub", self.subs.currentData()))
        self.timer = QTimer(self); self.timer.setInterval(500); self.timer.timeout.connect(self._update)
        self.tick = QTimer(self); self.tick.setInterval(1000); self.tick.timeout.connect(self._tick)
        self.hide_timer = QTimer(self); self.hide_timer.setInterval(200); self.hide_timer.timeout.connect(self._autohide)

    # lifecycle
    def ensure_player(self) -> bool:
        if self.player:
            return True
        self.video.winId()
        s = {k: self.get_settings(k) for k in ("hwdec", "hdr", "upscale", "quality", "denoise", "deinterlace", "hdr_enhance", "motion", "tone_mapping", "display_peak", "timeshift", "volume", "audio_device", "pass_ac3", "pass_eac3", "pass_dts", "pass_hd", "audio_exclusive", "max_reconnects")}
        try:
            self.player = pl.Player(int(self.video.winId()), s)
        except Exception as e:
            log.exception("Player init failed")
            self.failed.emit(str(e)); return False
        a, sl = self.get_settings("audio_lang"), self.get_settings("sub_lang")
        try:
            if a: self.player.m.alang = a
            if sl: self.player.m.slang = sl
        except Exception:
            pass
        self.timer.start(); self.tick.start(); self.hide_timer.start()
        return True

    def reset_player(self):
        if self.player:
            self.timer.stop(); self.tick.stop(); self.player.shutdown(); self.player = None

    def open(self, title, url, live, start=0.0, alternates=None, profile=None):
        if not self.ensure_player():
            return False
        self.profile = dict(profile or {}); self.player.apply_picture(self.profile); self._thumbs_for(url, live)
        self.title.setText(title); self.status.setText(""); self._tracks_sig = None
        self.seek.setVisible(not live); self.time.setVisible(not live)
        self.audio.clear(); self.subs.clear()
        self.player.play(url, live, start, alternates); self.b_play.setText("⏸")
        return True

    def reload(self):
        if self.player and self.player.current_url:
            self.player.reload(); n = len(self.player.sources)
            self.status.setText(f"Reloading…" + (f" (source {self.player.source_index + 1}/{n})" if n > 1 else ""))

    def _thumbs_for(self, url, live):
        """Scrub thumbnails need a second connection to the provider, so they are opt-in and VOD-only."""
        if self.thumbs and self._thumb_url != url: self.thumbs.close(); self.thumbs = None
        if not live and self.get_settings("scrub_thumbs") and self.thumbs is None:
            self.thumbs = ThumbWorker(url); self._thumb_url = url; self.thumbs.ready.connect(self._thumb_ready)
        self.tip.hide()

    def _scrub_hover(self, frac, gpos):
        if not self.player or self.player.is_live: return
        dur = self.player.position()[1]
        if dur <= 0: return
        self._tip_t = frac * dur; self._tip_pos = gpos
        txt = _fmt(self._tip_t)
        if self.thumbs and not self.thumbs.failed:
            b = int(self._tip_t // BUCKET); img = self.thumbs.cache.get(b)
            self.thumbs.request(self._tip_t)
            if img is not None: self.tip.setPixmap(QPixmap.fromImage(img)); self.tip.setText("") if False else None; self._tip_txt = txt; self._place_tip(img.height() + 40, txt, img); return
        self.tip.setPixmap(QPixmap()); self.tip.setText(txt); self.tip.adjustSize(); self.tip.move(gpos.x() - self.tip.width() // 2, gpos.y() - self.tip.height() - 14); self.tip.show()

    def _place_tip(self, h, txt, img):
        pm = QPixmap.fromImage(img); from PySide6.QtGui import QPainter, QColor, QFont
        pm2 = QPixmap(pm.width(), pm.height() + 26); pm2.fill(QColor("#0a0a0d")); p = QPainter(pm2); p.drawPixmap(0, 0, pm); p.setPen(QColor("#f2f2f4")); f = QFont(); f.setBold(True); f.setPixelSize(13); p.setFont(f)
        p.drawText(0, pm.height(), pm.width(), 26, Qt.AlignCenter, txt); p.end(); self.tip.setPixmap(pm2); self.tip.adjustSize()
        g = getattr(self, "_tip_pos", QCursor.pos()); self.tip.move(g.x() - self.tip.width() // 2, g.y() - self.tip.height() - 14); self.tip.show()

    def _thumb_ready(self, b, img):
        if self.tip.isVisible() and int(getattr(self, "_tip_t", -1) // BUCKET) == b: self._place_tip(0, _fmt(self._tip_t), img)

    # ---- per-channel picture options
    def picture_menu(self):
        if not self.player: return
        pic = self.player.pic; m = QMenu(self)
        a_m = m.addAction("Smooth motion (interpolation)"); a_m.setCheckable(True); a_m.setChecked(pic.get("motion") == "smooth")
        a_b = m.addAction("Deband (smooth gradients)"); a_b.setCheckable(True); a_b.setChecked(pic.get("deband") == "on")
        dn = m.addMenu("Noise reduction (≤1080p, uses CPU)"); dg = QActionGroup(dn); dacts = {}
        for key, label in (("off", "Off"), ("light", "Light"), ("medium", "Medium")):
            a = dn.addAction(label); a.setCheckable(True); a.setChecked(pic.get("denoise") == key); dg.addAction(a); dacts[a] = key
        di = m.addMenu("Deinterlace"); ig = QActionGroup(di); iacts = {}
        for key, label in (("auto", "Auto"), ("on", "Always on"), ("off", "Off")):
            a = di.addAction(label); a.setCheckable(True); a.setChecked(pic.get("deinterlace") == key); ig.addAction(a); iacts[a] = key
        m.addSeparator(); a_r = m.addAction("Reset this channel to defaults")
        act = m.exec(self.b_pic.mapToGlobal(QPoint(0, self.b_pic.height())))
        if act is None: return
        p = dict(self.profile)
        if act is a_m: p["motion"] = "smooth" if a_m.isChecked() else "off"
        elif act is a_b: p["deband"] = "on" if a_b.isChecked() else "off"
        elif act in dacts: p["denoise"] = dacts[act]
        elif act in iacts: p["deinterlace"] = iacts[act]
        elif act is a_r: p = {}
        self.profile = p; self.player.apply_picture(p); self.profile_changed.emit(p)
        self.status.setText("Picture settings saved for this channel" if p else "Picture reset"); QTimer.singleShot(2500, lambda: self.status.text().startswith("Picture") and self.status.setText(""))

    def stop(self):
        if self.player:
            p, self.last_dur = self.player.position()
            if not self.player.is_live and p > 5:
                self.position_changed.emit(p)
            self.player.stop()

    def toggle_pause(self):
        if self.player:
            self.player.toggle_pause(); paused = bool(self.player.m.pause); self.b_play.setText("▶" if paused else "⏸"); self.center.flash("play" if paused else "pause", self.video_rect())

    def skip(self, secs):
        """Back/forward by secs. Works on VOD and, with the rewind buffer, on live streams."""
        if self.player: self.player.seek(secs)

    def go_live(self):
        if self.player: self.player.go_live()

    def video_rect(self):
        tl = self.video.mapToGlobal(self.video.rect().topLeft()); r = self.video.rect(); r.moveTopLeft(tl); return r

    def _fs_style(self, on):
        for w in (self.top, self.bar):
            w.setProperty("fs", on); w.style().unpolish(w); w.style().polish(w)
            for c in w.findChildren(QWidget): c.style().unpolish(c); c.style().polish(c)

    def set_fullscreen(self, on):
        """Full screen: the control bars float over the video (no re-layout, so the picture never resizes) and fade away."""
        self._full = on; self._fs_style(on)
        if on:
            self.info.hide()
            for w, host in ((self.top, self.top_win), (self.bar, self.bar_win)):
                self.lay.removeWidget(w); host.host(w); w.show()
            self._place_overlays(); self.top_win.hide_now(); self.bar_win.hide_now()
        else:
            for w, host in ((self.top, self.top_win), (self.bar, self.bar_win)):
                host.lay.removeWidget(w); host.hide_now()
            self.lay.insertWidget(0, self.top); self.lay.addWidget(self.bar); self.top.show(); self.bar.show()
            self.banner.hide_now(); self.osd.hide_now(); self.center.hide_now()

    def _place_overlays(self):
        v = self.video_rect()
        for h in (self.top_win, self.bar_win): h.place(v)

    def show_banner(self, number, name, now, nxt):
        """Channel banner (full screen) / now-next in the title (windowed)."""
        if self._full: self.banner.show_channel(number, name, now, nxt, self.video_rect())
        self.title.setText((f"{number}  ·  " if number else "") + name + (f"   —   {now.title}" if now else ""))

    def show_entry(self, digits, hint):
        self.osd.show_entry(digits, hint, self.video_rect())

    def hide_entry(self): self.osd.fade_out()

    # periodic
    def _seek_release(self):
        self._seeking = False
        if self.player:
            d = self.player.position()[1]
            if d: self.player.seek(self.seek.value() / 1000 * d, absolute=True)

    def _autohide(self):
        if not self._full: return
        pos = QCursor.pos(); now = time.time()
        over = self.top_win.isVisible() and (self.top_win.geometry().contains(pos) or self.bar_win.geometry().contains(pos))
        if (pos.x(), pos.y()) != self._last_mouse:
            self._last_mouse = (pos.x(), pos.y()); self._last_move = now
            if self.video_rect().contains(pos) or over:
                self._place_overlays(); self.top_win.pop(); self.bar_win.pop()
        elif now - self._last_move > 3 and self.top_win.isVisible() and not over and not self.audio.view().isVisible() and not self.subs.view().isVisible():
            self.top_win.fade_out(); self.bar_win.fade_out()

    def _tick(self):
        if not self.player:
            return
        r = self.player.tick()
        if r == "reconnect":
            self.status.setText(f"Stream stalled - reloading… ({self.player.retries}/{self.player.settings.get('max_reconnects')})")
        elif r == "switched":
            self.status.setText(f"Trying backup source {self.player.source_index + 1}/{len(self.player.sources)}… ({self.player.retries}/{self.player.settings.get('max_reconnects')})")
        elif r == "failed":
            self.status.setText("Playback failed"); self.failed.emit("The stream stopped and could not be reconnected. See the log for details.")
        elif r == "ended":
            self.status.setText("Finished")
        elif self.status.text().startswith(("Stream stalled", "Trying backup", "Reloading")) and self.player.position()[0] > 3:
            self.status.setText("")

    def _update(self):
        p = self.player
        if not p:
            return
        pos, dur = p.position()
        if p.is_live:
            behind = p.behind_live(); self.b_live.setVisible(True)
            self.b_live.setText("● LIVE" if behind < 3 else f"−{int(behind)}s  ▶ LIVE"); self.b_live.setStyleSheet(theme.acc(("color:#e0262d;" if behind < 3 else "color:#f2f2f4; background:#8f1a1f;") + " font-weight:800; font-size:12px; min-width:70px;"))
        else:
            self.b_live.setVisible(False)
        if not p.is_live and dur > 0:
            self.time.setText(f"{_fmt(pos)} / {_fmt(dur)}")
            if not self._seeking: self.seek.setValue(int(pos / dur * 1000))
        tr = p.tracks(); sig = tuple((t.get("type"), t.get("id"), t.get("selected")) for t in tr)
        if sig != self._tracks_sig:
            self._tracks_sig = sig; self.audio.clear(); self.subs.clear(); self.subs.addItem("Subtitles: off", "no")
            for t in tr:
                lang = t.get("lang") or "und"; desc = f"{lang.upper()}  {t.get('codec', '')}"
                if t.get("demux-channel-count"): desc += f" {t['demux-channel-count']}ch"
                if t.get("title"): desc += f"  {t['title']}"
                if "atmos" in (t.get("codec-profile") or "").lower(): desc += "  Atmos"
                if t.get("type") == "audio": self.audio.addItem(desc, t["id"]); self.audio.setCurrentIndex(self.audio.count() - 1) if t.get("selected") else None
                elif t.get("type") == "sub":
                    self.subs.addItem(desc, t["id"])
                    if t.get("selected"): self.subs.setCurrentIndex(self.subs.count() - 1)
        if self.info.isVisible():
            self.info.setPlainText(pl.format_info(p.info()))
