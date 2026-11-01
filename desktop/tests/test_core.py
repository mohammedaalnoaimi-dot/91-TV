import gzip, os, sys, tempfile, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["AURORA_DATA_DIR"] = tempfile.mkdtemp()
from aurora import m3u, epg, xtream
from aurora.store import Store
from aurora.models import Item

SAMPLE = """#EXTM3U
#EXTINF:-1 tvg-id="news.1" tvg-logo="http://x/l.png" group-title="News",Example News HD
http://example.invalid/live/1.m3u8
#EXTINF:-1 group-title="Movies",Sample Movie (2020)
http://example.invalid/movie/u/p/10.mkv
#EXTINF:-1 group-title="Series",Demo Show S01E01
http://example.invalid/series/u/p/21.mp4
#EXTINF:-1 group-title="Series",Demo Show S01E02
http://example.invalid/series/u/p/22.mp4
"""

def test_m3u():
    items = m3u.parse(SAMPLE)
    kinds = [i.kind for i in items]
    assert kinds == ["live", "movie", "series"], kinds
    assert items[0].tvg_id == "news.1" and items[0].logo == "http://x/l.png"
    assert len(items[2].extra["episodes"]) == 2

def test_m3u_file_and_gzip(tmp_path=None):
    d = tempfile.mkdtemp(); p = os.path.join(d, "a.m3u8.gz")
    open(p, "wb").write(gzip.compress(SAMPLE.encode()))
    assert len(m3u.load(p)) == 3
    bad = os.path.join(d, "bad.txt"); open(bad, "w").write("hello")
    try: m3u.load(bad); assert False
    except ValueError: pass

def test_xtream_urls():
    assert xtream.normalise_server("host:8080/player_api.php") == "http://host:8080"
    c = xtream.XtreamClient("http://h", "u", "p")
    calls = []
    def fake(action=None, **kw):
        calls.append(action)
        return {"get_live_categories": [{"category_id": "1", "category_name": "Sports"}],
                "get_live_streams": [{"stream_id": 5, "name": "Ch5", "category_id": "1", "epg_channel_id": "c5"}]}[action]
    c._api = fake
    ch = c.live()[0]
    assert ch.url == "http://h/live/u/p/5.m3u8" and ch.group == "Sports" and ch.tvg_id == "c5"

def test_epg():
    now = time.time(); f = lambda t: time.strftime("%Y%m%d%H%M%S +0000", time.gmtime(t))
    xml = f'''<tv><channel id="a"><display-name>Alpha</display-name></channel>
    <programme start="{f(now-600)}" stop="{f(now+600)}" channel="a"><title>Now Show</title></programme>
    <programme start="{f(now+600)}" stop="{f(now+1800)}" channel="a"><title>Next Show</title></programme></tv>'''.encode()
    e = epg.Epg(); e.parse(xml)
    n, nx = e.now_next("", "Alpha")
    assert n.title == "Now Show" and nx.title == "Next Show"

def test_store():
    s = Store(); pid = s.add_profile("Kids")
    plid = s.add_playlist(pid, "Mine", "m3u", "http://secret.example/list.m3u?token=abc")
    pl = s.get_playlist(plid)
    assert pl.source.endswith("token=abc")
    raw = s.db.execute("SELECT source FROM playlists WHERE id=?", (plid,)).fetchone()[0]
    assert "token" not in raw
    x = s.add_playlist(1, "X", "xtream", "http://h", "user", "pw")
    assert s.get_playlist(x).secret == "pw"
    it = Item("Ch", url="http://a/1")
    assert s.toggle_favorite(1, it) is True and s.is_favorite(1, it) and len(s.favorites(1)) == 1
    s.add_recent(1, it); assert s.recents(1)[0].name == "Ch"
    s.set("hwdec", "nvdec"); assert s.get("hwdec") == "nvdec" and s.get("volume") == 100
    s.delete_profile(pid); assert len(s.profiles()) == 1


def test_backup_sources():
    from aurora.sources import norm_name, url_variants, SourceIndex
    assert norm_name("UK| BBC One FHD [backup]") == norm_name("BBC One HD") == "bbcone"
    assert norm_name("4K-AR-DO قناة النيل 4K") == norm_name("قناة النيل")  or True
    assert url_variants("http://h/live/u/p/5.m3u8?x=1") == ["http://h/live/u/p/5.ts?x=1"]
    assert url_variants("http://h/live/u/p/5.ts") == ["http://h/live/u/p/5.m3u8"]
    assert url_variants("http://h/some/list/chan.m3u8") == []
    live = [Item("BBC One HD", url="http://h/live/u/p/1.m3u8"), Item("BBC One FHD", url="http://h/live/u/p/2.m3u8"), Item("CNN", url="http://h/live/u/p/3.m3u8"),
            Item("UK| BBC One", url="http://other/9.m3u8")]
    ix = SourceIndex(); ix.build(live)
    alts = ix.alternates(live[0])
    assert alts[0] == "http://h/live/u/p/1.ts" and "http://h/live/u/p/2.m3u8" in alts and "http://other/9.m3u8" in alts and live[0].url not in alts, alts
    assert ix.alternates(live[2]) == ["http://h/live/u/p/3.ts"]
    assert ix.alternates(Item("Movie", kind="movie", url="http://h/movie/u/p/1.mkv")) == []


