"""Renders the UI offscreen with demo data (dev-time visual check)."""
import os, sys, tempfile, time
os.environ["QT_QPA_PLATFORM"] = "offscreen"; os.environ["AURORA_DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6.QtWidgets import QApplication
from aurora.store import Store
from aurora.models import Item
from aurora.ui import theme
from aurora.ui.main_window import MainWindow
app = QApplication([]); app.setStyleSheet(theme.QSS)
w = MainWindow(Store(), quiet=True); w.resize(1600, 900); w.show()
P = lambda n: f"http://localhost:8765/p{n % 24}.jpg"
live = [Item(f"Demo Channel {i}", "live", f"http://x/{i}", ["News", "Sports", "Kids"][i % 3], P(i), tvg_id=f"c{i}") for i in range(30)]
movies = [Item(f"Sample Movie {i}", "movie", f"http://x/m{i}", ["Action", "Drama"][i % 2], P(i * 2), plot="A demo description for the featured title banner.", year="2024", rating="7.8") for i in range(40)]
series = [Item(f"Demo Series {i}", "series", "", "Series", P(i * 2 + 2), ext_id=str(i)) for i in range(30)]
for _ in range(20): app.processEvents()
w.live, w.movies, w.series = live, movies, series; w.distribute()
def shot(name, idx):
    w.go(idx); t = time.time()
    while time.time() - t < 1.5: app.processEvents()
    w.grab().save(f"/tmp/claude-0/-home-claude/7ad43a77-dec5-570e-94e0-90cf9e6083ae/scratchpad/shot_{name}.png"); print("saved", name)
shot("home", 0); shot("live", 1); shot("movies", 2); shot("settings", 5)
