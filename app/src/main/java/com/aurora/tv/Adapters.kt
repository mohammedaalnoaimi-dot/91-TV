package com.aurora.tv

import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.text.TextUtils
import android.view.Gravity
import android.view.ViewGroup
import android.view.ViewOutlineProvider
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView

/** Category chips (horizontal) or category list entries (vertical). */
class ChipAdapter(
    private val a: MainActivity, var labels: List<String>, var sel: Int, private val vertical: Boolean,
    private val onPick: (Int) -> Unit, private val onLong: (Int) -> Unit
) : RecyclerView.Adapter<ChipAdapter.VH>() {
    class VH(val tv: TextView) : RecyclerView.ViewHolder(tv)
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val tv = TextView(a).apply {
            textSize = if (vertical) 17f else 16f; setTextColor(Color.WHITE); isFocusable = true; maxLines = 1; ellipsize = TextUtils.TruncateAt.END
            setPadding(a.dp(16), a.dp(10), a.dp(16), a.dp(10))
            layoutParams = RecyclerView.LayoutParams(if (vertical) -1 else -2, -2).apply { setMargins(a.dp(3), a.dp(3), a.dp(3), a.dp(3)) }
        }
        return VH(tv)
    }
    override fun getItemCount() = labels.size
    override fun onBindViewHolder(h: VH, position: Int) {
        val r = if (vertical) 10 else 24
        fun paint(focused: Boolean) {
            val selected = position == sel
            h.tv.background = a.rbg(if (focused) Color.parseColor("#33E50914") else if (selected) Color.parseColor("#26FFFFFF") else Color.TRANSPARENT,
                if (focused) RED else if (selected && vertical) Color.parseColor("#55E50914") else Color.TRANSPARENT, r, 2)
            h.tv.setTextColor(if (selected || focused) Color.WHITE else Color.parseColor("#B5B5C0"))
        }
        h.tv.text = labels[position]; paint(false)
        h.tv.setOnFocusChangeListener { _, f -> paint(f) }
        h.tv.setOnClickListener { sel = h.adapterPosition; notifyDataSetChanged(); onPick(sel) }
        h.tv.setOnLongClickListener { onLong(h.adapterPosition); true }
    }
}

/** Portrait poster card with the title underneath (home rows, movies/series/my-list grids). */
class PosterAdapter(
    private val a: MainActivity, var items: List<Item>,
    private val onPick: (List<Item>, Int) -> Unit, private val onLong: (Item) -> Unit
) : RecyclerView.Adapter<PosterAdapter.VH>() {
    class VH(val cell: LinearLayout, val img: ImageView, val ini: TextView, val label: TextView, val bg: GradientDrawable) : RecyclerView.ViewHolder(cell)
    override fun getItemCount() = items.size
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val bg = a.rbg(CARD, Color.TRANSPARENT, 12, 3)
        val cell = LinearLayout(a).apply {
            orientation = LinearLayout.VERTICAL; isFocusable = true
            layoutParams = RecyclerView.LayoutParams(a.dp(150), -2).apply { setMargins(a.dp(7), a.dp(7), a.dp(7), a.dp(7)) }
        }
        val box = FrameLayout(a).apply { background = bg; clipToOutline = true; outlineProvider = ViewOutlineProvider.BACKGROUND }
        val ini = TextView(a).apply { setTextColor(Color.parseColor("#CCFFFFFF")); textSize = 15f; gravity = Gravity.CENTER; setPadding(a.dp(10), 0, a.dp(10), 0); maxLines = 4 }
        box.addView(ini, FrameLayout.LayoutParams(-1, -1))
        val img = ImageView(a); box.addView(img, FrameLayout.LayoutParams(-1, -1))
        cell.addView(box, LinearLayout.LayoutParams(a.dp(150), a.dp(225)))
        val label = TextView(a).apply { setTextColor(Color.WHITE); textSize = 13f; maxLines = 2; ellipsize = TextUtils.TruncateAt.END; setPadding(a.dp(2), a.dp(6), a.dp(2), 0) }
        cell.addView(label, LinearLayout.LayoutParams(-1, -2))
        cell.setOnFocusChangeListener { v, f ->
            v.animate().scaleX(if (f) 1.07f else 1f).scaleY(if (f) 1.07f else 1f).setDuration(120).start()
            v.elevation = if (f) 24f else 0f
            bg.setStroke(a.dp(3), if (f) RED else Color.TRANSPARENT)
        }
        return VH(cell, img, ini, label, bg)
    }
    override fun onBindViewHolder(h: VH, position: Int) {
        val it = items[position]
        h.label.text = it.name
        h.bg.setColor(hueColor(it.name))
        val live = it.kind == "live"
        h.img.scaleType = if (live) ImageView.ScaleType.FIT_CENTER else ImageView.ScaleType.CENTER_CROP
        h.img.setPadding(if (live) a.dp(18) else 0, if (live) a.dp(18) else 0, if (live) a.dp(18) else 0, if (live) a.dp(18) else 0)
        h.ini.text = if (it.logo.isBlank()) it.name else ""
        Img.load(it.logo, h.img, a.dp(150))
        h.cell.setOnClickListener { onPick(items, h.adapterPosition) }
        h.cell.setOnLongClickListener { onLong(items[h.adapterPosition]); true }
    }
}

