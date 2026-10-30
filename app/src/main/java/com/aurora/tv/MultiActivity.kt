package com.aurora.tv

import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.res.Configuration
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.KeyEvent
import android.view.View
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.datasource.DefaultDataSource
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.exoplayer.DefaultRenderersFactory
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.exoplayer.trackselection.DefaultTrackSelector
import androidx.media3.extractor.DefaultExtractorsFactory
import androidx.media3.extractor.ts.DefaultTsPayloadReaderFactory
import androidx.media3.ui.PlayerView
import org.json.JSONArray
import org.json.JSONObject

/** Multi-view: watch 2 or 4 live channels at once. The highlighted screen has the sound. */
class MultiActivity : Activity() {
    private val ui = Handler(Looper.getMainLooper())
    private lateinit var prefs: android.content.SharedPreferences
    private var n = 2
    private val slots = arrayOfNulls<Item>(4)
    private val panes = ArrayList<Pane>()
    private var all: List<Item> = emptyList()
    private lateinit var root: FrameLayout
    private lateinit var hint: TextView

    override fun attachBaseContext(base: Context) {
        if (base.getSharedPreferences("aurora", Context.MODE_PRIVATE).getBoolean("classic", false)) { super.attachBaseContext(base); return }
        val cfg = Configuration(base.resources.configuration)
        val w = maxOf(base.resources.displayMetrics.widthPixels, base.resources.displayMetrics.heightPixels)
        cfg.densityDpi = (160f * w / 1280f).toInt().coerceIn(120, 640)
        super.attachBaseContext(base.createConfigurationContext(cfg))
    }

    inner class Pane(val index: Int) : FrameLayout(this@MultiActivity) {
        val pv = PlayerView(this@MultiActivity).apply { useController = false; setShowBuffering(PlayerView.SHOW_BUFFERING_NEVER); setShutterBackgroundColor(Color.BLACK); keepScreenOn = true }
        val label = TextView(this@MultiActivity).apply { textSize = 15f; setTextColor(CREAM); setBackgroundColor(Color.argb(170, 0, 0, 0)); setPadding(dp(10), dp(5), dp(10), dp(5)); maxLines = 1 }
        val empty = TextView(this@MultiActivity).apply { text = "Press OK to choose a channel"; textSize = 18f; setTextColor(GRAY); gravity = Gravity.CENTER }
        val sound = TextView(this@MultiActivity).apply { text = "♪"; textSize = 20f; setTextColor(ROSE); setPadding(dp(10), dp(4), dp(10), dp(4)); visibility = View.GONE }
        var player: ExoPlayer? = null
        var attempt = 0

        init {
            isFocusable = true; isFocusableInTouchMode = false; setBackgroundColor(Color.parseColor("#0d0a0b"))
            addView(pv, LayoutParams(-1, -1)); addView(empty, LayoutParams(-1, -1))
            addView(label, LayoutParams(-2, -2, Gravity.BOTTOM or Gravity.START).apply { setMargins(dp(8), 0, 0, dp(8)) })
            addView(sound, LayoutParams(-2, -2, Gravity.TOP or Gravity.END))
            setOnClickListener { pick(index) }
            setOnLongClickListener { pick(index); true }
            onFocusChangeListener = View.OnFocusChangeListener { _, f -> border(f); if (f) setAudio(index) }
            border(false)
        }

        fun border(f: Boolean) {
            foreground = GradientDrawable().apply { setColor(Color.TRANSPARENT); setStroke(dp(if (f) 4 else 1), if (f) ROSE else Color.parseColor("#2a2220")) }
        }

        fun show(it: Item?) {
            releasePlayer(); attempt = 0
            if (it == null) { empty.visibility = View.VISIBLE; label.visibility = View.GONE; return }
            empty.visibility = View.GONE; label.visibility = View.VISIBLE; label.text = it.name
            start(it)
        }

        fun start(it: Item) {
            releasePlayer()
            val p = makePlayer(); player = p; pv.player = p
            val url = urlOf(it, attempt)
            p.setMediaItem(MediaItem.Builder().setUri(url).apply { if (url.contains(".m3u8")) setMimeType(MimeTypes.APPLICATION_M3U8) }.build())
            p.volume = if (hasFocus()) 1f else 0f
            p.addListener(object : Player.Listener {
                override fun onPlayerError(e: PlaybackException) {
                    if (player !== p) return
                    attempt++
                    if (attempt <= 3) ui.postDelayed({ if (player === p) start(it) }, 1500L * attempt)
                    else label.text = it.name + "  ·  not available"
                }
            })
            p.prepare(); p.playWhenReady = true
        }

        fun releasePlayer() { pv.player = null; player?.release(); player = null }
    }