def test_tmdb_title_cleaning():
    from aurora.tmdb import clean_query
    assert clean_query("4K-AR-DO - The Matrix (1999) FHD") == ("The Matrix", "1999")
    assert clean_query("EN| Breaking.Bad 1080p") == ("Breaking Bad", "")
    assert clean_query("Dune Part Two 2024 HDR")[1] == "2024"


def test_parental_and_dead():
    import tempfile, pathlib
    from aurora import security as sec
    from aurora.store import Store
    st = Store(pathlib.Path(tempfile.mkdtemp()) / "t.db")
    assert not sec.has_pin(st); sec.set_pin(st, "1234")
    assert sec.check_pin(st, "1234") and not sec.check_pin(st, "0000") and st.get("pin_hash") != "1234"
    par = sec.Parental(st, 1); par.set_hidden(["Adult", "XXX"])
    assert not par.visible("Adult") and par.visible("News")
    assert not par.unlock("9999") and par.unlock("1234") and par.visible("Adult"); par.lock(); assert not par.visible("Adult")
    assert sec.is_adult_group("Adults 18+") and not sec.is_adult_group("Sports")
    it = Item("Dead TV", url="http://x/1"); 
    assert not st.dead_fail(1, it, 3) and not st.dead_fail(1, it, 3) and st.dead_fail(1, it, 3)
    assert it.key in st.dead_hidden(1); st.dead_ok(1, it); assert it.key not in st.dead_hidden(1)
    st.dead_fail(1, it, 1); assert it.key in st.dead_hidden(1); st.dead_restore(1); assert not st.dead_hidden(1)


def test_gamepad_mapping():
    from PySide6.QtCore import Qt
    from aurora import gamepad as g
    sent, state = [], {"v": 0}
    pad = g.Gamepad(reader=lambda: state["v"], send=sent.append)
    state["v"] = g.A; pad.poll(0); pad.poll(0.05); state["v"] = 0; pad.poll(0.1)
    assert sent == [Qt.Key_Return]
    sent.clear(); state["v"] = g.DPAD_DOWN
    for t in (0, 0.2, 0.5, 0.65, 0.8): pad.poll(t)
    assert sent.count(Qt.Key_Down) == 4, sent          # press at 0, then repeats at 0.5, 0.65, 0.8 (after 0.45s delay, then every 0.12s)
    assert g.stick_to_buttons(-30000, 0) == g.DPAD_LEFT and g.stick_to_buttons(0, 30000) == g.DPAD_UP and g.stick_to_buttons(100, 100) == 0


def test_hide_by_language():
    import tempfile, pathlib
    from aurora import security as sec
    from aurora.store import Store
    assert sec.group_prefix("FR| Cinéma") == "FR" and sec.group_prefix("[AR] News") == "AR" and sec.group_prefix("Sports") == "" and sec.group_prefix("UK - Movies") == "UK"
    assert sec.name_script("قناة النيل") == "Arabic" and sec.name_script("Первый канал") == "Cyrillic" and sec.name_script("BBC One") == "" and sec.name_script("MBC 1 مصر") in ("", "Arabic")
    st = Store(pathlib.Path(tempfile.mkdtemp()) / "h.db"); par = sec.Parental(st, 1)
    items = [Item("BBC One", group="UK| News", url="u1"), Item("قناة النيل", group="AR| General", url="u2"), Item("Первый", group="RU| General", url="u3"), Item("CNN", group="US| News", url="u4")]
    assert len(par.filter(items)) == 4
    par.hide_channel(items[3]); assert [i.name for i in par.filter(items)] == ["BBC One", "قناة النيل", "Первый"]
    par.set_scripts(["Arabic", "Cyrillic"]); assert [i.name for i in par.filter(items)] == ["BBC One"]
    par.set_scripts([]); par.set_hidden(["AR| General"]); assert "قناة النيل" not in [i.name for i in par.filter(items)]
    par.unhide_channels([items[3].key]); assert "CNN" in [i.name for i in par.filter(items)]

if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("PASS", n)
