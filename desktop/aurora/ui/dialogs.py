from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QWidget as _W, QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton, QLabel, QTabWidget, QWidget,
                               QFileDialog, QTreeWidget, QTreeWidgetItem, QDialogButtonBox, QMessageBox)


class PlaylistDialog(QDialog):
    """Add an M3U/M3U8 (URL or file) or Xtream Codes playlist."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add playlist"); self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        self.name = QLineEdit(); self.name.setPlaceholderText("Playlist name (e.g. My IPTV)")
        lay.addWidget(self.name)
        self.tabs = QTabWidget(); lay.addWidget(self.tabs)
        t1 = QWidget(); f1 = QFormLayout(t1)
        self.url = QLineEdit(); self.url.setPlaceholderText("https://example.com/list.m3u8")
        f1.addRow("M3U / M3U8 URL", self.url)
        row = QHBoxLayout(); self.path = QLineEdit(); self.path.setPlaceholderText("or choose a local .m3u / .m3u8 file")
        b = QPushButton("Browse…"); b.clicked.connect(self._browse); row.addWidget(self.path); row.addWidget(b)
        f1.addRow("Local file", row)
        t2 = QWidget(); f2 = QFormLayout(t2)
        self.server = QLineEdit(); self.server.setPlaceholderText("http://provider.example:8080")
        self.user = QLineEdit(); self.pw = QLineEdit(); self.pw.setEchoMode(QLineEdit.Password)
        f2.addRow("Server URL", self.server); f2.addRow("Username", self.user); f2.addRow("Password", self.pw)
        self.tabs.addTab(t1, "M3U / M3U8"); self.tabs.addTab(t2, "Xtream Codes")
        self.epg = QLineEdit(); self.epg.setPlaceholderText("Optional XMLTV EPG URL (Xtream and many M3U lists provide one automatically)")
        lay.addWidget(self.epg)
        note = QLabel("Credentials and URLs are stored in Windows Credential Manager, not in plain text."); note.setObjectName("muted"); lay.addWidget(note)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); bb.accepted.connect(self._ok); bb.rejected.connect(self.reject); lay.addWidget(bb)
        self.result_data = None

    def _browse(self):
        p, _ = QFileDialog.getOpenFileName(self, "Choose playlist", "", "Playlists (*.m3u *.m3u8 *.txt *.gz);;All files (*)")
        if p:
            self.path.setText(p)

    def _ok(self):
        if self.tabs.currentIndex() == 1:
            if not (self.server.text().strip() and self.user.text().strip() and self.pw.text()):
                QMessageBox.warning(self, "Missing data", "Enter server, username and password."); return
            self.result_data = dict(name=self.name.text().strip() or self.user.text().strip(), type_="xtream", source=self.server.text().strip(),
                                    username=self.user.text().strip(), secret=self.pw.text(), epg_url=self.epg.text().strip())
        else:
            src = self.url.text().strip() or self.path.text().strip()
            if not src:
                QMessageBox.warning(self, "Missing data", "Enter a playlist URL or choose a file."); return
            self.result_data = dict(name=self.name.text().strip() or "Playlist", type_="m3u", source=src, epg_url=self.epg.text().strip())
        self.accept()


class EpisodesDialog(QDialog):
    chosen = Signal(object)

    def __init__(self, title, episodes, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title); self.resize(620, 560)
        lay = QVBoxLayout(self)
        h = QLabel(title); h.setObjectName("h1"); lay.addWidget(h)
        self.tree = QTreeWidget(); self.tree.setHeaderHidden(True); lay.addWidget(self.tree)
        self.plot = QLabel(""); self.plot.setWordWrap(True); self.plot.setObjectName("muted"); lay.addWidget(self.plot)
        seasons = {}
        for e in episodes:
            if e.season not in seasons:
                node = QTreeWidgetItem([f"Season {e.season}"]); self.tree.addTopLevelItem(node); seasons[e.season] = node
            c = QTreeWidgetItem([f"{e.number:02d}  {e.title}"]); c.setData(0, Qt.UserRole, e); seasons[e.season].addChild(c)
        if seasons:
            self.tree.expandItem(next(iter(seasons.values())))
        self.tree.itemDoubleClicked.connect(self._pick)
        self.tree.currentItemChanged.connect(lambda cur, _p: self.plot.setText((cur.data(0, Qt.UserRole).plot if cur and cur.data(0, Qt.UserRole) else "")))
        b = QPushButton("▶  Play episode"); b.setObjectName("primary"); b.clicked.connect(lambda: self._pick(self.tree.currentItem())); lay.addWidget(b)

    def _pick(self, item, _col=0):
        e = item.data(0, Qt.UserRole) if item else None
        if e:
            self.chosen.emit(e); self.accept()


class CategoriesDialog(QDialog):
    """Tick the categories to hide (per profile)."""
    def __init__(self, groups: list[str], hidden: set[str], is_adult, parent=None):
        super().__init__(parent); from PySide6.QtWidgets import QListWidget, QListWidgetItem
        self.setWindowTitle("Hidden categories"); self.resize(460, 560); lay = QVBoxLayout(self)
        h = QLabel("Hide categories"); h.setObjectName("h1"); lay.addWidget(h)
        n = QLabel("Ticked categories are removed from every screen (Live TV, guide, movies, series, home, search)."); n.setObjectName("muted"); n.setWordWrap(True); lay.addWidget(n)
        self.search = QLineEdit(); self.search.setPlaceholderText("Filter…"); lay.addWidget(self.search)
        self.lst = QListWidget(); lay.addWidget(self.lst, 1)
        for g in groups:
            it = QListWidgetItem(g); it.setFlags(it.flags() | Qt.ItemIsUserCheckable); it.setCheckState(Qt.Checked if g in hidden else Qt.Unchecked); self.lst.addItem(it)
        self.is_adult = is_adult
        row = QHBoxLayout(); b = QPushButton("Tick adult-looking categories"); b.clicked.connect(self._adult); row.addWidget(b); row.addStretch(); lay.addLayout(row)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); bb.accepted.connect(self.accept); bb.rejected.connect(self.reject); lay.addWidget(bb)
        self.search.textChanged.connect(lambda t: [self.lst.item(i).setHidden(t.lower() not in self.lst.item(i).text().lower()) for i in range(self.lst.count())])

    def _adult(self):
        for i in range(self.lst.count()):
            if self.is_adult(self.lst.item(i).text()): self.lst.item(i).setCheckState(Qt.Checked)

    def hidden(self) -> list[str]:
        return [self.lst.item(i).text() for i in range(self.lst.count()) if self.lst.item(i).checkState() == Qt.Checked]


class HideDialog(QDialog):
    """One place to hide what you don't need: whole languages/countries (category prefixes), writing systems, categories, single channels."""
    def __init__(self, groups: dict, hidden_groups: set, scripts: dict, hidden_scripts: set, chans: dict, is_adult, parent=None):
        super().__init__(parent); from PySide6.QtWidgets import QListWidget, QListWidgetItem, QTabWidget
        from .. import security
        self.setWindowTitle("Hide channels"); self.resize(560, 640); lay = QVBoxLayout(self)
        h = QLabel("Hide what you don't need"); h.setObjectName("h1"); lay.addWidget(h)
        self.tabs = QTabWidget(); lay.addWidget(self.tabs, 1); self.hidden_groups = set(hidden_groups); self.restore_keys: list[str] = []
        self.by_prefix: dict[str, list[str]] = {}
        for g in groups: self.by_prefix.setdefault(security.group_prefix(g) or "", []).append(g)
        # tab 1: languages / countries
        t1 = QWidget(); l1 = QVBoxLayout(t1)
        n = QLabel("Providers label categories with a language/country code (FR|, AR|, DE|…). Tick the ones you don't want and every category with that code disappears. Writing systems hide channels by the alphabet of their name."); n.setWordWrap(True); n.setObjectName("muted"); l1.addWidget(n)
        self.pre = QListWidget(); l1.addWidget(self.pre, 1)
        for pf in sorted((p for p in self.by_prefix if p), key=lambda p: -sum(groups[g] for g in self.by_prefix[p])):
            cats = self.by_prefix[pf]; cnt = sum(groups[g] for g in cats)
            it = QListWidgetItem(f"{pf}   ·   {len(cats)} categories, {cnt:,} items"); it.setData(Qt.UserRole, pf); it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if all(c in hidden_groups for c in cats) else Qt.Unchecked); self.pre.addItem(it)
        l1.addWidget(QLabel("Hide by alphabet:")); self.scr = QListWidget(); self.scr.setMaximumHeight(130); l1.addWidget(self.scr)
        for sc, cnt in scripts.items():
            it = QListWidgetItem(f"{sc} script   ·   {cnt:,} items"); it.setData(Qt.UserRole, sc); it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if sc in hidden_scripts else Qt.Unchecked); self.scr.addItem(it)
        if not scripts: l1.addWidget(QLabel("No non-Latin channel names found."))
        self.tabs.addTab(t1, "Languages")
        # tab 2: categories
        t2 = QWidget(); l2 = QVBoxLayout(t2); self.search = QLineEdit(); self.search.setPlaceholderText("Filter categories…"); l2.addWidget(self.search); self.lst = QListWidget(); l2.addWidget(self.lst, 1)
        for g in sorted(groups):
            it = QListWidgetItem(f"{g}   ({groups[g]:,})"); it.setData(Qt.UserRole, g); it.setFlags(it.flags() | Qt.ItemIsUserCheckable); it.setCheckState(Qt.Checked if g in hidden_groups else Qt.Unchecked); self.lst.addItem(it)
        self.is_adult = is_adult; row = QHBoxLayout(); b = QPushButton("Tick adult-looking categories"); b.clicked.connect(self._adult); row.addWidget(b); row.addStretch(); l2.addLayout(row)
        self.search.textChanged.connect(lambda t: [self.lst.item(i).setHidden(t.lower() not in self.lst.item(i).text().lower()) for i in range(self.lst.count())])
        self.tabs.addTab(t2, "Categories")
        # tab 3: single channels
        t3 = QWidget(); l3 = QVBoxLayout(t3); n3 = QLabel("Channels you hid one by one (right-click a channel → Hide). Select channels to bring back."); n3.setObjectName("muted"); n3.setWordWrap(True); l3.addWidget(n3)
        self.ch = QListWidget(); self.ch.setSelectionMode(QListWidget.ExtendedSelection); l3.addWidget(self.ch, 1)
        for k, name in chans.items():
            it = QListWidgetItem(name); it.setData(Qt.UserRole, k); self.ch.addItem(it)
        b3 = QPushButton("Restore selected"); b3.clicked.connect(self._restore); l3.addWidget(b3, 0, Qt.AlignLeft); self.tabs.addTab(t3, f"Hidden channels ({len(chans)})")
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); bb.accepted.connect(self.accept); bb.rejected.connect(self.reject); lay.addWidget(bb)

    def _adult(self):
        for i in range(self.lst.count()):
            if self.is_adult(self.lst.item(i).data(Qt.UserRole)): self.lst.item(i).setCheckState(Qt.Checked)

    def _restore(self):
        for it in self.ch.selectedItems(): self.restore_keys.append(it.data(Qt.UserRole)); it.setHidden(True)

    def result_groups(self) -> list[str]:
        hide = {self.lst.item(i).data(Qt.UserRole) for i in range(self.lst.count()) if self.lst.item(i).checkState() == Qt.Checked}
        for i in range(self.pre.count()):             # prefix ticks add/remove whole families of categories
            it = self.pre.item(i); cats = set(self.by_prefix[it.data(Qt.UserRole)])
            if it.checkState() == Qt.Checked: hide |= cats
            elif all(c in self.hidden_groups for c in cats): hide -= cats              # was fully hidden and got unticked
        return sorted(hide)

    def result_scripts(self) -> list[str]:
        return [self.scr.item(i).data(Qt.UserRole) for i in range(self.scr.count()) if self.scr.item(i).checkState() == Qt.Checked]


