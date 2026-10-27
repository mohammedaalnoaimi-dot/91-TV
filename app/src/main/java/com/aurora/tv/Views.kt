package com.aurora.tv

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.view.Gravity
import android.view.View
import android.widget.TextView

val RED = Color.parseColor("#E50914")
val BG = Color.parseColor("#0A0A0D")
val PANEL = Color.parseColor("#14141A")
val CARD = Color.parseColor("#1B1B22")
val GRAY = Color.parseColor("#9A9AA6")

fun Context.dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()

fun Context.rbg(color: Int, stroke: Int = Color.TRANSPARENT, radius: Int = 10, strokeW: Int = 3): GradientDrawable =
    GradientDrawable().apply { cornerRadius = dp(radius).toFloat(); setColor(color); setStroke(dp(strokeW), stroke) }

fun Context.mkText(t: String, sp: Float = 16f, color: Int = Color.WHITE, bold: Boolean = false): TextView =
    TextView(this).apply { text = t; textSize = sp; setTextColor(color); if (bold) typeface = Typeface.DEFAULT_BOLD }

/** Focusable pill button (red = primary). Gets a white ring and a slight zoom while focused. */
fun Context.mkButton(label: String, primary: Boolean, onClick: () -> Unit): TextView {
    val base = if (primary) RED else Color.parseColor("#2A2A33")
    return TextView(this).apply {
        text = label; textSize = 18f; setTextColor(Color.WHITE); typeface = Typeface.DEFAULT_BOLD; gravity = Gravity.CENTER
        setPadding(dp(26), dp(12), dp(26), dp(12)); isFocusable = true; isClickable = true
        background = rbg(base, Color.TRANSPARENT, 8)
        setOnFocusChangeListener { v, f ->
            v.background = rbg(base, if (f) Color.WHITE else Color.TRANSPARENT, 8)
            v.animate().scaleX(if (f) 1.06f else 1f).scaleY(if (f) 1.06f else 1f).setDuration(110).start()
        }
        setOnClickListener { onClick() }
    }
}

fun hueColor(name: String, s: Float = 0.35f, v: Float = 0.24f): Int =
    Color.HSVToColor(floatArrayOf((Math.abs(name.hashCode()) % 360).toFloat(), s, v))

/** Thin progress bar (programme progress). */
class Bar(ctx: Context) : View(ctx) {
    private val back = Paint().apply { color = Color.parseColor("#33FFFFFF") }
    private val front = Paint().apply { color = RED }
    var frac = 0f
        set(v) { field = v.coerceIn(0f, 1f); invalidate() }
    override fun onDraw(c: Canvas) {
        c.drawRect(0f, 0f, width.toFloat(), height.toFloat(), back)
        c.drawRect(0f, 0f, width * frac, height.toFloat(), front)
    }
}
