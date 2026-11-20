package com.aurora.tv

import android.view.ViewOutlineProvider
import android.graphics.drawable.LayerDrawable
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
    GradientDrawable().apply { cornerRadius = dp(radius).toFloat(); setColor(color); setStroke(dp(strokeW), stroke); setDither(true) }

/** Gradient with dithering on, so dark fades stay smooth on OLED / 4K panels instead of showing bands. */
fun dgrad(o: GradientDrawable.Orientation, c: IntArray): GradientDrawable = GradientDrawable(o, c).apply { setDither(true) }

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
    val surf = Surface(this, fill, 3, true, if (primary) Color.WHITE else CREAM, 2f)
    return TextView(this).apply {
        text = label.uppercase(); textSize = 14f; setTextColor(ink); typeface = fDisplay(); letterSpacing = 0.14f; gravity = Gravity.CENTER
        setPadding(dp(22), dp(13), dp(22), dp(13)); isFocusable = true; isClickable = true
        background = LayerDrawable(arrayOf(surf, rbg(Color.TRANSPARENT, edge, 3, 1)))
        outlineProvider = ViewOutlineProvider.BACKGROUND
        setOnFocusChangeListener { v, f ->
            surf.setColor(if (f && !primary) Color.parseColor("#33EBDDC4") else fill); surf.setFocused(f)
            v.animate().scaleX(if (f) 1.04f else 1f).scaleY(if (f) 1.04f else 1f).setDuration(130).setInterpolator(android.view.animation.DecelerateInterpolator()).start()
            if (primary) v.lift(f)
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
    private val pill = Surface(ctx, Color.TRANSPARENT, 22, true, Color.parseColor("#66EBDDC4"), 1f, false)
    var sel = false
        set(v) { field = v; refresh() }
    init {
        text = label; textSize = 15f; typeface = ctx.fDisplay(); letterSpacing = 0.2f; isFocusable = true; isClickable = true
        setPadding(ctx.dp(18), ctx.dp(10), ctx.dp(18), ctx.dp(13)); gravity = Gravity.CENTER
        setOnFocusChangeListener { _, _ -> refresh() }
        refresh()
    }
    private fun refresh() {
        setTextColor(if (sel || isFocused) CREAM else GRAY)
        background = pill; pill.setColor(if (isFocused) Color.parseColor("#1AEBDDC4") else Color.TRANSPARENT); pill.setFocused(isFocused)
        invalidate()
    }
    override fun onDraw(c: Canvas) {
        super.onDraw(c)
        if (sel || isFocused) {
            val h = if (isFocused) 3f else 2f
            line.shader = android.graphics.LinearGradient(paddingLeft.toFloat(), 0f, width - paddingRight.toFloat(), 0f, intArrayOf(ROSE, GOLD), null, android.graphics.Shader.TileMode.CLAMP)
            c.drawRect(paddingLeft.toFloat(), height - h - 3f, width - paddingRight.toFloat(), height - 3f, line)
        }
    }
}


/** A very short, soft synthetic click for moving between tiles. Generated in code (no audio file), plays at low volume and never blocks. */
object Click {
    private var track: android.media.AudioTrack? = null
    private var last = 0L
    fun init() {
        try {
            val rate = 22050; val n = rate * 28 / 1000; val pcm = ShortArray(n)
            for (i in 0 until n) { val env = Math.exp(-i / (n * 0.22)); pcm[i] = (Math.sin(2 * Math.PI * 1500.0 * i / rate) * env * 9000).toInt().toShort() }
            val t = android.media.AudioTrack.Builder()
                .setAudioAttributes(android.media.AudioAttributes.Builder().setUsage(android.media.AudioAttributes.USAGE_ASSISTANCE_SONIFICATION).setContentType(android.media.AudioAttributes.CONTENT_TYPE_SONIFICATION).build())
                .setAudioFormat(android.media.AudioFormat.Builder().setEncoding(android.media.AudioFormat.ENCODING_PCM_16BIT).setSampleRate(rate).setChannelMask(android.media.AudioFormat.CHANNEL_OUT_MONO).build())
                .setBufferSizeInBytes(n * 2).setTransferMode(android.media.AudioTrack.MODE_STATIC).build()
            t.write(pcm, 0, n); t.setVolume(0.35f); track = t
        } catch (e: Throwable) { track = null }
    }
    fun tick() {
        val now = System.currentTimeMillis(); if (now - last < 70) return; last = now
        try { track?.let { it.stop(); it.reloadStaticData(); it.play() } } catch (e: Throwable) { }
    }
}

/** Small outlined quality tag (4K, DV, HDR ...) drawn inline in a TextView. */
class BadgeSpan(private val color: Int, private val density: Float) : android.text.style.ReplacementSpan() {
    private fun pad() = 5f * density
    private fun gap() = 5f * density
    override fun getSize(paint: Paint, text: CharSequence, start: Int, end: Int, fm: Paint.FontMetricsInt?): Int {
        val p = Paint(paint).apply { textSize = paint.textSize * 0.86f }
        return (p.measureText(text, start, end) + pad() * 2 + gap()).toInt()
    }
    override fun draw(canvas: Canvas, text: CharSequence, start: Int, end: Int, x: Float, top: Int, y: Int, bottom: Int, paint: Paint) {
        val p = Paint(paint).apply { textSize = paint.textSize * 0.86f; this.color = this@BadgeSpan.color; isAntiAlias = true }
        val w = p.measureText(text, start, end)
        val fm = p.fontMetrics
        val t = y + fm.ascent - 2f * density; val b = y + fm.descent + 2f * density
        val box = Paint().apply { isAntiAlias = true; style = Paint.Style.STROKE; strokeWidth = 1.2f * density; this.color = this@BadgeSpan.color; alpha = 190 }
        canvas.drawRoundRect(x + 0.6f * density, t, x + w + pad() * 2 - 0.6f * density, b, 3f * density, 3f * density, box)
        canvas.drawText(text, start, end, x + pad(), y.toFloat(), p)
    }
}


/**
 * Premium surface: a rounded body with a faint top-lit sheen, a hairline edge that catches light on top,
 * and a soft focus ring that fades in and out. No blur filters or bitmaps (cheap on TV GPUs); all paints are reused.
 * fill=false draws only the edge and focus layer, so it can sit as a foreground over a poster image.
 */
class Surface(private val ctx: Context, color: Int, private val radiusDp: Int = 8, private val fill: Boolean = true,
              private val ringColor: Int = CREAM, private val ringDp: Float = 2f, private val edge: Boolean = true) : android.graphics.drawable.Drawable() {
    private var body = color
    private val rect = android.graphics.RectF()
    private val pBody = Paint(Paint.ANTI_ALIAS_FLAG)
    private val pSheen = Paint(Paint.ANTI_ALIAS_FLAG)
    private val pEdge = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE }
    private val pRing = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE }
    private val pGlow = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE }
    private val d = ctx.resources.displayMetrics.density
    private var shaderH = -1
    var focus = 0f
        private set
    private var anim: android.animation.ValueAnimator? = null

    fun setColor(c: Int) { if (c != body) { body = c; invalidateSelf() } }
    fun setFocused(f: Boolean, animate: Boolean = true) {
        anim?.cancel()
        val to = if (f) 1f else 0f
        if (!animate) { focus = to; invalidateSelf(); return }
        anim = android.animation.ValueAnimator.ofFloat(focus, to).apply {
            duration = if (f) 150L else 120L; interpolator = android.view.animation.DecelerateInterpolator()
            addUpdateListener { focus = it.animatedValue as Float; invalidateSelf() }; start()
        }
    }
    override fun onBoundsChange(b: android.graphics.Rect) {
        if (b.height() != shaderH) {
            shaderH = b.height(); val h = b.height().toFloat()
            pSheen.shader = LinearGradient(0f, 0f, 0f, h, intArrayOf(Color.argb(20, 255, 240, 220), Color.TRANSPARENT, Color.argb(34, 0, 0, 0)), floatArrayOf(0f, 0.5f, 1f), Shader.TileMode.CLAMP)
            pEdge.shader = LinearGradient(0f, 0f, 0f, h, intArrayOf(Color.argb(60, 255, 240, 220), Color.argb(14, 255, 240, 220), Color.argb(26, 255, 240, 220)), floatArrayOf(0f, 0.45f, 1f), Shader.TileMode.CLAMP)
        }
    }
    override fun draw(c: Canvas) {
        val r = radiusDp * d
        rect.set(bounds)
        if (fill) {
            pBody.color = body; c.drawRoundRect(rect, r, r, pBody)
            if (Color.alpha(body) > 110) c.drawRoundRect(rect, r, r, pSheen)   // sheen only on solid surfaces, never on see-through ones (keeps text clean)
        }
        if (edge) { val hw = maxOf(1f, d * 0.75f); pEdge.strokeWidth = hw
            rect.inset(hw / 2, hw / 2); c.drawRoundRect(rect, r, r, pEdge) }
        if (focus > 0.01f) {
            val w = ringDp * d
            pGlow.strokeWidth = w * 3f; pGlow.color = Color.argb((46 * focus).toInt(), 201, 71, 92)
            rect.set(bounds); rect.inset(w * 1.5f, w * 1.5f); c.drawRoundRect(rect, r, r, pGlow)
            pRing.strokeWidth = w; pRing.color = Color.argb((Color.alpha(ringColor) * focus).toInt(), Color.red(ringColor), Color.green(ringColor), Color.blue(ringColor))
            rect.set(bounds); rect.inset(w / 2, w / 2); c.drawRoundRect(rect, r, r, pRing)
        }
    }
    override fun getOutline(o: android.graphics.Outline) { o.setRoundRect(bounds, radiusDp * d) }
    override fun setAlpha(a: Int) {}
    override fun setColorFilter(cf: android.graphics.ColorFilter?) {}
    @Suppress("OVERRIDE_DEPRECATION") override fun getOpacity() = android.graphics.PixelFormat.TRANSLUCENT
}

