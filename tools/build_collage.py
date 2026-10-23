"""Page 3 collage (assets/p2-collage.jpg): six page photos in two rows with thin dark-green gaps.

    python tools/build_collage.py


Canvas has the page's bleed shape (216x154mm). The outer frame is 3mm bleed + one gap wide, so
after trimming the printed page shows a frame the same width as the gaps between tiles.
"""
import sys
from PIL import Image

from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
assets, out = ROOT / "assets", ROOT / "assets" / "p2-collage.jpg"
W = 2048
H = round(W * 154 / 216)            # 1460
G = 14                              # gap between tiles
P = G + round(W * 3 / 216)          # outer frame: gap + 3mm bleed
BG = (13, 46, 31)
row_h = (H - 2 * P - G) // 2
row_w = W - 2 * P - 2 * G

# (file, tile width, horizontal focus 0–1, vertical focus 0–1, zoom) — top row pages 6, 7, 8; bottom 9, 10, 11
rows = [
    [("school-visit.jpg", 620, 0.43, 0.50, 1.0), ("collage-discussion.jpg", 681, 0.50, 0.50, 1.0),
     ("collage-bookfair.jpg", 635, 0.45, 0.00, 1.2)],
    [("collage-box.jpg", 620, 0.50, 0.52, 1.0), ("exhibition-conversation.jpg", 640, 0.50, 0.40, 1.0),
     ("new-muslims-group.jpg", 676, 0.50, 0.30, 1.0)],
]


def cover(im, tw, th, fx, fy, zoom):
    s = max(tw / im.width, th / im.height) * zoom
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x = min(max(round(im.width * fx - tw / 2), 0), im.width - tw)
    y = min(max(round(im.height * fy - th / 2), 0), im.height - th)
    return im.crop((x, y, x + tw, y + th))


canvas = Image.new("RGB", (W, H), BG)
for r, row in enumerate(rows):
    assert sum(t[1] for t in row) == row_w, (sum(t[1] for t in row), row_w)
    x, y = P, P + r * (row_h + G)
    for name, tw, fx, fy, zoom in row:
        canvas.paste(cover(Image.open(f"{assets}/{name}").convert("RGB"), tw, row_h, fx, fy, zoom), (x, y))
        x += tw + G

canvas.save(out, quality=88, optimize=True)
print(f"saved {out} {canvas.size}; then run tools/build_print_pdf.py to update the PDFs")
