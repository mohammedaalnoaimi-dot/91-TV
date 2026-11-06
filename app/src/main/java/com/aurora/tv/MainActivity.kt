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
    private var vdec = "?"
    private var previewChip: TextView? = null
    private var lastDiag = ""
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
        Img.init(this); Click.init()
        lastLiveKey = prefs.getString("lastLive", "") ?: ""; liveCat = prefs.getInt("liveCat", 0)
        if (prefs.getInt("cacheVer", 0) < 2) { Cache.clear(this); prefs.edit().putInt("cacheVer", 2).apply() }
        if (!prefs.contains("favs_mr") && prefs.contains("favs")) prefs.edit().putString("favs_mr", prefs.getString("favs", "")).apply()
        val old = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { t, e ->
            try { prefs.edit().putString("crash", android.util.Log.getStackTraceString(e).take(2500)).commit() } catch (x: Throwable) { }
            old?.uncaughtException(t, e)
        }
        val crash = prefs.getString("crash", "") ?: ""
        if (crash.isNotBlank()) { prefs.edit().remove("crash").apply(); showCrash(crash) } else begin()
    }

    private fun activationView(msg: String = prefs.getString("lic_msg", "") ?: "") {
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL; setBackgroundColor(BG); setPadding(dp(120), dp(60), dp(120), dp(20)) }
        col.addView(android.widget.ImageView(this).apply { setImageResource(R.drawable.wordmark); scaleType = android.widget.ImageView.ScaleType.FIT_CENTER }, LinearLayout.LayoutParams(dp(380), dp(58)))
        col.addView(mkText("Activate your TV", 24f, CREAM, true).apply { setPadding(0, dp(34), 0, dp(6)) })
        val pairTv = mkText("", 18f, GOLD).apply { gravity = Gravity.CENTER; setPadding(0, 0, 0, dp(12)); maxWidth = dp(760) }
        if (Lic.PAIR_API.isNotBlank()) col.addView(pairTv)
        col.addView(mkText("Or type your code with the keys below:", 15f, GRAY).apply { setPadding(0, 0, 0, dp(6)); gravity = Gravity.CENTER })
        col.addView(mkText("No code yet? Get a free ${Lic.TRIAL_DAYS}-day trial at ninetyonetv.com/trial (just your email, no card). The code appears on the page.", 15f, GRAY).apply { setPadding(0, 0, 0, dp(14)); gravity = Gravity.CENTER; maxWidth = dp(700) })
        val et = EditText(this).apply { hint = "XXXX-XXXX-XXXX-XXXX"; textSize = 22f; setTextColor(CREAM); setHintTextColor(Color.GRAY); setSingleLine(); gravity = Gravity.CENTER }
        if (Lic.hasKey(prefs)) et.setText(prefs.getString("lic_key", ""))
        col.addView(et, LinearLayout.LayoutParams(dp(560), -2))
        // Remote-friendly keypad: codes only use 0-9 and A-F, so nobody has to hunt through a full keyboard.
        fun fmt(raw: String): String {
            val isHex = raw.all { it in '0'..'9' || it.uppercaseChar() in 'A'..'F' }
            if (!isHex || raw.length > 32) return raw
            val u = raw.uppercase()
            return listOf(0 to 8, 8 to 12, 12 to 16, 16 to 20, 20 to 32).map { (x, y) -> if (x >= u.length) "" else u.substring(x, minOf(y, u.length)) }.filter { it.isNotEmpty() }.joinToString("-")
        }
        fun setRaw(raw: String) { et.setText(fmt(raw)); et.setSelection(et.text.length) }
        fun raw() = et.text.toString().filter { it.isLetterOrDigit() }
        fun keyRow(chars: String, extra: List<Pair<String, () -> Unit>> = emptyList()) {
            val r = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER }
            for (c in chars) r.addView(mkButton(c.toString(), false) { setRaw(raw() + c) }.apply { textSize = 13f; setPadding(dp(14), dp(8), dp(14), dp(8)) }, LinearLayout.LayoutParams(-2, -2).apply { leftMargin = dp(4); rightMargin = dp(4); topMargin = dp(4) })
            for ((label, act) in extra) r.addView(mkButton(label, false) { act() }.apply { textSize = 13f; setPadding(dp(14), dp(8), dp(14), dp(8)) }, LinearLayout.LayoutParams(-2, -2).apply { leftMargin = dp(8); rightMargin = dp(4); topMargin = dp(4) })
            col.addView(r)
        }
        keyRow("01234567")
        keyRow("89ABCDEF", listOf("Delete" to { setRaw(raw().dropLast(1)) }, "Clear" to { et.setText("") }))
        val m = mkText(msg, 16f, RED).apply { setPadding(0, dp(10), 0, 0); gravity = Gravity.CENTER }; col.addView(m)
        pairGen++; if (Lic.PAIR_API.isNotBlank()) startPairing(pairTv, m, pairGen)
        val btns = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER }
        btns.addView(mkButton("Activate", true) {
            m.text = "Checking…"; val k = et.text.toString().trim()
            Thread { val r = Lic.activate(this, prefs, k); ui.post { if (r == null) begin() else m.text = r } }.start()
        })
        if (Lic.hasKey(prefs)) btns.addView(mkButton("Check again", false) {
            m.text = "Checking…"
            Thread { val good = Lic.refresh(prefs); ui.post { if (good) begin() else m.text = prefs.getString("lic_msg", "") ?: "" } }.start()
        }, LinearLayout.LayoutParams(-2, -2).apply { leftMargin = dp(14) })
        col.addView(btns, LinearLayout.LayoutParams(-2, -2).apply { topMargin = dp(18) })
        col.addView(mkText("Tip: use the keys above with your remote, no dashes needed. Or paste it from your phone: Google TV app › Remote › keyboard.", 14f, GRAY).apply { setPadding(0, dp(22), 0, 0); gravity = Gravity.CENTER; maxWidth = dp(640) })
        if (Lic.BUY_URL.isNotBlank()) col.addView(mkText("Buy a plan at ninetyonetv.com. No code or a problem? Email ninetyonetv.support@gmail.com", 15f, GRAY).apply { setPadding(0, dp(12), 0, 0) })
        setContentView(android.widget.ScrollView(this).apply { setBackgroundColor(BG); isFillViewport = true; addView(col) }); et.requestFocus()
    }

    private var pairGen = 0

    /** Shows a short code on the TV; the phone page (ninetyonetv.com/activate) sends the licence key to it, and the TV activates itself. */
    private fun startPairing(label: TextView, msg: TextView, gen: Int) {
        fun call(method: String, path: String): org.json.JSONObject {
            val c = java.net.URL(Lic.PAIR_API + path).openConnection() as java.net.HttpURLConnection
            c.requestMethod = method; c.connectTimeout = 10000; c.readTimeout = 15000
            if (method == "POST") { c.doOutput = true; c.outputStream.use { it.write(ByteArray(0)) } }
            return try { org.json.JSONObject(c.inputStream.bufferedReader().use { it.readText() }) } finally { c.disconnect() }
        }
        Thread {
            var code = ""; var secret = ""; var born = 0L; var fails = 0
            while (gen == pairGen && !isFinishing) {
                try {
                    if (code.isEmpty() || System.currentTimeMillis() - born > 13 * 60_000L) {
                        val n = call("POST", "/new"); code = n.getString("code"); secret = n.getString("secret"); born = System.currentTimeMillis()
                        val shown = code.substring(0, 3) + " " + code.substring(3)
                        ui.post { if (gen == pairGen) label.text = "On your phone, open  ninetyonetv.com/activate  and type this code:\n\n$shown" ; label.textSize = 18f }
                    }
                    val st = call("GET", "/status?code=$code&secret=$secret")
                    if (st.has("key")) {
                        val key = st.getString("key"); ui.post { if (gen == pairGen) msg.text = "Activating…" }
                        val r = Lic.activate(this, prefs, key)
                        ui.post { if (gen == pairGen) { if (r == null) { pairGen++; begin() } else msg.text = r } }
                        code = ""; if (r == null) return@Thread
                    } else if (st.optBoolean("expired")) code = ""
                    fails = 0
                } catch (e: Throwable) { fails++ ; if (fails == 3) ui.post { if (gen == pairGen) label.text = "Phone activation needs the internet. You can still type your code with the keys below." } }
                try { Thread.sleep(3000) } catch (e: InterruptedException) { return@Thread }
            }
        }.start()
    }

    private fun begin() {
        pairGen++
        if (Lic.needsScreen(prefs)) { activationView(); return }
        proceed()
    }

    private fun proceed() {
        if (!Lic.ok(prefs)) { activationView(); return }
        Lic.recheck(prefs)
        if (prefs.getString("server", "").isNullOrBlank() && prefs.getString("m3u", "").isNullOrBlank()) setupView() else startLoading()
    }

    private fun showCrash(text: String) {
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(BG); setPadding(dp(60), dp(30), dp(60), dp(20)) }
        col.addView(mkText("91 TV closed unexpectedly last time", 26f, RED, true))
        col.addView(mkText("Take a photo of this screen and send it, then press Continue.", 16f, GRAY).apply { setPadding(0, dp(6), 0, dp(10)) })
        val sv = ScrollView(this); sv.addView(mkText(text, 13f, CREAM).apply { typeface = Typeface.MONOSPACE })
        col.addView(sv, LinearLayout.LayoutParams(-1, 0, 1f))
        col.addView(mkButton("Continue", true) { begin() }, LinearLayout.LayoutParams(-2, -2).apply { topMargin = dp(12) })
        setContentView(col)
    }

    // =====================================================================================
    // setup + loading
    // =====================================================================================
    private fun setupView() {
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(BG); setPadding(dp(80), dp(40), dp(80), dp(20)) }
        col.addView(mkText("Add your provider", 28f, CREAM, true).apply { setPadding(0, 0, 0, dp(16)) })
        fun field(hint: String, key: String, pw: Boolean = false) = EditText(this).apply {
            this.hint = hint; textSize = 20f; setTextColor(CREAM); setHintTextColor(Color.GRAY); setSingleLine()
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


    // =====================================================================================
    // profiles: Mr / Mrs / Together / Kids  ("Who is watching" screen)
    // =====================================================================================
    private var profileChosen = false
    private var pickerOpen = false

    /** After the channels are ready: ask who is watching (once per start), then open the app. */
    private fun enterApp() {
        if (profileChosen) { buildShell(); nav(startSection()); return }
        showProfilePicker(true)
    }

    private fun setProfile(p: String) {
        prefs.edit().putString("profile", p).apply()
        visCache.clear(); smart.clear(); becauseRows = emptyList(); becauseSig = ""; catFor.clear(); liveCat = 0; query = ""
    }

    private fun pickProfile(p: String) {
        profileChosen = true; pickerOpen = false
        setProfile(p)
        if (p == "kids") {
            splash("Getting the Kids profile ready")
            Thread {
                try { visible("live", live); visible("movie", movies); visible("series", series) } catch (e: Throwable) { }
                ui.post { buildShell(); nav("home") }
            }.start()
        } else { buildShell(); nav(startSection()) }
    }

    /** "Who is watching?" - four floating names. The focused one lifts, glows and gets a gold line. */
    private fun showProfilePicker(atStart: Boolean) {
        pickerOpen = !atStart
        val root = FrameLayout(this).apply { setBackgroundColor(BG) }
        val glow = ImageView(this).apply { setImageResource(R.drawable.glow_rose); scaleType = ImageView.ScaleType.FIT_XY; alpha = 0.32f }
        root.addView(glow, FrameLayout.LayoutParams(dp(900), dp(620), Gravity.CENTER))
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER }
        col.addView(ImageView(this).apply { setImageResource(R.drawable.wordmark); scaleType = ImageView.ScaleType.FIT_CENTER }, LinearLayout.LayoutParams(dp(420), dp(63)))
        col.addView(mkText("WHO IS WATCHING?", 18f, GRAY, true).apply { letterSpacing = 0.3f; gravity = Gravity.CENTER; setPadding(0, dp(26), 0, dp(54)) })
        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER; clipChildren = false; clipToPadding = false }
        col.clipChildren = false; root.clipChildren = false
        val defs = listOf(Triple("mr", "MR", "Favourites"), Triple("mrs", "MRS", "Favourites"), Triple("together", "TOGETHER", "Saved by both"), Triple("kids", "KIDS", "Cartoons & family"))
        val cur = profile(); var first: View? = null; var curView: View? = null
        val anims = ArrayList<android.animation.Animator>()
        defs.forEachIndexed { i, (key, name, sub) ->
            val item = FrameLayout(this).apply { isFocusable = true; isClickable = true; alpha = 0.42f; clipChildren = false; setPadding(dp(24), dp(18), dp(24), dp(22)) }
            val spot = ImageView(this).apply { alpha = 0f; setImageResource(R.drawable.glow_rose); scaleType = ImageView.ScaleType.FIT_XY }
            item.addView(spot, FrameLayout.LayoutParams(-1, -1).apply { setMargins(-dp(70), -dp(50), -dp(70), -dp(50)) })
            val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL }
            val nm = mkText(name, 30f, CREAM, true).apply { maxLines = 1 }.also { it.setSingleLine() }.apply { letterSpacing = 0.1f; gravity = Gravity.CENTER; typeface = fDisplay() }
            val sb = mkText(sub, 13f, GRAY).apply { gravity = Gravity.CENTER; setPadding(0, dp(4), 0, 0) }
            val line = View(this).apply { setBackgroundColor(GOLD); scaleX = 0f }
            box.addView(nm); box.addView(sb); box.addView(line, LinearLayout.LayoutParams(dp(120), dp(3)).apply { topMargin = dp(10) })
            item.addView(box, FrameLayout.LayoutParams(-2, -2, Gravity.CENTER))
            item.setOnFocusChangeListener { v, f ->
                v.animate().alpha(if (f) 1f else 0.42f).scaleX(if (f) 1.14f else 1f).scaleY(if (f) 1.14f else 1f).setDuration(260).start()
                spot.animate().alpha(if (f) 1f else 0f).setDuration(260).start()
                line.animate().scaleX(if (f) 1f else 0f).setDuration(300).start()
                nm.setTextColor(if (f) GOLD else CREAM); sb.setTextColor(if (f) CREAM else GRAY)
            }
            item.setOnClickListener { pickProfile(key) }
            val fl = android.animation.ObjectAnimator.ofFloat(box, "translationY", 0f, -dp(7).toFloat()).apply {
                duration = 2600; startDelay = i * 450L; repeatMode = android.animation.ValueAnimator.REVERSE; repeatCount = android.animation.ValueAnimator.INFINITE
                interpolator = android.view.animation.AccelerateDecelerateInterpolator()
            }
            anims.add(fl); fl.start()
            row.addView(item, LinearLayout.LayoutParams(-2, -2).apply { setMargins(dp(14), 0, dp(14), 0) })
            if (first == null) first = item; if (key == cur) curView = item
        }
        col.addView(row)
        col.addView(mkText("Use ◀ ▶ to choose, OK to open", 13f, Color.parseColor("#8f806c")).apply { gravity = Gravity.CENTER; setPadding(0, dp(46), 0, 0) })
        root.addView(col, FrameLayout.LayoutParams(-1, -2, Gravity.CENTER))
        root.addOnAttachStateChangeListener(object : View.OnAttachStateChangeListener {
            override fun onViewAttachedToWindow(v: View) {}
            override fun onViewDetachedFromWindow(v: View) { anims.forEach { it.cancel() } }
        })
        setContentView(root)
        (curView ?: first)?.requestFocus()
    }

    /** Loading screen: sharp wordmark that fades in, a soft rose glow that breathes, a tagline and a sweeping progress line. */
    private fun splash(msg: String = "") {
        val root = FrameLayout(this).apply {
            background = GradientDrawable(GradientDrawable.Orientation.TL_BR, intArrayOf(Color.parseColor("#1c0d11"), BG, Color.parseColor("#0d0809")))
        }
        val glow = View(this).apply {
            background = GradientDrawable().apply {
                gradientType = GradientDrawable.RADIAL_GRADIENT; gradientRadius = dp(520).toFloat()
                colors = intArrayOf(Color.parseColor("#40C9475C"), Color.parseColor("#00C9475C"))
            }
            alpha = 0.55f
        }
        root.addView(glow, FrameLayout.LayoutParams(dp(1040), dp(1040), Gravity.CENTER))
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER }
        val logo = ImageView(this).apply { setImageResource(R.drawable.wordmark); scaleType = ImageView.ScaleType.FIT_CENTER; alpha = 0f; scaleX = 0.93f; scaleY = 0.93f }
        col.addView(logo, LinearLayout.LayoutParams(dp(600), dp(90)))
        val tag = TextView(this).apply {
            text = "Everything you watch. In one beautiful app."; textSize = 16f; setTextColor(GOLD); gravity = Gravity.CENTER
            letterSpacing = 0.06f; alpha = 0f; setPadding(0, dp(22), 0, 0)
        }
        col.addView(tag)
        val track = FrameLayout(this).apply { background = GradientDrawable().apply { setColor(Color.parseColor("#2a2220")); cornerRadius = dp(2).toFloat() } }
        val bar = View(this).apply { background = GradientDrawable(GradientDrawable.Orientation.LEFT_RIGHT, intArrayOf(Color.TRANSPARENT, GOLD, Color.TRANSPARENT)).apply { cornerRadius = dp(2).toFloat() } }
        track.addView(bar, FrameLayout.LayoutParams(dp(90), dp(3)))
        col.addView(track, LinearLayout.LayoutParams(dp(280), dp(3)).apply { topMargin = dp(46) })
        val note = TextView(this).apply { text = if (msg.isBlank()) "Loading channels" else msg; textSize = 15f; setTextColor(Color.parseColor("#8f806c")); gravity = Gravity.CENTER; setPadding(0, dp(16), 0, 0) }
        col.addView(note)
        root.addView(col, FrameLayout.LayoutParams(-1, -2, Gravity.CENTER))
        setContentView(root)
        val anims = ArrayList<android.animation.Animator>()
        fun go(a: android.animation.Animator) { anims.add(a); a.start() }
        go(android.animation.ObjectAnimator.ofFloat(logo, "alpha", 0f, 1f).apply { duration = 900 })
        go(android.animation.ObjectAnimator.ofFloat(logo, "scaleX", 0.93f, 1f).apply { duration = 1200 })
        go(android.animation.ObjectAnimator.ofFloat(logo, "scaleY", 0.93f, 1f).apply { duration = 1200 })
        go(android.animation.ObjectAnimator.ofFloat(tag, "alpha", 0f, 0.9f).apply { duration = 900; startDelay = 600 })
        go(android.animation.ObjectAnimator.ofFloat(glow, "alpha", 0.35f, 0.8f).apply { duration = 2200; repeatMode = android.animation.ValueAnimator.REVERSE; repeatCount = android.animation.ValueAnimator.INFINITE })
        go(android.animation.ObjectAnimator.ofFloat(bar, "translationX", -dp(90).toFloat(), dp(280).toFloat()).apply {
            duration = 1500; repeatCount = android.animation.ValueAnimator.INFINITE; interpolator = android.view.animation.LinearInterpolator() })
        root.addOnAttachStateChangeListener(object : View.OnAttachStateChangeListener {
            override fun onViewAttachedToWindow(v: View) {}
            override fun onViewDetachedFromWindow(v: View) { anims.forEach { it.cancel() } }
        })
    }

    private fun bigMessage(t: String) { splash(t.removePrefix("91 TV").trim()) }

    private fun setData(l: List<Item>?, m: List<Item>?, se: List<Item>?) {
        if (l != null) live = l; if (m != null) movies = m; if (se != null) series = se; visCache.clear(); smart.clear()
    }

    /** Opens instantly from the disk cache; downloads (or refreshes in the background when older than 6 h) otherwise. */
    private fun startLoading(force: Boolean = false) {
        val server = prefs.getString("server", "") ?: ""; val m3uUrl = prefs.getString("m3u", "") ?: ""
        if (server.isBlank() && m3uUrl.isBlank()) { setupView(); return }
        if (force) Cache.clear(this)
        if (server.isNotBlank()) xt = Xtream(server, prefs.getString("user", "") ?: "", prefs.getString("pass", "") ?: "") else xt = null
        if (!force && Cache.ageHours(this, "live") != Long.MAX_VALUE) {
            splash()
            Thread {
                val cl = Cache.load(this, "live")
                if (cl != null && cl.isNotEmpty()) {
                    val mv = Cache.load(this, "movie") ?: emptyList(); val sr = Cache.load(this, "series") ?: emptyList()
                    ui.post { setData(cl, mv, sr); enterApp() }
                    if (Cache.ageHours(this, "live") >= 6) refreshInBackground(server, m3uUrl)
                } else ui.post { startLoading(true) }
            }.start()
            return
        }
        bigMessage("91 TV\n\nConnecting…")
        Thread {
            try {
                var shown = false
                if (server.isNotBlank()) {
                    val x = xt!!; x.login()
                    ui.post { bigMessage("91 TV\n\nLoading channels… (first time only)") }
                    val l = x.live(); Cache.save(this, "live", l)
                    ui.post { setData(l, null, null); enterApp() }; shown = true
                    val m = try { x.movies() } catch (e: Throwable) { emptyList() }; Cache.save(this, "movie", m)
                    ui.post { setData(null, m, null) }
                    val se = try { x.series() } catch (e: Throwable) { emptyList() }; Cache.save(this, "series", se)
                    ui.post { setData(null, null, se); if (playerRoot == null && shell != null) refreshPage() }
                } else {
                    val all = M3u.parse(Http.get(m3uUrl))
                    val l = all.filter { it.kind == "live" }; val m = all.filter { it.kind == "movie" }; val se = all.filter { it.kind == "episode" }
                    setData(l, m, se); Cache.save(this, "live", l); Cache.save(this, "movie", m); Cache.save(this, "series", se)
                }
                if (!shown) ui.post { enterApp() }
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
    // shell: header + top menu + content   (C3 "Dark Luxury Theatre")
    // =====================================================================================
    private var hdrClock: TextView? = null
    private var hdrDate: TextView? = null
    private var hdrNext: TextView? = null
    private var hdrNextSub: TextView? = null
    private val navItems = LinkedHashMap<String, NavItem>()
    private val chromeTick = object : Runnable {
        override fun run() { updateChrome(); ui.postDelayed(this, 15_000) }
    }

    private fun buildShell() {
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(BG) }
        // ---- header
        val head = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; setPadding(dp(36), dp(14), dp(36), dp(2)) }
        val leftBox = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        hdrNext = mkText("", 13f, CREAM, true).apply { letterSpacing = 0.14f }
        hdrNextSub = mkItalic("", 14f, GRAY)
        leftBox.addView(hdrNext); leftBox.addView(hdrNextSub)
        head.addView(leftBox, LinearLayout.LayoutParams(0, -2, 1f))
        val brandBox = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL }
        val brand = android.widget.ImageView(this).apply { setImageResource(R.drawable.wordmark); adjustViewBounds = true; scaleType = android.widget.ImageView.ScaleType.FIT_CENTER }
        brandBox.addView(brand, LinearLayout.LayoutParams(dp(190), dp(29)))
        head.addView(brandBox, LinearLayout.LayoutParams(-2, -2))
        val rightBox = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.END }
        hdrClock = mkText("", 26f, CREAM).apply { gravity = Gravity.END }
        hdrDate = mkText("", 13f, GRAY).apply { gravity = Gravity.END }
        rightBox.addView(hdrClock); rightBox.addView(hdrDate)
        head.addView(rightBox, LinearLayout.LayoutParams(0, -2, 1f))
        root.addView(head, LinearLayout.LayoutParams(-1, -2))
        // ---- top menu
        val navRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER; setPadding(0, dp(2), 0, 0) }
        navItems.clear()
        val entries = if (profile() == "kids") listOf("home" to "HOME", "live" to "LIVE TV", "movie" to "MOVIES", "series" to "TV SERIES", "list" to "MY LIST", "profile" to "WHO IS WATCHING")
        else listOf("home" to "HOME", "live" to "LIVE TV", "multi" to "MULTI", "movie" to "MOVIES", "series" to "TV SERIES",
            "list" to "MY LIST", "prayer" to "PRAYER", "search" to "SEARCH", "settings" to "SETTINGS", "profile" to profName().uppercase())
        for ((k, label) in entries) {
            val ni = NavItem(this, label).apply { setOnClickListener { if (k == "profile") showProfilePicker(false) else if (k == "search") searchDialog() else if (k == "multi") { releasePreview(); startActivity(android.content.Intent(this@MainActivity, MultiActivity::class.java)) } else nav(k) } }
            navItems[k] = ni; navRow.addView(ni, LinearLayout.LayoutParams(-2, -2).apply { setMargins(dp(6), 0, dp(6), 0) })
        }
        root.addView(navRow, LinearLayout.LayoutParams(-1, -2))
        root.addView(View(this).apply { setBackgroundColor(Color.parseColor("#1FEBDDC4")) }, LinearLayout.LayoutParams(-1, dp(1)).apply { setMargins(dp(36), 0, dp(36), 0) })
        content = FrameLayout(this)
        root.addView(content, LinearLayout.LayoutParams(-1, 0, 1f))
        shell = root; setContentView(root)
        ui.removeCallbacks(chromeTick); updateChrome(); ui.postDelayed(chromeTick, 15_000)
    }

    private fun markSection() { for ((k, v) in navItems) v.sel = k == section }

    private var lastRemind = ""
    private fun updateChrome() {
        val now = System.currentTimeMillis()
        hdrClock?.text = Prayer.clock(now); hdrDate?.text = Prayer.shortDate(now).uppercase()
        if (prefs.getBoolean("ptWidget", true)) {
            val nx = Prayer.next(now)
            val ram = Prayer.today?.hijriMonth == 9       // Ramadan: the header names Maghrib "Iftar" and Fajr "Suhoor ends"
            if (nx != null) { hdrNext?.text = "${(if (ram && nx.first == "Maghrib") "IFTAR" else if (ram && nx.first == "Fajr") "SUHOOR ENDS" else nx.first.uppercase())}  ·  ${Prayer.clock(nx.second)}"; hdrNextSub?.text = "in " + Prayer.left(nx.second - now) }
            else { hdrNext?.text = ""; hdrNextSub?.text = "" }
        } else { hdrNext?.text = ""; hdrNextSub?.text = "" }
        Prayer.ensure(prefs) { updateChrome() }
        checkReminder(now)
    }

    private var prevNext: Pair<String, Long>? = null
    private fun checkReminder(now: Long) {
        val nx = Prayer.next(now) ?: return
        val prev = prevNext; prevNext = nx
        val mins = prefs.getInt("ptRemind", 0); if (mins <= 0) return
        if (prev != null && prev.second != nx.second && now - prev.second in 0..120_000L) { remindUser("It is time for ${prev.first.uppercase()}"); return }
        val diff = nx.second - now
        val pre = "${nx.first}@${nx.second}"
        if (diff in 1..(mins * 60_000L) && lastRemind != pre) { lastRemind = pre; remindUser("${nx.first.uppercase()} in ${Prayer.left(diff)}  ·  ${Prayer.clock(nx.second)}") }
    }

    private var banner: TextView? = null
    private val dropBanner = Runnable { banner?.let { (it.parent as? ViewGroup)?.removeView(it) }; banner = null }
    private fun remindUser(msg: String) {
        try { android.media.RingtoneManager.getRingtone(this, android.media.RingtoneManager.getDefaultUri(android.media.RingtoneManager.TYPE_NOTIFICATION))?.play() } catch (e: Throwable) { }
        if (playerRoot != null && titleView != null) { showTitle(msg, 9000); return }
        ui.removeCallbacks(dropBanner); dropBanner.run()
        val t = mkText(msg, 20f, CREAM, true).apply { setPadding(dp(26), dp(14), dp(26), dp(14)); background = rbg(Color.parseColor("#F2120A0C"), ROSE, 3, 2); gravity = Gravity.CENTER }
        (window.decorView as ViewGroup).addView(t, FrameLayout.LayoutParams(-2, -2, Gravity.TOP or Gravity.CENTER_HORIZONTAL).apply { topMargin = dp(24) })
        banner = t; ui.postDelayed(dropBanner, 9000)
    }

    private fun startSection(): String { val x = prefs.getString("lastSection", "home") ?: "home"; return if (profile() == "kids") (if (x in setOf("home", "live", "movie", "series", "list")) x else "home") else if (x in setOf("home", "live", "movie", "series", "list", "prayer")) x else "home" }

    private fun nav(sec0: String) {
        val sec = if (profile() == "kids" && sec0 !in setOf("home", "live", "movie", "series", "list")) "home" else sec0
        if (sec != "settings") prefs.edit().putString("lastSection", sec).apply()
        section = sec; pageStack.clear(); markSection()
        showPage {
            when (sec) {
                "home" -> homeView(); "live" -> liveView(); "movie" -> gridPage("movie"); "series" -> gridPage("series")
                "list" -> listPage(); "prayer" -> Prayer.page(this, prefs, { if (section == "prayer" && playerRoot == null) refreshPage() }, { pushPage { Prayer.monthPage(this, prefs) } }); "settings" -> settingsView(); else -> homeView()
            }
        }
    }

    private fun showPage(builder: () -> View) { currentPage = { releasePreview(); panel = null; show(builder()) }; currentPage!!() }
    private fun pushPage(builder: () -> View) { currentPage?.let { pageStack.addLast(it) }; showPage(builder) }
    private fun show(v: View) { content.removeAllViews(); content.addView(v, FrameLayout.LayoutParams(-1, -1)) }
    private fun refreshPage() { currentPage?.invoke() }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (playerRoot != null) { leavePlayer(); return }
        if (pickerOpen && shell != null) { pickerOpen = false; setContentView(shell); return }
        if (shell == null) { finish(); return }
        if (pageStack.isNotEmpty()) { currentPage = pageStack.removeLast(); currentPage!!(); return }
        if (section != "home") { nav("home"); return }
        finish()
    }

    // =====================================================================================
    // data helpers: hiding, favourites, recents, epg
    // =====================================================================================
    private fun hidden(): Set<String> = prefs.getStringSet("hidden", emptySet()) ?: emptySet()
    private val visCache = java.util.concurrent.ConcurrentHashMap<String, List<Item>>()
    private val smart = HashMap<String, List<Item>>()
    private val HOLLY = Regex("hollywood|english|\\bEN\\b|^\\s*EN\\s*[|:\\-\\]]|\\bUSA?\\b|\\bUK\\b", RegexOption.IGNORE_CASE)
    private val YEAR = Regex("\\((\\d{4})\\)")
    private fun yearOf(n: String) = YEAR.find(n)?.groupValues?.get(1)?.toIntOrNull() ?: 0
    /** Shows the provider's rating straight away, then IMDb / Rotten Tomatoes from OMDb when a key is set in Settings. */
    private fun loadRatings(item: Item, year: String, cb: (String) -> Unit) {
        if (item.kind == "live") return
        cb(if (item.rating > 0f && item.rating <= 10f) String.format(java.util.Locale.US, "★ %.1f", item.rating) else "")
        val key = prefs.getString("omdb", "") ?: ""
        if (key.isBlank()) return
        Thread { val r = Ratings.lookup(prefs, key, item.name, year, item.kind); if (r != null) ui.post { cb(r) } }.start()
    }
    private val rateExec = Executors.newSingleThreadExecutor()
    private val rateMemo = HashMap<String, String>()
    /** Rating line under a poster: provider score at once, IMDb / Rotten Tomatoes when an OMDb key is set (looked up one by one, then remembered). */
    fun cardRating(item: Item, cb: (String) -> Unit) {
        if (item.kind == "live") return
        val prov = if (item.rating > 0f && item.rating <= 10f) String.format(java.util.Locale.US, "★ %.1f", item.rating) else ""
        val key = prefs.getString("omdb", "") ?: ""
        if (key.isBlank()) { cb(prov); return }
        rateMemo[item.key]?.let { cb(it); return }
        cb(prov)
        rateExec.execute { val r = Ratings.lookup(prefs, key, item.name, Ratings.yearOf(item.name), item.kind); if (r != null) ui.post { rateMemo[item.key] = r; cb(r) } }
    }
    private fun smartTitle(w: String) = when (w) { "@recent" -> "Recently added"; "@top" -> "Top rated"; "@new" -> "New releases"; "@hollywood" -> "Hollywood / English"; else -> w }
    /** Ready-made lists built from what the provider sends: recently added, top rated, new releases, Hollywood. */
    private fun smartList(kind: String, which: String): List<Item> = smart.getOrPut("$kind|$which") {
        val base = visible(kind, if (kind == "movie") movies else series)
        val thisYear = java.util.Calendar.getInstance().get(java.util.Calendar.YEAR)
        when (which) {
            "@recent" -> base.filter { it.added > 0 }.sortedByDescending { it.added }.take(300)
            "@top" -> base.filter { it.rating > 0f && it.rating <= 10f }.sortedByDescending { it.rating }.take(300)
            "@new" -> base.filter { yearOf(it.name) >= thisYear - 1 }.sortedByDescending { it.added }.take(300)
            "@hollywood" -> base.filter { HOLLY.containsMatchIn(it.group) }.sortedByDescending { it.rating }.take(1500)
            else -> emptyList()
        }
    }
    /** Sorting ~90k titles takes a moment, so the three home lists are built off the UI thread; the home page is redrawn once when they are ready. */
    private fun warmSmart() {
        val keys = listOf("movie" to "@recent", "movie" to "@top", "movie" to "@new", "series" to "@top", "series" to "@new")
        val rec = recents().filter { it.kind == "movie" || it.kind == "series" || it.kind == "episode" }.take(12)
        val bsig = rec.take(6).joinToString("|") { it.key }
        if ((keys.all { smart.containsKey("${it.first}|${it.second}") } && bsig == becauseSig) || smartBusy) return
        smartBusy = true
        val bases = mapOf("movie" to visible("movie", movies), "series" to visible("series", series))
        val year = java.util.Calendar.getInstance().get(java.util.Calendar.YEAR)
        Thread {
            val out = HashMap<String, List<Item>>()
            for ((k, w) in keys) {
                val base = bases[k] ?: emptyList()
                out["$k|$w"] = when (w) {
                    "@recent" -> base.filter { it.added > 0 }.sortedByDescending { it.added }.take(300)
                    "@top" -> base.filter { it.rating > 0f && it.rating <= 10f }.sortedByDescending { it.rating }.take(300)
                    else -> base.filter { yearOf(it.name) >= year - 1 }.sortedByDescending { it.added }.take(300)
                }
            }
            // "Because you watched ...": same category as something you watched, not watched yet, better rated first (built only from this TV's own history)
            val watched = rec.map { it.key }.toSet(); val rows = ArrayList<Pair<String, List<Item>>>(); val used = HashSet<String>()
            val all = (bases["movie"] ?: emptyList()) + (bases["series"] ?: emptyList())
            val byGroup = all.groupBy { it.kind + "|" + it.group }
            for (r in rec) {
                val kind = if (r.kind == "episode") "series" else r.kind
                val gk = kind + "|" + r.group
                if (r.group.isBlank() || !used.add(gk)) continue
                val cand = (byGroup[gk] ?: emptyList()).filter { it.key !in watched }
                if (cand.size < 6) continue
                rows.add(r.name to cand.sortedByDescending { it.rating }.take(30)); if (rows.size >= 3) break
            }
            ui.post {
                becauseRows = rows; becauseSig = bsig
                smartBusy = false; smart.putAll(out)
                if (section == "home" && pageStack.isEmpty() && playerRoot == null) refreshPage()
            }
        }.start()
    }
    private var smartBusy = false
    private var becauseRows: List<Pair<String, List<Item>>> = emptyList()
    private var becauseSig = ""
    private fun favCats(): Set<String> = prefs.getStringSet("favcats", emptySet()) ?: emptySet()
    private fun isFavCat(kind: String, g: String) = "$kind|$g" in favCats()
    private fun toggleFavCat(kind: String, g: String) {
        val v = "$kind|$g"; val n = HashSet(favCats()); if (!n.remove(v)) n.add(v)
        prefs.edit().putStringSet("favcats", n).apply()
        Toast.makeText(this, if (v in n) "★ “$g” is now a favourite category (shown first)" else "“$g” removed from favourite categories", Toast.LENGTH_SHORT).show()
    }
    /** Favourite categories first, then the rest A to Z. */
    private fun sortGroups(kind: String, groups: Collection<String>): List<String> = groups.sortedWith(compareBy({ !isFavCat(kind, it) }, { it.lowercase() }))
    private fun addHidden(v: String) { prefs.edit().putStringSet("hidden", HashSet(hidden()) + v).apply(); visCache.clear(); smart.clear() }
    // Kids profile: only what clearly looks like children's content is shown. Anything unrecognised stays hidden, and anything that looks adult is always hidden.
    // Plain word lists and a per-category memo keep this fast even on a TV with a big playlist (the first version used regexes on every title and froze the app).
    private val kidsWords = listOf("kids", "kidz", "cartoon", "toon", "disney", "nickelodeon", "nick jr", "junior", "baby", "children", "pixar",
        "boomerang", "spacetoon", "majid", "mbc3", "mbc 3", "baraem", "karameesh", "toyor", "jeem", "cartoonito", "pogo", "duck tv", "babytv", "nicktoons", "cbeebies", "cbbc", "tiny pop",
        "da vinci", "boing", "gulli", "teletoon", "zoo moo", "kika", "dreamworks", "اطفال", "أطفال", "كرتون", "سبيستون", "ماجد", "براعم", "طيور الجنة")
    private val adultWords = listOf("xxx", "adult", "18+", "+18", "18 +", "porn", "sex", "erotic", "playboy", "brazzers", "hentai", "nude", "nsfw", "uncensored", "للكبار", "للبالغين", "جنس", "اباح", "إباح", "عاري", "ساخن")
    private val studioWords = listOf("disney", "pixar", "dreamworks", "illumination", "spongebob", "paw patrol", "peppa", "bluey", "tom and jerry", "tom & jerry", "mickey", "toy story", "frozen",
        "moana", "encanto", "minions", "shrek", "kung fu panda", "ice age", "madagascar", "lion king", "finding nemo", "cocomelon", "barbie", "my little pony", "looney tunes", "scooby", "pocoyo", "masha")
    private val scaryWords = listOf("blood", "vampire", "killer", "murder", "horror", "zombie", "massacre", "slasher", "demon slayer", "gore", "naked", "erotic", "lust", "seduc", "bdsm", "fetish")
    private fun hasAny(text: String, words: List<String>): Boolean { val l = text.lowercase(); for (w in words) if (l.contains(w)) return true; return false }
    // Movies/series: a category only counts when it is clearly a kids category, and mature titles are always blocked even inside one.
    private val strictKidsGroups = listOf("kids", "kidz", "cartoon", "children", "disney", "pixar", "nickelodeon", "nick jr", "dreamworks", "اطفال", "أطفال", "كرتون", "اطفال")
    private val matureTitles = listOf("stranger things", "disenchantment", "blue eye", "mating season", "batman", "mickey 17", "transformers", "violet evergarden", "garden of words", "ocean waves",
        "typhoon", "who (", "goat", "wild robot", "knightfall", "one piece", "naruto", "attack on titan", "demon", "death note", "bleach", "jujutsu", "chainsaw", "berserk", "hunter", "south park", "family guy",
        "simpsons", "rick and morty", "bojack", "big mouth", "harley", "invincible", "castlevania", "arcane", "love death", "midnight gospel", "archer", "futurama", "american dad", "bob's burgers", "deadpool", "joker", "venom", "spider-man", "justice league", "crisis on infinite", "dc league", "suicide squad", "watchmen", "gen v", "the boys")
    private val groupMemo = java.util.concurrent.ConcurrentHashMap<String, Int>()      // 1 = kids category, 2 = adult category, 0 = neither
    private fun groupClass(g: String): Int = groupMemo.getOrPut(g) { if (hasAny(g, adultWords)) 2 else if (hasAny(g, kidsWords)) 1 else 0 }
    private val strictMemo = java.util.concurrent.ConcurrentHashMap<String, Boolean>()
    private fun strictKids(g: String): Boolean = strictMemo.getOrPut(g) { !hasAny(g, adultWords) && hasAny(g, strictKidsGroups) }
    private fun kidsOk(it: Item): Boolean {
        if (hasAny(it.name, adultWords)) return false
        if (it.kind == "live") return when (groupClass(it.group)) { 2 -> false; 1 -> !hasAny(it.name, scaryWords); else -> hasAny(it.name, kidsWords) }
        if (hasAny(it.name, matureTitles) || hasAny(it.name, scaryWords)) return false
        return hasAny(it.name, studioWords) || strictKids(it.group)
    }
    private fun visible(kind: String, items: List<Item>): List<Item> {
        if (profile() == "kids") { val ck = "kids|$kind"; visCache[ck]?.let { return it }; val out = items.filter { kidsOk(it) }; visCache[ck] = out; return out }
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
    private fun profile(): String = prefs.getString("profile", "mr") ?: "mr"
    /** Kids profile gets bigger, brighter tiles. */
    fun isKids(): Boolean = profile() == "kids"
    fun tileW(): Int = if (isKids()) 200 else 150
    private fun profName(p: String = profile()) = when (p) { "mrs" -> "Mrs"; "kids" -> "Kids"; "together" -> "Together"; else -> "Mr" }
    private fun favsOf(p: String): List<Item> {
        if (p == "together") { val b = readList("favs_mrs").map { it.key }.toSet(); return readList("favs_mr").filter { it.key in b } }
        return readList("favs_$p")
    }
    private fun favs() = favsOf(profile())
    private fun isFav(it: Item) = favs().any { f -> f.key == it.key }
    private fun isFavOf(p: String, it: Item) = favsOf(p).any { f -> f.key == it.key }
    private fun toggleFav(it: Item) {
        if (profile() == "together") { if (isFav(it)) { removeFavFrom("mr", it); removeFavFrom("mrs", it) } else { addFavTo("mr", it); addFavTo("mrs", it) }; return }
        val l = favs().toMutableList(); if (!l.removeAll { f -> f.key == it.key }) l.add(0, it); writeList("favs_" + profile(), l)
    }
    private fun addFavTo(p: String, it: Item) { val l = favsOf(p).toMutableList(); if (l.none { f -> f.key == it.key }) { l.add(0, it); writeList("favs_$p", l) } }
    private fun removeFavFrom(p: String, it: Item) { val l = favsOf(p).toMutableList(); if (l.removeAll { f -> f.key == it.key }) writeList("favs_$p", l) }
    private fun recentKey() = when (profile()) { "kids" -> "recent_kids"; "mrs" -> "recent_mrs"; "together" -> "recent_together"; else -> "recent" }   // each profile keeps its own history ("mr" keeps the original key)
    private fun recents() = readList(recentKey())
    private fun addRecent(it: Item) { val l = recents().toMutableList(); l.removeAll { r -> r.key == it.key }; l.add(0, it); writeList(recentKey(), l.take(60)) }
    private fun savedPos(it: Item): Long = prefs.getLong("pos_" + it.key, 0L)
    /** How much of a movie / episode has been watched (0..1), for the red bar on "Continue watching" posters. */
    fun progressOf(it: Item): Float { if (it.kind != "movie" && it.kind != "episode") return 0f; val d = prefs.getLong("dur_" + it.key, 0L); val p = savedPos(it); return if (d > 0 && p > 0) (p.toFloat() / d).coerceIn(0f, 1f) else 0f }

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
        opts += if (isFav(it)) "Remove from ${profName()}'s list" else "Add to ${profName()}'s list"; acts += { toggleFav(it); refreshPage() }
        if (profile() == "kids") { android.app.AlertDialog.Builder(this).setTitle(it.name).setItems(opts.toTypedArray()) { _, i -> acts[i]() }.show(); return }
        if (isFavOf("mr", it) && isFavOf("mrs", it)) { opts += "Remove from both lists"; acts += { removeFavFrom("mr", it); removeFavFrom("mrs", it); refreshPage() } }
        else { opts += "Add to both lists (Together)"; acts += { addFavTo("mr", it); addFavTo("mrs", it); refreshPage() } }
        if (it.kind == "live") { opts += "▣ Watch in a small corner screen"; acts += { startPip(it) } }
        if (pip != null) { opts += "▣ Corner screen options…"; acts += { pipMenu() } }
        val kind = hideKind(it); val pre = groupPrefix(it.group)
        opts += if (isFavCat(kind, it.group)) "★ Remove “${it.group}” from favourite categories" else "★ Make “${it.group}” a favourite category"; acts += { toggleFavCat(kind, it.group); catFor[kind] = null; liveCat = 0; refreshPage() }
        opts += "Hide category “${it.group}”"; acts += { addHidden("$kind|${it.group}"); refreshPage() }
        if (pre.isNotEmpty()) { opts += "Hide every category starting with $pre"; acts += { addHidden("$kind|prefix:$pre"); refreshPage() } }
        android.app.AlertDialog.Builder(this).setTitle(it.name).setItems(opts.toTypedArray()) { _, i -> acts[i]() }.show()
    }
    private fun groupMenu(kind: String, g: String) {
        if (profile() == "kids") return
        val pre = groupPrefix(g); val opts = ArrayList<String>(); val acts = ArrayList<() -> Unit>()
        opts += if (isFavCat(kind, g)) "★ Remove “$g” from favourite categories" else "★ Make “$g” a favourite category"
        acts += { toggleFavCat(kind, g); catFor[kind] = null; liveCat = 0; refreshPage() }
        opts += "Hide “$g”"; acts += { addHidden("$kind|$g"); catFor[kind] = null; liveCat = 0; refreshPage() }
        if (pre.isNotEmpty()) { opts += "Hide every category starting with $pre"; acts += { addHidden("$kind|prefix:$pre"); catFor[kind] = null; liveCat = 0; refreshPage() } }
        android.app.AlertDialog.Builder(this).setTitle("Category").setItems(opts.toTypedArray()) { _, i -> acts[i]() }.show()
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
        warmSmart()
        col.addView(heroView(), LinearLayout.LayoutParams(-1, dp(340)))
        val cont = recents().filter { (it.kind == "movie" || it.kind == "episode") && savedPos(it) > 10_000 }
        if (cont.isNotEmpty()) col.addView(rowView("Continue watching", cont))
        becauseRows.forEach { (t, l) -> col.addView(rowView("Because you watched  " + Ratings.cleanTitle(t), l)) }
        val fv = favs()
        if (profile() != "kids") {
            val fch = fv.filter { it.kind == "live" }; val ftl = fv.filter { it.kind != "live" }
            if (fch.isNotEmpty()) col.addView(rowView("${profName()}'s channels", fch))
            if (ftl.isNotEmpty()) col.addView(rowView("${profName()}'s list", ftl))
            val rl = recents().filter { it.kind == "live" }.take(20); if (rl.isNotEmpty()) col.addView(rowView("${profName()} watched live", rl))
        } else if (fv.isNotEmpty()) col.addView(rowView("${profName()}'s list", fv))
        fun cached(k: String, w: String) = smart["$k|$w"] ?: emptyList()
        cached("movie", "@recent").let { if (it.isNotEmpty()) col.addView(rowView("Recently added movies", it.take(24))) }
        cached("movie", "@top").let { if (it.isNotEmpty()) col.addView(rowView("Top rated movies", it.take(24))) }
        cached("movie", "@new").let { if (it.isNotEmpty()) col.addView(rowView("New releases", it.take(24))) }
        cached("series", "@top").let { if (it.isNotEmpty()) col.addView(rowView("Top rated series", it.take(24))) }
        val l = visible("live", live); if (l.isNotEmpty()) col.addView(rowView("Live TV", l.take(30)))
        val m = visible("movie", movies); if (m.isNotEmpty()) col.addView(rowView("Movies", m.take(24)))
        val s = visible("series", series); if (s.isNotEmpty()) col.addView(rowView("TV Series", s.take(24)))
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
        val day = System.currentTimeMillis() / 86_400_000L
        // banner = best rated + newest titles that have a poster (falls back to a daily shuffle until the lists are ready)
        val best = (smart["movie|@top"].orEmpty() + smart["series|@top"].orEmpty() + smart["movie|@new"].orEmpty() + smart["series|@new"].orEmpty()).filter { it.logo.isNotBlank() }
            .distinctBy { it.key }.sortedByDescending { it.rating + if (yearOf(it.name) >= java.util.Calendar.getInstance().get(java.util.Calendar.YEAR) - 1) 2f else 0f }.take(10)
        val pool = if (best.size >= 4) best else (visible("movie", movies).filter { it.logo.isNotBlank() }.take(60) + visible("series", series).filter { it.logo.isNotBlank() }.take(40))
            .shuffled(java.util.Random(day)).take(10)
        var idx = 0
        var feat: Item? = pool.firstOrNull()
        val infoCache = HashMap<String, Info>()
        val hero = FrameLayout(this).apply { setBackgroundColor(Color.parseColor("#120C0D")); clipChildren = true }
        val bgImg = ImageView(this).apply { scaleType = ImageView.ScaleType.CENTER_CROP; alpha = 0.85f }
        hero.addView(bgImg, FrameLayout.LayoutParams(-1, -1))
        hero.addView(View(this).apply { background = GradientDrawable(GradientDrawable.Orientation.BOTTOM_TOP, intArrayOf(BG, Color.parseColor("#99070506"), Color.TRANSPARENT)) }, FrameLayout.LayoutParams(-1, -1))
        hero.addView(View(this).apply { background = GradientDrawable(GradientDrawable.Orientation.LEFT_RIGHT, intArrayOf(Color.parseColor("#E6070506"), Color.TRANSPARENT)) }, FrameLayout.LayoutParams(-1, -1))
        hero.addView(View(this).apply { setBackgroundColor(BG) }, FrameLayout.LayoutParams(-1, dp(4), Gravity.BOTTOM))   // hides the thin line the zoom left at the bottom edge
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(40), 0, dp(40), dp(28)) }
        val label = mkText("MOVIE", 11f, GOLD, true).apply { letterSpacing = 0.34f }
        val title = mkText("Tonight, together", 36f, CREAM, true).apply { maxLines = 2; letterSpacing = 0.06f }
        val desc = mkText("", 16f, Color.parseColor("#cdbb9e")).apply { maxLines = 3; setPadding(0, dp(6), 0, dp(12)) }
        val dots = mkText("", 14f, RED, true).apply { setPadding(0, dp(8), 0, 0) }
        val rateTv = mkText("", 16f, GOLD, true).apply { letterSpacing = 0.08f; setPadding(0, dp(4), 0, 0) }
        col.addView(label); col.addView(title); col.addView(rateTv); col.addView(desc, LinearLayout.LayoutParams(dp(620), -2))
        val btns = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        val trailerBtn = mkButton("▶  Trailer", false) {
            val f = feat ?: return@mkButton
            val t = infoCache[f.key]?.trailer ?: ""
            if (t.isNotBlank()) try {
                startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(if (t.startsWith("http")) t else "https://www.youtube.com/watch?v=$t")))
            } catch (e: Exception) { Toast.makeText(this, "No YouTube app on this TV to play the trailer", Toast.LENGTH_LONG).show() }
        }.apply { visibility = View.GONE }
        if (feat != null) {
            btns.addView(mkButton("▶  Play", true) { feat?.let { f -> if (f.kind == "movie") play(listOf(f), 0) else pushPage { detailView(f) } } })
            btns.addView(mkButton("More info", false) { feat?.let { f -> pushPage { detailView(f) } } }, LinearLayout.LayoutParams(-2, -2).apply { leftMargin = dp(12) })
            btns.addView(trailerBtn, LinearLayout.LayoutParams(-2, -2).apply { leftMargin = dp(12) })
        }
        col.addView(btns); col.addView(dots)
        hero.addView(col, FrameLayout.LayoutParams(-1, -1, Gravity.BOTTOM or Gravity.START).apply { gravity = Gravity.BOTTOM })

        fun showInfo(f: Item, inf: Info) {
            if (feat?.key != f.key) return
            desc.text = inf.plot
            trailerBtn.visibility = if (inf.trailer.isNotBlank()) View.VISIBLE else View.GONE
            if (inf.backdrop.startsWith("http")) Img.load(inf.backdrop, bgImg, dp(900))
        }
        fun show(i: Int, animate: Boolean) {
            val f = pool.getOrNull(i) ?: return
            feat = f
            label.text = if (f.kind == "series") "SERIES" else "MOVIE"; title.text = f.name; desc.text = ""
            trailerBtn.visibility = View.GONE
            rateTv.text = ""; loadRatings(f, Ratings.yearOf(f.name)) { t -> if (feat?.key == f.key) rateTv.text = t }
            dots.text = pool.indices.joinToString(" ") { if (it == i) "●" else "·" }
            val go = {
                Img.load(f.logo, bgImg, dp(900))
                bgImg.scaleX = 1f; bgImg.scaleY = 1f
                bgImg.animate().alpha(0.85f).setDuration(600).start()
                // (slow zoom removed: it kept the GPU busy all the time and made the whole home screen stutter)
            }
            if (animate) bgImg.animate().alpha(0f).setDuration(400).withEndAction { go() }.start() else go()
            val cached = infoCache[f.key]
            if (cached != null) showInfo(f, cached)
            else xt?.let { x -> Thread {
                try {
                    val inf = if (f.kind == "movie") x.vodInfo(f.id) else x.seriesData(f.id).info
                    ui.post { infoCache[f.key] = inf; showInfo(f, inf) }
                } catch (e: Exception) { }
            }.start() }
        }
        if (pool.isNotEmpty()) show(0, false)
        val tick = object : Runnable {
            override fun run() {
                if (!hero.isAttachedToWindow || pool.size < 2 || playerRoot != null) return
                idx = (idx + 1) % pool.size; show(idx, true)
                hero.postDelayed(this, 10_000)
            }
        }
        hero.addOnAttachStateChangeListener(object : View.OnAttachStateChangeListener {
            override fun onViewAttachedToWindow(v: View) { hero.removeCallbacks(tick); hero.postDelayed(tick, 10_000) }
            override fun onViewDetachedFromWindow(v: View) { hero.removeCallbacks(tick) }
        })
        return hero
    }

    /** One pool of poster cards shared by every home row, so scrolling down does not inflate hundreds of new cards. */
    private val posterPool = RecyclerView.RecycledViewPool().apply { setMaxRecycledViews(0, 40) }

    private fun rowView(titleText: String, items: List<Item>): View {
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; clipChildren = false; setPadding(dp(32), dp(14), 0, dp(6)) }
        box.addView(mkText(titleText.uppercase(), 15f, GOLD, true).apply { letterSpacing = 0.26f; setPadding(dp(4), 0, 0, dp(2)) })
        val rv = RecyclerView(this).apply {
            layoutManager = LinearLayoutManager(this@MainActivity, LinearLayoutManager.HORIZONTAL, false).apply { initialPrefetchItemCount = 6 }
            setHasFixedSize(true); setItemViewCacheSize(6); setRecycledViewPool(posterPool)
            adapter = PosterAdapter(this@MainActivity, items, { l, p -> openAny(l, p) }, { itemMenu(it) })
            clipChildren = false; clipToPadding = false; setPadding(0, dp(6), dp(30), dp(10)); itemAnimator = null
        }
        box.addView(rv, LinearLayout.LayoutParams(-1, dp(tileW() * 3 / 2 + 74)))
        return box
    }

    // =====================================================================================
    // MOVIES / SERIES / MY LIST / SEARCH grids
    // =====================================================================================
    private fun gridPage(kind: String): View {
        val base = visible(kind, if (kind == "movie") movies else series)
        val counts = base.groupingBy { it.group }.eachCount()
        val specials = listOf("@recent", "@top", "@new", "@hollywood").filter { kind == "movie" || it != "@hollywood" }.filter { smartList(kind, it).isNotEmpty() }
        val groups = specials + sortGroups(kind, counts.keys)
        var sel = catFor[kind]; if (sel != null && sel !in groups) sel = null; catFor[kind] = sel
        fun shown(): List<Item> { val c = catFor[kind]; return if (c == null) base else if (c.startsWith("@")) smartList(kind, c) else base.filter { it.group == c } }
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(BG); setPadding(dp(32), dp(22), dp(10), 0) }
        root.addView(eyebrow(if (kind == "movie") "MOVIES" else "TV SERIES"))
        val heading = mkText("", 30f, CREAM, true)
        root.addView(heading)
        val grid = RecyclerView(this)
        val cards = PosterAdapter(this, shown(), { l, p -> openAny(l, p) }, { itemMenu(it) })
        fun upd() { heading.text = (if (kind == "movie") "Movies" else "TV Series") + "   ·   ${shown().size}" }
        upd()
        val labels = listOf("All  (${base.size})") + groups.map { if (it.startsWith("@")) "★ ${smartTitle(it)}  (${smartList(kind, it).size})" else (if (isFavCat(kind, it)) "★ " else "") + "$it  (${counts[it]})" }
        val chips = RecyclerView(this).apply {
            layoutManager = LinearLayoutManager(this@MainActivity, LinearLayoutManager.HORIZONTAL, false)
            adapter = ChipAdapter(this@MainActivity, labels, if (catFor[kind] == null) 0 else groups.indexOf(catFor[kind]) + 1, false,
                { i -> catFor[kind] = if (i == 0) null else groups[i - 1]; cards.items = shown(); cards.notifyDataSetChanged(); grid.scrollToPosition(0); upd() },
                { i -> if (i > 0 && !groups[i - 1].startsWith("@")) groupMenu(kind, groups[i - 1]) })
            clipChildren = false; clipToPadding = false; setPadding(0, dp(8), 0, dp(6))
        }
        root.addView(chips, LinearLayout.LayoutParams(-1, -2))
        val span = maxOf(1, (resources.displayMetrics.widthPixels - dp(60)) / (dp(tileW()) + dp(14)))
        grid.apply { layoutManager = GridLayoutManager(this@MainActivity, span); adapter = cards; clipChildren = false; clipToPadding = false; setPadding(0, dp(8), 0, dp(40)); itemAnimator = null }
        root.addView(grid, LinearLayout.LayoutParams(-1, 0, 1f))
        grid.post { (grid.getChildAt(0) ?: chips.getChildAt(0))?.requestFocus() }
        return root
    }

    private fun plainGrid(label: String, headingText: String, items: List<Item>, emptyMsg: String): View {
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(BG); setPadding(dp(32), dp(22), dp(10), 0) }
        root.addView(eyebrow(label))
        root.addView(mkText(headingText, 30f, CREAM, true).apply { setPadding(0, 0, 0, dp(8)) })
        if (items.isEmpty()) { root.addView(mkText(emptyMsg, 18f, GRAY)); return root }
        val span = maxOf(1, (resources.displayMetrics.widthPixels - dp(60)) / (dp(tileW()) + dp(14)))
        val grid = RecyclerView(this).apply {
            layoutManager = GridLayoutManager(this@MainActivity, span); adapter = PosterAdapter(this@MainActivity, items, { l, p -> openAny(l, p) }, { itemMenu(it) })
            clipChildren = false; clipToPadding = false; setPadding(0, dp(8), 0, dp(40)); itemAnimator = null
        }
        root.addView(grid, LinearLayout.LayoutParams(-1, 0, 1f)); grid.post { grid.getChildAt(0)?.requestFocus() }
        return root
    }

    private fun kidsListPage(): View {
        val scroll = ScrollView(this).apply { setBackgroundColor(BG); isFillViewport = true; clipChildren = false }
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; clipChildren = false; setPadding(0, dp(18), 0, dp(24)) }
        col.addView(eyebrow("MY LIST").apply { setPadding(dp(32), 0, 0, 0) })
        col.addView(mkText("Kids' list", 26f, CREAM, true).apply { setPadding(dp(32), dp(6), 0, dp(10)) })
        val fv = favs().filter { kidsOk(it) }
        if (fv.isEmpty()) col.addView(mkItalic("Nothing saved yet. Hold OK on a cartoon or show to add it here.", 16f, GRAY).apply { setPadding(dp(32), dp(8), 0, 0) })
        else col.addView(rowView("Saved", fv))
        scroll.addView(col, FrameLayout.LayoutParams(-1, -2))
        scroll.post { (findFirstFocusable(col, 1))?.requestFocus() }
        return scroll
    }

    private fun listPage(): View {
        if (profile() == "kids") return kidsListPage()
        val mr = favsOf("mr"); val mrs = favsOf("mrs")
        val mrsKeys = mrs.map { it.key }.toSet()
        val both = mr.filter { it.key in mrsKeys }
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(BG); setPadding(dp(32), dp(18), dp(24), 0) }
        root.addView(eyebrow("WATCHLIST"))
        root.addView(mkText("What shall we watch tonight?", 26f, CREAM, true).apply { setPadding(0, dp(6), 0, 0) })
        root.addView(mkItalic("You are adding as ${profName()}  ·  change who is watching with the profile button in the top bar  ·  hold OK on any title for more", 14f, GRAY).apply { setPadding(0, dp(2), 0, dp(10)) })
        val cols = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; clipChildren = false }
        val grids = ArrayList<RecyclerView>()
        fun column(title: String, sub: String, items: List<Item>, accent: Int, empty: String) {
            val c = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; clipChildren = false; setPadding(dp(8), 0, dp(8), 0) }
            c.addView(mkText("$title  ·  ${items.size}", 14f, accent, true).apply { letterSpacing = 0.2f })
            c.addView(mkItalic(sub, 13f, MUTED).apply { setPadding(0, 0, 0, dp(4)) })
            c.addView(View(this).apply { setBackgroundColor(Color.parseColor("#1FEBDDC4")) }, LinearLayout.LayoutParams(-1, dp(1)))
            if (items.isEmpty()) c.addView(mkItalic(empty, 15f, MUTED).apply { setPadding(0, dp(14), dp(10), 0) })
            else {
                val g = RecyclerView(this).apply {
                    layoutManager = GridLayoutManager(this@MainActivity, 2)
                    adapter = PosterAdapter(this@MainActivity, items, { l, p -> openAny(l, p) }, { itemMenu(it) })
                    clipChildren = false; clipToPadding = false; setPadding(0, dp(10), 0, dp(40)); itemAnimator = null
                }
                grids.add(g); c.addView(g, LinearLayout.LayoutParams(-1, 0, 1f))
            }
            cols.addView(c, LinearLayout.LayoutParams(0, -1, 1f))
        }
        column("MR'S LIST", "saved by him", mr, GOLD, "Nothing yet.")
        column("TOGETHER", "on both lists", both, ROSE, "Titles you both saved appear here. Hold OK on a title and choose “Add to both lists”.")
        column("MRS'S LIST", "saved by her", mrs, GOLD, "Nothing yet.")
        root.addView(cols, LinearLayout.LayoutParams(-1, 0, 1f))
        root.post { grids.firstOrNull { g -> g.getChildAt(0) != null }?.getChildAt(0)?.requestFocus() }
        return root
    }

    private fun searchView(): View {
        val q = query
        val toks = q.lowercase().split(' ', '-', '.', '_').filter { it.isNotBlank() }
        val first = toks.firstOrNull() ?: q.lowercase()
        fun score(it: Item): Int {
            val n = it.name.lowercase()
            val k = when (it.kind) { "movie" -> 0; "series" -> 1; else -> 2 }
            val w = if (n.startsWith(first)) 0 else if (n.contains(" $first")) 1 else 2
            return w * 3 + k
        }
        val all = (visible("movie", movies) + visible("series", series) + visible("live", live))
            .filter { x -> val n = x.name.lowercase(); toks.all { t -> n.contains(t) } }
            .sortedWith(compareBy({ score(it) }, { -it.rating }))
            .take(300)
        return plainGrid("SEARCH", "“$q”   ·   ${all.size}", all, "Nothing matches “$q”.")
    }

    private fun detailView(item: Item): View {
        val scroll = ScrollView(this).apply { setBackgroundColor(BG); isFillViewport = true; clipChildren = false }
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val hero = FrameLayout(this)
        val bgImg = ImageView(this).apply { scaleType = ImageView.ScaleType.CENTER_CROP; alpha = 0.9f }
        hero.addView(bgImg, FrameLayout.LayoutParams(-1, -1))
        hero.addView(View(this).apply { background = GradientDrawable(GradientDrawable.Orientation.BOTTOM_TOP, intArrayOf(BG, Color.parseColor("#B3070506"), Color.TRANSPARENT)) }, FrameLayout.LayoutParams(-1, -1))
        hero.addView(View(this).apply { background = GradientDrawable(GradientDrawable.Orientation.LEFT_RIGHT, intArrayOf(Color.parseColor("#F0070506"), Color.TRANSPARENT)) }, FrameLayout.LayoutParams(-1, -1))
        Img.load(item.logo, bgImg, dp(900))
        val back = mkButton("←  Back", false) { onBackPressed() }
        val info = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(40), 0, dp(40), dp(28)) }
        info.addView(eyebrow(if (item.kind == "series") "SERIES" else "MOVIE"))
        info.addView(mkText(item.name, 34f, CREAM, true).apply { maxLines = 2; setPadding(0, dp(6), 0, 0) })
        val rate = mkText("", 16f, GOLD, true).apply { letterSpacing = 0.08f; setPadding(0, dp(4), 0, 0) }
        info.addView(rate)
        val meta = mkItalic(item.group, 17f, GOLD).apply { setPadding(0, dp(6), 0, dp(4)) }
        val plot = mkText("Loading details…", 16f, Color.parseColor("#cdbb9e")).apply { maxLines = 5 }
        val cast = mkText("", 14f, GRAY).apply { setPadding(0, dp(4), 0, dp(12)); maxLines = 2 }
        info.addView(meta); info.addView(plot, LinearLayout.LayoutParams(dp(680), -2)); info.addView(cast, LinearLayout.LayoutParams(dp(680), -2))
        val btnRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        fun favLabel() = (if (isFav(item)) "♥  In ${profName()}'s list" else "♡  ${profName()}'s list").uppercase()
        val favBtn = mkButton("", false) {}
        favBtn.text = favLabel()
        favBtn.setOnClickListener { toggleFav(item); favBtn.text = favLabel() }
        val trailerBtn = mkButton("▶  Trailer", false) {}.apply { visibility = View.GONE }
        val playBtn = mkButton("▶  Play", true) { if (item.kind == "movie") play(listOf(item), 0) }
        btnRow.addView(playBtn); btnRow.addView(favBtn, LinearLayout.LayoutParams(-2, -2).apply { leftMargin = dp(12) })
        btnRow.addView(trailerBtn, LinearLayout.LayoutParams(-2, -2).apply { leftMargin = dp(12) })
        info.addView(btnRow)
        hero.addView(info, FrameLayout.LayoutParams(-1, -1, Gravity.BOTTOM or Gravity.START).apply { gravity = Gravity.BOTTOM })
        col.addView(back, LinearLayout.LayoutParams(-2, -2).apply { setMargins(dp(32), dp(14), 0, dp(8)) })   // own row above the banner, so it can never sit on the title
        col.addView(hero, LinearLayout.LayoutParams(-1, dp(420)))
        val seasonsBox = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(32), dp(10), dp(32), dp(40)) }
        col.addView(seasonsBox)
        scroll.addView(col, FrameLayout.LayoutParams(-1, -2))
        loadRatings(item, Ratings.yearOf(item.name)) { t -> if (rate.isAttachedToWindow || t.isNotBlank()) rate.text = t }
        fun fill(inf: Info) {
            val bits = ArrayList<String>(); if (inf.year.isNotBlank()) bits += inf.year
            if ((inf.rating.toDoubleOrNull() ?: 0.0) > 0) bits += "★ ${inf.rating}"; if (inf.genre.isNotBlank()) bits += inf.genre
            meta.text = if (bits.isEmpty()) item.group else bits.joinToString("   ·   ")
            plot.text = inf.plot.ifBlank { "No description from your provider." }
            cast.text = if (inf.cast.isNotBlank()) "Starring: ${inf.cast}" else ""
            if (inf.backdrop.startsWith("http")) Img.load(inf.backdrop, bgImg, dp(900))
            if (inf.trailer.isNotBlank()) {
                trailerBtn.visibility = View.VISIBLE
                trailerBtn.setOnClickListener {
                    val t = inf.trailer
                    try { startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(if (t.startsWith("http")) t else "https://www.youtube.com/watch?v=$t"))) }
                    catch (e: Exception) { Toast.makeText(this, "No YouTube app on this TV to play the trailer", Toast.LENGTH_LONG).show() }
                }
            }
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
                        playBtn.setOnClickListener { val resume = d.seasons.values.flatten().lastOrNull { savedPos(it) > 10_000 }; val l = d.seasons.values.flatten(); if (l.isNotEmpty()) play(l, if (resume != null) l.indexOf(resume) else 0, true) }
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
                    setOnFocusChangeListener { v, f -> v.background = rbg(if (f) Color.parseColor("#26C9475C") else Color.parseColor("#14FFFFFF"), if (f) RED else Color.TRANSPARENT, 10, 2) }
                    setOnClickListener { play(eps, i, true) }
                }
                val thumb = ImageView(this).apply { scaleType = ImageView.ScaleType.CENTER_CROP; background = rbg(CARD, Color.TRANSPARENT, 6); clipToOutline = true; outlineProvider = ViewOutlineProvider.BACKGROUND }
                Img.load(e.logo, thumb, dp(160)); row.addView(thumb, LinearLayout.LayoutParams(dp(150), dp(84)).apply { rightMargin = dp(16) })
                row.addView(mkText(e.name + if (done) "     ✓ started" else "", 18f, CREAM, true))
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
        val groups = sortGroups("live", base.map { it.group }.distinct())
        val labels = listOf("All channels", "★  Favorites", "Recently watched") + groups.map { (if (isFavCat("live", it)) "★ " else "") + it }
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
        c1.addView(mkText("Channels", 30f, CREAM, true))
        val countTv = mkText("", 13f, GRAY).apply { setPadding(0, 0, 0, dp(10)) }; c1.addView(countTv)
        val chAd = ChannelAdapter(this, emptyList(), { it -> onChannelFocus(it) }, { l, p -> lastLiveKey = l[p].key; play(l, p) }, { itemMenu(it) })
        val chRv = RecyclerView(this)
        val catRv = RecyclerView(this).apply { layoutManager = LinearLayoutManager(this@MainActivity) }
        val showCat = { i: Int -> liveCat = i; prefs.edit().putInt("liveCat", i).apply(); val l = listFor(i); chAd.items = l; chAd.notifyDataSetChanged(); chRv.scrollToPosition(0); countTv.text = if (l.isEmpty()) "no channels here" else "${l.size} channels" }
        catRv.adapter = ChipAdapter(this, labels, liveCat, true,
            { i -> showCat(i); chRv.post { chRv.getChildAt(0)?.requestFocus() } },
            { i -> if (i >= 3) groupMenu("live", groups[i - 3]) })
        c1.addView(catRv, LinearLayout.LayoutParams(-1, 0, 1f))
        root.addView(c1, LinearLayout.LayoutParams(dp(215), -1).apply { rightMargin = dp(12) })

        // column 2: channels
        val first = listFor(liveCat); chAd.items = first; countTv.text = "${first.size} channels"
        chRv.apply { layoutManager = LinearLayoutManager(this@MainActivity); adapter = chAd; clipChildren = false; clipToPadding = false; setPadding(0, 0, dp(10), dp(30)); itemAnimator = null; setHasFixedSize(true); setItemViewCacheSize(16) }
        val favKeys = favs().map { f -> f.key }.toSet()
        val favList = base.filter { it.key in favKeys }
        val mid = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        if (favList.isNotEmpty()) {
            mid.addView(mkText("★  Your favourite channels", 14f, GRAY, true).apply { setPadding(dp(4), 0, 0, dp(2)) })
            val fr = RecyclerView(this).apply {
                layoutManager = LinearLayoutManager(this@MainActivity, LinearLayoutManager.HORIZONTAL, false)
                adapter = ChipAdapter(this@MainActivity, favList.map { it.name }, -1, false, { i -> lastLiveKey = favList[i].key; play(favList, i) }, { i -> itemMenu(favList[i]) })
                clipChildren = false; clipToPadding = false
            }
            mid.addView(fr, LinearLayout.LayoutParams(-1, -2).apply { bottomMargin = dp(8) })
        }
        mid.addView(chRv, LinearLayout.LayoutParams(-1, 0, 1f))
        root.addView(mid, LinearLayout.LayoutParams(0, -1, 1f))

        // column 3: preview panel
        val p = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(16), dp(16), dp(16), dp(16)); background = rbg(Color.parseColor("#120C0D"), Color.parseColor("#22FFFFFF"), 16, 1) }
        val vBox = FrameLayout(this).apply { setBackgroundColor(Color.BLACK) }
        val pv = android.view.LayoutInflater.from(this).inflate(R.layout.preview_player, null) as PlayerView
        vBox.addView(pv, FrameLayout.LayoutParams(-1, -1))
        p.addView(vBox, LinearLayout.LayoutParams(-1, dp(225)))
        val chip = mkText("●  LIVE   ·   sound off", 12f, RED, true).apply { setPadding(0, dp(10), 0, dp(4)) }; p.addView(chip); previewChip = chip
        val title = mkText("", 24f, CREAM, true).apply { maxLines = 2 }
        val cat = mkText("", 14f, GRAY)
        val nowLabel = mkText("NOW PLAYING", 11f, RED, true).apply { letterSpacing = 0.2f; setPadding(0, dp(10), 0, dp(2)); visibility = View.GONE }
        val nowT = mkText("", 18f, CREAM, true).apply { maxLines = 2 }
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
                            textSize = 14f; setTextColor(CREAM); maxLines = 1; setPadding(0, dp(2), 0, dp(2))
                        })
                    }
                }
            }
        }
    }
    fun hmOf(sec: Long): String = hm(sec)
    private fun hm(sec: Long): String { val c = java.util.Calendar.getInstance(); c.timeInMillis = sec * 1000; return String.format("%02d:%02d", c.get(java.util.Calendar.HOUR_OF_DAY), c.get(java.util.Calendar.MINUTE)) }

    private fun startPreview(it: Item) {
        val pn = panel ?: return
        previewAttempt = 0
        val p: ExoPlayer = preview ?: newPlayer(false).also { np ->
            np.volume = 0f; preview = np; pn.video.player = np
            np.addListener(object : Player.Listener {
                override fun onRenderedFirstFrame() { previewChip?.text = "●  LIVE   ·   sound off" }
                override fun onPlayerError(error: PlaybackException) {
                    val cur = previewItem ?: return
                    if (previewAttempt < 3) { previewAttempt++; previewChip?.text = "●  retrying preview… (${error.errorCodeName})"; loadInto(np, cur, previewAttempt) }
                    else previewChip?.text = "●  preview failed: ${error.errorCodeName}  -  press OK to watch full screen"
                }
            })
        }
        previewChip?.text = "●  loading preview…"
        loadInto(p, it, 0)
    }
    private fun releasePreview() { ui.removeCallbacks(previewRun); preview?.release(); preview = null; panel?.video?.player = null }

    // =====================================================================================
    // SETTINGS
    // =====================================================================================
    private fun hostLabel(): String {
        val server = prefs.getString("server", "") ?: ""
        if (server.isNotBlank()) return try { android.net.Uri.parse(server).host ?: server } catch (e: Throwable) { server }
        return if ((prefs.getString("m3u", "") ?: "").isNotBlank()) "an M3U playlist" else "nothing yet"
    }

    private fun curVersionCode(): Int = try { packageManager.getPackageInfo(packageName, 0).let { if (android.os.Build.VERSION.SDK_INT >= 28) it.longVersionCode.toInt() else it.versionCode } } catch (e: Throwable) { 0 }
    private fun curVersionName(): String = try { packageManager.getPackageInfo(packageName, 0).versionName ?: "" } catch (e: Throwable) { "" }

    private val APK_URL = "https://github.com/mohammedaalnoaimi-dot/91-TV/releases/download/latest-build/91TV.apk"
    private val VERSION_URL = "https://raw.githubusercontent.com/mohammedaalnoaimi-dot/91-TV/main/app/build.gradle.kts"

    /** Reads the newest version number published with the app, and offers to install it when it is newer than this one. */
    private fun checkUpdate() {
        Toast.makeText(this, "Checking for updates…", Toast.LENGTH_SHORT).show()
        Thread {
            try {
                val t = Http.get(VERSION_URL)
                val code = Regex("versionCode\\s*=\\s*(\\d+)").find(t)!!.groupValues[1].toInt()
                val name = Regex("versionName\\s*=\\s*\"([^\"]+)\"").find(t)!!.groupValues[1]
                ui.post {
                    if (code > curVersionCode()) {
                        android.app.AlertDialog.Builder(this).setTitle("Update available")
                            .setMessage("Version $name is ready. You have ${curVersionName()}. Download and install it now?")
                            .setPositiveButton("Update") { _, _ -> installUpdate(code) }
                            .setNegativeButton("Later", null).show()
                    } else Toast.makeText(this, "You have the latest version (${curVersionName()})", Toast.LENGTH_LONG).show()
                }
            } catch (e: Throwable) { ui.post { Toast.makeText(this, "Could not check for updates: ${e.message ?: e.javaClass.simpleName}", Toast.LENGTH_LONG).show() } }
        }.start()
    }

    private fun installUpdate(minCode: Int) {
        if (android.os.Build.VERSION.SDK_INT >= 26 && !packageManager.canRequestPackageInstalls()) {
            android.app.AlertDialog.Builder(this).setTitle("Allow installs")
                .setMessage("Android needs your OK before 91 TV can install an update. Press Open settings, switch it on for 91 TV, then come back and press Check for updates again.")
                .setPositiveButton("Open settings") { _, _ ->
                    try { startActivity(android.content.Intent(android.provider.Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, android.net.Uri.parse("package:$packageName"))) }
                    catch (e: Throwable) { Toast.makeText(this, "Open Settings > Apps > 91 TV > Install unknown apps", Toast.LENGTH_LONG).show() }
                }.setNegativeButton("Cancel", null).show()
            return
        }
        Toast.makeText(this, "Downloading the update…", Toast.LENGTH_LONG).show()
        Thread {
            try {
                val f = java.io.File(cacheDir, "update.apk")
                val c = Http.open(APK_URL)
                try { c.inputStream.use { i -> f.outputStream().use { o -> i.copyTo(o) } } } finally { c.disconnect() }
                val info = packageManager.getPackageArchiveInfo(f.absolutePath, 0)
                val got = info?.let { if (android.os.Build.VERSION.SDK_INT >= 28) it.longVersionCode.toInt() else it.versionCode } ?: 0
                if (got < minCode) { ui.post { Toast.makeText(this, "The new version is still being prepared. Try again in a few minutes.", Toast.LENGTH_LONG).show() }; return@Thread }
                ui.post {
                    val uri = androidx.core.content.FileProvider.getUriForFile(this, "$packageName.fileprovider", f)
                    startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW).setDataAndType(uri, "application/vnd.android.package-archive")
                        .addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION or android.content.Intent.FLAG_ACTIVITY_NEW_TASK))
                }
            } catch (e: Throwable) { ui.post { Toast.makeText(this, "Update failed: ${e.message ?: e.javaClass.simpleName}", Toast.LENGTH_LONG).show() } }
        }.start()
    }

    private fun settingsView(): View {
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(BG); setPadding(dp(40), dp(26), dp(40), dp(20)) }
        root.addView(eyebrow("SETTINGS"))
        root.addView(mkText("Settings", 28f, CREAM, true).apply { setPadding(0, dp(4), 0, dp(10)) })
        var firstRow: View? = null
        fun head(t: String) { root.addView(mkText(t, 11f, GOLD, true).apply { letterSpacing = 0.34f; setPadding(dp(4), dp(14), 0, dp(6)) }) }
        fun row(label: String, sub: String, act: () -> Unit) {
            val r = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL; isFocusable = true; setPadding(dp(20), dp(11), dp(20), dp(11)); background = rbg(Color.parseColor("#14EBDDC4"), Color.TRANSPARENT, 2, 2)
                setOnFocusChangeListener { v, f -> v.background = rbg(if (f) Color.parseColor("#26C9475C") else Color.parseColor("#14EBDDC4"), if (f) CREAM else Color.TRANSPARENT, 2, 2) }
                setOnClickListener { act() }
            }
            r.addView(mkText(label, 17f, CREAM, true)); r.addView(mkText(sub, 14f, GRAY))
            root.addView(r, LinearLayout.LayoutParams(dp(760), -2).apply { setMargins(0, 0, 0, dp(6)) })
            if (firstRow == null) firstRow = r
        }
        head("YOU")
        row("Who is watching", "Now: ${profName()}.  Press to choose Mr, Mrs, Together or Kids") { showProfilePicker(false) }
        head("PRAYER TIMES  ·  BAHRAIN")
        row("Calculation method", "${Prayer.methodName(prefs)}  - press to change (Gulf Region is the usual one for Bahrain). Times come from Aladhan and can differ by a minute or two from the official timetable") {
            val i = Prayer.METHODS.indexOfFirst { it.first == prefs.getInt("ptMethod", 8) }
            prefs.edit().putInt("ptMethod", Prayer.METHODS[(i + 1) % Prayer.METHODS.size].first).apply(); Prayer.reset(); Prayer.ensure(prefs) { refreshPage() }; refreshPage()
        }
        row("Next prayer in the top bar", (if (prefs.getBoolean("ptWidget", true)) "ON" else "OFF") + "  - press to switch") { prefs.edit().putBoolean("ptWidget", !prefs.getBoolean("ptWidget", true)).apply(); updateChrome(); refreshPage() }
        row("Prayer reminder", (prefs.getInt("ptRemind", 0).let { if (it == 0) "OFF" else "$it minutes before each prayer, and again at prayer time (small notice and a sound)" }) + "  - press to change") {
            val i = Prayer.REMIND.indexOf(prefs.getInt("ptRemind", 0)); prefs.edit().putInt("ptRemind", Prayer.REMIND[(i + 1) % Prayer.REMIND.size]).apply(); refreshPage()
        }
        head("LIBRARY")
        row("Provider", "Change server, login or M3U playlist") { setupView() }
        row("Log out from this host", "Signed in to: ${hostLabel()}  - removes the server, login and downloaded lists from this TV") {
            android.app.AlertDialog.Builder(this).setTitle("Log out from this host?")
                .setMessage("The server, username, password and downloaded lists will be removed from this TV. Your 91 TV licence stays. You can add a provider again afterwards.")
                .setPositiveButton("Log out") { _, _ ->
                    prefs.edit().remove("server").remove("user").remove("pass").remove("m3u").remove("recent").remove("recent_mrs").remove("recent_kids").remove("recent_together").apply()
                    Cache.clear(this); xt = null; setData(emptyList(), emptyList(), emptyList())
                    Toast.makeText(this, "Logged out", Toast.LENGTH_SHORT).show(); setupView()
                }
                .setNegativeButton("Cancel", null).show()
        }
        row("Show all hidden categories", "${hidden().size} hidden right now") { prefs.edit().remove("hidden").apply(); visCache.clear(); smart.clear(); Toast.makeText(this, "All categories shown again", Toast.LENGTH_SHORT).show(); refreshPage() }
        row("Reload lists", "Download channels, movies and series again (normally automatic every 6 hours)") { startLoading(true) }
        head("RATINGS")
        row("IMDb and Rotten Tomatoes", (if ((prefs.getString("omdb", "") ?: "").isBlank()) "OFF - press OK and type your free OMDb key (omdbapi.com). Until then only the provider's score is shown" else "ON - key saved. Press OK to change it") ) {
            val et = EditText(this).apply { hint = "OMDb key, e.g. a1b2c3d4"; setSingleLine(); setText(prefs.getString("omdb", "")); textSize = 22f }
            android.app.AlertDialog.Builder(this).setTitle("OMDb key").setView(et)
                .setPositiveButton("Save") { _, _ -> prefs.edit().putString("omdb", et.text.toString().trim()).apply(); refreshPage() }
                .setNegativeButton("Cancel", null).show()
        }
        head("PICTURE AND SOUND")
        val cap = AudioCapabilities.getCapabilities(this)
        val tvAtmos = cap.supportsEncoding(C.ENCODING_E_AC3_JOC)
        row("Audio output", (if (prefs.getBoolean("pcm", false)) "Stereo PCM (safe mode, no Dolby)" else "Dolby passthrough (Atmos / Dolby Digital+ sent to your TV or soundbar)") + "\nYour TV reports: Atmos " + (if (tvAtmos) "YES" else "NO") + ", Dolby Digital+ " + (if (cap.supportsEncoding(C.ENCODING_E_AC3)) "YES" else "NO") + "  - press to switch") { prefs.edit().putBoolean("pcm", !prefs.getBoolean("pcm", false)).apply(); refreshPage() }
        val hm0 = prefs.getInt("hdrmode", if (prefs.getBoolean("notunnel", false)) 1 else 0)
        row("HDR / Dolby Vision mode", when (hm0) { 1 -> "Normal (try this if HDR looks wrong)"; 2 -> "Bright SDR (HDR is converted to normal picture - use this if HDR is too dark)"; else -> "Tunnelled (used automatically for Dolby Vision, HDR10 and HLG, fixes washed-out picture on many TVs)" } + "  - press to switch") {
            val n = (hm0 + 1) % 3; prefs.edit().putInt("hdrmode", n).putBoolean("notunnel", n != 0).apply(); refreshPage()
        }
        row("Check Dolby Atmos", "See what your TV and soundbar can receive") { atmosCheck() }
        head("SCREENSAVER")
        row("Remote click sound", (if (prefs.getBoolean("noclick", false)) "OFF" else "ON - soft click when moving between tiles") + "  - press to switch") { prefs.edit().putBoolean("noclick", !prefs.getBoolean("noclick", false)).apply(); refreshPage() }
        row("Screensaver", (if (prefs.getBoolean("nosaver", false)) "OFF" else "ON - after 2 minutes of no button presses") + "  - press to switch") { prefs.edit().putBoolean("nosaver", !prefs.getBoolean("nosaver", false)).apply(); bumpIdle(); refreshPage() }
        row("Screensaver style", (if (prefs.getString("saverStyle", "clock") == "clock") "Quiet clock with date, next prayer and what you were watching (gentle on the screen)" else "Slideshow of movie posters") + "  - press to switch") { prefs.edit().putString("saverStyle", if (prefs.getString("saverStyle", "clock") == "clock") "posters" else "clock").apply(); refreshPage() }
        if (Lic.REQUIRED) {
            head("LICENCE")
            if (!Lic.hasKey(prefs)) row("91 TV licence", "${Lic.summary(prefs)}  - press to enter a code or buy one at ninetyonetv.com") { activationView() }
            else row("91 TV licence", "${Lic.summary(prefs)}  - press to remove it from this TV, so the code can be used on another device") {
                android.app.AlertDialog.Builder(this).setTitle("Remove licence from this TV?")
                    .setMessage("91 TV will stop working here until a code is entered again.")
                    .setPositiveButton("Remove") { _, _ ->
                        Thread { val r = Lic.deactivate(prefs); ui.post { if (r == null) activationView("Licence removed from this TV.") else Toast.makeText(this, r, Toast.LENGTH_LONG).show() } }.start()
                    }
                    .setNegativeButton("Cancel", null).show()
            }
        }
        head("OTHER")
        row("Clear watch history", "Continue watching and recently watched (this profile)") { prefs.edit().remove(recentKey()).apply(); becauseSig = ""; Toast.makeText(this, "History cleared", Toast.LENGTH_SHORT).show() }
        row("Check for updates", "You have version ${curVersionName()}  - press to look for a newer one") { checkUpdate() }
        row("About", "91 TV ${curVersionName()} · long-press OK on anything to add to My List or hide its category") { }
        root.post { firstRow?.requestFocus() }
        return ScrollView(this).apply { isFillViewport = true; setBackgroundColor(BG); isVerticalScrollBarEnabled = false; addView(root, FrameLayout.LayoutParams(-1, -2)) }
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
        p.addAnalyticsListener(object : androidx.media3.exoplayer.analytics.AnalyticsListener {
            override fun onVideoDecoderInitialized(eventTime: androidx.media3.exoplayer.analytics.AnalyticsListener.EventTime, decoderName: String, initializedTimestampMs: Long, initializationDurationMs: Long) { vdec = decoderName }
        })
        p.trackSelectionParameters = p.trackSelectionParameters.buildUpon().setTrackTypeDisabled(C.TRACK_TYPE_TEXT, !prefs.getBoolean("subs", false)).build()
        p.setAudioAttributes(AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_MOVIE).build(), main)
        return p
    }

    @Suppress("DEPRECATION")
    private fun request4k(on: Boolean) {
        try {
            val lp = window.attributes
            if (on) {
                val modes = windowManager.defaultDisplay.supportedModes
                val m = modes.filter { it.physicalWidth >= 3840 }.sortedBy { Math.abs(it.refreshRate - 60f) }.firstOrNull()
                if (m != null) lp.preferredDisplayModeId = m.modeId
            } else lp.preferredDisplayModeId = 0
            window.attributes = lp
        } catch (e: Throwable) {}
    }

    @Suppress("DEPRECATION")
    private fun hdrTypes(): String = try {
        val t = windowManager.defaultDisplay.hdrCapabilities?.supportedHdrTypes ?: IntArray(0)
        if (t.isEmpty()) "NO HDR AT ALL" else t.joinToString(" + ") { when (it) { 1 -> "DOLBY VISION"; 2 -> "HDR10"; 3 -> "HLG"; 4 -> "HDR10+"; else -> "type$it" } }
    } catch (e: Throwable) { "unknown" }

    @Suppress("DEPRECATION")
    private fun modeInfo(): String = try {
        val m = windowManager.defaultDisplay.mode; "${m.physicalWidth}x${m.physicalHeight} @${m.refreshRate.toInt()}Hz  colorMode=${window.colorMode}  all modes: " + windowManager.defaultDisplay.supportedModes.map { "${it.physicalWidth}x${it.physicalHeight}@${it.refreshRate.toInt()}" }.distinct().joinToString(", ")
    } catch (e: Throwable) { "unknown" }


    // ---------- screensaver (after 2 minutes of no key presses while browsing) ----------
    private var saver: FrameLayout? = null
    private var saverFg: ImageView? = null
    private var saverBg: ImageView? = null
    private var saverTitle: TextView? = null
    private var saverList: List<Item> = emptyList()
    private var saverIdx = 0
    private val saverStart = Runnable { startSaver() }
    private val saverStep = Runnable { saverNext() }

    private fun bumpIdle() { ui.removeCallbacks(saverStart); if (playerRoot == null && !prefs.getBoolean("nosaver", false)) ui.postDelayed(saverStart, 120_000) }

    private var ambBox: LinearLayout? = null
    private var ambClock: TextView? = null
    private var ambDate: TextView? = null
    private var ambNext: TextView? = null
    private var ambUp: TextView? = null
    private var ambCount = 0

    private fun startAmbient() {
        val f = FrameLayout(this).apply { setBackgroundColor(BG); alpha = 0f }
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL }
        val clock = mkText("", 120f, CREAM).apply { gravity = Gravity.CENTER; letterSpacing = 0.04f; includeFontPadding = false }
        val date = mkText("", 15f, GOLD, true).apply { letterSpacing = 0.3f; gravity = Gravity.CENTER; setPadding(0, dp(8), 0, 0) }
        val next = mkItalic("", 22f, SOFT).apply { gravity = Gravity.CENTER; setPadding(0, dp(26), 0, 0) }
        val up = mkItalic("", 17f, GRAY).apply { gravity = Gravity.CENTER; setPadding(0, dp(10), 0, 0) }
        box.addView(clock); box.addView(date); box.addView(next); box.addView(up)
        val brand = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL }
        brand.addView(ImageView(this).apply { setImageResource(R.drawable.wordmark); scaleType = ImageView.ScaleType.FIT_CENTER; alpha = 0.85f }, LinearLayout.LayoutParams(dp(150), dp(23)))
        f.addView(box, FrameLayout.LayoutParams(-2, -2, Gravity.CENTER))
        f.addView(brand, FrameLayout.LayoutParams(-2, -2, Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL).apply { bottomMargin = dp(34) })
        (window.decorView as ViewGroup).addView(f, ViewGroup.LayoutParams(-1, -1))
        f.animate().alpha(1f).setDuration(900).start()
        saver = f; ambBox = box; ambClock = clock; ambDate = date; ambNext = next; ambUp = up; ambCount = 0
        ambientTick()
    }

    private fun ambientTick() {
        val box = ambBox ?: return
        val now = System.currentTimeMillis()
        ambClock?.text = Prayer.clock(now)
        ambDate?.text = (Prayer.longDate(now) + (Prayer.today?.hijri?.takeIf { it.isNotBlank() }?.let { "   ·   $it" } ?: "")).uppercase()
        val nx = Prayer.next(now)
        ambNext?.text = if (nx != null) "${nx.first} at ${Prayer.clock(nx.second)}   ·   in ${Prayer.left(nx.second - now)}" else ""
        val up = recents().firstOrNull { (it.kind == "movie" || it.kind == "episode") && savedPos(it) > 10_000 }
        ambUp?.text = if (up != null) "Continue watching:  ${up.name}" else ""
        if (ambCount++ % 6 == 0) {   // every minute drift a little so no pixel stays lit in one place
            val r = java.util.Random()
            box.animate().translationX((r.nextInt(120) - 60) * resources.displayMetrics.density).translationY((r.nextInt(80) - 40) * resources.displayMetrics.density).setDuration(5000).start()
        }
        ui.removeCallbacks(saverStep); ui.postDelayed(saverStep, 10_000)
    }

    private fun startSaver() {
        if (playerRoot != null || saver != null) return
        if ((prefs.getString("saverStyle", "clock") ?: "clock") == "clock") { startAmbient(); return }
        val pool = (visible("movie", movies) + visible("series", series)).filter { it.logo.isNotEmpty() }
        if (pool.isEmpty()) return
        saverList = pool.shuffled().take(60); saverIdx = 0
        val f = FrameLayout(this).apply { setBackgroundColor(Color.BLACK); alpha = 0f }
        val bg = ImageView(this).apply { scaleType = ImageView.ScaleType.CENTER_CROP; alpha = 0f }
        f.addView(bg, FrameLayout.LayoutParams(-1, -1))
        f.addView(View(this).apply { background = GradientDrawable(GradientDrawable.Orientation.BOTTOM_TOP, intArrayOf(Color.parseColor("#E6070506"), Color.TRANSPARENT)) }, FrameLayout.LayoutParams(-1, dp(220), Gravity.BOTTOM))
        val brand = ImageView(this).apply { setImageResource(R.drawable.wordmark); scaleType = ImageView.ScaleType.FIT_START }
        f.addView(brand, FrameLayout.LayoutParams(dp(190), dp(29), Gravity.TOP or Gravity.START).apply { setMargins(dp(40), dp(30), 0, 0) })
        val t = mkText("", 24f, CREAM, true).apply { gravity = Gravity.CENTER }
        f.addView(t, FrameLayout.LayoutParams(-1, -2, Gravity.BOTTOM).apply { setMargins(dp(40), 0, dp(40), dp(36)) })
        (window.decorView as ViewGroup).addView(f, ViewGroup.LayoutParams(-1, -1))
        f.animate().alpha(1f).setDuration(900).start()
        saver = f; saverFg = null; saverBg = bg; saverTitle = t
        saverNext()
    }

    /** Full-screen background only (no poster in the middle). Uses the film's wide backdrop when the provider has one. */
    private fun saverNext() {
        if (saver == null) return
        if (ambBox != null) { ambientTick(); return }
        val item = saverList[saverIdx % saverList.size]; saverIdx++
        val bg = saverBg ?: return
        fun show(url: String) {
            if (saver == null) return
            bg.animate().alpha(0f).setDuration(400).withEndAction {
                if (saver == null) return@withEndAction
                Img.load(url, bg, 1200); saverTitle?.text = item.name
                bg.scaleX = 1f; bg.scaleY = 1f
                bg.animate().alpha(0.95f).setDuration(700).start()
                bg.animate().scaleX(1.1f).scaleY(1.1f).setDuration(9000).start()
            }.start()
        }
        val x = xt
        if (x != null && item.kind != "live") Thread {
            val back = try { (if (item.kind == "movie") x.vodInfo(item.id) else x.seriesData(item.id).info).backdrop } catch (e: Exception) { "" }
            ui.post { show(if (back.startsWith("http")) back else item.logo) }
        }.start() else show(item.logo)
        ui.removeCallbacks(saverStep); ui.postDelayed(saverStep, 9000)
    }

    private fun stopSaver() {
        ui.removeCallbacks(saverStep)
        val f = saver ?: return
        saver = null; saverFg = null; saverBg = null; saverTitle = null
        ambBox = null; ambClock = null; ambDate = null; ambNext = null; ambUp = null
        (f.parent as? ViewGroup)?.removeView(f)
    }

    private fun atmosCheck() {
        val c = AudioCapabilities.getCapabilities(this)
        fun y(e: Int) = if (c.supportsEncoding(e)) "YES" else "no"
        val msg = "What your TV tells the app it can receive:\n\n" +
            "Dolby Digital (AC3):  " + y(C.ENCODING_AC3) + "\n" +
            "Dolby Digital Plus (E-AC3):  " + y(C.ENCODING_E_AC3) + "\n" +
            "DOLBY ATMOS (E-AC3 JOC):  " + y(C.ENCODING_E_AC3_JOC) + "\n" +
            "Dolby TrueHD:  " + y(C.ENCODING_DOLBY_TRUEHD) + "\n" +
            "DTS:  " + y(C.ENCODING_DTS) + "     DTS-HD:  " + y(C.ENCODING_DTS_HD) + "\n" +
            "Most channels:  " + c.maxChannelCount + "\n\n" +
            "App audio mode:  " + (if (prefs.getBoolean("pcm", false)) "Stereo PCM (no Dolby) - switch it in Settings" else "Dolby passthrough (correct for Atmos)") + "\n\n" +
            "To hear Atmos: the movie must have an Atmos track, your soundbar or TV must have Atmos on, and the app must be in passthrough. While a movie plays, press RIGHT: the info line says DOLBY ATMOS only when the track really is Atmos.\n\n" +
            "This list is what Android reports. I cannot hear your speakers, so only your soundbar can confirm Atmos is really playing."
        android.app.AlertDialog.Builder(this).setTitle("Dolby Atmos check").setMessage(msg).setPositiveButton("OK", null).show()
    }

    private fun audioDialog() {
        val p = player ?: return
        val groups = p.currentTracks.groups.filter { it.type == C.TRACK_TYPE_AUDIO }
        
        val subs = prefs.getBoolean("subs", false)
        val vf = p.videoFormat; val af = p.audioFormat
        val info = "INFO  video: " + (vf?.sampleMimeType?.removePrefix("video/") ?: "-") + " " + (vf?.codecs ?: "") + " " + (vf?.let { "${it.width}x${it.height}" } ?: "") +
            (if (vf?.sampleMimeType == "video/dolby-vision") "  = DOLBY VISION" else if (vf?.colorInfo?.colorTransfer == C.COLOR_TRANSFER_ST2084) "  = HDR10" else if (vf?.colorInfo?.colorTransfer == C.COLOR_TRANSFER_HLG) "  = HLG" else "") +
            "  |  audio: " + (af?.sampleMimeType?.removePrefix("audio/") ?: "-") + " " + (af?.codecs ?: "") + (if (af?.sampleMimeType == "audio/eac3-joc" || af?.codecs?.contains("joc") == true) "  = DOLBY ATMOS" else "")
        val labels = listOf(if (lastDiag.isNotEmpty()) lastDiag.replace("\n", "  |  ") else info, "Subtitles: " + (if (subs) "ON  (press to turn off)" else "OFF  (press to turn on)")) + groups.mapIndexed { n, g ->
            val f = g.getTrackFormat(0)
            "Track ${n + 1}:  ${f.language ?: "?"}  ·  ${if (f.channelCount > 0) f.channelCount.toString() + " ch" else ""}  ·  ${(f.sampleMimeType ?: "").removePrefix("audio/")}" + if (g.isSelected) "   ✓" else ""
        } + listOf("▶ Open in another player (Kodi, VLC, Just Player…)") + (if (playing?.kind == "live") listOf("▣ Continue in a small corner screen") else emptyList()) + listOf("⧉ Shrink to a floating window (stays when you leave the app)")
        val live = playing?.kind == "live"
        val pipIdx = labels.size - 1
        val cornerIdx = if (live) labels.size - 2 else -1
        val extIdx = labels.size - (if (live) 3 else 2)
        android.app.AlertDialog.Builder(this).setTitle("Audio / subtitles").setItems(labels.toTypedArray()) { _, i ->
            if (i == pipIdx) {
                if (!enterPip()) Toast.makeText(this, "This TV does not support a floating window", Toast.LENGTH_LONG).show()
            } else if (i == cornerIdx) {
                val cur = playing; if (cur != null) { leavePlayer(); startPip(cur) }
            } else if (i == 1) {
                val on = !prefs.getBoolean("subs", false); prefs.edit().putBoolean("subs", on).apply()
                p.trackSelectionParameters = p.trackSelectionParameters.buildUpon().setTrackTypeDisabled(C.TRACK_TYPE_TEXT, !on).build()
                playerView?.subtitleView?.visibility = if (on) View.VISIBLE else View.GONE
            } else if (i == extIdx) {
                val cur = playing
                if (cur != null) {
                    p.playWhenReady = false
                    try {
                        val intent = android.content.Intent(android.content.Intent.ACTION_VIEW).setDataAndType(android.net.Uri.parse(urlFor(cur, attempt)), "video/*").putExtra("title", cur.name)
                        startActivity(android.content.Intent.createChooser(intent, "Play with"))
                    } catch (e: Exception) { Toast.makeText(this, "No other video player installed on this TV", Toast.LENGTH_LONG).show() }
                }
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

    private var nextBtn: TextView? = null
    private fun hasNextEp(): Boolean { val c = zapList.getOrNull(zapIndex) ?: return false; return c.kind == "episode" && zapIndex + 1 < zapList.size }
    private fun goNextEpisode() {
        if (!hasNextEp()) return
        ui.removeCallbacks(nextRun); savePosition(); prefs.edit().remove("pos_" + zapList[zapIndex].key).apply()
        zapIndex++; startCurrent(); updateNextBtn()
    }
    /** "Next episode" button: visible with the controls, and automatically for the last 90 seconds of an episode. */
    private fun updateNextBtn() {
        val b = nextBtn ?: return
        val p = player; val d = p?.duration ?: -1L
        val ending = d > 0 && p != null && d - p.currentPosition < 90_000L
        val ctl = playerView?.isControllerFullyVisible == true
        if (hasNextEp() && (ending || ctl)) {
            val n = zapList[zapIndex + 1].name
            b.text = "NEXT EPISODE  ▶    " + (if (n.length > 38) n.take(36) + "…" else n) + "      (press ▲)"; b.visibility = View.VISIBLE
        } else b.visibility = View.GONE
        if (playerRoot != null && hasNextEp()) { ui.removeCallbacks(nextBtnTick); ui.postDelayed(nextBtnTick, 1500) }
    }
    private val nextBtnTick = Runnable { updateNextBtn() }
    private var chainNext = false
    private var prevLiveKey = ""
    private var numBuf = ""
    private val nextRun = Runnable { if (playerRoot != null && zapIndex + 1 < zapList.size) { zapIndex++; startCurrent() } }
    private val numRun = Runnable {
        val n = numBuf.toIntOrNull(); numBuf = ""
        if (playerRoot == null) return@Runnable
        if (n != null && n >= 1 && n <= zapList.size) { zapIndex = n - 1; lastLiveKey = zapList[zapIndex].key; startCurrent() } else showTitle("No channel ${n ?: ""} in this list", 2500)
    }

    private fun play(list: List<Item>, index: Int, chain: Boolean = false) {
        releasePreview(); closePip(); ui.removeCallbacks(previewRun); ui.removeCallbacks(nextRun)
        chainNext = chain
        zapList = list; zapIndex = index
        val root = FrameLayout(this).apply { setBackgroundColor(Color.BLACK) }
        val pv = (android.view.LayoutInflater.from(this).inflate(R.layout.player_view, null) as PlayerView).apply { useController = list[index].kind != "live"; controllerAutoShow = false; keepScreenOn = true; setShowBuffering(PlayerView.SHOW_BUFFERING_NEVER); setShutterBackgroundColor(Color.TRANSPARENT) }
        root.addView(pv, FrameLayout.LayoutParams(-1, -1))
        titleView = TextView(this).apply { textSize = 24f; setTextColor(CREAM); setBackgroundColor(Color.argb(190, 0, 0, 0)); setPadding(dp(24), dp(14), dp(24), dp(14)); visibility = View.GONE }
        root.addView(titleView, FrameLayout.LayoutParams(-2, -2, Gravity.TOP or Gravity.START))
        nextBtn = TextView(this).apply {
            textSize = 20f; setTextColor(Color.BLACK); typeface = fMedium(); background = rbg(GOLD, Color.TRANSPARENT, 12, 0); setPadding(dp(26), dp(14), dp(26), dp(14)); visibility = View.GONE
            isFocusable = false; setOnClickListener { goNextEpisode() }
        }
        root.addView(nextBtn, FrameLayout.LayoutParams(-2, -2, Gravity.BOTTOM or Gravity.END).apply { setMargins(0, 0, dp(48), dp(110)) })
        ui.removeCallbacks(nextBtnTick); ui.postDelayed(nextBtnTick, 1500)
        pv.subtitleView?.visibility = if (prefs.getBoolean("subs", false)) View.VISIBLE else View.GONE
        if (android.os.Build.VERSION.SDK_INT >= 26 && prefs.getInt("hdrmode", 0) != 2) window.setColorMode(android.content.pm.ActivityInfo.COLOR_MODE_HDR)
        playerView = pv; playerRoot = root; setContentView(root); pv.isFocusable = true; pv.requestFocus()
        val p = newPlayer(); player = p; pv.player = p
        // Netflix-style buttons: +/-10 seconds (the stock buttons use 5 / 15 s)
        pv.findViewById<View>(androidx.media3.ui.R.id.exo_rew)?.setOnClickListener { p.seekTo(maxOf(0L, p.currentPosition - 10_000L)) }
        pv.findViewById<View>(androidx.media3.ui.R.id.exo_ffwd)?.setOnClickListener { val d = p.duration; val t = p.currentPosition + 10_000L; p.seekTo(if (d > 0) minOf(t, d) else t) }
        p.addListener(object : Player.Listener {
            override fun onTracksChanged(tracks: androidx.media3.common.Tracks) {
                val hdr = tracks.groups.any { g ->
                    g.type == C.TRACK_TYPE_VIDEO && g.getTrackFormat(0).let { f ->
                        val t = f.colorInfo?.colorTransfer; val c = f.codecs ?: ""
                        f.sampleMimeType == "video/dolby-vision" || t == C.COLOR_TRANSFER_ST2084 || t == C.COLOR_TRANSFER_HLG || c.startsWith("hvc1.2") || c.startsWith("hev1.2")
                    }
                }
                if (hdr && !prefs.getBoolean("notunnel", false)) setTunnel(p, true)
            }
            override fun onPlaybackStateChanged(state: Int) {
                if (state != Player.STATE_ENDED || player !== p) return
                val cur = zapList.getOrNull(zapIndex) ?: return
                if (cur.kind == "live") return
                prefs.edit().remove("pos_" + cur.key).apply()
                if (chainNext && zapIndex + 1 < zapList.size) {
                    showTitle("Next episode in 4 seconds:  " + zapList[zapIndex + 1].name + "      (BACK to stop)", 5000)
                    ui.removeCallbacks(nextRun); ui.postDelayed(nextRun, 4000)
                } else ui.postDelayed({ if (playerRoot != null && player === p) leavePlayer() }, 1500)
            }
            override fun onRenderedFirstFrame() {
                ui.postDelayed({
                    val vf = p.videoFormat; val af = p.audioFormat
                    val cv = p.currentTracks.groups.firstOrNull { it.type == C.TRACK_TYPE_VIDEO }?.getTrackFormat(0)
                    val t = "VIDEO in file: " + (cv?.sampleMimeType ?: "?") + " " + (cv?.codecs ?: "") + "\nVIDEO decoding as: " + (vf?.sampleMimeType ?: "?") + " " + (vf?.codecs ?: "") + " " + (vf?.let { "${it.width}x${it.height}" } ?: "") +
                        " transfer=" + (vf?.colorInfo?.colorTransfer ?: -1) + (if (vf?.sampleMimeType == "video/dolby-vision") "  = DOLBY VISION" else "") +
                        "  tunnelled=" + (selectors[p]?.parameters?.tunnelingEnabled ?: false) + "\nDECODER: " + vdec + "\nSCREEN reports: " + hdrTypes() + "   mode: " + modeInfo() + "\nAUDIO: " + (af?.sampleMimeType ?: "?") + " " + (af?.codecs ?: "") + " " + (af?.channelCount ?: 0) + "ch" + (if (af?.codecs?.contains("joc") == true || af?.sampleMimeType == "audio/eac3-joc") "  = DOLBY ATMOS" else "")
                    lastDiag = t
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

    private val warmed = HashMap<String, Long>()
    /** Contacts the next and previous channel in the background (DNS, TLS, provider redirect) so switching to them has less to do. It does not decode video in advance. */
    private fun prewarm(items: List<Item>) {
        val now = System.currentTimeMillis()
        val urls = items.map { it.url }.filter { it.startsWith("http") && now - (warmed[it] ?: 0L) > 120_000L }
        if (urls.isEmpty()) return
        if (warmed.size > 300) warmed.clear(); urls.forEach { warmed[it] = now }
        Thread {
            for (u in urls) try {
                val c = java.net.URL(u).openConnection() as java.net.HttpURLConnection
                c.connectTimeout = 4000; c.readTimeout = 4000; c.setRequestProperty("Range", "bytes=0-2047"); c.setRequestProperty("User-Agent", Http.UA)
                c.inputStream.use { it.read(ByteArray(2048)) }; c.disconnect()
            } catch (e: Exception) { }
        }.start()
    }

    private fun startCurrent() {
        savePosition()
        val old = playing
        val it = zapList[zapIndex]; playing = it; attempt = 0
        if (it.kind == "live") { if (old != null && old.kind == "live" && old.key != it.key) prevLiveKey = old.key; prefs.edit().putString("lastLive", it.key).apply() }
        addRecent(it)
        val start = if (it.kind != "live") savedPos(it) else 0L
        player?.let { loadInto(it, zapList[zapIndex], 0, if (start > 10_000) start else 0L) }
        if (it.kind == "live") {
            prewarm(listOf(zapList[(zapIndex + 1) % zapList.size], zapList[(zapIndex - 1 + zapList.size) % zapList.size]))
            showTitle("${zapIndex + 1}  ${it.name}      (0-9 channel number  ·  ◀ last channel  ·  ▶ audio / subtitles)")
            epgFor(it) { l -> val n = nowOf(l); if (n != null && playing?.key == it.key) showTitle("${zapIndex + 1}  ${it.name}\n${n.title}   ${hm(n.start)} – ${hm(n.end)}") }
        }
    }

    private fun savePosition() {
        val p = player ?: return; val it = playing ?: return
        if (it.kind == "live") return
        val pos = p.currentPosition; val dur = p.duration
        val e = prefs.edit()
        if (dur > 0) e.putLong("dur_" + it.key, dur)
        if (dur > 0 && pos > dur * 0.95) e.remove("pos_" + it.key) else if (pos > 10_000) e.putLong("pos_" + it.key, pos)
        e.apply()
    }

    private fun showTitle(t: String, ms: Long = 4000) { titleView?.text = t; titleView?.visibility = View.VISIBLE; ui.removeCallbacks(hideTitle); ui.postDelayed(hideTitle, ms) }
    private val hideTitle = Runnable { titleView?.visibility = View.GONE }

    private fun zap(delta: Int) { if (zapList.size < 2) return; zapIndex = (zapIndex + delta + zapList.size) % zapList.size; lastLiveKey = zapList[zapIndex].key; startCurrent() }

    // ---------------------------------------------------------------- small corner screen (keeps playing while you browse)
    private var pip: ExoPlayer? = null
    private var pipBox: FrameLayout? = null
    private var pipItem: Item? = null
    private var pipSound = false

    private fun startPip(it: Item) {
        closePip()
        val p = newPlayer(false); pip = p; pipItem = it
        selectors[p]?.let { sel -> sel.parameters = sel.buildUponParameters().setMaxVideoSize(1280, 720).build() }
        p.volume = if (pipSound) 1f else 0f
        val box = FrameLayout(this).apply { setBackgroundColor(Color.BLACK); elevation = dp(10).toFloat(); isFocusable = false
            foreground = GradientDrawable().apply { setColor(Color.TRANSPARENT); setStroke(dp(2), ROSE) } }
        val pv = PlayerView(this).apply { useController = false; setShowBuffering(PlayerView.SHOW_BUFFERING_NEVER); setShutterBackgroundColor(Color.BLACK); isFocusable = false; this.player = p }
        box.addView(pv, FrameLayout.LayoutParams(-1, -1))
        box.addView(TextView(this).apply { text = it.name; textSize = 12f; setTextColor(CREAM); setBackgroundColor(Color.argb(170, 0, 0, 0)); setPadding(dp(8), dp(3), dp(8), dp(3)); maxLines = 1 },
            FrameLayout.LayoutParams(-2, -2, Gravity.BOTTOM or Gravity.START))
        (window.decorView as ViewGroup).addView(box, FrameLayout.LayoutParams(dp(300), dp(169), Gravity.BOTTOM or Gravity.END).apply { setMargins(0, 0, dp(24), dp(24)) })
        pipBox = box
        var att = 0
        p.addListener(object : Player.Listener {
            override fun onPlayerError(e: PlaybackException) { if (pip === p && att < 3) { att++; ui.postDelayed({ if (pip === p) { loadInto(p, it, att) } }, 1500L * att) } }
        })
        loadInto(p, it, 0)
        Toast.makeText(this, "Corner screen on. Press Play/Pause for its options.", Toast.LENGTH_LONG).show()
    }

    /** Android's own picture-in-picture: a floating window that can stay on top of other apps (if the TV supports it). */
    private fun enterPip(): Boolean {
        if (android.os.Build.VERSION.SDK_INT < 26 || playerRoot == null || !packageManager.hasSystemFeature(android.content.pm.PackageManager.FEATURE_PICTURE_IN_PICTURE)) return false
        return try { enterPictureInPictureMode(android.app.PictureInPictureParams.Builder().setAspectRatio(android.util.Rational(16, 9)).build()) } catch (e: Exception) { false }
    }
    override fun onUserLeaveHint() { super.onUserLeaveHint(); if (playerRoot != null) enterPip() }
    override fun onPictureInPictureModeChanged(isInPictureInPictureMode: Boolean, newConfig: Configuration) {
        super.onPictureInPictureModeChanged(isInPictureInPictureMode, newConfig)
        if (isInPictureInPictureMode) { titleView?.visibility = View.GONE; playerView?.useController = false }
        else playerView?.useController = playing?.kind != "live"
    }

    private fun closePip() {
        pipBox?.let { (it.parent as? ViewGroup)?.removeView(it) }; pipBox = null
        pip?.release(); pip = null; pipItem = null
    }

    private fun pipMenu() {
        val cur = pipItem ?: return
        val opts = arrayOf("Make it full screen", "Sound: " + (if (pipSound) "ON  (press to mute)" else "OFF  (press to turn on)"), "Close the corner screen")
        android.app.AlertDialog.Builder(this).setTitle(cur.name).setItems(opts) { _, i ->
            when (i) {
                0 -> { closePip(); play(listOf(cur), 0) }
                1 -> { pipSound = !pipSound; pip?.volume = if (pipSound) 1f else 0f }
                else -> closePip()
            }
        }.show()
    }

    private fun leavePlayer() {
        ui.removeCallbacks(nextRun); ui.removeCallbacks(nextBtnTick); nextBtn = null; ui.removeCallbacks(numRun); numBuf = ""
        savePosition(); ui.removeCallbacks(hideTitle); player?.release(); player = null; playerRoot = null; titleView = null; playerView = null; playing = null
        if (android.os.Build.VERSION.SDK_INT >= 26) window.setColorMode(android.content.pm.ActivityInfo.COLOR_MODE_DEFAULT)
        request4k(false)
        shell?.let { setContentView(it) }; refreshPage()
    }

    /** Moving between tiles: a soft click, and holding a direction jumps several tiles per repeat so long rows scroll quickly. */
    @Volatile var holdUntil = 0L
    fun tick() { if (playerRoot == null && !prefs.getBoolean("noclick", false)) Click.tick() }
    private var lastHold = 0L
    private fun fastScroll(e: KeyEvent): Boolean {
        val dir = when (e.keyCode) { KeyEvent.KEYCODE_DPAD_RIGHT -> View.FOCUS_RIGHT; KeyEvent.KEYCODE_DPAD_LEFT -> View.FOCUS_LEFT; else -> return false }
        if (e.repeatCount < 3) return false
        holdUntil = System.currentTimeMillis() + 250
        val start = currentFocus ?: return false
        if (start.parent !is RecyclerView) return false
        var v: View = start
        repeat(2) { val n = v.focusSearch(dir) ?: return@repeat; if (n.parent === start.parent) v = n }
        if (v !== start) { v.requestFocus(); return true }
        return false
    }

    override fun dispatchKeyEvent(e: KeyEvent): Boolean {
        if (saver != null) { stopSaver(); bumpIdle(); return true }
        bumpIdle()
        if (playerRoot == null && e.action == KeyEvent.ACTION_DOWN && e.repeatCount > 0) { if (fastScroll(e)) return true }
        if (playerRoot != null && e.action == KeyEvent.ACTION_DOWN && zapList.getOrNull(zapIndex)?.kind != "live") {
            val hidden = playerView?.isControllerFullyVisible == false
            if (nextBtn?.visibility == View.VISIBLE && hasNextEp() && (e.keyCode == KeyEvent.KEYCODE_DPAD_UP || e.keyCode == KeyEvent.KEYCODE_MEDIA_NEXT || e.keyCode == KeyEvent.KEYCODE_CHANNEL_UP)) { goNextEpisode(); return true }
            if (hasNextEp() && (e.keyCode == KeyEvent.KEYCODE_MEDIA_NEXT || e.keyCode == KeyEvent.KEYCODE_CHANNEL_UP)) { goNextEpisode(); return true }
            if (e.keyCode == KeyEvent.KEYCODE_MENU || e.keyCode == KeyEvent.KEYCODE_INFO || (e.keyCode == KeyEvent.KEYCODE_DPAD_RIGHT && hidden)) { audioDialog(); return true }
        }
        return super.dispatchKeyEvent(e)
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent): Boolean {
        if (pip != null && playerRoot == null && keyCode == KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE) { pipMenu(); return true }
        if (playerRoot != null && zapList.getOrNull(zapIndex)?.kind == "live") {
            when (keyCode) {
                KeyEvent.KEYCODE_CHANNEL_UP, KeyEvent.KEYCODE_DPAD_UP -> { zap(1); return true }
                KeyEvent.KEYCODE_CHANNEL_DOWN, KeyEvent.KEYCODE_DPAD_DOWN -> { zap(-1); return true }
                KeyEvent.KEYCODE_DPAD_CENTER, KeyEvent.KEYCODE_ENTER -> { startCurrent(); return true }
                KeyEvent.KEYCODE_DPAD_RIGHT, KeyEvent.KEYCODE_MENU -> { audioDialog(); return true }
                KeyEvent.KEYCODE_DPAD_LEFT, KeyEvent.KEYCODE_LAST_CHANNEL -> {
                    val i = zapList.indexOfFirst { x -> x.key == prevLiveKey }
                    if (i >= 0) { zapIndex = i; lastLiveKey = zapList[i].key; startCurrent() } else showTitle("No previous channel yet", 2000)
                    return true
                }
                in KeyEvent.KEYCODE_0..KeyEvent.KEYCODE_9 -> {
                    if (numBuf.length < 4) numBuf += (keyCode - KeyEvent.KEYCODE_0)
                    showTitle("Channel  $numBuf", 2500)
                    ui.removeCallbacks(numRun); ui.postDelayed(numRun, 1800)
                    return true
                }
            }
        }
        if (playerRoot != null && keyCode == KeyEvent.KEYCODE_MENU) { audioDialog(); return true }
        if (playerRoot != null && keyCode != KeyEvent.KEYCODE_BACK && playerView?.dispatchKeyEvent(event) == true) return true
        return super.onKeyDown(keyCode, event)
    }

    override fun onResume() { super.onResume(); bumpIdle(); if (shell != null) { ui.removeCallbacks(chromeTick); ui.post(chromeTick) } }
    override fun onStop() { super.onStop(); ui.removeCallbacks(chromeTick); stopSaver(); ui.removeCallbacks(saverStart); savePosition(); player?.pause(); releasePreview(); closePip() }
    override fun onDestroy() { super.onDestroy(); player?.release(); preview?.release() }
}
