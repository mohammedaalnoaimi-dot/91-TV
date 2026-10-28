package com.aurora.tv

import android.content.Context
import java.io.File

/** Disk cache of the channel / movie / series lists so the app opens instantly. */
object Cache {
    private fun file(ctx: Context, name: String) = File(ctx.cacheDir, "list_$name.tsv")
    private fun clean(s: String) = s.replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')

    fun save(ctx: Context, name: String, items: List<Item>) {
        try {
            val tmp = File(ctx.cacheDir, "list_$name.tmp")
            tmp.bufferedWriter().use { w ->
                for (it in items) { w.write(clean(it.name)); w.write("\t"); w.write(clean(it.url)); w.write("\t"); w.write(clean(it.group)); w.write("\t")
                    w.write(it.kind); w.write("\t"); w.write(clean(it.id)); w.write("\t"); w.write(clean(it.logo)); w.write("\t"); w.write(it.added.toString()); w.write("\t"); w.write(it.rating.toString()); w.write("\n") }
            }
            tmp.renameTo(file(ctx, name))
        } catch (e: Exception) { }
    }

    fun load(ctx: Context, name: String): List<Item>? {
        val f = file(ctx, name); if (!f.exists()) return null
        return try {
            val out = ArrayList<Item>()
            f.bufferedReader().useLines { lines ->
                for (line in lines) { val p = line.split('\t'); if (p.size >= 6) out.add(Item(p[0], p[1], p[2], p[3], p[4], p[5], p.getOrNull(6)?.toLongOrNull() ?: 0L, p.getOrNull(7)?.toFloatOrNull() ?: 0f)) }
            }
            out
        } catch (e: Exception) { null }
    }

    fun ageHours(ctx: Context, name: String): Long { val f = file(ctx, name); return if (f.exists()) (System.currentTimeMillis() - f.lastModified()) / 3_600_000L else Long.MAX_VALUE }
    fun clear(ctx: Context) { ctx.cacheDir.listFiles()?.filter { it.name.startsWith("list_") }?.forEach { it.delete() } }
}
