from __future__ import annotations
import time
from .. import prayer
from PySide6.QtCore import Qt, Signal, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, QListView, QListWidget, QListWidgetItem,
                               QScrollArea, QPushButton, QFrame, QAbstractItemView, QMenu, QCheckBox, QSpinBox, QMessageBox, QTabWidget, QFormLayout)
from .widgets import ItemModel, PosterDelegate, ChannelDelegate, Row, Hero, HoverTracker, ITEM_ROLE
from ..models import Item
from .backdrop import Backdrop
from ..ratings import clean_title
from .. import smart


class HomePage(QScrollArea):
    play = Signal(object)
    info = Signal(object)
    context = Signal(object, object)

    def __init__(self, loader, fav):
        super().__init__()
        self.setWidgetResizable(True); self.setFrameShape(QFrame.NoFrame)
        body = QWidget(); self.lay = QVBoxLayout(body); self.lay.setContentsMargins(0, 0, 0, 40); self.lay.setSpacing(10)
        self.hero = Hero(loader); self.lay.addWidget(self.hero)
        self.hero.play.connect(self.play); self.hero.info.connect(self.info)
        self.rows: dict[str, Row] = {}
        for key, title in (("recent", "Continue watching"), ("b0", "Because you watched"), ("b1", "Because you watched"), ("b2", "Because you watched"), ("@recent", "Recently added"), ("@top", "Top rated"), ("@new", "New releases"), ("fav", "My list"), ("live", "Live TV"), ("movie", "Movies"), ("series", "TV series")):
            r = Row(title, loader, fav); r.setContentsMargins(48, 0, 24, 0)
            r.activated.connect(lambda it, k=key: self._act(it, k)); r.context.connect(self.context); self.rows[key] = r; self.lay.addWidget(r); r.hide()
        self.lay.addStretch()
        self.setWidget(body)

    def _act(self, it, row=""):
        (self.info if (it.kind in ("series", "movie") and row != "recent") else self.play).emit(it)

    def resizeEvent(self, e):
        w = max(140, min(260, int(self.width() / 9.5)))
        for r in self.rows.values():
            r.set_card_width(w)
        super().resizeEvent(e)

    def set_loading(self):
        for k in ("live", "movie", "series"):
            self.rows[k].set_items([Item("", kind="skeleton") for _ in range(10)]); self.rows[k].show()

    def populate(self, live, movies, series, recents, favs, sm=None):
        sm = sm or {}
        pool = [i for i in sm.get("@top", []) + sm.get("@new", []) if i.logo]          # banner: best rated + newest, with posters
        seen, feat = set(), []
        for i in sorted(pool, key=lambda x: (smart.score(x) + (2 if smart.year(x) >= 2025 else 0)), reverse=True):
            if i.key not in seen: seen.add(i.key); feat.append(i)
        feat = feat[:12] or [i for i in movies + series if i.logo][:12] or [i for i in live if i.logo][:6]
        if not feat or [i.key for i in feat] != [i.key for i in self.hero.items]: self.hero.set_items(feat)
        for k in ("@recent", "@top", "@new"): self.rows[k].set_items(sm.get(k, [])[:40])
        bw = sm.get("because", [])
        for n in range(3):
            r = self.rows[f"b{n}"]
            if n < len(bw): r.title.setText("Because you watched  " + clean_title(bw[n][0])); r.set_items(bw[n][1])
            else: r.set_items([])
        self.rows["recent"].set_items(recents); self.rows["fav"].set_items(favs)
        self.rows["live"].set_items([i for i in live if i.logo][:40] or live[:40])
        self.rows["movie"].set_items(movies[:60]); self.rows["series"].set_items(series[:60])