/** Gentle raise-on-focus using the GPU's own shadow (a faint rose-warm spot shadow on API 28+). */
fun View.lift(on: Boolean, fast: Boolean = false) {
    if (android.os.Build.VERSION.SDK_INT >= 28) { outlineSpotShadowColor = Color.argb(200, 201, 71, 92); outlineAmbientShadowColor = Color.argb(90, 0, 0, 0) }
    val z = resources.displayMetrics.density * if (on) 12f else 0f
    if (fast) { animate().cancel(); translationZ = z } else animate().translationZ(z).setDuration(150).start()
}

/** Very faint warm light from the upper left on the main background. Drawn once, dithered. */
class AmbientBg : android.graphics.drawable.Drawable() {
    private val p = Paint(Paint.ANTI_ALIAS_FLAG).apply { isDither = true }
    override fun onBoundsChange(b: android.graphics.Rect) {
        p.shader = android.graphics.RadialGradient(b.width() * 0.18f, -b.height() * 0.05f, b.width() * 0.85f,
            intArrayOf(Color.parseColor("#150D0F"), Color.parseColor("#0A0708"), BG), floatArrayOf(0f, 0.55f, 1f), Shader.TileMode.CLAMP)
    }
    override fun draw(c: Canvas) { c.drawRect(bounds.left.toFloat(), bounds.top.toFloat(), bounds.right.toFloat(), bounds.bottom.toFloat(), p) }
    override fun setAlpha(a: Int) {}
    override fun setColorFilter(cf: android.graphics.ColorFilter?) {}
    @Suppress("OVERRIDE_DEPRECATION") override fun getOpacity() = android.graphics.PixelFormat.OPAQUE
}


/** Sets a Surface as this view's background and drives its focus ring. rest = optional always-visible outline. */
fun View.premium(base: Int, focusFill: Int = base, radius: Int = 8, rest: Int = Color.TRANSPARENT, ring: Int = RED, ringDp: Float = 1.5f,
                 edge: Boolean = true, extra: ((Boolean) -> Unit)? = null) {
    val s = Surface(context, base, radius, true, ring, ringDp, edge)
    background = if (rest != Color.TRANSPARENT) LayerDrawable(arrayOf(context.rbg(Color.TRANSPARENT, rest, radius, 1), s)) else s
    setOnFocusChangeListener { _, f -> s.setColor(if (f) focusFill else base); s.setFocused(f); extra?.invoke(f) }
}

/** Panel / popup / dialog body: solid surface with sheen + hairline edge, plus an optional always-visible outline. */
fun Context.panelBg(color: Int, radius: Int, rest: Int = Color.TRANSPARENT): android.graphics.drawable.Drawable {
    val s = Surface(this, color, radius)
    return if (rest != Color.TRANSPARENT) LayerDrawable(arrayOf(rbg(Color.TRANSPARENT, rest, radius, 1), s)) else s
}
