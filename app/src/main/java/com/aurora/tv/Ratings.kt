package com.aurora.tv

import android.content.SharedPreferences
import org.json.JSONObject
import java.net.URLEncoder

/** IMDb and Rotten Tomatoes scores from OMDb (free key from omdbapi.com), cached on the TV. */
object Ratings {
    private val YEAR = Regex("\\((\\d{4})\\)")
    private val BRACKETS = Regex("[\\[\\(][^\\]\\)]*[\\]\\)]")

    /** Provider titles look like "4K-A+ - Tenzing (2026)" or "FR - Les Portes du temps (2007)". */
    fun cleanTitle(raw: String): String {
        var n = raw
        val i = n.indexOf(" - ")
        if (i in 1..14 && n.substring(0, i).none { it.isLowerCase() }) n = n.substring(i + 3)
        n = n.replace(BRACKETS, " ")
        return n.replace(Regex("\\s+"), " ").trim()
    }
    fun yearOf(raw: String): String = YEAR.find(raw)?.groupValues?.get(1) ?: ""

    private fun norm(t: String) = t.lowercase().filter { it.isLetterOrDigit() }
    private fun matches(a: String, b: String): Boolean { val x = norm(a); val y = norm(b); return x.isNotEmpty() && y.isNotEmpty() && (x == y || x.contains(y) || y.contains(x)) }

    /** Blocking. Returns e.g. "IMDb 7.8   ·   RT 91%" or null when nothing was found. */
    fun lookup(prefs: SharedPreferences, key: String, rawName: String, yearHint: String, kind: String): String? {
        val title = cleanTitle(rawName); if (title.length < 2) return null
        val year = yearOf(rawName).ifBlank { yearHint.take(4) }
        val ck = "rt2_${kind}_${title.lowercase()}_$year"
        prefs.getString(ck, null)?.let { return it.ifBlank { null } }
        return try {
            val type = if (kind == "series") "series" else "movie"
            val url = "https://www.omdbapi.com/?apikey=${URLEncoder.encode(key, "UTF-8")}&t=${URLEncoder.encode(title, "UTF-8")}&type=$type" + (if (year.isNotBlank() && kind != "series") "&y=$year" else "")
            val o = JSONObject(Http.get(url))
            if (o.optString("Response") != "True") { prefs.edit().putString(ck, "").apply(); return null }
            if (!matches(title, o.optString("Title"))) { prefs.edit().putString(ck, "").apply(); return null }
            val oy = o.optString("Year").take(4).toIntOrNull(); val hy = year.toIntOrNull()
            if (kind != "series" && oy != null && hy != null && Math.abs(oy - hy) > 1) { prefs.edit().putString(ck, "").apply(); return null }
            val parts = ArrayList<String>()
            val imdb = o.optString("imdbRating"); if (imdb.isNotBlank() && imdb != "N/A") parts += "IMDb $imdb"
            val arr = o.optJSONArray("Ratings")
            if (arr != null) for (i in 0 until arr.length()) { val r = arr.getJSONObject(i); if (r.optString("Source").contains("Rotten")) parts += "RT ${r.optString("Value")}" }
            val text = parts.joinToString("   ·   ")
            prefs.edit().putString(ck, text).apply()
            text.ifBlank { null }
        } catch (e: Throwable) { null }
    }
}