class BrowsePage(Backdrop):
    """Grid of movies or series with search + category filter."""
    activated = Signal(object)
    context = Signal(object, object)
    hide_group = Signal(str, bool)

    def __init__(self, title, loader, fav, kind=""):
        super().__init__(); self.kind = kind
        lay = QVBoxLayout(self); lay.setContentsMargins(36, 28, 24, 12)
        top = QHBoxLayout(); hb = QVBoxLayout(); eb = QLabel(title.upper()); eb.setObjectName("eyebrow"); h = QLabel("Browse " + title.lower() if title != "My List" else "Your saved titles"); h.setObjectName("display")
        hb.addWidget(eb); hb.addWidget(h); top.addLayout(hb); top.addStretch()
        self.group = QComboBox(); self.group.setMinimumWidth(220); self.group.addItem("All categories", "")
        self.search = QLineEdit(); self.search.setPlaceholderText("Search…"); self.search.setClearButtonEnabled(True); self.search.setMinimumWidth(260)
        self.search.setObjectName("search"); self.b_hide = QPushButton("Hide category"); self.b_hide.setObjectName("ghostsm"); self.b_hide.setToolTip("Hide the selected category everywhere (undo in Settings → Hide channels & languages)"); self.b_hide.hide()
        self.b_hide.clicked.connect(lambda: self.group.currentData() and self.hide_group.emit(self.group.currentData(), False))
        self.group.currentIndexChanged.connect(lambda _i: self.b_hide.setVisible(bool(self.group.currentData())))
        top.addWidget(self.group); top.addWidget(self.b_hide); top.addWidget(self.search); lay.addLayout(top)
        self.model = ItemModel(self); self.delegate = PosterDelegate(loader, 170, fav)
        self.view = QListView(); self.view.setModel(self.model); self.view.setItemDelegate(self.delegate)
        self.view.setViewMode(QListView.IconMode); self.view.setResizeMode(QListView.Adjust); self.view.setMovement(QListView.Static)
        self.view.setUniformItemSizes(True); self.view.setMouseTracking(True); self.view.setSpacing(4)
        self.view.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel); self.view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.view.verticalScrollBar().setSingleStep(40)
        lay.addWidget(self.view)
        self.empty = QLabel("Nothing here yet. Add a playlist in Settings."); self.empty.setObjectName("muted"); self.empty.setAlignment(Qt.AlignCenter); lay.addWidget(self.empty)
        self._t = QTimer(self); self._t.setSingleShot(True); self._t.setInterval(180); self._t.timeout.connect(self._apply)
        self.search.textChanged.connect(lambda _t: self._t.start()); self.group.currentIndexChanged.connect(lambda _i: self._apply())
        self.view.clicked.connect(lambda i: self.activated.emit(i.data(ITEM_ROLE)))        # one click opens (series page / movie), like Netflix
        self.view.activated.connect(lambda i: self.activated.emit(i.data(ITEM_ROLE)))      # Enter key
        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._ctx)
        self.loader = loader; self._ht = HoverTracker(self.view); self._ht.hoverRow.connect(self._tint_row)
        self.view.selectionModel().currentChanged.connect(lambda cur, _p: self._tint_row(cur.row()) if cur.isValid() else None)

    def _tint_row(self, row):
        """Background glow follows the poster under the pointer / keyboard focus."""
        if row is None or not 0 <= row < len(self.model.items): return
        it = self.model.items[row]
        if it.kind != "skeleton" and self.loader.color(it.logo) is not None: self.set_tint(self.loader.color(it.logo))

    def set_loading(self):
        self.model.set_loading(24); self.group.blockSignals(True); self.group.clear(); self.group.addItem("All categories", ""); self.group.blockSignals(False)
        self.empty.hide(); self.view.show()

    def _ctx(self, pos):
        i = self.view.indexAt(pos)
        if i.isValid():
            self.context.emit(i.data(ITEM_ROLE), self.view.viewport().mapToGlobal(pos))

    def _apply(self):
        g = self.group.currentData() or ""; q = self.search.text().strip()
        if g.startswith("@"):                  # ready-made lists: recently added, top rated, new releases, Hollywood
            base = smart.build(g, self.model.all, self.kind or "movie")
            items = smart.rank(base, q) if q else base
            self.model.beginResetModel(); self.model.items = items; self.model.endResetModel(); return
        if len(q) >= 2 and not g:
            items = smart.rank(self.model.all, q, 1500)
            self.model.beginResetModel(); self.model.items = items; self.model.endResetModel(); return
        self.model.filter(q, g)

    def set_items(self, items):
        self.model.set_items(items)
        self.group.blockSignals(True); self.group.clear(); self.group.addItem("All categories", "")
        if self.kind:
            for k, label in smart.SPECIALS:
                if k != "@hollywood" or self.kind == "movie": self.group.addItem("★  " + label, k)
        for g in sorted({i.group for i in items if i.group}):
            self.group.addItem(g, g)
        self.group.blockSignals(False)
        self.empty.setVisible(not items); self.view.setVisible(bool(items))

    def resizeEvent(self, e):
        self.delegate.set_width(max(140, min(280, int(self.width() / 8.5)))); self.model.layoutChanged.emit(); super().resizeEvent(e)


