package com.aurora.tv

import android.content.Context
import android.content.SharedPreferences
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * Activation by code, using Lemon Squeezy license keys (no secret is stored in the app).
 *
 * To switch it on: fill STORE_ID, PRODUCT_ID and BUY_URL, set REQUIRED = true, then build.
 * Plans (1 month / 1 year / lifetime) are variants of one product; their length comes from
 * the "license length" you set in Lemon Squeezy, so nothing about plans is hard-coded here.
 */
object Lic {
    const val REQUIRED = true
    const val STORE_ID = 0              // Lemon Squeezy store number (Settings > Stores). 0 = not checked
    const val PRODUCT_ID = 1488147      // "91 TV" (Android TV) product. 0 = not checked
    const val BUY_URL = "ninty0ne.lemonsqueezy.com"   // shown on the activation screen

    private const val DAY = 24L * 3600 * 1000
    private const val RECHECK_MS = 1 * DAY       // online re-check at most once a day
    private const val GRACE_MS = 7 * DAY         // keeps working offline this long after the last good check
    private const val API = "https://api.lemonsqueezy.com/v1/licenses/"
    /** Owner code: only its SHA-256 fingerprint is in the app. Unlocks forever, offline, on any number of devices. */
    private const val OWNER_HASH = "4c0370c68585860d7442a9f93dae1246b941b6965d665b4096a61bcad0dd014d"

    // Overridable for tests.
    internal var required = REQUIRED
    internal var storeId = STORE_ID
    internal var productId = PRODUCT_ID
    internal var clock: () -> Long = { System.currentTimeMillis() }
    internal var transport: (String, List<Pair<String, String>>) -> JSONObject = { p, kv -> post(p, kv) }

    class NoNet : Exception()

    private fun post(path: String, kv: List<Pair<String, String>>): JSONObject {
        try {
            val body = kv.joinToString("&") { URLEncoder.encode(it.first, "UTF-8") + "=" + URLEncoder.encode(it.second, "UTF-8") }
            val c = URL(API + path).openConnection() as HttpURLConnection
            c.requestMethod = "POST"; c.doOutput = true; c.connectTimeout = 10000; c.readTimeout = 15000
            c.setRequestProperty("Accept", "application/json"); c.setRequestProperty("Content-Type", "application/x-www-form-urlencoded")
            c.outputStream.use { it.write(body.toByteArray()) }
            val code = c.responseCode
            val txt = (if (code in 200..299) c.inputStream else c.errorStream)?.bufferedReader()?.use { it.readText() } ?: ""
            c.disconnect()
            return try { JSONObject(txt) } catch (e: Exception) { throw NoNet() }   // not JSON = proxy / captive portal
        } catch (e: java.io.IOException) { throw NoNet() }
    }

    private fun deviceName(ctx: Context): String =
        android.os.Build.MODEL + " " + (android.provider.Settings.Secure.getString(ctx.contentResolver, android.provider.Settings.Secure.ANDROID_ID) ?: "").takeLast(6)

    internal fun isOwner(code: String?): Boolean {
        val c = (code ?: "").trim().uppercase(); if (c.isEmpty()) return false
        val d = java.security.MessageDigest.getInstance("SHA-256").digest(("91tv-owner:" + c).toByteArray())
        return d.joinToString("") { "%02x".format(it) } == OWNER_HASH
    }

    private fun belongs(o: JSONObject): Boolean {
        val m = o.optJSONObject("meta") ?: return false
        return (storeId == 0 || m.optInt("store_id", -1) == storeId) && (productId == 0 || m.optInt("product_id", -1) == productId)
    }

    /** "2027-10-30T18:00:00.000000Z" -> millis, 0 when there is no end date (lifetime). */
    internal fun parseDate(s: String?): Long {
        if (s.isNullOrBlank() || s == "null" || s.length < 19) return 0L
        return try {
            SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") }.parse(s.substring(0, 19))?.time ?: 0L
        } catch (e: Exception) { 0L }
    }

    private fun day(ms: Long) = SimpleDateFormat("d MMM yyyy", Locale.US).format(Date(ms))

    private fun friendly(err: String?): String {
        val e = (err ?: "").lowercase()
        return when {
            "limit" in e -> "This code is already used on the maximum number of devices. Remove it on the other device (Settings > Licence) and try again."
            "not found" in e -> "Code not found. Please check it and try again."
            "expired" in e -> "This code has expired. Please buy a new plan."
            "disabled" in e -> "This code has been cancelled."
            e.isNotBlank() -> err!!
            else -> "Code not accepted"
        }
    }

    private fun save(prefs: SharedPreferences, key: String, inst: String, o: JSONObject) {
        val now = clock()
        prefs.edit().putString("lic_key", key).putString("lic_inst", inst)
            .putLong("lic_ok", now).putLong("lic_exp", parseDate(o.optJSONObject("license_key")?.optString("expires_at")))
            .putString("lic_plan", o.optJSONObject("meta")?.optString("variant_name") ?: "").remove("lic_msg").apply()
    }

    private fun forget(prefs: SharedPreferences, msg: String?) {
        val e = prefs.edit().remove("lic_key").remove("lic_inst").remove("lic_ok").remove("lic_exp").remove("lic_plan")
        if (msg == null) e.remove("lic_msg") else e.putString("lic_msg", msg)
        e.apply()
    }

