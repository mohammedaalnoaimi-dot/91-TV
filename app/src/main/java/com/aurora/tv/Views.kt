package com.aurora.tv

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Shader
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.view.Gravity
import android.view.View
import android.widget.TextView

// "Dark Luxury Theatre" palette (concept C3)
val ROSE = Color.parseColor("#C9475C")
val RED = ROSE                      // accent colour used all over the app
val BG = Color.parseColor("#070506")
val PANEL = Color.parseColor("#0E080A")
val CARD = Color.parseColor("#18110F")
val GRAY = Color.parseColor("#a8977e")
val MUTED = Color.parseColor("#8f806c")
val CREAM = Color.parseColor("#EBDDC4")
val GOLD = Color.parseColor("#d7b88a")
val SOFT = Color.parseColor("#cdbb9e")

/** Fonts bundled in assets/fonts (Cinzel, Jost, EB Garamond Italic; all SIL Open Font License). */
object Fonts {
    private val cache = HashMap<String, Typeface>()
    fun get(ctx: Context, file: String, fallback: Typeface): Typeface =
        cache.getOrPut(file) { try { Typeface.createFromAsset(ctx.applicationContext.assets, "fonts/$file") } catch (e: Throwable) { fallback } }
}
fun Context.fDisplay(): Typeface = Fonts.get(this, "cinzel.ttf", Typeface.SERIF)
fun Context.fBody(): Typeface = Fonts.get(this, "jost.ttf", Typeface.DEFAULT)
fun Context.fMedium(): Typeface = Fonts.get(this, "jost_medium.ttf", Typeface.DEFAULT_BOLD)
fun Context.fItalic(): Typeface = Fonts.get(this, "garamond_italic.ttf", Typeface.SERIF)

fun Context.dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()

fun Context.rbg(color: Int, stroke: Int = Color.TRANSPARENT, radius: Int = 10, strokeW: Int = 3): GradientDrawable =
    GradientDrawable().apply { cornerRadius = dp(radius).toFloat(); setColor(color); setStroke(dp(strokeW), stroke) }

/** bold = true gives the Cinzel display face, otherwise Jost. */
fun Context.mkText(t: String, sp: Float = 16f, color: Int = CREAM, bold: Boolean = false): TextView =
    TextView(this).apply {
        text = t; textSize = sp; setTextColor(color)
        if (bold) { typeface = fDisplay(); letterSpacing = 0.04f } else typeface = fBody()
    }

fun Context.mkItalic(t: String, sp: Float = 16f, color: Int = GRAY): TextView =
    TextView(this).apply { text = t; textSize = sp; setTextColor(color); typeface = fItalic() }

/** Small heading with a rose line in front, like "—— NEXT PRAYER". */
fun Context.eyebrow(t: String): android.widget.LinearLayout =
    android.widget.LinearLayout(this).apply {
        orientation = android.widget.LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL
        addView(View(context).apply { setBackgroundColor(ROSE) }, android.widget.LinearLayout.LayoutParams(dp(24), dp(1)).apply { rightMargin = dp(10) })
        addView(mkText(t, 10f, GOLD, true).apply { letterSpacing = 0.34f })
    }

/** Square-cornered button: cream = primary, outlined = secondary. Bright ring and a slight zoom while focused. */
fun Context.mkButton(label: String, primary: Boolean, onClick: () -> Unit): TextView {
    val fill = if (primary) CREAM else Color.parseColor("#8C140A0C")
    val ink = if (primary) Color.parseColor("#160B0D") else CREAM
    val edge = if (primary) CREAM else Color.parseColor("#7A6250")
    return TextView(this).apply {
        text = label.uppercase(); textSize = 14f; setTextColor(ink); typeface = fDisplay(); letterSpacing = 0.14f; gravity = Gravity.CENTER
        setPadding(dp(22), dp(13), dp(22), dp(13)); isFocusable = true; isClickable = true
        background = rbg(fill, edge, 2, 1)
        setOnFocusChangeListener { v, f ->
            v.background = rbg(if (f && !primary) Color.parseColor("#33EBDDC4") else fill, if (f) Color.WHITE else edge, 2, if (f) 3 else 1)
            v.animate().scaleX(if (f) 1.05f else 1f).scaleY(if (f) 1.05f else 1f).setDuration(110).start()
        }
        setOnClickListener { onClick() }
    }
}

