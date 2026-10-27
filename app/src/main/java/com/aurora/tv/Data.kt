package com.aurora.tv

import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** kind: live | movie | series | episode */
data class Item(val name: String, val url: String, val group: String, val kind: String, val id: String = "", val logo: String = "") {
    val key: String get() = "$kind|${if (id.isNotEmpty()) id else url}"
    fun toJson(): JSONObject = JSONObject().put("n", name).put("u", url).put("g", group).put("k", kind).put("i", id).put("l", logo)
    companion object {
        fun fromJson(o: JSONObject) = Item(o.optString("n"), o.optString("u"), o.optString("g"), o.optString("k"), o.optString("i"), o.optString("l"))
    }
}

data class Prog(val title: String, val desc: String, val start: Long, val end: Long)
data class Info(val plot: String = "", val cast: String = "", val genre: String = "", val year: String = "", val rating: String = "", val backdrop: String = "", val poster: String = "", val trailer: String = "")
data class SeriesData(val info: Info, val seasons: Map<String, List<Item>>)

object Http {
    const val UA = "VLC/3.0.20 LibVLC/3.0.20"

    /** Opens a URL and follows redirects by hand (HttpURLConnection will not follow http -> https). */
    fun open(url0: String): HttpURLConnection {
        var url = url0
        for (i in 0 until 6) {
            val c = URL(url).openConnection() as HttpURLConnection
            c.connectTimeout = 15000; c.readTimeout = 60000; c.instanceFollowRedirects = false
            c.setRequestProperty("User-Agent", UA)
            val code = c.responseCode
            if (code in 301..308 && code != 304) {
                val loc = c.getHeaderField("Location"); c.disconnect()
                if (loc == null) throw RuntimeException("Redirect without a target")
                url = URL(URL(url), loc).toString(); continue
            }
            if (code !in 200..299) { c.disconnect(); throw RuntimeException("Server answered HTTP $code") }
            return c
        }
        throw RuntimeException("Too many redirects")
    }

    fun get(url: String): String {
        val c = open(url)
        try { return c.inputStream.bufferedReader().use { it.readText() } } finally { c.disconnect() }
    }

    fun bytes(url: String, max: Int = 4_000_000): ByteArray {
        val c = open(url)
        try {
            val out = java.io.ByteArrayOutputStream(); val buf = ByteArray(8192)
            c.inputStream.use { ins -> while (true) { val n = ins.read(buf); if (n < 0) break; out.write(buf, 0, n); if (out.size() > max) break } }
            return out.toByteArray()
        } finally { c.disconnect() }
    }
}

private val PREFIX = Regex("^(\\[[^\\]]{1,5}\\]|[A-Za-z]{2,4}\\s?\\|)")
/** Language-style prefix of a category, e.g. "FR|" or "[AR]". Empty when there is none. */
fun groupPrefix(g: String): String = PREFIX.find(g.trim())?.value?.replace(" ", "") ?: ""

object M3u {
    fun parse(text: String): List<Item> {
        val out = ArrayList<Item>()
        var name = ""; var group = "Other"; var logo = ""
        val attr = Regex("([A-Za-z0-9_-]+)=\"([^\"]*)\"")
        for (raw in text.lineSequence()) {
            val line = raw.trim()
            if (line.startsWith("#EXTINF")) {
                val attrs = attr.findAll(line).associate { it.groupValues[1].lowercase() to it.groupValues[2] }
                group = attrs["group-title"]?.ifBlank { null } ?: "Other"; logo = attrs["tvg-logo"] ?: ""
                name = line.substringAfterLast(",", "").trim().ifBlank { attrs["tvg-name"] ?: "Channel" }
            } else if (line.isNotEmpty() && !line.startsWith("#")) {
                val low = line.lowercase()
                val kind = if (low.contains("/movie/")) "movie" else if (low.contains("/series/")) "episode" else "live"
                out.add(Item(name.ifBlank { line }, line, group, kind, "", logo)); name = ""; group = "Other"; logo = ""
            }
        }
        return out
    }
}

class Xtream(base: String, private val user: String, private val pass: String) {
    private val base = base.trim().trimEnd('/').let { if (it.startsWith("http")) it else "http://$it" }
    private fun api(action: String, extra: String = ""): String =
        "$base/player_api.php?username=$user&password=$pass&action=$action$extra"

    private fun arr(action: String, extra: String = ""): JSONArray {
        val t = Http.get(api(action, extra)).trim()
        return if (t.startsWith("[")) JSONArray(t) else JSONArray()
    }

    fun login(): String {
        val o = JSONObject(Http.get("$base/player_api.php?username=$user&password=$pass"))
        val ui = o.optJSONObject("user_info") ?: throw RuntimeException("Wrong server address or login")
        if (ui.optInt("auth", 0) != 1) throw RuntimeException("Login refused (check username/password)")
        return ui.optString("status", "Active")
    }

    private fun cats(action: String): Map<String, String> {
        val m = HashMap<String, String>(); val a = arr(action)
        for (i in 0 until a.length()) { val o = a.getJSONObject(i); m[o.optString("category_id")] = o.optString("category_name") }
        return m
    }

