"""Generates assets/aurora.ico + aurora.png (dev-time only; needs Pillow)."""
from PIL import Image, ImageDraw, ImageFont
import os
S = 512
img = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
d.rounded_rectangle((16, 16, S - 16, S - 16), 110, fill=(8, 8, 10, 255), outline=(224, 38, 45, 255), width=14)
for i in range(60):   # soft red glow ring
    d.arc((60 - i // 3, 60 - i // 3, S - 60 + i // 3, S - 60 + i // 3), 200, 340, fill=(224, 38, 45, max(0, 120 - i * 2)), width=2)
font = None
for f in ("arialbd.ttf", "DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
    try: font = ImageFont.truetype(f, 330); break
    except OSError: pass
font = font or ImageFont.load_default()
d.text((S / 2, S / 2 + 10), "A", fill=(242, 242, 244, 255), font=font, anchor="mm")
d.polygon([(S * 0.62, S * 0.62), (S * 0.62, S * 0.86), (S * 0.82, S * 0.74)], fill=(224, 38, 45, 255))
os.makedirs("assets", exist_ok=True)
img.save("assets/aurora.png")
img.save("assets/aurora.ico", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
print("icons written")
