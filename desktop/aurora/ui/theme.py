BG = "#070506"; PANEL = "#0e080a"; CARD = "#18110f"; TEXT = "#EBDDC4"; MUTED = "#a8977e"; GOLD = "#d7b88a"; SOFT = "#cdbb9e"; INK = "#160B0D"
DISPLAY = "Cinzel"; BODY = "Jost"; ITALIC = "EB Garamond"
ACCENTS = {"rose": (201, 71, 92), "red": (224, 38, 45), "blue": (46, 125, 255), "purple": (150, 92, 255), "teal": (20, 184, 166), "gold": (232, 164, 30)}
TENFOOT = False
ACC = ACCENTS["rose"]; RED = "#c9475c"; RED_DIM = "#7e2c3a"; RED_HI = "#d9667a"; ACCENT_NAME = "rose"


def _hex(c): return "#%02x%02x%02x" % tuple(int(max(0, min(255, v))) for v in c)


def set_accent(name: str):
    """Switch the accent colour (module-level so painters/stylesheets read it dynamically). Call before building the UI, or restyle after."""
    global ACC, RED, RED_DIM, RED_HI, ACCENT_NAME
    ACCENT_NAME = name if name in ACCENTS else "rose"; ACC = ACCENTS[ACCENT_NAME]
    RED = _hex(ACC); RED_DIM = _hex([v * 0.62 for v in ACC]); RED_HI = _hex([v + (255 - v) * 0.18 for v in ACC])


def acc(s: str) -> str:
    """Recolour a stylesheet/markup string written with the default red."""
    return (s.replace("#e0262d", RED).replace("#8f1a1f", RED_DIM).replace("#c9475c", RED).replace("224,38,45", "%d,%d,%d" % ACC).replace("224, 38, 45", "%d, %d, %d" % ACC))


