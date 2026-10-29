package com.aurora.tv

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.os.Handler
import android.os.Looper
import android.util.LruCache
import android.widget.ImageView
import java.util.concurrent.Executors

/** Tiny poster/logo loader: background download, size-limited decode, memory cache. */
object Img {
    private val cache = object : LruCache<String, Bitmap>((Runtime.getRuntime().maxMemory() / 1024 / 8).toInt()) {
        override fun sizeOf(key: String, value: Bitmap): Int = value.byteCount / 1024
    }
    private val pool = Executors.newFixedThreadPool(4)
    private val ui = Handler(Looper.getMainLooper())
    private val failed = HashSet<String>()

    private var dir: java.io.File? = null
    /** Posters are kept on disk after the first download, so after a restart the home screen fills instantly instead of waiting for the network. */
    fun init(ctx: android.content.Context) {
        val d = java.io.File(ctx.cacheDir, "img"); d.mkdirs(); dir = d
        Thread {
            try {
                val files = d.listFiles() ?: return@Thread; var total = files.sumOf { it.length() }
                if (total > 250L * 1024 * 1024) for (f in files.sortedBy { it.lastModified() }) { total -= f.length(); f.delete(); if (total < 180L * 1024 * 1024) break }
            } catch (e: Exception) { }
        }.start()
    }
    private fun fileFor(url: String): java.io.File? = dir?.let { java.io.File(it, java.security.MessageDigest.getInstance("MD5").digest(url.toByteArray()).joinToString("") { b -> "%02x".format(b) }) }

    fun load(url: String, iv: ImageView, targetW: Int) {
        iv.tag = url; iv.setImageDrawable(null)
        if (url.isBlank() || !url.startsWith("http")) return
        val hit = cache.get(url)
        if (hit != null) { iv.setImageBitmap(hit); return }
        if (synchronized(failed) { url in failed }) return
        pool.execute {
            try {
                val cf = fileFor(url)
                val data = if (cf != null && cf.exists() && cf.length() > 0) cf.readBytes() else Http.bytes(url).also { b -> try { if (cf != null && b.isNotEmpty()) cf.writeBytes(b) } catch (e: Exception) { } }
                val o = BitmapFactory.Options(); o.inJustDecodeBounds = true
                BitmapFactory.decodeByteArray(data, 0, data.size, o)
                var s = 1; while (o.outWidth / (s * 2) >= targetW * 2) s *= 2
                val o2 = BitmapFactory.Options(); o2.inSampleSize = s; o2.inPreferredConfig = Bitmap.Config.RGB_565      // half the memory and GPU upload of ARGB_8888; fine for posters
                val bm = BitmapFactory.decodeByteArray(data, 0, data.size, o2)
                if (bm != null) { cache.put(url, bm); ui.post { if (iv.tag == url) iv.setImageBitmap(bm) } }
                else synchronized(failed) { failed.add(url) }
            } catch (e: Exception) { synchronized(failed) { failed.add(url) } }
        }
    }
}
