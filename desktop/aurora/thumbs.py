"""Scrub-bar preview thumbnails for movies/episodes. Uses a SECOND libmpv instance (video output off) that opens the same URL and
grabs frames on demand. That is a second connection to your provider, so it is OFF by default (Settings -> Scrub thumbnails)."""
from __future__ import annotations
import logging, queue, threading, time
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage
from . import player as pl

log = logging.getLogger(__name__)
BUCKET = 10          # seconds per cached thumbnail


class ThumbWorker(QObject):
    ready = Signal(int, object)         # bucket, QImage

    def __init__(self, url: str):
        super().__init__(); self.url = url; self.q: queue.Queue = queue.Queue(); self.cache: dict[int, QImage] = {}; self.stop_flag = False; self.failed = False
        self.t = threading.Thread(target=self._run, daemon=True); self.t.start()

    def request(self, seconds: float):
        b = int(seconds // BUCKET)
        if b in self.cache: self.ready.emit(b, self.cache[b]); return
        while not self.q.empty():
            try: self.q.get_nowait()
            except queue.Empty: break
        self.q.put(b)

    def close(self):
        self.stop_flag = True; self.q.put(None)

    def _run(self):
        mpv = pl.load_mpv()
        if mpv is None: self.failed = True; return
        try:
            m = mpv.MPV(vo="null", ao="null", audio="no", sub="no", pause="yes", hwdec="no", ytdl="no", idle="yes", cache="yes", demuxer_max_bytes="24MiB",
                        network_timeout="8", user_agent="VLC/3.0.20 LibVLC/3.0.20", hr_seek="no", vd_lavc_skiploopfilter="all", vd_lavc_fast="yes", loglevel="fatal")
            m.play(self.url); t0 = time.time()
            while not self.stop_flag and time.time() - t0 < 15:
                if (m.duration or 0) > 0: break
                time.sleep(0.1)
        except Exception as e:
            log.info("thumbnail engine unavailable: %s", e); self.failed = True; return
        while not self.stop_flag:
            b = self.q.get()
            if b is None: break
            try:
                m.command("seek", b * BUCKET + BUCKET / 2, "absolute", "keyframes"); t0 = time.time()
                while time.time() - t0 < 4 and m.seeking: time.sleep(0.03)
                time.sleep(0.12)
                r = m.command("screenshot-raw", "video"); w, h = r["w"], r["h"]
                img = QImage(bytes(r["data"]), w, h, r["stride"], QImage.Format.Format_RGB32).copy().scaledToWidth(240)
                self.cache[b] = img; self.ready.emit(b, img)
            except Exception as e:
                log.debug("thumb failed: %s", e)
        try: m.terminate()
        except Exception: pass