class DeadDialog(QDialog):
    """Channels that were hidden automatically after failing repeatedly."""
    def __init__(self, dead: dict, parent=None):
        super().__init__(parent); from PySide6.QtWidgets import QListWidget, QListWidgetItem
        self.setWindowTitle("Auto-hidden channels"); self.resize(460, 460); lay = QVBoxLayout(self); self.restore_keys: list[str] = []; self.restore_all = False
        h = QLabel("Auto-hidden channels"); h.setObjectName("h1"); lay.addWidget(h)
        n = QLabel("These failed to play several times in a row. They are retried automatically after 7 days. Select channels to bring back now."); n.setObjectName("muted"); n.setWordWrap(True); lay.addWidget(n)
        self.lst = QListWidget(); self.lst.setSelectionMode(QListWidget.ExtendedSelection); lay.addWidget(self.lst, 1)
        for k, name in dead.items():
            it = QListWidgetItem(name); it.setData(Qt.UserRole, k); self.lst.addItem(it)
        if not dead: lay.addWidget(QLabel("Nothing is hidden right now."))
        row = QHBoxLayout(); b1 = QPushButton("Restore selected"); b2 = QPushButton("Restore all"); row.addWidget(b1); row.addWidget(b2); row.addStretch(); lay.addLayout(row)
        b1.clicked.connect(lambda: (setattr(self, "restore_keys", [i.data(Qt.UserRole) for i in self.lst.selectedItems()]), self.accept()))
        b2.clicked.connect(lambda: (setattr(self, "restore_all", True), self.accept()))
        bb = QDialogButtonBox(QDialogButtonBox.Close); bb.rejected.connect(self.reject); bb.accepted.connect(self.reject); lay.addWidget(bb)