/** Live channel row: number, logo tile, name, now-playing + progress. */
class ChannelAdapter(
    private val a: MainActivity, var items: List<Item>,
    private val onFocus: (Item) -> Unit, private val onOpen: (List<Item>, Int) -> Unit, private val onLong: (Item) -> Unit
) : RecyclerView.Adapter<ChannelAdapter.VH>() {
    class VH(val row: LinearLayout, val num: TextView, val tile: FrameLayout, val img: ImageView, val ini: TextView,
             val name: TextView, val sub: TextView, val bar: Bar) : RecyclerView.ViewHolder(row)
    override fun getItemCount() = items.size
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val row = LinearLayout(a).apply {
            orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; isFocusable = true
            setPadding(a.dp(12), a.dp(8), a.dp(12), a.dp(8))
            layoutParams = RecyclerView.LayoutParams(-1, a.dp(72)).apply { setMargins(0, a.dp(3), 0, a.dp(3)) }
        }
        val num = TextView(a).apply { setTextColor(Color.parseColor("#8A8A96")); textSize = 15f; gravity = Gravity.CENTER }
        row.addView(num, LinearLayout.LayoutParams(a.dp(44), -2))
        val tile = FrameLayout(a).apply { background = a.rbg(Color.parseColor("#22222A"), Color.TRANSPARENT, 8); clipToOutline = true; outlineProvider = ViewOutlineProvider.BACKGROUND }
        val ini = TextView(a).apply { setTextColor(Color.parseColor("#88FFFFFF")); textSize = 15f; gravity = Gravity.CENTER; typeface = android.graphics.Typeface.DEFAULT_BOLD }
        tile.addView(ini, FrameLayout.LayoutParams(-1, -1))
        val img = ImageView(a).apply { scaleType = ImageView.ScaleType.FIT_CENTER; setPadding(a.dp(5), a.dp(5), a.dp(5), a.dp(5)) }
        tile.addView(img, FrameLayout.LayoutParams(-1, -1))
        row.addView(tile, LinearLayout.LayoutParams(a.dp(54), a.dp(54)).apply { setMargins(0, 0, a.dp(14), 0) })
        val col = LinearLayout(a).apply { orientation = LinearLayout.VERTICAL }
        val name = TextView(a).apply { setTextColor(Color.WHITE); textSize = 17f; typeface = android.graphics.Typeface.DEFAULT_BOLD; maxLines = 1; ellipsize = TextUtils.TruncateAt.END }
        val sub = TextView(a).apply { setTextColor(GRAY); textSize = 13f; maxLines = 1; ellipsize = TextUtils.TruncateAt.END }
        val bar = Bar(a)
        col.addView(name); col.addView(sub); col.addView(bar, LinearLayout.LayoutParams(-1, a.dp(3)).apply { topMargin = a.dp(5) })
        row.addView(col, LinearLayout.LayoutParams(0, -2, 1f))
        row.setOnFocusChangeListener { v, f -> v.background = a.rbg(if (f) Color.parseColor("#26E50914") else Color.parseColor("#12FFFFFF"), if (f) RED else Color.TRANSPARENT, 10, 2) }
        row.background = a.rbg(Color.parseColor("#12FFFFFF"), Color.TRANSPARENT, 10, 2)
        return VH(row, num, tile, img, ini, name, sub, bar)
    }
    override fun onBindViewHolder(h: VH, position: Int) {
        val it = items[position]
        h.num.text = "${position + 1}"; h.name.text = it.name; h.sub.text = it.group; h.bar.frac = 0f
        h.ini.text = it.name.take(2).uppercase(); Img.load(it.logo, h.img, a.dp(54)); h.row.tag = it.key
        a.epgFor(it, false) { list ->
            if (h.row.tag == it.key) {
                val now = a.nowOf(list)
                if (now != null) { h.sub.text = now.title; h.bar.frac = (System.currentTimeMillis() / 1000 - now.start).toFloat() / maxOf(1L, now.end - now.start) }
            }
        }
        h.row.setOnFocusChangeListener { v, f ->
            v.background = a.rbg(if (f) Color.parseColor("#26E50914") else Color.parseColor("#12FFFFFF"), if (f) RED else Color.TRANSPARENT, 10, 2)
            if (f) onFocus(it)
        }
        h.row.setOnClickListener { onOpen(items, h.adapterPosition) }
        h.row.setOnLongClickListener { onLong(items[h.adapterPosition]); true }
    }
}
