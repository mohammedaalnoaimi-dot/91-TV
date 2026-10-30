package com.aurora.tv

import android.content.Context
import android.content.SharedPreferences
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/**
 * Activation by code (Lemon Squeezy license keys: no secret is stored in the app).
 * Switched OFF until the shop exists: set REQUIRED = true and PRODUCT_ID to the number of the product, then build.
 */
object Lic {
    const val REQUIRED = false
    const val PRODUCT_ID = 0            // the Lemon Squeezy product number; keys of other products are refused
    private const val RECHECK_MS = 7L * 24 * 3600 * 1000
    private const val GRACE_MS = 14L * 24 * 3600 * 1000
    private const val API = "https://api.lemonsqueezy.com/v1/licenses/"

    private fun post(path: String, vararg kv: Pair<String, String>): JSONObject {
        val body = kv.joinToString("&") { URLEncoder.encode(it.first, "UTF-8") + "=" + URLEncoder.encode(it.second, "UTF-8") }
        val c = URL(API + path).openConnection() as HttpURLConnection
        c.requestMethod = "POST"; c.doOutput = true; c.connectTimeout = 10000; c.readTimeout = 15000
        c.setRequestProperty("Accept", "application/json"); c.setRequestProperty("Content-Type", "application/x-www-form-urlencoded")
        c.outputStream.use { it.write(body.toByteArray()) }
        val code = c.responseCode
        val txt = (if (code in 200..299) c.inputStream else c.errorStream)?.bufferedReader()?.use { it.readText() } ?: "{}"
        c.disconnect()
        return try { JSONObject(txt) } catch (e: Exception) { JSONObject() }
    }

    private fun deviceName(ctx: Context): String =
        android.os.Build.MODEL + " " + (android.provider.Settings.Secure.getString(ctx.contentResolver, android.provider.Settings.Secure.ANDROID_ID) ?: "").takeLast(6)

    /** Blocking. Returns null when activated, otherwise the message to show. */
    fun activate(ctx: Context, prefs: SharedPreferences, key: String): String? {
        if (key.length < 8) return "Please type the full code"
        return try {
            val o = post("activate", "license_key" to key, "instance_name" to deviceName(ctx))
            if (o.optBoolean("activated")) {
                val pid = o.optJSONObject("meta")?.optInt("product_id", -1) ?: -1
                if (PRODUCT_ID != 0 && pid != PRODUCT_ID) return "This code is not for 91 TV"
                prefs.edit().putString("lic_key", key).putString("lic_inst", o.optJSONObject("instance")?.optString("id") ?: "")
                    .putLong("lic_ok", System.currentTimeMillis()).apply()
                null
            } else o.optString("error").ifBlank { "Code not accepted" }
        } catch (e: Exception) { "No internet connection. Please try again." }
    }

    /** True when the app may open. Re-checks online every 7 days and still works offline for 14 days. */
    fun ok(prefs: SharedPreferences): Boolean {
        if (!REQUIRED) return true
        val key = prefs.getString("lic_key", "") ?: ""; if (key.isBlank()) return false
        val last = prefs.getLong("lic_ok", 0L); val now = System.currentTimeMillis()
        return now - last < GRACE_MS
    }

    /** Background re-check (call at start). Cancelled or refunded codes stop working after the grace period. */
    fun recheck(prefs: SharedPreferences) {
        if (!REQUIRED) return
        val key = prefs.getString("lic_key", "") ?: ""; val inst = prefs.getString("lic_inst", "") ?: ""
        if (key.isBlank() || System.currentTimeMillis() - prefs.getLong("lic_ok", 0L) < RECHECK_MS) return
        Thread {
            try {
                val o = post("validate", "license_key" to key, "instance_id" to inst)
                if (o.optBoolean("valid")) prefs.edit().putLong("lic_ok", System.currentTimeMillis()).apply()
                else if (o.has("valid")) prefs.edit().putLong("lic_ok", 0L).apply()      // refused (cancelled / refunded)
            } catch (e: Exception) { }
        }.start()
    }
}
