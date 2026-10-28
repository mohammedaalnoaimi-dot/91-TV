package com.aurora.tv

import android.app.Activity
import android.content.SharedPreferences
import android.graphics.Color
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.View
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.TimeZone

/** Prayer times for Bahrain (Manama) from the Aladhan API, cached per day on the TV. */
object Prayer {
    val TZ: TimeZone = TimeZone.getTimeZone("Asia/Bahrain")
    val ORDER = listOf("Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha")
    private val AR = mapOf("Fajr" to "الفجر", "Sunrise" to "الشروق", "Dhuhr" to "الظهر", "Asr" to "العصر", "Maghrib" to "المغرب", "Isha" to "العشاء")
    val METHODS = listOf(8 to "Gulf Region", 4 to "Umm Al-Qura (Makkah)", 9 to "Kuwait", 10 to "Qatar", 3 to "Muslim World League")
    val REMIND = listOf(0, 5, 10, 15, 30)

    class Day(val key: String, val times: Map<String, String>, val hijri: String)

    @Volatile var today: Day? = null
    @Volatile var tomorrow: Day? = null
    private var loading = false
    private var lastTry = 0L
    private val main = Handler(Looper.getMainLooper())

    fun arabic(n: String) = AR[n] ?: ""
    fun methodName(prefs: SharedPreferences): String { val m = prefs.getInt("ptMethod", 8); return METHODS.firstOrNull { it.first == m }?.second ?: "Gulf Region" }

    private fun fmt(p: String) = SimpleDateFormat(p, Locale.US).apply { timeZone = TZ }
    fun key(ms: Long): String = fmt("dd-MM-yyyy").format(java.util.Date(ms))
    fun clock(ms: Long): String = fmt("HH:mm").format(java.util.Date(ms))
    fun longDate(ms: Long): String = fmt("EEEE, d MMMM yyyy").format(java.util.Date(ms))
    fun shortDate(ms: Long): String = fmt("EEE d MMM").format(java.util.Date(ms))

    fun millis(d: Day, name: String): Long {
        val t = d.times[name] ?: return 0L
        return try { fmt("dd-MM-yyyy HH:mm").parse(d.key + " " + t)?.time ?: 0L } catch (e: Exception) { 0L }
    }

    private fun parse(raw: String, key: String): Day? = try {
        val o = JSONObject(raw); val t = o.getJSONObject("t"); val m = LinkedHashMap<String, String>()
        for (n in ORDER) m[n] = t.getString(n)
        Day(key, m, o.optString("h", ""))
    } catch (e: Exception) { null }

    private fun load(prefs: SharedPreferences, method: Int, key: String): Day? {
        val ck = "pt_${method}_$key"
        prefs.getString(ck, null)?.let { parse(it, key)?.let { d -> return d } }
        return try {
            val resp = JSONObject(Http.get("https://api.aladhan.com/v1/timingsByCity/$key?city=Manama&country=Bahrain&method=$method"))
            val data = resp.getJSONObject("data"); val tm = data.getJSONObject("timings")
            val t = JSONObject(); for (n in ORDER) t.put(n, tm.getString(n).trim().take(5))
            val h = data.optJSONObject("date")?.optJSONObject("hijri")
            val hs = if (h != null) "${h.optString("day").trimStart('0')} ${h.optJSONObject("month")?.optString("en") ?: ""} ${h.optString("year")} AH" else ""
            val raw = JSONObject().put("t", t).put("h", hs).toString()
            prefs.edit().putString(ck, raw).apply()
            parse(raw, key)
        } catch (e: Throwable) { null }
    }

    private fun prune(prefs: SharedPreferences, keep: Set<String>) {
        val e = prefs.edit(); var any = false
        for (k in prefs.all.keys) if (k.startsWith("pt_") && keep.none { k.endsWith(it) }) { e.remove(k); any = true }
        if (any) e.apply()
    }

    /** Makes sure today's and tomorrow's times are loaded; calls cb on the main thread when something new arrived. */
    fun ensure(prefs: SharedPreferences, cb: () -> Unit) {
        val now = System.currentTimeMillis(); val k0 = key(now); val k1 = key(now + 86_400_000L)
        if (today?.key == k0 && tomorrow?.key == k1) return
        if (loading || now - lastTry < 60_000L) return
        loading = true; lastTry = now
        val method = prefs.getInt("ptMethod", 8)
        Thread {
            try {
                val d0 = load(prefs, method, k0); val d1 = load(prefs, method, k1)
                if (d0 != null) today = d0
                if (d1 != null) tomorrow = d1
                prune(prefs, setOf(k0, k1))
            } finally { loading = false }
            main.post { cb() }
        }.start()
    }

    fun reset() { today = null; tomorrow = null; lastTry = 0L }

    /** The next of Fajr, Dhuhr, Asr, Maghrib, Isha and when it starts. */
    fun next(now: Long): Pair<String, Long>? {
        val t = today ?: return null
        for (n in listOf("Fajr", "Dhuhr", "Asr", "Maghrib", "Isha")) { val m = millis(t, n); if (m > now) return n to m }
        val tm = tomorrow ?: return null
        return "Fajr" to millis(tm, "Fajr")
    }

