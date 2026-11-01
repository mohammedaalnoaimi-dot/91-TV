"""Prayer times page (Bahrain) + the small chip that lives in the top bar."""
from __future__ import annotations
from PySide6.QtCore import Qt, QTimer
import threading
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QDialog, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
from .. import prayer
from . import theme


class MonthDialog(QDialog):
    got = Signal(object)

    def __init__(self, parent, method):
        super().__init__(parent); self.setWindowTitle("Monthly prayer timetable · Manama"); self.resize(900, 760); self.method = method
        l = QVBoxLayout(self); self.head = QLabel("Loading…"); self.head.setObjectName("h2"); l.addWidget(self.head)
        self.tbl = QTableWidget(0, 8); self.tbl.setHorizontalHeaderLabels(["Date", "Hijri"] + prayer.ORDER); self.tbl.verticalHeader().hide()
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tbl.setSelectionMode(QAbstractItemView.NoSelection)
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); l.addWidget(self.tbl, 1)
        self.got.connect(self.fill); n = prayer.now()
        threading.Thread(target=lambda: self.got.emit(prayer.fetch_month(method, n.year, n.month)), daemon=True).start()

    def fill(self, rows):
        if not rows: self.head.setText("Could not load the timetable (needs the internet the first time)."); return
        today = prayer.day_key(prayer.now()); self.head.setText(prayer.now().strftime("%B %Y").upper()); self.tbl.setRowCount(len(rows))
        for r, (dk, hd, hm, t) in enumerate(rows):
            vals = [prayer.datetime.strptime(dk, "%d-%m-%Y").strftime("%a %d %b"), (f"Ramadan {hd}" if hm == 9 else hd)] + [t[n] for n in prayer.ORDER]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v); it.setTextAlignment(Qt.AlignCenter if c > 1 else Qt.AlignVCenter | Qt.AlignLeft)
                if dk == today: it.setBackground(QColor(theme.RED)); it.setForeground(QColor("white"))
                self.tbl.setItem(r, c, it)
        if today in [x[0] for x in rows]: self.tbl.scrollToItem(self.tbl.item([x[0] for x in rows].index(today), 0))


class PrayerPage(QWidget):
    def __init__(self, times: prayer.Times, store):
        super().__init__()
        self.times, self.store = times, store
        lay = QVBoxLayout(self); lay.setContentsMargins(60, 40, 60, 30); lay.setSpacing(6)
        eb = QLabel("PRAYER TIMES · MANAMA, BAHRAIN"); eb.setObjectName("eyebrow"); lay.addWidget(eb)
        self.next_name = QLabel("—"); self.next_name.setObjectName("display"); self.next_name.setStyleSheet("font-size:54px; background:transparent;"); lay.addWidget(self.next_name)
        self.count = QLabel(""); self.count.setStyleSheet(f"font-size:30px; color:{theme.GOLD}; background:transparent;"); lay.addWidget(self.count)
        self.hijri = QLabel(""); self.hijri.setObjectName("muted"); lay.addWidget(self.hijri)
        self.ram_t = QLabel(""); self.ram_t.setStyleSheet(f"color:{theme.RED}; font-weight:700; letter-spacing:3px; background:transparent;")
        self.ram_c = QLabel(""); self.ram_c.setStyleSheet(f"font-size:26px; color:{theme.TEXT}; background:transparent;"); self.ram_s = QLabel(""); self.ram_s.setObjectName("muted")
        for w in (self.ram_t, self.ram_c, self.ram_s): lay.addWidget(w); w.hide()
        self.b_month = QPushButton("Monthly timetable"); self.b_month.setObjectName("ghost"); self.b_month.setCursor(Qt.PointingHandCursor); self.b_month.clicked.connect(self.open_month)
        row = QHBoxLayout(); row.addWidget(self.b_month); row.addStretch(); lay.addSpacing(6); lay.addLayout(row); lay.addSpacing(10)
        self.rows = {}
        box = QFrame(); box.setStyleSheet("QFrame{background:rgba(235,221,196,0.04); border:1px solid rgba(235,221,196,0.12);} QLabel{border:none; background:transparent;}")
        bl = QVBoxLayout(box); bl.setContentsMargins(24, 14, 24, 14); bl.setSpacing(2)
        for n in prayer.ORDER:
            r = QHBoxLayout(); a = QLabel(n); a.setStyleSheet("font-size:20px;"); ar = QLabel(prayer.ARABIC[n]); ar.setStyleSheet(f"font-size:20px; color:{theme.MUTED};"); t = QLabel("--:--"); t.setStyleSheet("font-size:22px; font-weight:600;")
            a.setMinimumWidth(180); r.addWidget(a); r.addWidget(ar); r.addStretch(); r.addWidget(t); bl.addLayout(r); self.rows[n] = (a, t)
        lay.addWidget(box); lay.addSpacing(12)
        self.note = QLabel(""); self.note.setObjectName("muted"); self.note.setWordWrap(True); lay.addWidget(self.note); lay.addStretch()
        self.tick_t = QTimer(self); self.tick_t.setInterval(1000); self.tick_t.timeout.connect(self.tick)

    def open_month(self):
        MonthDialog(self.window(), int(self.store.get("pt_method") or 8)).exec()

    def showEvent(self, e):
        self.times.refresh(); self.tick_t.start(); self.tick(); super().showEvent(e)

    def hideEvent(self, e):
        self.tick_t.stop(); super().hideEvent(e)

    def tick(self):
        d = self.times.today; nx = self.times.next()
        self.note.setText(f"Method: {prayer.method_name(self.store.get('pt_method'))} (change in Settings). Times come from aladhan.com and are cached on this PC; Bahrain time (UTC+3).")
        if not d:
            self.next_name.setText("Loading…"); self.count.setText("Needs internet the first time"); return
        self.hijri.setText(d.hijri)
        for n, (a, t) in self.rows.items():
            t.setText(d.times[n]); on = nx and nx[0] == n and nx[1].date() == prayer.now().date()
            a.setStyleSheet(f"font-size:20px; color:{theme.RED if on else theme.TEXT};"); t.setStyleSheet(f"font-size:22px; font-weight:600; color:{theme.RED if on else theme.TEXT};")
        if prayer.ramadan(d):
            n = prayer.now(); fajr = d.at("Fajr"); mag = d.at("Maghrib")
            if n < fajr: t, c, s = "SUHOOR ENDS (FAJR)", fajr - n, fajr.strftime("%H:%M")
            elif n < mag: t, c, s = "IFTAR (MAGHRIB)", mag - n, mag.strftime("%H:%M") + "  ·  the fast ends then"
            elif self.times.tomorrow: f2 = self.times.tomorrow.at("Fajr"); t, c, s = "SUHOOR ENDS (FAJR) TOMORROW", f2 - n, f2.strftime("%H:%M")
            else: t = c = s = None
            if t: self.ram_t.setText("RAMADAN MUBARAK  ·  " + t); self.ram_c.setText("in " + prayer.hms(c)); self.ram_s.setText("at " + s)
            for w in (self.ram_t, self.ram_c, self.ram_s): w.setVisible(bool(t))
        else:
            for w in (self.ram_t, self.ram_c, self.ram_s): w.hide()
        if nx:
            self.next_name.setText(f"{nx[0]}  ·  {prayer.ARABIC[nx[0]]}"); self.count.setText(f"{nx[1].strftime('%H:%M')}   —   in {prayer.hms(nx[1] - prayer.now())}")