class SettingsPage(QScrollArea):
    add_playlist = Signal()
    refresh_library = Signal()
    changed = Signal()

    def __init__(self, store):
        super().__init__()
        self.store = store; self.setWidgetResizable(True); self.setFrameShape(QFrame.NoFrame)
        body = QWidget(); self.setWidget(body); lay = QVBoxLayout(body); lay.setContentsMargins(36, 28, 36, 40); lay.setSpacing(14)
        h = QLabel("Settings"); h.setObjectName("h1"); lay.addWidget(h)
        # profiles + playlists
        lay.addWidget(self._h("Profile & playlists"))
        row = QHBoxLayout(); self.profile = QComboBox(); self.b_newp = QPushButton("New profile"); self.b_delp = QPushButton("Delete profile")
        row.addWidget(QLabel("Profile")); row.addWidget(self.profile, 1); row.addWidget(self.b_newp); row.addWidget(self.b_delp); lay.addLayout(row)
        self.pl_list = QListWidget(); self.pl_list.setObjectName("cats"); self.pl_list.setFixedHeight(150); lay.addWidget(self.pl_list)
        row = QHBoxLayout()
        self.b_add = QPushButton("Add playlist…"); self.b_use = QPushButton("Use selected"); self.b_del = QPushButton("Remove"); self.b_ref = QPushButton("Reload content")
        for b in (self.b_add, self.b_use, self.b_del, self.b_ref): row.addWidget(b)
        row.addStretch(); lay.addLayout(row)
        # playback
        lay.addWidget(self._h("Video"))
        f = QFormLayout()
        self.hwdec = QComboBox()
        for label, v in (("Automatic (recommended)", "auto-safe"), ("NVIDIA NVDEC (direct)", "nvdec"), ("NVIDIA NVDEC (copy-back)", "nvdec-copy"),
                         ("Direct3D 11 (D3D11VA)", "d3d11va"), ("Software only", "no")):
            self.hwdec.addItem(label, v)
        self.hdr = QComboBox(); self.hdr.addItem("Auto - signal HDR10 to Windows when content is HDR", "auto"); self.hdr.addItem("Off - always tone-map to SDR", "off")
        self.quality = QComboBox(); self.quality.addItem("Fast - lightest on the GPU", "fast"); self.quality.addItem("Balanced (recommended)", "balanced"); self.quality.addItem("Max quality - best scalers + debanding (RTX-class GPU)", "max")
        self.denoise = QComboBox(); self.denoise.addItem("Off", "off"); self.denoise.addItem("Light - removes mild blocking/noise", "light"); self.denoise.addItem("Medium - for very low-bitrate streams", "medium")
        self.deint = QComboBox(); self.deint.addItem("Auto (when the stream is interlaced)", "auto"); self.deint.addItem("Always on", "on"); self.deint.addItem("Off", "off")
        self.hdr_enh = QCheckBox("Enhanced HDR→SDR (contrast recovery) when the display is not in HDR mode")
        self.motion = QComboBox(); self.motion.addItem("Off - original frame rate", "off"); self.motion.addItem("Smooth motion - frame interpolation (sports; can look 'soap-opera')", "smooth")
        self.tone = QComboBox()
        for label, v in (("Automatic (BT.2390)", "auto"), ("Spline", "spline"), ("Mobius", "mobius"), ("Hable", "hable"), ("Reinhard", "reinhard")): self.tone.addItem(label, v)
        self.peak = QSpinBox(); self.peak.setRange(0, 4000); self.peak.setSingleStep(50); self.peak.setSpecialValueText("Auto"); self.peak.setSuffix(" nits")
        self.timeshift = QComboBox()
        for label, v in (("Off", 0), ("2 minutes", 2), ("5 minutes (recommended)", 5), ("10 minutes", 10), ("20 minutes", 20)): self.timeshift.addItem(label, v)
        f.addRow("Hardware decoding", self.hwdec); f.addRow("HDR output", self.hdr); f.addRow("Picture quality", self.quality); f.addRow("Noise reduction", self.denoise); f.addRow("Deinterlacing", self.deint)
        f.addRow("Motion", self.motion); f.addRow("HDR → SDR tone-mapping", self.tone); f.addRow("Display peak brightness", self.peak); f.addRow("Live rewind buffer", self.timeshift); lay.addLayout(f)
        lay.addWidget(self.hdr_enh)
        row = QHBoxLayout(); self.b_hdr_set = QPushButton("Windows HDR settings"); self.b_hdr_cal = QPushButton("Windows HDR Calibration app"); row.addWidget(self.b_hdr_set); row.addWidget(self.b_hdr_cal); row.addStretch(); lay.addLayout(row)
        hdn = QLabel("For correct HDR: turn on Windows HDR (Settings → System → Display → HDR), run the free 'Windows HDR Calibration' app once for your monitor, then set Display peak brightness here to the value it reports. Noise reduction runs on the CPU, only for 1080p-and-below streams, and switches hardware decoding to copy mode."); hdn.setWordWrap(True); hdn.setObjectName("muted"); lay.addWidget(hdn)
        self.b_hdr_set.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("ms-settings:display-advancedcolor"))); self.b_hdr_cal.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("ms-windows-store://pdp/?ProductId=9N7F2SM5D1LR")))
        hn = QLabel("Display peak brightness: set your monitor's HDR peak (e.g. 600 or 1000 nits) to tune how HDR is mapped; leave on Auto if unsure. Live rewind keeps the last few minutes in RAM (about 1 MiB per second of stream is assumed, so 4K streams hold less) so you can step back 10 s on live TV."); hn.setWordWrap(True); hn.setObjectName("muted"); lay.addWidget(hn)
        un = QLabel("Uses mpv's GPU scalers (EWA Lanczos, sigmoid upscaling, deband). These are classic filters, not AI upscaling, and are not NVIDIA DLSS."); un.setWordWrap(True); un.setObjectName("muted"); lay.addWidget(un)
        lay.addWidget(self._h("Audio"))
        f2 = QFormLayout(); self.dev = QComboBox(); self.dev.addItem("System default", "auto"); f2.addRow("Output device", self.dev)
        self.lang_a = QLineEdit(); self.lang_a.setPlaceholderText("e.g. eng,ara"); self.lang_s = QLineEdit(); self.lang_s.setPlaceholderText("e.g. eng,ara")
        f2.addRow("Preferred audio language(s)", self.lang_a); f2.addRow("Preferred subtitle language(s)", self.lang_s); lay.addLayout(f2)
        self.p_ac3 = QCheckBox("Bitstream Dolby Digital (AC-3)"); self.p_eac3 = QCheckBox("Bitstream Dolby Digital Plus (E-AC-3) - carries Atmos from streaming-style sources")
        self.p_dts = QCheckBox("Bitstream DTS"); self.p_hd = QCheckBox("Bitstream Dolby TrueHD / DTS-HD (needs HDMI audio device exposing these formats)")
        self.excl = QCheckBox("WASAPI exclusive mode (often required for HD passthrough)")
        for c in (self.p_ac3, self.p_eac3, self.p_dts, self.p_hd, self.excl): lay.addWidget(c)
        n = QLabel("Passthrough only works when the output device is an HDMI/optical device that supports the format (set it up in Windows Sound → device → Properties → Supported Formats) and your receiver accepts it. When off, audio is decoded to PCM."); n.setWordWrap(True); n.setObjectName("muted"); lay.addWidget(n)
        lay.addWidget(self._h("Live preview"))
        self.pv_on = QCheckBox("Play a live preview in Live TV when a channel is selected"); self.pv_mute = QCheckBox("Start previews muted")
        lay.addWidget(self.pv_on); lay.addWidget(self.pv_mute)
        lay.addWidget(self._h("Appearance"))
        fa = QFormLayout(); self.accent = QComboBox()
        for label, v in (("Rose (default)", "rose"), ("Red", "red"), ("Blue", "blue"), ("Purple", "purple"), ("Teal", "teal"), ("Gold", "gold")): self.accent.addItem(label, v)
        self.uiscale = QComboBox()
        for v in (100, 115, 130, 150, 175): self.uiscale.addItem(f"{v}%", v)
        fa.addRow("Accent colour", self.accent); fa.addRow("Text & UI size", self.uiscale); lay.addLayout(fa)
        self.tenfoot = QCheckBox("10-foot mode: big cards and text, strong focus highlight, starts maximised (for a TV + controller)"); self.anim = QCheckBox("Animations (page fades, hover lift, zoom)")
        self.thumbs = QCheckBox("Scrub thumbnails on movies/episodes (opens a 2nd connection to your provider - leave off if your plan allows 1 stream)")
        for c in (self.tenfoot, self.anim, self.thumbs): lay.addWidget(c)
        row = QHBoxLayout(); self.b_restart = QPushButton("Restart 91 TV to apply colour / size"); row.addWidget(self.b_restart); row.addStretch(); lay.addLayout(row)
        lay.addWidget(self._h("Prayer times (Bahrain)"))
        fp = QFormLayout(); self.pt_method = QComboBox()
        for v, label in prayer.METHODS: self.pt_method.addItem(label, v)
        self.pt_remind = QComboBox()
        for v in prayer.REMIND: self.pt_remind.addItem("Off" if v == 0 else f"{v} minutes before", v)
        self.pt_header = QCheckBox("Show the next prayer and countdown in the top bar")
        fp.addRow("Calculation method", self.pt_method); fp.addRow("Reminder banner", self.pt_remind); lay.addLayout(fp); lay.addWidget(self.pt_header)
        lay.addWidget(self._h("Screensaver"))
        self.ss_on = QCheckBox("Show a clock screensaver when nothing is playing and nobody touches the PC"); self.ss_min = QComboBox()
        for v in (1, 2, 5, 10, 20): self.ss_min.addItem(f"after {v} minute{'s' if v > 1 else ''}", v)
        fs = QFormLayout(); fs.addRow("Start", self.ss_min); lay.addWidget(self.ss_on); lay.addLayout(fs)
        lay.addWidget(self._h("IMDb & Rotten Tomatoes (OMDb)"))
        self.omdb = QLineEdit(); self.omdb.setEchoMode(QLineEdit.Password); self.omdb.setPlaceholderText("Paste your free OMDb key (omdbapi.com)"); lay.addWidget(self.omdb)
        on = QLabel("Free key at omdbapi.com/apikey.aspx (1000 look-ups a day). Without it the provider's own score is shown instead. Only the title and year are sent."); on.setWordWrap(True); on.setObjectName("muted"); lay.addWidget(on)
        lay.addWidget(self._h("Artwork & info (TMDB)"))
        row = QHBoxLayout(); self.tmdb = QLineEdit(); self.tmdb.setEchoMode(QLineEdit.Password); self.tmdb.setPlaceholderText("Paste your free TMDB API key or read-access token")
        self.b_tmdb = QPushButton("Test key"); row.addWidget(self.tmdb, 1); row.addWidget(self.b_tmdb); lay.addLayout(row)
        self.tmdb_replace = QCheckBox("Prefer TMDB posters over the provider's artwork (otherwise only fills in missing ones)"); lay.addWidget(self.tmdb_replace)
        self.tmdb_state = QLabel(""); self.tmdb_state.setObjectName("muted"); self.tmdb_state.setWordWrap(True); lay.addWidget(self.tmdb_state)
        tn = QLabel("Get a free key at themoviedb.org (Settings → API). Titles of your movies/series are sent to TMDB to look up artwork, plot, rating and cast. Nothing else is sent."); tn.setWordWrap(True); tn.setObjectName("muted"); lay.addWidget(tn)
        lay.addWidget(self._h("Parental controls"))
        row = QHBoxLayout(); self.b_pin = QPushButton("Set PIN…"); self.b_pin_clear = QPushButton("Remove PIN"); self.b_cats = QPushButton("Hide channels & languages…"); self.b_unlock = QPushButton("Unlock hidden content")
        for b in (self.b_pin, self.b_pin_clear, self.b_cats, self.b_unlock): row.addWidget(b)
        row.addStretch(); lay.addLayout(row)
        self.auto_dead = QCheckBox("Auto-hide channels that fail repeatedly (retested after 7 days)"); lay.addWidget(self.auto_dead)
        row = QHBoxLayout(); self.b_dead = QPushButton("Auto-hidden channels…"); row.addWidget(self.b_dead); row.addStretch(); lay.addLayout(row)
        pn = QLabel("Use Hide channels & languages to remove languages/countries (FR|, AR|…), alphabets, categories or single channels you don't need (right-click any channel to hide it). Hidden categories can be PIN-locked: with a PIN set they come back only after Unlock."); pn.setWordWrap(True); pn.setObjectName("muted"); lay.addWidget(pn)
        lay.addWidget(self._h("Controls"))
        self.pad = QCheckBox("Game controller support (Xbox / XInput pads)"); lay.addWidget(self.pad)
        pdn = QLabel("D-pad / left stick = move, A = select, B = back, X = reload, Y = full screen, LB / RB = channel -/+, Start = play/pause. Remote-control media keys (play/pause, stop, next/previous, channel up/down) work too."); pdn.setWordWrap(True); pdn.setObjectName("muted"); lay.addWidget(pdn)
        row = QHBoxLayout(); self.b_wizard = QPushButton("Run setup wizard…"); row.addWidget(self.b_wizard); row.addStretch(); lay.addLayout(row)
        lay.addWidget(self._h("Network & guide"))
        f3 = QFormLayout(); self.epg = QLineEdit(); self.epg.setPlaceholderText("Default XMLTV URL (used when a playlist has none)")
        self.retries = QSpinBox(); self.retries.setRange(0, 20)
        f3.addRow("EPG (XMLTV) URL", self.epg); f3.addRow("Auto-reconnect attempts", self.retries); lay.addLayout(f3)
        lay.addWidget(self._h("Diagnostics"))
        row = QHBoxLayout(); self.b_log = QPushButton("Open log folder"); self.b_diag = QPushButton("Run diagnostics"); row.addWidget(self.b_log); row.addWidget(self.b_diag); row.addStretch(); lay.addLayout(row)
        self.diag = QLabel(""); self.diag.setWordWrap(True); self.diag.setObjectName("muted"); self.diag.setTextInteractionFlags(Qt.TextSelectableByMouse); lay.addWidget(self.diag)
        from .. import lic as _lic
        lh = QLabel("Licence"); lh.setObjectName("h2"); lay.addWidget(lh)
        self._lic = _lic.Lic(store); self.lic_lbl = QLabel(self._lic.summary()); lay.addWidget(self.lic_lbl)
        lrow = QHBoxLayout(); b_code = QPushButton("Enter a code"); b_rm = QPushButton("Remove from this PC"); lrow.addWidget(b_code); lrow.addWidget(b_rm); lrow.addStretch(); lay.addLayout(lrow)
        def _enter():
            from .dialogs import ActivationDialog
            ActivationDialog(self._lic, self).exec(); self.lic_lbl.setText(self._lic.summary())
        def _remove():
            if QMessageBox.question(self, "91 TV", "Remove the code from this PC so it can be used on another device? 91 TV will ask for a code again.") != QMessageBox.Yes: return
            r = self._lic.deactivate(); self.lic_lbl.setText(self._lic.summary())
            if r: QMessageBox.warning(self, "91 TV", r)
        b_code.clicked.connect(_enter); b_rm.clicked.connect(_remove)
        lay.addStretch()
        self._load()
        for w in (self.hwdec, self.hdr, self.dev, self.quality, self.denoise, self.deint, self.accent, self.uiscale, self.motion, self.tone, self.timeshift): w.currentIndexChanged.connect(lambda _i: self._save())
        for c in (self.p_ac3, self.p_eac3, self.p_dts, self.p_hd, self.excl, self.pv_on, self.pv_mute, self.tmdb_replace, self.auto_dead, self.pad, self.hdr_enh, self.tenfoot, self.anim, self.thumbs): c.toggled.connect(lambda _b: self._save())
        self.peak.valueChanged.connect(lambda _v: self._save()); self.tmdb.editingFinished.connect(self._save)
        for e in (self.epg, self.lang_a, self.lang_s): e.editingFinished.connect(self._save)
        self.retries.valueChanged.connect(lambda _v: self._save())
        for w in (self.pt_method, self.pt_remind, self.ss_min): w.currentIndexChanged.connect(lambda _i: self._save())
        for c in (self.pt_header, self.ss_on): c.toggled.connect(lambda _b: self._save())
        self.omdb.editingFinished.connect(self._save)

    @staticmethod
    def _h(t):
        l = QLabel(t); l.setObjectName("h2"); l.setStyleSheet("margin-top:16px;"); return l

    def set_devices(self, devs):
        self.dev.blockSignals(True); cur = self.store.get("audio_device"); self.dev.clear(); self.dev.addItem("System default", "auto")
        for name, desc in devs:
            if name != "auto": self.dev.addItem(desc, name)
        i = self.dev.findData(cur); self.dev.setCurrentIndex(max(0, i)); self.dev.blockSignals(False)

    def _load(self):
        s = self.store; self._loading = True
        self.hwdec.setCurrentIndex(max(0, self.hwdec.findData(s.get("hwdec")))); self.hdr.setCurrentIndex(max(0, self.hdr.findData(s.get("hdr"))))
        self.p_ac3.setChecked(bool(s.get("pass_ac3"))); self.p_eac3.setChecked(bool(s.get("pass_eac3"))); self.p_dts.setChecked(bool(s.get("pass_dts")))
        self.p_hd.setChecked(bool(s.get("pass_hd"))); self.excl.setChecked(bool(s.get("audio_exclusive")))
        self.quality.setCurrentIndex(max(0, self.quality.findData(s.get("quality")))); self.denoise.setCurrentIndex(max(0, self.denoise.findData(s.get("denoise")))); self.deint.setCurrentIndex(max(0, self.deint.findData(s.get("deinterlace"))))
        self.hdr_enh.setChecked(bool(s.get("hdr_enhance"))); self.accent.setCurrentIndex(max(0, self.accent.findData(s.get("accent")))); self.uiscale.setCurrentIndex(max(0, self.uiscale.findData(int(s.get("ui_scale") or 100))))
        self.tenfoot.setChecked(bool(s.get("tenfoot"))); self.anim.setChecked(bool(s.get("animations"))); self.thumbs.setChecked(bool(s.get("scrub_thumbs")))
        self.pv_on.setChecked(bool(s.get("preview_enabled"))); self.pv_mute.setChecked(bool(s.get("preview_muted")))
        self.motion.setCurrentIndex(max(0, self.motion.findData(s.get("motion")))); self.tone.setCurrentIndex(max(0, self.tone.findData(s.get("tone_mapping"))))
        self.timeshift.setCurrentIndex(max(0, self.timeshift.findData(int(s.get("timeshift") or 0)))); self.peak.setValue(int(s.get("display_peak") or 0))
        self.tmdb.setText(s.tmdb_key()); self.tmdb_replace.setChecked(bool(s.get("tmdb_replace"))); self.auto_dead.setChecked(bool(s.get("auto_hide_dead"))); self.pad.setChecked(bool(s.get("gamepad")))
        self.epg.setText(s.get("epg_url") or ""); self.lang_a.setText(s.get("audio_lang") or ""); self.lang_s.setText(s.get("sub_lang") or ""); self.retries.setValue(int(s.get("max_reconnects")))
        self.pt_method.setCurrentIndex(max(0, self.pt_method.findData(int(s.get("pt_method") or 8)))); self.pt_remind.setCurrentIndex(max(0, self.pt_remind.findData(int(s.get("pt_remind") or 0))))
        self.pt_header.setChecked(bool(s.get("pt_header"))); self.ss_on.setChecked(bool(s.get("ss_on"))); self.ss_min.setCurrentIndex(max(0, self.ss_min.findData(int(s.get("ss_minutes") or 2)))); self.omdb.setText(s.get("omdb_key") or "")
        self._loading = False

    def _save(self):
        if getattr(self, "_loading", False):
            return
        s = self.store
        s.set("hwdec", self.hwdec.currentData()); s.set("hdr", self.hdr.currentData()); s.set("audio_device", self.dev.currentData() or "auto")
        for k, c in (("pass_ac3", self.p_ac3), ("pass_eac3", self.p_eac3), ("pass_dts", self.p_dts), ("pass_hd", self.p_hd), ("audio_exclusive", self.excl)):
            s.set(k, c.isChecked())
        s.set("quality", self.quality.currentData()); s.set("denoise", self.denoise.currentData()); s.set("deinterlace", self.deint.currentData()); s.set("hdr_enhance", self.hdr_enh.isChecked())
        s.set("accent", self.accent.currentData()); s.set("ui_scale", self.uiscale.currentData()); s.set("tenfoot", self.tenfoot.isChecked()); s.set("animations", self.anim.isChecked()); s.set("scrub_thumbs", self.thumbs.isChecked())
        s.set("upscale", "high" if self.quality.currentData() == "max" else "off"); s.set("preview_enabled", self.pv_on.isChecked()); s.set("preview_muted", self.pv_mute.isChecked())
        s.set("motion", self.motion.currentData()); s.set("tone_mapping", self.tone.currentData()); s.set("timeshift", self.timeshift.currentData()); s.set("display_peak", self.peak.value())
        s.set_tmdb_key(self.tmdb.text()); s.set("tmdb_replace", self.tmdb_replace.isChecked()); s.set("auto_hide_dead", self.auto_dead.isChecked()); s.set("gamepad", self.pad.isChecked())
        s.set("epg_url", self.epg.text().strip()); s.set("audio_lang", self.lang_a.text().strip()); s.set("sub_lang", self.lang_s.text().strip()); s.set("max_reconnects", self.retries.value())
        s.set("pt_method", self.pt_method.currentData()); s.set("pt_remind", self.pt_remind.currentData()); s.set("pt_header", self.pt_header.isChecked())
        s.set("ss_on", self.ss_on.isChecked()); s.set("ss_minutes", self.ss_min.currentData()); s.set("omdb_key", self.omdb.text().strip())
        self.changed.emit()

    def reload_playlists(self, profile_id, active_id):
        self.pl_list.clear()
        for pl in self.store.playlists(profile_id):
            it = QListWidgetItem(("● " if pl.id == active_id else "   ") + f"{pl.name}   ({pl.type.upper()})"); it.setData(Qt.UserRole, pl.id); self.pl_list.addItem(it)

    def reload_profiles(self, active_pid):
        self.profile.blockSignals(True); self.profile.clear()
        for pid, name in self.store.profiles():
            self.profile.addItem(name, pid)
        self.profile.setCurrentIndex(max(0, self.profile.findData(active_pid))); self.profile.blockSignals(False)
