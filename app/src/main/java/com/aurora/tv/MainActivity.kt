package com.aurora.tv

import android.app.Activity
import android.content.Context
import android.content.SharedPreferences
import android.content.res.Configuration
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.view.Gravity
import android.view.KeyEvent
import android.view.View
import android.view.ViewGroup
import android.view.ViewOutlineProvider
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.TrackSelectionOverride
import androidx.media3.exoplayer.DefaultLoadControl
import androidx.media3.exoplayer.audio.AudioCapabilities
import androidx.media3.exoplayer.audio.AudioSink
import androidx.media3.exoplayer.audio.DefaultAudioSink
import androidx.media3.datasource.DefaultDataSource
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.exoplayer.DefaultRenderersFactory
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.extractor.DefaultExtractorsFactory
import androidx.media3.extractor.ts.DefaultTsPayloadReaderFactory
import androidx.media3.ui.PlayerView
import androidx.recyclerview.widget.GridLayoutManager
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import org.json.JSONArray
import java.util.concurrent.Executors

class MainActivity : Activity() {
    private val ui = Handler(Looper.getMainLooper())
    private lateinit var prefs: SharedPreferences

    private var xt: Xtream? = null
    private var live: List<Item> = emptyList()
    private var movies: List<Item> = emptyList()
    private var series: List<Item> = emptyList()

    private var shell: View? = null
    private lateinit var content: FrameLayout
    private val sideItems = LinkedHashMap<String, TextView>()
    private var section = "home"
    private val pageStack = ArrayDeque<() -> Unit>()
    private var currentPage: (() -> Unit)? = null
    private var query = ""
    private var liveCat = 0
    private var lastLiveKey = ""
    private var catFor = HashMap<String, String?>()   // movie / series page -> selected category

    // player
    private var player: ExoPlayer? = null
    private var playerRoot: FrameLayout? = null
    private var playerView: PlayerView? = null
    private var titleView: TextView? = null
    private var zapList: List<Item> = emptyList()
    private var zapIndex = 0
    private var attempt = 0
    private var playing: Item? = null

    // live preview
    private var preview: ExoPlayer? = null
    private var previewAttempt = 0
    private var previewItem: Item? = null
    private val previewRun = Runnable { previewItem?.let { startPreview(it) } }
    private var panel: LivePanel? = null

    // EPG cache
    private val epgCache = HashMap<String, List<Prog>>()
    private val epgPool = Executors.newFixedThreadPool(3)

    class LivePanel(val video: PlayerView, val title: TextView, val cat: TextView, val nowLabel: TextView, val now: TextView, val time: TextView,
                    val bar: Bar, val next: LinearLayout, val fav: TextView)