def build() -> str:
    return f"""
* {{ font-family: '{BODY}', 'Segoe UI Variable Display', 'Segoe UI', sans-serif; color: {TEXT}; }}
QLabel#h1, QLabel#h2, QLabel#display, QLabel#brand, QLabel#eyebrow, QPushButton#primary, QPushButton#ghost, QPushButton#topnav, QLabel#clock, QLabel#chipname {{ font-family: '{DISPLAY}', 'Georgia', serif; }}
QFrame#chrome {{ background: {BG}; border-bottom: 1px solid rgba(235,221,196,0.12); }}
QPushButton#topnav {{ background: transparent; border: none; border-bottom: 2px solid transparent; border-radius: 0; padding: 9px 14px; color: {MUTED}; font-size: 13px; }}
QPushButton#topnav:hover {{ color: {TEXT}; }}
QPushButton#topnav:checked {{ color: {TEXT}; border-bottom: 2px solid {RED}; }}
QPushButton#topnav:focus {{ color: {TEXT}; border-bottom: 3px solid {RED}; }}
QPushButton#who {{ background: rgba(235,221,196,0.07); border: 1px solid rgba(235,221,196,0.22); border-radius: 2px; padding: 4px 12px; font-size: 11px; color: {GOLD}; }}
QPushButton#who:hover {{ background: rgba(235,221,196,0.14); }}
QMainWindow, QWidget#root, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {BG}; }}
QWidget {{ font-size: 14px; }}
QFrame#sidebar {{ background: {PANEL}; border-right: 1px solid #1b1b20; }}
QLabel#brand {{ font-size: 20px; font-weight: 800; letter-spacing: 4px; color: {TEXT}; padding: 18px 20px 10px 20px; }}
QLabel#brand b {{ color: {RED}; }}
QPushButton#nav {{ text-align: left; padding: 12px 22px; border: none; border-left: 3px solid transparent; background: transparent; color: {MUTED}; font-size: 15px; border-radius: 0; }}
QPushButton#nav:hover {{ color: {TEXT}; background: #121216; }}
QPushButton#nav:checked {{ color: {TEXT}; background: #15151a; border-left: 3px solid {RED}; font-weight: 600; }}
QLabel#h1 {{ font-size: 26px; font-weight: 700; }}
QLabel#h2 {{ font-size: 18px; font-weight: 650; padding: 4px 0; }}
QLabel#muted {{ color: {MUTED}; }}
QPushButton {{ background: #1c1412; border: 1px solid #2f2420; border-radius: 3px; padding: 8px 16px; }}
QPushButton:hover {{ background: #271c19; }}
QPushButton:pressed {{ background: #2f2f38; }}
QPushButton#primary {{ background: {TEXT}; border: 1px solid {TEXT}; font-weight: 700; padding: 11px 26px; border-radius: 2px; color: {INK}; font-size: 14px; }}
QPushButton#primary:hover {{ background: #ffffff; }}
QPushButton#ghost {{ background: rgba(20,10,12,0.55); border: 1px solid #7a6250; padding: 11px 24px; border-radius: 2px; font-size: 14px; }}
QPushButton#ghost:hover {{ background: rgba(235,221,196,0.16); }}
QPushButton#icon {{ padding: 6px 12px; min-width: 28px; font-size: 16px; }}
QLineEdit, QComboBox, QSpinBox {{ background: {CARD}; border: 1px solid #26262c; border-radius: 10px; padding: 8px 12px; selection-background-color: {RED}; }}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {RED}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{ background: {CARD}; border: 1px solid #2a2a31; selection-background-color: {RED_DIM}; outline: none; }}
QListView, QListWidget, QTreeWidget {{ background: transparent; border: none; outline: none; }}
QListWidget#cats::item {{ padding: 10px 14px; border-radius: 10px; color: {MUTED}; }}
QListWidget#cats::item:selected {{ background: #1a1a20; color: {TEXT}; border-left: 3px solid {RED}; }}
QListWidget#cats::item:hover {{ background: #121216; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #2b2b33; border-radius: 4px; min-height: 40px; }}
QScrollBar::handle:vertical:hover {{ background: {RED_DIM}; }}
QScrollBar:horizontal {{ height: 0px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QSlider::groove:horizontal {{ height: 4px; background: #2a2a31; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {RED}; border-radius: 2px; }}
QSlider::handle:horizontal {{ width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; background: {TEXT}; }}
QFrame#panel {{ background: {PANEL}; border: 1px solid #1b1b20; border-radius: 16px; }}
QFrame#controls {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 rgba(0,0,0,0), stop:0.45 rgba(0,0,0,150), stop:1 rgba(0,0,0,235)); border: none; }}
QFrame#controls[edge="top"] {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 rgba(0,0,0,225), stop:0.6 rgba(0,0,0,110), stop:1 rgba(0,0,0,0)); }}
QFrame#controls QLabel {{ background: transparent; }}
QLabel#ptitle {{ font-size: 21px; font-weight: 600; background: transparent; }}
QLabel#ptime {{ font-size: 15px; color: #e9e9ee; background: transparent; }}
QPushButton#ptext {{ background: transparent; border: none; color: #d9d9df; padding: 8px 12px; font-size: 14px; }}
QPushButton#ptext:hover, QPushButton#ptext:checked {{ color: white; background: rgba(255,255,255,0.12); border-radius: 4px; }}
QFrame#controls QSlider::groove:horizontal {{ height: 5px; background: rgba(255,255,255,0.28); border-radius: 2px; }}
QFrame#controls QSlider::sub-page:horizontal {{ background: {RED}; border-radius: 2px; }}
QFrame#controls QSlider::handle:horizontal {{ background: {RED}; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; }}
QFrame#controls QComboBox {{ background: rgba(255,255,255,0.10); border: none; border-radius: 4px; padding: 7px 12px; color: #f2f2f4; }}
QDialog, QMessageBox {{ background: #0e0e11; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid #3a3a42; background: {CARD}; }}
QCheckBox::indicator:checked {{ background: {RED}; border: 1px solid {RED}; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; padding: 10px 18px; color: {MUTED}; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {RED}; }}
QLabel#display {{ font-size: 34px; font-weight: 800; }}
QLabel#eyebrow {{ color: {RED}; font-size: 11px; font-weight: 800; letter-spacing: 3px; }}
QLineEdit#search {{ background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.09); border-radius: 22px; padding: 11px 20px; font-size: 14px; }}
QLineEdit#search:focus {{ border: 1px solid {RED}; background: rgba(255,255,255,0.07); }}
QFrame#glass {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 rgba(255,255,255,0.055), stop:1 rgba(255,255,255,0.018)); border: 1px solid rgba(255,255,255,0.08); border-radius: 24px; }}
QPushButton#ghostsm {{ background: rgba(255,255,255,0.07); border: none; border-radius: 14px; padding: 6px 14px; font-size: 12px; color: #c9c9d0; }}
QPushButton#ghostsm:hover {{ background: rgba(255,255,255,0.14); }}
QListWidget#cats {{ background: transparent; }}
QListWidget#cats::item {{ padding: 11px 16px; margin: 1px 0; border-radius: 12px; color: {MUTED}; font-size: 14px; }}
QFrame#controls[fs="true"] QPushButton {{ font-size: 17px; padding: 10px 18px; min-height: 30px; }}
QFrame#controls[fs="true"] QPushButton#icon {{ font-size: 20px; padding: 10px 16px; min-width: 40px; }}
QFrame#controls[fs="true"] QComboBox {{ font-size: 15px; padding: 9px 14px; min-height: 28px; }}
QFrame#controls[fs="true"] QLabel {{ font-size: 16px; }}
QFrame#controls[fs="true"] QSlider::groove:horizontal {{ height: 8px; border-radius: 4px; }}
QFrame#controls[fs="true"] QSlider::sub-page:horizontal {{ border-radius: 4px; }}
QFrame#controls[fs="true"] QSlider::handle:horizontal {{ width: 22px; height: 22px; margin: -8px 0; border-radius: 11px; }}
{"QPushButton:focus, QComboBox:focus, QCheckBox:focus { border: 2px solid " + RED + "; }" if TENFOOT else ""}
QToolTip {{ background: {CARD}; color: {TEXT}; border: 1px solid #2a2a31; }}
QMenu {{ background: {CARD}; border: 1px solid #2a2a31; padding: 6px; border-radius: 10px; }}
QMenu::item {{ padding: 8px 20px; border-radius: 6px; }}
QMenu::item:selected {{ background: {RED_DIM}; }}
"""


QSS = build()


def load_fonts():
    """Cinzel (headings), Jost (text) and EB Garamond italic ship in assets/fonts (all SIL OFL)."""
    from PySide6.QtGui import QFontDatabase
    from ..paths import asset
    for f in ("cinzel.ttf", "jost.ttf", "jost_medium.ttf", "garamond_italic.ttf"):
        p = asset("fonts/" + f)
        if p.exists(): QFontDatabase.addApplicationFont(str(p))
