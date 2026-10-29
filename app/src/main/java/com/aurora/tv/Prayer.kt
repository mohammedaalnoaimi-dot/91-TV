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

    class Day(val key: String, val times: Map<String, String>, val hijri: String, val hijriMonth: Int = 0)

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
        Day(key, m, o.optString("h", ""), o.optInt("hm", 0))
    } catch (e: Exception) { null }

    private fun load(prefs: SharedPreferences, method: Int, key: String): Day? {
        val ck = "pt2_${method}_$key"
        prefs.getString(ck, null)?.let { parse(it, key)?.let { d -> return d } }
        return try {
            val resp = JSONObject(Http.get("https://api.aladhan.com/v1/timingsByCity/$key?city=Manama&country=Bahrain&method=$method"))
            val data = resp.getJSONObject("data"); val tm = data.getJSONObject("timings")
            val t = JSONObject(); for (n in ORDER) t.put(n, tm.getString(n).trim().take(5))
            val h = data.optJSONObject("date")?.optJSONObject("hijri")
            val hs = if (h != null) "${h.optString("day").trimStart('0')} ${h.optJSONObject("month")?.optString("en") ?: ""} ${h.optString("year")} AH" else ""
            val raw = JSONObject().put("t", t).put("h", hs).put("hm", h?.optJSONObject("month")?.optInt("number") ?: 0).toString()
            prefs.edit().putString(ck, raw).apply()
            parse(raw, key)
        } catch (e: Throwable) { null }
    }

    private fun prune(prefs: SharedPreferences, keep: Set<String>) {
        val e = prefs.edit(); var any = false
        for (k in prefs.all.keys) if ((k.startsWith("pt_") || k.startsWith("pt2_")) && keep.none { k.endsWith(it) }) { e.remove(k); any = true }
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
    fun page(a: Activity, prefs: SharedPreferences, again: () -> Unit, openMonth: () -> Unit = {}): View {
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
        val ramadan = day.hijriMonth == 9
        val rLabel = a.mkText("", 15f, GOLD, true).apply { letterSpacing = 0.22f; setPadding(0, a.dp(22), 0, 0) }
        val rCount = a.mkText("", 34f, CREAM).apply { letterSpacing = 0.05f }
        val rSub = a.mkItalic("", 17f, SOFT)
        if (ramadan) { left.addView(a.mkText("RAMADAN MUBARAK", 13f, RED, true).apply { letterSpacing = 0.3f; setPadding(0, a.dp(24), 0, 0) }); left.addView(rLabel); left.addView(rCount); left.addView(rSub) }
        left.addView(a.mkButton("Monthly timetable", false) { openMonth() }, LinearLayout.LayoutParams(-2, -2).apply { topMargin = a.dp(24) })
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
                if (ramadan) {
                    val t0 = today; val t1 = tomorrow
                    if (t0 != null) {
                        val fajr = millis(t0, "Fajr"); val mag = millis(t0, "Maghrib")
                        if (now < fajr) { rLabel.text = "SUHOOR ENDS (FAJR)"; rCount.text = "in " + hms(fajr - now); rSub.text = "at ${clock(fajr)}" }
                        else if (now < mag) { rLabel.text = "IFTAR (MAGHRIB)"; rCount.text = "in " + hms(mag - now); rSub.text = "at ${clock(mag)}  ·  fast ends then" }
                        else if (t1 != null) { val f2 = millis(t1, "Fajr"); rLabel.text = "SUHOOR ENDS (FAJR) TOMORROW"; rCount.text = "in " + hms(f2 - now); rSub.text = "at ${clock(f2)}" }
                    }
                }
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

    // ---------------- monthly timetable ----------------
    /** One row per day: date, hijri day, six times. Cached per month so it works offline after the first visit. */
    private fun loadMonth(prefs: SharedPreferences, method: Int, year: Int, month: Int): List<List<String>>? {
        val ck = "ptm_${method}_${year}_$month"
        fun parseRows(raw: String): List<List<String>> { val a = org.json.JSONArray(raw); return (0 until a.length()).map { i -> val r = a.getJSONArray(i); (0 until r.length()).map { r.getString(it) } } }
        prefs.getString(ck, null)?.let { try { return parseRows(it) } catch (e: Exception) { } }
        return try {
            val resp = JSONObject(Http.get("https://api.aladhan.com/v1/calendarByCity/$year/$month?city=Manama&country=Bahrain&method=$method"))
            val arr = resp.getJSONArray("data"); val out = org.json.JSONArray()
            for (i in 0 until arr.length()) {
                val d = arr.getJSONObject(i); val tm = d.getJSONObject("timings"); val row = org.json.JSONArray()
                row.put(d.getJSONObject("date").getJSONObject("gregorian").getString("date"))
                row.put(d.getJSONObject("date").getJSONObject("hijri").optString("day").trimStart('0'))
                row.put(d.getJSONObject("date").getJSONObject("hijri").getJSONObject("month").optInt("number").toString())
                for (n in ORDER) row.put(tm.getString(n).trim().take(5))
                out.put(row)
            }
            prefs.edit().putString(ck, out.toString()).apply(); parseRows(out.toString())
        } catch (e: Throwable) { null }
    }

    fun monthPage(a: Activity, prefs: SharedPreferences): View {
        val root = FrameLayout(a).apply { setBackgroundColor(BG) }
        val cal = java.util.Calendar.getInstance(TZ); val y = cal.get(java.util.Calendar.YEAR); val m = cal.get(java.util.Calendar.MONTH) + 1
        val col = LinearLayout(a).apply { orientation = LinearLayout.VERTICAL; setPadding(a.dp(56), a.dp(26), a.dp(56), a.dp(10)) }
        col.addView(a.eyebrow("MONTHLY TIMETABLE · MANAMA"))
        col.addView(a.mkText(SimpleDateFormat("MMMM yyyy", Locale.US).apply { timeZone = TZ }.format(java.util.Date()), 30f, CREAM, true).apply { letterSpacing = 0.06f; setPadding(0, a.dp(4), 0, a.dp(10)) })
        val body = LinearLayout(a).apply { orientation = LinearLayout.VERTICAL }
        val scroll = android.widget.ScrollView(a).apply { addView(body); isFocusable = false }
        col.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f)); root.addView(col, FrameLayout.LayoutParams(-1, -1))
        body.addView(a.mkText("Loading…", 18f, SOFT))
        val method = prefs.getInt("ptMethod", 8)
        Thread {
            val rows = loadMonth(prefs, method, y, m)
            a.runOnUiThread {
                body.removeAllViews()
                if (rows == null) { body.addView(a.mkText("Could not load the timetable (needs the internet the first time).", 18f, SOFT)); return@runOnUiThread }
                fun line(cells: List<String>, head: Boolean, today: Boolean, ram: Boolean): View {
                    val r = LinearLayout(a).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; setPadding(a.dp(14), a.dp(7), a.dp(14), a.dp(7)); isFocusable = !head
                        background = if (today) a.rbg(Color.parseColor("#33C9475C"), Color.parseColor("#C9475C"), 2, 1) else if (head) null else a.rbg(Color.parseColor("#0FFFFFFF"), Color.TRANSPARENT, 2, 1)
                        setOnFocusChangeListener { v, f -> if (!head && !today) v.background = a.rbg(if (f) Color.parseColor("#26C9475C") else Color.parseColor("#0FFFFFFF"), if (f) RED else Color.TRANSPARENT, 2, 1) } }
                    cells.forEachIndexed { i, t ->
                        val w = if (i == 0) 2.2f else if (i == 1) 1.1f else 1f
                        r.addView(a.mkText(t, if (head) 12f else 17f, if (head) GOLD else if (today) CREAM else SOFT, head).apply { if (i > 1) gravity = Gravity.CENTER; if (head) letterSpacing = 0.14f }, LinearLayout.LayoutParams(0, -2, w))
                    }
                    return r
                }
                body.addView(line(listOf("DATE", if (rows.any { it[2] == "9" }) "RAMADAN" else "HIJRI") + ORDER.map { it.uppercase() }, true, false, false))
                val todayKey = key(System.currentTimeMillis()); var focusRow: View? = null
                for (r in rows) {
                    val isToday = r[0] == todayKey; val ram = r[2] == "9"
                    val dateTxt = try { SimpleDateFormat("EEE d MMM", Locale.US).apply { timeZone = TZ }.format(SimpleDateFormat("dd-MM-yyyy", Locale.US).apply { timeZone = TZ }.parse(r[0])!!) } catch (e: Exception) { r[0] }
                    val v = line(listOf(dateTxt, if (ram) "Ramadan ${r[1]}" else r[1]) + r.drop(3), false, isToday, ram)
                    body.addView(v, LinearLayout.LayoutParams(-1, -2).apply { bottomMargin = a.dp(2) }); if (isToday) focusRow = v
                }
                focusRow?.let { f -> f.post { f.requestFocus() } }
            }
        }.start()
        return root
    }
}