    fun left(ms: Long): String {
        val s = maxOf(0L, ms / 1000); val h = s / 3600; val m = (s % 3600) / 60
        return if (h > 0) "${h}h ${m}m" else if (m > 0) "${m}m" else "<1m"
    }
    fun hms(ms: Long): String { val s = maxOf(0L, ms / 1000); return String.format(Locale.US, "%02d:%02d:%02d", s / 3600, (s % 3600) / 60, s % 60) }

    // ---------------- the Prayer screen ----------------
    fun page(a: Activity, prefs: SharedPreferences, again: () -> Unit): View {
        val root = FrameLayout(a).apply { setBackgroundColor(BG) }
        root.addView(NightView(a), FrameLayout.LayoutParams(-1, -1))
        ensure(prefs, again)
        val day = today
        if (day == null) {
            root.addView(a.mkText("Loading prayer times for Manama…\n(needs the internet)", 20f, SOFT).apply { gravity = Gravity.CENTER },
                FrameLayout.LayoutParams(-1, -1))
            return root
        }
        val left = LinearLayout(a).apply { orientation = LinearLayout.VERTICAL; setPadding(a.dp(56), a.dp(34), 0, 0) }
        left.addView(a.eyebrow("NEXT PRAYER"))
        val name = a.mkText("", 54f, CREAM, true).apply { letterSpacing = 0.08f; setPadding(0, a.dp(10), 0, 0) }
        val arab = a.mkText("", 34f, GOLD).apply { setPadding(0, 0, 0, a.dp(6)) }
        val count = a.mkText("", 40f, CREAM).apply { letterSpacing = 0.06f }
        val sub = a.mkItalic("", 20f, SOFT).apply { setPadding(0, a.dp(4), 0, a.dp(26)) }
        left.addView(name); left.addView(arab); left.addView(count); left.addView(sub)
        left.addView(a.mkText(longDate(System.currentTimeMillis()), 17f, CREAM))
        if (day.hijri.isNotBlank()) left.addView(a.mkText(day.hijri, 17f, GOLD).apply { setPadding(0, a.dp(2), 0, 0) })
        root.addView(left, FrameLayout.LayoutParams(a.dp(640), -1))

        val panel = LinearLayout(a).apply {
            orientation = LinearLayout.VERTICAL; setPadding(a.dp(26), a.dp(22), a.dp(26), a.dp(18))
            background = a.rbg(Color.parseColor("#B80E080A"), Color.parseColor("#1FEBDDC4"), 3, 1)
        }
        panel.addView(a.mkText("TODAY IN MANAMA", 11f, GOLD, true).apply { letterSpacing = 0.3f; setPadding(0, 0, 0, a.dp(10)) })
        val rows = LinkedHashMap<String, Triple<View, TextView, TextView>>()
        for (n in ORDER) {
            val r = LinearLayout(a).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; setPadding(a.dp(12), a.dp(11), a.dp(12), a.dp(11)) }
            val nm = a.mkText(n.uppercase(), 15f, SOFT, true).apply { letterSpacing = 0.14f }
            val ar = a.mkText(arabic(n), 17f, MUTED).apply { gravity = Gravity.END; setPadding(0, 0, a.dp(18), 0) }
            val tm = a.mkText(day.times[n] ?: "--:--", 22f, SOFT)
            r.addView(nm, LinearLayout.LayoutParams(0, -2, 1f)); r.addView(ar); r.addView(tm)
            panel.addView(r, LinearLayout.LayoutParams(-1, -2).apply { bottomMargin = a.dp(4) })
            rows[n] = Triple(r, nm, tm)
        }
        panel.addView(a.mkItalic("Source: Aladhan · ${methodName(prefs)} method · Manama", 13f, MUTED).apply { setPadding(a.dp(4), a.dp(10), 0, 0) })
        root.addView(panel, FrameLayout.LayoutParams(a.dp(420), -2, Gravity.END or Gravity.CENTER_VERTICAL).apply { rightMargin = a.dp(48) })

        var shownNext = ""
        val tick = object : Runnable {
            override fun run() {
                if (!root.isAttachedToWindow) return
                val now = System.currentTimeMillis(); val nx = next(now)
                if (nx != null) {
                    name.text = nx.first.uppercase(); arab.text = arabic(nx.first)
                    count.text = "in " + hms(nx.second - now)
                    sub.text = "at ${clock(nx.second)}   ·   now ${clock(now)}"
                    if (shownNext != nx.first) {
                        shownNext = nx.first
                        for ((n, v) in rows) {
                            val on = n == nx.first
                            v.first.background = if (on) a.rbg(Color.parseColor("#26C9475C"), Color.parseColor("#C9475C"), 2, 1) else null
                            v.second.setTextColor(if (on) CREAM else SOFT); v.third.setTextColor(if (on) CREAM else SOFT)
                        }
                    }
                } else name.text = "—"
                ensure(prefs, again)
                root.postDelayed(this, 1000)
            }
        }
        root.addOnAttachStateChangeListener(object : View.OnAttachStateChangeListener {
            override fun onViewAttachedToWindow(v: View) { root.removeCallbacks(tick); root.post(tick) }
            override fun onViewDetachedFromWindow(v: View) { root.removeCallbacks(tick) }
        })
        return root
    }
}
