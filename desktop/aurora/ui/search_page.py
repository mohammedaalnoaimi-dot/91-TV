"""Global search (Ctrl+K or '/'): channels, movies, series and upcoming programmes in one list."""
from __future__ import annotations
import time
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton
from .backdrop import Backdrop
from ..models import Item
from .. import smart
from . import widgets

CAP = 12            # results per section


def _hm(t): return time.strftime("%a %H:%M", time.localtime(t))


class SearchPage(Backdrop):
    open_item = Signal(object)                 # channel / movie / series
    open_programme = Signal(object, object)    # channel Item, Programme

    def __init__(self, loader, get_lists, epg):
        super().__init__()
        self.get_lists, self.epg = get_lists, epg; self._idx = None; self._rows: list = []
        lay = QVBoxLayout(self); lay.setContentsMargins(60, 36, 60, 24); lay.setSpacing(14)
        eb = QLabel("SEARCH"); eb.setObjectName("eyebrow"); lay.addWidget(eb)
        self.box = QLineEdit(); self.box.setObjectName("search"); self.box.setPlaceholderText("Search channels, movies, series and programmes…"); self.box.setClearButtonEnabled(True); self.box.setMinimumHeight(52)
        self.box.setStyleSheet("font-size:20px;"); lay.addWidget(self.box)
        self.hint = QLabel("Type to search. ↑ ↓ to move, Enter to open, Esc to go back."); self.hint.setObjectName("muted"); lay.addWidget(self.hint)
        self.list = QListWidget(); self.list.setObjectName("cats"); self.list.setSpacing(2); lay.addWidget(self.list, 1)
        self.t = QTimer(self); self.t.setSingleShot(True); self.t.setInterval(160); self.t.timeout.connect(self.run)
        self.box.textChanged.connect(lambda _t: self.t.start()); self.box.returnPressed.connect(self.open_current)
        self.list.itemActivated.connect(lambda _i: self.open_current()); self.list.itemClicked.connect(lambda _i: self.open_current())

    def focus(self): self.box.setFocus(); self.box.selectAll()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Down, Qt.Key_Up):
            r = self.list.currentRow(); step = 1 if e.key() == Qt.Key_Down else -1; n = self.list.count(); r += step
            while 0 <= r < n and not (self.list.item(r).flags() & Qt.ItemIsSelectable): r += step
            if 0 <= r < n: self.list.setCurrentRow(r)
            e.accept(); return
        super().keyPressEvent(e)

    def search(self, q: str):
        """Returns [(section, label, sub, payload)]. Pure function (used by tests)."""
        q = q.strip().lower(); out = []
        if len(q) < 2: return out
        live, movies, series = self.get_lists()
        for section, items in (("Channels", live), ("Movies", movies), ("Series", series)):
            for it in smart.rank(items, q, CAP):
                rt = widgets.RATE(it) if it.kind in ("movie", "series") else ""
                out.append((section, it.name, "   ·   ".join(x for x in (it.group, rt) if x), ("item", it)))
        # programmes (upcoming only), matched to a visible channel
        by_id = {}
        for it in live: by_id.setdefault(it.tvg_id, it); by_id.setdefault(it.name.strip().lower(), it)
        name_of = {c: n for n, c in self.epg.names.items()}; now = time.time(); progs = []
        for cid, plist in self.epg.by_channel.items():
            if cid.startswith("x:"): continue
            ch = by_id.get(cid) or by_id.get(name_of.get(cid, ""))
            if not ch: continue
            for pr in plist:
                if pr.stop > now and q in (pr.title or "").lower(): progs.append((pr.start, ch, pr))
        progs.sort(key=lambda x: x[0])
        for start, ch, pr in progs[:CAP * 2]: out.append(("Programmes", pr.title, f"{ch.name}  ·  {_hm(pr.start)}", ("prog", ch, pr)))
        return out

    def run(self):
        res = self.search(self.box.text()); self.list.clear(); self._rows = []
        if not res:
            self.hint.setText("Nothing found." if len(self.box.text().strip()) >= 2 else "Type at least 2 letters."); return
        last = None
        for section, label, sub, payload in res:
            if section != last:
                h = QListWidgetItem(section.upper()); h.setFlags(Qt.NoItemFlags); f = h.font(); f.setBold(True); f.setPixelSize(11); h.setFont(f); h.setForeground(Qt.gray); self.list.addItem(h); last = section
            it = QListWidgetItem(f"{label}" + (f"      {sub}" if sub else "")); it.setData(Qt.UserRole, payload); self.list.addItem(it)
        self.hint.setText(f"{len(res)} results"); first = next((i for i in range(self.list.count()) if self.list.item(i).flags() & Qt.ItemIsSelectable), -1)
        if first >= 0: self.list.setCurrentRow(first)

    def open_current(self):
        it = self.list.currentItem()
        if not it or not it.data(Qt.UserRole): return
        p = it.data(Qt.UserRole)
        if p[0] == "item": self.open_item.emit(p[1])
        else: self.open_programme.emit(p[1], p[2])