    private fun urlOf(it: Item, att: Int): String {
        val v = when {
            it.url.endsWith(".ts") -> listOf(it.url, it.url.removeSuffix(".ts") + ".m3u8")
            it.url.endsWith(".m3u8") -> listOf(it.url, it.url.removeSuffix(".m3u8") + ".ts")
            else -> listOf(it.url)
        }
        return v[att % v.size]
    }

    private fun makePlayer(): ExoPlayer {
        val http = DefaultHttpDataSource.Factory().setUserAgent(Http.UA).setAllowCrossProtocolRedirects(true).setConnectTimeoutMs(15000).setReadTimeoutMs(20000)
        val ex = DefaultExtractorsFactory().setTsExtractorFlags(DefaultTsPayloadReaderFactory.FLAG_ALLOW_NON_IDR_KEYFRAMES or DefaultTsPayloadReaderFactory.FLAG_DETECT_ACCESS_UNITS)
        val sel = DefaultTrackSelector(this).also { s ->
            s.parameters = s.buildUponParameters().setMaxVideoSize(if (n == 4) 1280 else 1920, if (n == 4) 720 else 1080).setTrackTypeDisabled(C.TRACK_TYPE_TEXT, true).build()
        }
        val p = ExoPlayer.Builder(this, DefaultRenderersFactory(this).setEnableDecoderFallback(true))
            .setMediaSourceFactory(DefaultMediaSourceFactory(DefaultDataSource.Factory(this, http), ex)).setTrackSelector(sel).build()
        p.setAudioAttributes(AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_MOVIE).build(), false)
        return p
    }

    private fun setAudio(focused: Int) {
        for (p in panes) { p.player?.volume = if (p.index == focused) 1f else 0f; p.sound.visibility = if (p.index == focused) View.VISIBLE else View.GONE }
    }

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        prefs = getSharedPreferences("aurora", Context.MODE_PRIVATE)
        n = if (prefs.getInt("multiN", 2) == 4) 4 else 2
        try { val a = JSONArray(prefs.getString("multi", "[]")); for (i in 0 until minOf(4, a.length())) if (!a.isNull(i)) slots[i] = Item.fromJson(a.getJSONObject(i)) } catch (e: Exception) { }
        root = FrameLayout(this).apply { setBackgroundColor(Color.BLACK) }
        hint = TextView(this).apply { text = "OK: choose channel   ·   MENU: 2 / 4 screens   ·   BACK: exit"; textSize = 14f; setTextColor(CREAM); setBackgroundColor(Color.argb(190, 0, 0, 0)); setPadding(dp(16), dp(8), dp(16), dp(8)) }
        setContentView(root)
        Thread { val l = Cache.load(this, "live") ?: emptyList(); val h = prefs.getStringSet("hidden", emptySet()) ?: emptySet()
            all = if (h.isEmpty()) l else { val bad = HashSet<String>(); for (g in l.asSequence().map { it.group }.toSet()) { val pre = groupPrefix(g); if ("live|$g" in h || (pre.isNotEmpty() && "live|prefix:$pre" in h)) bad.add(g) }; l.filter { it.group !in bad } } }.start()
    }

    override fun onStart() { super.onStart(); build() }
    override fun onStop() { super.onStop(); ui.removeCallbacksAndMessages(null); panes.forEach { it.releasePlayer() }; panes.clear(); root.removeAllViews() }

    private fun build(focusIndex: Int = 0) {
        panes.forEach { it.releasePlayer() }; panes.clear(); root.removeAllViews()
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val rows = if (n == 4) 2 else 1; val per = if (n == 4) 2 else 2
        var idx = 0
        for (r in 0 until rows) {
            val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
            for (c in 0 until per) {
                val pane = Pane(idx++); panes.add(pane)
                row.addView(pane, LinearLayout.LayoutParams(0, -1, 1f).apply { setMargins(dp(2), dp(2), dp(2), dp(2)) })
            }
            col.addView(row, LinearLayout.LayoutParams(-1, 0, 1f))
        }
        root.addView(col, FrameLayout.LayoutParams(-1, -1))
        root.addView(hint, FrameLayout.LayoutParams(-2, -2, Gravity.TOP or Gravity.CENTER_HORIZONTAL))
        hint.visibility = View.VISIBLE; ui.postDelayed({ hint.visibility = View.GONE }, 6000)
        panes.forEachIndexed { i, p -> p.show(slots[i]) }
        panes.getOrNull(focusIndex)?.requestFocus()
        setAudio(focusIndex)
    }

    private fun save() {
        val a = JSONArray(); for (i in 0 until 4) a.put(slots[i]?.toJson() ?: JSONObject.NULL)
        prefs.edit().putString("multi", a.toString()).putInt("multiN", n).apply()
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent): Boolean {
        if (keyCode == KeyEvent.KEYCODE_MENU) {
            val f = panes.indexOfFirst { it.hasFocus() }.coerceAtLeast(0)
            n = if (n == 2) 4 else 2; save(); build(minOf(f, n - 1)); return true
        }
        return super.onKeyDown(keyCode, event)
    }

    // ---------------------------------------------------------------- channel picker
    private fun lists(): List<Pair<String, List<Item>>> {
        val out = ArrayList<Pair<String, List<Item>>>()
        val prof = prefs.getString("profile", "mr") ?: "mr"
        fun read(key: String): List<Item> = try { val a = JSONArray(prefs.getString(key, "") ?: ""); (0 until a.length()).map { Item.fromJson(a.getJSONObject(it)) } } catch (e: Exception) { emptyList() }
        val rec = read("recent").filter { it.kind == "live" }; if (rec.isNotEmpty()) out.add("Recently watched" to rec)
        val fav = read("favs_$prof").filter { it.kind == "live" }; if (fav.isNotEmpty()) out.add("★  Favorites" to fav)
        all.groupBy { it.group }.toSortedMap(compareBy { it.lowercase() }).forEach { (g, l) -> out.add(g to l) }
        return out
    }

    private fun choose(index: Int, it: Item?) { slots[index] = it; save(); panes.getOrNull(index)?.show(it); setAudio(panes.indexOfFirst { p -> p.hasFocus() }.coerceAtLeast(0)) }

    private fun pick(index: Int) {
        if (all.isEmpty()) { hint.text = "Channels are still loading - try again in a moment"; hint.visibility = View.VISIBLE; ui.postDelayed({ hint.visibility = View.GONE }, 3000); return }
        val ls = lists()
        val names = ArrayList<String>(); names.add("🔍  Search by name"); if (slots[index] != null) names.add("✕  Clear this screen")
        val offset = names.size; ls.forEach { names.add("${it.first}   (${it.second.size})") }
        AlertDialog.Builder(this).setTitle("Screen ${index + 1}").setItems(names.toTypedArray()) { _, i ->
            when {
                i == 0 -> search(index)
                slots[index] != null && i == 1 -> choose(index, null)
                else -> channelsOf(index, ls[i - offset])
            }
        }.show()
    }

    private fun channelsOf(index: Int, g: Pair<String, List<Item>>) {
        val l = g.second
        AlertDialog.Builder(this).setTitle(g.first).setItems(l.map { it.name }.toTypedArray()) { _, i -> choose(index, l[i]) }.show()
    }

    private fun search(index: Int) {
        val et = EditText(this).apply { hint = "Channel name"; setSingleLine(true); setTextColor(Color.BLACK) }
        AlertDialog.Builder(this).setTitle("Search channels").setView(et).setPositiveButton("Search") { _, _ ->
            val q = et.text.toString().trim().lowercase()
            if (q.length >= 2) { val r = all.filter { it.name.lowercase().contains(q) }.take(300); if (r.isEmpty()) { hint.text = "Nothing found"; hint.visibility = View.VISIBLE; ui.postDelayed({ hint.visibility = View.GONE }, 2500) } else channelsOf(index, "Results" to r) }
        }.setNegativeButton("Cancel", null).show()
    }
}