    /**
     * Blocking. Returns null when activated, otherwise the message to show.
     * Checks the code BEFORE activating, so a wrong or expired code never uses up an activation.
     * Typing the same code again on this TV reuses its activation instead of taking a new one.
     */
    fun activate(ctx: Context, prefs: SharedPreferences, key: String): String? {
        val k = key.trim()
        if (k.length < 8) return "Please type the full code"
        if (isOwner(k)) {
            prefs.edit().putString("lic_key", k.uppercase()).putString("lic_inst", "owner").putLong("lic_ok", clock())
                .putLong("lic_exp", 0L).putString("lic_plan", "Owner").remove("lic_msg").apply()
            return null
        }
        return try {
            val inst = prefs.getString("lic_inst", "") ?: ""
            if (k == prefs.getString("lic_key", "") && inst.isNotBlank()) {
                val v = transport("validate", listOf("license_key" to k, "instance_id" to inst))
                if (v.optBoolean("valid") && belongs(v)) { save(prefs, k, inst, v); return null }
            }
            val v = transport("validate", listOf("license_key" to k))
            val lk = v.optJSONObject("license_key") ?: return friendly(v.optString("error"))
            if (!belongs(v)) return "This code is not for 91 TV"
            val exp = parseDate(lk.optString("expires_at"))
            if (lk.optString("status") == "expired" || (exp > 0 && exp < clock())) return friendly("expired")
            if (lk.optString("status") == "disabled") return friendly("disabled")
            val a = transport("activate", listOf("license_key" to k, "instance_name" to deviceName(ctx)))
            if (!a.optBoolean("activated")) return friendly(a.optString("error"))
            save(prefs, k, a.optJSONObject("instance")?.optString("id") ?: "", a)
            null
        } catch (e: NoNet) { "No internet connection. Please try again." }
    }

    /** True when the app may open. When false, lic_msg says why (shown on the activation screen). */
    fun ok(prefs: SharedPreferences): Boolean {
        if (!required) return true
        if ((prefs.getString("lic_key", "") ?: "").isBlank()) return false
        if (isOwner(prefs.getString("lic_key", ""))) return true
        val now = clock()
        val exp = prefs.getLong("lic_exp", 0L)
        if (exp in 1 until now) { prefs.edit().putString("lic_msg", "Your plan ended on ${day(exp)}. Renew it, then press Check again.").apply(); return false }
        if (now - prefs.getLong("lic_ok", 0L) >= GRACE_MS) { prefs.edit().putString("lic_msg", "Connect to the internet so 91 TV can check your code.").apply(); return false }
        return true
    }

    /** True when a code is saved on this TV (so the activation screen can offer "Check again"). */
    fun hasKey(prefs: SharedPreferences) = (prefs.getString("lic_key", "") ?: "").isNotBlank()

    /**
     * Blocking online check of the saved code. Returns true when it is valid now.
     * Cancelled, refunded or removed codes are cleared from this TV; expired ones are kept so a renewal works.
     */
    fun refresh(prefs: SharedPreferences): Boolean {
        val key = prefs.getString("lic_key", "") ?: ""; val inst = prefs.getString("lic_inst", "") ?: ""
        if (key.isBlank()) return false
        if (isOwner(key)) return true
        return try {
            val v = transport("validate", listOf("license_key" to key, "instance_id" to inst))
            val status = v.optJSONObject("license_key")?.optString("status")
            when {
                v.optBoolean("valid") && belongs(v) -> { save(prefs, key, inst, v); true }
                !v.has("valid") -> false                                               // odd reply: change nothing
                status == "expired" -> { prefs.edit().putLong("lic_ok", 0L).putString("lic_msg", "Your plan has ended. Renew it, then press Check again.").apply(); false }
                else -> { forget(prefs, "This code was cancelled or removed from this TV. Please enter a valid code."); false }
            }
        } catch (e: NoNet) {
            prefs.edit().putString("lic_msg", "No internet connection. Please try again.").apply(); false
        }
    }

    /** Background re-check at start, at most once a day. */
    fun recheck(prefs: SharedPreferences) {
        if (!required || !hasKey(prefs) || isOwner(prefs.getString("lic_key", "")) || clock() - prefs.getLong("lic_ok", 0L) < RECHECK_MS) return
        Thread { refresh(prefs) }.start()
    }

    /** Blocking. Frees this TV's activation so the code can be used on another device. Null = done. */
    fun deactivate(prefs: SharedPreferences): String? {
        val key = prefs.getString("lic_key", "") ?: ""; val inst = prefs.getString("lic_inst", "") ?: ""
        if (key.isBlank() || isOwner(key)) { forget(prefs, null); return null }
        return try {
            val o = transport("deactivate", listOf("license_key" to key, "instance_id" to inst))
            if (o.optBoolean("deactivated") || "not found" in o.optString("error").lowercase()) { forget(prefs, null); null }
            else friendly(o.optString("error"))
        } catch (e: NoNet) { "No internet connection. Please try again." }
    }

    /** One line for Settings, e.g. "1 Year · until 30 Oct 2027" or "Lifetime". */
    fun summary(prefs: SharedPreferences): String {
        if (!hasKey(prefs)) return "Not activated"
        if (isOwner(prefs.getString("lic_key", ""))) return "Owner · unlimited"
        val plan = (prefs.getString("lic_plan", "") ?: "").ifBlank { "Activated" }
        val exp = prefs.getLong("lic_exp", 0L)
        return if (exp > 0) "$plan · until ${day(exp)}" else if ("lifetime" in plan.lowercase()) plan else "$plan · no end date"
    }
}
