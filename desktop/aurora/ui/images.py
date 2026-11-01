"""Async poster/logo loader with memory + disk cache."""
from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkDiskCache
import hashlib
from ..paths import cache_dir


def img_fmt():
    from PySide6.QtGui import QImage
    return QImage.Format.Format_ARGB32


class ImageLoader(QObject):
    loaded = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.nam = QNetworkAccessManager(self)
        dc = QNetworkDiskCache(self); dc.setCacheDirectory(str(cache_dir() / "images")); dc.setMaximumCacheSize(300 * 1024 * 1024)
        self.nam.setCache(dc)
        self.mem: dict[str, QPixmap] = {}
        self.pending: set[str] = set()
        self.failed: set[str] = set()
        self.stats: dict[str, tuple] = {}
        self.raw = cache_dir() / "imgraw"; self.raw.mkdir(parents=True, exist_ok=True); self._prune_raw()

    def _prune_raw(self):
        """Posters are saved after the first download so the home screen fills instantly after a restart. Keep about 400 MB."""
        try:
            fs = sorted(self.raw.iterdir(), key=lambda f: f.stat().st_mtime); tot = sum(f.stat().st_size for f in fs)
            while fs and tot > 400 * 1024 * 1024: f = fs.pop(0); tot -= f.stat().st_size; f.unlink()
        except Exception: pass

    def _raw_file(self, url): return self.raw / hashlib.md5(url.encode()).hexdigest()

    def status(self, url: str) -> str:
        """'ready' | 'loading' | 'failed' | 'none' (no usable URL) - drives skeletons and fallback tiles."""
        if not url or not url.lower().startswith("http"): return "none"
        if url in self.failed: return "failed"
        return "ready" if (url in self.mem or url + "#w" in self.mem) else "loading"

    def color(self, url: str):
        """Dominant accent-friendly colour of an image (QColor) once loaded."""
        st = self.stats.get(url); return st[0] if st else None

    def luma(self, url: str) -> float:
        st = self.stats.get(url); return st[1] if st else 0.5

    @staticmethod
    def _analyse(pm):
        """Average colour (saturation weighted) and brightness of the opaque pixels, from a 24px thumbnail."""
        from PySide6.QtGui import QColor
        from PySide6.QtCore import Qt
        img = pm.toImage().scaled(24, 24, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).convertToFormat(img_fmt())
        sr = sg = sb = sw = lum = la = 0.0
        for y in range(24):
            for x in range(24):
                c = img.pixelColor(x, y); a = c.alphaF()
                if a < 0.2: continue
                l = (0.2126 * c.redF() + 0.7152 * c.greenF() + 0.0722 * c.blueF()); lum += l * a; la += a
                w = (0.15 + c.hsvSaturationF()) * (1.0 - abs(l - 0.45)) * a
                sr += c.red() * w; sg += c.green() * w; sb += c.blue() * w; sw += w
        col = QColor(int(sr / sw), int(sg / sw), int(sb / sw)) if sw > 0 else QColor(120, 120, 130)
        return col, (lum / la if la else 0.5)

    def get(self, url: str, wide: bool = False):
        """wide=True keeps up to 1920px (hero/backdrop images, few of them); otherwise posters are capped at 700px."""
        if not url or not url.lower().startswith("http"):
            return None
        key = url + ("#w" if wide else "")
        pm = self.mem.get(key)
        if pm is not None:
            return pm
        rf = self._raw_file(url)
        if rf.exists() and url not in self.failed:
            try:
                if self._store(QPixmap(), url, key, wide, rf.read_bytes()): return self.mem.get(key)
            except Exception: pass
        if key not in self.pending and url not in self.failed and len(self.pending) < 64:
            self.pending.add(key)
            req = QNetworkRequest(QUrl(url))
            req.setAttribute(QNetworkRequest.RedirectPolicyAttribute, QNetworkRequest.NoLessSafeRedirectPolicy)
            req.setAttribute(QNetworkRequest.CacheLoadControlAttribute, QNetworkRequest.PreferCache)
            req.setRawHeader(b"User-Agent", b"VLC/3.0.20 LibVLC/3.0.20")
            req.setTransferTimeout(12000)
            rep = self.nam.get(req)
            rep.finished.connect(lambda r=rep, u=url, k=key, w=wide: self._done(r, u, k, w))
        return None

    def _store(self, pm, url, key, wide, data: bytes) -> bool:
        from PySide6.QtCore import Qt
        if not (pm.loadFromData(data) and not pm.isNull()): return False
        cap = 1920 if wide else 700
        if pm.width() > cap: pm = pm.scaledToWidth(cap, Qt.SmoothTransformation)
        limit = 12 if wide else 350
        same = [k for k in self.mem if k.endswith("#w") == wide]
        if len(same) > limit: self.mem.pop(same[0])
        self.mem[key] = pm
        try: self.stats[url] = self._analyse(pm)
        except Exception: pass
        return True

    def _done(self, rep, url, key, wide):
        self.pending.discard(key)
        data = bytes(rep.readAll()); err = rep.errorString(); ok = rep.error() == rep.NetworkError.NoError
        rep.deleteLater()
        if ok and self._store(QPixmap(), url, key, wide, data):
            try: self._raw_file(url).write_bytes(data)
            except Exception: pass
            self.loaded.emit(url)
        else:
            import logging; logging.getLogger(__name__).debug("image failed %s: %s", url.split('?')[0], err)
            self.failed.add(url)