    /** Lay out as if the screen were 1280 dp wide whatever the TV reports, so every TV gets the same proportions. */
    override fun attachBaseContext(base: Context) {
        val cfg = Configuration(base.resources.configuration)
        val w = maxOf(base.resources.displayMetrics.widthPixels, base.resources.displayMetrics.heightPixels)
        cfg.densityDpi = (160f * w / 1280f).toInt().coerceIn(120, 640)
        super.attachBaseContext(base.createConfigurationContext(cfg))
    }

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        prefs = getSharedPreferences("aurora", Context.MODE_PRIVATE)
        val old = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { t, e ->
            try { prefs.edit().putString("crash", android.util.Log.getStackTraceString(e).take(2500)).commit() } catch (x: Throwable) { }
            old?.uncaughtException(t, e)
        }
        val crash = prefs.getString("crash", "") ?: ""
        if (crash.isNotBlank()) { prefs.edit().remove("crash").apply(); showCrash(crash) } else begin()
    }

    private fun begin() {
        if (prefs.getString("server", "").isNullOrBlank() && prefs.getString("m3u", "").isNullOrBlank()) setupView() else startLoading()
    }

    private fun showCrash(text: String) {
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(BG); setPadding(dp(60), dp(30), dp(60), dp(20)) }
        col.addView(mkText("91 TV closed unexpectedly last time", 26f, RED, true))
        col.addView(mkText("Take a photo of this screen and send it, then press Continue.", 16f, GRAY).apply { setPadding(0, dp(6), 0, dp(10)) })
        val sv = ScrollView(this); sv.addView(mkText(text, 13f, Color.WHITE).apply { typeface = Typeface.MONOSPACE })
        col.addView(sv, LinearLayout.LayoutParams(-1, 0, 1f))
        col.addView(mkButton("Continue", true) { begin() }, LinearLayout.LayoutParams(-2, -2).apply { topMargin = dp(12) })
        setContentView(col)
    }

    // =====================================================================================
    // setup + loading
    // =====================================================================================
    private fun setupView() {
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(BG); setPadding(dp(80), dp(40), dp(80), dp(20)) }
        col.addView(mkText("91 TV - add your provider", 28f, Color.WHITE, true).apply { setPadding(0, 0, 0, dp(16)) })
        fun field(hint: String, key: String, pw: Boolean = false) = EditText(this).apply {
            this.hint = hint; textSize = 20f; setTextColor(Color.WHITE); setHintTextColor(Color.GRAY); setSingleLine()
            setText(prefs.getString(key, "")); if (pw) inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
        }
        val s = field("Server  (http://host:port)", "server"); val u = field("Username", "user"); val p = field("Password", "pass", true)
        val m = field("...or an M3U playlist URL instead", "m3u")
        for (v in listOf(s, u, p, m)) col.addView(v, LinearLayout.LayoutParams(-1, -2))
        col.addView(mkButton("Connect", true) {
            prefs.edit().putString("server", s.text.toString().trim()).putString("user", u.text.toString().trim())
                .putString("pass", p.text.toString().trim()).putString("m3u", m.text.toString().trim()).apply()
            startLoading(true)
        }, LinearLayout.LayoutParams(-2, -2).apply { topMargin = dp(16) })
        setContentView(col); s.requestFocus()
    }

    private fun bigMessage(t: String) = setContentView(TextView(this).apply { text = t; textSize = 26f; setTextColor(Color.WHITE); gravity = Gravity.CENTER; setBackgroundColor(BG) })

    private fun setData(l: List<Item>?, m: List<Item>?, se: List<Item>?) {
        if (l != null) live = l; if (m != null) movies = m; if (se != null) series = se; visCache.clear()
    }

    /** Opens instantly from the disk cache; downloads (or refreshes in the background when older than 6 h) otherwise. */
    private fun startLoading(force: Boolean = false) {
        val server = prefs.getString("server", "") ?: ""; val m3uUrl = prefs.getString("m3u", "") ?: ""
        if (force) Cache.clear(this)
        if (server.isNotBlank()) xt = Xtream(server, prefs.getString("user", "") ?: "", prefs.getString("pass", "") ?: "") else xt = null
        val cl = Cache.load(this, "live")
        if (cl != null && cl.isNotEmpty()) {
            setData(cl, Cache.load(this, "movie") ?: emptyList(), Cache.load(this, "series") ?: emptyList())
            buildShell(); nav("home")
            if (Cache.ageHours(this, "live") >= 6) refreshInBackground(server, m3uUrl)
            return
        }
        bigMessage("91 TV\n\nConnecting…")
        Thread {
            try {
                if (server.isNotBlank()) {
                    val x = xt!!; x.login()
                    ui.post { bigMessage("91 TV\n\nLoading channels… (first time only)") }
                    val l = x.live(); setData(l, null, null); Cache.save(this, "live", l)
                    ui.post { bigMessage("91 TV\n\nLoading movies…") }
                    val m = try { x.movies() } catch (e: Throwable) { emptyList() }; setData(null, m, null); Cache.save(this, "movie", m)
                    ui.post { bigMessage("91 TV\n\nLoading series…") }
                    val se = try { x.series() } catch (e: Throwable) { emptyList() }; setData(null, null, se); Cache.save(this, "series", se)
                } else {
                    val all = M3u.parse(Http.get(m3uUrl))
                    val l = all.filter { it.kind == "live" }; val m = all.filter { it.kind == "movie" }; val se = all.filter { it.kind == "episode" }
                    setData(l, m, se); Cache.save(this, "live", l); Cache.save(this, "movie", m); Cache.save(this, "series", se)
                }
                ui.post { buildShell(); nav("home") }
            } catch (e: Throwable) {
                ui.post { Toast.makeText(this, "Could not connect: ${e.message ?: e.javaClass.simpleName}", Toast.LENGTH_LONG).show(); setupView() }
            }
        }.start()
    }

    private fun refreshInBackground(server: String, m3uUrl: String) {
        Thread {
            try {
                if (server.isNotBlank()) {
                    val x = xt ?: return@Thread
                    val l = x.live(); Cache.save(this, "live", l)
                    val m = try { x.movies() } catch (e: Throwable) { null }; if (m != null) Cache.save(this, "movie", m)
                    val se = try { x.series() } catch (e: Throwable) { null }; if (se != null) Cache.save(this, "series", se)
                    ui.post { setData(l, m, se) }
                } else {
                    val all = M3u.parse(Http.get(m3uUrl))
                    val l = all.filter { it.kind == "live" }; val m = all.filter { it.kind == "movie" }; val se = all.filter { it.kind == "episode" }
                    Cache.save(this, "live", l); Cache.save(this, "movie", m); Cache.save(this, "series", se); ui.post { setData(l, m, se) }
                }
            } catch (e: Throwable) { }
        }.start()
    }

    // =====================================================================================
    // shell: sidebar + content
    // =====================================================================================
    private fun buildShell() {
        val root = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; setBackgroundColor(BG) }
        val side = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(Color.parseColor("#0F0F14")); setPadding(dp(14), dp(26), dp(14), dp(16)) }
        val logo = TextView(this).apply {
            text = android.text.SpannableString("91 TV").apply { setSpan(android.text.style.ForegroundColorSpan(RED), 0, 2, 0) }
            textSize = 28f; setTextColor(Color.WHITE); typeface = Typeface.DEFAULT_BOLD; letterSpacing = 0.15f; setPadding(dp(12), 0, 0, dp(22))
        }
        side.addView(logo)
        sideItems.clear()
        val entries = listOf("home" to "⌂   Home", "live" to "📺   Live TV", "movie" to "🎬   Movies", "series" to "📚   TV Series",
            "list" to "♡   My List", "search" to "🔍   Search", "settings" to "⚙   Settings")
        for ((k, label) in entries) {
            val tv = TextView(this).apply {
                text = label; textSize = 19f; setTextColor(Color.parseColor("#B5B5C0")); setPadding(dp(16), dp(13), dp(16), dp(13)); isFocusable = true
                background = rbg(Color.TRANSPARENT, Color.TRANSPARENT, 10, 2)
                setOnFocusChangeListener { v, f -> v.background = rbg(if (f) Color.parseColor("#33E50914") else Color.TRANSPARENT, if (f) RED else Color.TRANSPARENT, 10, 2); (v as TextView).setTextColor(if (f || k == section) Color.WHITE else Color.parseColor("#B5B5C0")) }
                setOnClickListener { if (k == "search") searchDialog() else nav(k) }
            }
            sideItems[k] = tv; side.addView(tv, LinearLayout.LayoutParams(-1, -2).apply { setMargins(0, 0, 0, dp(4)) })
        }
        side.addView(View(this), LinearLayout.LayoutParams(-1, 0, 1f))
        side.addView(mkText("${live.size} channels · ${movies.size} movies · ${series.size} series", 12f, GRAY).apply { setPadding(dp(8), 0, 0, dp(6)) })
        side.addView(mkText("Profile: Default", 13f, GRAY).apply { setPadding(dp(8), 0, 0, 0) })
        root.addView(side, LinearLayout.LayoutParams(dp(220), -1))
        content = FrameLayout(this)
        root.addView(content, LinearLayout.LayoutParams(0, -1, 1f))
        shell = root; setContentView(root)
    }

    private fun markSection() {
        for ((k, tv) in sideItems) {
            val sel = k == section
            tv.setTextColor(if (sel) Color.WHITE else Color.parseColor("#B5B5C0"))
            tv.typeface = if (sel) Typeface.DEFAULT_BOLD else Typeface.DEFAULT
        }
    }

    private fun nav(sec: String) {
        section = sec; pageStack.clear(); markSection()
        showPage {
            when (sec) {
                "home" -> homeView(); "live" -> liveView(); "movie" -> gridPage("movie"); "series" -> gridPage("series")
                "list" -> listPage(); "settings" -> settingsView(); else -> homeView()
            }
        }
    }

    private fun showPage(builder: () -> View) { currentPage = { show(builder()) }; currentPage!!() }
    private fun pushPage(builder: () -> View) { currentPage?.let { pageStack.addLast(it) }; showPage(builder) }
    private fun show(v: View) { releasePreview(); panel = null; content.removeAllViews(); content.addView(v, FrameLayout.LayoutParams(-1, -1)) }
    private fun refreshPage() { currentPage?.invoke() }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (playerRoot != null) { leavePlayer(); return }
        if (shell == null) { finish(); return }
        if (pageStack.isNotEmpty()) { currentPage = pageStack.removeLast(); currentPage!!(); return }
        if (section != "home") { nav("home"); return }
        finish()
    }

    // =====================================================================================
    // data helpers: hiding, favourites, recents, epg
    // =====================================================================================
    private fun hidden(): Set<String> = prefs.getStringSet("hidden", emptySet()) ?: emptySet()
    private val visCache = HashMap<String, List<Item>>()
    private fun addHidden(v: String) { prefs.edit().putStringSet("hidden", HashSet(hidden()) + v).apply(); visCache.clear() }
    private fun visible(kind: String, items: List<Item>): List<Item> {
        val h = hidden(); if (h.isEmpty()) return items
        visCache[kind]?.let { return it }
        val bad = HashSet<String>()
        for (g in items.asSequence().map { it.group }.toSet()) { val pre = groupPrefix(g); if ("$kind|$g" in h || (pre.isNotEmpty() && "$kind|prefix:$pre" in h)) bad.add(g) }
        val out = items.filter { it.group !in bad }; visCache[kind] = out; return out
    }
    private fun hideKind(it: Item) = if (it.kind == "episode") "series" else it.kind

    private fun readList(key: String): List<Item> {
        val s = prefs.getString(key, "") ?: ""; if (s.isBlank()) return emptyList()
        return try { val a = JSONArray(s); (0 until a.length()).map { Item.fromJson(a.getJSONObject(it)) } } catch (e: Exception) { emptyList() }
    }
    private fun writeList(key: String, l: List<Item>) { val a = JSONArray(); l.forEach { a.put(it.toJson()) }; prefs.edit().putString(key, a.toString()).apply() }
    private fun favs() = readList("favs")
    private fun isFav(it: Item) = favs().any { f -> f.key == it.key }
    private fun toggleFav(it: Item) { val l = favs().toMutableList(); if (!l.removeAll { f -> f.key == it.key }) l.add(0, it); writeList("favs", l) }
    private fun recents() = readList("recent")
    private fun addRecent(it: Item) { val l = recents().toMutableList(); l.removeAll { r -> r.key == it.key }; l.add(0, it); writeList("recent", l.take(60)) }
    private fun savedPos(it: Item): Long = prefs.getLong("pos_" + it.key, 0L)

    fun epgFor(it: Item, fetch: Boolean = true, cb: (List<Prog>) -> Unit) {
        if (it.kind != "live" || it.id.isEmpty() || xt == null) return
        val c = epgCache[it.id]; if (c != null) { cb(c); return }
        if (!fetch) return
        epgPool.execute {
            val l = try { xt?.shortEpg(it.id) ?: emptyList() } catch (e: Exception) { emptyList() }
            ui.post { epgCache[it.id] = l; cb(l) }
        }
    }
    fun nowOf(l: List<Prog>): Prog? { val t = System.currentTimeMillis() / 1000; return l.firstOrNull { it.start <= t && t < it.end } ?: l.firstOrNull { it.end > t } }

    // =====================================================================================
    // item routing / menus
    // =====================================================================================
    private fun openAny(list: List<Item>, pos: Int) {
        val it = list[pos]
        when (it.kind) {
            "live", "episode" -> play(list, pos)
            else -> pushPage { detailView(it) }
        }
    }

    private fun itemMenu(it: Item) {
        val opts = ArrayList<String>(); val acts = ArrayList<() -> Unit>()
        opts += if (isFav(it)) "Remove from My List" else "Add to My List"; acts += { toggleFav(it); refreshPage() }
        val kind = hideKind(it); val pre = groupPrefix(it.group)
        opts += "Hide category “${it.group}”"; acts += { addHidden("$kind|${it.group}"); refreshPage() }
        if (pre.isNotEmpty()) { opts += "Hide every category starting with $pre"; acts += { addHidden("$kind|prefix:$pre"); refreshPage() } }
        android.app.AlertDialog.Builder(this).setTitle(it.name).setItems(opts.toTypedArray()) { _, i -> acts[i]() }.show()
    }
    private fun groupMenu(kind: String, g: String) {
        val pre = groupPrefix(g); val opts = ArrayList<String>(); opts += "Hide “$g”"; if (pre.isNotEmpty()) opts += "Hide every category starting with $pre"
        android.app.AlertDialog.Builder(this).setTitle("Category").setItems(opts.toTypedArray()) { _, i ->
            addHidden(if (i == 0) "$kind|$g" else "$kind|prefix:$pre"); catFor[kind] = null; liveCat = 0; refreshPage()
        }.show()
    }

    private fun searchDialog() {
        val et = EditText(this).apply { hint = "Type a channel, movie or series…"; setSingleLine(); setText(query); textSize = 22f }
        android.app.AlertDialog.Builder(this).setTitle("Search").setView(et)
            .setPositiveButton("Search") { _, _ -> query = et.text.toString().trim(); if (query.isNotBlank()) { section = "search"; markSection(); pageStack.clear(); showPage { searchView() } } }
            .setNegativeButton("Cancel", null).show()
    }

    // =====================================================================================
    // HOME
    // =====================================================================================
    private fun homeView(): View {
        val scroll = ScrollView(this).apply { setBackgroundColor(BG); isFillViewport = true; clipChildren = false }
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; clipChildren = false }
        col.addView(heroView(), LinearLayout.LayoutParams(-1, dp(340)))
        val cont = recents().filter { (it.kind == "movie" || it.kind == "episode") && savedPos(it) > 10_000 }
        if (cont.isNotEmpty()) col.addView(rowView("Continue watching", cont))
        val fv = favs(); if (fv.isNotEmpty()) col.addView(rowView("My List", fv))
        val l = visible("live", live); if (l.isNotEmpty()) col.addView(rowView("Live TV", l.take(40)))
        val m = visible("movie", movies); if (m.isNotEmpty()) col.addView(rowView("Movies", m.take(40)))
        val s = visible("series", series); if (s.isNotEmpty()) col.addView(rowView("TV Series", s.take(40)))
        scroll.addView(col, FrameLayout.LayoutParams(-1, -2))
        scroll.post { (findFirstFocusable(col, 1))?.requestFocus() }
        return scroll
    }

    private fun findFirstFocusable(v: View, skip: Int): View? {
        // first focusable thing in the page (the hero's Play button, or the first poster)
        var n = 0
        fun walk(x: View): View? {
            if (x.isFocusable && x !is ViewGroup) return x
            if (x.isFocusable && x is ViewGroup && x !is RecyclerView) return x
            if (x is ViewGroup) {
                if (x is RecyclerView) { return x.getChildAt(0) }
                for (i in 0 until x.childCount) { val r = walk(x.getChildAt(i)); if (r != null) return r }
            }
            return null
        }
        n += skip; return walk(v)
    }

    private fun heroView(): View {
        val pool = visible("movie", movies).filter { it.logo.isNotBlank() }.ifEmpty { visible("series", series).filter { it.logo.isNotBlank() } }
        val feat: Item? = if (pool.isEmpty()) null else pool[(System.currentTimeMillis() / 86_400_000L % minOf(pool.size, 30)).toInt()]
        val hero = FrameLayout(this).apply { setBackgroundColor(Color.parseColor("#14141A")) }
        val bgImg = ImageView(this).apply { scaleType = ImageView.ScaleType.CENTER_CROP; alpha = 0.85f }
        hero.addView(bgImg, FrameLayout.LayoutParams(-1, -1))
        hero.addView(View(this).apply { background = GradientDrawable(GradientDrawable.Orientation.BOTTOM_TOP, intArrayOf(BG, Color.parseColor("#990A0A0D"), Color.TRANSPARENT)) }, FrameLayout.LayoutParams(-1, -1))
        hero.addView(View(this).apply { background = GradientDrawable(GradientDrawable.Orientation.LEFT_RIGHT, intArrayOf(Color.parseColor("#E60A0A0D"), Color.TRANSPARENT)) }, FrameLayout.LayoutParams(-1, -1))
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(40), 0, dp(40), dp(28)) }
        val label = mkText(if (feat?.kind == "series") "SERIES" else "MOVIE", 13f, RED, true).apply { letterSpacing = 0.25f }
        val title = mkText(feat?.name ?: "Welcome to 91 TV", 38f, Color.WHITE, true).apply { maxLines = 2 }
        val desc = mkText("", 16f, Color.parseColor("#D0D0D8")).apply { maxLines = 3; setPadding(0, dp(6), 0, dp(12)) }
        col.addView(label); col.addView(title); col.addView(desc, LinearLayout.LayoutParams(dp(620), -2))
        val btns = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        if (feat != null) {
            btns.addView(mkButton("▶  Play", true) { if (feat.kind == "movie") play(listOf(feat), 0) else pushPage { detailView(feat) } })
            btns.addView(mkButton("More info", false) { pushPage { detailView(feat) } }, LinearLayout.LayoutParams(-2, -2).apply { leftMargin = dp(12) })
            Img.load(feat.logo, bgImg, dp(900))
            val x = xt
            if (x != null) Thread {
                try {
                    val inf = if (feat.kind == "movie") x.vodInfo(feat.id) else x.seriesData(feat.id).info
                    ui.post { desc.text = inf.plot; if (inf.backdrop.startsWith("http")) Img.load(inf.backdrop, bgImg, dp(1200)) }
                } catch (e: Exception) { }
            }.start()
        }
        col.addView(btns)
        hero.addView(col, FrameLayout.LayoutParams(-1, -1, Gravity.BOTTOM or Gravity.START).apply { gravity = Gravity.BOTTOM })
        return hero
    }

    private fun rowView(titleText: String, items: List<Item>): View {
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; clipChildren = false; setPadding(dp(32), dp(14), 0, dp(6)) }
        box.addView(mkText(titleText, 22f, Color.WHITE, true).apply { setPadding(dp(4), 0, 0, dp(2)) })
        val rv = RecyclerView(this).apply {
            layoutManager = LinearLayoutManager(this@MainActivity, LinearLayoutManager.HORIZONTAL, false)
            adapter = PosterAdapter(this@MainActivity, items, { l, p -> openAny(l, p) }, { itemMenu(it) })
            clipChildren = false; clipToPadding = false; setPadding(0, dp(6), dp(30), dp(10)); itemAnimator = null
        }
        box.addView(rv, LinearLayout.LayoutParams(-1, dp(225 + 56)))
        return box
    }

    // =====================================================================================
    // MOVIES / SERIES / MY LIST / SEARCH grids
    // =====================================================================================
    private fun gridPage(kind: String): View {
        val base = visible(kind, if (kind == "movie") movies else series)
        val counts = base.groupingBy { it.group }.eachCount(); val groups = counts.keys.sortedBy { it.lowercase() }
        var sel = catFor[kind]; if (sel != null && sel !in groups) sel = null; catFor[kind] = sel
        fun shown(): List<Item> = if (catFor[kind] == null) base else base.filter { it.group == catFor[kind] }
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(BG); setPadding(dp(32), dp(22), dp(10), 0) }
        root.addView(mkText(if (kind == "movie") "MOVIES" else "TV SERIES", 13f, RED, true).apply { letterSpacing = 0.25f })
        val heading = mkText("", 30f, Color.WHITE, true)
        root.addView(heading)
        val grid = RecyclerView(this)
        val cards = PosterAdapter(this, shown(), { l, p -> openAny(l, p) }, { itemMenu(it) })
        fun upd() { heading.text = (if (kind == "movie") "Movies" else "TV Series") + "   ·   ${shown().size}" }
        upd()
        val labels = listOf("All  (${base.size})") + groups.map { "$it  (${counts[it]})" }
        val chips = RecyclerView(this).apply {
            layoutManager = LinearLayoutManager(this@MainActivity, LinearLayoutManager.HORIZONTAL, false)
            adapter = ChipAdapter(this@MainActivity, labels, if (catFor[kind] == null) 0 else groups.indexOf(catFor[kind]) + 1, false,
                { i -> catFor[kind] = if (i == 0) null else groups[i - 1]; cards.items = shown(); cards.notifyDataSetChanged(); grid.scrollToPosition(0); upd() },
                { i -> if (i > 0) groupMenu(kind, groups[i - 1]) })
            clipChildren = false; clipToPadding = false; setPadding(0, dp(8), 0, dp(6))
        }
        root.addView(chips, LinearLayout.LayoutParams(-1, -2))
        val span = maxOf(1, (resources.displayMetrics.widthPixels - dp(220) - dp(60)) / (dp(150) + dp(14)))
        grid.apply { layoutManager = GridLayoutManager(this@MainActivity, span); adapter = cards; clipChildren = false; clipToPadding = false; setPadding(0, dp(8), 0, dp(40)); itemAnimator = null }
        root.addView(grid, LinearLayout.LayoutParams(-1, 0, 1f))
        grid.post { (grid.getChildAt(0) ?: chips.getChildAt(0))?.requestFocus() }
        return root
    }

    private fun plainGrid(label: String, headingText: String, items: List<Item>, emptyMsg: String): View {
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(BG); setPadding(dp(32), dp(22), dp(10), 0) }
        root.addView(mkText(label, 13f, RED, true).apply { letterSpacing = 0.25f })
        root.addView(mkText(headingText, 30f, Color.WHITE, true).apply { setPadding(0, 0, 0, dp(8)) })
        if (items.isEmpty()) { root.addView(mkText(emptyMsg, 18f, GRAY)); return root }
        val span = maxOf(1, (resources.displayMetrics.widthPixels - dp(220) - dp(60)) / (dp(150) + dp(14)))
        val grid = RecyclerView(this).apply {
            layoutManager = GridLayoutManager(this@MainActivity, span); adapter = PosterAdapter(this@MainActivity, items, { l, p -> openAny(l, p) }, { itemMenu(it) })
            clipChildren = false; clipToPadding = false; setPadding(0, dp(8), 0, dp(40)); itemAnimator = null
        }
        root.addView(grid, LinearLayout.LayoutParams(-1, 0, 1f)); grid.post { grid.getChildAt(0)?.requestFocus() }
        return root
    }

    private fun listPage(): View = plainGrid("MY LIST", "My List", favs(), "Long-press OK on any channel, movie or series and choose “Add to My List”.")

    private fun searchView(): View {
        val q = query
        val all = (visible("live", live) + visible("movie", movies) + visible("series", series)).filter { it.name.contains(q, true) }.take(240)
        return plainGrid("SEARCH", "“$q”   ·   ${all.size}", all, "Nothing matches “$q”.")
    }

    // =====================================================================================
    // DETAIL (movie / series)
    // =====================================================================================
    private fun detailView(item: Item): View {
        val scroll = ScrollView(this).apply { setBackgroundColor(BG); isFillViewport = true; clipChildren = false }
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val hero = FrameLayout(this)
        val bgImg = ImageView(this).apply { scaleType = ImageView.ScaleType.CENTER_CROP; alpha = 0.9f }
        hero.addView(bgImg, FrameLayout.LayoutParams(-1, -1))
        hero.addView(View(this).apply { background = GradientDrawable(GradientDrawable.Orientation.BOTTOM_TOP, intArrayOf(BG, Color.parseColor("#B30A0A0D"), Color.TRANSPARENT)) }, FrameLayout.LayoutParams(-1, -1))
        hero.addView(View(this).apply { background = GradientDrawable(GradientDrawable.Orientation.LEFT_RIGHT, intArrayOf(Color.parseColor("#F00A0A0D"), Color.TRANSPARENT)) }, FrameLayout.LayoutParams(-1, -1))
        Img.load(item.logo, bgImg, dp(900))
        val back = mkButton("←  Back", false) { onBackPressed() }
        hero.addView(back, FrameLayout.LayoutParams(-2, -2, Gravity.TOP or Gravity.START).apply { setMargins(dp(32), dp(22), 0, 0) })
        val info = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(40), 0, dp(40), dp(28)) }
        info.addView(mkText(if (item.kind == "series") "SERIES" else "MOVIE", 13f, RED, true).apply { letterSpacing = 0.25f })
        info.addView(mkText(item.name, 38f, Color.WHITE, true).apply { maxLines = 2 })
        val meta = mkText(item.group, 16f, Color.parseColor("#D0D0D8")).apply { setPadding(0, dp(6), 0, dp(4)) }
        val plot = mkText("Loading details…", 16f, Color.parseColor("#D0D0D8")).apply { maxLines = 5 }
        val cast = mkText("", 14f, GRAY).apply { setPadding(0, dp(4), 0, dp(12)); maxLines = 2 }
        info.addView(meta); info.addView(plot, LinearLayout.LayoutParams(dp(680), -2)); info.addView(cast, LinearLayout.LayoutParams(dp(680), -2))
        val btnRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        val favBtn = mkButton(if (isFav(item)) "♥  In My List" else "♡  My List", false) {}
        favBtn.setOnClickListener { toggleFav(item); favBtn.text = if (isFav(item)) "♥  In My List" else "♡  My List" }
        val playBtn = mkButton("▶  Play", true) { if (item.kind == "movie") play(listOf(item), 0) }
        btnRow.addView(playBtn); btnRow.addView(favBtn, LinearLayout.LayoutParams(-2, -2).apply { leftMargin = dp(12) })
        info.addView(btnRow)
        hero.addView(info, FrameLayout.LayoutParams(-1, -1, Gravity.BOTTOM or Gravity.START).apply { gravity = Gravity.BOTTOM })
        col.addView(hero, LinearLayout.LayoutParams(-1, dp(420)))
        val seasonsBox = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(32), dp(10), dp(32), dp(40)) }
        col.addView(seasonsBox)
        scroll.addView(col, FrameLayout.LayoutParams(-1, -2))
        fun fill(inf: Info) {
            val bits = ArrayList<String>(); if (inf.year.isNotBlank()) bits += inf.year
            if ((inf.rating.toDoubleOrNull() ?: 0.0) > 0) bits += "★ ${inf.rating}"; if (inf.genre.isNotBlank()) bits += inf.genre
            meta.text = if (bits.isEmpty()) item.group else bits.joinToString("   ·   ")
            plot.text = inf.plot.ifBlank { "No description from your provider." }
            cast.text = if (inf.cast.isNotBlank()) "Starring: ${inf.cast}" else ""
            if (inf.backdrop.startsWith("http")) Img.load(inf.backdrop, bgImg, dp(1200))
        }
        val x = xt
        if (x == null) { plot.text = ""; }
        else Thread {
            try {
                if (item.kind == "movie") { val inf = x.vodInfo(item.id); ui.post { fill(inf) } }
                else {
                    val d = x.seriesData(item.id)
                    ui.post {
                        fill(d.info); buildSeasons(seasonsBox, d)
                        val first = d.seasons.values.firstOrNull()
                        playBtn.setOnClickListener { val resume = d.seasons.values.flatten().lastOrNull { savedPos(it) > 10_000 }; val l = d.seasons.values.flatten(); if (l.isNotEmpty()) play(l, if (resume != null) l.indexOf(resume) else 0) }
                        if (first == null) plot.text = plot.text.toString() + "\n(No episodes listed.)"
                    }
                }
            } catch (e: Exception) { ui.post { plot.text = "Could not load details: ${e.message}" } }
        }.start()
        scroll.post { playBtn.requestFocus() }
        return scroll
    }

    private fun buildSeasons(box: LinearLayout, d: SeriesData) {
        box.removeAllViews()
        val keys = d.seasons.keys.toList(); if (keys.isEmpty()) return
        var sel = 0
        val epBox = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        fun fillEps() {
            epBox.removeAllViews(); val eps = d.seasons[keys[sel]] ?: emptyList()
            for ((i, e) in eps.withIndex()) {
                val done = savedPos(e) > 10_000
                val row = LinearLayout(this).apply {
                    orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; isFocusable = true; setPadding(dp(16), dp(10), dp(16), dp(10))
                    background = rbg(Color.parseColor("#14FFFFFF"), Color.TRANSPARENT, 10, 2)
                    setOnFocusChangeListener { v, f -> v.background = rbg(if (f) Color.parseColor("#26E50914") else Color.parseColor("#14FFFFFF"), if (f) RED else Color.TRANSPARENT, 10, 2) }
                    setOnClickListener { play(eps, i) }
                }
                val thumb = ImageView(this).apply { scaleType = ImageView.ScaleType.CENTER_CROP; background = rbg(CARD, Color.TRANSPARENT, 6); clipToOutline = true; outlineProvider = ViewOutlineProvider.BACKGROUND }
                Img.load(e.logo, thumb, dp(160)); row.addView(thumb, LinearLayout.LayoutParams(dp(150), dp(84)).apply { rightMargin = dp(16) })
                row.addView(mkText(e.name + if (done) "     ✓ started" else "", 18f, Color.WHITE, true))
                epBox.addView(row, LinearLayout.LayoutParams(-1, -2).apply { setMargins(0, dp(4), 0, dp(4)) })
            }
        }
        val chips = RecyclerView(this).apply {
            layoutManager = LinearLayoutManager(this@MainActivity, LinearLayoutManager.HORIZONTAL, false)
            adapter = ChipAdapter(this@MainActivity, keys, 0, false, { i -> sel = i; fillEps() }, { })
            clipChildren = false; clipToPadding = false
        }
        box.addView(chips, LinearLayout.LayoutParams(-1, -2)); box.addView(epBox); fillEps()
    }

    // =====================================================================================
    // LIVE TV: categories | channels | preview panel
    // =====================================================================================
    private fun liveView(): View {
        val base = visible("live", live)
        val groups = base.map { it.group }.distinct().sortedBy { it.lowercase() }
        val labels = listOf("All channels", "★  Favorites", "Recently watched") + groups
        if (liveCat >= labels.size) liveCat = 0
        fun listFor(i: Int): List<Item> = when (i) {
            0 -> base
            1 -> { val k = favs().map { it.key }.toSet(); base.filter { it.key in k } }
            2 -> { val k = recents().filter { it.kind == "live" }.map { it.key }; k.mapNotNull { key -> base.firstOrNull { it.key == key } } }
            else -> base.filter { it.group == groups[i - 3] }
        }
        val root = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; setBackgroundColor(BG); setPadding(dp(24), dp(20), dp(16), dp(12)) }

        // column 1: categories
        val c1 = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        c1.addView(mkText("LIVE TV", 12f, RED, true).apply { letterSpacing = 0.25f })
        c1.addView(mkText("Channels", 30f, Color.WHITE, true))
        val countTv = mkText("", 13f, GRAY).apply { setPadding(0, 0, 0, dp(10)) }; c1.addView(countTv)
        val chAd = ChannelAdapter(this, emptyList(), { it -> onChannelFocus(it) }, { l, p -> lastLiveKey = l[p].key; play(l, p) }, { itemMenu(it) })
        val chRv = RecyclerView(this)
        val catRv = RecyclerView(this).apply { layoutManager = LinearLayoutManager(this@MainActivity) }
        val showCat = { i: Int -> liveCat = i; val l = listFor(i); chAd.items = l; chAd.notifyDataSetChanged(); chRv.scrollToPosition(0); countTv.text = if (l.isEmpty()) "no channels here" else "${l.size} channels" }
        catRv.adapter = ChipAdapter(this, labels, liveCat, true,
            { i -> showCat(i); chRv.post { chRv.getChildAt(0)?.requestFocus() } },
            { i -> if (i >= 3) groupMenu("live", groups[i - 3]) })
        c1.addView(catRv, LinearLayout.LayoutParams(-1, 0, 1f))
        root.addView(c1, LinearLayout.LayoutParams(dp(215), -1).apply { rightMargin = dp(12) })

        // column 2: channels
        val first = listFor(liveCat); chAd.items = first; countTv.text = "${first.size} channels"
        chRv.apply { layoutManager = LinearLayoutManager(this@MainActivity); adapter = chAd; clipChildren = false; clipToPadding = false; setPadding(0, 0, dp(10), dp(30)); itemAnimator = null; setHasFixedSize(true); setItemViewCacheSize(16) }
        root.addView(chRv, LinearLayout.LayoutParams(0, -1, 1f))

        // column 3: preview panel
        val p = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(16), dp(16), dp(16), dp(16)); background = rbg(Color.parseColor("#14141A"), Color.parseColor("#22FFFFFF"), 16, 1) }
        val vBox = FrameLayout(this).apply { background = rbg(Color.BLACK, Color.TRANSPARENT, 10); clipToOutline = true; outlineProvider = ViewOutlineProvider.BACKGROUND }
        val pv = PlayerView(this).apply { useController = false; setKeepContentOnPlayerReset(true); setShowBuffering(PlayerView.SHOW_BUFFERING_ALWAYS) }
        vBox.addView(pv, FrameLayout.LayoutParams(-1, -1))
        p.addView(vBox, LinearLayout.LayoutParams(-1, dp(225)))
        val chip = mkText("●  LIVE   ·   sound off", 12f, RED, true).apply { setPadding(0, dp(10), 0, dp(4)) }; p.addView(chip)
        val title = mkText("", 24f, Color.WHITE, true).apply { maxLines = 2 }
        val cat = mkText("", 14f, GRAY)
        val nowLabel = mkText("NOW PLAYING", 11f, RED, true).apply { letterSpacing = 0.2f; setPadding(0, dp(10), 0, dp(2)); visibility = View.GONE }
        val nowT = mkText("", 18f, Color.WHITE, true).apply { maxLines = 2 }
        val time = mkText("", 13f, GRAY)
        val bar = Bar(this)
        val next = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(0, dp(8), 0, 0) }
        p.addView(title); p.addView(cat); p.addView(nowLabel); p.addView(nowT); p.addView(time)
        p.addView(bar, LinearLayout.LayoutParams(-1, dp(3)).apply { topMargin = dp(6) }); p.addView(next)
        p.addView(View(this), LinearLayout.LayoutParams(-1, 0, 1f))
        val btns = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        val watch = mkButton("▶  Watch full screen", true) { previewItem?.let { cur -> val l = chAd.items; val i = l.indexOfFirst { it.key == cur.key }; if (i >= 0) { lastLiveKey = cur.key; play(l, i) } } }
        val fav = mkButton("♡", false) { previewItem?.let { toggleFav(it); panel?.fav?.text = if (isFav(it)) "♥" else "♡" } }
        btns.addView(watch, LinearLayout.LayoutParams(0, -2, 1f)); btns.addView(fav, LinearLayout.LayoutParams(-2, -2).apply { leftMargin = dp(10) })
        p.addView(btns)
        root.addView(p, LinearLayout.LayoutParams(dp(410), -1))
        panel = LivePanel(pv, title, cat, nowLabel, nowT, time, bar, next, fav)

        chRv.post {
            val idx = if (lastLiveKey.isNotEmpty()) chAd.items.indexOfFirst { it.key == lastLiveKey } else -1
            val pos = if (idx >= 0) idx else 0
            (chRv.layoutManager as LinearLayoutManager).scrollToPositionWithOffset(pos, dp(120))
            chRv.post { (chRv.findViewHolderForAdapterPosition(pos)?.itemView ?: chRv.getChildAt(0))?.requestFocus() }
        }
        return root
    }

    private fun onChannelFocus(it: Item) {
        previewItem = it
        val pn = panel ?: return
        pn.title.text = "${it.name}"; pn.cat.text = it.group; pn.fav.text = if (isFav(it)) "♥" else "♡"
        pn.nowLabel.visibility = View.GONE; pn.now.text = ""; pn.time.text = ""; pn.bar.frac = 0f; pn.next.removeAllViews()
        ui.removeCallbacks(previewRun); ui.postDelayed(previewRun, 600)
        epgFor(it) { list ->
            if (previewItem?.key == it.key) {
                val now = nowOf(list); val pp = panel ?: return@epgFor
                if (now != null) {
                    pp.nowLabel.visibility = View.VISIBLE; pp.now.text = now.title; pp.time.text = hm(now.start) + " – " + hm(now.end)
                    pp.bar.frac = (System.currentTimeMillis() / 1000 - now.start).toFloat() / maxOf(1L, now.end - now.start)
                    pp.next.removeAllViews()
                    for (n in list.filter { x -> x.start >= now.end }.take(5)) {
                        pp.next.addView(TextView(this).apply {
                            text = android.text.SpannableString(hm(n.start) + "   " + n.title).apply { setSpan(android.text.style.ForegroundColorSpan(RED), 0, 5, 0) }
                            textSize = 14f; setTextColor(Color.WHITE); maxLines = 1; setPadding(0, dp(2), 0, dp(2))
                        })
                    }
                }
            }
        }
    }
    private fun hm(sec: Long): String { val c = java.util.Calendar.getInstance(); c.timeInMillis = sec * 1000; return String.format("%02d:%02d", c.get(java.util.Calendar.HOUR_OF_DAY), c.get(java.util.Calendar.MINUTE)) }

    private fun startPreview(it: Item) {
        val pn = panel ?: return
        previewAttempt = 0
        val p: ExoPlayer = preview ?: newPlayer(false).also { np ->
            np.volume = 0f; preview = np; pn.video.player = np
            np.addListener(object : Player.Listener {
                override fun onPlayerError(error: PlaybackException) {
                    val cur = previewItem ?: return
                    if (previewAttempt < 3) { previewAttempt++; loadInto(np, cur, previewAttempt) }
                }
            })
        }
        loadInto(p, it, 0)
    }
    private fun releasePreview() { ui.removeCallbacks(previewRun); preview?.release(); preview = null; panel?.video?.player = null }

    // =====================================================================================
    // SETTINGS
    // =====================================================================================
    private fun settingsView(): View {
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(BG); setPadding(dp(40), dp(26), dp(40), dp(20)) }
        root.addView(mkText("SETTINGS", 13f, RED, true).apply { letterSpacing = 0.25f })
        root.addView(mkText("Settings", 30f, Color.WHITE, true).apply { setPadding(0, 0, 0, dp(14)) })
        fun row(label: String, sub: String, act: () -> Unit) {
            val r = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL; isFocusable = true; setPadding(dp(20), dp(14), dp(20), dp(14)); background = rbg(Color.parseColor("#14FFFFFF"), Color.TRANSPARENT, 10, 2)
                setOnFocusChangeListener { v, f -> v.background = rbg(if (f) Color.parseColor("#26E50914") else Color.parseColor("#14FFFFFF"), if (f) RED else Color.TRANSPARENT, 10, 2) }
                setOnClickListener { act() }
            }
            r.addView(mkText(label, 20f, Color.WHITE, true)); r.addView(mkText(sub, 14f, GRAY))
            root.addView(r, LinearLayout.LayoutParams(dp(700), -2).apply { setMargins(0, 0, 0, dp(8)) })
        }
        row("Provider", "Change server, login or M3U playlist") { setupView() }
        row("Show all hidden categories", "${hidden().size} hidden right now") { prefs.edit().remove("hidden").apply(); visCache.clear(); Toast.makeText(this, "All categories shown again", Toast.LENGTH_SHORT).show(); refreshPage() }
        row("Reload lists", "Download channels, movies and series again (normally automatic every 6 hours)") { startLoading(true) }
        val cap = AudioCapabilities.getCapabilities(this)
        val tvAtmos = cap.supportsEncoding(C.ENCODING_E_AC3_JOC)
        row("Audio output", (if (prefs.getBoolean("pcm", false)) "Stereo PCM (safe mode, no Dolby)" else "Dolby passthrough (Atmos / Dolby Digital+ sent to your TV or soundbar)") + "\nYour TV reports: Atmos " + (if (tvAtmos) "YES" else "NO") + ", Dolby Digital+ " + (if (cap.supportsEncoding(C.ENCODING_E_AC3)) "YES" else "NO") + "  - press to switch") { prefs.edit().putBoolean("pcm", !prefs.getBoolean("pcm", false)).apply(); refreshPage() }
        row("Dolby Vision mode", (if (prefs.getBoolean("notunnel", false)) "Normal" else "Tunnelled (used automatically for Dolby Vision, fixes blue / washed-out picture on many TVs)") + "  - press to switch") { prefs.edit().putBoolean("notunnel", !prefs.getBoolean("notunnel", false)).apply(); refreshPage() }
        row("Clear watch history", "Continue watching and recently watched") { prefs.edit().remove("recent").apply(); Toast.makeText(this, "History cleared", Toast.LENGTH_SHORT).show() }
        row("About", "91 TV 0.3.9 · long-press OK on anything to add to My List or hide its category") { }
        root.post { (root.getChildAt(2))?.requestFocus() }
        return root
    }

    // =====================================================================================
    // PLAYER
    // =====================================================================================
    private val selectors = java.util.WeakHashMap<ExoPlayer, androidx.media3.exoplayer.trackselection.DefaultTrackSelector>()
    private fun setTunnel(p: ExoPlayer, on: Boolean) {
        val sel = selectors[p] ?: return
        if (sel.parameters.tunnelingEnabled != on) sel.parameters = sel.buildUponParameters().setTunnelingEnabled(on).build()
    }

    private fun newPlayer(main: Boolean = true): ExoPlayer {
        val http = DefaultHttpDataSource.Factory().setUserAgent(Http.UA).setAllowCrossProtocolRedirects(true).setConnectTimeoutMs(15000).setReadTimeoutMs(20000)
        val extractors = DefaultExtractorsFactory().setTsExtractorFlags(DefaultTsPayloadReaderFactory.FLAG_ALLOW_NON_IDR_KEYFRAMES or DefaultTsPayloadReaderFactory.FLAG_DETECT_ACCESS_UNITS)
        val factory = DefaultMediaSourceFactory(DefaultDataSource.Factory(this, http), extractors)
        val passthrough = !prefs.getBoolean("pcm", false)
        val rf = object : DefaultRenderersFactory(this) {
            override fun buildAudioSink(context: Context, enableFloatOutput: Boolean, enableAudioTrackPlaybackParams: Boolean): AudioSink? =
                DefaultAudioSink.Builder(context)
                    .setAudioCapabilities(if (passthrough) AudioCapabilities.getCapabilities(context) else AudioCapabilities.DEFAULT_AUDIO_CAPABILITIES)
                    .setEnableFloatOutput(false).setEnableAudioTrackPlaybackParams(false).build()
        }.setEnableDecoderFallback(true)
        val sel = androidx.media3.exoplayer.trackselection.DefaultTrackSelector(this)
        val b = ExoPlayer.Builder(this, rf).setMediaSourceFactory(factory).setTrackSelector(sel)
        if (main) b.setLoadControl(DefaultLoadControl.Builder().setBufferDurationsMs(15000, 50000, 2500, 5000).build())
        val p = b.build()
        selectors[p] = sel
        p.trackSelectionParameters = p.trackSelectionParameters.buildUpon().setTrackTypeDisabled(C.TRACK_TYPE_TEXT, !prefs.getBoolean("subs", false)).build()
        p.setAudioAttributes(AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_MOVIE).build(), main)
        return p
    }

    private fun audioDialog() {
        val p = player ?: return
        val groups = p.currentTracks.groups.filter { it.type == C.TRACK_TYPE_AUDIO }
        
        val subs = prefs.getBoolean("subs", false)
        val vf = p.videoFormat; val af = p.audioFormat
        val info = "INFO  video: " + (vf?.sampleMimeType?.removePrefix("video/") ?: "-") + " " + (vf?.codecs ?: "") + " " + (vf?.let { "${it.width}x${it.height}" } ?: "") +
            (if (vf?.sampleMimeType == "video/dolby-vision") "  = DOLBY VISION" else if (vf?.colorInfo?.colorTransfer == C.COLOR_TRANSFER_ST2084) "  = HDR10" else if (vf?.colorInfo?.colorTransfer == C.COLOR_TRANSFER_HLG) "  = HLG" else "") +
            "  |  audio: " + (af?.sampleMimeType?.removePrefix("audio/") ?: "-") + " " + (af?.codecs ?: "") + (if (af?.sampleMimeType == "audio/eac3-joc" || af?.codecs?.contains("joc") == true) "  = DOLBY ATMOS" else "")
        val labels = listOf(info, "Subtitles: " + (if (subs) "ON  (press to turn off)" else "OFF  (press to turn on)")) + groups.mapIndexed { n, g ->
            val f = g.getTrackFormat(0)
            "Track ${n + 1}:  ${f.language ?: "?"}  ·  ${if (f.channelCount > 0) f.channelCount.toString() + " ch" else ""}  ·  ${(f.sampleMimeType ?: "").removePrefix("audio/")}" + if (g.isSelected) "   ✓" else ""
        }
        android.app.AlertDialog.Builder(this).setTitle("Audio / subtitles").setItems(labels.toTypedArray()) { _, i ->
            if (i == 1) {
                val on = !prefs.getBoolean("subs", false); prefs.edit().putBoolean("subs", on).apply()
                p.trackSelectionParameters = p.trackSelectionParameters.buildUpon().setTrackTypeDisabled(C.TRACK_TYPE_TEXT, !on).build()
                playerView?.subtitleView?.visibility = if (on) View.VISIBLE else View.GONE
            } else if (i >= 2) {
                p.trackSelectionParameters = p.trackSelectionParameters.buildUpon().setOverrideForType(TrackSelectionOverride(groups[i - 2].mediaTrackGroup, 0)).build()
            }
        }.show()
    }

    private fun variants(it: Item): List<String> = when {
        it.kind != "live" -> listOf(it.url)
        it.url.endsWith(".ts") -> listOf(it.url, it.url.removeSuffix(".ts") + ".m3u8")
        it.url.endsWith(".m3u8") -> listOf(it.url, it.url.removeSuffix(".m3u8") + ".ts")
        else -> listOf(it.url)
    }
    private fun urlFor(it: Item, att: Int): String { val v = variants(it); return v[att % v.size] }
    private fun loadInto(p: ExoPlayer, it: Item, att: Int, startMs: Long = 0L) {
        val url = urlFor(it, att)
        val mi = MediaItem.Builder().setUri(url).apply { if (url.contains(".m3u8")) setMimeType(MimeTypes.APPLICATION_M3U8) }.build()
        if (startMs > 0) p.setMediaItem(mi, startMs) else p.setMediaItem(mi)
        setTunnel(p, false)
        p.prepare(); p.playWhenReady = true
    }

    private fun play(list: List<Item>, index: Int) {
        releasePreview(); ui.removeCallbacks(previewRun)
        zapList = list; zapIndex = index
        val root = FrameLayout(this).apply { setBackgroundColor(Color.BLACK) }
        val pv = PlayerView(this).apply { useController = list[index].kind != "live"; keepScreenOn = true; setShowBuffering(PlayerView.SHOW_BUFFERING_ALWAYS) }
        root.addView(pv, FrameLayout.LayoutParams(-1, -1))
        titleView = TextView(this).apply { textSize = 24f; setTextColor(Color.WHITE); setBackgroundColor(Color.argb(190, 0, 0, 0)); setPadding(dp(24), dp(14), dp(24), dp(14)) }
        root.addView(titleView, FrameLayout.LayoutParams(-2, -2, Gravity.TOP or Gravity.START))
        pv.subtitleView?.visibility = if (prefs.getBoolean("subs", false)) View.VISIBLE else View.GONE
        if (android.os.Build.VERSION.SDK_INT >= 26) window.setColorMode(android.content.pm.ActivityInfo.COLOR_MODE_HDR)
        playerView = pv; playerRoot = root; setContentView(root); pv.isFocusable = true; pv.requestFocus()
        val p = newPlayer(); player = p; pv.player = p
        p.addListener(object : Player.Listener {
            override fun onTracksChanged(tracks: androidx.media3.common.Tracks) {
                val dv = tracks.groups.any { it.type == C.TRACK_TYPE_VIDEO && it.getTrackFormat(0).sampleMimeType == "video/dolby-vision" }
                if (dv && !prefs.getBoolean("notunnel", false)) setTunnel(p, true)
            }
            override fun onRenderedFirstFrame() {
                ui.postDelayed({
                    val vf = p.videoFormat; val af = p.audioFormat
                    val cv = p.currentTracks.groups.firstOrNull { it.type == C.TRACK_TYPE_VIDEO }?.getTrackFormat(0)
                    val t = "VIDEO in file: " + (cv?.sampleMimeType ?: "?") + " " + (cv?.codecs ?: "") + "\nVIDEO decoding as: " + (vf?.sampleMimeType ?: "?") + " " + (vf?.codecs ?: "") + " " + (vf?.let { "${it.width}x${it.height}" } ?: "") +
                        " transfer=" + (vf?.colorInfo?.colorTransfer ?: -1) + (if (vf?.sampleMimeType == "video/dolby-vision") "  = DOLBY VISION" else "") +
                        "  tunnelled=" + (selectors[p]?.parameters?.tunnelingEnabled ?: false) + "\nAUDIO: " + (af?.sampleMimeType ?: "?") + " " + (af?.codecs ?: "") + " " + (af?.channelCount ?: 0) + "ch" + (if (af?.codecs?.contains("joc") == true || af?.sampleMimeType == "audio/eac3-joc") "  = DOLBY ATMOS" else "")
                    showTitle(t, 9000)
                }, 1500)
            }
            override fun onPlayerError(error: PlaybackException) {
                val cur = zapList[zapIndex]
                if (attempt < 5) { attempt++; showTitle("Retrying ($attempt/5)…  ${error.errorCodeName}", 4000); loadInto(p, cur, attempt) }
                else showTitle("Can't play this stream: ${error.errorCodeName}\n${error.cause?.message ?: ""}\n${urlFor(cur, attempt)}", 15000)
            }
        })
        startCurrent()
    }

    private fun startCurrent() {
        savePosition()
        val it = zapList[zapIndex]; playing = it; attempt = 0
        addRecent(it)
        val start = if (it.kind != "live") savedPos(it) else 0L
        player?.let { loadInto(it, zapList[zapIndex], 0, if (start > 10_000) start else 0L) }
        if (it.kind == "live") {
            showTitle("${zapIndex + 1}  ${it.name}      (→ audio / subtitles)")
            epgFor(it) { l -> val n = nowOf(l); if (n != null && playing?.key == it.key) showTitle("${zapIndex + 1}  ${it.name}\n${n.title}   ${hm(n.start)} – ${hm(n.end)}") }
        } else showTitle(it.name)
    }

    private fun savePosition() {
        val p = player ?: return; val it = playing ?: return
        if (it.kind == "live") return
        val pos = p.currentPosition; val dur = p.duration
        val e = prefs.edit()
        if (dur > 0 && pos > dur * 0.95) e.remove("pos_" + it.key) else if (pos > 10_000) e.putLong("pos_" + it.key, pos)
        e.apply()
    }

    private fun showTitle(t: String, ms: Long = 4000) { titleView?.text = t; titleView?.visibility = View.VISIBLE; ui.removeCallbacks(hideTitle); ui.postDelayed(hideTitle, ms) }
    private val hideTitle = Runnable { titleView?.visibility = View.GONE }

    private fun zap(delta: Int) { if (zapList.size < 2) return; zapIndex = (zapIndex + delta + zapList.size) % zapList.size; lastLiveKey = zapList[zapIndex].key; startCurrent() }

    private fun leavePlayer() {
        savePosition(); ui.removeCallbacks(hideTitle); player?.release(); player = null; playerRoot = null; titleView = null; playerView = null; playing = null
        if (android.os.Build.VERSION.SDK_INT >= 26) window.setColorMode(android.content.pm.ActivityInfo.COLOR_MODE_DEFAULT)
        shell?.let { setContentView(it) }; refreshPage()
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent): Boolean {
        if (playerRoot != null && zapList.getOrNull(zapIndex)?.kind == "live") {
            when (keyCode) {
                KeyEvent.KEYCODE_CHANNEL_UP, KeyEvent.KEYCODE_DPAD_UP -> { zap(1); return true }
                KeyEvent.KEYCODE_CHANNEL_DOWN, KeyEvent.KEYCODE_DPAD_DOWN -> { zap(-1); return true }
                KeyEvent.KEYCODE_DPAD_CENTER, KeyEvent.KEYCODE_ENTER -> { startCurrent(); return true }
                KeyEvent.KEYCODE_DPAD_RIGHT, KeyEvent.KEYCODE_MENU -> { audioDialog(); return true }
            }
        }
        if (playerRoot != null && keyCode == KeyEvent.KEYCODE_MENU) { audioDialog(); return true }
        if (playerRoot != null && keyCode != KeyEvent.KEYCODE_BACK && playerView?.dispatchKeyEvent(event) == true) return true
        return super.onKeyDown(keyCode, event)
    }

    override fun onStop() { super.onStop(); savePosition(); player?.pause(); releasePreview() }
    override fun onDestroy() { super.onDestroy(); player?.release(); preview?.release() }
}