class ActivationDialog(QDialog):
    """No valid code: get a free trial code by email, enter a code, or buy one."""
    def __init__(self, lic, parent=None):
        super().__init__(parent)
        from .. import lic as L
        self.lic = lic; self.setWindowTitle("91 TV"); self.setMinimumWidth(520)
        lay = QVBoxLayout(self); lay.setSpacing(10)
        t = QLabel("Activate 91 TV"); t.setObjectName("h1"); lay.addWidget(t)
        self.msg = QLabel(lic.message()); self.msg.setWordWrap(True); self.msg.setObjectName("muted"); lay.addWidget(self.msg)
        if not self.msg.text():
            self.msg.setText("Get a free %d-day trial code by email (no card), or enter a code you bought." % L.TRIAL_DAYS)
        b_try = QPushButton("Get free trial code"); b_try.clicked.connect(self._trial); lay.addWidget(b_try)
        sup = QLabel("No code, or a problem? Email ninetyonetv.support@gmail.com"); sup.setObjectName("muted"); sup.setWordWrap(True); lay.addWidget(sup)
        lay.addWidget(QLabel("Have a code?"))
        self.code = QLineEdit(); self.code.setPlaceholderText("Paste your activation code"); lay.addWidget(self.code)
        self.status = QLabel(""); self.status.setWordWrap(True); lay.addWidget(self.status)
        row = QHBoxLayout()
        self.b_act = QPushButton("Activate"); self.b_act.clicked.connect(self._activate)
        b_buy = QPushButton("Buy a code"); b_buy.clicked.connect(self._buy)
        b_quit = QPushButton("Quit"); b_quit.clicked.connect(self.reject)
        row.addWidget(self.b_act); row.addWidget(b_buy); row.addStretch(); row.addWidget(b_quit); lay.addLayout(row)
        if lic.has_key():
            b_chk = QPushButton("Check again"); b_chk.clicked.connect(self._check); row.insertWidget(2, b_chk)

    def _trial(self):
        from PySide6.QtCore import QUrl; from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl("https://ninetyonetv.com/trial/")); self.status.setText("Enter your email on the page that opened. The code arrives in your inbox. Paste it below.")

    def _activate(self):
        self.status.setText("Checking..."); self.b_act.setEnabled(False)
        from PySide6.QtWidgets import QApplication; QApplication.processEvents()
        r = self.lic.activate(self.code.text()); self.b_act.setEnabled(True)
        if r is None: self.accept()
        else: self.status.setText(r)

    def _check(self):
        self.status.setText("Checking..."); from PySide6.QtWidgets import QApplication; QApplication.processEvents()
        if self.lic.refresh() and self.lic.licensed(): self.accept()
        else: self.status.setText(self.lic.message() or "Not valid yet.")

    def _buy(self):
        from PySide6.QtGui import QDesktopServices; from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl("https://ninetyonetv.com/#pricing"))