    /** Streams a big JSON array (30k+ items) object by object so the whole list is never held as one string. */
    private fun streamArray(action: String, extra: String, keys: Set<String>, each: (Map<String, String>) -> Unit) {
        val c = Http.open(api(action, extra))
        try {
            android.util.JsonReader(c.inputStream.bufferedReader()).use { r ->
                if (r.peek() != android.util.JsonToken.BEGIN_ARRAY) return
                r.beginArray()
                while (r.hasNext()) {
                    if (r.peek() != android.util.JsonToken.BEGIN_OBJECT) { r.skipValue(); continue }
                    val m = HashMap<String, String>(8); r.beginObject()
                    while (r.hasNext()) {
                        val n = r.nextName()
                        if (n in keys) {
                            when (r.peek()) {
                                android.util.JsonToken.STRING, android.util.JsonToken.NUMBER -> m[n] = r.nextString()
                                android.util.JsonToken.BOOLEAN -> m[n] = r.nextBoolean().toString()
                                android.util.JsonToken.NULL -> r.nextNull()
                                else -> r.skipValue()
                            }
                        } else r.skipValue()
                    }
                    r.endObject(); each(m)
                }
                r.endArray()
            }
        } finally { c.disconnect() }
    }

    fun live(): List<Item> {
        val c = cats("get_live_categories"); val out = ArrayList<Item>()
        streamArray("get_live_streams", "", setOf("name", "stream_id", "category_id", "stream_icon")) { m ->
            val id = m["stream_id"] ?: ""
            out.add(Item(m["name"] ?: "", "$base/live/$user/$pass/$id.ts", c[m["category_id"] ?: ""] ?: "Other", "live", id, m["stream_icon"] ?: ""))
        }
        return out
    }

    fun movies(): List<Item> {
        val c = cats("get_vod_categories"); val out = ArrayList<Item>()
        streamArray("get_vod_streams", "", setOf("name", "stream_id", "category_id", "stream_icon", "container_extension")) { m ->
            val id = m["stream_id"] ?: ""; val ext = (m["container_extension"] ?: "mp4").ifBlank { "mp4" }
            out.add(Item(m["name"] ?: "", "$base/movie/$user/$pass/$id.$ext", c[m["category_id"] ?: ""] ?: "Other", "movie", id, m["stream_icon"] ?: ""))
        }
        return out
    }

    fun series(): List<Item> {
        val c = cats("get_series_categories"); val out = ArrayList<Item>()
        streamArray("get_series", "", setOf("name", "series_id", "category_id", "cover")) { m ->
            out.add(Item(m["name"] ?: "", "", c[m["category_id"] ?: ""] ?: "Other", "series", m["series_id"] ?: "", m["cover"] ?: ""))
        }
        return out
    }

    private fun b64(s: String): String = try { String(android.util.Base64.decode(s, android.util.Base64.DEFAULT), Charsets.UTF_8) } catch (e: Exception) { s }

    fun shortEpg(streamId: String): List<Prog> {
        val o = JSONObject(Http.get(api("get_short_epg", "&stream_id=$streamId&limit=6")))
        val a = o.optJSONArray("epg_listings") ?: return emptyList(); val out = ArrayList<Prog>()
        for (i in 0 until a.length()) {
            val e = a.getJSONObject(i)
            out.add(Prog(b64(e.optString("title")), b64(e.optString("description")), e.optString("start_timestamp").toLongOrNull() ?: 0L, e.optString("stop_timestamp").toLongOrNull() ?: 0L))
        }
        return out
    }

    private fun infoOf(i: JSONObject?): Info {
        if (i == null) return Info()
        val raw = i.opt("backdrop_path")
        val back = when (raw) { is JSONArray -> if (raw.length() > 0) raw.optString(0) else ""; is String -> raw; else -> "" }
        val date = i.optString("releasedate").ifBlank { i.optString("releaseDate") }.ifBlank { i.optString("release_date") }
        val rating = i.optString("rating").ifBlank { i.optString("rating_5based") }
        return Info(i.optString("plot").ifBlank { i.optString("description") }, i.optString("cast").ifBlank { i.optString("actors") },
            i.optString("genre"), date.take(4), rating, back, i.optString("movie_image").ifBlank { i.optString("cover") }, i.optString("youtube_trailer").ifBlank { i.optString("trailer") })
    }

    fun vodInfo(id: String): Info = infoOf(JSONObject(Http.get(api("get_vod_info", "&vod_id=$id"))).optJSONObject("info"))

    /** season label -> episodes, plus the series info block */
    fun seriesData(seriesId: String): SeriesData {
        val o = JSONObject(Http.get(api("get_series_info", "&series_id=$seriesId")))
        return SeriesData(infoOf(o.optJSONObject("info")), parseEpisodes(o))
    }

    private fun parseEpisodes(o: JSONObject): Map<String, List<Item>> {
        val eps = o.optJSONObject("episodes") ?: return emptyMap()
        val out = LinkedHashMap<String, List<Item>>()
        val keys = eps.keys().asSequence().toList().sortedBy { it.toIntOrNull() ?: 0 }
        for (k in keys) {
            val a = eps.optJSONArray(k) ?: continue; val list = ArrayList<Item>()
            for (i in 0 until a.length()) {
                val e = a.getJSONObject(i); val id = e.optString("id"); val ext = e.optString("container_extension", "mp4").ifBlank { "mp4" }
                val title = e.optString("title").ifBlank { "Episode ${e.optString("episode_num")}" }
                list.add(Item("E${e.optString("episode_num")}  $title", "$base/series/$user/$pass/$id.$ext", "Season $k", "episode", id, e.optJSONObject("info")?.optString("movie_image") ?: ""))
            }
            out["Season $k"] = list
        }
        return out
    }
}
