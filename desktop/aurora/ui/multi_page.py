"""Multi-view: 2-4 live channels on one screen (big match nights). Click a tile to hear it; the others stay muted."""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QFrame, QDialog, QLineEdit, QListWidget, QListWidgetItem)
from .preview import PreviewPane
from .. import smart
from . import theme


class PickDialog(QDialog):
    def __init__(self, parent, items):
        super().__init__(parent); self.setWindowTitle("Choose a channel"); self.items = items; self.chosen = None; self.resize(520, 560)
        l = QVBoxLayout(self); self.q = QLineEdit(); self.q.setPlaceholderText("Type a channel name…"); l.addWidget(self.q); self.lst = QListWidget(); l.addWidget(self.lst, 1)
        self.q.textChanged.connect(self.fill); self.lst.itemActivated.connect(self.pick); self.lst.itemClicked.connect(self.pick); self.fill(""); self.q.setFocus()

    def fill(self, t):
        self.lst.clear(); res = smart.rank(self.items, t, 200) if len(t.strip()) >= 1 else self.items[:200]
        for it in res: w = QListWidgetItem(it.name); w.setData(Qt.UserRole, it); self.lst.addItem(w)

    def pick(self, w): self.chosen = w.data(Qt.UserRole); self.accept()


class Tile(QFrame):
    def __init__(self, idx, store, owner):
        super().__init__(); self.idx, self.owner = idx, owner; self.item = None
        l = QVBoxLayout(self); l.setContentsMargins(0, 0, 0, 0); l.setSpacing(4)
        self.pane = PreviewPane(store); self.pane.muted = True; l.addWidget(self.pane)
        r = QHBoxLayout(); self.cap = QLabel("Empty"); self.cap.setObjectName("muted"); self.b_pick = QPushButton("Choose…"); self.b_full = QPushButton("Full screen"); self.b_clear = QPushButton("✕")
        for b in (self.b_pick, self.b_full, self.b_clear): b.setObjectName("ghostsm"); b.setCursor(Qt.PointingHandCursor)
        self.b_snd = QPushButton("🔇"); self.b_snd.setObjectName("ghostsm"); self.b_snd.setCursor(Qt.PointingHandCursor)
        r.addWidget(self.cap, 1); r.addWidget(self.b_snd); r.addWidget(self.b_pick); r.addWidget(self.b_full); r.addWidget(self.b_clear); l.addLayout(r)
        self.b_pick.clicked.connect(lambda: owner.pick(self)); self.b_full.clicked.connect(lambda: self.item and owner.open_full.emit(self.item))
        self.b_clear.clicked.connect(lambda: owner.set_tile(self, None)); self.b_snd.clicked.connect(lambda: owner.listen(self))

    def set_sound(self, on):
        self.pane.muted = not on
        if self.pane.player: self.pane.player.set_mute(not on)
        self.b_snd.setText("🔊" if on else "🔇")
        self.setStyleSheet(f"Tile {{ border: 2px solid {theme.RED if on else 'transparent'}; border-radius: 4px; }}")


class MultiPage(QWidget):
    open_full = Signal(object)

    def __init__(self, store, get_live, alternates):
        super().__init__(); self.store, self.get_live = store, get_live; self.n = 4; self.listening = None
        lay = QVBoxLayout(self); lay.setContentsMargins(36, 24, 36, 16); lay.setSpacing(8)
        top = QHBoxLayout(); col = QVBoxLayout(); eb = QLabel("MULTI-VIEW"); eb.setObjectName("eyebrow"); h = QLabel("Watch several channels at once"); h.setObjectName("display"); col.addWidget(eb); col.addWidget(h); top.addLayout(col); top.addStretch()
        self.btns = []
        for n in (2, 3, 4):
            b = QPushButton(f"{n} screens"); b.setCheckable(True); b.setObjectName("who"); b.clicked.connect(lambda _c=False, n=n: self.set_count(n)); self.btns.append(b); top.addWidget(b)
        lay.addLayout(top)
        self.grid_host = QWidget(); self.grid = QGridLayout(self.grid_host); self.grid.setSpacing(10); self.grid.setContentsMargins(0, 0, 0, 0); lay.addWidget(self.grid_host, 1)
        self.tiles = [Tile(i, store, self) for i in range(4)]
        for t in self.tiles: t.pane.alternates = alternates
        self.note = QLabel("Every screen opens its own stream, so your provider must allow that many connections at once. Only the screen with the red frame plays sound."); self.note.setObjectName("muted"); self.note.setWordWrap(True); lay.addWidget(self.note)
        self.set_count(4); self.listen(self.tiles[0])

    def set_count(self, n):
        self.n = n
        for b, k in zip(self.btns, (2, 3, 4)): b.setChecked(k == n)
        for t in self.tiles: self.grid.removeWidget(t); t.hide()
        cols = 2; rows = 1 if n == 2 else 2
        for i in range(n): self.grid.addWidget(self.tiles[i], i // cols, i % cols); self.tiles[i].show()
        for t in self.tiles[n:]: t.pane.release()
        self._size()

    def _size(self):
        rows = 1 if self.n == 2 else 2; avail_w = self.grid_host.width() - 10; avail_h = self.grid_host.height() - 10 * rows
        w = int(max(200, min(avail_w / 2, (avail_h / rows - 34) * 16 / 9)))
        for t in self.tiles: t.pane.setFixedWidth(w)

    def resizeEvent(self, e): self._size(); super().resizeEvent(e)

    def showEvent(self, e):
        self._size()
        for t in self.tiles[:self.n]:
            if t.item: t.pane.request(t.item)
        super().showEvent(e)

    def hideEvent(self, e):
        for t in self.tiles: t.pane.release()
        super().hideEvent(e)

    def listen(self, tile):
        self.listening = tile
        for t in self.tiles: t.set_sound(t is tile)

    def pick(self, tile):
        d = PickDialog(self, self.get_live())
        if d.exec() and d.chosen: self.set_tile(tile, d.chosen)

    def set_tile(self, tile, it):
        tile.item = it; tile.cap.setText(it.name if it else "Empty")
        if it: tile.pane.force = True; tile.pane.request(it)
        else: tile.pane.request(None); tile.pane.stop()

    def add_channel(self, it):
        """Put a channel in the first empty screen (used by the right-click menu)."""
        for t in self.tiles[:self.n]:
            if t.item is None: self.set_tile(t, it); return True
        self.set_tile(self.tiles[self.n - 1], it); return False