fun hueColor(name: String, s: Float = 0.35f, v: Float = 0.24f): Int =
    Color.HSVToColor(floatArrayOf((Math.abs(name.hashCode()) % 360).toFloat(), s, v))

/** Thin progress bar (programme progress). */
class Bar(ctx: Context) : View(ctx) {
    private val back = Paint().apply { color = Color.parseColor("#33EBDDC4") }
    private val front = Paint().apply { color = RED }
    var frac = 0f
        set(v) { field = v.coerceIn(0f, 1f); invalidate() }
    override fun onDraw(c: Canvas) {
        c.drawRect(0f, 0f, width.toFloat(), height.toFloat(), back)
        c.drawRect(0f, 0f, width * frac, height.toFloat(), front)
    }
}

/** Night sky with stars and a crescent, behind the prayer-times screen. */
class NightView(ctx: Context) : View(ctx) {
    private val p = Paint(Paint.ANTI_ALIAS_FLAG)
    private val stars = FloatArray(90).also { a -> val r = java.util.Random(7); for (i in a.indices) a[i] = r.nextFloat() }
    override fun onDraw(c: Canvas) {
        val w = width.toFloat(); val h = height.toFloat()
        p.shader = LinearGradient(0f, 0f, 0f, h,
            intArrayOf(Color.parseColor("#0A0C16"), Color.parseColor("#141A2A"), Color.parseColor("#3A2228"), Color.parseColor("#120709")),
            floatArrayOf(0f, 0.45f, 0.8f, 1f), Shader.TileMode.CLAMP)
        c.drawRect(0f, 0f, w, h, p); p.shader = null
        p.color = Color.parseColor("#E8E2D6")
        for (i in 0 until 45) c.drawCircle(stars[i * 2] * w, stars[i * 2 + 1] * h * 0.55f, 1.2f + (i % 3) * 0.6f, p)
        val cx = w * 0.82f; val cy = h * 0.2f; val r = h * 0.07f
        p.color = Color.parseColor("#EFE2C4"); c.drawCircle(cx, cy, r, p)
        p.color = Color.parseColor("#10142A"); c.drawCircle(cx + r * 0.45f, cy - r * 0.2f, r * 0.9f, p)
        p.shader = LinearGradient(0f, 0f, w * 0.6f, 0f, Color.parseColor("#E6070506"), Color.TRANSPARENT, Shader.TileMode.CLAMP)
        c.drawRect(0f, 0f, w, h, p); p.shader = null
    }
}

/** Top menu entry: Cinzel caps, rose underline while selected or focused. */
class NavItem(ctx: Context, label: String) : TextView(ctx) {
    private val line = Paint().apply { color = ROSE }
    var sel = false
        set(v) { field = v; refresh() }
    init {
        text = label; textSize = 13f; typeface = ctx.fDisplay(); letterSpacing = 0.16f; isFocusable = true; isClickable = true
        setPadding(ctx.dp(14), ctx.dp(10), ctx.dp(14), ctx.dp(12)); gravity = Gravity.CENTER
        setOnFocusChangeListener { _, _ -> refresh() }
        refresh()
    }
    private fun refresh() { setTextColor(if (sel || isFocused) CREAM else GRAY); invalidate() }
    override fun onDraw(c: Canvas) {
        super.onDraw(c)
        if (sel || isFocused) {
            val h = if (isFocused) 3f else 2f
            c.drawRect(paddingLeft.toFloat(), height - h - 2f, width - paddingRight.toFloat(), height - 2f, line)
        }
    }
}
