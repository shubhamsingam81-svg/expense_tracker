"""Generate PWA icons for the Expense Tracker app."""
from PIL import Image, ImageDraw, ImageFont
import os

ICON_DIR = os.path.join(os.path.dirname(__file__), 'icons')
os.makedirs(ICON_DIR, exist_ok=True)

def create_icon(size, path):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background circle with gradient effect
    margin = int(size * 0.02)
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=int(size * 0.22),
        fill=(26, 26, 46)
    )

    # Inner accent circle
    cx, cy = size // 2, size // 2
    r = int(size * 0.3)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(108, 99, 255))

    # Dollar/rupee symbol
    font_size = int(size * 0.35)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    text = "₹"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2 - int(size * 0.02)), text, fill='white', font=font)

    img.save(path, 'PNG')
    print(f"Created: {path}")

create_icon(192, os.path.join(ICON_DIR, 'icon-192.png'))
create_icon(512, os.path.join(ICON_DIR, 'icon-512.png'))
print("Done!")
